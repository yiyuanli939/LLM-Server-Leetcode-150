from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from typing import Hashable


# LC 981 Time Based Key-Value Store
class VersionedStore:
    def __init__(self) -> None:
        self.times: defaultdict[Hashable, list[int]] = defaultdict(list)
        self.values: defaultdict[Hashable, list[str]] = defaultdict(list)

    def set(self, key: Hashable, value: str, ts: int) -> None:
        self.times[key].append(ts)
        self.values[key].append(value)

    def get(self, key: Hashable, ts: int) -> str:
        if key not in self.times:
            return ""
        i = bisect_right(self.times[key], ts)
        return self.values[key][i - 1] if i else ""
