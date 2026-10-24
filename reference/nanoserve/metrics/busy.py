from __future__ import annotations

from bisect import bisect_left, bisect_right


# LC 2276 Count Integers in Intervals
class BusyTimeCounter:
    def __init__(self) -> None:
        # Disjoint, sorted closed intervals [starts[i], ends[i]].
        self.starts: list[int] = []
        self.ends: list[int] = []
        self.total = 0

    def add(self, left: int, right: int) -> None:
        # Intervals overlapping [left, right] are exactly indices lo..hi-1.
        lo = bisect_left(self.ends, left)
        hi = bisect_right(self.starts, right)
        if lo < hi:
            left = min(left, self.starts[lo])
            right = max(right, self.ends[hi - 1])
            for i in range(lo, hi):
                self.total -= self.ends[i] - self.starts[i] + 1
        self.starts[lo:hi] = [left]
        self.ends[lo:hi] = [right]
        self.total += right - left + 1

    def count(self) -> int:
        return self.total
