"""M5 integration: the toy model compiled to an operator graph and run by the engine."""
import random

import numpy as np
import pytest

from nanoserve.common.nodes import graph_nodes, graph_to_adjacency
from nanoserve.engine import Engine, GenerationConfig
from nanoserve.ir.compiler import GraphError, IRModel, compile_ir, lower_ngram, prune
from nanoserve.ir.devices import DEFAULT_TOPOLOGY, Topology, place
from nanoserve.ir.model_ir import ModelIR, Op, fold_constants, mass_value
from nanoserve.model.toy import NGramModel
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import make_trace
from nanoserve.tokenizer.tokenizer import Tokenizer

pytestmark = pytest.mark.milestone("M5")


@pytest.fixture(scope="module")
def tok():
    return Tokenizer()


@pytest.fixture(scope="module")
def ref(tok):
    return NGramModel(tok)


@pytest.fixture(scope="module")
def irm(tok, ref):
    return IRModel(tok, model=ref)


def _random_contexts(V, n, seed):
    rng = random.Random(seed)
    return [[rng.randrange(V) for _ in range(rng.randint(0, 9))] for _ in range(n)]


# ------------------------------------------------------------------------------ equivalence
def test_ir_logits_equal_model_logits(tok, ref, irm):
    ids = tok.encode("The compiler turns the model into a graph of operators. The cache is made of blocks.")
    contexts = [ids[:i] for i in range(len(ids) + 1)] + _random_contexts(len(tok), 200, seed=5)
    for ctx in contexts:
        assert np.allclose(irm.logits(ctx), ref.logits(ctx), rtol=0, atol=1e-12), ctx


def test_ir_model_built_from_scratch_with_other_hyperparameters(tok):
    kw = dict(order=3, lambdas=(0.6, 0.3, 0.075), floor=0.025)
    a, b = NGramModel(tok, **kw), IRModel(tok, **kw)
    assert b.ir.fixed_point == 1000 and mass_value(b.ir) == pytest.approx(1.0)
    for ctx in _random_contexts(len(tok), 100, seed=6):
        assert np.allclose(a.logits(ctx), b.logits(ctx))


def test_engine_with_ir_model_generates_identical_text():
    plain, compiled = Engine(), Engine(model=IRModel(Tokenizer()))
    for prompt in ("The scheduler", "The cache", "A", "When two requests share"):
        for cfg in (GenerationConfig(max_tokens=50, seed=3), GenerationConfig(max_tokens=40, temperature=0),
                    GenerationConfig(max_tokens=60, seed=8, stop=(".",), temperature=1.0, top_k=8)):
            a, b = plain.generate(prompt, cfg), compiled.generate(prompt, cfg)
            assert (a.text, a.token_ids, a.finish_reason) == (b.text, b.token_ids, b.finish_reason)


def test_server_outputs_identical_with_ir_model(tok):
    trace = lambda: make_trace(12, seed=4)  # noqa: E731
    reps = []
    for model in (None, IRModel(tok)):
        server = Server(Engine(tok, model=model), ServerConfig(max_batch=3))
        server.submit_many(trace())
        reps.append(server.run())
    assert len(reps[0].finished) == 12 and reps[0].outputs() == reps[1].outputs()


def test_coefficients_come_from_bytecode(irm, ref):
    consts = fold_constants(irm.ir)
    assert [consts[f"term{k}"] for k in (4, 3, 2, 1, 0)] == list(ref.lambdas)
    assert consts["base"] == ref.floor
    assert mass_value(irm.ir) == pytest.approx(sum(ref.lambdas) + ref.floor)


# ------------------------------------------------------------------------------ schedule / validation
def test_schedule_respects_dependencies(irm):
    plan = irm.plan
    pos = {op: i for i, op in enumerate(plan.order)}
    assert sorted(plan.order) == list(range(len(plan.ops)))
    for a, b in plan.ir.deps():
        assert pos[b] < pos[a]
    for i, op in enumerate(plan.ops):           # name-level check as well
        for t in op.inputs + op.optional:
            if t in plan.ir.index:
                assert pos[plan.ir.index[t]] < pos[i]


def test_cyclic_graph_is_rejected():
    ops = [Op("a", "sum", ("x",), optional=("c",)), Op("b", "scale", ("a",), program=("1",)),
           Op("c", "scale", ("b",), program=("1",)), Op("out", "log", ("c",))]
    with pytest.raises(GraphError, match="cycle"):
        compile_ir(ModelIR(ops, params=(), feeds=("x",), output="out"))
    with pytest.raises(GraphError, match="neither"):
        compile_ir(ModelIR([Op("out", "log", ("ghost",))], params=(), feeds=(), output="out"))


def test_malformed_bytecode_is_rejected():
    for prog in (("1", "+"), ("1", "2"), ("x",), ("99999999999",)):
        with pytest.raises(ValueError):
            ModelIR([Op("out", "scale", ("x",), program=prog)], params=("x",), feeds=(), output="out")


def test_dead_ops_are_eliminated():
    ops = [Op("a", "log", ("x",)), Op("unused", "log", ("a",)), Op("out", "log", ("a",))]
    plan = compile_ir(ModelIR(ops, params=("x",), feeds=(), output="out"))
    assert plan.eliminated == ["unused"] and [op.out for op in plan.ops] == ["a", "out"]


def test_parallel_pairs_are_exactly_the_unordered_ones(irm):
    plan = irm.plan
    pairs = set(plan.parallel_pairs())
    idx = plan.ir.index
    assert (idx["dist4"], idx["dist3"]) in pairs              # independent lookups
    assert (idx["dist4"], idx["term4"]) not in pairs          # producer -> consumer
    assert (idx["dist4"], idx["logits"]) not in pairs         # transitive
    for u, v in pairs:
        assert not plan.before[u][v] and not plan.before[v][u]
    deps = {(b, a) for a, b in plan.ir.deps()}
    assert all((u, v) not in deps and (v, u) not in deps for u, v in pairs)


def test_critical_path_bounds(irm):
    plan = irm.plan
    costs = [op.cost for op in plan.ops]
    cp = plan.critical_path()
    assert max(costs) <= cp <= sum(costs) == plan.serial_time()
    assert cp < sum(costs)  # the lookups really overlap
    # serialising everything in schedule order gives exactly the serial time
    chain = list(zip(plan.order, plan.order[1:]))
    assert plan.critical_path(chain) == sum(costs)


# ------------------------------------------------------------------------------ clone + pruning pass
def test_clone_is_deep_and_pass_leaves_original_untouched(irm):
    plan = irm.plan
    before_adj = graph_to_adjacency(plan.view)
    original = {id(n) for n in graph_nodes(plan.view)}
    assert len(original) == len(plan.ops)        # the view reaches every op from the entry node
    res = prune(plan, {"ctx1"})                   # edits a clone of plan.view
    assert graph_to_adjacency(plan.view) == before_adj
    assert not original & {id(n) for n in graph_nodes(res.work)}
    assert sorted(n.val for n in graph_nodes(res.work)) == sorted(irm.plan.ir.index[o] + 1 for o in
                                                                  [op.out for op in res.plan.ops])
    assert len(plan.ops) == 13 and plan.order == irm.plan.order


@pytest.mark.parametrize("n_ctx", range(0, 7))
def test_pruning_matches_context_length(irm, n_ctx):
    res = irm.specialize(n_ctx)
    kept = {op.out for op in res.plan.ops}
    for k in range(irm.order):
        present = k == 0 or n_ctx >= k
        assert (f"dist{k}" in kept) == present and (f"term{k}" in kept) == present
    assert {"base", "p", "logits"} <= kept
    assert len(res.removed) == 2 * max(0, irm.order - 1 - n_ctx)
    p = next(op for op in res.plan.ops if op.out == "p")
    assert set(p.optional) <= kept


def test_pruning_without_any_context_and_uncomputable_output(tok):
    plan = compile_ir(lower_ngram(NGramModel(tok, order=2, lambdas=(0.7, 0.2), floor=0.1))[0])
    assert {op.out for op in prune(plan, set()).plan.ops} == {"dist0", "term0", "base", "p", "logits"}
    needs_feed = compile_ir(ModelIR([Op("out", "log", ("x",))], params=(), feeds=("x",), output="out"))
    with pytest.raises(GraphError, match="not computable"):
        prune(needs_feed, set())


# ------------------------------------------------------------------------------ devices
def test_device_islands_and_broadcast():
    assert DEFAULT_TOPOLOGY.islands() == [[1, 2, 3, 4], [5, 6]]
    assert DEFAULT_TOPOLOGY.group_count() == 2
    one_way = Topology(3, [(1, 2, 4), (2, 3, 1)])
    assert one_way.islands() == [[1, 2, 3]]
    assert one_way.broadcast_time([1, 2, 3], 1) == 5
    assert one_way.broadcast_time([1, 2, 3], 3) == -1   # directed links: 3 reaches nobody


def test_placement_latency_between_parallel_and_serial(irm):
    plan = irm.plan
    p = place(plan, DEFAULT_TOPOLOGY)
    assert p.island == [1, 2, 3, 4] and p.broadcast == min(t for t in p.broadcast_by_host.values() if t >= 0)
    assert set(p.device_of) == {op.out for op in plan.ops} and set(p.device_of.values()) <= set(p.island)
    assert p.parallel <= p.latency <= p.serial
    single = place(plan, Topology(1, []))
    assert single.latency == single.serial and single.broadcast == 0
    wide = place(plan, Topology(8, [(u, u % 8 + 1, 1) for u in range(1, 9)]))   # a ring: 8 devices
    assert wide.latency == wide.parallel and wide.broadcast == 7


def test_no_valid_host_is_an_error(irm):
    with pytest.raises(ValueError):
        place(irm.plan, Topology(3, [(2, 1, 1), (3, 1, 1)]))   # nobody can reach both others
