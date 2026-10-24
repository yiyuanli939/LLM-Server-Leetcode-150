"""环形缓冲区（ring buffer）上的操作。

KV 槽位的回收顺序用环形缓冲区维护：写指针不断绕圈，导致底层数组看起来是一段被"旋转过"的
有序序列。本文件实现环形缓冲的原地旋转、二分查找以及寻找逻辑起点。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.rotate_buffer")
def rotate_right(buf: list[int], k: int) -> None:
    """把环形缓冲区原地向右循环移动 ``k`` 位（每移动一位，最后一个元素移到最前面）。

    规格：
      - 原地修改 ``buf``，返回 ``None``；不要换成新的列表对象，也不要改变长度。
      - 额外空间 O(1)。
      - ``1 <= len(buf) <= 10^5``；``0 <= k <= 10^5``，``k`` 可能大于 ``len(buf)``。

    示例：
      buf=[1,2,3,4,5,6,7], k=3   → buf 变为 [5,6,7,1,2,3,4]
      buf=[-1,-100,3,99], k=2    → buf 变为 [3,99,-1,-100]
    """
    raise TODO("kv.rotate_buffer")


@exercise("kv.ring_search")
def ring_search(buf: list[int], target: int) -> int:
    """在环形缓冲中查找块号 ``target``。``buf`` 是一个严格升序数组在某个未知位置被旋转后的结果
    （例如 [0,1,2,4,5,6,7] 旋转成 [4,5,6,7,0,1,2]；旋转 0 位即原数组也可能出现）。

    规格：
      - 元素互不相同。找到则返回其下标（从 0 开始），否则返回 -1。
      - 时间复杂度须为 O(log n)。``1 <= len(buf) <= 5000``；值与 ``target`` 都是任意整数。

    示例：
      buf=[4,5,6,7,0,1,2], target=0  → 4
      buf=[100005,100009,3,42], target=3  → 2
      buf=[4,5,6,7,0,1,2], target=3  → -1
      buf=[1], target=0              → -1
    """
    raise TODO("kv.ring_search")


@exercise("kv.ring_head")
def ring_min(buf: list[int]) -> int:
    """找到环形缓冲的逻辑起点：``buf`` 是严格升序数组旋转若干位（可能为 0 位或 n 位）后的结果，
    返回其中的最小值（注意：返回值本身，不是下标）。

    规格：
      - 元素互不相同；``1 <= len(buf) <= 5000``；值是任意整数。
      - 时间复杂度须为 O(log n)。

    示例：
      [3,4,5,1,2]        → 1
      [70001,70002,69998,69999] → 69998
      [4,5,6,7,0,1,2]    → 0
      [11,13,15,17]      → 11
    """
    raise TODO("kv.ring_head")
