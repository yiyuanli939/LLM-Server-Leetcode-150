"""Framework: ``python -m nanoserve kv``, the paged KV-cache manager under memory pressure (M3).

    NANOSERVE_REFERENCE=1 python -m nanoserve kv                       # all sections
    NANOSERVE_REFERENCE=1 python -m nanoserve kv --blocks 16 --eviction lfu --only server

Sections:
  server     the same trace with and without a KV budget: preemptions happen, outputs don't change;
             the block manager's report (sharing, host tier, free ranges, event log)
  policies   host-tier eviction policies (LRU / LFU / random) on two crafted reuse traces
  fork       parallel sampling (n > 1): forked block tables share blocks, copy-on-write on divergence
  spec       speculative decoding: drafts' KV rolled back to a checkpoint when the target rejects them
  sanitizer  injected double free, freed-while-in-use block, leaks and a corrupt table are all caught

Exercises reached from here: every M3 exercise, through nanoserve.kvcache.manager.BlockManager.
"""
from __future__ import annotations

import argparse

from nanoserve._exercise import reference_mode
from nanoserve.engine import Engine, GenerationConfig
from nanoserve.kvcache.manager import BlockManager
from nanoserve.kvcache.workloads import hot_vs_scan, parallel_sample, policy_table, shifting_hot_set, speculative_generate
from nanoserve.server.server import Server, ServerConfig
from nanoserve.server.trace import make_trace

SECTIONS = ("server", "policies", "fork", "spec", "sanitizer")


def server_section(engine: Engine, args) -> bool:
    trace = lambda: make_trace(args.requests, seed=args.seed, rate=args.rate)
    base = Server(engine, ServerConfig(max_batch=args.max_batch), name="no-kv-limit")
    base.submit_many(trace())
    rb = base.run()
    cfg = ServerConfig(max_batch=args.max_batch, kv_blocks=args.blocks, block_size=args.block_size,
                       eviction=args.eviction)
    srv = Server(engine, cfg, name=f"kv{args.blocks}x{args.block_size}")
    srv.submit_many(trace())
    r = srv.run()
    k = r.plugins["kv"]
    same = r.outputs() == rb.outputs() and len(r.finished) == len(rb.finished)
    pre = sum(q.preemptions for q in r.requests)
    print(rb.summary())
    print(r.summary())
    print(f"  preemptions {pre}; every output identical to the unlimited run: {'yes' if same else 'NO'}")
    print(f"  pool: {k['num_blocks']} blocks x {k['block_size']} tokens, peak in use {k['peak_in_use']}; "
          f"now {k['in_use']} in use, {k['cached']} cached, {k['free']} free, quarantined {k['quarantined']}")
    print(f"  prompt blocks: {k['shared']} shared with a running request, {k['revived']} revived from GPU cache, "
          f"{k['restored']} restored from host, {k['computed']} computed  (hit rate {k['prompt_block_hit_rate']})")
    print(f"  decode blocks {k['decode_blocks']}, copy-on-write {k['cow']}; offloaded {k['offloaded']} blocks to "
          f"host ({args.eviction}) in {k['transfers']} coalesced transfers")
    print(f"  free ranges {k['free_ranges']}  largest free run {k['largest_free_run']}; "
          f"free-list merges {k['pool_merges']} single + {k['pool_k_way_merges']} k-way")
    a = k["arena"]
    print(f"  token arena: {a['used']}/{a['size']} cells in use (peak {a['peak']}), "
          f"{a['failed_reservations']} failed reservations")
    print(f"  event log: {k['events']} events, oldest kept #{k['oldest_event']}; last ones:")
    for ts, tick, kind, block, rid in k["recent_events"][-5:]:
        print(f"    #{ts:<5} tick {tick:<4} {kind:<10} block {block:<4} {rid}")
    mgr = srv.kv
    t = r.ticks // 2
    held = [b for b in range(mgr.num_blocks) if mgr.owner_at(b, t)]
    print(f"  at tick {t}, {len(held)} blocks were charged to a request, e.g. "
          + ", ".join(f"{b}->{mgr.owner_at(b, t)}" for b in held[:4]))
    print(f"  invariants: {'OK' if not k['problems'] and not k['leaks'] else k['problems'] + k['leaks']}")
    return same and not k["problems"] and not k["leaks"]


def policies_section(args) -> bool:
    print("host-tier eviction (GPU pool holds one prompt, so every reuse is a host hit or a recompute):")
    print(f"  {'trace':<18} {'host':>4}  " + "  ".join(f"{p:>14}" for p in ("lru", "lfu", "random")))
    rows = [("hot vs scan", hot_vs_scan(), 4), ("shifting hot set", shifting_hot_set(), 4)]
    ok = True
    for name, trace, host in rows:
        tab = policy_table(trace, host_blocks=host, seed=args.seed)
        cells = [f"{tab[p]['restored']:>3} restored/{tab[p]['computed']:<3}" for p in ("lru", "lfu", "random")]
        print(f"  {name:<18} {host:>4}  " + "  ".join(f"{c:>14}" for c in cells))
        ok &= len({tab[p]["restored"] for p in tab}) > 1
    print("  (LFU keeps the long-term favourite through scans; LRU adapts when the hot set moves)")
    return ok


def fork_section(engine: Engine, args) -> bool:
    prompt, n = "The cache is made of blocks.", 4
    cfg = GenerationConfig(max_tokens=24, seed=args.seed)
    mgr = BlockManager(64, args.block_size)
    res = parallel_sample(engine, mgr, prompt, n, cfg)
    alone = [engine.generate(prompt, GenerationConfig(max_tokens=24, seed=args.seed + i)).text for i in range(n)]
    st = res.stats
    alone_blocks = sum(-(-(len(engine.tokenizer.encode(prompt)) + len(ids)) // args.block_size)
                       for ids in res.token_ids)
    print(f"parallel sampling n={n} of {prompt!r}: prompt blocks {sorted(res.shared_at_fork)} each referenced "
          f"{sorted(set(res.shared_at_fork.values()))} times after {st['forks']} forks")
    print(f"  copy-on-write {st['cow']}x; peak {res.peak_in_use} blocks in use vs {alone_blocks} for {n} "
          f"unshared copies; after all finished: {st['in_use']} in use, {st['cached']} cached")
    same = res.texts == alone
    print(f"  samples identical to independent generate() calls: {'yes' if same else 'NO'}")
    return same and st["in_use"] == 0 and not st["problems"]


def spec_section(engine: Engine, args) -> bool:
    mgr = BlockManager(64, args.block_size)
    res = speculative_generate(engine, mgr, "The scheduler", 48, k=4)
    plain = engine.generate("The scheduler", GenerationConfig(max_tokens=48, temperature=0))
    same = res.token_ids == plain.token_ids
    rep = mgr.report()
    print(f"speculative decoding (bigram drafts, k=4): {res.rounds} rounds, {res.accepted}/{res.drafted} drafted "
          f"tokens accepted")
    print(f"  {res.rollbacks} rollbacks, block table restored exactly every time: "
          f"{'yes' if res.exact_restores == res.rollbacks else 'NO'}; copy-on-write {rep['cow']}x")
    print(f"  text identical to plain greedy decoding: {'yes' if same else 'NO'}; "
          f"blocks in use afterwards: {rep['in_use']}")
    return same and res.exact_restores == res.rollbacks and rep["in_use"] == 0


def sanitizer_section(engine: Engine, args) -> bool:
    bs = args.block_size
    mgr = BlockManager(16, bs)
    ids = engine.tokenizer.encode("The engine keeps the keys and values of every token in a cache. ")
    mgr.admit("a", ids)
    mgr.admit("b", ids[: 2 * bs + 1])
    mgr.release("b")
    victim = mgr.block_table("a")[-1]
    free_one = mgr.pool.contents()[0][0]
    print("sanitizer: injecting faults into a manager with one running request")
    mgr.pool.stage([free_one])                        # a block freed twice
    q = mgr.sanitize()
    print(f"  double free of block {free_one}: quarantined {q}")
    mgr.pool.stage([victim])                          # a block freed while still in use
    print(f"  block {victim} freed while 'a' still uses it: check() says "
          f"{[p for p in mgr.check() if str(victim) in p][:1]}")
    mgr.sanitize()
    leaked = [mgr._take_block() for _ in range(3)]    # blocks taken but recorded nowhere
    found = mgr.audit_leaks()
    print(f"  leaked blocks {leaked}: audit finds {found}")
    d = mgr.describe(found[0]) if found else {}
    print(f"    e.g. {d}")
    good = mgr.seqs["a"]
    good.tail.next = good.head                         # corrupt the block table
    cyc = [p for p in mgr.check() if "cycle" in p]
    good.tail.next = None
    print(f"  corrupt block table: {cyc}")
    return bool(q) and sorted(found) == sorted(leaked) and bool(cyc)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve kv", description=__doc__.splitlines()[0])
    ap.add_argument("--blocks", type=int, default=18, help="KV blocks for the server section")
    ap.add_argument("--block-size", type=int, default=8)
    ap.add_argument("--eviction", choices=("lru", "lfu", "random"), default="lru")
    ap.add_argument("--requests", type=int, default=20)
    ap.add_argument("--rate", type=float, default=1.0)
    ap.add_argument("--max-batch", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--only", choices=SECTIONS, action="append", help="run only these sections (repeatable)")
    args = ap.parse_args(argv)
    if reference_mode():
        print("[reference mode]")
    engine = Engine()
    run = args.only or list(SECTIONS)
    ok = True
    for name in run:
        print(f"\n== {name} " + "=" * (60 - len(name)))
        if name == "server":
            ok &= server_section(engine, args)
        elif name == "policies":
            ok &= policies_section(args)
        elif name == "fork":
            ok &= fork_section(engine, args)
        elif name == "spec":
            ok &= spec_section(engine, args)
        else:
            ok &= sanitizer_section(engine, args)
    print("\nall checks passed" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
