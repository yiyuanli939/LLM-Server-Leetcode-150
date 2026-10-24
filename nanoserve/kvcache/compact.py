"""块号数组的原地压缩。

块管理器内部常用定长数组记录槽位与块号；回收、去重、合并都要求原地完成，
避免在热路径上频繁分配新数组。本文件实现这些原地压缩操作。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.compact")
def remove_freed(slots: list[int], freed: int) -> int:
    """原地压缩槽位数组：去掉所有值等于 ``freed`` 标记的槽位。

    规格：
      - 设不等于 ``freed`` 的元素共有 ``k`` 个。函数返回 ``k``，并且原地修改 ``slots``，
        使 ``slots[:k]`` 恰好是这些元素（顺序任意）。
      - ``slots[k:]`` 的内容不作要求；不要改变 ``slots`` 的长度。
      - ``len(slots)`` 0 ~ 10^4；元素与 ``freed`` 都是任意整数。

    示例：
      slots=[3,2,2,3], freed=3            → 返回 2，slots[:2] 为 [2,2]
      slots=[0,1005,0,7], freed=0         → 返回 2，slots[:2] 为 {7,1005} 的某种排列
      slots=[0,1,2,2,3,0,4,2], freed=2    → 返回 5，slots[:5] 为 {0,0,1,3,4} 的某种排列
    """
    raise TODO("kv.compact")


@exercise("kv.dedupe")
def dedupe_sorted(ids: list[int]) -> int:
    """有序块号原地去重：``ids`` 非递减，每个块号只保留一份。

    规格：
      - 设不同块号共有 ``k`` 个。返回 ``k``，并原地修改 ``ids``，使 ``ids[:k]``
        恰好是这些块号，按原来的升序排列。
      - ``ids[k:]`` 的内容不作要求；不要改变 ``ids`` 的长度。
      - 保证 ``len(ids) >= 1``（至多 3 * 10^4）；块号是任意整数。

    示例：
      [1,1,2]                → 返回 2，ids[:2] == [1,2]
      [-7,4096,4096,90000]   → 返回 3，ids[:3] == [-7,4096,90000]
      [0,0,1,1,1,2,2,3,3,4]  → 返回 5，ids[:5] == [0,1,2,3,4]
    """
    raise TODO("kv.dedupe")


@exercise("kv.merge_arrays")
def merge_into(a: list[int], m: int, b: list[int], n: int) -> None:
    """把有序空闲块号数组 ``b`` 原地合并进 ``a``。

    规格：
      - ``a`` 的长度为 ``m + n``：前 ``m`` 个是有效块号（非递减），后 ``n`` 个是占位用的 0，应被忽略。
      - ``b`` 的长度为 ``n``，非递减。
      - 函数返回 ``None``；结束后 ``a`` 必须是全部 ``m + n`` 个块号的非递减排列（重复保留）。
        不要给 ``a`` 换成新列表对象，也不要改变它的长度。
      - ``0 <= m, n <= 10^4``，``m + n >= 1``；块号在 [-10^9, 10^9] 内。

    示例：
      a=[1,2,3,0,0,0], m=3, b=[2,5,6], n=3  → a 变为 [1,2,2,3,5,6]
      a=[1], m=1, b=[], n=0                 → a 仍为 [1]
      a=[0], m=0, b=[1], n=1                → a 变为 [1]
      a=[0,4,9,0,0], m=3, b=[4,5], n=2      → a 变为 [0,4,4,5,9]（a 中真正的 0 不是占位）
    """
    raise TODO("kv.merge_arrays")
