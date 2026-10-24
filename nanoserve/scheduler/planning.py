"""离线批任务的容量规划。

离线批处理（评测集回放、批量摘要等）的任务时间表事先已知。上线前需要回答两个规划问题：
按时间表跑完所有请求最少需要多少个 worker；以及单个 worker 串行处理时，
最多能让多少个请求在各自的截止时刻（SLO）之前完成。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.min_workers")
def min_workers(intervals: list[list[int]]) -> int:
    """容量规划：每个请求占用一个闭区间 [start, end]，同一 worker 上的请求不能重叠，最少需要几个 worker。

    规格：
      - intervals[i] = [start, end]，表示请求 i 占用闭区间 [start, end]（两端都包含）；
        0 <= start <= end <= 10^6；1 <= len(intervals)。
      - 每个请求必须完整分配给恰好一个 worker；分到同一个 worker 的任意两个请求不能相交。
        **两端都包含**，所以 [1, 5] 与 [5, 8] 在时刻 5 相交，不能放在同一个 worker 上。
      - 返回所需 worker 的最少个数。
      - 复杂度：O(n log n)。

    示例：
      >>> min_workers([[5, 10], [6, 8], [1, 5], [2, 3], [1, 10]])
      3
      >>> min_workers([[1, 3], [5, 6], [8, 10], [11, 13]])
      1
      >>> min_workers([[0, 0], [0, 4], [5, 9]])                   # 时刻可以从 0 开始
      2
    """
    raise TODO("sched.min_workers")


@exercise("sched.slo_bound")
def max_on_time(jobs: list[list[int]]) -> int:
    """SLO 上界：单个 worker 串行处理，最多能让多少个请求在截止时刻前完成。

    规格：
      - jobs[i] = [duration, deadline]：请求 i 需要连续处理 duration 个时间单位，
        并且必须在时刻 deadline 或之前完成；1 <= duration, deadline <= 10^4；1 <= len(jobs)。
      - worker 从时刻 0 开始工作，同一时刻只能处理一个请求，一个请求开始后必须一直处理到完成，
        之后可以立即开始下一个。请求的处理顺序任意选择，也可以放弃（不处理）任何请求。
      - 被处理的请求若从时刻 t 开始，则完成时刻为 t + duration，要求 t + duration <= deadline。
      - 返回最多能按时完成的请求个数（没有任何请求能按时完成时返回 0）。
      - 复杂度：O(n log n)。

    示例：
      >>> max_on_time([[100, 200], [200, 1300], [1000, 1250], [2000, 3200]])
      3
      >>> max_on_time([[1, 2]])
      1
      >>> max_on_time([[3, 2], [4, 3]])
      0
    """
    raise TODO("sched.slo_bound")
