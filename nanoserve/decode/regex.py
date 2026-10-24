"""约束解码的正则校验。

约束解码要求模型输出符合一个简化正则（只支持 '.' 和 '*'）；生成结束后用它做最终校验，
判断整段输出是否完整匹配该模式。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("decode.regex")
def full_match(s: str, p: str) -> bool:
    """判断字符串 s 是否被模式 p **完整**匹配（覆盖整个 s，而不是部分子串）。

    规格：
      - s 可含任意字符（大小写字母、空格、标点、换行、任意 Unicode 字符，包括 ``.`` 和 ``*``）。
      - p 中只有 ``.`` 和 ``*`` 是特殊字符，其余任何字符都是字面量，只匹配与它相同的那一个字符
        （区分大小写）。没有转义：s 中的字面 ``.`` 只能由通配符 ``.`` 匹配。
      - ``.`` 匹配任意单个字符；``*`` 表示它前面那**一个**元素（字面字符或 ``.``）重复零次或多次。
      - 保证 p 中每个 ``*`` 前面都有一个合法元素（不会以 ``*`` 开头，也不会出现 ``**``）。
      - s 与 p 都可能为空串；空模式只匹配空串。
      - 不得使用 ``re`` 等现成正则库。

    示例：
      >>> full_match("aa", "a")
      False
      >>> full_match("aa", "a*")
      True
      >>> full_match("ab", ".*")
      True
      >>> full_match("The cache, ok.", "The c.*e, o*k.")
      True
      >>> full_match("The cache, ok.", "the c.*")
      False
    """
    raise TODO("decode.regex")
