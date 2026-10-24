"""Reference: sched.maintenance."""
from __future__ import annotations

import bisect


# LC 729 My Calendar I
class MaintenanceCalendar:
    def __init__(self) -> None:
        self.starts: list[int] = []  # sorted, disjoint bookings
        self.ends: list[int] = []

    def book(self, start: int, end: int) -> bool:
        i = bisect.bisect_right(self.starts, start)
        if i > 0 and self.ends[i - 1] > start:      # previous booking runs into us
            return False
        if i < len(self.starts) and self.starts[i] < end:  # next booking starts before we end
            return False
        self.starts.insert(i, start)
        self.ends.insert(i, end)
        return True
