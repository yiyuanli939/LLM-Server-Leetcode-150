import random

import pytest

from nanoserve.tokenizer.prefix import common_prefix
from nanoserve.tokenizer.segment import can_segment


# ---------------------------------------------------------------- tok.segment

def _segment_oracle(text, vocab):
    words = set(vocab)
    memo = {}

    def go(i):
        if i == len(text):
            return True
        if i not in memo:
            memo[i] = any(go(j) for j in range(i + 1, len(text) + 1) if text[i:j] in words)
        return memo[i]

    return go(0)


@pytest.mark.exercise("tok.segment")
def test_tok_segment_examples():
    assert can_segment("nanoserve", ["nano", "serve"]) is True
    assert can_segment("applepenapple", ["apple", "pen"]) is True
    assert can_segment("catsandog", ["cats", "dog", "sand", "and", "cat"]) is False


@pytest.mark.exercise("tok.segment")
def test_tok_segment_empty_text():
    assert can_segment("", ["a"]) is True


@pytest.mark.exercise("tok.segment")
def test_tok_segment_reuse_and_spaces():
    assert can_segment("aaaaaaa", ["aaaa", "aaa"]) is True
    assert can_segment("The cache. The", ["T", "he", " cache", ".", " "]) is True
    assert can_segment("The cache!", ["T", "he", " cache", ".", " "]) is False


@pytest.mark.exercise("tok.segment")
def test_tok_segment_greedy_trap():
    # greedy longest-match would take "abcd" and get stuck
    assert can_segment("abcde", ["abcd", "abc", "de"]) is True
    assert can_segment("ab", ["abc"]) is False


@pytest.mark.exercise("tok.segment")
def test_tok_segment_worst_case_is_polynomial():
    vocab = ["a" * i for i in range(1, 11)]
    assert can_segment("a" * 300 + "b", vocab) is False
    assert can_segment("a" * 300, vocab) is True


@pytest.mark.exercise("tok.segment")
def test_tok_segment_random():
    rng = random.Random(139)
    for _ in range(300):
        vocab = list({"".join(rng.choice("ab") for _ in range(rng.randint(1, 4))) for _ in range(rng.randint(1, 5))})
        text = "".join(rng.choice("ab") for _ in range(rng.randint(0, 14)))
        assert can_segment(text, vocab) == _segment_oracle(text, vocab), (text, vocab)


# ---------------------------------------------------------------- tok.common_prefix

@pytest.mark.exercise("tok.common_prefix")
def test_tok_common_prefix_examples():
    assert common_prefix(["flower", "flow", "flight"]) == "fl"
    assert common_prefix(["dog", "racecar", "car"]) == ""


@pytest.mark.exercise("tok.common_prefix")
def test_tok_common_prefix_system_prompt():
    assert common_prefix(["The scheduler wakes", "The scheduler sleeps"]) == "The scheduler "


@pytest.mark.exercise("tok.common_prefix")
def test_tok_common_prefix_empty_inputs():
    assert common_prefix([]) == ""
    assert common_prefix([""]) == ""
    assert common_prefix(["abc", ""]) == ""


@pytest.mark.exercise("tok.common_prefix")
def test_tok_common_prefix_single_and_identical():
    assert common_prefix(["only"]) == "only"
    assert common_prefix(["same", "same", "same"]) == "same"
    assert common_prefix(["ab", "a", "abc"]) == "a"
    assert common_prefix(["Abc", "abc"]) == ""


@pytest.mark.exercise("tok.common_prefix")
def test_tok_common_prefix_random():
    rng = random.Random(14)
    for _ in range(300):
        prompts = ["".join(rng.choice("ab ") for _ in range(rng.randint(0, 6))) for _ in range(rng.randint(1, 5))]
        n = 0
        while all(len(p) > n for p in prompts) and len({p[n] for p in prompts}) == 1:
            n += 1
        assert common_prefix(prompts) == prompts[0][:n]


