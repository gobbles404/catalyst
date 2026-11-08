"""The payment arithmetic a bilateral batch of trades and a batch of cashflows share,
cashflow-instrument.md: a payment's time fraction from the valuation day, ACT/365F; the curve's
factor on each payment day, by position, the curve being daily from its start; the discounted
value of a known amount and its DV01, the analytic sensitivity to a rise of one basis point in
the continuously compounded zero rates; and the one rule of a curve against the valuation day,
that it starts there. Which days are payments, which have paid and which the curve must cover
are each evaluator's to decide and to name in its own words; the convention is
docs/library/trades/evaluate-trades.md's, and nothing here reads a trade, a cashflow or a
market."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from catalyst.globals.discount_curve import DiscountCurve


def time_fractions(as_of: np.datetime64, days: NDArray[np.datetime64]) -> NDArray[np.float64]:
    """The calendar days from the valuation day to each day over 365, ACT/365F, weekends and
    leap days counted: the time the DV01 and the cross-gamma weight a payment by."""
    return (days - as_of).astype(np.int64) / 365.0


def curve_starts_on(curve: DiscountCurve, as_of: np.datetime64) -> None:
    """A curve starts on the valuation day and is never rebased: refused in the words both
    evaluators share, since the sheet reads one rule."""
    if curve.start_date != as_of:
        raise ValueError(
            f"discount curve {curve.name!r} starts on {curve.start_date}, expected {as_of}, the "
            "valuation date; "
            "a curve is never rebased"
        )


def factors_on(curve: DiscountCurve, days: NDArray[np.datetime64]) -> NDArray[np.float64]:
    """The curve's factor on each day, read by position from its start, the curve being daily:
    one gather, nothing searched. The days are checked covered before, by the caller, which can
    name an uncovered one."""
    return curve.factors[(days - curve.start_date).astype(np.intp)]


def discounted(
    amounts: NDArray[np.float64], factors: NDArray[np.float64], tau: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Each amount's value today and its DV01: the amount times its factor, and -0.0001 times its
    time fraction times that value, negative for an amount receivable, the convention the
    cross-gamma moves by too. Two products over the payments; the caller judges the results
    finite, under numpy's flags down where it sums them."""
    npv = amounts * factors
    return npv, -0.0001 * tau * npv


def compensated(terms: Sequence[NDArray[np.float64] | float]) -> NDArray[np.float64]:
    """Two or more signed terms of a payment summed with compensation, every payment at once for
    arrays of one shape and once for floats: the running sum and the part each addition dropped,
    Knuth's two-sum, exact whatever the two magnitudes, added back at the end, so that a small
    leg's dollar survives a strike that cancels a large leg's ten thousand trillion whatever
    order the terms come in, the way the aggregation sums its saved vectors,
    two-index-one-price.md. Nothing is copied or written in place: each step makes its own
    arrays, and the caller holds numpy's flags down where arrays may outrun and judges the
    result: a sum past the largest number is inf, and the dropped part is added back only where
    it is finite, so an overflow stays inf and not nan, and infinities of both signs are nan,
    which no rule takes for finite."""
    held = terms[0]
    dropped: NDArray[np.float64] | float = 0.0
    for entries in terms[1:]:
        after = held + entries
        carried = after - held  # the part of entries that reached the sum
        dropped = dropped + ((held - (after - carried)) + (entries - carried))  # the rest
        held = after
    return np.where(np.isfinite(dropped), held + dropped, held)
