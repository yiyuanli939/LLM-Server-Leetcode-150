"""位图分配器的位运算工具。

小块池用一个整数位图记录占用情况：第 i 位为 1 表示第 i 个块已被占用。
本文件实现统计占用数、序列化时的位序反转，以及求一段地址的公共对齐前缀。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.popcount")
def popcount(n: int) -> int:
    """位图中已占用的块数：返回正整数 ``n`` 的二进制表示中 1 的个数。

    规格：
      - ``1 <= n <= 2^31 - 1``。
      - 请用位运算实现（不要用 ``bin(n).count("1")`` 或 ``int.bit_count``）。

    示例：
      11 (0b1011)         → 3
      128 (0b10000000)    → 1
      2147483645          → 30
    """
    raise TODO("kv.popcount")


