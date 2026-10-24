"""Framework: benchmark grid, scheduler determinism check and config-parser fuzzing (M6).

**Grid** — a benchmark sweep turns feature toggles on and off and replays the SAME request trace
on every resulting configuration::

    rows = run_grid(available_toggles(CORE_TOGGLES + OPTIONAL_TOGGLES)[0], sizes=(1, 2))
    print(grid_table(rows))

Configurations with exactly k of the n toggles on are enumerated with ``choose``. Each row reports
makespan, p50 latency, utilisation (busy ticks / ticks), slot occupancy, deadline hits and whether
every request's output equals the baseline's: per-request seeds make outputs independent of
batching, admission and caching, so any "no" here is a bug. Toggles whose plug-in module does not
import yet (M3/M4 features built separately) are left out by ``available_toggles``.

**Determinism** — requests that arrive in the same tick can reach the queue in any order. For all
orders (``arrival_orders``) we replay the server and require identical per-request outputs, while
the schedules themselves (who waits, latencies) do differ.

**Fuzz** — the config loader's cheap pre-check ``brackets_balanced`` must accept every balanced
bracket structure of size n (``balanced_brackets``, typed with (), [] and {} by nesting depth) and
reject every single-character substitution, deletion and insertion of it. Those mutations are
guaranteed to unbalance a balanced string (a substitution either changes the open/close counts or
breaks the forced pairing; deletions/insertions make the length odd), so the expected answer is
known without a second bracket checker.

Exercises this file calls (M6): bench.choose, bench.orders, bench.json_fuzz.
(It also calls M5 config.brackets and, through ``Server``, the M2 core.)
"""
from __future__ import annotations

import dataclasses
import importlib
from dataclasses import dataclass, field
from typing import Callable, Sequence

from nanoserve.bench.fuzz import arrival_orders, balanced_brackets
from nanoserve.bench.sweep import choose
from nanoserve.config.parser import brackets_balanced
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig, ServerReport
from nanoserve.server.trace import make_trace

TraceFactory = Callable[[], list[Request]]


# ====================================================================================== grid
@dataclass(frozen=True)
class Toggle:
    name: str
    overrides: tuple[tuple[str, object], ...]   # ServerConfig fields set when the toggle is on
    requires: str | None = None                 # "module:Symbol" that must import for the feature
    note: str = ""


CORE_TOGGLES: list[Toggle] = [   # M2 server core: always available
    Toggle("batch8", (("max_batch", 8),), note="8 batch slots instead of 4"),
    Toggle("budget", (("token_budget", 160),), note="reservation-based admission, 160 tokens"),
    Toggle("prefill4", (("prefill_chunk", 4),), note="prefill only 4 prompt tokens per tick"),
]
OPTIONAL_TOGGLES: list[Toggle] = [   # later milestones, plugged in through build_plugins
    Toggle("kv", (("kv_blocks", 40),), "nanoserve.kvcache.manager:BlockManager", "M3 paged KV cache, 40 blocks"),
    Toggle("prefix", (("prefix_cache", True),), "nanoserve.prefix.cache:PrefixCache", "M4 prefix cache"),
    Toggle("edf", (("policy", "edf"),), "nanoserve.index.queue:DeadlineQueue", "M4 earliest-deadline-first"),
]


def available_toggles(toggles: Sequence[Toggle]) -> tuple[list[Toggle], list[tuple[str, str]]]:
    """Split into (usable toggles, [(name, why skipped)]). A toggle is usable if its plug-in imports."""
    ok, skipped = [], []
    for t in toggles:
        if t.requires is None:
            ok.append(t)
            continue
        mod, _, sym = t.requires.partition(":")
        try:
            m = importlib.import_module(mod)
        except ImportError as e:
            skipped.append((t.name, f"{mod} not importable ({e.__class__.__name__})"))
            continue
        if sym and not hasattr(m, sym):
            skipped.append((t.name, f"{mod} has no {sym}"))
            continue
        ok.append(t)
    return ok, skipped


def grid(toggles: Sequence[Toggle], sizes: Sequence[int] = (1, 2)) -> list[tuple[Toggle, ...]]:
    """All toggle combinations with k toggles on, for each k in ``sizes`` (plus the empty baseline).

    Combinations come from ``choose(n, k)`` over 1-based toggle numbers; toggles that set the same
    config field are mutually exclusive and such combinations are dropped.
    """
    n = len(toggles)
    if n > 20:  # choose() precondition: n <= 20
        raise ValueError("at most 20 toggles per grid")
    combos: list[tuple[Toggle, ...]] = [()]
    for k in sizes:
        if not 1 <= k <= n:  # choose() precondition: 1 <= k <= n
            continue
        for picked in sorted(sorted(c) for c in choose(n, k)):  # canonical order (choose's is arbitrary)
            ts = tuple(toggles[i - 1] for i in picked)
            fields = [f for t in ts for f, _ in t.overrides]
            if len(fields) == len(set(fields)):
                combos.append(ts)
    return combos


def config_for(base: ServerConfig, toggles: Sequence[Toggle]) -> ServerConfig:
    return dataclasses.replace(base, **{f: v for t in toggles for f, v in t.overrides})


def default_trace() -> list[Request]:
    """The benchmark trace: 16 requests, ~0.8 arrivals/tick, shared prefixes and deadlines."""
    return make_trace(16, seed=1, rate=0.8, deadline_slack=(5, 30))


@dataclass
class BenchRow:
    name: str
    config: ServerConfig
    report: ServerReport
    same_outputs: bool | None = None   # vs the baseline row (None for the baseline itself)

    @property
    def p50(self) -> float | None:
        return self.report.p50_latency

    @property
    def utilization(self) -> float:
        return self.report.utilization

    @property
    def occupancy(self) -> float:
        """Fraction of slot-ticks in use: Σ (finished - admitted) / (ticks * max_batch)."""
        rep = self.report
        used = sum(r.finished_at - r.admitted_at for r in rep.finished if r.admitted_at is not None)
        return used / (rep.ticks * self.config.max_batch) if rep.ticks else 0.0

    @property
    def deadline_hits(self) -> tuple[int, int]:
        judged = [r.met_deadline for r in self.report.finished if r.met_deadline is not None]
        return sum(judged), len(judged)


def run_config(config: ServerConfig, trace: TraceFactory = default_trace, name: str = "") -> ServerReport:
    server = Server(config=config, name=name or "bench")
    server.submit_many(trace())  # a fresh copy: the server mutates its requests
    return server.run()


def run_grid(toggles: Sequence[Toggle], sizes: Sequence[int] = (1, 2), *,
             base: ServerConfig | None = None, trace: TraceFactory = default_trace) -> list[BenchRow]:
    base = base or ServerConfig(max_batch=4)
    rows: list[BenchRow] = []
    for combo in grid(toggles, sizes):
        cfg = config_for(base, combo)
        name = "+".join(t.name for t in combo) or "baseline"
        rows.append(BenchRow(name, cfg, run_config(cfg, trace, name)))
    ref = rows[0].report.outputs()
    for row in rows[1:]:
        out = row.report.outputs()
        common = ref.keys() & out.keys()
        row.same_outputs = bool(common) and all(out[r] == ref[r] for r in common)
    return rows


def grid_table(rows: Sequence[BenchRow]) -> str:
    head = f"{'config':<22} {'done':>4} {'rej':>3} {'ticks':>5} {'p50':>6} {'util':>5} {'occ':>5} {'SLO':>6}  same-out"
    lines = [head, "-" * len(head)]
    for r in rows:
        hit, tot = r.deadline_hits
        p50 = "-" if r.p50 is None else f"{r.p50:.1f}"
        same = "(base)" if r.same_outputs is None else ("yes" if r.same_outputs else "NO")
        lines.append(f"{r.name:<22} {len(r.report.finished):>4} {len(r.report.rejected):>3} {r.report.ticks:>5} "
                     f"{p50:>6} {r.utilization:>5.0%} {r.occupancy:>5.0%} {f'{hit}/{tot}':>6}  {same}")
    return "\n".join(lines)


# ====================================================================================== determinism
@dataclass
class DeterminismResult:
    n_requests: int
    orders: int                      # how many arrival orders were replayed
    distinct_outputs: int            # distinct {rid: output} maps (must be 1)
    distinct_schedules: int          # distinct admission orders (>1: the permutations mattered)
    finished_everywhere: bool

    @property
    def ok(self) -> bool:
        return self.distinct_outputs == 1 and self.finished_everywhere


def same_tick_trace(m: int, seed: int = 0, tick: int = 0) -> list[Request]:
    """``m`` requests that all arrive at ``tick`` (rate=0 → no inter-arrival gap)."""
    return make_trace(m, seed=seed, rate=0, start=tick)


def check_arrival_orders(m: int = 4, config: ServerConfig | None = None, seed: int = 0) -> DeterminismResult:
    """Replay every arrival order of ``m`` same-tick requests; outputs must not depend on the order."""
    if not 1 <= m <= 6:  # arrival_orders precondition
        raise ValueError("m must be in 1..6")
    config = config or ServerConfig(max_batch=2)  # fewer slots than requests, so order decides who waits
    outputs, schedules, all_done = set(), set(), True
    perms = arrival_orders(list(range(1, m + 1)))  # distinct 1-based ids
    for order in perms:
        reqs = same_tick_trace(m, seed)
        server = Server(config=config, name="order")
        for i in order:  # same arrival tick → the queue keeps submission order
            server.submit(reqs[i - 1])
        rep = server.run()
        all_done &= len(rep.finished) == m
        outputs.add(tuple(sorted(rep.outputs().items())))
        schedules.add(tuple(r.rid for r in sorted(rep.finished, key=lambda r: (r.admitted_at, r.slot))))
    return DeterminismResult(m, len(perms), len(outputs), len(schedules), all_done)


# ====================================================================================== fuzz
OPEN, CLOSE = "([{", ")]}"


def typed(structure: str, offset: int = 0) -> str:
    """Give a '()' structure bracket types by nesting depth: depth d uses kind (d + offset) % 3."""
    out, depth = [], 0
    for ch in structure:
        if ch == "(":
            out.append(OPEN[(depth + offset) % 3])
            depth += 1
        else:
            depth -= 1
            out.append(CLOSE[(depth + offset) % 3])
    return "".join(out)


def mutations(s: str) -> set[str]:
    """Every single-character substitution, deletion and insertion of ``s`` (all unbalance a balanced s)."""
    alphabet = OPEN + CLOSE
    out: set[str] = set()
    for i, c in enumerate(s):
        out.update(s[:i] + x + s[i + 1:] for x in alphabet if x != c)
        out.add(s[:i] + s[i + 1:])
    for i in range(len(s) + 1):
        out.update(s[:i] + x + s[i:] for x in alphabet)
    out.discard("")  # brackets_balanced precondition: len >= 1
    return out


@dataclass
class FuzzResult:
    n: int
    structures: int
    valid_checked: int
    valid_rejected: list[str] = field(default_factory=list)       # false negatives of the pre-check
    mutants_checked: int = 0
    mutants_accepted: list[str] = field(default_factory=list)     # false positives of the pre-check

    @property
    def ok(self) -> bool:
        return not self.valid_rejected and not self.mutants_accepted


def fuzz_brackets(n: int, check: Callable[[str], bool] = brackets_balanced) -> FuzzResult:
    """Exhaustively fuzz a bracket pre-check with every structure of ``n`` pairs and its mutants."""
    if not 1 <= n <= 8:  # balanced_brackets precondition
        raise ValueError("n must be in 1..8")
    structures = balanced_brackets(n)
    valid = sorted({typed(s, off) for s in structures for off in range(3)})
    res = FuzzResult(n, len(structures), len(valid))
    mutants: set[str] = set()
    for s in valid:
        if not check(s):
            res.valid_rejected.append(s)
        mutants |= mutations(s)
    res.mutants_checked = len(mutants)
    res.mutants_accepted = sorted(m for m in mutants if check(m))
    return res
