"""Framework: ``python -m nanoserve autoscale`` — M7 capacity planning, validated on the real server.

    NANOSERVE_REFERENCE=1 python -m nanoserve autoscale
    NANOSERVE_REFERENCE=1 python -m nanoserve autoscale --burst 40 --target 45 --horizon 60 --waves 3

Prints three recommendations, each followed by the runs that check it: the smallest worker set for a
burst (autoscale.min_time), the batch size of single-adapter launches to drain per-tenant backlogs
(autoscale.min_rate), and the token budget per wave of an ordered batch job (autoscale.min_throughput).
Exit code 1 if a validation fails.
"""
from __future__ import annotations

import argparse

from nanoserve._exercise import reference_mode
from nanoserve.autoscale.autoscaler import POOL, Autoscaler, burst, ordered_job
from nanoserve.engine import Engine


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve autoscale", description=__doc__.splitlines()[0])
    ap.add_argument("--burst", type=int, default=30, help="requests in the traffic spike")
    ap.add_argument("--target", type=int, default=40, help="makespan target for the spike (ticks)")
    ap.add_argument("--queues", type=int, nargs="+", default=[7, 3, 11, 5], help="per-tenant backlogs")
    ap.add_argument("--horizon", type=int, default=40, help="drain the backlogs within this many ticks")
    ap.add_argument("--job", type=int, default=12, help="requests in the ordered batch job")
    ap.add_argument("--waves", type=int, default=4, help="max waves for the ordered batch job")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    if reference_mode():
        print("[reference mode]")

    scaler = Autoscaler(Engine())
    ok = True

    pool = scaler.size_pool(POOL, burst(args.burst), args.target)
    for line in pool.lines():
        print(line)
    ok = ok and pool.estimate is not None and pool.meets_target and \
        (pool.run_fewer is None or pool.run_fewer.ticks > args.target)

    print()
    queues = {f"t{i}": q for i, q in enumerate(args.queues)}
    try:
        drain = scaler.size_batch(queues, args.horizon)
    except ValueError as e:
        print(f"multi-LoRA sizing: {e}")
        ok = False
    else:
        for line in drain.lines():
            print(line)
        ok = ok and drain.run.ticks <= args.horizon and (drain.run_less is None or drain.run_less.ticks > args.horizon)

    print()
    waves = scaler.size_waves(ordered_job(args.job, args.seed), min(args.waves, args.job))
    for line in waves.lines():
        print(line)
    ok = ok and waves.waited(waves.run) == 0 and (waves.run_less is None or waves.waited(waves.run_less) > 0)
    print(f"\nall estimates validated: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
