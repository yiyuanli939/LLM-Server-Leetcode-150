"""Framework (M3): occupancy views of the block pool, for the KV report, the invariant checker and the
leak audit.

  * ``Bitmap``          one bit per block, packed into 31-bit words; the number of blocks in use is
                        the sum of the words' popcounts (kv.popcount).
  * ``free_summary``    the sorted free ids as 'a->b' range strings (kv.free_ranges) plus the largest
                        run of consecutive free ids (kv.longest_run): the biggest contiguous block
                        allocation the pool could serve right now (a fragmentation indicator).
  * ``charge_counts``   how many in-use blocks are charged to each sequence. The per-block charge
                        array holds 0 for "not in use". Those slots are squeezed out of a copy in place
                        (kv.compact), the rest is sorted into an owner-sorted table, and each sequence's
                        slice of it is found by binary search (kv.seq_range).
  * ``merge_distinct``  the distinct ids of several sorted lists, e.g. the blocks held by all block
                        tables (a shared block appears in several): merge each list in place into the
                        padded running result (kv.merge_arrays), then squeeze out repeats in place
                        (kv.dedupe).
  * ``PageTable``       the KV slot addresses (block * block_size + offset) of every in-use block, one
                        row per block in block-id order, so the table is sorted row by row. The checker
                        asks "is the slot the attention kernel will read mapped?" for every token of
                        every running sequence (kv.page_lookup).

Exercises this file calls (M3): kv.popcount, kv.free_ranges, kv.longest_run, kv.compact, kv.seq_range,
kv.merge_arrays, kv.dedupe, kv.page_lookup.
"""
from __future__ import annotations

from typing import Iterable

from nanoserve.kvcache.allocator import free_ranges, longest_free_run, owner_range
from nanoserve.kvcache.bitmap import popcount
from nanoserve.kvcache.compact import dedupe_sorted, merge_into, remove_freed
from nanoserve.kvcache.page_table import page_exists

NOT_IN_USE = 0   # charge value of a block nobody holds (sequence ids start at 1)


class Bitmap:
    """Occupancy bitmap: bit i of the pool is bit (i % 31) of word i // 31."""

    WORD = 31   # bits per word, so every non-zero word is a valid popcount input (1 <= w <= 2^31 - 1)

    def __init__(self, n: int) -> None:
        self.n = n
        self.words = [0] * ((n + self.WORD - 1) // self.WORD)

    def set(self, i: int) -> None:
        self.words[i // self.WORD] |= 1 << (i % self.WORD)

    def clear(self, i: int) -> None:
        self.words[i // self.WORD] &= ~(1 << (i % self.WORD))

    def test(self, i: int) -> bool:
        return bool(self.words[i // self.WORD] >> (i % self.WORD) & 1)

    def count(self) -> int:
        return sum(popcount(w) for w in self.words if w)


def free_summary(free_ids: list[int]) -> tuple[list[str], int]:
    """(range strings, largest consecutive run) of strictly increasing free ids."""
    return free_ranges(free_ids), longest_free_run(free_ids)


def charge_counts(charge: list[int]) -> dict[int, int]:
    """sequence id -> number of in-use blocks charged to it."""
    slots = list(charge)                      # a copy: the live array stays indexed by block id
    k = remove_freed(slots, NOT_IN_USE)
    table = sorted(slots[:k])                 # the owner-sorted table
    out: dict[int, int] = {}
    i = 0
    while i < k:
        first, last = owner_range(table, table[i])
        out[table[i]] = last - first + 1
        i = last + 1
    return out


def merge_distinct(lists: Iterable[list[int]]) -> list[int]:
    """Distinct values of several individually sorted lists, ascending."""
    out: list[int] = []
    for b in lists:
        m, n = len(out), len(b)
        if n == 0:
            continue
        out.extend([0] * n)                   # merge_into wants n slots of padding at the end
        merge_into(out, m, b, n)
        del out[dedupe_sorted(out):]          # keep the running result distinct (and short)
    return out


class PageTable:
    """KV slot addresses of the in-use blocks, one sorted row per block."""

    def __init__(self, in_use: Iterable[int], block_size: int) -> None:
        self.rows = [[b * block_size + j for j in range(block_size)] for b in sorted(in_use)]

    def mapped(self, addr: int) -> bool:
        return bool(self.rows) and page_exists(self.rows, addr)
