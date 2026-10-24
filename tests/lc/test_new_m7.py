"""M7 exercises: dashboard fuzzy filter, latency/series/utilization metrics, capacity sizing."""
import bisect
import contextlib
import itertools
import random
import signal
import threading

import pytest

from nanoserve.autoscale.sizing import min_drain_rate, min_throughput, min_time_for
from nanoserve.dashboard.filter import fuzzy_match
from nanoserve.metrics.busy import BusyTimeCounter
from nanoserve.metrics.series import CorrectableSeries
from nanoserve.metrics.slowest import KthSlowest


# ---------------------------------------------------------------- helpers

@contextlib.contextmanager
def _time_limit(seconds):
    """Fail (instead of hanging) when the code under test is asymptotically too slow.

    Uses SIGALRM where available (POSIX main thread); elsewhere it is a no-op.
    """
    if not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread():
        yield
        return

    def on_alarm(signum, frame):
        pytest.fail(f"took longer than {seconds}s: the required complexity is not met", pytrace=False)

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


# ---------------------------------------------------------------- dash.fuzzy

def _fuzzy_oracle(query, text):
    """Brute force: does any choice of len(query) positions in text spell query?"""
    return any(all(text[i] == c for i, c in zip(pos, query)) for pos in itertools.combinations(range(len(text)), len(query)))


@pytest.mark.exercise("dash.fuzzy")
def test_dash_fuzzy_examples():
    assert fuzzy_match("abc", "ahbgdc") is True
    assert fuzzy_match("axc", "ahbgdc") is False


@pytest.mark.exercise("dash.fuzzy")
def test_dash_fuzzy_model_names():
    assert fuzzy_match("lm3", "llama-3-8b") is True
    assert fuzzy_match("q7i", "qwen2-7b-instruct") is True
    assert fuzzy_match("8b3", "llama-3-8b") is False  # order matters
    assert fuzzy_match("llama-3-8b", "llama-3-8b") is True
    assert fuzzy_match("llama-3-8b!", "llama-3-8b") is False


@pytest.mark.exercise("dash.fuzzy")
def test_dash_fuzzy_empty():
    assert fuzzy_match("", "ahbgdc") is True
    assert fuzzy_match("", "") is True
    assert fuzzy_match("a", "") is False


@pytest.mark.exercise("dash.fuzzy")
def test_dash_fuzzy_repeats_and_case():
    assert fuzzy_match("aa", "a") is False
    assert fuzzy_match("aa", "bab") is False
    assert fuzzy_match("aa", "baba") is True
    assert fuzzy_match("aaa", "aabaa") is True
    assert fuzzy_match("A", "a") is False
    assert fuzzy_match("Ab", "aAb") is True


@pytest.mark.exercise("dash.fuzzy")
def test_dash_fuzzy_random():
    rng = random.Random(71)
    for _ in range(1500):
        text = "".join(rng.choice("abc") for _ in range(rng.randint(0, 9)))
        query = "".join(rng.choice("abc") for _ in range(rng.randint(0, 5)))
        assert fuzzy_match(query, text) is _fuzzy_oracle(query, text), (query, text)


@pytest.mark.exercise("dash.fuzzy")
def test_dash_fuzzy_large_linear():
    text = "ab" * 100_000
    with _time_limit(3):
        assert fuzzy_match("ba" * 99_999, text) is True
        assert fuzzy_match("a" * 100_000, text) is True
        assert fuzzy_match("a" * 100_001, text) is False
        assert fuzzy_match("b" * 100_000 + "a", text) is False


# ---------------------------------------------------------------- metrics.slowest_k

@pytest.mark.exercise("metrics.slowest_k")
def test_metrics_slowest_k_example():
    s = KthSlowest(3, [4, 5, 8, 2])
    assert [s.add(x) for x in [3, 5, 10, 9, 4]] == [4, 5, 5, 8, 8]


@pytest.mark.exercise("metrics.slowest_k")
def test_metrics_slowest_k_duplicates():
    s = KthSlowest(4, [7, 7, 7, 7, 8, 3])
    assert [s.add(x) for x in [2, 10, 9, 9]] == [7, 7, 7, 8]


@pytest.mark.exercise("metrics.slowest_k")
def test_metrics_slowest_k_initial_short():
    s = KthSlowest(1, [])
    assert [s.add(x) for x in [-3, -2, -4, 0, 4]] == [-3, -2, -2, 0, 4]
    s = KthSlowest(2, [0])
    assert [s.add(x) for x in [-1, 1, -2, -4, 3]] == [-1, 0, 0, 0, 1]


@pytest.mark.exercise("metrics.slowest_k")
def test_metrics_slowest_k_k_equals_count_and_independent():
    a = KthSlowest(3, [5, 1])
    b = KthSlowest(1, [5, 1])
    assert a.add(3) == 1  # exactly k values: the k-th largest is the minimum
    assert b.add(3) == 5
    assert a.add(0) == 1
    assert a.add(100) == 3
    assert b.add(6) == 6


@pytest.mark.exercise("metrics.slowest_k")
def test_metrics_slowest_k_random():
    rng = random.Random(72)
    for _ in range(150):
        k = rng.randint(1, 12)
        initial = [rng.randint(-50, 50) for _ in range(rng.randint(k - 1, k + 15))]
        s = KthSlowest(k, list(initial))
        seen = list(initial)
        for _ in range(rng.randint(1, 40)):
            x = rng.randint(-60, 60)
            seen.append(x)
            assert s.add(x) == sorted(seen, reverse=True)[k - 1]


@pytest.mark.exercise("metrics.slowest_k")
def test_metrics_slowest_k_large():
    rng = random.Random(73)
    k = 1000
    initial = [rng.randint(0, 10**9) for _ in range(20_000)]
    stream = [rng.randint(0, 10**9) for _ in range(20_000)]
    with _time_limit(3):
        s = KthSlowest(k, initial)
        got = [s.add(x) for x in stream]
    seen = sorted(initial)
    for i, x in enumerate(stream):
        bisect.insort(seen, x)
        if i % 997 == 0 or i == len(stream) - 1:
            assert got[i] == seen[-k]


# ---------------------------------------------------------------- metrics.corrected

def _run_series(ops):
    """ops: ("u", ts, v) | ("c",) | ("max",) | ("min",). Returns the list of query results."""
    s = CorrectableSeries()
    out = []
    for op in ops:
        if op[0] == "u":
            assert s.update(op[1], op[2]) is None
        elif op[0] == "c":
            out.append(s.current())
        elif op[0] == "max":
            out.append(s.maximum())
        else:
            out.append(s.minimum())
    return out


def _series_model(ops):
    at, out = {}, []
    for op in ops:
        if op[0] == "u":
            at[op[1]] = op[2]
        elif op[0] == "c":
            out.append(at[max(at)])
        elif op[0] == "max":
            out.append(max(at.values()))
        else:
            out.append(min(at.values()))
    return out


@pytest.mark.exercise("metrics.corrected")
def test_metrics_corrected_example():
    ops = [("u", 1, 10), ("u", 2, 5), ("c",), ("max",), ("u", 1, 3), ("max",), ("u", 4, 2), ("min",)]
    assert _run_series(ops) == [5, 10, 5, 2]


@pytest.mark.exercise("metrics.corrected")
def test_metrics_corrected_single_point():
    s = CorrectableSeries()
    s.update(7, 42)
    assert (s.current(), s.maximum(), s.minimum()) == (42, 42, 42)
    s.update(7, 1)
    assert (s.current(), s.maximum(), s.minimum()) == (1, 1, 1)
    s.update(7, 10**9)
    assert (s.current(), s.maximum(), s.minimum()) == (10**9, 10**9, 10**9)


@pytest.mark.exercise("metrics.corrected")
def test_metrics_corrected_out_of_order():
    ops = [
        ("u", 10, 4), ("c",),
        ("u", 3, 9), ("c",), ("max",),   # older point arrives late: current is still ts=10
        ("u", 12, 6), ("c",),
        ("u", 10, 1), ("c",), ("min",),  # correcting a non-latest point
        ("u", 12, 2), ("c",), ("max",), ("min",),
    ]
    assert _run_series(ops) == [4, 4, 9, 6, 6, 1, 2, 9, 1]


@pytest.mark.exercise("metrics.corrected")
def test_metrics_corrected_stale_extremes_disappear():
    s = CorrectableSeries()
    for ts, v in [(1, 100), (2, 1), (3, 50)]:
        s.update(ts, v)
    assert (s.maximum(), s.minimum()) == (100, 1)
    s.update(1, 40)
    s.update(2, 60)
    assert (s.maximum(), s.minimum(), s.current()) == (60, 40, 50)
    s.update(2, 1)
    s.update(2, 60)  # value goes back and forth
    assert (s.maximum(), s.minimum()) == (60, 40)
    s.update(1, 60)
    s.update(3, 60)
    assert (s.maximum(), s.minimum(), s.current()) == (60, 60, 60)


@pytest.mark.exercise("metrics.corrected")
def test_metrics_corrected_independent_instances():
    a, b = CorrectableSeries(), CorrectableSeries()
    a.update(1, 5)
    b.update(2, 7)
    assert (a.current(), a.maximum(), b.current(), b.minimum()) == (5, 5, 7, 7)


@pytest.mark.exercise("metrics.corrected")
def test_metrics_corrected_random():
    rng = random.Random(74)
    for _ in range(200):
        ops = []
        for _ in range(rng.randint(1, 60)):
            if not ops or rng.random() < 0.5:
                ops.append(("u", rng.randint(1, 15), rng.randint(1, 30)))
            else:
                ops.append((rng.choice(["c", "max", "min"]),))
        assert _run_series(ops) == _series_model(ops)


@pytest.mark.exercise("metrics.corrected")
def test_metrics_corrected_large():
    rng = random.Random(75)
    n = 60_000
    updates = []
    for i in range(n):
        if i and rng.random() < 0.3:
            updates.append((rng.choice(updates)[0], rng.randint(1, 10**9)))  # correction
        else:
            updates.append((rng.randint(1, 10**9), rng.randint(1, 10**9)))
    checkpoints = set(rng.sample(range(n), 25)) | {n - 1}
    got = {}
    with _time_limit(3):
        s = CorrectableSeries()
        for i, (ts, v) in enumerate(updates):
            s.update(ts, v)
            hi, lo, cur = s.maximum(), s.minimum(), s.current()
            if i in checkpoints:
                got[i] = (cur, hi, lo)
    at = {}
    for i, (ts, v) in enumerate(updates):
        at[ts] = v
        if i in checkpoints:
            assert got[i] == (at[max(at)], max(at.values()), min(at.values()))



@pytest.mark.exercise("metrics.corrected")
def test_metrics_corrected_zero_ts_and_value():
    s = CorrectableSeries()
    s.update(0, 5)
    assert (s.current(), s.maximum(), s.minimum()) == (5, 5, 5)
    s.update(1, 0)
    assert (s.current(), s.maximum(), s.minimum()) == (0, 5, 0)
    s.update(0, 0)  # correction of tick 0 down to zero
    assert (s.current(), s.maximum(), s.minimum()) == (0, 0, 0)
    s.update(1, 7)
    assert (s.current(), s.maximum(), s.minimum()) == (7, 7, 0)


@pytest.mark.exercise("metrics.corrected")
def test_metrics_corrected_random_with_zero():
    rng = random.Random(79)
    for _ in range(200):
        ops = []
        for _ in range(rng.randint(1, 50)):
            if not ops or rng.random() < 0.5:
                ops.append(("u", rng.randint(0, 8), rng.randint(0, 6)))
            else:
                ops.append((rng.choice(["c", "max", "min"]),))
        assert _run_series(ops) == _series_model(ops)


# ---------------------------------------------------------------- metrics.busy_time

def _union_size(intervals):
    total, cur_l, cur_r = 0, None, None
    for l, r in sorted(intervals):
        if cur_r is None or l > cur_r:
            if cur_r is not None:
                total += cur_r - cur_l + 1
            cur_l, cur_r = l, r
        else:
            cur_r = max(cur_r, r)
    if cur_r is not None:
        total += cur_r - cur_l + 1
    return total


@pytest.mark.exercise("metrics.busy_time")
def test_metrics_busy_time_example():
    c = BusyTimeCounter()
    assert c.add(2, 3) is None
    assert c.add(7, 10) is None
    assert c.count() == 6
    c.add(5, 8)
    assert c.count() == 8


@pytest.mark.exercise("metrics.busy_time")
def test_metrics_busy_time_empty_and_single_point():
    c = BusyTimeCounter()
    assert c.count() == 0
    c.add(5, 5)
    assert c.count() == 1
    c.add(5, 5)
    assert c.count() == 1


@pytest.mark.exercise("metrics.busy_time")
def test_metrics_busy_time_overlap_shapes():
    c = BusyTimeCounter()
    c.add(10, 20)
    c.add(12, 15)  # contained
    assert c.count() == 11
    c.add(21, 22)  # adjacent on the right
    assert c.count() == 13
    c.add(8, 9)  # adjacent on the left
    assert c.count() == 15
    c.add(1, 3)
    c.add(30, 40)
    assert c.count() == 3 + 15 + 11
    c.add(2, 35)  # swallows / bridges everything
    assert c.count() == 40
    c.add(1, 40)
    assert c.count() == 40


@pytest.mark.exercise("metrics.busy_time")
def test_metrics_busy_time_independent_instances():
    a, b = BusyTimeCounter(), BusyTimeCounter()
    a.add(1, 10)
    assert b.count() == 0
    b.add(3, 4)
    assert (a.count(), b.count()) == (10, 2)


@pytest.mark.exercise("metrics.busy_time")
def test_metrics_busy_time_random():
    rng = random.Random(76)
    for _ in range(200):
        c = BusyTimeCounter()
        covered = set()
        for _ in range(rng.randint(1, 40)):
            if rng.random() < 0.7:
                l = rng.randint(1, 60)
                r = rng.randint(l, min(60, l + rng.choice([0, 1, 3, 10, 30])))
                c.add(l, r)
                covered.update(range(l, r + 1))
            assert c.count() == len(covered)


@pytest.mark.exercise("metrics.busy_time")
def test_metrics_busy_time_huge_ranges():
    # Short limit: an implementation that stores every covered integer must be stopped early,
    # before it eats gigabytes of memory.
    with _time_limit(0.5):
        c = BusyTimeCounter()
        step = 10**6
        for i in range(1000):  # tile [1, 1e9] with width-1e6 blocks
            c.add(i * step + 1, (i + 1) * step)
        assert c.count() == 10**9
        c.add(1, 10**9)
        assert c.count() == 10**9
        c.add(5, 7)
        assert c.count() == 10**9

        c = BusyTimeCounter()
        c.add(1, 1)
        c.add(10**9, 10**9)
        assert c.count() == 2
        c.add(2, 10**9 - 1)
        assert c.count() == 10**9
        c = BusyTimeCounter()
        c.add(10**9 - 5, 10**9)
        c.add(1, 10**8)
        c.add(5 * 10**8, 6 * 10**8)
        assert c.count() == 6 + 10**8 + 10**8 + 1


@pytest.mark.exercise("metrics.busy_time")
def test_metrics_busy_time_large_random():
    rng = random.Random(77)
    ops = []
    for _ in range(20_000):
        l = rng.randint(1, 10**9)
        r = min(10**9, l + rng.choice([0, 0, 10, 100, 1000]) + rng.randint(0, 50))
        ops.append((l, r))
    checkpoints = set(rng.sample(range(len(ops)), 15)) | {len(ops) - 1}
    got = {}
    with _time_limit(3):
        c = BusyTimeCounter()
        for i, (l, r) in enumerate(ops):
            c.add(l, r)
            x = c.count()
            if i in checkpoints:
                got[i] = x
    for i in checkpoints:
        assert got[i] == _union_size(ops[: i + 1])



@pytest.mark.exercise("metrics.busy_time")
def test_metrics_busy_time_tick_zero():
    c = BusyTimeCounter()
    c.add(0, 0)
    assert c.count() == 1
    c.add(1, 3)  # adjacent to tick 0
    assert c.count() == 4
    c.add(0, 2)
    assert c.count() == 4
    c.add(10, 10)
    assert c.count() == 5


@pytest.mark.exercise("metrics.busy_time")
def test_metrics_busy_time_random_with_zero():
    rng = random.Random(78)
    for _ in range(200):
        c = BusyTimeCounter()
        covered = set()
        for _ in range(rng.randint(1, 30)):
            l = rng.randint(0, 20)
            r = rng.randint(l, min(25, l + rng.choice([0, 1, 4])))
            c.add(l, r)
            covered.update(range(l, r + 1))
            assert c.count() == len(covered)


# ---------------------------------------------------------------- autoscale.min_throughput

def _throughput_oracle(work, days):
    """DP over split points: best[i][d] = min possible max-load for work[i:] using <= d periods."""
    n = len(work)
    prefix = [0]
    for w in work:
        prefix.append(prefix[-1] + w)
    inf = float("inf")
    best = [[inf] * (days + 1) for _ in range(n + 1)]
    for d in range(days + 1):
        best[n][d] = 0
    for d in range(1, days + 1):
        for i in range(n - 1, -1, -1):
            for j in range(i + 1, n + 1):
                best[i][d] = min(best[i][d], max(prefix[j] - prefix[i], best[j][d - 1]))
    return best[0][days]


@pytest.mark.exercise("autoscale.min_throughput")
def test_autoscale_min_throughput_examples():
    assert min_throughput([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5) == 15
    assert min_throughput([3, 2, 2, 4, 1, 4], 3) == 6
    assert min_throughput([1, 2, 3, 1, 1], 4) == 3


@pytest.mark.exercise("autoscale.min_throughput")
def test_autoscale_min_throughput_extremes_of_days():
    work = [7, 2, 5, 10, 8]
    assert min_throughput(work, 1) == 32  # everything in one period
    assert min_throughput(work, len(work)) == 10  # one task per period
    assert min_throughput(work, 2) == 18
    assert min_throughput([9], 1) == 9


@pytest.mark.exercise("autoscale.min_throughput")
def test_autoscale_min_throughput_order_is_fixed():
    # Sorting or regrouping would allow 10; keeping the order forces 11.
    assert min_throughput([5, 6, 5, 4], 2) == 11
    assert min_throughput([1, 1, 1, 1, 10], 2) == 10
    assert min_throughput([10, 1, 1, 1, 1], 2) == 10


@pytest.mark.exercise("autoscale.min_throughput")
def test_autoscale_min_throughput_random():
    rng = random.Random(78)
    for _ in range(200):
        work = [rng.randint(1, 30) for _ in range(rng.randint(1, 10))]
        days = rng.randint(1, len(work))
        assert min_throughput(list(work), days) == _throughput_oracle(work, days)


@pytest.mark.exercise("autoscale.min_throughput")
def test_autoscale_min_throughput_large():
    rng = random.Random(79)
    with _time_limit(3):
        # 1001 equal big tasks over 1000 periods: one period must take two of them.
        assert min_throughput([5 * 10**8] * 1001, 1000) == 10**9
        work = [rng.randint(1, 10**9) for _ in range(20_000)]
        days = 7
        got = min_throughput(work, days)
    # Verify optimality with a greedy feasibility check at got and got - 1.
    def periods(cap):
        used, load = 1, 0
        for w in work:
            if load + w > cap:
                used, load = used + 1, 0
            load += w
        return used
    assert periods(got) <= days < periods(got - 1)


# ---------------------------------------------------------------- autoscale.min_rate

def _rate_oracle(queues, hours):
    rate = 1
    while sum(-(-q // rate) for q in queues) > hours:
        rate += 1
    return rate


@pytest.mark.exercise("autoscale.min_rate")
def test_autoscale_min_rate_examples():
    assert min_drain_rate([3, 6, 7, 11], 8) == 4
    assert min_drain_rate([30, 11, 23, 4, 20], 5) == 30
    assert min_drain_rate([30, 11, 23, 4, 20], 6) == 23


@pytest.mark.exercise("autoscale.min_rate")
def test_autoscale_min_rate_small():
    assert min_drain_rate([1], 1) == 1
    assert min_drain_rate([1], 10**9) == 1
    assert min_drain_rate([10], 3) == 4  # ceil(10 / 4) = 3 slices
    assert min_drain_rate([5, 5, 5], 3) == 5
    assert min_drain_rate([5, 5, 5], 6) == 3


@pytest.mark.exercise("autoscale.min_rate")
def test_autoscale_min_rate_no_spillover():
    # Leftover capacity in a slice cannot be used on another queue.
    assert min_drain_rate([1, 1, 1, 1, 9], 6) == 5
    assert min_drain_rate([2, 2], 3) == 2


@pytest.mark.exercise("autoscale.min_rate")
def test_autoscale_min_rate_random():
    rng = random.Random(80)
    for _ in range(300):
        queues = [rng.randint(1, 40) for _ in range(rng.randint(1, 8))]
        hours = rng.randint(len(queues), 3 * len(queues) + 20)
        assert min_drain_rate(list(queues), hours) == _rate_oracle(queues, hours)


@pytest.mark.exercise("autoscale.min_rate")
def test_autoscale_min_rate_large():
    with _time_limit(3):
        assert min_drain_rate([10**9], 2) == 5 * 10**8
        assert min_drain_rate([10**9] + [1] * 9999, 10_000) == 10**9
        assert min_drain_rate([10**9] * 1000, 10**9) == 1000
        assert min_drain_rate([10**9] * 10_000, 10**9) == 10**4
        assert min_drain_rate([10**9 - 1, 10**9], 3) == 10**9 - 1


# ---------------------------------------------------------------- autoscale.min_time

def _time_oracle(per_request_time, total):
    t = 0
    while sum(t // x for x in per_request_time) < total:
        t += 1
    return t


@pytest.mark.exercise("autoscale.min_time")
def test_autoscale_min_time_examples():
    assert min_time_for([1, 2, 3], 5) == 3
    assert min_time_for([2], 1) == 2


@pytest.mark.exercise("autoscale.min_time")
def test_autoscale_min_time_small():
    assert min_time_for([1], 1) == 1
    assert min_time_for([5, 10, 10], 9) == 25
    assert min_time_for([3, 3, 3], 3) == 3
    assert min_time_for([3, 3, 3], 4) == 6


@pytest.mark.exercise("autoscale.min_time")
def test_autoscale_min_time_slow_worker_irrelevant():
    assert min_time_for([1, 10**7], 10) == 10
    assert min_time_for([10**7, 1], 10**7) == 10**7  # at T = 10^7 - 1 only the fast worker has finished any
    assert min_time_for([10**7, 1], 10**7 + 1) == 10**7  # at T = 10^7 the slow worker contributes one
    assert min_time_for([2, 10**7], 5) == 10


@pytest.mark.exercise("autoscale.min_time")
def test_autoscale_min_time_random():
    rng = random.Random(81)
    for _ in range(300):
        workers = [rng.randint(1, 12) for _ in range(rng.randint(1, 6))]
        total = rng.randint(1, 30)
        assert min_time_for(list(workers), total) == _time_oracle(workers, total)


@pytest.mark.exercise("autoscale.min_time")
def test_autoscale_min_time_large():
    rng = random.Random(82)
    with _time_limit(3):
        assert min_time_for([10**7], 10**7) == 10**14
        assert min_time_for([10**7] * 20_000, 10**7) == 5 * 10**9
        workers = [rng.randint(9 * 10**6, 10**7) for _ in range(20_000)]
        got = min_time_for(workers, 10**7)
    done = lambda t: sum(t // x for x in workers)  # noqa: E731
    assert done(got) >= 10**7 > done(got - 1)
