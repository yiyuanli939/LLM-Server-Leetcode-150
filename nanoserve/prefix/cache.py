"""Framework (M4): the prompt prefix cache the server consults when it admits a request.

    cache = PrefixCache()
    cache.insert("The engine keeps the keys. The scheduler")       # server: on finish
    cache.match("The engine keeps the keys. When memory is low,")  # server: on admit → chars reused

When a request finishes, its prompt is remembered. When a new request is admitted, the server asks
how many leading prompt characters are already cached and only prefills the rest (fewer prefill
ticks → lower time-to-first-token). Outputs never change: the cache only shortens simulated work.

Granularity is the *token*, as in real radix/prefix caches: the KV of token t depends on every token
before it, so a cached prompt can only be reused up to the last token both prompts share. Matching
characters instead would be wrong: "The cache" and "The caches" agree on 9 characters but tokenize
differently near the end.

Tokens as characters: every token id t is written as the single character chr(0xE000 + t) (Unicode
private-use area, so it can never be mistaken for prompt text). A prompt becomes a string with exactly
one character per token, and "the first k tokens are a prefix of some cached prompt" becomes a plain
string-prefix question for the ``PrefixTrie``. That property is monotone in k (if k tokens are, so are
k-1), so k is found by binary search with ``starts_with`` — O(L log L) for an L-token prompt,
independent of the cache size. The answer is returned in characters (the server's unit); it always
ends on a token boundary, so the server's tokenization of the uncached rest is exactly the remaining
tokens.

Statistics: every hit is recorded under the reused text in two ``PrefixHitSum`` maps (hit count and
tokens saved), so "how many hits reused at least the shared system prompt?" is one prefix-sum query.
Without an explicit ``watch`` list, ``report()`` watches the *shared prefix* of the cached prompts:
the longest prefix that at least ``min_share`` of them start with, found with ``common_prefix`` on
their token strings (so it is whole tokens by construction).

Exercises this file calls: prefix.trie, prefix.hit_sum (M4); tok.common_prefix (M1).
"""
from __future__ import annotations

from typing import Iterable

from nanoserve.prefix.hit_sum import PrefixHitSum
from nanoserve.prefix.trie import PrefixTrie
from nanoserve.tokenizer.prefix import common_prefix
from nanoserve.tokenizer.tokenizer import Tokenizer

TOKEN_BASE = 0xE000   # token id t <-> character chr(TOKEN_BASE + t)


class PrefixCache:
    """Token-level prompt prefix cache (``PrefixCacheBackend``)."""

    def __init__(self, tokenizer: Tokenizer | None = None, *, watch: Iterable[str] | None = None,
                 min_share: int = 3) -> None:
        """``tokenizer`` must be the engine's (default: the default ``Tokenizer``).
        ``watch``: prompt prefixes whose hit statistics ``report()`` breaks out; default: the shared
        prefix of the cached prompts (see ``shared_prefix``), e.g. a common system prompt."""
        self.tok = tokenizer or Tokenizer()
        self.trie = PrefixTrie()                # token strings of cached prompts
        self.hit_count = PrefixHitSum()         # reused text -> number of hits that reused exactly it
        self.hit_tokens = PrefixHitSum()        # reused text -> tokens those hits saved
        self._count: dict[str, int] = {}        # running totals behind the two maps
        self._tokens: dict[str, int] = {}
        self.watch = None if watch is None else list(watch)
        self.min_share = min_share
        self._cached: set[str] = set()          # token strings of the distinct cached prompts
        self.lookups = self.hits = self.full_hits = self.exact_repeats = 0
        self.tokens_seen = self.tokens_saved = self.chars_saved = 0

    # ------------------------------------------------------------------ tokens <-> characters
    @staticmethod
    def _chars(ids: list[int]) -> str:
        return "".join(chr(TOKEN_BASE + t) for t in ids)

    def _text(self, token_chars: str) -> str:
        return self.tok.decode([ord(c) - TOKEN_BASE for c in token_chars])

    # ------------------------------------------------------------------ PrefixCacheBackend
    def insert(self, prompt: str) -> None:
        """Remember a prompt whose KV has been computed (the server calls this when a request finishes)."""
        key = self._chars(self.tok.encode(prompt))
        if not key:                             # the trie only holds non-empty keys
            return
        self.trie.insert(key)
        self._cached.add(key)

    def match(self, prompt: str) -> int:
        """Number of leading prompt characters whose KV can be reused (always on a token boundary)."""
        ids = self.tok.encode(prompt)
        key = self._chars(ids)
        # Invariant: the first `lo` tokens are a cached prefix (0 trivially); more than `hi` are not.
        lo, hi = 0, len(key)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.trie.starts_with(key[:mid]):
                lo = mid
            else:
                hi = mid - 1
        reused = self.tok.decode(ids[:lo])      # == prompt[:len(reused)]: greedy tokens tile the text
        self._record(len(ids), lo, reused, exact=0 < lo == len(ids) and self.trie.search(key))
        return len(reused)

    def report(self) -> dict:
        rep = {
            "lookups": self.lookups,
            "hits": self.hits,
            "misses": self.lookups - self.hits,
            "full_hits": self.full_hits,               # every prompt token was cached
            "exact_repeats": self.exact_repeats,       # ... because this very prompt was cached
            "hit_rate": round(self.hits / self.lookups, 3) if self.lookups else 0.0,
            "tokens_saved": self.tokens_saved,
            "token_hit_rate": round(self.tokens_saved / self.tokens_seen, 3) if self.tokens_seen else 0.0,
            "chars_saved": self.chars_saved,
            "cached_prompts": len(self._cached),
        }
        watch = self.watch if self.watch is not None else [p for p in [self.shared_prefix()] if p]
        if watch:
            rep["under"] = {p: {"hits": self.hits_under(p), "tokens_saved": self.tokens_saved_under(p)}
                            for p in watch}
        return rep

    # ------------------------------------------------------------------ statistics
    def _record(self, n_tokens: int, k: int, reused: str, *, exact: bool) -> None:
        self.lookups += 1
        self.tokens_seen += n_tokens
        if k == 0:
            return
        self.hits += 1
        self.full_hits += k == n_tokens
        self.exact_repeats += exact
        self.tokens_saved += k
        self.chars_saved += len(reused)
        # PrefixHitSum.insert *overwrites*, so we keep running totals and store the new total.
        self._count[reused] = self._count.get(reused, 0) + 1
        self._tokens[reused] = self._tokens.get(reused, 0) + k
        self.hit_count.insert(reused, self._count[reused])
        self.hit_tokens.insert(reused, self._tokens[reused])

    def hits_under(self, prefix: str) -> int:
        """Hits whose reused text starts with ``prefix``.

        Trailing whitespace of ``prefix`` is ignored: a match ends on a token boundary and the space
        before a word belongs to that word's token (" The"), so a reused system prompt "... cache. "
        shows up as "... cache." when the next word differs.
        """
        prefix = prefix.rstrip()
        return self.hit_count.sum(prefix) if prefix else self.hits

    def tokens_saved_under(self, prefix: str) -> int:
        """Prefill tokens saved by hits whose reused text starts with ``prefix`` (same rules as ``hits_under``)."""
        prefix = prefix.rstrip()
        return self.hit_tokens.sum(prefix) if prefix else self.tokens_saved

    def shared_prefix(self) -> str:
        """Longest prefix (whole tokens) that at least ``min_share`` cached prompts start with.

        In lexicographic order, prompts sharing a prefix are adjacent, so the best group of m prompts
        is a window of m consecutive sorted token strings; its shared part is ``common_prefix(window)``.
        With fewer cached prompts than ``min_share``, all of them form the group ("" for fewer than 2).
        """
        keys = sorted(self._cached)
        m = min(self.min_share, len(keys))
        if m < 2:
            return ""
        best = ""
        for i in range(len(keys) - m + 1):
            shared = common_prefix(keys[i:i + m])
            if len(shared) > len(best):
                best = shared
        return self._text(best)
