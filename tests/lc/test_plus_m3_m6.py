"""Plus exercises for milestones M3–M6: KV cache structures, prefix cache, index, IR, config, eval, decode."""
import itertools
import random
import re
from collections import deque

import pytest

from nanoserve.common.nodes import TreeNode, tree_to_level
from nanoserve.config.arith import eval_arith
from nanoserve.config.template import expand_template
from nanoserve.decode.regex import full_match
from nanoserve.eval.rouge import lcs_length
from nanoserve.index.fenwick import RangeCounter
from nanoserve.ir.latency import broadcast_latency, critical_path_time
from nanoserve.ir.topology import count_device_groups
from nanoserve.kvcache.lfu import LFUBlockCache
from nanoserve.kvcache.memalloc import MemoryAllocator
from nanoserve.kvcache.refcount import RefCounter
from nanoserve.kvcache.ring_queue import RingQueue
from nanoserve.kvcache.snapshot import SnapshotTable
from nanoserve.kvcache.versioned import VersionedStore
from nanoserve.prefix.codec import TreeCodec
from nanoserve.prefix.hit_sum import PrefixHitSum


# ---------------------------------------------------------------- kv.lfu

class _LFUModel:
    def __init__(self, capacity):
        self.cap = capacity
        self.d = {}  # key -> [value, freq, last_tick]
        self.tick = 0

    def get(self, key):
        self.tick += 1
        if key not in self.d:
            return -1
        e = self.d[key]
        e[1] += 1
        e[2] = self.tick
        return e[0]

    def put(self, key, value):
        self.tick += 1
        if key in self.d:
            e = self.d[key]
            e[0] = value
            e[1] += 1
            e[2] = self.tick
            return
        if len(self.d) >= self.cap:
            victim = min(self.d, key=lambda k: (self.d[k][1], self.d[k][2]))
            del self.d[victim]
        self.d[key] = [value, 1, self.tick]


@pytest.mark.exercise("kv.lfu")
def test_kv_lfu_example():
    c = LFUBlockCache(2)
    c.put(1, 1)
    c.put(2, 2)
    assert c.get(1) == 1
    c.put(3, 3)             # evicts 2 (freq 1)
    assert c.get(2) == -1
    assert c.get(3) == 3
    c.put(4, 4)             # 1 and 3 both freq 2; 1 is least recent
    assert c.get(1) == -1
    assert c.get(3) == 3
    assert c.get(4) == 4


@pytest.mark.exercise("kv.lfu")
def test_kv_lfu_capacity_one():
    c = LFUBlockCache(1)
    c.put(2, 1)
    assert c.get(2) == 1
    c.put(3, 2)
    assert c.get(2) == -1
    assert c.get(3) == 2


@pytest.mark.exercise("kv.lfu")
def test_kv_lfu_update_counts_as_use():
    c = LFUBlockCache(2)
    c.put(1, 10)
    c.put(2, 20)
    c.put(1, 11)            # key 1 now freq 2
    c.put(3, 30)            # evicts 2
    assert c.get(2) == -1
    assert c.get(1) == 11
    assert c.get(3) == 30


@pytest.mark.exercise("kv.lfu")
def test_kv_lfu_miss_does_not_change_state():
    c = LFUBlockCache(2)
    c.put(0, 0)
    c.put(1, 1)
    assert c.get(5) == -1
    c.get(0)
    c.put(2, 2)             # evicts 1
    assert c.get(1) == -1
    assert c.get(0) == 0
    assert c.get(2) == 2


@pytest.mark.exercise("kv.lfu")
def test_kv_lfu_random_vs_model():
    rng = random.Random(460)
    for cap in (1, 2, 3, 5, 8):
        c, m = LFUBlockCache(cap), _LFUModel(cap)
        for _ in range(600):
            k = rng.randrange(12)
            if rng.random() < 0.5:
                assert c.get(k) == m.get(k)
            else:
                v = rng.randrange(1000)
                c.put(k, v)
                m.put(k, v)


# ---------------------------------------------------------------- kv.ring_queue

@pytest.mark.exercise("kv.ring_queue")
def test_kv_ring_queue_example():
    q = RingQueue(3)
    assert q.enqueue(1) is True
    assert q.enqueue(2) is True
    assert q.enqueue(3) is True
    assert q.enqueue(4) is False
    assert q.rear() == 3
    assert q.is_full() is True
    assert q.dequeue() is True
    assert q.enqueue(4) is True
    assert q.rear() == 4


@pytest.mark.exercise("kv.ring_queue")
def test_kv_ring_queue_empty():
    q = RingQueue(2)
    assert q.is_empty() is True
    assert q.is_full() is False
    assert q.front() == -1
    assert q.rear() == -1
    assert q.dequeue() is False


@pytest.mark.exercise("kv.ring_queue")
def test_kv_ring_queue_capacity_one():
    q = RingQueue(1)
    assert q.enqueue(7) is True
    assert q.is_full() and not q.is_empty()
    assert q.front() == 7 and q.rear() == 7
    assert q.enqueue(8) is False
    assert q.dequeue() is True
    assert q.is_empty()
    assert q.front() == -1
    assert q.enqueue(9) is True
    assert q.front() == 9


@pytest.mark.exercise("kv.ring_queue")
def test_kv_ring_queue_wraparound():
    q = RingQueue(3)
    for x in (1, 2, 3):
        q.enqueue(x)
    q.dequeue()
    q.dequeue()
    q.enqueue(4)
    q.enqueue(5)
    assert q.front() == 3 and q.rear() == 5 and q.is_full()
    got = []
    while not q.is_empty():
        got.append(q.front())
        q.dequeue()
    assert got == [3, 4, 5]


@pytest.mark.exercise("kv.ring_queue")
def test_kv_ring_queue_random_vs_deque():
    rng = random.Random(622)
    for k in (1, 2, 5):
        q, m = RingQueue(k), deque()
        for _ in range(400):
            op = rng.randrange(6)
            if op == 0:
                x = rng.randrange(100)
                ok = len(m) < k
                if ok:
                    m.append(x)
                assert q.enqueue(x) is ok
            elif op == 1:
                ok = bool(m)
                if ok:
                    m.popleft()
                assert q.dequeue() is ok
            elif op == 2:
                assert q.front() == (m[0] if m else -1)
            elif op == 3:
                assert q.rear() == (m[-1] if m else -1)
            elif op == 4:
                assert q.is_empty() is (len(m) == 0)
            else:
                assert q.is_full() is (len(m) == k)


# ---------------------------------------------------------------- kv.snapshot

@pytest.mark.exercise("kv.snapshot")
def test_kv_snapshot_example():
    t = SnapshotTable(3)
    t.set(0, 5)
    assert t.snap() == 0
    t.set(0, 6)
    assert t.get(0, 0) == 5


@pytest.mark.exercise("kv.snapshot")
def test_kv_snapshot_initial_zero_and_ids():
    t = SnapshotTable(2)
    assert t.snap() == 0
    assert t.snap() == 1
    assert t.get(0, 0) == 0
    assert t.get(1, 1) == 0
    t.set(1, 4)
    assert t.snap() == 2
    assert t.get(1, 1) == 0
    assert t.get(1, 2) == 4


@pytest.mark.exercise("kv.snapshot")
def test_kv_snapshot_multiple_sets_between_snaps():
    t = SnapshotTable(1)
    t.set(0, 1)
    t.set(0, 2)
    t.set(0, 3)
    assert t.snap() == 0
    assert t.snap() == 1
    t.set(0, 9)
    assert t.snap() == 2
    assert [t.get(0, s) for s in range(3)] == [3, 3, 9]


@pytest.mark.exercise("kv.snapshot")
def test_kv_snapshot_set_back_to_zero():
    t = SnapshotTable(4)
    t.set(3, 15)
    assert t.snap() == 0
    t.set(3, 0)
    assert t.snap() == 1
    assert t.get(3, 0) == 15
    assert t.get(3, 1) == 0
    assert t.get(2, 1) == 0


@pytest.mark.exercise("kv.snapshot")
def test_kv_snapshot_random_vs_model():
    rng = random.Random(1146)
    n = 6
    t = SnapshotTable(n)
    cur = [0] * n
    snaps = []
    for _ in range(800):
        r = rng.random()
        if r < 0.5:
            i, v = rng.randrange(n), rng.randrange(-5, 50)
            t.set(i, v)
            cur[i] = v
        elif r < 0.65:
            assert t.snap() == len(snaps)
            snaps.append(cur[:])
        elif snaps:
            s, i = rng.randrange(len(snaps)), rng.randrange(n)
            assert t.get(i, s) == snaps[s][i]


# ---------------------------------------------------------------- kv.versioned

@pytest.mark.exercise("kv.versioned")
def test_kv_versioned_example():
    s = VersionedStore()
    s.set("foo", "bar", 1)
    assert s.get("foo", 1) == "bar"
    assert s.get("foo", 3) == "bar"
    s.set("foo", "bar2", 4)
    assert s.get("foo", 4) == "bar2"
    assert s.get("foo", 5) == "bar2"
    assert s.get("foo", 3) == "bar"


@pytest.mark.exercise("kv.versioned")
def test_kv_versioned_before_first_version():
    s = VersionedStore()
    s.set("love", "high", 10)
    s.set("love", "low", 20)
    assert s.get("love", 5) == ""
    assert s.get("love", 10) == "high"
    assert s.get("love", 15) == "high"
    assert s.get("love", 20) == "low"
    assert s.get("love", 25) == "low"


@pytest.mark.exercise("kv.versioned")
def test_kv_versioned_missing_key():
    s = VersionedStore()
    assert s.get("x", 100) == ""
    s.set("a", "1", 1)
    assert s.get("b", 100) == ""


@pytest.mark.exercise("kv.versioned")
def test_kv_versioned_keys_independent():
    s = VersionedStore()
    s.set("a", "a1", 1)
    s.set("b", "b2", 2)
    s.set("a", "a3", 3)
    assert s.get("b", 1) == ""
    assert s.get("a", 2) == "a1"
    assert s.get("b", 3) == "b2"
    assert s.get("a", 3) == "a3"


@pytest.mark.exercise("kv.versioned")
def test_kv_versioned_random_vs_model():
    rng = random.Random(981)
    s = VersionedStore()
    hist = []  # (key, value, ts)
    ts = 0
    for _ in range(600):
        if rng.random() < 0.4:
            ts += rng.randint(1, 3)
            k, v = rng.choice("abcd"), str(rng.randrange(1000))
            s.set(k, v, ts)
            hist.append((k, v, ts))
        else:
            k, q = rng.choice("abcde"), rng.randint(0, ts + 2)
            want = ""
            for hk, hv, hts in hist:
                if hk == k and hts <= q:
                    want = hv
            assert s.get(k, q) == want


# ---------------------------------------------------------------- kv.mem_alloc

class _AllocModel:
    def __init__(self, n):
        self.owner = [0] * n

    def allocate(self, size, owner):
        free = "".join("0" if o == 0 else "1" for o in self.owner)
        start = free.find("0" * size)
        if start >= 0:
            for i in range(start, start + size):
                self.owner[i] = owner
        return start

    def free(self, owner):
        cnt = self.owner.count(owner)
        self.owner = [0 if o == owner else o for o in self.owner]
        return cnt


@pytest.mark.exercise("kv.mem_alloc")
def test_kv_mem_alloc_example():
    m = MemoryAllocator(10)
    assert m.allocate(1, 1) == 0
    assert m.allocate(1, 2) == 1
    assert m.allocate(1, 3) == 2
    assert m.free(2) == 1
    assert m.allocate(3, 4) == 3
    assert m.allocate(1, 1) == 1
    assert m.allocate(1, 1) == 6
    assert m.free(1) == 3
    assert m.allocate(10, 2) == -1
    assert m.free(7) == 0


@pytest.mark.exercise("kv.mem_alloc")
def test_kv_mem_alloc_exact_fill():
    m = MemoryAllocator(4)
    assert m.allocate(4, 9) == 0
    assert m.allocate(1, 1) == -1
    assert m.free(9) == 4
    assert m.allocate(5, 1) == -1
    assert m.allocate(4, 1) == 0


@pytest.mark.exercise("kv.mem_alloc")
def test_kv_mem_alloc_first_fit_skips_small_holes():
    m = MemoryAllocator(8)
    assert m.allocate(2, 1) == 0
    assert m.allocate(1, 2) == 2
    assert m.allocate(2, 3) == 3
    assert m.allocate(1, 4) == 5
    assert m.free(1) == 2       # hole [0,2)
    assert m.free(3) == 2       # hole [3,5)
    assert m.allocate(3, 5) == -1   # free runs are 2, 2, 2: none fits 3
    assert m.allocate(2, 6) == 0
    assert m.allocate(2, 7) == 3
    assert m.allocate(2, 8) == 6
    assert m.allocate(1, 8) == -1


@pytest.mark.exercise("kv.mem_alloc")
def test_kv_mem_alloc_failed_allocate_changes_nothing():
    m = MemoryAllocator(3)
    assert m.allocate(1, 1) == 0
    assert m.allocate(1, 2) == 1
    assert m.allocate(2, 3) == -1
    assert m.free(3) == 0
    assert m.allocate(1, 3) == 2


@pytest.mark.exercise("kv.mem_alloc")
def test_kv_mem_alloc_random_vs_model():
    rng = random.Random(2502)
    for n in (1, 7, 30):
        a, m = MemoryAllocator(n), _AllocModel(n)
        for _ in range(400):
            owner = rng.randint(1, 6)
            if rng.random() < 0.65:
                size = rng.randint(1, max(1, n // 3))
                assert a.allocate(size, owner) == m.allocate(size, owner)
            else:
                assert a.free(owner) == m.free(owner)


# ---------------------------------------------------------------- kv.refcount

@pytest.mark.exercise("kv.refcount")
def test_kv_refcount_example():
    r = RefCounter()
    r.inc("hello")
    r.inc("hello")
    assert r.max_key() == "hello"
    assert r.min_key() == "hello"
    r.inc("leet")
    assert r.max_key() == "hello"
    assert r.min_key() == "leet"


@pytest.mark.exercise("kv.refcount")
def test_kv_refcount_empty():
    r = RefCounter()
    assert r.max_key() == ""
    assert r.min_key() == ""
    r.inc("a")
    r.dec("a")
    assert r.max_key() == ""
    assert r.min_key() == ""


@pytest.mark.exercise("kv.refcount")
def test_kv_refcount_dec_moves_down():
    r = RefCounter()
    for _ in range(3):
        r.inc("a")
    r.inc("b")
    r.inc("b")
    assert r.max_key() == "a" and r.min_key() == "b"
    r.dec("a")
    r.dec("a")
    assert r.max_key() == "b" and r.min_key() == "a"
    r.dec("a")              # a removed
    assert r.max_key() == "b" and r.min_key() == "b"


@pytest.mark.exercise("kv.refcount")
def test_kv_refcount_ties():
    r = RefCounter()
    for k in ("x", "y", "z"):
        r.inc(k)
    assert r.max_key() in {"x", "y", "z"}
    assert r.min_key() in {"x", "y", "z"}
    r.inc("y")
    assert r.max_key() == "y"
    assert r.min_key() in {"x", "z"}


@pytest.mark.exercise("kv.refcount")
def test_kv_refcount_random_vs_model():
    rng = random.Random(432)
    r, cnt = RefCounter(), {}
    keys = [f"b{i}" for i in range(8)]
    for _ in range(1500):
        op = rng.random()
        if op < 0.45 or not cnt:
            k = rng.choice(keys)
            r.inc(k)
            cnt[k] = cnt.get(k, 0) + 1
        elif op < 0.8:
            k = rng.choice(sorted(cnt))
            r.dec(k)
            cnt[k] -= 1
            if cnt[k] == 0:
                del cnt[k]
        if cnt:
            hi, lo = max(cnt.values()), min(cnt.values())
            assert r.max_key() in {k for k, v in cnt.items() if v == hi}
            assert r.min_key() in {k for k, v in cnt.items() if v == lo}
        else:
            assert r.max_key() == "" and r.min_key() == ""


# ---------------------------------------------------------------- prefix.codec

def _tree(level):
    """Level order (None holes) -> tree; local builder independent of shared helpers."""
    if not level or level[0] is None:
        return None
    nodes = [None if v is None else TreeNode(v) for v in level]
    root, parents, i = nodes[0], deque([nodes[0]]), 1
    while parents and i < len(nodes):
        p = parents.popleft()
        for side in ("left", "right"):
            if i < len(nodes):
                if nodes[i] is not None:
                    setattr(p, side, nodes[i])
                    parents.append(nodes[i])
                i += 1
    return root


def _roundtrip(level):
    c = TreeCodec()
    data = c.serialize(_tree(level))
    assert isinstance(data, str)
    return tree_to_level(TreeCodec().deserialize(data))


@pytest.mark.exercise("prefix.codec")
def test_prefix_codec_example():
    lv = [1, 2, 3, None, None, 4, 5]
    assert _roundtrip(lv) == lv


@pytest.mark.exercise("prefix.codec")
def test_prefix_codec_empty_and_single():
    c = TreeCodec()
    assert c.deserialize(c.serialize(None)) is None
    assert _roundtrip([0]) == [0]
    assert _roundtrip([-7]) == [-7]


@pytest.mark.exercise("prefix.codec")
def test_prefix_codec_negatives_and_duplicates():
    lv = [-1, -1, -1, None, 1000, -1000, None, 5, None, 5, 5]
    assert _roundtrip(lv) == lv


@pytest.mark.exercise("prefix.codec")
def test_prefix_codec_deep_skewed():
    depth = 3000
    root = TreeNode(0)
    cur = root
    for i in range(1, depth):
        nxt = TreeNode(-i if i % 2 else i)
        if i % 3:
            cur.right = nxt
        else:
            cur.left = nxt
        cur = nxt
    want = tree_to_level(root)
    c = TreeCodec()
    assert tree_to_level(c.deserialize(c.serialize(root))) == want


@pytest.mark.exercise("prefix.codec")
def test_prefix_codec_random_trees():
    rng = random.Random(297)
    for _ in range(60):
        size = rng.randint(1, 120)
        nodes = [TreeNode(rng.randint(-50, 50)) for _ in range(size)]
        for i in range(1, size):
            while True:
                p = nodes[rng.randrange(i)]
                side = rng.choice(("left", "right"))
                if getattr(p, side) is None:
                    setattr(p, side, nodes[i])
                    break
        want = tree_to_level(nodes[0])
        c = TreeCodec()
        s = c.serialize(nodes[0])
        assert tree_to_level(TreeCodec().deserialize(s)) == want


# ---------------------------------------------------------------- prefix.hit_sum

@pytest.mark.exercise("prefix.hit_sum")
def test_prefix_hit_sum_example():
    h = PrefixHitSum()
    h.insert("apple", 3)
    assert h.sum("ap") == 3
    h.insert("app", 2)
    assert h.sum("ap") == 5


@pytest.mark.exercise("prefix.hit_sum")
def test_prefix_hit_sum_overwrite():
    h = PrefixHitSum()
    h.insert("apple", 3)
    h.insert("apple", 2)
    assert h.sum("ap") == 2
    h.insert("apple", 0)
    assert h.sum("a") == 0


@pytest.mark.exercise("prefix.hit_sum")
def test_prefix_hit_sum_no_match_and_exact():
    h = PrefixHitSum()
    assert h.sum("a") == 0
    h.insert("a", 3)
    h.insert("b", 2)
    assert h.sum("a") == 3
    assert h.sum("c") == 0
    assert h.sum("ab") == 0


@pytest.mark.exercise("prefix.hit_sum")
def test_prefix_hit_sum_prefix_longer_than_key():
    h = PrefixHitSum()
    h.insert("aa", 3)
    assert h.sum("a") == 3
    h.insert("aaa", 5)
    assert h.sum("aaaa") == 0
    assert h.sum("aaa") == 5
    assert h.sum("aa") == 8


@pytest.mark.exercise("prefix.hit_sum")
def test_prefix_hit_sum_random_vs_model():
    rng = random.Random(677)
    h, d = PrefixHitSum(), {}
    word = lambda: "".join(rng.choice("abc") for _ in range(rng.randint(1, 4)))
    for _ in range(800):
        if rng.random() < 0.5:
            k, v = word(), rng.randrange(100)
            h.insert(k, v)
            d[k] = v
        else:
            p = word()
            assert h.sum(p) == sum(v for k, v in d.items() if k.startswith(p))


@pytest.mark.exercise("prefix.hit_sum")
def test_prefix_hit_sum_arbitrary_characters():
    h = PrefixHitSum()
    h.insert("Sys: hi!", 4)
    h.insert("Sys: héllo $5", 1)
    assert (h.sum("Sys: h"), h.sum("Sys: hé"), h.sum("sys")) == (5, 1, 0)
    h.insert("a$", 7)                   # sentinel-looking characters are ordinary characters here
    h.insert("a", 2)
    h.insert("#\n", 3)
    assert h.sum("a") == 9 and h.sum("a$") == 7 and h.sum("a$$") == 0
    assert h.sum("#") == 3 and h.sum("#\n") == 3
    h.insert("a$", 0)
    assert h.sum("a") == 2


@pytest.mark.exercise("prefix.hit_sum")
def test_prefix_hit_sum_random_mixed_alphabet():
    rng = random.Random(678)
    alphabet = "aA $#.,\n é漢\ue000"
    h, d = PrefixHitSum(), {}
    word = lambda: "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 4)))
    for _ in range(1500):
        if rng.random() < 0.5:
            k, v = word(), rng.randrange(100)
            h.insert(k, v)
            d[k] = v
        else:
            p = word()
            assert h.sum(p) == sum(v for k, v in d.items() if k.startswith(p))


# ---------------------------------------------------------------- index.range_sum

@pytest.mark.exercise("index.range_sum")
def test_index_range_sum_example():
    rc = RangeCounter([1, 3, 5])
    assert rc.sum_range(0, 2) == 9
    rc.update(1, 2)
    assert rc.sum_range(0, 2) == 8


@pytest.mark.exercise("index.range_sum")
def test_index_range_sum_single_element():
    rc = RangeCounter([-4])
    assert rc.sum_range(0, 0) == -4
    rc.update(0, 7)
    assert rc.sum_range(0, 0) == 7


@pytest.mark.exercise("index.range_sum")
def test_index_range_sum_update_is_assignment():
    rc = RangeCounter([5, 5, 5, 5])
    rc.update(2, 5)
    assert rc.sum_range(0, 3) == 20
    rc.update(2, -5)
    rc.update(2, -5)
    assert rc.sum_range(2, 2) == -5
    assert rc.sum_range(1, 3) == 5


@pytest.mark.exercise("index.range_sum")
def test_index_range_sum_does_not_alias_input():
    nums = [1, 2, 3]
    rc = RangeCounter(nums)
    nums[0] = 100
    assert rc.sum_range(0, 0) == 1
    rc.update(1, 10)
    assert rc.sum_range(0, 2) == 14


@pytest.mark.exercise("index.range_sum")
def test_index_range_sum_random_vs_model():
    rng = random.Random(307)
    for n in (1, 2, 17, 200):
        arr = [rng.randint(-100, 100) for _ in range(n)]
        rc = RangeCounter(list(arr))
        for _ in range(500):
            if rng.random() < 0.5:
                i, v = rng.randrange(n), rng.randint(-100, 100)
                rc.update(i, v)
                arr[i] = v
            else:
                l = rng.randrange(n)
                r = rng.randrange(l, n)
                assert rc.sum_range(l, r) == sum(arr[l:r + 1])


# ---------------------------------------------------------------- ir.op_latency

def _bellman_ford(edges, n, src):
    INF = float("inf")
    dist = [INF] * (n + 1)
    dist[src] = 0
    for _ in range(n - 1):
        for u, v, w in edges:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    worst = max(dist[1:])
    return -1 if worst == INF else worst


@pytest.mark.exercise("ir.op_latency")
def test_ir_op_latency_example():
    assert broadcast_latency([[2, 1, 1], [2, 3, 1], [3, 4, 1]], 4, 2) == 2


@pytest.mark.exercise("ir.op_latency")
def test_ir_op_latency_unreachable():
    assert broadcast_latency([[1, 2, 1]], 2, 1) == 1
    assert broadcast_latency([[1, 2, 1]], 2, 2) == -1
    assert broadcast_latency([], 3, 1) == -1


@pytest.mark.exercise("ir.op_latency")
def test_ir_op_latency_single_device():
    assert broadcast_latency([], 1, 1) == 0


@pytest.mark.exercise("ir.op_latency")
def test_ir_op_latency_longer_path_is_shorter():
    edges = [[1, 2, 10], [1, 3, 1], [3, 4, 1], [4, 2, 1], [2, 5, 0]]
    assert broadcast_latency(edges, 5, 1) == 3


@pytest.mark.exercise("ir.op_latency")
def test_ir_op_latency_random_vs_bellman_ford():
    rng = random.Random(743)
    for _ in range(80):
        n = rng.randint(1, 12)
        pairs = [(u, v) for u in range(1, n + 1) for v in range(1, n + 1) if u != v]
        rng.shuffle(pairs)
        edges = [[u, v, rng.randint(0, 20)] for u, v in pairs[: rng.randint(0, len(pairs))]]
        src = rng.randint(1, n)
        assert broadcast_latency(edges, n, src) == _bellman_ford(edges, n, src)


# ---------------------------------------------------------------- ir.critical_path

def _longest_finish(n, deps, cost):
    preds = [[] for _ in range(n + 1)]
    for a, b in deps:
        preds[b].append(a)
    memo = {}
    # n is small in tests, recursion depth is fine
    def finish(v):
        if v not in memo:
            memo[v] = cost[v - 1] + max((finish(u) for u in preds[v]), default=0)
        return memo[v]
    return max(finish(v) for v in range(1, n + 1))


@pytest.mark.exercise("ir.critical_path")
def test_ir_critical_path_example():
    assert critical_path_time(3, [[1, 3], [2, 3]], [3, 2, 5]) == 8


@pytest.mark.exercise("ir.critical_path")
def test_ir_critical_path_example2():
    deps = [[1, 5], [2, 5], [3, 5], [3, 4], [4, 5]]
    assert critical_path_time(5, deps, [1, 2, 3, 4, 5]) == 12


@pytest.mark.exercise("ir.critical_path")
def test_ir_critical_path_no_deps_and_single():
    assert critical_path_time(1, [], [7]) == 7
    assert critical_path_time(4, [], [3, 9, 1, 4]) == 9


@pytest.mark.exercise("ir.critical_path")
def test_ir_critical_path_chain_direction():
    # 3 -> 2 -> 1 chain: sum of all costs; direction matters only via relation semantics
    assert critical_path_time(3, [[3, 2], [2, 1]], [1, 2, 3]) == 6
    # diamond: 1 -> {2,3} -> 4
    assert critical_path_time(4, [[1, 2], [1, 3], [2, 4], [3, 4]], [2, 10, 1, 3]) == 15
    # a heavy root with no successors beats a light chain
    assert critical_path_time(3, [[1, 2]], [1, 1, 50]) == 50


@pytest.mark.exercise("ir.critical_path")
def test_ir_critical_path_random_dag():
    rng = random.Random(2050)
    for _ in range(80):
        n = rng.randint(1, 25)
        perm = list(range(1, n + 1))
        rng.shuffle(perm)
        deps = []
        for i in range(n):
            for j in range(i + 1, n):
                if rng.random() < 0.15:
                    deps.append([perm[i], perm[j]])
        rng.shuffle(deps)
        cost = [rng.randint(1, 30) for _ in range(n)]
        assert critical_path_time(n, deps, cost) == _longest_finish(n, deps, cost)


# ---------------------------------------------------------------- ir.device_groups

def _components(linked):
    n, seen, cnt = len(linked), set(), 0
    for s in range(n):
        if s in seen:
            continue
        cnt += 1
        stack = [s]
        seen.add(s)
        while stack:
            u = stack.pop()
            for v in range(n):
                if linked[u][v] and v not in seen:
                    seen.add(v)
                    stack.append(v)
    return cnt


@pytest.mark.exercise("ir.device_groups")
def test_ir_device_groups_example():
    assert count_device_groups([[1, 1, 0], [1, 1, 0], [0, 0, 1]]) == 2


@pytest.mark.exercise("ir.device_groups")
def test_ir_device_groups_all_isolated():
    assert count_device_groups([[1, 0, 0], [0, 1, 0], [0, 0, 1]]) == 3


@pytest.mark.exercise("ir.device_groups")
def test_ir_device_groups_single_and_full():
    assert count_device_groups([[1]]) == 1
    assert count_device_groups([[1] * 4 for _ in range(4)]) == 1


@pytest.mark.exercise("ir.device_groups")
def test_ir_device_groups_indirect():
    # 0-3, 3-1 links: 0,1,3 in one group; 2 alone
    m = [[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 0], [1, 1, 0, 1]]
    assert count_device_groups(m) == 2


@pytest.mark.exercise("ir.device_groups")
def test_ir_device_groups_random_vs_dfs():
    rng = random.Random(547)
    for _ in range(80):
        n = rng.randint(1, 30)
        p = rng.random() * 0.2
        m = [[0] * n for _ in range(n)]
        for i in range(n):
            m[i][i] = 1
            for j in range(i + 1, n):
                if rng.random() < p:
                    m[i][j] = m[j][i] = 1
        assert count_device_groups(m) == _components(m)


# ---------------------------------------------------------------- config.expand

def _gen_template(rng, depth):
    parts, plain = [], []
    for _ in range(rng.randint(1, 3)):
        if depth > 0 and rng.random() < 0.5:
            k = rng.randint(1, 4)
            t, e = _gen_template(rng, depth - 1)
            parts.append(f"{k}[{t}]")
            plain.append(e * k)
        else:
            w = "".join(rng.choice("xyz") for _ in range(rng.randint(1, 3)))
            parts.append(w)
            plain.append(w)
    return "".join(parts), "".join(plain)


@pytest.mark.exercise("config.expand")
def test_config_expand_examples():
    assert expand_template("3[a]2[bc]") == "aaabcbc"
    assert expand_template("3[a2[c]]") == "accaccacc"
    assert expand_template("2[abc]3[cd]ef") == "abcabccdcdcdef"


@pytest.mark.exercise("config.expand")
def test_config_expand_plain_and_empty():
    assert expand_template("abc") == "abc"
    assert expand_template("") == ""


@pytest.mark.exercise("config.expand")
def test_config_expand_multi_digit():
    assert expand_template("10[a]") == "a" * 10
    assert expand_template("2[12[b]c]") == ("b" * 12 + "c") * 2
    assert expand_template("100[ab]") == "ab" * 100


@pytest.mark.exercise("config.expand")
def test_config_expand_deep_nesting_with_suffix():
    assert expand_template("a2[b2[c2[d]]]e") == "a" + ("b" + ("c" + "dd") * 2) * 2 + "e"
    assert expand_template("1[1[1[z]]]") == "z"


@pytest.mark.exercise("config.expand")
def test_config_expand_random():
    rng = random.Random(394)
    for _ in range(200):
        t, want = _gen_template(rng, 3)
        assert expand_template(t) == want



@pytest.mark.exercise("config.expand")
def test_config_expand_mixed_characters():
    assert expand_template("2[gpu-A,]cpu_b") == "gpu-A,gpu-A,cpu_b"
    assert expand_template("3[ x.]") == " x. x. x."
    assert expand_template("a:2[B-x_c:]!") == "a:B-x_c:B-x_c:!"
    assert expand_template("2[(a),{b}]") == "(a),{b}(a),{b}"
    assert expand_template("Hello, World") == "Hello, World"


@pytest.mark.exercise("config.expand")
def test_config_expand_mixed_random():
    rng = random.Random(395)
    alphabet = "aZ,-_.: (){}!"

    def gen(depth):
        parts, plain = [], []
        for _ in range(rng.randint(1, 3)):
            if depth > 0 and rng.random() < 0.5:
                k = rng.randint(1, 12)
                t, e = gen(depth - 1)
                parts.append(f"{k}[{t}]")
                plain.append(e * k)
            else:
                w = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 3)))
                parts.append(w)
                plain.append(w)
        return "".join(parts), "".join(plain)

    for _ in range(300):
        t, want = gen(3)
        assert expand_template(t) == want, t


# ---------------------------------------------------------------- config.arith

def _arith_oracle(tokens):
    # tokens: [int, op, int, op, ...]; evaluate with precedence and truncating division
    vals = [tokens[0]]
    ops = []
    for op, x in zip(tokens[1::2], tokens[2::2]):
        if op == "*":
            vals[-1] = vals[-1] * x
        elif op == "/":
            q = abs(vals[-1]) // x
            vals[-1] = q if vals[-1] >= 0 else -q
        else:
            ops.append(op)
            vals.append(x)
    total = vals[0]
    for op, x in zip(ops, vals[1:]):
        total = total + x if op == "+" else total - x
    return total


@pytest.mark.exercise("config.arith")
def test_config_arith_examples():
    assert eval_arith("3+2*2") == 7
    assert eval_arith(" 3/2 ") == 1
    assert eval_arith(" 3+5 / 2 ") == 5


@pytest.mark.exercise("config.arith")
def test_config_arith_single_number_and_spaces():
    assert eval_arith("42") == 42
    assert eval_arith("   0  ") == 0
    assert eval_arith(" 4096 / 16 * 2 + 1 ") == 513


@pytest.mark.exercise("config.arith")
def test_config_arith_truncate_toward_zero():
    # 1 - 7/2 == 1 - 3 == -2 ; and a negative intermediate divided: 0-3*5/2 -> 0 - (15/2=7) = -7
    assert eval_arith("1-7/2") == -2
    assert eval_arith("0-3*5/2") == -7
    assert eval_arith("14-3/2") == 13
    assert eval_arith("2*3/4") == 1


@pytest.mark.exercise("config.arith")
def test_config_arith_left_to_right():
    assert eval_arith("10-2-3") == 5
    assert eval_arith("100/10/5") == 2
    assert eval_arith("2*3*4-1") == 23
    assert eval_arith("1+2*5/3+6/4*2") == 6


@pytest.mark.exercise("config.arith")
def test_config_arith_random():
    rng = random.Random(227)
    for _ in range(300):
        tokens = [rng.randint(0, 200)]
        for _ in range(rng.randint(0, 6)):
            op = rng.choice("+-*/")
            tokens += [op, rng.randint(1, 50) if op == "/" else rng.randint(0, 50)]
        s = ""
        for t in tokens:
            s += " " * rng.randint(0, 2) + str(t)
        s += " " * rng.randint(0, 2)
        assert eval_arith(s) == _arith_oracle(tokens)


# ---------------------------------------------------------------- eval.rouge_l

def _lcs_brute(a, b):
    best = 0
    for r in range(len(a), 0, -1):
        for idx in itertools.combinations(range(len(a)), r):
            sub = "".join(a[i] for i in idx)
            it = iter(b)
            if all(ch in it for ch in sub):
                return r
    return best


@pytest.mark.exercise("eval.rouge_l")
def test_eval_rouge_l_examples():
    assert lcs_length("abcde", "ace") == 3
    assert lcs_length("abc", "abc") == 3
    assert lcs_length("abc", "def") == 0


@pytest.mark.exercise("eval.rouge_l")
def test_eval_rouge_l_empty():
    assert lcs_length("", "") == 0
    assert lcs_length("abc", "") == 0
    assert lcs_length("", "abc") == 0


@pytest.mark.exercise("eval.rouge_l")
def test_eval_rouge_l_case_and_repeats():
    assert lcs_length("aaaa", "aa") == 2
    assert lcs_length("Abc", "abc") == 2
    assert lcs_length("bsbininm", "jmjkbkjkv") == 1
    assert lcs_length("ezupkr", "ubmrapg") == 2


@pytest.mark.exercise("eval.rouge_l")
def test_eval_rouge_l_long():
    a = "ab" * 500
    b = "ba" * 500
    assert lcs_length(a, b) == 999


@pytest.mark.exercise("eval.rouge_l")
def test_eval_rouge_l_random_vs_brute():
    rng = random.Random(1143)
    for _ in range(150):
        a = "".join(rng.choice("abc") for _ in range(rng.randint(0, 8)))
        b = "".join(rng.choice("abc") for _ in range(rng.randint(0, 8)))
        assert lcs_length(a, b) == _lcs_brute(a, b)


# ---------------------------------------------------------------- decode.regex

@pytest.mark.exercise("decode.regex")
def test_decode_regex_examples():
    assert full_match("aa", "a") is False
    assert full_match("aa", "a*") is True
    assert full_match("ab", ".*") is True


@pytest.mark.exercise("decode.regex")
def test_decode_regex_star_zero_times():
    assert full_match("aab", "c*a*b") is True
    assert full_match("", "a*b*.*") is True
    assert full_match("", "") is True
    assert full_match("", "a") is False
    assert full_match("a", "") is False


@pytest.mark.exercise("decode.regex")
def test_decode_regex_full_not_partial():
    assert full_match("mississippi", "mis*is*p*.") is False
    assert full_match("mississippi", "mis*is*ip*.") is True
    assert full_match("abc", "ab") is False
    assert full_match("ab", ".*c") is False


@pytest.mark.exercise("decode.regex")
def test_decode_regex_backtracking_cases():
    assert full_match("aaa", "a*a") is True
    assert full_match("aaa", "ab*a*c*a") is True
    assert full_match("a", "ab*") is True
    assert full_match("aaaaaaaaaaaaab", "a*a*a*a*a*a*a*a*a*c") is False
    assert full_match("abcd", "d*") is False


@pytest.mark.exercise("decode.regex")
def test_decode_regex_random_vs_re():
    rng = random.Random(10)
    for _ in range(1500):
        s = "".join(rng.choice("ab") for _ in range(rng.randint(0, 7)))
        p = ""
        for _ in range(rng.randint(0, 6)):
            p += rng.choice("ab.")
            if rng.random() < 0.4:
                p += "*"
        want = re.fullmatch(p, s) is not None
        assert full_match(s, p) is want


def _to_re(p):
    """Our dialect → Python re: '.' and '*' stay special, every other character is a literal."""
    return "".join(c if c in ".*" else re.escape(c) for c in p)


@pytest.mark.exercise("decode.regex")
def test_decode_regex_any_characters():
    assert full_match("The cache, ok.", "The c.*e, o*k.") is True
    assert full_match("The cache, ok.", "the c.*") is False          # literals are case-sensitive
    assert full_match("a.b", "a.b") is True                          # wildcard matches the literal '.'
    assert full_match("axb", "a.b") is True
    assert full_match("a*b", "a.b") is True                          # '*' in s is just a character
    assert full_match("a b", "a b") is True and full_match("ab", "a b") is False
    assert full_match("  x", " *x") is True                          # ' *' = zero or more spaces
    assert full_match("line\n", "line.") is True                     # '.' matches a newline too
    assert full_match("缓存命中", "缓存.*") is True
    assert full_match("café", "caf.") is True and full_match("café", "cafe") is False
    assert full_match("!!!?", "!*?") is True and full_match("?", "!*?") is True


@pytest.mark.exercise("decode.regex")
def test_decode_regex_random_mixed_alphabet_vs_re():
    rng = random.Random(1010)
    s_alphabet = "aB .,\n*中"
    p_literals = "aB ,\n中"  # '.' and '*' are always special in a pattern
    for _ in range(1500):
        s = "".join(rng.choice(s_alphabet) for _ in range(rng.randint(0, 7)))
        p = ""
        for _ in range(rng.randint(0, 6)):
            p += rng.choice(p_literals + "..")
            if rng.random() < 0.4:
                p += "*"
        want = re.fullmatch(_to_re(p), s, flags=re.DOTALL) is not None
        assert full_match(s, p) is want, (s, p)


# ---------------------------------------------------------------- kv.refcount / kv.versioned: integer keys

@pytest.mark.exercise("kv.refcount")
def test_kv_refcount_integer_block_keys():
    r = RefCounter()
    r.inc(0)
    r.inc(7)
    r.inc(7)
    assert r.max_key() == 7 and r.min_key() == 0     # block 0 is a key, not "missing"
    r.dec(7)
    r.dec(7)
    assert r.max_key() == 0 and r.min_key() == 0
    r.dec(0)
    assert r.max_key() == "" and r.min_key() == ""


@pytest.mark.exercise("kv.refcount")
def test_kv_refcount_random_vs_model_int_keys():
    rng = random.Random(4320)
    r, cnt = RefCounter(), {}
    for _ in range(2000):
        if rng.random() < 0.5 or not cnt:
            k = rng.randrange(0, 12)
            r.inc(k)
            cnt[k] = cnt.get(k, 0) + 1
        else:
            k = rng.choice(sorted(cnt))
            r.dec(k)
            cnt[k] -= 1
            if cnt[k] == 0:
                del cnt[k]
        if cnt:
            hi, lo = max(cnt.values()), min(cnt.values())
            assert r.max_key() in {k for k, v in cnt.items() if v == hi}
            assert r.min_key() in {k for k, v in cnt.items() if v == lo}
        else:
            assert r.max_key() == "" and r.min_key() == ""


@pytest.mark.exercise("kv.versioned")
def test_kv_versioned_integer_keys():
    s = VersionedStore()
    s.set(0, "r1", 6)
    assert s.get(0, 5) == ""
    assert s.get(0, 6) == "r1"
    assert s.get("0", 6) == ""          # 0 and "0" are different keys
    s.set(0, "", 7)                     # an empty value is a real version (block owned by nobody)
    s.set(3, "r2", 8)
    assert s.get(0, 7) == "" and s.get(0, 6) == "r1"
    assert s.get(3, 8) == "r2" and s.get(3, 7) == ""


@pytest.mark.exercise("kv.versioned")
def test_kv_versioned_random_vs_model_int_keys():
    rng = random.Random(9810)
    s = VersionedStore()
    hist = []
    ts = 0
    for _ in range(800):
        if rng.random() < 0.4:
            ts += rng.randint(1, 3)
            k, v = rng.randrange(0, 6), rng.choice(["", "r1", "r2", "r3"])
            s.set(k, v, ts)
            hist.append((k, v, ts))
        else:
            k, q = rng.randrange(0, 7), rng.randint(0, ts + 2)
            want = ""
            for hk, hv, hts in hist:
                if hk == k and hts <= q:
                    want = hv
            assert s.get(k, q) == want
