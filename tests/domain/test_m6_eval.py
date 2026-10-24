"""M6 integration: the evaluation harness scores server outputs and checks the multiplexed stream."""
import pytest

from nanoserve.engine import Engine
from nanoserve.eval.harness import (DEFAULT_EXAMPLES, Example, check_pattern, check_streams, corrupt_events,
                                    edit_score, evaluate, is_stream_of, normalize, rouge_l)
from nanoserve.server.server import ServerConfig

pytestmark = pytest.mark.milestone("M6")


@pytest.fixture(scope="module")
def report():
    return evaluate(DEFAULT_EXAMPLES, ServerConfig(max_batch=4), engine=Engine(), spacing=1)


def test_every_example_is_served_and_scored(report):
    assert len(report.scores) == len(DEFAULT_EXAMPLES) and not report.meta["rejected"]
    for s in report.scores:
        out, ref = normalize(s.output), normalize(s.reference)
        assert abs(len(out) - len(ref)) <= s.edit <= max(len(out), len(ref))
        assert (s.edit == 0) == (out == ref) == s.exact_match
        assert 0.0 <= s.rouge_f1 <= 1.0
        if s.exact_match:
            assert s.rouge_f1 == 1.0
    assert any(s.exact_match for s in report.scores) and not all(s.exact_match for s in report.scores)
    assert 0 < report.mean_rouge_f1 < 1


def test_metrics_on_known_pairs():
    assert edit_score("The cache,\nis  FULL.", "the cache is full") == 0  # normalisation
    assert edit_score("blocks", "block") == 1
    assert edit_score("a tree", "the tree") == 3
    p, r, f1 = rouge_l("the cache is a tree", "The prefix cache is a tree.")
    assert (p, r) == (1.0, 5 / 6) and f1 == pytest.approx(2 * 5 / 6 / (1 + 5 / 6))
    assert rouge_l("queue model", "model queue")[2] == 0.5   # LCS respects order
    assert rouge_l("", "the tree") == (0.0, 0.0, 0.0)


def test_output_constraints(report):
    for s in report.scores:
        assert check_pattern(s.output, ".*")                       # anything
        assert check_pattern(s.output, normalize(s.output))        # itself, literally
        if s.pattern is not None:
            assert s.pattern_ok == check_pattern(s.output, s.pattern)
    oks = [s.pattern_ok for s in report.scores if s.pattern_ok is not None]
    assert True in oks and False in oks
    assert check_pattern("The prefix cache is a tree.", "the pre.* cache is a tre*")
    assert check_pattern("The cache is a tr.", "the cache is a tre*")      # 'e*' may be empty
    assert not check_pattern("The cache", "the cach")                        # must cover ALL of the output
    assert not check_pattern("The cache", "the cache.")                      # '.' needs one more char
    assert not check_pattern("jazz", "jaz")                                  # symbols outside the corpus
    with pytest.raises(ValueError):
        check_pattern("tree", "*tree")


def test_multiplexed_stream_is_an_interleaving(report):
    sc = report.stream
    assert sc.ok
    assert len(sc.pairs) >= len(DEFAULT_EXAMPLES)  # batching really ran requests concurrently
    rids = {r for p in sc.pairs for r in p} | set(sc.solos)
    assert rids == {ex.eid for ex in DEFAULT_EXAMPLES}


def test_sampled_and_spread_out_streams_are_interleavings():
    examples = [Example(f"s{i}", ex.prompt, ex.reference, max_tokens=30, stop=())
                for i, ex in enumerate(DEFAULT_EXAMPLES[:8])]
    rep = evaluate(examples, ServerConfig(max_batch=3), spacing=7, temperature=0.8, seed=4)
    assert rep.stream.ok and rep.stream.pairs and len(rep.scores) == 8


@pytest.mark.parametrize("kind", ["swap", "drop", "dup"])
def test_corrupted_stream_is_detected(report, kind):
    for seed in range(3):
        events, rid = corrupt_events(report.server.events, kind, seed=seed)
        sc = check_streams(report.server.requests, events)
        assert not sc.ok
        assert all(rid in bad for bad in sc.bad)  # only checks involving the damaged request fail


def test_stream_check_on_raw_text():
    # raw engine text: capitals, spaces, punctuation, newlines are compared as-is
    a, b = "The Cache, Engine.", "A tree;\nWhen"
    merged = "A Thter Cee;a\nWchenhe, Engine."
    assert is_stream_of(a, b, merged)
    assert not is_stream_of(a, b, merged.replace("E", "e"))
    assert not is_stream_of(a, b, merged.replace("Engine.", "Engin.e"))  # "." of a delivered too early
    assert is_stream_of("缓存 hit.", "", "缓存 hit.") and not is_stream_of("缓存 hit.", "", "存缓 hit.")
