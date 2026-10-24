"""M7 integration: the text dashboard — heatmap, slowest-k, fuzzy filter, corrected throughput,
cluster utilization, health matrix with fault injection."""
import random
import re

import pytest

from nanoserve.autoscale.planned import PlannedCluster
from nanoserve.dashboard.demo import main as dashboard_main
from nanoserve.dashboard.health_router import HealthMatrix
from nanoserve.dashboard.panel import (Dashboard, Occupancy, ThroughputMonitor, busy_spans, cluster_utilization,
                                       filter_requests, row_text, slowest_panel)
from nanoserve.engine import Engine
from nanoserve.server.cluster import Cluster
from nanoserve.server.planner import fresh_batch
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import make_trace

pytestmark = pytest.mark.milestone("M7")

MODELS = ("toy-chat", "toy-code", "toy-base")


@pytest.fixture(scope="module")
def engine():
    return Engine()


@pytest.fixture(scope="module")
def server_report(engine):
    srv = Server(engine, ServerConfig(max_batch=3))
    srv.submit_many(make_trace(18, seed=21, rate=0.8, models=MODELS))
    return srv.run()


@pytest.fixture(scope="module")
def cluster_report(engine):
    cluster = Cluster(3, engine=engine, config=ServerConfig(max_batch=2), policy="weighted", weights=[3, 1, 1])
    cluster.submit_many(make_trace(20, seed=22, rate=0.3, models=MODELS))
    return cluster.run()


class TokenCapKV:
    """Test KV backend: at most ``cap`` generated tokens in flight; beyond that the server must preempt."""

    def __init__(self, cap):
        self.cap, self.held = cap, {}

    def can_admit(self, req, now):
        return sum(self.held.values()) < self.cap

    def on_admit(self, req, now):
        self.held[req.rid] = 0

    def on_token(self, req, now):
        if sum(self.held.values()) >= self.cap:
            return False
        self.held[req.rid] += 1
        return True

    def on_finish(self, req, now):
        self.held.pop(req.rid, None)

    def report(self):
        return {}


# ------------------------------------------------------------------------------------- heatmap
@pytest.mark.parametrize("which", ["server", "cluster"])
def test_heatmap_region_sums_match_brute_force(which, server_report, cluster_report):
    rep = server_report if which == "server" else cluster_report
    occ = Occupancy(rep)
    workers = rep.workers if which == "cluster" else [rep]
    # the matrix is the requests' slot occupancy
    total = sum(r.finished_at - r.admitted_at for w in workers for r in w.finished)
    assert occ.region(0, 0, len(occ.rows) - 1, occ.ticks - 1) == total
    rng = random.Random(7)
    for _ in range(300):
        r1, r2 = sorted(rng.randrange(len(occ.rows)) for _ in range(2))
        c1, c2 = sorted(rng.randrange(occ.ticks) for _ in range(2))
        brute = sum(occ.grid[r][c] for r in range(r1, r2 + 1) for c in range(c1, c2 + 1))
        assert occ.region(r1, c1, r2, c2) == brute
    # coarse cells tile the matrix exactly; a worker's column is non-empty iff it was busy
    groups, buckets, sums = occ.cells(width=17)
    assert sum(map(sum, sums)) == total
    for w, rep_w in enumerate(workers):
        busy = {t for s, e in rep_w.busy for t in range(s, e)}
        assert {t for t in range(occ.ticks) if occ.worker_busy_slots(w, t, t)} == busy


def test_heatmap_renders_every_slot(server_report):
    lines = Occupancy(server_report).heatmap(width=30)
    assert len(lines) == 1 + 3 and all("|" in l for l in lines[1:])


# ------------------------------------------------------------------------------------- slowest k
@pytest.mark.parametrize("k", [1, 3, 5])
def test_kth_slowest_matches_sorted_latencies_at_every_step(server_report, k):
    panel = slowest_panel(server_report.requests, k)
    fin = sorted(server_report.finished, key=lambda r: (r.finished_at, r.slot, r.rid))
    assert len(panel.thresholds) == len(fin) - k + 1
    for step, (rid, bar) in enumerate(panel.thresholds):
        seen = sorted((r.latency for r in fin[:k + step]), reverse=True)
        assert rid == fin[k - 1 + step].rid and bar == seen[k - 1]
    lat = sorted((r.latency for r in fin), reverse=True)
    assert [r.latency for r in panel.slowest] == [x for x in lat if x >= lat[k - 1]]


# ------------------------------------------------------------------------------------- filter
def subsequence(q, s):
    """Independent oracle: q's characters in order, anything in between."""
    return re.search(".*".join(map(re.escape, q)), s, re.DOTALL) is not None


def test_fuzzy_filter_matches_brute_force(server_report):
    reqs = server_report.requests
    rng = random.Random(8)
    alphabet = "rtoy-cheabds0127 .TS"
    queries = ["", "r01", "rb", "tcd", "chat", "code", "r0aT", "zz", "toy-base", "r017", "rcThe."]
    queries += ["".join(rng.choice(alphabet) for _ in range(rng.randint(1, 6))) for _ in range(60)]
    for q in queries:
        shown = filter_requests(reqs, q)
        assert [r.rid for r in shown] == [r.rid for r in reqs if subsequence(q, row_text(r))], q
    assert len(filter_requests(reqs, "")) == len(reqs)
    assert [r.rid for r in filter_requests(reqs, "r017")] == ["r017"]
    assert filter_requests(reqs, "zz") == []


# ------------------------------------------------------------------------------------- corrections
def check_monitor(mon):
    """Replaying the monitor's update log into a dict gives the same current / max / min at every tick."""
    final = mon.per_tick(mon.server.events, mon.server.now)
    assert [mon.reported[t] for t in range(mon.server.now)] == final
    _, cur, hi, lo = mon.history[-1]
    assert (cur, hi, lo) == (final[-1], max(final), min(final))


def test_throughput_series_takes_late_corrections_from_preemption(engine):
    srv = Server(engine, ServerConfig(max_batch=4), kv=TokenCapKV(18))
    srv.submit_many(make_trace(10, seed=23, rate=1.5, max_tokens=(6, 12)))
    mon = ThroughputMonitor(srv)
    rep = mon.run()
    assert len(rep.finished) == 10 and sum(r.preemptions for r in rep.requests) > 0
    assert mon.corrections, "preemption must retroactively shrink earlier ticks"
    assert all(ts < at for at, ts, _ in mon.corrections)
    check_monitor(mon)
    # step-by-step: after every tick the series equals brute force over what is currently reported
    srv2 = Server(engine, ServerConfig(max_batch=4), kv=TokenCapKV(18))
    srv2.submit_many(make_trace(10, seed=23, rate=1.5, max_tokens=(6, 12)))
    mon2 = ThroughputMonitor(srv2)
    while not srv2.idle():
        mon2.step()
        vals = mon2.per_tick(srv2.events, srv2.now)
        assert mon2.history[-1][1:] == (vals[-1], max(vals), min(vals))
    assert mon2.corrections == mon.corrections


def test_throughput_with_the_real_kv_manager(engine):
    pytest.importorskip("nanoserve.kvcache.manager")
    srv = Server(engine, ServerConfig(max_batch=4, kv_blocks=20, block_size=4))
    srv.submit_many(make_trace(16, seed=3, rate=1.0))
    mon = ThroughputMonitor(srv)
    rep = mon.run()
    assert len(rep.finished) == 16
    if sum(r.preemptions for r in rep.requests):
        assert mon.corrections
    check_monitor(mon)


# ------------------------------------------------------------------------------------- utilization
def test_cluster_busy_time_is_the_union_of_worker_spans(cluster_report):
    u = cluster_utilization(cluster_report)
    union = {t for _, first, last in busy_spans(cluster_report) for t in range(first, last + 1)}
    assert u.any_busy == len(union) == u.merged and u.consistent
    assert u.any_busy < sum(u.worker_busy)          # workers overlap: the union is not the sum
    assert u.any_busy < cluster_report.ticks        # and the sparse trace leaves idle gaps
    lines = Dashboard(cluster_report).render(query="toy", k=3)
    assert any("cluster utilization" in l and "ok" in l for l in lines)


# ------------------------------------------------------------------------------------- health
def test_mask_contains_the_blast_radius_and_routing_avoids_it(engine):
    health = HealthMatrix(4, MODELS, weights=[[1, 2, 1], [2, 1, 1], [1, 1, 3], [1, 1, 1]])
    before = [row[:] for row in health.grid]
    health.fail(2, "toy-code")
    m = health.masked()
    assert health.grid[2][1] == 0 and health.grid[0] == before[0]  # the live matrix is untouched
    for w in range(4):
        for j in range(3):
            assert (m[w][j] == 0) == (w == 2 or j == 1)  # exactly row 2 and column toy-code
            if w != 2 and j != 1:
                assert m[w][j] == before[w][j]
    assert health.drained_workers() == [2] and health.paused_models() == ["toy-code"]

    trace = make_trace(24, seed=24, rate=1.0, models=MODELS)
    plan = health.route(trace)
    cluster = PlannedCluster(4, plan, engine=engine, config=ServerConfig(max_batch=2))
    cluster.submit_many(fresh_batch(trace))
    rep = cluster.run()
    by_rid = {r.rid: r for r in rep.requests}
    for r in trace:
        got = by_rid[r.rid]
        if r.model == "toy-code":
            assert got.finish_reason == "rejected" and got.worker is None
        else:
            assert got.worker not in (None, 2) and got.finish_reason != "rejected"
    assert len(rep.workers[2].requests) == 0
    # weighted round-robin follows the masked weights: worker 0 gets 1/4 of toy-chat (weights 1, 2, -, 1)
    chat = [by_rid[r.rid].worker for r in sorted(trace, key=lambda r: r.arrival) if r.model == "toy-chat"]
    assert chat[:4] == [0, 1, 1, 3]

    # a second failure on the drained worker pauses its model too, but drains no other worker
    health.fail(2, "toy-base")
    assert health.paused_models() == ["toy-code", "toy-base"]
    assert health.drained_workers() == [2]

    # failure in the first worker / first model (the corner the in-place masking uses as its markers)
    corner = HealthMatrix(3, MODELS)
    corner.fail(0, "toy-chat")
    assert corner.masked() == [[0, 0, 0], [0, 1, 1], [0, 1, 1]]
    assert all(w != 0 for w in corner.route(trace).values() if w is not None)


def test_dashboard_demo_runs(capsys):
    assert dashboard_main(["--n", "12", "--workers", "2", "--filter", "r0", "--k", "3"]) == 0
    out = capsys.readouterr().out
    assert "occupancy heatmap" in out and "slowest 3" in out and "health matrix" in out
    assert "requests on drained workers: 0" in out
