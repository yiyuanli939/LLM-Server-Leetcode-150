"""Framework: the tokenizer used by the engine.

Vocabulary = every character in the corpus + the most frequent words (with a leading space) as
multi-character tokens, chosen with ``top_k_pieces`` (exercise ``tok.top_pieces``). Encoding is
greedy longest-match, after validating the input with ``can_segment`` (exercise ``tok.segment``).
"""
from __future__ import annotations

import re
from collections import Counter

from nanoserve.model.corpus import CORPUS
from nanoserve.tokenizer.segment import can_segment
from nanoserve.tokenizer.train import top_k_pieces


class UnknownCharacterError(ValueError):
    def __init__(self, chars: list[str]):
        self.chars = chars
        super().__init__(f"text contains characters outside the vocabulary: {chars!r}")


class Tokenizer:
    def __init__(self, corpus: str = CORPUS, n_words: int = 48, min_count: int = 3):
        chars = sorted(set(corpus))
        pieces = re.findall(r"[A-Za-z]{3,}", corpus)
        counts = Counter(pieces)
        freqs = sorted(counts.values(), reverse=True)
        k = min(n_words, sum(1 for f in freqs if f >= min_count))
        while 0 < k < len(freqs) and freqs[k - 1] == freqs[k]:
            k -= 1  # cut at a frequency boundary so "the k most frequent" is unambiguous
        top = top_k_pieces(pieces, k) if k else []
        merged = [" " + w for w in sorted(top, key=lambda w: (-counts[w], w))]
        self.vocab: list[str] = chars + merged
        self.id_of: dict[str, int] = {t: i for i, t in enumerate(self.vocab)}
        self.max_len = max(len(t) for t in self.vocab)

    def __len__(self) -> int:
        return len(self.vocab)

    def encode(self, text: str) -> list[int]:
        if not can_segment(text, self.vocab):
            raise UnknownCharacterError(sorted({c for c in text if c not in self.id_of}))
        ids, i = [], 0
        while i < len(text):
            for L in range(min(self.max_len, len(text) - i), 0, -1):
                piece = text[i : i + L]
                if piece in self.id_of:
                    ids.append(self.id_of[piece])
                    i += L
                    break
            else:  # pragma: no cover - can_segment guarantees we never get here
                raise UnknownCharacterError([text[i]])
        return ids

    def decode(self, ids: list[int]) -> str:
        return "".join(self.vocab[i] for i in ids)

    def sanitize(self, text: str, replacement: str = " ") -> str:
        """Replace characters outside the vocabulary (used by the CLI for friendly input handling)."""
        return "".join(c if c in self.id_of else replacement for c in text)
