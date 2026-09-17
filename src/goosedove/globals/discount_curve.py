"""A daily discount curve: one factor per calendar day from its start to its last date, built
from the anchors the desk supplies, the days between them filled by a straight line on the
factor. docs/library/globals/discount-curve.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.interpolation import interpolate_discount_factors


@dataclass(frozen=True, slots=True)
class DiscountCurve:
    """Dates and factors aligned by position, both read-only, one row per calendar day: dates[i]
    and factors[i] describe the same day. The first date is the curve's start and the last is
    the furthest date the library may price."""

    dates: NDArray[np.datetime64]
    factors: NDArray[np.float64]

    @property
    def start_date(self) -> np.datetime64:
        return self.dates[0]

    @property
    def max_date(self) -> np.datetime64:
        return self.dates[-1]


def discount_curve(dates: NDArray[np.datetime64], factors: NDArray[np.float64]) -> DiscountCurve:
    """The one way to make a DiscountCurve: the rules of meaning on the anchors, checked once,
    vectorized, then every day from the first anchor to the last filled in.

    The anchors are the rows the desk supplies, the first the curve's start, with any gaps
    between their dates: a daily table is anchors with no gaps. What the curve keeps is the days
    and their factors, made here and frozen, so the curve owns its data and a Python caller keeps
    whatever it passed. Rows count as the sheet counts them, the first row of the body being
    row 1.
    """
    days = np.asarray(dates, dtype="datetime64[D]")  # read, never written: no copy of the anchors
    bad = ~np.isfinite(factors)
    if bad.any():  # before any arithmetic: numpy warns on inf - inf, and a warning fails here
        i = int(bad.argmax())
        raise ValueError(
            f"discount_factor row {i + 1} is {float(factors[i])!r}, expected a finite number"
        )
    if factors[0] != 1.0:
        raise ValueError(
            f"discount_factor row 1 is {float(factors[0])!r}, "
            "expected exactly 1 at the curve's first date"
        )
    rises = factors[1:] > factors[:-1]
    if rises.any():
        k = int(rises.argmax())  # factors[k + 1] is the first factor above the one before it
        raise ValueError(
            f"discount_factor rises at row {k + 2}, "
            f"from {float(factors[k])!r} to {float(factors[k + 1])!r}"
        )
    if factors[-1] <= 0.0:
        raise ValueError(
            f"discount_factor row {factors.size} is {float(factors[-1])!r}, expected greater than 0"
        )
    unordered = days[1:] <= days[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # days[k + 1] is the first date not after the one before it
        raise ValueError(
            f"date row {k + 2} is {days[k + 1]}, expected a date after row {k + 1}'s {days[k]}"
        )
    every_day, values = interpolate_discount_factors(days, factors)
    every_day.setflags(write=False)
    values.setflags(write=False)
    return DiscountCurve(every_day, values)
