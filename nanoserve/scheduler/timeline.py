"""GPU 忙碌时间线。

调度器记录每块 GPU 在哪些时间段处于忙碌状态，用来计算利用率、寻找空闲窗口。
时间线以闭区间 [start, end] 的列表表示；本文件负责把零散的忙碌区间整理成
互不重叠的有序时间线，以及向已整理好的时间线中插入新区间。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.merge_busy")
def merge_busy(intervals: list[list[int]]) -> list[list[int]]:
    """合并 GPU 忙碌区间，得到互不重叠的时间线（用于计算利用率）。

    规格：
      - intervals 非空，每个元素为 [start, end]，0 <= start <= end；输入顺序任意。
      - 有公共点的区间要合并（包括端点相接，例如 [1, 4] 与 [4, 5] 合并为 [1, 5]）。
      - 返回合并后的区间列表，按 start 升序排列，区间两两不相交。

    示例：
      >>> merge_busy([[1, 3], [2, 6], [8, 10], [15, 18]])
      [[1, 6], [8, 10], [15, 18]]
      >>> merge_busy([[1, 4], [4, 5]])
      [[1, 5]]
    """
    raise TODO("sched.merge_busy")


@exercise("sched.insert_busy")
def insert_busy(intervals: list[list[int]], new: list[int]) -> list[list[int]]:
    """向已排序且不重叠的忙碌时间线中插入一个新的忙碌区间。

    规格：
      - intervals 按 start 升序排列且两两不相交（可以为空），每个元素为 [start, end]，start <= end。
      - new = [start, end]，start <= end。
      - 插入后若与已有区间有公共点（包括端点相接）则合并。
      - 返回新的区间列表，仍按 start 升序且两两不相交。
      - 复杂度：O(n)。

    示例：
      >>> insert_busy([[1, 3], [6, 9]], [2, 5])
      [[1, 5], [6, 9]]
      >>> insert_busy([[1, 2], [3, 5], [6, 7], [8, 10], [12, 16]], [4, 8])
      [[1, 2], [3, 10], [12, 16]]
    """
    raise TODO("sched.insert_busy")
