"""feature flag 条件表达式求值。

路由与灰度配置里可以用布尔条件表达式决定某个 feature flag 是否开启，例如 ``&(t,|(f,t),!(f))``。
加载配置时要把这些表达式求值成 True / False。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("config.flags")
def eval_flag_expr(expr: str) -> bool:
    """对 feature flag 条件表达式求值。

    规格：
      - 语法（递归定义）：
        * ``t`` 为真，``f`` 为假；
        * ``!(x)``：子表达式 x 的逻辑非（括号内恰好一个子表达式）；
        * ``&(x1,x2,...,xn)``（n >= 1）：所有子表达式的逻辑与；
        * ``|(x1,x2,...,xn)``（n >= 1）：所有子表达式的逻辑或。
      - ``expr`` 只由字符 ``( ) & | ! t f ,`` 组成，子表达式之间用逗号分隔，没有空格；保证是合法表达式。
      - 1 <= len(expr) <= 2*10^4，括号嵌套深度不超过 200。
      - 返回 Python 的 ``bool``。

    示例：
      >>> eval_flag_expr("&(|(f))")
      False
      >>> eval_flag_expr("|(f,f,f,t)")
      True
      >>> eval_flag_expr("!(&(f,t))")
      True
    """
    raise TODO("config.flags")
