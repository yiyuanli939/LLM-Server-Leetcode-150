"""Beam search 的两步扩展。

两步 beam 扩展时，第一步和第二步各自有一个按代价升序排好的候选列表；
组合代价是两步代价之和，我们只想要代价最小的 k 个组合，而不必枚举全部 m*n 对。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("decode.beam_pairs")
def k_best_pairs(a: list[int], b: list[int], k: int) -> list[list[int]]:
    """从两个升序代价列表中选出代价和最小的 k 对组合。

    规格：
      - a、b 均按非递减顺序排列，长度 >= 1，元素可为负数、可重复。
      - 一对组合是 ``[a[i], b[j]]``（取元素值，不是下标）；每个下标对 (i, j) 至多使用一次。
      - 返回 k 对组合，使它们的和是所有 len(a)*len(b) 对中最小的 k 个；保证
        ``1 <= k <= len(a) * len(b)``。
      - 和相同时可任选，返回列表的顺序任意。复杂度应为 O(k log k) 级别（不可枚举全部组合）。

    示例：
      >>> k_best_pairs([1, 7, 11], [2, 4, 6], 3)
      [[1, 2], [1, 4], [1, 6]]
      >>> k_best_pairs([1, 1, 2], [1, 2, 3], 2)
      [[1, 1], [1, 1]]
    """
    raise TODO("decode.beam_pairs")
