from __future__ import annotations

from nanoserve.common.nodes import TreeNode


# LC 100 Same Tree
def same_tree(a: TreeNode | None, b: TreeNode | None) -> bool:
    if a is None or b is None:
        return a is b
    return a.val == b.val and same_tree(a.left, b.left) and same_tree(a.right, b.right)


