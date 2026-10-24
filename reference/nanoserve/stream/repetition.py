"""Reference: stream.unique_run, stream.min_cover, stream.repeat_window."""
from __future__ import annotations



# LC 3 Longest Substring Without Repeating Characters
def longest_unique_run(s: str) -> int:
    last: dict[str, int] = {}
    best = left = 0
    for right, ch in enumerate(s):
        if last.get(ch, -1) >= left:
            left = last[ch] + 1
        last[ch] = right
        best = max(best, right - left + 1)
    return best


# LC 219 Contains Duplicate II
def repeats_within(tokens: list[int], k: int) -> bool:
    if k <= 0:
        return False
    window: set[int] = set()
    for i, tok in enumerate(tokens):
        if tok in window:
            return True
        window.add(tok)
        if len(window) > k:
            window.remove(tokens[i - k])
    return False
