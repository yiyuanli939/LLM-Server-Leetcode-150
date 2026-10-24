"""Reference: sched.cooldown."""
from __future__ import annotations

from collections import Counter


# LC 621 Task Scheduler
def min_slots_with_cooldown(adapters: list[str], n: int) -> int:
    counts = Counter(adapters)
    top = max(counts.values())
    n_top = sum(1 for c in counts.values() if c == top)
    return max(len(adapters), (top - 1) * (n + 1) + n_top)
