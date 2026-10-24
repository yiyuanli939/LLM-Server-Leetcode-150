"""Reference: sched.min_workers / sched.slo_bound."""
from __future__ import annotations

import heapq


# LC 2406 Divide Intervals Into Minimum Number of Groups
def min_workers(intervals: list[list[int]]) -> int:
    ends: list[int] = []  # min-heap of each worker's last occupied time
    for start, end in sorted(intervals):
        if ends and ends[0] < start:  # closed intervals: must end strictly before we start
            heapq.heapreplace(ends, end)
        else:
            heapq.heappush(ends, end)
    return len(ends)


# LC 630 Course Schedule III
def max_on_time(jobs: list[list[int]]) -> int:
    taken: list[int] = []  # max-heap (negated) of durations of the jobs we keep
    t = 0
    for duration, deadline in sorted(jobs, key=lambda j: j[1]):
        heapq.heappush(taken, -duration)
        t += duration
        if t > deadline:  # drop the longest job so far; never hurts, frees the most time
            t += heapq.heappop(taken)
    return len(taken)
