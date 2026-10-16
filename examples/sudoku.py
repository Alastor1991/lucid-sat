"""Solve a Sudoku by encoding it as SAT.

Variable x(r, c, d) means "cell (r, c) holds digit d". Every cell holds exactly
one digit, and every row, column and box holds each digit exactly once.

    python examples/sudoku.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lucidsat import Formula  # noqa: E402

# Known as one of the harder puzzles for human solvers (Arto Inkala, 2012).
PUZZLE = """
8........
..36.....
.7..9.2..
.5...7...
....457..
...1...3.
..1....68
..85...1.
.9....4..
"""


def solve_sudoku(grid: str) -> list[list[int]] | None:
    rows = [line.strip() for line in grid.strip().splitlines()]
    f = Formula()
    x = {(r, c, d): f.new_var() for r in range(9) for c in range(9) for d in range(1, 10)}

    for r in range(9):
        for c in range(9):
            f.exactly_one([x[r, c, d] for d in range(1, 10)])
            if rows[r][c] != ".":
                f.add([x[r, c, int(rows[r][c])]])
    for d in range(1, 10):
        for i in range(9):
            f.exactly_one([x[i, c, d] for c in range(9)])  # row i
            f.exactly_one([x[r, i, d] for r in range(9)])  # column i
            br, bc = 3 * (i // 3), 3 * (i % 3)
            f.exactly_one([x[br + r, bc + c, d] for r in range(3) for c in range(3)])  # box i

    solver = f.solver()
    if not solver.solve():
        return None
    true = {lit for lit in solver.model if lit > 0}
    return [[next(d for d in range(1, 10) if x[r, c, d] in true) for c in range(9)] for r in range(9)]


if __name__ == "__main__":
    solution = solve_sudoku(PUZZLE)
    if solution is None:
        print("no solution")
    else:
        for r, row in enumerate(solution):
            if r and r % 3 == 0:
                print("------+-------+------")
            print(" | ".join(" ".join(map(str, row[c : c + 3])) for c in (0, 3, 6)))
