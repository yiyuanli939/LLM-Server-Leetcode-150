"""离线调度模拟器。

在真正上线一种调度策略之前，先用离散事件模拟回放一批任务，看看任务会以什么顺序被处理、
被分配给哪个 worker、负载是否均衡。本文件包含三种策略的模拟：
单 worker 最短作业优先、多 worker 按权重分配、多 worker 延后执行。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.sjf")
def sjf_order(tasks: list[list[int]]) -> list[int]:
    """单 worker 最短作业优先（非抢占）调度模拟：返回任务被处理的顺序。

    规格：
      - tasks[i] = [arrive, duration]：任务 i 在时刻 arrive 到达（之后可被处理），需要处理 duration 时间。
        1 <= len(tasks)；0 <= arrive；1 <= duration（整数）。
      - 只有一个 worker，同一时刻最多处理一个任务，开始处理后必须一直处理到完成（不可抢占）。
      - worker 空闲且当前没有已到达未处理的任务时，保持空闲直到下一个任务到达。
      - worker 空闲且有已到达未处理的任务时，选择 duration 最短的那个；
        duration 相同则选下标最小的那个。
      - 一个任务完成的同一时刻即可开始下一个任务；在时刻 t 到达的任务在时刻 t 就可被选择。
      - 返回任务下标（从 0 开始）按处理先后排列的列表。
      - 复杂度：O(n log n)。

    示例：
      >>> sjf_order([[1, 2], [2, 4], [3, 2], [4, 1]])
      [0, 2, 3, 1]
      >>> sjf_order([[7, 10], [7, 12], [7, 5], [7, 4], [7, 2]])
      [4, 3, 2, 0, 1]
      >>> sjf_order([[0, 3], [0, 1], [0, 2]])                  # 时刻 0 就可以到达
      [1, 2, 0]
    """
    raise TODO("sched.sjf")


@exercise("sched.assign_workers")
def assign_workers(weights: list[int], tasks: list[int]) -> list[int]:
    """多 worker 分配模拟：返回每个任务被分配到的 worker 下标。

    规格：
      - weights[i] 为第 i 个 worker 的权重（越小越优先）；tasks[j] 为任务 j 的处理时长（秒）。
        1 <= len(weights), len(tasks)；1 <= weights[i]；1 <= tasks[j]。
      - 任务 j 在第 j 秒（从 0 开始）到达并进入一个先进先出的等待队列。
      - 只要有空闲 worker 且队列非空，就把队首任务分配给空闲 worker 中权重最小的那个；
        权重相同则选下标最小的。
      - 若当前没有空闲 worker，队列中的任务等待，直到有 worker 空闲后尽快分配。
        若同一时刻有多个 worker 空闲，则按队列顺序依次分配多个任务，每次都按上述优先级挑 worker。
      - worker 在时刻 t 开始处理任务 j，则在时刻 t + tasks[j] 重新空闲（并可在该时刻立即接新任务）。
      - 返回长度为 len(tasks) 的列表 ans，ans[j] 为任务 j 被分配到的 worker 下标（从 0 开始）。
      - 复杂度：O((n + m) log n)，n 为 worker 数，m 为任务数。

    示例：
      >>> assign_workers([3, 3, 2], [1, 2, 3, 2, 1, 2])
      [2, 2, 0, 2, 1, 2]
      >>> assign_workers([5, 1, 4, 3, 2], [2, 1, 2, 4, 5, 2, 1])
      [1, 4, 1, 4, 1, 3, 2]
    """
    raise TODO("sched.assign_workers")


@exercise("sched.busiest_worker")
def busiest_worker(n: int, jobs: list[list[int]]) -> int:
    """n 个 worker 处理一批带时间窗口的任务（任务可被延后，但时长不变），返回承接任务最多的 worker。

    规格：
      - worker 编号 0..n-1，1 <= n。jobs[i] = [start, end] 表示任务原计划占用时间区间 [start, end)
        （左闭右开），0 <= start < end；所有 start 互不相同；1 <= len(jobs)。
      - 每个任务分配给当前空闲的 worker 中编号最小的那个。
      - 若没有空闲 worker，任务被延后，直到有 worker 空闲；延后的任务保持原时长 end - start。
      - 当有 worker 空闲时，原计划 start 更早的任务优先获得它。
      - 一个 worker 在时刻 t 结束任务，则时刻 t 开始的任务可以使用它。
      - 返回承接任务数最多的 worker 编号；若有多个并列，返回编号最小的。
      - 复杂度：O(m log m + m log n)，m 为任务数。

    示例：
      >>> busiest_worker(2, [[0, 10], [1, 5], [2, 7], [3, 4]])
      0
      >>> busiest_worker(3, [[1, 20], [2, 10], [3, 5], [4, 9], [6, 8]])
      1
    """
    raise TODO("sched.busiest_worker")
