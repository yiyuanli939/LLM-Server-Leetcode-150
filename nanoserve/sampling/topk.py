"""top-k 采样的阈值计算。

top-k 采样只保留 logit 最大的 k 个候选 token，其余置为 -inf。为此采样器需要知道
"第 k 大的 logit" 是多少，以它为阈值做截断。本文件实现这个阈值的计算。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sample.kth_largest")
def kth_largest(logits: list[float], k: int) -> float:
    """top-k 采样的阈值：返回 logits 中第 k 大的值。

    规格：
      - logits：非空数列，元素为 float 或 int（可为负），允许重复值。
      - 1 <= k <= len(logits)。
      - "第 k 大"按排序后的位置计，重复值各占一个名次：即把 logits 降序排序后下标 k-1
        处的元素（不是第 k 个不同的值）。返回该元素本身（类型随输入）。
      - 不得修改调用方传入的列表。
      - 复杂度要求优于完整排序：平均 O(n) 或 O(n log k)。

    示例：
      >>> kth_largest([3, 2, 1, 5, 6, 4], 2)
      5
      >>> kth_largest([3, 2, 3, 1, 2, 4, 5, 5, 6], 4)
      4
      >>> kth_largest([0.5, -1.25, 2.0], 3)
      -1.25
    """
    raise TODO("sample.kth_largest")
