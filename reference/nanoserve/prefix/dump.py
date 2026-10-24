from __future__ import annotations

from collections import deque

from nanoserve.common.nodes import TreeNode


def _levels(root: TreeNode | None) -> list[list[int]]:
    if root is None:
        return []
    out, q = [], deque([root])
    while q:
        level = []
        for _ in range(len(q)):
            n = q.popleft()
            level.append(n.val)
            if n.left:
                q.append(n.left)
            if n.right:
                q.append(n.right)
        out.append(level)
    return out


# LC 102 Binary Tree Level Order Traversal
def level_dump(root: TreeNode | None) -> list[list[int]]:
    return _levels(root)


