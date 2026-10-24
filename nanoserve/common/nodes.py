"""Node types shared by the engine, the exercises and the tests.

Field names deliberately match the usual LeetCode definitions (val/next/left/right/...), so the
algorithms you write here transfer 1:1. Domain aliases are provided for readability.
"""
from __future__ import annotations

from collections import deque
from typing import Iterable, Optional


class ListNode:
    """A block in a block chain / free list. ``val`` is the block id (or its heat, etc.)."""

    __slots__ = ("val", "next")

    def __init__(self, val: int = 0, next: Optional["ListNode"] = None):
        self.val = val
        self.next = next

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        out, cur, n = [], self, 0
        while cur is not None and n < 20:
            out.append(str(cur.val))
            cur, n = cur.next, n + 1
        return "ListNode(" + " -> ".join(out) + (" -> ..." if cur else "") + ")"


class RandomListNode:
    """A block whose ``random`` points at any block in the same chain (a shared reference) or None."""

    __slots__ = ("val", "next", "random")

    def __init__(self, val: int = 0, next: Optional["RandomListNode"] = None, random: Optional["RandomListNode"] = None):
        self.val = val
        self.next = next
        self.random = random


class TreeNode:
    """Binary tree node used by the prefix-cache views and the deadline index.

    ``next`` is only used by the level-linking exercise; everything else ignores it.
    """

    __slots__ = ("val", "left", "right", "next")

    def __init__(self, val: int = 0, left: Optional["TreeNode"] = None, right: Optional["TreeNode"] = None, next: Optional["TreeNode"] = None):
        self.val = val
        self.left = left
        self.right = right
        self.next = next

    def __repr__(self) -> str:  # pragma: no cover
        return f"TreeNode({self.val})"


class GraphNode:
    """Operator node in the compute graph. ``neighbors`` are undirected edges for cloning."""

    __slots__ = ("val", "neighbors")

    def __init__(self, val: int = 0, neighbors: Optional[list["GraphNode"]] = None):
        self.val = val
        self.neighbors = neighbors if neighbors is not None else []


class QuadNode:
    """Quad-tree node for compressing 0/1 masks."""

    __slots__ = ("val", "isLeaf", "topLeft", "topRight", "bottomLeft", "bottomRight")

    def __init__(self, val: bool = False, isLeaf: bool = False, topLeft=None, topRight=None, bottomLeft=None, bottomRight=None):
        self.val = val
        self.isLeaf = isLeaf
        self.topLeft = topLeft
        self.topRight = topRight
        self.bottomLeft = bottomLeft
        self.bottomRight = bottomRight


# Domain aliases
Block = ListNode
SharedBlock = RandomListNode
CacheNode = TreeNode
OpNode = GraphNode


# ---------------------------------------------------------------------------
# Conversion helpers (used by tests and debugging tools; not exercises)
# ---------------------------------------------------------------------------

def list_to_chain(values: Iterable[int]) -> Optional[ListNode]:
    dummy = ListNode()
    cur = dummy
    for v in values:
        cur.next = ListNode(v)
        cur = cur.next
    return dummy.next


def chain_to_list(head: Optional[ListNode], limit: int = 100_000) -> list[int]:
    out = []
    while head is not None:
        out.append(head.val)
        head = head.next
        if len(out) > limit:
            raise ValueError("chain too long (cycle?)")
    return out


def tree_from_level(values: list[Optional[int]]) -> Optional[TreeNode]:
    """Build a tree from LeetCode-style level order with ``None`` holes, e.g. [3,9,20,None,None,15,7]."""
    if not values or values[0] is None:
        return None
    it = iter(values)
    root = TreeNode(next(it))
    q = deque([root])
    while q:
        node = q.popleft()
        try:
            lv = next(it)
        except StopIteration:
            break
        if lv is not None:
            node.left = TreeNode(lv)
            q.append(node.left)
        try:
            rv = next(it)
        except StopIteration:
            break
        if rv is not None:
            node.right = TreeNode(rv)
            q.append(node.right)
    return root


def tree_to_level(root: Optional[TreeNode]) -> list[Optional[int]]:
    """Inverse of ``tree_from_level`` (trailing ``None`` trimmed)."""
    out: list[Optional[int]] = []
    q = deque([root])
    while q:
        node = q.popleft()
        if node is None:
            out.append(None)
            continue
        out.append(node.val)
        q.append(node.left)
        q.append(node.right)
    while out and out[-1] is None:
        out.pop()
    return out


def find_tree_node(root: Optional[TreeNode], val: int) -> Optional[TreeNode]:
    stack = [root]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        if n.val == val:
            return n
        stack.extend((n.left, n.right))
    return None


def random_chain_from_pairs(pairs: list[list[Optional[int]]]) -> Optional[RandomListNode]:
    """Build from LeetCode format [[val, random_index], ...]."""
    nodes = [RandomListNode(v) for v, _ in pairs]
    for i, (_, r) in enumerate(pairs):
        if i + 1 < len(nodes):
            nodes[i].next = nodes[i + 1]
        nodes[i].random = nodes[r] if r is not None else None
    return nodes[0] if nodes else None


def random_chain_to_pairs(head: Optional[RandomListNode]) -> list[list[Optional[int]]]:
    nodes, idx = [], {}
    cur = head
    while cur is not None:
        idx[id(cur)] = len(nodes)
        nodes.append(cur)
        cur = cur.next
    return [[n.val, idx[id(n.random)] if n.random is not None else None] for n in nodes]


def graph_from_adjacency(adj: list[list[int]]) -> Optional[GraphNode]:
    """Build from LeetCode format: adj[i] lists neighbours of node i+1 (1-based values)."""
    if not adj:
        return None
    nodes = [GraphNode(i + 1) for i in range(len(adj))]
    for i, nbrs in enumerate(adj):
        nodes[i].neighbors = [nodes[j - 1] for j in nbrs]
    return nodes[0]


def graph_to_adjacency(node: Optional[GraphNode]) -> list[list[int]]:
    if node is None:
        return []
    seen = {node.val: node}
    q = deque([node])
    while q:
        n = q.popleft()
        for m in n.neighbors:
            if m.val not in seen:
                seen[m.val] = m
                q.append(m)
    return [[m.val for m in seen[v].neighbors] for v in sorted(seen)]


def graph_nodes(node: Optional[GraphNode]) -> list[GraphNode]:
    if node is None:
        return []
    seen = {id(node): node}
    q = deque([node])
    while q:
        n = q.popleft()
        for m in n.neighbors:
            if id(m) not in seen:
                seen[id(m)] = m
                q.append(m)
    return list(seen.values())


def quad_to_list(root: Optional[QuadNode]) -> list[Optional[list[int]]]:
    """LeetCode serialization of a quad tree: level order of [isLeaf, val], None for missing children."""
    out: list[Optional[list[int]]] = []
    q = deque([root])
    while q:
        n = q.popleft()
        if n is None:
            out.append(None)
            continue
        out.append([int(bool(n.isLeaf)), int(bool(n.val))])
        if n.isLeaf:
            q.extend([None, None, None, None])
        else:
            q.extend([n.topLeft, n.topRight, n.bottomLeft, n.bottomRight])
    while out and out[-1] is None:
        out.pop()
    return out
