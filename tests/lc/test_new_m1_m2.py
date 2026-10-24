"""New exercises for M1/M2: stop-string overlap, UTF-8 check, session tokens, slots, planning, load balancing."""
import itertools
import random
import re

import pytest

from nanoserve.scheduler.batch_slots import SlotAllocator
from nanoserve.scheduler.calendar import MaintenanceCalendar
from nanoserve.scheduler.lb import busiest_servers
from nanoserve.scheduler.planning import max_on_time, min_workers
from nanoserve.server.auth_tokens import TokenManager
from nanoserve.server.utf8 import utf8_valid
from nanoserve.stream.overlap import longest_border


# ---------------------------------------------------------------- stream.stop_overlap

def _border_brute(s):
    for k in range(len(s) - 1, 0, -1):
        if s[:k] == s[len(s) - k:]:
            return s[:k]
    return ""


@pytest.mark.exercise("stream.stop_overlap")
def test_stream_stop_overlap_examples():
    assert longest_border("level") == "l"
    assert longest_border("ababab") == "abab"


@pytest.mark.exercise("stream.stop_overlap")
def test_stream_stop_overlap_none_and_single():
    assert longest_border("a") == ""
    assert longest_border("abc") == ""
    assert longest_border("ab") == ""
    assert longest_border("abca") == "a"


@pytest.mark.exercise("stream.stop_overlap")
def test_stream_stop_overlap_all_same_and_fallback():
    assert longest_border("aaaa") == "aaa"
    assert longest_border("aabaaab") == "aab"
    assert longest_border("abacabab") == "ab"  # must fall back through shorter borders
    assert longest_border("aabaabaa") == "aabaa"


@pytest.mark.exercise("stream.stop_overlap")
def test_stream_stop_overlap_arbitrary_chars():
    assert longest_border("</s>\x00ok </") == "</"
    assert longest_border("\n\n.\n\n") == "\n\n"
    assert longest_border("### x ##") == "##"
    assert longest_border("\x00\x00") == "\x00"
    assert longest_border("🙂x🙂") == "🙂"
    assert longest_border("你好，你好") == "你好"
    assert longest_border("A a") == ""          # case-sensitive, space is a normal char
    assert longest_border(". .") == "."


@pytest.mark.exercise("stream.stop_overlap")
def test_stream_stop_overlap_engine_holdback():
    # The engine asks: how long is the longest suffix of `tail` that is a prefix of `stop`?
    def overlap(stop, tail):
        return max((k for k in range(min(len(stop), len(tail)) + 1) if tail.endswith(stop[:k])), default=0)

    cases = [
        ("</s>", "abc</"), ("</s>", "abc</s"), ("</s>", "abc"), ("</s>", "<<"),
        ("\n\n", "line\n"), ("###", "a##"), ("###", "#"), ("。」", "好。"), ("abab", "xaba"),
    ]
    for stop, text in cases:
        tail = text[-(len(stop) - 1):]
        assert len(longest_border(stop + "\x00" + tail)) == overlap(stop, tail), (stop, text)


@pytest.mark.exercise("stream.stop_overlap")
def test_stream_stop_overlap_long_inputs():
    n = 100_000
    assert longest_border("a" * n) == "a" * (n - 1)
    assert longest_border("ab" * (n // 2)) == "ab" * (n // 2 - 1)
    assert longest_border("a" * n + "b") == ""


@pytest.mark.exercise("stream.stop_overlap")
def test_stream_stop_overlap_random():
    rng = random.Random(1392)
    for alphabet in ("ab", "abc", "a\x00\n .🙂", "</s>"):
        for _ in range(250):
            s = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 30)))
            assert longest_border(s) == _border_brute(s), repr(s)


# ---------------------------------------------------------------- server.utf8_ok

_UTF8_RE = re.compile(r"(0.{7}|110.{5}10.{6}|1110.{4}(10.{6}){2}|11110.{3}(10.{6}){3})*")


def _utf8_brute(data):
    return _UTF8_RE.fullmatch("".join(format(b, "08b") for b in data)) is not None


@pytest.mark.exercise("server.utf8_ok")
def test_server_utf8_ok_examples():
    assert utf8_valid([197, 130, 1]) is True
    assert utf8_valid([235, 140, 4]) is False


@pytest.mark.exercise("server.utf8_ok")
def test_server_utf8_ok_real_text():
    for text in ["hello", "你好，世界", "naïve café", "🙂🚀", "a\x00b\n", "mixed 中 é 🙂 end"]:
        assert utf8_valid(list(text.encode("utf-8"))) is True, text


@pytest.mark.exercise("server.utf8_ok")
def test_server_utf8_ok_single_bytes():
    assert utf8_valid([0]) is True
    assert utf8_valid([127]) is True
    assert utf8_valid([128]) is False       # continuation byte cannot lead
    assert utf8_valid([0xBF]) is False
    assert utf8_valid([0xC2]) is False      # truncated 2-byte
    assert utf8_valid([255]) is False


@pytest.mark.exercise("server.utf8_ok")
def test_server_utf8_ok_truncated_and_extra():
    ni = list("你".encode("utf-8"))
    smile = list("🙂".encode("utf-8"))
    assert utf8_valid(ni[:2]) is False
    assert utf8_valid(smile[:3]) is False
    assert utf8_valid([0xF0]) is False
    assert utf8_valid(ni + [0x80]) is False          # stray continuation byte
    assert utf8_valid([0xC5, 0x82, 0x82]) is False
    assert utf8_valid([0xE4, 0x41, 0xA0]) is False   # ASCII where a continuation byte belongs
    assert utf8_valid(ni + smile + [65]) is True


@pytest.mark.exercise("server.utf8_ok")
def test_server_utf8_ok_bit_patterns_only():
    assert utf8_valid([0xF8, 0x80, 0x80, 0x80, 0x80]) is False  # 11111xxx is never a lead byte
    assert utf8_valid([0xFC, 0x80, 0x80, 0x80, 0x80, 0x80]) is False
    # no overlong / surrogate / code-point range checks
    assert utf8_valid([0xC0, 0x80]) is True
    assert utf8_valid([0xE0, 0x80, 0x80]) is True
    assert utf8_valid([0xED, 0xA0, 0x80]) is True
    assert utf8_valid([0xF7, 0xBF, 0xBF, 0xBF]) is True


@pytest.mark.exercise("server.utf8_ok")
def test_server_utf8_ok_random():
    rng = random.Random(393)

    def char():
        n = rng.choice([1, 1, 2, 3, 4])
        lead = [0x00, 0xC0, 0xE0, 0xF0][n - 1]
        free = [7, 5, 4, 3][n - 1]
        return [lead | rng.randrange(1 << free)] + [0x80 | rng.randrange(64) for _ in range(n - 1)]

    for _ in range(1500):
        data = [b for _ in range(rng.randint(1, 6)) for b in char()]
        r = rng.random()
        if r < 0.25 and len(data) > 1:
            del data[rng.randrange(len(data))]
        elif r < 0.5:
            data[rng.randrange(len(data))] = rng.randrange(256)
        elif r < 0.6:
            data.insert(rng.randrange(len(data) + 1), rng.randrange(256))
        assert utf8_valid(data) == _utf8_brute(data), data


# ---------------------------------------------------------------- server.tokens

class _TokenModel:
    def __init__(self, ttl):
        self.ttl = ttl
        self.exp = {}

    def generate(self, token_id, now):
        self.exp[token_id] = now + self.ttl

    def renew(self, token_id, now):
        if self.exp.get(token_id, now) > now:
            self.exp[token_id] = now + self.ttl

    def count_unexpired(self, now):
        return sum(e > now for e in self.exp.values())


@pytest.mark.exercise("server.tokens")
def test_server_tokens_example():
    m = TokenManager(5)
    assert m.renew("aaa", 1) is None
    assert m.generate("aaa", 2) is None
    assert m.count_unexpired(6) == 1
    m.generate("bbb", 7)
    m.renew("aaa", 8)
    m.renew("bbb", 10)
    assert m.count_unexpired(15) == 0


@pytest.mark.exercise("server.tokens")
def test_server_tokens_expiry_boundary():
    m = TokenManager(5)
    m.generate("a", 1)  # expires at 6
    assert m.count_unexpired(5) == 1
    assert m.count_unexpired(6) == 0
    assert m.count_unexpired(7) == 0


@pytest.mark.exercise("server.tokens")
def test_server_tokens_renew_at_expiry_is_ignored():
    m = TokenManager(5)
    m.generate("a", 1)   # expires at 6
    m.generate("b", 2)   # expires at 7
    m.renew("a", 6)      # already expired at 6 -> ignored
    m.renew("b", 6)      # still valid -> now expires at 11
    assert m.count_unexpired(8) == 1
    assert m.count_unexpired(10) == 1
    assert m.count_unexpired(11) == 0


@pytest.mark.exercise("server.tokens")
def test_server_tokens_unknown_renew_does_not_create():
    m = TokenManager(3)
    m.renew("ghost", 1)
    assert m.count_unexpired(2) == 0
    m.generate("real", 3)
    m.renew("ghost", 4)
    assert m.count_unexpired(5) == 1


@pytest.mark.exercise("server.tokens")
def test_server_tokens_renew_reorders_expiry():
    m = TokenManager(10)
    m.generate("a", 1)   # 11
    m.generate("b", 2)   # 12
    m.generate("c", 3)   # 13
    m.renew("a", 4)      # a -> 14, now the latest
    assert m.count_unexpired(11) == 3
    assert m.count_unexpired(12) == 2
    assert m.count_unexpired(13) == 1
    assert m.count_unexpired(14) == 0


@pytest.mark.exercise("server.tokens")
def test_server_tokens_random_vs_model():
    rng = random.Random(1797)
    for ttl in (1, 2, 5, 13):
        m, model = TokenManager(ttl), _TokenModel(ttl)
        now, fresh = 0, 0
        for _ in range(800):
            now += rng.randint(1, 3)
            r = rng.random()
            if r < 0.3:
                tid = f"t{fresh}"
                fresh += 1
                m.generate(tid, now)
                model.generate(tid, now)
            elif r < 0.65:
                tid = f"t{rng.randrange(fresh + 2)}"
                m.renew(tid, now)
                model.renew(tid, now)
            else:
                assert m.count_unexpired(now) == model.count_unexpired(now)


@pytest.mark.exercise("server.tokens")
def test_server_tokens_same_time_calls():
    m = TokenManager(4)
    m.generate("x", 3)
    m.generate("y", 3)
    assert m.count_unexpired(3) == 2
    m.renew("x", 6)
    m.renew("x", 6)         # renewing twice at the same instant is harmless
    assert m.count_unexpired(6) == 2
    assert m.count_unexpired(7) == 1   # "y" expired at 7, "x" lives until 10
    m.generate("z", 7)
    m.renew("y", 7)         # expired at 7: ignored
    assert m.count_unexpired(7) == 2


@pytest.mark.exercise("server.tokens")
def test_server_tokens_random_non_decreasing_vs_model():
    rng = random.Random(17970)
    for ttl in (1, 3, 7):
        m, model = TokenManager(ttl), _TokenModel(ttl)
        now, fresh = 0, 0
        for _ in range(800):
            now += rng.choice((0, 0, 1, 2))   # many calls share a timestamp
            r = rng.random()
            if r < 0.3:
                tid = f"t{fresh}"
                fresh += 1
                m.generate(tid, now)
                model.generate(tid, now)
            elif r < 0.65:
                tid = f"t{rng.randrange(fresh + 2)}"
                m.renew(tid, now)
                model.renew(tid, now)
            else:
                assert m.count_unexpired(now) == model.count_unexpired(now)


# ---------------------------------------------------------------- sched.slots

@pytest.mark.exercise("sched.slots")
def test_sched_slots_example():
    s = SlotAllocator(5)
    assert s.reserve() == 1
    assert s.reserve() == 2
    assert s.unreserve(2) is None
    assert [s.reserve() for _ in range(4)] == [2, 3, 4, 5]
    assert s.unreserve(5) is None


@pytest.mark.exercise("sched.slots")
def test_sched_slots_single():
    s = SlotAllocator(1)
    assert s.reserve() == 1
    s.unreserve(1)
    assert s.reserve() == 1


@pytest.mark.exercise("sched.slots")
def test_sched_slots_smallest_free_first():
    s = SlotAllocator(6)
    assert [s.reserve() for _ in range(6)] == [1, 2, 3, 4, 5, 6]
    s.unreserve(5)
    s.unreserve(2)
    s.unreserve(4)
    assert s.reserve() == 2
    assert s.reserve() == 4
    s.unreserve(1)
    assert s.reserve() == 1
    assert s.reserve() == 5


@pytest.mark.exercise("sched.slots")
def test_sched_slots_returned_below_fresh():
    s = SlotAllocator(10)
    assert [s.reserve() for _ in range(3)] == [1, 2, 3]
    s.unreserve(3)
    assert s.reserve() == 3
    assert s.reserve() == 4
    s.unreserve(1)
    assert s.reserve() == 1
    assert s.reserve() == 5


@pytest.mark.exercise("sched.slots")
def test_sched_slots_large_n():
    s = SlotAllocator(100_000)
    assert [s.reserve() for _ in range(5)] == [1, 2, 3, 4, 5]
    s.unreserve(3)
    assert s.reserve() == 3


@pytest.mark.exercise("sched.slots")
def test_sched_slots_random_vs_model():
    rng = random.Random(1845)
    for n in (1, 2, 5, 17, 60):
        s = SlotAllocator(n)
        free = set(range(1, n + 1))
        taken = []
        for _ in range(1000):
            if free and (not taken or rng.random() < 0.55):
                want = min(free)
                assert s.reserve() == want
                free.remove(want)
                taken.append(want)
            else:
                slot = taken.pop(rng.randrange(len(taken)))
                s.unreserve(slot)
                free.add(slot)


# ---------------------------------------------------------------- sched.maintenance

@pytest.mark.exercise("sched.maintenance")
def test_sched_maintenance_example():
    c = MaintenanceCalendar()
    assert c.book(10, 20) is True
    assert c.book(15, 25) is False
    assert c.book(20, 30) is True


@pytest.mark.exercise("sched.maintenance")
def test_sched_maintenance_touching_both_sides():
    c = MaintenanceCalendar()
    assert c.book(10, 20) is True
    assert c.book(5, 10) is True
    assert c.book(20, 21) is True
    assert c.book(9, 11) is False
    assert c.book(19, 20) is False


@pytest.mark.exercise("sched.maintenance")
def test_sched_maintenance_contained_and_containing():
    c = MaintenanceCalendar()
    assert c.book(10, 20) is True
    assert c.book(12, 15) is False
    assert c.book(5, 25) is False
    assert c.book(10, 20) is False


@pytest.mark.exercise("sched.maintenance")
def test_sched_maintenance_rejected_not_recorded():
    c = MaintenanceCalendar()
    assert c.book(10, 20) is True
    assert c.book(5, 30) is False
    assert c.book(25, 30) is True   # would clash if [5, 30) had been kept
    assert c.book(0, 5) is True


@pytest.mark.exercise("sched.maintenance")
def test_sched_maintenance_unit_windows_and_gap():
    c = MaintenanceCalendar()
    assert c.book(0, 1) is True
    assert c.book(2, 3) is True
    assert c.book(1, 2) is True
    assert c.book(0, 3) is False
    assert c.book(3, 1_000_000_000) is True


@pytest.mark.exercise("sched.maintenance")
def test_sched_maintenance_random_vs_model():
    rng = random.Random(729)
    for _ in range(40):
        c, booked = MaintenanceCalendar(), []
        for _ in range(60):
            s = rng.randrange(0, 100)
            e = s + rng.randint(1, 10)
            ok = all(max(s, bs) >= min(e, be) for bs, be in booked)
            assert c.book(s, e) is ok
            if ok:
                booked.append((s, e))


# ---------------------------------------------------------------- sched.min_workers

def _min_workers_brute(intervals):
    # closed integer intervals: the answer is the largest number of intervals sharing one point
    lo = min(s for s, _ in intervals)
    hi = max(e for _, e in intervals)
    return max(sum(s <= t <= e for s, e in intervals) for t in range(lo, hi + 1))


@pytest.mark.exercise("sched.min_workers")
def test_sched_min_workers_examples():
    assert min_workers([[5, 10], [6, 8], [1, 5], [2, 3], [1, 10]]) == 3
    assert min_workers([[1, 3], [5, 6], [8, 10], [11, 13]]) == 1


@pytest.mark.exercise("sched.min_workers")
def test_sched_min_workers_closed_endpoints():
    assert min_workers([[1, 5], [5, 8]]) == 2
    assert min_workers([[1, 5], [6, 8]]) == 1
    assert min_workers([[3, 3], [3, 3], [3, 3]]) == 3


@pytest.mark.exercise("sched.min_workers")
def test_sched_min_workers_single():
    assert min_workers([[1, 1]]) == 1
    assert min_workers([[1, 1_000_000]]) == 1


@pytest.mark.exercise("sched.min_workers")
def test_sched_min_workers_nested_and_chain():
    assert min_workers([[1, 10], [2, 9], [3, 8], [4, 7]]) == 4
    assert min_workers([[1, 2], [2, 3], [3, 4], [4, 5]]) == 2
    assert min_workers([[4, 5], [1, 2], [3, 4], [2, 3]]) == 2   # unsorted input


@pytest.mark.exercise("sched.min_workers")
def test_sched_min_workers_random():
    rng = random.Random(2406)
    for _ in range(300):
        ivs = []
        for _ in range(rng.randint(1, 12)):
            s = rng.randint(1, 30)
            ivs.append([s, s + rng.randint(0, 8)])
        assert min_workers([iv[:] for iv in ivs]) == _min_workers_brute(ivs), ivs


@pytest.mark.exercise("sched.min_workers")
def test_sched_min_workers_from_time_zero():
    assert min_workers([[0, 0], [0, 4], [5, 9]]) == 2
    assert min_workers([[0, 0]]) == 1
    assert min_workers([[0, 3], [4, 7], [0, 0]]) == 2


@pytest.mark.exercise("sched.min_workers")
def test_sched_min_workers_random_with_zero():
    rng = random.Random(24060)
    for _ in range(300):
        ivs = []
        for _ in range(rng.randint(1, 12)):
            s = rng.randint(0, 10)
            ivs.append([s, s + rng.randint(0, 6)])
        assert min_workers([iv[:] for iv in ivs]) == _min_workers_brute(ivs), ivs


# ---------------------------------------------------------------- sched.slo_bound

def _on_time_brute(jobs):
    best = 0
    for r in range(len(jobs), 0, -1):
        if r <= best:
            break
        for subset in itertools.combinations(jobs, r):
            for order in itertools.permutations(subset):
                t, ok = 0, True
                for d, dl in order:
                    t += d
                    if t > dl:
                        ok = False
                        break
                if ok:
                    best = r
                    break
            if best == r:
                break
    return best


@pytest.mark.exercise("sched.slo_bound")
def test_sched_slo_bound_examples():
    assert max_on_time([[100, 200], [200, 1300], [1000, 1250], [2000, 3200]]) == 3
    assert max_on_time([[1, 2]]) == 1
    assert max_on_time([[3, 2], [4, 3]]) == 0


@pytest.mark.exercise("sched.slo_bound")
def test_sched_slo_bound_deadline_inclusive():
    assert max_on_time([[5, 5]]) == 1
    assert max_on_time([[5, 4]]) == 0
    assert max_on_time([[1, 2], [2, 3]]) == 2


@pytest.mark.exercise("sched.slo_bound")
def test_sched_slo_bound_swap_out_long_job():
    # taking the earliest-deadline job first is a trap: swapping it for two shorter ones wins
    assert max_on_time([[5, 5], [4, 6], [2, 6]]) == 2
    assert max_on_time([[7, 7], [1, 8], [1, 8], [1, 8]]) == 3


@pytest.mark.exercise("sched.slo_bound")
def test_sched_slo_bound_same_deadline():
    assert max_on_time([[2, 5], [2, 5], [2, 5]]) == 2
    assert max_on_time([[3, 6], [1, 6], [2, 6], [4, 6]]) == 3


@pytest.mark.exercise("sched.slo_bound")
def test_sched_slo_bound_order_independent():
    jobs = [[1, 3], [4, 9], [2, 4], [3, 7], [5, 12], [2, 2]]
    expected = _on_time_brute(jobs)
    for perm in ([0, 1, 2, 3, 4, 5], [5, 4, 3, 2, 1, 0], [2, 0, 5, 3, 1, 4]):
        assert max_on_time([jobs[i][:] for i in perm]) == expected


@pytest.mark.exercise("sched.slo_bound")
def test_sched_slo_bound_random():
    rng = random.Random(630)
    for _ in range(200):
        jobs = [[rng.randint(1, 6), rng.randint(1, 15)] for _ in range(rng.randint(1, 6))]
        assert max_on_time([j[:] for j in jobs]) == _on_time_brute(jobs), jobs


# ---------------------------------------------------------------- sched.rr_busiest

def _busiest_brute(k, arrival, load):
    free_at = [0] * k
    count = [0] * k
    for i, (t, d) in enumerate(zip(arrival, load)):
        for step in range(k):
            w = (i + step) % k
            if free_at[w] <= t:
                free_at[w] = t + d
                count[w] += 1
                break
    best = max(count)
    return [w for w in range(k) if count[w] == best]


@pytest.mark.exercise("sched.rr_busiest")
def test_sched_rr_busiest_examples():
    assert sorted(busiest_servers(3, [1, 2, 3, 4, 5], [5, 2, 3, 3, 3])) == [1]
    assert sorted(busiest_servers(3, [1, 2, 3, 4], [1, 2, 1, 2])) == [0]
    assert sorted(busiest_servers(3, [1, 2, 3], [10, 12, 11])) == [0, 1, 2]


@pytest.mark.exercise("sched.rr_busiest")
def test_sched_rr_busiest_single_worker():
    assert busiest_servers(1, [1], [1]) == [0]
    assert busiest_servers(1, [1, 2, 3], [5, 1, 1]) == [0]     # requests 1, 2 dropped


@pytest.mark.exercise("sched.rr_busiest")
def test_sched_rr_busiest_wrap_around_and_release_boundary():
    # req 3 starts at worker 0 (free at 3 <= 4); req 4 starts at worker 1, wraps past 1, 2 to worker 0,
    # which becomes free exactly at its arrival time 5.
    assert sorted(busiest_servers(3, [1, 2, 3, 4, 5], [2, 100, 100, 1, 1])) == [0]


@pytest.mark.exercise("sched.rr_busiest")
def test_sched_rr_busiest_all_busy_drops():
    # all three workers are busy when request 3 arrives -> dropped, counts stay [1, 1, 1]
    assert sorted(busiest_servers(3, [1, 2, 3, 4], [10, 10, 10, 1])) == [0, 1, 2]


@pytest.mark.exercise("sched.rr_busiest")
def test_sched_rr_busiest_more_workers_than_requests():
    assert sorted(busiest_servers(5, [1, 2], [1, 1])) == [0, 1]
    assert sorted(busiest_servers(4, [1, 2, 3], [100, 100, 100])) == [0, 1, 2]


@pytest.mark.exercise("sched.rr_busiest")
def test_sched_rr_busiest_random():
    rng = random.Random(1606)
    for _ in range(300):
        k = rng.randint(1, 8)
        n = rng.randint(1, 40)
        arrival = sorted(rng.sample(range(1, 4 * n + 1), n))
        load = [rng.randint(1, 12) for _ in range(n)]
        got = sorted(busiest_servers(k, arrival[:], load[:]))
        assert got == _busiest_brute(k, arrival, load), (k, arrival, load)


@pytest.mark.exercise("sched.rr_busiest")
def test_sched_rr_busiest_same_time_arrivals():
    # three requests at t=0 on two workers: 0 -> w0, 1 -> w1, 2 starts at w0 (busy), w1 (busy) -> dropped
    assert sorted(busiest_servers(2, [0, 0, 0, 3], [3, 1, 5, 1])) == [1]
    assert sorted(busiest_servers(3, [0, 0, 0], [1, 1, 1])) == [0, 1, 2]
    assert busiest_servers(1, [0, 0, 1], [1, 1, 1]) == [0]   # second t=0 request dropped, t=1 one served


@pytest.mark.exercise("sched.rr_busiest")
def test_sched_rr_busiest_random_non_decreasing():
    rng = random.Random(16060)
    for _ in range(300):
        k = rng.randint(1, 6)
        n = rng.randint(1, 30)
        arrival = sorted(rng.randint(0, 2 * n) for _ in range(n))
        load = [rng.randint(1, 10) for _ in range(n)]
        got = sorted(busiest_servers(k, arrival[:], load[:]))
        assert got == _busiest_brute(k, arrival, load), (k, arrival, load)
