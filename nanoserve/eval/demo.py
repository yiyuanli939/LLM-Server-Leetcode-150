"""Framework: ``python -m nanoserve eval`` — offline evaluation report and speculative decoding (M6).

    NANOSERVE_REFERENCE=1 python -m nanoserve eval            # harness report + stream integrity
    NANOSERVE_REFERENCE=1 python -m nanoserve eval --spec     # ... + speculative vs plain greedy

Exercises reached from here: eval.edit_distance, eval.rouge_l, decode.regex, eval.interleave_ok
(via nanoserve.eval.harness) and decode.beam_pairs (via nanoserve.decode.speculative).
"""
from __future__ import annotations

import argparse
import time

from nanoserve._exercise import reference_mode
from nanoserve.decode.speculative import SpeculativeDecoder
from nanoserve.engine import Engine, GenerationConfig
from nanoserve.eval.harness import DEFAULT_EXAMPLES, check_streams, corrupt_events, evaluate
from nanoserve.server.server import ServerConfig


def spec_comparison(engine: Engine, prompts: list[str], k_values: list[int], max_tokens: int) -> list[str]:
    cfg = GenerationConfig(temperature=0, max_tokens=max_tokens)
    t0 = time.perf_counter()
    plain = [engine.generate(p, cfg) for p in prompts]
    plain_s = time.perf_counter() - t0
    n_tok = sum(len(r.token_ids) for r in plain)
    lines = [f"speculative decoding: {len(prompts)} prompts, greedy, max_tokens={max_tokens}",
             f"{'decoder':<12} {'target passes':>13} {'tok/pass':>8} {'accept':>6} {'scored':>6}  identical",
             f"{'plain':<12} {n_tok:>13} {1.0:>8.2f} {'-':>6} {n_tok:>6}  (reference)  {plain_s * 1e3:.0f} ms"]
    for k in k_values:
        spec = SpeculativeDecoder(engine, k=k)
        t0 = time.perf_counter()
        res = [spec.generate(p, cfg) for p in prompts]
        dt = time.perf_counter() - t0
        passes = sum(r.stats["target_passes"] for r in res)
        accepted = sum(r.stats["draft_accepted"] for r in res)
        scored = sum(r.stats["scored_positions"] for r in res)
        same = all(a.token_ids == b.token_ids and a.text == b.text for a, b in zip(plain, res))
        lines.append(f"{f'tree k={k}':<12} {passes:>13} {n_tok / passes:>8.2f} {accepted / (2 * passes):>6.0%} "
                     f"{scored:>6}  {'yes' if same else 'NO'}  {dt * 1e3:.0f} ms")
    lines.append("tok/pass = tokens per sequential target pass; accept = drafted tokens accepted / drafted depth;")
    lines.append("scored = tree positions the target scored (a real engine batches them into one forward pass).")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve eval", description=__doc__.splitlines()[0])
    ap.add_argument("--spec", action="store_true", help="also compare speculative decoding with plain greedy")
    ap.add_argument("--k", type=int, action="append", default=None, help="draft-tree size (repeatable; default 1,4,8,16)")
    ap.add_argument("--max-batch", type=int, default=4)
    ap.add_argument("--spacing", type=int, default=1, help="ticks between example arrivals")
    ap.add_argument("--max-tokens", type=int, default=40, help="tokens per prompt in the --spec comparison")
    args = ap.parse_args(argv)
    if reference_mode():
        print("[reference mode]")

    engine = Engine()
    rep = evaluate(DEFAULT_EXAMPLES, ServerConfig(max_batch=args.max_batch), engine=engine, spacing=args.spacing)
    print(f"evaluated {len(rep.scores)} examples (greedy) through the server — {rep.server.summary()}")
    print(rep.table())

    sc = rep.stream
    print(f"\nstream integrity: {len(sc.pairs)} concurrent pairs + {len(sc.solos)} solo requests checked "
          f"against the multiplexed stream ({len(rep.server.events)} events): "
          f"{'all interleavings OK' if sc.ok else f'BROKEN {sc.bad}'}")
    for kind in ("swap", "drop", "dup"):
        events, rid = corrupt_events(rep.server.events, kind, seed=0)
        bad = check_streams(rep.server.requests, events)
        caught = [b for b in bad.bad if rid in b]
        print(f"  corrupted stream ({kind:<4} in {rid}): {'caught' if caught else 'MISSED'} "
              f"by {len(caught)} of the checks involving {rid}")

    if args.spec:
        print()
        prompts = [ex.prompt for ex in DEFAULT_EXAMPLES]
        for line in spec_comparison(engine, prompts, args.k or [1, 4, 8, 16], args.max_tokens):
            print(line)
    return 0 if sc.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
