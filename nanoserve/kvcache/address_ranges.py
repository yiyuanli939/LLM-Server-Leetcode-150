"""已分配地址区间的跟踪。

KV 池按地址区间批量分配和回收（例如一次把 [1024, 4096) 分给某个大请求）。
块管理器需要随时回答"某段地址是否已经整段被分配"，以便做越界检查和泄漏排查。
区间可以重叠地反复添加、也可以从中间挖掉一段，所以要维护的是这些操作之后的并集。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.address_ranges")
class AddressRanges:
    """已分配地址集合，按半开区间 [left, right) 增、删、整段查询。

    规格：
      - ``AddressRanges()``：初始没有任何地址被标记为已分配。
      - ``add_range(left, right)``：把半开区间 [left, right) 内的**每一个**实数地址都标记为已分配
        （其中部分地址可能早已被标记，不影响）。返回 None。
      - ``query_range(left, right)``：当且仅当 [left, right) 内的每一个地址当前都已分配时返回 True。
      - ``remove_range(left, right)``：把 [left, right) 内当前已分配的地址全部取消标记。返回 None。
      - 都是左闭右开：add_range(10, 20) 之后 20 本身不算已分配；
        add_range(10, 20) 与 add_range(20, 30) 之后 query_range(10, 30) 为 True（两段首尾相接、无空隙）。
      - 0 <= left < right <= 10^9（地址 0 也是合法地址）；操作总数在 10^4 量级。
      - 复杂度：每次操作 O(k)（k 为当前不相交段数）即可，O(log k) 均摊更好。

    示例：
      >>> r = AddressRanges()
      >>> r.add_range(10, 20); r.remove_range(14, 16)
      >>> r.query_range(10, 14), r.query_range(13, 15), r.query_range(16, 17)
      (True, False, True)
      >>> r.add_range(0, 4); r.query_range(0, 1), r.query_range(3, 5)
      (True, False)
    """

    def __init__(self) -> None:
        raise TODO("kv.address_ranges")

    def add_range(self, left: int, right: int) -> None:
        raise TODO("kv.address_ranges")

    def query_range(self, left: int, right: int) -> bool:
        raise TODO("kv.address_ranges")

    def remove_range(self, left: int, right: int) -> None:
        raise TODO("kv.address_ranges")
