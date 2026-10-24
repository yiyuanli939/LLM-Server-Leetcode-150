from __future__ import annotations

from nanoserve.common.nodes import TreeNode


# LC 173 Binary Search Tree Iterator
class DeadlineIterator:
    def __init__(self, root: TreeNode | None) -> None:
        self.stack: list[TreeNode] = []
        self._push_left(root)

    def _push_left(self, node: TreeNode | None) -> None:
        while node is not None:
            self.stack.append(node)
            node = node.left

    def next(self) -> int:
        node = self.stack.pop()
        self._push_left(node.right)
        return node.val

    def has_next(self) -> bool:
        return bool(self.stack)


# LC 230 Kth Smallest Element in a BST
def kth_earliest(root: TreeNode, k: int) -> int:
    stack: list[TreeNode] = []
    node: TreeNode | None = root
    while True:
        while node is not None:
            stack.append(node)
            node = node.left
        node = stack.pop()
        k -= 1
        if k == 0:
            return node.val
        node = node.right


# LC 98 Validate Binary Search Tree
def is_valid_index(root: TreeNode | None) -> bool:
    def ok(node: TreeNode | None, lo: float, hi: float) -> bool:
        if node is None:
            return True
        if not lo < node.val < hi:
            return False
        return ok(node.left, lo, node.val) and ok(node.right, node.val, hi)

    return ok(root, float("-inf"), float("inf"))


# LC 530 Minimum Absolute Difference in BST
def min_gap(root: TreeNode) -> int:
    best = float("inf")
    prev: int | None = None
    stack: list[TreeNode] = []
    node: TreeNode | None = root
    while stack or node is not None:
        while node is not None:
            stack.append(node)
            node = node.left
        node = stack.pop()
        if prev is not None:
            best = min(best, node.val - prev)
        prev = node.val
        node = node.right
    return int(best)


# LC 108 Convert Sorted Array to Binary Search Tree
def build_balanced(sorted_vals: list[int]) -> TreeNode | None:
    def build(lo: int, hi: int) -> TreeNode | None:
        if lo > hi:
            return None
        mid = (lo + hi) // 2
        return TreeNode(sorted_vals[mid], build(lo, mid - 1), build(mid + 1, hi))

    return build(0, len(sorted_vals) - 1)
