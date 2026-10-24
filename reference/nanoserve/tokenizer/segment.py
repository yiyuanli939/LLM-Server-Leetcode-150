"""Reference: tok.segment."""
from __future__ import annotations


# LC 139 Word Break
def can_segment(text: str, vocab: list[str]) -> bool:
    words = set(vocab)
    lengths = sorted({len(w) for w in words})
    n = len(text)
    ok = [False] * (n + 1)
    ok[0] = True
    for i in range(1, n + 1):
        for L in lengths:
            if L > i:
                break
            if ok[i - L] and text[i - L : i] in words:
                ok[i] = True
                break
    return ok[n]
