"""批处理发射决策。

连续批处理（continuous batching）中，调度器要决定何时"发射"一个 batch：
既要让每个请求都在其可服务时间窗口内被服务到，又希望发射次数尽量少；
另一方面，一个 batch 需要凑够足够的 token 才划算。本文件处理这两类计算。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.min_launches")
def min_launches(windows: list[list[int]]) -> int:
    """求服务所有请求所需的最少 batch 发射次数。

    每个请求有一个可服务时间窗口 [earliest, latest]（闭区间）。在时刻 t 发射一次 batch，
    会同时服务所有满足 earliest <= t <= latest 的请求。t 可以取任意整数时刻。

    规格：
      - windows 非空，每个元素为 [earliest, latest]，earliest <= latest，
        取值范围 -2^31 <= earliest <= latest <= 2^31 - 1；输入顺序任意。
      - 返回使每个请求至少被一次发射服务到所需的最少发射次数。

    示例：
      >>> min_launches([[10, 16], [2, 8], [1, 6], [7, 12]])
      2
      >>> min_launches([[1, 2], [2, 3], [3, 4], [4, 5]])
      2
    """
    raise TODO("sched.min_launches")


