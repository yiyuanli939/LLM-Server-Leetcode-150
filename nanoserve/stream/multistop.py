"""流式输出中的多 stop string 检测。

生成时用户可以给出多个 stop string，一旦已输出的文本以其中任意一个结尾就应停止生成。
token 是逐个解码、逐字符吐出的，因此检测器必须是增量的：每喂入一个字符就立即给出判断，
而不能每次都把全部输出与所有 stop string 重新比一遍。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("stream.multi_stop")
class MultiStopMatcher:
    """流式多 stop string 检测器：每喂入一个字符，判断当前输出是否以任一 stop string 结尾。

    规格：
      - 构造：stops 为非空列表，每个 stop string 非空；可能有重复。
        stop string 可含**任意字符**：标点（"."、"###"）、空白与换行（"\\n\\n"）、"</s>" 这类标记、
        "\\x00"、任意 Unicode 字符（"。"、"🙂"）都可能出现。字符一律按 Python ``str`` 的单个元素比较。
        注意：不要拿某个"普通字符"（如 "$"、"#"）当 Trie 的结束标记——它也可能出现在 stop string 里。
      - feed(ch)：ch 是长度为 1 的字符串（同样可以是任意字符）。把它追加到"迄今为止喂入的全部字符"之后，
        若存在某个 stop string 恰好是这段全部字符的后缀，返回 True，否则返回 False。
      - 一次返回 True 不会重置状态：之后继续 feed，仍然基于从构造起喂入的全部字符判断。
      - 复杂度：设最长 stop string 长度为 L，每次 feed 为 O(L)（与已喂入的总字符数无关）。

    示例：
      >>> m = MultiStopMatcher(["cd", "f", "kl"])
      >>> [m.feed(c) for c in "abcdefghijkl"]
      [False, False, False, True, False, True, False, False, False, False, False, True]
      >>> m = MultiStopMatcher(["</s>", "\\n\\n"])
      >>> [m.feed(c) for c in "a\\n</s>"]
      [False, False, False, False, False, True]
    """

    def __init__(self, stops: list[str]) -> None:
        raise TODO("stream.multi_stop")

    def feed(self, ch: str) -> bool:
        raise TODO("stream.multi_stop")
