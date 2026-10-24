"""延迟分位数统计。

Metrics 模块需要报告 p50（中位数）延迟：一方面要在请求不断完成时在线维护中位数，
另一方面要在汇总阶段把两个 worker 各自上报的、已排序的延迟样本合并起来求中位数，
而且不能真的把两份样本合并一遍。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("metrics.median")
class MedianTracker:
    """在线 p50 延迟：请求一个个完成，随时查询目前所有延迟样本的中位数。

    规格：
      - 构造时样本为空。
      - add(x)：加入一个整数延迟样本 x（可能重复，可能为负数也须正确处理）。
      - median()：返回目前全部样本的中位数（float）。样本数为奇数时是排序后正中间那个值；
        为偶数时是正中间两个值的算术平均（例如 2 和 3 得 2.5）。
      - 保证调用 median() 时至少已有一个样本。
      - 复杂度：add 为 O(log n)，median 为 O(1)。

    示例：
      >>> t = MedianTracker(); t.add(1); t.add(2); t.median()
      1.5
      >>> t.add(3); t.median()
      2.0
    """

    def __init__(self) -> None:
        raise TODO("metrics.median")

    def add(self, x: int) -> None:
        raise TODO("metrics.median")

    def median(self) -> float:
        raise TODO("metrics.median")


@exercise("metrics.merged_median")
def merged_median(a: list[int], b: list[int]) -> float:
    """合并两个 worker 各自有序的延迟样本，求全部样本的中位数。

    规格：
      - a、b 都按非降序排列，长度分别为 m、n（0 <= m, n），且 m + n >= 1（至少一个非空）。
      - 返回把 a 和 b 合在一起后的中位数（float）：总数为奇数时取正中间的值，
        为偶数时取正中间两个值的算术平均。
      - 复杂度要求：O(log(m + n))，不能把两个数组真正合并。

    示例：
      >>> merged_median([1, 3], [2])
      2.0
      >>> merged_median([1, 2], [3, 4])
      2.5
    """
    raise TODO("metrics.merged_median")
