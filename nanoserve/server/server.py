"""Framework: the serving loop with continuous batching (M2 core).

    server = Server(config=ServerConfig(max_batch=4))
    server.submit_many(make_trace(20, seed=0))
    report = server.run()
    print(report.summary())

Every tick (= one decode step of the running batch):

  1. arrivals    → session check (TTL tokens), QPS counter, into the waiting queue
  2. admission   → while a batch slot is free and we're not in a maintenance window:
                   token-budget reservation check + KV check (M3), take a slot, look up the
                   prefix cache (M4) to shorten prefill, start decoding state
  3. compute     → each running request does one prefill tick or one decode step;
                   out-of-KV → preempt the most recently admitted request (recompute later)
  4. bookkeeping → busy timeline, queue length, finished requests release slot / KV / reservation

Exercises this file calls (M2): sched.slots, server.tokens, sched.maintenance, metrics.qps,
sched.insert_busy, metrics.median, sched.capacity_ok.
Later milestones plug in through ``nanoserve.server.plugins``.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from nanoserve.engine import Engine, GenerationConfig
from nanoserve.metrics.latency import MedianTracker
from nanoserve.metrics.window import QpsCounter
from nanoserve.scheduler.batch_slots import SlotAllocator
from nanoserve.scheduler.calendar import MaintenanceCalendar
from nanoserve.scheduler.capacity import fits_capacity
from nanoserve.scheduler.timeline import insert_busy
from nanoserve.server.auth_tokens import TokenManager
from nanoserve.server.plugins import FCFSQueue, NullKV, NullPrefixCache
from nanoserve.server.request import Request


@dataclass
class ServerConfig:
    max_batch: int = 4
    prefill_chunk: int = 16           # prompt tokens prefilled per tick
    token_budget: int | None = None   # reservation-based admission: Σ(prompt+max_tokens) of in-flight work
    policy: str = "fcfs"              # "fcfs" | "edf" (earliest deadline first, M4 index)
    kv_blocks: int | None = None      # M3: number of KV blocks (None → no KV accounting)
    block_size: int = 8               # M3: tokens per block
    eviction: str = "lru"             # M3: "lru" | "lfu" | "random" for cached blocks
    prefix_cache: bool = False        # M4
    max_sessions: int | None = None   # reject requests opening a new session beyond this many live ones
    session_ttl: int = 50             # ticks a session stays alive without a request
    tick_ms: int = 10                 # wall-clock length of one tick, for QPS
    max_ticks: int = 100_000


@dataclass
class ServerReport:
    name: str
    ticks: int
    requests: list[Request]
    events: list[tuple[int, str, str]]   # (tick, rid, chunk) in emission order — the multiplexed stream
    busy: list[list[int]]                # merged busy intervals [start, end] (closed, tick units)
    queue_len: list[int]                 # waiting-queue length at the end of every tick
    qps: list[tuple[int, int]]           # (tick, requests seen in the last 3 s) at every arrival
    active_sessions: list[int]           # live sessions at the end of every tick (if sessions used)
    p50_latency: float | None
    plugins: dict = field(default_factory=dict)

    @property
    def finished(self) -> list[Request]:
        return [r for r in self.requests if r.finished_at is not None and r.finish_reason != "rejected"]

    @property
    def rejected(self) -> list[Request]:
        return [r for r in self.requests if r.finish_reason == "rejected"]

    @property
    def busy_ticks(self) -> int:
        return sum(e - s for s, e in self.busy)

    @property
    def utilization(self) -> float:
        return self.busy_ticks / self.ticks if self.ticks else 0.0

    def outputs(self) -> dict[str, str]:
        return {r.rid: r.output for r in self.finished}

    def summary(self) -> str:
        fin = self.finished
        lat = sorted(r.latency for r in fin)
        p50 = self.p50_latency
        return (f"[{self.name}] {len(fin)} finished, {len(self.rejected)} rejected in {self.ticks} ticks; "
                f"p50 latency {p50 if p50 is not None else '-'} ticks, max {lat[-1] if lat else '-'}; "
                f"utilization {self.utilization:.0%}")


def build_plugins(cfg: ServerConfig, tokenizer=None):
    """Instantiate the plug-ins the config asks for (imports are lazy so M2 works on its own).

    ``tokenizer`` is the engine's tokenizer, so the KV manager and prefix cache count/share exactly
    the tokens the model sees.
    """
    kv, prefix, queue = NullKV(), NullPrefixCache(), FCFSQueue()
    if cfg.kv_blocks is not None:
        from nanoserve.kvcache.manager import BlockManager
        kv = BlockManager(num_blocks=cfg.kv_blocks, block_size=cfg.block_size, eviction=cfg.eviction,
                          tokenizer=tokenizer)
    if cfg.prefix_cache:
        from nanoserve.prefix.cache import PrefixCache
        prefix = PrefixCache(tokenizer)
    if cfg.policy == "edf":
        from nanoserve.index.queue import DeadlineQueue
        queue = DeadlineQueue()
    elif cfg.policy != "fcfs":
        raise ValueError(f"unknown policy {cfg.policy!r}")
    return kv, prefix, queue


class Server:
    def __init__(self, engine: Engine | None = None, config: ServerConfig | None = None, *,
                 kv=None, prefix_cache=None, queue=None, name: str = "worker0"):
        self.cfg = config or ServerConfig()
        self.engine = engine or Engine()
        dkv, dprefix, dqueue = build_plugins(self.cfg, self.engine.tokenizer)
        self.kv = kv if kv is not None else dkv
        self.prefix_cache = prefix_cache if prefix_cache is not None else dprefix
        self.queue = queue if queue is not None else dqueue
        self.name = name

        self.now = 0
        self.requests: list[Request] = []
        self._pending: deque[Request] = deque()
        self.running: dict[int, Request] = {}
        self.slots = SlotAllocator(self.cfg.max_batch)
        self.qps = QpsCounter()
        self._t_ms = 0  # last arrival timestamp (ms); QpsCounter needs t >= 1 and strictly increasing
        self.latency = MedianTracker()
        self._n_latency = 0
        self.busy: list[list[int]] = []
        self.events: list[tuple[int, str, str]] = []
        self.queue_len: list[int] = []
        self.qps_series: list[tuple[int, int]] = []
        self.sessions = TokenManager(self.cfg.session_ttl)
        self._seen_sessions: set[str] = set()
        self.active_sessions: list[int] = []
        self.calendar = MaintenanceCalendar()
        self.maintenance: list[tuple[int, int]] = []
        self._reservations: dict[str, list[int]] = {}  # rid -> [tokens, start, end)

    # ------------------------------------------------------------------ public API
    def submit(self, req: Request) -> None:
        self.submit_many([req])

    def submit_many(self, reqs: Iterable[Request]) -> None:
        reqs = list(reqs)
        self.requests.extend(reqs)
        # keep pending sorted by arrival (stable for equal arrivals)
        self._pending = deque(sorted([*self._pending, *reqs], key=lambda r: r.arrival))

    def schedule_maintenance(self, start: int, end: int) -> bool:
        """Book a maintenance window [start, end) during which nothing new is admitted."""
        if self.calendar.book(start, end):
            self.maintenance.append((start, end))
            return True
        return False

    def in_maintenance(self, t: int) -> bool:
        return any(s <= t < e for s, e in self.maintenance)

    def idle(self) -> bool:
        return not self._pending and not len(self.queue) and not self.running

    def run(self, max_ticks: int | None = None) -> ServerReport:
        limit = max_ticks if max_ticks is not None else self.cfg.max_ticks
        while not self.idle() and self.now < limit:
            self.tick()
        return self.report()

    # ------------------------------------------------------------------ the loop
    def tick(self) -> None:
        now = self.now
        self._arrivals(now)
        if not self.in_maintenance(now):
            self._admit_waiting(now)
        computed = self._compute(now)
        if computed:
            self.busy = insert_busy(self.busy, [now, now + 1])
        self.queue_len.append(len(self.queue))
        if self._seen_sessions:
            self.active_sessions.append(self.sessions.count_unexpired(now))
        self.now += 1

    def _arrivals(self, now: int) -> None:
        while self._pending and self._pending[0].arrival <= now:
            req = self._pending.popleft()
            self._t_ms = max(self._t_ms + 1, now * self.cfg.tick_ms)  # strictly increasing timestamps
            self.qps_series.append((now, self.qps.hit(self._t_ms)))
            if not self._session_ok(req, now):
                self._reject(req, now)
                continue
            req.prompt_tokens = len(self.engine.tokenizer.encode(req.prompt))
            self.queue.push(req)

    def _session_ok(self, req: Request, now: int) -> bool:
        if req.session is None:
            return True
        if req.session in self._seen_sessions:
            self.sessions.renew(req.session, now)
            return True
        if self.cfg.max_sessions is not None and self.sessions.count_unexpired(now) >= self.cfg.max_sessions:
            return False
        self.sessions.generate(req.session, now)
        self._seen_sessions.add(req.session)
        return True

    def _admit_waiting(self, now: int) -> None:
        ever_fits = getattr(self.kv, "can_ever_fit", None)
        while len(self.running) < self.cfg.max_batch and len(self.queue):
            req = self.queue.peek()
            if ever_fits is not None and not ever_fits(req):
                # Would need more KV than the whole cache even running alone: admitting it would
                # preempt everyone and then itself, forever. Reject now. This guarantee is what
                # makes "preempt the most recently admitted" livelock-free: the oldest running
                # request can always finish once the others are out of its way.
                self.queue.pop()
                self._reject(req, now)
                continue
            ok = self._budget_ok(req, now) and self.kv.can_admit(req, now)
            if not ok:
                if not self.running:  # can never fit, even on an empty server
                    self.queue.pop()
                    self._reject(req, now)
                    continue
                break  # head-of-line waits for capacity
            self.queue.pop()
            self._admit(req, now)

    def _estimate_ticks(self, req: Request, uncached_tokens: int) -> int:
        return math.ceil(max(uncached_tokens, 1) / self.cfg.prefill_chunk) + req.max_tokens

    def _budget_ok(self, req: Request, now: int) -> bool:
        if self.cfg.token_budget is None:
            return True
        cand = [req.prompt_tokens + req.max_tokens, now, now + self._estimate_ticks(req, req.prompt_tokens)]
        return fits_capacity(list(self._reservations.values()) + [cand], self.cfg.token_budget)

    def _admit(self, req: Request, now: int) -> None:
        req.slot = self.slots.reserve()
        req.admitted_at = now
        req.cached_chars = self.prefix_cache.match(req.prompt)
        rest = req.prompt[req.cached_chars:]
        uncached = len(self.engine.tokenizer.encode(rest)) if rest else 0
        req.prefill_left = math.ceil(uncached / self.cfg.prefill_chunk) if uncached else 0
        req.state = self.engine.start(req.prompt, GenerationConfig(
            max_tokens=req.max_tokens, temperature=req.temperature, top_k=req.top_k,
            seed=req.seed, stop=req.stop))
        self.kv.on_admit(req, now)
        self.running[req.slot] = req
        if self.cfg.token_budget is not None:
            self._reservations[req.rid] = [req.prompt_tokens + req.max_tokens, now,
                                           now + self._estimate_ticks(req, uncached)]

    def _compute(self, now: int) -> bool:
        if not self.running:
            return False
        for slot in sorted(self.running):
            req = self.running.get(slot)
            if req is None:  # preempted earlier in this tick
                continue
            if req.prefill_left > 0:
                req.prefill_left -= 1
                continue
            chunk = self.engine.step(req.state)
            if not self.kv.on_token(req, now) and not self._make_room(req, now):
                continue  # req itself was preempted
            if chunk:
                if req.first_token_at is None:
                    req.first_token_at = now + 1
                req.chunks.append((now, chunk))
                self.events.append((now, req.rid, chunk))
            if req.state.done:
                self._finish(req, now)
        return True

    def _make_room(self, req: Request, now: int) -> bool:
        """KV is full: preempt the most recently admitted request until ``req`` fits (or is itself preempted)."""
        while True:
            victim = max(self.running.values(), key=lambda r: (r.admitted_at, r.slot))
            self._preempt(victim, now)
            if victim is req:
                return False
            if self.kv.on_token(req, now):
                return True

    def _preempt(self, req: Request, now: int) -> None:
        self.kv.on_finish(req, now)
        del self.running[req.slot]
        self.slots.unreserve(req.slot)
        self._reservations.pop(req.rid, None)
        # drop events already streamed for this request: it will be recomputed identically
        self.events = [e for e in self.events if e[1] != req.rid]
        req.reset_runtime()
        req.preemptions += 1
        self.queue.push_front(req)

    def _finish(self, req: Request, now: int) -> None:
        req.finished_at = now + 1
        req.finish_reason = req.state.finish_reason
        req.output = req.state.text
        del self.running[req.slot]
        self.slots.unreserve(req.slot)
        self._reservations.pop(req.rid, None)
        self.kv.on_finish(req, now)
        self.prefix_cache.insert(req.prompt)
        self.latency.add(req.latency)
        self._n_latency += 1

    def _reject(self, req: Request, now: int) -> None:
        req.finished_at = now
        req.finish_reason = "rejected"

    # ------------------------------------------------------------------ report
    def report(self) -> ServerReport:
        plugins = {}
        for name, p in (("kv", self.kv), ("prefix_cache", self.prefix_cache), ("queue", self.queue)):
            rep = getattr(p, "report", None)
            if callable(rep):
                r = rep()
                if r:
                    plugins[name] = r
        return ServerReport(
            name=self.name,
            ticks=self.now,
            requests=list(self.requests),
            events=list(self.events),
            busy=[list(b) for b in self.busy],
            queue_len=list(self.queue_len),
            qps=list(self.qps_series),
            active_sessions=list(self.active_sessions),
            p50_latency=self.latency.median() if self._n_latency else None,
            plugins=plugins,
        )
