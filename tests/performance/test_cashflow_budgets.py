"""What booking and valuing cashflows cost, cashflow-instrument.md and cashflow-curve-keys.md: the
counters, one cashflow per ticket row, one payment day per distinct day and one payment group
per day and key booked, one curve selected per key, one factor read and one payment valued per
unpaid group and seven reductions; the same functions and numpy calls whatever the size, three
rows on three days, two thousand rows on two thousand days and two thousand rows on twenty, the
booking per row inside numpy's uniques and the valuation per day inside its gathers, nothing per
row of the batch once booked; the peaks by rows and days; the two records' retained bytes; and
through the seam the two creators, each one publication, the two reports and the readback."""

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from test_seam_allocation import ENTRY, SLACK, least_peak, retained_numpy_bytes

from catalyst.cashflows.booking import Cashflows, cashflows
from catalyst.cashflows.valuation import cashflow_results
from catalyst.excel import bridge
from catalyst.excel.bridge import Cells
from catalyst.globals.discount_curve import DiscountCurve, discount_curve
from catalyst.globals.discount_curve_set import DiscountCurveSet, collect_discount_curves
from catalyst.globals.valuation_date import ValuationDate, valuation_date
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import CASHFLOW
from catalyst.instruments.fields import FieldValues
from catalyst.trades.risk_report import Bucket, Risk
from catalyst.trades.template import trade_template

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
AS_OF = np.datetime64("2027-01-04", "D")
SERIAL = 46391.0  # 4 January 2027 as the sheet counts days
TEMPLATE = trade_template(
    FieldValues(
        CASHFLOW,
        1,
        ("currency", "discount_curve_key"),
        {"currency": ("USD",), "discount_curve_key": ("SOFR",)},
    )
)
# A template naming no key, for a ticket that brings a key a row, cashflow-curve-keys.md.
UNKEYED = trade_template(FieldValues(CASHFLOW, 1, ("currency",), {"currency": ("USD",)}))
NAMES = ("SOFR", "FFOIS", "SONIA", "ESTR")
SIZES = [(3, 3), (2_000, 2_000), (2_000, 20)]
IDS = ["three rows on three days", "two thousand rows on as many days", "two thousand on twenty"]


def a_ticket(rows: int, days: int) -> FieldValues:
    """That many rows paying from the day after the valuation day over that many distinct days,
    the amounts a hundred and counting, as the seam would bind them."""
    pay = AS_OF + np.timedelta64(1, "D") + (np.arange(rows) % days).astype("timedelta64[D]")
    return FieldValues(
        CASHFLOW,
        rows,
        ("trade_date", "amount", "payment_day"),
        {
            "trade_date": np.full(rows, AS_OF, dtype="datetime64[D]"),
            "amount": 100.0 + np.arange(rows, dtype=np.float64),
            "payment_day": pay.astype("datetime64[D]"),
        },
    )


def a_curve(days: int, name: str = "SOFR") -> DiscountCurve:
    """A curve of that name from the valuation day past the last payment day, two anchors."""
    dates = np.array([AS_OF, AS_OF + np.timedelta64(days + 1, "D")], dtype="datetime64[D]")
    return discount_curve(name, dates, np.array([1.0, 0.9]))


def a_set(days: int, curves: int = 1) -> DiscountCurveSet:
    """A collection of that many curves, SOFR first, each past the last payment day."""
    return collect_discount_curves(
        tuple([a_curve(days, name) for name in NAMES[:curves]]), WorkCounter()
    )


def a_keyed_ticket(rows: int, days: int, curves: int) -> FieldValues:
    """That many rows with a key a row, the keys turning row by row among the first names and
    the payment day moving on once every key has had a row, so that a day holds several keys:
    a group a day and key."""
    turn = np.arange(rows)
    pay = AS_OF + np.timedelta64(1, "D") + ((turn // curves) % days).astype("timedelta64[D]")
    return FieldValues(
        CASHFLOW,
        rows,
        ("trade_date", "amount", "payment_day", "discount_curve_key"),
        {
            "trade_date": np.full(rows, AS_OF, dtype="datetime64[D]"),
            "amount": 100.0 + turn.astype(np.float64),
            "payment_day": pay.astype("datetime64[D]"),
            "discount_curve_key": tuple([NAMES[int(k)] for k in turn % curves]),
        },
    )


def keyed_groups(rows: int, days: int, curves: int) -> tuple[int, int]:
    """The distinct payment days and the distinct pairs of day and key a_keyed_ticket books, by
    the fixture's own arithmetic."""
    turn = np.arange(rows)
    day = (turn // curves) % days
    return int(np.unique(day).size), int(np.unique(day * curves + turn % curves).size)


def a_batch(rows: int, days: int) -> Cashflows:
    return cashflows(a_ticket(rows, days), TEMPLATE, WorkCounter())


DATE: ValuationDate = valuation_date(AS_OF, 0.5)

# The booking: the instrument and the two records' fields read, the required ones looked for,
# the currency, the amounts and since cashflow-curve-keys.md the keys judged, then three
# uniques, the days, the months and the years, and one bincount; the same whatever the rows or
# the days. A batch on one key, the template's, has a group a day and sorts nothing more.
BOOKING_CALLS = {
    "cashflows": 1,
    "_booked": 1,
    "_the_required": 1,
    "_the_currency": 1,
    "_the_keys": 1,  # the rows' keys and the distinct ones, cashflow-curve-keys.md
    "finite_amounts": 1,
    "_Booked.has": 8,  # 7 before: the key looked for among the required
    "_Booked.numbers": 1,
    "_Booked.dates": 2,
    "_Booked.texts": 2,  # 1 before: the currency, and the key
    "FieldValues.has": 6,
    "FieldValues.numbers": 1,
    "FieldValues.dates": 2,
    "WorkCounter.__init__": 1,
    "WorkCounter.hit": 3,  # 2 before: the groups counted
}
BOOKING_NUMPY = {
    "ndarray.any": 2,  # an amount not finite, a group's sum not finite
    "ndarray.argsort": 3,  # the three uniques
    "ndarray.cumsum": 3,
    "ndarray.flatten": 3,
    "ndarray.reshape": 3,
    "ndarray.astype": 9,  # 7 before: the groups' days and keys cast as the record declares them
    "numpy.arange": 1,  # none before: one key's groups are its days, their own places
    "numpy.zeros": 1,  # none before: and every group on the one key
    "numpy.asanyarray": 6,
    "numpy.empty": 6,
    "numpy._make_extobj": 1,  # numpy's flags down around the sums
    "ufunc.reduce": 2,
    "ndarray.setflags": 12,  # 10 before: frozen, the groups' days and keys among them
}
# A ticket bringing a key a row, on two keys or more: the column read and each distinct key
# judged by the curve's name rule and named with its first row, a fourth unique for the pairs
# of day and key, and the rows placed among the keys; the same whatever the rows.
KEYED_BOOKING_NUMPY = {
    "ndarray.any": 2,
    "ndarray.argsort": 4,  # the three uniques and the pairs'
    "ndarray.cumsum": 4,
    "ndarray.flatten": 4,
    "ndarray.reshape": 4,
    "ndarray.astype": 9,
    "numpy.array": 1,  # each row's key's place
    "numpy.asanyarray": 8,
    "numpy.empty": 8,
    "numpy._make_extobj": 1,
    "ufunc.reduce": 2,
    "ndarray.setflags": 12,
}


def keyed_booking_calls(curves: int) -> dict[str, int]:
    return {
        **BOOKING_CALLS,
        "FieldValues.has": 7,
        "FieldValues.texts": 1,  # the ticket's column of keys
        "_Booked.where": curves,  # each distinct key named with its first row
        "curve_name": curves,  # and judged once by the curve's name rule
    }


# The valuation: each key bound by the shared step, then per curve the start rule, its unpaid
# days judged covered and one gather of its factors; the time fractions, the two products,
# three sums, the DV01 by curve onto the days, the months and the years and each curve's total;
# the two display axes and each curve's early facts. The same whatever the groups, nothing per
# row of the batch, and by curve only what a curve's own rules and facts take.
def valuation_calls(curves: int) -> dict[str, int]:
    return {
        "cashflow_results": 1,
        "curve_named": curves,  # the shared step, shared-curve-binding.md; none before
        "curve_starts_on": curves,
        "DiscountCurve.start_date": 2 * curves,  # the rule's look and the factors' positions
        "DiscountCurve.max_date": curves,  # the coverage rule
        "factors_on": curves,
        "time_fractions": 1,
        "discounted": 1,
        "period_axis": 2,
        "period_start": 2,
        "places_from": 4,
        "rows_through": 4,
        "display_periods": 2,
        "early_risk": curves,
        "early_fact": 2 * curves,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 4,  # 3 before: the curves selected counted
    }


def valuation_numpy(curves: int) -> dict[str, int]:
    return {
        # A period not finite twice, the curves' own totals not finite once, since the review
        # of #260, and each curve's days covered.
        "ndarray.any": 3 + curves,
        "ndarray.astype": 11 + curves,
        "generic.astype": 2,  # the period starts
        "ndarray.searchsorted": 4,  # the display axes' places
        "ndarray.nonzero": 2 * curves,  # the early facts
        "ndarray.ravel": 4 + 2 * curves,  # 2 before on one curve: the by-curve places and weights
        "ndarray.reshape": 3,  # none before: the three views, a row a curve
        "ndarray.sum": 4,  # 3 before: the three totals and the curves' own
        "ufunc.reduce": 7 + curves,
        "numpy.arange": 3,  # 2 before: the display periods, and the curves' rows
        "numpy.asanyarray": 2 * curves,
        "numpy.count_nonzero": 1,  # the unpaid groups counted
        "numpy.empty": 1,
        "numpy.zeros": 1,
        "numpy._make_extobj": 1,
        "ndarray.setflags": 14,  # 13 before: frozen, the groups' DV01 among them
    }


VALUATION_CALLS = valuation_calls(1)
VALUATION_NUMPY = valuation_numpy(1)


@pytest.mark.parametrize(("rows", "days"), SIZES, ids=IDS)
def test_the_counters_report_rows_booked_days_mapped_and_unpaid_days_valued(
    rows: int, days: int
) -> None:
    counter = WorkCounter()
    batch = cashflows(a_ticket(rows, days), TEMPLATE, counter)
    assert counter.freeze().as_dict() == {
        "cashflows_booked": rows,
        "payment_days_mapped": days,
        "payment_groups_formed": days,  # one key: a group a day
    }
    counter = WorkCounter()
    cashflow_results(batch, DATE, a_set(days), counter)
    assert counter.freeze().as_dict() == {
        "curves_selected": 1,
        "payment_factors_read": days,
        "payments_valued": days,
        "risk_reductions": 7,
    }


@pytest.mark.parametrize(("rows", "days"), SIZES, ids=IDS)
def test_the_same_functions_and_numpy_calls_at_any_size(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, days: int
) -> None:
    ticket = a_ticket(rows, days)
    assert call_profile(lambda: cashflows(ticket, TEMPLATE, WorkCounter())) == BOOKING_CALLS
    assert numpy_calls(lambda: cashflows(ticket, TEMPLATE, WorkCounter())) == BOOKING_NUMPY
    batch = a_batch(rows, days)
    curve = a_set(days)
    assert call_profile(lambda: cashflow_results(batch, DATE, curve, WorkCounter())) == (
        VALUATION_CALLS
    )
    assert numpy_calls(lambda: cashflow_results(batch, DATE, curve, WorkCounter())) == (
        VALUATION_NUMPY
    )
    result = cashflow_results(batch, DATE, curve, WorkCounter())
    # A report selects and places one saved vector: no sum, no sort, no search.
    assert call_profile(lambda: result.report(Risk.DV01, Bucket.MONTH)) == {
        "CashflowResults.report": 1,
        "EarlyRisk.refuse": 1,
        "curve_words": 1,  # the curve's word, as every report names it
        "dv01_label": 1,
        "placed": 1,
    }
    assert numpy_calls(lambda: result.report(Risk.DV01, Bucket.MONTH)) == {"numpy.zeros": 1}


# A key a row, on two keys and on four: booking counts the groups of day and key, the valuation
# binds each distinct key once and reads one factor per unpaid group, and by curve it runs only
# a curve's own rules and facts, whatever the rows; a report places one saved vector a curve.
KEYED = [(rows, days, curves) for rows, days in SIZES[1:] for curves in (2, 4)]
KEYED_IDS = [f"{name}, {curves} keys" for name in IDS[1:] for curves in ("two", "four")]


@pytest.mark.parametrize(("rows", "days", "curves"), KEYED, ids=KEYED_IDS)
def test_a_key_a_row_books_by_group_and_values_by_group_and_by_curve(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, days: int, curves: int
) -> None:
    ticket = a_keyed_ticket(rows, days, curves)
    used, groups = keyed_groups(rows, days, curves)
    counter = WorkCounter()
    batch = cashflows(ticket, UNKEYED, counter)
    assert len(batch.keys) == curves and batch.group_amounts.size == groups
    assert counter.freeze().as_dict() == {
        "cashflows_booked": rows,
        "payment_days_mapped": used,
        "payment_groups_formed": groups,
    }
    assert call_profile(lambda: cashflows(ticket, UNKEYED, WorkCounter())) == (
        keyed_booking_calls(curves)
    )
    assert numpy_calls(lambda: cashflows(ticket, UNKEYED, WorkCounter())) == KEYED_BOOKING_NUMPY
    held = a_set(days, curves)
    counter = WorkCounter()
    result = cashflow_results(batch, DATE, held, counter)
    assert counter.freeze().as_dict() == {
        "curves_selected": curves,
        "payment_factors_read": groups,  # one a group, every group unpaid
        "payments_valued": groups,
        "risk_reductions": 7,  # whatever the curves
    }
    assert call_profile(lambda: cashflow_results(batch, DATE, held, WorkCounter())) == (
        valuation_calls(curves)
    )
    assert numpy_calls(lambda: cashflow_results(batch, DATE, held, WorkCounter())) == (
        valuation_numpy(curves)
    )
    assert len(result.rate_contributions) == curves
    assert call_profile(lambda: result.report(Risk.DV01, Bucket.MONTH)) == {
        "CashflowResults.report": 1,
        "EarlyRisk.refuse": curves,
        "curve_words": 1,
        "dv01_label": curves,
        "placed": curves,
    }
    assert numpy_calls(lambda: result.report(Risk.DV01, Bucket.MONTH)) == {"numpy.zeros": curves}
    # A curve nobody selects costs nothing: the same ledger over a collection twice the size.
    wider = a_set(days, len(NAMES))
    if curves < len(NAMES):
        assert call_profile(lambda: cashflow_results(batch, DATE, wider, WorkCounter())) == (
            valuation_calls(curves)
        )


# Booking pays the rows' columns and the uniques over them and the groups' sums and axes,
# measured 2026-11-20 at 7,214 bytes for three rows on three days, 199,518 for two thousand rows
# on two thousand days and 99,803 on twenty, where 6,958, 151,254 and 83,763 stood before
# cashflow-curve-keys.md: 8 bytes a row more, the rows' keys, and 16 a day, each group's day
# and key. Valuing pays per group, about 77 bytes a group on one curve: 5,440 for three days,
# 153,360 for two thousand and 6,596 for twenty under two thousand rows, where 3,659, 117,472
# and 4,509 stood: the groups' days gathered, each curve's own days and the three views a row a
# curve. The batch keeps its rows' dates and amounts and its groups' sums, days and keys; the
# result its groups' flags, factors, values, cash and DV01s, 33 bytes a group.
@pytest.mark.parametrize(("rows", "days"), SIZES, ids=IDS)
def test_the_peaks_follow_the_rows_and_the_days_and_the_records_keep_their_columns(
    rows: int, days: int
) -> None:
    ticket = a_ticket(rows, days)
    assert least_peak(lambda: cashflows(ticket, TEMPLATE, WorkCounter())) <= (
        56 * rows + 56 * days + 7 * SLACK
    )
    batch = a_batch(rows, days)
    curve = a_set(days)
    assert least_peak(lambda: cashflow_results(batch, DATE, curve, WorkCounter())) <= (
        80 * days + 24 * days + 6 * SLACK
    )
    kept = batch.trade_date.nbytes + batch.amount.nbytes + batch.payment_date.nbytes
    kept += batch.group_of_row.nbytes + batch.payment_days.nbytes + batch.group_amounts.nbytes
    kept += batch.group_day.nbytes + batch.group_key.nbytes
    assert kept == 32 * rows + 32 * days
    result = cashflow_results(batch, DATE, curve, WorkCounter())
    held = (
        result.is_paid.nbytes
        + result.payment_factor.nbytes
        + result.npv.nbytes
        + result.payment_cash.nbytes
        + result.group_dv01.nbytes
    )
    assert held == 33 * days


# On several keys the valuation's peak follows the groups and, for the three views, the curves
# times the days: 144,376 bytes for two thousand groups on two keys and 171,908 on four,
# 8,291 for forty groups and 11,708 for eighty, measured 2026-11-20.
@pytest.mark.parametrize(("rows", "days", "curves"), KEYED, ids=KEYED_IDS)
def test_a_keyed_valuations_peak_follows_its_groups_and_its_curves_days(
    rows: int, days: int, curves: int
) -> None:
    used, groups = keyed_groups(rows, days, curves)
    batch = cashflows(a_keyed_ticket(rows, days, curves), UNKEYED, WorkCounter())
    held = a_set(days, curves)
    assert least_peak(lambda: cashflow_results(batch, DATE, held, WorkCounter())) <= (
        80 * groups + 24 * curves * used + 6 * SLACK
    )


# --- through the seam -----------------------------------------------------------------------------

FIELDS = Cells.from_rows([["trade_date", "amount", "payment_day"]])
CURVE_HEADERS = Cells.from_rows([["date", "discount_factor"]])


def a_sheet(rows: int, days: int) -> dict[str, Any]:
    """The template, keyed on SOFR, the ticket's cells, the valuation date and a collection of
    one curve past the last day."""
    pay = (np.arange(rows) % days) + 1
    body = Cells.from_rows([[SERIAL, 100.0 + i, SERIAL + float(pay[i])] for i in range(rows)])
    return {
        "template": ENTRY["_CreateTradeTemplate"](
            "cashflow",
            Cells.from_rows([["currency", "discount_curve_key"]]),
            Cells.from_rows([["USD", "SOFR"]]),
        ),
        "body": body,
        "date": ENTRY["_CreateValuationDate"](SERIAL, 0.5),
        "curve": ENTRY["_CollectDiscountCurves"](
            ENTRY["_CreateDiscountCurve"](
                "SOFR", CURVE_HEADERS, Cells.from_rows([[SERIAL, 1.0], [SERIAL + days + 1, 0.9]])
            )
        ),
    }


# The creator: the header row and the rows bound against the template's instrument through the
# field path, the handle resolved, the library's booking and one publication; the evaluator:
# three handles resolved, the library's valuation and one publication. The same at every size.
@pytest.mark.parametrize(("rows", "days"), SIZES, ids=IDS)
def test_the_two_creators_bind_resolve_book_and_publish_once(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, days: int
) -> None:
    sheet = a_sheet(rows, days)
    template, body = sheet["template"], sheet["body"]
    assert call_profile(lambda: ENTRY["_CreateCashflows"](FIELDS, body, template)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text_row": 1,
        "_one_row": 1,
        "_shape": 1,
        "_texts": 1,
        "_field_rows": 1,
        "_text": 1,
        "_resolve": 1,
        "by_template": 1,
        "_bind_fields": 1,
        "_field_cells": 1,
        "_field_body": 1,
        "_field_dates": 2,
        "_not_dates": 2,
        "_as_days": 2,
        "_field_numbers": 1,
        "_CreateCashflows": 1,
        **BOOKING_CALLS,
        "_publish": 1,
    }
    assert numpy_calls(lambda: ENTRY["_CreateCashflows"](FIELDS, body, template)) == {
        **BOOKING_NUMPY,
        "ndarray.any": 5,  # the booking's two and one look per typed column
        "ndarray.astype": 13,  # the booking's nine and the two date columns on their way to days
        "ndarray.cumsum": 4,
        "ndarray.reshape": 4,
        "ndarray.ravel": 1,
        "numpy.array": 1,
        "ufunc.reduce": 5,
    }
    batch = ENTRY["_CreateCashflows"](FIELDS, body, template)
    date, curve = sheet["date"], sheet["curve"]
    assert call_profile(lambda: ENTRY["_EvaluateCashflows"](batch, date, curve)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text": 3,
        "_resolve": 3,
        "_EvaluateCashflows": 1,
        **VALUATION_CALLS,
        "_publish": 1,
    }
    assert numpy_calls(lambda: ENTRY["_EvaluateCashflows"](batch, date, curve)) == (VALUATION_NUMPY)


# The creators' peaks are the library's and the field path's, about 55 bytes a row and 34 a day
# to book and 58 a day to value, measured 2026-10-17 at 7,945 and 3,659 bytes for three rows on
# three days, 184,225 and 117,472 for two thousand on two thousand, and 116,734 and 4,509 for
# two thousand on twenty; each publishes one record, the batch its columns and the result its
# days', which release frees. The two reports and the readback make their tables and nothing
# more: the values report one row, the risk report the months from the valuation day's, the
# readback a row per booked row or per payment day with the totals once.
@pytest.mark.parametrize(("rows", "days"), SIZES, ids=IDS)
def test_the_creators_cost_their_rows_and_days_and_keep_their_columns_until_released(
    rows: int, days: int
) -> None:
    sheet = a_sheet(rows, days)
    template, body, date, curve = sheet["template"], sheet["body"], sheet["date"], sheet["curve"]
    assert least_peak(lambda: ENTRY["_CreateCashflows"](FIELDS, body, template)) <= (
        72 * rows + 56 * days + 8 * SLACK
    )
    kept, after = retained_numpy_bytes(lambda: ENTRY["_CreateCashflows"](FIELDS, body, template))
    assert 24 * rows + 16 * days <= kept <= 40 * rows + 64 * days + SLACK and after == 0
    batch = ENTRY["_CreateCashflows"](FIELDS, body, template)
    assert least_peak(lambda: ENTRY["_EvaluateCashflows"](batch, date, curve)) <= (
        80 * days + 24 * days + 6 * SLACK
    )
    kept, after = retained_numpy_bytes(lambda: ENTRY["_EvaluateCashflows"](batch, date, curve))
    assert 33 * days <= kept <= 33 * days + 48 * days + SLACK and after == 0
    results = ENTRY["_EvaluateCashflows"](batch, date, curve)
    live = bridge.live_handles()
    assert least_peak(lambda: ENTRY["_ReportValues"](results)) <= 2 * SLACK
    assert least_peak(lambda: ENTRY["_ReportRisk"](results, "dv01", "month")) <= (
        60 * (days // 28 + 2) + 3 * SLACK
    )
    # The key is a column more of each readback: a word a row, and a word a group.
    assert least_peak(lambda: ENTRY["util_ReadHandle"](batch)) <= 110 * rows + 3 * SLACK
    assert least_peak(lambda: ENTRY["util_ReadHandle"](results)) <= 420 * days + 4 * SLACK
    assert bridge.live_handles() == live  # the reports and the readback publish nothing
