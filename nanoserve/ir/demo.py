"""Framework: ``python -m nanoserve compile`` — the toy model as an operator graph (M5).

    NANOSERVE_REFERENCE=1 python -m nanoserve compile
    NANOSERVE_REFERENCE=1 python -m nanoserve compile --prompt "The cache" --short 2 --devices 1

Prints the lowered op graph, its schedule, the ops pruned for a short context, the op pairs that may
run in parallel, the critical-path latency estimate, a device placement, a rejected cyclic graph, and
checks that the compiled model's logits equal ``NGramModel.logits`` along a real prompt.

Exercises reached from here (via nanoserve.ir.compiler / model_ir / devices): ir.order_ok, ir.order,
ir.clone, ir.rpn, ir.depends_on, ir.computable, ir.critical_path, ir.op_latency, ir.device_groups.
"""
from __future__ import annotations

import argparse

import numpy as np

from nanoserve._exercise import reference_mode
from nanoserve.ir.compiler import GraphError, IRModel, compile_ir
from nanoserve.ir.devices import DEFAULT_TOPOLOGY, Topology, place
from nanoserve.ir.model_ir import ModelIR, Op, mass_program, mass_value
from nanoserve.model.toy import NGramModel
from nanoserve.tokenizer.tokenizer import Tokenizer


def cyclic_example() -> ModelIR:
    """A broken graph: attention needs the projection that needs the attention output."""
    return ModelIR([Op("attn", "sum", ("x",), optional=("proj",)), Op("proj", "scale", ("attn",), program=("1",)),
                    Op("out", "log", ("proj",))], params=(), feeds=("x",), output="out")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve compile", description=__doc__.splitlines()[0])
    ap.add_argument("--prompt", default="The compiler turns the model into a graph of operators.")
    ap.add_argument("--short", type=int, default=2, help="context length for the pruning example")
    ap.add_argument("--devices", type=int, default=0,
                    help="place on N fully linked devices instead of the default 6-device topology")
    args = ap.parse_args(argv)
    if reference_mode():
        print("[reference mode]")

    tok = Tokenizer()
    ref = NGramModel(tok)
    model = IRModel(tok, model=ref)
    plan = model.plan

    print(f"op graph: {len(plan.ops)} ops, params {', '.join(model.ir.params)}; feeds {', '.join(model.ir.feeds)}")
    for line in model.ir.table():
        print("  " + line)
    print(f"coefficient bytecode (fixed point {model.ir.fixed_point}): total mass "
          f"[{' '.join(mass_program(model.ir))}] / {model.ir.fixed_point} = {mass_value(model.ir):g}")
    print("schedule: " + " -> ".join(plan.names(plan.order)))

    short = model.specialize(args.short)
    print(f"context of {args.short} token(s): pruned {len(short.removed)} ops ({' '.join(short.removed) or '-'}); "
          f"runs {' -> '.join(short.plan.names(short.plan.order))}")
    for n in range(model.order + 1):
        print(f"  len(context)={n}: {len(model.specialize(n).plan.ops):>2} ops")

    pairs = plan.parallel_pairs()
    lookups = [(u, v) for u, v in pairs if plan.ops[u].kind == plan.ops[v].kind == "lookup"]
    print(f"parallel op pairs: {len(pairs)} of {len(plan.ops) * (len(plan.ops) - 1) // 2} "
          f"(e.g. {', '.join(f'{plan.ops[u].out}|{plan.ops[v].out}' for u, v in lookups[:4])})")
    cp = plan.critical_path()
    print(f"latency estimate: critical path {cp} vs serial {plan.serial_time()} "
          f"(max single op {max(op.cost for op in plan.ops)})")

    topo = DEFAULT_TOPOLOGY
    if args.devices:
        n = args.devices
        topo = Topology(n, [(u, v, 1) for u in range(1, n + 1) for v in range(1, n + 1) if u != v])
    for line in place(plan, topo).summary():
        print(line)

    try:
        compile_ir(cyclic_example())
        print("cyclic graph: accepted?!")
    except GraphError as e:
        print(f"cyclic graph rejected: {e}")

    ids = tok.encode(args.prompt)
    same = all(np.array_equal(model.logits(ids[:i]), ref.logits(ids[:i])) for i in range(len(ids) + 1))
    print(f"IR logits == NGramModel logits on all {len(ids) + 1} prefixes of {args.prompt!r}: "
          f"{'yes' if same else 'NO'}")
    return 0 if same else 1
