"""Reference: tok.common_prefix."""
from __future__ import annotations


# LC 14 Longest Common Prefix
def common_prefix(prompts: list[str]) -> str:
    if not prompts:
        return ""
    shortest = min(prompts, key=len)
    for i, ch in enumerate(shortest):
        for p in prompts:
            if p[i] != ch:
                return shortest[:i]
    return shortest
