"""Framework: capacity planning / autoscaling from a trace, checked against the real server (M7).

    scaler = Autoscaler(engine)
    rec = scaler.size_pool(POOL, burst(30), target=40)       # smallest worker set finishing the burst by 40
    rec.lines()                                              # recommendation + the validating runs

Three sizing questions, each answered by one exercise and then *run* on the M2 server to show the estimate
is tight (enough with it, not enough with one unit less):

  * **pool size for a burst** (autoscale.min_time) — a burst of identical requests lands at tick 0 on a
    pool of heterogeneous single-stream workers; worker i needs ``t_i`` ticks per request (its kind's
    prefill_chunk changes ``t_i``). The minimum makespan T of n requests is the smallest T with
    Σ T // t_i >= n; workers are added fastest-first until T meets the target. Validation: the optimal plan
    (worker i gets T // t_i requests) runs on a ``PlannedCluster`` and finishes at exactly T; one worker fewer
    misses the target, and the starting (too small) pool misses it too.
  * **batch size per adapter launch** (autoscale.min_rate) — multi-LoRA serving: a batch holds one tenant's
    adapter, so every launch serves *one* tenant's queue, up to ``max_batch`` requests, for S ticks (equal
    requests). Draining per-tenant backlogs q_i within H ticks = within H // S launches needs the smallest
    ``max_batch`` with Σ ceil(q_i / max_batch) <= H // S. Validation: a server whose waiting queue only
    launches single-tenant batches (``AdapterBatchQueue``) drains by H with that ``max_batch``, not with one less.
  * **token budget per wave** (autoscale.min_throughput) — an ordered batch job (results must come back in
    order) runs in at most D waves; each wave admits a contiguous run of the backlog at once, and the
    server's reservation budget (``ServerConfig.token_budget``: Σ prompt + max_tokens in flight) caps a wave.
    The smallest budget C fitting the backlog into D waves is computed, the backlog is packed greedily into
    waves under C (wave k released at tick k·L, L = longest request) and run: with budget C every request is
    admitted the tick its wave is released; with C − 1 the plan stalls (someone waits).

Service time model: a request occupies its slot ceil(prompt_tokens / prefill_chunk) + max_tokens ticks
(exact without stop strings and prefix cache — the traces built here have neither).

Exercises this file calls (M7): autoscale.min_time, autoscale.min_rate, autoscale.min_throughput
(and, through Server / Cluster, the M2 core).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterator, Sequence

from nanoserve.autoscale.planned import PlannedCluster
from nanoserve.autoscale.sizing import min_drain_rate, min_throughput, min_time_for
from nanoserve.engine import Engine
from nanoserve.server.cluster import ClusterReport
from nanoserve.server.planner import fresh_batch, service_ticks
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig, ServerReport
from nanoserve.server.trace import make_trace

BURST_PROMPT = "The scheduler"   # 13 tokens


# ====================================================================================== traces
def burst(n: int, *, max_tokens: int = 4, prompt: str = BURST_PROMPT, at: int = 0, tenant: str = "a") -> list[Request]:
    """``n`` identical requests (no stop strings) arriving together — a traffic spike."""
    return [Request(rid=f"b{i:03d}", prompt=prompt, arrival=at, max_tokens=max_tokens, tenant=tenant, seed=i)
            for i in range(n)]


def tenant_backlog(queues: dict[str, int], *, max_tokens: int = 4, prompt: str = BURST_PROMPT) -> list[Request]:
    """Per-tenant backlogs of identical requests, all waiting at tick 0 (interleaved by tenant)."""
    out: list[Request] = []
    left = dict(queues)
    i = 0
    while any(left.values()):
        for t in queues:
            if left[t]:
                out.append(Request(rid=f"{t}{i:03d}", prompt=prompt, arrival=0, max_tokens=max_tokens,
                                   tenant=t, seed=i))
                left[t] -= 1
                i += 1
    return out


# ====================================================================================== worker kinds
@dataclass(frozen=True)
class WorkerKind:
    name: str
    prefill_chunk: int    # prompt tokens prefilled per tick: the only difference between kinds here

    def config(self, base: ServerConfig) -> ServerConfig:
        return replace(base, max_batch=1, prefill_chunk=self.prefill_chunk)


POOL = [WorkerKind("gpu-a", 16), WorkerKind("gpu-b", 8), WorkerKind("cpu", 4), WorkerKind("gpu-a", 16),
        WorkerKind("cpu", 2), WorkerKind("gpu-b", 8)]


# ====================================================================================== multi-LoRA queue
class AdapterBatchQueue:
    """``WaitingQueue`` for multi-LoRA batching: one batch = one tenant's adapter, launched together.

    While a batch runs nothing new is admitted; when the server is empty, the tenant with the largest
    backlog (then name) is launched and up to max_batch of its requests are admitted in that tick.
    Needs the server (for ``running`` / ``now``): ``srv.queue = AdapterBatchQueue(srv)``.
    """

    def __init__(self, server: Server) -> None:
        self.server = server
        self._items: list[Request] = []
        self._tenant: str | None = None
        self._launch: int | None = None
        self.launches: list[tuple[int, str]] = []

    def _open(self) -> list[Request]:
        """Requests admissible right now (the launching tenant's, in arrival order)."""
        srv = self.server
        if srv.running and self._launch != srv.now:
            return []  # a batch is running: closed
        if not srv.running and self._launch != srv.now and self._items:
            backlog: dict[str, int] = {}
            for r in self._items:
                backlog[r.tenant] = backlog.get(r.tenant, 0) + 1
            self._tenant = min(backlog, key=lambda t: (-backlog[t], t))
            self._launch = srv.now
            self.launches.append((srv.now, self._tenant))
        return [r for r in self._items if r.tenant == self._tenant]

    def push(self, req: Request) -> None:
        self._items.append(req)

    def push_front(self, req: Request) -> None:
        self._items.insert(0, req)

    def peek(self) -> Request | None:
        ready = self._open()
        return ready[0] if ready else None

    def pop(self) -> Request:
        req = self.peek()
        if req is None:
            raise IndexError("no request may be admitted now")
        self._items.remove(req)
        return req

    def remove(self, req: Request) -> None:
        self._items.remove(req)

    def __len__(self) -> int:
        # the server asks len() before peek(); 0 while a batch runs keeps it from mixing adapters.
        # (idle() also uses len(), but while a batch runs the server is busy anyway.)
        return len(self._open()) if self.server.running else len(self._items)

    def __iter__(self) -> Iterator[Request]:
        return iter(list(self._items))


# ====================================================================================== results
@dataclass
class PoolRecommendation:
    n: int
    target: int
    per_request: list[int]                       # t_i of every candidate in the pool, in pool order
    workers: list[WorkerKind]                    # recommended set (fastest-first prefix of the pool)
    estimate: int | None                         # min makespan of the recommended set
    estimate_fewer: int | None                   # ... with one worker fewer
    run: ClusterReport | None = None
    run_fewer: ClusterReport | None = None
    start_size: int = 1
    run_start: ClusterReport | None = None

    @property
    def size(self) -> int:
        return len(self.workers)

    @property
    def meets_target(self) -> bool:
        return self.run is not None and self.run.ticks <= self.target and len(self.run.finished) == self.n

    def lines(self) -> list[str]:
        out = [f"burst of {self.n} requests, target makespan {self.target} ticks"]
        if self.run_start is not None:
            out.append(f"  too-small pool ({self.start_size} worker(s)): finished in {self.run_start.ticks} ticks "
                       f"-> {'meets' if self.run_start.ticks <= self.target else 'MISSES'} the target")
        if self.estimate is None:
            out.append("  even the whole pool cannot meet the target")
            return out
        kinds = ", ".join(f"{k.name}({t})" for k, t in zip(self.workers, self.per_request[:self.size]))
        out.append(f"  recommendation: {self.size} worker(s) [{kinds}] (ticks/request in parentheses); "
                   f"estimated makespan {self.estimate}")
        if self.run is not None:
            out.append(f"  run with {self.size}: {len(self.run.finished)}/{self.n} done in {self.run.ticks} ticks "
                       f"(per worker {self.run.counts})")
        if self.run_fewer is not None:
            out.append(f"  run with {self.size - 1}: done in {self.run_fewer.ticks} ticks "
                       f"(estimate {self.estimate_fewer}) -> misses the target")
        return out


@dataclass
class DrainRecommendation:
    queues: dict[str, int]
    horizon: int              # ticks
    slice_ticks: int          # S: ticks one launch occupies the server
    launches: int             # H // S
    max_batch: int
    run: ServerReport | None = None
    run_less: ServerReport | None = None
    launch_log: list[tuple[int, str]] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [f"multi-LoRA backlog {self.queues}, drain within {self.horizon} ticks "
               f"({self.launches} launches of {self.slice_ticks} ticks)",
               f"  recommendation: max_batch {self.max_batch} per single-adapter launch"]
        if self.run is not None:
            out.append(f"  run with max_batch {self.max_batch}: drained in {self.run.ticks} ticks, "
                       f"{len(self.launch_log)} launches")
        if self.run_less is not None:
            out.append(f"  run with max_batch {self.max_batch - 1}: drained in {self.run_less.ticks} ticks "
                       f"-> misses the horizon")
        return out


@dataclass
class WaveRecommendation:
    work: list[int]           # prompt + max_tokens of every request, in backlog order
    waves: int                # D
    budget: int               # C
    plan: list[list[str]]     # rids of every wave
    wave_ticks: int           # L
    run: ServerReport | None = None
    run_less: ServerReport | None = None

    @staticmethod
    def waited(rep: ServerReport) -> int:
        return sum(1 for r in rep.finished if r.admitted_at > r.arrival)

    def lines(self) -> list[str]:
        sizes = [len(w) for w in self.plan]
        out = [f"ordered batch of {len(self.work)} requests in <= {self.waves} waves of {self.wave_ticks} ticks",
               f"  recommendation: token budget {self.budget} per wave (waves {sizes})"]
        if self.run is not None:
            out.append(f"  run with budget {self.budget}: {len(self.run.finished)} done, "
                       f"{self.waited(self.run)} waited past their wave's release, makespan {self.run.ticks}")
        if self.run_less is not None:
            out.append(f"  run with budget {self.budget - 1}: {self.waited(self.run_less)} request(s) "
                       f"stalled -> the plan does not fit")
        return out


# ====================================================================================== the autoscaler
class Autoscaler:
    def __init__(self, engine: Engine | None = None, base: ServerConfig | None = None) -> None:
        self.engine = engine or Engine()
        self.base = base or ServerConfig()

    # ---------------------------------------------------------------- pool size (min_time)
    def per_request(self, kind: WorkerKind, req: Request) -> int:
        return service_ticks(self.engine, req, kind.prefill_chunk)

    def makespan(self, times: Sequence[int], n: int) -> int:
        return min_time_for(list(times), n)

    def plan_burst(self, times: Sequence[int], n: int) -> tuple[int, list[int]]:
        """Optimal split of n identical requests over workers with per-request times ``times``:
        T = min makespan, worker i takes up to T // t_i requests (filled fastest-first)."""
        T = self.makespan(times, n)
        counts, left = [0] * len(times), n
        for i in sorted(range(len(times)), key=lambda i: (times[i], i)):
            counts[i] = min(T // times[i], left)
            left -= counts[i]
        return T, counts

    def run_burst(self, kinds: Sequence[WorkerKind], reqs: Sequence[Request]) -> ClusterReport:
        times = [self.per_request(k, reqs[0]) for k in kinds]
        _, counts = self.plan_burst(times, len(reqs))
        plan: dict[str, int | None] = {}
        it = iter(sorted(reqs, key=lambda r: r.rid))
        for w, c in enumerate(counts):
            for _ in range(c):
                plan[next(it).rid] = w
        cluster = PlannedCluster(len(kinds), plan, engine=self.engine, config=self.base,
                                 configs=[k.config(self.base) for k in kinds])
        cluster.submit_many(fresh_batch(reqs))
        return cluster.run()

    def size_pool(self, pool: Sequence[WorkerKind], reqs: Sequence[Request], target: int, *,
                  start: int = 1, validate: bool = True) -> PoolRecommendation:
        """Smallest fastest-first set of workers from ``pool`` that finishes the burst ``reqs`` by ``target``."""
        reqs = list(reqs)
        n = len(reqs)
        times = [self.per_request(k, reqs[0]) for k in pool]
        order = sorted(range(len(pool)), key=lambda i: (times[i], i))
        ranked = [pool[i] for i in order]
        rtimes = [times[i] for i in order]
        size = next((m for m in range(1, len(pool) + 1) if self.makespan(rtimes[:m], n) <= target), None)
        if size is None:
            return PoolRecommendation(n, target, rtimes, list(ranked), None, None)
        rec = PoolRecommendation(n, target, rtimes, ranked[:size], self.makespan(rtimes[:size], n),
                                 self.makespan(rtimes[:size - 1], n) if size > 1 else None, start_size=start)
        if validate:
            rec.run_start = self.run_burst(ranked[:start], reqs)
            rec.run = self.run_burst(ranked[:size], reqs)
            if size > 1:
                rec.run_fewer = self.run_burst(ranked[:size - 1], reqs)
        return rec

    # ---------------------------------------------------------------- batch per launch (min_rate)
    def run_adapters(self, reqs: Sequence[Request], max_batch: int) -> tuple[ServerReport, list[tuple[int, str]]]:
        srv = Server(self.engine, replace(self.base, max_batch=max_batch, token_budget=None, kv_blocks=None,
                                          prefix_cache=False), name=f"lora-b{max_batch}")
        srv.queue = AdapterBatchQueue(srv)
        srv.submit_many(fresh_batch(reqs))
        rep = srv.run()
        return rep, list(srv.queue.launches)

    def size_batch(self, queues: dict[str, int], horizon: int, *, max_tokens: int = 4,
                   validate: bool = True) -> DrainRecommendation:
        reqs = tenant_backlog(queues, max_tokens=max_tokens)
        S = service_ticks(self.engine, reqs[0], self.base.prefill_chunk)
        launches = horizon // S
        if launches < len(queues):
            raise ValueError(f"horizon {horizon} allows {launches} launches of {S} ticks: fewer than the "
                             f"{len(queues)} tenants, so no batch size can drain every queue")
        b = min_drain_rate(list(queues.values()), launches)
        rec = DrainRecommendation(dict(queues), horizon, S, launches, b)
        if validate:
            rec.run, rec.launch_log = self.run_adapters(reqs, b)
            if b > 1:
                rec.run_less, _ = self.run_adapters(reqs, b - 1)
        return rec

    # ---------------------------------------------------------------- wave budget (min_throughput)
    @staticmethod
    def pack_waves(work: Sequence[int], budget: int) -> list[list[int]]:
        """Indices of each wave: contiguous runs, a new wave whenever the next request would exceed budget."""
        waves: list[list[int]] = [[]]
        load = 0
        for i, w in enumerate(work):
            if waves[-1] and load + w > budget:
                waves.append([])
                load = 0
            waves[-1].append(i)
            load += w
        return waves

    def run_waves(self, reqs: Sequence[Request], waves: list[list[int]], budget: int, wave_ticks: int) -> ServerReport:
        batch = fresh_batch(reqs)
        for k, wave in enumerate(waves):
            for i in wave:
                batch[i].arrival = k * wave_ticks
        cfg = replace(self.base, max_batch=max(len(w) for w in waves), token_budget=budget, kv_blocks=None,
                      prefix_cache=False, policy="fcfs")
        srv = Server(self.engine, cfg, name=f"waves-c{budget}")
        srv.submit_many(batch)
        return srv.run()

    def size_waves(self, reqs: Sequence[Request], waves: int, *, validate: bool = True) -> WaveRecommendation:
        reqs = list(reqs)
        work = [len(self.engine.tokenizer.encode(r.prompt)) + r.max_tokens for r in reqs]
        if not 1 <= waves <= len(work):
            raise ValueError("need 1 <= waves <= number of requests")
        c = min_throughput(work, waves)
        packed = self.pack_waves(work, c)
        wave_ticks = max(service_ticks(self.engine, r, self.base.prefill_chunk) for r in reqs)
        rec = WaveRecommendation(work, waves, c, [[reqs[i].rid for i in w] for w in packed], wave_ticks)
        if validate:
            rec.run = self.run_waves(reqs, packed, c, wave_ticks)
            if c - 1 >= max(work):  # below max(work) a single request could never be admitted at all
                rec.run_less = self.run_waves(reqs, packed, c - 1, wave_ticks)
        return rec


def ordered_job(n: int = 12, seed: int = 0) -> list[Request]:
    """An ordered batch job (eval-set replay): requests from the synthetic trace, no stop strings."""
    return make_trace(n, seed=seed, rate=0, max_tokens=(2, 10))
