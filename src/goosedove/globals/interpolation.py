"""Filling the days between a curve's anchors: a straight line on the discount factor itself,
weighted by calendar days, the library's one rule for interpolation, in
docs/library/conventions.md under What holds everywhere. The curve's page,
docs/library/globals/discount-curve.md, is where the calculation is written down; it has no
worksheet surface of its own."""

from typing import Final

import numpy as np
from numpy.typing import NDArray

ONE_DAY: Final = np.timedelta64(1, "D")


def interpolate_discount_factors(
    dates: NDArray[np.datetime64], factors: NDArray[np.float64]
) -> tuple[NDArray[np.datetime64], NDArray[np.float64]]:
    """Every calendar day from the first anchor to the last, inclusive, and the factor on each:
    an anchor keeps its own factor exactly, and a day between two anchors takes the straight line
    between their factors, weighted by calendar days, weekends and leap days included.

    The anchors are taken as checked, dates strictly increasing with one factor per date, the
    factors never rising, which is the builder's job. numpy's interp is the implementation: it
    would repeat an endpoint outside the anchors and never sorts, so it is asked only for the
    days between the first anchor and the last, in the order the anchors arrived. No day is made
    before the first anchor or after the last. Vectorized: nothing runs per day.

    The line is then held above the anchor it runs to. In arithmetic it never falls below that
    anchor; in float64 the slope's rounding can take it a step below, near underflow, and a curve
    that rose on its last day was a finding of the review of #70. The line never rises above the
    anchor it runs from, since it adds a non-positive step to it, so the hold is the one bound
    left to keep, and for any ordinary curve it changes nothing.
    """
    days = np.arange(dates[0], dates[-1] + ONE_DAY, dtype="datetime64[D]")
    offsets = (dates - dates[0]) / ONE_DAY
    values = np.interp(np.arange(days.size, dtype=np.float64), offsets, factors)
    # The anchor each day runs to: the first anchor for its own day, then each later anchor for
    # every day since the one before it.
    counts = np.concatenate(([1], (dates[1:] - dates[:-1]).astype(np.int64)))
    np.maximum(values, np.repeat(factors, counts), out=values)
    return days, values
