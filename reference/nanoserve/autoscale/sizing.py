from __future__ import annotations


# LC 1011 Capacity To Ship Packages Within D Days
def min_throughput(work: list[int], days: int) -> int:
    def periods_needed(cap: int) -> int:
        used, load = 1, 0
        for w in work:
            if load + w > cap:
                used += 1
                load = 0
            load += w
        return used

    lo, hi = max(work), sum(work)
    while lo < hi:
        mid = (lo + hi) // 2
        if periods_needed(mid) <= days:
            hi = mid
        else:
            lo = mid + 1
    return lo


# LC 875 Koko Eating Bananas
def min_drain_rate(queues: list[int], hours: int) -> int:
    lo, hi = 1, max(queues)
    while lo < hi:
        mid = (lo + hi) // 2
        if sum((q + mid - 1) // mid for q in queues) <= hours:
            hi = mid
        else:
            lo = mid + 1
    return lo


# LC 2187 Minimum Time to Complete Trips
def min_time_for(per_request_time: list[int], total: int) -> int:
    lo, hi = 1, min(per_request_time) * total
    while lo < hi:
        mid = (lo + hi) // 2
        if sum(mid // t for t in per_request_time) >= total:
            hi = mid
        else:
            lo = mid + 1
    return lo
