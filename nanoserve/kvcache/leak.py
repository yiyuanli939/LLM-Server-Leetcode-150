"""块泄漏与副本缺失检测。

分配/释放日志与多副本清单都要求每个块号出现固定次数；只有一个块号"落单"时，
它就是泄漏或缺副本的块。本文件用 O(1) 额外空间的位运算把它找出来。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.leaked")
def find_leaked(events: list[int]) -> int:
    """分配与释放日志中，每个正常块号恰好出现两次（一次分配、一次释放）；
    只有一个泄漏的块号只出现一次。找出它。

    规格：
      - 保证恰有一个块号出现一次，其余每个块号恰好出现两次。``1 <= len(events) <= 3 * 10^4``；
        块号在 [-3 * 10^4, 3 * 10^4] 内（可能为负）。
      - 时间 O(n)，额外空间 O(1)（不要用 dict / set / Counter）。

    示例：
      [2,2,1]        → 1
      [4,1,2,1,2]    → 4
      [1]            → 1
    """
    raise TODO("kv.leaked")


