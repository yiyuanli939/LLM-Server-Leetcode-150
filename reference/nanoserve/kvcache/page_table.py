from __future__ import annotations


# LC 74 Search a 2D Matrix
def page_exists(table: list[list[int]], addr: int) -> bool:
    m, n = len(table), len(table[0])
    lo, hi = 0, m * n - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        v = table[mid // n][mid % n]
        if v == addr:
            return True
        if v < addr:
            lo = mid + 1
        else:
            hi = mid - 1
    return False
