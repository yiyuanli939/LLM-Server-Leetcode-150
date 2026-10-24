from __future__ import annotations

from nanoserve.common.nodes import TreeNode


# LC 701 Insert into a Binary Search Tree
def insert_key(root: TreeNode | None, val: int) -> TreeNode:
    node = TreeNode(val)
    if root is None:
        return node
    cur = root
    while True:
        if val < cur.val:
            if cur.left is None:
                cur.left = node
                return root
            cur = cur.left
        else:
            if cur.right is None:
                cur.right = node
                return root
            cur = cur.right


# LC 450 Delete Node in a BST
def delete_key(root: TreeNode | None, key: int) -> TreeNode | None:
    parent: TreeNode | None = None
    node = root
    while node is not None and node.val != key:
        parent, node = node, (node.left if key < node.val else node.right)
    if node is None:
        return root

    if node.left is None or node.right is None:
        replacement = node.left if node.left is not None else node.right
    else:
        # Splice in the in-order successor (leftmost node of the right subtree).
        succ_parent, succ = node, node.right
        while succ.left is not None:
            succ_parent, succ = succ, succ.left
        if succ_parent is not node:
            succ_parent.left = succ.right
            succ.right = node.right
        succ.left = node.left
        replacement = succ

    if parent is None:
        return replacement
    if parent.left is node:
        parent.left = replacement
    else:
        parent.right = replacement
    return root


# LC 1008 Construct Binary Search Tree from Preorder Traversal
def bst_from_preorder(preorder: list[int]) -> TreeNode | None:
    if not preorder:
        return None
    root = TreeNode(preorder[0])
    stack = [root]  # path of nodes that may still receive a right child, values decreasing
    for v in preorder[1:]:
        node = TreeNode(v)
        if v < stack[-1].val:
            stack[-1].left = node
        else:
            parent = stack.pop()
            while stack and stack[-1].val < v:
                parent = stack.pop()
            parent.right = node
        stack.append(node)
    return root
