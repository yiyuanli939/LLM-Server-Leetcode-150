"""Framework: ``python -m nanoserve dashboard`` — the M7 text dashboard of a server / cluster run.

    NANOSERVE_REFERENCE=1 python -m nanoserve dashboard
    NANOSERVE_REFERENCE=1 python -m nanoserve dashboard --filter rb --k 3 --workers 3 --fail 1 toy-code

Prints: the dashboard of one server run (heatmap, slowest-k, filtered request list); the throughput
panel of a run under KV pressure (late corrections when the server preempts — needs the M3 BlockManager,
skipped if it does not import); with ``--workers`` > 1 a cluster dashboard (utilization union) and the
health matrix with a fault injection, followed by a health-aware run that routes around the blast radius.

Exercises reached from here: dash.region_sum, metrics.slowest_k, dash.fuzzy, metrics.corrected,
metrics.busy_time (via panel), dash.mask_failed (via health_router).
"""
from __future__ import annotations

import argparse
import importlib

from nanoserve._exercise import reference_mode
from nanoserve.autoscale.planned import PlannedCluster
from nanoserve.dashboard.health_router import HealthMatrix
from nanoserve.dashboard.panel import Dashboard, ThroughputMonitor
from nanoserve.engine import Engine
from nanoserve.server.cluster import Cluster
from nanoserve.server.planner import fresh_batch
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import make_trace

MODELS = ("toy-chat", "toy-code", "toy-base")


def kv_available() -> bool:
    try:
        importlib.import_module("nanoserve.kvcache.manager")
    except ImportError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve dashboard", description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=24, help="requests in the trace")
    ap.add_argument("--rate", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--filter", default="", help="fzf-style filter over rid / tenant / model / prompt")
    ap.add_argument("--k", type=int, default=5, help="size of the slowest-requests panel")
    ap.add_argument("--width", type=int, default=48, help="heatmap columns")
    ap.add_argument("--workers", type=int, default=1, help="> 1 adds the cluster + health panels")
    ap.add_argument("--kv-blocks", type=int, default=20, help="KV blocks for the throughput/preemption run")
    ap.add_argument("--fail", nargs=2, metavar=("WORKER", "MODEL"), default=None,
                    help="fault injection for the health matrix (default: last worker, toy-code)")
    args = ap.parse_args(argv)
    if reference_mode():
        print("[reference mode]")

    engine = Engine()
    cfg = ServerConfig(max_batch=args.batch)
    trace = make_trace(args.n, seed=args.seed, rate=args.rate, models=MODELS)

    server = Server(engine, cfg, name="server")
    server.submit_many(fresh_batch(trace))
    for line in Dashboard(server.run()).render(query=args.filter, k=args.k, width=args.width):
        print(line)

    print()
    if kv_available():
        kv_server = Server(engine, ServerConfig(max_batch=args.batch, kv_blocks=args.kv_blocks, block_size=4),
                           name="kv-pressure")
        kv_server.submit_many(fresh_batch(trace))
        mon = ThroughputMonitor(kv_server)
        rep = mon.run()
        print(f"[{rep.name}] {len(rep.finished)} finished, "
              f"{sum(r.preemptions for r in rep.requests)} preemption(s), {rep.ticks} ticks")
        for line in mon.lines():
            print("  " + line)
        for at, ts, v in mon.corrections[:3]:
            print(f"    at tick {at}: tick {ts} corrected to {v} chars")
    else:
        print("throughput panel skipped: nanoserve.kvcache.manager (M3) does not import yet")

    if args.workers > 1:
        print()
        cluster = Cluster(args.workers, engine=engine, config=cfg, policy="weighted", seed=args.seed)
        cluster.submit_many(fresh_batch(trace))
        crep = cluster.run()
        for line in Dashboard(crep).render(query=args.filter, k=args.k, width=args.width, rows=0):
            print(line)

        print()
        health = HealthMatrix(args.workers, MODELS)
        w, m = (int(args.fail[0]), args.fail[1]) if args.fail else (args.workers - 1, "toy-code")
        health.fail(w, m)
        for line in health.lines():
            print(line)
        plan = health.route(trace)
        routed = PlannedCluster(args.workers, plan, engine=engine, config=cfg)
        routed.submit_many(fresh_batch(trace))
        hrep = routed.run()
        on_drained = [r.rid for r in hrep.requests if r.worker in health.drained_workers()]
        print(f"  health-aware run: {len(hrep.finished)} finished, {len(hrep.rejected)} rejected (paused model); "
              f"requests on drained workers: {len(on_drained)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
