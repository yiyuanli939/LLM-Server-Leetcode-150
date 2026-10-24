"""Framework: ``python -m nanoserve config [path]`` — load a server config and run a trace with it (M5).

    NANOSERVE_REFERENCE=1 python -m nanoserve config                                   # examples/server.conf
    NANOSERVE_REFERENCE=1 python -m nanoserve config nanoserve/config/examples/minimal.conf -n 12

Pretty-prints the loaded config (server settings, model path, worker pool, flags, routing rules),
shows where a few model names are routed, then replays a short synthetic trace on one ``Server`` per
worker. With ``--canonical`` it prints the canonical text form instead of running.

Exercises reached from here (via nanoserve.config.loader / deploy): config.strip_comments,
config.brackets, config.expr, config.arith, config.flags, config.expand, config.norm_path,
config.glob (and ir.order for flag dependencies; with ``compiled = t`` the M5 IR compiler).
"""
from __future__ import annotations

import argparse
from collections import Counter

from nanoserve._exercise import reference_mode
from nanoserve.config.deploy import Deployment
from nanoserve.config.loader import ConfigError, NoRoute, example_path, load_config
from nanoserve.server.trace import make_trace

MODELS = ("toy-chat", "toy-7b-instruct", "ToyXBase", "toy-chat-v2", "mystery")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve config", description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default=str(example_path()), help="config file (default: examples/server.conf)")
    ap.add_argument("-n", "--requests", type=int, default=24, help="requests in the trace")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--canonical", action="store_true", help="print the canonical config text and exit")
    args = ap.parse_args(argv)
    if reference_mode():
        print("[reference mode]")

    try:
        cfg = load_config(args.path)
    except (ConfigError, OSError) as e:
        print(f"cannot load {args.path}: {e}")
        return 1
    if args.canonical:
        print(cfg.to_text(), end="")
        return 0
    for line in cfg.describe():
        print(line)

    for m in MODELS:
        try:
            print(f"  {m:<16} -> worker {cfg.route(m)}")
        except NoRoute:
            print(f"  {m:<16} -> (no route: rejected)")

    if cfg.server.policy != "fcfs" or cfg.server.kv_blocks is not None or cfg.server.prefix_cache or any(
            cfg.worker_config(i).kv_blocks is not None for i in range(len(cfg.workers))):
        print("(this config uses M3/M4 plug-ins; the run needs them implemented)")
    dep = Deployment(cfg)
    dep.submit_many(make_trace(args.requests, seed=args.seed, models=MODELS))
    print(f"trace: {args.requests} requests over models {', '.join(MODELS)}")
    for rep, server in zip(dep.run(), dep.servers):
        by_model = Counter(r.model for r in rep.requests)
        print(f"  {rep.summary()}  max_batch={server.cfg.max_batch} "
              f"models={dict(sorted(by_model.items()))}")
    if dep.unrouted:
        print(f"  unrouted: {len(dep.unrouted)} request(s) rejected ({', '.join(sorted({r.model for r in dep.unrouted}))})")
    return 0
