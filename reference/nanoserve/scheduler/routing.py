"""Reference: sched.weighted_route."""
from __future__ import annotations

import bisect
import itertools
import random


# LC 528 Random Pick with Weight
class WeightedRouter:
    def __init__(self, weights: list[int]) -> None:
        self.prefix = list(itertools.accumulate(weights))

    def pick(self) -> int:
        target = random.randint(1, self.prefix[-1])
        return bisect.bisect_left(self.prefix, target)
