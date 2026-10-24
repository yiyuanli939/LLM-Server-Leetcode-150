"""Reference: stream.justify, stream.reverse_words."""
from __future__ import annotations


# LC 68 Text Justification
def justify(words: list[str], width: int) -> list[str]:
    lines: list[str] = []
    i, n = 0, len(words)
    while i < n:
        j, length = i + 1, len(words[i])
        while j < n and length + 1 + len(words[j]) <= width:
            length += 1 + len(words[j])
            j += 1
        line_words = words[i:j]
        gaps = j - i - 1
        if j == n or gaps == 0:
            line = " ".join(line_words)
            lines.append(line + " " * (width - len(line)))
        else:
            spaces = width - sum(len(w) for w in line_words)
            base, extra = divmod(spaces, gaps)
            parts: list[str] = []
            for g, word in enumerate(line_words[:-1]):
                parts.append(word + " " * (base + (1 if g < extra else 0)))
            parts.append(line_words[-1])
            lines.append("".join(parts))
        i = j
    return lines


