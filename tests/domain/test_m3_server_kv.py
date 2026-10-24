"""M3 integration: the paged KV-cache manager plugged into the server (ServerConfig.kv_blocks)."""
import pytest

from nanoserve.engine import Engine
from nanoserve.kvcache.manager import BlockManager
from nanoserve.server.plugins import KVBackend
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import make_trace

pytestmark = pytest.mark.milestone("M3")


@pytest.fixture(scope="module")
def engine():
    return Engine()


@pytest.fixture(scope="module")
def unlimited(engine):
    srv = Server(engine, ServerConfig(max_batch=4))
    srv.submit_many(make_trace(20, seed=0))
    return srv.run()


def _run(engine, debug=False, **kw):
    srv = Server(engine, ServerConfig(max_batch=4, **kw))
    srv.kv.debug = debug               # debug: every KV operation re-checks all invariants
    srv.submit_many(make_trace(20, seed=0))
    return srv, srv.run()


def test_build_plugins_instantiates_the_block_manager(engine):
    srv = Server(engine, ServerConfig(kv_blocks=32, block_size=8, eviction="lfu"))
    assert isinstance(srv.kv, BlockManager) and isinstance(srv.kv, KVBackend)
    assert (srv.kv.num_blocks, srv.kv.block_size, srv.kv.eviction) == (32, 8, "lfu")


@pytest.mark.parametrize("eviction", ["lru", "lfu", "random"])
def test_small_budget_preempts_but_outputs_match_unlimited_run(engine, unlimited, eviction):
    srv, rep = _run(engine, debug=True, kv_blocks=14, block_size=8, eviction=eviction)
    assert len(rep.finished) == 20 and not rep.rejected
    assert sum(r.preemptions for r in rep.requests) > 0          # memory pressure was real
    assert rep.outputs() == unlimited.outputs()                  # ... and changed no output
    kv = rep.plugins["kv"]
    assert kv["peak_in_use"] <= 14
    assert kv["in_use"] == 0 and kv["charged"] == {}            # everything released
    assert not kv["problems"] and not kv["leaks"] and kv["quarantined"] == []
    assert kv["offloaded"] > 0 and kv["restored"] > 0           # host tier in action
    assert kv["shared"] > 0 and kv["revived"] > 0                # prefix blocks shared and reused
    assert srv.kv.check() == []


def test_generous_budget_never_preempts_and_keeps_the_schedule(engine, unlimited):
    _, rep = _run(engine, kv_blocks=64, block_size=8)
    assert sum(r.preemptions for r in rep.requests) == 0
    assert rep.outputs() == unlimited.outputs()
    assert [r.finished_at for r in rep.requests] == [r.finished_at for r in unlimited.requests]


def test_shared_prompt_prefix_is_stored_once(engine):
    # Two requests with the same 47-token system-prompt prompt running at the same time share
    # its full blocks instead of storing them twice.
    srv, rep = _run(engine, kv_blocks=64, block_size=8)
    kv = rep.plugins["kv"]
    assert kv["shared"] >= 5 and kv["prompt_block_hit_rate"] > 0.5
    mgr = srv.kv
    # the dedup table maps every cached block's chain hash back to that block
    for b in mgr.cached:
        assert mgr.table.get(mgr.hash_of[b]) == b


def test_more_blocks_never_hurt(engine):
    ticks = []
    for kb in (12, 16, 24, 40):
        _, rep = _run(engine, kv_blocks=kb, block_size=8)
        assert len(rep.finished) == 20
        ticks.append(rep.ticks)
    assert ticks == sorted(ticks, reverse=True) and ticks[0] > ticks[-1]


def test_request_that_can_never_fit_is_rejected(engine):
    from nanoserve.server.trace import PROMPTS
    from nanoserve.server.request import Request
    srv = Server(engine, ServerConfig(max_batch=2, kv_blocks=4, block_size=8))
    srv.submit(Request("big", PROMPTS[10], max_tokens=4))       # 60 prompt tokens > 4 blocks of 8
    srv.submit(Request("ok", PROMPTS[0], max_tokens=4, arrival=1))
    rep = srv.run()
    assert [r.rid for r in rep.rejected] == ["big"]
    assert [r.rid for r in rep.finished] == ["ok"]
    assert rep.plugins["kv"]["problems"] == []
