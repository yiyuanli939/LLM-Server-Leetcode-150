"""Framework: a cluster of serving workers behind one front end (M2).

    cluster = Cluster(3, policy="weighted", weights=[1, 2, 1], config=ServerConfig(max_batch=4))
    cluster.submit_many(make_trace(30, seed=0))
    report = cluster.run()
    print("\\n".join(report.table()))

Every worker is a full ``Server`` (its own slots, queue, KV / prefix-cache plug-ins); they share one
``Engine`` (the model is read-only, all per-request state lives in ``DecodeState``) and tick in lockstep.
Routing policies:

  * ``weighted``      — each request goes to worker i with probability weights[i] / Σweights
                        (sched.weighted_route; seeded, so a run is reproducible).
  * ``rr``            — classic front-end load balancer over single-stream replicas (every worker serves one
                        request at a time, so ``max_batch`` is set to 1): request i tries worker i % k first,
                        then the next ones around the ring, and is dropped (HTTP 503) if all are busy.
                        Afterwards the request log is replayed (sched.rr_busiest) to name the hot workers.
  * ``weighted_free`` — batch mode: the submitter releases the batch one request per tick (arrivals are
                        rewritten to the release tick), and each request is placed on the cheapest free batch
                        slot, by ``costs`` then worker index, FIFO when everything is busy (sched.assign_workers,
                        with service times estimated from prompt length and max_tokens). Exact service times
                        make the plan exact: nobody waits while a slot is idle.

The cluster report merges the workers' busy timelines (sched.merge_busy) and computes the cluster-wide p50
from the workers' sorted latency lists (metrics.merged_median; workers are folded into two halves).

Exercises this file calls (M2): sched.weighted_route, sched.rr_busiest, sched.assign_workers, sched.merge_busy,
metrics.merged_median (and, through every worker, the M2 server core).
"""
from __future__ import annotations

import heapq
import random
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Iterable, Sequence

from nanoserve.engine import Engine
from nanoserve.metrics.latency import merged_median
from nanoserve.scheduler.lb import busiest_servers
from nanoserve.scheduler.routing import WeightedRouter
from nanoserve.scheduler.simulate import assign_workers
from nanoserve.scheduler.timeline import merge_busy
from nanoserve.server.planner import release_one_per_tick, service_ticks
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig, ServerReport

POLICIES = ("weighted", "rr", "weighted_free")


def cluster_p50(latencies: Sequence[Sequence[int]]) -> float | None:
    """Median over every worker's latencies. Each worker's list is sorted; the workers are folded into two
    sorted halves (heapq.merge) and the halves combined by ``merged_median`` without merging them."""
    lists = [sorted(x) for x in latencies]
    if not any(lists):
        return None
    mid = (len(lists) + 1) // 2
    left = list(heapq.merge(*lists[:mid]))
    right = list(heapq.merge(*lists[mid:]))
    return merged_median(left, right)


@dataclass
class ClusterReport:
    policy: str
    ticks: int
    workers: list[ServerReport]
    requests: list[Request]               # every request the front end saw, in arrival (dispatch) order
    busy: list[list[int]]                 # union of the workers' busy timelines
    p50_latency: float | None             # cluster-wide
    hot_workers: list[int] | None = None  # rr: replay of the request log
    planned: dict[str, int] = field(default_factory=dict)  # weighted_free: rid -> worker from the plan

    @property
    def finished(self) -> list[Request]:
        return [r for w in self.workers for r in w.finished]

    @property
    def dropped(self) -> list[Request]:
        """Rejected by the front end (no worker could take it)."""
        return [r for r in self.requests if r.finish_reason == "rejected" and r.worker is None]

    @property
    def rejected(self) -> list[Request]:
        return [r for r in self.requests if r.finish_reason == "rejected"]

    @property
    def counts(self) -> list[int]:
        """Requests each worker finished."""
        return [len(w.finished) for w in self.workers]

    @property
    def busy_ticks(self) -> int:
        """Ticks during which at least one worker was computing."""
        return sum(e - s for s, e in self.busy)

    @property
    def utilization(self) -> float:
        """Mean worker utilization (Σ worker busy ticks / (workers × ticks))."""
        total = len(self.workers) * self.ticks
        return sum(w.busy_ticks for w in self.workers) / total if total else 0.0

    def outputs(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for w in self.workers:
            out.update(w.outputs())
        return out

    def summary(self) -> str:
        p50 = self.p50_latency if self.p50_latency is not None else "-"
        return (f"[cluster/{self.policy}] {len(self.finished)} finished, {len(self.rejected)} rejected "
                f"({len(self.dropped)} dropped at the front end) in {self.ticks} ticks on {len(self.workers)} "
                f"workers; p50 latency {p50} ticks; any-worker-busy {self.busy_ticks}/{self.ticks} ticks, "
                f"mean utilization {self.utilization:.0%}")

    def table(self) -> list[str]:
        lines = [self.summary(), f"  {'worker':<9}{'done':>5}{'rej':>5}{'p50':>7}{'util':>7}  busy timeline"]
        for w in self.workers:
            p50 = f"{w.p50_latency:g}" if w.p50_latency is not None else "-"
            spans = " ".join(f"[{s},{e})" for s, e in w.busy[:4]) + (" …" if len(w.busy) > 4 else "")
            lines.append(f"  {w.name:<9}{len(w.finished):>5}{len(w.rejected):>5}{p50:>7}{w.utilization:>7.0%}  {spans}")
        if self.hot_workers is not None:
            lines.append(f"  rr replay of the request log: busiest worker(s) {self.hot_workers}")
        return lines


class Cluster:
    def __init__(self, n_workers: int = 2, *, engine: Engine | None = None, config: ServerConfig | None = None,
                 policy: str = "weighted", weights: Sequence[int] | None = None,
                 costs: Sequence[int] | None = None, seed: int = 0) -> None:
        if policy not in POLICIES:
            raise ValueError(f"unknown policy {policy!r} (choose from {', '.join(POLICIES)})")
        if n_workers < 1:
            raise ValueError("a cluster needs at least one worker")
        cfg = config or ServerConfig()
        if policy == "rr":
            cfg = replace(cfg, max_batch=1)  # single-stream replicas: a worker is busy or free
        self.cfg = cfg
        self.policy = policy
        self.engine = engine or Engine()
        self.weights = list(weights) if weights is not None else [1] * n_workers  # routing share
        self.costs = list(costs) if costs is not None else [1] * n_workers        # free-slot preference
        if len(self.weights) != n_workers or len(self.costs) != n_workers:
            raise ValueError("need one weight and one cost per worker")
        if min(self.weights) < 1 or min(self.costs) < 1:
            raise ValueError("weights and costs must be positive integers")
        self.seed = seed
        self.workers = [Server(self.engine, cfg, name=f"worker{i}") for i in range(n_workers)]
        self.requests: list[Request] = []
        self.planned: dict[str, int] = {}
        self.now = 0

    # ------------------------------------------------------------------ public API
    def submit_many(self, reqs: Iterable[Request]) -> None:
        self.requests.extend(reqs)

    def run(self, max_ticks: int | None = None) -> ClusterReport:
        limit = max_ticks if max_ticks is not None else self.cfg.max_ticks
        reqs = sorted(self.requests, key=lambda r: r.arrival)  # stable: same-tick requests keep their order
        self.requests = reqs
        live: deque[Request] = deque()
        if self.policy == "weighted":
            self._route_weighted(reqs)
        elif self.policy == "weighted_free":
            self.requests = reqs = release_one_per_tick(reqs, start=reqs[0].arrival if reqs else 0)
            self._place_free_slots(reqs)
        else:  # rr dispatches live, against the workers' current state
            live = deque(reqs)
        index = 0
        while (live or not all(w.idle() for w in self.workers)) and self.now < limit:
            while live and live[0].arrival <= self.now:
                self._dispatch_rr(live.popleft(), index)
                index += 1
            for w in self.workers:
                w.tick()
            self.now += 1
        return self.report()

    # ------------------------------------------------------------------ routing
    def _send(self, req: Request, w: int) -> None:
        req.worker = w
        self.workers[w].submit(req)

    def _route_weighted(self, reqs: list[Request]) -> None:
        router = WeightedRouter(self.weights)
        saved = random.getstate()  # the router draws from the global RNG: seed it, then restore
        random.seed(self.seed)
        try:
            picks = [router.pick() for _ in reqs]
        finally:
            random.setstate(saved)
        for req, w in zip(reqs, picks):
            self._send(req, w)

    def _place_free_slots(self, reqs: list[Request]) -> None:
        """Plan with one entry per batch slot (slot s of worker w has cost costs[w]) and dispatch."""
        if not reqs:
            return
        b = self.cfg.max_batch
        slot_costs = [c for c in self.costs for _ in range(b)]
        durations = [service_ticks(self.engine, r, self.cfg.prefill_chunk) for r in reqs]
        for req, slot in zip(reqs, assign_workers(slot_costs, durations)):
            self.planned[req.rid] = slot // b
            self._send(req, slot // b)

    def _in_flight(self, w: int) -> int:
        return sum(1 for r in self.workers[w].requests if r.finished_at is None)

    def _dispatch_rr(self, req: Request, i: int) -> None:
        k = len(self.workers)
        for step in range(k):
            w = (i + step) % k
            if self._in_flight(w) < self.cfg.max_batch:
                self._send(req, w)
                return
        req.finished_at, req.finish_reason = self.now, "rejected"  # every worker busy: 503

    # ------------------------------------------------------------------ report
    def report(self) -> ClusterReport:
        workers = [w.report() for w in self.workers]
        spans = [list(iv) for rep in workers for iv in rep.busy]
        hot = None
        if self.policy == "rr" and self.requests:
            hot = busiest_servers(len(self.workers), [r.arrival for r in self.requests],
                                  [service_ticks(self.engine, r, self.cfg.prefill_chunk) for r in self.requests])
        return ClusterReport(
            policy=self.policy,
            ticks=self.now,
            workers=workers,
            requests=list(self.requests),
            busy=merge_busy(spans) if spans else [],
            p50_latency=cluster_p50([[r.latency for r in rep.finished] for rep in workers]),
            hot_workers=sorted(hot) if hot is not None else None,
            planned=dict(self.planned),
        )
