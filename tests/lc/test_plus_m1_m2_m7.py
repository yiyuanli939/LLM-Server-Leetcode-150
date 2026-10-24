import bisect
import random
import statistics
from collections import Counter

import pytest

from nanoserve.dashboard.region import RegionSum
from nanoserve.metrics.window import QpsCounter, window_max, window_median
from nanoserve.scheduler.capacity import fits_capacity
from nanoserve.scheduler.cooldown import min_slots_with_cooldown
from nanoserve.scheduler.routing import WeightedRouter
from nanoserve.scheduler.simulate import assign_workers, busiest_worker, sjf_order
from nanoserve.stream.multistop import MultiStopMatcher
from nanoserve.stream.protocol import FrameCodec
from nanoserve.tokenizer.train import top_k_pieces


# ---------------------------------------------------------------- tok.top_pieces

@pytest.mark.exercise("tok.top_pieces")
def test_tok_top_pieces_example():
    assert sorted(top_k_pieces(["a", "a", "a", "b", "b", "c"], 2)) == ["a", "b"]


@pytest.mark.exercise("tok.top_pieces")
def test_tok_top_pieces_single():
    assert top_k_pieces(["the"], 1) == ["the"]


@pytest.mark.exercise("tok.top_pieces")
def test_tok_top_pieces_all_distinct_k():
    pieces = ["x", "y", "y", "z", "z", "z"]
    assert sorted(top_k_pieces(pieces, 3)) == ["x", "y", "z"]
    assert top_k_pieces(pieces, 1) == ["z"]


@pytest.mark.exercise("tok.top_pieces")
def test_tok_top_pieces_ties_inside_answer():
    # 'ab' and ' t' tie, but both are inside the top-2 so the answer is still unique
    pieces = ["ab", " t", "ab", "q", " t"]
    assert sorted(top_k_pieces(pieces, 2)) == [" t", "ab"]


@pytest.mark.exercise("tok.top_pieces")
def test_tok_top_pieces_random():
    rng = random.Random(11)
    for _ in range(200):
        n_distinct = rng.randint(1, 12)
        names = [f"p{i}" for i in range(n_distinct)]
        freqs = rng.sample(range(1, 40), n_distinct)  # distinct counts -> unique answer for any k
        pieces = [nm for nm, f in zip(names, freqs) for _ in range(f)]
        rng.shuffle(pieces)
        k = rng.randint(1, n_distinct)
        expected = sorted(nm for nm, _ in Counter(pieces).most_common(k))
        assert sorted(top_k_pieces(pieces, k)) == expected


# ---------------------------------------------------------------- stream.multi_stop

@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_example():
    m = MultiStopMatcher(["cd", "f", "kl"])
    got = [m.feed(c) for c in "abcdefghijkl"]
    assert got == [False, False, False, True, False, True, False, False, False, False, False, True]


@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_overlapping_stops():
    m = MultiStopMatcher(["ab", "ba", "aaaaa", "abaa"])
    got = [m.feed(c) for c in "aaaaaba"]
    assert got == [False, False, False, False, True, True, True]


@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_does_not_reset():
    m = MultiStopMatcher(["aa"])
    assert [m.feed(c) for c in "aaaba"] == [False, True, True, False, False]


@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_single_char_and_duplicates():
    m = MultiStopMatcher(["z", "z", "xyz"])
    assert [m.feed(c) for c in "zxyzz"] == [True, False, False, True, True]


@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_long_stop_not_prefix_fed():
    m = MultiStopMatcher(["abcde"])
    assert [m.feed(c) for c in "bcde"] == [False, False, False, False]


@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_punctuation_and_markup():
    m = MultiStopMatcher(["</s>", "###", "."])
    got = [m.feed(c) for c in "Hi.<</s>##x###"]
    assert got == [False, False, True, False, False, False, False, True,
                   False, False, False, False, False, True]


@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_newlines_and_whitespace():
    m = MultiStopMatcher(["\n\n", "\nUser:", " \t"])
    got = [m.feed(c) for c in "a\nb\n\nUser: \t"]
    assert got == [False, False, False, False, True, False, False, False, False, True, False, True]
    m = MultiStopMatcher(["\nUser:"])
    assert [m.feed(c) for c in "\nUser:"] == [False] * 5 + [True]


@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_unicode_and_nul():
    m = MultiStopMatcher(["。", "🙂🙂", "\x00", "你好"])
    got = [m.feed(c) for c in "你好🙂x🙂🙂\x00。"]
    assert got == [False, True, False, False, False, True, True, True]


@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_marker_like_chars_in_stops():
    # characters a trie might be tempted to use as an end marker must work as ordinary characters
    m = MultiStopMatcher(["$x", "#", "x*"])
    assert [m.feed(c) for c in "x$x*#"] == [False, False, True, True, True]
    m = MultiStopMatcher(["$"])
    assert [m.feed(c) for c in "a$$"] == [False, True, True]
    m = MultiStopMatcher(["$x"])
    assert [m.feed(c) for c in "xx$x"] == [False, False, False, True]


@pytest.mark.exercise("stream.multi_stop")
def test_stream_multi_stop_random():
    rng = random.Random(12)
    for alphabet in ("ab", "ab.\n", "<>/s#$ \x00🙂。"):
        for _ in range(40):
            stops = ["".join(rng.choice(alphabet) for _ in range(rng.randint(1, 5)))
                     for _ in range(rng.randint(1, 6))]
            m = MultiStopMatcher(stops)
            fed = ""
            for _ in range(60):
                ch = rng.choice(alphabet + "c")
                fed += ch
                assert m.feed(ch) == any(fed.endswith(s) for s in stops)


# ---------------------------------------------------------------- stream.frame_codec

def _roundtrip(chunks):
    enc = FrameCodec().encode(list(chunks))
    assert isinstance(enc, str)
    assert FrameCodec().decode(enc) == list(chunks)


@pytest.mark.exercise("stream.frame_codec")
def test_stream_frame_codec_example():
    _roundtrip(["Hello", "World"])


@pytest.mark.exercise("stream.frame_codec")
def test_stream_frame_codec_empty_list_and_empty_strings():
    _roundtrip([])
    _roundtrip([""])
    _roundtrip(["", ""])
    _roundtrip(["", "a", ""])


@pytest.mark.exercise("stream.frame_codec")
def test_stream_frame_codec_tricky_chars():
    _roundtrip(["12#3", "#", ",", "4#abc", "0#", "#5#", "\n", "a,b\nc"])
    _roundtrip(["10", "1", "#1#", "##", ",,"])


@pytest.mark.exercise("stream.frame_codec")
def test_stream_frame_codec_unicode():
    _roundtrip(["你好", "世界🙂", "é́", "\x00", "\t\r\n", "\\#\\"])


@pytest.mark.exercise("stream.frame_codec")
def test_stream_frame_codec_random():
    rng = random.Random(13)
    alphabet = "ab09#,;:\n\\ 你🙂\x00\"'"
    for _ in range(300):
        chunks = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 15)))
                  for _ in range(rng.randint(0, 8))]
        _roundtrip(chunks)


# ---------------------------------------------------------------- sched.weighted_route

def _frequencies(weights, n_picks, seed):
    random.seed(seed)
    r = WeightedRouter(weights)
    cnt = Counter()
    for _ in range(n_picks):
        i = r.pick()
        assert isinstance(i, int) and 0 <= i < len(weights)
        cnt[i] += 1
    return [cnt[i] / n_picks for i in range(len(weights))]


@pytest.mark.exercise("sched.weighted_route")
def test_sched_weighted_route_single():
    random.seed(0)
    r = WeightedRouter([7])
    assert [r.pick() for _ in range(20)] == [0] * 20


@pytest.mark.exercise("sched.weighted_route")
def test_sched_weighted_route_two():
    freq = _frequencies([1, 3], 20000, seed=14)
    assert freq == pytest.approx([0.25, 0.75], abs=0.02)


@pytest.mark.exercise("sched.weighted_route")
def test_sched_weighted_route_uneven():
    w = [1, 2, 3, 4, 10]
    freq = _frequencies(w, 20000, seed=7)
    assert freq == pytest.approx([x / sum(w) for x in w], abs=0.02)


@pytest.mark.exercise("sched.weighted_route")
def test_sched_weighted_route_small_weight_still_reachable():
    w = [100, 1, 100]
    freq = _frequencies(w, 20000, seed=11)
    assert freq == pytest.approx([x / sum(w) for x in w], abs=0.02)
    assert freq[1] > 0


@pytest.mark.exercise("sched.weighted_route")
def test_sched_weighted_route_many():
    rng = random.Random(99)
    w = [rng.randint(1, 50) for _ in range(30)]
    freq = _frequencies(w, 20000, seed=3)
    assert freq == pytest.approx([x / sum(w) for x in w], abs=0.015)


# ---------------------------------------------------------------- sched.capacity_ok

@pytest.mark.exercise("sched.capacity_ok")
def test_sched_capacity_ok_examples():
    assert fits_capacity([[2, 1, 5], [3, 3, 7]], 4) is False
    assert fits_capacity([[2, 1, 5], [3, 3, 7]], 5) is True


@pytest.mark.exercise("sched.capacity_ok")
def test_sched_capacity_ok_end_exclusive():
    assert fits_capacity([[2, 1, 5], [3, 5, 7]], 3) is True
    assert fits_capacity([[2, 1, 5], [3, 4, 7]], 3) is False


@pytest.mark.exercise("sched.capacity_ok")
def test_sched_capacity_ok_empty_and_single():
    assert fits_capacity([], 1) is True
    assert fits_capacity([[5, 0, 1]], 5) is True
    assert fits_capacity([[6, 0, 1]], 5) is False


@pytest.mark.exercise("sched.capacity_ok")
def test_sched_capacity_ok_many_overlapping():
    assert fits_capacity([[3, 2, 7], [3, 7, 9], [8, 3, 9]], 11) is True
    assert fits_capacity([[1, 0, 1000]] * 10, 10) is True
    assert fits_capacity([[1, 0, 1000]] * 11, 10) is False


@pytest.mark.exercise("sched.capacity_ok")
def test_sched_capacity_ok_random():
    rng = random.Random(15)
    for _ in range(300):
        reqs = []
        for _ in range(rng.randint(0, 10)):
            s = rng.randint(0, 30)
            reqs.append([rng.randint(1, 6), s, rng.randint(s + 1, 31)])
        cap = rng.randint(1, 20)
        usage = [0] * 32
        for b, s, e in reqs:
            for t in range(s, e):
                usage[t] += b
        assert fits_capacity([r[:] for r in reqs], cap) == (max(usage) <= cap)


@pytest.mark.exercise("sched.capacity_ok")
def test_sched_capacity_ok_large_times():
    big = 10**9
    assert fits_capacity([[2, big, big + 5], [3, big + 3, big + 7]], 4) is False
    assert fits_capacity([[2, big, big + 5], [3, big + 5, big + 7]], 3) is True
    assert fits_capacity([[1, 0, 2 * big], [1, big, big + 1]], 2) is True


@pytest.mark.exercise("sched.capacity_ok")
def test_sched_capacity_ok_random_sparse_times():
    rng = random.Random(10940)
    for _ in range(300):
        reqs = []
        for _ in range(rng.randint(0, 8)):
            s = rng.randint(0, 40) * 10**7
            reqs.append([rng.randint(1, 6), s, s + rng.randint(1, 40) * 10**7])
        cap = rng.randint(1, 20)
        # occupancy only changes at a start, so checking every start is exhaustive
        peak = max((sum(b for b, s, e in reqs if s <= t < e) for _, t, _ in reqs), default=0)
        assert fits_capacity([r[:] for r in reqs], cap) == (peak <= cap), (reqs, cap)


# ---------------------------------------------------------------- sched.sjf

def _sjf_brute(tasks):
    n = len(tasks)
    done = [False] * n
    out, t = [], 0
    while len(out) < n:
        avail = [i for i in range(n) if not done[i] and tasks[i][0] <= t]
        if not avail:
            t = min(tasks[i][0] for i in range(n) if not done[i])
            continue
        i = min(avail, key=lambda j: (tasks[j][1], j))
        done[i] = True
        out.append(i)
        t += tasks[i][1]
    return out


@pytest.mark.exercise("sched.sjf")
def test_sched_sjf_example1():
    assert sjf_order([[1, 2], [2, 4], [3, 2], [4, 1]]) == [0, 2, 3, 1]


@pytest.mark.exercise("sched.sjf")
def test_sched_sjf_example2_same_arrival():
    assert sjf_order([[7, 10], [7, 12], [7, 5], [7, 4], [7, 2]]) == [4, 3, 2, 0, 1]


@pytest.mark.exercise("sched.sjf")
def test_sched_sjf_single_and_idle_gap():
    assert sjf_order([[5, 3]]) == [0]
    # worker idles between 3 and 100; task 2 arrives exactly when task 0 finishes
    assert sjf_order([[100, 1], [1, 2], [3, 5], [3, 1]]) == [1, 3, 2, 0]


@pytest.mark.exercise("sched.sjf")
def test_sched_sjf_tie_by_index_and_non_preemptive():
    assert sjf_order([[1, 3], [1, 3], [1, 3]]) == [0, 1, 2]
    # long task starts first; shorter tasks that arrive later must wait
    assert sjf_order([[1, 10], [2, 1], [3, 1]]) == [0, 1, 2]


@pytest.mark.exercise("sched.sjf")
def test_sched_sjf_random():
    rng = random.Random(16)
    for _ in range(200):
        tasks = [[rng.randint(1, 20), rng.randint(1, 6)] for _ in range(rng.randint(1, 12))]
        assert sjf_order([t[:] for t in tasks]) == _sjf_brute(tasks)


@pytest.mark.exercise("sched.sjf")
def test_sched_sjf_arrival_zero():
    assert sjf_order([[0, 3], [0, 1], [0, 2]]) == [1, 2, 0]
    assert sjf_order([[0, 5], [1, 1], [0, 2]]) == [2, 1, 0]


@pytest.mark.exercise("sched.sjf")
def test_sched_sjf_random_with_zero():
    rng = random.Random(18340)
    for _ in range(200):
        tasks = [[rng.randint(0, 10), rng.randint(1, 6)] for _ in range(rng.randint(1, 12))]
        assert sjf_order([t[:] for t in tasks]) == _sjf_brute(tasks)


# ---------------------------------------------------------------- sched.assign_workers

def _assign_brute(weights, tasks):
    free_at = [0] * len(weights)
    ans, t = [], 0
    for j, dur in enumerate(tasks):
        t = max(t, j)
        while True:
            idle = [i for i in range(len(weights)) if free_at[i] <= t]
            if idle:
                break
            t = min(free_at)
        i = min(idle, key=lambda s: (weights[s], s))
        ans.append(i)
        free_at[i] = t + dur
    return ans


@pytest.mark.exercise("sched.assign_workers")
def test_sched_assign_workers_example1():
    assert assign_workers([3, 3, 2], [1, 2, 3, 2, 1, 2]) == [2, 2, 0, 2, 1, 2]


@pytest.mark.exercise("sched.assign_workers")
def test_sched_assign_workers_example2():
    assert assign_workers([5, 1, 4, 3, 2], [2, 1, 2, 4, 5, 2, 1]) == [1, 4, 1, 4, 1, 3, 2]


@pytest.mark.exercise("sched.assign_workers")
def test_sched_assign_workers_single_worker():
    assert assign_workers([1], [3, 1, 1]) == [0, 0, 0]
    assert assign_workers([4], [1]) == [0]


@pytest.mark.exercise("sched.assign_workers")
def test_sched_assign_workers_backlog_released_by_weight():
    # both workers busy until t=10; queued tasks then go out by (weight, index)
    assert assign_workers([2, 1], [10, 10, 1, 1, 1]) == [1, 0, 1, 1, 0]
    assert assign_workers([1, 1, 1], [5, 5, 5, 1, 1, 1]) == [0, 1, 2, 0, 0, 1]


@pytest.mark.exercise("sched.assign_workers")
def test_sched_assign_workers_random():
    rng = random.Random(17)
    for _ in range(200):
        weights = [rng.randint(1, 5) for _ in range(rng.randint(1, 5))]
        tasks = [rng.randint(1, 8) for _ in range(rng.randint(1, 15))]
        assert assign_workers(weights[:], tasks[:]) == _assign_brute(weights, tasks)


# ---------------------------------------------------------------- sched.busiest_worker

def _busiest_brute(n, jobs):
    free_at = [0] * n
    count = [0] * n
    for s, e in sorted(jobs):
        idle = [w for w in range(n) if free_at[w] <= s]
        if idle:
            w = idle[0]
            free_at[w] = e
        else:
            w = min(range(n), key=lambda x: (free_at[x], x))
            free_at[w] += e - s
        count[w] += 1
    return max(range(n), key=lambda w: (count[w], -w))


@pytest.mark.exercise("sched.busiest_worker")
def test_sched_busiest_worker_example1():
    assert busiest_worker(2, [[0, 10], [1, 5], [2, 7], [3, 4]]) == 0


@pytest.mark.exercise("sched.busiest_worker")
def test_sched_busiest_worker_example2():
    assert busiest_worker(3, [[1, 20], [2, 10], [3, 5], [4, 9], [6, 8]]) == 1


@pytest.mark.exercise("sched.busiest_worker")
def test_sched_busiest_worker_single_and_unsorted():
    assert busiest_worker(1, [[5, 6]]) == 0
    # input not sorted by start; back-to-back jobs reuse worker 0
    assert busiest_worker(3, [[2, 3], [0, 1], [1, 2]]) == 0


@pytest.mark.exercise("sched.busiest_worker")
def test_sched_busiest_worker_tie_smallest_index():
    assert busiest_worker(2, [[0, 10], [1, 10]]) == 0
    assert busiest_worker(4, [[0, 1]]) == 0


@pytest.mark.exercise("sched.busiest_worker")
def test_sched_busiest_worker_delay_keeps_duration():
    # job [1,2] waits until worker 0 frees at 5 and then occupies [5,6);
    # job [5,7] must then wait until 6 (worker 0) -> worker 0 gets 3 jobs
    assert busiest_worker(1, [[0, 5], [1, 2], [5, 7]]) == 0
    assert busiest_worker(2, [[0, 5], [1, 6], [2, 3], [3, 4], [10, 11]]) == 0


@pytest.mark.exercise("sched.busiest_worker")
def test_sched_busiest_worker_random():
    rng = random.Random(18)
    for _ in range(200):
        n = rng.randint(1, 4)
        starts = rng.sample(range(0, 40), rng.randint(1, 15))
        jobs = [[s, s + rng.randint(1, 10)] for s in starts]
        assert busiest_worker(n, [j[:] for j in jobs]) == _busiest_brute(n, jobs)


# ---------------------------------------------------------------- sched.cooldown

def _cooldown_brute(adapters, n):
    # greedy simulation: at each slot run the available adapter with most remaining tasks
    remaining = Counter(adapters)
    next_ok = {a: 0 for a in remaining}
    t = 0
    while remaining:
        avail = [a for a in remaining if next_ok[a] <= t]
        if avail:
            a = max(avail, key=lambda x: (remaining[x], x))
            remaining[a] -= 1
            if remaining[a] == 0:
                del remaining[a]
            next_ok[a] = t + n + 1
        t += 1
    return t


@pytest.mark.exercise("sched.cooldown")
def test_sched_cooldown_example1():
    assert min_slots_with_cooldown(["A", "A", "A", "B", "B", "B"], 2) == 8


@pytest.mark.exercise("sched.cooldown")
def test_sched_cooldown_example2_no_idle():
    assert min_slots_with_cooldown(["A", "C", "A", "B", "D", "B"], 1) == 6


@pytest.mark.exercise("sched.cooldown")
def test_sched_cooldown_example3():
    assert min_slots_with_cooldown(["A", "A", "A", "B", "B", "B"], 3) == 10


@pytest.mark.exercise("sched.cooldown")
def test_sched_cooldown_edges():
    assert min_slots_with_cooldown(["A", "A", "A"], 0) == 3
    assert min_slots_with_cooldown(["lora-x"], 5) == 1
    assert min_slots_with_cooldown(["A", "A", "A"], 2) == 7
    assert min_slots_with_cooldown(["A", "A", "A", "A", "A", "A", "B", "C", "D", "E", "F", "G"], 2) == 16


@pytest.mark.exercise("sched.cooldown")
def test_sched_cooldown_random():
    rng = random.Random(19)
    for _ in range(300):
        adapters = [rng.choice(["q", "k", "v", "o", "up", "down"]) for _ in range(rng.randint(1, 20))]
        n = rng.randint(0, 5)
        assert min_slots_with_cooldown(adapters[:], n) == _cooldown_brute(adapters, n)


# ---------------------------------------------------------------- metrics.qps

@pytest.mark.exercise("metrics.qps")
def test_metrics_qps_example():
    q = QpsCounter()
    assert [q.hit(t) for t in [1, 100, 3001, 3002]] == [1, 2, 3, 3]


@pytest.mark.exercise("metrics.qps")
def test_metrics_qps_single():
    assert QpsCounter().hit(42) == 1


@pytest.mark.exercise("metrics.qps")
def test_metrics_qps_inclusive_boundary():
    q = QpsCounter()
    assert q.hit(1000) == 1
    assert q.hit(4000) == 2  # 4000 - 3000 == 1000 is still inside
    assert q.hit(4001) == 2  # 1000 drops out


@pytest.mark.exercise("metrics.qps")
def test_metrics_qps_large_gap_and_instances_independent():
    a, b = QpsCounter(), QpsCounter()
    assert [a.hit(t) for t in [1, 2, 3]] == [1, 2, 3]
    assert a.hit(10**9) == 1
    assert b.hit(5) == 1


@pytest.mark.exercise("metrics.qps")
def test_metrics_qps_random():
    rng = random.Random(20)
    q = QpsCounter()
    seen = []
    t = 0
    for _ in range(3000):
        t += rng.randint(1, 50) if rng.random() < 0.8 else rng.randint(1000, 5000)
        seen.append(t)
        assert q.hit(t) == len(seen) - bisect.bisect_left(seen, t - 3000)


# ---------------------------------------------------------------- metrics.window_max

@pytest.mark.exercise("metrics.window_max")
def test_metrics_window_max_example():
    assert window_max([1, 3, -1, -3, 5, 3, 6, 7], 3) == [3, 3, 5, 5, 6, 7]


@pytest.mark.exercise("metrics.window_max")
def test_metrics_window_max_single():
    assert window_max([1], 1) == [1]


@pytest.mark.exercise("metrics.window_max")
def test_metrics_window_max_k_equals_n_and_k_one():
    xs = [4, -2, 9, 9, 0]
    assert window_max(xs, 5) == [9]
    assert window_max(xs, 1) == xs


@pytest.mark.exercise("metrics.window_max")
def test_metrics_window_max_duplicates_negatives_decreasing():
    assert window_max([-7, -8, 7, 5, 7, 1, 6, 0], 4) == [7, 7, 7, 7, 7]
    assert window_max([9, 8, 7, 6, 5], 2) == [9, 8, 7, 6]
    assert window_max([2, 2, 2, 2], 3) == [2, 2]


@pytest.mark.exercise("metrics.window_max")
def test_metrics_window_max_random():
    rng = random.Random(21)
    for _ in range(200):
        xs = [rng.randint(-20, 20) for _ in range(rng.randint(1, 40))]
        k = rng.randint(1, len(xs))
        assert window_max(xs[:], k) == [max(xs[i:i + k]) for i in range(len(xs) - k + 1)]


@pytest.mark.exercise("metrics.window_max")
def test_metrics_window_max_large():
    rng = random.Random(22)
    xs = [rng.randint(-10**4, 10**4) for _ in range(50000)]
    k = 1000
    got = window_max(xs, k)
    assert len(got) == len(xs) - k + 1
    for i in rng.sample(range(len(got)), 30):
        assert got[i] == max(xs[i:i + k])


# ---------------------------------------------------------------- metrics.window_median

@pytest.mark.exercise("metrics.window_median")
def test_metrics_window_median_example1():
    assert window_median([1, 3, -1, -3, 5, 3, 6, 7], 3) == pytest.approx([1.0, -1.0, -1.0, 3.0, 5.0, 6.0])


@pytest.mark.exercise("metrics.window_median")
def test_metrics_window_median_example2():
    assert window_median([1, 2, 3, 4, 2, 3, 1, 4, 2], 3) == pytest.approx(
        [2.0, 3.0, 3.0, 3.0, 2.0, 3.0, 2.0])


@pytest.mark.exercise("metrics.window_median")
def test_metrics_window_median_even_k_and_returns_floats():
    got = window_median([1, 2, 3, 4], 2)
    assert got == pytest.approx([1.5, 2.5, 3.5])
    assert all(isinstance(x, float) for x in got)


@pytest.mark.exercise("metrics.window_median")
def test_metrics_window_median_edges():
    assert window_median([5], 1) == pytest.approx([5.0])
    assert window_median([2, -1, 7], 1) == pytest.approx([2.0, -1.0, 7.0])
    assert window_median([4, 4, 4, 4], 4) == pytest.approx([4.0])
    big = 2**31 - 1
    assert window_median([big, big], 2) == pytest.approx([float(big)])
    assert window_median([-2**31, -2**31, big], 2) == pytest.approx([-2.0**31, -0.5])


@pytest.mark.exercise("metrics.window_median")
def test_metrics_window_median_random():
    rng = random.Random(23)
    for _ in range(200):
        xs = [rng.randint(-10, 10) for _ in range(rng.randint(1, 40))]
        k = rng.randint(1, len(xs))
        expected = [float(statistics.median(xs[i:i + k])) for i in range(len(xs) - k + 1)]
        assert window_median(xs[:], k) == pytest.approx(expected)


@pytest.mark.exercise("metrics.window_median")
def test_metrics_window_median_large():
    rng = random.Random(24)
    xs = [rng.randint(-10**6, 10**6) for _ in range(30000)]
    k = 2000
    got = window_median(xs, k)
    assert len(got) == len(xs) - k + 1
    for i in rng.sample(range(len(got)), 10):
        assert got[i] == pytest.approx(statistics.median(xs[i:i + k]))


# ---------------------------------------------------------------- dash.region_sum

_GRID = [
    [3, 0, 1, 4, 2],
    [5, 6, 3, 2, 1],
    [1, 2, 0, 1, 5],
    [4, 1, 0, 1, 7],
    [1, 0, 3, 0, 5],
]


@pytest.mark.exercise("dash.region_sum")
def test_dash_region_sum_example():
    rs = RegionSum([row[:] for row in _GRID])
    assert rs.sum_region(2, 1, 4, 3) == 8
    assert rs.sum_region(1, 1, 2, 2) == 11
    assert rs.sum_region(1, 2, 2, 4) == 12


@pytest.mark.exercise("dash.region_sum")
def test_dash_region_sum_whole_and_single_cell():
    rs = RegionSum([row[:] for row in _GRID])
    assert rs.sum_region(0, 0, 4, 4) == sum(map(sum, _GRID))
    assert rs.sum_region(0, 0, 0, 0) == 3
    assert rs.sum_region(4, 4, 4, 4) == 5
    assert rs.sum_region(3, 0, 3, 0) == 4


@pytest.mark.exercise("dash.region_sum")
def test_dash_region_sum_one_by_one_and_row_col():
    assert RegionSum([[-7]]).sum_region(0, 0, 0, 0) == -7
    row = RegionSum([[1, -2, 3, -4]])
    assert row.sum_region(0, 1, 0, 3) == -3
    col = RegionSum([[1], [2], [3]])
    assert col.sum_region(1, 0, 2, 0) == 5


@pytest.mark.exercise("dash.region_sum")
def test_dash_region_sum_negatives_repeated_queries():
    rs = RegionSum([[-1, -2], [-3, -4]])
    for _ in range(3):
        assert rs.sum_region(0, 0, 1, 1) == -10
        assert rs.sum_region(0, 1, 1, 1) == -6


@pytest.mark.exercise("dash.region_sum")
def test_dash_region_sum_random():
    rng = random.Random(25)
    for _ in range(30):
        m, n = rng.randint(1, 8), rng.randint(1, 8)
        grid = [[rng.randint(-50, 50) for _ in range(n)] for _ in range(m)]
        rs = RegionSum([row[:] for row in grid])
        for _ in range(30):
            r1, r2 = sorted(rng.randint(0, m - 1) for _ in range(2))
            c1, c2 = sorted(rng.randint(0, n - 1) for _ in range(2))
            expected = sum(grid[r][c] for r in range(r1, r2 + 1) for c in range(c1, c2 + 1))
            assert rs.sum_region(r1, c1, r2, c2) == expected
