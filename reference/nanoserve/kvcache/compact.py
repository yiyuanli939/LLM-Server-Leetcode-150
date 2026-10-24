from __future__ import annotations


# LC 27 Remove Element
def remove_freed(slots: list[int], freed: int) -> int:
    k = 0
    for v in slots:
        if v != freed:
            slots[k] = v
            k += 1
    return k


# LC 26 Remove Duplicates from Sorted Array
def dedupe_sorted(ids: list[int]) -> int:
    k = 0
    for v in ids:
        if k == 0 or ids[k - 1] != v:
            ids[k] = v
            k += 1
    return k


# LC 88 Merge Sorted Array
def merge_into(a: list[int], m: int, b: list[int], n: int) -> None:
    i, j, w = m - 1, n - 1, m + n - 1
    while j >= 0:
        if i >= 0 and a[i] > b[j]:
            a[w] = a[i]
            i -= 1
        else:
            a[w] = b[j]
            j -= 1
        w -= 1
