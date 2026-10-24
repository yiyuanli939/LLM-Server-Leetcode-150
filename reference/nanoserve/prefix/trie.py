from __future__ import annotations


# LC 208 Implement Trie (Prefix Tree) — dict children, so keys may use any characters
class _Node:
    __slots__ = ("children", "end")

    def __init__(self) -> None:
        self.children: dict[str, _Node] = {}
        self.end = False


class PrefixTrie:
    def __init__(self) -> None:
        self.root = _Node()

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            nxt = node.children.get(ch)
            if nxt is None:
                nxt = node.children[ch] = _Node()
            node = nxt
        node.end = True

    def _walk(self, s: str) -> _Node | None:
        node = self.root
        for ch in s:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def search(self, word: str) -> bool:
        node = self._walk(word)
        return node is not None and node.end

    def starts_with(self, prefix: str) -> bool:
        return self._walk(prefix) is not None
