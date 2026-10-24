from __future__ import annotations


# LC 452 Minimum Number of Arrows to Burst Balloons
def min_launches(windows: list[list[int]]) -> int:
    count = 0
    last = None
    for s, e in sorted(windows, key=lambda w: w[1]):
        if last is None or s > last:
            count += 1
            last = e
    return count


