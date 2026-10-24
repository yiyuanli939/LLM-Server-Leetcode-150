"""Framework: Medusa-style speculative decoding with a two-token draft tree (M6).

Plain greedy decoding runs the target model once per generated token. Here two cheap *draft heads*
guess the next two tokens; the ``k`` most likely 2-token guesses form a small tree, and the target
model scores every node of that tree in ONE verification pass (a real engine does this with tree
attention; our n-gram model simply scores each node's context). We then accept the longest guessed
prefix that agrees with the target's own greedy choices, plus the one *bonus* token the target
produced at the deepest accepted node. Every committed token is the target's argmax at its
position, so the text is **identical** to ``Engine.generate(..., temperature=0)`` — only the number
of sequential target passes shrinks::

    spec = SpeculativeDecoder(engine, k=8)
    res = spec.generate("The scheduler", GenerationConfig(temperature=0, max_tokens=40, stop=(".",)))
    res.stats["target_passes"] < res.stats["completion_tokens"]

Draft heads (``DraftHeads``): both look only at the last committed token, like Medusa heads reading
the last hidden state. Head 1 is a bigram table P(x[t+1] | x[t]), head 2 a skip-gram table
P(x[t+2] | x[t]); both are counted from the corpus token stream. Their costs (-log p) are independent,
so the best k guesses by summed cost come straight out of ``k_best_pairs`` over the two ascending
cost lists — without scoring all V*V pairs.

Committing goes through ``Engine.step`` of an engine whose model is a ``VerifiedLogits`` view of the
target: it serves the logits that the verification pass already computed. Stop strings, max_tokens,
word streaming and finish reasons are therefore handled by exactly the same code as plain decoding,
and ``VerifiedLogits.misses`` proves no token was committed without being verified.

Exercises this file calls (M6): decode.beam_pairs.
(Through ``Engine.step`` it also runs the M1 sampling/streaming exercises.)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator

import numpy as np

from nanoserve.decode.beam import k_best_pairs
from nanoserve.engine import Engine, GenerationConfig, GenerationResult
from nanoserve.model.corpus import CORPUS

COST_SCALE = 1000  # costs are integers: -log p in units of 1/1000 nat
DRAFT_DEPTH = 2    # the draft tree guesses two tokens ahead


class DraftHeads:
    """Two cheap next-token predictors that only look at the last committed token.

    ``cost[h][row, tok]`` is the integer cost (-log p, quantised) that head ``h`` (0: next token,
    1: the token after it) assigns to ``tok`` given last token ``row``; row ``V`` is used when there is
    no context yet (empty prompt) and holds the unigram distribution.
    """

    def __init__(self, tokenizer, corpus: str = CORPUS, alpha: float = 0.05):
        V = len(tokenizer)
        ids = tokenizer.encode(corpus)
        unigram = np.bincount(ids, minlength=V).astype(float)
        tables = []
        for gap in (1, 2):  # bigram head, skip-gram head
            counts = np.full((V + 1, V), alpha)  # add-alpha smoothing: every token has a finite cost
            for a, b in zip(ids, ids[gap:]):
                counts[a, b] += 1
            counts[V] += unigram
            p = counts / counts.sum(axis=1, keepdims=True)
            tables.append(np.rint(-np.log(p) * COST_SCALE).astype(np.int64))
        self.V = V
        self.cost = tables

    def ranked(self, head: int, last: int | None, m: int) -> list[int]:
        """The ``m`` cheapest tokens of a head, ascending by (cost, token id)."""
        row = self.cost[head][self.V if last is None else last]
        order = np.lexsort((np.arange(self.V), row))  # primary key: cost; ties: token id
        return [int(t) for t in order[:m]]


class VerifiedLogits:
    """The target model as seen by the committing engine.

    ``score`` is the verification pass: it runs the real model on one tree node's context and keeps the
    logits. ``logits`` (called by ``Engine.step``) serves those stored logits; a context that was never
    scored counts as a ``miss`` and falls back to the real model (never happens when the verifier is
    correct — the tests check ``misses == 0``).
    """

    def __init__(self, model):
        self.model = model
        self._scored: dict[tuple[int, ...], np.ndarray] = {}
        self.scored_positions = 0
        self.misses = 0

    def new_pass(self) -> None:
        self._scored.clear()

    def score(self, context: list[int]) -> np.ndarray:
        key = tuple(context)
        if key not in self._scored:
            self._scored[key] = self.model.logits(context)
            self.scored_positions += 1
        return self._scored[key]

    def logits(self, context: list[int]) -> np.ndarray:
        key = tuple(context)
        if key not in self._scored:
            self.misses += 1
            self._scored[key] = self.model.logits(context)
        return self._scored[key]


@dataclass
class DraftTree:
    """The k best 2-token guesses, plus every prefix of them (the tree's nodes below the root)."""

    pairs: list[tuple[int, int]]

    @property
    def nodes(self) -> list[tuple[int, ...]]:
        firsts = sorted({(a,) for a, _ in self.pairs})
        return [()] + firsts + sorted(set(self.pairs))

    def has(self, prefix: tuple[int, ...]) -> bool:
        if len(prefix) == 1:
            return any(a == prefix[0] for a, _ in self.pairs)
        return prefix in self.pairs


class SpeculativeDecoder:
    """Greedy decoding with a k-candidate, depth-2 draft tree verified by the target model."""

    def __init__(self, engine: Engine | None = None, k: int = 8, heads: DraftHeads | None = None):
        if k < 1:
            raise ValueError("k must be >= 1")
        self.target = engine or Engine()
        self.k = k
        self.heads = heads or DraftHeads(self.target.tokenizer)
        self.last_result: GenerationResult | None = None

    # ------------------------------------------------------------------ drafting
    def draft(self, context: list[int]) -> DraftTree:
        """Build the draft tree: the k 2-token guesses with the smallest summed head cost."""
        last = context[-1] if context else None
        m = min(self.k, self.heads.V)       # the k best pairs never use more than k entries per list
        firsts = self.heads.ranked(0, last, m)
        seconds = self.heads.ranked(1, last, m)
        row = self.heads.V if last is None else last
        # k_best_pairs returns cost VALUES, so each list needs distinct values to map back to tokens.
        # Encode value = cost * W + rank with W = 2m: ranks stay below W even when two are summed, so
        # ordering pairs by summed value == ordering by (summed cost, summed rank). Lists stay ascending.
        W = 2 * m
        a = [int(self.heads.cost[0][row, t]) * W + r for r, t in enumerate(firsts)]
        b = [int(self.heads.cost[1][row, t]) * W + r for r, t in enumerate(seconds)]
        tok_a, tok_b = dict(zip(a, firsts)), dict(zip(b, seconds))
        k = min(self.k, len(a) * len(b))   # precondition: 1 <= k <= len(a) * len(b)
        return DraftTree([(tok_a[x], tok_b[y]) for x, y in k_best_pairs(a, b, k)])

    # ------------------------------------------------------------------ verification
    def verify(self, view: VerifiedLogits, context: list[int], tree: DraftTree) -> tuple[list[int], int]:
        """One target pass over the tree. Returns (tokens to commit, how many of them were drafted).

        The target's greedy token at the root is always committed; while it matches a tree node we
        descend and the target's greedy token at that node is committed too (the bonus at the leaf).
        """
        view.new_pass()
        for node in tree.nodes:  # the whole tree is scored in one (batched) pass
            view.score(context + list(node))
        accepted: list[int] = []
        while True:
            greedy = int(np.argmax(view.logits(context + accepted)))
            if len(accepted) < DRAFT_DEPTH and tree.has(tuple(accepted + [greedy])):
                accepted.append(greedy)
                continue
            return accepted + [greedy], len(accepted)

    # ------------------------------------------------------------------ public API
    def stream(self, prompt: str, cfg: GenerationConfig | None = None) -> Iterator[str]:
        cfg = cfg or GenerationConfig(temperature=0)
        if cfg.temperature != 0 or cfg.no_repeat_window:
            raise ValueError("speculative decoding here is greedy only: temperature=0, no_repeat_window=0")
        t0 = time.perf_counter()
        view = VerifiedLogits(self.target.model)
        committer = Engine(self.target.tokenizer, view)  # same step loop as plain decoding
        st = committer.start(prompt, cfg)
        passes = drafted_accepted = 0
        while not st.done:
            commit, n_drafted = self.verify(view, st.context, self.draft(st.context))
            passes += 1
            for i, tok in enumerate(commit):
                chunk = committer.step(st)
                if st.out[-1] != tok:  # Engine.step re-derived the token from the verified logits
                    raise RuntimeError("speculative commit diverged from the verified token")
                if i < n_drafted:
                    drafted_accepted += 1
                if chunk:
                    yield chunk
                if st.done:
                    break
        res = committer.result(st, time.perf_counter() - t0)
        n = len(st.out)
        res.stats.update({
            "target_passes": passes,
            "tokens_per_pass": round(n / passes, 2) if passes else 0.0,
            "draft_accepted": drafted_accepted,
            "acceptance_rate": round(drafted_accepted / (DRAFT_DEPTH * passes), 3) if passes else 0.0,
            "scored_positions": view.scored_positions,
            "unverified_commits": view.misses,
            "k": self.k,
        })
        self.last_result = res

    def generate(self, prompt: str, cfg: GenerationConfig | None = None) -> GenerationResult:
        for _ in self.stream(prompt, cfg):
            pass
        assert self.last_result is not None
        return self.last_result
