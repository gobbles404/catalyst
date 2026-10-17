"""A daily discount curve: one factor per calendar day from its start to its last date, built
from the anchors the desk supplies, the days between them filled by a straight line on the
factor. docs/library/globals/discount-curve.md is the page."""

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.interpolation import interpolate_discount_factors
from goosedove.instrumentation.work_counts import WorkCounter

# The most days a curve holds: a sheet's rows less the two heading rows util_ReadHandle spills
# first, so that whatever a creator keeps can be read back. A curve two thousand years long that
# no cell could show was a finding of the review of #70; the seam's own bound on a result's size
# is open in docs/seam/history.md.
MAX_DAYS: Final = 1_048_574


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
    # Before any arithmetic: numpy warns on inf - inf, and a warning fails here. The mask is the
    # finite one, asked whether every factor is; its inverse is made only to name the first that
    # is not.
    finite = np.isfinite(factors)
    if not finite.all():
        i = int((~finite).argmax())
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
    if days[-1] - days[0] >= np.timedelta64(MAX_DAYS, "D"):
        raise ValueError(
            f"date row {days.size} is {days[-1]}, "
            f"expected within {MAX_DAYS - 1} days of row 1's {days[0]}"
        )
    every_day, values = interpolate_discount_factors(days, factors)
    every_day.setflags(write=False)
    values.setflags(write=False)
    return DiscountCurve(every_day, values)


FACTORS_SHIFTED = "factors_shifted"  # one per stored day of the curve bumped, since each is moved


def bump_discount_curve(
    curve: DiscountCurve, bump_bps: float, counter: WorkCounter
) -> DiscountCurve:
    """The one way to bump a DiscountCurve, bump-discount-curve.md: a parallel shift of its
    continuously compounded zero rates by that many basis points, the move the DV01 and the
    cross-gamma measure, applied to every stored day's factor from the curve's own start,
    ACT/365F, and the result built through the ordinary constructor over the daily table, so
    that the curve's rules judge it and nothing here says again what a curve is.

    tau is the calendar days from the start over 365, and the day's factor becomes
    factor * exp(-bump_bps / 10000 * tau). A bump up lowers every factor after the first; a bump
    down raises them, and is accepted while no factor rises on the one before, so a curve of
    ones bumped down is refused by the row that rose, as is a bump so large that a factor
    overflows or underflows to nothing, numpy's flags down and the rules the judge. The first
    factor stays 1 exactly, since exp(0) is 1; a bump of nothing moves nothing, bit for bit. The
    bump is a finite number, as the sheet sends one, a Python caller's nan or inf refused by
    name; no text is read and nothing is rounded. The curve is read and never written, and the
    new curve owns its arrays, frozen. Work: one factor shifted per stored day, reported to the
    counter, and the constructor's own over the curve's length; nothing per trade, no market,
    history or valuation date read.
    """
    if not math.isfinite(bump_bps):
        raise ValueError(f"bump_bps is {bump_bps!r}, expected a finite number of basis points")
    tau = (curve.dates - curve.start_date).astype(np.int64) / 365.0
    with np.errstate(over="ignore", under="ignore"):  # the constructor's rules are the judge
        shifted = curve.factors * np.exp(-(bump_bps / 10000.0) * tau)
    counter.hit(FACTORS_SHIFTED, int(shifted.size))
    return discount_curve(curve.dates, shifted)
