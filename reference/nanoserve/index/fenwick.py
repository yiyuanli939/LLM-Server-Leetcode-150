from __future__ import annotations


# LC 307 Range Sum Query - Mutable (Fenwick tree)
class RangeCounter:
    def __init__(self, nums: list[int]) -> None:
        self.n = len(nums)
        self.nums = list(nums)
        self.tree = [0] * (self.n + 1)
        for i, v in enumerate(nums, 1):
            self.tree[i] += v
            j = i + (i & -i)
            if j <= self.n:
                self.tree[j] += self.tree[i]

    def _prefix(self, i: int) -> int:
        s = 0
        while i > 0:
            s += self.tree[i]
            i -= i & -i
        return s

    def update(self, i: int, val: int) -> None:
        delta = val - self.nums[i]
        self.nums[i] = val
        j = i + 1
        while j <= self.n:
            self.tree[j] += delta
            j += j & -j

    def sum_range(self, l: int, r: int) -> int:
        return self._prefix(r + 1) - self._prefix(l)
