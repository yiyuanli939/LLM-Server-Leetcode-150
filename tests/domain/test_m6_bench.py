"""M6 integration: benchmark grid, arrival-order determinism, config pre-check fuzzing."""
import pytest

from nanoserve.bench.runner import (CORE_TOGGLES, OPTIONAL_TOGGLES, Toggle, available_toggles,
                                    check_arrival_orders, config_for, fuzz_brackets, grid, run_grid)
from nanoserve.server.server import ServerConfig

pytestmark = pytest.mark.milestone("M6")


def test_grid_is_k_of_n_combinations():
    combos = grid(CORE_TOGGLES, sizes=(1, 2))
    n = len(CORE_TOGGLES)
    assert len(combos) == 1 + n + n * (n - 1) // 2
    assert len({tuple(t.name for t in c) for c in combos}) == len(combos)
    assert combos[0] == ()
    clash = [Toggle("b2", (("max_batch", 2),)), Toggle("b8", (("max_batch", 8),))]
    assert grid(clash, sizes=(2,)) == [()]  # toggles setting the same field never combine
    cfg = config_for(ServerConfig(), combos[-1])
    assert all(getattr(cfg, f) == v for t in combos[-1] for f, v in t.overrides)


def test_grid_run_tabulates_and_never_changes_outputs():
    rows = run_grid(CORE_TOGGLES, sizes=(1, 2), base=ServerConfig(max_batch=4))
    base = rows[0]
    by_name = {r.name: r for r in rows}
    for r in rows:
        assert len(r.report.finished) == 16 and not r.report.rejected
        assert 0 < r.utilization <= 1 and 0 < r.occupancy <= 1
        assert r.same_outputs in (None, True)  # admission/batching knobs must not change any output
    # crafted expectations: more slots → lower median latency; throttles → longer makespan
    assert by_name["batch8"].p50 < base.p50
    assert by_name["budget"].report.ticks > base.report.ticks
    assert by_name["prefill4"].report.ticks > base.report.ticks


def test_unavailable_features_are_skipped_not_crashed():
    fake = Toggle("warp", (("max_batch", 64),), "nanoserve.does_not_exist:Warp")
    ok, skipped = available_toggles(CORE_TOGGLES + OPTIONAL_TOGGLES + [fake])
    names = {t.name for t in ok}
    assert {t.name for t in CORE_TOGGLES} <= names
    assert "warp" not in names and "warp" in dict(skipped)
    assert names | set(dict(skipped)) == {t.name for t in CORE_TOGGLES + OPTIONAL_TOGGLES} | {"warp"}


def test_every_arrival_order_gives_the_same_outputs():
    res = check_arrival_orders(4, ServerConfig(max_batch=2))
    assert res.orders == 24
    assert res.finished_everywhere
    assert res.distinct_outputs == 1          # outputs do not depend on the order of same-tick arrivals
    assert res.distinct_schedules > 1         # ... although the schedules really differ
    assert res.ok


def test_config_precheck_fuzz():
    catalan = {1: 1, 2: 2, 3: 5, 4: 14, 5: 42}
    for n, c in catalan.items():
        res = fuzz_brackets(n)
        assert res.structures == c and res.valid_checked == 3 * c
        assert res.ok, (res.valid_rejected[:3], res.mutants_accepted[:3])
    # the fuzzer has teeth: a checker that only counts brackets is caught
    weak = fuzz_brackets(4, check=lambda s: sum(c in "([{" for c in s) * 2 == len(s))
    assert not weak.ok and weak.mutants_accepted and not weak.valid_rejected
