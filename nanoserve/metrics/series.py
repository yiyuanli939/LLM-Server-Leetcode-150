"""可被迟到数据修正的指标序列。

上报的指标点可能乱序到达，也可能在之后被更正（同一时间戳重新上报一个新值）。
面板需要随时给出最新时间戳上的值，以及当前所有点中的最大值和最小值。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("metrics.corrected")
class CorrectableSeries:
    """支持修正的指标时间序列。

    规格：
      - ``CorrectableSeries()`` 创建空序列。
      - ``update(ts, value)``：记录时间戳 ``ts`` 上的值为 ``value``，无返回值。时间戳可以乱序到达；
        若 ``ts`` 已经有值，则这次是修正：用新值**覆盖**旧值（旧值作废，不再参与最大 / 最小值）。
      - ``current()``：返回目前出现过的最大时间戳上的当前值。
      - ``maximum()`` / ``minimum()``：返回所有时间戳上的当前值中的最大值 / 最小值。
      - 0 <= ts <= 10^9，0 <= value <= 10^9（时间戳从 0 开始，值可以为 0）。保证三个查询方法只会在至少一次 ``update`` 之后调用。
      - 不同实例互不影响。
      - 复杂度：每次操作 O(log n)（允许均摊），n 为操作次数。

    示例：
      >>> s = CorrectableSeries()
      >>> s.update(1, 10); s.update(2, 5)
      >>> s.current(), s.maximum()
      (5, 10)
      >>> s.update(1, 3)  # 修正 ts=1 上的值
      >>> s.maximum()
      5
      >>> s.update(4, 2)
      >>> s.minimum()
      2
      >>> s.update(0, 0); s.minimum(), s.current()
      (0, 2)
    """

    def __init__(self) -> None:
        raise TODO("metrics.corrected")

    def update(self, ts: int, value: int) -> None:
        raise TODO("metrics.corrected")

    def current(self) -> int:
        raise TODO("metrics.corrected")

    def maximum(self) -> int:
        raise TODO("metrics.corrected")

    def minimum(self) -> int:
        raise TODO("metrics.corrected")
