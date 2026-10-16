"""Small helpers for writing problems as CNF.

>>> f = Formula()
>>> a, b, c = f.new_vars(3)
>>> f.exactly_one([a, b, c])
>>> f.add([-a])
>>> f.add([-b])
>>> s = f.solver()
>>> s.solve(), s.model[c - 1] > 0
(True, True)
"""

from __future__ import annotations

from typing import Iterable, Sequence

from .solver import Solver


class Formula:
    def __init__(self) -> None:
        self.num_vars = 0
        self.clauses: list[list[int]] = []

    def new_var(self) -> int:
        self.num_vars += 1
        return self.num_vars

    def new_vars(self, n: int) -> list[int]:
        return [self.new_var() for _ in range(n)]

    def add(self, clause: Iterable[int]) -> None:
        self.clauses.append(list(clause))

    def at_least_one(self, lits: Sequence[int]) -> None:
        self.add(lits)

    def at_most_one(self, lits: Sequence[int]) -> None:
        """Pairwise encoding for short lists, sequential counter otherwise.

        Pairwise needs n(n-1)/2 clauses; the sequential counter (Sinz 2005)
        needs about 3n clauses and n-1 auxiliary variables.
        """
        lits = list(lits)
        n = len(lits)
        if n <= 6:
            for i in range(n):
                for j in range(i + 1, n):
                    self.add([-lits[i], -lits[j]])
            return
        s = self.new_vars(n - 1)  # s[i]: "some lit among lits[0..i] is true"
        self.add([-lits[0], s[0]])
        for i in range(1, n - 1):
            self.add([-lits[i], s[i]])
            self.add([-s[i - 1], s[i]])
            self.add([-lits[i], -s[i - 1]])
        self.add([-lits[n - 1], -s[n - 2]])

    def exactly_one(self, lits: Sequence[int]) -> None:
        self.at_least_one(lits)
        self.at_most_one(lits)

    def solver(self) -> Solver:
        return Solver(self.clauses, num_vars=self.num_vars)
