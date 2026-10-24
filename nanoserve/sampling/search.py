"""按累积分布采样时的定位。

采样器先把候选 token 的概率累加成一条严格递增的 CDF，再在 [0, 总和) 里取一个随机数 r，
r 落在哪一段就选哪个 token。本文件实现"在 CDF 中定位 r"这一步，供 ``sampler.sample`` 调用。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sample.cdf_index")
def cdf_index(cdf: list[float], r: float) -> int:
    """按累积分布采样：返回 r 在严格递增的 cdf 中的位置或插入点。

    规格：
      - cdf：严格递增（元素互不相同）的数列，元素可以是 float 或 int，长度 >= 1。
      - r：float 或 int。
      - 若 r 等于 cdf 中某个元素，返回该元素的下标；否则返回把 r 插入后仍保持有序的位置，
        即满足 cdf[i] >= r 的最小下标 i；若 r 大于所有元素，返回 len(cdf)。
      - 下标从 0 开始。
      - 复杂度要求 O(log n)；不得调用 bisect 模块。

    示例：
      >>> cdf_index([1, 3, 5, 6], 5)
      2
      >>> cdf_index([1, 3, 5, 6], 2)
      1
      >>> cdf_index([1, 3, 5, 6], 7)
      4
      >>> cdf_index([0.1, 0.4, 1.0], 0.25)
      1
    """
    raise TODO("sample.cdf_index")
