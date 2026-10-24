"""维护窗口预约。

运维可以给服务器预约维护窗口（升级权重、重建 KV 池等），窗口期间不接纳新请求。
两个维护窗口不能重叠：新的预约只有在与所有已接受的预约都不冲突时才被接受。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.maintenance")
class MaintenanceCalendar:
    """维护窗口预约表：半开区间 [start, end) 不得与已有预约重叠。

    规格：
      - ``MaintenanceCalendar()``：初始没有任何预约。
      - ``book(start, end)``：尝试预约时间区间 [start, end)（左闭右开，0 <= start < end）。
        若它与任一**已接受**的预约存在公共时刻，则拒绝并返回 False（不做任何改动）；
        否则记录这次预约并返回 True。
      - 因为是左闭右开，[10, 20) 与 [20, 30) 不重叠；被拒绝的预约不会被记录，也不影响之后的判断。

    示例：
      >>> c = MaintenanceCalendar()
      >>> c.book(10, 20), c.book(15, 25), c.book(20, 30)
      (True, False, True)
    """

    def __init__(self) -> None:
        raise TODO("sched.maintenance")

    def book(self, start: int, end: int) -> bool:
        raise TODO("sched.maintenance")
