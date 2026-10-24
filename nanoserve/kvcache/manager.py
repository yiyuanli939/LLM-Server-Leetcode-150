"""Framework (M3): the paged KV-cache block manager, the server's ``KVBackend``.

    server = Server(config=ServerConfig(max_batch=4, kv_blocks=24, block_size=8, eviction="lfu"))
    report = server.run()
    report.plugins["kv"]                              # BlockManager.report()

    mgr = BlockManager(num_blocks=32, block_size=4)   # or drive it directly with token ids:
    mgr.admit("r1", prompt_ids); mgr.store("r1", prompt_ids + new_ids); mgr.release("r1")
    mgr.fork("r1", "r1/2")                            # parallel sampling: share every block, copy on write
    snap = mgr.checkpoint("r1"); ...; mgr.rollback("r1", snap)   # speculative tokens rejected

Paged attention in one paragraph: KV memory is cut into ``num_blocks`` blocks of ``block_size`` token
slots. A sequence's *block table* lists the blocks holding its tokens in order: token ``p`` lives in
slot ``table[p // block_size] * block_size + p % block_size``. Blocks are reference counted, so
sequences can share them: prompts with a common prefix share the prefix's full blocks, and forked
samples share everything until one of them writes into a shared block (copy-on-write).

Where everything lives:

  * Block tables are chains of ``RandomListNode``: ``val`` = block id, ``next`` = the next block,
    ``random`` = the previous node (a back link). Tokens are appended and rolled back at the tail.
    Releasing walks tail → head over the back links, so a sequence's tail blocks enter the cache
    before its head blocks. Tail blocks are the least likely to be shared, so they should be evicted
    first, as in vLLM. ``fork`` deep-copies a table, back links included, with ``fork_chain``
    (kv.fork). The invariant checker proves each chain ends (``has_cycle``, kv.has_cycle) before it walks it.
  * Free blocks: ``FreePool`` (pool.py), a sorted chain with staged, batched releases and a double-free
    sanitizer. Double-freed blocks are quarantined and never handed out again; so are blocks that
    show up on the free list while still marked in use (checked when they are popped).
  * Prefix sharing: every full block gets a chain hash over all tokens up to its end, and
    ``BlockHashMap`` (kv.block_hash) maps hash → block. A hit is verified against the block's exact
    token key, so a hash collision can never share the wrong KV.
  * References: ``refs[b]`` plus the per-sequence breakdown ``holders[b]``. A ``RefCounter``
    (kv.refcount) mirrors them, so the report gets the most and least shared block in O(1). Every
    in-use block is *charged* to one holder (whoever brought it in; when that holder lets go, the next
    holder). ``VersionedStore`` (kv.versioned) keeps the charge history keyed by event number and
    answers "who owned block b at tick t" for leak and double-free diagnostics.
  * Cached blocks: when the last reference to a registered full block goes away, its KV stays on the
    GPU as *cache* and a later prompt hit revives it. When the free list runs dry, a cached block is
    evicted: the ``scan`` oldest releases are ordered cold-first by heat (a saturating reuse count)
    with ``partition_by_heat`` (kv.partition_hot), so blocks reused ``hot`` times or more are
    protected. Evicted blocks are offloaded to the host tier (tiers.py, policy = ``eviction``) and
    restored from there on a later hit. The copies issued in one tick are coalesced into one transfer
    per contiguous block range with ``FreeRangeTracker`` (kv.free_tracker).
  * Checkpoints: a sequence's table history is a ``SnapshotTable`` (kv.snapshot): slot 0 holds the
    number of stored tokens n, slot i the block at table position i-1; a snapshot's table is slots
    1..ceil(n / block_size). ``checkpoint`` snaps it and pins the blocks; ``rollback`` reads the
    snapshot back and restores the exact table.
    Only changes are stored, so a checkpoint per speculative round costs O(changes), not O(table).
  * The token-slot arena (arena.py), the event log (eventlog.py) and the occupancy views
    (occupancy.py) are separate modules.
  * ``audit_leaks`` compares the occupancy bitmap with what is reachable from the block tables,
    checkpoints and the cache. Counting tells how many blocks of an id range are unaccounted for. A
    range missing exactly one has it identified by ``find_leaked`` (kv.leaked) over the two id
    lists, where every accounted block appears twice. Ranges missing more are halved.

Exercises this file calls (M3): kv.fork, kv.has_cycle, kv.partition_hot, kv.block_hash, kv.refcount,
kv.versioned, kv.snapshot, kv.free_tracker, kv.leaked.
Through its helpers: kv.sort_free, kv.ring_queue, kv.merge_free, kv.merge_free_k, kv.drop_double_free
(pool.py); kv.popcount, kv.free_ranges, kv.longest_run, kv.compact, kv.seq_range, kv.merge_arrays,
kv.dedupe, kv.page_lookup (occupancy.py); kv.ring_head, kv.ring_search, kv.rotate_buffer (eventlog.py);
kv.lru, kv.lfu, kv.random_evict, kv.block_hash (tiers.py); kv.mem_alloc, kv.address_ranges (arena.py).
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from itertools import islice

from nanoserve.common.nodes import ListNode, RandomListNode
from nanoserve.kvcache.arena import ArenaBoundsError, TokenArena
from nanoserve.kvcache.block_table import fork_chain, has_cycle, partition_by_heat
from nanoserve.kvcache.eventlog import EventLog
from nanoserve.kvcache.free_tracker import FreeRangeTracker
from nanoserve.kvcache.hashmap import BlockHashMap
from nanoserve.kvcache.leak import find_leaked
from nanoserve.kvcache.occupancy import Bitmap, PageTable, charge_counts, free_summary, merge_distinct
from nanoserve.kvcache.pool import FreePool
from nanoserve.kvcache.refcount import RefCounter
from nanoserve.kvcache.snapshot import SnapshotTable
from nanoserve.kvcache.tiers import POLICIES, make_host_tier
from nanoserve.kvcache.versioned import VersionedStore
from nanoserve.server.request import Request

MAX_BLOCKS = 4096          # pool size limit of this toy manager
MAX_BLOCK_SIZE = 128
HEAT_CAP = 200             # heat is a saturating reuse counter
MAX_SCAN = 200             # eviction looks at most this many of the oldest cached blocks
HASH_MOD = 999_983         # prime < 10^6, so dedup-table keys stay in [0, 10^6]
CHECK_MOD = 999_979
ROOT_HASH = 1


def chain_hash(parent: int, tokens: list[int]) -> int:
    """Hash of a full block given its parent block's hash: identifies all tokens up to the block's end."""
    h = parent
    for t in tokens:
        h = (h * 257 + t + 1) % HASH_MOD
    return h


def checksum(key: tuple[int, ...]) -> int:
    """Stand-in for the KV payload of a block whose prefix tokens are ``key`` (stored in the host tier)."""
    c = 7
    for t in key:
        c = (c * 131 + t + 1) % CHECK_MOD
    return c


def _blocks_for(tokens: int, block_size: int) -> int:
    return -(-tokens // block_size)


@dataclass(eq=False)
class SeqState:
    """One admitted sequence (a request incarnation: a preempted request gets a fresh one)."""

    sid: int
    rid: str
    head: RandomListNode | None = None
    tail: RandomListNode | None = None
    length: int = 0                                      # blocks in the table
    tokens: list[int] = field(default_factory=list)      # tokens whose KV is stored
    hashes: list[int] = field(default_factory=list)      # chain hash of every full block
    hist: SnapshotTable | None = None                    # table history, created at the first checkpoint
    checkpoints: list[int] = field(default_factory=list) # live snapshot ids, ascending

    @property
    def stored(self) -> int:
        return len(self.tokens)

    def block_list(self) -> list[int]:
        out, cur = [], self.head
        while cur is not None:
            out.append(cur.val)
            cur = cur.next
        return out


class BlockManager:
    """Paged KV-cache manager with prefix sharing, copy-on-write, checkpoints and a host tier."""

    def __init__(self, num_blocks: int, block_size: int = 8, eviction: str = "lru", *,
                 host_blocks: int | None = None, hot: int = 2, scan: int = 32,
                 arena_size: int | None = None, log_capacity: int = 256, tokenizer=None,
                 seed: int = 0, debug: bool = False) -> None:
        if not 1 <= num_blocks <= MAX_BLOCKS:
            raise ValueError(f"num_blocks must be in [1, {MAX_BLOCKS}]")
        if not 1 <= block_size <= MAX_BLOCK_SIZE:
            raise ValueError(f"block_size must be in [1, {MAX_BLOCK_SIZE}]")
        if eviction not in POLICIES:
            raise ValueError(f"unknown eviction policy {eviction!r} (expected one of {POLICIES})")
        if not 1 <= hot <= HEAT_CAP:          # partition_by_heat: x in [-200, 200]
            raise ValueError(f"hot must be in [1, {HEAT_CAP}]")
        if not 1 <= scan <= MAX_SCAN:         # partition_by_heat: at most 200 nodes
            raise ValueError(f"scan must be in [1, {MAX_SCAN}]")
        n = num_blocks
        self.num_blocks, self.block_size, self.eviction = n, block_size, eviction
        self.hot, self.scan, self.debug = hot, scan, debug

        self.pool = FreePool(range(n))
        self.bitmap = Bitmap(n)                       # bit set = block is off the free list
        self.refs = [0] * n
        self.holders: list[dict[int, int]] = [{} for _ in range(n)]   # sid -> references
        self.charge = [0] * n                         # sid the block is charged to (0 = nobody)
        self.content: list[list[int]] = [[] for _ in range(n)]       # tokens whose KV the block holds
        self.key: list[tuple[int, ...] | None] = [None] * n          # all tokens up to a full block's end
        self.hash_of = [-1] * n
        self.heat = [0] * n
        self.last_event = [0] * n
        self.table = BlockHashMap()                   # chain hash -> block (full blocks only)
        self.refcount = RefCounter()                  # block -> references, for most/least shared
        self.owners = VersionedStore()                # block -> rid it is charged to, by event number
        self.cached: dict[int, None] = {}             # refs == 0 but KV kept; insertion = release order
        self.quarantine: list[int] = []
        self._quarantined: set[int] = set()
        self.host = make_host_tier(eviction, host_blocks or n, seed=seed)
        self.arena = TokenArena(arena_size or 2 * n * block_size)
        self.log = EventLog(log_capacity)

        self.seqs: dict[str, SeqState] = {}
        self._rid_of: dict[int, str] = {}
        self._next_sid = 1
        self.now = 0
        self._ticks: list[int] = []                   # ticks that logged events, ascending
        self._tick_ts: list[int] = []                 # ... and the last event number of each
        self._freed: list[int] = []                   # blocks released by the current operation
        self._xfer: FreeRangeTracker | None = None    # blocks offloaded in the current tick
        self.in_use = 0
        self.peak_in_use = 0
        self.stats = dict.fromkeys((
            "admitted", "released", "shared", "revived", "restored", "computed", "decode_blocks",
            "cow", "offloaded", "transfers", "forks", "checkpoints", "rollbacks"), 0)
        self._tok = tokenizer
        self._enc: dict[str, list[int]] = {}

    # ================================================================== KVBackend protocol
    def can_admit(self, req: Request, now: int) -> bool:
        self._clock(now)
        tokens = self._encode(req)
        if tokens is None:                    # can't see the token ids: assume nothing is shared
            n = req.prompt_tokens
            return (_blocks_for(n + 1, self.block_size) <= len(self.pool) + len(self.cached)
                    and self.arena.fits(n + self.block_size, self._next_sid))
        return self.fits(tokens)

    def can_ever_fit(self, req: Request) -> bool:
        """Could ``req`` run to completion if it had the whole cache to itself?

        Worst case = prompt + max_tokens tokens with nothing shared. The server rejects requests that
        fail this up front: admitting them would preempt everybody else and then itself, forever
        (a livelock), because ``can_admit`` only checks that the prompt + one token fits *now*.
        Quarantined (double-freed) blocks are never handed out again, so they don't count.
        """
        need = _blocks_for(req.prompt_tokens + req.max_tokens, self.block_size)
        return need <= self.num_blocks - len(self.quarantine)

    def on_admit(self, req: Request, now: int) -> None:
        self.admit(req.rid, list(req.state.prompt_ids), now)

    def on_token(self, req: Request, now: int) -> bool:
        return self.store(req.rid, req.state.context, now)

    def on_finish(self, req: Request, now: int) -> None:
        self.release(req.rid, now)

    # ================================================================== the same, by rid and token ids
    def fits(self, tokens: list[int]) -> bool:
        """Could a sequence with this prompt be admitted now (prompt + one new token)?"""
        need = _blocks_for(len(tokens) + 1, self.block_size)
        need -= sum(1 for _, _, b in self._prompt_blocks(tokens) if b >= 0 and self.refs[b])
        return (need <= len(self.pool) + len(self.cached)
                and self.arena.fits(len(tokens) + self.block_size, self._next_sid))

    def admit(self, rid: str, tokens: list[int], now: int | None = None) -> None:
        """Allocate (or share / revive / restore) the blocks of a new sequence's prompt."""
        self._clock(self.now if now is None else now)
        if rid in self.seqs:
            raise ValueError(f"{rid} is already admitted")
        if not tokens:
            raise ValueError("empty prompt")
        bs = self.block_size
        tokens = list(tokens)
        seq = self._new_seq(rid)
        plan = self._prompt_blocks(tokens)
        blocks = [b for _, _, b in plan]
        for b in blocks:                      # pin every GPU hit first, so eviction can't take them
            if b < 0:
                continue
            if self.refs[b]:
                self._ref(b, seq)
                self.stats["shared"] += 1
                self._event("share", b, seq.sid)
            else:
                del self.cached[b]
                self._ref(b, seq)
                self.stats["revived"] += 1
                self._acquire(b, seq, "revive")
            self.heat[b] = min(self.heat[b] + 1, HEAT_CAP)
        for i, (h, key, b) in enumerate(plan):
            if b >= 0:
                continue
            on_host = self.host.get(h) == checksum(key)   # the host tier still has this block's KV
            nb = self._must_take()
            self.content[nb] = list(key[-bs:])
            self._ref(nb, seq)
            if on_host:
                self.stats["restored"] += 1
                self.heat[nb] = 1
                self._acquire(nb, seq, "restore")
            else:
                self.stats["computed"] += 1
                self._acquire(nb, seq, "alloc")
            self._register(nb, h, key)
            blocks[i] = nb
        rest = tokens[len(plan) * bs:]
        if rest:                                     # the prompt's partial last block (never shared)
            nb = self._must_take()
            self.content[nb] = list(rest)
            self._ref(nb, seq)
            self._acquire(nb, seq, "alloc")
            blocks.append(nb)
        for b in blocks:
            self._append_node(seq, b)
        seq.tokens = tokens
        seq.hashes = [h for h, _, _ in plan]
        if not self.arena.reserve(seq.sid, len(tokens) + bs):
            raise RuntimeError("token arena full: admit() called although fits() is False")
        self._write_slots(seq, 0)
        self.stats["admitted"] += 1
        self._after()

    def store(self, rid: str, context: list[int], now: int | None = None) -> bool:
        """Store the KV of ``context[stored:]`` for ``rid`` (its first ``stored`` tokens must be the
        ones already stored). False if a block or arena cell is missing; what fit stays stored."""
        self._clock(self.now if now is None else now)
        ok = self._store(self.seqs[rid], context)
        self._after()
        return ok

    def release(self, rid: str, now: int | None = None) -> None:
        """Release everything ``rid`` holds (finish or preemption); unknown rids are ignored."""
        self._clock(self.now if now is None else now)
        seq = self.seqs.pop(rid, None)
        if seq is None:
            return
        for snap in list(seq.checkpoints):
            self._drop_checkpoint(seq, snap)
        self._release_table(seq)
        self.arena.release(seq.sid)
        self.stats["released"] += 1
        self._after()

    # ================================================================== fork / checkpoints
    def fork(self, parent_rid: str, child_rid: str, now: int | None = None) -> bool:
        """Admit ``child_rid`` as a copy of ``parent_rid`` that shares every block (parallel sampling,
        beam branching). The child continues from the parent's stored tokens; the first write into a
        shared partial block copies it (copy-on-write). False if the token arena has no room."""
        self._clock(self.now if now is None else now)
        src = self.seqs[parent_rid]
        if child_rid in self.seqs:
            raise ValueError(f"{child_rid} is already admitted")
        if not self.arena.reserve(self._next_sid, src.stored + self.block_size):
            return False
        seq = self._new_seq(child_rid)
        seq.head = fork_chain(src.head)
        node = seq.head
        while node is not None:
            seq.tail, seq.length = node, seq.length + 1
            self._ref(node.val, seq)
            self._event("share", node.val, seq.sid)
            node = node.next
        seq.tokens, seq.hashes = list(src.tokens), list(src.hashes)
        self._write_slots(seq, 0)
        self.stats["forks"] += 1
        self._after()
        return True

    def checkpoint(self, rid: str) -> int:
        """Snapshot ``rid``'s block table and pin its blocks; returns the snapshot id."""
        seq = self.seqs[rid]
        blocks = seq.block_list()
        if seq.hist is None:
            seq.hist = SnapshotTable(self.num_blocks + 1)   # a table never has more blocks than the pool
            seq.hist.set(0, seq.stored)
            for i, b in enumerate(blocks):
                seq.hist.set(i + 1, b)
        snap = seq.hist.snap()
        for b in blocks:
            self._ref(b, seq)
        seq.checkpoints.append(snap)
        self.stats["checkpoints"] += 1
        self._after()
        return snap

    def rollback(self, rid: str, snap: int) -> None:
        """Restore ``rid``'s table exactly as it was at ``snap``; drops that checkpoint and later ones.
        The caller rolls its own token state back to (at least) ``stored_tokens(rid)`` tokens."""
        seq = self.seqs[rid]
        if snap not in seq.checkpoints:
            raise KeyError(f"{rid} has no checkpoint {snap}")
        blocks, n = self._snapshot(seq, snap)
        for b in blocks:                      # the restored table's references (pins keep them alive)
            self._ref(b, seq)
        self._release_table(seq)
        for b in blocks:
            self._append_node(seq, b)
        del seq.tokens[n:]
        del seq.hashes[n // self.block_size:]
        seq.hist.set(0, n)
        self._write_slots(seq, 0)
        for s in [s for s in seq.checkpoints if s >= snap]:
            self._drop_checkpoint(seq, s)
        self.stats["rollbacks"] += 1
        self._after()

    def commit(self, rid: str, snap: int) -> None:
        """Drop checkpoint ``snap`` without rolling back (its pins are released)."""
        self._drop_checkpoint(self.seqs[rid], snap)
        self._after()

    def sanitize(self) -> list[int]:
        """Merge staged releases now; returns the blocks newly quarantined as double frees."""
        before = len(self.quarantine)
        self._flush()
        self._after()
        return self.quarantine[before:]

    def stored_tokens(self, rid: str) -> int:
        return self.seqs[rid].stored

    def block_table(self, rid: str) -> list[int]:
        return self.seqs[rid].block_list()

    # ================================================================== queries
    def owner(self, block: int) -> str:
        """rid the block is charged to right now ("" = nobody)."""
        return self.owners.get(block, self.log.total) if self.log.total else ""

    def owner_at(self, block: int, tick: int) -> str:
        """rid the block was charged to at the end of ``tick`` ("" = nobody)."""
        i = bisect_right(self._ticks, tick) - 1
        return "" if i < 0 else self.owners.get(block, self._tick_ts[i])

    def describe(self, block: int) -> dict:
        ev = self.log.find(self.last_event[block]) if self.last_event[block] else None
        return {"block": block, "refs": self.refs[block], "owner": self.owner(block),
                "last_event": None if ev is None else (ev.ts, ev.tick, ev.kind, ev.sid)}

    def audit_leaks(self) -> list[int]:
        """Blocks marked in use that no block table, checkpoint or cache entry accounts for."""
        marked = [b for b in range(self.num_blocks) if self.bitmap.test(b)]
        lists = [sorted(self.cached)]
        for seq in self.seqs.values():
            if has_cycle(seq.head):
                continue                      # corrupt table: check() reports it
            lists.append(sorted(seq.block_list()))
            for snap in seq.checkpoints:
                lists.append(sorted(self._snapshot(seq, snap)[0]))
        held = [b for b in merge_distinct(lists) if self.bitmap.test(b)]  # dangling refs: check()'s job
        leaks: list[int] = []
        self._bisect_leaks(marked, held, 0, self.num_blocks, leaks)
        return sorted(leaks)

    @staticmethod
    def _bisect_leaks(marked: list[int], held: list[int], lo: int, hi: int, out: list[int]) -> None:
        i, j = bisect_left(marked, lo), bisect_left(marked, hi)
        k, m = bisect_left(held, lo), bisect_left(held, hi)
        missing = (j - i) - (m - k)           # held ⊆ marked, so this counts the leaks in [lo, hi)
        if missing <= 0:
            return
        if missing == 1:                      # every other id appears twice: XOR finds the odd one
            out.append(find_leaked(marked[i:j] + held[k:m]))
            return
        mid = (lo + hi) // 2
        BlockManager._bisect_leaks(marked, held, lo, mid, out)
        BlockManager._bisect_leaks(marked, held, mid, hi, out)

    def check(self, *, leaks: bool = True) -> list[str]:
        """Verify every invariant of the manager; returns the problems found (empty = consistent)."""
        bad: list[str] = []
        n, bs = self.num_blocks, self.block_size
        parts = self.pool.contents()          # read-only: checking must not change behaviour
        if any(a >= b for a, b in zip(parts[0], parts[0][1:])):
            bad.append(f"free list not strictly increasing: {parts[0]}")
        free = merge_distinct(parts)
        pending = sum(map(len, parts)) - len(free)
        if pending:
            bad.append(f"{pending} double-freed block(s) staged, not sanitized yet")
        where: dict[int, str] = {}
        for label, ids in (("free", free), ("cached", list(self.cached)),
                           ("quarantined", [b for b in self.quarantine if not self.refs[b]]),
                           ("in use", [b for b in range(n) if self.refs[b]])):
            for b in ids:
                if b in where:
                    bad.append(f"block {b} is both {where[b]} and {label}")
                where[b] = label
        if len(where) != n:
            bad.append(f"{n - len(where)} blocks are in no state: {sorted(set(range(n)) - set(where))[:10]}")
        for b in range(n):
            marked = self.bitmap.test(b)
            if marked != (where.get(b) in ("in use", "cached")):
                bad.append(f"bitmap bit {b} is {int(marked)} but the block is {where.get(b, 'nowhere')}")
        if self.bitmap.count() != self.in_use + len(self.cached):
            bad.append(f"bitmap counts {self.bitmap.count()} used blocks, expected {self.in_use + len(self.cached)}")
        if self.in_use != sum(1 for r in self.refs if r):
            bad.append("in-use counter out of sync")
        for b in range(n):
            if self.refs[b] != sum(self.holders[b].values()):
                bad.append(f"block {b}: refs {self.refs[b]} != holders {self.holders[b]}")
            dead = [s for s in self.holders[b] if self._rid_of.get(s) not in self.seqs
                    or self.seqs[self._rid_of[s]].sid != s]
            if dead:
                bad.append(f"block {b} still referenced by finished sequence(s) "
                           f"{[self._rid_of.get(s) for s in dead]}")
            if self.refs[b] and self.charge[b] not in self.holders[b]:
                bad.append(f"block {b} charged to sid {self.charge[b]}, not one of its holders")
            if not self.refs[b] and self.charge[b]:
                bad.append(f"block {b} is not in use but charged to sid {self.charge[b]}")
        if sum(charge_counts(self.charge).values()) != self.in_use:
            bad.append("charged blocks != blocks in use")
        if self.in_use:
            top, low = self.refcount.max_key(), self.refcount.min_key()
            used = [r for r in self.refs if r]
            if top == "" or self.refs[top] != max(used) or self.refs[low] != min(used):
                bad.append("RefCounter disagrees with the reference counts")
        for b in self.cached:
            if self.key[b] is None or self.table.get(self.hash_of[b]) != b:
                bad.append(f"cached block {b} is not registered in the dedup table")
        # block tables, checkpoints and the token arena
        expect: dict[tuple[int, int], int] = {}
        live: dict[int, int] = {}
        for rid, seq in self.seqs.items():
            if has_cycle(seq.head):
                bad.append(f"{rid}: block table has a cycle")
                continue
            blocks, prev, node = [], None, seq.head
            while node is not None:
                if node.random is not prev:
                    bad.append(f"{rid}: broken back link at table position {len(blocks)}")
                blocks.append(node.val)
                prev, node = node, node.next
            if prev is not seq.tail or len(blocks) != seq.length:
                bad.append(f"{rid}: tail/length out of sync")
            if len(blocks) != _blocks_for(seq.stored, bs):
                bad.append(f"{rid}: {len(blocks)} blocks for {seq.stored} tokens")
            for i, b in enumerate(blocks):
                if self.content[b] != seq.tokens[i * bs:(i + 1) * bs]:
                    bad.append(f"{rid}: block {b} at position {i} holds other tokens")
            pinned = [self._snapshot(seq, s)[0] for s in seq.checkpoints]
            for b in blocks + [b for p in pinned for b in p]:
                expect[(b, seq.sid)] = expect.get((b, seq.sid), 0) + 1
            live[seq.sid] = seq.stored
        for b in range(n):
            for sid, cnt in self.holders[b].items():
                if expect.pop((b, sid), 0) != cnt:
                    bad.append(f"block {b}: {self._rid_of.get(sid)} holds {cnt} references its tables don't explain")
        if expect:
            bad.append(f"table entries without references: {sorted(expect)[:5]}")
        bad += self.arena.check(live)
        pages = PageTable([b for b in range(n) if self.refs[b]], bs)
        for rid, seq in self.seqs.items():
            if has_cycle(seq.head):
                continue
            blocks = seq.block_list()
            for p in range(seq.stored):
                slot = blocks[p // bs] * bs + p % bs
                try:
                    got = self.arena.read(seq.sid, p)
                except ArenaBoundsError as e:
                    bad.append(f"{rid}: {e}")
                    break
                if got != slot or not pages.mapped(slot):
                    bad.append(f"{rid}: token {p} maps to slot {got}, expected mapped slot {slot}")
                    break
        if leaks:
            for b in self.audit_leaks():
                bad.append(f"leaked block {b}: {self.describe(b)}")
        return bad

    def report(self) -> dict:
        self._close_tick()
        free = merge_distinct(self.pool.contents())   # free list + staged batches, sorted, distinct
        ranges, run = free_summary(free)
        top, low = self.refcount.max_key(), self.refcount.min_key()
        leaks = self.audit_leaks()
        problems = self.check(leaks=False)
        s = self.stats
        hits = s["shared"] + s["revived"] + s["restored"]
        lookups = hits + s["computed"]
        return {
            "num_blocks": self.num_blocks, "block_size": self.block_size, "eviction": self.eviction,
            "free": len(free), "in_use": self.in_use, "cached": len(self.cached),
            "used": self.bitmap.count(), "peak_in_use": self.peak_in_use,
            "quarantined": sorted(self.quarantine),
            "free_ranges": ranges, "largest_free_run": run,
            "most_shared": None if top == "" else [top, self.refs[top]],     # [block, references]
            "least_shared": None if low == "" else [low, self.refs[low]],
            "charged": {self._rid_of[sid]: k for sid, k in charge_counts(self.charge).items()},
            **s,
            "prompt_block_hit_rate": round(hits / lookups, 3) if lookups else None,
            "pool_merges": self.pool.merges, "pool_k_way_merges": self.pool.k_way_merges,
            "arena": self.arena.stats(),
            "events": self.log.total, "oldest_event": self.log.oldest(),
            "recent_events": [(e.ts, e.tick, e.kind, e.block, self._rid_of.get(e.sid, ""))
                              for e in self.log.chronological()[-8:]],
            "leaks": [self.describe(b) for b in leaks],
            "problems": problems,
        }

    # ================================================================== internals: references
    def _new_seq(self, rid: str) -> SeqState:
        seq = SeqState(self._next_sid, rid)
        self._rid_of[seq.sid] = rid
        self._next_sid += 1
        self.seqs[rid] = seq
        return seq

    def _ref(self, b: int, seq: SeqState) -> None:
        if self.refs[b] == 0:
            self.in_use += 1
            self.peak_in_use = max(self.peak_in_use, self.in_use)
        self.refs[b] += 1
        h = self.holders[b]
        h[seq.sid] = h.get(seq.sid, 0) + 1
        self.refcount.inc(b)

    def _unref(self, b: int, seq: SeqState) -> None:
        self.refs[b] -= 1
        h = self.holders[b]
        h[seq.sid] -= 1
        if not h[seq.sid]:
            del h[seq.sid]
        self.refcount.dec(b)
        if self.refs[b] == 0:
            self.in_use -= 1
            self._retire(b)
        elif self.charge[b] == seq.sid and seq.sid not in h:
            nxt = min(h)                       # the charge moves on to another holder
            self.charge[b] = nxt
            self._event("charge", b, nxt, owner=self._rid_of[nxt])

    def _acquire(self, b: int, seq: SeqState, kind: str) -> None:
        self.charge[b] = seq.sid
        self._event(kind, b, seq.sid, owner=seq.rid)

    def _retire(self, b: int) -> None:
        """The last reference is gone: keep the KV as cache if the block is registered, else free it."""
        self.charge[b] = 0
        if b in self._quarantined:             # freed while in use earlier: stays out of circulation
            self._clear(b)
            self._event("drop", b, 0, owner="")
        elif self.key[b] is not None and self.table.get(self.hash_of[b]) == b:
            self.cached[b] = None
            self._event("cache", b, 0, owner="")
        else:
            self._clear(b)
            self._freed.append(b)
            self._event("drop", b, 0, owner="")

    def _clear(self, b: int) -> None:
        if self.hash_of[b] >= 0 and self.table.get(self.hash_of[b]) == b:
            self.table.remove(self.hash_of[b])
        self.content[b] = []
        self.key[b] = None
        self.hash_of[b] = -1
        self.heat[b] = 0
        self.bitmap.clear(b)

    def _register(self, b: int, h: int, key: tuple[int, ...]) -> None:
        self.hash_of[b], self.key[b] = h, key
        if self.table.get(h) == -1:            # first come, first registered (duplicates aren't shared)
            self.table.put(h, b)

    def _lookup(self, h: int, key: tuple[int, ...]) -> int:
        b = self.table.get(h)
        if b >= 0 and self.key[b] == key and (self.refs[b] or b in self.cached):
            return b
        return -1

    def _prompt_blocks(self, tokens: list[int]) -> list[tuple[int, tuple[int, ...], int]]:
        """(chain hash, key, GPU block or -1) for every full prompt block."""
        bs, out, h = self.block_size, [], ROOT_HASH
        for i in range(len(tokens) // bs):
            h = chain_hash(h, tokens[i * bs:(i + 1) * bs])
            key = tuple(tokens[:(i + 1) * bs])
            out.append((h, key, self._lookup(h, key)))
        return out

    # ================================================================== internals: blocks
    def _take_block(self) -> int | None:
        while True:
            b = self.pool.pop()
            if b is None:                      # free list dry: merge staged releases, else evict
                if self.pool.staged_count:
                    self._flush()
                elif self.cached:
                    self._evict(1)
                else:
                    return None
                continue
            if self.bitmap.test(b) or self.refs[b] or b in self._quarantined:
                self._quarantine(b)            # handed back while still in use: never reuse it
                continue
            self.bitmap.set(b)
            return b

    def _must_take(self) -> int:
        b = self._take_block()
        if b is None:
            raise RuntimeError("no KV block left: admit() called although fits() is False")
        return b

    def _evict(self, k: int) -> None:
        """Offload ``k`` cached blocks, cold ones first among the ``scan`` oldest releases."""
        window = list(islice(self.cached, self.scan))
        nodes = [ListNode(min(self.heat[b], HEAT_CAP)) for b in window]
        for a, c in zip(nodes, nodes[1:]):
            a.next = c
        block_of = {id(node): b for node, b in zip(nodes, window)}
        cur, victims = partition_by_heat(nodes[0], self.hot), []
        while cur is not None and len(victims) < k:
            victims.append(block_of[id(cur)])
            cur = cur.next
        for b in victims:
            del self.cached[b]
            self.host.put(self.hash_of[b], checksum(self.key[b]))
            if self._xfer is None:
                self._xfer = FreeRangeTracker()
            self._xfer.add(b)
            self.stats["offloaded"] += 1
            self._event("offload", b, 0)
            self._clear(b)
            self._freed.append(b)
        self._stage_freed()

    def _flush(self) -> None:
        for b in self.pool.flush():
            self._quarantine(b)

    def _quarantine(self, b: int) -> None:
        if b in self.cached:                   # its KV can't be trusted any more
            del self.cached[b]
            self._clear(b)
        if b not in self._quarantined:
            self._quarantined.add(b)
            self.quarantine.append(b)
        self._event("quarantine", b, 0)

    def _stage_freed(self) -> None:
        if self._freed:
            if self.pool.full():
                self._flush()
            self.pool.stage(self._freed)
            self._freed = []

    # ================================================================== internals: tables
    def _append_node(self, seq: SeqState, b: int) -> None:
        node = RandomListNode(b, None, seq.tail)       # random = back link
        if seq.tail is None:
            seq.head = node
        else:
            seq.tail.next = node
        seq.tail = node
        seq.length += 1
        if seq.hist is not None:
            seq.hist.set(seq.length, b)

    def _release_table(self, seq: SeqState) -> None:
        node = seq.tail
        while node is not None:                         # tail → head over the back links
            self._unref(node.val, seq)
            node = node.random
        seq.head = seq.tail = None
        seq.length = 0

    def _store(self, seq: SeqState, ctx: list[int]) -> bool:
        """Store the KV of every context token not stored yet; False if a block or arena slot is missing."""
        bs = self.block_size
        while seq.stored < len(ctx):
            pos = seq.stored
            off = pos % bs
            if pos >= self.arena.capacity(seq.sid) and not self.arena.reserve(seq.sid, bs):
                return False
            if off == 0:
                b = self._take_block()
                if b is None:
                    return False
                self._ref(b, seq)
                self._acquire(b, seq, "alloc")
                self._append_node(seq, b)
                self.stats["decode_blocks"] += 1
            elif self.refs[seq.tail.val] > 1 and not self._copy_on_write(seq):
                return False
            b = seq.tail.val
            self.content[b].append(ctx[pos])
            seq.tokens.append(ctx[pos])
            if seq.hist is not None:
                seq.hist.set(0, seq.stored)
            self.arena.write(seq.sid, pos, b * bs + off)
            if off == bs - 1:                           # the block just filled up: make it shareable
                parent = seq.hashes[-1] if seq.hashes else ROOT_HASH
                h = chain_hash(parent, seq.tokens[pos + 1 - bs:])
                seq.hashes.append(h)
                self._register(b, h, tuple(seq.tokens))
        return True

    def _copy_on_write(self, seq: SeqState) -> bool:
        """The tail block is shared and we're about to write into it: switch to a private copy."""
        old = seq.tail.val
        nb = self._take_block()
        if nb is None:
            return False
        start = (seq.length - 1) * self.block_size
        self.content[nb] = self.content[old][:seq.stored - start]
        seq.tail.val = nb
        self._ref(nb, seq)
        self._acquire(nb, seq, "cow")
        self._unref(old, seq)
        if seq.hist is not None:
            seq.hist.set(seq.length, nb)
        self._write_slots(seq, start)
        self.stats["cow"] += 1
        return True

    def _snapshot(self, seq: SeqState, snap: int) -> tuple[list[int], int]:
        n = seq.hist.get(0, snap)
        return [seq.hist.get(i + 1, snap) for i in range(_blocks_for(n, self.block_size))], n

    def _drop_checkpoint(self, seq: SeqState, snap: int) -> None:
        blocks, _ = self._snapshot(seq, snap)
        seq.checkpoints.remove(snap)
        for b in reversed(blocks):
            self._unref(b, seq)

    def _write_slots(self, seq: SeqState, start: int) -> None:
        """(Re)write the arena entries of tokens ``start..stored-1`` from the block table."""
        bs, blocks = self.block_size, seq.block_list()
        for p in range(start, seq.stored):
            self.arena.write(seq.sid, p, blocks[p // bs] * bs + p % bs)

    # ================================================================== internals: misc
    def _encode(self, req: Request) -> list[int] | None:
        """Token ids of a waiting request's prompt (the server only tells us their number), or None
        if our tokenizer disagrees with the server's (then admission assumes no sharing)."""
        if req.state is not None:
            return list(req.state.prompt_ids)
        if req.prompt not in self._enc:
            if self._tok is None:
                from nanoserve.tokenizer.tokenizer import Tokenizer
                self._tok = Tokenizer()
            try:
                self._enc[req.prompt] = self._tok.encode(req.prompt)
            except ValueError:
                self._enc[req.prompt] = []
        ids = self._enc[req.prompt]
        return ids if ids and (not req.prompt_tokens or len(ids) == req.prompt_tokens) else None

    def _clock(self, now: int) -> None:
        if now > self.now:
            self._close_tick()
            self.now = now

    def _close_tick(self) -> None:
        if self._xfer is not None:              # one transfer per contiguous range of offloaded blocks
            self.stats["transfers"] += len(self._xfer.ranges())
            self._xfer = None

    def _event(self, kind: str, b: int, sid: int, owner: str | None = None) -> int:
        ts = self.log.append(self.now, kind, b, sid)
        self.last_event[b] = ts
        if self._ticks and self._ticks[-1] == self.now:
            self._tick_ts[-1] = ts
        else:
            self._ticks.append(self.now)
            self._tick_ts.append(ts)
        if owner is not None:
            self.owners.set(b, owner, ts)
        return ts

    def _after(self) -> None:
        self._stage_freed()
        if self.debug:
            problems = self.check()
            if problems:
                raise AssertionError("KV invariants violated:\n  " + "\n  ".join(problems))
