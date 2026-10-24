"""Framework (M3): the host-memory tier that keeps the KV of evicted GPU blocks for later reuse.

When the block manager evicts a cached block from the GPU, it copies the block's KV to host memory
(offload), keyed by the block's content hash. A later prompt that misses on the GPU but hits here
restores the block instead of recomputing it (as SGLang HiCache or vLLM CPU offloading do).
Host memory is finite too, so the tier evicts by the policy ``ServerConfig.eviction`` selects:

  * "lru"    → LRUBlockCache (kv.lru): evict the entry used least recently
  * "lfu"    → LFUBlockCache (kv.lfu): evict the least frequently used entry, the least recent among ties
  * "random" → ``RandomTier``: ``capacity`` host slots. A BlockHashMap (kv.block_hash) maps each hash
               to its slot, and a RandomEvictSet (kv.random_evict) holds the occupied slots and picks
               a victim uniformly at random

Values are payload checksums, a stand-in for the KV bytes: the manager compares the stored checksum
with the one it expects before counting a restore. All tiers share one tiny interface,
``get(key) -> value | -1`` and ``put(key, value)``. The tier *is* the storage, so an entry it evicts
on its own needs no further cleanup.

The random tier must draw from the global ``random`` module (the exercise's contract). To keep runs
reproducible without disturbing anybody else's use of ``random``, it swaps its own seeded generator
state in around each ``pick``.

Exercises this file calls (M3): kv.lru, kv.lfu, kv.random_evict, kv.block_hash.
"""
from __future__ import annotations

import random
from typing import Protocol

from nanoserve.kvcache.evict import RandomEvictSet
from nanoserve.kvcache.hashmap import BlockHashMap
from nanoserve.kvcache.lfu import LFUBlockCache
from nanoserve.kvcache.lru import LRUBlockCache

POLICIES = ("lru", "lfu", "random")


class HostTier(Protocol):
    def get(self, key: int) -> int: ...
    def put(self, key: int, value: int) -> None: ...


class RandomTier:
    """``capacity`` host slots; a new key arriving while all are taken replaces a random one."""

    MAX_CAPACITY = 1_000_000   # slot numbers are BlockHashMap values: at most 10^6

    def __init__(self, capacity: int, seed: int = 0) -> None:
        if not 1 <= capacity <= self.MAX_CAPACITY:
            raise ValueError(f"random tier capacity must be in [1, {self.MAX_CAPACITY}]")
        self.capacity = capacity
        self.slot_of = BlockHashMap()          # content hash -> host slot
        self.key = [0] * capacity              # what each slot holds
        self.value = [0] * capacity
        self.occupied = RandomEvictSet()       # occupied slot numbers, for O(1) uniform picks
        self.spare = list(range(capacity - 1, -1, -1))
        self.evictions = 0
        self._rng_state = random.Random(seed).getstate()

    def get(self, key: int) -> int:
        s = self.slot_of.get(key)
        return -1 if s == -1 else self.value[s]

    def put(self, key: int, value: int) -> None:
        s = self.slot_of.get(key)
        if s == -1:                            # a new key needs a slot
            if not self.spare:
                victim = self._pick()
                self.slot_of.remove(self.key[victim])
                self.occupied.remove(victim)
                self.spare.append(victim)
                self.evictions += 1
            s = self.spare.pop()
            self.occupied.insert(s)
            self.key[s] = key
            self.slot_of.put(key, s)
        self.value[s] = value

    def _pick(self) -> int:
        saved = random.getstate()
        random.setstate(self._rng_state)
        try:
            return self.occupied.pick()
        finally:
            self._rng_state = random.getstate()
            random.setstate(saved)


def make_host_tier(policy: str, capacity: int, *, seed: int = 0) -> HostTier:
    if capacity < 1:
        raise ValueError("host tier capacity must be >= 1 block")
    if policy == "lru":
        return LRUBlockCache(capacity)
    if policy == "lfu":
        return LFUBlockCache(capacity)
    if policy == "random":
        return RandomTier(capacity, seed)
    raise ValueError(f"unknown eviction policy {policy!r} (expected one of {POLICIES})")
