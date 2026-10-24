"""配置中的整数算术表达式求值。

配置项允许写简单的算术表达式（例如 "4096 / 16 * 2 + 1"）；加载时求出整数值。
出于安全考虑，不允许调用 eval/exec 等任何动态求值手段。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("config.arith")
def eval_arith(s: str) -> int:
    """对只含非负整数、``+ - * /`` 和空格的表达式求值，返回整数结果。

    规格：
      - 没有括号，没有一元负号；保证表达式合法且非空（可含任意多空格，数字可以有多位）。
      - 遵循通常优先级：``*`` ``/`` 先于 ``+`` ``-``，同级从左到右。
      - 整数除法**向零截断**（例如 -7/2 若出现在中间结果里应为 -3；注意与 Python 的 ``//`` 不同）。
      - 所有中间结果与最终结果都在 32 位有符号整数范围内；不得使用 eval/exec。

    示例：
      >>> eval_arith("3+2*2")
      7
      >>> eval_arith(" 3/2 ")
      1
      >>> eval_arith(" 3+5 / 2 ")
      5
    """
    raise TODO("config.arith")
