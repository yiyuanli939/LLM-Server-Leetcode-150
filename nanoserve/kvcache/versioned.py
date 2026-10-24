"""带时间戳的多版本缓存条目。

同一个键（例如某个 adapter 的配置、某段前缀的元数据）会随时间写入多个版本；
读取时给出一个时间点，返回在该时间点及之前写入的最新版本。
"""
from __future__ import annotations

from typing import Hashable

from nanoserve._exercise import TODO, exercise


@exercise("kv.versioned")
class VersionedStore:
    """多版本键值存储：按时间戳写入，查询不晚于给定时间戳的最新版本。

    规格：
      - 键可以是任意可哈希的值（例如字符串，或整数块号——0 也是合法的键）；值是字符串。
      - ``set(key, value, ts)``：在时间戳 ``ts`` 为 ``key`` 写入一个版本 ``value``。
        保证所有 ``set`` 调用的 ``ts`` 严格递增（跨所有键全局递增）。
      - ``get(key, ts)``：返回 ``key`` 的所有版本中时间戳 ``<= ts`` 的那个最新版本的值；
        若不存在这样的版本（键从未写入，或最早版本也晚于 ts），返回空字符串 ``""``。
      - 时间戳为正整数；get 应为 O(log m)（m 为该键的版本数）。

    示例：
      >>> s = VersionedStore(); s.set("foo", "bar", 1); s.get("foo", 1), s.get("foo", 3)
      ('bar', 'bar')
      >>> s.set("foo", "bar2", 4); s.get("foo", 4), s.get("foo", 5)
      ('bar2', 'bar2')
      >>> s.set(0, "r1", 6); s.get(0, 5), s.get(0, 6), s.get("0", 6)
      ('', 'r1', '')
    """

    def __init__(self) -> None:
        raise TODO("kv.versioned")

    def set(self, key: Hashable, value: str, ts: int) -> None:
        raise TODO("kv.versioned")

    def get(self, key: Hashable, ts: int) -> str:
        raise TODO("kv.versioned")
