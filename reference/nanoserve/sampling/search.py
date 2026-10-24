"""Reference: sample.cdf_index."""
from __future__ import annotations


# LC 35 Search Insert Position
def cdf_index(cdf: list[float], r: float) -> int:
    lo, hi = 0, len(cdf)
    while lo < hi:
        mid = (lo + hi) // 2
        if cdf[mid] < r:
            lo = mid + 1
        else:
            hi = mid
    return lo
