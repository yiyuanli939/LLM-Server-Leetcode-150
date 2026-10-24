"""离线评测指标。

评测流水线拿模型输出和参考答案做比对，并跟踪训练过程中各个 checkpoint 的评分走势。
这里实现两个基础指标：字符级编辑距离，以及评分序列中"持续进步"的最长长度。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("eval.edit_distance")
def edit_distance(a: str, b: str) -> int:
    """计算模型输出 a 与参考答案 b 之间的编辑距离。

    规格：
      - 允许三种单字符操作，每次代价为 1：插入一个字符、删除一个字符、替换一个字符。
      - 返回把 a 变成 b 所需的最少操作次数。
      - a、b 可为空串，可含任意字符（大小写字母、空格、标点、换行、任意 Unicode 字符）；
        字符按原样逐个比较（区分大小写，不做任何归一化）。复杂度 O(len(a) * len(b))。

    示例：
      >>> edit_distance("horse", "ros")
      3
      >>> edit_distance("intention", "execution")
      5
      >>> edit_distance("The cache.", "the cache!")
      2
    """
    raise TODO("eval.edit_distance")


