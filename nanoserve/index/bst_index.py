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

Range queries (``between``) walk down to the range's split node using the key order and then do a
pruned in-order walk: O(depth + answer). Repair (``repair``) handles the opposite situation — the keys
are right but the order is broken (a corrupted checkpoint) — so it cannot trust key comparisons and uses
the general lowest common ancestor to find the smallest damaged subtree.

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


def _split(root: TreeNode | None, lo: int, hi: int) -> TreeNode | None:
    """The highest node whose key lies in [lo, hi] — the "split node" of the range — or None.

    One root-to-leaf walk using the BST order: above the range go left, below it go right. Every key in
    [lo, hi] lives in the split node's subtree, so for two keys a <= b of the tree, ``_split(a, b)`` is
    their lowest common ancestor. O(depth).
    """
    while root is not None and not lo <= root.val <= hi:
        root = root.left if root.val > hi else root.right
    return root


def _inorder_nodes(root: TreeNode | None) -> list[TreeNode]:
    """Nodes in in-order position — structural, no key comparisons (works on a broken BST too)."""
    out, stack = [], []
    while stack or root is not None:
        while root is not None:
            stack.append(root)
            root = root.left
        root = stack.pop()
        out.append(root)
        root = root.right
    return out


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
        """Keys in [lo, hi], increasing, in O(depth + answer).

        Start at the range's split node (``_split``, one walk down) and do an in-order walk that
        prunes every subtree lying entirely outside [lo, hi]: go left only while the node's key is
        > lo, right only while it is < hi. Nodes outside the range are visited only along the two
        boundary paths, so the cost is the depth plus the number of keys returned.
        """
        out: list[int] = []
        stack: list[TreeNode] = []
        node = _split(self.root, lo, hi)
        while stack or node is not None:
            while node is not None:            # descend left, but never into keys < lo
                stack.append(node)
                node = node.left if node.val > lo else None
            node = stack.pop()
            if lo <= node.val <= hi:
                out.append(node.val)
            node = node.right if node.val < hi else None
        return out

    def repair(self) -> int:
        """Restore BST order in place when the keys are right but some sit in the wrong nodes —
        e.g. a checkpoint writer swapped two keys. Returns how many nodes were rewritten (0 = was fine).

        The in-order sequence of a BST is increasing. Take the first and the last place where it
        decreases: the two nodes involved bound the damage, and their lowest common ancestor
        (``fork_point`` — the general binary-tree version, because the tree is *not* a valid BST, so
        a walk guided by the keys would go astray) is the smallest subtree that contains it. Sorting
        that subtree's keys back into its in-order positions repairs it without touching the rest of
        the tree. Repeat until the whole in-order sequence increases (one round for a single swap).
        """
        rewritten = 0
        while True:
            order = _inorder_nodes(self.root)
            bad = [i for i in range(len(order) - 1) if order[i].val >= order[i + 1].val]
            if not bad:
                return rewritten
            lo_node, hi_node = order[bad[0]], order[bad[-1] + 1]
            sub = fork_point(self.root, lo_node, hi_node)
            nodes = _inorder_nodes(sub)
            vals = sorted(n.val for n in nodes)
            if any(vals[i] == vals[i + 1] for i in range(len(vals) - 1)):
                raise ValueError("duplicate keys: the index cannot be repaired by reordering")
            for n, v in zip(nodes, vals):
                if n.val != v:
                    n.val = v
                    rewritten += 1
            self._measure()

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

