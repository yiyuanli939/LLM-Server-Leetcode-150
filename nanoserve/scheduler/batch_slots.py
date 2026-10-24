"""运行中 batch 的槽位分配。

连续 batching 的服务器同时最多运行 n 个请求，每个运行中的请求占用一个编号为 1..n 的槽位
（槽位号决定它在 batch 张量里的行）。新请求被接纳时拿走编号最小的空闲槽，
请求结束时归还槽位，让 batch 尽量紧凑地排在前面几行。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.slots")
class SlotAllocator:
    """batch 槽位分配器：总是分配编号最小的空闲槽（槽位编号 1..n）。

    规格：
      - ``SlotAllocator(n)``：共有 n 个槽位，编号 1..n（从 1 开始），初始全部空闲；``n >= 1``。
      - ``reserve()``：占用当前编号最小的空闲槽位并返回其编号。
        保证调用时至少有一个空闲槽位。
      - ``unreserve(slot)``：释放槽位 slot，使它重新空闲；保证 slot 当前处于被占用状态。返回 None。
      - 复杂度：每次操作 O(log n)。

    示例：
      >>> s = SlotAllocator(5)
      >>> s.reserve(), s.reserve()
      (1, 2)
      >>> s.unreserve(2)
      >>> s.reserve(), s.reserve(), s.reserve(), s.reserve()
      (2, 3, 4, 5)
      >>> s.unreserve(5)
    """

    def __init__(self, n: int) -> None:
        raise TODO("sched.slots")

    def reserve(self) -> int:
        raise TODO("sched.slots")

    def unreserve(self, slot: int) -> None:
        raise TODO("sched.slots")
