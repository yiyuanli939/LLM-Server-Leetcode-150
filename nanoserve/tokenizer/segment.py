"""编码前的可切分性校验。

分词器在把文本编码成 token id 之前，先要确认这段文本能被词表中的 token 完整拼出来；
否则贪心最长匹配会在中途卡住。本文件实现这一校验，供 ``Tokenizer.encode`` 调用。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("tok.segment")
def can_segment(text: str, vocab: list[str]) -> bool:
    """编码前校验：判断 text 能否被完整切分为若干个词表 token 的首尾拼接。

    规格：
      - vocab：词表，元素互不相同，每个 token 都是非空字符串（可含空格、标点等任意字符）。
      - 切分时每个 token 可以使用任意多次，也可以不用；切分必须恰好覆盖整个 text，不重叠、不遗漏。
      - 能切分返回 True，否则返回 False。空字符串 text 视为可切分，返回 True。
      - 规模：len(text) 至多数千，词表至多上千个 token；需要多项式时间（不能指数级枚举切法）。

    示例：
      >>> can_segment("nanoserve", ["nano", "serve"])
      True
      >>> can_segment("applepenapple", ["apple", "pen"])
      True
      >>> can_segment("catsandog", ["cats", "dog", "sand", "and", "cat"])
      False
    """
    raise TODO("tok.segment")
