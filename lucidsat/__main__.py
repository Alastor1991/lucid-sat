"""Command line interface, following SAT competition output conventions.

    python -m lucidsat problem.cnf
    cat problem.cnf | python -m lucidsat -

Exit status: 10 = SATISFIABLE, 20 = UNSATISFIABLE, 0 = UNKNOWN.
"""

from __future__ import annotations

import argparse
import sys
import time

from . import __version__
from .dimacs import DimacsError, parse
from .solver import Solver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lucidsat", description="Solve a DIMACS CNF file.")
    parser.add_argument("file", help="DIMACS CNF file, or - for standard input")
    parser.add_argument("--max-conflicts", type=int, default=None, help="give up after this many conflicts")
    parser.add_argument("-q", "--quiet", action="store_true", help="print only the s line")
    parser.add_argument("--version", action="version", version=f"lucidsat {__version__}")
    args = parser.parse_args(argv)

    try:
        if args.file == "-":
            text = sys.stdin.read()
        else:
            with open(args.file, encoding="utf-8") as f:
                text = f.read()
        num_vars, clauses = parse(text)
    except (OSError, DimacsError) as e:
        print(f"c error: {e}", file=sys.stderr)
        return 1

    start = time.perf_counter()
    solver = Solver(clauses, num_vars=num_vars)
    result = solver.solve(max_conflicts=args.max_conflicts)
    elapsed = time.perf_counter() - start

    if not args.quiet:
        st = solver.stats
        print(f"c {num_vars} variables, {len(clauses)} clauses")
        print(
            f"c {st.decisions} decisions, {st.propagations} propagations, "
            f"{st.conflicts} conflicts, {st.learned} learned, {st.restarts} restarts"
        )
        print(f"c {elapsed:.3f} s")

    if result is True:
        print("s SATISFIABLE")
        if not args.quiet:
            print("v " + " ".join(map(str, solver.model)) + " 0")
        return 10
    if result is False:
        print("s UNSATISFIABLE")
        return 20
    print("s UNKNOWN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
