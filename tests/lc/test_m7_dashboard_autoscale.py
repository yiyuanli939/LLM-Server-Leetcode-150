import random

import pytest

from nanoserve.dashboard.health import mask_failures


# ---------------------------------------------------------------- dash.mask_failed

def _mask_oracle(m):
    rows, cols = len(m), len(m[0])
    zr = {i for i in range(rows) for j in range(cols) if m[i][j] == 0}
    zc = {j for i in range(rows) for j in range(cols) if m[i][j] == 0}
    return [[0 if (i in zr or j in zc) else m[i][j] for j in range(cols)] for i in range(rows)]


@pytest.mark.exercise("dash.mask_failed")
def test_dash_mask_failed_center():
    m = [[1, 1, 1], [1, 0, 1], [1, 1, 1]]
    assert mask_failures(m) is None
    assert m == [[1, 0, 1], [0, 0, 0], [1, 0, 1]]


@pytest.mark.exercise("dash.mask_failed")
def test_dash_mask_failed_first_row():
    m = [[0, 1, 2, 0], [3, 4, 5, 2], [1, 3, 1, 5]]
    assert mask_failures(m) is None
    assert m == [[0, 0, 0, 0], [0, 4, 5, 0], [0, 3, 1, 0]]


@pytest.mark.exercise("dash.mask_failed")
def test_dash_mask_failed_no_zero_and_single():
    m = [[1, -2], [3, 4]]
    mask_failures(m)
    assert m == [[1, -2], [3, 4]]
    m = [[0]]
    mask_failures(m)
    assert m == [[0]]
    m = [[5]]
    mask_failures(m)
    assert m == [[5]]


@pytest.mark.exercise("dash.mask_failed")
def test_dash_mask_failed_first_column_corner():
    m = [[1, 2, 3], [0, 5, 6], [7, 8, 9]]
    mask_failures(m)
    assert m == [[0, 2, 3], [0, 0, 0], [0, 8, 9]]
    m = [[1], [0], [3]]
    mask_failures(m)
    assert m == [[0], [0], [0]]
    m = [[1, 0, 3]]
    mask_failures(m)
    assert m == [[0, 0, 0]]


@pytest.mark.exercise("dash.mask_failed")
def test_dash_mask_failed_random():
    rng = random.Random(73)
    for _ in range(300):
        rows, cols = rng.randint(1, 7), rng.randint(1, 7)
        m = [[0 if rng.random() < 0.12 else rng.randint(-5, 5) or 1 for _ in range(cols)] for _ in range(rows)]
        expected = _mask_oracle(m)
        assert mask_failures(m) is None
        assert m == expected


# ---------------------------------------------------------------- autoscale.*


