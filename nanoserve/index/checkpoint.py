"""Framework (M4): checkpoint / restore of the deadline index.

Two on-disk forms of the same tree:

  * compact — the preorder key list, ``"P:" + ",".join(keys)``. A BST with distinct keys is fully
    determined by its preorder sequence, so ``bst_from_preorder`` rebuilds the *identical* shape in O(n).
  * generic — ``"T:" + TreeCodec().serialize(root)``: any binary tree, no BST assumption; useful to
    dump an index for debugging even when it is (suspected to be) corrupted.

A checkpoint is only trusted after a read-back: ``verify`` reloads it and compares it node by node with
the live tree (``same_tree``)::

    blob = dump_index(q.index.root)                 # compact by default
    assert verify(q.index.root, blob)
    ckpt = checkpoint_queue(q)                       # whole waiting queue (index + key owners)
    q2 = restore_queue(ckpt, requests)               # same order, same tree shape, check() == []

Exercises this file calls (M4): index.restore, prefix.codec, prefix.same_snapshot
(and, with ``restore_queue(repair=True)``, prefix.fork_point through ``BSTIndex.repair``)
(and, through ``DeadlineQueue.check``, the index audit: index.validate, index.iter, prefix.depth).
"""
from __future__ import annotations

from typing import Iterable

from nanoserve.common.nodes import TreeNode
from nanoserve.index.bst_ops import bst_from_preorder
from nanoserve.index.queue import DeadlineQueue
from nanoserve.prefix.codec import TreeCodec
from nanoserve.prefix.snapshot import same_tree
from nanoserve.server.request import Request

FORMATS = ("preorder", "codec")


def preorder(root: TreeNode | None) -> list[int]:
    """Root, left subtree, right subtree — iteratively (a skewed index may be deep)."""
    out, stack = [], [root]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        out.append(node.val)
        stack.append(node.right)
        stack.append(node.left)
    return out


def dump_index(root: TreeNode | None, fmt: str = "preorder") -> str:
    """Serialize the index tree: ``fmt`` = "preorder" (compact, BST only) or "codec" (any binary tree)."""
    if fmt == "preorder":
        return "P:" + ",".join(map(str, preorder(root)))
    if fmt == "codec":
        return "T:" + TreeCodec().serialize(root)
    raise ValueError(f"unknown checkpoint format {fmt!r}")


def load_index(blob: str) -> TreeNode | None:
    """Inverse of ``dump_index`` (the format is read from the tag)."""
    tag, _, body = blob.partition(":")
    if tag == "P":
        return bst_from_preorder([int(x) for x in body.split(",")] if body else [])
    if tag == "T":
        return TreeCodec().deserialize(body)
    raise ValueError(f"not an index checkpoint: {blob[:20]!r}")


def verify(root: TreeNode | None, blob: str) -> bool:
    """Does ``blob`` restore to exactly this tree (same shape, same keys)?"""
    return same_tree(root, load_index(blob))


def checkpoint_queue(q: DeadlineQueue, fmt: str = "preorder") -> dict:
    """Everything needed to rebuild a waiting queue: the index tree + which request owns which key.

    Raises if the written index does not read back identically.
    """
    ckpt = {
        "format": fmt,
        "index": dump_index(q.index.root, fmt),
        "owners": {str(k): r.rid for k, r in q.owners().items()},
        "seqs": {r.rid: seq for r, seq in q.sequence_numbers().items()},  # incl. running requests
        "next_seq": q._next_seq,
    }
    if not verify(q.index.root, ckpt["index"]):
        raise RuntimeError("index checkpoint failed its read-back check")
    return ckpt


def restore_queue(ckpt: dict, requests: Iterable[Request], *, repair: bool = False) -> DeadlineQueue:
    """Rebuild a ``DeadlineQueue`` from ``checkpoint_queue`` output; ``requests`` supplies objects by rid.

    The index keeps its exact checkpointed shape (no re-insertion); the restored queue is audited.
    ``repair=True``: if the index came back with the right keys in the wrong order (a corrupted
    checkpoint), fix it in place (``BSTIndex.repair``) before the audit instead of refusing it.
    """
    by_rid = {r.rid: r for r in requests}
    owners = {int(k): by_rid[rid] for k, rid in ckpt["owners"].items()}
    seqs = {by_rid[rid]: seq for rid, seq in ckpt["seqs"].items() if rid in by_rid}
    q = DeadlineQueue.from_index(load_index(ckpt["index"]), owners, seqs, ckpt["next_seq"])
    if repair:
        q.repaired = q.index.repair()
    problems = q.check()
    if problems:
        raise ValueError("restored queue is inconsistent: " + "; ".join(problems))
    return q
