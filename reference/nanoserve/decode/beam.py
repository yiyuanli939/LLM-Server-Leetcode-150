"""Reference: two-step beam expansion."""
from __future__ import annotations

import heapq


# LC 373 Find K Pairs with Smallest Sums
def k_best_pairs(a: list[int], b: list[int], k: int) -> list[list[int]]:
    heap = [(a[i] + b[0], i, 0) for i in range(min(k, len(a)))]
    heapq.heapify(heap)
    out: list[list[int]] = []
    while heap and len(out) < k:
        _, i, j = heapq.heappop(heap)
        out.append([a[i], b[j]])
        if j + 1 < len(b):
            heapq.heappush(heap, (a[i] + b[j + 1], i, j + 1))
    return out
