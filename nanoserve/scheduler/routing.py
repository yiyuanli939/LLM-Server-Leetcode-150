"""请求路由：把新请求分发给多个 worker。

不同 worker 的算力不同（例如显卡型号或 TP 大小不同），调度器按权重随机路由，
使每个 worker 收到的请求比例与它的权重成正比。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.weighted_route")
class WeightedRouter:
    """按权重把请求路由到 worker：返回下标 i 的概率为 w[i] / sum(w)。

    规格：
      - 构造：weights 为非空正整数列表，weights[i] 是第 i 个 worker 的权重（1 <= weights[i]）。
      - pick()：随机返回一个下标 i（0 <= i < len(weights)），各次调用相互独立，
        返回 i 的概率恰为 weights[i] / sum(weights)。
      - 随机源使用标准库 random 模块的全局随机数（如 random.random / random.randint），
        这样调用方可以用 random.seed 复现结果。
      - 复杂度：构造 O(n)，每次 pick() 为 O(log n)。

    示例：
      >>> r = WeightedRouter([1, 3])
      >>> r.pick() in (0, 1)   # 约 25% 的概率返回 0，约 75% 的概率返回 1
      True
    """

    def __init__(self, weights: list[int]) -> None:
        raise TODO("sched.weighted_route")

    def pick(self) -> int:
        raise TODO("sched.weighted_route")
