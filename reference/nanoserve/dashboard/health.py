from __future__ import annotations


# LC 73 Set Matrix Zeroes (O(1) extra space: first row/col as markers)
def mask_failures(m: list[list[int]]) -> None:
    rows, cols = len(m), len(m[0])
    first_row_zero = any(m[0][j] == 0 for j in range(cols))
    first_col_zero = any(m[i][0] == 0 for i in range(rows))
    for i in range(1, rows):
        for j in range(1, cols):
            if m[i][j] == 0:
                m[i][0] = 0
                m[0][j] = 0
    for i in range(1, rows):
        for j in range(1, cols):
            if m[i][0] == 0 or m[0][j] == 0:
                m[i][j] = 0
    if first_row_zero:
        for j in range(cols):
            m[0][j] = 0
    if first_col_zero:
        for i in range(rows):
            m[i][0] = 0


