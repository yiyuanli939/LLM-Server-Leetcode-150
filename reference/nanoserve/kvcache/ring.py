from __future__ import annotations


def _reverse(buf: list[int], i: int, j: int) -> None:
    while i < j:
        buf[i], buf[j] = buf[j], buf[i]
        i += 1
        j -= 1


# LC 189 Rotate Array
def rotate_right(buf: list[int], k: int) -> None:
    n = len(buf)
    k %= n
    _reverse(buf, 0, n - 1)
    _reverse(buf, 0, k - 1)
    _reverse(buf, k, n - 1)


# LC 33 Search in Rotated Sorted Array
def ring_search(buf: list[int], target: int) -> int:
    lo, hi = 0, len(buf) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if buf[mid] == target:
            return mid
        if buf[lo] <= buf[mid]:
            if buf[lo] <= target < buf[mid]:
                hi = mid - 1
            else:
                lo = mid + 1
        else:
            if buf[mid] < target <= buf[hi]:
                lo = mid + 1
            else:
                hi = mid - 1
    return -1


# LC 153 Find Minimum in Rotated Sorted Array
def ring_min(buf: list[int]) -> int:
    lo, hi = 0, len(buf) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if buf[mid] > buf[hi]:
            lo = mid + 1
        else:
            hi = mid
    return buf[lo]
