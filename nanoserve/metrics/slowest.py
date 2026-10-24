"""「最慢 k 个请求」面板。

面板持续展示延迟最高的 k 个请求。请求延迟流式到达，需要随时知道当前第 k 慢的延迟——
它就是新请求进入这个面板的门槛。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("metrics.slowest_k")
class KthSlowest:
    """在线跟踪第 k 大的请求延迟。

    规格：
      - ``KthSlowest(k, initial)``：k >= 1；``initial`` 是已有的延迟列表（可以为空，元素个数可以少于 k）。
      - ``add(latency)``：记录一个新延迟，并返回**目前为止全部**延迟（initial 加上此前所有 add 的值，
        含本次）中第 k 大的值。按排序后的位置计数，重复值分别计数（例如 [5, 5, 4] 中第 2 大是 5）。
      - 保证每次 ``add`` 之后延迟总数 >= k。延迟为整数（可能为 0 或负数）。
      - 不同实例互不影响。
      - 复杂度：每次 ``add`` O(log k)，额外空间 O(k)。

    示例：
      >>> s = KthSlowest(3, [4, 5, 8, 2])
      >>> [s.add(x) for x in [3, 5, 10, 9, 4]]
      [4, 5, 5, 8, 8]
    """

    def __init__(self, k: int, initial: list[int]) -> None:
        raise TODO("metrics.slowest_k")

    def add(self, latency: int) -> int:
        raise TODO("metrics.slowest_k")
