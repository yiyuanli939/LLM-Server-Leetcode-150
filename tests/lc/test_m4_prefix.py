"""M4 core exercises: prefix trie, wildcard index and cache-tree operations."""
import random

import pytest

from nanoserve.common.nodes import TreeNode, find_tree_node, tree_from_level, tree_to_level
from nanoserve.prefix.dump import level_dump
from nanoserve.prefix.snapshot import same_tree
from nanoserve.prefix.tree_ops import fork_point, max_depth
from nanoserve.prefix.trie import PrefixTrie


# ---------------------------------------------------------------- helpers

def _random_tree(rng, n, lo=-20, hi=20, distinct=False):
    """Random-shaped binary tree with n nodes (values distinct if requested)."""
    if n == 0:
        return None
    vals = rng.sample(range(lo, hi + 1), n) if distinct else [rng.randint(lo, hi) for _ in range(n)]
    root = TreeNode(vals[0])
    nodes = [root]
    for v in vals[1:]:
        while True:
            parent = rng.choice(nodes)
            side = rng.choice(("left", "right"))
            if getattr(parent, side) is None:
                child = TreeNode(v)
                setattr(parent, side, child)
                nodes.append(child)
                break
    return root


def _all_nodes(root):
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        out.append(n)
        stack.extend((n.right, n.left))
    return out


def _preorder(root):
    return [] if root is None else [root.val] + _preorder(root.left) + _preorder(root.right)


def _inorder(root):
    return [] if root is None else _inorder(root.left) + [root.val] + _inorder(root.right)


def _postorder(root):
    return [] if root is None else _postorder(root.left) + _postorder(root.right) + [root.val]


def _levels_oracle(root):
    if root is None:
        return []
    out, cur = [], [root]
    while cur:
        out.append([n.val for n in cur])
        cur = [c for n in cur for c in (n.left, n.right) if c is not None]
    return out


def _leaf_paths(root):
    if root is None:
        return []
    if root.left is None and root.right is None:
        return [[root.val]]
    return [[root.val] + p for c in (root.left, root.right) for p in _leaf_paths(c)]


def _clone(root):
    if root is None:
        return None
    return TreeNode(root.val, _clone(root.left), _clone(root.right))


# ---------------------------------------------------------------- prefix.trie

@pytest.mark.exercise("prefix.trie")
def test_prefix_trie_example():
    t = PrefixTrie()
    t.insert("apple")
    assert t.search("apple") is True
    assert t.search("app") is False
    assert t.starts_with("app") is True
    t.insert("app")
    assert t.search("app") is True


@pytest.mark.exercise("prefix.trie")
def test_prefix_trie_empty():
    t = PrefixTrie()
    assert t.search("a") is False
    assert t.starts_with("a") is False


@pytest.mark.exercise("prefix.trie")
def test_prefix_trie_longer_than_key():
    t = PrefixTrie()
    t.insert("ab")
    assert t.search("abc") is False
    assert t.starts_with("abc") is False
    assert t.starts_with("ab") is True
    assert t.search("a") is False
    assert t.starts_with("a") is True


@pytest.mark.exercise("prefix.trie")
def test_prefix_trie_duplicates_and_branches():
    t = PrefixTrie()
    for w in ["car", "car", "cart", "cat", "dog"]:
        t.insert(w)
    assert t.search("car") and t.search("cart") and t.search("cat") and t.search("dog")
    assert not t.search("ca") and not t.search("do") and not t.search("carts")
    assert t.starts_with("ca") and t.starts_with("d") and not t.starts_with("e")


@pytest.mark.exercise("prefix.trie")
def test_prefix_trie_random_ops():
    rng = random.Random(4101)
    t = PrefixTrie()
    words = set()
    for _ in range(2000):
        w = "".join(rng.choice("abc") for _ in range(rng.randint(1, 5)))
        op = rng.randrange(3)
        if op == 0:
            t.insert(w)
            words.add(w)
        elif op == 1:
            assert t.search(w) == (w in words)
        else:
            assert t.starts_with(w) == any(x.startswith(w) for x in words)


@pytest.mark.exercise("prefix.trie")
def test_prefix_trie_arbitrary_characters():
    t = PrefixTrie()
    t.insert("Sys: héllo, wörld! €5")
    assert t.starts_with("Sys: hé") and t.starts_with("Sys: héllo, wörld! €5")
    assert not t.search("Sys: héllo") and not t.starts_with("sys") and not t.starts_with("Sys:  ")
    t.insert("a$")                      # characters often used as sentinels are ordinary characters here
    t.insert("#")
    t.insert("x\ny\t")
    t.insert("\ue000\ue001")
    assert t.search("a$") and not t.search("a") and t.starts_with("a")
    assert t.search("#") and not t.starts_with("#!")
    assert t.search("x\ny\t") and t.starts_with("x\n") and not t.search("x\n")
    assert t.search("\ue000\ue001") and t.starts_with("\ue000") and not t.search("\ue000")
    assert not t.starts_with("A")       # case-sensitive


@pytest.mark.exercise("prefix.trie")
def test_prefix_trie_random_mixed_alphabet():
    rng = random.Random(4102)
    alphabet = "aA $#.,\n é漢€\ue000"
    t = PrefixTrie()
    words = set()
    for _ in range(3000):
        w = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 5)))
        op = rng.randrange(3)
        if op == 0:
            t.insert(w)
            words.add(w)
        elif op == 1:
            assert t.search(w) == (w in words)
        else:
            assert t.starts_with(w) == any(x.startswith(w) for x in words)


# ---------------------------------------------------------------- prefix.fork_point

FORK_TREE = [3, 5, 1, 6, 2, 0, 8, None, None, 7, 4]


@pytest.mark.exercise("prefix.fork_point")
def test_prefix_fork_point_example_root():
    root = tree_from_level(FORK_TREE)
    p, q = find_tree_node(root, 5), find_tree_node(root, 1)
    assert fork_point(root, p, q) is root


@pytest.mark.exercise("prefix.fork_point")
def test_prefix_fork_point_ancestor_is_answer():
    root = tree_from_level(FORK_TREE)
    p, q = find_tree_node(root, 5), find_tree_node(root, 4)
    assert fork_point(root, p, q) is p
    assert fork_point(root, q, p) is p


@pytest.mark.exercise("prefix.fork_point")
def test_prefix_fork_point_two_nodes():
    root = tree_from_level([1, 2])
    assert fork_point(root, root, root.left) is root


@pytest.mark.exercise("prefix.fork_point")
def test_prefix_fork_point_deep_subtree():
    root = tree_from_level(FORK_TREE)
    p, q = find_tree_node(root, 7), find_tree_node(root, 6)
    assert fork_point(root, p, q) is find_tree_node(root, 5)
    p, q = find_tree_node(root, 0), find_tree_node(root, 8)
    assert fork_point(root, p, q) is find_tree_node(root, 1)


@pytest.mark.exercise("prefix.fork_point")
def test_prefix_fork_point_random():
    rng = random.Random(4103)
    for _ in range(150):
        n = rng.randint(2, 40)
        root = _random_tree(rng, n, -100, 100, distinct=True)
        parent = {id(root): None}
        for node in _all_nodes(root):
            for c in (node.left, node.right):
                if c is not None:
                    parent[id(c)] = node
        nodes = _all_nodes(root)
        p, q = rng.sample(nodes, 2)
        anc = set()
        x = p
        while x is not None:
            anc.add(id(x))
            x = parent[id(x)]
        y = q
        while id(y) not in anc:
            y = parent[id(y)]
        assert fork_point(root, p, q) is y


# ---------------------------------------------------------------- prefix.depth

@pytest.mark.exercise("prefix.depth")
def test_prefix_depth_example():
    assert max_depth(tree_from_level([3, 9, 20, None, None, 15, 7])) == 3


@pytest.mark.exercise("prefix.depth")
def test_prefix_depth_right_only():
    assert max_depth(tree_from_level([1, None, 2])) == 2


@pytest.mark.exercise("prefix.depth")
def test_prefix_depth_empty_and_single():
    assert max_depth(None) == 0
    assert max_depth(TreeNode(0)) == 1


@pytest.mark.exercise("prefix.depth")
def test_prefix_depth_skewed_chain():
    root = TreeNode(0)
    cur = root
    for i in range(1, 50):
        cur.left = TreeNode(i)
        cur = cur.left
    assert max_depth(root) == 50


@pytest.mark.exercise("prefix.depth")
def test_prefix_depth_random():
    rng = random.Random(4104)
    for _ in range(100):
        root = _random_tree(rng, rng.randint(0, 40))
        assert max_depth(root) == len(_levels_oracle(root))


# ---------------------------------------------------------------- prefix.level_dump

@pytest.mark.exercise("prefix.level_dump")
def test_prefix_level_dump_example():
    assert level_dump(tree_from_level([3, 9, 20, None, None, 15, 7])) == [[3], [9, 20], [15, 7]]


@pytest.mark.exercise("prefix.level_dump")
def test_prefix_level_dump_single():
    assert level_dump(tree_from_level([1])) == [[1]]


@pytest.mark.exercise("prefix.level_dump")
def test_prefix_level_dump_empty():
    assert level_dump(None) == []


@pytest.mark.exercise("prefix.level_dump")
def test_prefix_level_dump_gaps_and_duplicates():
    root = tree_from_level([1, 2, 2, None, 3, None, 3, 4])
    assert level_dump(root) == [[1], [2, 2], [3, 3], [4]]


@pytest.mark.exercise("prefix.level_dump")
def test_prefix_level_dump_random():
    rng = random.Random(4105)
    for _ in range(100):
        root = _random_tree(rng, rng.randint(0, 40))
        assert level_dump(root) == _levels_oracle(root)


PATH_TREE = [5, 4, 8, 11, None, 13, 4, 7, 2, None, None, None, 1]


# ---------------------------------------------------------------- prefix.same_snapshot

@pytest.mark.exercise("prefix.same_snapshot")
def test_prefix_same_snapshot_equal():
    assert same_tree(tree_from_level([1, 2, 3]), tree_from_level([1, 2, 3])) is True


@pytest.mark.exercise("prefix.same_snapshot")
def test_prefix_same_snapshot_shape_differs():
    assert same_tree(tree_from_level([1, 2]), tree_from_level([1, None, 2])) is False


@pytest.mark.exercise("prefix.same_snapshot")
def test_prefix_same_snapshot_values_differ():
    assert same_tree(tree_from_level([1, 2, 1]), tree_from_level([1, 1, 2])) is False


@pytest.mark.exercise("prefix.same_snapshot")
def test_prefix_same_snapshot_empty():
    assert same_tree(None, None) is True
    assert same_tree(TreeNode(0), None) is False
    assert same_tree(None, TreeNode(0)) is False


@pytest.mark.exercise("prefix.same_snapshot")
def test_prefix_same_snapshot_random():
    rng = random.Random(4112)
    for _ in range(150):
        a = _random_tree(rng, rng.randint(0, 12), 0, 2)
        b = _clone(a) if rng.random() < 0.5 else _random_tree(rng, rng.randint(0, 12), 0, 2)
        assert same_tree(a, b) == (tree_to_level(a) == tree_to_level(b))


