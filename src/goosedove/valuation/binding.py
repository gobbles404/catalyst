"""The binding: one price per observation for one valuation, the print where the observation
has fixed and the mark of its contract where it has not, made from the market's answers and
refusing a fixed observation without a print, so that a missing print never shortens an
average. docs/library/valuation/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import OBSERVATION, WorkCounter
from goosedove.valuation.columns import finite, kept, rows


@dataclass(frozen=True, slots=True)
class Binding:
    """Three columns aligned by position per observation and one per mark, all read-only.
    is_fixed[o] is whether observation o has fixed, as its index's calendar says; price[o] its
    price, the print where it has fixed and marks[mark_of[o]] where it has not; mark_of[o] the
    row of the mark that prices it while it has not fixed, read only there; and marks[m] the
    current price of mark m, the vector the sheet supplied, one per contract the terms may
    read. The marks and the mapping stay here so that the compressed view, which folds the
    terms by mark, is made from the binding alone."""

    is_fixed: NDArray[np.bool_]
    price: NDArray[np.float64]
    mark_of: NDArray[np.intp]
    marks: NDArray[np.float64]

    @property
    def observations(self) -> int:
        return self.price.size


def binding(
    is_fixed: NDArray[np.bool_],
    prints: NDArray[np.float64],
    mark_of: NDArray[np.intp],
    marks: NDArray[np.float64],
    counter: WorkCounter,
) -> Binding:
    """The one way to make a Binding: five rules, checked once, vectorized, in this order, the
    first failure being the message; then one price per observation, in one gather, and one
    copy of each column, frozen.

    The prints and the mapping of one length with the flags, one row per observation. Every
    mark a finite number. Every fixed observation with a finite print: a day that has passed
    and has no print is refused, never dropped, so that an average is never taken over fewer
    days than its contract names; a print on an observation not yet fixed is not read, the
    flag being the calendar's answer. Every unfixed observation's mark a row of the marks,
    counted from zero; a fixed observation's mapping is not read, its contract may have
    expired. The work is one observation priced per row, counted on the counter. Rows count as
    the sheet counts them, the first being row 1.
    """
    for name, column in (("prints", prints), ("mark_of", mark_of)):
        if column.size != is_fixed.size:
            raise ValueError(
                f"{name} has {column.size} {rows(column.size)}, expected {is_fixed.size}, "
                "one per observation as is_fixed has"
            )
    finite("marks", marks)
    missing = is_fixed & ~np.isfinite(prints)
    if missing.any():
        o = int(missing.argmax())
        raise ValueError(
            f"prints row {o + 1} is {float(prints[o])!r}, expected a finite number, "
            f"since observation {o + 1} has fixed"
        )
    live = np.flatnonzero(~is_fixed)
    of = mark_of[live]
    outside = (of < 0) | (of >= marks.size)
    if outside.any():
        k = int(outside.argmax())
        o = int(live[k])
        wanted = (
            f"0 through {marks.size - 1}, the marks counted from zero"
            if marks.size
            else "a mark, and marks has 0 rows"
        )
        raise ValueError(
            f"mark_of row {o + 1} is {int(of[k])}, expected {wanted}, "
            f"since observation {o + 1} has not fixed"
        )
    counter.hit(OBSERVATION, is_fixed.size)
    price = prints.copy()
    price[live] = marks[of]
    price.setflags(write=False)
    return Binding(kept(is_fixed), price, kept(mark_of), kept(marks))
