import itertools
import random

import pytest

from nanoserve.scheduler.batching import min_launches
from nanoserve.scheduler.timeline import insert_busy, merge_busy


# ---------------------------------------------------------------- sched.merge_busy

def _brute_merge(intervals):
    # repeatedly fuse any two intervals sharing a point until none do
    ivs = [list(iv) for iv in intervals]
    changed = True
    while changed:
        changed = False
        for a in range(len(ivs)):
            for b in range(a + 1, len(ivs)):
                if ivs[a][0] <= ivs[b][1] and ivs[b][0] <= ivs[a][1]:
                    ivs[a] = [min(ivs[a][0], ivs[b][0]), max(ivs[a][1], ivs[b][1])]
                    del ivs[b]
                    changed = True
                    break
            if changed:
                break
    return sorted(ivs)


@pytest.mark.exercise("sched.merge_busy")
def test_sched_merge_busy_example():
    assert merge_busy([[1, 3], [2, 6], [8, 10], [15, 18]]) == [[1, 6], [8, 10], [15, 18]]


@pytest.mark.exercise("sched.merge_busy")
def test_sched_merge_busy_touching():
    assert merge_busy([[1, 4], [4, 5]]) == [[1, 5]]


@pytest.mark.exercise("sched.merge_busy")
def test_sched_merge_busy_single_and_points():
    assert merge_busy([[0, 0]]) == [[0, 0]]
    assert merge_busy([[1, 2], [3, 4]]) == [[1, 2], [3, 4]]


@pytest.mark.exercise("sched.merge_busy")
def test_sched_merge_busy_unsorted_and_nested():
    assert merge_busy([[4, 7], [1, 4]]) == [[1, 7]]
    assert merge_busy([[2, 3], [1, 10], [4, 5]]) == [[1, 10]]
    assert merge_busy([[5, 6], [1, 2], [1, 2]]) == [[1, 2], [5, 6]]


@pytest.mark.exercise("sched.merge_busy")
def test_sched_merge_busy_random():
    rng = random.Random(56)
    for _ in range(300):
        ivs = []
        for _ in range(rng.randint(1, 8)):
            s = rng.randint(0, 20)
            ivs.append([s, s + rng.randint(0, 5)])
        assert merge_busy([list(iv) for iv in ivs]) == _brute_merge(ivs), ivs


# ---------------------------------------------------------------- sched.insert_busy

@pytest.mark.exercise("sched.insert_busy")
def test_sched_insert_busy_example():
    assert insert_busy([[1, 3], [6, 9]], [2, 5]) == [[1, 5], [6, 9]]


@pytest.mark.exercise("sched.insert_busy")
def test_sched_insert_busy_example_spanning():
    assert insert_busy([[1, 2], [3, 5], [6, 7], [8, 10], [12, 16]], [4, 8]) == [[1, 2], [3, 10], [12, 16]]


@pytest.mark.exercise("sched.insert_busy")
def test_sched_insert_busy_empty():
    assert insert_busy([], [5, 7]) == [[5, 7]]


@pytest.mark.exercise("sched.insert_busy")
def test_sched_insert_busy_front_back_touching():
    assert insert_busy([[3, 5]], [0, 1]) == [[0, 1], [3, 5]]
    assert insert_busy([[3, 5]], [7, 8]) == [[3, 5], [7, 8]]
    assert insert_busy([[1, 5]], [5, 7]) == [[1, 7]]
    assert insert_busy([[1, 5]], [2, 3]) == [[1, 5]]
    assert insert_busy([[1, 2], [5, 6]], [3, 4]) == [[1, 2], [3, 4], [5, 6]]


@pytest.mark.exercise("sched.insert_busy")
def test_sched_insert_busy_random():
    rng = random.Random(57)
    for _ in range(300):
        raw = []
        for _ in range(rng.randint(0, 6)):
            s = rng.randint(0, 30)
            raw.append([s, s + rng.randint(0, 4)])
        base = _brute_merge(raw) if raw else []
        s = rng.randint(0, 32)
        new = [s, s + rng.randint(0, 8)]
        assert insert_busy([list(iv) for iv in base], list(new)) == _brute_merge(base + [new]), (base, new)


# ---------------------------------------------------------------- sched.min_launches

def _brute_launches(windows):
    cands = sorted({e for _, e in windows})
    for k in range(1, len(windows) + 1):
        for pts in itertools.combinations(cands, k):
            if all(any(s <= t <= e for t in pts) for s, e in windows):
                return k
    raise AssertionError("unreachable")


@pytest.mark.exercise("sched.min_launches")
def test_sched_min_launches_example():
    assert min_launches([[10, 16], [2, 8], [1, 6], [7, 12]]) == 2


@pytest.mark.exercise("sched.min_launches")
def test_sched_min_launches_disjoint():
    assert min_launches([[1, 2], [3, 4], [5, 6], [7, 8]]) == 4


@pytest.mark.exercise("sched.min_launches")
def test_sched_min_launches_touching_endpoints_share():
    assert min_launches([[1, 2], [2, 3], [3, 4], [4, 5]]) == 2


@pytest.mark.exercise("sched.min_launches")
def test_sched_min_launches_single_and_extremes():
    assert min_launches([[5, 5]]) == 1
    lo, hi = -(2 ** 31), 2 ** 31 - 1
    assert min_launches([[lo, hi], [hi, hi]]) == 1
    assert min_launches([[lo, lo], [hi, hi]]) == 2


@pytest.mark.exercise("sched.min_launches")
def test_sched_min_launches_random():
    rng = random.Random(452)
    for _ in range(200):
        ws = []
        for _ in range(rng.randint(1, 7)):
            s = rng.randint(-10, 10)
            ws.append([s, s + rng.randint(0, 6)])
        assert min_launches([list(w) for w in ws]) == _brute_launches(ws), ws


# ---------------------------------------------------------------- sched.can_reach / sched.min_hops


