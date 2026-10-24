from __future__ import annotations

from collections import deque
from typing import Optional

from nanoserve.common.nodes import TreeNode


# LC 297 Serialize and Deserialize Binary Tree (iterative BFS, no recursion limits)
class TreeCodec:
    def serialize(self, root: Optional[TreeNode]) -> str:
        out: list[str] = []
        q = deque([root])
        while q:
            node = q.popleft()
            if node is None:
                out.append("#")
                continue
            out.append(str(node.val))
            q.append(node.left)
            q.append(node.right)
        return ",".join(out)

    def deserialize(self, data: str) -> Optional[TreeNode]:
        tokens = data.split(",")
        if not tokens or tokens[0] == "#":
            return None
        root = TreeNode(int(tokens[0]))
        q = deque([root])
        i = 1
        while q:
            node = q.popleft()
            if tokens[i] != "#":
                node.left = TreeNode(int(tokens[i]))
                q.append(node.left)
            if tokens[i + 1] != "#":
                node.right = TreeNode(int(tokens[i + 1]))
                q.append(node.right)
            i += 2
        return root
