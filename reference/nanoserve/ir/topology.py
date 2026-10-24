from __future__ import annotations


# LC 547 Number of Provinces
def count_device_groups(linked: list[list[int]]) -> int:
    n = len(linked)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    groups = n
    for i in range(n):
        for j in range(i + 1, n):
            if linked[i][j]:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
                    groups -= 1
    return groups
