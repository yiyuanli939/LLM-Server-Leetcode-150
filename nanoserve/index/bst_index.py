"""Framework (M4): a binary-search-tree index over distinct integer keys that keeps itself shallow.

The EDF waiting queue (``nanoserve.index.queue.DeadlineQueue``) keeps one of these over its request
keys; its order *is* the queue order::

    idx = BSTIndex()
    for k in (50, 10, 90):
        idx.add(k)
    idx.first(), idx.kth(2), list(idx.keys()), idx.between(20, 95)   # 10, 50, [10, 50, 90], [50, 90]

Balance. Plain BST insertion degenerates into a chain when keys arrive in increasing order — which is
how deadlines usually arrive (later requests, later deadlines). After every update the index measures
its depth; when it exceeds ``depth_limit(n) = 2·log2(n) + 2`` (a balanced tree has ⌈log2(n+1)⌉ levels)
the tree is rebuilt perfectly balanced from its in-order keys. Measuring is O(n), which is fine for a
waiting queue of a few hundred requests, and it keeps the guarantee independent of *how* insert/delete
reshape the tree (their specs allow any valid BST as the result).

Preconditions the owner must establish: every key passed to ``add`` is absent and every key passed to
``discard`` is present (the queue tracks membership in a dict); ``check()`` audits the result.

Exercises this file calls (M4): index.insert, index.delete, index.kth, index.iter, index.validate,
index.build, index.min_gap, prefix.depth, prefix.level_dump, prefix.fork_point.
"""
from __future__ import annotations

import math
from typing import Iterable, Iterator

from nanoserve.common.nodes import TreeNode
from nanoserve.index.bst_ops import delete_key, insert_key
from nanoserve.index.deadline import DeadlineIterator, build_balanced, is_valid_index, kth_earliest, min_gap
from nanoserve.prefix.dump import level_dump
from nanoserve.prefix.tree_ops import fork_point, max_depth


def depth_limit(n: int) -> float:
    """Deepest a tree of ``n`` keys may get before it is rebuilt."""
    return 2 * math.log2(n) + 2 if n > 0 else 0.0


def _ceiling(root: TreeNode | None, key: int) -> TreeNode | None:
    """Node holding the smallest key >= ``key`` (one root-to-leaf walk), or None."""
    best = None
    while root is not None:
        if root.val >= key:
            best, root = root, root.left
        else:
            root = root.right
    return best


def _floor(root: TreeNode | None, key: int) -> TreeNode | None:
    """Node holding the largest key <= ``key``, or None."""
    best = None
    while root is not None:
        if root.val <= key:
            best, root = root, root.right
        else:
            root = root.left
    return best


class BSTIndex:
    """Ordered set of distinct ints on a self-rebalancing BST (``TreeNode.val`` = key)."""

    def __init__(self, sorted_keys: Iterable[int] = ()) -> None:
        self.root: TreeNode | None = None
        self.size = 0
        self.height = 0            # depth measured after the last update
        self.deepest = 0           # largest depth ever measured
        self.rebuilds = 0          # balanced rebuilds triggered by depth
        self.reset(list(sorted_keys))

    # ------------------------------------------------------------------ bulk (re)construction
    def reset(self, sorted_keys: list[int]) -> None:
        """Replace the contents with ``sorted_keys`` (strictly increasing) as a height-balanced tree."""
        self.root = build_balanced(sorted_keys)
        self.size = len(sorted_keys)
        self._measure()

    def adopt(self, root: TreeNode | None, size: int) -> None:
        """Take over an existing tree as-is, e.g. one restored from a checkpoint (shape preserved)."""
        self.root, self.size = root, size
        self._measure()

    def rebuild(self) -> None:
        """Same keys, height-balanced: in-order walk → middle-out build."""
        self.reset(list(self.keys()))
        self.rebuilds += 1

    # ------------------------------------------------------------------ updates
    def add(self, key: int) -> None:
        """Insert a key that is not in the index."""
        self.root = insert_key(self.root, key)
        self.size += 1
        self._rebalance_if_needed()

    def discard(self, key: int) -> None:
        """Delete a key that is in the index."""
        self.root = delete_key(self.root, key)
        self.size -= 1
        self._rebalance_if_needed()

    def _measure(self) -> int:
        self.height = max_depth(self.root)
        self.deepest = max(self.deepest, self.height)
        return self.height

    def _rebalance_if_needed(self) -> None:
        if self._measure() > depth_limit(self.size):
            self.rebuild()

    # ------------------------------------------------------------------ queries
    def __len__(self) -> int:
        return self.size

    def keys(self) -> Iterator[int]:
        """All keys in increasing order, lazily with O(depth) extra space. Don't mutate while iterating."""
        it = DeadlineIterator(self.root)
        while it.has_next():
            yield it.next()

    def first(self) -> int:
        """Smallest key; the index must be non-empty."""
        return kth_earliest(self.root, 1)

    def kth(self, k: int) -> int:
        """k-th smallest key, 1-based."""
        if not 1 <= k <= self.size:
            raise IndexError(f"k={k} outside 1..{self.size}")
        return kth_earliest(self.root, k)

    def rank(self, key: int) -> int:
        """1-based position of ``key`` (which must be in the index): binary search on k-th smallest."""
        lo, hi = 1, self.size
        while lo < hi:
            mid = (lo + hi) // 2
            if kth_earliest(self.root, mid) < key:
                lo = mid + 1
            else:
                hi = mid
        if self.size == 0 or kth_earliest(self.root, lo) != key:
            raise KeyError(key)
        return lo

    def between(self, lo: int, hi: int) -> list[int]:
        """Keys in [lo, hi], increasing.

        The smallest and the largest key in range both exist as nodes; their fork point (lowest common
        ancestor) is the split node of the range, and every key between them lives in its subtree. So
        only that subtree is walked, not the whole index.
        """
        first, last = _ceiling(self.root, lo), _floor(self.root, hi)
        if first is None or last is None or first.val > last.val:
            return []
        split = first if first is last else fork_point(self.root, first, last)
        out = []
        it = DeadlineIterator(split)
        while it.has_next():
            k = it.next()
            if k > last.val:
                break
            if k >= first.val:
                out.append(k)
        return out

    def min_gap(self) -> int | None:
        """Smallest difference between two keys (None with fewer than two keys)."""
        return min_gap(self.root) if self.size >= 2 else None

    def levels(self) -> list[list[int]]:
        """Keys level by level, root first, left to right (debug view)."""
        return level_dump(self.root)

    def check(self) -> list[str]:
        """Audit the index; returns the problems found (empty list = healthy)."""
        problems = []
        if not is_valid_index(self.root):
            problems.append("not a strict binary search tree")
        n = sum(1 for _ in self.keys())
        if n != self.size:
            problems.append(f"size says {self.size} keys, tree has {n}")
        if self._measure() > depth_limit(self.size):
            problems.append(f"depth {self.height} over limit {depth_limit(self.size):.1f}")
        return problems
