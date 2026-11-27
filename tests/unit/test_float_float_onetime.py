"""A onetime period on a float_float, issue #279: one window across a row's two dates, each leg
averaged over its own pricing days of it, across a month end and a roll, and the two averages
settled against the spread price in one net payment. The units tests' RB in dollars a gallon
less WTI in dollars a barrel, WTI closed on the window's last day so that the two legs count
different days; the window priced by hand while every day is live, part fixed and paid; the
window found on each leg's own schedule; and the rules: both methods asian, two futures indexes,
a quantity of the period or a day. Every expected number is hand arithmetic here; the production
code is never asked for one."""

import re
from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest
from holiday_fixtures import a_name
from test_bilateral_kernel import curve_of, curve_set
from test_create_trades import seam_calendars, seam_key
from test_float_float import TEMPLATE_FIELDS
from test_float_float_units import (
    A_GAL,
    B_BBL,
    CRACK,
    RB,
    TICKET,
    an_index,
    booked,
    history_at,
    near,
    refused,
    valued,
)
from test_trades import dates, day, quoted
from test_two_index import (
    AS_OF,
    CLOSE,
    PAY,
    PID,
    SEAM,
    across,
    cell,
    close,
    down,
    grid,
    read,
    serial,
    spilled,
    under,
)

from catalyst.excel import bridge
from catalyst.excel.bridge import Cells
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades
from catalyst.trades.results import TradeResults
from catalyst.trades.terms import FREQUENCIES, SettlementFrequency

# --- the window -----------------------------------------------------------------------------------
# Wednesday 20 January to Wednesday 10 February 2027: 22 calendar days and 16 business days, six
# to G27's expiry on the 27th, which G27 prices, and ten after it, which H27 prices. WTI is
# closed on the 10th, so it counts 15 days, nine of them H27's, and is last observed on the 9th.

WTI = an_index(
    "WTI", ("DOLLAR", "BBL"), (1_000.0, "BBL"), holidays=("2026-12-25", "2027-01-01", "2027-02-10")
)
ONETIME: dict[str, object] = {
    **CRACK,
    "schedule_method": "asian",
    "second_schedule_method": "asian",
    "settlement_frequency": "onetime",
    "quantity_per": "period",
}
WINDOW: dict[str, list[object]] = {
    **{name: values for name, values in TICKET.items() if name != "contract_code"},
    "start_date": ["2027-01-20"],
    "end_date": ["2027-02-10"],
}
# Quoted on 4 January 2027 from G27 on: RB at 2.10 and 2.14 a gallon, WTI at 70 and 71 a barrel.
QUOTES = ((2.10, 2.14), (70.00, 71.00))
# RB averages (6 x 2.10 + 10 x 2.14) / 16 = 2.125 a gallon, 89.25 a barrel; WTI averages
# (6 x 70 + 9 x 71) / 15 = 70.60. On 1,000 barrels at a spread price of 15.00: 89,250 less 70,600
# less 15,000.
THREE = ((2.10, 2.14, 2.16), (70.00, 71.00, 72.00))  # and J27, for February's last days
RB_SIDE = 89_250.0  # 42,000 gallons at 2.125
WTI_SIDE = -70_600.0  # 1,000 barrels at 70.60, paid
PAYMENT = 3_650.0


def a_window(
    template: Mapping[str, object] = ONETIME, ticket: Mapping[str, list[object]] = WINDOW
) -> Trades:
    return booked(template, ticket, (RB, WTI))


def test_the_hand_table_is_the_two_averages_against_the_spread_price() -> None:
    batch = a_window()
    terms = batch.resolved
    assert terms.descriptor == "RB-WTI"
    # One row, one component, its calculation period the window itself.
    assert terms.occurrence.tolist() == [0]
    assert terms.settlement_frequency.tolist() == [FREQUENCIES.index(SettlementFrequency.ONETIME)]
    np.testing.assert_array_equal(terms.period_start, dates("2027-01-20"))
    np.testing.assert_array_equal(terms.period_end, dates("2027-02-10"))
    assert terms.component_quantity.tolist() == [1_000.0]  # the window's total
    rb, wti = batch.encoded.legs
    # Each leg its own pricing days of the window: 16 and 15, the last the 10th and the 9th.
    assert (rb.slot_date.size, wti.slot_date.size) == (16, 15)
    assert (rb.slot_date[-1], wti.slot_date[-1]) == (day("2027-02-10"), day("2027-02-09"))
    assert day("2027-02-10") not in wti.slot_date
    close(rb.slot_exposure, [42_000.0 / 16] * 16)
    close(wti.slot_exposure, [-1_000.0 / 15] * 15)
    assert batch.encoded.offset.tolist() == [-15_000.0]  # one spread leg for the window
    assert batch.encoded.group_head.size == 1  # and one payment
    results = valued(batch, QUOTES)
    first, second = results.legs
    close(first.dated_live_contribution.sum(keepdims=True), [RB_SIDE])
    close(second.dated_live_contribution.sum(keepdims=True), [WTI_SIDE])
    near(results.payment_amount, [PAYMENT])
    close(results.payment_factor, [0.95])
    assert results.mark == pytest.approx(0.95 * PAYMENT, rel=1e-12)
    assert results.dv01 == pytest.approx(-0.95 * PAYMENT * 1e-4, rel=1e-12)
    assert results.cash == 0.0


def test_each_legs_delta_is_split_by_the_days_each_contract_prices() -> None:
    # One lot of RB, 42,000 gallons, six sixteenths on G27 and ten on H27; minus one lot of
    # WTI, six fifteenths on G27 and nine on H27. The roll is each leg's own calendar's.
    results = valued(a_window(), QUOTES)
    first, second = results.legs
    close(first.nominal_delta, [6 / 16, 10 / 16])
    close(second.nominal_delta, [-6 / 15, -9 / 15])
    assert first.nominal_delta_total == pytest.approx(1.0, **CLOSE)
    assert second.nominal_delta_total == pytest.approx(-1.0, **CLOSE)
    assert first.delta_total == pytest.approx(0.95, **CLOSE)
    assert second.delta_total == pytest.approx(-0.95, **CLOSE)


def test_the_readback_names_the_window_by_its_two_dates() -> None:
    table = grid(a_window())
    assert len(table) == 3  # one row for the window, whatever months it crosses
    assert cell(table, 0, "booked_period") == "2027-01-20 to 2027-02-10"
    assert cell(table, 0, "settlement_frequency") == "onetime"
    assert cell(table, 0, "schedule_method") == "asian"
    assert cell(table, 0, "second_schedule_method") == "asian"
    assert cell(table, 0, "covered_days") == 22.0
    assert cell(table, 0, "spread_price") == 15.0


def test_a_sold_window_reverses_the_payment_and_every_delta() -> None:
    sold = valued(a_window(ticket={**WINDOW, "quantity": [-1_000]}), QUOTES)
    near(sold.payment_amount, [-PAYMENT])
    assert [leg.nominal_delta_total for leg in sold.legs] == pytest.approx([-1.0, 1.0], **CLOSE)


def test_a_quantity_per_day_is_the_windows_calendar_days() -> None:
    # 100 barrels a calendar day over the window's 22 days is 2,200 barrels: 2.2 times the table.
    daily = a_window({**ONETIME, "quantity_per": "calday"}, {**WINDOW, "quantity": [100]})
    assert daily.resolved.component_quantity.tolist() == [2_200.0]
    near(valued(daily, QUOTES).payment_amount, [2.2 * PAYMENT])


# --- the payment ----------------------------------------------------------------------------------


def test_the_window_pays_once_counted_from_the_later_legs_last_pricing_day() -> None:
    # RB is last observed on Wednesday the 10th and WTI on the 9th: two business days after the
    # later, Friday 12 February.
    batch = a_window({**ONETIME, "payment_day": "+2bd"})
    assert batch.resolved.payment is not None
    np.testing.assert_array_equal(batch.resolved.payment.date, dates("2027-02-12"))
    assert batch.encoded.payment_date is not None
    np.testing.assert_array_equal(batch.encoded.payment_date, dates("2027-02-12"))
    # The other way round, WTI less RB, the second leg is the later: the same Friday.
    turned = booked({**ONETIME, "payment_day": "+2bd"}, WINDOW, (WTI, RB))
    assert turned.resolved.payment is not None
    np.testing.assert_array_equal(turned.resolved.payment.date, dates("2027-02-12"))
    # A stated date on or before that last day is refused, as for any row.
    assert refused({**ONETIME, "payment_day": day("2027-02-10")}, WINDOW, (RB, WTI)) == (
        "trade 1 at row 1 pays on 2027-02-10, expected a day after its last observation, "
        "2027-02-10, when its final price exists"
    )


# --- the lifecycle --------------------------------------------------------------------------------
# RB settles at 2.00 on every fixed day and 2.20 on G27's expiry; WTI at 68 and 72. The window
# pays on 12 February.


def at(as_of: str, batch: Trades) -> TradeResults:
    """The window valued on the day: each leg's history as above, H27 quoted 2.14 and 71."""
    rb, wti = batch.resolved.legs
    histories = [
        history_at(rb.index, as_of, 2.00, {"2027-01-27": 2.20}),
        history_at(wti.index, as_of, 68.0, {"2027-01-27": 72.0}),
    ]
    prepared = prepared_trades(batch.encoded, histories, WorkCounter())
    markets = [quoted(histories[0], 2.14), quoted(histories[1], 71.0)]
    curve = curve_of((as_of, 1.0), (PAY, 0.95))
    return trade_results(prepared, markets, WorkCounter(), curve_set(curve))


def test_the_window_part_fixed_on_1_february() -> None:
    # Eight days of each leg have fixed, the 20th to the 29th. RB: seven at 2.00 and the expiry
    # at 2.20, 16.20, and eight still to come at 2.14, 17.12: 33.32 over 16 days. WTI: seven at
    # 68 and 72, 548, and seven to come at 71, 497: 1,045 over 15 days.
    results = at("2027-02-01", a_window({**ONETIME, "payment_day": "+2bd"}))
    rb_side = 42_000 * (7 * 2.00 + 2.20 + 8 * 2.14) / 16
    wti_side = -1_000 * (7 * 68.0 + 72.0 + 7 * 71.0) / 15
    near(results.payment_amount, [rb_side + wti_side - 15_000.0])
    assert results.cash == 0.0
    first, second = results.legs
    # What is still live: eight sixteenths of a lot of RB, seven fifteenths of WTI.
    assert first.nominal_delta_total == pytest.approx(8 / 16, **CLOSE)
    assert second.nominal_delta_total == pytest.approx(-7 / 15, **CLOSE)


def test_the_window_paid_is_one_cash_amount() -> None:
    # Every day fixed and the payment day behind: RB averaged (15 x 2.00 + 2.20) / 16 and WTI
    # (14 x 68 + 72) / 15, one net amount of cash and nothing left to mark or to hedge.
    results = at("2027-02-16", a_window({**ONETIME, "payment_day": "+2bd"}))
    rb_side = 42_000 * (15 * 2.00 + 2.20) / 16
    wti_side = -1_000 * (14 * 68.0 + 72.0) / 15
    assert results.cash == pytest.approx(rb_side + wti_side - 15_000.0, rel=1e-12)
    assert results.mark == 0.0 and results.dv01 == 0.0
    assert [leg.nominal_delta_total for leg in results.legs] == [0.0, 0.0]


# --- beside months --------------------------------------------------------------------------------


def test_a_window_of_one_whole_month_is_the_months_own_average() -> None:
    # February booked as one window and as the month G27: the same days on each leg, so the same
    # payment and the same lots. H27 prices February to its expiry on the 24th and J27 after.
    monthly = {**ONETIME, "settlement_frequency": "monthly", "quantity_per": "month"}
    february: dict[str, list[object]] = {**TICKET, "contract_code": ["G27"]}
    as_window = valued(a_window(ONETIME, february), THREE)
    as_month = valued(a_window(monthly, february), THREE)
    near(as_window.payment_amount, [float(v) for v in as_month.payment_amount or ()])
    for mine, theirs in zip(as_window.legs, as_month.legs, strict=True):
        close(mine.nominal_delta, theirs.nominal_delta.tolist())


def test_a_window_and_a_month_in_one_batch_are_two_payments() -> None:
    # The window beside the month G27, February, each row its own frequency and basis: two
    # rows, two components and two groups, the window's amount the table's.
    template = {
        k: v for k, v in ONETIME.items() if k not in ("settlement_frequency", "quantity_per")
    }
    ticket: dict[str, list[object]] = {
        "trade_id": [1, 2],
        "trade_date": ["2026-12-15", "2026-12-15"],
        "contract_code": [None, "G27"],
        "start_date": ["2027-01-20", None],
        "end_date": ["2027-02-10", None],
        "quantity": [1_000, 1_000],
        "spread_price": [15.00, 15.00],
        "settlement_frequency": ["onetime", "monthly"],
        "quantity_per": ["period", "month"],
    }
    batch = a_window(template, ticket)
    assert batch.resolved.occurrence.tolist() == [0, 1]
    assert batch.encoded.group_head.size == 2
    results = valued(batch, THREE)
    assert results.payment_amount is not None and results.payment_amount.size == 2
    # The window opens first, so it is the first group.
    assert float(results.payment_amount[0]) == pytest.approx(PAYMENT, rel=1e-12, abs=1e-8)
    table = grid(batch)
    assert [cell(table, r, "booked_period") for r in (0, 1)] == ["2027-01-20 to 2027-02-10", "G27"]


# --- each leg's own schedule ----------------------------------------------------------------------


def test_a_window_is_found_on_each_legs_own_schedule() -> None:
    # A's F27 expires on 29 December and B's on 4 January. A window opening on 30 December is
    # priced first by G27 on A and by F27 on B: each leg's row is the contract pricing the
    # window's first day on its own schedule, and its days roll on its own expiries.
    ticket: dict[str, list[object]] = {
        **WINDOW,
        "start_date": ["2026-12-30"],
        "end_date": ["2027-01-15"],
    }
    batch = booked(ONETIME, ticket, (A_GAL, B_BBL))
    a, b = batch.resolved.legs
    assert (a.contract.tolist(), b.contract.tolist()) == ([3], [2])  # G27 on A, F27 on B
    on_a, on_b = batch.encoded.legs
    assert on_a.references.tolist() == [3]  # every day of A's is G27's
    assert on_b.references.tolist() == [2, 3]  # B's first three days are F27's
    # Twelve pricing days each, New Year's Day closed: B's 30th, 31st and 4th before its expiry.
    assert (on_a.slot_date.size, on_b.slot_date.size) == (12, 12)
    assert int((on_b.slot_reference == 2).sum()) == 3


# --- the rules ------------------------------------------------------------------------------------

AVERAGED = (
    "expected 'asian' under settlement_frequency = onetime; a onetime period averages every "
    "pricing day it covers, and the expiry-based methods take their contract's month"
)


def test_both_methods_are_asian_under_onetime() -> None:
    assert refused({**ONETIME, "schedule_method": "lastday"}, WINDOW, (RB, WTI)) == (
        f"schedule_method of trade 1 at row 1 is 'lastday', {AVERAGED}"
    )
    assert refused({**ONETIME, "second_schedule_method": "lastday"}, WINDOW, (RB, WTI)) == (
        f"second_schedule_method of trade 1 at row 1 is 'lastday', {AVERAGED}"
    )
    assert refused({**ONETIME, "second_schedule_method": "last3day"}, WINDOW, (RB, WTI)) == (
        f"second_schedule_method of trade 1 at row 1 is 'last3day', {AVERAGED}"
    )


def test_the_quantity_is_the_windows_or_a_days_and_never_a_months() -> None:
    assert refused({**ONETIME, "quantity_per": "month"}, WINDOW, (RB, WTI)) == (
        "quantity_per of trade 1 at row 1 is 'month', expected 'period' or 'calday' under "
        "settlement_frequency = onetime; month says nothing of a window, period is its total "
        "and calday its days"
    )
    monthly = {**ONETIME, "settlement_frequency": "monthly"}
    assert refused(monthly, {**TICKET, "contract_code": ["G27"]}, (RB, WTI)).startswith(
        "quantity_per of trade 1 at row 1 is 'period', expected 'month' or 'calday' under "
        "settlement_frequency = monthly"
    )


def test_a_window_past_a_legs_last_contract_is_refused_by_that_leg() -> None:
    # Both schedules end with J27, expiring 29 March: a window running to the 31st has days
    # nothing prices.
    late: dict[str, list[object]] = {
        **WINDOW,
        "start_date": ["2027-03-22"],
        "end_date": ["2027-03-31"],
    }
    assert refused(ONETIME, late, (RB, WTI)) == (
        "trade 1 at row 1 observes 2027-03-30, after the schedule's last expiry, 2027-03-29; "
        "nothing prices it"
    )


# --- on the sheet ---------------------------------------------------------------------------------

SHEET_VALUES: dict[str, object] = {
    "spread_price_currency_unit": "DOLLAR",
    "spread_price_quantity_unit": "BBL",
    "quantity_unit": "BBL",
    "quantity_per": "period",
    "settlement_frequency": "onetime",
    "nearby": 1.0,
    "schedule_method": "asian",
    "second_schedule_method": "asian",
    "route": "bilateral",
    "settlement_method": "financial",
    "counterparty": "ACME Trading",
    "discount_curve_key": "SOFR",
    "payment_day": serial(PAY),
}


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """The window on a sheet: RB in DOLLAR per GAL and WTI in DOLLAR per BBL over F27, G27 and
    H27, 1 January 2027 closed on both and 10 February on WTI alone; valued 4 January 2027, RB
    quoted 2.10 and 2.14 and WTI 70 and 71, SOFR at 0.95 a year on, when the template pays; and
    the ticket's one row, 1,000 BBL from 20 January to 10 February at 15.00."""
    headers = across(
        "name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"
    )
    schedule = SEAM["_CreateFuturesSchedule"](
        down("F27", "G27", "H27"),
        down(serial("2026-12-29"), serial("2027-01-27"), serial("2027-02-24")),
        bridge.MISSING,
    )
    date = SEAM["_CreateValuationDate"](serial(AS_OF), 0.5)
    open_days = SEAM["_CreateHolidayCalendar"](a_name(), serial("2027-01-01"))
    shut = SEAM["_CreateHolidayCalendar"](
        a_name(), down(serial("2027-01-01"), serial("2027-02-10"))
    )
    cells: dict[str, Any] = {"holidays": seam_key(open_days)}
    for key, name, unit, lot, settles, quotes, holidays in (
        ("rb", "RB", "GAL", 42000.0, (2.05, 2.04), QUOTES[0], open_days),
        ("wti", "WTI", "BBL", 1000.0, (70.50, 70.40), QUOTES[1], shut),
    ):
        made = SEAM["_CreateIndex"](
            name,
            f"Crack leg {name}, a futures index",
            schedule,
            SEAM["_CreateIndexConventions"]("DOLLAR", unit, "DOLLAR", "VOLUME", unit),
            SEAM["_CreateContractSpecifications"](
                headers,
                Cells.from_rows([["LOT", lot, unit, 0.0, 0.0], ["BBL", 1.0, "BBL", 0.0, 0.0]]),
            ),
            seam_key(holidays),
            "LOT",
            seam_calendars(),
        )
        history = SEAM["_CreateMarketHistory"](
            SEAM["_CreateCalendar"](date, made),
            SEAM["_CreateFuturesFixings"](
                down(serial("2026-12-31"), serial("2026-12-30")), down(*settles), made
            ),
        )
        cells[key] = made
        cells[f"hist_{key}"] = history
        cells[f"market_{key}"] = SEAM["_CreateMarket"](
            history, SEAM["_CreatePriceVector"](name, down(*quotes))
        )
    cells["curves"] = SEAM["_CollectDiscountCurves"](
        SEAM["_CreateDiscountCurve"](
            "SOFR",
            across("date", "discount_factor"),
            Cells.from_rows([[serial(AS_OF), 1.0], [serial(PAY), 0.95]]),
        )
    )
    cells["both"] = down(cells["rb"], cells["wti"])
    cells["headers"] = across(
        "trade_id", "trade_date", "start_date", "end_date", "quantity", "spread_price"
    )
    cells["row"] = across(
        1.0, serial("2026-12-15"), serial("2027-01-20"), serial("2027-02-10"), 1000.0, 15.00
    )
    return cells


def sheet_template(
    sheet: Mapping[str, Any],
    instrument: str = "float_float",
    fields: tuple[str, ...] = TEMPLATE_FIELDS,
    **changed: object,
) -> object:
    """The sheet's onetime template, a value changed or the fields another instrument's."""
    values = {**SHEET_VALUES, "payment_holiday_key": sheet["holidays"], **changed}
    return SEAM["_CreateTradeTemplate"](
        instrument, across(*fields), across(*(values[name] for name in fields))
    )


def test_the_sheet_books_prepares_and_values_a_window(sheet: dict[str, Any]) -> None:
    trades_ = SEAM["_CreateTrades"](
        sheet["both"], sheet["headers"], sheet["row"], sheet_template(sheet)
    )
    assert re.fullmatch(rf"{PID}:trades:RB-WTI:\d+", str(trades_)), trades_
    table = read(trades_)
    assert len(table) == 3  # one row for the window
    assert under(table, "booked_period") == ["2027-01-20 to 2027-02-10"]
    assert under(table, "settlement_frequency") == ["onetime"]
    assert under(table, "quantity_per") == ["period"]
    assert under(table, "start_date") == [serial("2027-01-20")]
    assert under(table, "end_date") == [serial("2027-02-10")]
    assert under(table, "covered_days") == [22.0]
    assert under(table, "component_quantity") == [1_000.0]
    assert under(table, "quote_quantity") == [42_000.0] and under(table, "offset") == [-15_000.0]
    prepared = SEAM["_PrepareTrades"](trades_, down(sheet["hist_rb"], sheet["hist_wti"]))
    slots = read(prepared)
    # Sixteen days of RB and fifteen of WTI, each its own contracts' and an equal share of a lot.
    assert under(slots, "index") == ["RB"] * 16 + ["WTI"] * 15
    assert (
        under(slots, "pricing_contract") == ["G27"] * 6 + ["H27"] * 10 + ["G27"] * 6 + ["H27"] * 9
    )
    assert under(slots, "observation_date")[15] == serial("2027-02-10")
    assert under(slots, "observation_date")[-1] == serial("2027-02-09")
    assert under(slots, "live_lots") == pytest.approx([1 / 16] * 16 + [-1 / 15] * 15, **CLOSE)
    results = SEAM["_EvaluateTrades"](
        prepared, across(sheet["market_rb"], sheet["market_wti"]), sheet["curves"]
    )
    assert re.fullmatch(rf"{PID}:trade_results:RB-WTI:\d+", str(results)), results
    values = spilled(SEAM["_ReportValues"](results))
    assert values[2][0] == pytest.approx(0.95 * PAYMENT, **CLOSE) and values[2][1] == 0.0
    priced = read(results)
    assert under(priced, "payment_amount")[0] == pytest.approx(PAYMENT, **CLOSE)
    contributions = [float(str(each)) for each in under(priced, "floating_contribution")]
    assert sum(contributions[:16]) == pytest.approx(RB_SIDE, **CLOSE)
    assert sum(contributions[16:]) == pytest.approx(WTI_SIDE, **CLOSE)
    # The lots by the month of the contract that prices them: February's G27 and March's H27.
    risk = spilled(SEAM["_ReportRisk"](results, "all", "month"))
    assert risk[3][0] == "Total"
    assert risk[3][1:] == pytest.approx(
        [1.0, 0.95, -1.0, -0.95, -0.95 * PAYMENT * 1e-4, -0.000095, 0.000095], **CLOSE
    )
    # The report runs a month a row to the payment's, January 2028.
    assert [line[0] for line in risk[5:7]] == [serial("2027-02-01"), serial("2027-03-01")]
    assert [line[1] for line in risk[5:7]] == pytest.approx([6 / 16, 10 / 16], **CLOSE)
    assert [line[3] for line in risk[5:7]] == pytest.approx([-6 / 15, -9 / 15], **CLOSE)
    assert all(line[1] == 0.0 and line[3] == 0.0 for line in risk[7:])


def test_the_sheet_books_a_quantity_a_calendar_day(sheet: dict[str, Any]) -> None:
    row = across(
        2.0, serial("2026-12-15"), serial("2027-01-20"), serial("2027-02-10"), 100.0, 15.00
    )
    table = read(
        SEAM["_CreateTrades"](
            sheet["both"], sheet["headers"], row, sheet_template(sheet, quantity_per="calday")
        )
    )
    assert under(table, "quantity") == [100.0] and under(table, "quantity_per") == ["calday"]
    assert under(table, "component_quantity") == [2_200.0]  # 22 calendar days
    assert under(table, "offset") == [-33_000.0]


def test_the_sheet_refuses_a_window_by_its_rule(sheet: dict[str, Any]) -> None:
    def create(template: object, headers: object = None) -> object:
        return SEAM["_CreateTrades"](
            sheet["both"], sheet["headers"] if headers is None else headers, sheet["row"], template
        )

    start = "#ERROR _CreateTrades: ValueError: "
    assert create(sheet_template(sheet, second_schedule_method="lastday")) == (
        f"{start}second_schedule_method of trade 1 at row 1 is 'lastday', {AVERAGED}"
    )
    assert create(sheet_template(sheet, schedule_method="last3day")) == (
        f"{start}schedule_method of trade 1 at row 1 is 'last3day', {AVERAGED}"
    )
    assert create(sheet_template(sheet, quantity_per="month")) == (
        f"{start}quantity_per of trade 1 at row 1 is 'month', expected 'period' or 'calday' "
        "under settlement_frequency = onetime; month says nothing of a window, period is its "
        "total and calday its days"
    )
    # The same two indexes and the same window under a fixed_float: a pair's window is not built.
    pair = sheet_template(sheet, "fixed_float", TEMPLATE_FIELDS[2:])
    priced = across("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price")
    assert create(pair, priced) == (
        f"{start}settlement_frequency of trade 1 at row 1 is 'onetime', expected 'monthly' with "
        "two indexes on a fixed_float; a onetime period on two indexes is built for a "
        "float_float alone"
    )
