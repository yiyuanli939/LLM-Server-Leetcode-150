"""Framework: offline batch-job planner (M2) — Batch-API style, every request is known upfront.

Before a batch (an eval-set replay, a bulk summarisation job…) goes to the server, the planner answers
the capacity questions an operator asks, and checks its answers against the real server:

  * execution order on one worker    — shortest-job-first order (sched.sjf), then *actually run* through a
                                        max_batch=1 Server with a ``PlannedQueue`` and compared with FCFS
  * static-batching launches         — fewest batch launches so every request starts inside its
                                        [arrival, deadline - service] window (sched.min_launches)
  * multi-LoRA makespan              — prefill slots needed when re-loading the same adapter (one per tenant)
                                        needs a cooldown (sched.cooldown)
  * lanes for zero queueing          — fewest batch slots so nobody ever waits (sched.min_workers);
                                        verified: max_batch=W never queues, W-1 does
  * SLO upper bound                  — most deadlines one serial worker could meet (sched.slo_bound);
                                        the real max_batch=1 server never beats it
  * reserved lanes, hottest lane     — the batch released one request per tick onto N reserved lanes;
                                        which lane carries the most requests (sched.busiest_worker);
                                        verified against the server's slot usage

Service time model (exact for requests without stop strings and without prefix-cache hits, an upper bound
otherwise): a request occupies its batch slot for ceil(prompt_tokens / prefill_chunk) prefill ticks plus
max_tokens decode ticks — the same arithmetic the server's admission uses.

Exercises this file calls (M2): sched.sjf, sched.min_launches, sched.cooldown, sched.min_workers,
sched.slo_bound, sched.busiest_worker (and, through Server, the M2 core).
"""
from __future__ import annotations

import bisect
import copy
import dataclasses
import math
from dataclasses import dataclass, field, replace
from typing import Callable, Iterator, Sequence

from nanoserve.engine import Engine
from nanoserve.scheduler.batching import min_launches
from nanoserve.scheduler.cooldown import min_slots_with_cooldown
from nanoserve.scheduler.planning import max_on_time, min_workers
from nanoserve.scheduler.simulate import busiest_worker, sjf_order
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig, ServerReport

OPEN_END = 2**31 - 1  # latest start of a request without a deadline

# Fields the server fills in while a request runs; a fresh copy resets them to their defaults.
RUNTIME_FIELDS = ("prompt_tokens", "state", "slot", "worker", "admitted_at", "first_token_at", "finished_at",
                  "finish_reason", "cached_chars", "prefill_left", "preemptions", "output", "chunks")


# ---------------------------------------------------------------------------------------- helpers
def fresh(req: Request) -> Request:
    """A copy of ``req`` that has never been served (the server mutates the requests it runs)."""
    new = copy.copy(req)
    defaults = {f.name: f for f in dataclasses.fields(Request)}
    for name in RUNTIME_FIELDS:
        f = defaults[name]
        value = f.default_factory() if f.default_factory is not dataclasses.MISSING else f.default
        setattr(new, name, value)
    return new


def fresh_batch(reqs: Sequence[Request]) -> list[Request]:
    return [fresh(r) for r in reqs]


def service_ticks(engine: Engine, req: Request, prefill_chunk: int) -> int:
    """Ticks ``req`` holds a batch slot: prefill ticks + one tick per generated token."""
    n_prompt = len(engine.tokenizer.encode(req.prompt))
    return math.ceil(n_prompt / prefill_chunk) + max(req.max_tokens, 1)  # the engine always takes >= 1 step


def release_one_per_tick(reqs: Sequence[Request], start: int = 0) -> list[Request]:
    """The batch submitter's release schedule: in arrival order (stable), request j is released at tick
    ``start + j``. Sets ``arrival`` accordingly and returns the requests in release order."""
    order = sorted(reqs, key=lambda r: r.arrival)
    for j, r in enumerate(order):
        r.arrival = start + j
    return order


def mean_latency(report: ServerReport) -> float:
    lat = [r.latency for r in report.finished]
    return sum(lat) / len(lat) if lat else 0.0


def waited(report: ServerReport) -> list[Request]:
    """Requests that sat in the waiting queue for at least one tick."""
    return [r for r in report.finished if r.admitted_at is not None and r.admitted_at > r.arrival]


# ---------------------------------------------------------------------------------------- planned queue
class PlannedQueue:
    """``WaitingQueue`` plug-in that serves waiting requests in a precomputed order.

    Among the requests currently waiting, the one planned earliest goes first. If the server's timing
    follows the plan (exact service times), this is exactly the planned order; if a request finishes
    early, the queue still makes the sensible choice instead of idling.
    """

    def __init__(self, order: Sequence[str]) -> None:
        self._rank = {rid: i for i, rid in enumerate(order)}
        self._items: list[tuple[tuple[int, int], Request]] = []  # sorted by (rank, tiebreak)
        self._seq = 0

    def _insert(self, key: tuple[int, int], req: Request) -> None:
        bisect.insort(self._items, (key, req), key=lambda item: item[0])

    def push(self, req: Request) -> None:
        self._seq += 1
        self._insert((self._rank.get(req.rid, len(self._rank)), self._seq), req)

    def push_front(self, req: Request) -> None:  # a preempted request goes back first
        self._seq += 1
        self._insert((-1, -self._seq), req)

    def peek(self) -> Request | None:
        return self._items[0][1] if self._items else None

    def pop(self) -> Request:
        return self._items.pop(0)[1]

    def remove(self, req: Request) -> None:
        for i, (_, r) in enumerate(self._items):
            if r is req:
                del self._items[i]
                return
        raise ValueError(f"{req.rid} is not waiting")

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Request]:
        return iter([r for _, r in self._items])


# ---------------------------------------------------------------------------------------- the planner
@dataclass
class BatchPlan:
    n: int
    durations: dict[str, int]
    # single worker: SJF vs FCFS (both actually run, max_batch=1)
    sjf_order: list[str]
    sjf_report: ServerReport
    fcfs_report: ServerReport
    # static batching
    launches: int
    infeasible: list[str]               # requests that can't meet their deadline even if started on arrival
    # multi-LoRA
    lora_cooldown: int
    lora_slots: int
    # zero-queueing capacity
    min_lanes: int
    min_lanes_waits: int                # requests that waited with max_batch = min_lanes   (plan: 0)
    fewer_lanes_waits: int | None       # … with max_batch = min_lanes - 1                  (plan: > 0)
    # SLO
    slo_jobs: int
    slo_bound: int | None
    slo_met_fcfs: int | None
    slo_met_sjf: int | None
    # reserved lanes, released one per tick
    lanes: int
    hottest_lane: int
    lane_counts: list[int] = field(default_factory=list)  # measured on the server (slot usage)

    @property
    def sjf_mean_latency(self) -> float:
        return mean_latency(self.sjf_report)

    @property
    def fcfs_mean_latency(self) -> float:
        return mean_latency(self.fcfs_report)

    @property
    def sjf_followed(self) -> bool:
        """Did the real server admit requests exactly in the planned SJF order?"""
        admitted = sorted(self.sjf_report.finished, key=lambda r: (r.admitted_at, r.slot or 0))
        return [r.rid for r in admitted] == self.sjf_order

    @property
    def measured_hottest_lane(self) -> int:
        best = max(self.lane_counts)
        return self.lane_counts.index(best)

    def lines(self) -> list[str]:
        out = [f"batch plan for {self.n} requests (service = prefill ticks + max_tokens)"]
        out.append(f"  one worker, SJF vs FCFS (both run, max_batch=1): mean latency "
                   f"{self.sjf_mean_latency:.1f} vs {self.fcfs_mean_latency:.1f} ticks; "
                   f"server followed the plan: {self.sjf_followed}")
        inf = f", {len(self.infeasible)} can't make their deadline" if self.infeasible else ""
        out.append(f"  static batching: >= {self.launches} launches so every request starts in its window{inf}")
        out.append(f"  multi-LoRA (adapter per tenant, cooldown {self.lora_cooldown}): {self.lora_slots} prefill "
                   f"slots for {self.n} requests ({self.lora_slots - self.n} idle)")
        fewer = "-" if self.fewer_lanes_waits is None else self.fewer_lanes_waits
        out.append(f"  zero-queueing capacity: {self.min_lanes} lanes (verified: {self.min_lanes_waits} waited; "
                   f"with {self.min_lanes - 1} lanes {fewer} waited)")
        if self.slo_bound is not None:
            out.append(f"  SLO: one serial worker can meet at most {self.slo_bound}/{self.slo_jobs} deadlines; "
                       f"achieved FCFS {self.slo_met_fcfs}, SJF {self.slo_met_sjf}")
        out.append(f"  {self.lanes} reserved lanes, one release per tick: hottest lane {self.hottest_lane} "
                   f"(measured slot usage {self.lane_counts})")
        return out


class BatchPlanner:
    def __init__(self, engine: Engine | None = None, config: ServerConfig | None = None) -> None:
        self.engine = engine or Engine()
        # the planner models plain slots: no KV / prefix cache / token budget; its own queue plug-in
        base = config or ServerConfig()
        self.cfg = replace(base, policy="fcfs", kv_blocks=None, prefix_cache=False, token_budget=None,
                           max_sessions=None)

    # ---------------------------------------------------------------- estimates
    def durations(self, reqs: Sequence[Request]) -> list[int]:
        return [service_ticks(self.engine, r, self.cfg.prefill_chunk) for r in reqs]

    def sjf(self, reqs: Sequence[Request]) -> list[Request]:
        """Shortest-job-first execution order for one worker (non-preemptive, respects arrivals)."""
        order = sjf_order([[r.arrival, d] for r, d in zip(reqs, self.durations(reqs))])
        return [reqs[i] for i in order]

    def launch_windows(self, reqs: Sequence[Request]) -> tuple[list[list[int]], list[str]]:
        """[earliest, latest] start of every request that can still meet its deadline (+ the rest)."""
        windows, infeasible = [], []
        for r, d in zip(reqs, self.durations(reqs)):
            latest = OPEN_END if r.deadline is None else r.deadline - d
            if latest < r.arrival:
                infeasible.append(r.rid)
            else:
                windows.append([r.arrival, latest])
        return windows, infeasible

    def launches(self, reqs: Sequence[Request]) -> tuple[int, list[str]]:
        windows, infeasible = self.launch_windows(reqs)
        return (min_launches(windows) if windows else 0), infeasible

    @staticmethod
    def lora_slots(reqs: Sequence[Request], cooldown: int,
                   adapter: Callable[[Request], str] = lambda r: r.tenant) -> int:
        """Prefill slots to start every request when each tenant has its own LoRA adapter and reloading
        an adapter needs ``cooldown`` slots in between."""
        return min_slots_with_cooldown([adapter(r) for r in reqs], cooldown)

    def occupancy(self, reqs: Sequence[Request]) -> list[list[int]]:
        """Closed tick interval each request holds a slot if admitted the moment it arrives."""
        return [[r.arrival, r.arrival + d - 1] for r, d in zip(reqs, self.durations(reqs))]

    def min_lanes(self, reqs: Sequence[Request]) -> int:
        return min_workers(self.occupancy(reqs))

    def slo_jobs(self, reqs: Sequence[Request]) -> list[list[int]]:
        """[service ticks, deadline] of every request with a deadline (a deadline < 1 can never be met:
        nothing finishes before tick 1, so those are left out of the bound)."""
        return [[d, r.deadline] for r, d in zip(reqs, self.durations(reqs))
                if r.deadline is not None and r.deadline >= 1]

    def slo_bound(self, reqs: Sequence[Request]) -> int | None:
        jobs = self.slo_jobs(reqs)
        return max_on_time(jobs) if jobs else None

    def hottest_lane(self, released: Sequence[Request], lanes: int) -> int:
        """``released`` must follow the one-per-tick schedule (request j at tick j)."""
        return busiest_worker(lanes, [[r.arrival, r.arrival + d] for r, d in zip(released, self.durations(released))])

    # ---------------------------------------------------------------- real runs
    def run(self, reqs: Sequence[Request], *, max_batch: int = 1, order: Sequence[Request] | None = None,
            name: str = "plan") -> ServerReport:
        """Run fresh copies of ``reqs`` on one server (FCFS, or the given execution order)."""
        queue = PlannedQueue([r.rid for r in order]) if order is not None else None
        server = Server(self.engine, replace(self.cfg, max_batch=max_batch), queue=queue, name=name)
        server.submit_many(fresh_batch(reqs))
        return server.run()

    def plan(self, reqs: Sequence[Request], *, lanes: int | None = None, cooldown: int = 2) -> BatchPlan:
        reqs = list(reqs)
        durations = self.durations(reqs)
        order = self.sjf(reqs)
        sjf_rep = self.run(reqs, order=order, name="sjf")
        fcfs_rep = self.run(reqs, name="fcfs")
        launches, infeasible = self.launches(reqs)

        w = self.min_lanes(reqs)
        waits_w = len(waited(self.run(reqs, max_batch=w, name=f"lanes{w}")))
        waits_less = len(waited(self.run(reqs, max_batch=w - 1, name=f"lanes{w - 1}"))) if w > 1 else None

        bound = self.slo_bound(reqs)
        met = lambda rep: sum(1 for r in rep.finished if r.met_deadline)  # noqa: E731

        lanes = lanes or self.cfg.max_batch
        released = release_one_per_tick(fresh_batch(reqs))
        hot = self.hottest_lane(released, lanes)
        lane_rep = self.run(released, max_batch=lanes, name="lanes")
        counts = [0] * lanes
        for r in lane_rep.finished:
            counts[r.slot - 1] += 1  # slots are 1-based

        return BatchPlan(
            n=len(reqs), durations={r.rid: d for r, d in zip(reqs, durations)},
            sjf_order=[r.rid for r in order], sjf_report=sjf_rep, fcfs_report=fcfs_rep,
            launches=launches, infeasible=infeasible,
            lora_cooldown=cooldown, lora_slots=self.lora_slots(reqs, cooldown),
            min_lanes=w, min_lanes_waits=waits_w, fewer_lanes_waits=waits_less,
            slo_jobs=len(self.slo_jobs(reqs)), slo_bound=bound,
            slo_met_fcfs=met(fcfs_rep) if bound is not None else None,
            slo_met_sjf=met(sjf_rep) if bound is not None else None,
            lanes=lanes, hottest_lane=hot, lane_counts=counts,
        )
