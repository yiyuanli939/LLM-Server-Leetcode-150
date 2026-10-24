"""Framework: the workers × models health matrix and health-aware routing (M7).

    health = HealthMatrix(workers=3, models=["toy-chat", "toy-code", "toy-base"])
    health.fail(1, "toy-code")              # fault injection: replica of toy-code on worker 1 is broken
    masked = health.masked()                # row 1 (drain worker 1) and column toy-code (pause it) -> 0
    plan = health.route(trace)              # rid -> healthy worker, None for paused models
    rep = PlannedCluster(3, plan, ...).run()

Cell (w, m) holds the health of model m's replica on worker w: a positive number (its routing weight /
capacity share) or 0 when it failed. A failure is contained by its blast radius: we don't trust the rest of
worker w (shared GPU, driver, host) nor model m anywhere (a bad checkpoint / config rollout), so the whole
row and column are masked — in place, from the snapshot of failures (dash.mask_failed). Only failures
present in the snapshot count; the masking itself must not cascade.

Routing then only uses unmasked cells: a request for model m goes to a worker whose (w, m) cell is still
positive, spreading requests round-robin over those workers in proportion to the cell weights. A model
whose column is masked is paused: its requests are rejected at the front end.

Exercises this file calls (M7): dash.mask_failed.
"""
from __future__ import annotations

import copy
from typing import Sequence

from nanoserve.dashboard.health import mask_failures
from nanoserve.server.request import Request


class HealthMatrix:
    def __init__(self, workers: int, models: Sequence[str], weights: Sequence[Sequence[int]] | None = None):
        if workers < 1 or not models:
            raise ValueError("need at least one worker and one model")
        self.models = list(models)
        self.grid = [list(row) for row in weights] if weights is not None else \
            [[1] * len(self.models) for _ in range(workers)]
        if len(self.grid) != workers or any(len(row) != len(self.models) for row in self.grid):
            raise ValueError("weights must be a workers x models matrix")

    @property
    def workers(self) -> int:
        return len(self.grid)

    def fail(self, worker: int, model: str) -> None:
        self.grid[worker][self.models.index(model)] = 0

    def masked(self) -> list[list[int]]:
        """Copy of the matrix with every failure's row and column masked (the live grid is untouched)."""
        m = copy.deepcopy(self.grid)
        mask_failures(m)
        return m

    def drained_workers(self) -> list[int]:
        m = self.masked()
        return [w for w, row in enumerate(m) if all(v == 0 for v in row)]

    def paused_models(self) -> list[str]:
        m = self.masked()
        return [name for j, name in enumerate(self.models) if all(row[j] == 0 for row in m)]

    def route(self, reqs: Sequence[Request]) -> dict[str, int | None]:
        """rid -> worker (or None when the model is paused / unknown). Weighted round-robin per model."""
        m = self.masked()
        rings: dict[str, list[int]] = {}
        for j, name in enumerate(self.models):
            rings[name] = [w for w in range(self.workers) for _ in range(max(m[w][j], 0))]
        nxt = {name: 0 for name in self.models}
        plan: dict[str, int | None] = {}
        for r in sorted(reqs, key=lambda r: r.arrival):
            ring = rings.get(r.model)
            if not ring:
                plan[r.rid] = None
                continue
            plan[r.rid] = ring[nxt[r.model] % len(ring)]
            nxt[r.model] += 1
        return plan

    def lines(self) -> list[str]:
        m = self.masked()
        width = max(len(n) for n in self.models)
        out = ["health matrix (workers x models; x = failed, - = masked by a failure's blast radius)",
               "  " + " " * 9 + " ".join(f"{n:>{width}}" for n in self.models)]
        for w, (row, mrow) in enumerate(zip(self.grid, m)):
            cells = ["x" if v == 0 else ("-" if mv == 0 else str(v)) for v, mv in zip(row, mrow)]
            out.append(f"  worker{w:<3}" + " ".join(f"{c:>{width}}" for c in cells))
        out.append(f"  drained workers {self.drained_workers()}, paused models {self.paused_models()}")
        return out
