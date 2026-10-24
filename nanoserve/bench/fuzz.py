"""调度器与约束解码的穷举测试生成器。

确定性测试需要穷举小规模输入：请求的所有到达顺序，以及所有合法的括号嵌套结构
（用于测试 JSON 约束解码器）。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("bench.orders")
def arrival_orders(ids: list[int]) -> list[list[int]]:
    """枚举一组请求的所有到达顺序。

    规格：
      - ids 中的整数互不相同，``1 <= len(ids) <= 6``。
      - 返回 ids 的全部排列（共 len(ids)! 个），每个排列恰好出现一次。
      - 排列之间的顺序任意。

    示例：
      >>> sorted(arrival_orders([1, 2, 3]))
      [[1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1], [3, 1, 2], [3, 2, 1]]
      >>> arrival_orders([1])
      [[1]]
    """
    raise TODO("bench.orders")


@exercise("bench.json_fuzz")
def balanced_brackets(n: int) -> list[str]:
    """生成所有由 n 对圆括号组成的合法嵌套结构。

    规格：
      - 每个结果是长度为 2n、只含 ``'('`` 和 ``')'`` 的字符串，且括号正确配对。
      - 返回全部这样的字符串，每个恰好出现一次，顺序任意。
      - ``1 <= n <= 8``。

    示例：
      >>> sorted(balanced_brackets(3))
      ['((()))', '(()())', '(())()', '()(())', '()()()']
      >>> balanced_brackets(1)
      ['()']
    """
    raise TODO("bench.json_fuzz")
