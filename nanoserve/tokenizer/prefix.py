"""批量 prompt 的公共前缀检测。

同一应用发来的请求往往共享一段很长的 system prompt。找出一批 prompt 的最长公共前缀，
是后续前缀缓存（多个请求复用同一段 KV cache）的起点；引擎的 ``shared_prefix`` 会调用这里。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("tok.common_prefix")
def common_prefix(prompts: list[str]) -> str:
    """找出一批 prompt 的最长公共前缀，用于检测共享的 system prompt。

    规格：
      - prompts：字符串列表，元素可含任意字符，也可以是空字符串。
      - 返回所有字符串共同拥有的最长前缀（逐字符、区分大小写比较）。
      - 没有公共前缀时返回 ""；prompts 为空列表时返回 ""；只有一个元素时返回它本身。

    示例：
      >>> common_prefix(["flower", "flow", "flight"])
      'fl'
      >>> common_prefix(["dog", "racecar", "car"])
      ''
      >>> common_prefix(["The scheduler wakes", "The scheduler sleeps"])
      'The scheduler '
    """
    raise TODO("tok.common_prefix")
