from __future__ import annotations

from typing import Hashable, Optional


class _Bucket:
    __slots__ = ("count", "keys", "prev", "next")

    def __init__(self, count: int) -> None:
        self.count = count
        self.keys: set[Hashable] = set()
        self.prev: Optional[_Bucket] = None
        self.next: Optional[_Bucket] = None


# LC 432 All O`one Data Structure
class RefCounter:
    def __init__(self) -> None:
        self.head = _Bucket(0)          # sentinel: smaller than every count
        self.tail = _Bucket(0)          # sentinel: larger than every count
        self.head.next, self.tail.prev = self.tail, self.head
        self.where: dict[Hashable, _Bucket] = {}

    def _insert_after(self, node: _Bucket, count: int) -> _Bucket:
        b = _Bucket(count)
        b.prev, b.next = node, node.next
        node.next.prev = b
        node.next = b
        return b

    def _remove_if_empty(self, b: _Bucket) -> None:
        if not b.keys:
            b.prev.next, b.next.prev = b.next, b.prev

    def inc(self, key: Hashable) -> None:
        cur = self.where.get(key, self.head)
        nxt = cur.next
        if nxt is self.tail or nxt.count != cur.count + 1:
            nxt = self._insert_after(cur, cur.count + 1)
        nxt.keys.add(key)
        self.where[key] = nxt
        if cur is not self.head:
            cur.keys.discard(key)
            self._remove_if_empty(cur)

    def dec(self, key: Hashable) -> None:
        cur = self.where[key]
        if cur.count == 1:
            del self.where[key]
        else:
            prv = cur.prev
            if prv is self.head or prv.count != cur.count - 1:
                prv = self._insert_after(prv, cur.count - 1)
            prv.keys.add(key)
            self.where[key] = prv
        cur.keys.discard(key)
        self._remove_if_empty(cur)

    def max_key(self) -> Hashable:
        b = self.tail.prev
        return "" if b is self.head else next(iter(b.keys))

    def min_key(self) -> Hashable:
        b = self.head.next
        return "" if b is self.tail else next(iter(b.keys))
