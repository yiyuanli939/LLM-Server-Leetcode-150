"""配置文本的预检。

在真正解析配置之前，先做一遍廉价的结构检查：所有括号都必须正确配对和嵌套，
否则直接报错，不必进入完整的解析器。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("config.brackets")
def brackets_balanced(s: str) -> bool:
    """检查字符串中的括号是否正确配对。

    规格：
      - s 是任意字符串（长度 >= 1，可以含字母、数字、空格、换行、``=`` ``,`` 等任何字符），
        这样整段配置文本可以直接拿来检查。
      - 只有 ``( ) [ ] { }`` 这六种字符参与检查，其它字符一律忽略。
      - 合法当且仅当：每个左括号都被同类型的右括号闭合；闭合顺序正确（后开先闭）；
        每个右括号都有一个对应的同类型左括号。不含任何括号的字符串是合法的。
      - 合法返回 True，否则返回 False。

    示例：
      >>> brackets_balanced("()[]{}")
      True
      >>> brackets_balanced("(]")
      False
      >>> brackets_balanced("([])")
      True
      >>> brackets_balanced("[server]\\npool = 2[big,]small")
      True
      >>> brackets_balanced("x = (1 + 2]")
      False
    """
    raise TODO("config.brackets")
