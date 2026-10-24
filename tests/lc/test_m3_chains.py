"""M3 core exercises: KV block chains, free lists and the LRU block cache."""
import random

import pytest

from nanoserve.common.nodes import (
    RandomListNode,
    chain_to_list,
    list_to_chain,
    random_chain_from_pairs,
    random_chain_to_pairs,
)
from nanoserve.kvcache.block_table import (
    fork_chain,
    has_cycle,
    partition_by_heat,
)
from nanoserve.kvcache.free_list import (
    drop_double_freed,
    merge_free_lists,
    merge_k_free_lists,
    sort_free_list,
)
from nanoserve.kvcache.lru import LRUBlockCache


def _nodes(head):
    out = []
    while head is not None:
        out.append(head)
        head = head.next
    return out


# ---------------------------------------------------------------- kv.lru

class _LRUModel:
    def __init__(self, capacity):
        self.cap = capacity
        self.d = {}  # insertion order == recency order (oldest first)

    def get(self, key):
        if key not in self.d:
            return -1
        v = self.d.pop(key)
        self.d[key] = v
        return v

    def put(self, key, value):
        self.d.pop(key, None)
        self.d[key] = value
        if len(self.d) > self.cap:
            del self.d[next(iter(self.d))]


@pytest.mark.exercise("kv.lru")
def test_kv_lru_example():
    c = LRUBlockCache(2)
    assert c.put(1, 1) is None
    c.put(2, 2)
    assert c.get(1) == 1
    c.put(3, 3)
    assert c.get(2) == -1
    c.put(4, 4)
    assert c.get(1) == -1
    assert c.get(3) == 3
    assert c.get(4) == 4


@pytest.mark.exercise("kv.lru")
def test_kv_lru_capacity_one():
    c = LRUBlockCache(1)
    assert c.get(5) == -1
    c.put(2, 1)
    assert c.get(2) == 1
    c.put(3, 2)
    assert c.get(2) == -1
    assert c.get(3) == 2


@pytest.mark.exercise("kv.lru")
def test_kv_lru_update_refreshes_recency():
    c = LRUBlockCache(2)
    c.put(2, 1)
    c.put(1, 1)
    c.put(2, 3)  # update: 2 becomes most recent, 1 is now LRU
    c.put(4, 1)  # evicts 1
    assert c.get(1) == -1
    assert c.get(2) == 3
    assert c.get(4) == 1


@pytest.mark.exercise("kv.lru")
def test_kv_lru_miss_does_not_change_state():
    c = LRUBlockCache(2)
    c.put(1, 10)
    c.put(2, 20)
    assert c.get(3) == -1
    c.put(3, 30)  # 1 is LRU and gets evicted
    assert c.get(1) == -1
    assert c.get(2) == 20
    assert c.get(3) == 30


@pytest.mark.exercise("kv.lru")
def test_kv_lru_get_refreshes_recency():
    c = LRUBlockCache(3)
    for k in (1, 2, 3):
        c.put(k, k * 100)
    assert c.get(1) == 100
    c.put(4, 400)  # evicts 2
    assert c.get(2) == -1
    c.put(5, 500)  # evicts 3
    assert c.get(3) == -1
    assert [c.get(k) for k in (1, 4, 5)] == [100, 400, 500]


@pytest.mark.exercise("kv.lru")
def test_kv_lru_randomized():
    rng = random.Random(146)
    for cap in (1, 2, 3, 7, 20):
        c, m = LRUBlockCache(cap), _LRUModel(cap)
        for _ in range(1500):
            k = rng.randrange(30)
            if rng.random() < 0.5:
                assert c.get(k) == m.get(k)
            else:
                v = rng.randrange(1000)
                c.put(k, v)
                m.put(k, v)


# ---------------------------------------------------------------- kv.fork

def _check_fork(pairs):
    head = random_chain_from_pairs(pairs)
    orig_nodes = _nodes(head)
    orig_ids = {id(n) for n in orig_nodes}
    orig_snapshot = [(n.val, n.next, n.random) for n in orig_nodes]
    copy = fork_chain(head)
    if not pairs:
        assert copy is None
        return
    copy_nodes = _nodes(copy)
    copy_ids = {id(n) for n in copy_nodes}
    assert not (orig_ids & copy_ids), "copy reuses nodes of the original"
    for n in copy_nodes:
        assert isinstance(n, RandomListNode)
        assert n.random is None or id(n.random) in copy_ids, "random points outside the copy"
    assert random_chain_to_pairs(copy) == pairs
    # original untouched
    assert [(n.val, n.next, n.random) for n in orig_nodes] == orig_snapshot
    assert random_chain_to_pairs(head) == pairs


@pytest.mark.exercise("kv.fork")
def test_kv_fork_example():
    _check_fork([[7, None], [13, 0], [11, 4], [10, 2], [1, 0]])


@pytest.mark.exercise("kv.fork")
def test_kv_fork_small():
    _check_fork([[1, 1], [2, 1]])
    _check_fork([[3, None], [3, 0], [3, None]])


@pytest.mark.exercise("kv.fork")
def test_kv_fork_empty_and_single():
    _check_fork([])
    _check_fork([[5, None]])
    _check_fork([[5, 0]])


@pytest.mark.exercise("kv.fork")
def test_kv_fork_randomized():
    rng = random.Random(138)
    for _ in range(40):
        n = rng.randrange(1, 60)
        pairs = [[rng.randrange(-50, 50), rng.choice([None, rng.randrange(n)])] for _ in range(n)]
        _check_fork(pairs)


# ---------------------------------------------------------------- kv.has_cycle

def _cyclic(values, pos):
    head = list_to_chain(values)
    if pos >= 0:
        nodes = _nodes(head)
        nodes[-1].next = nodes[pos]
    return head


@pytest.mark.exercise("kv.has_cycle")
def test_kv_has_cycle_examples():
    assert has_cycle(_cyclic([3, 2, 0, -4], 1)) is True
    assert has_cycle(_cyclic([1, 2], 0)) is True
    assert has_cycle(_cyclic([1], -1)) is False


@pytest.mark.exercise("kv.has_cycle")
def test_kv_has_cycle_empty_and_self_loop():
    assert has_cycle(None) is False
    assert has_cycle(_cyclic([1], 0)) is True


@pytest.mark.exercise("kv.has_cycle")
def test_kv_has_cycle_no_cycle_long():
    head = list_to_chain(range(10_000))
    assert has_cycle(head) is False
    assert chain_to_list(head) == list(range(10_000))


@pytest.mark.exercise("kv.has_cycle")
def test_kv_has_cycle_various_positions():
    rng = random.Random(141)
    for _ in range(50):
        n = rng.randrange(1, 300)
        pos = rng.randrange(-1, n)
        vals = [rng.randrange(-5, 5) for _ in range(n)]  # duplicates: values do not identify nodes
        assert has_cycle(_cyclic(vals, pos)) is (pos >= 0)


# ---------------------------------------------------------------- kv.partition_hot

def _partition_oracle(vals, x):
    return [v for v in vals if v < x] + [v for v in vals if v >= x]


@pytest.mark.exercise("kv.partition_hot")
def test_kv_partition_hot_examples():
    assert chain_to_list(partition_by_heat(list_to_chain([1, 4, 3, 2, 5, 2]), 3)) == [1, 2, 2, 4, 3, 5]
    assert chain_to_list(partition_by_heat(list_to_chain([2, 1]), 2)) == [1, 2]


@pytest.mark.exercise("kv.partition_hot")
def test_kv_partition_hot_empty_and_single():
    assert partition_by_heat(None, 0) is None
    assert chain_to_list(partition_by_heat(list_to_chain([1]), 0)) == [1]


@pytest.mark.exercise("kv.partition_hot")
def test_kv_partition_hot_all_one_side_and_negatives():
    assert chain_to_list(partition_by_heat(list_to_chain([3, 1, 2]), 10)) == [3, 1, 2]
    assert chain_to_list(partition_by_heat(list_to_chain([3, 1, 2]), -10)) == [3, 1, 2]
    assert chain_to_list(partition_by_heat(list_to_chain([0, -3, 5, -1, -3]), -1)) == [-3, -3, 0, 5, -1]


@pytest.mark.exercise("kv.partition_hot")
def test_kv_partition_hot_randomized_stable():
    rng = random.Random(86)
    for _ in range(100):
        n = rng.randrange(0, 40)
        vals = [rng.randrange(-200, 201) for _ in range(n)]
        x = rng.randrange(-200, 201)
        head = list_to_chain(vals)
        nodes = _nodes(head)
        out = partition_by_heat(head, x)
        assert chain_to_list(out) == _partition_oracle(vals, x)
        # stability at node level (duplicates must keep their original relative order)
        expect_nodes = [nd for nd in nodes if nd.val < x] + [nd for nd in nodes if nd.val >= x]
        assert all(a is b for a, b in zip(_nodes(out), expect_nodes))


# ---------------------------------------------------------------- kv.merge_free

@pytest.mark.exercise("kv.merge_free")
def test_kv_merge_free_example():
    out = merge_free_lists(list_to_chain([1, 2, 4]), list_to_chain([1, 3, 4]))
    assert chain_to_list(out) == [1, 1, 2, 3, 4, 4]


@pytest.mark.exercise("kv.merge_free")
def test_kv_merge_free_empty():
    assert merge_free_lists(None, None) is None
    assert chain_to_list(merge_free_lists(None, list_to_chain([0]))) == [0]
    assert chain_to_list(merge_free_lists(list_to_chain([0]), None)) == [0]


@pytest.mark.exercise("kv.merge_free")
def test_kv_merge_free_disjoint_and_negatives():
    assert chain_to_list(merge_free_lists(list_to_chain([5, 6, 7]), list_to_chain([-3, -1]))) == [-3, -1, 5, 6, 7]
    assert chain_to_list(merge_free_lists(list_to_chain([2, 2]), list_to_chain([2]))) == [2, 2, 2]


@pytest.mark.exercise("kv.merge_free")
def test_kv_merge_free_randomized():
    rng = random.Random(21)
    for _ in range(100):
        a = sorted(rng.randrange(-100, 101) for _ in range(rng.randrange(0, 51)))
        b = sorted(rng.randrange(-100, 101) for _ in range(rng.randrange(0, 51)))
        assert chain_to_list(merge_free_lists(list_to_chain(a), list_to_chain(b))) == sorted(a + b)


# ---------------------------------------------------------------- kv.merge_free_k

@pytest.mark.exercise("kv.merge_free_k")
def test_kv_merge_free_k_example():
    lists = [list_to_chain([1, 4, 5]), list_to_chain([1, 3, 4]), list_to_chain([2, 6])]
    assert chain_to_list(merge_k_free_lists(lists)) == [1, 1, 2, 3, 4, 4, 5, 6]


@pytest.mark.exercise("kv.merge_free_k")
def test_kv_merge_free_k_empty():
    assert merge_k_free_lists([]) is None
    assert merge_k_free_lists([None]) is None
    assert merge_k_free_lists([None, None, None]) is None


@pytest.mark.exercise("kv.merge_free_k")
def test_kv_merge_free_k_single_and_mixed_empty():
    assert chain_to_list(merge_k_free_lists([list_to_chain([-2, 0, 9])])) == [-2, 0, 9]
    assert chain_to_list(merge_k_free_lists([None, list_to_chain([3]), None, list_to_chain([1, 3])])) == [1, 3, 3]


@pytest.mark.exercise("kv.merge_free_k")
def test_kv_merge_free_k_randomized():
    rng = random.Random(23)
    for _ in range(20):
        k = rng.randrange(0, 60)
        raw = [sorted(rng.randrange(-10_000, 10_001) for _ in range(rng.randrange(0, 30))) for _ in range(k)]
        out = merge_k_free_lists([list_to_chain(r) for r in raw])
        assert chain_to_list(out) == sorted(v for r in raw for v in r)


@pytest.mark.exercise("kv.merge_free_k")
def test_kv_merge_free_k_many_lists():
    rng = random.Random(2323)
    raw = [[rng.randrange(-10_000, 10_001)] for _ in range(5000)] + [[] for _ in range(5000)]
    rng.shuffle(raw)
    out = merge_k_free_lists([list_to_chain(r) for r in raw])
    assert chain_to_list(out) == sorted(v for r in raw for v in r)


# ---------------------------------------------------------------- kv.sort_free

@pytest.mark.exercise("kv.sort_free")
def test_kv_sort_free_examples():
    assert chain_to_list(sort_free_list(list_to_chain([4, 2, 1, 3]))) == [1, 2, 3, 4]
    assert chain_to_list(sort_free_list(list_to_chain([-1, 5, 3, 4, 0]))) == [-1, 0, 3, 4, 5]


@pytest.mark.exercise("kv.sort_free")
def test_kv_sort_free_empty_and_single():
    assert sort_free_list(None) is None
    assert chain_to_list(sort_free_list(list_to_chain([7]))) == [7]


@pytest.mark.exercise("kv.sort_free")
def test_kv_sort_free_duplicates_sorted_and_reversed():
    assert chain_to_list(sort_free_list(list_to_chain([3, 1, 3, 1, 2]))) == [1, 1, 2, 3, 3]
    assert chain_to_list(sort_free_list(list_to_chain([1, 2, 3, 4]))) == [1, 2, 3, 4]
    assert chain_to_list(sort_free_list(list_to_chain([4, 3, 2, 1]))) == [1, 2, 3, 4]


@pytest.mark.exercise("kv.sort_free")
def test_kv_sort_free_randomized_2000():
    rng = random.Random(148)
    vals = [rng.randrange(-100_000, 100_001) for _ in range(2000)]
    head = list_to_chain(vals)
    ids = {id(x) for x in _nodes(head)}
    out = sort_free_list(head)
    assert chain_to_list(out) == sorted(vals)
    assert {id(x) for x in _nodes(out)} == ids


# ---------------------------------------------------------------- kv.drop_double_free

def _drop_dup_oracle(vals):
    return [v for v in vals if vals.count(v) == 1]


@pytest.mark.exercise("kv.drop_double_free")
def test_kv_drop_double_free_examples():
    assert chain_to_list(drop_double_freed(list_to_chain([1, 2, 3, 3, 4, 4, 5]))) == [1, 2, 5]
    assert chain_to_list(drop_double_freed(list_to_chain([1, 1, 1, 2, 3]))) == [2, 3]


@pytest.mark.exercise("kv.drop_double_free")
def test_kv_drop_double_free_empty_and_all_dup():
    assert drop_double_freed(None) is None
    assert drop_double_freed(list_to_chain([1, 1])) is None
    assert drop_double_freed(list_to_chain([-1, -1, 2, 2, 2])) is None


@pytest.mark.exercise("kv.drop_double_free")
def test_kv_drop_double_free_no_dup_and_tail_dup():
    assert chain_to_list(drop_double_freed(list_to_chain([1]))) == [1]
    assert chain_to_list(drop_double_freed(list_to_chain([-3, 0, 4]))) == [-3, 0, 4]
    assert chain_to_list(drop_double_freed(list_to_chain([1, 2, 3, 3]))) == [1, 2]


@pytest.mark.exercise("kv.drop_double_free")
def test_kv_drop_double_free_randomized():
    rng = random.Random(82)
    for _ in range(150):
        vals = sorted(rng.randrange(-10, 11) for _ in range(rng.randrange(0, 40)))
        assert chain_to_list(drop_double_freed(list_to_chain(vals))) == _drop_dup_oracle(vals)


# ---------------------------------------------------------------- widened ranges (block ids of a real pool)

@pytest.mark.exercise("kv.fork")
def test_kv_fork_long_back_linked_chain():
    # block table of 3000 blocks; every random points at the previous node (a back link)
    n = 3000
    pairs = [[4096 + i, i - 1 if i else None] for i in range(n)]
    _check_fork(pairs)


@pytest.mark.exercise("kv.fork")
def test_kv_fork_randomized_large_values():
    rng = random.Random(1381)
    for _ in range(20):
        n = rng.randrange(0, 400)
        pairs = [[rng.randrange(0, 10**6), rng.choice([None] + list(range(n)))] for _ in range(n)]
        _check_fork(pairs)


@pytest.mark.exercise("kv.merge_free")
def test_kv_merge_free_large_ids():
    out = merge_free_lists(list_to_chain([7, 4096]), list_to_chain([-3, 512]))
    assert chain_to_list(out) == [-3, 7, 512, 4096]


@pytest.mark.exercise("kv.merge_free")
def test_kv_merge_free_randomized_wide():
    rng = random.Random(2121)
    for _ in range(30):
        a = sorted(rng.randrange(-10**6, 10**6) for _ in range(rng.randrange(0, 600)))
        b = sorted(rng.randrange(-10**6, 10**6) for _ in range(rng.randrange(0, 600)))
        assert chain_to_list(merge_free_lists(list_to_chain(a), list_to_chain(b))) == sorted(a + b)


@pytest.mark.exercise("kv.drop_double_free")
def test_kv_drop_double_free_large_ids():
    out = drop_double_freed(list_to_chain([998, 4096, 4096, 5000]))
    assert chain_to_list(out) == [998, 5000]


@pytest.mark.exercise("kv.drop_double_free")
def test_kv_drop_double_free_randomized_wide():
    rng = random.Random(8282)
    for _ in range(30):
        pool = [rng.randrange(-10**6, 10**6) for _ in range(rng.randrange(1, 300))]
        vals = sorted(rng.choice(pool) for _ in range(rng.randrange(0, 2000)))
        assert chain_to_list(drop_double_freed(list_to_chain(vals))) == _drop_dup_oracle_fast(vals)


def _drop_dup_oracle_fast(vals):
    from collections import Counter
    c = Counter(vals)
    return [v for v in vals if c[v] == 1]
