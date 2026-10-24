"""M7 integration: capacity planning closes the loop on the real server — each estimate is enough,
one unit less is not."""
from itertools import combinations

import pytest

from nanoserve.autoscale.autoscaler import POOL, Autoscaler, WorkerKind, burst, ordered_job
from nanoserve.autoscale.demo import main as autoscale_main
from nanoserve.engine import Engine
from nanoserve.server.cluster import Cluster
from nanoserve.server.planner import fresh_batch
from nanoserve.server.server import ServerConfig

pytestmark = pytest.mark.milestone("M7")


@pytest.fixture(scope="module")
def scaler():
    return Autoscaler(Engine())


def test_too_small_cluster_misses_and_recommended_pool_meets_the_target(scaler):
    reqs = burst(30)
    target = 40
    # a plain M2 cluster of the starting size (2 single-stream replicas) misses the target
    small = Cluster(2, engine=scaler.engine, config=ServerConfig(max_batch=1), policy="weighted", seed=1)
    small.submit_many(fresh_batch(reqs))
    srep = small.run()
    assert len(srep.finished) == 30 and srep.ticks > target

    rec = scaler.size_pool(POOL, reqs, target, start=2)
    assert rec.run_start.ticks > target
    assert rec.size > 2 and rec.estimate <= target < rec.estimate_fewer
    # the estimate is exactly what the server does under the optimal plan
    assert rec.run.ticks == rec.estimate and rec.meets_target
    assert rec.run_fewer.ticks == rec.estimate_fewer > target
    assert sorted(r.rid for r in rec.run.finished) == sorted(r.rid for r in reqs)
    # brute force over every subset of the pool: no smaller set of workers meets the target
    times = [scaler.per_request(k, reqs[0]) for k in POOL]

    def best(ts):  # brute-force min makespan
        t = 1
        while sum(t // x for x in ts) < len(reqs):
            t += 1
        return t

    assert rec.estimate == best(rec.per_request[:rec.size])
    assert all(best([times[i] for i in c]) > target for c in combinations(range(len(POOL)), rec.size - 1))


def test_heterogeneous_kinds_change_per_request_time(scaler):
    r = burst(1)[0]
    fast, slow = WorkerKind("fast", 16), WorkerKind("slow", 2)
    assert scaler.per_request(fast, r) < scaler.per_request(slow, r)
    # an impossible target: the whole pool is not enough
    rec = scaler.size_pool(POOL, burst(30), target=3, validate=False)
    assert rec.estimate is None


@pytest.mark.parametrize("queues,horizon", [({"a": 7, "b": 3, "c": 11, "d": 5}, 40),
                                            ({"a": 9, "b": 9}, 25),
                                            ({"a": 1, "b": 2, "c": 12}, 30)])
def test_batch_size_per_adapter_launch_drains_by_the_horizon(scaler, queues, horizon):
    rec = scaler.size_batch(queues, horizon)
    run = rec.run
    assert len(run.finished) == sum(queues.values()) and run.ticks <= horizon
    # every launch serves exactly one tenant, and launches never overlap
    spans = {}
    for r in run.finished:
        spans.setdefault(r.admitted_at, set()).add(r.tenant)
    assert all(len(t) == 1 for t in spans.values())
    assert sorted(spans) == [t for t, _ in rec.launch_log]
    assert len(rec.launch_log) <= rec.launches
    # brute force: the smallest batch size b with sum ceil(q / b) <= launches
    b = 1
    while sum(-(-q // b) for q in queues.values()) > rec.launches:
        b += 1
    assert rec.max_batch == b
    if b > 1:
        assert rec.run_less.ticks > horizon


def test_adapter_queue_infeasible_horizon_is_reported(scaler):
    with pytest.raises(ValueError):
        scaler.size_batch({"a": 1, "b": 1, "c": 1}, horizon=6)  # 1 launch of 5 ticks for 3 tenants


@pytest.mark.parametrize("n,waves,seed", [(12, 4, 0), (10, 3, 1), (8, 8, 2), (9, 1, 3)])
def test_token_budget_per_wave_fits_the_ordered_job(scaler, n, waves, seed):
    reqs = ordered_job(n, seed)
    rec = scaler.size_waves(reqs, waves)
    assert len(rec.plan) <= waves and [rid for w in rec.plan for rid in w] == [r.rid for r in reqs]
    # with budget C nobody waits past the release of its wave: the plan is what happened
    assert len(rec.run.finished) == n and rec.waited(rec.run) == 0
    # brute force: no smaller budget packs the ordered job into <= waves contiguous waves
    for c in range(max(rec.work), rec.budget):
        assert len(scaler.pack_waves(rec.work, c)) > waves
    if rec.run_less is not None:
        assert rec.waited(rec.run_less) > 0
    else:
        assert rec.budget == max(rec.work)


def test_autoscale_demo_validates_all_estimates(capsys):
    assert autoscale_main([]) == 0
    assert "all estimates validated: True" in capsys.readouterr().out
