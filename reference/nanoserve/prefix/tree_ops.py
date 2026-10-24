from __future__ import annotations

from nanoserve.common.nodes import TreeNode


# LC 236 Lowest Common Ancestor of a Binary Tree
def fork_point(root: TreeNode, p: TreeNode, q: TreeNode) -> TreeNode:
    def dfs(node: TreeNode | None) -> TreeNode | None:
        if node is None or node is p or node is q:
            return node
        left, right = dfs(node.left), dfs(node.right)
        if left is not None and right is not None:
            return node
        return left if left is not None else right

    return dfs(root)


# LC 104 Maximum Depth of Binary Tree
def max_depth(root: TreeNode | None) -> int:
    if root is None:
        return 0
    return 1 + max(max_depth(root.left), max_depth(root.right))
