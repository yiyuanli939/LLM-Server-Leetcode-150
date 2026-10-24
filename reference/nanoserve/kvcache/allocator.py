from __future__ import annotations


# LC 128 Longest Consecutive Sequence
def longest_free_run(ids: list[int]) -> int:
    s = set(ids)
    best = 0
    for v in s:
        if v - 1 not in s:
            end = v
            while end + 1 in s:
                end += 1
            best = max(best, end - v + 1)
    return best


# LC 228 Summary Ranges
def free_ranges(ids: list[int]) -> list[str]:
    out: list[str] = []
    i, n = 0, len(ids)
    while i < n:
        j = i
        while j + 1 < n and ids[j + 1] == ids[j] + 1:
            j += 1
        out.append(str(ids[i]) if i == j else f"{ids[i]}->{ids[j]}")
        i = j + 1
    return out


# LC 34 Find First and Last Position of Element in Sorted Array
def owner_range(owners: list[int], seq_id: int) -> list[int]:
    def lower_bound(x: int) -> int:
        lo, hi = 0, len(owners)
        while lo < hi:
            mid = (lo + hi) // 2
            if owners[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        return lo

    first = lower_bound(seq_id)
    if first == len(owners) or owners[first] != seq_id:
        return [-1, -1]
    return [first, lower_bound(seq_id + 1) - 1]
