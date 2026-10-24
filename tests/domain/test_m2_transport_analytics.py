"""M2 integration: the streaming wire protocol and post-run analytics of a real server run."""
import random
import statistics
from collections import Counter

import pytest

from nanoserve.engine import Engine
from nanoserve.server.analytics import analyze, finish_order, hot_tenant, periodic_trace, queue_deltas
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import PROMPTS, make_trace
from nanoserve.server.transport import StreamClient, Transport, roundtrip

pytestmark = pytest.mark.milestone("M2")


@pytest.fixture(scope="module")
def engine():
    return Engine()


@pytest.fixture(scope="module")
def report(engine):
    server = Server(engine, ServerConfig(max_batch=3))
    server.submit_many(make_trace(24, seed=8, rate=1.2, tenant_weights=(3, 1, 1)))
    return server.run()


# ---------------------------------------------------------------- transport
@pytest.mark.parametrize("packet_size", [1, 3, 16, 4096])
def test_transport_roundtrip_of_a_server_run(report, packet_size):
    client = roundtrip(report.events, packet_size)
    assert client.frames == report.events          # every (tick, rid, chunk), in order
    assert client.text == {rid: out for rid, out in report.outputs().items() if out}
    assert client.pending == 0


UNICODE_CHUNKS = ["café ", "中文", "", "🚀 lift-off", "3#4#", "\n", "#", "12", "naïve 😀😀", "ü", "€", "x"]


@pytest.mark.parametrize("packet_size", [1, 2, 3, 5])
def test_transport_unicode_never_previews_half_a_character(packet_size):
    rng = random.Random(packet_size)
    events, t = [], 0
    for i in range(40):
        t += rng.randint(0, 1)
        events.append((t, f"r{i % 3}", rng.choice(UNICODE_CHUNKS)))
    tx, client = Transport(packet_size), StreamClient()
    for pkt in tx.stream(events):
        assert len(pkt.payload) <= packet_size
        preview = client.receive(pkt)
        if preview is not None:
            # a preview is a clean decode of a byte prefix of the message: never a split character
            assert preview.encode("utf-8") == tx.message([(r, c) for tt, r, c in events if tt == pkt.tick]
                                                         ).encode("utf-8")[: pkt.offset + len(pkt.payload)]
    assert client.frames == events
    assert client.held > 0  # small packets do split multi-byte characters; the client waited for the rest


def test_transport_one_response_with_tricky_chunks():
    chunks = ["", "", "10#", "#", "😀", "a\nb", ""]
    client = StreamClient().receive_all(Transport(2).chunk_stream(chunks, rid="r"))
    assert [c for _, _, c in client.frames] == chunks


# ---------------------------------------------------------------- analytics
def test_rolling_latency_matches_brute_force(report):
    stats = analyze(report, window=4)
    lat = [r.latency for r in finish_order(report)]
    assert [r.finished_at for r in finish_order(report)] == sorted(r.finished_at for r in report.finished)
    windows = [lat[i:i + 4] for i in range(len(lat) - 3)]
    assert stats["rolling_max"] == [max(w) for w in windows]
    assert stats["rolling_p50"] == [statistics.median(w) for w in windows]
    first, last = stats["worst_window"]
    worst = max(range(len(windows)), key=lambda i: (statistics.median(windows[i]), -i))
    assert (first, last) == (finish_order(report)[worst].rid, finish_order(report)[worst + 3].rid)


def test_hot_tenant_only_with_a_real_majority(report, engine):
    tenants = [r.tenant for r in report.requests]
    top, cnt = Counter(tenants).most_common(1)[0]
    stats = analyze(report)
    assert 2 * cnt > len(tenants)                      # the trace was skewed towards tenant 'a'
    assert stats["hot_tenant"] == top and stats["hot_share"] == pytest.approx(cnt / len(tenants))
    # a balanced trace has no hot tenant, even though the vote still yields a candidate
    assert hot_tenant(["a", "b", "c", "a", "b", "c"])[0] is None
    assert hot_tenant(["b", "a", "b"]) == ("b", pytest.approx(2 / 3))
    server = Server(engine, ServerConfig(max_batch=4))
    server.submit_many(make_trace(30, seed=9, rate=1.0, tenants=("a", "b", "c", "d")))
    assert analyze(server.run())["hot_tenant"] is None


def test_queue_burst_is_the_largest_growth(report):
    stats = analyze(report)
    q = [0] + report.queue_len
    brute = max(q[j] - q[i] for i in range(len(q)) for j in range(i + 1, len(q)))
    assert stats["queue_burst"] == brute > 0
    assert sum(queue_deltas(report.queue_len)) == report.queue_len[-1]


def test_periodic_burst_wraps_around_the_period(engine):
    period = 60
    # one "day": a rush that starts 6 ticks before midnight and lasts 6 ticks into the next day
    day = [Request(rid=f"q{i}", prompt=PROMPTS[0], arrival=t, max_tokens=3, seed=i)
           for i, t in enumerate([54, 55, 56, 57, 58, 59, 0, 1, 2, 3, 4, 5])]
    server = Server(engine, ServerConfig(max_batch=1))
    server.submit_many(periodic_trace(day, period, 3))
    rep = server.run()
    stats = analyze(rep, window=4, period=period)
    deltas = queue_deltas(rep.queue_len)
    one = deltas[period:2 * period]
    assert stats["period_start"] == period
    circ = max(sum(one[(i + k) % period] for k in range(n)) for i in range(period) for n in range(1, period + 1))
    assert stats["period_burst_wrap"] == circ
    # the rush straddles the period boundary: inside one period only part of it is visible,
    # with wrap-around we see it whole — exactly the burst the continuous run experienced
    assert stats["period_burst"] < stats["period_burst_wrap"] == stats["queue_burst"]
