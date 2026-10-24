"""M2 integration: a cluster of servers — routing policies, merged timelines, cluster-wide p50."""
import statistics
from collections import Counter

import pytest

from nanoserve.engine import Engine, GenerationConfig
from nanoserve.server.cluster import Cluster, cluster_p50
from nanoserve.server.planner import fresh_batch, release_one_per_tick
from nanoserve.server.server import ServerConfig
from nanoserve.server.trace import make_trace

pytestmark = pytest.mark.milestone("M2")


@pytest.fixture(scope="module")
def engine():
    return Engine()


def run(engine, trace, n=3, **kw):
    cfg = kw.pop("config", ServerConfig(max_batch=2))
    cluster = Cluster(n, engine=engine, config=cfg, **kw)
    cluster.submit_many(fresh_batch(trace))
    return cluster.run()


def alone(engine, r):
    cfg = GenerationConfig(max_tokens=r.max_tokens, temperature=r.temperature, top_k=r.top_k, seed=r.seed,
                           stop=r.stop)
    return engine.generate(r.prompt, cfg).text


def waiting_while_idle(rep, slots_per_worker):
    """Ticks at which some request waits although some batch slot in the cluster is free."""
    bad = []
    for t in range(rep.ticks):
        waiting = [r for r in rep.finished if r.arrival <= t < r.admitted_at]
        running = [r for r in rep.finished if r.admitted_at <= t < r.finished_at]
        if waiting and len(running) < slots_per_worker * len(rep.workers):
            bad.append(t)
    return bad


@pytest.mark.parametrize("policy", ["weighted", "rr", "weighted_free"])
def test_cluster_outputs_identical_to_running_alone(engine, policy):
    trace = make_trace(24, seed=11, rate=1.0, stop=(".",))
    rep = run(engine, trace, policy=policy, weights=[1, 2, 1], costs=[2, 1, 3])
    assert rep.finished and all(r.worker is not None for r in rep.finished)
    by_rid = {r.rid: r for r in trace}
    assert rep.outputs() == {rid: alone(engine, by_rid[rid]) for rid in rep.outputs()}
    assert len(rep.finished) + len(rep.rejected) == len(trace)
    if policy != "rr":
        assert not rep.rejected


def test_weighted_routing_is_proportional_and_reproducible(engine):
    trace = make_trace(240, seed=12, rate=4.0, max_tokens=(1, 2))
    a = run(engine, trace, n=2, policy="weighted", weights=[1, 3], seed=5, config=ServerConfig(max_batch=8))
    b = run(engine, trace, n=2, policy="weighted", weights=[1, 3], seed=5, config=ServerConfig(max_batch=8))
    share = Counter(r.worker for r in a.requests)
    assert share[1] / len(trace) == pytest.approx(0.75, abs=0.08)
    assert [r.worker for r in a.requests] == [r.worker for r in b.requests]


def test_cluster_p50_and_merged_busy_timeline(engine):
    trace = make_trace(30, seed=13, rate=0.4)
    rep = run(engine, trace, n=3, policy="weighted", weights=[3, 1, 1])
    lat = [r.latency for r in rep.finished]
    assert rep.p50_latency == statistics.median(lat)
    any_busy = {t for w in rep.workers for s, e in w.busy for t in range(s, e)}
    assert {t for s, e in rep.busy for t in range(s, e)} == any_busy
    assert all(a[1] < b[0] for a, b in zip(rep.busy, rep.busy[1:]))
    assert rep.busy_ticks <= sum(w.busy_ticks for w in rep.workers)
    # cluster p50 folds any number of workers, empty ones included
    groups = [[5, 1, 9], [], [2, 2], [7], [3, 8, 4, 6]]
    for k in range(1, len(groups) + 1):
        flat = [x for g in groups[:k] for x in g]
        assert cluster_p50(groups[:k]) == statistics.median(flat)
    assert cluster_p50([[], []]) is None


def test_free_slot_placement_follows_the_plan_and_beats_random_routing(engine):
    trace = release_one_per_tick(make_trace(30, seed=14, rate=1.0))  # the batch, released one per tick
    free = run(engine, trace, n=3, policy="weighted_free", costs=[2, 1, 3])
    rand = run(engine, trace, n=3, policy="weighted", weights=[1, 1, 1], seed=1)
    assert len(free.finished) == len(rand.finished) == len(trace)
    # the plan (sched.assign_workers) is what actually happened
    assert {r.rid: r.worker for r in free.finished} == free.planned
    # the cheapest worker fills first: the first two requests (2 slots) land on worker 1, the next on 0
    order = sorted(free.finished, key=lambda r: r.arrival)
    assert [r.worker for r in order[:3]] == [1, 1, 0]
    # global FIFO: requests start in release order, and nobody waits while a slot is idle
    starts = [r.admitted_at for r in order]
    assert starts == sorted(starts)
    assert waiting_while_idle(free, 2) == []
    assert waiting_while_idle(rand, 2) != []           # random routing queues behind a busy worker
    mean = lambda rep: sum(r.latency for r in rep.finished) / len(rep.finished)  # noqa: E731
    assert mean(free) < mean(rand) and free.ticks <= rand.ticks


def test_round_robin_drops_when_all_busy_and_replay_names_hot_workers(engine):
    trace = make_trace(30, seed=15, rate=0.5)
    rep = run(engine, trace, n=3, policy="rr")
    assert all(w.name for w in rep.workers)
    assert rep.dropped and len(rep.dropped) == len(rep.rejected)
    # single-stream replicas: nobody ever waits, a worker never runs two requests at once
    assert all(r.admitted_at == r.arrival for r in rep.finished)
    for w in rep.workers:
        spans = sorted((r.admitted_at, r.finished_at) for r in w.finished)
        assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
    # a request is dropped only if every worker was busy at its arrival
    for d in rep.dropped:
        assert all(any(r.admitted_at <= d.arrival < r.finished_at for r in w.finished) for w in rep.workers)
    # the replay of the request log (exact service times) agrees with what the workers handled
    best = max(rep.counts)
    assert rep.hot_workers == [i for i, c in enumerate(rep.counts) if c == best]
    # more replicas → fewer drops
    more = run(engine, trace, n=5, policy="rr")
    assert len(more.dropped) < len(rep.dropped)
