"""first-fit 显存分配器。

把一段显存看作 n 个连续的单元，按请求分配一段连续空闲单元（取最左侧的可行位置），
并在请求结束时按 owner 一次性释放它占用的全部单元。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.mem_alloc")
class MemoryAllocator:
    """n 个单元（下标 0..n-1）的 first-fit 分配器，按 owner 批量释放。

    规格：
      - ``MemoryAllocator(n)``：初始时全部 n 个单元空闲（``n >= 1``）。
      - ``allocate(size, owner)``：寻找**最左侧**的、由 ``size`` 个连续空闲单元组成的段，
        把它们标记为属于 ``owner`` 并返回该段起始下标；找不到返回 -1（不做任何改动）。
      - ``free(owner)``：释放 ``owner`` 占用的**所有**单元（可能来自多次 allocate、彼此不连续），
        返回释放的单元总数；没有则返回 0。
      - 同一 owner 可以多次 allocate；``size >= 1``，``owner >= 1``。

    示例：
      >>> m = MemoryAllocator(10)
      >>> m.allocate(1, 1), m.allocate(1, 2), m.allocate(1, 3)
      (0, 1, 2)
      >>> m.free(2), m.allocate(3, 4), m.allocate(1, 1), m.allocate(1, 1)
      (1, 3, 1, 6)
      >>> m.free(1), m.allocate(10, 2), m.free(7)
      (3, -1, 0)
    """

    def __init__(self, n: int) -> None:
        raise TODO("kv.mem_alloc")

    def allocate(self, size: int, owner: int) -> int:
        raise TODO("kv.mem_alloc")

    def free(self, owner: int) -> int:
        raise TODO("kv.mem_alloc")
