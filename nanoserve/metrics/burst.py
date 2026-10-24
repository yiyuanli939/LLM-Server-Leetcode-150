"""队列突发检测。

Metrics 模块以秒为粒度记录等待队列长度的变化量（正数为增长、负数为回落）。
"最大突发"定义为某一段连续时间内队列长度累计增长的最大值，用来评估峰值压力；
对按天循环的周期性流量，这段时间还可以跨过周期末尾接回周期开头。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("metrics.max_burst")
def max_burst(deltas: list[int]) -> int:
    """求最大连续累计增长（最大突发）。

    规格：
      - deltas 非空，元素为整数（可为负）。
      - 返回所有非空连续子段元素和中的最大值。注意子段必须非空：
        若全部为负，返回其中最大的那个元素。
      - 复杂度：O(n)。

    示例：
      >>> max_burst([-2, 1, -3, 4, -1, 2, 1, -5, 4])
      6
      >>> max_burst([5, 4, -1, 7, 8])
      23
    """
    raise TODO("metrics.max_burst")


@exercise("metrics.max_burst_circular")
def max_burst_circular(deltas: list[int]) -> int:
    """同 max_burst，但 deltas 是循环的周期序列，连续子段可以跨过末尾回到开头。

    规格：
      - deltas 非空，元素为整数（可为负），视为首尾相接的环。
      - 连续子段可以从某处开始，一直延伸过末尾再从下标 0 接着取，但每个元素最多取一次
        （子段长度 1 … len(deltas)）。
      - 返回所有这样的非空子段元素和中的最大值；全部为负时返回最大的那个元素。
      - 复杂度：O(n)。

    示例：
      >>> max_burst_circular([1, -2, 3, -2])
      3
      >>> max_burst_circular([5, -3, 5])
      10
      >>> max_burst_circular([-3, -2, -3])
      -2
    """
    raise TODO("metrics.max_burst_circular")
