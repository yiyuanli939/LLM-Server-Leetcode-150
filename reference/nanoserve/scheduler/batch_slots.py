"""Reference: sched.slots."""
from __future__ import annotations

import heapq


# LC 1845 Seat Reservation Manager
class SlotAllocator:
    def __init__(self, n: int) -> None:
        # Slots >= next_fresh were never handed out; returned slots (all < next_fresh) sit in a
        # min-heap, so whenever the heap is non-empty its top is the smallest free slot.
        self.next_fresh = 1
        self.returned: list[int] = []

    def reserve(self) -> int:
        if self.returned:
            return heapq.heappop(self.returned)
        slot = self.next_fresh
        self.next_fresh += 1
        return slot

    def unreserve(self, slot: int) -> None:
        heapq.heappush(self.returned, slot)
