"""A CDCL SAT solver written to be read.

The whole algorithm lives in this file. Reading order that works well:

1. ``Solver.solve``      – the main loop: propagate, and either learn from a
                           conflict or make a decision.
2. ``Solver._propagate`` – unit propagation with two watched literals.
3. ``Solver._analyze``   – conflict analysis down to the first UIP.
4. Everything else is bookkeeping.

Conventions
-----------
* Variables are positive integers ``1..num_vars`` (as in DIMACS).
* A literal is ``v`` (variable is true) or ``-v`` (variable is false).
* ``assign[v]`` is ``1`` (true), ``-1`` (false) or ``0`` (unassigned).
* A clause is a Python list of literals. Positions 0 and 1 are the two
  *watched* literals. When a clause becomes the reason for an implied
  literal, that literal sits at position 0.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional, Sequence

RESTART_BASE = 100  # conflicts per unit of the Luby sequence
ACTIVITY_DECAY = 0.95  # VSIDS: smaller = forget old conflicts faster
RESCALE_LIMIT = 1e100


@dataclass
class Stats:
    decisions: int = 0
    propagations: int = 0
    conflicts: int = 0
    learned: int = 0
    restarts: int = 0


def luby(i: int) -> int:
    """The i-th element (1-indexed) of the Luby sequence 1,1,2,1,1,2,4,1,...

    Restarting after ``luby(k) * RESTART_BASE`` conflicts is a schedule that is
    provably within a log factor of the best fixed schedule for Las Vegas
    algorithms (Luby, Sinclair & Zuckerman, 1993).
    """
    if i < 1:
        raise ValueError("luby() is 1-indexed")
    while True:
        k = i.bit_length()  # 2^(k-1) <= i < 2^k
        if i == (1 << k) - 1:
            return 1 << (k - 1)
        i -= (1 << (k - 1)) - 1


class Solver:
    """Conflict-driven clause learning SAT solver.

    >>> s = Solver([[1, 2], [-1, 2], [-2, 3]])
    >>> s.solve()
    True
    >>> s.model
    [-1, 2, 3]
    """

    def __init__(self, clauses: Iterable[Iterable[int]] = (), num_vars: int = 0):
        self.num_vars = 0
        self.clauses: list[list[int]] = []
        self.watches: dict[int, list[int]] = {}

        # Per-variable state; index 0 is unused so that ``assign[v]`` works.
        self.assign: list[int] = [0]
        self.level: list[int] = [0]
        self.reason: list[Optional[int]] = [None]
        self.activity: list[float] = [0.0]
        self.phase: list[bool] = [False]

        # The trail is every assigned literal in assignment order.
        # trail_lim[d] is where decision level d+1 starts in the trail.
        self.trail: list[int] = []
        self.trail_lim: list[int] = []
        self.qhead = 0  # trail[qhead:] still has to be propagated

        self.heap: list[tuple[float, int]] = []  # (-activity, var), lazy
        self.bump_amount = 1.0

        self.ok = True  # becomes False once UNSAT is proven at level 0
        self.model: list[int] = []
        self.stats = Stats()

        self._ensure_vars(num_vars)
        for clause in clauses:
            self.add_clause(clause)

    # ------------------------------------------------------------------ API

    def add_clause(self, literals: Iterable[int]) -> bool:
        """Add a clause. Returns False if the formula is now known to be UNSAT.

        Clauses can be added between calls to ``solve`` (incremental use).
        """
        if not self.ok:
            return False
        self._backtrack(0)

        lits = set(literals)
        if 0 in lits:
            raise ValueError("0 is not a valid literal")
        if lits:
            self._ensure_vars(max(abs(l) for l in lits))
        if any(-l in lits for l in lits):
            return True  # tautology: x or not x

        # At level 0 every assignment is a proven fact, so we can simplify.
        clause = []
        for lit in sorted(lits, key=abs):
            value = self._value(lit)
            if value == 1:
                return True  # already satisfied forever
            if value == 0:
                clause.append(lit)
            # value == -1: the literal is false forever, drop it

        if not clause:
            self.ok = False
        elif len(clause) == 1:
            self._enqueue(clause[0], None)
            if self._propagate() is not None:
                self.ok = False
        else:
            self._attach(clause)
        return self.ok

    def solve(self, max_conflicts: Optional[int] = None) -> Optional[bool]:
        """Return True (SAT, see ``model``), False (UNSAT) or None (gave up)."""
        if not self.ok:
            return False
        self._backtrack(0)
        start_conflicts = self.stats.conflicts
        restart_index = 1
        conflicts_until_restart = luby(restart_index) * RESTART_BASE

        while True:
            conflict = self._propagate()

            if conflict is not None:
                self.stats.conflicts += 1
                conflicts_until_restart -= 1
                if self._decision_level() == 0:
                    self.ok = False  # conflict without any decision: UNSAT
                    return False

                learnt, backjump_level = self._analyze(conflict)
                self._backtrack(backjump_level)
                if len(learnt) == 1:
                    self._enqueue(learnt[0], None)
                else:
                    index = self._attach(learnt)
                    self.stats.learned += 1
                    # The learnt clause is now unit: learnt[0] is implied.
                    self._enqueue(learnt[0], index)
                self.bump_amount /= ACTIVITY_DECAY

                if (
                    max_conflicts is not None
                    and self.stats.conflicts - start_conflicts >= max_conflicts
                ):
                    return None
                continue

            if conflicts_until_restart <= 0:
                self.stats.restarts += 1
                restart_index += 1
                conflicts_until_restart = luby(restart_index) * RESTART_BASE
                self._backtrack(0)
                continue

            literal = self._pick_branch()
            if literal is None:  # everything assigned, no conflict
                self.model = [
                    v if self.assign[v] > 0 else -v
                    for v in range(1, self.num_vars + 1)
                ]
                return True
            self.stats.decisions += 1
            self.trail_lim.append(len(self.trail))
            self._enqueue(literal, None)

    def iter_models(self, project: Optional[Sequence[int]] = None) -> Iterator[list[int]]:
        """Yield every model, distinct on the variables in ``project``.

        After each model a *blocking clause* forbidding it is added, so the
        solver is permanently changed by iterating.
        """
        variables = list(project) if project is not None else list(range(1, self.num_vars + 1))
        while self.solve():
            model = self.model
            yield model
            self.add_clause([-model[v - 1] for v in variables])

    # ---------------------------------------------------------- propagation

    def _propagate(self) -> Optional[int]:
        """Unit propagation. Returns the index of a conflicting clause or None.

        Two-watched-literal scheme: each clause watches two of its literals that
        are not false. Only when a watched literal becomes false do we look at
        the clause, and then we try to find another non-false literal to watch.
        If there is none, the clause is unit (the other watch is implied) or,
        if the other watch is false as well, in conflict.

        Nothing has to be undone on backtracking, which is what makes this fast.
        """
        while self.qhead < len(self.trail):
            true_lit = self.trail[self.qhead]
            self.qhead += 1
            self.stats.propagations += 1

            false_lit = -true_lit
            watchers = self.watches[false_lit]
            self.watches[false_lit] = kept = []

            for i, index in enumerate(watchers):
                clause = self.clauses[index]
                # Make sure the literal that just became false is at position 1.
                if clause[0] == false_lit:
                    clause[0], clause[1] = clause[1], clause[0]

                if self._value(clause[0]) == 1:
                    kept.append(index)  # clause already satisfied
                    continue

                for k in range(2, len(clause)):
                    if self._value(clause[k]) != -1:
                        clause[1], clause[k] = clause[k], clause[1]
                        self.watches[clause[1]].append(index)
                        break  # found a new watch; this list no longer has it
                else:
                    kept.append(index)
                    if self._value(clause[0]) == -1:
                        kept.extend(watchers[i + 1 :])
                        return index  # every literal false: conflict
                    self._enqueue(clause[0], index)  # unit: clause[0] must hold
        return None

    # ----------------------------------------------------- conflict analysis

    def _analyze(self, conflict: int) -> tuple[list[int], int]:
        """Derive a learnt clause from a conflict (first-UIP scheme).

        Start from the conflicting clause and repeatedly resolve it with the
        reason of its most recently assigned literal from the current decision
        level, until exactly one literal from the current level is left. That
        literal is the first *unique implication point*. The result:

        * is implied by the formula (it is a chain of resolutions),
        * is false under the current assignment,
        * becomes unit after backjumping, so it immediately forces something.

        Returns the clause (asserting literal first) and the level to jump to.
        """
        current_level = self._decision_level()
        learnt = [0]  # slot 0 is filled with the asserting literal at the end
        seen: set[int] = set()
        open_count = 0  # literals of the current level not yet resolved away
        resolved: Optional[int] = None
        clause = self.clauses[conflict]
        position = len(self.trail) - 1

        while True:
            for lit in clause:
                var = abs(lit)
                if resolved is not None and var == abs(resolved):
                    continue
                if var in seen or self.level[var] == 0:
                    continue  # level-0 facts can always be resolved away
                seen.add(var)
                self._bump(var)
                if self.level[var] == current_level:
                    open_count += 1
                else:
                    learnt.append(lit)

            # Walk back along the trail to the latest literal we have seen.
            while abs(self.trail[position]) not in seen:
                position -= 1
            resolved = self.trail[position]
            position -= 1
            open_count -= 1
            if open_count == 0:
                break
            clause = self.clauses[self.reason[abs(resolved)]]

        learnt[0] = -resolved

        if len(learnt) == 1:
            return learnt, 0
        # Watch the literal with the highest level as the second watch: after
        # backjumping to that level it is the last one to become unassigned.
        best = max(range(1, len(learnt)), key=lambda i: self.level[abs(learnt[i])])
        learnt[1], learnt[best] = learnt[best], learnt[1]
        return learnt, self.level[abs(learnt[1])]

    # ------------------------------------------------------------ heuristics

    def _bump(self, var: int) -> None:
        """VSIDS: variables involved in recent conflicts get branched on first.

        Instead of decaying every activity after each conflict, the bump amount
        grows geometrically, which has the same effect on the ordering.
        """
        self.activity[var] += self.bump_amount
        if self.activity[var] > RESCALE_LIMIT:
            for v in range(1, self.num_vars + 1):
                self.activity[v] /= RESCALE_LIMIT
            self.bump_amount /= RESCALE_LIMIT
            self.heap = [(-self.activity[v], v) for v in range(1, self.num_vars + 1) if self.assign[v] == 0]
            heapq.heapify(self.heap)
        if self.assign[var] == 0:
            heapq.heappush(self.heap, (-self.activity[var], var))

    def _pick_branch(self) -> Optional[int]:
        """Most active unassigned variable, in the polarity it last had.

        The heap is lazy: it may hold stale or duplicate entries. Invariant:
        every unassigned variable has at least one entry, because variables
        are pushed back whenever they become unassigned.
        """
        while self.heap:
            _, var = heapq.heappop(self.heap)
            if self.assign[var] == 0:
                return var if self.phase[var] else -var
        return None

    # ----------------------------------------------------------- bookkeeping

    def _ensure_vars(self, n: int) -> None:
        while self.num_vars < n:
            self.num_vars += 1
            v = self.num_vars
            self.assign.append(0)
            self.level.append(0)
            self.reason.append(None)
            self.activity.append(0.0)
            self.phase.append(False)
            self.watches[v] = []
            self.watches[-v] = []
            heapq.heappush(self.heap, (0.0, v))

    def _value(self, lit: int) -> int:
        value = self.assign[abs(lit)]
        return value if lit > 0 else -value

    def _decision_level(self) -> int:
        return len(self.trail_lim)

    def _enqueue(self, lit: int, reason: Optional[int]) -> None:
        var = abs(lit)
        self.assign[var] = 1 if lit > 0 else -1
        self.level[var] = self._decision_level()
        self.reason[var] = reason
        self.trail.append(lit)

    def _attach(self, clause: list[int]) -> int:
        index = len(self.clauses)
        self.clauses.append(clause)
        self.watches[clause[0]].append(index)
        self.watches[clause[1]].append(index)
        return index

    def _backtrack(self, level: int) -> None:
        if self._decision_level() <= level:
            return
        start = self.trail_lim[level]
        for lit in self.trail[start:]:
            var = abs(lit)
            self.phase[var] = lit > 0  # phase saving
            self.assign[var] = 0
            self.reason[var] = None
            heapq.heappush(self.heap, (-self.activity[var], var))
        del self.trail[start:]
        del self.trail_lim[level:]
        self.qhead = len(self.trail)
