"""Core exercises for milestone M5: IR graph / interpreter and config parsing."""
import random

import pytest

from nanoserve.common.nodes import graph_from_adjacency, graph_nodes, graph_to_adjacency
from nanoserve.config.expr import eval_expr
from nanoserve.config.parser import brackets_balanced
from nanoserve.config.paths import normalize_path
from nanoserve.ir.graph import can_schedule, clone_graph, topo_order
from nanoserve.ir.interp import eval_rpn


# ---------------------------------------------------------------- helpers

def _has_cycle(n, deps):
    adj = [[] for _ in range(n)]
    for a, b in deps:
        adj[b].append(a)
    color = [0] * n

    def dfs(u):
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1 or (color[v] == 0 and dfs(v)):
                return True
        color[u] = 2
        return False

    return any(color[i] == 0 and dfs(i) for i in range(n))


def _assert_valid_order(n, deps, order):
    assert sorted(order) == list(range(n))
    pos = {v: i for i, v in enumerate(order)}
    for a, b in deps:
        assert pos[b] < pos[a], f"{b} must run before {a}"


def _random_deps(rng, n, m, acyclic):
    perm = list(range(n))
    rng.shuffle(perm)
    pairs = set()
    tries = 0
    while len(pairs) < m and tries < 10 * m + 10:
        tries += 1
        i, j = rng.sample(range(n), 2)
        if acyclic and i > j:
            i, j = j, i
        # perm[j] depends on perm[i] (perm[i] first) when acyclic
        pairs.add((perm[j], perm[i]))
    return [list(p) for p in pairs]


# ---------------------------------------------------------------- ir.order_ok

@pytest.mark.exercise("ir.order_ok")
def test_ir_order_ok_examples():
    assert can_schedule(2, [[1, 0]]) is True
    assert can_schedule(2, [[1, 0], [0, 1]]) is False


@pytest.mark.exercise("ir.order_ok")
def test_ir_order_ok_no_deps():
    assert can_schedule(1, []) is True
    assert can_schedule(5, []) is True


@pytest.mark.exercise("ir.order_ok")
def test_ir_order_ok_long_cycle():
    assert can_schedule(4, [[1, 0], [2, 1], [3, 2], [0, 3]]) is False
    assert can_schedule(4, [[1, 0], [2, 1], [3, 2]]) is True


@pytest.mark.exercise("ir.order_ok")
def test_ir_order_ok_diamond_and_isolated_cycle():
    assert can_schedule(4, [[1, 0], [2, 0], [3, 1], [3, 2]]) is True
    # acyclic part plus a separate 2-cycle
    assert can_schedule(5, [[1, 0], [3, 4], [4, 3]]) is False


@pytest.mark.exercise("ir.order_ok")
def test_ir_order_ok_random_vs_dfs():
    rng = random.Random(207)
    for _ in range(200):
        n = rng.randint(2, 12)
        deps = _random_deps(rng, n, rng.randint(0, 15), acyclic=rng.random() < 0.5)
        assert can_schedule(n, deps) is (not _has_cycle(n, deps))


# ---------------------------------------------------------------- ir.order

@pytest.mark.exercise("ir.order")
def test_ir_order_examples():
    _assert_valid_order(2, [[1, 0]], topo_order(2, [[1, 0]]))
    deps = [[1, 0], [2, 0], [3, 1], [3, 2]]
    _assert_valid_order(4, deps, topo_order(4, deps))


@pytest.mark.exercise("ir.order")
def test_ir_order_single_node():
    assert topo_order(1, []) == [0]


@pytest.mark.exercise("ir.order")
def test_ir_order_cycle_returns_empty():
    assert topo_order(2, [[1, 0], [0, 1]]) == []
    assert topo_order(3, [[0, 1], [1, 2], [2, 0]]) == []


@pytest.mark.exercise("ir.order")
def test_ir_order_no_deps_is_permutation():
    _assert_valid_order(6, [], topo_order(6, []))


@pytest.mark.exercise("ir.order")
def test_ir_order_random():
    rng = random.Random(210)
    for _ in range(200):
        n = rng.randint(1, 12)
        deps = _random_deps(rng, n, rng.randint(0, 15), acyclic=rng.random() < 0.6) if n > 1 else []
        got = topo_order(n, deps)
        if _has_cycle(n, deps):
            assert got == []
        else:
            _assert_valid_order(n, deps, got)


# ---------------------------------------------------------------- ir.clone

def _assert_deep_clone(adj):
    orig = graph_from_adjacency(adj)
    orig_ids = {id(x) for x in graph_nodes(orig)}
    copy = clone_graph(orig)
    assert copy is not None and copy is not orig
    assert copy.val == orig.val
    assert graph_to_adjacency(copy) == adj
    assert not ({id(x) for x in graph_nodes(copy)} & orig_ids)
    assert graph_to_adjacency(orig) == adj  # original untouched


@pytest.mark.exercise("ir.clone")
def test_ir_clone_example_square():
    _assert_deep_clone([[2, 4], [1, 3], [2, 4], [1, 3]])


@pytest.mark.exercise("ir.clone")
def test_ir_clone_single_node():
    _assert_deep_clone([[]])


@pytest.mark.exercise("ir.clone")
def test_ir_clone_empty():
    assert clone_graph(None) is None


@pytest.mark.exercise("ir.clone")
def test_ir_clone_two_nodes_and_triangle():
    _assert_deep_clone([[2], [1]])
    _assert_deep_clone([[2, 3], [1, 3], [1, 2]])


@pytest.mark.exercise("ir.clone")
def test_ir_clone_random_connected():
    rng = random.Random(133)
    for _ in range(30):
        n = rng.randint(1, 15)
        edges = set()
        for v in range(2, n + 1):  # spanning tree keeps it connected
            edges.add(frozenset((v, rng.randint(1, v - 1))))
        for _ in range(rng.randint(0, n)):
            u, v = rng.sample(range(1, n + 1), 2) if n > 1 else (1, 1)
            if u != v:
                edges.add(frozenset((u, v)))
        adj = [[] for _ in range(n)]
        for e in edges:
            u, v = tuple(e)
            adj[u - 1].append(v)
            adj[v - 1].append(u)
        for lst in adj:
            rng.shuffle(lst)
        _assert_deep_clone(adj)


# ---------------------------------------------------------------- ir.rpn

@pytest.mark.exercise("ir.rpn")
def test_ir_rpn_examples():
    assert eval_rpn(["2", "1", "+", "3", "*"]) == 9
    assert eval_rpn(["4", "13", "5", "/", "+"]) == 6
    assert eval_rpn(["10", "6", "9", "3", "+", "-11", "*", "/", "*", "17", "+", "5", "+"]) == 22


@pytest.mark.exercise("ir.rpn")
def test_ir_rpn_single_number():
    assert eval_rpn(["42"]) == 42
    assert eval_rpn(["-7"]) == -7


@pytest.mark.exercise("ir.rpn")
def test_ir_rpn_division_truncates_toward_zero():
    assert eval_rpn(["-7", "2", "/"]) == -3
    assert eval_rpn(["7", "-2", "/"]) == -3
    assert eval_rpn(["6", "-132", "/"]) == 0
    assert eval_rpn(["-8", "-3", "/"]) == 2


@pytest.mark.exercise("ir.rpn")
def test_ir_rpn_operand_order():
    assert eval_rpn(["3", "5", "-"]) == -2
    assert eval_rpn(["20", "4", "/"]) == 5


def _trunc_div(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


@pytest.mark.exercise("ir.rpn")
def test_ir_rpn_random():
    rng = random.Random(150)

    def build(depth):
        if depth == 0 or rng.random() < 0.3:
            v = rng.randint(-20, 20)
            return [str(v)], v
        lt, lv = build(depth - 1)
        rt, rv = build(depth - 1)
        op = rng.choice("+-*/")
        if op == "/" and rv == 0:
            op = "+"
        val = {"+": lv + rv, "-": lv - rv, "*": lv * rv}.get(op) if op != "/" else _trunc_div(lv, rv)
        return lt + rt + [op], val

    for _ in range(300):
        toks, val = build(4)
        assert eval_rpn(toks) == val


# ---------------------------------------------------------------- config.brackets

@pytest.mark.exercise("config.brackets")
def test_config_brackets_examples():
    assert brackets_balanced("()") is True
    assert brackets_balanced("()[]{}") is True
    assert brackets_balanced("(]") is False
    assert brackets_balanced("([])") is True


@pytest.mark.exercise("config.brackets")
def test_config_brackets_wrong_nesting():
    assert brackets_balanced("([)]") is False
    assert brackets_balanced("{[]}") is True


@pytest.mark.exercise("config.brackets")
def test_config_brackets_unmatched():
    assert brackets_balanced("(") is False
    assert brackets_balanced("]") is False
    assert brackets_balanced("(()") is False
    assert brackets_balanced("())") is False


@pytest.mark.exercise("config.brackets")
def test_config_brackets_closing_first():
    assert brackets_balanced(")(") is False
    assert brackets_balanced("}{") is False


@pytest.mark.exercise("config.brackets")
def test_config_brackets_random():
    rng = random.Random(20)

    def oracle(s):
        prev = None
        while prev != s:
            prev = s
            s = s.replace("()", "").replace("[]", "").replace("{}", "")
        return s == ""

    for _ in range(500):
        s = "".join(rng.choice("()[]{}") for _ in range(rng.randint(1, 12)))
        assert brackets_balanced(s) is oracle(s)



@pytest.mark.exercise("config.brackets")
def test_config_brackets_ignores_other_characters():
    assert brackets_balanced("[server]\npool = 2[big,]small") is True
    assert brackets_balanced("x = (1 + 2]") is False
    assert brackets_balanced("no brackets at all") is True
    assert brackets_balanced(" ") is True
    assert brackets_balanced("f(a[0], {k: v})") is True
    assert brackets_balanced("f(a[0)]") is False
    assert brackets_balanced("a)b(c") is False


@pytest.mark.exercise("config.brackets")
def test_config_brackets_mixed_random():
    rng = random.Random(21)

    def oracle(s):
        s = "".join(c for c in s if c in "()[]{}")
        prev = None
        while prev != s:
            prev = s
            s = s.replace("()", "").replace("[]", "").replace("{}", "")
        return s == ""

    for _ in range(800):
        s = "".join(rng.choice("()[]{}ab =,\n") for _ in range(rng.randint(1, 16)))
        assert brackets_balanced(s) is oracle(s), s


# ---------------------------------------------------------------- config.norm_path

@pytest.mark.exercise("config.norm_path")
def test_config_norm_path_examples():
    assert normalize_path("/home/") == "/home"
    assert normalize_path("/home//foo/") == "/home/foo"
    assert normalize_path("/home/user/Documents/../Pictures") == "/home/user/Pictures"
    assert normalize_path("/../") == "/"
    assert normalize_path("/.../a/../b/c/../d/./") == "/.../b/d"


@pytest.mark.exercise("config.norm_path")
def test_config_norm_path_root():
    assert normalize_path("/") == "/"
    assert normalize_path("///") == "/"
    assert normalize_path("/./.") == "/"


@pytest.mark.exercise("config.norm_path")
def test_config_norm_path_dot_names():
    assert normalize_path("/a/.../..../b") == "/a/.../..../b"
    assert normalize_path("/..hidden/.x") == "/..hidden/.x"


@pytest.mark.exercise("config.norm_path")
def test_config_norm_path_up_past_root():
    assert normalize_path("/a/../../b/../c//.//") == "/c"
    assert normalize_path("/a/./b/../../c/") == "/c"


@pytest.mark.exercise("config.norm_path")
def test_config_norm_path_random():
    import posixpath

    rng = random.Random(71)
    parts = ["a", "b", "model_1", ".", "..", "...", "", "w.bin"]
    for _ in range(400):
        p = "/" + "/".join(rng.choice(parts) for _ in range(rng.randint(0, 8)))
        expect = posixpath.normpath(p)
        if expect.startswith("//"):
            expect = "/" + expect.lstrip("/")
        assert normalize_path(p) == expect



@pytest.mark.exercise("config.norm_path")
def test_config_norm_path_mixed_characters():
    assert normalize_path("/models/./llama-3_8B/../qwen2.5-7b/") == "/models/qwen2.5-7b"
    assert normalize_path("/Srv//Weights:v2/./A-b_C") == "/Srv/Weights:v2/A-b_C"
    assert normalize_path("/a-/..-/-../x") == "/a-/..-/-../x"
    assert normalize_path("/x/~/../@y") == "/x/@y"


@pytest.mark.exercise("config.norm_path")
def test_config_norm_path_mixed_random():
    import posixpath

    rng = random.Random(72)
    parts = ["A", "b-1", "Qwen2.5", "w:v2", "_x", "~", "+", ".", "..", "...", "", "..x"]
    for _ in range(600):
        p = "/" + "/".join(rng.choice(parts) for _ in range(rng.randint(0, 8)))
        expect = posixpath.normpath(p)
        if expect.startswith("//"):
            expect = "/" + expect.lstrip("/")
        assert normalize_path(p) == expect, p


# ---------------------------------------------------------------- config.expr

@pytest.mark.exercise("config.expr")
def test_config_expr_examples():
    assert eval_expr("1 + 1") == 2
    assert eval_expr(" 2-1 + 2 ") == 3
    assert eval_expr("(1+(4+5+2)-3)+(6+8)") == 23


@pytest.mark.exercise("config.expr")
def test_config_expr_unary_minus():
    assert eval_expr("-(2+3)") == -5
    assert eval_expr("1-(     -2)") == 3
    assert eval_expr("-2+ 1") == -1
    assert eval_expr("- (3 + (4 + 5))") == -12


@pytest.mark.exercise("config.expr")
def test_config_expr_single_and_large():
    assert eval_expr("0") == 0
    assert eval_expr("2147483647") == 2147483647
    assert eval_expr("  42  ") == 42


@pytest.mark.exercise("config.expr")
def test_config_expr_nested_subtraction():
    assert eval_expr("10 - (2 - (3 - 4))") == 7
    assert eval_expr("((((7))))") == 7


@pytest.mark.exercise("config.expr")
def test_config_expr_random():
    rng = random.Random(224)

    def build(depth):
        # returns (text, value)
        if depth == 0 or rng.random() < 0.3:
            v = rng.randint(0, 99)
            return str(v), v
        terms = rng.randint(1, 3)
        text, val = "", 0
        for i in range(terms):
            t, v = build(depth - 1)
            wrapped = rng.random() < 0.4 or (i > 0 and not t.isdigit())
            if wrapped:
                t = f"({t})"
            if i == 0:
                if wrapped and rng.random() < 0.3:
                    text, val = "-" + t, -v
                else:
                    text, val = t, v
            else:
                op = rng.choice("+-")
                sp = " " * rng.randint(0, 2)
                text += f"{sp}{op}{sp}{t}"
                val = val + v if op == "+" else val - v
        return text, val

    for _ in range(300):
        text, val = build(4)
        assert eval_expr(text) == val
