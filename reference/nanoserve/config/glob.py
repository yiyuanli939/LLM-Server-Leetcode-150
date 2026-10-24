from __future__ import annotations


# LC 44 Wildcard Matching
def glob_match(s: str, p: str) -> bool:
    i = j = 0
    star = -1  # index in p of the last '*' seen
    mark = 0  # index in s where that '*' currently stops matching
    while i < len(s):
        if j < len(p) and (p[j] == "?" or p[j] == s[i]):
            i += 1
            j += 1
        elif j < len(p) and p[j] == "*":
            star, mark = j, i
            j += 1
        elif star != -1:
            # Let the last '*' swallow one more character and retry.
            mark += 1
            i, j = mark, star + 1
        else:
            return False
    while j < len(p) and p[j] == "*":
        j += 1
    return j == len(p)
