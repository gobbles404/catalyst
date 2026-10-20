"""What booking and valuing cashflows cost, cashflow-instrument.md: the counters, one cashflow per
ticket row and one payment day per distinct day booked, one factor read and one payment valued
per unpaid day and five reductions; the same functions and numpy calls whatever the size, three
rows on three days, two thousand rows on two thousand days and two thousand rows on twenty, the
booking per row inside numpy's uniques and the valuation per day inside its gathers, nothing per
row of the batch once booked; the peaks by rows and days; the two records' retained bytes; and
through the seam the two creators, each one publication, the two reports and the readback."""

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from test_seam_allocation import ENTRY, SLACK, least_peak, retained_numpy_bytes

from goosedove.cashflows.booking import Cashflows, cashflows
from goosedove.cashflows.valuation import cashflow_results
from goosedove.excel import bridge
from goosedove.excel.bridge import Cells
from goosedove.globals.discount_curve import DiscountCurve, discount_curve
from goosedove.globals.valuation_date import ValuationDate, valuation_date
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import CASHFLOW
from goosedove.instruments.fields import FieldValues
from goosedove.trades.risk_report import Bucket, Risk
from goosedove.trades.template import trade_template

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
AS_OF = np.datetime64("2027-01-04", "D")
SERIAL = 46391.0  # 4 January 2027 as the sheet counts days
TEMPLATE = trade_template(FieldValues(CASHFLOW, 1, ("currency",), {"currency": ("USD",)}))
SIZES = [(3, 3), (2_000, 2_000), (2_000, 20)]
IDS = ["three rows on three days", "two thousand rows on as many days", "two thousand on twenty"]


def a_ticket(rows: int, days: int) -> FieldValues:
    """That many rows paying from the day after the valuation day over that many distinct days,
    the amounts a hundred and counting, as the seam would bind them."""
    pay = AS_OF + np.timedelta64(1, "D") + (np.arange(rows) % days).astype("timedelta64[D]")
    return FieldValues(
        CASHFLOW,
        rows,
        ("trade_date", "amount", "payment_date"),
        {
            "trade_date": np.full(rows, AS_OF, dtype="datetime64[D]"),
            "amount": 100.0 + np.arange(rows, dtype=np.float64),
            "payment_date": pay.astype("datetime64[D]"),
        },
    )


def a_curve(days: int) -> DiscountCurve:
    """A curve from the valuation day past the last payment day, two anchors."""
    dates = np.array([AS_OF, AS_OF + np.timedelta64(days + 1, "D")], dtype="datetime64[D]")
    return discount_curve("SOFR", dates, np.array([1.0, 0.9]))


def a_batch(rows: int, days: int) -> Cashflows:
    return cashflows(a_ticket(rows, days), TEMPLATE, WorkCounter())


DATE: ValuationDate = valuation_date(AS_OF, 0.5)

# The booking: the instrument and the two records' fields read, the required ones looked for,
# the currency and the amounts judged, then three uniques, the days, the months and the years,
# and one bincount; the same whatever the rows or the days.
BOOKING_CALLS = {
    "cashflows": 1,
    "_booked": 1,
    "_the_required": 1,
    "_the_currency": 1,
    "finite_amounts": 1,
    "_Booked.has": 7,
    "_Booked.numbers": 1,
    "_Booked.dates": 2,
    "_Booked.texts": 1,
    "FieldValues.has": 6,
    "FieldValues.numbers": 1,
    "FieldValues.dates": 2,
    "WorkCounter.__init__": 1,
    "WorkCounter.hit": 2,
}
BOOKING_NUMPY = {
    "ndarray.any": 2,  # an amount not finite, a day's sum not finite
    "ndarray.argsort": 3,  # the three uniques
    "ndarray.cumsum": 3,
    "ndarray.flatten": 3,
    "ndarray.reshape": 3,
    "ndarray.astype": 7,
    "numpy.asanyarray": 6,
    "numpy.empty": 6,
    "numpy._make_extobj": 1,  # numpy's flags down around the sums
    "ufunc.reduce": 2,
    "ndarray.setflags": 10,  # frozen
}
# The valuation: the start rule, the days judged unpaid and covered, one gather of factors, the
# time fractions, the two products, three sums and two bincounts, the two display axes and the
# early facts; the same whatever the days, nothing per row of the batch.
VALUATION_CALLS = {
    "cashflow_results": 1,
    "curve_starts_on": 1,
    "DiscountCurve.start_date": 2,  # the rule's look and the factors' positions
    "DiscountCurve.max_date": 1,  # the coverage rule
    "factors_on": 1,
    "time_fractions": 1,
    "discounted": 1,
    "period_axis": 2,
    "period_start": 2,
    "places_from": 4,
    "rows_through": 4,
    "display_periods": 2,
    "early_risk": 1,
    "early_fact": 2,
    "WorkCounter.__init__": 1,
    "WorkCounter.hit": 3,
}
VALUATION_NUMPY = {
    "ndarray.any": 3,  # a day uncovered, a total not finite twice
    "ndarray.astype": 12,
    "generic.astype": 2,  # the period starts
    "ndarray.searchsorted": 4,  # the display axes' places
    "ndarray.nonzero": 2,  # the early facts
    "ndarray.ravel": 2,
    "ndarray.sum": 3,  # the three totals
    "ufunc.reduce": 6,
    "numpy.arange": 2,  # the display periods
    "numpy.asanyarray": 2,
    "numpy.count_nonzero": 1,  # the unpaid days counted
    "numpy.empty": 1,
    "numpy.zeros": 1,
    "numpy._make_extobj": 1,
    "ndarray.setflags": 13,  # frozen
}


@pytest.mark.parametrize(("rows", "days"), SIZES, ids=IDS)
def test_the_counters_report_rows_booked_days_mapped_and_unpaid_days_valued(
    rows: int, days: int
) -> None:
    counter = WorkCounter()
    batch = cashflows(a_ticket(rows, days), TEMPLATE, counter)
    assert counter.freeze().as_dict() == {"cashflows_booked": rows, "payment_days_mapped": days}
    counter = WorkCounter()
    cashflow_results(batch, DATE, a_curve(days), counter)
    assert counter.freeze().as_dict() == {
        "payment_factors_read": days,
        "payments_valued": days,
        "risk_reductions": 5,
    }


@pytest.mark.parametrize(("rows", "days"), SIZES, ids=IDS)
def test_the_same_functions_and_numpy_calls_at_any_size(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, days: int
) -> None:
    ticket = a_ticket(rows, days)
    assert call_profile(lambda: cashflows(ticket, TEMPLATE, WorkCounter())) == BOOKING_CALLS
    assert numpy_calls(lambda: cashflows(ticket, TEMPLATE, WorkCounter())) == BOOKING_NUMPY
    batch = a_batch(rows, days)
    curve = a_curve(days)
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


# Booking pays the rows' columns and the uniques over them, about 42 bytes a row, and the days'
# sums and axes, about 34 a day, beyond some six slacks of small objects: measured 2026-10-17 at
# 6,958 bytes for three rows on three days, 151,254 for two thousand rows on two thousand days
# and 83,763 on twenty. Valuing pays per distinct day alone, about 58 bytes a
# day: 3,659 for three days, 117,472 for two thousand and 4,509 for twenty under two thousand
# rows. The batch keeps its rows' dates and amounts and its days' sums and axes; the result its
# days' flags, factors, values, cash and DV01s, 33 bytes a day.
@pytest.mark.parametrize(("rows", "days"), SIZES, ids=IDS)
def test_the_peaks_follow_the_rows_and_the_days_and_the_records_keep_their_columns(
    rows: int, days: int
) -> None:
    ticket = a_ticket(rows, days)
    assert least_peak(lambda: cashflows(ticket, TEMPLATE, WorkCounter())) <= (
        48 * rows + 40 * days + 7 * SLACK
    )
    batch = a_batch(rows, days)
    curve = a_curve(days)
    assert least_peak(lambda: cashflow_results(batch, DATE, curve, WorkCounter())) <= (
        64 * days + 4 * SLACK
    )
    kept = batch.trade_date.nbytes + batch.amount.nbytes + batch.payment_date.nbytes
    kept += batch.day_of_row.nbytes + batch.payment_days.nbytes + batch.payment_amounts.nbytes
    assert kept == 32 * rows + 16 * days
    result = cashflow_results(batch, DATE, curve, WorkCounter())
    held = (
        result.is_paid.nbytes
        + result.payment_factor.nbytes
        + result.npv.nbytes
        + result.payment_cash.nbytes
        + result.rate_contributions[0].dv01_by_day.nbytes
    )
    assert held == 33 * days


# --- through the seam -----------------------------------------------------------------------------

FIELDS = Cells.from_rows([["trade_date", "amount", "payment_date"]])
CURVE_HEADERS = Cells.from_rows([["date", "discount_factor"]])


def a_sheet(rows: int, days: int) -> dict[str, Any]:
    """The template, the ticket's cells, the valuation date and a curve past the last day."""
    pay = (np.arange(rows) % days) + 1
    body = Cells.from_rows([[SERIAL, 100.0 + i, SERIAL + float(pay[i])] for i in range(rows)])
    return {
        "template": ENTRY["_CreateTradeTemplate"](
            "cashflow", Cells.from_rows([["currency"]]), Cells.from_rows([["USD"]])
        ),
        "body": body,
        "date": ENTRY["_CreateValuationDate"](SERIAL, 0.5),
        "curve": ENTRY["_CreateDiscountCurve"](
            "SOFR", CURVE_HEADERS, Cells.from_rows([[SERIAL, 1.0], [SERIAL + days + 1, 0.9]])
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
        "ndarray.astype": 11,  # the booking's seven and the two date columns on their way to days
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
        64 * rows + 40 * days + 8 * SLACK
    )
    kept, after = retained_numpy_bytes(lambda: ENTRY["_CreateCashflows"](FIELDS, body, template))
    assert 24 * rows + 16 * days <= kept <= 40 * rows + 48 * days + SLACK and after == 0
    batch = ENTRY["_CreateCashflows"](FIELDS, body, template)
    assert least_peak(lambda: ENTRY["_EvaluateCashflows"](batch, date, curve)) <= (
        64 * days + 4 * SLACK
    )
    kept, after = retained_numpy_bytes(lambda: ENTRY["_EvaluateCashflows"](batch, date, curve))
    assert 33 * days <= kept <= 33 * days + 48 * days + SLACK and after == 0
    results = ENTRY["_EvaluateCashflows"](batch, date, curve)
    live = bridge.live_handles()
    assert least_peak(lambda: ENTRY["_ReportValues"](results)) <= 2 * SLACK
    assert least_peak(lambda: ENTRY["_ReportRisk"](results, "dv01", "month")) <= (
        60 * (days // 28 + 2) + 3 * SLACK
    )
    assert least_peak(lambda: ENTRY["util_ReadHandle"](batch)) <= 80 * rows + 3 * SLACK
    assert least_peak(lambda: ENTRY["util_ReadHandle"](results)) <= 400 * days + 3 * SLACK
    assert bridge.live_handles() == live  # the reports and the readback publish nothing
