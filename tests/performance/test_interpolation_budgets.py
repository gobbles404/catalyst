"""What interpolating contract prices costs, interpolate-contract-prices.md: the counter's anchors,
schedule rows, months and the one interpolation; the same functions and numpy calls at three
months and at a hundred and twenty; the peak following the schedule's rows and the months
generated, nothing per day between the expiries; and the retained bytes exactly the two arrays'.
The small index is the ticket's CL-style three months; the large one a hundred and twenty monthly
contracts from January 2027, each expiring on the 20th of the month before."""

from collections.abc import Callable

import numpy as np
import pytest
from test_seam_allocation import SLACK, least_peak

from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.contract_codes import code_of_month
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.holiday_calendar import holiday_calendar
from catalyst.index_definitions.index import Index, index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market_data.interpolated_contracts import interpolate_contracts

CallProfile = Callable[[Callable[[], object]], dict[str, int]]


def futures_index(name: str, codes: tuple[str, ...], expiries: np.ndarray) -> Index:
    return index(
        name,
        f"{name} index",
        futures_schedule(codes, expiries, None),
        index_conventions("DOLLAR", "BBL", "DOLLAR", "VOLUME", "BBL", UNITS),
        contract_specifications(
            ("LOT",), np.array([1000.0]), ("BBL",), np.array([0.0]), np.array([0.0]), UNITS
        ),
        holiday_calendar(np.array(["2030-01-01"], dtype="datetime64[D]")),
        "LOT",
        UNITS,
    )


CL = futures_index(
    "CL",
    ("J27", "K27", "M27"),
    np.array(["2027-03-22", "2027-04-20", "2027-05-20"], "datetime64[D]"),
)
MONTHS = np.arange("2027-01", "2037-01", dtype="datetime64[M]")  # a hundred and twenty
LONG = futures_index(
    "LONG",
    tuple([code_of_month(m.astype("datetime64[D]")) for m in MONTHS]),
    (MONTHS - np.timedelta64(1, "M")).astype("datetime64[D]") + np.timedelta64(19, "D"),
)
CASES = [
    (CL, ("J27", "M27"), (70.0, 76.0), 3),
    (LONG, ("F27", "K30", "Z36"), (60.0, 66.0, 72.0), 120),
]
IDS = ["three months, two anchors", "a hundred and twenty months, three anchors"]


def prices_of(*values: float) -> np.ndarray:
    return np.array(values, dtype=np.float64)


@pytest.mark.parametrize(("ix", "anchors", "prices", "months"), CASES, ids=IDS)
def test_the_counter_reports_anchors_rows_months_and_one_interpolation(
    ix: Index, anchors: tuple[str, ...], prices: tuple[float, ...], months: int
) -> None:
    counter = WorkCounter()
    made = interpolate_contracts(ix, anchors, prices_of(*prices), counter)
    assert len(made.codes) == months
    assert counter.freeze().as_dict() == {
        "anchors_read": len(anchors),
        "interpolations": 1,
        "months_generated": months,
        "schedule_rows_read": len(ix.schedule.codes),
    }


# The anchors read, one look per label and one per code of the schedule, the months generated
# and placed by one sort and one search, the expiries gathered, the line drawn once; the same
# at three months and at a hundred and twenty, nothing per day between the expiries.
@pytest.mark.parametrize(("ix", "anchors", "prices", "months"), CASES, ids=IDS)
def test_the_same_functions_and_numpy_calls_at_any_size(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    ix: Index,
    anchors: tuple[str, ...],
    prices: tuple[float, ...],
    months: int,
) -> None:
    given = prices_of(*prices)
    assert call_profile(lambda: interpolate_contracts(ix, anchors, given, WorkCounter())) == {
        "interpolate_contracts": 1,
        "_anchor_months": 1,
        "_month_of": len(anchors),  # one reading per label
        "month_and_year": len(anchors) + len(ix.schedule.codes),  # the codes' own reading
        "schedule_months": 1,  # every row of the schedule, once
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 4,
    }
    # numpy's own calls under the kernel's: the anchors' months and the schedule's sorted, the
    # wanted months placed by one search, each rule's mask reduced once, the line drawn once and
    # the two arrays frozen; the same ledger whatever the size.
    assert numpy_calls(lambda: interpolate_contracts(ix, anchors, given, WorkCounter())) == {
        "numpy.empty": 2,
        "numpy.arange": 1,
        "ndarray.argsort": 3,
        "ndarray.searchsorted": 1,
        "ndarray.nonzero": 4,
        "ndarray.ravel": 4,
        "ndarray.all": 3,
        "ndarray.any": 1,
        "ufunc.reduce": 4,
        "numpy.asarray": 2,
        "numpy.asanyarray": 4,
        "numpy._make_extobj": 1,
        "numpy.interp": 1,
        "ndarray.setflags": 2,
    }


# The peak follows the schedule's rows, their months and their order, and the months generated,
# the day offsets, the places and the two arrays kept; nothing per day between the expiries.
# Measured 2026-10-17: 6,408 bytes for three months and 12,689 for a hundred and twenty, each on
# a schedule of as many rows; 102,178 for twelve hundred; and 31,775 for three months on a
# schedule of twelve hundred rows: about 21 bytes a row and 59 a month beyond some six slacks
# of small objects.
@pytest.mark.parametrize(("ix", "anchors", "prices", "months"), CASES, ids=IDS)
def test_the_peak_follows_the_rows_and_the_months_and_the_retained_bytes_are_the_arrays(
    ix: Index, anchors: tuple[str, ...], prices: tuple[float, ...], months: int
) -> None:
    given = prices_of(*prices)
    rows = len(ix.schedule.codes)
    assert least_peak(lambda: interpolate_contracts(ix, anchors, given, WorkCounter())) <= (
        24 * rows + 64 * months + 7 * SLACK
    )
    made = interpolate_contracts(ix, anchors, given, WorkCounter())
    assert made.prices.nbytes + made.expiries.nbytes == 16 * months
    assert not made.prices.flags.writeable and not made.expiries.flags.writeable
