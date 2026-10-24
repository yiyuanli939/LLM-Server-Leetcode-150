"""Framework: the offline evaluation harness (M6).

    report = evaluate(DEFAULT_EXAMPLES, ServerConfig(max_batch=4))
    print(report.table())

1. **Generate** — every example becomes a ``Request`` (greedy by default) and the whole set runs
   through one ``Server`` with continuous batching, exactly like production traffic.
2. **Score** — each output is compared with its reference after answer normalisation
   (``normalize``: lower-case, punctuation dropped, whitespace collapsed):
     * character edit distance                         → ``edit_distance``
     * word-level ROUGE-L F1 from the LCS length       → ``lcs_length``
     * optional output constraint in the '.'/'*' regex dialect, matched against the whole
       normalised output                               → ``full_match``
3. **Stream integrity** — the server multiplexes all running requests into one event stream
   (``report.events``). For every pair of requests that ran concurrently, the raw stream restricted to
   the two must be an interleaving of their two outputs: nothing lost, duplicated or reordered within a
   request (``is_interleaving``). A request that never overlapped another is checked against the empty
   partner. ``corrupt_events`` produces deliberately broken streams to show the check bites.

Exercises this file calls (M6): eval.edit_distance, eval.rouge_l, decode.regex, eval.interleave_ok.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import combinations
from typing import Sequence

from nanoserve.decode.regex import full_match
from nanoserve.engine import Engine
from nanoserve.eval.metrics import edit_distance
from nanoserve.eval.rouge import lcs_length
from nanoserve.eval.streams import is_interleaving
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig, ServerReport

Event = tuple[int, str, str]  # (tick, rid, chunk), as in ServerReport.events


@dataclass
class Example:
    eid: str
    prompt: str
    reference: str
    pattern: str | None = None   # constraint on normalize(output), '.'/'*' dialect, full match
    max_tokens: int = 24
    stop: tuple[str, ...] = (".",)


# Prompts cut from corpus sentences; the reference is the rest of the sentence.
DEFAULT_EXAMPLES: list[Example] = [
    Example("sched", "The scheduler wakes up every few", " milliseconds and looks at the queue", "milliseconds .*"),
    Example("blocks", "The cache is made of", " blocks", "blocks"),
    Example("fixed", "Each block holds a fixed", " number of tokens", ".*tokens"),
    Example("tree", "The prefix cache is", " a tree", "a tre*"),
    Example("free", "When a request finishes, its blocks", " go back to the free list", "go back to .*"),
    Example("choice", "The sampler turns the scores of the model", " into a choice", "into a .*"),
    Example("temp", "A higher temperature makes the text", " more surprising", "more s.*"),
    Example("graph", "The compiler turns the model into a", " graph of operators", ".*operators"),
    Example("teacher", "A small engine is a", " good teacher"),
    Example("median", "The median latency tells you how a", " typical request feels", ".*feels"),
    Example("short", "Some requests are short and", " some are long", "some are .*"),
    Example("share", "When two requests share the same prefix, the engine", " can share the same blocks",
            "can share .*"),
]


@dataclass
class ExampleScore:
    eid: str
    output: str
    reference: str
    edit: int                 # character edit distance between normalised output and reference
    rouge_p: float
    rouge_r: float
    rouge_f1: float
    pattern: str | None
    pattern_ok: bool | None   # None when the example has no constraint

    @property
    def exact_match(self) -> bool:
        return normalize(self.output) == normalize(self.reference)


@dataclass
class StreamCheck:
    pairs: list[tuple[str, str]]          # concurrently running pairs that were checked
    solos: list[str]                      # requests that never overlapped another one
    bad: list[tuple[str, ...]]            # pairs / solos whose restricted stream is NOT an interleaving

    @property
    def ok(self) -> bool:
        return not self.bad


@dataclass
class EvalReport:
    scores: list[ExampleScore]
    stream: StreamCheck
    server: ServerReport
    meta: dict = field(default_factory=dict)

    @property
    def mean_rouge_f1(self) -> float:
        return sum(s.rouge_f1 for s in self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def mean_edit(self) -> float:
        return sum(s.edit for s in self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def constraint_pass_rate(self) -> float | None:
        checked = [s.pattern_ok for s in self.scores if s.pattern_ok is not None]
        return sum(checked) / len(checked) if checked else None

    def table(self, width: int = 34) -> str:
        lines = [f"{'example':<8} {'edit':>4} {'rougeL':>6} {'regex':>5}  output", "-" * (32 + width)]
        for s in self.scores:
            ok = "-" if s.pattern_ok is None else ("ok" if s.pattern_ok else "FAIL")
            out = normalize(s.output)
            out = out if len(out) <= width else out[: width - 3] + "..."
            lines.append(f"{s.eid:<8} {s.edit:>4} {s.rouge_f1:>6.2f} {ok:>5}  {out}")
        rate = self.constraint_pass_rate
        lines.append("-" * (32 + width))
        lines.append(f"mean edit {self.mean_edit:.1f}, mean ROUGE-L F1 {self.mean_rouge_f1:.2f}, "
                     f"exact {sum(s.exact_match for s in self.scores)}/{len(self.scores)}, "
                     f"constraints {'-' if rate is None else f'{rate:.0%}'}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------------- scoring
def normalize(text: str) -> str:
    """Answer normalisation: lower-case, drop punctuation, collapse whitespace.

    >>> normalize("The cache,\\n  is FULL.")
    'the cache is full'
    """
    kept = "".join(c for c in text.lower() if c.isalnum() or c.isspace())
    return " ".join(kept.split())


def edit_score(output: str, reference: str) -> int:
    """Character edit distance between the normalised output and reference."""
    return edit_distance(normalize(output), normalize(reference))


def rouge_l(output: str, reference: str) -> tuple[float, float, float]:
    """Word-level ROUGE-L: (precision, recall, F1) from the longest common word subsequence."""
    cand, ref = normalize(output).split(), normalize(reference).split()
    if not cand or not ref:
        return 0.0, 0.0, 0.0
    # spell both word lists with one private-use character per distinct word, so the LCS runs on words
    sym: dict[str, str] = {}
    c, r = ("".join(sym.setdefault(w, chr(0xE000 + len(sym))) for w in words) for words in (cand, ref))
    lcs = lcs_length(c, r)
    if lcs == 0:
        return 0.0, 0.0, 0.0
    p, rec = lcs / len(cand), lcs / len(ref)
    return p, rec, 2 * p * rec / (p + rec)


def check_pattern(output: str, pattern: str) -> bool:
    """Does the WHOLE normalised output match ``pattern`` ('.' any char, 'x*' zero or more x)?"""
    if pattern.startswith("*") or "**" in pattern:  # full_match precondition
        raise ValueError(f"malformed pattern {pattern!r}: every '*' must follow a character or '.'")
    return full_match(normalize(output), pattern)


def score_example(ex: Example, output: str) -> ExampleScore:
    p, r, f1 = rouge_l(output, ex.reference)
    ok = None if ex.pattern is None else check_pattern(output, ex.pattern)
    return ExampleScore(ex.eid, output, ex.reference, edit_score(output, ex.reference), p, r, f1, ex.pattern, ok)


# ---------------------------------------------------------------------------------- stream integrity
def restrict(events: Sequence[Event], rids: set[str]) -> str:
    """The multiplexed stream as seen by a client that only follows ``rids``."""
    return "".join(chunk for _, rid, chunk in events if rid in rids)


def is_stream_of(a: str, b: str, merged: str) -> bool:
    """Is ``merged`` (raw text) an interleaving of the outputs ``a`` and ``b``?"""
    return is_interleaving(a, b, merged)


def concurrent_pairs(requests: Sequence[Request]) -> list[tuple[Request, Request]]:
    """Pairs of finished requests whose running intervals [admitted_at, finished_at) overlap."""
    done = [r for r in requests if r.admitted_at is not None and r.finished_at is not None]
    return [(x, y) for x, y in combinations(done, 2)
            if x.admitted_at < y.finished_at and y.admitted_at < x.finished_at]


def check_streams(requests: Sequence[Request], events: Sequence[Event]) -> StreamCheck:
    finished = [r for r in requests if r.admitted_at is not None and r.finished_at is not None]
    pairs = concurrent_pairs(finished)
    paired = {r.rid for p in pairs for r in p}
    bad: list[tuple[str, ...]] = []
    for x, y in pairs:
        if not is_stream_of(x.output, y.output, restrict(events, {x.rid, y.rid})):
            bad.append((x.rid, y.rid))
    solos = [r for r in finished if r.rid not in paired]
    for r in solos:  # ran alone: its stream must interleave with "nothing", i.e. equal its output
        if not is_stream_of(r.output, "", restrict(events, {r.rid})):
            bad.append((r.rid,))
    return StreamCheck([(x.rid, y.rid) for x, y in pairs], [r.rid for r in solos], bad)


def corrupt_events(events: Sequence[Event], kind: str, seed: int = 0) -> tuple[list[Event], str]:
    """A deliberately broken copy of the stream. Returns (events, rid of the damaged request).

    kind: "swap"  two different chunks of one request delivered out of order,
          "drop"  one character of a chunk lost,
          "dup"   one chunk delivered twice.
    """
    rng = random.Random(seed)
    ev = list(events)
    by_rid: dict[str, list[int]] = {}
    for i, (_, rid, _) in enumerate(ev):
        by_rid.setdefault(rid, []).append(i)
    if kind == "swap":  # only chunk pairs whose order is observable (c1+c2 != c2+c1)
        cands = [(rid, i, j) for rid, idx in sorted(by_rid.items()) for i, j in zip(idx, idx[1:])
                 if ev[i][2] + ev[j][2] != ev[j][2] + ev[i][2]]
        rid, i, j = rng.choice(cands)
        (ti, _, ci), (tj, _, cj) = ev[i], ev[j]
        ev[i], ev[j] = (ti, rid, cj), (tj, rid, ci)
    elif kind == "drop":
        i = rng.choice([i for i, e in enumerate(ev) if e[2]])
        t, rid, c = ev[i]
        k = rng.randrange(len(c))
        ev[i] = (t, rid, c[:k] + c[k + 1:])
    elif kind == "dup":
        i = rng.randrange(len(ev))
        rid = ev[i][1]
        ev.insert(i + 1, ev[i])
    else:
        raise ValueError(f"unknown corruption {kind!r}")
    return ev, rid


# ---------------------------------------------------------------------------------- driver
def build_requests(examples: Sequence[Example], *, spacing: int = 1, temperature: float = 0.0,
                   seed: int = 0) -> list[Request]:
    """One request per example; arrivals ``spacing`` ticks apart so several run concurrently."""
    return [Request(rid=ex.eid, prompt=ex.prompt, arrival=i * spacing, max_tokens=ex.max_tokens,
                    stop=tuple(ex.stop), temperature=temperature, seed=seed + i)
            for i, ex in enumerate(examples)]


def evaluate(examples: Sequence[Example] = DEFAULT_EXAMPLES, config: ServerConfig | None = None, *,
             engine: Engine | None = None, spacing: int = 1, temperature: float = 0.0,
             seed: int = 0) -> EvalReport:
    """Serve every example through one batched ``Server`` and score the outputs (see module doc)."""
    if len({ex.eid for ex in examples}) != len(examples):
        raise ValueError("example ids must be distinct (they become request ids)")
    server = Server(engine=engine, config=config or ServerConfig(max_batch=4))
    server.submit_many(build_requests(examples, spacing=spacing, temperature=temperature, seed=seed))
    rep = server.run()
    by_rid = {r.rid: r for r in rep.finished}
    scores = [score_example(ex, by_rid[ex.eid].output) for ex in examples if ex.eid in by_rid]
    return EvalReport(scores, check_streams(rep.requests, rep.events), rep,
                      meta={"rejected": [r.rid for r in rep.rejected]})
