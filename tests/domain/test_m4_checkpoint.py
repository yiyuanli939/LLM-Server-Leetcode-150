"""M4 integration: checkpoint / restore of the deadline index (nanoserve.index.checkpoint)."""
import random

import pytest

from nanoserve.common.nodes import TreeNode
from nanoserve.engine import Engine
from nanoserve.index.checkpoint import (FORMATS, checkpoint_queue, dump_index, load_index, preorder,
                                        restore_queue, verify)
from nanoserve.index.queue import DeadlineQueue
from nanoserve.index.workloads import deadline_trace
from nanoserve.server.request import Request
from nanoserve.server.server import Server, ServerConfig

pytestmark = pytest.mark.milestone("M4")


def _shape(root):
    """(val, left-shape, right-shape) nested tuples, iteratively-safe for our sizes."""
    return None if root is None else (root.val, _shape(root.left), _shape(root.right))


def _random_queue(seed, n=120):
    rng = random.Random(seed)
    q = DeadlineQueue()
    reqs = [Request(rid=f"c{i:03d}", prompt="The", arrival=i, max_tokens=rng.randint(1, 20),
                    deadline=None if rng.random() < 0.1 else rng.randint(0, 300)) for i in range(n)]
    for r in reqs:
        q.push(r)
        if rng.random() < 0.3:
            q.remove(rng.choice(list(q)))
    return q, reqs


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("seed", [0, 1])
def test_index_checkpoint_round_trip_is_exact(fmt, seed):
    q, _ = _random_queue(seed)
    blob = dump_index(q.index.root, fmt)
    back = load_index(blob)
    assert _shape(back) == _shape(q.index.root)                      # same shape, same keys
    assert verify(q.index.root, blob)                                # same_tree read-back check
    assert dump_index(back, fmt) == blob


def test_verify_detects_a_different_tree():
    q, _ = _random_queue(2)
    blob = dump_index(q.index.root, "preorder")
    q.pop()
    assert not verify(q.index.root, blob)
    assert verify(None, dump_index(None, "preorder")) and verify(None, dump_index(None, "codec"))


def test_codec_dumps_a_tree_that_is_not_a_bst():
    # e.g. a corrupted index: the generic format must still round-trip it exactly
    root = TreeNode(5, TreeNode(9, TreeNode(-3)), TreeNode(5, None, TreeNode(-3)))
    blob = dump_index(root, "codec")
    assert verify(root, blob)
    assert preorder(load_index(blob)) == [5, 9, -3, 5, -3]


@pytest.mark.parametrize("fmt", FORMATS)
def test_restore_waiting_queue_mid_run_and_resume(fmt):
    """Pause an EDF server, checkpoint its waiting queue, restore it into a fresh queue, swap it in and finish:
    the run must be indistinguishable from an uninterrupted one."""
    engine = Engine()

    def server():
        s = Server(engine, ServerConfig(max_batch=2, policy="edf"))
        s.submit_many(deadline_trace(seed=3))
        return s

    ref = server().run()
    s = server()
    s.run(max_ticks=9)
    assert len(s.queue) > 5
    ckpt = checkpoint_queue(s.queue, fmt)
    restored = restore_queue(ckpt, s.requests)
    assert _shape(restored.index.root) == _shape(s.queue.index.root)
    assert [r.rid for r in restored] == [r.rid for r in s.queue]
    assert restored.check() == []
    s.queue = restored
    rep = s.run()
    assert rep.outputs() == ref.outputs()
    assert {r.rid: (r.admitted_at, r.finished_at) for r in rep.requests} == \
           {r.rid: (r.admitted_at, r.finished_at) for r in ref.requests}


def _all_nodes(root):
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        if n is not None:
            out.append(n)
            stack += [n.left, n.right]
    return out


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_corrupted_checkpoint_with_two_swapped_keys_is_repaired_on_restore(seed):
    """A codec checkpoint whose writer swapped two keys: refused by default; with repair=True the
    damage is localised (lowest common ancestor of the two out-of-order nodes) and only that subtree
    is rewritten — the restored queue pops in exactly the original order."""
    q, reqs = _random_queue(seed)
    ckpt = checkpoint_queue(q, "codec")
    rng = random.Random(seed)
    root = load_index(ckpt["index"])
    nodes = _all_nodes(root)
    a, b = rng.sample(nodes, 2)
    a.val, b.val = b.val, a.val
    bad = dict(ckpt, index=dump_index(root, "codec"))

    with pytest.raises(ValueError):
        restore_queue(bad, reqs)
    fixed = restore_queue(bad, reqs, repair=True)
    assert fixed.check() == []
    assert 2 <= fixed.repaired <= len(nodes)
    assert [r.rid for r in fixed] == [r.rid for r in q]          # same EDF order as before the damage
    healthy = restore_queue(ckpt, reqs, repair=True)
    assert healthy.repaired == 0 and [r.rid for r in healthy] == [r.rid for r in q]


def test_repair_only_touches_the_damaged_subtree():
    from nanoserve.index.bst_index import BSTIndex
    idx = BSTIndex()
    for k in (50, 25, 75, 10, 30, 60, 90, 5, 15):
        idx.add(k)
    left = idx.root.left                       # subtree of 25: keys 5, 10, 15, 25, 30
    a, b = left.left.left, left.right          # 5 and 30, both under 25
    a.val, b.val = b.val, a.val
    right_before = _shape(idx.root.right)
    assert idx.check() != []
    assert idx.repair() == 2                   # only the two swapped nodes change
    assert idx.check() == [] and _shape(idx.root.right) == right_before
    assert list(idx.keys()) == [5, 10, 15, 25, 30, 50, 60, 75, 90]
