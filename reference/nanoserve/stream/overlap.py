"""Reference: stream.stop_overlap."""
from __future__ import annotations


# LC 1392 Longest Happy Prefix
def longest_border(s: str) -> str:
    # KMP prefix function: pi[i] = length of the longest proper border of s[:i + 1].
    pi = [0] * len(s)
    k = 0
    for i in range(1, len(s)):
        while k and s[i] != s[k]:
            k = pi[k - 1]
        if s[i] == s[k]:
            k += 1
        pi[i] = k
    return s[:pi[-1]] if s else ""
