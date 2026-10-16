"""Reading and writing the DIMACS CNF format used by SAT competitions.

Example::

    c a comment
    p cnf 3 2
    1 -2 0
    2 3 0
"""

from __future__ import annotations

from typing import Iterable, TextIO


class DimacsError(ValueError):
    pass


def parse(text: str) -> tuple[int, list[list[int]]]:
    """Parse DIMACS CNF text into ``(num_vars, clauses)``.

    Lenient where real-world files are sloppy: clauses may span lines, the
    final ``0`` may be missing, and a ``%`` line (as in SATLIB) ends the input.
    The clause count in the problem line is not enforced, since many published
    benchmarks get it wrong.
    """
    num_vars = 0
    clauses: list[list[int]] = []
    current: list[int] = []

    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("%"):
            break
        if line.startswith("p"):
            parts = line.split()
            if len(parts) != 4 or parts[1] != "cnf":
                raise DimacsError(f"line {line_number}: bad problem line {line!r}")
            try:
                num_vars = max(num_vars, int(parts[2]))
                int(parts[3])
            except ValueError:
                raise DimacsError(f"line {line_number}: bad problem line {line!r}") from None
            continue
        for token in line.split():
            try:
                lit = int(token)
            except ValueError:
                raise DimacsError(f"line {line_number}: not an integer: {token!r}") from None
            if lit == 0:
                clauses.append(current)
                current = []
            else:
                current.append(lit)
                num_vars = max(num_vars, abs(lit))

    if current:
        clauses.append(current)
    return num_vars, clauses


def load(stream: TextIO) -> tuple[int, list[list[int]]]:
    return parse(stream.read())


def dumps(num_vars: int, clauses: Iterable[Iterable[int]]) -> str:
    clauses = [list(c) for c in clauses]
    lines = [f"p cnf {num_vars} {len(clauses)}"]
    lines += [" ".join(map(str, c + [0])) for c in clauses]
    return "\n".join(lines) + "\n"
