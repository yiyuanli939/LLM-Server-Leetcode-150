"""Reference: dash.region_sum."""
from __future__ import annotations


# LC 304 Range Sum Query 2D - Immutable
class RegionSum:
    def __init__(self, grid: list[list[int]]) -> None:
        m, n = len(grid), len(grid[0])
        p = [[0] * (n + 1) for _ in range(m + 1)]
        for r in range(m):
            row_sum = 0
            for c in range(n):
                row_sum += grid[r][c]
                p[r + 1][c + 1] = p[r][c + 1] + row_sum
        self.p = p

    def sum_region(self, r1: int, c1: int, r2: int, c2: int) -> int:
        p = self.p
        return p[r2 + 1][c2 + 1] - p[r1][c2 + 1] - p[r2 + 1][c1] + p[r1][c1]
