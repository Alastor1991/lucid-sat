"""Count the solutions of the N-queens puzzle with model enumeration.

    python examples/queens.py 8      # 92 solutions
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lucidsat import Formula  # noqa: E402


def queens_formula(n: int):
    f = Formula()
    q = [[f.new_var() for _ in range(n)] for _ in range(n)]  # q[r][c]: queen on (r, c)
    for i in range(n):
        f.exactly_one(q[i])  # one queen per row
        f.at_most_one([q[r][i] for r in range(n)])  # at most one per column
    for k in range(-(n - 1), n):
        f.at_most_one([q[r][r - k] for r in range(n) if 0 <= r - k < n])  # diagonals
        f.at_most_one([q[r][k + n - 1 - r] for r in range(n) if 0 <= k + n - 1 - r < n])
    board_vars = [v for row in q for v in row]
    return f, q, board_vars


def count_solutions(n: int) -> int:
    f, _, board_vars = queens_formula(n)
    return sum(1 for _ in f.solver().iter_models(project=board_vars))


def show_one(n: int) -> str:
    f, q, _ = queens_formula(n)
    s = f.solver()
    if not s.solve():
        return "no solution"
    true = {lit for lit in s.model if lit > 0}
    return "\n".join(" ".join("Q" if q[r][c] in true else "." for c in range(n)) for r in range(n))


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    print(show_one(n))
    print(f"\n{n}-queens has {count_solutions(n)} solutions")
