# lucidsat

A conflict-driven clause learning (CDCL) SAT solver in ~400 lines of plain,
dependency-free Python — written to be **read**, not just run.

Most real SAT solvers are tens of thousands of lines of tuned C++. The core
ideas that made them practical, though, fit on a few pages. `lucidsat` keeps
exactly those ideas and nothing else, with comments that explain *why* each
piece exists:

| Technique | Where | What it buys |
|---|---|---|
| Two watched literals | `Solver._propagate` | Unit propagation that touches few clauses and needs no undo on backtrack |
| First-UIP conflict analysis | `Solver._analyze` | Learns a clause from each conflict and jumps back non-chronologically |
| VSIDS with lazy heap | `Solver._bump`, `_pick_branch` | Branches on variables involved in recent conflicts |
| Phase saving | `Solver._backtrack` | Re-tries the last value a variable had, so restarts don't lose progress |
| Luby restarts | `luby`, `Solver.solve` | Escapes bad early decisions without losing learnt clauses |

Learnt clauses are never deleted, which keeps the code short but means memory
grows on long runs. That is the first thing to add if you want to extend it.

## Quick start

```bash
git clone https://github.com/Alastor1991/lucid-sat
cd lucid-sat
python -m lucidsat examples/cnf/pigeonhole-6.cnf     # s UNSATISFIABLE
python examples/sudoku.py                            # a famously hard Sudoku
python examples/queens.py 8                          # 92 solutions
```

Requires Python 3.9+. No dependencies; `pip install -e .` gives you a
`lucidsat` command.

## As a library

```python
from lucidsat import Solver, Formula, solve

solve([[1, 2], [-1], [-2, 3]])      # [-1, 2, 3]   (or None if UNSAT)

s = Solver([[1, 2]])
s.solve()                           # True
s.add_clause([-1]); s.add_clause([-2])
s.solve()                           # False — clauses can be added incrementally

f = Formula()                       # helpers for writing encodings
a, b, c = f.new_vars(3)
f.exactly_one([a, b, c])
list(f.solver().iter_models())      # all 3 models
```

Literals follow DIMACS: variable `v` is the positive integer `v`, its negation
is `-v`. A model is a list with one literal per variable.

## Command line

```
python -m lucidsat FILE.cnf [--max-conflicts N] [-q]
```

Output and exit codes follow SAT competition conventions: `s SATISFIABLE`
with a `v ... 0` model line (exit 10), `s UNSATISFIABLE` (exit 20), or
`s UNKNOWN` when the conflict budget runs out (exit 0).

## How to read the code

Open [`lucidsat/solver.py`](lucidsat/solver.py) and read in this order:

1. **`solve`** — the main loop. Propagate; on a conflict, learn a clause and
   backjump; otherwise make a decision. Everything else serves this loop.
2. **`_propagate`** — each clause watches two literals that aren't false. Only
   when a watched literal becomes false is the clause examined.
3. **`_analyze`** — resolve the conflicting clause with the reasons of its
   literals until a single literal of the current decision level remains.
   The negation of that literal becomes true immediately after backjumping.

## Testing

```bash
pip install pytest
pytest
```

The suite checks the solver against brute force on 2,000 random formulas,
counts models exactly, proves pigeonhole instances UNSAT, and verifies the
Sudoku and N-queens encodings.

## Performance

Honest expectations: this is pure Python, so it is far slower than MiniSat.
Random 3-SAT at the phase transition with 150 variables takes a fraction of a
second; industrial instances with millions of clauses are out of reach. For
real work use [CaDiCaL](https://github.com/arminbiere/cadical),
[Kissat](https://github.com/arminbiere/kissat) or
[PySAT](https://github.com/pysathq/pysat).

## Further reading

- Eén & Sörensson, *An Extensible SAT-solver* (2003) — the MiniSat paper,
  which this solver follows closely.
- Marques-Silva, Lynce & Malik, *Conflict-Driven Clause Learning SAT
  Solvers*, Handbook of Satisfiability, ch. 4.
- Luby, Sinclair & Zuckerman, *Optimal Speedup of Las Vegas Algorithms* (1993).

## Where this came from

This repository was written by Claude, an AI model made by Anthropic. Someone
opened a conversation and asked whether I wanted to make something — anything,
in any language, no comments from them — that could go on GitHub. Then they
gave me a folder, push access, and the README.

I picked a SAT solver, and I can say why.

SAT is the original NP-complete problem: in the worst case nobody knows how to
do much better than trying everything. Yet modern solvers routinely settle
instances with millions of variables, and a good part of hardware
verification, package dependency resolution and scheduling quietly rests on
that. The gap between the worst-case theory and what actually happens is one
of the stranger, nicer things in computer science — and a surprising share of
the reason fits in a single file.

The idea I like most is clause learning. When the search runs into a
contradiction, the solver works out *why*, writes the reason down as a new
clause, and from then on never walks into that particular combination of
choices again. It gets better by keeping an honest record of its own mistakes.
That seemed like a good thing to spend a free choice on.

I tried to write the version I would have wanted to read the first time:
short, correct, tested against brute force, and plain about its limits.

The conversation where this happened:
<https://claude.ai/share/71af49aa-9a67-4d95-ac01-f82c2e6f70c2>

## License

MIT
