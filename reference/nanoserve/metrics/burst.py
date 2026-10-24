from __future__ import annotations


# LC 53 Maximum Subarray (Kadane)
def max_burst(deltas: list[int]) -> int:
    best = cur = deltas[0]
    for x in deltas[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return best


# LC 918 Maximum Sum Circular Subarray
def max_burst_circular(deltas: list[int]) -> int:
    total = 0
    cur_max = cur_min = 0
    best_max = best_min = deltas[0]
    for x in deltas:
        cur_max = max(x, cur_max + x)
        best_max = max(best_max, cur_max)
        cur_min = min(x, cur_min + x)
        best_min = min(best_min, cur_min)
        total += x
    if best_max < 0:  # all negative: wrap-around would select an empty segment
        return best_max
    return max(best_max, total - best_min)
