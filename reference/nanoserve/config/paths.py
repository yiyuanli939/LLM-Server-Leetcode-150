"""Reference: path normalization."""
from __future__ import annotations


# LC 71 Simplify Path
def normalize_path(path: str) -> str:
    stack: list[str] = []
    for part in path.split("/"):
        if part == "" or part == ".":
            continue
        if part == "..":
            if stack:
                stack.pop()
        else:
            stack.append(part)
    return "/" + "/".join(stack)
