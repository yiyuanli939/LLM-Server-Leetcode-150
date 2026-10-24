from __future__ import annotations


# LC 191 Number of 1 Bits
def popcount(n: int) -> int:
    count = 0
    while n:
        n &= n - 1
        count += 1
    return count


