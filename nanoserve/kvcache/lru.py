"""KV Cache 的 LRU 块缓存。

块管理器把最近用过的 KV 块留在显存里；容量满时淘汰最久没有被访问的块，
为新请求腾出位置。这是整个 KV Cache 子系统里最基础的淘汰策略。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.lru")
class LRUBlockCache:
    """按"最近最少使用"淘汰的 KV 块缓存：键是块号，值是该块在显存中的槽位。

    规格：
      - ``LRUBlockCache(capacity)``：``capacity >= 1``，最多同时保存 ``capacity`` 个键。
      - ``get(key)``：键存在则返回其值，并把该键标记为"最近使用"；不存在返回 -1（不改变任何状态）。
      - ``put(key, value)``：键已存在则更新值，并标记为最近使用；否则插入新键——
        若插入后键数超过 ``capacity``，淘汰最久未使用（最近一次 get 命中 / put 最早）的那个键。
      - 键、值均为非负整数。
      - ``get`` 与 ``put`` 均须为平均 O(1)。建议不借助 ``collections.OrderedDict``，
        自己用哈希表 + 双向链表实现。

    示例：
      >>> c = LRUBlockCache(2); c.put(1, 1); c.put(2, 2); c.get(1)
      1
      >>> c.put(3, 3); c.get(2)      # 2 最久未用，被淘汰
      -1
      >>> c.put(4, 4); c.get(1)      # 1 最久未用，被淘汰
      -1
      >>> c.get(3), c.get(4)
      (3, 4)
    """

    def __init__(self, capacity: int) -> None:
        raise TODO("kv.lru")

    def get(self, key: int) -> int:
        raise TODO("kv.lru")

    def put(self, key: int, value: int) -> None:
        raise TODO("kv.lru")
