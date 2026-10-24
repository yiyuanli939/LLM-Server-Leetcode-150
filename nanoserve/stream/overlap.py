"""stop string 与输出尾部的精确重叠。

流式输出时，已生成文本的末尾可能恰好是某个 stop string 的开头（例如 stop 是 "</s>"，
输出刚好以 "</" 结尾）。这几个字符暂时不能发给客户端：下一个 token 可能把 stop 补全。
扣留得太多会让输出卡顿，扣留得太少会把 stop 的一部分漏发出去。引擎把
``stop + "\\x00" + tail`` 交给本文件的函数，算出的最长 border 长度恰好就是需要扣留的字符数。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("stream.stop_overlap")
def longest_border(s: str) -> str:
    """返回 s 最长的「既是真前缀、又是后缀」的子串（border）；不存在则返回空串 ""。

    规格：
      - s 可含任意字符：字母、数字、标点、空格、换行、"\\x00"、任意 Unicode 字符都可能出现；
        字符一律按 Python ``str`` 的单个元素逐个比较。1 <= len(s)。
      - 「真前缀」指 s[:k] 且 0 <= k < len(s)（不能是 s 本身）。
        返回满足 s[:k] == s[len(s) - k:] 的最大 k 对应的 s[:k]。
      - 前缀与后缀允许相互重叠（见下面 "ababab" 的例子）。
      - 复杂度：O(n)。逐个 k 比较前后缀的 O(n^2) 做法不满足要求。
      - 引擎的用法：``len(longest_border(stop + "\\x00" + tail))`` 就是 tail 的最长后缀、
        同时又是 stop 前缀的长度（"\\x00" 不出现在 stop 中，保证 border 不会跨过分隔符）。

    示例：
      >>> longest_border("level")
      'l'
      >>> longest_border("ababab")
      'abab'
      >>> longest_border("abc")
      ''
      >>> longest_border("</s>\\x00ok </")
      '</'
    """
    raise TODO("stream.stop_overlap")
