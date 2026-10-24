from __future__ import annotations

import heapq


# LC 2034 Stock Price Fluctuation
class CorrectableSeries:
    def __init__(self) -> None:
        self.at: dict[int, int] = {}
        self.latest = 0
        self.max_heap: list[tuple[int, int]] = []  # (-value, ts), lazily invalidated
        self.min_heap: list[tuple[int, int]] = []  # (value, ts), lazily invalidated

    def update(self, ts: int, value: int) -> None:
        self.at[ts] = value
        self.latest = max(self.latest, ts)
        heapq.heappush(self.max_heap, (-value, ts))
        heapq.heappush(self.min_heap, (value, ts))

    def current(self) -> int:
        return self.at[self.latest]

    def maximum(self) -> int:
        while self.at[self.max_heap[0][1]] != -self.max_heap[0][0]:
            heapq.heappop(self.max_heap)
        return -self.max_heap[0][0]

    def minimum(self) -> int:
        while self.at[self.min_heap[0][1]] != self.min_heap[0][0]:
            heapq.heappop(self.min_heap)
        return self.min_heap[0][0]
