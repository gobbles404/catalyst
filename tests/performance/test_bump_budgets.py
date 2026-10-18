"""What bumping a discount curve costs, bump-discount-curve.md: the counter's factors shifted,
one per stored day; the same functions and numpy calls at eight days and at ten years; the peak
following the curve's length, the shift's own arrays and the constructor's filling; and the new
curve's retained bytes its two arrays, the source's untouched. The curves are daily tables from
11 September 2026, the factors falling a millionth a day."""

from collections.abc import Callable

import numpy as np
import pytest
from test_seam_allocation import SLACK, least_peak

from goosedove.globals.discount_curve import DiscountCurve, bump_discount_curve, discount_curve
from goosedove.instrumentation.work_counts import WorkCounter

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
FIRST = np.datetime64("2026-09-11", "D")
SIZES = [8, 366, 3_631]
IDS = ["eight days", "a year and a day", "ten years"]


def daily_curve(days: int) -> DiscountCurve:
    dates = np.arange(FIRST, FIRST + np.timedelta64(days, "D"), dtype="datetime64[D]")
    return discount_curve("SOFR", dates, 1.0 - np.arange(days, dtype=np.float64) * 1e-6)


@pytest.mark.parametrize("days", SIZES, ids=IDS)
def test_the_counter_reports_one_factor_shifted_per_stored_day(days: int) -> None:
    curve = daily_curve(days)
    counter = WorkCounter()
    made = bump_discount_curve(curve, 1.0, counter)
    assert made.factors.size == days
    assert counter.freeze().as_dict() == {"factors_shifted": days}


# The start read once, the days' offsets, one exp over them and one product, then the
# constructor's own looks and its filling of the daily table; the same whatever the length, the
# work per day inside numpy calls no ledger counts. Nothing per trade, no market, history or
# valuation date read.
@pytest.mark.parametrize("days", SIZES, ids=IDS)
def test_the_same_functions_and_numpy_calls_at_any_length(
    call_profile: CallProfile, numpy_calls: CallProfile, days: int
) -> None:
    curve = daily_curve(days)
    assert call_profile(lambda: bump_discount_curve(curve, 1.0, WorkCounter())) == {
        "bump_discount_curve": 1,
        "DiscountCurve.start_date": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 1,
        "discount_curve": 1,
        "curve_name": 1,  # the name rule, shared with the key since slice 3
        "interpolate_discount_factors": 1,
    }
    assert numpy_calls(lambda: bump_discount_curve(curve, 1.0, WorkCounter())) == {
        "ndarray.astype": 2,  # the days from the start as counts, and the constructor's gaps
        "numpy._make_extobj": 1,  # numpy's flags down around the shift
        "ndarray.all": 1,  # every factor finite
        "ndarray.any": 2,  # none rising; the dates in order
        "ufunc.reduce": 3,
        "numpy.asarray": 2,
        "numpy.arange": 2,  # the constructor's day grid and the offsets it interpolates over
        "numpy.interp": 1,
        "ndarray.repeat": 1,
        "ndarray.setflags": 2,  # frozen
    }


# The peak follows the curve's length: the offsets, the shift and the shifted factors, then the
# constructor's day grid, offsets, the anchors each day runs to and the two arrays it keeps, about
# 59 bytes a day beyond two slacks of small objects. Measured 2026-10-17: 2,606 bytes at eight
# days, 23,760 at 366, 216,395 at 3,631 and 2,157,141 at a century's 36,525.
@pytest.mark.parametrize("days", SIZES, ids=IDS)
def test_the_peak_follows_the_length_and_the_new_curve_keeps_sixteen_bytes_a_day(
    days: int,
) -> None:
    curve = daily_curve(days)
    assert least_peak(lambda: bump_discount_curve(curve, 1.0, WorkCounter())) <= (
        64 * days + 3 * SLACK
    )
    made = bump_discount_curve(curve, 1.0, WorkCounter())
    assert made.dates.nbytes + made.factors.nbytes == 16 * days
    assert not np.shares_memory(made.dates, curve.dates)
    assert not np.shares_memory(made.factors, curve.factors)
