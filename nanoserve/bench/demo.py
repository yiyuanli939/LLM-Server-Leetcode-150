"""Framework: ``python -m nanoserve bench`` — benchmark grid, determinism check, parser fuzzing (M6).

    NANOSERVE_REFERENCE=1 python -m nanoserve bench
    NANOSERVE_REFERENCE=1 python -m nanoserve bench --sizes 1 2 3 --orders 5 --fuzz-n 7

Exercises reached from here (via nanoserve.bench.runner): bench.choose, bench.orders, bench.json_fuzz
(plus config.brackets, the checker being fuzzed).
"""
from __future__ import annotations

import argparse

from nanoserve._exercise import reference_mode
from nanoserve.bench.runner import (CORE_TOGGLES, OPTIONAL_TOGGLES, available_toggles, check_arrival_orders,
                                    fuzz_brackets, grid_table, run_grid)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve bench", description=__doc__.splitlines()[0])
    ap.add_argument("--sizes", type=int, nargs="+", default=[1, 2], help="numbers of toggles on (k of n)")
    ap.add_argument("--core-only", action="store_true", help="only M2-core toggles (no M3/M4 plug-ins)")
    ap.add_argument("--orders", type=int, default=4, help="same-tick requests whose arrival orders are replayed (1..6)")
    ap.add_argument("--fuzz-n", type=int, default=6, help="bracket pairs for the parser fuzz (1..8)")
    args = ap.parse_args(argv)
    if reference_mode():
        print("[reference mode]")

    wanted = CORE_TOGGLES if args.core_only else CORE_TOGGLES + OPTIONAL_TOGGLES
    toggles, skipped = available_toggles(wanted)
    print(f"benchmark grid: {len(toggles)} toggles, configs with k in {args.sizes} on, same 16-request trace")
    for t in toggles:
        print(f"  {t.name:<9} {t.note}")
    for name, why in skipped:
        print(f"  {name:<9} skipped: {why}")
    rows = run_grid(toggles, args.sizes)
    print(grid_table(rows))
    best = min(rows, key=lambda r: (r.p50 if r.p50 is not None else float("inf"), r.report.ticks))
    print(f"lowest p50: {best.name} ({best.p50} ticks); util = busy ticks / ticks, occ = slot occupancy, "
          f"SLO = deadlines met; same-out = outputs identical to baseline")
    outputs_ok = all(r.same_outputs is not False for r in rows)

    det = check_arrival_orders(args.orders)
    print(f"\ndeterminism: {det.orders} arrival orders of {det.n_requests} same-tick requests (2 slots) -> "
          f"{det.distinct_schedules} distinct schedules, {det.distinct_outputs} distinct output set(s): "
          f"{'OK' if det.ok else 'NOT DETERMINISTIC'}")

    fz = fuzz_brackets(args.fuzz_n)
    print(f"\nconfig pre-check fuzz (n={fz.n}): {fz.structures} bracket structures -> {fz.valid_checked} typed "
          f"valid strings, {fz.mutants_checked} single-char mutants")
    print(f"  valid rejected: {len(fz.valid_rejected)}   mutants accepted: {len(fz.mutants_accepted)}   "
          f"{'OK' if fz.ok else 'CHECKER IS WRONG'}")
    for s in (fz.valid_rejected + fz.mutants_accepted)[:5]:
        print(f"    e.g. {s!r}")
    return 0 if (outputs_ok and det.ok and fz.ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
