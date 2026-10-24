"""Reference: sched.sjf / sched.assign_workers / sched.busiest_worker."""
from __future__ import annotations

import heapq


# LC 1834 Single-Threaded CPU
def sjf_order(tasks: list[list[int]]) -> list[int]:
    order = sorted(range(len(tasks)), key=lambda i: tasks[i][0])
    ready: list[tuple[int, int]] = []
    out: list[int] = []
    t = 0
    i = 0
    while len(out) < len(tasks):
        if not ready and i < len(order) and t < tasks[order[i]][0]:
            t = tasks[order[i]][0]
        while i < len(order) and tasks[order[i]][0] <= t:
            idx = order[i]
            heapq.heappush(ready, (tasks[idx][1], idx))
            i += 1
        dur, idx = heapq.heappop(ready)
        out.append(idx)
        t += dur
    return out


# LC 1882 Process Tasks Using Servers
def assign_workers(weights: list[int], tasks: list[int]) -> list[int]:
    free = [(w, i) for i, w in enumerate(weights)]
    heapq.heapify(free)
    busy: list[tuple[int, int, int]] = []  # (free_at, weight, index)
    ans: list[int] = []
    t = 0
    for j, dur in enumerate(tasks):
        t = max(t, j)
        if not free:
            t = max(t, busy[0][0])
        while busy and busy[0][0] <= t:
            _, w, i = heapq.heappop(busy)
            heapq.heappush(free, (w, i))
        w, i = heapq.heappop(free)
        ans.append(i)
        heapq.heappush(busy, (t + dur, w, i))
    return ans


# LC 2402 Meeting Rooms III
def busiest_worker(n: int, jobs: list[list[int]]) -> int:
    free = list(range(n))
    busy: list[tuple[int, int]] = []  # (end_time, worker)
    count = [0] * n
    for start, end in sorted(jobs):
        while busy and busy[0][0] <= start:
            _, w = heapq.heappop(busy)
            heapq.heappush(free, w)
        if free:
            w = heapq.heappop(free)
            heapq.heappush(busy, (end, w))
        else:
            t, w = heapq.heappop(busy)
            heapq.heappush(busy, (t + end - start, w))
        count[w] += 1
    return max(range(n), key=lambda w: (count[w], -w))
