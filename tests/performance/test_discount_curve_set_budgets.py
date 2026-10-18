"""What collecting discount curves costs, named-curves-slice-1.md: one curve counted per curve
given, the names read once each for the repeat rule, no date read and no factor copied, so the
work and the peak follow the curves and never their days; through the seam, each handle resolved
once, one publication and a readback of one row per curve."""

from collections.abc import Callable

import numpy as np
import pytest
from test_seam_allocation import ENTRY, SLACK, least_peak, retained_numpy_bytes

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells
from goosedove.globals.discount_curve import DiscountCurve, discount_curve
from goosedove.globals.discount_curve_set import collect_discount_curves
from goosedove.instrumentation.work_counts import WorkCounter

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
FIRST = np.datetime64("2026-09-11", "D")
SIZES = [1, 2, 24]
IDS = ["one curve", "two curves", "two dozen"]
CURVE_HEADERS = Cells.from_rows([["date", "discount_factor"]])


def a_curve(name: str, days: int) -> DiscountCurve:
    dates = np.arange(FIRST, FIRST + np.timedelta64(days, "D"), dtype="datetime64[D]")
    return discount_curve(name, dates, 1.0 - np.arange(days, dtype=np.float64) * 1e-6)


def curves(count: int, days: int) -> tuple[DiscountCurve, ...]:
    return tuple(a_curve(f"CURVE_{i}", days) for i in range(count))


# --- the library ----------------------------------------------------------------------------------


@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_the_counter_reports_one_curve_collected_per_curve_given(count: int) -> None:
    counter = WorkCounter()
    made = collect_discount_curves(curves(count, 3_631), counter)
    assert len(made.curves) == count
    assert counter.freeze().as_dict() == {"curves_collected": count}


# One pass over the curves for the repeat rule and one count: no numpy call at all, whatever the
# curves' lengths, since no date is read and no factor touched.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_collecting_runs_no_numpy_whatever_the_curves_lengths(
    call_profile: CallProfile, numpy_calls: CallProfile, count: int
) -> None:
    given = curves(count, 3_631)
    assert call_profile(lambda: collect_discount_curves(given, WorkCounter())) == {
        "collect_discount_curves": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 1,
    }
    assert numpy_calls(lambda: collect_discount_curves(given, WorkCounter())) == {}


# The peak is the tuple, the dictionary of names and the record, about 48 bytes a curve beyond
# a slack of small objects whatever the curves' lengths: measured 240 bytes at one and at two
# curves of ten years, 1,408 at two dozen and 5,024 at a hundred on 2026-10-18; the collection
# keeps no array of its own.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_the_peak_follows_the_curves_and_nothing_of_their_days(count: int) -> None:
    given = curves(count, 3_631)
    assert least_peak(lambda: collect_discount_curves(given, WorkCounter())) <= (SLACK + 48 * count)


# --- through the seam -----------------------------------------------------------------------------


def handles(count: int, days: int) -> Cells:
    body = Cells.from_rows([[46276.0 + i, 1.0 - i * 1e-5] for i in range(days)])
    return Cells.from_rows(
        [[ENTRY["_CreateDiscountCurve"](f"CURVE_{i}", CURVE_HEADERS, body)] for i in range(count)]
    )


# The vector's shape checked once, the cells decoded in one pass, each resolved once, the
# library's one pass and one publication: the seam's calls grow with the handles and nothing
# else does, and no numpy runs.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_a_collection_resolves_each_curve_once_and_publishes_once(
    call_profile: CallProfile, numpy_calls: CallProfile, count: int
) -> None:
    given = handles(count, 8)
    ENTRY["_CollectDiscountCurves"](given)
    assert call_profile(lambda: ENTRY["_CollectDiscountCurves"](given)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve_each": 1,
        "_values": 1,
        "_decoded": count,
        "_text": count,
        "_resolve": count,
        "_CollectDiscountCurves": 1,
        "WorkCounter.__init__": 1,
        "collect_discount_curves": 1,
        "WorkCounter.hit": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: ENTRY["_CollectDiscountCurves"](given)) == {}


# Through the seam a collection pays the vector's decoding and its publication, some five and a
# half kilobytes of small objects whatever the curves' lengths, and a few bytes a curve: measured
# 5,568 bytes at one ten-year curve, 5,616 at two, 5,776 at two dozen and 6,448 at a hundred on
# 2026-10-18. It keeps no numpy bytes of its own: the curves are theirs, made before and held by
# reference, and release frees nothing because nothing was kept.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_a_collection_costs_small_objects_and_keeps_no_bytes_of_its_own(count: int) -> None:
    given = handles(count, 3_631)
    assert least_peak(lambda: ENTRY["_CollectDiscountCurves"](given)) <= 6 * SLACK + 16 * count
    assert retained_numpy_bytes(lambda: ENTRY["_CollectDiscountCurves"](given)) == (0, 0)


# Reading a collection back lays out one row per curve, four columns, the spans to serials,
# about 86 bytes a curve beyond two slacks: measured 2,037 bytes at one curve, 2,114 at two,
# 4,040 at two dozen and 10,500 at a hundred on 2026-10-18; nothing is published.
@pytest.mark.parametrize("count", SIZES, ids=IDS)
def test_reading_a_collection_back_is_one_row_per_curve(count: int) -> None:
    collection = ENTRY["_CollectDiscountCurves"](handles(count, 3_631))
    live = bridge.live_handles()
    assert least_peak(lambda: ENTRY["util_ReadHandle"](collection)) <= 2 * SLACK + 96 * count
    assert bridge.live_handles() == live
