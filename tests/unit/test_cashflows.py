"""The cashflow instrument, cashflow-instrument.md: known signed amounts in one currency, each on
its own payment day, booked from a template and a ticket and valued on a valuation day over a
discount curve, each unpaid day discounted with its DV01 and each paid day cash. The figures are
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

from goosedove.cashflows.booking import Cashflows, cashflows
from goosedove.cashflows.valuation import CashflowResults, cashflow_results
from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells
from goosedove.globals.discount_curve import DiscountCurve, bump_discount_curve
from goosedove.globals.valuation_date import valuation_date
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import CASHFLOW, FIXED_FLOAT, FieldType
from goosedove.instruments.fields import FieldValues
from goosedove.trades.risk_report import Bucket, Risk
from goosedove.trades.template import TradeTemplate, trade_template

DAY_BEFORE = "2027-01-03"
CURVE = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90))
DV01_LABEL = "SOFR USD dv01 [USD per basis point]"


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
    """A cashflow template holding those fields, one row."""
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
    payment_date=[A_YEAR, TWO_YEARS, DAY_BEFORE],
    description=["Receivable", "Payable", "Earlier rebate"],
)


def booked(
    rows: FieldValues = TICKET,
    shared: TradeTemplate = TEMPLATE,
    counter: WorkCounter | None = None,
) -> Cashflows:
    return cashflows(rows, shared, counter or WorkCounter())


def valued(
    batch: Cashflows,
    as_of: str = AS_OF,
    curve: DiscountCurve = CURVE,
    counter: WorkCounter | None = None,
) -> CashflowResults:
    return cashflow_results(
        batch, valuation_date(np.datetime64(as_of), 0.5), curve, counter or WorkCounter()
    )


def refused_booking(rows: FieldValues, shared: TradeTemplate = TEMPLATE) -> str:
    with pytest.raises(ValueError) as caught:
        booked(rows, shared)
    return str(caught.value)


def refused_valuation(batch: Cashflows, as_of: str = AS_OF, curve: DiscountCurve = CURVE) -> str:
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
    # The distinct days, increasing, the rows' amounts on each and each row's place among them.
    np.testing.assert_array_equal(batch.payment_days, dates(DAY_BEFORE, A_YEAR, TWO_YEARS))
    assert batch.payment_amounts.tolist() == [250.0, 10_000.0, -10_000.0]
    assert batch.day_of_row.tolist() == [1, 2, 0]
    np.testing.assert_array_equal(batch.months, dates("2027-01-01", "2028-01-01", "2029-01-01"))
    assert batch.month_of_day.tolist() == [0, 1, 2]
    np.testing.assert_array_equal(batch.years, dates("2027-01-01", "2028-01-01", "2029-01-01"))
    assert batch.year_of_month.tolist() == [0, 1, 2]
    assert counter.freeze().as_dict() == {"cashflows_booked": 3, "payment_days_mapped": 3}
    counter = WorkCounter()
    result = valued(batch, counter=counter)
    assert result.cashflows is batch and result.curve is CURVE
    assert str(result.as_of) == AS_OF and result.currency == "USD"
    assert result.mark == pytest.approx(500.0, **CLOSE)
    assert result.cash == 250.0
    assert result.dv01 == pytest.approx(0.85, **CLOSE)
    assert result.is_paid.tolist() == [True, False, False]
    np.testing.assert_allclose(result.payment_factor, [1.0, 0.95, 0.90], **TIGHT)
    np.testing.assert_allclose(result.npv, [0.0, 9_500.0, -9_000.0], **TIGHT)
    assert result.payment_cash.tolist() == [250.0, 0.0, 0.0]
    (contribution,) = result.rate_contributions  # the one curve's share, the whole of it
    assert contribution.curve is result.curve and contribution.currency == "USD"
    assert contribution.dv01 == result.dv01
    assert contribution.days is result.cashflows.payment_days
    np.testing.assert_allclose(contribution.dv01_by_day, [0.0, -0.95, 1.80], **TIGHT)
    np.testing.assert_allclose(contribution.dv01_by_month, [0.0, -0.95, 1.80], **TIGHT)
    np.testing.assert_allclose(contribution.dv01_by_year, [0.0, -0.95, 1.80], **TIGHT)
    assert counter.freeze().as_dict() == {
        "payment_factors_read": 2,
        "payments_valued": 2,
        "risk_reductions": 5,
    }
    for array in (
        result.is_paid,
        result.payment_factor,
        result.npv,
        result.payment_cash,
        result.rate_contributions[0].dv01_by_day,
        result.rate_contributions[0].dv01_by_month,
        result.rate_contributions[0].dv01_by_year,
        batch.trade_date,
        batch.amount,
        batch.payment_date,
        batch.payment_days,
        batch.payment_amounts,
        batch.day_of_row,
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
    batch = booked(ticket(trade_date=[AS_OF], amount=[100.0], payment_date=[A_YEAR]))
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
        ticket(trade_date=[AS_OF, AS_OF], amount=[100.0, -100.0], payment_date=[A_YEAR, A_YEAR])
    )
    assert same.payment_amounts.tolist() == [0.0] and same.rows == 2
    result = valued(same)
    assert (result.mark, result.cash, result.dv01) == (0.0, 0.0, 0.0)
    apart = booked(
        ticket(trade_date=[AS_OF, AS_OF], amount=[100.0, -100.0], payment_date=[A_YEAR, TWO_YEARS])
    )
    assert apart.payment_amounts.tolist() == [100.0, -100.0]
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
            payment_date=[TWO_YEARS, A_YEAR, A_YEAR, A_YEAR],
        )
    )
    assert batch.amount.tolist() == [0.5, 0.0, 100.0, 100.0]
    np.testing.assert_array_equal(batch.payment_days, dates(A_YEAR, TWO_YEARS))
    assert batch.payment_amounts.tolist() == [200.0, 0.5]
    assert batch.day_of_row.tolist() == [1, 0, 0, 0]
    result = valued(batch)
    assert result.mark == pytest.approx(190.0 + 0.45, **CLOSE)
    assert result.dv01 == pytest.approx(-0.019 - 0.00009, **CLOSE)


def test_a_batch_is_the_sum_of_its_singletons() -> None:
    whole = valued(booked())
    parts = [
        valued(booked(ticket(trade_date=[AS_OF], amount=[a], payment_date=[d])))
        for a, d in ((10_000.0, A_YEAR), (-10_000.0, TWO_YEARS), (250.0, DAY_BEFORE))
    ]
    assert whole.mark == pytest.approx(sum(p.mark for p in parts), **CLOSE)
    assert whole.cash == pytest.approx(sum(p.cash for p in parts), **CLOSE)
    assert whole.dv01 == pytest.approx(sum(p.dv01 for p in parts), **CLOSE)


def test_the_template_may_supply_the_payment_itself_and_the_ticket_the_rest() -> None:
    # A template holding the amount, the day and the currency: every row pays the same, the
    # ticket's trade dates and identifiers its own; a template of one row of everything serves
    # a ticket of trade dates alone.
    shared = template(currency="USD", amount=100.0, payment_date=A_YEAR, trade_id=7)
    batch = booked(ticket(trade_date=[AS_OF, DAY_BEFORE]), shared)
    assert batch.amount.tolist() == [100.0, 100.0]
    assert batch.trade_id is not None and batch.trade_id.tolist() == [7, 7]
    assert batch.payment_amounts.tolist() == [200.0] and batch.counterparty is None
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
        ticket(trade_date=[AS_OF], amount=[1.0], payment_date=[A_YEAR], currency=["USD"])
    ) == ("currency is supplied by the template and by the ticket, expected by one of them")
    assert refused_booking(ticket(trade_date=[AS_OF], payment_date=[A_YEAR])) == (
        "amount is missing, expected a value in the template or a column in the ticket"
    )
    assert refused_booking(ticket(amount=[1.0], payment_date=[A_YEAR])) == (
        "trade_date is missing, expected a value in the template or a column in the ticket"
    )
    assert refused_booking(
        ticket(trade_date=[AS_OF], amount=[1.0], payment_date=[A_YEAR]), template(counterparty="x")
    ) == ("currency is missing, expected a value in the template or a column in the ticket")
    assert refused_booking(ticket(trade_date=[AS_OF], amount=[1.0])) == (
        "payment_date is missing, expected a value in the template or a column in the ticket"
    )


def test_the_currency_is_usd_exactly_one_per_batch_and_cent_is_no_currency() -> None:
    bare = template(counterparty="Firm A")
    assert refused_booking(
        ticket(trade_date=[AS_OF], amount=[1.0], payment_date=[A_YEAR], currency=["usd"]), bare
    ) == ("currency row 1 is 'usd', expected USD, the one currency this version books")
    assert refused_booking(
        ticket(
            trade_date=[AS_OF] * 3,
            amount=[1.0] * 3,
            payment_date=[A_YEAR] * 3,
            currency=["USD", "CAD", "CAD"],
        ),
        bare,
    ) == ("currency row 2 is 'CAD', expected USD, the one currency this version books")
    assert refused_booking(
        ticket(trade_date=[AS_OF], amount=[1.0], payment_date=[A_YEAR], currency=["CENT"]), bare
    ) == ("currency row 1 is 'CENT', expected USD, the one currency this version books")
    with pytest.raises(ValueError) as caught:
        template(currency="CENT")
    assert (
        str(caught.value) == "currency is 'CENT', expected USD, the one currency this version books"
    )
    both = booked(
        ticket(trade_date=[AS_OF, AS_OF], amount=[1.0, 2.0], payment_date=[A_YEAR, A_YEAR],
               currency=["USD", "USD"]),
        bare,
    )  # fmt: skip
    assert both.currency == "USD"


def test_amounts_are_finite_and_identifiers_whole_each_named_by_its_row() -> None:
    assert refused_booking(
        ticket(trade_date=[AS_OF] * 2, amount=[1.0, math.inf], payment_date=[A_YEAR] * 2)
    ) == ("amount row 2 is inf, expected a finite amount")
    assert refused_booking(
        ticket(trade_date=[AS_OF], amount=[math.nan], payment_date=[A_YEAR])
    ) == ("amount row 1 is nan, expected a finite amount")
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
                payment_date=[A_YEAR] * 2,
            )
        ),
    )
    # Amounts finite each but past the largest number together on one day: refused by the day.
    largest = float(np.finfo(np.float64).max)
    assert refused_booking(
        ticket(trade_date=[AS_OF] * 2, amount=[largest, largest], payment_date=[A_YEAR] * 2)
    ) == (
        f"the payments on {A_YEAR} sum to inf, expected a finite amount of USD; the rows' "
        "amounts, each finite, sum past the largest number"
    )


# --- the rules of valuation -----------------------------------------------------------------------


def test_the_curve_starts_on_the_day_and_covers_every_unpaid_day_a_paid_one_needing_none() -> None:
    batch = booked()
    assert refused_valuation(batch, curve=curve_of(("2027-01-05", 1.0), (TWO_YEARS, 0.9))) == (
        "discount curve 'SOFR' starts on 2027-01-05, expected 2027-01-04, the valuation date; "
        "a curve is never rebased"
    )
    assert refused_valuation(batch, curve=curve_of((AS_OF, 1.0), (A_YEAR, 0.95))) == (
        f"the payment on {TWO_YEARS} is past the discount curve, which runs from {AS_OF} to "
        f"{A_YEAR}; expected every unpaid payment day covered"
    )
    # Paid in full on the day after the last payment: a curve of that one day serves.
    settled = valued(batch, "2029-01-04", curve_of(("2029-01-04", 1.0)))
    assert (settled.mark, settled.cash, settled.dv01) == (0.0, 250.0, 0.0)


def test_a_total_past_the_largest_number_is_refused_by_the_batch() -> None:
    largest = float(np.finfo(np.float64).max)
    batch = booked(
        ticket(trade_date=[AS_OF] * 2, amount=[largest, largest], payment_date=[A_YEAR, TWO_YEARS])
    )
    assert refused_valuation(batch) == (
        "the batch has inf of mark in all, expected a finite amount of USD; the payments, each "
        "finite, sum past the largest number"
    )
    paid = booked(
        ticket(trade_date=[AS_OF] * 2, amount=[largest, largest], payment_date=[DAY_BEFORE, AS_OF])
    )
    assert refused_valuation(paid) == (
        "the batch has inf of cash in all, expected a finite amount of USD; the payments, each "
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
FIELDS = row("trade_id", "trade_date", "amount", "payment_date", "description")
ROWS = Cells.from_rows(
    [
        [1.0, serial(AS_OF), 10_000.0, serial(A_YEAR), "Receivable"],
        [2.0, serial(AS_OF), -10_000.0, serial(TWO_YEARS), "Payable"],
        [3.0, serial(AS_OF), 250.0, serial(DAY_BEFORE), "Earlier rebate"],
    ]
)


def a_sheet() -> dict[str, Any]:
    """The ticket's example through the seam: the template, the batch, the valuation date, the
    curve and the results, each a handle."""
    template = ENTRY["_CreateTradeTemplate"](
        "cashflow", row("currency", "counterparty"), row("USD", "Firm A")
    )
    batch = ENTRY["_CreateCashflows"](FIELDS, ROWS, template)
    date = ENTRY["_CreateValuationDate"](serial(AS_OF), 0.5)
    curve = ENTRY["_CreateDiscountCurve"]("SOFR", CURVE_HEADERS, CURVE_BODY)
    results = ENTRY["_EvaluateCashflows"](batch, date, curve)
    return {
        "template": template, "batch": batch, "date": date, "curve": curve, "results": results
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
    assert bridge.live_handles()[0] == live + 5
    values = spilled(ENTRY["_ReportValues"](sheet["results"]))
    assert values[0] == ["cashflow_mark", "cashflow_cash", "currency", "as_of"]
    assert values[1] == ["float64", "float64", "str", "datetime64[D]"]
    assert values[2][0] == pytest.approx(500.0, **CLOSE)
    assert values[2][1:] == [250.0, "USD", serial(AS_OF)]
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
        "payment_date",
        "counterparty",
        "description",
    ]
    assert batch[1] == ["int64", "datetime64[D]", "float64", "str", "datetime64[D]", "str", "str"]
    assert batch[2] == [1.0, serial(AS_OF), 10_000.0, "USD", serial(A_YEAR), "Firm A", "Receivable"]
    assert batch[4] == [
        3.0,
        serial(AS_OF),
        250.0,
        "USD",
        serial(DAY_BEFORE),
        "Firm A",
        "Earlier rebate",
    ]
    results = spilled(ENTRY["util_ReadHandle"](sheet["results"]))
    assert results[0] == [
        "payment_date", "amount", "is_paid", "payment_factor", "npv", "cash", "dv01", "currency",
        "as_of", "cashflow_mark", "cashflow_cash", "cashflow_dv01",
    ]  # fmt: skip
    assert results[1] == [
        "datetime64[D]", "float64", "bool", "float64", "float64", "float64", "float64", "str",
        "datetime64[D]", "float64", "float64", "float64",
    ]  # fmt: skip
    assert len(results) == 5  # three distinct days under the two heading rows
    first, second, third = results[2], results[3], results[4]
    assert first[:3] == [serial(DAY_BEFORE), 250.0, True] and first[3:7] == [1.0, 0.0, 250.0, 0.0]
    assert first[7:9] == ["USD", serial(AS_OF)]
    assert first[9] == pytest.approx(500.0, **CLOSE) and first[10] == 250.0
    assert first[11] == pytest.approx(0.85, **CLOSE)
    assert second[:3] == [serial(A_YEAR), 10_000.0, False]
    assert second[4] == pytest.approx(9_500.0, **CLOSE) and second[6] == pytest.approx(
        -0.95, **CLOSE
    )
    assert second[9:] == ["-", "-", "-"]  # the totals once, on the first row
    assert third[:3] == [serial(TWO_YEARS), -10_000.0, False] and third[9:] == ["-", "-", "-"]


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
        "cashflow: trade_id, trade_date, amount, currency, payment_date, counterparty, description"
    )
    assert ENTRY["_CreateCashflows"](
        row("trade_date", "amount", "payment_date"),
        Cells.from_rows([[serial(AS_OF), "x", serial(A_YEAR)]]),
        sheet["template"],
    ) == ("#ERROR _CreateCashflows: cashflow_rows cell (1, 2) is text 'x', expected number")
    assert ENTRY["_CreateCashflows"](FIELDS, ROWS, MISSING) == (
        "#ERROR _CreateCashflows: template is missing, expected trade template handle"
    )
    assert ENTRY["_EvaluateCashflows"](MISSING, sheet["date"], sheet["curve"]) == (
        "#ERROR _EvaluateCashflows: cashflows is missing, expected cashflows handle"
    )
    assert ENTRY["_EvaluateCashflows"](sheet["template"], sheet["date"], sheet["curve"]) == (
        f"#ERROR _EvaluateCashflows: cashflows is trade template handle '{sheet['template']}', "
        "expected cashflows handle"
    )
    assert ENTRY["_EvaluateCashflows"](sheet["batch"], sheet["curve"], sheet["curve"]) == (
        f"#ERROR _EvaluateCashflows: valuation_date is discount curve handle '{sheet['curve']}', "
        "expected valuation date handle"
    )
    later = ENTRY["_CreateValuationDate"](serial("2027-01-05"), 0.5)
    assert ENTRY["_EvaluateCashflows"](sheet["batch"], later, sheet["curve"]) == (
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
