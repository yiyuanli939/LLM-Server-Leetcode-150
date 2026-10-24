"""输出的重复/退化检测与片段定位。

小模型很容易陷入"复读"。本文件提供几种基于滑动窗口与哈希表的指标：不含重复字符的最长片段
（退化程度统计）、覆盖一组必需字符的最短片段（引用定位），以及 no-repeat 窗口检查
（同一 token 是否在近距离内重复出现，采样时用来禁止复读）。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("stream.unique_run")
def longest_unique_run(s: str) -> int:
    """退化检测指标：返回 s 中不含重复字符的最长连续片段的长度。

    规格：
      - s 可含任意字符（字母、数字、空格、标点、Unicode），可以为空。
      - 片段必须是连续子串；片段内任意两个字符都不相同（空格也算字符）。
      - 返回最长这种片段的长度；s 为空时返回 0。
      - 复杂度要求 O(len(s))。

    示例：
      >>> longest_unique_run("abcabcbb")
      3
      >>> longest_unique_run("bbbbb")
      1
      >>> longest_unique_run("pwwkew")
      3
    """
    raise TODO("stream.unique_run")


@exercise("stream.repeat_window")
def repeats_within(tokens: list[int], k: int) -> bool:
    """no-repeat 窗口：判断是否有同一个 token 在距离 <= k 的范围内重复出现。

    规格：
      - tokens：token id 列表（整数，可为负），可以为空；k >= 0。
      - 当且仅当存在两个不同下标 i != j，满足 tokens[i] == tokens[j] 且 |i - j| <= k 时返回 True。
      - k == 0 时必然返回 False。
      - 复杂度要求 O(len(tokens))（额外空间 O(min(n, k)) 更佳）。

    示例：
      >>> repeats_within([1, 2, 3, 1], 3)
      True
      >>> repeats_within([1, 0, 1, 1], 1)
      True
      >>> repeats_within([1, 2, 3, 1, 2, 3], 2)
      False
    """
    raise TODO("stream.repeat_window")
