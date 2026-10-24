from __future__ import annotations


# LC 677 Map Sum Pairs — dict children, so keys may use any characters
class _Node:
    __slots__ = ("children", "total")

    def __init__(self) -> None:
        self.children: dict[str, _Node] = {}
        self.total = 0  # sum of the values of all keys passing through this node


class PrefixHitSum:
    def __init__(self) -> None:
        self.root = _Node()
        self.vals: dict[str, int] = {}

    def insert(self, key: str, val: int) -> None:
        delta = val - self.vals.get(key, 0)
        self.vals[key] = val
        node = self.root
        for ch in key:
            nxt = node.children.get(ch)
            if nxt is None:
                nxt = node.children[ch] = _Node()
            node = nxt
            node.total += delta

    def sum(self, prefix: str) -> int:
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return 0
        return node.total
