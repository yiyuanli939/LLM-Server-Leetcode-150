"""Benchmark 参数扫描。

压测前需要把一份紧凑的扫描描述展开成具体的配置列表：配置码逐位展开、
从若干特性开关中挑选组合、用若干请求大小凑出目标 batch。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("bench.choose")
def choose(n: int, k: int) -> list[list[int]]:
    """从编号 1..n 的特性开关中选出 k 个，列出所有组合。

    规格：
      - 每个组合是 k 个互不相同的整数（取自 1..n），不计顺序（[1, 2] 与 [2, 1] 视为同一组合，
        只能出现一次）。
      - 返回全部组合，组合之间的顺序和组合内部的顺序都任意。
      - ``1 <= k <= n <= 20``。

    示例：
      >>> sorted(sorted(c) for c in choose(4, 2))
      [[1, 2], [1, 3], [1, 4], [2, 3], [2, 4], [3, 4]]
      >>> choose(1, 1)
      [[1]]
    """
    raise TODO("bench.choose")


