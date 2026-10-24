from __future__ import annotations

import heapq


# LC 295 Find Median from Data Stream
class MedianTracker:
    def __init__(self) -> None:
        self._low: list[int] = []   # max-heap (negated), holds the smaller half
        self._high: list[int] = []  # min-heap, holds the larger half

    def add(self, x: int) -> None:
        heapq.heappush(self._low, -x)
        heapq.heappush(self._high, -heapq.heappop(self._low))
        if len(self._high) > len(self._low):
            heapq.heappush(self._low, -heapq.heappop(self._high))

    def median(self) -> float:
        if len(self._low) > len(self._high):
            return float(-self._low[0])
        return (-self._low[0] + self._high[0]) / 2.0


# LC 4 Median of Two Sorted Arrays
def merged_median(a: list[int], b: list[int]) -> float:
    if len(a) > len(b):
        a, b = b, a
    m, n = len(a), len(b)
    half = (m + n + 1) // 2
    lo, hi = 0, m
    neg, pos = float("-inf"), float("inf")
    while lo <= hi:
        i = (lo + hi) // 2  # elements taken from a into the left half
        j = half - i
        a_left = a[i - 1] if i > 0 else neg
        a_right = a[i] if i < m else pos
        b_left = b[j - 1] if j > 0 else neg
        b_right = b[j] if j < n else pos
        if a_left <= b_right and b_left <= a_right:
            left_max = max(a_left, b_left)
            if (m + n) % 2:
                return float(left_max)
            return (left_max + min(a_right, b_right)) / 2.0
        if a_left > b_right:
            hi = i - 1
        else:
            lo = i + 1
    raise ValueError("inputs must be sorted")
