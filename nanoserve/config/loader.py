"""Framework: the server config file format and its loader (M5).

    cfg = load_config("nanoserve/config/examples/server.conf")   # or the text itself
    cfg.server            # ServerConfig for the worker pool
    cfg.workers           # ["gpu", "gpu", "cpu"]  (worker index = position)
    cfg.route("toy-chat") # -> worker index, first matching routing rule wins
    cfg.model_path, cfg.flags, cfg.to_text()

The format is INI-like, with C comments, templates, expressions and flag conditions::

    // line comment            /* block comment, may span lines */
    [server]
    max_batch     = 2 * 2                 // * and /   -> eval_arith (no parentheses, no unary minus)
    token_budget  = 4096 - (512 + 128)    // + - ( )   -> eval_expr  (unary minus allowed)
    policy        = fcfs
    kv_blocks     = none                  // optional ints: none / off
    prefix_cache  = &(fast, debug)        // bools are flag conditions
    [model]
    path     = /models/toy/./ngram-5/     // normalised: /models/toy/ngram-5
    compiled = fast                       // run the model through the IR compiler (M5)
    [workers]
    pool = 2[gpu,]cpu                     // template: k[...] repeats -> gpu,gpu,cpu
    [pool.cpu]                            // per-kind ServerConfig overrides
    max_batch = 1
    [flags]                               // t / f / true / false / on / off, other flags, !( ) &( ) |( )
    stable = t
    debug  = off
    fast   = &(stable, !(debug))
    [routes]                              // model-name glob = worker index; first match wins
    llama-*-instruct = 1
    *                = 0

Because comments are stripped first, ``//`` and ``/*`` always start a comment — also inside a value:
write paths without doubled slashes and route patterns without ``/*``. Inside a template, digits are
repeat counts, so worker kinds that contain digits must be listed without ``k[...]``.

Loading pipeline: reject control characters → ``strip_comments`` (after checking every block comment
is closed) → ``brackets_balanced`` over the whole text → split into sections / keys → resolve flags
in dependency order (``topo_order``; a cycle is an error) → typed values: numbers via
``eval_arith`` / ``eval_expr`` (dispatched on the operators present, syntax checked first), bools via
``eval_flag_expr`` after substituting flag values, templates via ``expand_template``, the model path
via ``normalize_path``. Routing uses ``glob_match``.

Exercises this file calls: config.strip_comments, config.brackets, config.expr, config.arith,
config.flags, config.expand, config.norm_path, config.glob (and ir.order for flag dependencies).
"""
from __future__ import annotations

import dataclasses
import re
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nanoserve.config.arith import eval_arith
from nanoserve.config.comments import strip_comments
from nanoserve.config.expr import eval_expr
from nanoserve.config.flags import eval_flag_expr
from nanoserve.config.glob import glob_match
from nanoserve.config.parser import brackets_balanced
from nanoserve.config.paths import normalize_path
from nanoserve.config.template import expand_template
from nanoserve.ir.graph import topo_order
from nanoserve.server.server import ServerConfig

EXAMPLES = Path(__file__).resolve().parent / "examples"
DEFAULT_MODEL_PATH = "/models/toy/ngram-5"
SECTIONS = ("server", "model", "workers", "flags", "routes")   # plus "pool.<kind>"
TRUE_WORDS = ("t", "true", "on", "yes")
FALSE_WORDS = ("f", "false", "off", "no")
NONE_WORDS = ("none", "off")
CHOICES = {"policy": ("fcfs", "edf"), "eviction": ("lru", "lfu", "random")}
MINIMUM = {"max_batch": 1, "prefill_chunk": 1, "token_budget": 1, "kv_blocks": 1, "block_size": 1,
           "max_sessions": 0, "session_ttl": 1, "tick_ms": 1, "max_ticks": 1}
INT32_MAX = 2**31 - 1
MAX_WORKERS = 64
MAX_GLOB = 2000
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")            # flag names
_KIND = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*\Z")           # worker kinds
_SERVER_TYPES: dict[str, Any] = typing.get_type_hints(ServerConfig)


def _base_type(typ: Any) -> Any:
    """``int | None`` -> int; plain types unchanged."""
    args = [a for a in typing.get_args(typ) if a is not type(None)]
    return args[0] if len(args) == 1 else typ


# ServerConfig fields a config file can set (bool / int / optional int / str); others are rejected
SUPPORTED = {name: _base_type(t) for name, t in _SERVER_TYPES.items() if _base_type(t) in (bool, int, str)}


class ConfigError(ValueError):
    """The config text is malformed or has an invalid value."""


class NoRoute(LookupError):
    """No routing rule matches a model name."""


# ====================================================================================== result
@dataclass
class LoadedConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    model_path: str = DEFAULT_MODEL_PATH
    compiled: bool = False                       # build the model through the IR compiler
    workers: list[str] = field(default_factory=lambda: ["worker"])
    pool: dict[str, dict[str, Any]] = field(default_factory=dict)   # kind -> ServerConfig overrides
    flags: dict[str, bool] = field(default_factory=dict)
    routes: list[tuple[str, int]] = field(default_factory=list)     # (glob, worker index), in order
    source: str = field(default="<text>", compare=False)

    def route(self, model: str) -> int:
        """Worker index for a model name: first matching rule; no rules -> worker 0."""
        if not self.routes:
            return 0
        if not _printable(model) or "?" in model or "*" in model or len(model) > MAX_GLOB:
            raise NoRoute(f"model name {model!r} is not routable (printable ASCII, no wildcards)")
        for pattern, worker in self.routes:
            if glob_match(model, pattern):
                return worker
        raise NoRoute(f"no routing rule matches model {model!r}")

    def worker_config(self, i: int) -> ServerConfig:
        """ServerConfig of worker ``i``: the [server] values plus its kind's [pool.<kind>] overrides."""
        return dataclasses.replace(self.server, **self.pool.get(self.workers[i], {}))

    def to_text(self) -> str:
        """Canonical text form; ``load_config(c.to_text()) == c``."""
        out = ["[server]"]
        out += [f"{name} = {_fmt(getattr(self.server, name))}" for name in SUPPORTED]
        out += ["", "[model]", f"path = {self.model_path}", f"compiled = {_fmt(self.compiled)}"]
        out += ["", "[workers]", f"pool = {','.join(self.workers)}"]
        for kind, over in self.pool.items():
            out += ["", f"[pool.{kind}]"] + [f"{k} = {_fmt(v)}" for k, v in over.items()]
        if self.flags:
            out += ["", "[flags]"] + [f"{k} = {_fmt(v)}" for k, v in self.flags.items()]
        if self.routes:
            out += ["", "[routes]"] + [f"{p} = {w}" for p, w in self.routes]
        return "\n".join(out) + "\n"

    def describe(self) -> list[str]:
        lines = [f"config {self.source}"]
        core = ("max_batch", "prefill_chunk", "token_budget", "policy")   # always shown; others only if changed
        shown = {f.name: getattr(self.server, f.name) for f in dataclasses.fields(ServerConfig)
                 if f.name in core or getattr(self.server, f.name) != f.default}
        lines.append("  server   " + " ".join(f"{k}={_fmt(v)}" for k, v in shown.items()))
        lines.append(f"  model    {self.model_path}" + ("  (compiled to IR)" if self.compiled else ""))
        for i, kind in enumerate(self.workers):
            over = self.pool.get(kind, {})
            extra = "  " + " ".join(f"{k}={_fmt(v)}" for k, v in over.items()) if over else ""
            lines.append(f"  worker {i} {kind}{extra}")
        lines.append("  flags    " + (" ".join(f"{k}={_fmt(v)}" for k, v in self.flags.items()) or "-"))
        for p, w in self.routes:
            lines.append(f"  route    {p:<22} -> worker {w}")
        return lines


def _fmt(v: Any) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "t" if v else "f"
    return str(v)


def _printable(s: str) -> bool:
    return all(" " <= c <= "~" for c in s)


# ====================================================================================== stage 1: text
# Appended behind the text before stripping comments. Not open block: both lines come back unchanged.
# Open block: "<eof>" is swallowed and "*/" closes it, so the output cannot end with these two lines.
_SENTINEL = ["<eof>", "*/<eof>"]


def clean_lines(text: str) -> list[str]:
    """Comment-free, non-blank lines (comments stripped, block comments must be closed)."""
    lines = text.replace("\t", " ").splitlines()
    for no, line in enumerate(lines, 1):
        if not _printable(line):
            raise ConfigError(f"line {no}: only printable ASCII is allowed")
    # strip_comments requires every block comment to be closed: the sentinel guarantees that and tells us
    # whether the text itself left one open.
    stripped = strip_comments(lines + _SENTINEL)
    if stripped[-2:] != _SENTINEL:
        raise ConfigError("unterminated /* block comment")
    return [ln.strip() for ln in stripped[:-2] if ln.strip()]


def split_sections(lines: list[str]) -> dict[str, list[tuple[str, str]]]:
    if not brackets_balanced("\n".join(lines) or " "):
        raise ConfigError("unbalanced brackets ( ) [ ] { } in config")
    sections: dict[str, list[tuple[str, str]]] = {}
    current: str | None = None
    for line in lines:
        if line.startswith("[") and line.endswith("]") and "=" not in line:
            current = line[1:-1].strip()
            kind = current.split(".", 1)
            if current in sections:
                raise ConfigError(f"section [{current}] appears twice")
            if current not in SECTIONS and not (kind[0] == "pool" and len(kind) == 2 and _KIND.match(kind[1])):
                raise ConfigError(f"unknown section [{current}]")
            sections[current] = []
            continue
        if "=" not in line:
            raise ConfigError(f"expected 'key = value', got {line!r}")
        if current is None:
            raise ConfigError(f"{line!r} appears before any [section]")
        key, value = (s.strip() for s in line.split("=", 1))
        if not key or not value:
            raise ConfigError(f"empty key or value in {line!r}")
        if any(k == key for k, _ in sections[current]):
            raise ConfigError(f"[{current}] {key} is set twice")
        sections[current].append((key, value))
    return sections


# ====================================================================================== numbers
_NUM_TOKEN = re.compile(r"\d+|[-+*/()]|\S")


def eval_number(value: str) -> int:
    """Integer value of a config expression; dispatches on the operators it contains."""
    toks = _NUM_TOKEN.findall(value)
    for t in toks:
        if not (t.isdigit() or t in "+-*/()"):
            raise ConfigError(f"{value!r}: unexpected {t!r} in a number")
        if t.isdigit() and int(t) > INT32_MAX:
            raise ConfigError(f"{value!r}: {t} does not fit in 32 bits")
    has_parens = any(t in "()" for t in toks)
    has_muldiv = any(t in "*/" for t in toks)
    if has_parens and has_muldiv:
        raise ConfigError(f"{value!r}: use either * / or parentheses in one value, not both")
    lits = [int(t) for t in toks if t.isdigit()]
    if has_muldiv:
        _check_arith(value, toks)
        bound = 1
        for n in lits:   # |any + - * / combination| <= prod(n + 1): keeps every intermediate in 32 bits
            bound *= n + 1
        if bound > INT32_MAX:
            raise ConfigError(f"{value!r}: may overflow 32-bit arithmetic")
        return eval_arith(value)
    _check_plus_minus(value, toks)
    if sum(lits) > INT32_MAX:
        raise ConfigError(f"{value!r}: may overflow 32-bit arithmetic")
    return eval_expr(value)


def _check_arith(value: str, toks: list[str]) -> None:
    """eval_arith's input contract: n (op n)*, non-negative literals, no parentheses, no x/0."""
    ok = len(toks) % 2 == 1 and all(t.isdigit() for t in toks[::2]) and all(t in "+-*/" for t in toks[1::2])
    if not ok:
        raise ConfigError(f"{value!r}: expected numbers joined by + - * / (no unary minus)")
    if any(op == "/" and int(n) == 0 for op, n in zip(toks[1::2], toks[2::2])):
        raise ConfigError(f"{value!r}: division by zero")


def _check_plus_minus(value: str, toks: list[str]) -> None:
    """eval_expr's input contract: + - ( ), unary minus only, never two operators in a row."""
    want_operand, depth, prev = True, 0, ""
    for t in toks:
        if want_operand:
            if t.isdigit():
                want_operand = False
            elif t == "(":
                depth += 1
            elif not (t == "-" and prev not in ("+", "-")):
                raise ConfigError(f"{value!r}: unexpected {t!r}")
        elif t in "+-":
            want_operand = True
        elif t == ")" and depth > 0:
            depth -= 1
        else:
            raise ConfigError(f"{value!r}: unexpected {t!r}")
        prev = t
    if want_operand or depth:
        raise ConfigError(f"{value!r}: incomplete expression")


# ====================================================================================== flags
_FLAG_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\s+|.")


def flag_refs(value: str) -> list[str]:
    """Flag names referenced by a condition (literal words excluded)."""
    return [t for t in _FLAG_TOKEN.findall(value) if _NAME.match(t) and t.lower() not in TRUE_WORDS + FALSE_WORDS]


def eval_condition(value: str, flags: dict[str, bool]) -> bool:
    """Evaluate ``t``, ``off``, ``other_flag``, ``&(a, !(b))`` … with the given flag values."""
    out = []
    for t in _FLAG_TOKEN.findall(value):
        if t.isspace():
            continue
        if _NAME.match(t):
            low = t.lower()
            if low in TRUE_WORDS or low in FALSE_WORDS:
                out.append("t" if low in TRUE_WORDS else "f")
            elif t in flags:
                out.append("t" if flags[t] else "f")
            else:
                raise ConfigError(f"{value!r}: unknown flag {t!r}")
        elif t in "()&|!,":
            out.append(t)
        else:
            raise ConfigError(f"{value!r}: unexpected {t!r} in a condition")
    expr = "".join(out)
    _check_condition(value, expr)
    return eval_flag_expr(expr)


def _check_condition(value: str, expr: str) -> None:
    """eval_flag_expr's input contract: t | f | !(x) | &(x,...) | |(x,...); depth <= 200."""
    if not 1 <= len(expr) <= 20_000:
        raise ConfigError(f"{value!r}: condition is empty or too long")
    ops: list[str] = []          # open operators, innermost last
    want_value, i = True, 0
    while i < len(expr):
        c = expr[i]
        if want_value and c in "tf":
            want_value = False
        elif want_value and c in "!&|" and expr[i + 1:i + 2] == "(":
            ops.append(c)
            if len(ops) > 200:
                raise ConfigError(f"{value!r}: nested too deeply")
            i += 1
        elif not want_value and c == "," and ops and ops[-1] != "!":   # !( ) takes exactly one argument
            want_value = True
        elif not want_value and c == ")" and ops:
            ops.pop()
        else:
            raise ConfigError(f"{value!r}: unexpected {c!r} in the condition")
        i += 1
        if not want_value and not ops and i < len(expr):
            raise ConfigError(f"{value!r}: trailing text after the condition")
    if want_value or ops:
        raise ConfigError(f"{value!r}: incomplete condition")


def resolve_flags(items: list[tuple[str, str]]) -> dict[str, bool]:
    """Evaluate the [flags] section; flags may use flags defined anywhere in it (no cycles)."""
    names = [k for k, _ in items]
    for k in names:
        if not _NAME.match(k) or k.lower() in TRUE_WORDS + FALSE_WORDS:
            raise ConfigError(f"bad flag name {k!r}")
    if not items:
        return {}
    idx = {k: i for i, k in enumerate(names)}
    deps: set[tuple[int, int]] = set()
    for a, (name, value) in enumerate(items):
        for ref in flag_refs(value):
            if ref not in idx:
                raise ConfigError(f"flag {name}: unknown flag {ref!r}")
            if ref == name:
                raise ConfigError(f"flag {name} refers to itself")
            deps.add((a, idx[ref]))   # flag a depends on flag ref
    order = topo_order(len(items), [list(d) for d in sorted(deps)])
    if not order:
        raise ConfigError("flags refer to each other in a cycle")
    values: dict[str, bool] = {}
    for i in order:
        name, value = items[i]
        values[name] = eval_condition(value, values)
    return {k: values[k] for k in names}   # keep the file's order


# ====================================================================================== templates
_DIGITS = re.compile(r"\d+")


def expand_list(value: str) -> list[str]:
    """``2[gpu,]cpu`` -> ``["gpu", "gpu", "cpu"]`` (comma-separated after template expansion)."""
    if "[" in value or "]" in value:
        # expand_template's contract: balanced [ ], digits only as repeat counts k >= 1 right before "["
        if any(c in value for c in "(){}") or not brackets_balanced(value):
            raise ConfigError(f"{value!r}: a template uses balanced [ ] only")
        counts = list(_DIGITS.finditer(value))
        if any(value[m.end():m.end() + 1] != "[" or int(m.group()) < 1 for m in counts):
            raise ConfigError(f"{value!r}: digits in a template must be repeat counts k >= 1 written k[...]")
        if sum(1 for c in value if c == "[") != len(counts):
            raise ConfigError(f"{value!r}: every [ needs a repeat count in front of it")
        bound = len(value)
        for m in counts:
            bound *= int(m.group())
        if bound > 100_000:
            raise ConfigError(f"{value!r}: template expands too much")
        value = expand_template(value)
    items = [s.strip() for s in value.split(",")]
    items = [s for s in items if s]
    bad = [s for s in items if not _KIND.match(s)]
    if bad:
        raise ConfigError(f"bad worker kind(s) {bad}: use letters, digits, _ and -")
    return items


# ====================================================================================== typed values
def _server_value(key: str, value: str, flags: dict[str, bool]) -> Any:
    if key not in _SERVER_TYPES:
        raise ConfigError(f"unknown server setting {key!r}")
    if key not in SUPPORTED:
        raise ConfigError(f"server setting {key!r} cannot be set from a config file")
    typ, optional = SUPPORTED[key], type(None) in typing.get_args(_SERVER_TYPES[key])
    if optional and value.lower() in NONE_WORDS:
        return None
    if typ is bool:
        return eval_condition(value, flags)
    if typ is str:
        if value not in CHOICES.get(key, (value,)):
            raise ConfigError(f"{key} must be one of {CHOICES[key]}, got {value!r}")
        return value
    n = eval_number(value)
    if n < MINIMUM.get(key, 0):
        raise ConfigError(f"{key} must be >= {MINIMUM.get(key, 0)}, got {n}")
    return typ(n)


def _model_path(value: str) -> str:
    if not value.startswith("/") or not _printable(value) or " " in value:
        raise ConfigError(f"model path {value!r} must be absolute, without spaces")
    return normalize_path(value)


def _route_pattern(p: str) -> str:
    if " " in p or len(p) > MAX_GLOB:
        raise ConfigError(f"route pattern {p!r}: no spaces, at most {MAX_GLOB} characters")
    return p


# ====================================================================================== entry point
def load_config(text_or_path: str | Path) -> LoadedConfig:
    """Load a config from a path (``Path`` or an existing file name) or from the config text itself."""
    source = "<text>"
    text = str(text_or_path)
    if isinstance(text_or_path, Path) or not any(c in text for c in "\n=["):   # a file name, not config text
        source = str(text_or_path)
        text = Path(text_or_path).read_text()
    sec = split_sections(clean_lines(text))

    flags = resolve_flags(sec.get("flags", []))
    server = ServerConfig(**{k: _server_value(k, v, flags) for k, v in sec.get("server", [])})

    model = dict(sec.get("model", []))
    unknown = set(model) - {"path", "compiled"}
    if unknown:
        raise ConfigError(f"unknown [model] settings {sorted(unknown)}")
    model_path = _model_path(model.get("path", DEFAULT_MODEL_PATH))
    compiled = eval_condition(model["compiled"], flags) if "compiled" in model else False

    w = dict(sec.get("workers", []))
    if set(w) - {"pool"}:
        raise ConfigError(f"unknown [workers] settings {sorted(set(w) - {'pool'})}")
    workers = expand_list(w["pool"]) if "pool" in w else ["worker"]
    if not 1 <= len(workers) <= MAX_WORKERS:
        raise ConfigError(f"the pool needs 1..{MAX_WORKERS} workers, got {len(workers)}")

    pool: dict[str, dict[str, Any]] = {}
    for name, items in sec.items():
        if name.startswith("pool."):
            kind = name[5:]
            if kind not in workers:
                raise ConfigError(f"[{name}]: no worker of kind {kind!r} in the pool")
            pool[kind] = {k: _server_value(k, v, flags) for k, v in items}
            dataclasses.replace(server, **pool[kind])   # validates the combination early

    routes = []
    for pattern, value in sec.get("routes", []):
        idx = eval_number(value)
        if not 0 <= idx < len(workers):
            raise ConfigError(f"route {pattern!r} -> worker {idx}, but there are {len(workers)} workers")
        routes.append((_route_pattern(pattern), idx))

    return LoadedConfig(server=server, model_path=model_path, compiled=compiled, workers=workers,
                        pool=pool, flags=flags, routes=routes, source=source)


def example_path(name: str = "server.conf") -> Path:
    return EXAMPLES / name
