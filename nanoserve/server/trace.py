"""Framework: deterministic synthetic request traces for demos and integration tests."""
from __future__ import annotations

import random

from nanoserve.server.request import Request

# Prompts made from corpus phrases (so every character is in the vocabulary). Several share long
# prefixes on purpose — that's what the prefix cache (M4) feeds on.
SYSTEM = "The engine keeps the keys and values of every token in a cache. "
PROMPTS = [
    "The scheduler",
    "The model reads the prompt and",
    "The cache is made of blocks.",
    "When two requests share the same prefix, the engine",
    "The sampler turns the scores of the model into",
    "The metrics panel shows the queue,",
    "The compiler turns the model into",
    "A small engine is a good teacher.",
    SYSTEM + "The scheduler",
    SYSTEM + "When memory is low,",
    SYSTEM + "A new request walks down the tree",
    SYSTEM + "The prefix cache is a tree.",
]


def make_trace(n: int = 20, *, seed: int = 0, rate: float = 1.0, tenants: tuple[str, ...] = ("a", "b", "c"),
               tenant_weights: tuple[float, ...] | None = None, max_tokens: tuple[int, int] = (8, 24),
               deadline_slack: tuple[int, int] | None = None, sessions: int | None = None,
               stop: tuple[str, ...] = (), start: int = 0, models: tuple[str, ...] = ("toy",)) -> list[Request]:
    """``n`` requests with roughly ``rate`` arrivals per tick.

    deadline_slack=(lo, hi): deadline = arrival + max_tokens + uniform(lo, hi).
    sessions=k: requests carry one of k session ids.
    """
    rng = random.Random(seed)
    t = float(start)
    out = []
    for i in range(n):
        t += rng.expovariate(rate) if rate > 0 else 0
        arrival = int(t)
        mt = rng.randint(*max_tokens)
        tenant = rng.choices(tenants, weights=tenant_weights)[0]
        dl = None
        if deadline_slack is not None:
            dl = arrival + mt + rng.randint(*deadline_slack)
        out.append(Request(
            rid=f"r{i:03d}", prompt=rng.choice(PROMPTS), arrival=arrival, max_tokens=mt, tenant=tenant,
            deadline=dl, stop=stop, seed=seed * 1000 + i,
            session=f"s{rng.randrange(sessions)}" if sessions else None,
            model=rng.choice(models),
        ))
    return out
