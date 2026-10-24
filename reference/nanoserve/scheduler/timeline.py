from __future__ import annotations


# LC 56 Merge Intervals
def merge_busy(intervals: list[list[int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


# LC 57 Insert Interval
def insert_busy(intervals: list[list[int]], new: list[int]) -> list[list[int]]:
    s, e = new
    out: list[list[int]] = []
    i, n = 0, len(intervals)
    while i < n and intervals[i][1] < s:
        out.append(list(intervals[i]))
        i += 1
    while i < n and intervals[i][0] <= e:
        s = min(s, intervals[i][0])
        e = max(e, intervals[i][1])
        i += 1
    out.append([s, e])
    out.extend(list(iv) for iv in intervals[i:])
    return out
