"""多路复用输出流的校验。

服务端把两个请求的输出按字符交错写进同一条连接；评测时需要确认这条合并流没有丢字、
多字或打乱单个请求内部的顺序。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("eval.interleave_ok")
def is_interleaving(a: str, b: str, merged: str) -> bool:
    """判断 merged 能否由 a 与 b 交错合并而成。

    规格：
      - 交错合并：把 a 和 b 各自切成若干段，按 a 段、b 段交替（或 b 段、a 段交替）拼接；
        等价地说，merged 中的字符可以分成两组，一组按原顺序恰好构成 a，另一组按原顺序恰好构成 b。
      - 长度必须匹配：``len(merged) == len(a) + len(b)``，否则返回 False。
      - a、b、merged 可为空串，可含任意字符（大小写字母、空格、标点、换行、任意 Unicode 字符）；
        字符按原样逐个比较。复杂度 O(len(a) * len(b))。

    示例：
      >>> is_interleaving("aabcc", "dbbca", "aadbbcbcac")
      True
      >>> is_interleaving("aabcc", "dbbca", "aadbbbaccc")
      False
      >>> is_interleaving("", "", "")
      True
      >>> is_interleaving("Hi, ", "ok.", "Hio,k .")
      True
    """
    raise TODO("eval.interleave_ok")
