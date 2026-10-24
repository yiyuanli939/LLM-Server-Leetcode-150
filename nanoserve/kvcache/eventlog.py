"""Framework (M3): the KV manager's flight recorder, a fixed-size ring buffer of recent block events.

    log = EventLog(capacity=64)
    ts = log.append(tick=3, kind="alloc", block=7, sid=2)   # returns the event number
    log.find(ts)            # the event, or None once it has been overwritten
    log.chronological()     # oldest → newest

Writers store each event at a cursor that wraps around, overwriting the oldest event. The columns
(timestamp, tick, kind, block, sequence) are plain int arrays without a header, so a reader looking
at a dump (or ``report()``) recovers the order from the timestamps alone. Timestamps are strictly
increasing event numbers, so once the buffer has wrapped, the timestamp column is a sorted array
rotated at the cursor:

  * oldest event      = ring_min(ts)                  (kv.ring_head)
  * event by number   = ring_search(ts, number)       (kv.ring_search); the manager uses it to
                        quote a block's last event when it diagnoses a double free or a leak
  * chronological dump: rotate copies of the columns right by (n - index of the oldest) (kv.rotate_buffer)

Exercises this file calls (M3): kv.ring_head, kv.ring_search, kv.rotate_buffer.
"""
from __future__ import annotations

from dataclasses import dataclass

from nanoserve.kvcache.ring import ring_min, ring_search, rotate_right

# alloc/cow/restore: a fresh block gets content for a sequence; revive: a cached block is reused by a
# prefix hit; share: one more sequence references an in-use block; charge: the block is re-charged to
# another holder; cache/drop: the last reference went away (content kept as cache / block freed);
# offload: a cached block is evicted to the host tier; quarantine: the block was freed twice.
KINDS = ("alloc", "cow", "restore", "revive", "share", "charge", "cache", "drop", "offload", "quarantine")
KIND_CODE = {k: i for i, k in enumerate(KINDS)}
MAX_CAPACITY = 5000


@dataclass(frozen=True)
class Event:
    ts: int      # event number (1, 2, 3, ...)
    tick: int
    kind: str
    block: int
    sid: int     # sequence id (0 = nobody)


class EventLog:
    def __init__(self, capacity: int = 64) -> None:
        if not 1 <= capacity <= MAX_CAPACITY:
            raise ValueError(f"event log capacity must be in [1, {MAX_CAPACITY}]")
        self.capacity = capacity
        self.ts = [0] * capacity
        self.tick = [0] * capacity
        self.kind = [0] * capacity
        self.block = [0] * capacity
        self.sid = [0] * capacity
        self.total = 0        # events ever appended (= the last timestamp)
        self._cursor = 0

    def __len__(self) -> int:
        return min(self.total, self.capacity)

    def append(self, tick: int, kind: str, block: int, sid: int) -> int:
        self.total += 1
        i = self._cursor
        self.ts[i], self.tick[i], self.kind[i], self.block[i], self.sid[i] = (
            self.total, tick, KIND_CODE[kind], block, sid)
        self._cursor = (i + 1) % self.capacity
        return self.total

    # ------------------------------------------------------------------ readers (timestamps only)
    def _stamps(self) -> list[int]:
        n = len(self)
        return self.ts if n == self.capacity else self.ts[:n]   # before wrapping: a sorted prefix

    def oldest(self) -> int | None:
        """Timestamp of the oldest event still in the buffer."""
        return ring_min(self._stamps()) if len(self) else None

    def _event(self, i: int) -> Event:
        return Event(self.ts[i], self.tick[i], KINDS[self.kind[i]], self.block[i], self.sid[i])

    def find(self, ts: int) -> Event | None:
        """The event with timestamp ``ts``, or None if it was never logged or got overwritten."""
        if not len(self):
            return None
        i = ring_search(self._stamps(), ts)
        return None if i < 0 else self._event(i)

    def chronological(self) -> list[Event]:
        n = len(self)
        if not n:
            return []
        cols = [c[:n] for c in (self.ts, self.tick, self.kind, self.block, self.sid)]  # copies
        start = ring_search(cols[0], ring_min(cols[0]))   # where the oldest event sits
        for col in cols:
            rotate_right(col, (n - start) % n)
        ts, tick, kind, block, sid = cols
        return [Event(ts[i], tick[i], KINDS[kind[i]], block[i], sid[i]) for i in range(n)]
