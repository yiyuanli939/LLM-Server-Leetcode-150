import bisect
import random

import pytest

from nanoserve.sampling.search import cdf_index
from nanoserve.sampling.topk import kth_largest
from nanoserve.stream.detok import trailing_word_len
from nanoserve.stream.render import justify
from nanoserve.stream.repetition import longest_unique_run, repeats_within
from nanoserve.stream.stop import find_stop


# ---------------------------------------------------------------- stream.find_stop

def _find_oracle(text, stop):
    for i in range(len(text) - len(stop) + 1):
        if text[i : i + len(stop)] == stop:
            return i
    return -1


@pytest.mark.exercise("stream.find_stop")
def test_stream_find_stop_examples():
    assert find_stop("sadbutsad", "sad") == 0
    assert find_stop("nanoserve", "nanos.") == -1


@pytest.mark.exercise("stream.find_stop")
def test_stream_find_stop_middle_and_end():
    assert find_stop("hello", "ll") == 2
    assert find_stop("The engine stops.", ".") == 16
    assert find_stop("abc", "abc") == 0


@pytest.mark.exercise("stream.find_stop")
def test_stream_find_stop_edges():
    assert find_stop("", "a") == -1
    assert find_stop("a", "aa") == -1
    assert find_stop("a", "a") == 0


@pytest.mark.exercise("stream.find_stop")
def test_stream_find_stop_overlapping_prefix():
    assert find_stop("aaab", "aab") == 1
    assert find_stop("ababcabcabababd", "ababd") == 10
    assert find_stop("mississippi", "issip") == 4


@pytest.mark.exercise("stream.find_stop")
def test_stream_find_stop_random():
    rng = random.Random(28)
    for _ in range(500):
        text = "".join(rng.choice("ab") for _ in range(rng.randint(0, 20)))
        stop = "".join(rng.choice("ab") for _ in range(rng.randint(1, 4)))
        assert find_stop(text, stop) == _find_oracle(text, stop), (text, stop)


# ---------------------------------------------------------------- stream.justify

@pytest.mark.exercise("stream.justify")
def test_stream_justify_example1():
    assert justify(["This", "is", "an", "example", "of", "text", "justification."], 16) == [
        "This    is    an",
        "example  of text",
        "justification.  ",
    ]


@pytest.mark.exercise("stream.justify")
def test_stream_justify_example2_single_word_line():
    assert justify(["What", "must", "be", "acknowledgment", "shall", "be"], 16) == [
        "What   must   be",
        "acknowledgment  ",
        "shall be        ",
    ]


@pytest.mark.exercise("stream.justify")
def test_stream_justify_example3_uneven_gaps():
    words = ["Science", "is", "what", "we", "understand", "well", "enough", "to", "explain", "to",
             "a", "computer.", "Art", "is", "everything", "else", "we", "do"]
    assert justify(words, 20) == [
        "Science  is  what we",
        "understand      well",
        "enough to explain to",
        "a  computer.  Art is",
        "everything  else  we",
        "do                  ",
    ]


@pytest.mark.exercise("stream.justify")
def test_stream_justify_edges():
    assert justify(["a"], 1) == ["a"]
    assert justify(["a"], 3) == ["a  "]
    assert justify(["abc", "d"], 3) == ["abc", "d  "]
    assert justify(["a", "b", "c", "d"], 3) == ["a b", "c d"]
    assert justify(["ab", "c", "d"], 5) == ["ab  c", "d    "]


@pytest.mark.exercise("stream.justify")
def test_stream_justify_random_invariants():
    rng = random.Random(68)
    for _ in range(200):
        width = rng.randint(1, 20)
        words = ["x" * rng.randint(1, width) for _ in range(rng.randint(1, 15))]
        lines = justify(words, width)
        assert all(len(line) == width for line in lines)
        assert [w for line in lines for w in line.split()] == words
        last = lines[-1].rstrip(" ")
        assert last == " ".join(last.split())
        for k, line in enumerate(lines[:-1]):
            gaps = [len(g) for g in line.strip(" ").split("x") if g]
            if len(line.split()) > 1:
                assert not line.startswith(" ") and not line.endswith(" ")
                assert gaps == sorted(gaps, reverse=True) and gaps[0] - gaps[-1] <= 1
                # greedy: first word of the next line would not have fitted
                nxt = lines[k + 1].split()[0]
                assert len(" ".join(line.split())) + 1 + len(nxt) > width


# ---------------------------------------------------------------- stream.holdback

@pytest.mark.exercise("stream.holdback")
def test_stream_holdback_examples():
    assert trailing_word_len("Hello World") == 5
    assert trailing_word_len("   fly me   to   the moon  ") == 4
    assert trailing_word_len("luffy is still joyboy") == 6


@pytest.mark.exercise("stream.holdback")
def test_stream_holdback_no_word():
    assert trailing_word_len("") == 0
    assert trailing_word_len("     ") == 0


@pytest.mark.exercise("stream.holdback")
def test_stream_holdback_single_word():
    assert trailing_word_len("a") == 1
    assert trailing_word_len("  token") == 5
    assert trailing_word_len("token ") == 5


@pytest.mark.exercise("stream.holdback")
def test_stream_holdback_punctuation_counts():
    assert trailing_word_len("The cache evic") == 4
    assert trailing_word_len("done.") == 5


@pytest.mark.exercise("stream.holdback")
def test_stream_holdback_random():
    rng = random.Random(58)
    for _ in range(300):
        s = "".join(rng.choice("ab  ") for _ in range(rng.randint(0, 12)))
        words = s.split(" ")
        expected = next((len(w) for w in reversed(words) if w), 0)
        assert trailing_word_len(s) == expected, s


# ---------------------------------------------------------------- stream.unique_run

def _unique_oracle(s):
    best = 0
    for i in range(len(s)):
        for j in range(i, len(s) + 1):
            if len(set(s[i:j])) == j - i:
                best = max(best, j - i)
    return best


@pytest.mark.exercise("stream.unique_run")
def test_stream_unique_run_examples():
    assert longest_unique_run("abcabcbb") == 3
    assert longest_unique_run("bbbbb") == 1
    assert longest_unique_run("pwwkew") == 3


@pytest.mark.exercise("stream.unique_run")
def test_stream_unique_run_edges():
    assert longest_unique_run("") == 0
    assert longest_unique_run(" ") == 1
    assert longest_unique_run("au") == 2


@pytest.mark.exercise("stream.unique_run")
def test_stream_unique_run_window_does_not_move_back():
    assert longest_unique_run("abba") == 2
    assert longest_unique_run("dvdf") == 3
    assert longest_unique_run("tmmzuxt") == 5


@pytest.mark.exercise("stream.unique_run")
def test_stream_unique_run_mixed_chars():
    assert longest_unique_run("the the") == 4
    assert longest_unique_run("词表词") == 2


@pytest.mark.exercise("stream.unique_run")
def test_stream_unique_run_random():
    rng = random.Random(3)
    for _ in range(300):
        s = "".join(rng.choice("abcd ") for _ in range(rng.randint(0, 15)))
        assert longest_unique_run(s) == _unique_oracle(s), s


# ---------------------------------------------------------------- stream.repeat_window

def _repeat_oracle(tokens, k):
    n = len(tokens)
    return any(tokens[i] == tokens[j] and abs(i - j) <= k for i in range(n) for j in range(n) if i != j)


@pytest.mark.exercise("stream.repeat_window")
def test_stream_repeat_window_examples():
    assert repeats_within([1, 2, 3, 1], 3) is True
    assert repeats_within([1, 0, 1, 1], 1) is True
    assert repeats_within([1, 2, 3, 1, 2, 3], 2) is False


@pytest.mark.exercise("stream.repeat_window")
def test_stream_repeat_window_k_zero():
    assert repeats_within([5, 5, 5], 0) is False


@pytest.mark.exercise("stream.repeat_window")
def test_stream_repeat_window_empty_single():
    assert repeats_within([], 3) is False
    assert repeats_within([7], 5) is False


@pytest.mark.exercise("stream.repeat_window")
def test_stream_repeat_window_boundary_and_negatives():
    assert repeats_within([-1, 4, -1], 2) is True
    assert repeats_within([-1, 4, -1], 1) is False
    assert repeats_within([1, 2, 3], 100) is False


@pytest.mark.exercise("stream.repeat_window")
def test_stream_repeat_window_random():
    rng = random.Random(219)
    for _ in range(400):
        tokens = [rng.randint(-3, 6) for _ in range(rng.randint(0, 12))]
        k = rng.randint(0, 6)
        assert repeats_within(tokens, k) == _repeat_oracle(tokens, k), (tokens, k)


# ---------------------------------------------------------------- sample.cdf_index

@pytest.mark.exercise("sample.cdf_index")
def test_sample_cdf_index_examples():
    assert cdf_index([1, 3, 5, 6], 5) == 2
    assert cdf_index([1, 3, 5, 6], 2) == 1
    assert cdf_index([1, 3, 5, 6], 7) == 4


@pytest.mark.exercise("sample.cdf_index")
def test_sample_cdf_index_front_and_single():
    assert cdf_index([1, 3, 5, 6], 0) == 0
    assert cdf_index([1], 1) == 0
    assert cdf_index([1], 0) == 0
    assert cdf_index([1], 2) == 1


@pytest.mark.exercise("sample.cdf_index")
def test_sample_cdf_index_floats():
    cdf = [0.1, 0.4, 1.0]
    assert cdf_index(cdf, 0.25) == 1
    assert cdf_index(cdf, 0.0) == 0
    assert cdf_index(cdf, 0.4) == 1
    assert cdf_index(cdf, 0.999) == 2
    assert cdf_index([-2.5, -1.0, 3.5], -1.5) == 1


@pytest.mark.exercise("sample.cdf_index")
def test_sample_cdf_index_negatives():
    assert cdf_index([-10, -3, 0, 4], -3) == 1
    assert cdf_index([-10, -3, 0, 4], -11) == 0
    assert cdf_index([-10, -3, 0, 4], 5) == 4


@pytest.mark.exercise("sample.cdf_index")
def test_sample_cdf_index_logarithmic():
    class CountingList(list):
        reads = 0

        def __getitem__(self, i):
            CountingList.reads += 1
            return list.__getitem__(self, i)

    cdf = CountingList(range(0, 2_000_000, 2))
    assert cdf_index(cdf, 777_777) == 388_889
    assert CountingList.reads <= 64


@pytest.mark.exercise("sample.cdf_index")
def test_sample_cdf_index_random():
    rng = random.Random(35)
    for _ in range(400):
        if rng.random() < 0.5:
            cdf = sorted(rng.sample(range(-50, 50), rng.randint(1, 20)))
            r = rng.randint(-55, 55)
        else:
            cdf, acc = [], 0.0
            for _ in range(rng.randint(1, 20)):
                acc += rng.random() + 1e-6
                cdf.append(acc)
            r = rng.choice([rng.random() * cdf[-1] * 1.1, rng.choice(cdf)])
        assert cdf_index(cdf, r) == bisect.bisect_left(cdf, r), (cdf, r)


# ---------------------------------------------------------------- sample.kth_largest

@pytest.mark.exercise("sample.kth_largest")
def test_sample_kth_largest_examples():
    assert kth_largest([3, 2, 1, 5, 6, 4], 2) == 5
    assert kth_largest([3, 2, 3, 1, 2, 4, 5, 5, 6], 4) == 4


@pytest.mark.exercise("sample.kth_largest")
def test_sample_kth_largest_single_and_extremes():
    assert kth_largest([7], 1) == 7
    assert kth_largest([3, 1, 2], 1) == 3
    assert kth_largest([3, 1, 2], 3) == 1


@pytest.mark.exercise("sample.kth_largest")
def test_sample_kth_largest_duplicates_count_separately():
    assert kth_largest([2, 2, 2, 1], 3) == 2
    assert kth_largest([5, 5, 4], 2) == 5
    assert kth_largest([1, 1, 1, 1], 4) == 1


@pytest.mark.exercise("sample.kth_largest")
def test_sample_kth_largest_floats_negatives():
    assert kth_largest([0.5, -1.25, 2.0], 3) == pytest.approx(-1.25)
    assert kth_largest([-3.0, -1.5, -2.25, -1.5], 2) == pytest.approx(-1.5)
    assert kth_largest([-3.0, -1.5, -2.25, -1.5], 3) == pytest.approx(-2.25)


@pytest.mark.exercise("sample.kth_largest")
def test_sample_kth_largest_does_not_mutate():
    logits = [0.3, 1.7, -0.2, 1.7, 0.9]
    snapshot = list(logits)
    assert kth_largest(logits, 3) == pytest.approx(0.9)
    assert logits == snapshot


@pytest.mark.exercise("sample.kth_largest")
def test_sample_kth_largest_random():
    rng = random.Random(215)
    for _ in range(300):
        n = rng.randint(1, 40)
        if rng.random() < 0.5:
            logits = [rng.randint(-5, 5) for _ in range(n)]
        else:
            logits = [rng.uniform(-10, 10) for _ in range(n)]
        k = rng.randint(1, n)
        assert kth_largest(logits, k) == sorted(logits, reverse=True)[k - 1]
    big = [rng.uniform(-20, 20) for _ in range(50_000)]
    assert kth_largest(big, 8) == sorted(big, reverse=True)[7]
