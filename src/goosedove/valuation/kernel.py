"""The kernel: the arithmetic between the terms, a binding and the marks, with no product, date,
code or name in it. The amounts, one per component, each its fixed leg plus the sum over its
terms of coefficient times price, in one gather and one grouped sum. The compressed view of the
terms under one binding: per component its fixed leg, the printed part of its floating leg and
their sum, the constant, and one coefficient per mark, which is the sensitivity table and prices
a new vector of marks in one multiply. And the dense view, the terms laid into a rectangle for
the eye. Work is counted, never timed. docs/library/valuation/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import CELL, KERNEL, TERM, WorkCounter
from goosedove.valuation.binding import Binding, prices
from goosedove.valuation.columns import kept
from goosedove.valuation.terms import Terms


def amounts(
    terms: Terms, binding: Binding, marks: NDArray[np.float64], counter: WorkCounter
) -> NDArray[np.float64]:
    """One amount per component, in the settlement currency: its fixed leg plus the sum of
    coefficient times price over its terms, the price being the one prices() gives the term's
    observation under these marks, its print where it has fixed and its contract's mark where
    it has not. One rule, that the binding covers every observation the terms read, and the two
    of prices(); then one gather of a price per term, one multiply in place, one sum per run of
    terms, the terms being grouped by component, and one add of the fixed legs: one array made
    the length of the observations, one the length of the terms and a few the length of the
    components, and no copy of any column. The work is the prices' one observation per
    observation and one term per term, counted on the counter."""
    _covers(terms, binding)
    price = prices(binding, marks, counter)
    counter.hit(KERNEL)
    counter.hit(TERM, terms.coefficient.size)
    products = price[terms.observation]
    products *= terms.coefficient
    sums = np.zeros(terms.components)
    runs = terms.first[:-1] < terms.first[1:]  # the components with a term
    if runs.any():
        sums[runs] = np.add.reduceat(products, terms.first[:-1][runs])
    return terms.fixed_leg + sums


@dataclass(frozen=True, slots=True)
class Compressed:
    """The terms folded by mark for one binding, all read-only. fixed_leg[c] is component c's
    fixed leg, as the terms hold it; printed[c] the printed part of its floating leg, each of its
    fixed terms' coefficient times its print; constant[c] the two added, the part of its amount
    no mark moves, added once here so that a tick adds one number; and coefficient[c, m] the sum
    of the coefficients of its unfixed terms that mark m prices, the amount per unit of that
    mark, which is what a move in the mark does to the amount. The sheet's compressed view: one
    row per component, one column per mark, the fixed leg, the printed part and the constant
    beside. Valid for the binding it was made from and no other: a day that fixes, a print that
    is corrected or a valuation date that moves calls for a new one, and a tick for none."""

    fixed_leg: NDArray[np.float64]
    printed: NDArray[np.float64]
    constant: NDArray[np.float64]
    coefficient: NDArray[np.float64]

    @property
    def components(self) -> int:
        return self.constant.size

    @property
    def marks(self) -> int:
        return self.coefficient.shape[1]


def compressed(terms: Terms, binding: Binding, counter: WorkCounter) -> Compressed:
    """The one way to make Compressed: one rule, that the binding covers every observation the
    terms read; then every term folded once, the unfixed ones summed by component and mark into
    the coefficients and the fixed ones, each times its print, summed by component into the
    printed parts, which are added to the fixed legs once to make the constants. No mark is
    read: the binding holds none, and the view is made once per fixing state. The work is one
    term per term and one cell per cell of the view made, zeros included, both counted on the
    counter: the view is components times marks whatever the terms, and the count is what shows
    it. Nothing is timed."""
    _covers(terms, binding)
    marks = binding.marks
    counter.hit(KERNEL)
    counter.hit(TERM, terms.coefficient.size)
    counter.hit(CELL, terms.components * marks)
    fixed = binding.is_fixed[terms.observation]
    live = ~fixed
    keys = terms.component[live] * marks + binding.mark_of[terms.observation[live]]
    # the cells start at zero and each unfixed term is added into its own, in the order given; so
    # they hold numbers with a fraction even when no term is added, where bincount gives integers
    cells = np.zeros(terms.components * marks)
    np.add.at(cells, keys, terms.coefficient[live])
    cells.setflags(write=False)  # the sum itself, so that the view cannot be made writable alone
    folded = binding.prints[terms.observation[fixed]]
    folded *= terms.coefficient[fixed]
    printed = np.zeros(terms.components)  # the same order of addition as the cells
    np.add.at(printed, terms.component[fixed], folded)
    printed.setflags(write=False)
    constant = terms.fixed_leg + printed
    constant.setflags(write=False)
    return Compressed(
        kept(terms.fixed_leg), printed, constant, cells.reshape(terms.components, marks)
    )


def compressed_amounts(
    compressed: Compressed, marks: NDArray[np.float64], counter: WorkCounter
) -> NDArray[np.float64]:
    """One amount per component from the compressed view and a vector of marks, the tick: the
    coefficients times the marks, one multiply of the rectangle by the vector, plus the
    constants, the fixed legs and the printed parts added once when the view was made. One rule,
    that the vector has one mark per column. The work is one cell per cell of the rectangle,
    zeros included, counted on the counter; the marks must be the same marks, in the same order,
    the binding was made for, which the vector cannot say and the sheet keeps right."""
    if marks.size != compressed.marks:
        raise ValueError(
            f"marks has {marks.size} {'row' if marks.size == 1 else 'rows'}, "
            f"expected {compressed.marks}, one per mark as the compressed view has"
        )
    counter.hit(KERNEL)
    counter.hit(CELL, compressed.coefficient.size)
    return compressed.coefficient @ marks + compressed.constant


def dense(terms: Terms, binding: Binding, counter: WorkCounter) -> NDArray[np.float64]:
    """The terms laid into a rectangle, one row per component and one column per observation
    of the binding, each cell the sum of the coefficients of that component's terms on that
    observation and zero elsewhere, so that the rectangle times the prices under any marks plus
    the fixed legs is the amounts. A view for the eye and the reference the other two
    calculations are checked against, made on request and kept by nobody: components times
    observations cells, most of them zero, each counted on the counter."""
    _covers(terms, binding)
    counter.hit(KERNEL)
    counter.hit(CELL, terms.components * binding.observations)
    rectangle = np.zeros((terms.components, binding.observations))
    np.add.at(rectangle, (terms.component, terms.observation), terms.coefficient)
    return rectangle


def _covers(terms: Terms, binding: Binding) -> None:
    """The binding binds every observation the terms read: one comparison of two numbers, the
    terms' highest observation having been found once when they were made."""
    if binding.observations < terms.observations:
        raise ValueError(
            f"binding has {binding.observations} "
            f"{'observation' if binding.observations == 1 else 'observations'}, "
            f"expected {terms.observations} or more, "
            f"since the terms read observation row {terms.observations}"
        )
