from __future__ import annotations


# LC 169 Majority Element (Boyer-Moore voting). Without a majority the candidate is still an element.
def dominant_tenant(requests: list[int] | list[str]) -> int | str:
    candidate = requests[0]
    count = 0
    for r in requests:
        if count == 0:
            candidate = r
        count += 1 if r == candidate else -1
    return candidate
