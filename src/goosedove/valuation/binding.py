"""The binding: where each observation's price comes from for one fixing state, its print where
the observation has fixed and the contract whose mark prices it where it has not, holding no
mark; and the prices, one per observation for one vector of marks. The binding is made when a
day fixes, a print is corrected or the valuation date moves, and refuses a fixed observation
without a print, so that a missing print never shortens an average; a tick brings only the
marks. docs/library/valuation/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import OBSERVATION, WorkCounter
from goosedove.valuation.columns import finite, kept, rows


@dataclass(frozen=True, slots=True)
class Binding:
    """Three columns aligned by position per observation, all read-only, and one number, for one
    fixing state and no mark's value. is_fixed[o] is whether observation o has fixed, as its
    index's calendar says; prints[o] its print where it has, the price it is bound to for good,
    and nothing that is read where it has not; mark_of[o] the row of the mark that prices it
    while it has not fixed, the contract it is bound to, read only there; and marks how many
    marks a tick brings, one per contract the terms may read, in the order the price vector
    gives them. The marks themselves come with each tick, to prices() and to a compressed view,
    so that a tick changes nothing held here."""

    is_fixed: NDArray[np.bool_]
    prints: NDArray[np.float64]
    mark_of: NDArray[np.intp]
    marks: int

    @property
    def observations(self) -> int:
        return self.is_fixed.size


def binding(
    is_fixed: NDArray[np.bool_],
    prints: NDArray[np.float64],
    mark_of: NDArray[np.intp],
    marks: int,
) -> Binding:
    """The one way to make a Binding: four rules, checked once, vectorized, in this order, the
    first failure being the message; then one copy of each column, frozen. Once per fixing state,
    never on a tick, and no price is made, so nothing is counted.

    The prints and the mapping of one length with the flags, one row per observation. Every
    fixed observation with a finite print: a day that has passed and has no print is refused,
    never dropped, so that an average is never taken over fewer days than its contract names; a
    print on an observation not yet fixed is not read, the flag being the calendar's answer.
    Every unfixed observation's mark a row of the marks, counted from zero; a fixed
    observation's mapping is not read, its contract may have expired. Rows count as the sheet
    counts them, the first being row 1.
    """
    for name, column in (("prints", prints), ("mark_of", mark_of)):
        if column.size != is_fixed.size:
            raise ValueError(
                f"{name} has {column.size} {rows(column.size)}, expected {is_fixed.size}, "
                "one per observation as is_fixed has"
            )
    missing = is_fixed & ~np.isfinite(prints)
    if missing.any():
        o = int(missing.argmax())
        raise ValueError(
            f"prints row {o + 1} is {float(prints[o])!r}, expected a finite number, "
            f"since observation {o + 1} has fixed"
        )
    live = np.flatnonzero(~is_fixed)
    of = mark_of[live]
    outside = (of < 0) | (of >= marks)
    if outside.any():
        k = int(outside.argmax())
        o = int(live[k])
        wanted = (
            f"0 through {marks - 1}, the marks counted from zero"
            if marks
            else "a mark, and marks is 0"
        )
        raise ValueError(
            f"mark_of row {o + 1} is {int(of[k])}, expected {wanted}, "
            f"since observation {o + 1} has not fixed"
        )
    return Binding(kept(is_fixed), kept(prints), kept(mark_of), marks)


def prices(
    binding: Binding, marks: NDArray[np.float64], counter: WorkCounter
) -> NDArray[np.float64]:
    """One price per observation for one vector of marks: the print where the observation has
    fixed and the mark of its contract where it has not, the sheet's price used. Two rules, in
    this order, the first failure being the message: the vector has one mark per mark the
    binding names, and every mark is a finite number. Then one copy of the prints and one
    gather of a mark per unfixed observation, a new array each call. The work is one
    observation priced per observation, counted on the counter; a failed call counts nothing.
    The marks must be the marks, in the order, the binding was made for, which the vector
    cannot say and the sheet keeps right."""
    if marks.size != binding.marks:
        raise ValueError(
            f"marks has {marks.size} {rows(marks.size)}, expected {binding.marks}, "
            "one per mark as the binding has"
        )
    finite("marks", marks)
    counter.hit(OBSERVATION, binding.observations)
    live = np.flatnonzero(~binding.is_fixed)
    price = binding.prints.copy()
    price[live] = marks[binding.mark_of[live]]
    return price
