"""二维页表。

当块数很多时，块管理器用两级页表把逻辑地址映射到物理块：每一行是一页，页内地址升序，
且每一页的首地址都大于上一页的末地址。本文件实现在这样的页表里查找某个地址是否存在。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.page_lookup")
def page_exists(table: list[list[int]], addr: int) -> bool:
    """在二维页表中查找地址 ``addr`` 是否存在。

    规格：
      - ``table`` 是 m 行 n 列的矩阵（``m, n >= 1``，``m * n <= 10^6``）；每行非递减，且每行的
        第一个元素大于上一行的最后一个元素（逐行展开后整体有序）。
      - 存在返回 ``True``，否则返回 ``False``。值与 ``addr`` 都是任意整数。
      - 时间复杂度须为 O(log(m * n))。

    示例：
      table=[[1,3,5,7],[10,11,16,20],[23,30,34,60]], addr=3   → True
      table=[[1,3,5,7],[10,11,16,20],[23,30,34,60]], addr=13  → False
      table=[[0,1,2,3],[24,25,26,27]], addr=26                 → True
    """
    raise TODO("kv.page_lookup")
