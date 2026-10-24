"""Framework: the IR compiler — lowering, validation, scheduling, passes and estimates (M5).

    ir, weights = lower_ngram(model)       # NGramModel -> operator graph (+ its count tables as params)
    plan = compile_ir(ir)                  # validate, drop dead ops, schedule, fold coefficient bytecode
    short = prune(plan, {"ctx1", "ctx2"})  # specialise for a 2-token context (clone + edit pass)
    plan.parallel_pairs(), plan.critical_path()
    IRModel(tokenizer).logits(context)     # drop-in for NGramModel.logits, runs the compiled graph

Pipeline of ``compile_ir``:

  1. every input tensor must be a param, a feed or some op's output;
  2. the dependency graph must be acyclic (``can_schedule``) — otherwise ``GraphError``;
  3. precedence matrix "op u must run before op v" (``depends_queries``) — ops that are not needed
     by the output are dead and dropped; pairs with no order either way may run in parallel;
  4. an execution order (``topo_order``) and the op-graph view (``ModelIR.build_view``);
  5. constant folding of the coefficient bytecode (``eval_rpn`` via ``model_ir.fold_constants``).

``prune`` is the optimisation pass used at run time: given the feeds a call actually has (a short
context lacks the last-4-tokens feed, …) it keeps only ops ``computable_outputs`` can produce. Like any
pass it edits a *copy* of the op-graph view (``clone_graph``): it unlinks the dead ops there and keeps
the component still attached to the output, so the original plan stays usable for the next context.

Exercises this file calls: ir.order_ok, ir.order, ir.depends_on, ir.clone, ir.computable,
ir.critical_path (and ir.rpn through ``model_ir``).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Sequence

import numpy as np

from nanoserve.common.nodes import GraphNode, graph_nodes
from nanoserve.ir.graph import can_schedule, clone_graph, topo_order
from nanoserve.ir.latency import critical_path_time
from nanoserve.ir.model_ir import ModelIR, Op, coef_program, decimal_places, execute, fold_constants
from nanoserve.ir.reach import computable_outputs, depends_queries
from nanoserve.model.toy import NGramModel


class GraphError(ValueError):
    """The operator graph cannot be compiled (cycle, unknown tensor, output not computable)."""


# ====================================================================================== lowering
def lower_ngram(model: NGramModel) -> tuple[ModelIR, dict[str, Any]]:
    """Express ``NGramModel.logits`` as an operator graph. Returns ``(ir, params)``.

    Op list (order 5): dist4, term4, dist3, term3, …, dist0, term0, base, p, logits. ``dist_k`` looks
    up the count table of order k with feed ``ctx_k`` (= the last k tokens; order 0 needs no feed),
    ``term_k`` scales it by λ_k, ``base`` is the uniform floor, ``p`` sums, ``logits = log p``.
    """
    orders = [k for k, _ in zip(range(model.order - 1, -1, -1), model.lambdas)]
    lambdas = list(model.lambdas)[: len(orders)]
    fixed_point = 10 ** max(decimal_places(c) for c in [*lambdas, model.floor])
    ops: list[Op] = []
    for k, lam in zip(orders, lambdas):
        ins = (f"table{k}", f"ctx{k}") if k else (f"table{k}",)
        ops.append(Op(f"dist{k}", "lookup", ins, cost=2 + k, order=k))   # hashing k tokens + a row gather
        ops.append(Op(f"term{k}", "scale", (f"dist{k}",), program=coef_program(lam, fixed_point)))
    ops.append(Op("base", "floor", ("vocab_size",), program=coef_program(model.floor, fixed_point)))
    ops.append(Op("p", "sum", ("base",), optional=tuple(f"term{k}" for k in orders), cost=2))
    ops.append(Op("logits", "log", ("p",), cost=2))
    params: dict[str, Any] = {f"table{k}": model.counts[k] for k in orders}
    params["vocab_size"] = model.V
    feeds = [f"ctx{k}" for k in orders if k]
    return ModelIR(ops, list(params), feeds, "logits", fixed_point), params


# ====================================================================================== compiling
@dataclass
class Plan:
    """A validated, scheduled IR ready to execute."""

    ir: ModelIR
    order: list[int]                  # execution order (op indices)
    before: list[list[bool]]          # before[u][v]: op u must (transitively) finish before op v
    view: GraphNode                   # op-graph view, entry node = op #1 (val 1)
    consts: dict[str, float]          # folded coefficients, op name -> value
    eliminated: list[str] = field(default_factory=list)   # dead ops dropped while compiling

    @property
    def ops(self) -> list[Op]:
        return self.ir.ops

    def names(self, idx: Iterable[int]) -> list[str]:
        return [self.ir.ops[i].out for i in idx]

    def parallel_pairs(self) -> list[tuple[int, int]]:
        """Op pairs ``(u, v)``, u < v, with no ordering constraint either way."""
        n = len(self.ops)
        return [(u, v) for u in range(n) for v in range(u + 1, n)
                if not self.before[u][v] and not self.before[v][u]]

    def critical_path(self, extra_before: Iterable[tuple[int, int]] = ()) -> int:
        """Latency with unlimited parallelism (sum of costs along the longest dependency chain).

        ``extra_before``: additional (u, v) "u runs before v" constraints, e.g. ops serialised on one
        device; they must agree with ``order`` so the graph stays acyclic.
        """
        pairs = {(b, a) for a, b in self.ir.deps()} | set(extra_before)
        return critical_path_time(len(self.ops), [[u + 1, v + 1] for u, v in sorted(pairs)],
                                  [op.cost for op in self.ops])

    def serial_time(self) -> int:
        return sum(op.cost for op in self.ops)

    def run(self, env: dict[str, Any]) -> Any:
        return execute(self.ir, self.order, self.consts, env)


def validate(ir: ModelIR) -> None:
    """Raise ``GraphError`` unless every input resolves and the dependency graph is acyclic."""
    unknown = ir.unknown_tensors()
    if unknown:
        raise GraphError(f"inputs that are neither params, feeds nor op outputs: {unknown}")
    if not can_schedule(len(ir.ops), ir.deps()):
        raise GraphError(f"dependency cycle: no execution order exists for the {len(ir.ops)} ops")


def precedence(ir: ModelIR) -> list[list[bool]]:
    """``before[u][v]`` for all op pairs (acyclic IR). One batched query, n <= 100 -> <= 9900 queries."""
    n = len(ir.ops)
    before = [[False] * n for _ in range(n)]
    if n == 1:
        return before
    runs_first = [[b, a] for a, b in ir.deps()]   # a depends on b  ->  b must run before a
    queries = [[u, v] for u in range(n) for v in range(n) if u != v]
    for (u, v), yes in zip(queries, depends_queries(n, runs_first, queries)):
        before[u][v] = yes
    return before


def compile_ir(ir: ModelIR) -> Plan:
    validate(ir)
    before = precedence(ir)
    out = ir.index[ir.output]
    dead = [i for i in range(len(ir.ops)) if i != out and not before[i][out]]
    if dead:  # nothing live reads a dead op's output, so dropping them never breaks an input
        live = ModelIR([op for i, op in enumerate(ir.ops) if i not in set(dead)],
                       ir.params, ir.feeds, ir.output, ir.fixed_point)
        plan = compile_ir(live)
        plan.eliminated = [ir.ops[i].out for i in dead] + plan.eliminated
        return plan
    order = topo_order(len(ir.ops), ir.deps())
    # every op is an ancestor of the output now, so the undirected view is connected
    return Plan(ir, order, before, ir.build_view(), fold_constants(ir))


# ====================================================================================== pruning pass
@dataclass
class Pruned:
    plan: Plan                 # the specialised plan
    removed: list[str]         # ops of the original plan that were pruned
    work: GraphNode            # output node of the edited copy of the original view


def prune(plan: Plan, available: Iterable[str]) -> Pruned:
    """Specialise ``plan`` for the feeds in ``available``; ops that cannot be computed are removed."""
    ir = plan.ir
    have = set(available)
    provided = list(ir.params) + [f for f in ir.feeds if f in have]
    ok = set(computable_outputs([op.out for op in ir.ops], [list(op.inputs) for op in ir.ops], provided))
    if ir.output not in ok:
        raise GraphError(f"output {ir.output!r} is not computable from feeds {sorted(have)}")

    work = clone_graph(plan.view)  # the pass edits a copy: plan.view must survive for other contexts
    by_val = {node.val: node for node in graph_nodes(work)}
    for val, node in by_val.items():
        if ir.ops[val - 1].out not in ok:     # unlink the op from the copy
            for nb in node.neighbors:
                nb.neighbors.remove(node)
            node.neighbors = []
    work_out = by_val[ir.index[ir.output] + 1]
    keep = sorted(node.val - 1 for node in graph_nodes(work_out))  # still attached to the output
    kept = {ir.ops[i].out for i in keep}
    ops = [replace(ir.ops[i], optional=tuple(t for t in ir.ops[i].optional if t in kept or t not in ir.index))
           for i in keep]
    small = compile_ir(ModelIR(ops, ir.params, ir.feeds, ir.output, ir.fixed_point))
    removed = [op.out for op in ir.ops if op.out not in kept] + small.eliminated
    return Pruned(small, removed, work_out)


# ====================================================================================== the model
class IRModel:
    """Drop-in replacement for ``NGramModel``: ``logits`` runs the compiled operator graph.

    The count tables ("weights") come from an ``NGramModel`` built with the same arguments (or passed
    in as ``model``). One pruned plan is compiled per set of available context feeds and cached.
    """

    def __init__(self, tokenizer, model: NGramModel | None = None, **ngram_kwargs: Any):
        weights = model if model is not None else NGramModel(tokenizer, **ngram_kwargs)
        self.V = weights.V
        self.order = weights.order
        self.ir, self.params = lower_ngram(weights)
        self.plan = compile_ir(self.ir)
        self.feed_len = {f"ctx{op.order}": op.order for op in self.ir.ops if op.kind == "lookup" and op.order}
        self._pruned: dict[frozenset[str], Pruned] = {}

    def specialize(self, n_context: int) -> Pruned:
        """The plan for a context of ``n_context`` tokens (compiled on first use, then cached)."""
        key = frozenset(f for f, k in self.feed_len.items() if n_context >= k)
        if key not in self._pruned:
            self._pruned[key] = prune(self.plan, key)
        return self._pruned[key]

    def feeds(self, context: Sequence[int]) -> dict[str, tuple]:
        return {f: tuple(context[-k:]) for f, k in self.feed_len.items() if len(context) >= k}

    def logits(self, context: list[int]) -> np.ndarray:
        plan = self.specialize(len(context)).plan
        return plan.run({**self.params, **self.feeds(context)})
