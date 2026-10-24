"""Framework: the model IR — operators, tensors, coefficient bytecode and the interpreter (M5).

A model is lowered (see ``nanoserve.ir.compiler``) to a list of :class:`Op` records. Every op
produces one named tensor (``op.out``, also the op's name) from named input tensors. Tensors no op
produces are *params* (always present: weight tables, sizes) or *feeds* (per-call inputs that may be
missing — e.g. "the last 4 context tokens" when the context is shorter than 4). The toy n-gram model
``p = floor/V + Σ_k λ_k · dist_k(context[-k:])``, ``logits = log p`` becomes::

    dist4  = lookup(table4, ctx4)         next-token distribution after the last 4 tokens (or None)
    term4  = scale(dist4)                 coef [5 100 * 10 /]  = 50 -> 50 / 100 = 0.5
    ...                                   (orders 3, 2, 1 and the context-free unigram, order 0)
    base   = floor(vocab_size)            coef [1 100 * 100 /] = 1  -> 0.01 spread over the vocab
    p      = sum(base; term4 term3 term2 term1 term0)   variadic: absent optional terms are skipped
    logits = log(p)

Scalar coefficients are stored as tiny postfix *bytecode* programs over 32-bit integers, interpreted
by ``eval_rpn``: the program computes ``coefficient * fixed_point`` (``coef_program``; the fixed
point is the smallest power of ten that represents every coefficient exactly — 100 here), and
``fold_constants`` runs every program once per compiled graph. ``mass_program`` concatenates them
into one program whose value is the model's total probability mass (Σλ + floor), a sanity check.

``ModelIR.build_view`` gives the *op-graph view* that optimisation passes edit: one ``GraphNode``
per op (``val`` = op index + 1, ``neighbors`` = ops it exchanges a tensor with, either direction).

Exercises this file calls: ir.rpn (``fold_constants``, ``mass_value``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from nanoserve.common.nodes import GraphNode
from nanoserve.ir.interp import eval_rpn

KINDS = ("lookup", "scale", "floor", "sum", "log")
MAX_OPS = 100          # the dependency analyses in the compiler are sized for small graphs
INT32_MAX = 2**31 - 1  # the bytecode interpreter works on 32-bit integers


@dataclass(frozen=True)
class Op:
    """One operator. Frozen: passes build new op records instead of mutating them."""

    out: str                         # tensor this op produces (also the op's name)
    kind: str                        # one of KINDS
    inputs: tuple[str, ...]          # required inputs: the op cannot run without all of them
    optional: tuple[str, ...] = ()   # variadic extras (sum terms): used, in this order, when present
    cost: int = 1                    # abstract latency units, for schedule / latency estimates
    program: tuple[str, ...] = ()    # postfix bytecode of the op's scalar coefficient (scale/floor)
    order: int | None = None         # n-gram order k of a lookup (its context = the last k tokens)

    def describe(self) -> str:
        args = ", ".join(self.inputs)
        if self.optional:
            args += "; " + " ".join(self.optional)
        coef = f"  coef=[{' '.join(self.program)}]" if self.program else ""
        return f"{self.out} = {self.kind}({args}){coef}"


class ModelIR:
    """An operator graph plus the names of its params, feeds and output tensor.

    The constructor only checks *names* (unique, ops well-formed). Graph properties — acyclic, no
    dead ops, every input resolvable — are the compiler's job (``compiler.compile_ir``), so that a
    broken graph can still be built, inspected and rejected with a precise error.
    """

    def __init__(self, ops: Sequence[Op], params: Sequence[str], feeds: Sequence[str], output: str,
                 fixed_point: int = 1):
        self.ops: list[Op] = list(ops)
        self.params: tuple[str, ...] = tuple(params)
        self.feeds: tuple[str, ...] = tuple(feeds)
        self.output = output
        self.fixed_point = fixed_point
        self._check_names()
        self.index: dict[str, int] = {op.out: i for i, op in enumerate(self.ops)}

    def _check_names(self) -> None:
        if not 1 <= len(self.ops) <= MAX_OPS:
            raise ValueError(f"an IR needs 1..{MAX_OPS} ops, got {len(self.ops)}")
        names = [op.out for op in self.ops] + list(self.params) + list(self.feeds)
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            raise ValueError(f"tensor names must be unique, duplicated: {dup}")
        for op in self.ops:
            args = op.inputs + op.optional
            if op.kind not in KINDS:
                raise ValueError(f"{op.out}: unknown op kind {op.kind!r}")
            if not op.inputs or len(set(args)) != len(args):
                raise ValueError(f"{op.out}: needs >= 1 required input and no repeated inputs")
            if op.out in args:
                raise ValueError(f"{op.out}: an op cannot consume its own output")
            if op.cost < 1:
                raise ValueError(f"{op.out}: cost must be a positive integer")
            if (op.kind in ("scale", "floor")) != bool(op.program):
                raise ValueError(f"{op.out}: scale/floor ops need a coefficient program, other ops none")
            if op.program:
                _check_program(op.out, op.program)
        if self.output not in {op.out for op in self.ops}:
            raise ValueError(f"output {self.output!r} is not produced by any op")

    # ------------------------------------------------------------------ structure
    def deps(self) -> list[list[int]]:
        """``[a, b]``: op a consumes op b's output, i.e. a depends on b (0-based, no duplicates)."""
        out: list[list[int]] = []
        for a, op in enumerate(self.ops):
            seen: set[int] = set()
            for t in op.inputs + op.optional:
                b = self.index.get(t)
                if b is not None and b not in seen:
                    seen.add(b)
                    out.append([a, b])
        return out

    def unknown_tensors(self) -> list[str]:
        known = set(self.index) | set(self.params) | set(self.feeds)
        return sorted({t for op in self.ops for t in op.inputs + op.optional if t not in known})

    def build_view(self) -> GraphNode:
        """Undirected op-adjacency view; returns the entry node (``val`` 1 = op 0).

        Every op is reachable from the entry as long as the graph has no dead ops (the compiler
        checks that first): each op then has a path to the output.
        """
        nodes = [GraphNode(i + 1) for i in range(len(self.ops))]
        adj: list[set[int]] = [set() for _ in self.ops]
        for a, b in self.deps():
            adj[a].add(b)
            adj[b].add(a)
        for i, node in enumerate(nodes):
            node.neighbors = [nodes[j] for j in sorted(adj[i])]
        return nodes[0]

    def table(self) -> list[str]:
        """One line per op, for demos."""
        return [f"#{i + 1:<2} {op.describe():<54} cost={op.cost}" for i, op in enumerate(self.ops)]


# ====================================================================================== bytecode
_OPS = ("+", "-", "*", "/")


def _check_program(name: str, program: Sequence[str]) -> None:
    """Structural check of postfix bytecode: int32 literals, operators with two operands, one result.

    (Value ranges and division by zero depend on the numbers; ``coef_program`` guarantees them for the
    programs the compiler emits.)
    """
    depth = 0
    for tok in program:
        if tok in _OPS:
            if depth < 2:
                raise ValueError(f"{name}: operator {tok!r} needs two operands in {list(program)}")
            depth -= 1
        elif re.fullmatch(r"-?\d+", tok) and -INT32_MAX - 1 <= int(tok) <= INT32_MAX:
            depth += 1
        else:
            raise ValueError(f"{name}: bad bytecode token {tok!r}")
    if depth != 1:
        raise ValueError(f"{name}: program must leave exactly one value, got {list(program)}")


def decimal_places(c: float, max_places: int = 9) -> int:
    """Fewest decimal places that represent ``c`` exactly (as a float), capped at ``max_places``."""
    for e in range(max_places + 1):
        if round(c * 10**e) / 10**e == c:
            return e
    return max_places


def coef_program(c: float, fixed_point: int) -> tuple[str, ...]:
    """Bytecode computing ``c * fixed_point`` as an integer, e.g. 0.15 @ 10^4 -> ``15 10000 * 100 /``.

    ``fixed_point`` must be a power of ten with at least ``decimal_places(c)`` zeros, so the
    division is exact. Raises if an intermediate would leave the interpreter's 32-bit range.
    """
    if c < 0:
        raise ValueError("coefficients must be non-negative")
    e = decimal_places(c)
    num, den = round(c * 10**e), 10**e
    if fixed_point % den:
        raise ValueError(f"fixed point {fixed_point} cannot represent {c} exactly")
    if num * fixed_point <= INT32_MAX:
        return (str(num), str(fixed_point), "*", str(den), "/")
    if num * (fixed_point // den) <= INT32_MAX:   # same value without the big intermediate
        return (str(num), str(fixed_point // den), "*")
    raise ValueError(f"coefficient {c} does not fit the 32-bit fixed-point bytecode")


def fold_constants(ir: ModelIR) -> dict[str, float]:
    """Run every op's coefficient bytecode once: ``{op.out: program_value / fixed_point}``."""
    return {op.out: eval_rpn(list(op.program)) / ir.fixed_point for op in ir.ops if op.program}


def mass_program(ir: ModelIR) -> list[str]:
    """One program summing every coefficient: ``prog1 prog2 + prog3 + ...``."""
    progs = [list(op.program) for op in ir.ops if op.program]
    out = progs[0] if progs else ["0"]
    for p in progs[1:]:
        out = out + p + ["+"]
    return out


def mass_value(ir: ModelIR) -> float:
    """Total probability mass the coefficients assign (1.0 for a normalised model)."""
    parts = fold_constants(ir)   # each program on its own is within 32 bits; the running sum must be too
    if sum(abs(v) for v in parts.values()) * ir.fixed_point > INT32_MAX:
        raise ValueError("coefficient sum does not fit the 32-bit bytecode")
    return eval_rpn(mass_program(ir)) / ir.fixed_point


# ====================================================================================== runtime
def _lookup(table: Mapping[tuple, np.ndarray], ctx: tuple) -> np.ndarray | None:
    """Next-token distribution after ``ctx``; ``None`` when the context was never seen."""
    row = table.get(ctx)
    if row is None or row.sum() == 0:
        return None
    return row / row.sum()


def execute(ir: ModelIR, order: Sequence[int], consts: Mapping[str, float], env: Mapping[str, Any]) -> Any:
    """Interpret ``ir`` op by op in ``order`` (a valid schedule). ``env`` holds params and feeds.

    A tensor may evaluate to ``None`` ("no evidence", e.g. an unseen context): ``scale`` passes it
    through and ``sum`` skips it — exactly the ``if d is not None`` of ``NGramModel.logits``.
    """
    vals: dict[str, Any] = dict(env)
    for i in order:
        op = ir.ops[i]
        if op.kind == "lookup":
            ctx = vals[op.inputs[1]] if len(op.inputs) > 1 else ()
            vals[op.out] = _lookup(vals[op.inputs[0]], ctx)
        elif op.kind == "scale":
            d = vals[op.inputs[0]]
            vals[op.out] = None if d is None else consts[op.out] * d
        elif op.kind == "floor":
            V = int(vals[op.inputs[0]])
            vals[op.out] = np.full(V, consts[op.out] / V)
        elif op.kind == "sum":
            acc = np.array(vals[op.inputs[0]], dtype=float, copy=True)
            for t in op.optional:  # declared order = summation order (keeps results bit-identical)
                v = vals.get(t)
                if v is not None:
                    acc += v
            vals[op.out] = acc
        elif op.kind == "log":
            vals[op.out] = np.log(vals[op.inputs[0]])
        else:  # pragma: no cover - rejected by ModelIR._check_names
            raise ValueError(op.kind)
    return vals[ir.output]
