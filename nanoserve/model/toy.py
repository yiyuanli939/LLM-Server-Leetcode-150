"""Framework: a tiny token-level n-gram language model in numpy.

It stands in for a transformer: ``logits(context_ids) -> np.ndarray[vocab]``. Everything the
engine does around it (sampling, streaming, batching, KV cache, prefix cache) is the same as
for a real model; only the numbers are dumber.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from nanoserve.model.corpus import CORPUS


class NGramModel:
    def __init__(self, tokenizer, corpus: str = CORPUS, order: int = 5, lambdas=(0.5, 0.25, 0.15, 0.06, 0.03), floor: float = 0.01):
        self.V = len(tokenizer)
        self.order = order
        self.lambdas = lambdas
        self.floor = floor
        ids = tokenizer.encode(corpus)
        self.counts: list[dict[tuple, np.ndarray]] = []
        for n in range(1, order + 1):
            table: dict[tuple, np.ndarray] = defaultdict(lambda: np.zeros(self.V))
            for i in range(n - 1, len(ids)):
                ctx = tuple(ids[i - n + 1 : i])
                table[ctx][ids[i]] += 1
            self.counts.append(dict(table))

    def _dist(self, ctx: tuple) -> np.ndarray | None:
        row = self.counts[len(ctx)].get(ctx)
        if row is None or row.sum() == 0:
            return None
        return row / row.sum()

    def logits(self, context: list[int]) -> np.ndarray:
        p = np.full(self.V, self.floor / self.V)
        weights = list(self.lambdas)  # trigram, bigram, unigram
        for k, lam in zip(range(self.order - 1, -1, -1), weights):
            ctx = tuple(context[-k:]) if k else ()
            if k and len(context) < k:
                continue
            d = self._dist(ctx)
            if d is not None:
                p += lam * d
        return np.log(p)
