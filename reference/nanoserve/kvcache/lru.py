from __future__ import annotations


class _Node:
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key = key
        self.val = val
        self.prev: _Node | None = None
        self.next: _Node | None = None


# LC 146 LRU Cache
class LRUBlockCache:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.map: dict[int, _Node] = {}
        self.head = _Node()  # sentinel: head.next is most recently used
        self.tail = _Node()  # sentinel: tail.prev is least recently used
        self.head.next = self.tail
        self.tail.prev = self.head

    def _unlink(self, node: _Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev

    def _push_front(self, node: _Node) -> None:
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: int) -> int:
        node = self.map.get(key)
        if node is None:
            return -1
        self._unlink(node)
        self._push_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        node = self.map.get(key)
        if node is not None:
            node.val = value
            self._unlink(node)
            self._push_front(node)
            return
        node = _Node(key, value)
        self.map[key] = node
        self._push_front(node)
        if len(self.map) > self.capacity:
            lru = self.tail.prev
            self._unlink(lru)
            del self.map[lru.key]
