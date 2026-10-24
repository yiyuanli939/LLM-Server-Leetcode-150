"""M6 integration: speculative decoding with a k-best draft tree is exactly greedy decoding, in fewer passes."""
import itertools

import pytest

from nanoserve.decode.speculative import DRAFT_DEPTH, SpeculativeDecoder
from nanoserve.engine import Engine, GenerationConfig
from nanoserve.server.trace import PROMPTS

pytestmark = pytest.mark.milestone("M6")


@pytest.fixture(scope="module")
def engine():
    return Engine()


CASES = [
    ((), 40),
    ((".",), 60),
    ((" the queue", ","), 50),
]


@pytest.mark.parametrize("k", [1, 4, 16])
def test_output_identical_to_plain_greedy(engine, k):
    spec = SpeculativeDecoder(engine, k=k)
    for prompt, (stop, max_tokens) in itertools.product(PROMPTS[:8] + [""], CASES):
        cfg = GenerationConfig(temperature=0, max_tokens=max_tokens, stop=stop)
        plain = engine.generate(prompt, cfg)
        chunks = list(spec.stream(prompt, cfg))
        fast = spec.last_result
        assert fast.token_ids == plain.token_ids, (prompt, stop)
        assert fast.text == plain.text == "".join(chunks)
        assert fast.finish_reason == plain.finish_reason
        assert fast.stats["unverified_commits"] == 0  # every committed token came from a verification pass


def test_fewer_target_passes_than_tokens(engine):
    cfg = GenerationConfig(temperature=0, max_tokens=40)
    totals = {}
    for k in (1, 8, 16):
        spec = SpeculativeDecoder(engine, k=k)
        res = [spec.generate(p, cfg) for p in PROMPTS]
        tokens = sum(len(r.token_ids) for r in res)
        passes = sum(r.stats["target_passes"] for r in res)
        accepted = sum(r.stats["draft_accepted"] for r in res)
        assert passes < tokens and accepted > 0
        for r in res:
            # each pass commits its accepted drafts + one bonus token; only the last pass may be cut
            # short by max_tokens before its bonus token
            n, p = len(r.token_ids), r.stats["target_passes"]
            assert r.stats["draft_accepted"] in (n - p, n - p + 1)
            assert 0 <= r.stats["acceptance_rate"] <= 1
        totals[k] = passes, tokens
    passes8, tokens = totals[8]
    assert tokens / passes8 > 1.5  # the draft heads really do predict the target most of the time
    assert totals[16][0] < totals[1][0]  # a wider tree accepts more


def test_draft_tree_is_the_k_cheapest_pairs(engine):
    spec = SpeculativeDecoder(engine, k=8)
    heads = spec.heads
    for prompt in ("The scheduler", "The cache is made of", ""):
        ctx = engine.tokenizer.encode(prompt)
        tree = spec.draft(ctx)
        row = heads.V if not ctx else ctx[-1]
        cost = lambda a, b: int(heads.cost[0][row, a]) + int(heads.cost[1][row, b])
        assert len(tree.pairs) == 8 and len(set(tree.pairs)) == 8
        brute = sorted(cost(a, b) for a in range(heads.V) for b in range(heads.V))[:8]
        assert sorted(cost(a, b) for a, b in tree.pairs) == brute
        assert all(len(node) <= DRAFT_DEPTH for node in tree.nodes)


def test_stop_and_length_limits(engine):
    spec = SpeculativeDecoder(engine, k=8)
    res = spec.generate("The engine", GenerationConfig(temperature=0, max_tokens=200, stop=(".",)))
    assert res.finish_reason == "stop" and "." not in res.text
    for n in (1, 2, 3, 7):
        res = spec.generate("The scheduler", GenerationConfig(temperature=0, max_tokens=n))
        assert len(res.token_ids) == n and res.finish_reason == "length"


def test_sampling_is_rejected(engine):
    with pytest.raises(ValueError):
        SpeculativeDecoder(engine).generate("The cache", GenerationConfig(temperature=0.7))
