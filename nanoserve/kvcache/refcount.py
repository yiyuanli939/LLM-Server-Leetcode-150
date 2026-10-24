"""块引用计数。

共享前缀块被多个请求引用；每次引用/解除引用都要更新计数，
并且要能 O(1) 找出被引用最多的块（热点）和被引用最少的块（最先可回收的候选）。
"""
from __future__ import annotations

from typing import Hashable

from nanoserve._exercise import TODO, exercise


@exercise("kv.refcount")
class RefCounter:
    """计数器，支持 O(1) 增减计数以及 O(1) 取计数最大/最小的键。

    规格：
      - 键可以是任意可哈希的值（例如字符串，或整数块号——块号 0 也是合法的键）。
      - ``inc(key)``：key 的计数 +1；key 不存在时以计数 1 插入。
      - ``dec(key)``：key 的计数 -1；减到 0 时把 key 移除。保证调用时 key 存在。
      - ``max_key()``：返回计数最大的任意一个键（并列时返回其中任意一个）；没有任何键时返回 ``""``。
      - ``min_key()``：返回计数最小的任意一个键（并列时返回其中任意一个）；没有任何键时返回 ``""``。
      - 四个操作均须为平均 O(1)。

    示例：
      >>> r = RefCounter(); r.inc("hello"); r.inc("hello"); r.max_key(), r.min_key()
      ('hello', 'hello')
      >>> r.inc("leet"); r.max_key(), r.min_key()
      ('hello', 'leet')
      >>> b = RefCounter(); b.inc(0); b.inc(7); b.inc(7); b.max_key(), b.min_key()
      (7, 0)
    """

    def __init__(self) -> None:
        raise TODO("kv.refcount")

    def inc(self, key: Hashable) -> None:
        raise TODO("kv.refcount")

    def dec(self, key: Hashable) -> None:
        raise TODO("kv.refcount")

    def max_key(self) -> Hashable:
        raise TODO("kv.refcount")

    def min_key(self) -> Hashable:
        raise TODO("kv.refcount")
