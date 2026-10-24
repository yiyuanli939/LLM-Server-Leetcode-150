"""New M3 exercises: block-hash dedup table, free-range tracker, allocated address ranges."""
import random

import pytest

from nanoserve.kvcache.address_ranges import AddressRanges
from nanoserve.kvcache.free_tracker import FreeRangeTracker
from nanoserve.kvcache.hashmap import BlockHashMap


# ---------------------------------------------------------------- kv.block_hash

@pytest.mark.exercise("kv.block_hash")
def test_kv_block_hash_example():
    m = BlockHashMap()
    assert m.put(1, 1) is None
    m.put(2, 2)
    assert m.get(1) == 1
    assert m.get(3) == -1
    m.put(2, 1)
    assert m.get(2) == 1
    assert m.remove(2) is None
    assert m.get(2) == -1


@pytest.mark.exercise("kv.block_hash")
def test_kv_block_hash_empty_and_remove_missing():
    m = BlockHashMap()
    assert m.get(0) == -1
    m.remove(0)
    m.remove(123)
    assert m.get(123) == -1
    m.put(0, 0)
    assert m.get(0) == 0


@pytest.mark.exercise("kv.block_hash")
def test_kv_block_hash_extreme_keys_and_values():
    m = BlockHashMap()
    m.put(0, 1_000_000)
    m.put(1_000_000, 0)
    assert m.get(0) == 1_000_000
    assert m.get(1_000_000) == 0
    m.remove(0)
    assert m.get(0) == -1
    assert m.get(1_000_000) == 0


@pytest.mark.exercise("kv.block_hash")
def test_kv_block_hash_colliding_strides():
    # keys sharing a common stride tend to land in the same bucket of a naive table
    m = BlockHashMap()
    keys = [i * 1000 for i in range(1000)] + [i * 1024 for i in range(900)]
    for k in keys:
        m.put(k, k % 9973)
    for k in keys:
        assert m.get(k) == k % 9973
    for k in keys[::2]:
        m.remove(k)
    removed = set(keys[::2])
    for k in keys:
        assert m.get(k) == (-1 if k in removed else k % 9973)


@pytest.mark.exercise("kv.block_hash")
def test_kv_block_hash_reinsert_after_remove():
    m = BlockHashMap()
    m.put(7, 70)
    m.remove(7)
    m.remove(7)
    assert m.get(7) == -1
    m.put(7, 71)
    assert m.get(7) == 71
    m.put(7, 72)
    assert m.get(7) == 72


@pytest.mark.exercise("kv.block_hash")
def test_kv_block_hash_random_vs_model():
    rng = random.Random(706)
    for key_space in (5, 50, 3000, 1_000_001):
        m, model = BlockHashMap(), {}
        for _ in range(3000):
            k = rng.randrange(key_space)
            r = rng.random()
            if r < 0.4:
                v = rng.randrange(1_000_001)
                m.put(k, v)
                model[k] = v
            elif r < 0.6:
                m.remove(k)
                model.pop(k, None)
            else:
                assert m.get(k) == model.get(k, -1)
        for k in list(model)[:200]:
            assert m.get(k) == model[k]


# ---------------------------------------------------------------- kv.free_tracker

def _ranges_brute(blocks):
    out = []
    for b in sorted(set(blocks)):
        if out and out[-1][1] == b - 1:
            out[-1][1] = b
        else:
            out.append([b, b])
    return out


@pytest.mark.exercise("kv.free_tracker")
def test_kv_free_tracker_example():
    t = FreeRangeTracker()
    expected = [
        (1, [[1, 1]]),
        (3, [[1, 1], [3, 3]]),
        (7, [[1, 1], [3, 3], [7, 7]]),
        (2, [[1, 3], [7, 7]]),
        (6, [[1, 3], [6, 7]]),
    ]
    for block, want in expected:
        assert t.add(block) is None
        assert t.ranges() == want


@pytest.mark.exercise("kv.free_tracker")
def test_kv_free_tracker_empty_and_zero():
    t = FreeRangeTracker()
    assert t.ranges() == []
    t.add(0)
    assert t.ranges() == [[0, 0]]
    t.add(10_000)
    assert t.ranges() == [[0, 0], [10_000, 10_000]]


@pytest.mark.exercise("kv.free_tracker")
def test_kv_free_tracker_duplicates():
    t = FreeRangeTracker()
    for b in (5, 5, 6, 5, 6, 4, 4):
        t.add(b)
    assert t.ranges() == [[4, 6]]
    t.add(5)
    assert t.ranges() == [[4, 6]]


@pytest.mark.exercise("kv.free_tracker")
def test_kv_free_tracker_bridge_and_extend():
    t = FreeRangeTracker()
    for b in (10, 11, 13, 14):
        t.add(b)
    assert t.ranges() == [[10, 11], [13, 14]]
    t.add(12)                    # bridges two ranges
    assert t.ranges() == [[10, 14]]
    t.add(9)                     # extends left
    t.add(15)                    # extends right
    assert t.ranges() == [[9, 15]]
    t.add(17)
    assert t.ranges() == [[9, 15], [17, 17]]


@pytest.mark.exercise("kv.free_tracker")
def test_kv_free_tracker_descending_adds_and_fresh_list():
    t = FreeRangeTracker()
    for b in range(20, 0, -2):
        t.add(b)
    assert t.ranges() == [[b, b] for b in range(2, 21, 2)]
    for b in range(19, 0, -2):
        t.add(b)
    out = t.ranges()
    assert out == [[1, 20]]
    out.append([99, 99])         # caller mutating the result must not corrupt the tracker
    out[0][1] = 0
    assert t.ranges() == [[1, 20]]


@pytest.mark.exercise("kv.free_tracker")
def test_kv_free_tracker_random_vs_model():
    rng = random.Random(352)
    for hi in (10, 60, 400):
        t, seen = FreeRangeTracker(), []
        for _ in range(600):
            b = rng.randint(0, hi)
            t.add(b)
            seen.append(b)
            if rng.random() < 0.3:
                assert t.ranges() == _ranges_brute(seen)
        assert t.ranges() == _ranges_brute(seen)


# ---------------------------------------------------------------- kv.address_ranges

class _AddressModel:
    """Unit cells [x, x + 1) over a small integer universe (exact for integer endpoints)."""

    def __init__(self):
        self.cells = set()

    def add(self, left, right):
        self.cells.update(range(left, right))

    def remove(self, left, right):
        self.cells.difference_update(range(left, right))

    def query(self, left, right):
        return all(x in self.cells for x in range(left, right))


@pytest.mark.exercise("kv.address_ranges")
def test_kv_address_ranges_example():
    r = AddressRanges()
    assert r.add_range(10, 20) is None
    assert r.remove_range(14, 16) is None
    assert r.query_range(10, 14) is True
    assert r.query_range(13, 15) is False
    assert r.query_range(16, 17) is True


@pytest.mark.exercise("kv.address_ranges")
def test_kv_address_ranges_half_open_edges():
    r = AddressRanges()
    r.add_range(10, 20)
    assert r.query_range(10, 20) is True
    assert r.query_range(19, 20) is True
    assert r.query_range(20, 21) is False
    assert r.query_range(9, 10) is False
    assert r.query_range(9, 11) is False
    assert r.query_range(19, 21) is False


@pytest.mark.exercise("kv.address_ranges")
def test_kv_address_ranges_touching_adds_merge():
    r = AddressRanges()
    r.add_range(10, 20)
    r.add_range(20, 30)
    assert r.query_range(10, 30) is True
    r.add_range(40, 50)
    assert r.query_range(10, 50) is False
    r.add_range(25, 45)
    assert r.query_range(10, 50) is True


@pytest.mark.exercise("kv.address_ranges")
def test_kv_address_ranges_empty_and_remove_uncovered():
    r = AddressRanges()
    assert r.query_range(1, 2) is False
    r.remove_range(1, 100)
    assert r.query_range(1, 2) is False
    r.add_range(5, 8)
    r.remove_range(1, 5)          # touches the left edge only
    r.remove_range(8, 100)        # touches the right edge only
    assert r.query_range(5, 8) is True


@pytest.mark.exercise("kv.address_ranges")
def test_kv_address_ranges_remove_spanning_and_splitting():
    r = AddressRanges()
    r.add_range(1, 5)
    r.add_range(10, 15)
    r.add_range(20, 25)
    r.remove_range(3, 22)         # trims the first, deletes the second, trims the third
    assert r.query_range(1, 3) is True
    assert r.query_range(2, 4) is False
    assert r.query_range(10, 11) is False
    assert r.query_range(21, 22) is False
    assert r.query_range(22, 25) is True
    r.add_range(1, 1_000_000_000)
    assert r.query_range(1, 1_000_000_000) is True
    r.remove_range(999_999_999, 1_000_000_000)
    assert r.query_range(1, 999_999_999) is True
    assert r.query_range(999_999_998, 1_000_000_000) is False


@pytest.mark.exercise("kv.address_ranges")
def test_kv_address_ranges_readd_inside_and_over():
    r = AddressRanges()
    r.add_range(10, 20)
    r.add_range(12, 15)           # fully inside: nothing changes
    assert r.query_range(10, 20) is True
    r.remove_range(12, 15)
    r.add_range(5, 25)            # covers everything again
    assert r.query_range(5, 25) is True
    assert r.query_range(4, 5) is False
    assert r.query_range(25, 26) is False


@pytest.mark.exercise("kv.address_ranges")
def test_kv_address_ranges_random_vs_model():
    rng = random.Random(715)
    for universe in (8, 30, 80):
        r, model = AddressRanges(), _AddressModel()
        for _ in range(700):
            left = rng.randint(1, universe - 1)
            right = rng.randint(left + 1, universe)
            op = rng.random()
            if op < 0.35:
                r.add_range(left, right)
                model.add(left, right)
            elif op < 0.6:
                r.remove_range(left, right)
                model.remove(left, right)
            else:
                assert r.query_range(left, right) is model.query(left, right), (left, right)


# ---------------------------------------------------------------- kv.address_ranges: address 0 is valid

@pytest.mark.exercise("kv.address_ranges")
def test_kv_address_ranges_zero_address():
    r = AddressRanges()
    r.add_range(0, 4)
    assert r.query_range(0, 1) is True
    assert r.query_range(0, 4) is True
    assert r.query_range(3, 5) is False
    r.remove_range(0, 1)
    assert r.query_range(0, 1) is False
    assert r.query_range(1, 4) is True


@pytest.mark.exercise("kv.address_ranges")
def test_kv_address_ranges_random_vs_model_from_zero():
    rng = random.Random(7150)
    for universe in (6, 40):
        r, model = AddressRanges(), _AddressModel()
        for _ in range(600):
            left = rng.randint(0, universe - 1)
            right = rng.randint(left + 1, universe)
            op = rng.random()
            if op < 0.35:
                r.add_range(left, right)
                model.add(left, right)
            elif op < 0.6:
                r.remove_range(left, right)
                model.remove(left, right)
            else:
                assert r.query_range(left, right) is model.query(left, right), (left, right)
