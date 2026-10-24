"""随机淘汰策略的候选集合。

在某些负载下，随机淘汰比 LRU 更不容易被访问模式"打败"。块管理器维护一个候选块号集合，
支持快速加入、移除，以及等概率随机挑一个作为淘汰对象。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.random_evict")
class RandomEvictSet:
    """随机淘汰候选集合：存放互不相同的块号。

    规格：
      - ``RandomEvictSet()``：创建空集合。
      - ``insert(x)``：若 ``x`` 不在集合中则加入并返回 ``True``；已存在则不做改动并返回 ``False``。
      - ``remove(x)``：若 ``x`` 在集合中则移除并返回 ``True``；否则返回 ``False``。
      - ``pick()``：从当前集合中等概率随机返回一个元素（不移除）。调用时保证集合非空。
        请使用标准库 ``random`` 模块的全局随机数生成器（如 ``random.randrange`` / ``random.choice``）。
      - 三个操作均须为平均 O(1)。块号在 [-2^31, 2^31 - 1] 内。

    示例：
      >>> s = RandomEvictSet(); s.insert(1), s.remove(2), s.insert(2)
      (True, False, True)
      >>> s.pick() in (1, 2)
      True
      >>> s.remove(1), s.insert(2), s.pick()
      (True, False, 2)
    """

    def __init__(self) -> None:
        raise TODO("kv.random_evict")

    def insert(self, x: int) -> bool:
        raise TODO("kv.random_evict")

    def remove(self, x: int) -> bool:
        raise TODO("kv.random_evict")

    def pick(self) -> int:
        raise TODO("kv.random_evict")
