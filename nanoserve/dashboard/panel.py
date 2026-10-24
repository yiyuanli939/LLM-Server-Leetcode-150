"""Framework: the text dashboard of a server or cluster run (M7).

    rep = server.run()                       # or cluster.run()
    dash = Dashboard(rep)
    print("\\n".join(dash.render(query="r01", k=5)))

Panels:

  * **occupancy heatmap** — a 0/1 matrix, one row per batch slot (``(worker, slot)`` for a cluster), one
    column per tick: 1 while a request holds that slot (``admitted_at <= t < finished_at``). The matrix is
    frozen for one refresh and queried a lot (every coarse cell of the picture, every box the operator
    selects), so it is preprocessed once into a ``RegionSum`` and every rectangle costs O(1) (dash.region_sum).
    Cells are drawn with shade characters by how full they are.
  * **slowest requests** — finishes are replayed in completion order; ``KthSlowest`` keeps the live k-th
    slowest latency, i.e. the bar a request must clear to enter the "slowest k" panel (metrics.slowest_k).
  * **request filter** — fzf-style: a request row is shown if the query's characters appear in order in
    the row text (dash.fuzzy).
  * **throughput with late corrections** — ``ThroughputMonitor`` ticks a live ``Server`` and reports the
    characters streamed in every tick. When the server preempts a request it drops that request's already
    streamed events (they will be recomputed), so per-tick totals of *earlier* ticks shrink after the fact:
    the monitor re-reports those ticks as corrections into a ``CorrectableSeries`` (metrics.corrected),
    whose current / peak / min are what the panel shows.
  * **cluster utilization** — the workers' busy spans arrive per worker (out of time order, overlapping
    each other); ``BusyTimeCounter`` keeps the size of their union online (metrics.busy_time). It is
    cross-checked against the merged cluster timeline (sched.merge_busy, computed by ``Cluster``).
  * **health matrix** (workers × models) — see ``nanoserve.dashboard.health_router``.

Exercises this file calls (M7): dash.region_sum, metrics.slowest_k, dash.fuzzy, metrics.corrected,
metrics.busy_time.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from nanoserve.dashboard.filter import fuzzy_match
from nanoserve.dashboard.region import RegionSum
from nanoserve.metrics.busy import BusyTimeCounter
from nanoserve.metrics.series import CorrectableSeries
from nanoserve.metrics.slowest import KthSlowest
from nanoserve.server.cluster import ClusterReport
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerReport

SHADES = " .:-=+*#%@"   # empty .. full


# ====================================================================================== occupancy
class Occupancy:
    """Slot × tick occupancy matrix of a run, with O(1) rectangle sums."""

    def __init__(self, report: ServerReport | ClusterReport) -> None:
        workers = report.workers if isinstance(report, ClusterReport) else [report]
        self.ticks = max(report.ticks, 1)
        self.rows: list[tuple[int, int]] = []          # row -> (worker index, slot)
        self.worker_rows: list[tuple[int, int]] = []   # worker -> (first row, last row)
        for w, rep in enumerate(workers):
            served = [r for r in rep.requests if r.slot is not None and r.admitted_at is not None]
            n_slots = max([r.slot for r in served], default=1)
            first = len(self.rows)
            self.rows += [(w, s) for s in range(1, n_slots + 1)]
            self.worker_rows.append((first, len(self.rows) - 1))
        index = {ws: i for i, ws in enumerate(self.rows)}
        self.grid = [[0] * self.ticks for _ in self.rows]
        for w, rep in enumerate(workers):
            for r in rep.requests:
                if r.slot is None or r.admitted_at is None or r.finished_at is None:
                    continue
                row = self.grid[index[(w, r.slot)]]
                for t in range(r.admitted_at, min(r.finished_at, self.ticks)):
                    row[t] = 1
        self.sums = RegionSum(self.grid)

    def region(self, r1: int, c1: int, r2: int, c2: int) -> int:
        """Slot-ticks in use in rows r1..r2, ticks c1..c2 (inclusive); clipped to the matrix."""
        r1, r2 = max(r1, 0), min(r2, len(self.rows) - 1)
        c1, c2 = max(c1, 0), min(c2, self.ticks - 1)
        if r1 > r2 or c1 > c2:
            return 0
        return self.sums.sum_region(r1, c1, r2, c2)

    def worker_busy_slots(self, w: int, t0: int, t1: int) -> int:
        first, last = self.worker_rows[w]
        return self.region(first, t0, last, t1)

    def cells(self, width: int = 48, by_worker: bool | None = None) -> tuple[list[tuple[str, int, int]],
                                                                            list[tuple[int, int]],
                                                                            list[list[int]]]:
        """Coarse heatmap: (row groups, time buckets, sums[group][bucket])."""
        if by_worker is None:
            by_worker = len(self.worker_rows) > 1
        if by_worker:
            groups = [(f"worker{w}", a, b) for w, (a, b) in enumerate(self.worker_rows)]
        else:
            groups = [(f"w{w}/slot{s}", i, i) for i, (w, s) in enumerate(self.rows)]
        bw = max(1, math.ceil(self.ticks / max(width, 1)))
        buckets = [(c, min(c + bw, self.ticks) - 1) for c in range(0, self.ticks, bw)]
        sums = [[self.region(a, c1, b, c2) for c1, c2 in buckets] for _, a, b in groups]
        return groups, buckets, sums

    def heatmap(self, width: int = 48) -> list[str]:
        groups, buckets, sums = self.cells(width)
        bw = buckets[0][1] - buckets[0][0] + 1
        out = [f"occupancy heatmap ({len(self.rows)} slots x {self.ticks} ticks, {bw} tick(s) per column)"]
        label_w = max(len(g[0]) for g in groups)
        for (label, a, b), row in zip(groups, sums):
            chars = []
            for (c1, c2), v in zip(buckets, row):
                cap = (b - a + 1) * (c2 - c1 + 1)
                chars.append(SHADES[min(len(SHADES) - 1, math.ceil(v / cap * (len(SHADES) - 1)))])
            used = self.region(a, 0, b, self.ticks - 1)
            out.append(f"  {label:<{label_w}} |{''.join(chars)}| {used / ((b - a + 1) * self.ticks):.0%}")
        return out


# ====================================================================================== slowest k
@dataclass
class SlowestPanel:
    k: int
    thresholds: list[tuple[str, int]]   # (rid that just finished, k-th slowest latency so far)
    slowest: list[Request]              # requests at/above the final threshold, slowest first

    @property
    def threshold(self) -> int | None:
        return self.thresholds[-1][1] if self.thresholds else None


def slowest_panel(requests: Sequence[Request], k: int = 5) -> SlowestPanel:
    """Replay finishes in completion order and track the k-th slowest latency after each one."""
    fin = sorted((r for r in requests if r.finished_at is not None and r.finish_reason != "rejected"),
                 key=lambda r: (r.finished_at, r.slot or 0, r.rid))
    if not fin:
        return SlowestPanel(k, [], [])
    k = max(1, min(k, len(fin)))
    # precondition of add(): at least k latencies afterwards → seed with the first k-1 finishes
    tracker = KthSlowest(k, [r.latency for r in fin[:k - 1]])
    thresholds = [(r.rid, tracker.add(r.latency)) for r in fin[k - 1:]]
    bar = thresholds[-1][1]
    slowest = sorted((r for r in fin if r.latency >= bar), key=lambda r: (-r.latency, r.rid))
    return SlowestPanel(k, thresholds, slowest)


# ====================================================================================== filter
def row_text(r: Request) -> str:
    """The text of one request row; the fuzzy filter matches against it."""
    return f"{r.rid} {r.tenant} {r.model} {r.prompt}"


def filter_requests(requests: Sequence[Request], query: str) -> list[Request]:
    return [r for r in requests if fuzzy_match(query, row_text(r))]


# ====================================================================================== throughput
@dataclass
class ThroughputMonitor:
    """Tick a live server and stream per-tick throughput (characters emitted) into a correctable series.

    After every tick the monitor recomputes the per-tick totals of the server's event stream. A new tick is
    reported once; a tick whose total changed since it was reported (a preempted request's events were
    dropped) is re-reported as a correction.
    """

    server: Server
    series: CorrectableSeries = field(default_factory=CorrectableSeries)
    reported: dict[int, int] = field(default_factory=dict)   # tick -> value last sent to the series
    corrections: list[tuple[int, int, int]] = field(default_factory=list)  # (at tick, ts, new value)
    history: list[tuple[int, int, int, int]] = field(default_factory=list)  # (tick, current, max, min)

    @staticmethod
    def per_tick(events: Sequence[tuple[int, str, str]], ticks: int) -> list[int]:
        out = [0] * ticks
        for t, _, chunk in events:
            out[t] += len(chunk)
        return out

    def step(self) -> None:
        now = self.server.now
        self.server.tick()
        totals = self.per_tick(self.server.events, now + 1)
        for ts, v in enumerate(totals):
            old = self.reported.get(ts)
            if old == v:
                continue
            if old is not None:
                self.corrections.append((now, ts, v))
            self.series.update(ts, v)
            self.reported[ts] = v
        self.history.append((now, self.series.current(), self.series.maximum(), self.series.minimum()))

    def run(self, max_ticks: int | None = None) -> ServerReport:
        limit = max_ticks if max_ticks is not None else self.server.cfg.max_ticks
        while not self.server.idle() and self.server.now < limit:
            self.step()
        return self.server.report()

    def lines(self) -> list[str]:
        if not self.history:
            return ["throughput: no ticks"]
        _, cur, hi, lo = self.history[-1]
        return [f"throughput (chars/tick): current {cur}, peak {hi}, min {lo}; "
                f"{len(self.corrections)} late correction(s) from preemptions"]


# ====================================================================================== utilization
def busy_spans(report: ClusterReport) -> list[tuple[int, int, int]]:
    """(worker, first busy tick, last busy tick) of every worker's busy span, worker by worker."""
    return [(w, s, e - 1) for w, rep in enumerate(report.workers) for s, e in rep.busy]


@dataclass
class Utilization:
    any_busy: int        # ticks in which at least one worker computed (union of all spans)
    merged: int          # the same from the merged cluster timeline (cross-check)
    worker_busy: list[int]
    ticks: int

    @property
    def consistent(self) -> bool:
        return self.any_busy == self.merged


def cluster_utilization(report: ClusterReport) -> Utilization:
    counter = BusyTimeCounter()
    for _, first, last in busy_spans(report):  # spans [s, e) are fed as closed [s, e-1]
        counter.add(first, last)
    return Utilization(counter.count(), report.busy_ticks, [w.busy_ticks for w in report.workers], report.ticks)


# ====================================================================================== dashboard
class Dashboard:
    def __init__(self, report: ServerReport | ClusterReport) -> None:
        self.report = report
        self.occupancy = Occupancy(report)

    @property
    def requests(self) -> list[Request]:
        return list(self.report.requests)

    def render(self, query: str = "", k: int = 5, width: int = 48, rows: int = 8) -> list[str]:
        rep = self.report
        out = [rep.summary(), ""]
        out += self.occupancy.heatmap(width)

        panel = slowest_panel(rep.requests, k)
        if panel.threshold is not None:
            bars = [t for _, t in panel.thresholds]
            out += ["", f"slowest {panel.k} (live bar rose {bars[0]} -> {panel.threshold} ticks over "
                        f"{len(bars)} finishes):"]
            for r in panel.slowest[:max(k, 1) + 2]:
                out.append(f"  {r.rid:<8}{r.tenant:<4}latency {r.latency:>4}  ttft {r.ttft}  "
                           f"preempted {r.preemptions}")

        if isinstance(rep, ClusterReport):
            u = cluster_utilization(rep)
            out += ["", f"cluster utilization: some worker busy {u.any_busy}/{u.ticks} ticks "
                        f"(merged timeline {u.merged}: {'ok' if u.consistent else 'MISMATCH'}); "
                        f"per worker {u.worker_busy}"]

        shown = filter_requests(rep.requests, query) if query else list(rep.requests)
        out += ["", f"requests matching {query!r}: {len(shown)}/{len(rep.requests)}" if query
                else f"requests: {len(shown)}"]
        for r in shown[:rows]:
            state = r.finish_reason or "running"
            out.append(f"  {row_text(r)[:60]:<60} {state}")
        if len(shown) > rows:
            out.append(f"  … {len(shown) - rows} more")
        return out
