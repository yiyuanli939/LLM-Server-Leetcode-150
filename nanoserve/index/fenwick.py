"""按 deadline 桶统计 token 数的区间计数器。

请求按 deadline 落入编号连续的桶，每个桶记录待生成的 token 数；调度器频繁修改单个桶，
又频繁询问"某个 deadline 区间内一共还有多少 token"，两者都要求对数时间。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("index.range_sum")
class RangeCounter:
    """支持单点赋值与闭区间求和的整数数组（树状数组 / 线段树）。

    规格：
      - ``RangeCounter(nums)``：以 ``nums``（长度 n >= 1，元素可为负）初始化；之后不应依赖调用方继续持有该列表。
      - ``update(i, val)``：把下标 ``i``（0 起）的值**设为** ``val``（赋值，不是加上）。
      - ``sum_range(l, r)``：返回下标 ``l..r``（闭区间，``0 <= l <= r < n``）的元素和。
      - 初始化 O(n) 或 O(n log n)；update 与 sum_range 均为 O(log n)。

    示例：
      >>> rc = RangeCounter([1, 3, 5]); rc.sum_range(0, 2)
      9
      >>> rc.update(1, 2); rc.sum_range(0, 2)
      8
    """

    def __init__(self, nums: list[int]) -> None:
        raise TODO("index.range_sum")

    def update(self, i: int, val: int) -> None:
        raise TODO("index.range_sum")

    def sum_range(self, l: int, r: int) -> int:
        raise TODO("index.range_sum")
