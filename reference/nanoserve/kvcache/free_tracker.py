"""Reference: kv.free_tracker."""
from __future__ import annotations

import bisect


# LC 352 Data Stream as Disjoint Intervals
class FreeRangeTracker:
    def __init__(self) -> None:
        self.starts: list[int] = []  # sorted starts of disjoint, non-adjacent closed intervals
        self.ends: list[int] = []

    def add(self, block: int) -> None:
        i = bisect.bisect_right(self.starts, block)  # intervals [0, i) start at or before block
        if i > 0 and self.ends[i - 1] >= block:      # already covered
            return
        join_left = i > 0 and self.ends[i - 1] == block - 1
        join_right = i < len(self.starts) and self.starts[i] == block + 1
        if join_left and join_right:
            self.ends[i - 1] = self.ends[i]
            del self.starts[i], self.ends[i]
        elif join_left:
            self.ends[i - 1] = block
        elif join_right:
            self.starts[i] = block
        else:
            self.starts.insert(i, block)
            self.ends.insert(i, block)

    def ranges(self) -> list[list[int]]:
        return [[s, e] for s, e in zip(self.starts, self.ends)]
