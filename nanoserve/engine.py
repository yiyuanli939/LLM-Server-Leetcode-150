"""Framework: the generation loop (milestone M1).

Single request, streaming::

    engine = Engine()
    for chunk in engine.stream("The scheduler", GenerationConfig(max_tokens=40, stop=(".",))):
        print(chunk, end="", flush=True)
    print(engine.last_result.stats)

Step-wise (what the M2 server uses to batch many requests)::

    st = engine.start("The cache", cfg)
    while not st.done:
        chunk = engine.step(st)       # one decode step; returns the newly *emitted* text

Exercises this file calls (M1):
  tok.segment, tok.top_pieces (via Tokenizer), sample.kth_largest, sample.cdf_index (via sampler),
  stream.multi_stop, stream.find_stop, stream.stop_overlap, stream.holdback,
  stream.repeat_window, stream.unique_run, stream.justify, tok.common_prefix
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Iterator, Sequence

from nanoserve.model.toy import NGramModel
from nanoserve.sampling.sampler import sample
from nanoserve.stream.detok import trailing_word_len
from nanoserve.stream.multistop import MultiStopMatcher
from nanoserve.stream.overlap import longest_border
from nanoserve.stream.render import justify
from nanoserve.stream.repetition import longest_unique_run, repeats_within
from nanoserve.stream.stop import find_stop
from nanoserve.tokenizer.prefix import common_prefix
from nanoserve.tokenizer.tokenizer import Tokenizer


@dataclass
class GenerationConfig:
    max_tokens: int = 60
    temperature: float = 0.6
    top_k: int = 4
    seed: int = 0
    stop: Sequence[str] = ()
    no_repeat_window: int = 0  # forbid a token from re-appearing within this many positions (0 = off)
    word_stream: bool = True  # only emit whole words while streaming


@dataclass
class GenerationResult:
    text: str
    token_ids: list[int]
    finish_reason: str  # "stop" | "length"
    stats: dict = field(default_factory=dict)


@dataclass
class DecodeState:
    """Everything one in-flight request needs between decode steps."""

    prompt: str
    cfg: GenerationConfig
    prompt_ids: list[int]
    rng: random.Random
    matcher: MultiStopMatcher | None
    out: list[int] = field(default_factory=list)
    text: str = ""
    emitted: int = 0
    done: bool = False
    finish_reason: str | None = None
    steps: int = 0

    @property
    def context(self) -> list[int]:
        return self.prompt_ids + self.out


class Engine:
    def __init__(self, tokenizer: Tokenizer | None = None, model=None):
        self.tokenizer = tokenizer or Tokenizer()
        self.model = model or NGramModel(self.tokenizer)
        self.last_result: GenerationResult | None = None

    # ------------------------------------------------------------------ step API
    def start(self, prompt: str, cfg: GenerationConfig | None = None) -> DecodeState:
        cfg = cfg or GenerationConfig()
        stops = [s for s in cfg.stop if s]
        return DecodeState(
            prompt=prompt,
            cfg=cfg,
            prompt_ids=self.tokenizer.encode(prompt),
            rng=random.Random(cfg.seed),
            matcher=MultiStopMatcher(stops) if stops else None,
        )

    def step(self, st: DecodeState) -> str:
        """Run one decode step. Returns the text that became safe to emit (may be "")."""
        if st.done:
            return ""
        cfg = st.cfg
        logits = self.model.logits(st.context)
        tok = self._pick(logits, st.out, cfg, st.rng)
        st.out.append(tok)
        st.steps += 1
        piece = self.tokenizer.vocab[tok]
        st.text += piece

        # stop strings: the incremental matcher says *whether* a stop just completed,
        # find_stop says *where* the earliest one starts, so we can cut there.
        hit = False
        if st.matcher is not None:
            for ch in piece:
                hit = st.matcher.feed(ch) or hit
        if hit:
            st.text = st.text[: self._earliest_stop(st.text, cfg.stop)]
            return self._finish(st, "stop")
        if st.steps >= cfg.max_tokens:
            return self._finish(st, "length")

        hold = self._stop_holdback(st.text, cfg.stop)  # a stop string may be forming at the tail
        if cfg.word_stream and st.text and not st.text[-1].isspace():
            hold = max(hold, trailing_word_len(st.text))  # don't emit half a word
        safe = len(st.text) - hold
        if safe > st.emitted:
            chunk = st.text[st.emitted : safe]
            st.emitted = safe
            return chunk
        return ""

    def _finish(self, st: DecodeState, reason: str) -> str:
        st.done, st.finish_reason = True, reason
        chunk = st.text[st.emitted :]
        st.emitted = len(st.text)
        return chunk

    def result(self, st: DecodeState, elapsed: float | None = None) -> GenerationResult:
        return GenerationResult(
            text=st.text,
            token_ids=list(st.out),
            finish_reason=st.finish_reason or "running",
            stats={
                "prompt_tokens": len(st.prompt_ids),
                "completion_tokens": len(st.out),
                "tokens_per_s": round(len(st.out) / elapsed, 1) if elapsed else None,
                "longest_unique_run": longest_unique_run(st.text),
            },
        )

    # ------------------------------------------------------------------ single-request API
    def stream(self, prompt: str, cfg: GenerationConfig | None = None) -> Iterator[str]:
        t0 = time.perf_counter()
        st = self.start(prompt, cfg)
        while not st.done:
            chunk = self.step(st)
            if chunk:
                yield chunk
        self.last_result = self.result(st, time.perf_counter() - t0)

    def generate(self, prompt: str, cfg: GenerationConfig | None = None) -> GenerationResult:
        for _ in self.stream(prompt, cfg):
            pass
        assert self.last_result is not None
        return self.last_result

    # ------------------------------------------------------------------ helpers
    def _pick(self, logits, out: list[int], cfg: GenerationConfig, rng: random.Random) -> int:
        tok = sample(logits, temperature=cfg.temperature, top_k=cfg.top_k, rng=rng)
        W = cfg.no_repeat_window
        if not W:
            return tok
        window = out[-W:]
        # Invariant: ``window`` never contains a repeat (we never commit one, see below), so the
        # exercise's answer is about the new token only.
        if not repeats_within(window + [tok], W):
            return tok
        banned = set(window)
        if len(banned) >= len(logits):     # every token is in the window: nothing can satisfy it
            return tok
        # Draw again with the window's tokens removed (top-k is re-applied to what's left), so the
        # result is the model's distribution conditioned on "not in the window" — one extra draw,
        # never a retry loop, and the window stays repeat-free.
        return sample(logits, temperature=cfg.temperature, top_k=cfg.top_k, rng=rng, banned=banned)

    @staticmethod
    def _earliest_stop(text: str, stops: Sequence[str]) -> int:
        best = len(text)
        for s in stops:
            if s:
                i = find_stop(text, s)
                if 0 <= i < best:
                    best = i
        return best

    @staticmethod
    def _stop_holdback(text: str, stops: Sequence[str]) -> int:
        """Exactly how many trailing chars could still become the start of a stop string."""
        hold = 0
        for s in stops:
            if len(s) > 1 and text:
                tail = text[-(len(s) - 1):]
                hold = max(hold, len(longest_border(s + "\x00" + tail)))
        return hold

    # ------------------------------------------------------------------ utilities
    @staticmethod
    def render(text: str, width: int) -> list[str]:
        words = text.split()
        return justify(words, width) if words else []

    @staticmethod
    def shared_prefix(prompts: list[str]) -> str:
        """Shared prefix of several prompts — the seed of prefix caching (M4)."""
        return common_prefix(prompts)
