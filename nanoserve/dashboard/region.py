"""监控面板上的热力图区域统计。

面板把各 worker、各时间桶的指标画成一张二维热力图，用户可以框选任意矩形区域查看合计值。
热力图数据在一次刷新内不变，而框选查询非常频繁，因此需要预处理后做到每次查询 O(1)。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("dash.region_sum")
class RegionSum:
    """热力图任意矩形区域求和，查询 O(1)。

    规格：
      - 构造：grid 为 m x n 的整数矩阵（1 <= m, n；元素可为负），构造后不会再被修改。
      - sum_region(r1, c1, r2, c2)：返回以 (r1, c1) 为左上角、(r2, c2) 为右下角的矩形内
        所有元素之和，四条边都包含在内。行列下标从 0 开始；
        保证 0 <= r1 <= r2 < m，0 <= c1 <= c2 < n。
      - 复杂度：构造 O(m·n)，每次 sum_region 为 O(1)。

    示例：
      >>> g = [[3, 0, 1, 4, 2],
      ...      [5, 6, 3, 2, 1],
      ...      [1, 2, 0, 1, 5],
      ...      [4, 1, 0, 1, 7],
      ...      [1, 0, 3, 0, 5]]
      >>> rs = RegionSum(g)
      >>> rs.sum_region(2, 1, 4, 3), rs.sum_region(1, 1, 2, 2), rs.sum_region(1, 2, 2, 4)
      (8, 11, 12)
    """

    def __init__(self, grid: list[list[int]]) -> None:
        raise TODO("dash.region_sum")

    def sum_region(self, r1: int, c1: int, r2: int, c2: int) -> int:
        raise TODO("dash.region_sum")
