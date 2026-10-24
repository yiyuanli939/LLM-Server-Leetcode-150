"""块表的 copy-on-write 快照。

fork 请求（如并行采样、beam search）需要在某一时刻"冻结"块表，之后仍能按快照号读出当时的映射。
整表复制太贵，所以每个槽位只记录发生过的变化，查询时按快照号定位历史值。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.snapshot")
class SnapshotTable:
    """长度为 length 的整数表，支持打快照并按快照号查询任一槽位的历史值；只记录变化，不整表复制。

    规格：
      - ``SnapshotTable(length)``：创建长度为 ``length >= 1`` 的表，所有槽位初值为 0。
      - ``set(index, val)``：把槽位 ``index``（0 起，``0 <= index < length``）设为 ``val``。
      - ``snap()``：打一次快照，返回快照号 = 已打快照总次数 - 1（第一次返回 0，之后依次 +1）。
      - ``get(index, snap_id)``：返回打编号为 ``snap_id`` 的快照那一刻，槽位 ``index`` 的值。
        保证 ``snap_id`` 是已经返回过的快照号。
      - 空间应与 set 次数成正比（而不是 length × 快照数）；get 应为 O(log m)（m 为该槽位的修改次数）。

    示例：
      >>> t = SnapshotTable(3); t.set(0, 5); t.snap()
      0
      >>> t.set(0, 6); t.get(0, 0)
      5
    """

    def __init__(self, length: int) -> None:
        raise TODO("kv.snapshot")

    def set(self, index: int, val: int) -> None:
        raise TODO("kv.snapshot")

    def snap(self) -> int:
        raise TODO("kv.snapshot")

    def get(self, index: int, snap_id: int) -> int:
        raise TODO("kv.snapshot")
