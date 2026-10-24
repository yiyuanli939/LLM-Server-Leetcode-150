"""块内容哈希的去重表。

前缀共享时，内容完全相同的 KV 块只需要存一份：块管理器先算出块内容的哈希（一个整数），
再查表看这个哈希是否已经对应某个物理块号。这张表处在每次分配的热路径上，
因此要求自己实现，不依赖内置的 dict / set。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.block_hash")
class BlockHashMap:
    """块内容哈希 → 物理块号的去重表（自己实现的整数键哈希表）。

    规格：
      - ``BlockHashMap()``：初始为空表。
      - ``put(key, value)``：把 key 映射到 value；若 key 已存在则覆盖原值。返回 None。
      - ``get(key)``：返回 key 当前映射到的值；key 不存在返回 -1。
      - ``remove(key)``：删除 key 及其映射；key 不存在则什么也不做。返回 None。
      - 0 <= key, value <= 10^6；总调用次数不超过 10^4 量级。
      - 实现要求：不得使用内置 ``dict`` / ``set``（以及基于它们的 ``collections`` 容器），
        请用"桶数组 + 链表/列表拉链"或"开放寻址"自己实现。各操作平均 O(1)。

    示例：
      >>> m = BlockHashMap()
      >>> m.put(1, 1); m.put(2, 2)
      >>> m.get(1), m.get(3)
      (1, -1)
      >>> m.put(2, 1); m.get(2)
      1
      >>> m.remove(2); m.get(2)
      -1
    """

    def __init__(self) -> None:
        raise TODO("kv.block_hash")

    def put(self, key: int, value: int) -> None:
        raise TODO("kv.block_hash")

    def get(self, key: int) -> int:
        raise TODO("kv.block_hash")

    def remove(self, key: int) -> None:
        raise TODO("kv.block_hash")
