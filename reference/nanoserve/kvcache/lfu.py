from __future__ import annotations

from collections import OrderedDict, defaultdict


# LC 460 LFU Cache
class LFUBlockCache:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.vals: dict[int, int] = {}
        self.freq: dict[int, int] = {}
        self.buckets: defaultdict[int, OrderedDict[int, None]] = defaultdict(OrderedDict)
        self.min_freq = 0

    def _touch(self, key: int) -> None:
        f = self.freq[key]
        bucket = self.buckets[f]
        del bucket[key]
        if not bucket:
            del self.buckets[f]
            if self.min_freq == f:
                self.min_freq = f + 1
        self.freq[key] = f + 1
        self.buckets[f + 1][key] = None

    def get(self, key: int) -> int:
        if key not in self.vals:
            return -1
        self._touch(key)
        return self.vals[key]

    def put(self, key: int, value: int) -> None:
        if self.capacity <= 0:
            return
        if key in self.vals:
            self.vals[key] = value
            self._touch(key)
            return
        if len(self.vals) >= self.capacity:
            bucket = self.buckets[self.min_freq]
            victim, _ = bucket.popitem(last=False)
            if not bucket:
                del self.buckets[self.min_freq]
            del self.vals[victim]
            del self.freq[victim]
        self.vals[key] = value
        self.freq[key] = 1
        self.buckets[1][key] = None
        self.min_freq = 1
