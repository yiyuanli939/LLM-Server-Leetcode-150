"""M3 integration: BlockManager driven directly: fork, checkpoints, eviction policies, sanitizers, report."""
import random

import pytest

from nanoserve.engine import Engine, GenerationConfig
from nanoserve.kvcache.manager import BlockManager
from nanoserve.kvcache.workloads import hot_vs_scan, parallel_sample, policy_table, shifting_hot_set, speculative_generate
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import make_trace

pytestmark = pytest.mark.milestone("M3")


@pytest.fixture(scope="module")
def engine():
    return Engine()


def _tokens(engine, text):
    return engine.tokenizer.encode(text)


# ------------------------------------------------------------------------------- fork / sharing
def test_fork_shares_blocks_and_refcounts_drop_to_zero(engine):
    mgr = BlockManager(64, 4, debug=True)
    ids = _tokens(engine, "The cache is made of blocks.")          # 17 tokens: 4 full blocks + 1
    mgr.admit("p", ids)
    parent = mgr.block_table("p")
    assert mgr.fork("p", "c")
    child = mgr.block_table("c")
    assert child == parent                                          # same physical blocks ...
    assert mgr.seqs["c"].head is not mgr.seqs["p"].head             # ... in a separate table
    assert all(mgr.refs[b] == 2 for b in parent)
    assert mgr.report()["most_shared"][1] == 2
    # diverge: both append a different token into the shared partial last block
    assert mgr.store("p", ids + [5]) and mgr.store("c", ids + [6])
    assert mgr.stats["cow"] == 1
    p2, c2 = mgr.block_table("p"), mgr.block_table("c")
    assert p2[:-1] == c2[:-1] and p2[-1] != c2[-1]                  # only the written block was copied
    assert mgr.content[p2[-1]][-1] == 5 and mgr.content[c2[-1]][-1] == 6
    mgr.release("p")
    assert all(mgr.refs[b] == 1 for b in c2)
    assert mgr.owner(c2[0]) == "c"                                   # the charge moved to the survivor
    mgr.release("c")
    assert all(r == 0 for r in mgr.refs) and mgr.in_use == 0
    assert mgr.check() == []


def test_parallel_sampling_matches_independent_generation(engine):
    prompt, n = "The engine keeps the keys and values of every token in a cache. The scheduler", 4
    cfg = GenerationConfig(max_tokens=20, seed=3)
    mgr = BlockManager(64, 4, debug=True)
    res = parallel_sample(engine, mgr, prompt, n, cfg)
    alone = [engine.generate(prompt, GenerationConfig(max_tokens=20, seed=3 + i)) for i in range(n)]
    assert res.texts == [a.text for a in alone]
    assert set(res.shared_at_fork.values()) == {n}                    # every prompt block shared n ways
    prompt_blocks = len(res.shared_at_fork)
    unshared = sum(-(-(len(_tokens(engine, prompt)) + len(a.token_ids)) // 4) for a in alone)
    assert res.peak_in_use <= unshared - (n - 1) * (prompt_blocks - 1)   # at most the partial block copied
    assert res.stats["in_use"] == 0 and res.stats["problems"] == [] and res.stats["leaks"] == []


# ------------------------------------------------------------------------------- checkpoints
def test_snapshot_rollback_restores_the_exact_block_table(engine):
    mgr = BlockManager(48, 4, debug=True)
    ids = _tokens(engine, "The scheduler")                            # 13 tokens
    mgr.admit("r", ids)
    mgr.fork("r", "twin")                                             # tail block shared → CoW on write
    rng = random.Random(7)
    ctx = list(ids)
    for _ in range(12):
        snap = mgr.checkpoint("r")
        table, stored = mgr.block_table("r"), mgr.stored_tokens("r")
        before_refs = list(mgr.refs)
        draft = [rng.randrange(len(engine.tokenizer)) for _ in range(rng.randrange(1, 9))]
        assert mgr.store("r", ctx + draft)
        assert mgr.block_table("r") != table or len(draft) < 4 - stored % 4
        mgr.rollback("r", snap)
        assert mgr.block_table("r") == table and mgr.stored_tokens("r") == stored
        assert mgr.refs == before_refs or mgr.cached                   # pins released (blocks → cache)
        assert mgr.check() == []
        ctx.append(rng.randrange(len(engine.tokenizer)))               # commit one real token
        assert mgr.store("r", ctx)
    # nested checkpoints: rolling back to the outer one drops the inner one too
    s1 = mgr.checkpoint("r")
    t1 = mgr.block_table("r")
    mgr.store("r", ctx + [1, 2, 3, 4, 5])
    s2 = mgr.checkpoint("r")
    mgr.store("r", ctx + [1, 2, 3, 4, 5, 6, 7, 8, 9])
    mgr.rollback("r", s1)
    assert mgr.block_table("r") == t1 and mgr.seqs["r"].checkpoints == []
    with pytest.raises(KeyError):
        mgr.rollback("r", s2)
    mgr.release("r")
    mgr.release("twin")
    assert mgr.in_use == 0 and mgr.check() == []


def test_speculative_decoding_rolls_back_rejected_drafts(engine):
    mgr = BlockManager(64, 4, debug=True)
    res = speculative_generate(engine, mgr, "The model reads the prompt and", 40, k=4)
    plain = engine.generate("The model reads the prompt and", GenerationConfig(max_tokens=40, temperature=0))
    assert res.token_ids == plain.token_ids
    assert res.rollbacks > 0 and res.exact_restores == res.rollbacks
    assert mgr.stats["checkpoints"] == res.rounds
    assert mgr.in_use == 0 and mgr.check() == []


# ------------------------------------------------------------------------------- eviction policies
def test_eviction_policies_differ_on_crafted_reuse_traces():
    scan = policy_table(hot_vs_scan(), host_blocks=4)
    shift = policy_table(shifting_hot_set(), host_blocks=4)
    # a hot prompt between ever longer one-off scans: LFU keeps it on the host, LRU loses it
    assert scan["lfu"]["restored"] > scan["lru"]["restored"]
    assert scan["lfu"]["computed"] < scan["lru"]["computed"]
    # the hot set moves on: LFU stays polluted by the old favourite, LRU adapts
    assert shift["lru"]["restored"] > shift["lfu"]["restored"]
    # same trace, same number of lookups whatever the policy
    for tab in (scan, shift):
        assert len({t["restored"] + t["computed"] for t in tab.values()}) == 1
        assert len({t["restored"] for t in tab.values()}) > 1


def test_random_eviction_is_seeded_and_leaves_global_random_alone():
    random.seed(123)
    expect = random.random()
    random.seed(123)
    a = policy_table(hot_vs_scan(), host_blocks=4, policies=("random",), seed=5)
    assert random.random() == expect                                 # global stream untouched
    b = policy_table(hot_vs_scan(), host_blocks=4, policies=("random",), seed=5)
    assert a == b


def test_gpu_eviction_offloads_cold_blocks_first(engine):
    # Cache: one block reused twice (hot) and several used once (cold); evicting must take cold ones.
    mgr = BlockManager(8, 4, hot=2)
    hot_ids = list(range(100, 104))
    for t in range(3):
        mgr.admit(f"h{t}", hot_ids + [1], now=t)
        mgr.release(f"h{t}", now=t)
    hot_block = mgr.table.get(mgr.hash_of[next(b for b in mgr.cached if mgr.key[b] == tuple(hot_ids))])
    assert mgr.heat[hot_block] >= 2
    for t in range(3, 15):                                           # 12 one-off prompts: more than fits
        mgr.admit(f"c{t}", list(range(10 * t, 10 * t + 4)) + [2], now=t)
        mgr.release(f"c{t}", now=t)
    assert mgr.stats["offloaded"] >= 5
    assert hot_block in mgr.cached                                   # survived while colder blocks went
    assert mgr.check() == []


# ------------------------------------------------------------------------------- sanitizers
def _busy_manager(engine):
    mgr = BlockManager(24, 4)
    long = _tokens(engine, "The engine keeps the keys and values of every token in a cache. ")
    mgr.admit("a", long)
    mgr.admit("b", long[:9])
    mgr.release("b")
    return mgr


def test_double_free_is_quarantined_and_never_reused(engine):
    mgr = _busy_manager(engine)
    free_block = mgr.pool.contents()[0][0]
    mgr.pool.stage([free_block])                                     # freed a second time
    assert any("double-freed" in p for p in mgr.check(leaks=False))
    assert mgr.sanitize() == [free_block]
    ev = mgr.log.find(mgr.last_event[free_block])
    assert ev.kind == "quarantine" and ev.block == free_block
    for i in range(10):                                              # allocate a lot: never handed out
        mgr.admit(f"x{i}", list(range(500 + 8 * i, 508 + 8 * i)))
        assert free_block not in mgr.block_table(f"x{i}")
        mgr.release(f"x{i}")
    assert mgr.report()["quarantined"] == [free_block] and mgr.check() == []


def test_block_freed_while_in_use_is_caught(engine):
    mgr = _busy_manager(engine)
    victim = mgr.block_table("a")[1]
    mgr.pool.stage([victim])                                         # released although "a" holds it
    assert any(f"block {victim} is both free and in use" in p for p in mgr.check())
    mgr.sanitize()                                                   # not a duplicate: merged into the list
    for i in range(6):                                               # ... but never handed out
        mgr.admit(f"y{i}", list(range(700 + 8 * i, 708 + 8 * i)))
        assert victim not in mgr.block_table(f"y{i}")
    assert victim in mgr.quarantine
    mgr.release("a")
    assert mgr.refs[victim] == 0 and not mgr.bitmap.test(victim)     # dropped, not recycled


def test_injected_leaks_are_found_exactly(engine):
    mgr = _busy_manager(engine)
    assert mgr.audit_leaks() == [] and mgr.check() == []
    for k in (1, 2, 5):                                              # 1 leak: XOR alone; more: bisection
        leaked = sorted(mgr._take_block() for _ in range(k))         # taken, but recorded nowhere
        assert mgr.audit_leaks() == leaked
        assert any(f"leaked block {leaked[0]}" in p for p in mgr.check())
        for b in leaked:                                             # clean up the injected leak
            mgr.bitmap.clear(b)
            mgr.pool.stage([b])
        mgr.sanitize()
        assert mgr.audit_leaks() == []


def test_corrupt_block_table_is_detected(engine):
    mgr = _busy_manager(engine)
    seq = mgr.seqs["a"]
    seq.tail.next = seq.head.next                                    # cycle
    assert any("cycle" in p for p in mgr.check())
    seq.tail.next = None
    seq.tail.random = None                                           # broken back link
    assert any("back link" in p for p in mgr.check())


def test_arena_bounds_checker_rejects_stale_access(engine):
    from nanoserve.kvcache.arena import ArenaBoundsError
    mgr = _busy_manager(engine)
    sid = mgr.seqs["a"].sid
    n = mgr.stored_tokens("a")
    assert mgr.arena.read(sid, n - 1) >= 0
    with pytest.raises(ArenaBoundsError):
        mgr.arena.read(sid, mgr.arena.capacity(sid))                 # past the row
    mgr.release("a")
    with pytest.raises(ArenaBoundsError):
        mgr.arena.read(sid, 0)                                       # released row


# ------------------------------------------------------------------------------- report vs brute force
def test_report_agrees_with_brute_force(engine):
    srv = Server(engine, ServerConfig(max_batch=4, kv_blocks=20, block_size=8))
    srv.submit_many(make_trace(14, seed=4))
    srv.run(max_ticks=40)                                            # stop mid-run: requests in flight
    mgr = srv.kv
    rep = mgr.report()
    n = mgr.num_blocks
    tables = {rid: seq.block_list() for rid, seq in mgr.seqs.items()}
    held = [b for t in tables.values() for b in t]
    refs = [held.count(b) for b in range(n)]
    assert refs == mgr.refs and rep["in_use"] == sum(1 for r in refs if r) > 0
    free = sorted(set(range(n)) - set(held) - set(mgr.cached) - set(mgr.quarantine))
    assert rep["free"] == len(free)
    # ranges: rebuild from the strings
    decoded = []
    for part in rep["free_ranges"]:
        a, _, b = part.partition("->")
        decoded += list(range(int(a), int(b or a) + 1))
    assert decoded == free
    best, cur = 0, 0
    for i, b in enumerate(free):
        cur = cur + 1 if i and b == free[i - 1] + 1 else 1
        best = max(best, cur)
    assert rep["largest_free_run"] == best
    assert rep["used"] == sum(1 for b in range(n) if refs[b] or b in mgr.cached)
    top, low = rep["most_shared"], rep["least_shared"]
    assert top[1] == max(r for r in refs if r) and low[1] == min(r for r in refs if r)
    charged = {rid: sum(1 for b in range(n) if mgr.charge[b] == mgr.seqs[rid].sid) for rid in tables}
    assert rep["charged"] == {rid: k for rid, k in charged.items() if k}
    assert sum(rep["charged"].values()) == rep["in_use"]
    # event log: oldest timestamp and chronological order
    evs = mgr.log.chronological()
    assert [e.ts for e in evs] == list(range(mgr.log.total - len(evs) + 1, mgr.log.total + 1))
    assert rep["oldest_event"] == evs[0].ts and len(evs) == min(mgr.log.total, mgr.log.capacity)
    assert mgr.log.find(evs[0].ts - 1) is None and mgr.log.find(evs[-1].ts) == evs[-1]
    # ownership history: replay the (retained) charge events
    for b in range(n):
        assert mgr.owner(b) == (mgr.seqs[[r for r, s in mgr.seqs.items() if s.sid == mgr.charge[b]][0]].rid
                                if mgr.charge[b] else "")
    assert rep["problems"] == [] and rep["leaks"] == []


def test_owner_history_answers_who_held_a_block_at_tick_t(engine):
    mgr = BlockManager(8, 4)
    mgr.admit("a", [1, 2, 3, 4, 5], now=1)          # blocks 0 (full), 1 (partial)
    mgr.admit("b", [1, 2, 3, 4, 9], now=2)          # shares block 0, gets block 2
    mgr.release("a", now=3)                         # block 0's charge moves to b; block 1 freed
    mgr.admit("c", [7, 7, 7, 7, 7], now=4)
    assert [mgr.owner_at(0, t) for t in (0, 1, 2, 3, 4)] == ["", "a", "a", "b", "b"]
    assert [mgr.owner_at(1, t) for t in (1, 2, 3)] == ["a", "a", ""]
    assert mgr.owner_at(2, 2) == "b" and mgr.owner(2) == "b"
    assert mgr.check() == []


def test_event_log_wraps_and_stays_searchable(engine):
    mgr = BlockManager(16, 4, log_capacity=10)
    for t in range(12):
        mgr.admit(f"r{t}", list(range(20 * t, 20 * t + 6)), now=t)
        mgr.release(f"r{t}", now=t)
    log = mgr.log
    assert log.total > 3 * log.capacity
    evs = log.chronological()
    assert len(evs) == 10 and [e.ts for e in evs] == list(range(log.total - 9, log.total + 1))
    assert [e.tick for e in evs] == sorted(e.tick for e in evs)
    assert log.oldest() == log.total - 9
    for e in evs:
        assert log.find(e.ts) == e
    assert log.find(log.total - 10) is None and log.find(log.total + 1) is None


def test_offload_transfers_are_coalesced_per_tick():
    mgr = BlockManager(6, 2, host_blocks=32)
    mgr.admit("a", list(range(10, 22)), now=0)        # 6 full blocks: the whole pool
    mgr.release("a", now=0)
    mgr.admit("b", list(range(40, 52)), now=1)        # evicts all six in one tick
    mgr.release("b", now=1)
    mgr.report()
    assert mgr.stats["offloaded"] == 6
    assert mgr.stats["transfers"] < 6                  # contiguous ranges merged into one copy each
    mgr.admit("a2", list(range(10, 22)), now=2)       # all six restored from the host tier
    assert mgr.stats["restored"] == 6
