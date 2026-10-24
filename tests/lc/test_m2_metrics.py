import random
import statistics
from collections import Counter

import pytest

from nanoserve.metrics.burst import max_burst, max_burst_circular
from nanoserve.metrics.latency import MedianTracker, merged_median
from nanoserve.metrics.tenants import dominant_tenant


# ---------------------------------------------------------------- metrics.median

@pytest.mark.exercise("metrics.median")
def test_metrics_median_example():
    t = MedianTracker()
    t.add(1)
    t.add(2)
    assert t.median() == pytest.approx(1.5)
    t.add(3)
    assert t.median() == pytest.approx(2.0)


@pytest.mark.exercise("metrics.median")
def test_metrics_median_single():
    t = MedianTracker()
    t.add(-7)
    m = t.median()
    assert isinstance(m, float)
    assert m == pytest.approx(-7.0)


@pytest.mark.exercise("metrics.median")
def test_metrics_median_duplicates_and_negatives():
    t = MedianTracker()
    out = []
    for x in [5, 5, -3, 5, -10, 0]:
        t.add(x)
        out.append(t.median())
    assert out == pytest.approx([5.0, 5.0, 5.0, 5.0, 5.0, 2.5])


@pytest.mark.exercise("metrics.median")
def test_metrics_median_descending_stream():
    t = MedianTracker()
    for x in range(10, 0, -1):
        t.add(x)
    assert t.median() == pytest.approx(5.5)
    t.add(0)
    assert t.median() == pytest.approx(5.0)


@pytest.mark.exercise("metrics.median")
def test_metrics_median_random():
    rng = random.Random(295)
    t = MedianTracker()
    seen = []
    for _ in range(600):
        x = rng.randint(-1000, 1000)
        t.add(x)
        seen.append(x)
        if rng.random() < 0.3:
            assert t.median() == pytest.approx(float(statistics.median(seen)))


# ---------------------------------------------------------------- metrics.merged_median

@pytest.mark.exercise("metrics.merged_median")
def test_metrics_merged_median_example_odd():
    assert merged_median([1, 3], [2]) == pytest.approx(2.0)


@pytest.mark.exercise("metrics.merged_median")
def test_metrics_merged_median_example_even():
    assert merged_median([1, 2], [3, 4]) == pytest.approx(2.5)


@pytest.mark.exercise("metrics.merged_median")
def test_metrics_merged_median_one_empty():
    assert merged_median([], [1]) == pytest.approx(1.0)
    assert merged_median([2], []) == pytest.approx(2.0)
    assert merged_median([], [2, 3]) == pytest.approx(2.5)
    assert merged_median([1, 2, 3, 4, 5], []) == pytest.approx(3.0)


@pytest.mark.exercise("metrics.merged_median")
def test_metrics_merged_median_duplicates_negatives():
    assert merged_median([0, 0], [0, 0]) == pytest.approx(0.0)
    assert merged_median([-5, -3, -1], [-2]) == pytest.approx(-2.5)
    assert merged_median([1, 1, 1], [1, 1, 2]) == pytest.approx(1.0)


@pytest.mark.exercise("metrics.merged_median")
def test_metrics_merged_median_disjoint_ranges():
    assert merged_median([1, 2, 3], [10, 11, 12, 13]) == pytest.approx(10.0)
    assert merged_median([100], [1, 2, 3, 4]) == pytest.approx(3.0)


@pytest.mark.exercise("metrics.merged_median")
def test_metrics_merged_median_random():
    rng = random.Random(4)
    for _ in range(400):
        m, n = rng.randint(0, 12), rng.randint(0, 12)
        if m + n == 0:
            continue
        a = sorted(rng.randint(-50, 50) for _ in range(m))
        b = sorted(rng.randint(-50, 50) for _ in range(n))
        expect = float(statistics.median(a + b))
        assert merged_median(a, b) == pytest.approx(expect), (a, b)


# ---------------------------------------------------------------- metrics.dominant

@pytest.mark.exercise("metrics.dominant")
def test_metrics_dominant_example():
    assert dominant_tenant([3, 2, 3]) == 3


@pytest.mark.exercise("metrics.dominant")
def test_metrics_dominant_example_long():
    assert dominant_tenant([2, 2, 1, 1, 1, 2, 2]) == 2


@pytest.mark.exercise("metrics.dominant")
def test_metrics_dominant_single():
    assert dominant_tenant([42]) == 42


@pytest.mark.exercise("metrics.dominant")
def test_metrics_dominant_negative_ids():
    assert dominant_tenant([-1, -1, 5, -1, 7]) == -1
    assert dominant_tenant([0, 1, 0]) == 0


@pytest.mark.exercise("metrics.dominant")
def test_metrics_dominant_majority_at_end():
    assert dominant_tenant([1, 2, 3, 4, 9, 9, 9, 9, 9]) == 9


@pytest.mark.exercise("metrics.dominant")
def test_metrics_dominant_random():
    rng = random.Random(169)
    for _ in range(200):
        n = rng.randint(1, 30)
        major = rng.randint(-5, 5)
        k = n // 2 + 1
        xs = [major] * k + [rng.randint(-5, 5) for _ in range(n - k)]
        rng.shuffle(xs)
        expect = Counter(xs).most_common(1)[0][0]
        assert dominant_tenant(xs) == expect


@pytest.mark.exercise("metrics.dominant")
def test_metrics_dominant_string_ids():
    assert dominant_tenant(["acme", "beta", "acme"]) == "acme"
    assert dominant_tenant(["b", "a", "b", "c", "b"]) == "b"
    assert dominant_tenant(["solo"]) == "solo"


@pytest.mark.exercise("metrics.dominant")
def test_metrics_dominant_no_majority_returns_some_id():
    for xs in (["a", "b", "c"], ["a", "a", "b", "b"], [1, 2, 3, 4, 1, 2]):
        assert dominant_tenant(list(xs)) in xs


@pytest.mark.exercise("metrics.dominant")
def test_metrics_dominant_random_strings_any_input():
    rng = random.Random(1690)
    for _ in range(300):
        xs = [rng.choice("abcd") for _ in range(rng.randint(1, 15))]
        if rng.random() < 0.5:  # plant a majority half of the time
            k = len(xs) // 2 + 1
            xs = ["m"] * k + xs[: len(xs) - k]
            rng.shuffle(xs)
        got = dominant_tenant(list(xs))
        assert got in xs
        top, cnt = Counter(xs).most_common(1)[0]
        if 2 * cnt > len(xs):
            assert got == top, xs


# ---------------------------------------------------------------- metrics.max_burst

def _brute_max_sub(xs):
    return max(sum(xs[i:j]) for i in range(len(xs)) for j in range(i + 1, len(xs) + 1))


def _brute_max_circ(xs):
    n = len(xs)
    return max(sum(xs[(i + t) % n] for t in range(length))
               for i in range(n) for length in range(1, n + 1))


@pytest.mark.exercise("metrics.max_burst")
def test_metrics_max_burst_example():
    assert max_burst([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == 6


@pytest.mark.exercise("metrics.max_burst")
def test_metrics_max_burst_single():
    assert max_burst([1]) == 1
    assert max_burst([-9]) == -9


@pytest.mark.exercise("metrics.max_burst")
def test_metrics_max_burst_whole_array():
    assert max_burst([5, 4, -1, 7, 8]) == 23


@pytest.mark.exercise("metrics.max_burst")
def test_metrics_max_burst_all_negative():
    assert max_burst([-3, -1, -2]) == -1


@pytest.mark.exercise("metrics.max_burst")
def test_metrics_max_burst_zeros():
    assert max_burst([0, -1, 0]) == 0


@pytest.mark.exercise("metrics.max_burst")
def test_metrics_max_burst_random():
    rng = random.Random(53)
    for _ in range(300):
        xs = [rng.randint(-20, 20) for _ in range(rng.randint(1, 15))]
        assert max_burst(xs) == _brute_max_sub(xs), xs


# ---------------------------------------------------------------- metrics.max_burst_circular

@pytest.mark.exercise("metrics.max_burst_circular")
def test_metrics_max_burst_circular_example():
    assert max_burst_circular([1, -2, 3, -2]) == 3


@pytest.mark.exercise("metrics.max_burst_circular")
def test_metrics_max_burst_circular_wraps():
    assert max_burst_circular([5, -3, 5]) == 10


@pytest.mark.exercise("metrics.max_burst_circular")
def test_metrics_max_burst_circular_all_negative():
    assert max_burst_circular([-3, -2, -3]) == -2


@pytest.mark.exercise("metrics.max_burst_circular")
def test_metrics_max_burst_circular_single():
    assert max_burst_circular([7]) == 7
    assert max_burst_circular([-7]) == -7


@pytest.mark.exercise("metrics.max_burst_circular")
def test_metrics_max_burst_circular_each_element_once():
    # whole ring is positive: the answer is the total, not more
    assert max_burst_circular([1, 2, 3]) == 6
    assert max_burst_circular([3, -1, 2, -1]) == 4


@pytest.mark.exercise("metrics.max_burst_circular")
def test_metrics_max_burst_circular_random():
    rng = random.Random(918)
    for _ in range(300):
        xs = [rng.randint(-20, 20) for _ in range(rng.randint(1, 12))]
        assert max_burst_circular(xs) == _brute_max_circ(xs), xs
