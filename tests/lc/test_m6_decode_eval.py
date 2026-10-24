"""Core exercises for milestone M6: decoding DP, evaluation metrics and benchmark generators."""
import itertools
import random
from functools import lru_cache

import pytest

from nanoserve.bench.fuzz import arrival_orders, balanced_brackets
from nanoserve.bench.sweep import choose
from nanoserve.decode.beam import k_best_pairs
from nanoserve.eval.metrics import edit_distance
from nanoserve.eval.streams import is_interleaving


# ---------------------------------------------------------------- eval.edit_distance

def _edit_oracle(a, b):
    @lru_cache(maxsize=None)
    def go(i, j):
        if i == len(a):
            return len(b) - j
        if j == len(b):
            return len(a) - i
        if a[i] == b[j]:
            return go(i + 1, j + 1)
        return 1 + min(go(i + 1, j), go(i, j + 1), go(i + 1, j + 1))

    return go(0, 0)


@pytest.mark.exercise("eval.edit_distance")
def test_eval_edit_distance_examples():
    assert edit_distance("horse", "ros") == 3
    assert edit_distance("intention", "execution") == 5


@pytest.mark.exercise("eval.edit_distance")
def test_eval_edit_distance_empty():
    assert edit_distance("", "") == 0
    assert edit_distance("abc", "") == 3
    assert edit_distance("", "abcd") == 4


@pytest.mark.exercise("eval.edit_distance")
def test_eval_edit_distance_identical_and_single():
    assert edit_distance("same", "same") == 0
    assert edit_distance("a", "b") == 1
    assert edit_distance("a", "a") == 0


@pytest.mark.exercise("eval.edit_distance")
def test_eval_edit_distance_symmetric():
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("sitting", "kitten") == 3


@pytest.mark.exercise("eval.edit_distance")
def test_eval_edit_distance_random():
    rng = random.Random(72)
    for _ in range(200):
        a = "".join(rng.choice("abc") for _ in range(rng.randint(0, 8)))
        b = "".join(rng.choice("abc") for _ in range(rng.randint(0, 8)))
        assert edit_distance(a, b) == _edit_oracle(a, b)


MIXED = "aA .,\n*é中"  # letters of both cases, space, punctuation, newline, '*', unicode


@pytest.mark.exercise("eval.edit_distance")
def test_eval_edit_distance_any_characters():
    assert edit_distance("The cache.", "the cache!") == 2       # case-sensitive, punctuation counts
    assert edit_distance("a b", "ab") == 1                       # spaces are ordinary characters
    assert edit_distance("line\n", "line") == 1
    assert edit_distance("café", "cafe") == 1
    assert edit_distance("缓存命中", "缓存未命中") == 1
    assert edit_distance("A", "a") == 1


@pytest.mark.exercise("eval.edit_distance")
def test_eval_edit_distance_random_mixed_alphabet():
    rng = random.Random(720)
    for _ in range(200):
        a = "".join(rng.choice(MIXED) for _ in range(rng.randint(0, 8)))
        b = "".join(rng.choice(MIXED) for _ in range(rng.randint(0, 8)))
        assert edit_distance(a, b) == _edit_oracle(a, b)


# ---------------------------------------------------------------- eval.interleave_ok

def _interleave_oracle(a, b, c):
    if len(a) + len(b) != len(c):
        return False

    @lru_cache(maxsize=None)
    def go(i, j):
        if i == len(a) and j == len(b):
            return True
        k = i + j
        return (i < len(a) and a[i] == c[k] and go(i + 1, j)) or (
            j < len(b) and b[j] == c[k] and go(i, j + 1)
        )

    return go(0, 0)


@pytest.mark.exercise("eval.interleave_ok")
def test_eval_interleave_ok_examples():
    assert is_interleaving("aabcc", "dbbca", "aadbbcbcac") is True
    assert is_interleaving("aabcc", "dbbca", "aadbbbaccc") is False
    assert is_interleaving("", "", "") is True


@pytest.mark.exercise("eval.interleave_ok")
def test_eval_interleave_ok_length_mismatch():
    assert is_interleaving("a", "b", "a") is False
    assert is_interleaving("a", "", "ab") is False
    assert is_interleaving("", "", "a") is False


@pytest.mark.exercise("eval.interleave_ok")
def test_eval_interleave_ok_one_empty():
    assert is_interleaving("", "abc", "abc") is True
    assert is_interleaving("abc", "", "abc") is True
    assert is_interleaving("abc", "", "acb") is False


@pytest.mark.exercise("eval.interleave_ok")
def test_eval_interleave_ok_order_within_stream():
    assert is_interleaving("ab", "cd", "acbd") is True
    assert is_interleaving("ab", "cd", "bacd") is False


@pytest.mark.exercise("eval.interleave_ok")
def test_eval_interleave_ok_random():
    rng = random.Random(97)
    for _ in range(300):
        a = "".join(rng.choice("ab") for _ in range(rng.randint(0, 6)))
        b = "".join(rng.choice("ab") for _ in range(rng.randint(0, 6)))
        if rng.random() < 0.5:
            # build a true interleaving
            ia, ib, out = 0, 0, []
            while ia < len(a) or ib < len(b):
                if ib == len(b) or (ia < len(a) and rng.random() < 0.5):
                    out.append(a[ia])
                    ia += 1
                else:
                    out.append(b[ib])
                    ib += 1
            c = "".join(out)
        else:
            length = max(0, len(a) + len(b) + rng.choice([0, 0, 0, 1, -1]))
            c = "".join(rng.choice("ab") for _ in range(length))
        assert is_interleaving(a, b, c) is _interleave_oracle(a, b, c)


@pytest.mark.exercise("eval.interleave_ok")
def test_eval_interleave_ok_any_characters():
    assert is_interleaving("Hi, ", "ok.", "Hio,k .") is True
    assert is_interleaving("Hi, ", "ok.", "Hio ,k.") is False     # ',' and ' ' of "Hi, " out of order
    assert is_interleaving("The\n", "A.", "TAh.e\n") is True
    assert is_interleaving("The", "A", "tAhe") is False             # case-sensitive
    assert is_interleaving("缓存", "命中", "缓命存中") is True
    assert is_interleaving("é", "e", "eé") is True


@pytest.mark.exercise("eval.interleave_ok")
def test_eval_interleave_ok_random_mixed_alphabet():
    rng = random.Random(970)
    alphabet = "aA .,\n中"
    for _ in range(300):
        a = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6)))
        b = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6)))
        if rng.random() < 0.5:
            ia, ib, out = 0, 0, []
            while ia < len(a) or ib < len(b):
                if ib == len(b) or (ia < len(a) and rng.random() < 0.5):
                    out.append(a[ia])
                    ia += 1
                else:
                    out.append(b[ib])
                    ib += 1
            c = "".join(out)
            if c and rng.random() < 0.3:  # sometimes damage it
                k = rng.randrange(len(c))
                c = c[:k] + rng.choice(alphabet) + c[k + 1:]
        else:
            length = max(0, len(a) + len(b) + rng.choice([0, 0, 0, 1, -1]))
            c = "".join(rng.choice(alphabet) for _ in range(length))
        assert is_interleaving(a, b, c) is _interleave_oracle(a, b, c)


# ---------------------------------------------------------------- decode.beam_pairs

def _check_pairs(a, b, k, got):
    assert len(got) == k
    # every returned pair must correspond to a distinct index pair (i, j)
    from collections import Counter

    avail = Counter((x, y) for x in a for y in b)
    for p in got:
        assert isinstance(p, list) and len(p) == 2
        t = (p[0], p[1])
        assert avail[t] > 0, f"pair {p} not available (or reused)"
        avail[t] -= 1
    expect = sorted(x + y for x in a for y in b)[:k]
    assert sorted(x + y for x, y in got) == expect


@pytest.mark.exercise("decode.beam_pairs")
def test_decode_beam_pairs_examples():
    got = k_best_pairs([1, 7, 11], [2, 4, 6], 3)
    assert sorted(got) == [[1, 2], [1, 4], [1, 6]]
    got = k_best_pairs([1, 1, 2], [1, 2, 3], 2)
    assert sorted(got) == [[1, 1], [1, 1]]


@pytest.mark.exercise("decode.beam_pairs")
def test_decode_beam_pairs_all_pairs():
    a, b = [1, 2], [3]
    _check_pairs(a, b, 2, k_best_pairs(a, b, 2))
    a, b = [1, 2, 4], [-1, 5]
    _check_pairs(a, b, 6, k_best_pairs(a, b, 6))


@pytest.mark.exercise("decode.beam_pairs")
def test_decode_beam_pairs_single():
    assert k_best_pairs([5], [7], 1) == [[5, 7]]


@pytest.mark.exercise("decode.beam_pairs")
def test_decode_beam_pairs_negatives_and_ties():
    a, b = [-10, -4, 0, 0, 6], [-3, -3, 2, 8]
    for k in (1, 4, 7, 20):
        _check_pairs(a, b, k, k_best_pairs(a, b, k))


@pytest.mark.exercise("decode.beam_pairs")
def test_decode_beam_pairs_random():
    rng = random.Random(373)
    for _ in range(150):
        a = sorted(rng.randint(-20, 20) for _ in range(rng.randint(1, 8)))
        b = sorted(rng.randint(-20, 20) for _ in range(rng.randint(1, 8)))
        k = rng.randint(1, len(a) * len(b))
        _check_pairs(a, b, k, k_best_pairs(a, b, k))


@pytest.mark.exercise("decode.beam_pairs")
def test_decode_beam_pairs_large_small_k():
    a = list(range(0, 20000, 2))
    b = list(range(1, 20000, 2))
    got = k_best_pairs(a, b, 5)
    assert sorted(x + y for x, y in got) == [1, 3, 3, 5, 5]


_PAD = {"2": "abc", "3": "def", "4": "ghi", "5": "jkl", "6": "mno", "7": "pqrs", "8": "tuv", "9": "wxyz"}


# ---------------------------------------------------------------- bench.choose

def _norm_sets(xss):
    return sorted(sorted(x) for x in xss)


@pytest.mark.exercise("bench.choose")
def test_bench_choose_example():
    assert _norm_sets(choose(4, 2)) == [[1, 2], [1, 3], [1, 4], [2, 3], [2, 4], [3, 4]]


@pytest.mark.exercise("bench.choose")
def test_bench_choose_single():
    assert _norm_sets(choose(1, 1)) == [[1]]


@pytest.mark.exercise("bench.choose")
def test_bench_choose_k_equals_n():
    assert _norm_sets(choose(5, 5)) == [[1, 2, 3, 4, 5]]


@pytest.mark.exercise("bench.choose")
def test_bench_choose_k_one():
    assert _norm_sets(choose(6, 1)) == [[i] for i in range(1, 7)]


@pytest.mark.exercise("bench.choose")
def test_bench_choose_vs_itertools():
    for n in range(1, 11):
        for k in range(1, n + 1):
            got = choose(n, k)
            assert _norm_sets(got) == sorted(list(c) for c in itertools.combinations(range(1, n + 1), k))


# ---------------------------------------------------------------- bench.orders

@pytest.mark.exercise("bench.orders")
def test_bench_orders_example():
    assert sorted(arrival_orders([1, 2, 3])) == [
        [1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1], [3, 1, 2], [3, 2, 1],
    ]


@pytest.mark.exercise("bench.orders")
def test_bench_orders_two():
    assert sorted(arrival_orders([0, 1])) == [[0, 1], [1, 0]]


@pytest.mark.exercise("bench.orders")
def test_bench_orders_single():
    assert arrival_orders([1]) == [[1]]


@pytest.mark.exercise("bench.orders")
def test_bench_orders_negatives():
    ids = [-5, 10, 0]
    got = arrival_orders(ids)
    assert sorted(got) == sorted(list(p) for p in itertools.permutations([-5, 10, 0]))


@pytest.mark.exercise("bench.orders")
def test_bench_orders_six_vs_itertools():
    ids = [4, -1, 7, 2, 9, 0]
    got = arrival_orders(ids)
    assert len(got) == 720
    assert sorted(got) == sorted(list(p) for p in itertools.permutations(ids))


# ---------------------------------------------------------------- bench.json_fuzz

def _balanced_oracle(n):
    out = []
    for bits in itertools.product("()", repeat=2 * n):
        depth = 0
        for ch in bits:
            depth += 1 if ch == "(" else -1
            if depth < 0:
                break
        if depth == 0:
            out.append("".join(bits))
    return sorted(out)


@pytest.mark.exercise("bench.json_fuzz")
def test_bench_json_fuzz_example():
    assert sorted(balanced_brackets(3)) == ["((()))", "(()())", "(())()", "()(())", "()()()"]


@pytest.mark.exercise("bench.json_fuzz")
def test_bench_json_fuzz_one():
    assert balanced_brackets(1) == ["()"]


@pytest.mark.exercise("bench.json_fuzz")
def test_bench_json_fuzz_two():
    assert sorted(balanced_brackets(2)) == ["(())", "()()"]


@pytest.mark.exercise("bench.json_fuzz")
def test_bench_json_fuzz_catalan_count():
    got = balanced_brackets(8)
    assert len(got) == 1430
    assert len(set(got)) == 1430


@pytest.mark.exercise("bench.json_fuzz")
def test_bench_json_fuzz_vs_bruteforce():
    for n in range(1, 7):
        assert sorted(balanced_brackets(n)) == _balanced_oracle(n)
