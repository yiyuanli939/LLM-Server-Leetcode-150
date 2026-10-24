"""Reference: interleaved stream validation."""
from __future__ import annotations


# LC 97 Interleaving String
def is_interleaving(a: str, b: str, merged: str) -> bool:
    m, n = len(a), len(b)
    if m + n != len(merged):
        return False
    dp = [False] * (n + 1)
    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0 and j == 0:
                dp[j] = True
                continue
            k = i + j - 1
            from_a = i > 0 and dp[j] and a[i - 1] == merged[k]
            from_b = j > 0 and dp[j - 1] and b[j - 1] == merged[k]
            dp[j] = from_a or from_b
    return dp[n]
