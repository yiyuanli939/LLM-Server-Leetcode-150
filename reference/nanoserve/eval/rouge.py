from __future__ import annotations


# LC 1143 Longest Common Subsequence
def lcs_length(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    dp = [0] * (len(b) + 1)
    for ca in a:
        prev = 0  # dp[i-1][j-1]
        for j, cb in enumerate(b, 1):
            tmp = dp[j]
            dp[j] = prev + 1 if ca == cb else max(dp[j], dp[j - 1])
            prev = tmp
    return dp[-1]
