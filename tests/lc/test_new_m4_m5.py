"""M4/M5 exercises: deadline-index insert/delete/restore, operator reachability, config preprocessing."""
import contextlib
import random
import signal
import threading

import pytest

from nanoserve.common.nodes import TreeNode, tree_from_level, tree_to_level
from nanoserve.config.comments import strip_comments
from nanoserve.config.flags import eval_flag_expr
from nanoserve.config.glob import glob_match
from nanoserve.index.bst_ops import bst_from_preorder, delete_key, insert_key
from nanoserve.ir.reach import computable_outputs, depends_queries


# ---------------------------------------------------------------- helpers

@contextlib.contextmanager
def _time_limit(seconds):
    """Fail (instead of hanging) when the code under test is asymptotically too slow.

    Uses SIGALRM where available (POSIX main thread); elsewhere it is a no-op.
    """
    if not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread():
        yield
        return

    def on_alarm(signum, frame):
        pytest.fail(f"took longer than {seconds}s: the required complexity is not met", pytrace=False)

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


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


def _nodes(root):
    """All node objects of the tree; fails if a node is reachable twice (cycle / shared subtree)."""
    seen, out, stack = set(), [], [root]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        assert id(n) not in seen, "a node is reachable twice: result is not a tree"
        seen.add(id(n))
        out.append(n)
        stack.append(n.right)
        stack.append(n.left)
    return out


def _inorder(root):
    _nodes(root)  # structural sanity first, so a cycle fails cleanly
    out, stack, node = [], [], root
    while stack or node is not None:
        while node is not None:
            stack.append(node)
            node = node.left
        node = stack.pop()
        out.append(node.val)
        node = node.right
    return out


def _preorder(root):
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        out.append(n.val)
        stack.append(n.right)
        stack.append(n.left)
    return out


def _is_bst(root):
    stack = [(root, float("-inf"), float("inf"))]
    while stack:
        n, lo, hi = stack.pop()
        if n is None:
            continue
        if not lo < n.val < hi:
            return False
        stack.append((n.left, lo, n.val))
        stack.append((n.right, n.val, hi))
    return True


# ---------------------------------------------------------------- index.insert

def _check_insert(root, val):
    before = [(n, n.val) for n in _nodes(root)]
    expect = sorted([v for _, v in before] + [val])
    new_root = insert_key(root, val)
    after = _nodes(new_root)
    assert len(after) == len(before) + 1
    ids = {id(n) for n in after}
    for n, v in before:
        assert id(n) in ids, "an existing index node was dropped or replaced"
        assert n.val == v, "an existing node's value was changed"
    assert _is_bst(new_root)
    assert _inorder(new_root) == expect
    return new_root


@pytest.mark.exercise("index.insert")
def test_index_insert_example():
    root = _check_insert(tree_from_level([4, 2, 7, 1, 3]), 5)
    assert _inorder(root) == [1, 2, 3, 4, 5, 7]


@pytest.mark.exercise("index.insert")
def test_index_insert_second_example():
    root = _check_insert(tree_from_level([40, 20, 60, 10, 30, 50, 70]), 25)
    assert _inorder(root) == [10, 20, 25, 30, 40, 50, 60, 70]


@pytest.mark.exercise("index.insert")
def test_index_insert_into_empty():
    root = insert_key(None, 5)
    assert isinstance(root, TreeNode)
    assert tree_to_level(root) == [5]


@pytest.mark.exercise("index.insert")
def test_index_insert_new_min_max_and_negatives():
    root = _check_insert(tree_from_level([0]), -(2**31))
    root = _check_insert(root, 2**31 - 1)
    root = _check_insert(root, -1)
    _check_insert(root, 1)


@pytest.mark.exercise("index.insert")
def test_index_insert_skewed_chain():
    root = _bst_from([1, 2, 3, 4, 5])
    root = _check_insert(root, 6)
    root = _check_insert(root, 0)
    _check_insert(_bst_from([5, 4, 3, 2, 1]), 0)


@pytest.mark.exercise("index.insert")
def test_index_insert_random():
    rng = random.Random(31)
    for _ in range(120):
        vals = rng.sample(range(-500, 501), rng.randint(0, 50))
        root = _bst_from(vals)
        present = set(vals)
        for _ in range(rng.randint(1, 8)):
            v = rng.choice([x for x in range(-520, 521) if x not in present])
            present.add(v)
            root = _check_insert(root, v)
        assert _inorder(root) == sorted(present)


# ---------------------------------------------------------------- index.delete

def _check_delete(root, key, model):
    """model: sorted list of current values (updated in place)."""
    shape = tree_to_level(root)
    new_root = delete_key(root, key)
    if key in model:
        model.remove(key)
    else:
        assert tree_to_level(new_root) == shape, "deleting an absent key must leave the index unchanged"
    assert _is_bst(new_root)
    assert _inorder(new_root) == model
    return new_root


@pytest.mark.exercise("index.delete")
def test_index_delete_example():
    root = tree_from_level([5, 3, 6, 2, 4, None, 7])
    root = _check_delete(root, 3, [2, 3, 4, 5, 6, 7])
    assert _inorder(root) == [2, 4, 5, 6, 7]


@pytest.mark.exercise("index.delete")
def test_index_delete_absent_and_empty():
    root = tree_from_level([5, 3, 6, 2, 4, None, 7])
    root = delete_key(root, 0)
    assert tree_to_level(root) == [5, 3, 6, 2, 4, None, 7]
    assert delete_key(None, 0) is None


@pytest.mark.exercise("index.delete")
def test_index_delete_single_node_and_root():
    assert delete_key(TreeNode(1), 1) is None
    root = _check_delete(tree_from_level([1, None, 2]), 1, [1, 2])
    assert tree_to_level(root) == [2]
    root = _check_delete(tree_from_level([2, 1]), 2, [1, 2])
    assert tree_to_level(root) == [1]


@pytest.mark.exercise("index.delete")
def test_index_delete_leaf_one_child_two_children():
    base = [50, 30, 70, 20, 40, 60, 80, None, None, 35, 45, None, 65]
    _check_delete(tree_from_level(base), 20, sorted(v for v in base if v is not None))  # leaf
    _check_delete(tree_from_level(base), 60, sorted(v for v in base if v is not None))  # one child
    _check_delete(tree_from_level(base), 30, sorted(v for v in base if v is not None))  # two children
    _check_delete(tree_from_level(base), 50, sorted(v for v in base if v is not None))  # root, deep successor


@pytest.mark.exercise("index.delete")
def test_index_delete_until_empty():
    vals = [8, 3, 10, 1, 6, 14, 4, 7, 13]
    root = _bst_from(vals)
    model = sorted(vals)
    for key in [8, 3, 14, 99, 1, 13, 10, 6, 7, 4]:
        root = _check_delete(root, key, model)
    assert root is None


@pytest.mark.exercise("index.delete")
def test_index_delete_random():
    rng = random.Random(32)
    for _ in range(120):
        vals = rng.sample(range(-200, 201), rng.randint(0, 60))
        root = _bst_from(vals)
        model = sorted(vals)
        for _ in range(rng.randint(1, len(vals) + 3)):
            if model and rng.random() < 0.8:
                key = rng.choice(model)
            else:
                key = rng.randint(-210, 210)
            root = _check_delete(root, key, model)


# ---------------------------------------------------------------- index.restore

@pytest.mark.exercise("index.restore")
def test_index_restore_example():
    assert tree_to_level(bst_from_preorder([8, 5, 1, 7, 10, 12])) == [8, 5, 10, 1, 7, None, 12]


@pytest.mark.exercise("index.restore")
def test_index_restore_small():
    assert tree_to_level(bst_from_preorder([1, 3])) == [1, None, 3]
    assert tree_to_level(bst_from_preorder([3, 1])) == [3, 1]
    assert tree_to_level(bst_from_preorder([42])) == [42]
    assert bst_from_preorder([]) is None


@pytest.mark.exercise("index.restore")
def test_index_restore_chains():
    root = bst_from_preorder(list(range(500, 0, -1)))
    assert _inorder(root) == list(range(1, 501))
    assert _preorder(root) == list(range(500, 0, -1))
    assert root.right is None and root.left.val == 499
    root = bst_from_preorder(list(range(1, 501)))
    assert root.left is None and root.right.val == 2
    assert _inorder(root) == list(range(1, 501))


@pytest.mark.exercise("index.restore")
def test_index_restore_zigzag_and_negatives():
    pre = [0, -10, -5, -7, -6, 10, 5, 7, 6]
    root = bst_from_preorder(pre)
    assert tree_to_level(root) == [0, -10, 10, None, -5, 5, None, -7, None, None, 7, None, -6, 6]
    pre = [-1, -(2**31), 2**31 - 1]
    assert tree_to_level(bst_from_preorder(pre)) == [-1, -(2**31), 2**31 - 1]


@pytest.mark.exercise("index.restore")
def test_index_restore_random():
    rng = random.Random(33)
    for _ in range(200):
        vals = rng.sample(range(-1000, 1001), rng.randint(1, 80))
        original = _bst_from(vals)
        pre = _preorder(original)
        got = bst_from_preorder(list(pre))
        assert _is_bst(got)
        assert tree_to_level(got) == tree_to_level(original)


@pytest.mark.exercise("index.restore")
def test_index_restore_large():
    rng = random.Random(34)
    vals = rng.sample(range(10**6), 10_000)
    original = _bst_from(vals)
    got = bst_from_preorder(_preorder(original))
    assert tree_to_level(got) == tree_to_level(original)


# ---------------------------------------------------------------- ir.depends_on

def _reach_oracle(n, deps, queries):
    succ = [[] for _ in range(n)]
    for a, b in deps:
        succ[a].append(b)
    reach = []
    for s in range(n):
        seen, stack = set(), [s]
        while stack:
            u = stack.pop()
            for v in succ[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        reach.append(seen)
    return [v in reach[u] for u, v in queries]


def _random_dag(rng, n, p):
    order = list(range(n))
    rng.shuffle(order)
    deps = [[order[i], order[j]] for i in range(n) for j in range(i + 1, n) if rng.random() < p]
    rng.shuffle(deps)
    return deps


@pytest.mark.exercise("ir.depends_on")
def test_ir_depends_on_examples():
    assert depends_queries(2, [[1, 0]], [[0, 1], [1, 0]]) == [False, True]
    assert depends_queries(2, [], [[1, 0], [0, 1]]) == [False, False]
    assert depends_queries(3, [[1, 2], [1, 0], [2, 0]], [[1, 0], [1, 2]]) == [True, True]


@pytest.mark.exercise("ir.depends_on")
def test_ir_depends_on_transitive_chain():
    deps = [[0, 1], [1, 2], [2, 3], [3, 4]]
    queries = [[0, 4], [4, 0], [1, 3], [3, 1], [0, 1], [2, 4], [4, 3]]
    assert depends_queries(5, deps, queries) == [True, False, True, False, True, True, False]


@pytest.mark.exercise("ir.depends_on")
def test_ir_depends_on_diamond_and_parallel_branches():
    # 0 -> {1, 2} -> 3; 4 is independent.
    deps = [[0, 1], [0, 2], [1, 3], [2, 3]]
    queries = [[0, 3], [1, 2], [2, 1], [3, 0], [4, 0], [0, 4], [1, 3], [2, 3]]
    assert depends_queries(5, deps, queries) == [True, False, False, False, False, False, True, True]


@pytest.mark.exercise("ir.depends_on")
def test_ir_depends_on_single_and_empty_queries():
    assert depends_queries(1, [], []) == []
    assert depends_queries(3, [[2, 0]], []) == []
    assert depends_queries(3, [[2, 0]], [[2, 0], [2, 0], [0, 2]]) == [True, True, False]


@pytest.mark.exercise("ir.depends_on")
def test_ir_depends_on_random():
    rng = random.Random(35)
    for _ in range(150):
        n = rng.randint(1, 12)
        deps = _random_dag(rng, n, rng.choice([0.1, 0.3, 0.6]))
        queries = [rng.sample(range(n), 2) for _ in range(rng.randint(0, 30))] if n >= 2 else []
        assert depends_queries(n, deps, queries) == _reach_oracle(n, deps, queries)


@pytest.mark.exercise("ir.depends_on")
def test_ir_depends_on_large():
    rng = random.Random(36)
    n = 100
    deps = _random_dag(rng, n, 0.15)
    queries = [rng.sample(range(n), 2) for _ in range(10_000)]
    assert depends_queries(n, deps, queries) == _reach_oracle(n, deps, queries)


# ---------------------------------------------------------------- ir.computable

def _computable_oracle(outputs, inputs, provided):
    have = set(provided)
    done = set()
    changed = True
    while changed:
        changed = False
        for out, ins in zip(outputs, inputs):
            if out not in done and all(x in have for x in ins):
                done.add(out)
                have.add(out)
                changed = True
    return sorted(done)


@pytest.mark.exercise("ir.computable")
def test_ir_computable_example():
    assert sorted(computable_outputs(["attn"], [["q", "k"]], ["q", "k", "v"])) == ["attn"]


@pytest.mark.exercise("ir.computable")
def test_ir_computable_chained_outputs():
    got = computable_outputs(["attn", "proj"], [["q", "k"], ["attn", "w_o"]], ["q", "k", "w_o"])
    assert sorted(got) == ["attn", "proj"]
    got = computable_outputs(
        ["attn", "proj", "resid"],
        [["q", "k"], ["attn", "w_o"], ["proj", "w_o", "attn"]],
        ["q", "k", "w_o"],
    )
    assert sorted(got) == ["attn", "proj", "resid"]


@pytest.mark.exercise("ir.computable")
def test_ir_computable_declared_after_use():
    # "out" is listed before the operator that produces its input.
    got = computable_outputs(["out", "mid", "head"], [["mid"], ["head"], ["x"]], ["x"])
    assert sorted(got) == ["head", "mid", "out"]


@pytest.mark.exercise("ir.computable")
def test_ir_computable_missing_input():
    got = computable_outputs(["a", "b", "c"], [["x", "ghost"], ["x"], ["a", "b"]], ["x"])
    assert sorted(got) == ["b"]
    assert computable_outputs(["a"], [["y"]], []) == []


@pytest.mark.exercise("ir.computable")
def test_ir_computable_cycles_are_not_computable():
    got = computable_outputs(
        ["a", "b", "c", "d", "e"],
        [["b", "x"], ["a"], ["a", "x"], ["x"], ["d", "c"]],
        ["x"],
    )
    assert sorted(got) == ["d"]
    # A cycle that also has a provided input on every operator is still a cycle.
    got = computable_outputs(["p", "q", "r"], [["q", "s"], ["p", "s"], ["s"]], ["s"])
    assert sorted(got) == ["r"]
    # An operator that consumes its own output can never start.
    assert computable_outputs(["s"], [["s", "x"]], ["x"]) == []


@pytest.mark.exercise("ir.computable")
def test_ir_computable_random():
    rng = random.Random(37)
    for _ in range(300):
        m = rng.randint(1, 12)
        outputs = [f"o{i}" for i in range(m)]
        provided = [f"p{i}" for i in range(rng.randint(0, 5))]
        pool_extra = [f"x{i}" for i in range(rng.randint(0, 2))]  # never provided
        inputs = []
        for i in range(m):
            pool = [o for o in outputs if o != outputs[i]] + provided + pool_extra
            if not pool:
                pool = ["x_missing"]
            inputs.append(rng.sample(pool, rng.randint(1, min(4, len(pool)))))
        order = list(range(m))
        rng.shuffle(order)
        outputs = [outputs[i] for i in order]
        inputs = [inputs[i] for i in order]
        got = computable_outputs(outputs, inputs, provided)
        assert len(got) == len(set(got))
        assert sorted(got) == _computable_oracle(outputs, inputs, provided)


# ---------------------------------------------------------------- config.strip_comments

def _strip_oracle(lines):
    """Join with newlines, scan the whole text once, then split and drop empty lines."""
    text = "\n".join(lines)
    out = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            assert j != -1, "generator produced an unterminated block comment"
            i = j + 2
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
        else:
            out.append(text[i])
            i += 1
    return [line for line in "".join(out).split("\n") if line]


@pytest.mark.exercise("config.strip_comments")
def test_config_strip_comments_example():
    src = [
        "/*Serve config */",
        "server()",
        "{ ",
        "  // listener settings ",
        "port = 8080;",
        "/* This is a test",
        "   multiline  ",
        "   comment for ",
        "   testing */",
        "tp = pp * dp;",
        "}",
    ]
    assert strip_comments(src) == ["server()", "{ ", "  ", "port = 8080;", "tp = pp * dp;", "}"]


@pytest.mark.exercise("config.strip_comments")
def test_config_strip_comments_block_joins_lines():
    assert strip_comments(["a/*comment", "line", "more_comment*/b"]) == ["ab"]
    assert strip_comments(["a/*", "*/"]) == ["a"]
    assert strip_comments(["/*", "x", "*/b", "c"]) == ["b", "c"]
    assert strip_comments(["port = 8080; // http", "/* tp = 2; */", "tp = 1;"]) == ["port = 8080; ", "tp = 1;"]


@pytest.mark.exercise("config.strip_comments")
def test_config_strip_comments_earliest_marker_wins():
    assert strip_comments(["x//*y", "z*/"]) == ["x", "z*/"]  # line comment first: no block opens
    assert strip_comments(["a/* // */b"]) == ["ab"]  # // inside a block is just text
    assert strip_comments(["a// /* ", "b"]) == ["a", "b"]  # /* inside a line comment is ignored
    assert strip_comments(["a/*x*//*y*/b"]) == ["ab"]
    assert strip_comments(["a/**/b"]) == ["ab"]


@pytest.mark.exercise("config.strip_comments")
def test_config_strip_comments_tricky_terminators():
    assert strip_comments(["a/*/b", "c*/d"]) == ["ad"]  # "/*/" does not close the block
    assert strip_comments(["a/*x", "*//b"]) == ["a/b"]  # the trailing "/" is ordinary text
    assert strip_comments(["a*/b"]) == ["a*/b"]  # stray "*/" outside a block is ordinary
    assert strip_comments(["a/b", "/", "*"]) == ["a/b", "/", "*"]


@pytest.mark.exercise("config.strip_comments")
def test_config_strip_comments_empty_lines():
    assert strip_comments(["", "a", ""]) == ["a"]
    assert strip_comments(["   "]) == ["   "]
    assert strip_comments(["// only comment", "/* only */", "/*", "*/"]) == []
    assert strip_comments([]) == []


@pytest.mark.exercise("config.strip_comments")
def test_config_strip_comments_random():
    rng = random.Random(38)
    alphabet = "ab /*"
    for _ in range(800):
        lines = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 10))) for _ in range(rng.randint(1, 6))]
        text = "\n".join(lines)
        # Close a dangling block comment, if any, by appending a terminator to the last line.
        i, in_block = 0, False
        while i < len(text):
            if in_block:
                if text.startswith("*/", i):
                    in_block, i = False, i + 2
                else:
                    i += 1
            elif text.startswith("/*", i):
                in_block, i = True, i + 2
            elif text.startswith("//", i):
                j = text.find("\n", i)
                i = len(text) if j == -1 else j
            else:
                i += 1
        if in_block:
            lines[-1] += "*/"
        assert strip_comments(list(lines)) == _strip_oracle(lines)


# ---------------------------------------------------------------- config.flags

def _random_flag_expr(rng, depth):
    if depth == 0 or rng.random() < 0.3:
        v = rng.random() < 0.5
        return ("t" if v else "f"), v
    op = rng.choice("!&|")
    if op == "!":
        s, v = _random_flag_expr(rng, depth - 1)
        return f"!({s})", not v
    kids = [_random_flag_expr(rng, depth - 1) for _ in range(rng.randint(1, 4))]
    val = all(v for _, v in kids) if op == "&" else any(v for _, v in kids)
    return op + "(" + ",".join(s for s, _ in kids) + ")", val


@pytest.mark.exercise("config.flags")
def test_config_flags_examples():
    assert eval_flag_expr("&(|(f))") is False
    assert eval_flag_expr("|(f,f,f,t)") is True
    assert eval_flag_expr("!(&(f,t))") is True


@pytest.mark.exercise("config.flags")
def test_config_flags_atoms_and_single_operands():
    assert eval_flag_expr("t") is True
    assert eval_flag_expr("f") is False
    assert eval_flag_expr("!(t)") is False
    assert eval_flag_expr("&(t)") is True
    assert eval_flag_expr("|(f)") is False


@pytest.mark.exercise("config.flags")
def test_config_flags_nested():
    assert eval_flag_expr("&(t,|(f,t),!(f))") is True
    assert eval_flag_expr("|(&(t,f,t),!(t))") is False
    assert eval_flag_expr("!(!(t))") is True
    assert eval_flag_expr("&(|(f,!(f)),&(t,t),|(&(f),t))") is True
    assert eval_flag_expr("|(&(t,f),&(f,t),!(|(t,f)))") is False


@pytest.mark.exercise("config.flags")
def test_config_flags_deep_and_long():
    assert eval_flag_expr("!(" * 200 + "t" + ")" * 200) is True
    assert eval_flag_expr("!(" * 199 + "t" + ")" * 199) is False
    deep = "".join("&(" if i % 2 else "|(" for i in range(200)) + "f" + ")" * 200
    assert eval_flag_expr(deep) is False
    flat = ["t"] * 9998
    assert eval_flag_expr("&(" + ",".join(flat) + ")") is True
    flat[7777] = "f"
    assert eval_flag_expr("&(" + ",".join(flat) + ")") is False
    assert eval_flag_expr("|(" + ",".join(flat) + ")") is True


@pytest.mark.exercise("config.flags")
def test_config_flags_random():
    rng = random.Random(39)
    for _ in range(500):
        expr, val = _random_flag_expr(rng, rng.randint(0, 6))
        assert eval_flag_expr(expr) is val


# ---------------------------------------------------------------- config.glob

def _glob_oracle(s, p):
    """Plain recursion straight from the definition (exponential; small inputs only)."""
    if not p:
        return not s
    if p[0] == "*":
        return any(_glob_oracle(s[k:], p[1:]) for k in range(len(s) + 1))
    return bool(s) and (p[0] == "?" or p[0] == s[0]) and _glob_oracle(s[1:], p[1:])


@pytest.mark.exercise("config.glob")
def test_config_glob_examples():
    assert glob_match("aa", "a") is False
    assert glob_match("aa", "*") is True
    assert glob_match("cb", "?a") is False
    assert glob_match("adceb", "*a*b") is True
    assert glob_match("acdcb", "a*c?b") is False


@pytest.mark.exercise("config.glob")
def test_config_glob_model_names():
    assert glob_match("llama-3-8b-instruct", "llama-*-instruct") is True
    assert glob_match("llama-3-8b-chat", "llama-*-instruct") is False
    assert glob_match("qwen2-7b", "qwen?-7b") is True
    assert glob_match("qwen-7b", "qwen?-7b") is False
    assert glob_match("org/llama-3", "*/llama-?") is True
    assert glob_match("a/b", "a?b") is True  # wildcards also match "/"


@pytest.mark.exercise("config.glob")
def test_config_glob_empty_strings():
    assert glob_match("", "") is True
    assert glob_match("", "*") is True
    assert glob_match("", "***") is True
    assert glob_match("", "?") is False
    assert glob_match("", "a") is False
    assert glob_match("a", "") is False


@pytest.mark.exercise("config.glob")
def test_config_glob_literals_and_whole_string():
    assert glob_match("a.b", "a.b") is True
    assert glob_match("axb", "a.b") is False  # "." is literal
    assert glob_match("abc", "ab") is False  # must consume the whole name
    assert glob_match("abc", "bc") is False
    assert glob_match("abc", "*c") is True
    assert glob_match("abc", "a*") is True
    assert glob_match("abc", "?*?*?") is True
    assert glob_match("ab", "?*?*?") is False


@pytest.mark.exercise("config.glob")
def test_config_glob_many_stars_no_blowup():
    s = "a" * 400
    with _time_limit(3):
        assert glob_match(s, "*a" * 25 + "*b") is False
        assert glob_match(s + "b", "*a" * 25 + "*b") is True
        assert glob_match(s, "a*" * 30 + "a") is True
        assert glob_match("ab" * 200, "*" + "a*b*" * 40 + "?") is True
        assert glob_match("ab" * 200, "*" + "a*b*" * 40 + "c") is False
        assert glob_match("a" * 300, "*" * 100 + "a" * 300) is True
        assert glob_match("a" * 300, "*?" * 60 + "*b") is False


@pytest.mark.exercise("config.glob")
def test_config_glob_random():
    rng = random.Random(40)
    chars = "ab/"
    for _ in range(3000):
        s = "".join(rng.choice(chars) for _ in range(rng.randint(0, 8)))
        if rng.random() < 0.5:
            p = "".join(rng.choice(chars + "?*") for _ in range(rng.randint(0, 7)))
        else:  # derive a likely-matching pattern from s
            p, i = [], 0
            while i < len(s):
                r = rng.random()
                if r < 0.2:
                    p.append("?")
                    i += 1
                elif r < 0.4:
                    p.append("*")
                    i += rng.randint(0, 3)
                elif r < 0.45:
                    p.append(rng.choice(chars))
                    i += 1
                else:
                    p.append(s[i])
                    i += 1
            if rng.random() < 0.3:
                p.append("*")
            p = "".join(p)
        assert glob_match(s, p) is _glob_oracle(s, p), (s, p)



@pytest.mark.exercise("config.glob")
def test_config_glob_mixed_characters():
    assert glob_match("Qwen2.5-7B_chat:latest", "Qwen?.?-*:*") is True
    assert glob_match("Qwen2-7B", "qwen*") is False  # case-sensitive
    assert glob_match("org_A/Model:v1", "org_?/*:v?") is True
    assert glob_match("a b", "a?b") is True
    assert glob_match("x_y", "x-y") is False
    assert glob_match("~@!", "*!") is True


@pytest.mark.exercise("config.glob")
def test_config_glob_mixed_random():
    rng = random.Random(41)
    chars = "aB_:-. "
    for _ in range(3000):
        s = "".join(rng.choice(chars) for _ in range(rng.randint(0, 8)))
        p = "".join(rng.choice(chars + "??**") for _ in range(rng.randint(0, 7)))
        assert glob_match(s, p) is _glob_oracle(s, p), (s, p)
