"""CLI 输出的排版工具。

生成结束后，CLI 会把整段文本按固定宽度两端对齐打印成一个"摘要框"；调试日志时还有一个
按单词倒序查看的视图。本文件实现这两种纯文本排版。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("stream.justify")
def justify(words: list[str], width: int) -> list[str]:
    """CLI 输出的两端对齐排版：把单词序列排成每行恰好 width 个字符的若干行。

    规格：
      - words 非空，每个单词非空、不含空格，且 len(word) <= width。
      - 贪心分行：按顺序往当前行放尽可能多的单词，单词之间至少一个空格，行长不超过 width。
      - 除最后一行外，每行都要两端对齐：用空格补足到 width，空格尽量均匀地分配在单词之间的
        空隙里；若不能均分，靠左的空隙比靠右的多（多出的空格从左往右逐个分配）。
      - 若某行（非最后一行）只有一个单词，则左对齐：单词在前，右侧用空格补足到 width。
      - 最后一行左对齐：单词之间只放一个空格，行尾用空格补足到 width。
      - 返回各行组成的列表，每个字符串长度都恰好为 width。

    示例：
      >>> justify(["This", "is", "an", "example", "of", "text", "justification."], 16)
      ['This    is    an', 'example  of text', 'justification.  ']
      >>> justify(["What", "must", "be", "acknowledgment", "shall", "be"], 16)
      ['What   must   be', 'acknowledgment  ', 'shall be        ']
    """
    raise TODO("stream.justify")


