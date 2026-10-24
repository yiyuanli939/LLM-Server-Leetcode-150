"""M2 integration: the continuous-batching server core end to end.

Admission (slots, token budget, sessions, maintenance windows), the QPS series, the busy timeline and p50 —
and the invariant that batching never changes what a request generates.
"""
import statistics

import pytest

from nanoserve.engine import Engine, GenerationConfig
from nanoserve.server.planner import fresh_batch
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import PROMPTS, make_trace

pytestmark = pytest.mark.milestone("M2")


@pytest.fixture(scope="module")
def engine():
    return Engine()


def run(engine, reqs, **cfg):
    server = Server(engine, ServerConfig(**cfg))
    server.submit_many(fresh_batch(reqs))
    return server.run()


def alone(engine, r):
    cfg = GenerationConfig(max_tokens=r.max_tokens, temperature=r.temperature, top_k=r.top_k, seed=r.seed,
                           stop=r.stop)
    return engine.generate(r.prompt, cfg).text


def running_at(rep, t):
    return [r for r in rep.finished if r.admitted_at <= t < r.finished_at]


def test_batching_never_changes_outputs(engine):
    trace = make_trace(24, seed=1, rate=2.0, stop=(".",))
    expected = {r.rid: alone(engine, r) for r in trace}
    for cfg in (dict(max_batch=1), dict(max_batch=3), dict(max_batch=8), dict(max_batch=4, token_budget=200)):
        rep = run(engine, trace, **cfg)
        assert len(rep.finished) == len(trace) and not rep.rejected, cfg
        assert rep.outputs() == expected, cfg
        # the multiplexed stream carries exactly each request's output, in order
        streamed = {}
        for _, rid, chunk in rep.events:
            streamed[rid] = streamed.get(rid, "") + chunk
        assert streamed == {rid: out for rid, out in expected.items() if out}


def test_slots_bound_the_batch_and_more_slots_cut_latency(engine):
    trace = make_trace(30, seed=0, rate=1.5)
    reps = {b: run(engine, trace, max_batch=b) for b in (1, 2, 4, 8)}
    for b, rep in reps.items():
        assert all(1 <= r.slot <= b for r in rep.finished)
        for t in range(rep.ticks):
            live = running_at(rep, t)
            assert len(live) <= b
            assert len({r.slot for r in live}) == len(live)  # no two running requests share a slot
    p50 = [reps[b].p50_latency for b in (1, 2, 4, 8)]
    assert p50 == sorted(p50, reverse=True) and p50[0] > p50[-1]


def test_p50_busy_timeline_and_utilization(engine):
    trace = make_trace(20, seed=4, rate=0.03)  # sparse: the server goes idle in between
    rep = run(engine, trace, max_batch=2)
    lat = [r.latency for r in rep.finished]
    assert rep.p50_latency == statistics.median(lat)
    # busy timeline: sorted, disjoint, non-touching spans covering exactly the ticks something ran
    assert len(rep.busy) > 1
    assert all(s < e for s, e in rep.busy)
    assert all(a[1] < b[0] for a, b in zip(rep.busy, rep.busy[1:]))
    busy_ticks = {t for s, e in rep.busy for t in range(s, e)}
    ran = {t for r in rep.finished for t in range(r.admitted_at, r.finished_at)}
    assert busy_ticks == ran
    assert rep.utilization == pytest.approx(len(ran) / rep.ticks) and 0 < rep.utilization < 1


def test_qps_series_counts_last_three_seconds(engine):
    trace = make_trace(60, seed=2, rate=3.0)
    rep = run(engine, trace, max_batch=4, tick_ms=100)
    assert len(rep.qps) == len(trace)
    # the server stamps arrivals with strictly increasing ms timestamps (same tick → +1 ms)
    stamps, last = [], 0
    for tick, _ in rep.qps:
        last = max(last + 1, tick * 100)
        stamps.append(last)
    for i, (_, q) in enumerate(rep.qps):
        assert q == sum(1 for s in stamps[: i + 1] if s >= stamps[i] - 3000)
    assert max(q for _, q in rep.qps) > 30  # rate 3 / tick × 30 ticks per 3 s


def test_token_budget_admission(engine):
    trace = make_trace(20, seed=3, rate=2.0)
    budget = 160
    free = run(engine, trace, max_batch=8)
    capped = run(engine, trace, max_batch=8, token_budget=budget)
    assert len(capped.finished) == len(trace)
    for t in range(capped.ticks):
        assert sum(r.prompt_tokens + r.max_tokens for r in running_at(capped, t)) <= budget
    assert max(len(running_at(free, t)) for t in range(free.ticks)) > max(
        len(running_at(capped, t)) for t in range(capped.ticks))
    assert capped.ticks > free.ticks
    # a request that can never fit, even on an empty server, is rejected instead of blocking the queue
    huge = Request(rid="huge", prompt=PROMPTS[8], max_tokens=budget, arrival=0)
    rep = run(engine, [huge] + make_trace(4, seed=5, start=1), max_batch=4, token_budget=budget)
    assert [r.rid for r in rep.rejected] == ["huge"] and len(rep.finished) == 4


def test_session_limit_rejects_new_sessions_only(engine):
    trace = make_trace(30, seed=6, rate=2.0, sessions=8)
    open_ = run(engine, trace, max_batch=4, session_ttl=30)
    assert not open_.rejected
    limited = run(engine, trace, max_batch=4, session_ttl=30, max_sessions=3)
    assert limited.rejected and limited.finished
    assert max(limited.active_sessions) <= 3
    accepted = {r.session for r in limited.finished}
    assert all(r.session not in accepted for r in limited.rejected)  # only new sessions get turned away
    # sessions expire: with a short TTL, more sessions get in over the run
    short = run(engine, trace, max_batch=4, session_ttl=3, max_sessions=3)
    assert len(short.rejected) < len(limited.rejected)


def test_maintenance_window_blocks_admission(engine):
    trace = make_trace(25, seed=7, rate=1.0)
    server = Server(engine, ServerConfig(max_batch=4))
    assert server.schedule_maintenance(10, 25)
    assert not server.schedule_maintenance(20, 30)   # overlaps → refused
    assert server.schedule_maintenance(25, 30)       # half-open: touching is fine
    server.submit_many(fresh_batch(trace))
    rep = server.run()
    assert len(rep.finished) == len(trace)
    assert all(not 10 <= r.admitted_at < 30 for r in rep.finished)
    assert any(r.admitted_at == 30 for r in rep.finished)  # the backlog starts right after the window
    base = run(engine, trace, max_batch=4)
    assert rep.p50_latency > base.p50_latency
