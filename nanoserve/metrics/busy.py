"""利用率统计：忙碌时刻计数。

worker 的忙碌时段以闭区间 [left, right]（整数时刻）的形式不断上报，时段之间可能重叠。
利用率面板需要随时查询"至少被一个忙碌时段覆盖的时刻总数"。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("metrics.busy_time")
class BusyTimeCounter:
    """维护所有忙碌时段并集的大小。

    规格：
      - ``BusyTimeCounter()`` 创建时没有任何时段，此时 ``count()`` 为 0。
      - ``add(left, right)``：加入闭区间 [left, right]，即整数时刻 left, left+1, ..., right，无返回值。
        0 <= left <= right <= 10^9（时刻从 0 开始计）；不同区间可能重叠、相邻、互相包含或完全相同。
      - ``count()``：返回至少落在一个已加入区间内的不同整数的个数。
      - 区间长度可达 10^9，**不能**逐个整数地存储。
      - 不同实例互不影响。
      - 复杂度：``count`` O(1)。``add`` 不得逐个检查全部已有时段或每次重建整个并集：应维护一组互不相交、
        有序的时段，用二分查找定位与新区间重叠（或相邻）的那几个并只合并它们
        （在 Python 中对 list 做切片替换带来的内存搬移可以忽略）。

    示例：
      >>> c = BusyTimeCounter()
      >>> c.add(2, 3); c.add(7, 10); c.count()
      6
      >>> c.add(5, 8); c.count()
      8
      >>> c.add(0, 0); c.count()
      9
    """

    def __init__(self) -> None:
        raise TODO("metrics.busy_time")

    def add(self, left: int, right: int) -> None:
        raise TODO("metrics.busy_time")

    def count(self) -> int:
        raise TODO("metrics.busy_time")
