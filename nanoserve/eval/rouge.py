"""ROUGE-L 评测指标的核心计算。

ROUGE-L 用模型输出与参考答案的最长公共子序列（LCS）衡量两者的重合程度，
据此再算 precision / recall / F 值。这里只实现最核心的 LCS 长度。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("eval.rouge_l")
def lcs_length(a: str, b: str) -> int:
    """返回字符串 a 与 b 的最长公共子序列的长度。

    规格：
      - 子序列：从原串删去若干（可以为 0 个）字符、保持其余字符相对顺序得到的串，不要求连续。
      - 公共子序列须同时是 a 和 b 的子序列；不存在（或任一为空串）时返回 0。
      - 字符按原样逐个比较（区分大小写）；复杂度 O(len(a) * len(b))。

    示例：
      >>> lcs_length("abcde", "ace")
      3
      >>> lcs_length("abc", "def")
      0
    """
    raise TODO("eval.rouge_l")
