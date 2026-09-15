"""A daily discount curve: one factor per calendar day from its start to its last date.
docs/library/globals/discount-curve.md is the page."""

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

ONE_DAY: Final = np.timedelta64(1, "D")


@dataclass(frozen=True, slots=True)
class DiscountCurve:
    """Dates and factors aligned by position, both read-only: dates[i] and factors[i] describe
    the same calendar day. The first date is the curve's start and the last is the furthest
    date the library may price."""

    dates: NDArray[np.datetime64]
    factors: NDArray[np.float64]

    @property
    def start_date(self) -> np.datetime64:
        return self.dates[0]

    @property
    def max_date(self) -> np.datetime64:
        return self.dates[-1]


def discount_curve(dates: NDArray[np.datetime64], factors: NDArray[np.float64]) -> DiscountCurve:
    """The one way to make a DiscountCurve: the rules of meaning, checked once, vectorized.

    Both arrays are copied and then frozen, so the curve owns its data: the seam's factors
    column is a view of the whole table's storage, and a Python caller keeps whatever it passed.
    Rows count as the sheet counts them, the first row of the body being row 1.
    """
    days = np.array(dates, dtype="datetime64[D]")
    values = np.array(factors, dtype=np.float64)
    bad = ~np.isfinite(values)
    if bad.any():  # before any arithmetic: numpy warns on inf - inf, and a warning fails here
        i = int(bad.argmax())
        raise ValueError(
            f"discount_factor row {i + 1} is {float(values[i])!r}, expected a finite number"
        )
    if values[0] != 1.0:
        raise ValueError(
            f"discount_factor row 1 is {float(values[0])!r}, "
            "expected exactly 1 at the curve's first date"
        )
    rises = values[1:] > values[:-1]
    if rises.any():
        k = int(rises.argmax())  # values[k + 1] is the first factor above the one before it
        raise ValueError(
            f"discount_factor rises at row {k + 2}, "
            f"from {float(values[k])!r} to {float(values[k + 1])!r}"
        )
    if values[-1] <= 0.0:
        raise ValueError(
            f"discount_factor row {values.size} is {float(values[-1])!r}, expected greater than 0"
        )
    gaps = days[1:] - days[:-1] != ONE_DAY
    if gaps.any():
        k = int(gaps.argmax())  # days[k + 1] is the first day that does not follow the one before
        raise ValueError(
            f"date row {k + 2} is {days[k + 1]}, expected {days[k] + ONE_DAY}, "
            "one day after the row above"
        )
    days.setflags(write=False)
    values.setflags(write=False)
    return DiscountCurve(days, values)
