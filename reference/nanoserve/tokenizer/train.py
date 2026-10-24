"""Reference: tok.top_pieces."""
from __future__ import annotations

from collections import Counter


# LC 347 Top K Frequent Elements
def top_k_pieces(pieces: list[str], k: int) -> list[str]:
    counts = Counter(pieces)
    buckets: list[list[str]] = [[] for _ in range(len(pieces) + 1)]
    for piece, c in counts.items():
        buckets[c].append(piece)
    out: list[str] = []
    for c in range(len(buckets) - 1, 0, -1):
        for piece in buckets[c]:
            out.append(piece)
            if len(out) == k:
                return out
    return out
