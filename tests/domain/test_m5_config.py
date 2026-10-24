"""M5 integration: config files are parsed, round-trip exactly, and drive real server runs."""
import dataclasses

import pytest

from nanoserve.config.deploy import Deployment
from nanoserve.config.loader import ConfigError, LoadedConfig, NoRoute, example_path, load_config
from nanoserve.engine import Engine
from nanoserve.ir.compiler import IRModel
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import make_trace
from nanoserve.tokenizer.tokenizer import Tokenizer

pytestmark = pytest.mark.milestone("M5")

EXAMPLES = ("server.conf", "minimal.conf", "tiered.conf")


@pytest.fixture(scope="module")
def cfg():
    return load_config(example_path("server.conf"))


# ------------------------------------------------------------------------------ values
def test_example_values(cfg):
    s = cfg.server
    assert (s.max_batch, s.prefill_chunk, s.token_budget, s.session_ttl, s.max_ticks) == (4, 8, 3456, 50, 20000)
    assert (s.policy, s.kv_blocks, s.prefix_cache, s.max_sessions) == ("fcfs", None, False, None)
    assert cfg.model_path == "/models/toy/ngram-5" and cfg.compiled is True
    assert cfg.workers == ["gpu-a", "gpu-a", "cpu_b"]
    assert cfg.pool == {"cpu_b": {"max_batch": 1, "prefill_chunk": 4}}
    assert cfg.worker_config(2).max_batch == 1 and cfg.worker_config(0).max_batch == 4


def test_flags_resolve_in_dependency_order(cfg):
    assert cfg.flags == {"stable": True, "debug": False, "canary": True, "fast": True, "paranoid": False}
    assert list(cfg.flags) == ["stable", "debug", "canary", "fast", "paranoid"]   # file order kept


def test_number_dispatch_and_arithmetic():
    text = """[server]
max_batch = 10 / 3 * 3 + 7 / 2 - 1      // * / -> truncating, left to right: 9 + 3 - 1
prefill_chunk = 2 - (3 - (4 + 5))       // + - ( )
token_budget = -(-(100)) + (-20)        // unary minus after "(" or at the start
session_ttl = 7
"""
    s = load_config(text).server
    assert (s.max_batch, s.prefill_chunk, s.token_budget, s.session_ttl) == (11, 8, 80, 7)
    for bad in ("2 * (3 + 1)", "-2 * 3", "4 / 0", "3 + + 4", "(1 + 2", "5 x", "1 2", "99999999999", "1 + -2"):
        with pytest.raises(ConfigError):
            load_config(f"[server]\nmax_batch = {bad}\n")


def test_comments_are_removed_everywhere():
    text = """/* header
   [server]
   max_batch = 99 */
[server] // trailing
max_/* inline block */batch = 3
prefill_chunk = 4 /* spans
lines */ + 4
// policy = edf
"""
    s = load_config(text).server
    assert (s.max_batch, s.prefill_chunk, s.policy) == (3, 8, "fcfs")
    with pytest.raises(ConfigError, match="unterminated"):
        load_config("[server]\nmax_batch = 2 /* never closed\n")


def test_brackets_checked_before_parsing():
    for bad in ("[server\nmax_batch = 2\n", "[server]\nmax_batch = (2 + 3\n", "[workers]\npool = 2[a,]]b\n",
                "[server]\nmax_batch = (2]\n"):
        with pytest.raises(ConfigError, match="unbalanced"):
            load_config(bad)


def test_templates_expand_nested():
    c = load_config("[workers]\npool = 2[big, 2[small,]]solo\n")
    assert c.workers == ["big", "small", "small", "big", "small", "small", "solo"]
    for bad in ("2[a,]3", "[a]", "0[a]", "2(a)"):
        with pytest.raises(ConfigError):
            load_config(f"[workers]\npool = {bad}\n")


def test_flag_errors():
    for bad in ("a = b\nb = a\n", "a = !(a)\n", "a = &(t,ghost)\n", "a = !(t,f)\n", "a = &(t))\n", "a = t f\n"):
        with pytest.raises(ConfigError):
            load_config("[flags]\n" + bad)


def test_model_path_normalised():
    c = load_config("[model]\npath = /a/./b/../../models/x_y-1.0/./\n")
    assert c.model_path == "/models/x_y-1.0"
    assert load_config("[model]\npath = /../..\n").model_path == "/"


# ------------------------------------------------------------------------------ routes
def test_routes_first_match_wins(cfg):
    assert cfg.route("toy-7b-instruct") == 1
    assert cfg.route("toy-chat-instruct") == 1        # earlier rule wins over toy-chat*
    assert cfg.route("toy-chat") == cfg.route("toy-chat-v2") == 0
    assert cfg.route("ToyXBase") == 2 and cfg.route("toyXBase") == 0   # case-sensitive, falls to *
    narrow = load_config("[workers]\npool = a,b\n[routes]\nllama-?b = 1\nqwen*:* = 0\n")
    assert narrow.route("llama-7b") == 1 and narrow.route("qwen2.5:latest") == 0
    with pytest.raises(NoRoute):
        narrow.route("llama-70b")
    with pytest.raises(ConfigError):
        load_config("[workers]\npool = a\n[routes]\n* = 1\n")   # worker index out of range


# ------------------------------------------------------------------------------ round trips
@pytest.mark.parametrize("name", EXAMPLES)
def test_round_trip_examples(name):
    c = load_config(example_path(name))
    text = c.to_text()
    again = load_config(text)
    assert again == c and again.to_text() == text
    assert load_config(str(example_path(name))) == c        # path given as a string


def test_round_trip_programmatic_config():
    c = LoadedConfig(server=ServerConfig(max_batch=3, token_budget=500, policy="edf", kv_blocks=64,
                                         eviction="random", prefix_cache=True, max_sessions=0),
                     model_path="/m/x", compiled=True, workers=["a", "b-2", "a"],
                     pool={"b-2": {"max_batch": 1, "kv_blocks": None}}, flags={"on_call": True, "beta": False},
                     routes=[("a?-*", 2), ("*", 0)])
    assert load_config(c.to_text()) == c


# ------------------------------------------------------------------------------ driving a server
def test_loaded_config_drives_a_server_run():
    c = load_config(example_path("server.conf"))
    tok = Tokenizer()
    server = Server(Engine(tok), c.server)
    server.submit_many(make_trace(16, seed=2))
    rep = server.run()
    assert len(rep.finished) == 16 and not rep.rejected
    assert max(rep.queue_len) >= 1                      # the config's max_batch=4 really limited admission
    small = dataclasses.replace(c.server, max_batch=1)
    server1 = Server(Engine(tok), small)
    server1.submit_many(make_trace(16, seed=2))
    rep1 = server1.run()
    assert rep1.ticks > rep.ticks and rep1.outputs() == rep.outputs()


def test_deployment_routes_requests_to_workers():
    c = load_config(example_path("server.conf"))
    models = ("toy-chat", "toy-7b-instruct", "ToyXBase", "other")
    dep = Deployment(c)
    assert isinstance(dep.engine.model, IRModel)          # compiled = fast -> t
    trace = make_trace(24, seed=1, models=models)
    dep.submit_many(trace)
    reps = dep.run()
    assert [s.cfg.max_batch for s in dep.servers] == [4, 4, 1]
    for i, rep in enumerate(reps):
        assert all(r.worker == i and c.route(r.model) == i for r in rep.requests)
        assert len(rep.finished) == len(rep.requests)
    assert sum(len(r.requests) for r in reps) == 24 and not dep.unrouted
    # same requests on a single plain-model server: identical outputs (routing never changes text)
    solo = Server(Engine(), ServerConfig(max_batch=4))
    solo.submit_many(make_trace(24, seed=1, models=models))
    merged = {rid: out for rep in reps for rid, out in rep.outputs().items()}
    assert merged == solo.run().outputs()


def test_unrouted_requests_are_rejected():
    c = load_config("[workers]\npool = a\n[routes]\ntoy-* = 0\n")
    dep = Deployment(c)
    dep.submit_many(make_trace(8, seed=3, models=("toy-x", "nope")))
    reps = dep.run()
    assert dep.unrouted and all(r.model == "nope" and r.finish_reason == "rejected" for r in dep.unrouted)
    assert len(reps[0].finished) + len(dep.unrouted) == 8
