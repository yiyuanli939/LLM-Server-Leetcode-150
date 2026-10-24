"""M1 integration test: the engine generates end-to-end with your M1 implementations."""
import pytest

from nanoserve.engine import Engine, GenerationConfig
from nanoserve.tokenizer.tokenizer import UnknownCharacterError

pytestmark = pytest.mark.milestone("M1")


@pytest.fixture(scope="module")
def engine():
    return Engine()


def test_deterministic_with_seed(engine):
    cfg = GenerationConfig(max_tokens=40, seed=7)
    a = engine.generate("The scheduler", cfg).text
    b = engine.generate("The scheduler", cfg).text
    assert a == b and len(a) > 0


def test_stream_chunks_concatenate_to_result(engine):
    cfg = GenerationConfig(max_tokens=50, seed=3)
    chunks = list(engine.stream("The model", cfg))
    assert "".join(chunks) == engine.last_result.text


def test_word_stream_emits_whole_words(engine):
    cfg = GenerationConfig(max_tokens=60, seed=11, word_stream=True)
    chunks = list(engine.stream("The cache", cfg))
    prefix = ""
    for c in chunks[:-1]:
        prefix += c
        assert prefix[-1].isspace(), f"chunk boundary splits a word: {prefix[-15:]!r}"


def test_stop_string_truncates(engine):
    cfg = GenerationConfig(max_tokens=200, seed=1, stop=(".",))
    res = engine.generate("The engine", cfg)
    assert "." not in res.text
    assert res.finish_reason in ("stop", "length")


def test_greedy_matches_top1(engine):
    greedy = engine.generate("The sampler", GenerationConfig(max_tokens=30, temperature=0)).text
    top1 = engine.generate("The sampler", GenerationConfig(max_tokens=30, temperature=0.7, top_k=1, seed=5)).text
    assert greedy == top1


def test_no_repeat_window(engine):
    cfg = GenerationConfig(max_tokens=60, seed=2, no_repeat_window=3, temperature=1.2, top_k=20)
    ids = engine.generate("The queue", cfg).token_ids
    for i in range(len(ids)):
        assert ids[i] not in ids[max(0, i - 3):i]


def test_unknown_character_rejected(engine):
    with pytest.raises(UnknownCharacterError):
        engine.tokenizer.encode("emoji 🚀 here")


def test_render_respects_width(engine):
    res = engine.generate("The batch", GenerationConfig(max_tokens=60, seed=4))
    lines = engine.render(res.text, 30)
    assert lines and all(len(l) == 30 for l in lines)


def test_stats_and_shared_prefix(engine):
    res = engine.generate("The metrics", GenerationConfig(max_tokens=30, seed=9))
    assert res.stats["longest_unique_run"] >= 1
    assert engine.shared_prefix(["The scheduler wakes", "The scheduler sleeps"]) == "The scheduler "


def test_multiple_stop_strings_cut_at_earliest(engine):
    cfg = GenerationConfig(max_tokens=200, seed=3, stop=(",", ".", "\n"))
    res = engine.generate("The engine", cfg)
    assert not any(s in res.text for s in (",", ".", "\n"))
    # without stops the same seed produces a continuation that starts with our text
    free = engine.generate("The engine", GenerationConfig(max_tokens=200, seed=3)).text
    assert free.startswith(res.text)
    if res.finish_reason == "stop":
        assert free[len(res.text)] in ",.\n"


def _brute_overlap(text, stop):
    return max((j for j in range(len(stop)) if j and text.endswith(stop[:j])), default=0)


def test_stop_holdback_is_exact(engine):
    stop = " the queue."
    cfg = GenerationConfig(max_tokens=80, seed=5, stop=(stop,), word_stream=False)
    st = engine.start("The scheduler", cfg)
    while not st.done:
        engine.step(st)
        if not st.done:
            assert len(st.text) - st.emitted == _brute_overlap(st.text, stop)


def test_vocab_uses_most_frequent_words(engine):
    tok = engine.tokenizer
    merged = [t for t in tok.vocab if len(t) > 1]
    assert merged and all(t.startswith(" ") for t in merged)
    assert len(set(merged)) == len(merged)
    assert " the" in merged and " model" in merged
