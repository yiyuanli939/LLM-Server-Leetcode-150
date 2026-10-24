"""准入检查：一批已知时间窗口的请求能否同时放进显存。

每个请求在一段时间内占用固定数量的 KV 块。调度器在接纳一整批请求前，
需要确认在整条时间线上任意时刻的总占用都不超过显存容量。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.capacity_ok")
def fits_capacity(requests: list[list[int]], capacity: int) -> bool:
    """判断一批请求在任意时刻的总显存占用是否都不超过 capacity。

    规格：
      - requests[i] = [blocks, start, end]：该请求在时间区间 [start, end) 内占用 blocks 个块，
        即在时刻 start 开始占用、在时刻 end 已经释放（左闭右开）。
        因此一个在 t 结束的请求与一个在 t 开始的请求不会同时占用。
      - 1 <= blocks；0 <= start < end；1 <= capacity。时刻为非负整数，**没有上限**（服务器跑得越久时刻越大，
        可达 10^9），所以不要按时刻开数组；复杂度 O(n log n)，n 为请求数。
      - requests 可以为空（此时返回 True）。
      - 若任意时刻的总占用都 <= capacity 返回 True，否则返回 False。

    示例：
      >>> fits_capacity([[2, 1, 5], [3, 3, 7]], 4)
      False
      >>> fits_capacity([[2, 1, 5], [3, 3, 7]], 5)
      True
      >>> fits_capacity([[2, 1, 5], [3, 5, 7]], 3)
      True
      >>> fits_capacity([[2, 10**9, 10**9 + 5], [3, 10**9 + 3, 10**9 + 7]], 4)   # 时刻很大也一样
      False
    """
    raise TODO("sched.capacity_ok")
