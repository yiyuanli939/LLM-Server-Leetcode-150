from __future__ import annotations


# LC 392 Is Subsequence
def fuzzy_match(query: str, text: str) -> bool:
    i = 0
    for c in text:
        if i < len(query) and query[i] == c:
            i += 1
    return i == len(query)
