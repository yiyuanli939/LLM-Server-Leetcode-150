"""M3 core exercises: block-id arrays, ring buffers, allocator stats, page table, bitmaps, leaks, eviction."""
import random
from collections import Counter

import pytest

from nanoserve.kvcache.allocator import free_ranges, longest_free_run, owner_range
from nanoserve.kvcache.bitmap import popcount
from nanoserve.kvcache.compact import dedupe_sorted, merge_into, remove_freed
from nanoserve.kvcache.evict import RandomEvictSet
from nanoserve.kvcache.leak import find_leaked
from nanoserve.kvcache.page_table import page_exists
from nanoserve.kvcache.ring import ring_min, ring_search, rotate_right


# ---------------------------------------------------------------- kv.compact

def _check_compact(slots, freed):
    arr = list(slots)
    k = remove_freed(arr, freed)
    expected = sorted(v for v in slots if v != freed)
    assert k == len(expected)
    assert len(arr) == len(slots)
    assert sorted(arr[:k]) == expected


@pytest.mark.exercise("kv.compact")
def test_kv_compact_examples():
    _check_compact([3, 2, 2, 3], 3)
    _check_compact([0, 1, 2, 2, 3, 0, 4, 2], 2)


@pytest.mark.exercise("kv.compact")
def test_kv_compact_empty():
    _check_compact([], 0)


@pytest.mark.exercise("kv.compact")
def test_kv_compact_all_or_none_removed():
    _check_compact([4, 4, 4], 4)
    _check_compact([1, 2, 3], 7)
    _check_compact([1], 1)


@pytest.mark.exercise("kv.compact")
def test_kv_compact_randomized():
    rng = random.Random(27)
    for _ in range(200):
        slots = [rng.randrange(0, 6) for _ in range(rng.randrange(0, 101))]
        _check_compact(slots, rng.randrange(0, 6))


# ---------------------------------------------------------------- kv.dedupe

def _check_dedupe(ids):
    arr = list(ids)
    k = dedupe_sorted(arr)
    expected = sorted(set(ids))
    assert k == len(expected)
    assert len(arr) == len(ids)
    assert arr[:k] == expected


@pytest.mark.exercise("kv.dedupe")
def test_kv_dedupe_examples():
    _check_dedupe([1, 1, 2])
    _check_dedupe([0, 0, 1, 1, 1, 2, 2, 3, 3, 4])


@pytest.mark.exercise("kv.dedupe")
def test_kv_dedupe_single_and_all_same():
    _check_dedupe([5])
    _check_dedupe([-3, -3, -3, -3])


@pytest.mark.exercise("kv.dedupe")
def test_kv_dedupe_already_unique_negatives():
    _check_dedupe([-100, -5, 0, 7, 100])


@pytest.mark.exercise("kv.dedupe")
def test_kv_dedupe_randomized():
    rng = random.Random(26)
    for _ in range(200):
        _check_dedupe(sorted(rng.randrange(-10, 11) for _ in range(rng.randrange(1, 60))))


# ---------------------------------------------------------------- kv.merge_arrays

def _check_merge(a_vals, b_vals):
    m, n = len(a_vals), len(b_vals)
    a = list(a_vals) + [0] * n
    b = list(b_vals)
    a_obj = a
    assert merge_into(a, m, b, n) is None
    assert a is a_obj
    assert a == sorted(a_vals + b_vals)


@pytest.mark.exercise("kv.merge_arrays")
def test_kv_merge_arrays_example():
    _check_merge([1, 2, 3], [2, 5, 6])


@pytest.mark.exercise("kv.merge_arrays")
def test_kv_merge_arrays_one_side_empty():
    _check_merge([1], [])
    _check_merge([], [1])


@pytest.mark.exercise("kv.merge_arrays")
def test_kv_merge_arrays_b_all_smaller_and_negatives():
    _check_merge([4, 5, 6], [1, 2, 3])
    _check_merge([-1, 0, 0, 3], [-1_000_000_000, 0, 1_000_000_000])
    _check_merge([0, 0], [0])  # real zeros in a must not be confused with padding


@pytest.mark.exercise("kv.merge_arrays")
def test_kv_merge_arrays_randomized():
    rng = random.Random(88)
    for _ in range(200):
        m, n = rng.randrange(0, 30), rng.randrange(0, 30)
        if m + n == 0:
            continue
        a = sorted(rng.randrange(-20, 21) for _ in range(m))
        b = sorted(rng.randrange(-20, 21) for _ in range(n))
        _check_merge(a, b)


# ---------------------------------------------------------------- kv.rotate_buffer

def _check_rotate(buf_vals, k):
    buf = list(buf_vals)
    obj = buf
    assert rotate_right(buf, k) is None
    assert buf is obj
    s = k % len(buf_vals)
    assert buf == buf_vals[len(buf_vals) - s :] + buf_vals[: len(buf_vals) - s]


@pytest.mark.exercise("kv.rotate_buffer")
def test_kv_rotate_buffer_examples():
    _check_rotate([1, 2, 3, 4, 5, 6, 7], 3)
    _check_rotate([-1, -100, 3, 99], 2)


@pytest.mark.exercise("kv.rotate_buffer")
def test_kv_rotate_buffer_single_and_zero():
    _check_rotate([1], 0)
    _check_rotate([1], 5)
    _check_rotate([1, 2, 3], 0)


@pytest.mark.exercise("kv.rotate_buffer")
def test_kv_rotate_buffer_k_exceeds_len():
    _check_rotate([1, 2], 3)
    _check_rotate([1, 2, 3], 3)
    _check_rotate([1, 2, 3, 4, 5], 100_000)


@pytest.mark.exercise("kv.rotate_buffer")
def test_kv_rotate_buffer_randomized():
    rng = random.Random(189)
    for _ in range(200):
        n = rng.randrange(1, 50)
        _check_rotate([rng.randrange(-100, 100) for _ in range(n)], rng.randrange(0, 200))


# ---------------------------------------------------------------- kv.ring_search

def _rotated(rng, n, lo=-10_000, hi=10_000):
    base = sorted(rng.sample(range(lo, hi + 1), n))
    r = rng.randrange(n)
    return base[r:] + base[:r]


@pytest.mark.exercise("kv.ring_search")
def test_kv_ring_search_examples():
    assert ring_search([4, 5, 6, 7, 0, 1, 2], 0) == 4
    assert ring_search([4, 5, 6, 7, 0, 1, 2], 3) == -1
    assert ring_search([1], 0) == -1


@pytest.mark.exercise("kv.ring_search")
def test_kv_ring_search_single_and_pair():
    assert ring_search([1], 1) == 0
    assert ring_search([3, 1], 1) == 1
    assert ring_search([3, 1], 3) == 0
    assert ring_search([1, 3], 3) == 1
    assert ring_search([3, 1], 2) == -1


@pytest.mark.exercise("kv.ring_search")
def test_kv_ring_search_unrotated_and_bounds():
    buf = [-5, -2, 0, 3, 8]
    for i, v in enumerate(buf):
        assert ring_search(buf, v) == i
    assert ring_search(buf, -10) == -1
    assert ring_search(buf, 10) == -1


@pytest.mark.exercise("kv.ring_search")
def test_kv_ring_search_randomized():
    rng = random.Random(33)
    for _ in range(100):
        buf = _rotated(rng, rng.randrange(1, 60))
        for _ in range(10):
            t = rng.choice(buf) if rng.random() < 0.6 else rng.randrange(-10_000, 10_001)
            assert ring_search(buf, t) == (buf.index(t) if t in buf else -1)


# ---------------------------------------------------------------- kv.ring_head

@pytest.mark.exercise("kv.ring_head")
def test_kv_ring_head_examples():
    assert ring_min([3, 4, 5, 1, 2]) == 1
    assert ring_min([4, 5, 6, 7, 0, 1, 2]) == 0
    assert ring_min([11, 13, 15, 17]) == 11


@pytest.mark.exercise("kv.ring_head")
def test_kv_ring_head_single_and_pair():
    assert ring_min([5]) == 5
    assert ring_min([2, 1]) == 1
    assert ring_min([1, 2]) == 1


@pytest.mark.exercise("kv.ring_head")
def test_kv_ring_head_negatives_and_last():
    assert ring_min([-1, 0, 5, -5000, -10]) == -5000
    assert ring_min([2, 3, 4, 5, 1]) == 1


@pytest.mark.exercise("kv.ring_head")
def test_kv_ring_head_randomized():
    rng = random.Random(153)
    for _ in range(300):
        buf = _rotated(rng, rng.randrange(1, 80), -5000, 5000)
        assert ring_min(buf) == min(buf)


# ---------------------------------------------------------------- kv.longest_run

def _longest_run_oracle(ids):
    s = sorted(set(ids))
    best = cur = 0
    for i, v in enumerate(s):
        cur = cur + 1 if i and v == s[i - 1] + 1 else 1
        best = max(best, cur)
    return best


@pytest.mark.exercise("kv.longest_run")
def test_kv_longest_run_examples():
    assert longest_free_run([100, 4, 200, 1, 3, 2]) == 4
    assert longest_free_run([0, 3, 7, 2, 5, 8, 4, 6, 0, 1]) == 9
    assert longest_free_run([1, 0, 1, 2]) == 3


@pytest.mark.exercise("kv.longest_run")
def test_kv_longest_run_empty_and_single():
    assert longest_free_run([]) == 0
    assert longest_free_run([7]) == 1
    assert longest_free_run([7, 7, 7]) == 1


@pytest.mark.exercise("kv.longest_run")
def test_kv_longest_run_negatives_and_extremes():
    assert longest_free_run([-1, -3, -2, 0, 5]) == 4
    assert longest_free_run([10**9, -(10**9), 10**9 - 1]) == 2


@pytest.mark.exercise("kv.longest_run")
def test_kv_longest_run_randomized():
    rng = random.Random(128)
    for _ in range(200):
        ids = [rng.randrange(-30, 30) for _ in range(rng.randrange(0, 50))]
        assert longest_free_run(ids) == _longest_run_oracle(ids)


@pytest.mark.exercise("kv.longest_run")
def test_kv_longest_run_large_linear():
    rng = random.Random(1280)
    ids = list(range(0, 50_000)) + list(range(100_000, 150_001))
    rng.shuffle(ids)
    assert longest_free_run(ids) == 50_001


# ---------------------------------------------------------------- kv.free_ranges

@pytest.mark.exercise("kv.free_ranges")
def test_kv_free_ranges_examples():
    assert free_ranges([0, 1, 2, 4, 5, 7]) == ["0->2", "4->5", "7"]
    assert free_ranges([0, 2, 3, 4, 6, 8, 9]) == ["0", "2->4", "6", "8->9"]


@pytest.mark.exercise("kv.free_ranges")
def test_kv_free_ranges_empty_and_single():
    assert free_ranges([]) == []
    assert free_ranges([-1]) == ["-1"]


@pytest.mark.exercise("kv.free_ranges")
def test_kv_free_ranges_negatives_and_extremes():
    assert free_ranges([-3, -2, -1, 1]) == ["-3->-1", "1"]
    assert free_ranges([-(2**31), 2**31 - 1]) == ["-2147483648", "2147483647"]
    assert free_ranges([2**31 - 2, 2**31 - 1]) == ["2147483646->2147483647"]


@pytest.mark.exercise("kv.free_ranges")
def test_kv_free_ranges_randomized():
    rng = random.Random(228)
    for _ in range(200):
        ids = sorted(rng.sample(range(-15, 15), rng.randrange(0, 21)))
        out = free_ranges(ids)
        # decode and check: maximal ranges, covering exactly ids
        decoded, prev_end = [], None
        for part in out:
            a, _, b = part.partition("->")
            a = int(a)
            b = int(b) if b else a
            assert a < b or "->" not in part
            if prev_end is not None:
                assert a > prev_end + 1
            decoded += list(range(a, b + 1))
            prev_end = b
        assert decoded == ids


# ---------------------------------------------------------------- kv.seq_range

def _range_oracle(owners, x):
    idx = [i for i, v in enumerate(owners) if v == x]
    return [idx[0], idx[-1]] if idx else [-1, -1]


@pytest.mark.exercise("kv.seq_range")
def test_kv_seq_range_examples():
    assert owner_range([5, 7, 7, 8, 8, 10], 8) == [3, 4]
    assert owner_range([5, 7, 7, 8, 8, 10], 6) == [-1, -1]
    assert owner_range([], 0) == [-1, -1]


@pytest.mark.exercise("kv.seq_range")
def test_kv_seq_range_single_and_all_same():
    assert owner_range([1], 1) == [0, 0]
    assert owner_range([2, 2, 2, 2], 2) == [0, 3]
    assert owner_range([2, 2], 3) == [-1, -1]


@pytest.mark.exercise("kv.seq_range")
def test_kv_seq_range_ends_and_negatives():
    assert owner_range([-5, -5, 0, 3], -5) == [0, 1]
    assert owner_range([-5, -5, 0, 3, 3], 3) == [3, 4]
    assert owner_range([-5, 0, 3], -10) == [-1, -1]
    assert owner_range([-5, 0, 3], 10) == [-1, -1]


@pytest.mark.exercise("kv.seq_range")
def test_kv_seq_range_randomized():
    rng = random.Random(34)
    for _ in range(150):
        owners = sorted(rng.randrange(-8, 9) for _ in range(rng.randrange(0, 50)))
        for x in range(-10, 11):
            assert owner_range(owners, x) == _range_oracle(owners, x)


# ---------------------------------------------------------------- kv.page_lookup

TABLE = [[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]]


@pytest.mark.exercise("kv.page_lookup")
def test_kv_page_lookup_examples():
    assert page_exists(TABLE, 3) is True
    assert page_exists(TABLE, 13) is False


@pytest.mark.exercise("kv.page_lookup")
def test_kv_page_lookup_single_cell():
    assert page_exists([[1]], 1) is True
    assert page_exists([[1]], 2) is False
    assert page_exists([[1]], 0) is False


@pytest.mark.exercise("kv.page_lookup")
def test_kv_page_lookup_corners_and_out_of_range():
    for v in (1, 7, 23, 60, 10, 20):
        assert page_exists(TABLE, v) is True
    for v in (0, 61, 8, 21, -10_000, 10_000):
        assert page_exists(TABLE, v) is False


@pytest.mark.exercise("kv.page_lookup")
def test_kv_page_lookup_single_row_and_column():
    assert page_exists([[-5, -1, 4, 9]], 4) is True
    assert page_exists([[-5, -1, 4, 9]], 0) is False
    assert page_exists([[-5], [-1], [4], [9]], -1) is True
    assert page_exists([[-5], [-1], [4], [9]], 5) is False


@pytest.mark.exercise("kv.page_lookup")
def test_kv_page_lookup_randomized():
    rng = random.Random(74)
    for _ in range(100):
        m, n = rng.randrange(1, 8), rng.randrange(1, 8)
        flat = sorted(rng.sample(range(-200, 201), m * n))
        table = [flat[i * n : (i + 1) * n] for i in range(m)]
        s = set(flat)
        for _ in range(15):
            x = rng.randrange(-205, 206)
            assert page_exists(table, x) is (x in s)


# ---------------------------------------------------------------- kv.popcount

@pytest.mark.exercise("kv.popcount")
def test_kv_popcount_examples():
    assert popcount(11) == 3
    assert popcount(128) == 1
    assert popcount(2147483645) == 30


@pytest.mark.exercise("kv.popcount")
def test_kv_popcount_small():
    assert popcount(1) == 1
    assert popcount(2) == 1
    assert popcount(3) == 2


@pytest.mark.exercise("kv.popcount")
def test_kv_popcount_extremes():
    assert popcount(2**31 - 1) == 31
    assert popcount(2**30) == 1


@pytest.mark.exercise("kv.popcount")
def test_kv_popcount_randomized():
    rng = random.Random(191)
    for _ in range(500):
        n = rng.randrange(1, 2**31)
        assert popcount(n) == bin(n).count("1")


# ---------------------------------------------------------------- kv.leaked

@pytest.mark.exercise("kv.leaked")
def test_kv_leaked_examples():
    assert find_leaked([2, 2, 1]) == 1
    assert find_leaked([4, 1, 2, 1, 2]) == 4
    assert find_leaked([1]) == 1


@pytest.mark.exercise("kv.leaked")
def test_kv_leaked_negative_and_zero():
    assert find_leaked([-1, 5, 5]) == -1
    assert find_leaked([0, 3, 3]) == 0
    assert find_leaked([-30000, 30000, -30000]) == 30000


@pytest.mark.exercise("kv.leaked")
def test_kv_leaked_single_negative():
    assert find_leaked([-7]) == -7


@pytest.mark.exercise("kv.leaked")
def test_kv_leaked_randomized():
    rng = random.Random(136)
    for _ in range(100):
        pool = rng.sample(range(-30000, 30001), rng.randrange(1, 60))
        single, rest = pool[0], pool[1:]
        events = [single] + rest + rest
        rng.shuffle(events)
        assert find_leaked(events) == single


# ---------------------------------------------------------------- kv.random_evict

@pytest.mark.exercise("kv.random_evict")
def test_kv_random_evict_example():
    random.seed(380)
    s = RandomEvictSet()
    assert s.insert(1) is True
    assert s.remove(2) is False
    assert s.insert(2) is True
    assert s.pick() in (1, 2)
    assert s.remove(1) is True
    assert s.insert(2) is False
    assert s.pick() == 2


@pytest.mark.exercise("kv.random_evict")
def test_kv_random_evict_insert_remove_semantics():
    s = RandomEvictSet()
    assert s.remove(0) is False
    assert s.insert(0) is True
    assert s.insert(0) is False
    assert s.remove(0) is True
    assert s.remove(0) is False
    assert s.insert(0) is True
    assert s.pick() == 0


@pytest.mark.exercise("kv.random_evict")
def test_kv_random_evict_pick_covers_all():
    random.seed(12345)
    s = RandomEvictSet()
    vals = [-(2**31), -7, 0, 3, 42, 2**31 - 1]
    for v in vals:
        assert s.insert(v) is True
    seen = Counter(s.pick() for _ in range(3000))
    assert set(seen) == set(vals)
    # loose uniformity: each of 6 values expected ~500 times
    assert all(250 < c < 750 for c in seen.values())


@pytest.mark.exercise("kv.random_evict")
def test_kv_random_evict_randomized_against_set():
    random.seed(3800)
    rng = random.Random(380)
    s, model = RandomEvictSet(), set()
    for step in range(3000):
        x = rng.randrange(-20, 20)
        op = rng.random()
        if op < 0.45:
            assert s.insert(x) is (x not in model)
            model.add(x)
        elif op < 0.9:
            assert s.remove(x) is (x in model)
            model.discard(x)
        elif model:
            assert s.pick() in model
    # after the churn, pick still reaches every element and nothing else
    if model:
        seen = {s.pick() for _ in range(100 * len(model))}
        assert seen == model


# ---------------------------------------------------------------- widened ranges (block ids of a real pool)

@pytest.mark.exercise("kv.compact")
def test_kv_compact_large_values():
    _check_compact([0, 1005, 0, 7], 0)
    _check_compact([4096, -3, 4096, 4096], 4096)


@pytest.mark.exercise("kv.compact")
def test_kv_compact_randomized_wide():
    rng = random.Random(2727)
    for _ in range(50):
        pool = [rng.randrange(-10**6, 10**6) for _ in range(rng.randrange(1, 10))]
        slots = [rng.choice(pool) for _ in range(rng.randrange(0, 3000))]
        _check_compact(slots, rng.choice(pool))


@pytest.mark.exercise("kv.dedupe")
def test_kv_dedupe_large_values():
    _check_dedupe([-7, 4096, 4096, 90000])


@pytest.mark.exercise("kv.dedupe")
def test_kv_dedupe_randomized_wide():
    rng = random.Random(2626)
    for _ in range(50):
        pool = [rng.randrange(-10**9, 10**9) for _ in range(rng.randrange(1, 200))]
        _check_dedupe(sorted(rng.choice(pool) for _ in range(rng.randrange(1, 3000))))


@pytest.mark.exercise("kv.merge_arrays")
def test_kv_merge_arrays_real_zeros_and_long():
    _check_merge([0, 4, 9], [4, 5])
    _check_merge(list(range(0, 10_000, 2)), list(range(1, 10_000, 2)))


@pytest.mark.exercise("kv.merge_arrays")
def test_kv_merge_arrays_randomized_wide():
    rng = random.Random(8888)
    for _ in range(40):
        m, n = rng.randrange(0, 2000), rng.randrange(0, 2000)
        if m + n == 0:
            continue
        a = sorted(rng.randrange(-10**9, 10**9 + 1) for _ in range(m))
        b = sorted(rng.randrange(-10**9, 10**9 + 1) for _ in range(n))
        _check_merge(a, b)


@pytest.mark.exercise("kv.ring_search")
def test_kv_ring_search_large_values():
    assert ring_search([100005, 100009, 3, 42], 3) == 2
    assert ring_search([100005, 100009, 3, 42], 100009) == 1
    assert ring_search([100005, 100009, 3, 42], 50) == -1


@pytest.mark.exercise("kv.ring_search")
def test_kv_ring_search_randomized_wide():
    rng = random.Random(3333)
    for _ in range(100):
        buf = _rotated(rng, rng.randrange(1, 300), -10**9, 10**9)
        for _ in range(10):
            t = rng.choice(buf) if rng.random() < 0.6 else rng.randrange(-10**9, 10**9)
            assert ring_search(buf, t) == (buf.index(t) if t in buf else -1)


@pytest.mark.exercise("kv.ring_head")
def test_kv_ring_head_large_values():
    assert ring_min([70001, 70002, 69998, 69999]) == 69998
    assert ring_min([10**9, -10**9]) == -10**9


@pytest.mark.exercise("kv.ring_head")
def test_kv_ring_head_randomized_wide():
    rng = random.Random(1533)
    for _ in range(200):
        buf = _rotated(rng, rng.randrange(1, 300), -10**9, 10**9)
        assert ring_min(buf) == min(buf)


@pytest.mark.exercise("kv.free_ranges")
def test_kv_free_ranges_more_than_twenty():
    assert free_ranges([-1, 0, 1, 9, 1000, 1001]) == ["-1->1", "9", "1000->1001"]
    ids = list(range(0, 100)) + list(range(200, 300))
    assert free_ranges(ids) == ["0->99", "200->299"]


@pytest.mark.exercise("kv.free_ranges")
def test_kv_free_ranges_randomized_long():
    rng = random.Random(2288)
    for _ in range(40):
        ids = sorted(rng.sample(range(-3000, 3000), rng.randrange(0, 2000)))
        want, i = [], 0
        while i < len(ids):
            j = i
            while j + 1 < len(ids) and ids[j + 1] == ids[j] + 1:
                j += 1
            want.append(str(ids[i]) if i == j else f"{ids[i]}->{ids[j]}")
            i = j + 1
        assert free_ranges(ids) == want


@pytest.mark.exercise("kv.page_lookup")
def test_kv_page_lookup_block_addresses():
    table = [[0, 1, 2, 3], [24, 25, 26, 27]]
    assert page_exists(table, 26) is True
    assert page_exists(table, 4) is False
    assert page_exists(table, 0) is True


@pytest.mark.exercise("kv.page_lookup")
def test_kv_page_lookup_randomized_wide():
    rng = random.Random(7474)
    for _ in range(40):
        m, n = rng.randrange(1, 300), rng.randrange(1, 40)
        flat = sorted(rng.sample(range(-10**6, 10**6), m * n))
        table = [flat[i * n : (i + 1) * n] for i in range(m)]
        s = set(flat)
        for _ in range(30):
            x = rng.choice(flat) if rng.random() < 0.5 else rng.randrange(-10**6 - 5, 10**6 + 5)
            assert page_exists(table, x) is (x in s)
