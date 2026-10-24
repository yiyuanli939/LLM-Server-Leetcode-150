"""前缀缓存命中统计。

每个缓存键（一段 prompt 前缀）记录一个命中值；面板需要回答"以某前缀开头的所有键的命中值之和"，
用来判断哪一类 prompt 前缀最值得常驻。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("prefix.hit_sum")
class PrefixHitSum:
    """键 -> 命中值 的映射，支持按前缀求和。

    规格：
      - ``insert(key, val)``：把 ``key`` 的值设为 ``val``；若 key 已存在，**覆盖**旧值（不是累加）。
      - ``sum(prefix)``：返回所有以 ``prefix`` 开头的键（包括恰好等于 prefix 的键）的当前值之和；
        没有匹配返回 0。
      - key 与 prefix 为非空字符串，可以包含**任意字符**（空格、标点、换行、任意 Unicode 字符，包括 ``$``、
        ``#`` 这类常被拿来当哨兵的字符），按字符逐个比较、区分大小写；val 为非负整数。
      - insert 与 sum 的复杂度应只与字符串长度相关（O(len)），与键的数量无关。

    示例：
      >>> h = PrefixHitSum(); h.insert("apple", 3); h.sum("ap")
      3
      >>> h.insert("app", 2); h.sum("ap")
      5
      >>> h.insert("Sys: hi!", 4); h.insert("Sys: héllo $5", 1); h.sum("Sys: h"), h.sum("Sys: hé"), h.sum("sys")
      (5, 1, 0)
    """

    def __init__(self) -> None:
        raise TODO("prefix.hit_sum")

    def insert(self, key: str, val: int) -> None:
        raise TODO("prefix.hit_sum")

    def sum(self, prefix: str) -> int:
        raise TODO("prefix.hit_sum")
