"""Framework (M4): earliest-deadline-first waiting queue (``ServerConfig(policy="edf")``).

    q = DeadlineQueue()
    q.push(req)                  # server: on arrival
    q.peek(); q.pop()            # server: admission takes the request with the earliest deadline
    q.position(req)              # 1-based place in line
    q.due_between(100, 160)      # waiting requests whose deadline falls in [100, 160], EDF order
    q.tokens_due(100, 160)       # ... and how many tokens they may still generate
    q.check()                    # [] when every invariant holds

Ordering. Waiting requests live in a binary search tree (``BSTIndex``) whose keys must be distinct
integers. Each request gets a sequence number when it is first pushed, and

    key = deadline · SEQ_SPAN + seq          (no deadline: deadline := NO_DEADLINE)

so keys are distinct, the earliest deadline comes first, equal deadlines are served in arrival order
(FCFS tie-break), and requests without a deadline queue up behind every dated one. Keys are
non-negative (deadlines below 0 are clamped to 0).

Preempted requests (``push_front``) re-enter with their original key: their deadline did not change,
so EDF puts them back where they were — ahead of everything that arrived later with the same deadline.

Statistics, sampled at every arrival (``now`` = the arriving request's arrival tick):
  * overtakes      — how many waiting requests the newcomer jumped ahead of (its position in line);
  * urgent backlog — requests / tokens due within ``urgent_window`` ticks (index range + token counter);
  * deadline gap   — tightest spacing between two distinct pending deadlines, from a second index
                     holding one key per distinct pending deadline.
Token demand per deadline tick is kept in a ``RangeCounter`` (bucket = deadline tick, value =
Σ max_tokens of waiting requests due then), so any deadline window costs O(log n).

Exercises this file calls (M4): index.range_sum directly; through ``BSTIndex``: index.insert,
index.delete, index.kth, index.iter, index.validate, index.build, index.min_gap, prefix.depth,
prefix.level_dump, prefix.fork_point.
"""
from __future__ import annotations

from typing import Iterator

from nanoserve.index.bst_index import BSTIndex, depth_limit
from nanoserve.index.fenwick import RangeCounter
from nanoserve.server.request import Request

SEQ_SPAN = 1_000_000          # sequence numbers per deadline tick (max requests one queue ever orders)
NO_DEADLINE = 10 ** 12        # sort-key "deadline" of requests without one: after every real deadline


class DeadlineQueue:
    """EDF ``WaitingQueue`` on a BST index."""

    def __init__(self, *, urgent_window: int = 100, horizon: int = 256) -> None:
        """``urgent_window``: ticks ahead that count as urgent in the statistics.
        ``horizon``: deadline ticks the token counter covers initially (it grows on demand)."""
        self.index = BSTIndex()                   # request keys, in EDF order
        self.repaired = 0                         # index nodes rewritten by a repairing restore
        self.deadlines = BSTIndex()               # one key per distinct pending deadline
        self._at_deadline: dict[int, int] = {}    # deadline -> waiting requests due then
        self._req_of: dict[int, Request] = {}     # key -> waiting request
        self._key_of: dict[Request, int] = {}     # waiting request -> key
        self._seq_of: dict[Request, int] = {}     # every request ever pushed -> its sequence number
        self._next_seq = 0
        self._due_size = max(1, horizon)
        self._due = RangeCounter([0] * self._due_size)
        self.undated_tokens = 0                   # Σ max_tokens of waiting requests without a deadline
        self.urgent_window = urgent_window
        # run statistics for report()
        self.pushes = self.pops = self.removes = self.requeues = 0
        self.peak_len = 0
        self.overtakes = self.max_overtake = 0
        self.peak_urgent = self.peak_urgent_tokens = 0
        self.tightest_gap: int | None = None

    # ------------------------------------------------------------------ keys
    @staticmethod
    def deadline_of(key: int) -> int | None:
        d = key // SEQ_SPAN
        return None if d >= NO_DEADLINE else d

    @staticmethod
    def _deadline(req: Request) -> int | None:
        if req.deadline is None:
            return None
        if req.deadline >= NO_DEADLINE:
            raise ValueError(f"deadline {req.deadline} out of range")
        return max(req.deadline, 0)

    def _key(self, req: Request) -> int:
        seq = self._seq_of.get(req)
        if seq is None:
            if self._next_seq >= SEQ_SPAN:
                raise OverflowError(f"a DeadlineQueue orders at most {SEQ_SPAN} distinct requests")
            seq = self._seq_of[req] = self._next_seq
            self._next_seq += 1
        d = self._deadline(req)
        return (NO_DEADLINE if d is None else d) * SEQ_SPAN + seq

    # ------------------------------------------------------------------ WaitingQueue protocol
    def push(self, req: Request) -> None:
        self._enter(req)
        self.pushes += 1
        self._sample_arrival(req)

    def push_front(self, req: Request) -> None:
        """A preempted request comes back with its original key (see module docstring)."""
        self._enter(req)
        self.requeues += 1

    def peek(self) -> Request | None:
        if not len(self.index):
            return None
        return self._req_of[self.index.first()]

    def pop(self) -> Request:
        if not len(self.index):
            raise IndexError("pop from an empty DeadlineQueue")
        req = self._req_of[self.index.first()]
        self._leave(req)
        self.pops += 1
        return req

    def remove(self, req: Request) -> None:
        if req not in self._key_of:
            raise ValueError(f"request {req.rid} is not waiting")
        self._leave(req)
        self.removes += 1

    def __len__(self) -> int:
        return len(self.index)

    def __iter__(self) -> Iterator[Request]:
        """Waiting requests in EDF order (a snapshot, so the caller may mutate the queue meanwhile)."""
        return iter([self._req_of[k] for k in self.index.keys()])

    # ------------------------------------------------------------------ bookkeeping
    def _enter(self, req: Request) -> None:
        if req in self._key_of:
            raise ValueError(f"request {req.rid} is already waiting")
        key = self._key(req)                      # fresh: seq is unique per request
        self.index.add(key)
        self._req_of[key] = req
        self._key_of[req] = key
        d = self.deadline_of(key)
        if d is not None:
            n = self._at_deadline.get(d, 0)
            if n == 0:
                self.deadlines.add(d)             # first waiting request due at d
            self._at_deadline[d] = n + 1
        self._count_tokens(d, req.max_tokens)
        self.peak_len = max(self.peak_len, len(self))

    def _leave(self, req: Request) -> None:
        key = self._key_of.pop(req)
        del self._req_of[key]
        self.index.discard(key)
        d = self.deadline_of(key)                 # from the key: the one the request was filed under
        if d is not None:
            n = self._at_deadline[d] - 1
            if n == 0:
                del self._at_deadline[d]
                self.deadlines.discard(d)         # last waiting request due at d
            else:
                self._at_deadline[d] = n
        self._count_tokens(d, -req.max_tokens)

    def _count_tokens(self, d: int | None, delta: int) -> None:
        """Add ``delta`` tokens to deadline bucket ``d`` (None = the undated total)."""
        if d is None:
            self.undated_tokens += delta
            return
        if d >= self._due_size:
            self._grow_due(d + 1)
        # RangeCounter.update *assigns*: read the bucket (a one-element range), write back the new total.
        self._due.update(d, self._due.sum_range(d, d) + delta)

    def _grow_due(self, need: int) -> None:
        size = self._due_size
        while size < need:
            size *= 2
        old = [self._due.sum_range(i, i) for i in range(self._due_size)]
        self._due = RangeCounter(old + [0] * (size - self._due_size))
        self._due_size = size

    def _sample_arrival(self, req: Request) -> None:
        now = req.arrival
        overtaken = len(self) - self.position(req)
        self.overtakes += overtaken
        self.max_overtake = max(self.max_overtake, overtaken)
        urgent = self.due_between(now, now + self.urgent_window)
        self.peak_urgent = max(self.peak_urgent, len(urgent))
        self.peak_urgent_tokens = max(self.peak_urgent_tokens, self.tokens_due(now, now + self.urgent_window))
        gap = self.deadline_gap()
        if gap is not None and (self.tightest_gap is None or gap < self.tightest_gap):
            self.tightest_gap = gap

    # ------------------------------------------------------------------ checkpoint support
    def owners(self) -> dict[int, Request]:
        """key -> waiting request, in EDF order."""
        return {k: self._req_of[k] for k in self.index.keys()}

    def sequence_numbers(self) -> dict[Request, int]:
        """Every request this queue has ever ordered -> its sequence number (tie-break among equal deadlines)."""
        return dict(self._seq_of)

    @classmethod
    def from_index(cls, root, owners: dict[int, Request], seqs: dict[Request, int], next_seq: int,
                   **kw) -> "DeadlineQueue":
        """A queue around an already-built request index (``root``, e.g. restored from a checkpoint,
        kept with its exact shape) whose keys belong to ``owners``. Derived state is recomputed."""
        q = cls(**kw)
        q._seq_of = dict(seqs)
        q.index.adopt(root, len(owners))
        for key, req in owners.items():
            q._req_of[key] = req
            q._key_of[req] = key
            q._seq_of[req] = key % SEQ_SPAN
            d = q.deadline_of(key)
            if d is not None:
                q._at_deadline[d] = q._at_deadline.get(d, 0) + 1
            q._count_tokens(d, req.max_tokens)
        q.deadlines.reset(sorted(q._at_deadline))
        q._next_seq = next_seq
        q.peak_len = len(owners)
        return q

    # ------------------------------------------------------------------ queries
    def position(self, req: Request) -> int:
        """1-based place of a waiting request in line (1 = admitted next)."""
        return self.index.rank(self._key_of[req])

    def at(self, k: int) -> Request:
        """The request at 1-based position ``k`` in line."""
        return self._req_of[self.index.kth(k)]

    def due_between(self, lo: int, hi: int) -> list[Request]:
        """Waiting requests with lo <= deadline <= hi, in EDF order."""
        lo, hi = max(lo, 0), min(hi, NO_DEADLINE - 1)
        if hi < lo:
            return []
        keys = self.index.between(lo * SEQ_SPAN, hi * SEQ_SPAN + SEQ_SPAN - 1)
        return [self._req_of[k] for k in keys]

    def tokens_due(self, lo: int, hi: int) -> int:
        """Σ max_tokens of waiting requests whose deadline is in [lo, hi]."""
        lo, hi = max(lo, 0), min(hi, self._due_size - 1)
        return self._due.sum_range(lo, hi) if lo <= hi else 0

    def deadline_gap(self) -> int | None:
        """Smallest spacing between two distinct pending deadlines (None if fewer than two)."""
        return self.deadlines.min_gap()

    # ------------------------------------------------------------------ health
    def check(self) -> list[str]:
        """Audit every invariant; returns the problems found (empty list = healthy)."""
        problems = [f"request index: {p}" for p in self.index.check()]
        problems += [f"deadline index: {p}" for p in self.deadlines.check()]
        keys = list(self.index.keys())
        if sorted(self._key_of.values()) != keys or sorted(self._req_of) != keys:
            problems.append("request maps out of sync with the index")
        for key, req in self._req_of.items():
            if self._key_of.get(req) != key or self._key(req) != key:
                problems.append(f"request {req.rid} has a stale key")
        if list(self.deadlines.keys()) != sorted(self._at_deadline):
            problems.append("deadline index out of sync")
        dated = sum(r.max_tokens for r in self._key_of if r.deadline is not None)
        if self.tokens_due(0, self._due_size - 1) != dated:
            problems.append("deadline token counter out of sync")
        return problems

    def levels(self) -> list[list[str]]:
        """Debug view: the request index level by level, each key as ``deadline#seq`` (``-`` = none)."""
        def label(key: int) -> str:
            d = self.deadline_of(key)
            return f"{'-' if d is None else d}#{key % SEQ_SPAN}"
        return [[label(k) for k in level] for level in self.index.levels()]

    def report(self) -> dict:
        return {
            "policy": "edf",
            "pushes": self.pushes,
            "pops": self.pops,
            "removes": self.removes,
            "requeues": self.requeues,
            "peak_len": self.peak_len,
            "overtakes": self.overtakes,
            "max_overtake": self.max_overtake,
            "peak_urgent": self.peak_urgent,
            "peak_urgent_tokens": self.peak_urgent_tokens,
            "tightest_deadline_gap": self.tightest_gap,
            "index_rebuilds": self.index.rebuilds,
            "index_max_depth": self.index.deepest,
            "index_depth_limit_at_peak": round(depth_limit(self.peak_len), 1),
            "healthy": not self.check(),
        }
