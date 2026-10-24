"""块分配器的统计与查询。

分配器需要回答几类问题：空闲块号里最长的连续段有多长（能否满足一次大块分配）、
如何把空闲块号压缩成可读的区间描述、显存占用剖面里有多少碎片被"困住"，
以及按序列号排序的块表中某个序列占用了哪一段。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.longest_run")
def longest_free_run(ids: list[int]) -> int:
    """无序的空闲块号中，最长的一段"连续块号"（如 4,5,6,7）有多少个块。

    规格：
      - 只看块号的值是否连续，与它们在 ``ids`` 中的位置无关；重复的块号只算一次。
      - ``ids`` 为空时返回 0。``len(ids)`` 0 ~ 10^5，块号在 [-10^9, 10^9] 内。
      - 时间复杂度须为 O(n)（不要排序）。

    示例：
      [100,4,200,1,3,2]          → 4   （1,2,3,4）
      [0,3,7,2,5,8,4,6,0,1]      → 9
      [1,0,1,2]                  → 3
    """
    raise TODO("kv.longest_run")


@exercise("kv.free_ranges")
def free_ranges(ids: list[int]) -> list[str]:
    """把严格升序、互不相同的空闲块号压缩成区间描述列表。

    规格：
      - 把块号划分为若干段极大的连续区间（相邻块号相差 1 的归入同一段），按升序输出：
        区间 [a, b] 且 a != b 时写作 ``"a->b"``，a == b 时写作 ``"a"``（负数照常写负号）。
      - ``ids`` 为空时返回空列表。``len(ids)`` 0 ~ 10^4；块号在 [-2^31, 2^31 - 1] 内。

    示例：
      [0,1,2,4,5,7]      → ["0->2", "4->5", "7"]
      [-1,0,1,9,1000,1001] → ["-1->1", "9", "1000->1001"]
      [0,2,3,4,6,8,9]    → ["0", "2->4", "6", "8->9"]
    """
    raise TODO("kv.free_ranges")


@exercise("kv.seq_range")
def owner_range(owners: list[int], seq_id: int) -> list[int]:
    """块表按所属序列号非递减排序：``owners[i]`` 是第 i 个块所属的序列号。
    返回序列 ``seq_id`` 占用的第一个和最后一个块的下标。

    规格：
      - 返回 ``[first, last]``（下标从 0 开始）；若 ``seq_id`` 不在 ``owners`` 中，返回 ``[-1, -1]``。
      - 时间复杂度须为 O(log n)。``len(owners)`` 0 ~ 10^5；值在 [-10^9, 10^9] 内。

    示例：
      owners=[5,7,7,8,8,10], seq_id=8  → [3, 4]
      owners=[5,7,7,8,8,10], seq_id=6  → [-1, -1]
      owners=[], seq_id=0              → [-1, -1]
    """
    raise TODO("kv.seq_range")
