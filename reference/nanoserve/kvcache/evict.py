from __future__ import annotations

import random


# LC 380 Insert Delete GetRandom O(1)
class RandomEvictSet:
    def __init__(self) -> None:
        self.items: list[int] = []
        self.pos: dict[int, int] = {}

    def insert(self, x: int) -> bool:
        if x in self.pos:
            return False
        self.pos[x] = len(self.items)
        self.items.append(x)
        return True

    def remove(self, x: int) -> bool:
        i = self.pos.pop(x, None)
        if i is None:
            return False
        last = self.items.pop()
        if i < len(self.items):
            self.items[i] = last
            self.pos[last] = i
        return True

    def pick(self) -> int:
        return self.items[random.randrange(len(self.items))]
