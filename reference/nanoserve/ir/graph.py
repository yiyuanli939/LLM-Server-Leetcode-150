"""Reference: IR graph analysis."""
from __future__ import annotations

from collections import deque

from nanoserve.common.nodes import GraphNode


def _kahn(n: int, deps: list[list[int]]) -> list[int]:
    adj: list[list[int]] = [[] for _ in range(n)]
    indeg = [0] * n
    for a, b in deps:
        adj[b].append(a)
        indeg[a] += 1
    q = deque(i for i in range(n) if indeg[i] == 0)
    order: list[int] = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return order


# LC 207 Course Schedule
def can_schedule(n: int, deps: list[list[int]]) -> bool:
    return len(_kahn(n, deps)) == n


# LC 210 Course Schedule II
def topo_order(n: int, deps: list[list[int]]) -> list[int]:
    order = _kahn(n, deps)
    return order if len(order) == n else []


# LC 133 Clone Graph
def clone_graph(node: GraphNode | None) -> GraphNode | None:
    if node is None:
        return None
    copies = {node: GraphNode(node.val)}
    q = deque([node])
    while q:
        cur = q.popleft()
        for nb in cur.neighbors:
            if nb not in copies:
                copies[nb] = GraphNode(nb.val)
                q.append(nb)
            copies[cur].neighbors.append(copies[nb])
    return copies[node]
