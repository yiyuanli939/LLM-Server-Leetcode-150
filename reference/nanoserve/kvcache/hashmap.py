"""Reference: kv.block_hash."""
from __future__ import annotations


# LC 706 Design HashMap
class BlockHashMap:
    _BUCKETS = 2069  # prime, so keys with a common stride still spread out

    def __init__(self) -> None:
        # separate chaining: each bucket is a list of [key, value] pairs
        self.buckets: list[list[list[int]]] = [[] for _ in range(self._BUCKETS)]

    def _bucket(self, key: int) -> list[list[int]]:
        return self.buckets[key % self._BUCKETS]

    def put(self, key: int, value: int) -> None:
        bucket = self._bucket(key)
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value
                return
        bucket.append([key, value])

    def get(self, key: int) -> int:
        for k, v in self._bucket(key):
            if k == key:
                return v
        return -1

    def remove(self, key: int) -> None:
        bucket = self._bucket(key)
        for i, pair in enumerate(bucket):
            if pair[0] == key:
                bucket[i] = bucket[-1]  # swap-remove: order inside a bucket doesn't matter
                bucket.pop()
                return
