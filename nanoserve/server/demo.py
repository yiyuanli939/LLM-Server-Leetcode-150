"""Framework: ``python -m nanoserve serve`` — the M2 server on a synthetic trace.

    NANOSERVE_REFERENCE=1 python -m nanoserve serve
    NANOSERVE_REFERENCE=1 python -m nanoserve serve --n 40 --rate 2 --batch 4 --budget 300 --sessions 6 --max-sessions 4
    NANOSERVE_REFERENCE=1 python -m nanoserve serve --workers 3 --policy weighted_free --costs 1 2 2 --plan

Prints: the single-server summary (+ checks that batching never changed an output and that the streaming
transport delivered every byte), analytics of the run, a cluster table (``--workers`` > 1) and the offline
batch plan (``--plan``).

Exercises reached from here: the M2 server core (via Server), stream.frame_codec / server.utf8_ok (via
transport), metrics.* (via analytics), sched.weighted_route / rr_busiest / assign_workers / merge_busy and
metrics.merged_median (via cluster), sched.sjf / min_launches / cooldown / min_workers / slo_bound /
busiest_worker (via planner).
"""
from __future__ import annotations

import argparse

from nanoserve._exercise import reference_mode
from nanoserve.engine import Engine, GenerationConfig
from nanoserve.server import analytics
from nanoserve.server.cluster import POLICIES, Cluster
from nanoserve.server.planner import BatchPlanner, fresh_batch
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import make_trace
from nanoserve.server.transport import roundtrip


def same_as_alone(engine: Engine, reqs: list[Request]) -> int:
    """How many finished requests produced exactly what they'd produce alone (Engine.generate)?"""
    ok = 0
    for r in reqs:
        cfg = GenerationConfig(max_tokens=r.max_tokens, temperature=r.temperature, top_k=r.top_k,
                               seed=r.seed, stop=r.stop)
        ok += engine.generate(r.prompt, cfg).text == r.output
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve serve", description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=30, help="requests in the trace")
    ap.add_argument("--rate", type=float, default=1.5, help="mean arrivals per tick")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--batch", type=int, default=4, help="max running requests per worker")
    ap.add_argument("--budget", type=int, default=None, help="token budget: Σ(prompt+max_tokens) in flight")
    ap.add_argument("--sessions", type=int, default=None, help="requests carry one of this many session ids")
    ap.add_argument("--max-sessions", type=int, default=None, help="reject requests opening a session beyond this")
    ap.add_argument("--maintenance", type=int, nargs=2, metavar=("START", "END"), default=None,
                    help="book a maintenance window [START, END) on the single server")
    ap.add_argument("--hot", type=float, default=1.0, help="weight of tenant 'a' vs 1 for 'b' and 'c'")
    ap.add_argument("--window", type=int, default=5, help="rolling-latency window (finished requests)")
    ap.add_argument("--packet", type=int, default=16, help="transport packet size in bytes")
    ap.add_argument("--workers", type=int, default=1, help="cluster size (>1 adds the cluster table)")
    ap.add_argument("--policy", choices=POLICIES, default="weighted")
    ap.add_argument("--weights", type=int, nargs="+", default=None, help="routing weights (policy weighted)")
    ap.add_argument("--costs", type=int, nargs="+", default=None, help="free-slot preference (weighted_free)")
    ap.add_argument("--plan", action="store_true", help="also plan the trace as an offline batch job")
    args = ap.parse_args(argv)
    if reference_mode():
        print("[reference mode]")

    engine = Engine()
    cfg = ServerConfig(max_batch=args.batch, token_budget=args.budget, max_sessions=args.max_sessions)
    trace = make_trace(args.n, seed=args.seed, rate=args.rate, sessions=args.sessions,
                       tenant_weights=(args.hot, 1.0, 1.0), deadline_slack=(5, 60))

    # ---- one server
    server = Server(engine, cfg, name="server")
    if args.maintenance and not server.schedule_maintenance(*args.maintenance):
        print(f"maintenance window {args.maintenance} rejected")
    server.submit_many(fresh_batch(trace))
    rep = server.run()
    print(rep.summary())
    same = same_as_alone(engine, rep.finished)
    client = roundtrip(rep.events, args.packet)
    print(f"  outputs identical to running alone: {same}/{len(rep.finished)}; "
          f"transport ({args.packet}-byte packets): {len(client.frames)} frames, "
          f"{'exact' if client.text == rep.outputs() else 'MISMATCH'}")
    peak_qps = max((q for _, q in rep.qps), default=0)
    extra = f"; peak live sessions {max(rep.active_sessions)}" if rep.active_sessions else ""
    print(f"  busy {rep.busy_ticks}/{rep.ticks} ticks in {len(rep.busy)} span(s); peak QPS window "
          f"{peak_qps} req / 3 s{extra}")

    print("\nanalytics")
    for line in analytics.lines(analytics.analyze(rep, window=args.window)):
        print("  " + line)

    # ---- cluster
    ok = same == len(rep.finished) and client.text == rep.outputs()
    if args.workers > 1:
        print()
        cluster = Cluster(args.workers, engine=engine, config=cfg, policy=args.policy, weights=args.weights,
                          costs=args.costs, seed=args.seed)
        cluster.submit_many(fresh_batch(trace))
        crep = cluster.run()
        for line in crep.table():
            print(line)
        csame = same_as_alone(engine, crep.finished)
        print(f"  outputs identical to running alone: {csame}/{len(crep.finished)}")
        ok = ok and csame == len(crep.finished)

    # ---- offline plan
    if args.plan:
        print()
        plan = BatchPlanner(engine, cfg).plan(trace, lanes=args.batch)
        for line in plan.lines():
            print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
