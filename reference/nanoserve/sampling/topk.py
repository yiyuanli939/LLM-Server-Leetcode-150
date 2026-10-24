"""Reference: sample.kth_largest."""
from __future__ import annotations

import heapq


# LC 215 Kth Largest Element in an Array
def kth_largest(logits: list[float], k: int) -> float:
    heap = list(logits[:k])
    heapq.heapify(heap)
    for x in logits[k:]:
        if x > heap[0]:
            heapq.heapreplace(heap, x)
    return heap[0]
