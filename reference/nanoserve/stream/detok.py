"""Reference: stream.holdback."""
from __future__ import annotations


# LC 58 Length of Last Word
def trailing_word_len(s: str) -> int:
    i = len(s) - 1
    while i >= 0 and s[i] == " ":
        i -= 1
    end = i
    while i >= 0 and s[i] != " ":
        i -= 1
    return end - i
