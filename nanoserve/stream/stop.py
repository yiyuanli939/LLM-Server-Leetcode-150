"""stop string 检测。

生成循环每产出一个 token，就要检查用户给出的 stop string 是否已经出现在输出里，
出现了就截断并结束生成。本文件提供单个 stop string 的定位，以及"若干等长片段
以任意顺序拼接"这种乱序 stop 模式的定位。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("stream.find_stop")
def find_stop(text: str, stop: str) -> int:
    """返回 stop string 在已生成文本 text 中首次出现的起始下标（0-based），没有则返回 -1。

    规格：
      - text、stop 可含任意字符；保证 stop 非空（len(stop) >= 1），text 可以为空。
      - 返回最小的 i，使得 text[i : i + len(stop)] == stop；不存在返回 -1。
      - 不得直接调用 str.find / str.index / re 等现成的子串查找（要自己写匹配）。

    示例：
      >>> find_stop("sadbutsad", "sad")
      0
      >>> find_stop("nanoserve", "nanos.")
      -1
      >>> find_stop("hello", "ll")
      2
    """
    raise TODO("stream.find_stop")


