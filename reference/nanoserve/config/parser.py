"""Reference: bracket pre-check."""
from __future__ import annotations


# LC 20 Valid Parentheses
def brackets_balanced(s: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for ch in s:
        if ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
        elif ch in "([{":
            stack.append(ch)
        # every other character is ignored
    return not stack
