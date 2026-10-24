"""Reference: metrics.qps / metrics.window_max / metrics.window_median."""
from __future__ import annotations

import heapq
from collections import Counter, deque


# LC 933 Number of Recent Calls
class QpsCounter:
    def __init__(self) -> None:
        self.q: deque[int] = deque()

    def hit(self, t: int) -> int:
        self.q.append(t)
        while self.q[0] < t - 3000:
            self.q.popleft()
        return len(self.q)


# LC 239 Sliding Window Maximum
def window_max(latencies: list[int], k: int) -> list[int]:
    dq: deque[int] = deque()  # indices, values decreasing
    out: list[int] = []
    for i, x in enumerate(latencies):
        while dq and latencies[dq[-1]] <= x:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - k:
            dq.popleft()
        if i >= k - 1:
            out.append(latencies[dq[0]])
    return out


# LC 480 Sliding Window Median (two heaps + lazy deletion)
def window_median(latencies: list[int], k: int) -> list[float]:
    lo: list[int] = []  # max-heap (negated), holds the smaller half (+1 if k odd)
    hi: list[int] = []  # min-heap, holds the larger half
    pending: Counter[int] = Counter()

    def prune(heap: list[int], sign: int) -> None:
        while heap and pending[sign * heap[0]]:
            pending[sign * heap[0]] -= 1
            heapq.heappop(heap)

    def median() -> float:
        if k % 2:
            return float(-lo[0])
        return (-lo[0] + hi[0]) / 2

    for x in latencies[:k]:
        heapq.heappush(lo, -x)
    for _ in range(k // 2):
        heapq.heappush(hi, -heapq.heappop(lo))
    out = [median()]

    for i in range(k, len(latencies)):
        x, y = latencies[i], latencies[i - k]
        # balance > 0 means lo has too many valid elements, < 0 means hi does
        balance = 0
        if y <= -lo[0]:
            balance -= 1
        else:
            balance += 1
        pending[y] += 1
        if lo and x <= -lo[0]:
            heapq.heappush(lo, -x)
            balance += 1
        else:
            heapq.heappush(hi, x)
            balance -= 1
        if balance > 0:
            heapq.heappush(hi, -heapq.heappop(lo))
        elif balance < 0:
            heapq.heappush(lo, -heapq.heappop(hi))
        prune(lo, -1)
        prune(hi, 1)
        out.append(median())
    return out
