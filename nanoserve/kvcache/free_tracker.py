"""空闲块号的区间视图。

块被逐个释放回池子时，分配器希望看到的不是一长串零散块号，而是若干段连续的空闲区间
（便于一次分配一整段连续块）。本文件在线维护所有已释放块号组成的不相交区间。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.free_tracker")
class FreeRangeTracker:
    """在线维护空闲块号的不相交闭区间。

    规格：
      - ``FreeRangeTracker()``：初始没有任何空闲块。
      - ``add(block)``：记录块号 block 已空闲（0 <= block <= 10^4）。同一块号可能被 add 多次，
        重复 add 不产生任何变化。返回 None。
      - ``ranges()``：把迄今 add 过的全部块号（去重后）合并成极大的连续段，返回
        ``[[start, end], ...]``，每段是闭区间 [start, end]（两端都包含），
        各段按 start 升序排列、互不相交且互不相邻（相邻的块号必须合并到同一段）。
        还没有任何块时返回 []。返回新的列表（调用方可能修改它）。
      - 复杂度：设当前段数为 k，add 为 O(log k)（或 O(k)），ranges 为 O(k)。

    示例：
      >>> t = FreeRangeTracker()
      >>> t.add(1); t.ranges()
      [[1, 1]]
      >>> t.add(3); t.ranges()
      [[1, 1], [3, 3]]
      >>> t.add(7); t.ranges()
      [[1, 1], [3, 3], [7, 7]]
      >>> t.add(2); t.ranges()
      [[1, 3], [7, 7]]
      >>> t.add(6); t.ranges()
      [[1, 3], [6, 7]]
    """

    def __init__(self) -> None:
        raise TODO("kv.free_tracker")

    def add(self, block: int) -> None:
        raise TODO("kv.free_tracker")

    def ranges(self) -> list[list[int]]:
        raise TODO("kv.free_tracker")
