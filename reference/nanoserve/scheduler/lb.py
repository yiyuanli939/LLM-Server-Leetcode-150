"""Reference: sched.rr_busiest."""
from __future__ import annotations

import heapq


# LC 1606 Find Servers That Handled Most Number of Requests
def busiest_servers(k: int, arrival: list[int], load: list[int]) -> list[int]:
    # Free workers are stored as "virtual ids" v with v % k == worker and i <= v < i + k at step i,
    # so the heap minimum is exactly the first free worker at or after i % k (wrapping around).
    # Invariant: the minimum is popped every step, so no stored v ever falls below the current i.
    free = list(range(k))
    busy: list[tuple[int, int]] = []  # (free_at, worker)
    count = [0] * k
    for i, (t, dur) in enumerate(zip(arrival, load)):
        while busy and busy[0][0] <= t:
            _, w = heapq.heappop(busy)
            heapq.heappush(free, i + (w - i) % k)
        if not free:
            continue
        w = heapq.heappop(free) % k
        count[w] += 1
        heapq.heappush(busy, (t + dur, w))
    best = max(count)
    return [w for w in range(k) if count[w] == best]
