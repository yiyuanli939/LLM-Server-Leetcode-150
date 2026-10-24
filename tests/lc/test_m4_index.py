"""M4 core exercises: deadline BST index and the complete-tree priority queue."""
import random

import pytest

from nanoserve.common.nodes import TreeNode, tree_from_level, tree_to_level
from nanoserve.index.deadline import DeadlineIterator, build_balanced, is_valid_index, kth_earliest, min_gap


# ---------------------------------------------------------------- helpers

def _bst_from(values):
    """Insert values in the given order into an (unbalanced) BST; values must be distinct."""
    root = None
    for v in values:
        node = TreeNode(v)
        if root is None:
            root = node
            continue
        cur = root
        while True:
            if v < cur.val:
                if cur.left is None:
                    cur.left = node
                    break
                cur = cur.left
            else:
                if cur.right is None:
                    cur.right = node
                    break
                cur = cur.right
    return root


def _inorder(root):
    return [] if root is None else _inorder(root.left) + [root.val] + _inorder(root.right)


def _height(root):
    return 0 if root is None else 1 + max(_height(root.left), _height(root.right))


def _random_bst(rng, n, lo=-1000, hi=1000):
    vals = rng.sample(range(lo, hi + 1), n)
    return _bst_from(vals), sorted(vals)


class _CountingNode(TreeNode):
    """TreeNode whose child accesses are counted, to detect O(n) traversals."""

    __slots__ = ("_l", "_r")
    reads = 0

    def __init__(self, val):
        object.__setattr__(self, "_l", None)
        object.__setattr__(self, "_r", None)
        super().__init__(val)

    @property
    def left(self):
        _CountingNode.reads += 1
        return self._l

    @left.setter
    def left(self, v):
        self._l = v

    @property
    def right(self):
        _CountingNode.reads += 1
        return self._r

    @right.setter
    def right(self, v):
        self._r = v


# ---------------------------------------------------------------- index.iter

@pytest.mark.exercise("index.iter")
def test_index_iter_example():
    it = DeadlineIterator(tree_from_level([7, 3, 15, None, None, 9, 20]))
    assert it.next() == 3
    assert it.next() == 7
    assert it.has_next() is True
    assert it.next() == 9
    assert it.has_next() is True
    assert it.next() == 15
    assert it.has_next() is True
    assert it.next() == 20
    assert it.has_next() is False


@pytest.mark.exercise("index.iter")
def test_index_iter_empty():
    assert DeadlineIterator(None).has_next() is False


@pytest.mark.exercise("index.iter")
def test_index_iter_single_and_repeat_has_next():
    it = DeadlineIterator(TreeNode(-5))
    assert it.has_next() is True
    assert it.has_next() is True
    assert it.next() == -5
    assert it.has_next() is False
    assert it.has_next() is False


@pytest.mark.exercise("index.iter")
def test_index_iter_skewed():
    it = DeadlineIterator(_bst_from([5, 4, 3, 2, 1]))
    assert [it.next() for _ in range(5)] == [1, 2, 3, 4, 5]
    it = DeadlineIterator(_bst_from([1, 2, 3, 4, 5]))
    assert [it.next() for _ in range(5)] == [1, 2, 3, 4, 5]
    assert it.has_next() is False


@pytest.mark.exercise("index.iter")
def test_index_iter_random():
    rng = random.Random(4201)
    for _ in range(80):
        root, expect = _random_bst(rng, rng.randint(0, 60))
        it = DeadlineIterator(root)
        got = []
        while it.has_next():
            got.append(it.next())
            if rng.random() < 0.3:
                it.has_next()
        assert got == expect


# ---------------------------------------------------------------- index.kth

@pytest.mark.exercise("index.kth")
def test_index_kth_example():
    assert kth_earliest(tree_from_level([3, 1, 4, None, 2]), 1) == 1


@pytest.mark.exercise("index.kth")
def test_index_kth_second_example():
    assert kth_earliest(tree_from_level([5, 3, 6, 2, 4, None, None, 1]), 3) == 3


@pytest.mark.exercise("index.kth")
def test_index_kth_single():
    assert kth_earliest(TreeNode(0), 1) == 0


@pytest.mark.exercise("index.kth")
def test_index_kth_last_and_negative():
    root = _bst_from([0, -5, 5, -10, -1, 1, 10])
    assert kth_earliest(root, 7) == 10
    assert kth_earliest(root, 1) == -10
    assert kth_earliest(root, 4) == 0


@pytest.mark.exercise("index.kth")
def test_index_kth_random():
    rng = random.Random(4202)
    for _ in range(80):
        n = rng.randint(1, 60)
        root, sorted_vals = _random_bst(rng, n)
        for k in {1, n, rng.randint(1, n)}:
            assert kth_earliest(root, k) == sorted_vals[k - 1]


# ---------------------------------------------------------------- index.validate

@pytest.mark.exercise("index.validate")
def test_index_validate_example_valid():
    assert is_valid_index(tree_from_level([2, 1, 3])) is True


@pytest.mark.exercise("index.validate")
def test_index_validate_example_invalid():
    assert is_valid_index(tree_from_level([5, 1, 4, None, None, 3, 6])) is False


@pytest.mark.exercise("index.validate")
def test_index_validate_deep_violation():
    assert is_valid_index(tree_from_level([5, 4, 6, None, None, 3, 7])) is False


@pytest.mark.exercise("index.validate")
def test_index_validate_duplicates_invalid():
    assert is_valid_index(tree_from_level([2, 2, 2])) is False
    assert is_valid_index(tree_from_level([1, 1])) is False
    assert is_valid_index(tree_from_level([1, None, 1])) is False


@pytest.mark.exercise("index.validate")
def test_index_validate_empty_single_extremes():
    assert is_valid_index(None) is True
    assert is_valid_index(TreeNode(0)) is True
    assert is_valid_index(tree_from_level([2**31 - 1])) is True
    assert is_valid_index(tree_from_level([-(2**31), None, 2**31 - 1])) is True
    assert is_valid_index(tree_from_level([2**31 - 1, 2**31 - 1])) is False


@pytest.mark.exercise("index.validate")
def test_index_validate_random():
    rng = random.Random(4203)
    for _ in range(200):
        n = rng.randint(1, 25)
        root, _ = _random_bst(rng, n, -50, 50)
        if rng.random() < 0.6:
            # corrupt a random node's value
            nodes, stack = [], [root]
            while stack:
                x = stack.pop()
                if x is not None:
                    nodes.append(x)
                    stack.extend((x.left, x.right))
            rng.choice(nodes).val = rng.randint(-55, 55)
        vals = _inorder(root)
        expect = all(a < b for a, b in zip(vals, vals[1:]))
        assert is_valid_index(root) == expect


# ---------------------------------------------------------------- index.min_gap

@pytest.mark.exercise("index.min_gap")
def test_index_min_gap_example():
    assert min_gap(tree_from_level([4, 2, 6, 1, 3])) == 1


@pytest.mark.exercise("index.min_gap")
def test_index_min_gap_second_example():
    assert min_gap(tree_from_level([1, 0, 48, None, None, 12, 49])) == 1


@pytest.mark.exercise("index.min_gap")
def test_index_min_gap_two_nodes():
    assert min_gap(tree_from_level([10, None, 100000])) == 99990


@pytest.mark.exercise("index.min_gap")
def test_index_min_gap_across_levels():
    # closest pair is root (236) and a deep node (227) not adjacent as parent/child
    root = _bst_from([236, 104, 701, 227, 911])
    assert min_gap(root) == 9


@pytest.mark.exercise("index.min_gap")
def test_index_min_gap_random():
    rng = random.Random(4204)
    for _ in range(100):
        n = rng.randint(2, 50)
        root, s = _random_bst(rng, n, 0, 10000)
        assert min_gap(root) == min(b - a for a, b in zip(s, s[1:]))


# ---------------------------------------------------------------- index.build

def _assert_balanced_bst(root, vals):
    assert _inorder(root) == vals

    def check(node):
        if node is None:
            return 0
        lh, rh = check(node.left), check(node.right)
        assert abs(lh - rh) <= 1, f"unbalanced at {node.val}: {lh} vs {rh}"
        return 1 + max(lh, rh)

    check(root)


@pytest.mark.exercise("index.build")
def test_index_build_example():
    vals = [-10, -3, 0, 5, 9]
    _assert_balanced_bst(build_balanced(vals), vals)


@pytest.mark.exercise("index.build")
def test_index_build_two():
    vals = [1, 3]
    root = build_balanced(vals)
    _assert_balanced_bst(root, vals)
    assert tree_to_level(root) in ([1, None, 3], [3, 1])


@pytest.mark.exercise("index.build")
def test_index_build_empty_and_single():
    assert build_balanced([]) is None
    assert tree_to_level(build_balanced([7])) == [7]


@pytest.mark.exercise("index.build")
def test_index_build_perfect_size():
    vals = list(range(-7, 8))  # 15 values -> must be a perfect tree of height 4
    root = build_balanced(vals)
    _assert_balanced_bst(root, vals)
    assert _height(root) == 4


@pytest.mark.exercise("index.build")
def test_index_build_random():
    rng = random.Random(4205)
    for _ in range(100):
        n = rng.randint(0, 200)
        vals = sorted(rng.sample(range(-10000, 10001), n))
        _assert_balanced_bst(build_balanced(vals), vals)
