"""Framework: turns logits into a token id.

Uses two of your exercises:
  * ``kth_largest`` (sample.kth_largest) to find the top-k cut-off,
  * ``cdf_index``   (sample.cdf_index)   to draw from the cumulative distribution.
"""
from __future__ import annotations

import math
import random
from typing import Iterable

import numpy as np

from nanoserve.sampling.search import cdf_index
from nanoserve.sampling.topk import kth_largest


def sample(logits: np.ndarray, *, temperature: float, top_k: int, rng: random.Random, banned: Iterable[int] = ()) -> int:
    x = np.asarray(logits, dtype=float).copy()
    for b in banned:
        x[b] = -math.inf
    finite = np.isfinite(x)
    if not finite.any():
        raise ValueError("every token is banned")
    if temperature <= 0:
        return int(np.argmax(x))
    x = x / temperature
    if 0 < top_k < int(finite.sum()):
        thr = kth_largest(x[finite].tolist(), top_k)
        x[x < thr] = -math.inf
    p = np.exp(x - np.max(x))
    cand = np.nonzero(p > 0)[0]
    # strictly increasing CDF over candidates only (cdf_index assumes distinct sorted values)
    cdf = np.cumsum(p[cand]).tolist()
    r = rng.random() * cdf[-1]
    i = cdf_index(cdf, r)
    return int(cand[min(i, len(cand) - 1)])
