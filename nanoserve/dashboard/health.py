"""worker × model 健康矩阵。

面板用一张矩阵记录每个 worker 上每个模型副本的健康状况。某个格子出故障时，整行（该 worker）
和整列（该模型）都要被屏蔽显示；此外面板还要找出"全部健康"的最大正方形区域，
作为可整体调度的资源块。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("dash.mask_failed")
def mask_failures(m: list[list[int]]) -> None:
    """故障屏蔽：凡是出现 0 的行与列，整行整列全部置 0。

    规格：
      - m 为 rows x cols 的整数矩阵，1 <= rows, cols；元素可为任意整数（0 表示故障）。
      - 只依据调用前原矩阵中 0 的位置：若原来 m[i][j] == 0，则第 i 行与第 j 列全部置 0；
        其余元素保持不变（不会因为新置的 0 而连锁扩散）。
      - 原地修改 m，返回 None。
      - 进阶：只用 O(1) 额外空间。

    示例：
      >>> m = [[1, 1, 1], [1, 0, 1], [1, 1, 1]]
      >>> mask_failures(m); m
      [[1, 0, 1], [0, 0, 0], [1, 0, 1]]
      >>> m = [[0, 1, 2, 0], [3, 4, 5, 2], [1, 3, 1, 5]]
      >>> mask_failures(m); m
      [[0, 0, 0, 0], [0, 4, 5, 0], [0, 3, 1, 0]]
    """
    raise TODO("dash.mask_failed")


