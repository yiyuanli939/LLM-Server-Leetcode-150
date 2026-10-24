from __future__ import annotations

import heapq
from collections import deque


# LC 743 Network Delay Time
def broadcast_latency(edges: list[list[int]], n: int, src: int) -> int:
    adj: list[list[tuple[int, int]]] = [[] for _ in range(n + 1)]
    for u, v, w in edges:
        adj[u].append((v, w))
    dist: dict[int, int] = {}
    heap = [(0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if u in dist:
            continue
        dist[u] = d
        for v, w in adj[u]:
            if v not in dist:
                heapq.heappush(heap, (d + w, v))
    return max(dist.values()) if len(dist) == n else -1


# LC 2050 Parallel Courses III
def critical_path_time(n: int, deps: list[list[int]], cost: list[int]) -> int:
    adj: list[list[int]] = [[] for _ in range(n)]
    indeg = [0] * n
    for a, b in deps:
        adj[a - 1].append(b - 1)
        indeg[b - 1] += 1
    start = [0] * n
    q = deque(i for i in range(n) if indeg[i] == 0)
    best = 0
    while q:
        u = q.popleft()
        finish = start[u] + cost[u]
        best = max(best, finish)
        for v in adj[u]:
            start[v] = max(start[v], finish)
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return best
