"""Framework (M3): the free-block pool of the paged KV cache, a sorted chain of free block ids.

    pool = FreePool(range(1, 9))   # free list 1 -> 2 -> ... -> 8
    pool.pop(), pool.pop()         # 1, 2: always the lowest free id
    pool.stage([2, 1])             # one finished sequence's blocks, in any order
    pool.flush()                   # merged back: 1 -> 2 -> ... -> 8

Why sorted: ``pop`` always hands out the lowest free id, so allocations prefer low addresses and the
blocks in use stay packed at the bottom of the pool (locality, less fragmentation).

Releases are staged, not merged one by one. ``stage`` turns one sequence's released ids into a chain,
sorts it (kv.sort_free) and puts it in a fixed-capacity staging ring (kv.ring_queue) of batch
numbers. When the ring is full, the caller must flush first. ``flush`` drains the ring oldest-first
and merges the staged chains into the free list: a single chain with merge_free (kv.merge_free),
several at once with one k-way merge (kv.merge_free_k). The block manager flushes lazily: only when
the free list itself runs dry, when the ring is full, or on an explicit ``sanitize``. So the releases
of several finished sequences are usually merged in one k-way pass.

The merged list is then sanitized: an id that now appears more than once was freed twice. Every copy
is removed (kv.drop_double_free) and the id is returned to the caller, who quarantines the block:
something may still be using it, so it must never be handed out again.

Exercises this file calls (M3): kv.sort_free, kv.ring_queue, kv.merge_free, kv.merge_free_k,
kv.drop_double_free.
"""
from __future__ import annotations

from typing import Iterable

from nanoserve.common.nodes import ListNode, chain_to_list, list_to_chain
from nanoserve.kvcache.free_list import drop_double_freed, merge_free_lists, merge_k_free_lists, sort_free_list
from nanoserve.kvcache.ring_queue import RingQueue


class FreePool:
    """Free block ids as one sorted chain, plus a ring of staged (sorted) release batches."""

    def __init__(self, ids: Iterable[int], staging: int = 8) -> None:
        if staging < 1:
            raise ValueError("staging capacity must be >= 1")
        ids = sorted(ids)
        self.head: ListNode | None = list_to_chain(ids)
        self.listed = len(ids)                       # nodes on the free list
        self.ring = RingQueue(staging)               # numbers of the staged batches, oldest first
        self.slots: list[ListNode | None] = [None] * staging   # batch number % staging -> its chain
        self.staged_count = 0                        # ids waiting in staged batches
        self.batches = 0                             # batches ever staged
        self.merges = 0                              # flushes that merged a single batch
        self.k_way_merges = 0                        # flushes that merged several batches at once

    def __len__(self) -> int:
        """Free blocks, staged ones included (an unsanitized double free counts twice)."""
        return self.listed + self.staged_count

    def full(self) -> bool:
        return self.ring.is_full()

    def stage(self, ids: Iterable[int]) -> None:
        """Stage one batch of released block ids (any order). The ring must not be full."""
        ids = list(ids)
        if not ids:
            return
        n = self.batches
        if not self.ring.enqueue(n):
            raise RuntimeError("staging ring is full: flush() first")
        self.slots[n % len(self.slots)] = sort_free_list(list_to_chain(ids))
        self.batches += 1
        self.staged_count += len(ids)

    def flush(self) -> list[int]:
        """Merge every staged batch into the free list; return the ids found double-freed."""
        chains: list[ListNode | None] = []
        while not self.ring.is_empty():
            n = self.ring.front()
            self.ring.dequeue()
            chains.append(self.slots[n % len(self.slots)])
            self.slots[n % len(self.slots)] = None
        if not chains:
            return []
        if len(chains) == 1:
            self.head = merge_free_lists(self.head, chains[0])
            self.merges += 1
        else:
            self.head = merge_k_free_lists([self.head, *chains])
            self.k_way_merges += 1
        before = chain_to_list(self.head)
        self.staged_count = 0
        self.head = drop_double_freed(self.head)
        after = chain_to_list(self.head)
        self.listed = len(after)
        if len(after) == len(before):
            return []
        return sorted(set(before) - set(after))   # ids whose every copy was dropped

    def pop(self) -> int | None:
        """Take the lowest id off the free list (flush first so staged blocks count)."""
        node = self.head
        if node is None:
            return None
        self.head, node.next = node.next, None
        self.listed -= 1
        return node.val

    def contents(self) -> list[list[int]]:
        """Read-only view: the free list, then every staged batch (oldest first), each sorted."""
        out = [chain_to_list(self.head)]
        if not self.ring.is_empty():
            first = self.ring.front()
            for n in range(first, self.batches):
                out.append(chain_to_list(self.slots[n % len(self.slots)]))
        return out
