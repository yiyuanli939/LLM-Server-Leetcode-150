"""Reference: stream.multi_stop."""
from __future__ import annotations

from collections import deque

# End-of-word marker. Not a str, so it can never collide with a character of a stop string.
_END = None


# LC 1032 Stream of Characters
class MultiStopMatcher:
    def __init__(self, stops: list[str]) -> None:
        # Trie over the *reversed* stop strings, so a suffix check walks back from the newest char.
        self.root: dict = {}
        for s in stops:
            node = self.root
            for ch in reversed(s):
                node = node.setdefault(ch, {})
            node[_END] = True
        self.buf: deque[str] = deque(maxlen=max(len(s) for s in stops))

    def feed(self, ch: str) -> bool:
        self.buf.append(ch)
        node = self.root
        for c in reversed(self.buf):
            node = node.get(c)
            if node is None:
                return False
            if _END in node:
                return True
        return False
