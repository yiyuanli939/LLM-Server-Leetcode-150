from __future__ import annotations

from bisect import bisect_right


# LC 1146 Snapshot Array
class SnapshotTable:
    def __init__(self, length: int) -> None:
        # per index: parallel lists of snap ids and values, starting with (0 -> 0)
        self.ids: list[list[int]] = [[0] for _ in range(length)]
        self.vals: list[list[int]] = [[0] for _ in range(length)]
        self.snap_id = 0

    def set(self, index: int, val: int) -> None:
        ids, vals = self.ids[index], self.vals[index]
        if ids[-1] == self.snap_id:
            vals[-1] = val
        else:
            ids.append(self.snap_id)
            vals.append(val)

    def snap(self) -> int:
        self.snap_id += 1
        return self.snap_id - 1

    def get(self, index: int, snap_id: int) -> int:
        i = bisect_right(self.ids[index], snap_id) - 1
        return self.vals[index][i]
