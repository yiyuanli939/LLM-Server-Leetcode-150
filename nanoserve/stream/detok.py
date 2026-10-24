"""流式反解码时的"扣字"逻辑。

以单词为单位流式输出时，文本末尾可能停在半个单词上（下一个 token 还会接着拼）。
引擎需要知道末尾那个单词有多长，先把它扣住不发，等单词完整后再一起吐出去。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("stream.holdback")
def trailing_word_len(s: str) -> int:
    """返回 s 中最后一个单词的长度（忽略尾部空格），用于流式输出时扣住半个单词。

    规格：
      - s 由单词和空格 ' ' 组成；单词是不含空格的极大连续非空字符段。
      - 忽略末尾的所有空格，返回最后一个单词的字符数。
      - 若 s 为空串或全是空格（没有任何单词），返回 0。
      - 复杂度：只需从尾部扫描，O(最后一个单词长度 + 尾部空格数)。

    示例：
      >>> trailing_word_len("Hello World")
      5
      >>> trailing_word_len("   fly me   to   the moon  ")
      4
      >>> trailing_word_len("luffy is still joyboy")
      6
    """
    raise TODO("stream.holdback")
