"""Framework: post-run analytics of a server report (M2).

    report = server.run()
    stats = analyze(report, window=5)                # rolling latency, hot tenant, queue bursts
    stats = analyze(report, window=5, period=40)     # + wrap-around burst of a periodic (daily) trace

What it computes:

  * rolling latency over finish order — max and p50 of every ``window`` consecutive finished requests
    (metrics.window_max, metrics.window_median): a latency spike shows up as a plateau in the max.
  * hot tenant — a tenant sending more than half of all requests is a candidate for rate limiting.
    ``dominant_tenant`` returns the only possible candidate in O(1) extra space; one counting pass
    confirms it (metrics.dominant). No majority → ``None``.
  * queue bursts — the waiting queue's per-tick change; the largest growth over any stretch of
    consecutive ticks (metrics.max_burst). For a periodic trace, the same over one period with
    wrap-around, so a burst that straddles midnight counts in full (metrics.max_burst_circular).

``periodic_trace`` builds the periodic traces this is meant for (one day of traffic, repeated).

Exercises this file calls (M2): metrics.window_max, metrics.window_median, metrics.dominant,
metrics.max_burst, metrics.max_burst_circular.
"""
from __future__ import annotations

import copy
from typing import Sequence

from nanoserve.metrics.burst import max_burst, max_burst_circular
from nanoserve.metrics.tenants import dominant_tenant
from nanoserve.metrics.window import window_max, window_median
from nanoserve.server.request import Request
from nanoserve.server.server import ServerReport


def finish_order(report: ServerReport) -> list[Request]:
    """Finished requests in the order they completed (same tick: by batch slot)."""
    return sorted(report.finished, key=lambda r: (r.finished_at, r.slot or 0, r.rid))


def queue_deltas(queue_len: Sequence[int]) -> list[int]:
    """Per-tick change of the waiting queue (the queue is empty before tick 0)."""
    prev, out = 0, []
    for q in queue_len:
        out.append(q - prev)
        prev = q
    return out


def hot_tenant(tenants: Sequence[str]) -> tuple[str | None, float]:
    """(tenant with > 50 % of the requests or None, share of the candidate)."""
    if not tenants:
        return None, 0.0
    cand = dominant_tenant(list(tenants))
    share = sum(1 for t in tenants if t == cand) / len(tenants)  # verification pass, O(1) extra space
    return (cand if share > 0.5 else None), share


def period_slice(deltas: Sequence[int], period: int) -> tuple[int, list[int]]:
    """One full period of the per-tick deltas: the second period when the run has one (the first starts
    from an empty queue, i.e. it is warm-up), else the first. Returns (start tick, deltas)."""
    if period < 1:
        raise ValueError("period must be >= 1")
    start = period if len(deltas) >= 2 * period else 0
    return start, list(deltas[start:start + period])


def analyze(report: ServerReport, *, window: int = 5, period: int | None = None) -> dict:
    fin = finish_order(report)
    lat = [r.latency for r in fin]
    out: dict = {"finished": len(fin), "window": None, "rolling_max": [], "rolling_p50": [],
                 "worst_window": None}
    if lat:
        k = max(1, min(window, len(lat)))
        out["window"] = k
        out["rolling_max"] = window_max(lat, k)
        out["rolling_p50"] = window_median(lat, k)
        worst = max(range(len(out["rolling_p50"])), key=lambda i: (out["rolling_p50"][i], -i))
        out["worst_window"] = (fin[worst].rid, fin[worst + k - 1].rid)  # first / last request of that window

    tenant, share = hot_tenant([r.tenant for r in report.requests])
    out["hot_tenant"], out["hot_share"] = tenant, share

    deltas = queue_deltas(report.queue_len)
    out["queue_burst"] = max_burst(deltas) if deltas else 0
    if period is not None and deltas:
        start, one = period_slice(deltas, period)
        out["period_start"] = start
        out["period_burst"] = max_burst(one)
        out["period_burst_wrap"] = max_burst_circular(one)
    return out


def lines(stats: dict) -> list[str]:
    """Compact human-readable rendering of ``analyze``'s result."""
    out = []
    if stats["window"]:
        rm, rp = stats["rolling_max"], stats["rolling_p50"]
        first, last = stats["worst_window"]
        out.append(f"rolling latency (window {stats['window']} finishes): max {min(rm)}..{max(rm)}, "
                   f"p50 {min(rp):g}..{max(rp):g}; worst p50 window {first}..{last}")
    hot = stats["hot_tenant"]
    out.append(f"hot tenant: {hot!r} ({stats['hot_share']:.0%} of requests)" if hot is not None
               else "hot tenant: none (no tenant sends more than half of the requests)")
    out.append(f"largest queue burst: +{stats['queue_burst']} waiting requests")
    if "period_burst" in stats:
        out.append(f"one period from tick {stats['period_start']}: burst +{stats['period_burst']}, "
                   f"with wrap-around +{stats['period_burst_wrap']}")
    return out


def periodic_trace(day: Sequence[Request], period: int, repeats: int) -> list[Request]:
    """Repeat one period of traffic ``repeats`` times. Arrivals of ``day`` must lie in [0, period)."""
    if any(not 0 <= r.arrival < period for r in day):
        raise ValueError("every arrival of one period must lie in [0, period)")
    out = []
    for k in range(repeats):
        for r in day:
            c = copy.copy(r)
            c.chunks = []
            c.rid, c.arrival, c.seed = f"d{k}-{r.rid}", r.arrival + k * period, r.seed + 7919 * k
            out.append(c)
    return out
