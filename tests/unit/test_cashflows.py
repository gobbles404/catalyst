"""The cashflow instrument, cashflow-instrument.md: known signed amounts in one currency, each on
its own payment day, booked from a template and a ticket and valued on a valuation day over a
collection of named discount curves, each unpaid payment discounted on the curve its key names,
since cashflow-curve-keys.md, with its DV01 and each paid one cash. The figures are
the ticket's, priced by hand here: valued on 4 January 2027 on the curve 1, 0.95 a year out and
0.90 two years out, 10,000 receivable a year out is 9,500 and -0.95 of DV01, 10,000 payable two
years out -9,000 and +1.80, and a rebate of 250 paid the day before is cash; 500 of mark, 250 of
cash and 0.85 of DV01 in all. The production code is never asked for an expected answer; the
centered check bumps the curve each way through the ordinary bump. The seam makes the two handles,
the reports and the readback take them, and every refusal is in its own words.
docs/library/cashflows/create-cashflows.md and evaluate-cashflows.md are the pages."""

import math
import re
from typing import Any

import numpy as np
import pytest
from test_bilateral_kernel import A_YEAR, AS_OF, CLOSE, TIGHT, TWO_YEARS, curve_of
from test_trade_valuation import ENTRY, row, serial, spilled
from test_trades import dates

from catalyst.cashflows.booking import Cashflows, cashflows
from catalyst.cashflows.valuation import CashflowResults, cashflow_results
from catalyst.excel import bridge
from catalyst.excel.bridge import MISSING, Cells
from catalyst.globals.discount_curve import DiscountCurve, bump_discount_curve
from catalyst.globals.discount_curve_set import DiscountCurveSet, collect_discount_curves
from catalyst.globals.unit_conversions import (
    UNITS,
    UnitDefinition,
    category,
    unit_conversions,
)
from catalyst.globals.valuation_date import valuation_date
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import CASHFLOW, FIXED_FLOAT, FieldType
from catalyst.instruments.fields import FieldValues
from catalyst.trades.risk_report import Bucket, Risk
from catalyst.trades.template import TradeTemplate, trade_template

DAY_BEFORE = "2027-01-03"
CURVE = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90))
DV01_LABEL = "SOFR USD dv01 [DOLLAR per basis point]"


# --- the two records from Python, as the seam would build them ------------------------------------


def column(name: str, values: list[Any]) -> object:
    """A column of a cashflow field as the seam types it: numbers as floats, dates as days,
    text and codes as a tuple."""
    field_type = CASHFLOW_TYPES[name]
    if field_type is FieldType.NUMBER:
        return np.array([float(v) for v in values])
    if field_type is FieldType.DATE:
        return np.array([str(v) for v in values], dtype="datetime64[D]")
    return tuple(str(v) for v in values)


CASHFLOW_TYPES = {field.name: field.type for field in CASHFLOW.fields}


def template(**fields: Any) -> TradeTemplate:
    """A cashflow template holding those fields, one row, and since cashflow-curve-keys.md the
    key SOFR, the name of the tests' curve, unless the fields name another or, with None, leave
    the key to the ticket."""
    fields.setdefault("discount_curve_key", "SOFR")
    if fields["discount_curve_key"] is None:
        del fields["discount_curve_key"]
    return trade_template(
        FieldValues(
            CASHFLOW, 1, tuple(fields), {name: column(name, [v]) for name, v in fields.items()}
        )
    )


def ticket(**columns: list[Any]) -> FieldValues:
    """A cashflow ticket of those columns, one row per entry."""
    rows = len(next(iter(columns.values())))
    return FieldValues(
        CASHFLOW, rows, tuple(columns), {name: column(name, v) for name, v in columns.items()}
    )


TEMPLATE = template(currency="USD", counterparty="Firm A")
TICKET = ticket(
    trade_id=[1, 2, 3],
    trade_date=[AS_OF, AS_OF, AS_OF],
    amount=[10_000.0, -10_000.0, 250.0],
    payment_day=[A_YEAR, TWO_YEARS, DAY_BEFORE],
    description=["Receivable", "Payable", "Earlier rebate"],
)


def booked(
    rows: FieldValues = TICKET,
    shared: TradeTemplate = TEMPLATE,
    counter: WorkCounter | None = None,
) -> Cashflows:
    return cashflows(rows, shared, UNITS, counter or WorkCounter())


def booked_on(curve: DiscountCurve) -> Cashflows:
    """The ticket's batch keyed on that curve's name, to be valued on it."""
    shared = template(currency="USD", counterparty="Firm A", discount_curve_key=curve.name)
    return booked(shared=shared)


def collected(*curves: DiscountCurve) -> DiscountCurveSet:
    return collect_discount_curves(curves, WorkCounter())


def valued(
    batch: Cashflows,
    as_of: str = AS_OF,
    curve: DiscountCurve | DiscountCurveSet = CURVE,
    counter: WorkCounter | None = None,
) -> CashflowResults:
    """The batch valued on that day over a collection: the one given, or a collection of the
    one curve given, as a sheet on one curve passes."""
    curves = curve if isinstance(curve, DiscountCurveSet) else collected(curve)
    return cashflow_results(
        batch, valuation_date(np.datetime64(as_of), 0.5), curves, counter or WorkCounter()
    )


def refused_booking(rows: FieldValues, shared: TradeTemplate = TEMPLATE) -> str:
    with pytest.raises(ValueError) as caught:
        booked(rows, shared)
    return str(caught.value)


def refused_valuation(
    batch: Cashflows, as_of: str = AS_OF, curve: DiscountCurve | DiscountCurveSet = CURVE
) -> str:
    with pytest.raises(ValueError) as caught:
        valued(batch, as_of, curve)
    return str(caught.value)


# --- the worked example ---------------------------------------------------------------------------


def test_the_worked_example_books_three_payments_and_values_them_by_hand() -> None:
    counter = WorkCounter()
    batch = booked(counter=counter)
    assert batch.rows == 3 and batch.currency == "USD"
    assert batch.trade_id is not None and batch.trade_id.tolist() == [1, 2, 3]
    assert batch.trade_id.dtype == np.int64
    np.testing.assert_array_equal(batch.trade_date, dates(AS_OF, AS_OF, AS_OF))
    assert batch.amount.tolist() == [10_000.0, -10_000.0, 250.0]
    np.testing.assert_array_equal(batch.payment_date, dates(A_YEAR, TWO_YEARS, DAY_BEFORE))
    assert batch.counterparty == ("Firm A", "Firm A", "Firm A")  # the template's on every row
    assert batch.description == ("Receivable", "Payable", "Earlier rebate")
    # The distinct days, increasing; one key, so a group a day: the rows' amounts on each and
    # each row's place among them, every group on the one key.
    np.testing.assert_array_equal(batch.payment_days, dates(DAY_BEFORE, A_YEAR, TWO_YEARS))
    assert batch.discount_curve_key == ("SOFR",) * 3 and batch.keys == ("SOFR",)
    assert batch.group_amounts.tolist() == [250.0, 10_000.0, -10_000.0]
    assert batch.group_of_row.tolist() == [1, 2, 0]
    assert batch.group_day.tolist() == [0, 1, 2] and batch.group_key.tolist() == [0, 0, 0]
    np.testing.assert_array_equal(batch.months, dates("2027-01-01", "2028-01-01", "2029-01-01"))
    assert batch.month_of_day.tolist() == [0, 1, 2]
    np.testing.assert_array_equal(batch.years, dates("2027-01-01", "2028-01-01", "2029-01-01"))
    assert batch.year_of_month.tolist() == [0, 1, 2]
    assert counter.freeze().as_dict() == {
        "cashflows_booked": 3,
        "payment_days_mapped": 3,
        "payment_groups_formed": 3,
    }
    counter = WorkCounter()
    result = valued(batch, counter=counter)
    assert result.cashflows is batch and len(result.curves) == 1 and result.curves[0] is CURVE
    assert str(result.as_of) == AS_OF and result.currency == "USD"
    assert result.mark == pytest.approx(500.0, **CLOSE)
    assert result.cash == 250.0
    assert result.dv01 == pytest.approx(0.85, **CLOSE)
    assert result.is_paid.tolist() == [True, False, False]
    np.testing.assert_allclose(result.payment_factor, [1.0, 0.95, 0.90], **TIGHT)
    np.testing.assert_allclose(result.npv, [0.0, 9_500.0, -9_000.0], **TIGHT)
    assert result.payment_cash.tolist() == [250.0, 0.0, 0.0]
    (contribution,) = result.rate_contributions  # the one curve's share, the whole of it
    assert contribution.curve is CURVE and contribution.currency == "USD"
    assert contribution.dv01 == result.dv01
    assert contribution.days is result.cashflows.payment_days
    np.testing.assert_allclose(contribution.dv01_by_day, [0.0, -0.95, 1.80], **TIGHT)
    np.testing.assert_allclose(contribution.dv01_by_month, [0.0, -0.95, 1.80], **TIGHT)
    np.testing.assert_allclose(contribution.dv01_by_year, [0.0, -0.95, 1.80], **TIGHT)
    assert counter.freeze().as_dict() == {
        "curves_selected": 1,
        "payment_factors_read": 2,
        "payments_valued": 2,
        "risk_reductions": 7,
    }
    for array in (
        result.is_paid,
        result.payment_factor,
        result.npv,
        result.payment_cash,
        result.group_dv01,
        result.rate_contributions[0].dv01_by_day,
        result.rate_contributions[0].dv01_by_month,
        result.rate_contributions[0].dv01_by_year,
        batch.trade_date,
        batch.amount,
        batch.payment_date,
        batch.payment_days,
        batch.group_amounts,
        batch.group_of_row,
        batch.group_day,
        batch.group_key,
        batch.months,
        batch.month_of_day,
        batch.years,
        batch.year_of_month,
    ):  # every array the batch and the result keep, the mappings included
        assert not array.flags.writeable
    assert batch.trade_id is not None and not batch.trade_id.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        batch.month_of_day[0] = 1  # a mapping kept frozen: no later cast hands back a copy


def test_a_receipt_of_a_hundred_moves_with_the_curve_and_the_day_and_the_batch_never() -> None:
    # 100 a year out: 95 of mark, nothing of cash, -0.0095 of DV01; on a curve at 0.96 the batch
    # stands and the result is 96 and -0.0096; on the payment day, over a curve of that one day,
    # the amount is cash and nothing is discounted; the day after, still cash.
    batch = booked(ticket(trade_date=[AS_OF], amount=[100.0], payment_day=[A_YEAR]))
    result = valued(batch)
    assert (result.mark, result.cash) == (pytest.approx(95.0, **CLOSE), 0.0)
    assert result.dv01 == pytest.approx(-0.0095, **CLOSE)
    moved = valued(batch, curve=curve_of((AS_OF, 1.0), (A_YEAR, 0.96)))
    assert moved.cashflows is batch
    assert moved.mark == pytest.approx(96.0, **CLOSE)
    assert moved.dv01 == pytest.approx(-0.0096, **CLOSE)
    paid = valued(batch, A_YEAR, curve_of((A_YEAR, 1.0)))
    assert (paid.mark, paid.cash, paid.dv01) == (0.0, 100.0, 0.0)
    assert paid.is_paid.tolist() == [True] and paid.payment_factor.tolist() == [1.0]
    after = valued(batch, "2028-01-05", curve_of(("2028-01-05", 1.0)))
    assert (after.mark, after.cash, after.dv01) == (0.0, 100.0, 0.0)
    assert batch.amount.tolist() == [100.0]  # the batch read, never written


def test_amounts_on_one_day_are_one_amount_and_on_different_days_stay_apart() -> None:
    # Equal and opposite on one day cancel to a day of nothing; on different days the nominal
    # amounts net to nothing while the value and the DV01 do not, the days surviving.
    same = booked(
        ticket(trade_date=[AS_OF, AS_OF], amount=[100.0, -100.0], payment_day=[A_YEAR, A_YEAR])
    )
    assert same.group_amounts.tolist() == [0.0] and same.rows == 2
    result = valued(same)
    assert (result.mark, result.cash, result.dv01) == (0.0, 0.0, 0.0)
    apart = booked(
        ticket(trade_date=[AS_OF, AS_OF], amount=[100.0, -100.0], payment_day=[A_YEAR, TWO_YEARS])
    )
    assert apart.group_amounts.tolist() == [100.0, -100.0]
    result = valued(apart)
    assert result.mark == pytest.approx(95.0 - 90.0, **CLOSE)
    assert result.dv01 == pytest.approx(-0.0095 + 0.018, **CLOSE)


def test_fractions_zero_rows_repeats_and_any_order_book_as_they_are() -> None:
    # A fractional amount, a zero row kept, a repeated row a second payment, and the rows in
    # any order: the days sorted once and the readback in the ticket's order.
    batch = booked(
        ticket(
            trade_date=[AS_OF] * 4,
            amount=[0.5, 0.0, 100.0, 100.0],
            payment_day=[TWO_YEARS, A_YEAR, A_YEAR, A_YEAR],
        )
    )
    assert batch.amount.tolist() == [0.5, 0.0, 100.0, 100.0]
    np.testing.assert_array_equal(batch.payment_days, dates(A_YEAR, TWO_YEARS))
    assert batch.group_amounts.tolist() == [200.0, 0.5]
    assert batch.group_of_row.tolist() == [1, 0, 0, 0]
    result = valued(batch)
    assert result.mark == pytest.approx(190.0 + 0.45, **CLOSE)
    assert result.dv01 == pytest.approx(-0.019 - 0.00009, **CLOSE)


def test_a_batch_is_the_sum_of_its_singletons() -> None:
    whole = valued(booked())
    parts = [
        valued(booked(ticket(trade_date=[AS_OF], amount=[a], payment_day=[d])))
        for a, d in ((10_000.0, A_YEAR), (-10_000.0, TWO_YEARS), (250.0, DAY_BEFORE))
    ]
    assert whole.mark == pytest.approx(sum(p.mark for p in parts), **CLOSE)
    assert whole.cash == pytest.approx(sum(p.cash for p in parts), **CLOSE)
    assert whole.dv01 == pytest.approx(sum(p.dv01 for p in parts), **CLOSE)


def test_the_template_may_supply_the_payment_itself_and_the_ticket_the_rest() -> None:
    # A template holding the amount, the day and the currency: every row pays the same, the
    # ticket's trade dates and identifiers its own; a template of one row of everything serves
    # a ticket of trade dates alone.
    shared = template(currency="USD", amount=100.0, payment_day=A_YEAR, trade_id=7)
    batch = booked(ticket(trade_date=[AS_OF, DAY_BEFORE]), shared)
    assert batch.amount.tolist() == [100.0, 100.0]
    assert batch.trade_id is not None and batch.trade_id.tolist() == [7, 7]
    assert batch.group_amounts.tolist() == [200.0] and batch.counterparty is None
    assert batch.description is None
    assert valued(batch).mark == pytest.approx(190.0, **CLOSE)


def test_the_centered_difference_of_bumped_marks_is_the_saved_dv01() -> None:
    # The curve a tenth of a basis point each way through the ordinary bump: half the difference
    # of the marks over the bump is the analytic DV01 to its truncation, the shift squared over 6
    # times the third derivative of 9,500 exp(-b) - 9,000 exp(-2b) at nought, 62,500, times
    # 0.0001 per basis point: some 1e-10 at a tenth of a point and 1e-8 at a point; roundoff on
    # marks near 500 over 0.2 is some 1e-12 beside it.
    batch = booked()
    analytic = valued(batch)
    for h, tolerance in ((0.1, 1e-9), (1.0, 1e-7)):
        up = valued(batch, curve=bump_discount_curve(CURVE, h, WorkCounter()))
        down = valued(batch, curve=bump_discount_curve(CURVE, -h, WorkCounter()))
        assert (up.mark - down.mark) / (2 * h) == pytest.approx(analytic.dv01, rel=0, abs=tolerance)
        assert up.cash == down.cash == analytic.cash  # the paid rebate moves for no rate


# --- the rules of booking -------------------------------------------------------------------------


def test_a_template_of_another_instrument_is_refused_by_name() -> None:
    fixed = trade_template(FieldValues(FIXED_FLOAT, 1, ("route",), {"route": ("cleared",)}))
    assert refused_booking(TICKET, fixed) == (
        "template is of instrument 'fixed_float', expected cashflow, the one instrument whose "
        "cashflows are built"
    )


def test_the_fields_come_from_one_of_the_two_and_the_required_ones_from_either() -> None:
    assert refused_booking(
        ticket(trade_date=[AS_OF], amount=[1.0], payment_day=[A_YEAR], currency=["USD"])
    ) == ("currency is supplied by the template and by the ticket, expected by one of them")
    assert refused_booking(ticket(trade_date=[AS_OF], payment_day=[A_YEAR])) == (
        "amount is missing, expected a value in the template or a column in the ticket"
    )
    assert refused_booking(ticket(amount=[1.0], payment_day=[A_YEAR])) == (
        "trade_date is missing, expected a value in the template or a column in the ticket"
    )
    assert refused_booking(
        ticket(trade_date=[AS_OF], amount=[1.0], payment_day=[A_YEAR]), template(counterparty="x")
    ) == ("currency is missing, expected a value in the template or a column in the ticket")
    assert refused_booking(ticket(trade_date=[AS_OF], amount=[1.0])) == (
        "payment_day is missing, expected a value in the template or a column in the ticket"
    )


def test_the_currency_is_usd_exactly_one_per_batch_and_cent_is_no_currency() -> None:
    bare = template(counterparty="Firm A")
    assert refused_booking(
        ticket(trade_date=[AS_OF], amount=[1.0], payment_day=[A_YEAR], currency=["usd"]), bare
    ) == ("currency row 1 is 'usd', expected USD, the one currency this version books")
    assert refused_booking(
        ticket(
            trade_date=[AS_OF] * 3,
            amount=[1.0] * 3,
            payment_day=[A_YEAR] * 3,
            currency=["USD", "CAD", "CAD"],
        ),
        bare,
    ) == ("currency row 2 is 'CAD', expected USD, the one currency this version books")
    assert refused_booking(
        ticket(trade_date=[AS_OF], amount=[1.0], payment_day=[A_YEAR], currency=["CENT"]), bare
    ) == ("currency row 1 is 'CENT', expected USD, the one currency this version books")
    # Nor is DOLLAR, the unit of it since currency-and-currency-unit.md: a currency is USD.
    assert refused_booking(
        ticket(trade_date=[AS_OF], amount=[1.0], payment_day=[A_YEAR], currency=["DOLLAR"]), bare
    ) == ("currency row 1 is 'DOLLAR', expected USD, the one currency this version books")
    with pytest.raises(ValueError) as caught:
        template(currency="CENT")
    assert (
        str(caught.value) == "currency is 'CENT', expected USD, the one currency this version books"
    )
    both = booked(
        ticket(trade_date=[AS_OF, AS_OF], amount=[1.0, 2.0], payment_day=[A_YEAR, A_YEAR],
               currency=["USD", "USD"]),
        bare,
    )  # fmt: skip
    assert both.currency == "USD"


def test_amounts_are_finite_and_identifiers_whole_each_named_by_its_row() -> None:
    assert refused_booking(
        ticket(trade_date=[AS_OF] * 2, amount=[1.0, math.inf], payment_day=[A_YEAR] * 2)
    ) == ("amount row 2 is inf, expected a finite amount")
    assert refused_booking(ticket(trade_date=[AS_OF], amount=[math.nan], payment_day=[A_YEAR])) == (
        "amount row 1 is nan, expected a finite amount"
    )
    with pytest.raises(ValueError) as caught:
        template(amount=-math.inf)
    assert str(caught.value) == "amount is -inf, expected a finite amount"
    assert re.fullmatch(
        r"trade_id row 2 is 1\.5, expected .*",
        refused_booking(
            ticket(
                trade_id=[1, 1.5],
                trade_date=[AS_OF] * 2,
                amount=[1.0] * 2,
                payment_day=[A_YEAR] * 2,
            )
        ),
    )
    # Amounts finite each but past the largest number together on one day: refused by the day.
    largest = float(np.finfo(np.float64).max)
    assert refused_booking(
        ticket(trade_date=[AS_OF] * 2, amount=[largest, largest], payment_day=[A_YEAR] * 2)
    ) == (
        f"the payments on {A_YEAR} on SOFR sum to inf, expected a finite amount of DOLLAR; the "
        "rows' amounts, each finite, sum past the largest number"
    )


# --- the rules of valuation -----------------------------------------------------------------------


def test_the_curve_starts_on_the_day_and_covers_every_unpaid_day_a_paid_one_needing_none() -> None:
    batch = booked()
    assert refused_valuation(batch, curve=curve_of(("2027-01-05", 1.0), (TWO_YEARS, 0.9))) == (
        "discount curve 'SOFR' starts on 2027-01-05, expected 2027-01-04, the valuation date; "
        "a curve is never rebased"
    )
    assert refused_valuation(batch, curve=curve_of((AS_OF, 1.0), (A_YEAR, 0.95))) == (
        f"the payment on {TWO_YEARS} on SOFR is past the discount curve 'SOFR', which runs from "
        f"{AS_OF} to {A_YEAR}; expected every unpaid payment day covered"
    )
    # Paid in full on the day after the last payment: a curve of that one day serves.
    settled = valued(batch, "2029-01-04", curve_of(("2029-01-04", 1.0)))
    assert (settled.mark, settled.cash, settled.dv01) == (0.0, 250.0, 0.0)


def test_a_total_past_the_largest_number_is_refused_by_the_batch() -> None:
    largest = float(np.finfo(np.float64).max)
    batch = booked(
        ticket(trade_date=[AS_OF] * 2, amount=[largest, largest], payment_day=[A_YEAR, TWO_YEARS])
    )
    assert refused_valuation(batch) == (
        "the batch has inf of mark in all, expected a finite amount of DOLLAR; the payments, each "
        "finite, sum past the largest number"
    )
    paid = booked(
        ticket(trade_date=[AS_OF] * 2, amount=[largest, largest], payment_day=[DAY_BEFORE, AS_OF])
    )
    assert refused_valuation(paid) == (
        "the batch has inf of cash in all, expected a finite amount of DOLLAR; the payments, each "
        "finite, sum past the largest number"
    )


# --- the risk report ------------------------------------------------------------------------------


def test_the_report_selects_the_dv01_by_day_month_and_year_and_all_is_the_dv01_alone() -> None:
    result = valued(booked())
    by_day = result.report(Risk.DV01, Bucket.DAY)
    np.testing.assert_array_equal(by_day.dates, dates(DAY_BEFORE, A_YEAR, TWO_YEARS))
    assert by_day.labels == (DV01_LABEL,)
    assert by_day.totals == (result.dv01,)
    np.testing.assert_allclose(by_day.columns[0], [0.0, -0.95, 1.80], **TIGHT)
    by_month = result.report(Risk.DV01, Bucket.MONTH)
    assert by_month.dates.size == 25  # January 2027 through January 2029
    assert str(by_month.dates[0]) == "2027-01-01" and str(by_month.dates[-1]) == "2029-01-01"
    column = by_month.columns[0]
    assert column[12] == pytest.approx(-0.95, **CLOSE) and column[24] == pytest.approx(1.8, **CLOSE)
    assert np.count_nonzero(column) == 2
    by_year = result.report(Risk.ALL, Bucket.YEAR)
    np.testing.assert_array_equal(by_year.dates, dates("2027-01-01", "2028-01-01", "2029-01-01"))
    assert by_year.labels == (DV01_LABEL,)
    np.testing.assert_allclose(by_year.columns[0], [0.0, -0.95, 1.80], **TIGHT)
    for risk in (Risk.NOMINAL_DELTA, Risk.DELTA, Risk.CROSS_GAMMA):
        with pytest.raises(ValueError) as caught:
            result.report(risk, Bucket.DAY)
        assert str(caught.value) == (
            f"risk is {risk.value!r}, expected dv01 or all for a batch of cashflows, which has "
            "no commodity risk"
        )


# --- through the seam -----------------------------------------------------------------------------

HANDLE = re.compile(r"^\d+:(cashflows|cashflow_results):USD:\d+$")
CURVE_HEADERS = row("date", "discount_factor")
CURVE_BODY = Cells.from_rows(
    [[serial(AS_OF), 1.0], [serial(A_YEAR), 0.95], [serial(TWO_YEARS), 0.90]]
)
FIELDS = row("trade_id", "trade_date", "amount", "payment_day", "description")
ROWS = Cells.from_rows(
    [
        [1.0, serial(AS_OF), 10_000.0, serial(A_YEAR), "Receivable"],
        [2.0, serial(AS_OF), -10_000.0, serial(TWO_YEARS), "Payable"],
        [3.0, serial(AS_OF), 250.0, serial(DAY_BEFORE), "Earlier rebate"],
    ]
)


def a_sheet() -> dict[str, Any]:
    """The ticket's example through the seam: the template, keyed on SOFR since
    cashflow-curve-keys.md, the batch, the valuation date, the curve, the collection of that
    one curve and the results, each a handle."""
    template = ENTRY["_CreateTradeTemplate"](
        "cashflow",
        row("currency", "counterparty", "discount_curve_key"),
        row("USD", "Firm A", "SOFR"),
    )
    batch = ENTRY["_CreateCashflows"](FIELDS, ROWS, template)
    date = ENTRY["_CreateValuationDate"](serial(AS_OF), 0.5)
    curve = ENTRY["_CreateDiscountCurve"]("SOFR", CURVE_HEADERS, CURVE_BODY)
    curves = ENTRY["_CollectDiscountCurves"](curve)
    results = ENTRY["_EvaluateCashflows"](batch, date, curves)
    return {
        "template": template, "batch": batch, "date": date, "curve": curve, "curves": curves,
        "results": results,
    }  # fmt: skip


def test_the_seam_makes_the_two_handles_named_for_the_currency_and_values_the_example() -> None:
    live = bridge.live_handles()[0]
    sheet = a_sheet()
    assert isinstance(sheet["template"], str) and sheet["template"].split(":")[1] == (
        "trade_template"
    )
    for name in ("batch", "results"):
        assert isinstance(sheet[name], str) and HANDLE.fullmatch(sheet[name]), sheet[name]
    assert sheet["batch"].split(":")[1] == "cashflows"
    assert sheet["results"].split(":")[1] == "cashflow_results"
    assert bridge.live_handles()[0] == live + 6  # the collection among them
    values = spilled(ENTRY["_ReportValues"](sheet["results"]))
    # currency_unit last, since currency-and-currency-unit.md: a cashflow's amounts are in
    # its currency's reference unit, whole dollars, the unit the trades settled in dollars
    # share.
    assert values[0] == ["cashflow_mark", "cashflow_cash", "currency", "as_of", "currency_unit"]
    assert values[1] == ["float64", "float64", "str", "datetime64[D]", "str"]
    assert values[2][0] == pytest.approx(500.0, **CLOSE)
    assert values[2][1:] == [250.0, "USD", serial(AS_OF), "DOLLAR"]
    risk = spilled(ENTRY["_ReportRisk"](sheet["results"], "dv01", "year"))
    assert risk[0] == ["as_of", serial(AS_OF)]
    assert risk[1] == ["period", DV01_LABEL]
    assert risk[2] == ["str | datetime64[D]", "float64"]
    assert risk[3][0] == "Total" and risk[3][1] == pytest.approx(0.85, **CLOSE)
    assert [r[0] for r in risk[4:]] == [
        serial("2027-01-01"),
        serial("2028-01-01"),
        serial("2029-01-01"),
    ]
    assert risk[5][1] == pytest.approx(-0.95, **CLOSE) and risk[6][1] == pytest.approx(1.8, **CLOSE)
    everything = spilled(ENTRY["_ReportRisk"](sheet["results"], "all", "day"))
    assert everything[1] == ["period", DV01_LABEL]
    assert [r[0] for r in everything[4:]] == [serial(DAY_BEFORE), serial(A_YEAR), serial(TWO_YEARS)]


def test_the_seam_reads_the_batch_and_the_results_back() -> None:
    sheet = a_sheet()
    batch = spilled(ENTRY["util_ReadHandle"](sheet["batch"]))
    assert batch[0] == [
        "trade_id",
        "trade_date",
        "amount",
        "currency",
        "payment_day",  # the field's name, cashflow-payment-day.md, in the place it had
        "counterparty",
        "description",
        "discount_curve_key",  # last, so that no column a sheet already reads has moved
    ]
    assert batch[1] == [
        "int64", "datetime64[D]", "float64", "str", "datetime64[D]", "str", "str", "str",
    ]  # fmt: skip
    assert batch[2] == [
        1.0, serial(AS_OF), 10_000.0, "USD", serial(A_YEAR), "Firm A", "Receivable", "SOFR",
    ]  # fmt: skip
    assert batch[4] == [
        3.0,
        serial(AS_OF),
        250.0,
        "USD",
        serial(DAY_BEFORE),
        "Firm A",
        "Earlier rebate",
        "SOFR",
    ]
    results = spilled(ENTRY["util_ReadHandle"](sheet["results"]))
    assert results[0] == [
        "payment_date", "amount", "is_paid", "payment_factor", "npv", "cash", "dv01", "currency",
        "as_of", "cashflow_mark", "cashflow_cash", "cashflow_dv01", "discount_curve_key",
        "currency_unit",
    ]  # fmt: skip
    assert results[1] == [
        "datetime64[D]", "float64", "bool", "float64", "float64", "float64", "float64", "str",
        "datetime64[D]", "float64", "float64", "float64", "str", "str",
    ]  # fmt: skip
    assert len(results) == 5  # three days on one key, three groups, under the two heading rows
    first, second, third = results[2], results[3], results[4]
    assert first[:3] == [serial(DAY_BEFORE), 250.0, True] and first[3:7] == [1.0, 0.0, 250.0, 0.0]
    assert first[7:9] == ["USD", serial(AS_OF)]
    assert first[9] == pytest.approx(500.0, **CLOSE) and first[10] == 250.0
    assert first[11] == pytest.approx(0.85, **CLOSE) and first[12:] == ["SOFR", "DOLLAR"]
    assert second[:3] == [serial(A_YEAR), 10_000.0, False]
    assert second[4] == pytest.approx(9_500.0, **CLOSE) and second[6] == pytest.approx(
        -0.95, **CLOSE
    )
    assert second[9:] == ["-", "-", "-", "SOFR", "DOLLAR"]  # the totals once, on the first row
    assert third[:3] == [serial(TWO_YEARS), -10_000.0, False]
    assert third[9:] == ["-", "-", "-", "SOFR", "DOLLAR"]


def test_the_seam_refuses_in_its_own_words_and_relays_the_librarys() -> None:
    sheet = a_sheet()
    # A fixed_float template: the seam binds the ticket against the template's instrument first,
    # so a cashflow header is refused as no field of fixed_float, and a ticket of the two fields
    # the instruments share reaches the library, which refuses the template by name.
    fixed = ENTRY["_CreateTradeTemplate"]("fixed_float", row("route"), row("cleared"))
    assert str(ENTRY["_CreateCashflows"](FIELDS, ROWS, fixed)).startswith(
        "#ERROR _CreateCashflows: fields cell (1, 3) is text 'amount', expected a field of "
        "fixed_float: trade_id, trade_date, contract_code,"
    )
    assert ENTRY["_CreateCashflows"](row("trade_date"), row(serial(AS_OF)), fixed) == (
        "#ERROR _CreateCashflows: ValueError: template is of instrument 'fixed_float', expected "
        "cashflow, the one instrument whose cashflows are built"
    )
    assert ENTRY["_CreateCashflows"](row("quantity"), row(1.0), sheet["template"]) == (
        "#ERROR _CreateCashflows: fields cell (1, 1) is text 'quantity', expected a field of "
        "cashflow: trade_id, trade_date, amount, currency, payment_day, counterparty, "
        "description, discount_curve_key"
    )
    assert ENTRY["_CreateCashflows"](
        row("trade_date", "amount", "payment_day"),
        Cells.from_rows([[serial(AS_OF), "x", serial(A_YEAR)]]),
        sheet["template"],
    ) == ("#ERROR _CreateCashflows: cashflow_rows cell (1, 2) is text 'x', expected number")
    assert ENTRY["_CreateCashflows"](FIELDS, ROWS, MISSING) == (
        "#ERROR _CreateCashflows: template is missing, expected trade template handle"
    )
    assert ENTRY["_EvaluateCashflows"](MISSING, sheet["date"], sheet["curves"]) == (
        "#ERROR _EvaluateCashflows: cashflows is missing, expected cashflows handle"
    )
    assert ENTRY["_EvaluateCashflows"](sheet["template"], sheet["date"], sheet["curves"]) == (
        f"#ERROR _EvaluateCashflows: cashflows is trade template handle '{sheet['template']}', "
        "expected cashflows handle"
    )
    assert ENTRY["_EvaluateCashflows"](sheet["batch"], sheet["curve"], sheet["curves"]) == (
        f"#ERROR _EvaluateCashflows: valuation_date is discount curve handle '{sheet['curve']}', "
        "expected valuation date handle"
    )
    later = ENTRY["_CreateValuationDate"](serial("2027-01-05"), 0.5)
    assert ENTRY["_EvaluateCashflows"](sheet["batch"], later, sheet["curves"]) == (
        "#ERROR _EvaluateCashflows: ValueError: discount curve 'SOFR' starts on 2027-01-04, "
        "expected 2027-01-05, the valuation date; a curve is never rebased"
    )
    assert ENTRY["_ReportRisk"](sheet["results"], "delta", "day") == (
        "#ERROR _ReportRisk: ValueError: risk is 'delta', expected dv01 or all for a batch of "
        "cashflows, which has no commodity risk"
    )
    assert ENTRY["_ReportReserves"](sheet["results"]) == (
        f"#ERROR _ReportReserves: results is cashflow results handle '{sheet['results']}', "
        "expected trade results handle"
    )
    assert ENTRY["_ReportValues"](sheet["batch"]) == (
        f"#ERROR _ReportValues: results is cashflows handle '{sheet['batch']}', expected trade "
        "results or cashflow results handle"
    )
    assert ENTRY["_ReportValues"](MISSING) == (
        "#ERROR _ReportValues: results is missing, expected trade results or cashflow results "
        "handle"
    )


# --- cashflow-curve-keys.md, a named curve for each cashflow ------------------------------------
# FFOIS beside the tests' SOFR: 0.90 a year out and 0.80 two years out. A ticket brings its own
# keys under a template that names none.

FFOIS = curve_of((AS_OF, 1.0), (A_YEAR, 0.90), (TWO_YEARS, 0.80), name="FFOIS")
FFOIS_LABEL = "FFOIS USD dv01 [DOLLAR per basis point]"
UNKEYED = template(currency="USD", discount_curve_key=None)


def keyed(
    amounts: list[float], keys: list[str], days: list[str] | None = None, **more: list[Any]
) -> FieldValues:
    """A ticket of those amounts under those keys, paying a year out unless days are given."""
    n = len(amounts)
    return ticket(
        trade_date=[AS_OF] * n,
        amount=amounts,
        payment_day=days or [A_YEAR] * n,
        discount_curve_key=keys,
        **more,
    )


def test_ten_thousand_on_sofr_against_ten_thousand_on_ffois_is_two_groups_worth_500() -> None:
    # The ticket's example: the amounts net to nothing before discounting and are worth 500,
    # 9,500 on SOFR at 0.95 less 9,000 on FFOIS at 0.90, with -0.95 and +0.90 of DV01.
    counter = WorkCounter()
    batch = booked(keyed([10_000.0, -10_000.0], ["SOFR", "FFOIS"]), UNKEYED, counter)
    assert batch.discount_curve_key == ("SOFR", "FFOIS") and batch.keys == ("SOFR", "FFOIS")
    np.testing.assert_array_equal(batch.payment_days, dates(A_YEAR))  # one day, two groups
    assert batch.group_day.tolist() == [0, 0] and batch.group_key.tolist() == [0, 1]
    assert batch.group_amounts.tolist() == [10_000.0, -10_000.0]
    assert batch.group_of_row.tolist() == [0, 1]
    assert counter.freeze().as_dict() == {
        "cashflows_booked": 2,
        "payment_days_mapped": 1,
        "payment_groups_formed": 2,
    }
    counter = WorkCounter()
    result = valued(batch, curve=collected(CURVE, FFOIS), counter=counter)
    assert result.curves[0] is CURVE and result.curves[1] is FFOIS and len(result.curves) == 2
    assert result.mark == pytest.approx(500.0, **CLOSE) and result.cash == 0.0
    assert result.dv01 == pytest.approx(-0.05, **CLOSE)
    np.testing.assert_allclose(result.payment_factor, [0.95, 0.90], **TIGHT)
    np.testing.assert_allclose(result.npv, [9_500.0, -9_000.0], **TIGHT)
    np.testing.assert_allclose(result.group_dv01, [-0.95, 0.90], **TIGHT)
    sofr, ffois = result.rate_contributions  # one a curve, in key order
    assert sofr.curve is CURVE and ffois.curve is FFOIS
    assert sofr.dv01 == pytest.approx(-0.95, **CLOSE) and ffois.dv01 == pytest.approx(0.90, **CLOSE)
    assert sofr.days is batch.payment_days and ffois.days is batch.payment_days  # one axis
    np.testing.assert_allclose(sofr.dv01_by_day, [-0.95], **TIGHT)
    np.testing.assert_allclose(ffois.dv01_by_day, [0.90], **TIGHT)
    assert counter.freeze().as_dict() == {
        "curves_selected": 2,
        "payment_factors_read": 2,
        "payments_valued": 2,
        "risk_reductions": 7,
    }
    for array in (result.group_dv01, sofr.dv01_by_day, ffois.dv01_by_month, ffois.dv01_by_year):
        assert not array.flags.writeable
    # SOFR at 0.96: 600 and -0.06; FFOIS's share as it was and the booked cashflows the same.
    moved = valued(batch, curve=collected(curve_of((AS_OF, 1.0), (A_YEAR, 0.96)), FFOIS))
    assert moved.cashflows is batch
    assert moved.mark == pytest.approx(600.0, **CLOSE)
    assert moved.dv01 == pytest.approx(-0.06, **CLOSE)
    assert moved.rate_contributions[1].dv01 == ffois.dv01


def test_rows_net_within_a_day_and_a_key_and_never_across_keys() -> None:
    # 100 and -40 on SOFR are one group of 60; 60 and -60 on FFOIS a group of nothing, kept
    # with its key; a second day on SOFR is a group of its own.
    batch = booked(
        keyed(
            [100.0, -40.0, 60.0, -60.0, 7.0],
            ["SOFR", "SOFR", "FFOIS", "FFOIS", "SOFR"],
            [A_YEAR, A_YEAR, A_YEAR, A_YEAR, TWO_YEARS],
        ),
        UNKEYED,
    )
    assert batch.keys == ("SOFR", "FFOIS")
    np.testing.assert_array_equal(batch.payment_days, dates(A_YEAR, TWO_YEARS))
    assert batch.group_day.tolist() == [0, 0, 1] and batch.group_key.tolist() == [0, 1, 0]
    assert batch.group_amounts.tolist() == [60.0, 0.0, 7.0]
    assert batch.group_of_row.tolist() == [0, 0, 1, 1, 2]
    result = valued(batch, curve=collected(CURVE, FFOIS))
    np.testing.assert_allclose(result.npv, [57.0, 0.0, 6.3], **TIGHT)
    assert result.mark == pytest.approx(63.3, **CLOSE)
    sofr, ffois = result.rate_contributions
    assert ffois.dv01 == 0.0 and ffois.curve is FFOIS  # the group of nothing keeps its curve
    np.testing.assert_allclose(sofr.dv01_by_day, [-0.0057, -0.00126], **TIGHT)
    # The keys in the order the rows first name them, whatever their spelling sorts as.
    assert booked(keyed([1.0, 2.0], ["SOFR", "FFOIS"]), UNKEYED).keys == ("SOFR", "FFOIS")
    assert booked(keyed([1.0, 2.0], ["FFOIS", "SOFR"]), UNKEYED).keys == ("FFOIS", "SOFR")


def test_the_key_comes_from_the_template_or_the_ticket_and_is_a_curves_name() -> None:
    plain = ticket(trade_date=[AS_OF] * 2, amount=[1.0, 2.0], payment_day=[A_YEAR] * 2)
    from_template = booked(plain, template(currency="USD", discount_curve_key="FFOIS"))
    assert from_template.discount_curve_key == ("FFOIS", "FFOIS")
    assert from_template.keys == ("FFOIS",) and from_template.group_key.tolist() == [0]
    from_ticket = booked(keyed([1.0, 2.0], ["FFOIS", "SOFR"]), UNKEYED)
    assert from_ticket.discount_curve_key == ("FFOIS", "SOFR")
    assert refused_booking(keyed([1.0], ["SOFR"])) == (
        "discount_curve_key is supplied by the template and by the ticket, expected by one of them"
    )
    assert refused_booking(plain, UNKEYED) == (
        "discount_curve_key is missing, expected a value in the template or a column in the ticket"
    )
    # The curve's own name rule, each distinct text read once and named with its first row.
    assert refused_booking(keyed([1.0, 2.0, 3.0], ["SOFR", " SOFR", " SOFR"]), UNKEYED) == (
        "discount_curve_key row 2 is ' SOFR', expected a name with no whitespace around it"
    )
    with pytest.raises(ValueError) as caught:
        template(currency="USD", discount_curve_key="SOFR ")
    assert str(caught.value) == (
        "discount_curve_key is 'SOFR ', expected a name with no whitespace around it"
    )
    # Case and all: another spelling is another key, and names another curve.
    cased = booked(keyed([1.0, 1.0], ["SOFR", "sofr"]), UNKEYED)
    assert cased.keys == ("SOFR", "sofr") and cased.group_amounts.tolist() == [1.0, 1.0]


def test_a_key_is_bound_by_its_exact_name_and_one_the_collection_lacks_names_its_first_row() -> (
    None
):
    mixed = booked(keyed([1.0, 2.0, 3.0], ["SOFR", "SONIA", "SONIA"], trade_id=[1, 2, 3]), UNKEYED)
    assert refused_valuation(mixed, curve=collected(CURVE, FFOIS)) == (
        "discount_curve_key 'SONIA' of trade 2 at row 2 names no curve of the collection, which "
        "holds 'SOFR' and 'FFOIS'; expected a curve of that name"
    )
    # A collection of one is no fallback, and a ticket without identifiers names the row alone.
    one = booked(keyed([1.0], ["FFOIS"]), UNKEYED)
    assert refused_valuation(one) == (
        "discount_curve_key 'FFOIS' of trade at row 1 names no curve of the collection, which "
        "holds 'SOFR'; expected a curve of that name"
    )
    assert refused_valuation(booked(keyed([1.0], ["sofr"]), UNKEYED)).startswith(
        "discount_curve_key 'sofr' of trade at row 1 names no curve of the collection, "
    )
    # The collection's order changes nothing: the curves stand in the batch's key order.
    pair = booked(keyed([10_000.0, -10_000.0], ["SOFR", "FFOIS"]), UNKEYED)
    one_way = valued(pair, curve=collected(CURVE, FFOIS))
    other = valued(pair, curve=collected(FFOIS, CURVE))
    assert one_way.curves == other.curves and one_way.curves[0] is CURVE
    assert (one_way.mark, one_way.cash, one_way.dv01) == (other.mark, other.cash, other.dv01)


def test_each_selected_curve_starts_on_the_day_and_covers_its_own_days_alone() -> None:
    # SOFR pays a year out and FFOIS two years out: each curve is held to its own days.
    mixed = booked(keyed([100.0, 100.0], ["SOFR", "FFOIS"], [A_YEAR, TWO_YEARS]), UNKEYED)
    late = curve_of(("2027-01-05", 1.0), (TWO_YEARS, 0.9), name="FFOIS")
    assert refused_valuation(mixed, curve=collected(CURVE, late)) == (
        "discount curve 'FFOIS' starts on 2027-01-05, expected 2027-01-04, the valuation date; "
        "a curve is never rebased"
    )
    short = curve_of((AS_OF, 1.0), (A_YEAR, 0.9), name="FFOIS")
    assert refused_valuation(mixed, curve=collected(CURVE, short)) == (
        f"the payment on {TWO_YEARS} on FFOIS is past the discount curve 'FFOIS', which runs from "
        f"{AS_OF} to {A_YEAR}; expected every unpaid payment day covered"
    )
    # A SOFR curve of one year serves, its own payment being a year out.
    served = valued(mixed, curve=collected(curve_of((AS_OF, 1.0), (A_YEAR, 0.95)), FFOIS))
    assert served.mark == pytest.approx(95.0 + 80.0, **CLOSE)
    # A curve nobody selects is read for nothing: short, or starting on another day.
    unused = curve_of(("2030-01-01", 1.0), name="SONIA")
    beside = valued(mixed, curve=collected(unused, CURVE, FFOIS))
    assert beside.mark == valued(mixed, curve=collected(CURVE, FFOIS)).mark
    assert len(beside.curves) == 2 and len(beside.rate_contributions) == 2
    # Paid in full, the batch still binds its keys and checks each selected curve's start,
    # and reads no factor: curves of the one day serve.
    after = "2029-01-04"
    sofr_day = curve_of((after, 1.0))
    ffois_day = curve_of((after, 1.0), name="FFOIS")
    counter = WorkCounter()
    paid = valued(mixed, after, collected(sofr_day, ffois_day), counter)
    assert (paid.mark, paid.cash, paid.dv01) == (0.0, 200.0, 0.0)
    assert paid.is_paid.tolist() == [True, True] and paid.payment_factor.tolist() == [1.0, 1.0]
    assert (
        counter.freeze()["payment_factors_read"] == 0 and counter.freeze()["curves_selected"] == 2
    )
    assert refused_valuation(mixed, after, collected(sofr_day)).startswith(
        "discount_curve_key 'FFOIS' of trade at row 2 names no curve of the collection, "
    )
    assert refused_valuation(mixed, after, collected(sofr_day, FFOIS)) == (
        "discount curve 'FFOIS' starts on 2027-01-04, expected 2029-01-04, the valuation date; "
        "a curve is never rebased"
    )


MIXED_ROWS: tuple[tuple[float, str, str], ...] = (
    (10_000.0, "SOFR", A_YEAR),
    (-10_000.0, "FFOIS", A_YEAR),
    (250.0, "SOFR", DAY_BEFORE),
    (40.0, "FFOIS", TWO_YEARS),
    (-15.0, "SOFR", TWO_YEARS),
    (-15.0, "SOFR", TWO_YEARS),  # a repeated row, a second payment
    (0.0, "FFOIS", DAY_BEFORE),  # a zero row, kept
)


def of_rows(rows: tuple[tuple[float, str, str], ...]) -> Cashflows:
    return booked(keyed([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]), UNKEYED)


def test_a_mixed_batch_is_its_one_curve_batches_summed_curve_by_curve_in_any_order() -> None:
    both = collected(CURVE, FFOIS)
    whole = valued(of_rows(MIXED_ROWS), curve=both)
    sofr_alone = valued(of_rows(tuple(r for r in MIXED_ROWS if r[1] == "SOFR")), curve=both)
    ffois_alone = valued(of_rows(tuple(r for r in MIXED_ROWS if r[1] == "FFOIS")), curve=both)
    assert whole.mark == pytest.approx(sofr_alone.mark + ffois_alone.mark, **CLOSE)
    assert whole.cash == sofr_alone.cash + ffois_alone.cash == 250.0
    assert whole.dv01 == pytest.approx(sofr_alone.dv01 + ffois_alone.dv01, **CLOSE)
    for share, alone in zip(whole.rate_contributions, (sofr_alone, ffois_alone), strict=True):
        (its,) = alone.rate_contributions
        assert share.curve is its.curve and share.dv01 == pytest.approx(its.dv01, **CLOSE)
        by_day = dict(zip(share.days.tolist(), share.dv01_by_day.tolist(), strict=True))
        for day, value in zip(its.days.tolist(), its.dv01_by_day.tolist(), strict=True):
            assert by_day[day] == pytest.approx(value, **CLOSE)
        assert sum(by_day.values()) == pytest.approx(its.dv01, **CLOSE)
    # The rows in another order, and the collection in another: the same values and shares.
    turned = valued(of_rows(MIXED_ROWS[::-1]), curve=collected(FFOIS, CURVE))
    assert turned.mark == pytest.approx(whole.mark, **CLOSE) and turned.cash == whole.cash
    assert turned.cashflows.keys == ("FFOIS", "SOFR")  # the reversed rows name FFOIS first
    shares = {c.curve.name: c.dv01 for c in turned.rate_contributions}
    for share in whole.rate_contributions:
        assert shares[share.curve.name] == pytest.approx(share.dv01, **CLOSE)


def test_the_report_shows_a_dv01_column_per_curve_on_one_date_axis() -> None:
    result = valued(
        booked(
            keyed(
                [10_000.0, -10_000.0, 100.0],
                ["SOFR", "FFOIS", "FFOIS"],
                [A_YEAR, A_YEAR, TWO_YEARS],
            ),
            UNKEYED,
        ),
        curve=collected(CURVE, FFOIS),
    )
    by_day = result.report(Risk.DV01, Bucket.DAY)
    np.testing.assert_array_equal(by_day.dates, dates(A_YEAR, TWO_YEARS))
    assert by_day.labels == (DV01_LABEL, FFOIS_LABEL)
    assert by_day.totals == pytest.approx((-0.95, 0.90 - 0.016), **CLOSE)
    np.testing.assert_allclose(by_day.columns[0], [-0.95, 0.0], **TIGHT)  # SOFR pays one day
    np.testing.assert_allclose(by_day.columns[1], [0.90, -0.016], **TIGHT)
    by_year = result.report(Risk.ALL, Bucket.YEAR)
    np.testing.assert_array_equal(by_year.dates, dates("2027-01-01", "2028-01-01", "2029-01-01"))
    assert by_year.labels == (DV01_LABEL, FFOIS_LABEL)
    np.testing.assert_allclose(by_year.columns[0], [0.0, -0.95, 0.0], **TIGHT)
    np.testing.assert_allclose(by_year.columns[1], [0.0, 0.90, -0.016], **TIGHT)
    by_month = result.report(Risk.DV01, Bucket.MONTH)
    assert by_month.dates.size == 25 and len(by_month.columns) == 2
    assert by_month.columns[1][24] == pytest.approx(-0.016, **CLOSE)


def test_a_group_past_the_largest_number_is_refused_by_its_day_and_key() -> None:
    largest = float(np.finfo(np.float64).max)
    assert refused_booking(keyed([1.0, largest, largest], ["SOFR", "FFOIS", "FFOIS"]), UNKEYED) == (
        f"the payments on {A_YEAR} on FFOIS sum to inf, expected a finite amount of DOLLAR; the "
        "rows' amounts, each finite, sum past the largest number"
    )
    # The same amounts under two keys are two groups, each finite, and book.
    apart = booked(keyed([largest, largest], ["SOFR", "FFOIS"]), UNKEYED)
    assert apart.group_amounts.tolist() == [largest, largest]
    assert refused_valuation(apart, curve=collected(CURVE, FFOIS)) == (
        "the batch has inf of mark in all, expected a finite amount of DOLLAR; the payments, each "
        "finite, sum past the largest number"
    )


# The review's case on #260: eight annual payment days from 4 January 4850, each receiving 8e307
# on SOFR and paying 8e307 on FFOIS, both curves at 1 throughout, valued 4 January 2027. A
# payment that far out has a DV01 of some 2.26e307, 0.0001 times 2,823 years and more times its
# amount.
FAR_DAYS = [f"{year}-01-04" for year in range(4850, 4858)]
FAR_AMOUNT = 8e307


def far_curves() -> DiscountCurveSet:
    flat = ((AS_OF, 1.0), (FAR_DAYS[-1], 1.0))
    return collected(curve_of(*flat), curve_of(*flat, name="FFOIS"))


def far_ticket(days: list[str], first: str = "SOFR", second: str = "FFOIS") -> FieldValues:
    """On each of those days the amount received on the first key and paid on the second."""
    return keyed(
        [FAR_AMOUNT, -FAR_AMOUNT] * len(days),
        [first, second] * len(days),
        [d for d in days for _ in range(2)],
    )


def test_a_curves_own_total_past_the_largest_number_is_refused_by_its_curve() -> None:
    curves = far_curves()
    # Seven days: every total is finite, the batch's nothing and each curve's seven DV01s.
    seven = valued(booked(far_ticket(FAR_DAYS[:7]), UNKEYED), curve=curves)
    years_out = (dates(*FAR_DAYS[:7]) - np.datetime64(AS_OF)).astype(np.float64) / 365.0
    by_hand = -0.0001 * FAR_AMOUNT * float(years_out.sum())  # some -1.58e308, inside the range
    sofr, ffois = seven.rate_contributions
    assert math.isfinite(by_hand) and sofr.dv01 == pytest.approx(by_hand, **CLOSE)
    assert ffois.dv01 == -sofr.dv01
    assert seven.mark == 0.0 and seven.cash == 0.0
    assert abs(seven.dv01) <= 1e-9 * abs(by_hand)  # the curves' totals cancel in the batch's
    # The eighth: the receipts still cancel the payments in the batch's mark and DV01, and each
    # curve's months and years hold one payment day apiece, so the batch's totals and every
    # period are finite; each curve's own total is not, and the first in key order is named.
    eight = booked(far_ticket(FAR_DAYS), UNKEYED)
    assert refused_valuation(eight, curve=curves) == (
        "the batch has -inf of DV01 on SOFR in all, expected a finite amount of DOLLAR per basis "
        "point; the curve's payments' DV01s, each finite, sum past the largest number"
    )
    other_way = booked(far_ticket(FAR_DAYS, "FFOIS", "SOFR"), UNKEYED)
    assert refused_valuation(other_way, curve=curves) == (
        "the batch has -inf of DV01 on FFOIS in all, expected a finite amount of DOLLAR per basis "
        "point; the curve's payments' DV01s, each finite, sum past the largest number"
    )


# --- the same through the seam --------------------------------------------------------------------


def a_mixed_sheet() -> dict[str, Any]:
    """The ticket's two rows keyed in a ticket column, the two curves and their collection."""
    template = ENTRY["_CreateTradeTemplate"]("cashflow", row("currency"), row("USD"))
    batch = ENTRY["_CreateCashflows"](
        row("trade_date", "amount", "payment_day", "discount_curve_key"),
        Cells.from_rows(
            [
                [serial(AS_OF), 10_000.0, serial(A_YEAR), "SOFR"],
                [serial(AS_OF), -10_000.0, serial(A_YEAR), "FFOIS"],
            ]
        ),
        template,
    )
    date = ENTRY["_CreateValuationDate"](serial(AS_OF), 0.5)
    sofr = ENTRY["_CreateDiscountCurve"](
        "SOFR", CURVE_HEADERS, Cells.from_rows([[serial(AS_OF), 1.0], [serial(A_YEAR), 0.95]])
    )
    ffois = ENTRY["_CreateDiscountCurve"](
        "FFOIS", CURVE_HEADERS, Cells.from_rows([[serial(AS_OF), 1.0], [serial(A_YEAR), 0.90]])
    )
    curves = ENTRY["_CollectDiscountCurves"](Cells.from_rows([[sofr], [ffois]]))
    results = ENTRY["_EvaluateCashflows"](batch, date, curves)
    return {
        "template": template, "batch": batch, "date": date, "sofr": sofr, "ffois": ffois,
        "curves": curves, "results": results,
    }  # fmt: skip


def test_the_seam_values_two_keys_and_reads_a_column_and_a_row_for_each() -> None:
    sheet = a_mixed_sheet()
    values = spilled(ENTRY["_ReportValues"](sheet["results"]))
    assert values[2][0] == pytest.approx(500.0, **CLOSE) and values[2][1] == 0.0
    risk = spilled(ENTRY["_ReportRisk"](sheet["results"], "dv01", "day"))
    assert risk[1] == ["period", DV01_LABEL, FFOIS_LABEL]
    assert risk[3][0] == "Total"
    assert risk[3][1:] == pytest.approx([-0.95, 0.90], **CLOSE)
    assert risk[4][0] == serial(A_YEAR) and risk[4][1:] == pytest.approx([-0.95, 0.90], **CLOSE)
    assert len(risk) == 5  # one day, shared by the two curves
    everything = spilled(ENTRY["_ReportRisk"](sheet["results"], "all", "year"))
    assert everything[1] == ["period", DV01_LABEL, FFOIS_LABEL]
    booked_rows = spilled(ENTRY["util_ReadHandle"](sheet["batch"]))
    assert booked_rows[0][-1] == "discount_curve_key"
    assert [line[-1] for line in booked_rows[2:]] == ["SOFR", "FFOIS"]
    read = spilled(ENTRY["util_ReadHandle"](sheet["results"]))
    assert read[0][0] == "payment_date" and read[0][-2:] == ["discount_curve_key", "currency_unit"]
    assert len(read) == 4  # one payment day on two keys: two rows under the headings
    first, second = read[2], read[3]
    assert first[:3] == [serial(A_YEAR), 10_000.0, False] and first[-2:] == ["SOFR", "DOLLAR"]
    assert first[3:7] == pytest.approx([0.95, 9_500.0, 0.0, -0.95], **CLOSE)
    assert first[9:12] == pytest.approx([500.0, 0.0, -0.05], **CLOSE)  # the totals once
    assert second[:3] == [serial(A_YEAR), -10_000.0, False] and second[-2:] == ["FFOIS", "DOLLAR"]
    assert second[3:7] == pytest.approx([0.90, -9_000.0, 0.0, 0.90], **CLOSE)
    assert second[9:12] == ["-", "-", "-"]
    # SOFR at 0.96: new results, 600, over the same booked cashflows, the held results as
    # they were.
    lifted = ENTRY["_CreateDiscountCurve"](
        "SOFR", CURVE_HEADERS, Cells.from_rows([[serial(AS_OF), 1.0], [serial(A_YEAR), 0.96]])
    )
    again = ENTRY["_CollectDiscountCurves"](Cells.from_rows([[lifted], [sheet["ffois"]]]))
    moved = ENTRY["_EvaluateCashflows"](sheet["batch"], sheet["date"], again)
    assert spilled(ENTRY["_ReportValues"](moved))[2][0] == pytest.approx(600.0, **CLOSE)
    assert spilled(ENTRY["_ReportRisk"](moved, "dv01", "day"))[3][1:] == pytest.approx(
        [-0.96, 0.90], **CLOSE
    )
    assert spilled(ENTRY["_ReportValues"](sheet["results"]))[2][0] == pytest.approx(500.0, **CLOSE)
    # A collection of this result alone reports what the result reports.
    alone = ENTRY["_AggregateResults"](sheet["results"])
    assert spilled(ENTRY["_ReportRisk"](alone, "dv01", "day")) == risk


def test_the_seam_refuses_a_curve_where_the_collection_goes_and_a_key_naming_none() -> None:
    sheet = a_mixed_sheet()
    batch, date = sheet["batch"], sheet["date"]
    assert ENTRY["_EvaluateCashflows"](batch, date, sheet["sofr"]) == (
        "#ERROR _EvaluateCashflows: discount_curve_set is discount curve handle "
        f"'{sheet['sofr']}', expected discount curve set handle"
    )
    assert ENTRY["_EvaluateCashflows"](batch, date, MISSING) == (
        "#ERROR _EvaluateCashflows: discount_curve_set is missing, expected discount curve set "
        "handle"
    )
    only_sofr = ENTRY["_CollectDiscountCurves"](sheet["sofr"])
    assert ENTRY["_EvaluateCashflows"](batch, date, only_sofr) == (
        "#ERROR _EvaluateCashflows: ValueError: discount_curve_key 'FFOIS' of trade at row 2 "
        "names no curve of the collection, which holds 'SOFR'; expected a curve of that name"
    )
    fields = row("trade_date", "amount", "payment_day")
    cells = Cells.from_rows([[serial(AS_OF), 1.0, serial(A_YEAR)]])
    assert ENTRY["_CreateCashflows"](fields, cells, sheet["template"]) == (
        "#ERROR _CreateCashflows: ValueError: discount_curve_key is missing, expected a value in "
        "the template or a column in the ticket"
    )


def test_the_seam_publishes_no_results_whose_curve_total_is_past_the_largest_number() -> None:
    # The review's reproduction on #260, through the worksheet functions: results were published
    # with a mark of nothing, and the risk report and the collection then failed on SOFR's total.
    template = ENTRY["_CreateTradeTemplate"]("cashflow", row("currency"), row("USD"))
    body = [
        [serial(AS_OF), sign * FAR_AMOUNT, serial(day), key]
        for day in FAR_DAYS
        for sign, key in ((1.0, "SOFR"), (-1.0, "FFOIS"))
    ]
    batch = ENTRY["_CreateCashflows"](
        row("trade_date", "amount", "payment_day", "discount_curve_key"),
        Cells.from_rows(body),
        template,
    )
    date = ENTRY["_CreateValuationDate"](serial(AS_OF), 0.5)
    flat = Cells.from_rows([[serial(AS_OF), 1.0], [serial(FAR_DAYS[-1]), 1.0]])
    sofr = ENTRY["_CreateDiscountCurve"]("SOFR", CURVE_HEADERS, flat)
    ffois = ENTRY["_CreateDiscountCurve"]("FFOIS", CURVE_HEADERS, flat)
    curves = ENTRY["_CollectDiscountCurves"](Cells.from_rows([[sofr], [ffois]]))
    live = bridge.live_handles()[0]
    assert ENTRY["_EvaluateCashflows"](batch, date, curves) == (
        "#ERROR _EvaluateCashflows: ValueError: the batch has -inf of DV01 on SOFR in all, "
        "expected a finite amount of DOLLAR per basis point; the curve's payments' DV01s, each "
        "finite, sum past the largest number"
    )
    assert bridge.live_handles()[0] == live  # refused before anything was published


# --- cashflow-payment-day.md, a cashflow is booked under payment_day ----------------------------


def test_the_payment_day_is_the_trades_header_and_a_date_only() -> None:
    # The cashflow's field is named as the trades' is, and typed as a date where theirs is a
    # date or a rule; the instrument's own table says so.
    names = [field.name for field in CASHFLOW.fields]
    assert names.index("payment_day") == 4 and "payment_date" not in names
    assert CASHFLOW_TYPES["payment_day"] is FieldType.DATE
    theirs = {field.name: field.type for field in FIXED_FLOAT.fields}["payment_day"]
    assert theirs is FieldType.DATE_OR_TEXT
    shown = spilled(ENTRY["_ShowInstrument"]("cashflow"))
    at = shown[0].index("payment_day")
    assert at == 5  # after the row labels, where payment_date stood
    assert shown[4][at] == "date" and shown[5][at] == "a date"
    rule = str(shown[6][at])
    assert rule.startswith("A date only, used as entered, never rolled")
    assert "a rule such as +1bd is a trade's" in rule


def test_a_date_under_payment_day_books_from_the_template_or_the_ticket() -> None:
    keyed_template = ENTRY["_CreateTradeTemplate"](
        "cashflow", row("currency", "discount_curve_key"), row("USD", "SOFR")
    )
    from_ticket = ENTRY["_CreateCashflows"](
        row("trade_date", "amount", "payment_day"),
        Cells.from_rows([[serial(AS_OF), 100.0, serial(A_YEAR)]]),
        keyed_template,
    )
    dated = ENTRY["_CreateTradeTemplate"](
        "cashflow",
        row("currency", "discount_curve_key", "payment_day"),
        row("USD", "SOFR", serial(A_YEAR)),
    )
    from_template = ENTRY["_CreateCashflows"](
        row("trade_date", "amount"), Cells.from_rows([[serial(AS_OF), 100.0]]), dated
    )
    # The template's readback names the field it holds, and both batches read back the same:
    # the day under payment_day, fourth here, a ticket without identifiers having no first column.
    held = spilled(ENTRY["util_ReadHandle"](dated))
    assert held[0] == ["instrument", "currency", "discount_curve_key", "payment_day"]
    assert held[1][3] == "datetime64[D]" and held[2][3] == serial(A_YEAR)
    for batch in (from_ticket, from_template):
        read = spilled(ENTRY["util_ReadHandle"](batch))
        assert read[0] == ["trade_date", "amount", "currency", "payment_day", "discount_curve_key"]
        assert read[1][3] == "datetime64[D]" and read[2][3] == serial(A_YEAR)
    # Valued, the two are one answer, and the results name the resolved date payment_date.
    date = ENTRY["_CreateValuationDate"](serial(AS_OF), 0.5)
    sofr = ENTRY["_CreateDiscountCurve"](
        "SOFR", CURVE_HEADERS, Cells.from_rows([[serial(AS_OF), 1.0], [serial(A_YEAR), 0.95]])
    )
    curves = ENTRY["_CollectDiscountCurves"](sofr)
    reads = [
        spilled(ENTRY["util_ReadHandle"](ENTRY["_EvaluateCashflows"](batch, date, curves)))
        for batch in (from_ticket, from_template)
    ]
    assert reads[0] == reads[1]
    assert reads[0][0][0] == "payment_date" and reads[0][2][0] == serial(A_YEAR)
    assert reads[0][2][4] == pytest.approx(95.0, **CLOSE)
    # In both, as any field: refused by its name.
    assert ENTRY["_CreateCashflows"](
        row("trade_date", "amount", "payment_day"),
        Cells.from_rows([[serial(AS_OF), 100.0, serial(A_YEAR)]]),
        dated,
    ) == (
        "#ERROR _CreateCashflows: ValueError: payment_day is supplied by the template and by "
        "the ticket, expected by one of them"
    )
    assert ENTRY["_CreateCashflows"](
        row("trade_date", "amount"), Cells.from_rows([[serial(AS_OF), 100.0]]), keyed_template
    ) == (
        "#ERROR _CreateCashflows: ValueError: payment_day is missing, expected a value in the "
        "template or a column in the ticket"
    )


def test_the_old_header_is_no_field_and_a_rule_is_no_date_each_in_the_seams_words() -> None:
    keyed_template = ENTRY["_CreateTradeTemplate"](
        "cashflow", row("currency", "discount_curve_key"), row("USD", "SOFR")
    )
    no_field = (
        "is text 'payment_date', expected a field of cashflow: trade_id, trade_date, amount, "
        "currency, payment_day, counterparty, description, discount_curve_key"
    )
    # No alias: the old header is refused in a ticket and in a template by the sentence for any
    # header that is no field, which lists the fields and so names the new one.
    assert ENTRY["_CreateCashflows"](
        row("trade_date", "amount", "payment_date"),
        Cells.from_rows([[serial(AS_OF), 100.0, serial(A_YEAR)]]),
        keyed_template,
    ) == (f"#ERROR _CreateCashflows: fields cell (1, 3) {no_field}")
    assert ENTRY["_CreateTradeTemplate"](
        "cashflow", row("currency", "payment_date"), row("USD", serial(A_YEAR))
    ) == (f"#ERROR _CreateTradeTemplate: fields cell (1, 2) {no_field}")
    # A rule, the trades' other form of the header, is text where a date goes: refused by its
    # cell, in the sentence for any cell of the wrong kind, which names no field.
    assert ENTRY["_CreateCashflows"](
        row("trade_date", "amount", "payment_day"),
        Cells.from_rows([[serial(AS_OF), 100.0, "+5bd"]]),
        keyed_template,
    ) == ("#ERROR _CreateCashflows: cashflow_rows cell (1, 3) is text '+5bd', expected date")
    assert ENTRY["_CreateTradeTemplate"](
        "cashflow", row("currency", "discount_curve_key", "payment_day"), row("USD", "SOFR", "+5bd")
    ) == ("#ERROR _CreateTradeTemplate: values cell (1, 3) is text '+5bd', expected date")


# --- the currency and the unit of it, currency-and-currency-unit.md ------------------------------


def test_a_cashflows_unit_is_its_currencys_reference_unit_read_off_the_unit_tables() -> None:
    # Two facts: the currency a row enters, USD, and the unit of it the amounts are in, the
    # currency's reference unit in the unit tables, whole units and never cents. The batch,
    # the results and the contribution carry both.
    batch = booked()
    assert (batch.currency, batch.currency_unit) == ("USD", "DOLLAR")
    result = valued(batch)
    assert (result.currency, result.currency_unit) == ("USD", "DOLLAR")
    assert [(c.currency, c.currency_unit) for c in result.rate_contributions] == [("USD", "DOLLAR")]
    # The unit is the tables' and typed nowhere in the cashflows: under tables whose dollar is
    # spelled BUCK, a spelling of this test's alone, the same ticket books in BUCK, the
    # heading's brackets and every refusal of an amount say so, and the currency is USD as
    # entered.
    spelled = unit_conversions(
        category(
            "USD",
            "BUCK",
            UnitDefinition("BUCK", "BUCK", 1.0),
            UnitDefinition("CENT", "BUCK", 0.01),
        )
    )
    batch = cashflows(TICKET, TEMPLATE, spelled, WorkCounter())
    assert (batch.currency, batch.currency_unit) == ("USD", "BUCK")
    result = valued(batch)
    assert (result.currency, result.currency_unit) == ("USD", "BUCK")
    assert result.report(Risk.DV01, Bucket.DAY).labels == ("SOFR USD dv01 [BUCK per basis point]",)
    assert result.dv01 == pytest.approx(0.85, **CLOSE)  # the numbers as they were
    largest = float(np.finfo(np.float64).max)
    doubled = ticket(trade_date=[AS_OF] * 2, amount=[largest, largest], payment_day=[A_YEAR] * 2)
    with pytest.raises(ValueError) as caught:
        cashflows(doubled, TEMPLATE, spelled, WorkCounter())
    assert str(caught.value) == (
        f"the payments on {A_YEAR} on SOFR sum to inf, expected a finite amount of BUCK; the "
        "rows' amounts, each finite, sum past the largest number"
    )
    apart = ticket(
        trade_date=[AS_OF] * 2, amount=[largest, largest], payment_day=[A_YEAR, TWO_YEARS]
    )
    with pytest.raises(ValueError) as caught:
        cashflow_results(
            cashflows(apart, TEMPLATE, spelled, WorkCounter()),
            valuation_date(np.datetime64(AS_OF), 0.5),
            collected(curve_of((AS_OF, 1.0), (A_YEAR, 1.0), (TWO_YEARS, 1.0))),
            WorkCounter(),
        )
    assert str(caught.value) == (
        "the batch has inf of mark in all, expected a finite amount of BUCK; the payments, "
        "each finite, sum past the largest number"
    )
