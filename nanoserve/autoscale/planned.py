"""Framework: a ``Cluster`` whose front end follows a precomputed routing plan (M7).

    plan = {"r000": 0, "r001": 0, "r002": 1, "r003": None}      # None -> rejected at the front end
    cluster = PlannedCluster(2, plan, engine=engine, config=ServerConfig(max_batch=1))
    cluster.submit_many(fresh_batch(trace))
    report = cluster.run()                                      # a normal ClusterReport

The autoscaler (capacity plans it wants to validate on the real server) and the dashboard's health-aware
front end (requests routed around masked workers / models) both decide *where* every request goes before
the run. Everything else — lockstep ticking, per-worker ``Server``, merged busy timeline, cluster p50 — is
the M2 ``Cluster``. Workers may get their own ``ServerConfig`` (heterogeneous pools).

Exercises: none directly (through ``Cluster`` / ``Server`` the M2 core and sched.merge_busy,
metrics.merged_median).
"""
from __future__ import annotations

from typing import Mapping, Sequence

from nanoserve.engine import Engine
from nanoserve.server.cluster import Cluster, ClusterReport
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig


class PlannedCluster(Cluster):
    def __init__(self, n_workers: int, plan: Mapping[str, int | None], *, engine: Engine | None = None,
                 config: ServerConfig | None = None, configs: Sequence[ServerConfig] | None = None) -> None:
        # Cluster.run dispatches everything up front for policy "weighted"; we override that dispatch
        super().__init__(n_workers, engine=engine, config=config, policy="weighted")
        self.plan = dict(plan)
        if configs is not None:  # heterogeneous pool: one ServerConfig per worker
            if len(configs) != n_workers:
                raise ValueError("need one config per worker")
            self.workers = [Server(self.engine, c, name=f"worker{i}") for i, c in enumerate(configs)]

    def report(self) -> ClusterReport:
        rep = super().report()
        rep.policy = "planned"
        return rep

    def _route_weighted(self, reqs: list[Request]) -> None:
        """Called by ``Cluster.run`` before the first tick: dispatch every request by the plan."""
        for req in reqs:
            w = self.plan.get(req.rid)
            if w is None:
                req.finished_at, req.finish_reason = req.arrival, "rejected"  # no healthy target: 503
            else:
                self._send(req, w)
