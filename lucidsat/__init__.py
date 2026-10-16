"""lucidsat: a CDCL SAT solver in readable, dependency-free Python."""

from .dimacs import DimacsError, dumps, parse
from .encode import Formula
from .solver import Solver, Stats, luby

__all__ = ["Solver", "Stats", "Formula", "parse", "dumps", "DimacsError", "luby", "solve"]
__version__ = "0.1.0"


def solve(clauses, num_vars: int = 0):
    """One-shot helper: return a model (list of literals) or None if UNSAT."""
    s = Solver(clauses, num_vars=num_vars)
    return s.model if s.solve() else None
