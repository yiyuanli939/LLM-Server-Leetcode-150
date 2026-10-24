"""KV Cache 的 LFU 淘汰策略。

当显存中的缓存块已满时，优先淘汰被访问次数最少的块；访问次数相同时淘汰最久未被访问的块。
适用于热点前缀长期驻留、偶发请求的块尽快让位的场景。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.lfu")
class LFUBlockCache:
    """按访问频率淘汰的块缓存：容量满时淘汰使用次数最少的块，频率相同时淘汰最久未使用的块。

    规格：
      - ``LFUBlockCache(capacity)``：容量 ``capacity >= 1``（最多同时保存的键数）。
      - 每个键维护一个"使用次数"：新插入时为 1；之后每次 ``get`` 命中或 ``put`` 覆盖已有键都 +1，
        同时把该键标记为"最近使用"。
      - ``get(key)``：键存在返回其值（并计一次使用），否则返回 -1（不改变任何状态）。
      - ``put(key, value)``：键已存在则更新值（计一次使用）；否则插入新键——若此时已满，
        先淘汰使用次数最少的键，若有多个，淘汰其中最久未使用（最近一次 get/put 最早）的那个，再插入。
      - 键、值均为非负整数。
      - ``get`` 与 ``put`` 均须为平均 O(1)。

    示例：
      >>> c = LFUBlockCache(2); c.put(1, 1); c.put(2, 2); c.get(1)
      1
      >>> c.put(3, 3); c.get(2)      # 2 的使用次数最少，被淘汰
      -1
      >>> c.get(3)
      3
      >>> c.put(4, 4); c.get(1)      # 1 与 3 都用过 2 次，1 更久未用，被淘汰
      -1
      >>> c.get(3), c.get(4)
      (3, 4)
    """

    def __init__(self, capacity: int) -> None:
        raise TODO("kv.lfu")

    def get(self, key: int) -> int:
        raise TODO("kv.lfu")

    def put(self, key: int, value: int) -> None:
        raise TODO("kv.lfu")
