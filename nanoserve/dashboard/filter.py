"""面板中的模糊过滤。

运维面板的搜索框支持 fzf 式模糊过滤：输入 ``lm3`` 就能筛出 ``llama-3-8b`` 这样的模型名或请求名，
只要输入的字符按顺序出现在名字里即可。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("dash.fuzzy")
def fuzzy_match(query: str, text: str) -> bool:
    """判断 ``query`` 的字符是否按顺序（可以不连续）出现在 ``text`` 中。

    规格：
      - 等价于：能否从 ``text`` 中删去若干个（可以是 0 个）字符、且不改变其余字符的相对顺序，
        得到 ``query``。
      - 区分大小写；``query`` 中重复的字符需要在 ``text`` 中按顺序出现相应多次。
      - ``query`` 为空串时返回 True（``text`` 也可以为空）。
      - 复杂度 O(len(query) + len(text))。

    示例：
      >>> fuzzy_match("abc", "ahbgdc")
      True
      >>> fuzzy_match("axc", "ahbgdc")
      False
      >>> fuzzy_match("lm3", "llama-3-8b")
      True
    """
    raise TODO("dash.fuzzy")
