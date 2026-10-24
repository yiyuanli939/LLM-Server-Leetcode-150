"""Framework (M3): the token-slot arena, i.e. every running sequence's ``req_to_token`` row.

The attention kernel needs, for every token position of a sequence, the KV slot that holds it
(``block * block_size + offset``). Like SGLang's ``req_to_token`` pool, those slot numbers live in
one shared arena of ``size`` cells: each sequence owns a few contiguous *segments* of it. Segments are
carved out first-fit by ``MemoryAllocator`` (kv.mem_alloc), with the sequence id as the owner. A
sequence gets one segment at admission and another one whenever it outgrows what it has. When it
finishes, ``free(owner)`` returns all of its segments at once. Because sequences finish in any
order, the arena fragments, and first-fit can fail even when enough cells are free in total.

Every live segment is also entered in ``AddressRanges`` (kv.address_ranges), the arena's bounds
checker. Each read and write must land on an address that is currently allocated (``query_range``).
Released segments are removed from it, so a stale access fails, as it would under a memory sanitizer.

Exercises this file calls (M3): kv.mem_alloc, kv.address_ranges.
"""
from __future__ import annotations

from nanoserve.kvcache.address_ranges import AddressRanges
from nanoserve.kvcache.memalloc import MemoryAllocator


class ArenaBoundsError(RuntimeError):
    pass


class TokenArena:
    def __init__(self, size: int) -> None:
        if size < 1:
            raise ValueError("arena size must be >= 1")
        self.size = size
        self.mem = MemoryAllocator(size)
        self.bounds = AddressRanges()
        self.cells = [-1] * size                              # the req_to_token entries
        self.rows: dict[int, list[tuple[int, int]]] = {}      # owner -> [(start, length), ...]
        self.used = 0
        self.peak = 0
        self.failed = 0        # reservations that found no contiguous gap

    # ------------------------------------------------------------------ segments
    def fits(self, n: int, owner: int) -> bool:
        """Would a first ``n``-cell segment for (a new) ``owner`` fit right now? Tries it and undoes it."""
        if owner in self.rows:
            raise ValueError("fits() probes for an owner that holds nothing yet")
        if self.mem.allocate(n, owner) < 0:
            return False
        self.mem.free(owner)
        return True

    def reserve(self, owner: int, n: int) -> bool:
        """Give ``owner`` another segment of ``n`` cells (first fit). False if no gap is big enough."""
        start = self.mem.allocate(n, owner)
        if start < 0:
            self.failed += 1
            return False
        self.bounds.add_range(start, start + n)
        self.rows.setdefault(owner, []).append((start, n))
        self.used += n
        self.peak = max(self.peak, self.used)
        return True

    def release(self, owner: int) -> int:
        segs = self.rows.pop(owner, [])
        n = self.mem.free(owner)
        for start, size in segs:
            self.bounds.remove_range(start, start + size)
        if n != sum(size for _, size in segs):
            raise RuntimeError(f"arena accounting mismatch for sequence {owner}")
        self.used -= n
        return n

    def capacity(self, owner: int) -> int:
        return sum(n for _, n in self.rows.get(owner, ()))

    # ------------------------------------------------------------------ cells
    def address(self, owner: int, pos: int) -> int:
        """Arena address of the owner's ``pos``-th token, or -1 if its row is shorter."""
        for start, n in self.rows.get(owner, ()):
            if pos < n:
                return start + pos
            pos -= n
        return -1

    def _checked(self, owner: int, pos: int) -> int:
        addr = self.address(owner, pos)
        if addr < 0 or not self.bounds.query_range(addr, addr + 1):
            raise ArenaBoundsError(f"token slot out of bounds: sequence {owner}, position {pos}")
        return addr

    def write(self, owner: int, pos: int, slot: int) -> None:
        self.cells[self._checked(owner, pos)] = slot

    def read(self, owner: int, pos: int) -> int:
        return self.cells[self._checked(owner, pos)]

    # ------------------------------------------------------------------ debugging
    def check(self, live: dict[int, int]) -> list[str]:
        """``live``: owner -> tokens stored. Returns the problems found (empty if consistent)."""
        bad = []
        for owner, segs in self.rows.items():
            if owner not in live:
                bad.append(f"arena: finished sequence {owner} still owns {self.capacity(owner)} cells")
                continue
            for start, n in segs:
                if not self.bounds.query_range(start, start + n):
                    bad.append(f"arena: segment [{start}, {start + n}) of sequence {owner} is not tracked")
            if live[owner] > self.capacity(owner):
                bad.append(f"arena: sequence {owner} stores {live[owner]} tokens in {self.capacity(owner)} cells")
        for owner in live:
            if owner not in self.rows and live[owner]:
                bad.append(f"arena: sequence {owner} has no row")
        if self.used != sum(self.capacity(o) for o in self.rows):
            bad.append("arena: used-cell counter out of sync")
        return bad

    def stats(self) -> dict:
        return {"size": self.size, "used": self.used, "peak": self.peak, "rows": len(self.rows),
                "failed_reservations": self.failed}
