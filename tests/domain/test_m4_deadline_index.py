"""M4 integration: the earliest-deadline-first waiting queue (nanoserve.index.queue.DeadlineQueue)."""
import random

import pytest

from nanoserve.engine import Engine
from nanoserve.index.bst_index import BSTIndex, depth_limit
from nanoserve.index.queue import DeadlineQueue
from nanoserve.index.workloads import deadline_trace
from nanoserve.server.plugins import WaitingQueue
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import make_trace

pytestmark = pytest.mark.milestone("M4")


@pytest.fixture(scope="module")
def engine():
    return Engine()


def _edf_order(reqs, seq):
    """Oracle order: earliest deadline first, no deadline last, ties by first-push order."""
    return sorted(reqs, key=lambda r: (r.deadline is None, max(r.deadline, 0) if r.deadline is not None else 0,
                                       seq[r]))


def _serve(engine, policy, trace, **cfg):
    server = Server(engine, ServerConfig(policy=policy, **cfg))
    server.submit_many(trace)
    return server, server.run()


def test_config_flag_plugs_in_the_deadline_queue(engine):
    server = Server(engine, ServerConfig(policy="edf"))
    assert isinstance(server.queue, DeadlineQueue)
    assert isinstance(server.queue, WaitingQueue)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_edf_meets_more_deadlines_than_fcfs(engine, seed):
    trace_f, trace_e = deadline_trace(seed=seed), deadline_trace(seed=seed)
    _, fcfs = _serve(engine, "fcfs", trace_f, max_batch=2)
    server, edf = _serve(engine, "edf", trace_e, max_batch=2)
    assert len(fcfs.finished) == len(edf.finished) == len(trace_e)
    assert edf.outputs() == fcfs.outputs()                           # policy changes timing, never text

    def met(rep, tenant=None):
        return sum(bool(r.met_deadline) for r in rep.finished if tenant is None or r.tenant == tenant)

    assert met(edf) > met(fcfs)
    assert met(edf, "chat") == sum(r.tenant == "chat" for r in trace_e)   # every tight deadline is met
    assert all(r.met_deadline for r in edf.finished if r.deadline is not None and r.tenant == "batch")
    rep = edf.plugins["queue"]
    assert rep["healthy"] and rep["pushes"] == rep["pops"] == len(trace_e)
    assert rep["overtakes"] > 0 and rep["peak_urgent"] > 0 and rep["tightest_deadline_gap"] == 1
    assert len(server.queue) == 0 and server.queue.check() == []


def test_edf_admission_order_on_a_random_trace(engine):
    """With one slot, admission order must follow EDF among the requests that were waiting at the time."""
    trace = make_trace(25, seed=7, rate=0.8, max_tokens=(4, 10), deadline_slack=(0, 40))
    for r in trace[::5]:
        r.deadline = None                                            # mix in undated requests
    server, rep = _serve(engine, "edf", trace, max_batch=1)
    assert len(rep.finished) == len(trace)
    seq = {r: i for i, r in enumerate(sorted(trace, key=lambda r: r.arrival))}
    for r in rep.finished:
        waiting = [o for o in trace if o.arrival <= r.admitted_at and o.admitted_at >= r.admitted_at]
        assert _edf_order(waiting, seq)[0] is r


def test_queue_invariants_under_random_push_pop_remove():
    rng = random.Random(11)
    q = DeadlineQueue(urgent_window=30)
    reqs = [Request(rid=f"q{i:03d}", prompt="The", arrival=i // 3, max_tokens=rng.randint(1, 30),
                    deadline=None if rng.random() < 0.15 else rng.randint(-5, 400)) for i in range(400)]
    seq: dict[Request, int] = {}
    waiting: list[Request] = []
    nxt = 0
    for step in range(900):
        op = rng.random()
        if nxt < len(reqs) and (op < 0.45 or not waiting):
            r = reqs[nxt]; nxt += 1
            seq[r] = len(seq)
            q.push(r); waiting.append(r)
        elif op < 0.75 and waiting:
            assert q.peek() is _edf_order(waiting, seq)[0]
            r = q.pop(); waiting.remove(r)
        elif op < 0.9 and waiting:
            r = rng.choice(waiting)
            q.remove(r); waiting.remove(r)
        elif waiting:                                                # preempted: back with the same key
            r = q.pop(); q.push_front(r)
        if not waiting:
            assert q.peek() is None and len(q) == 0
            continue
        order = _edf_order(waiting, seq)
        if step % 7 == 0:
            assert q.check() == []
            assert list(q) == order                                  # DeadlineIterator walk
            k = rng.randint(1, len(order))
            assert q.at(k) is order[k - 1]                           # kth_earliest
            assert q.position(order[k - 1]) == k
            lo = rng.randint(-10, 300); hi = lo + rng.randint(0, 120)
            due = [r for r in order if r.deadline is not None and lo <= max(r.deadline, 0) <= hi]
            assert q.due_between(lo, hi) == due                      # fork_point-bounded range walk
            assert q.tokens_due(lo, hi) == sum(r.max_tokens for r in due)   # RangeCounter
            ds = sorted({max(r.deadline, 0) for r in waiting if r.deadline is not None})
            gap = min((b - a for a, b in zip(ds, ds[1:])), default=None)
            assert q.deadline_gap() == gap                           # min_gap
        assert q.index.height <= depth_limit(len(q))
    assert q.removes > 0 and q.requeues > 0


def test_rebalance_triggers_on_sorted_insertion():
    q = DeadlineQueue()
    n = 200
    reqs = [Request(rid=f"s{i}", prompt="The", arrival=i, deadline=3 * i) for i in range(n)]
    for i, r in enumerate(reqs):
        q.push(r)
        assert q.index.height <= depth_limit(i + 1)                  # never a chain
    assert q.index.rebuilds > 0
    assert q.index.height < 2 * 8 + 2 < n                            # log2(200) ≈ 7.6
    levels = q.index.levels()                                        # level_dump
    assert sum(map(len, levels)) == n and len(levels) == q.index.height
    assert levels[0] == [q.index.root.val]
    assert q.check() == [] and [r.rid for r in q] == [r.rid for r in reqs]
    for r in reqs[: n // 2]:                                         # drain half: limits shrink, still healthy
        assert q.pop() is r
    assert q.check() == [] and q.index.height <= depth_limit(len(q))


def test_bst_index_range_query_uses_split_node():
    rng = random.Random(5)
    keys = rng.sample(range(0, 5000), 300)
    idx = BSTIndex()
    for k in keys:
        idx.add(k)
    srt = sorted(keys)
    assert list(idx.keys()) == srt and idx.check() == []
    for _ in range(200):
        lo = rng.randint(-50, 5050); hi = lo + rng.randint(-20, 800)
        assert idx.between(lo, hi) == [k for k in srt if lo <= k <= hi]
    assert idx.min_gap() == min(b - a for a, b in zip(srt, srt[1:]))
    assert [idx.kth(i) for i in (1, 150, 300)] == [srt[0], srt[149], srt[299]]
