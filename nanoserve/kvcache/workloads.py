"""Framework (M3): workloads that drive a ``BlockManager`` directly, for the demo and the tests.

  * ``replay(mgr, prompts)``    admit and release prompts one after another (prompts are token-id lists).
    With a GPU pool that only holds one prompt, every admission evicts the previous prompt's blocks
    to the host tier, so the run measures the host tier's eviction policy alone:
      - ``hot_vs_scan()``       a hot prompt between growing runs of one-off prompts (LFU keeps it,
                                LRU forgets it once a run is longer than the host tier)
      - ``shifting_hot_set()``  a prompt that is hot early and then never again, followed by a new hot
                                set (LFU stays polluted by the old favourite, LRU adapts)
  * ``parallel_sample(...)``    n samples of one prompt (``n > 1`` sampling): the prompt is stored once,
    the other samples ``fork`` its block table and share every block until they write into a shared
    one (copy-on-write). Outputs equal independent ``Engine.generate`` calls with the same seeds.
  * ``speculative_generate(...)`` greedy decoding with drafts. A cheap bigram model drafts ``k``
    tokens. Their KV is stored speculatively after a ``checkpoint``, then the target model verifies
    them. Rejected drafts are undone with ``rollback``, which must restore the exact block table.
    The text equals plain greedy decoding.

Exercises: none directly; everything goes through ``BlockManager`` (all of M3) and ``Engine`` (M1).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from nanoserve.engine import Engine, GenerationConfig
from nanoserve.kvcache.manager import BlockManager
from nanoserve.model.toy import NGramModel

# ====================================================================================== reuse traces
BLOCK = 4   # block size the traces are written for: every prompt is exactly two full blocks


def _prompt(i: int) -> list[int]:
    return list(range(1000 + 8 * i, 1008 + 8 * i))


def hot_vs_scan(runs: int = 6) -> list[list[int]]:
    """H, s, H, s s, H, s s s, ... : the hot prompt H between ever longer runs of one-off prompts."""
    hot, out, k = _prompt(0), [], 1
    for r in range(1, runs + 1):
        out.append(hot)
        for _ in range(r):
            out.append(_prompt(k))
            k += 1
    out.append(hot)
    return out


def shifting_hot_set(early: int = 6, late: int = 8) -> list[list[int]]:
    """Old favourite O used ``early`` times, then a new hot pair A, B alternating ``late`` times."""
    old, a, b = _prompt(0), _prompt(1), _prompt(2)
    out = []
    for i in range(early):
        out += [old, _prompt(100 + i)]
    for _ in range(late):
        out += [a, b]
    return out


def replay(mgr: BlockManager, prompts: list[list[int]]) -> dict:
    """Admit and release each prompt in turn, one tick each. Returns the manager's report."""
    for t, tokens in enumerate(prompts):
        rid = f"q{t}"
        if not mgr.fits(tokens):
            raise RuntimeError(f"prompt {t} does not fit into an empty pool")
        mgr.admit(rid, tokens, now=t)
        mgr.release(rid, now=t)
    return mgr.report()


def policy_table(prompts: list[list[int]], *, host_blocks: int = 4, policies=("lru", "lfu", "random"),
                 seed: int = 0) -> dict[str, dict]:
    """Replay the same trace with each host-tier policy (GPU pool: one prompt + one free block)."""
    out = {}
    for p in policies:
        mgr = BlockManager(num_blocks=3, block_size=BLOCK, eviction=p, host_blocks=host_blocks, seed=seed)
        rep = replay(mgr, prompts)
        out[p] = {k: rep[k] for k in ("restored", "computed", "offloaded", "revived", "prompt_block_hit_rate")}
    return out


# ====================================================================================== parallel sampling
@dataclass
class SampleResult:
    texts: list[str]
    token_ids: list[list[int]]
    shared_at_fork: dict[int, int]    # block -> references right after the forks
    stats: dict                       # manager report after every sample finished
    peak_in_use: int                  # blocks in use at the peak (vs. n independent copies)


def parallel_sample(engine: Engine, mgr: BlockManager, prompt: str, n: int, cfg: GenerationConfig,
                    rid: str = "s") -> SampleResult:
    """``n`` samples of ``prompt`` with seeds cfg.seed, cfg.seed+1, ...; blocks shared via fork."""
    states = [engine.start(prompt, GenerationConfig(**{**cfg.__dict__, "seed": cfg.seed + i})) for i in range(n)]
    rids = [rid if i == 0 else f"{rid}/{i}" for i in range(n)]
    mgr.admit(rids[0], states[0].prompt_ids)
    for r in rids[1:]:
        if not mgr.fork(rids[0], r):
            raise RuntimeError("no room to fork")
    shared = {b: mgr.refs[b] for b in mgr.block_table(rids[0])}
    t = 0
    while any(not st.done for st in states):
        t += 1
        for r, st in zip(rids, states):
            if st.done:
                continue
            engine.step(st)
            if not mgr.store(r, st.context, now=t):
                raise RuntimeError("out of KV blocks while sampling")
            if st.done:
                mgr.release(r, now=t)
    return SampleResult([st.text for st in states], [list(st.out) for st in states], shared,
                        mgr.report(), mgr.peak_in_use)


# ====================================================================================== speculative decoding
@dataclass
class SpecResult:
    token_ids: list[int]
    text: str
    rounds: int = 0
    drafted: int = 0
    accepted: int = 0
    rollbacks: int = 0
    exact_restores: int = 0           # rollbacks after which the block table equalled the checkpoint's
    tables: list[tuple[list[int], list[int]]] = field(default_factory=list)  # (at checkpoint, after rollback)


def speculative_generate(engine: Engine, mgr: BlockManager, prompt: str, max_tokens: int, *, k: int = 4,
                         rid: str = "spec", draft: NGramModel | None = None) -> SpecResult:
    """Greedy decoding with a bigram draft model; the KV of drafts is rolled back when rejected."""
    target = engine.model
    draft = draft or NGramModel(engine.tokenizer, order=2, lambdas=(0.9, 0.1))
    ctx = list(engine.tokenizer.encode(prompt))
    n_prompt = len(ctx)
    mgr.admit(rid, ctx)
    res = SpecResult([], "")
    while len(ctx) - n_prompt < max_tokens:
        res.rounds += 1
        guess: list[int] = []
        for _ in range(min(k, max_tokens - (len(ctx) - n_prompt))):
            guess.append(int(np.argmax(draft.logits(ctx + guess))))
        snap = mgr.checkpoint(rid)
        before = mgr.block_table(rid)
        if not mgr.store(rid, ctx + guess):          # drafts' KV, written speculatively
            raise RuntimeError("out of KV blocks while drafting")
        keep: list[int] = []
        for i, g in enumerate(guess):                 # verify (a real engine: one batched forward pass)
            t = int(np.argmax(target.logits(ctx + guess[:i])))
            keep.append(t)
            if t != g:
                break
        res.drafted += len(guess)
        res.accepted += sum(1 for a, b in zip(keep, guess) if a == b)
        if keep != guess:                              # something was rejected: undo the drafts' KV
            mgr.rollback(rid, snap)
            after = mgr.block_table(rid)
            res.rollbacks += 1
            res.exact_restores += after == before
            res.tables.append((before, after))
            ctx += keep
            if not mgr.store(rid, ctx):
                raise RuntimeError("out of KV blocks while committing")
        else:
            mgr.commit(rid, snap)
            ctx += keep
    res.token_ids = ctx[n_prompt:n_prompt + max_tokens]
    res.text = engine.tokenizer.decode(res.token_ids)
    mgr.release(rid)
    return res
