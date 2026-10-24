from __future__ import annotations

import heapq


# LC 703 Kth Largest Element in a Stream
class KthSlowest:
    def __init__(self, k: int, initial: list[int]) -> None:
        self.k = k
        self.heap = list(initial)  # min-heap holding the k largest values seen so far
        heapq.heapify(self.heap)
        while len(self.heap) > k:
            heapq.heappop(self.heap)

    def add(self, latency: int) -> int:
        if len(self.heap) < self.k:
            heapq.heappush(self.heap, latency)
        elif latency > self.heap[0]:
            heapq.heapreplace(self.heap, latency)
        return self.heap[0]
