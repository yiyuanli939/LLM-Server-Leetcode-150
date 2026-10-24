from __future__ import annotations

from collections import defaultdict, deque


# LC 1462 Course Schedule IV
def depends_queries(n: int, deps: list[list[int]], queries: list[list[int]]) -> list[bool]:
    succ: list[list[int]] = [[] for _ in range(n)]
    indeg = [0] * n
    for a, b in deps:
        succ[a].append(b)
        indeg[b] += 1
    # before[v] is a bitmask of every operator that must run before v.
    before = [0] * n
    q = deque(i for i in range(n) if indeg[i] == 0)
    while q:
        u = q.popleft()
        for v in succ[u]:
            before[v] |= before[u] | (1 << u)
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return [bool(before[v] >> u & 1) for u, v in queries]


# LC 2115 Find All Possible Recipes from Given Supplies
def computable_outputs(outputs: list[str], inputs: list[list[str]], provided: list[str]) -> list[str]:
    users: dict[str, list[int]] = defaultdict(list)
    missing = [len(ins) for ins in inputs]
    for i, ins in enumerate(inputs):
        for name in ins:
            users[name].append(i)
    ready = deque(provided)
    result: list[str] = []
    while ready:
        name = ready.popleft()
        for i in users.get(name, ()):
            missing[i] -= 1
            if missing[i] == 0:
                result.append(outputs[i])
                ready.append(outputs[i])
    return result
