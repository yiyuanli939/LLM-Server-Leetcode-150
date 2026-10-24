"""Reference: sched.capacity_ok."""
from __future__ import annotations


# LC 1094 Car Pooling
def fits_capacity(requests: list[list[int]], capacity: int) -> bool:
    events: list[tuple[int, int]] = []
    for blocks, start, end in requests:
        events.append((start, blocks))
        events.append((end, -blocks))
    events.sort()  # at equal time, releases (negative) come before acquisitions
    used = 0
    for _, delta in events:
        used += delta
        if used > capacity:
            return False
    return True
