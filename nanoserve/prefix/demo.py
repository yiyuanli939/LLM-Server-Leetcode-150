"""Framework: ``python -m nanoserve prefix`` — prefix cache and deadline index on the server (M4).

    NANOSERVE_REFERENCE=1 python -m nanoserve prefix
    NANOSERVE_REFERENCE=1 python -m nanoserve prefix --n 60 --seed 3 --pause 6

Three parts:
  1. a shared-prefix trace (``make_trace``: several prompts start with the same system prompt),
     served without and with the prefix cache: prefill ticks, TTFT, hit statistics;
  2. a crafted deadline trace (bulk jobs first, then a burst of tight-deadline chat requests),
     served with FCFS and with EDF: deadlines met. The EDF run is paused once to show the index
     (level dump, positions in line, deadline window, checkpoint round-trip);
  3. the index under a skewed (sorted) insertion order: depth stays bounded by rebuilds.

Exercises reached from here: prefix.trie, prefix.hit_sum, tok.common_prefix (nanoserve.prefix.cache); index.insert,
index.delete, index.kth, index.iter, index.validate, index.build, index.min_gap, index.range_sum,
prefix.depth, prefix.level_dump, prefix.fork_point (nanoserve.index.queue / bst_index);
index.restore, prefix.codec, prefix.same_snapshot (nanoserve.index.checkpoint).
"""
from __future__ import annotations

import argparse
import math
from statistics import mean

from nanoserve._exercise import reference_mode
from nanoserve.engine import Engine
from nanoserve.index.bst_index import depth_limit
from nanoserve.index.checkpoint import FORMATS, checkpoint_queue, restore_queue, verify
from nanoserve.index.queue import DeadlineQueue
from nanoserve.index.workloads import deadline_trace
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig, ServerReport
from nanoserve.server.trace import SYSTEM, make_trace


def prefill_ticks(report: ServerReport, engine: Engine, prefill_chunk: int) -> int:
    """Prefill ticks the run spent: per request, the uncached prompt tokens / prefill_chunk (rounded up)."""
    total = 0
    for r in report.finished:
        rest = r.prompt[r.cached_chars:]
        total += math.ceil(len(engine.tokenizer.encode(rest)) / prefill_chunk) if rest else 0
    return total


def run_prefix(n: int, seed: int, rate: float, max_batch: int, prefill_chunk: int, engine: Engine,
               cache: bool) -> ServerReport:
    cfg = ServerConfig(max_batch=max_batch, prefill_chunk=prefill_chunk, prefix_cache=cache)
    server = Server(engine, cfg, name="cache" if cache else "no-cache")
    server.submit_many(make_trace(n, seed=seed, rate=rate))
    return server.run()


def deadline_server(policy: str, seed: int, engine: Engine) -> Server:
    server = Server(engine, ServerConfig(max_batch=2, policy=policy), name=policy)
    server.submit_many(deadline_trace(seed=seed))
    return server


def _met(report: ServerReport, tenant: str | None = None) -> tuple[int, int]:
    dated = [r for r in report.finished if r.deadline is not None and (tenant is None or r.tenant == tenant)]
    return sum(bool(r.met_deadline) for r in dated), len(dated)


def show_index(q: DeadlineQueue, now: int, window: int) -> None:
    if not len(q):
        print(f"  paused at tick {now}: nothing is waiting (try a smaller --pause)")
        return
    print(f"  paused at tick {now}: {len(q)} waiting, index depth {q.index.height} "
          f"(limit {depth_limit(len(q)):.1f}), level dump (deadline#seq, '-' = no deadline):")
    for i, level in enumerate(q.levels()[:5]):
        print(f"    L{i}: " + " ".join(level))
    head = [f"{q.at(k).rid}@{q.at(k).deadline}" for k in range(1, min(len(q), 4) + 1)]
    print(f"  next in line: {', '.join(head)}")
    last = q.at(len(q))
    print(f"  {last.rid} (deadline {last.deadline}) is at position {q.position(last)} of {len(q)}")
    due = q.due_between(now, now + window)
    print(f"  due in [{now}, {now + window}]: {len(due)} requests, {q.tokens_due(now, now + window)} tokens; "
          f"tightest deadline gap {q.deadline_gap()}; invariants {'OK' if not q.check() else q.check()}")
    for fmt in FORMATS:
        ckpt = checkpoint_queue(q, fmt)
        back = restore_queue(ckpt, list(q))
        same_order = [r.rid for r in back] == [r.rid for r in q]
        print(f"  checkpoint {fmt:<8} {len(ckpt['index']):>4} chars  read-back {'exact' if verify(q.index.root, ckpt['index']) else 'MISMATCH'}"
              f"  restored queue order {'identical' if same_order else 'DIFFERENT'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve prefix", description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=40, help="requests in the shared-prefix trace")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--rate", type=float, default=0.5, help="arrivals per tick in the shared-prefix trace")
    ap.add_argument("--max-batch", type=int, default=4)
    ap.add_argument("--prefill-chunk", type=int, default=4, help="prompt tokens prefilled per tick")
    ap.add_argument("--pause", type=int, default=9, help="tick at which the EDF run is paused for a look")
    ap.add_argument("--skewed", type=int, default=64, help="requests pushed in deadline order in part 3")
    args = ap.parse_args(argv)
    if reference_mode():
        print("[reference mode]")
    engine = Engine()
    ok = True

    # 1. prefix cache ---------------------------------------------------------------------------
    print(f"1) prefix cache — {args.n} requests from make_trace(seed={args.seed}), max_batch={args.max_batch}, "
          f"prefill_chunk={args.prefill_chunk}")
    base = run_prefix(args.n, args.seed, args.rate, args.max_batch, args.prefill_chunk, engine, cache=False)
    cached = run_prefix(args.n, args.seed, args.rate, args.max_batch, args.prefill_chunk, engine, cache=True)
    print(f"  {'':<10}{'prefill ticks':>14}{'mean TTFT':>11}{'p50 lat':>9}{'ticks':>7}")
    for rep in (base, cached):
        print(f"  {rep.name:<10}{prefill_ticks(rep, engine, args.prefill_chunk):>14}"
              f"{mean(r.ttft for r in rep.finished):>11.1f}{rep.p50_latency:>9}{rep.ticks:>7}")
    st = cached.plugins["prefix_cache"]
    (shared, under), = st["under"].items()       # default watch: the shared prefix of the cached prompts
    print(f"  hits {st['hits']}/{st['lookups']} (misses {st['misses']}, {st['exact_repeats']} exact repeats), "
          f"tokens saved {st['tokens_saved']} ({st['token_hit_rate']:.0%} of prompt tokens), chars saved {st['chars_saved']}")
    print(f"  shared prefix of the cached prompts: {shared!r}")
    print(f"  hits reusing all of it: {under['hits']} ({under['tokens_saved']} tokens); "
          f"it is the system prompt: {shared == SYSTEM.rstrip()}")
    same = base.outputs() == cached.outputs()
    ok &= same
    print(f"  outputs identical with and without cache: {same}")

    # 2. deadline index -------------------------------------------------------------------------
    trace = deadline_trace(seed=args.seed)
    print(f"\n2) EDF vs FCFS — crafted trace: {sum(r.tenant == 'batch' for r in trace)} bulk/background jobs at "
          f"tick 0, then {sum(r.tenant == 'chat' for r in trace)} chat requests with tight deadlines; max_batch=2")
    fcfs = deadline_server("fcfs", args.seed, engine).run()
    server = deadline_server("edf", args.seed, engine)
    server.run(max_ticks=args.pause)               # pause mid-run to look inside the index ...
    show_index(server.queue, server.now, 100)
    edf = server.run()                              # ... then finish the run
    print(f"  {'':<6}{'deadlines met':>14}{'chat met':>10}{'chat p50 lat':>14}{'bulk max lat':>14}")
    for rep in (fcfs, edf):
        m, d = _met(rep)
        cm, cd = _met(rep, "chat")
        chat = sorted(r.latency for r in rep.finished if r.tenant == "chat")
        bulk = [r.latency for r in rep.finished if r.tenant == "batch"]
        print(f"  {rep.name:<6}{f'{m}/{d}':>14}{f'{cm}/{cd}':>10}{chat[len(chat) // 2]:>14}{max(bulk):>14}")
    q = edf.plugins["queue"]
    print(f"  edf queue: {q['overtakes']} overtakes (max {q['max_overtake']}), peak {q['peak_len']} waiting, "
          f"peak urgent {q['peak_urgent']} req / {q['peak_urgent_tokens']} tokens, healthy={q['healthy']}")
    same = fcfs.outputs() == edf.outputs()
    ok &= same and q["healthy"]
    print(f"  outputs identical under both policies: {same}")

    # 3. skewed insertion -----------------------------------------------------------------------
    print(f"\n3) index balance — {args.skewed} requests pushed in increasing deadline order")
    sq = DeadlineQueue()
    for i in range(args.skewed):
        sq.push(Request(rid=f"s{i}", prompt="The", arrival=i, deadline=10 * i + 5))
    print(f"  depth {sq.index.height} (limit 2·log2(n)+2 = {depth_limit(len(sq)):.1f}, a chain would be {args.skewed}), "
          f"{sq.index.rebuilds} balanced rebuilds, max depth ever reached {sq.index.deepest}")
    print(f"  level widths: {[len(level) for level in sq.levels()]}; invariants {'OK' if not sq.check() else sq.check()}")
    ok &= not sq.check()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
