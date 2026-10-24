"""M2 integration: the offline batch planner — its numbers vs brute force and vs the real server."""
import itertools
from collections import Counter

import pytest

from nanoserve.engine import Engine
from nanoserve.server.planner import (BatchPlanner, PlannedQueue, fresh_batch, mean_latency,
                                      release_one_per_tick, waited)
from nanoserve.server.request import Request
from nanoserve.server.server import ServerConfig
from nanoserve.server.trace import PROMPTS, make_trace

pytestmark = pytest.mark.milestone("M2")


@pytest.fixture(scope="module")
def planner():
    return BatchPlanner(Engine(), ServerConfig(max_batch=3))


@pytest.fixture(scope="module")
def batch():
    return make_trace(14, seed=21, rate=0.4, deadline_slack=(0, 40))


@pytest.fixture(scope="module")
def plan(planner, batch):
    return planner.plan(batch, lanes=3, cooldown=2)


def test_service_estimate_is_exact_on_the_server(planner, batch):
    rep = planner.run(batch, max_batch=1)
    dur = dict(zip([r.rid for r in batch], planner.durations(batch)))
    assert all(r.finished_at - r.admitted_at == dur[r.rid] for r in rep.finished)


def test_sjf_plan_is_followed_and_beats_fcfs(planner):
    # one long job first, then a stream of short ones: FCFS makes them all wait behind it and each other
    reqs = [Request(rid="long", prompt=PROMPTS[3], arrival=0, max_tokens=40)]
    reqs += [Request(rid=f"s{i}", prompt=PROMPTS[0], arrival=1 + i, max_tokens=24 - 4 * (i % 5), seed=i)
             for i in range(8)]
    order = planner.sjf(reqs)
    sjf = planner.run(reqs, order=order)
    fcfs = planner.run(reqs)
    assert [r.rid for r in sorted(sjf.finished, key=lambda r: r.admitted_at)] == [r.rid for r in order]
    assert order[0].rid == "long"                       # non-preemptive: it was alone at t=0
    assert mean_latency(sjf) < mean_latency(fcfs)
    assert sjf.ticks == fcfs.ticks                      # same work, same makespan; only the order differs
    assert sjf.outputs() == fcfs.outputs()


def test_plan_summary_is_consistent_with_the_server(plan, batch):
    assert plan.sjf_followed
    assert plan.sjf_mean_latency <= plan.fcfs_mean_latency
    assert plan.min_lanes_waits == 0                    # min_lanes lanes: nobody queues
    assert plan.fewer_lanes_waits is None or plan.fewer_lanes_waits > 0
    assert plan.slo_bound >= max(plan.slo_met_fcfs, plan.slo_met_sjf)
    assert plan.hottest_lane == plan.measured_hottest_lane
    assert sum(plan.lane_counts) == len(batch)
    assert plan.lines() and all(isinstance(line, str) for line in plan.lines())


def test_min_lanes_is_the_peak_concurrency(planner, batch):
    occ = planner.occupancy(batch)
    peak = max(sum(s <= t <= e for s, e in occ) for t in range(min(s for s, _ in occ), max(e for _, e in occ) + 1))
    w = planner.min_lanes(batch)
    assert w == peak
    assert not waited(planner.run(batch, max_batch=w))
    if w > 1:
        assert waited(planner.run(batch, max_batch=w - 1))


def test_launch_count_is_minimal_by_brute_force(planner):
    reqs = make_trace(9, seed=22, rate=0.5, deadline_slack=(5, 25))
    windows, infeasible = planner.launch_windows(reqs)
    # trace deadlines ignore prefill: whoever can't finish even when started on arrival is reported apart
    dur = dict(zip([r.rid for r in reqs], planner.durations(reqs)))
    assert infeasible == [r.rid for r in reqs if r.arrival + dur[r.rid] > r.deadline]
    assert len(windows) + len(infeasible) == len(reqs) and len(windows) >= 6
    launches, _ = planner.launches(reqs)
    ends = sorted({e for _, e in windows})  # some optimal schedule launches only at window ends

    def feasible(times):
        return all(any(s <= t <= e for t in times) for s, e in windows)

    assert any(feasible(c) for c in itertools.combinations(ends, launches))
    assert not any(feasible(c) for c in itertools.combinations(ends, launches - 1))
    # a request whose deadline is shorter than its service time can't be planned at all
    late = Request(rid="late", prompt=PROMPTS[1], arrival=0, max_tokens=20, deadline=5)
    assert planner.launches(reqs + [late])[1] == infeasible + ["late"]


def _greedy_slots(adapters, n):
    """Oracle: every slot, run the free adapter with the most remaining work (else idle)."""
    left, ready_at, t = Counter(adapters), {}, 0
    while sum(left.values()):
        free = [a for a in left if left[a] and ready_at.get(a, 0) <= t]
        if free:
            a = max(free, key=lambda x: (left[x], x))
            left[a] -= 1
            ready_at[a] = t + n + 1
        t += 1
    return t


def test_lora_cooldown_slots_match_greedy_schedule(planner):
    reqs = make_trace(20, seed=23, tenants=("a", "b", "c", "d"), tenant_weights=(6, 2, 1, 1))
    for cd in (0, 1, 2, 4):
        assert planner.lora_slots(reqs, cd) == _greedy_slots([r.tenant for r in reqs], cd)
    assert planner.lora_slots(reqs, 0) == len(reqs)


def test_slo_bound_brute_force_and_never_beaten(planner):
    reqs = make_trace(7, seed=24, rate=0.3, deadline_slack=(-5, 30))
    jobs = planner.slo_jobs(reqs)
    best = 0
    for order in itertools.permutations(jobs):
        t, done = 0, 0
        for d, dl in order:          # take a job iff it still fits (a permutation covers every subset)
            if t + d <= dl:
                t, done = t + d, done + 1
        best = max(best, done)
    assert planner.slo_bound(reqs) == best
    for rep in (planner.run(reqs), planner.run(reqs, order=planner.sjf(reqs))):
        assert sum(1 for r in rep.finished if r.met_deadline) <= best


def test_hottest_lane_matches_the_server(planner):
    for seed, lanes in ((25, 2), (26, 3), (27, 4)):
        released = release_one_per_tick(fresh_batch(make_trace(15, seed=seed)))
        rep = planner.run(released, max_batch=lanes)
        counts = Counter(r.slot - 1 for r in rep.finished)
        top = max(counts.values())
        assert planner.hottest_lane(released, lanes) == min(l for l in range(lanes) if counts[l] == top)


def test_planned_queue_protocol():
    reqs = make_trace(4, seed=28)
    q = PlannedQueue(["r002", "r000", "r003", "r001"])
    for r in reqs:
        q.push(r)
    assert [r.rid for r in q] == ["r002", "r000", "r003", "r001"] and len(q) == 4
    q.remove(reqs[3])                                    # r003
    second = q.pop() and q.pop()                         # r002, then r000
    q.push_front(second)                                 # a preempted request goes back first
    assert q.peek() is second and [r.rid for r in q] == ["r000", "r001"]
