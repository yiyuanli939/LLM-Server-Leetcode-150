"""Framework: run a loaded config — one ``Server`` per worker, requests routed by model name (M5).

    cfg = load_config("nanoserve/config/examples/server.conf")
    dep = Deployment(cfg)
    dep.submit_many(make_trace(30, seed=0, models=("toy-chat", "toy-7b-instruct", "ToyXBase")))
    for rep in dep.run():
        print(rep.summary())

Every worker gets its own ``ServerConfig`` (``LoadedConfig.worker_config``: the [server] values plus
its kind's [pool.<kind>] overrides) and all workers share one engine. The engine's model is the
plain ``NGramModel`` or, with ``compiled = t``, the IR-compiled ``IRModel`` (identical logits).
Each request is routed with ``LoadedConfig.route`` (glob rules, first match wins) and stamped with
``req.worker``; requests that match no rule are rejected at their arrival tick.

Exercises reached from here: config.glob (routing) and, through ``IRModel``, the M5 IR compiler.
"""
from __future__ import annotations

from typing import Iterable

from nanoserve.config.loader import LoadedConfig, NoRoute
from nanoserve.engine import Engine
from nanoserve.ir.compiler import IRModel
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerReport
from nanoserve.tokenizer.tokenizer import Tokenizer


def build_engine(cfg: LoadedConfig) -> Engine:
    tokenizer = Tokenizer()
    return Engine(tokenizer, model=IRModel(tokenizer) if cfg.compiled else None)


class Deployment:
    def __init__(self, cfg: LoadedConfig, engine: Engine | None = None):
        self.cfg = cfg
        self.engine = engine or build_engine(cfg)
        self.servers = [Server(self.engine, cfg.worker_config(i), name=f"w{i}:{kind}")
                        for i, kind in enumerate(cfg.workers)]
        self.unrouted: list[Request] = []

    def submit_many(self, reqs: Iterable[Request]) -> None:
        per_worker: list[list[Request]] = [[] for _ in self.servers]
        for req in reqs:
            try:
                req.worker = self.cfg.route(req.model)
            except NoRoute:
                req.finished_at, req.finish_reason = req.arrival, "rejected"
                self.unrouted.append(req)
                continue
            per_worker[req.worker].append(req)
        for server, batch in zip(self.servers, per_worker):
            server.submit_many(batch)

    def run(self) -> list[ServerReport]:
        return [server.run() for server in self.servers]
