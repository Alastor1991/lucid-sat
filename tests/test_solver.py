import itertools
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

from lucidsat import Formula, Solver, dumps, luby, parse, solve  # noqa: E402
from lucidsat.__main__ import main  # noqa: E402


def satisfies(model, clauses):
    true = set(model)
    return all(any(lit in true for lit in clause) for clause in clauses)


def brute_force(num_vars, clauses):
    for bits in itertools.product((False, True), repeat=num_vars):
        if all(any((lit > 0) == bits[abs(lit) - 1] for lit in c) for c in clauses):
            return True
    return False


def random_formula(rng, max_vars=12):
    n = rng.randint(1, max_vars)
    m = rng.randint(1, 5 * n)
    clauses = [
        [rng.choice((-1, 1)) * rng.randint(1, n) for _ in range(rng.randint(1, 4))]
        for _ in range(m)
    ]
    return n, clauses


def pigeonhole(holes):
    """holes+1 pigeons into `holes` holes: UNSAT, and hard for resolution."""
    f = Formula()
    p = [[f.new_var() for _ in range(holes)] for _ in range(holes + 1)]
    for pigeon in p:
        f.at_least_one(pigeon)
    for h in range(holes):
        col = [p[i][h] for i in range(holes + 1)]
        for a, b in itertools.combinations(col, 2):
            f.add([-a, -b])
    return f


# ---------------------------------------------------------------- basics


def test_empty_formula_is_sat():
    s = Solver()
    assert s.solve() is True
    assert s.model == []


def test_empty_clause_is_unsat():
    assert Solver([[]]).solve() is False


def test_contradicting_units():
    assert Solver([[1], [-1]]).solve() is False


def test_tautology_is_ignored():
    s = Solver([[1, -1]])
    assert s.solve() is True


def test_zero_literal_rejected():
    with pytest.raises(ValueError):
        Solver([[1, 0]])


def test_num_vars_includes_unused_variables():
    s = Solver([[1]], num_vars=3)
    assert s.solve() and len(s.model) == 3


def test_solve_helper():
    assert solve([[1, 2], [-1], [-2, 3]]) == [-1, 2, 3]
    assert solve([[1], [-1]]) is None


# ------------------------------------------------------ against ground truth


@pytest.mark.parametrize("seed", range(10))
def test_matches_brute_force(seed):
    rng = random.Random(seed)
    for _ in range(200):
        n, clauses = random_formula(rng)
        s = Solver(clauses, num_vars=n)
        result = s.solve()
        assert result == brute_force(n, clauses), clauses
        if result:
            assert satisfies(s.model, clauses)


@pytest.mark.parametrize("n", [50, 100, 150])
def test_random_3sat_near_threshold(n):
    rng = random.Random(n)
    clauses = [
        [rng.choice((-1, 1)) * v for v in rng.sample(range(1, n + 1), 3)]
        for _ in range(int(4.26 * n))
    ]
    s = Solver(clauses)
    if s.solve():
        assert satisfies(s.model, clauses)


@pytest.mark.parametrize("holes", [3, 4, 5, 6])
def test_pigeonhole_unsat(holes):
    assert pigeonhole(holes).solver().solve() is False


def test_conflict_budget_returns_none():
    s = pigeonhole(8).solver()
    assert s.solve(max_conflicts=10) is None
    assert s.stats.conflicts >= 10


# ------------------------------------------------------------- incremental


def test_incremental_clauses():
    s = Solver([[1, 2]])
    assert s.solve()
    s.add_clause([-1])
    assert s.solve() and s.model[1] == 2
    s.add_clause([-2])
    assert s.solve() is False
    assert s.add_clause([3]) is False


def test_iter_models_counts_all():
    rng = random.Random(42)
    for _ in range(50):
        n, clauses = random_formula(rng, max_vars=8)
        expected = sum(
            all(any((l > 0) == bits[abs(l) - 1] for l in c) for c in clauses)
            for bits in itertools.product((False, True), repeat=n)
        )
        models = list(Solver(clauses, num_vars=n).iter_models())
        assert len(models) == expected
        assert len({tuple(m) for m in models}) == expected


# ---------------------------------------------------------------- encodings


@pytest.mark.parametrize("k", range(1, 12))
def test_exactly_one_has_exactly_k_models(k):
    f = Formula()
    xs = f.new_vars(k)
    f.exactly_one(xs)
    models = list(f.solver().iter_models(project=xs))
    assert len(models) == k
    for m in models:
        assert sum(m[v - 1] > 0 for v in xs) == 1


def test_queens():
    from queens import count_solutions

    assert [count_solutions(n) for n in range(1, 9)] == [1, 0, 0, 2, 10, 4, 40, 92]


def test_sudoku():
    from sudoku import PUZZLE, solve_sudoku

    grid = solve_sudoku(PUZZLE)
    digits = set(range(1, 10))
    for i in range(9):
        assert set(grid[i]) == digits
        assert {grid[r][i] for r in range(9)} == digits
        br, bc = 3 * (i // 3), 3 * (i % 3)
        assert {grid[br + r][bc + c] for r in range(3) for c in range(3)} == digits
    rows = [line.strip() for line in PUZZLE.strip().splitlines()]
    for r in range(9):
        for c in range(9):
            if rows[r][c] != ".":
                assert grid[r][c] == int(rows[r][c])


# ------------------------------------------------------------ misc pieces


def test_luby_prefix():
    assert [luby(i) for i in range(1, 16)] == [1, 1, 2, 1, 1, 2, 4, 1, 1, 2, 1, 1, 2, 4, 8]


def test_dimacs_round_trip():
    clauses = [[1, -2], [2, 3, -4], [4]]
    assert parse(dumps(4, clauses)) == (4, clauses)


def test_dimacs_lenient():
    text = "c hi\np cnf 3 2\n1 -2\n0 2 3 0\n%\n0\n"
    assert parse(text) == (3, [[1, -2], [2, 3]])


def test_cli(tmp_path, capsys):
    sat = tmp_path / "sat.cnf"
    sat.write_text("p cnf 2 2\n1 2 0\n-1 0\n")
    assert main([str(sat)]) == 10
    out = capsys.readouterr().out
    assert "s SATISFIABLE" in out and "v -1 2 0" in out

    unsat = tmp_path / "unsat.cnf"
    unsat.write_text("p cnf 1 2\n1 0\n-1 0\n")
    assert main([str(unsat), "-q"]) == 20
