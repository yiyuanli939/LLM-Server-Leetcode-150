"""M4 integration: the prompt prefix cache inside the server (nanoserve.prefix.cache.PrefixCache)."""
import math
import random
from statistics import mean

import pytest

from nanoserve.engine import Engine
from nanoserve.prefix.cache import PrefixCache
from nanoserve.server.plugins import PrefixCacheBackend
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import PROMPTS, SYSTEM, make_trace

pytestmark = pytest.mark.milestone("M4")


@pytest.fixture(scope="module")
def engine():
    return Engine()


def _run(engine, cache: bool, *, n=40, seed=0, rate=0.5, chunk=4, watch=None):
    cfg = ServerConfig(max_batch=4, prefill_chunk=chunk, prefix_cache=cache)
    pc = PrefixCache(engine.tokenizer, watch=watch) if (cache and watch is not None) else None
    server = Server(engine, cfg, prefix_cache=pc)                    # pc=None → built from the config flag
    server.submit_many(make_trace(n, seed=seed, rate=rate))
    return server, server.run()


def _prefill_ticks(engine, report, chunk):
    total = 0
    for r in report.finished:
        rest = r.prompt[r.cached_chars:]
        total += math.ceil(len(engine.tokenizer.encode(rest)) / chunk) if rest else 0
    return total


def test_config_flag_plugs_in_the_prefix_cache(engine):
    server = Server(engine, ServerConfig(prefix_cache=True))
    assert isinstance(server.prefix_cache, PrefixCache)
    assert isinstance(server.prefix_cache, PrefixCacheBackend)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_prefix_cache_cuts_prefill_and_ttft_without_changing_outputs(engine, seed):
    _, base = _run(engine, cache=False, seed=seed)
    _, cached = _run(engine, cache=True, seed=seed)
    n = len(base.requests)
    assert len(base.finished) == len(cached.finished) == n
    assert cached.outputs() == base.outputs()                        # the cache never changes generated text
    assert all(r.cached_chars == 0 for r in base.finished)
    assert _prefill_ticks(engine, cached, 4) < _prefill_ticks(engine, base, 4)
    assert mean(r.ttft for r in cached.finished) < mean(r.ttft for r in base.finished)
    assert cached.ticks <= base.ticks
    rep = cached.plugins["prefix_cache"]
    assert rep["lookups"] == n and rep["hits"] + rep["misses"] == n and rep["hits"] > 0
    # default watch = shared prefix of the cached prompts (common_prefix, whole tokens): the system prompt
    (shared, under), = rep["under"].items()
    assert shared == SYSTEM.rstrip()
    assert under["hits"] == sum(r.prompt[:r.cached_chars].startswith(shared) for r in cached.finished) > 0


def _token_lcp(a, b):
    k = 0
    while k < min(len(a), len(b)) and a[k] == b[k]:
        k += 1
    return k


def test_match_is_longest_cached_token_prefix(engine):
    """Oracle: max over cached prompts of the common *token* prefix, converted back to characters."""
    tok = engine.tokenizer
    rng = random.Random(4)
    pool = sorted({p[:cut] for p in PROMPTS for cut in range(1, len(p) + 1, 3)} | set(PROMPTS))
    cache = PrefixCache(tok)
    cached: list[list[int]] = []
    for step in range(120):
        prompt = rng.choice(pool)
        ids = tok.encode(prompt)
        best = max((_token_lcp(ids, c) for c in cached), default=0)
        got = cache.match(prompt)
        assert got == len(tok.decode(ids[:best]))
        assert prompt[:got] == tok.decode(ids[:best])                 # ends on a token boundary
        assert tok.encode(prompt[got:]) == ids[best:]                 # server's "uncached" tokens are exact
        if rng.random() < 0.4:
            cache.insert(prompt)
            cached.append(ids)
    rep = cache.report()
    assert rep["lookups"] == 120 and rep["cached_prompts"] == len({tok.decode(c) for c in cached})


def test_hit_statistics_match_what_the_server_saw(engine):
    server, report = _run(engine, cache=True, n=50, seed=3, rate=0.6, watch=[SYSTEM, "The "])
    rep = report.plugins["prefix_cache"]
    fin = report.finished
    reused = [r.prompt[:r.cached_chars] for r in fin if r.cached_chars]
    assert rep["hits"] == len(reused) and rep["misses"] == len(fin) - len(reused)
    assert rep["chars_saved"] == sum(r.cached_chars for r in fin)
    assert rep["full_hits"] == sum(r.cached_chars == len(r.prompt) for r in fin)
    tok = engine.tokenizer
    assert rep["tokens_saved"] == sum(len(tok.encode(s)) for s in reused)
    # per-prefix breakdown (PrefixHitSum): hits that reused at least the whole system prompt
    sys_hits = [s for s in reused if s.startswith(SYSTEM.rstrip())]
    assert rep["under"][SYSTEM]["hits"] == len(sys_hits) > 0
    assert rep["under"][SYSTEM]["tokens_saved"] == sum(len(tok.encode(s)) for s in sys_hits)
    the_hits = [s for s in reused if s.startswith("The")]
    assert rep["under"]["The "]["hits"] == len(the_hits)
    assert server.prefix_cache.hits_under("") == rep["hits"]


def test_shared_prefix_is_the_most_shared_whole_token_prefix(engine):
    tok = engine.tokenizer
    cache = PrefixCache(tok)
    assert cache.shared_prefix() == "" and "under" not in cache.report()
    cache.insert("The scheduler")
    assert cache.shared_prefix() == ""                               # one prompt shares nothing
    cache.insert("The scheduler wakes")
    assert cache.shared_prefix() == "The scheduler"                  # fewer than min_share: all of them
    for p in PROMPTS:
        cache.insert(p)
    shared = cache.shared_prefix()
    assert shared == SYSTEM.rstrip()                                 # 4 prompts start with the system prompt
    assert tok.encode(shared) == tok.encode(SYSTEM)[:len(tok.encode(shared))]   # whole tokens
    assert sum(p.startswith(shared) for p in PROMPTS) >= cache.min_share
    cache.match(SYSTEM + "The cache")
    assert cache.report()["under"][shared]["hits"] == 1
