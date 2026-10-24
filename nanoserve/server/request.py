"""Framework: the request object that flows through the server (M2+).

Time is simulated in integer *ticks*: one tick = one decode step of the running batch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(eq=False)  # identity semantics: queues remove/compare by object
class Request:
    rid: str
    prompt: str
    arrival: int = 0                 # tick at which the request reaches the server
    max_tokens: int = 24
    tenant: str = "default"
    deadline: int | None = None      # tick by which it should finish (SLO); used by the EDF policy
    stop: tuple[str, ...] = ()
    seed: int = 0
    temperature: float = 0.6
    top_k: int = 4
    session: str | None = None       # API session id (TTL-tracked by the server)
    model: str = "toy"               # model name, matched by routing rules (M5)

    # ---- runtime fields, filled in by the server -------------------------------------------
    prompt_tokens: int = 0
    state: Any = None                # nanoserve.engine.DecodeState while running
    slot: int | None = None
    worker: int | None = None
    admitted_at: int | None = None
    first_token_at: int | None = None
    finished_at: int | None = None
    finish_reason: str | None = None # "stop" | "length" | "rejected"
    cached_chars: int = 0            # prompt chars served from the prefix cache (M4)
    prefill_left: int = 0            # remaining prefill ticks
    preemptions: int = 0
    output: str = ""
    chunks: list[tuple[int, str]] = field(default_factory=list)  # (tick, emitted text)

    @property
    def latency(self) -> int | None:
        return None if self.finished_at is None else self.finished_at - self.arrival

    @property
    def ttft(self) -> int | None:
        return None if self.first_token_at is None else self.first_token_at - self.arrival

    @property
    def met_deadline(self) -> bool | None:
        if self.deadline is None or self.finished_at is None:
            return None
        return self.finished_at <= self.deadline

    def reset_runtime(self) -> None:
        """Called on preemption: the request will be recomputed from scratch."""
        self.state = None
        self.slot = None
        self.admitted_at = None
        self.first_token_at = None
        self.prefill_left = 0
        self.output = ""
        self.chunks = []
