"""滑动窗口类的服务指标。

Metrics 模块需要实时给出"最近一段时间"的统计量：最近 3 秒的请求数（近似 QPS）、
最近 k 个请求的最大延迟与中位延迟（p50）。这些统计都要在流式到达的数据上增量维护。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("metrics.qps")
class QpsCounter:
    """统计最近 3000ms 内的请求数。

    规格：
      - 构造时计数为空。
      - hit(t)：记录一个在时刻 t（毫秒）到达的请求，并返回时间区间 [t - 3000, t]（两端都包含）
        内的请求数（包括本次请求）。
      - 保证每次调用的 t 严格大于上一次调用的 t；1 <= t。
      - 复杂度：均摊 O(1)。

    示例：
      >>> q = QpsCounter()
      >>> [q.hit(t) for t in [1, 100, 3001, 3002]]
      [1, 2, 3, 3]
    """

    def __init__(self) -> None:
        raise TODO("metrics.qps")

    def hit(self, t: int) -> int:
        raise TODO("metrics.qps")


@exercise("metrics.window_max")
def window_max(latencies: list[int], k: int) -> list[int]:
    """滚动窗口最大延迟：返回每个长度为 k 的连续窗口内的最大值。

    规格：
      - latencies 为整数列表（可为负），1 <= k <= len(latencies)。
      - 窗口从最左端开始，每次右移一位，共 len(latencies) - k + 1 个窗口；
        返回按窗口从左到右排列的最大值列表。
      - 复杂度：O(n)。

    示例：
      >>> window_max([1, 3, -1, -3, 5, 3, 6, 7], 3)
      [3, 3, 5, 5, 6, 7]
      >>> window_max([1], 1)
      [1]
    """
    raise TODO("metrics.window_max")


@exercise("metrics.window_median")
def window_median(latencies: list[int], k: int) -> list[float]:
    """滚动窗口 p50 延迟：返回每个长度为 k 的连续窗口内的中位数。

    规格：
      - latencies 为整数列表（可为负，绝对值可达 2^31），1 <= k <= len(latencies)。
      - 窗口从最左端开始，每次右移一位，共 len(latencies) - k + 1 个窗口；
        返回按窗口从左到右排列的中位数列表，元素为 float。
      - 中位数：窗口排序后，k 为奇数时取正中间的元素；k 为偶数时取中间两个元素的平均值。
      - 复杂度：O(n log k)。

    示例：
      >>> window_median([1, 3, -1, -3, 5, 3, 6, 7], 3)
      [1.0, -1.0, -1.0, 3.0, 5.0, 6.0]
      >>> window_median([1, 2, 3, 4], 2)
      [1.5, 2.5, 3.5]
    """
    raise TODO("metrics.window_median")
