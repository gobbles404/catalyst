"""The whole-period average, onetime-averaging.md's third slice: a financial fixed_float whose
asian average runs over one window of dates, across calendar months, as one component, one group,
one quantity and one payment; the ticket's WTI trade month and NG strip as acceptance, in the
library and through the seam; the combinations the kernel does not average refused by name ahead
of any observation rule."""

from typing import Any

import numpy as np
import pytest
from test_create_trades import (
    a_template,
    a_ticket,
    an_index,
    components_of,
    created,
    key_of,
    refused,
    the_calendars,
)
from test_quote import Settle, priced
from test_trade_valuation import ENTRY, row, rows, serial, spilled, templated, valued
from test_trade_valuation import a_history as seam_history
from test_trade_valuation import a_market as seam_market
from test_trade_valuation import an_index as seam_index
from test_trades import day

from catalyst.excel import bridge
from catalyst.globals.unit_conversions import UNITS
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades, trades
from catalyst.trades.results import TradeResults
from catalyst.trades.terms import FREQUENCIES, SettlementFrequency, booked_words

# --- the WTI trade month -------------------------------------------------------------------------
# CME rule 804101's window for July 2026: 26 May to 25 June, the first business day after the
# 25th two months before to the last on or before the 25th of the month before. A WTI-like index
# whose contracts expire the month before their own, July's N26 on 22 June, the market closed on
# Memorial Day, Juneteenth, 3 July and New Year's Day, a barrel the one specification and the lot
# reported, so that a delta reads in barrels. Synthetic expiries and prices, the ticket's.
CL_CONTRACTS = (
    ("K26", "2026-04-21"),
    ("M26", "2026-05-19"),
    ("N26", "2026-06-22"),
    ("Q26", "2026-07-21"),
    ("U26", "2026-08-20"),
    ("V26", "2026-09-22"),
    ("X26", "2026-10-20"),
    ("Z26", "2026-11-20"),
    ("F27", "2026-12-21"),
    ("G27", "2027-01-20"),
    ("H27", "2027-02-22"),
    ("J27", "2027-03-22"),
)
CL_HOLIDAYS = ("2026-05-25", "2026-06-19", "2026-07-03", "2027-01-01")
CL = an_index("CL", CL_CONTRACTS, CL_HOLIDAYS, (("BBL", 1.0, "BBL"),), ("VOLUME", "BBL"))
TMA_TEMPLATE: dict[str, object] = {
    "quantity_unit": "BBL",
    "quantity_per": "period",
    "settlement_frequency": "onetime",
    "nearby": 1.0,
    "schedule_method": "asian",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "CME Clearing",
    "payment_day": day("2026-06-29"),
    "payment_holiday_key": key_of(CL.holiday_calendar),
}
TMA_TICKET: dict[str, list[object]] = {
    "trade_id": [1],
    "trade_date": ["2026-05-15"],
    "start_date": ["2026-05-26"],
    "end_date": ["2026-06-25"],
    "quantity": [2_200.0],
    "fixed_price": [71.0],
}
MONTHLY: dict[str, object] = {"quantity_per": "month", "settlement_frequency": "monthly"}
WINDOW = "2026-05-26 to 2026-06-25"
# The window's 22 pricing days: four of May, N26's through its expiry on 22 June, Q26's after.
WINDOW_DAYS = [
    *("2026-05-26", "2026-05-27", "2026-05-28", "2026-05-29"),
    *("2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"),
    *("2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12"),
    *("2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-22"),
    *("2026-06-23", "2026-06-24", "2026-06-25"),
]
PROJECTED = (19 * 70.0 + 3 * 72.0) / 22  # 70.2727, N26 at 70 and Q26 at 72 before any day fixes


def valued_on(batch: Trades, as_of: str, settle: Settle, *quotes: float) -> TradeResults:
    """The batch valued that day: the index's history at one settle on every fixed day, or the
    settle a function gives each day, and the quotes from the prompt contract on, prepared and
    evaluated on fresh counters."""
    market = priced(batch.resolved.legs[0].index, as_of, settle, *quotes)
    prepared = prepared_trades(batch.encoded, (market.market_history,), WorkCounter())
    return trade_results(prepared, (market,), WorkCounter())


def deltas(results: TradeResults) -> dict[str, float]:
    """The nominal delta by contract code, in the reporting lot, a barrel here."""
    leg = results.legs[0]
    return dict(zip(leg.codes(), leg.nominal_delta.tolist(), strict=True))


def labels(batch: Trades) -> list[str]:
    """Each component's booked period in words, as the readbacks give it."""
    terms = batch.resolved
    return list(booked_words(terms, terms.legs[0], np.arange(terms.occurrence.size, dtype=np.intp)))


def codes_of(batch: Trades, rows_: Any) -> list[str]:
    return [batch.resolved.legs[0].schedule.codes[int(r)] for r in rows_]


def test_the_wti_trade_month_is_one_average_one_quantity_and_one_payment() -> None:
    # The ticket's acceptance case: 2,200 barrels receiving the average of 26 May to 25 June
    # against 71, paid 29 June. One component over the 31 calendar days, its period the window,
    # its contract N26, the one pricing its first day, read for nothing that prices; 22
    # observations of 1/22, 100 barrels a day, N26 pricing nineteen and Q26 three; one group,
    # labelled by the two dates, with the one fixed leg of -156,200; before any day fixes, with
    # N26 at 70 and Q26 at
    # 72, the average 70.2727, the mark -1,600 and the delta 1,900 barrels to N26 and 300 to Q26.
    batch, counter = created(CL, TMA_TICKET, TMA_TEMPLATE)
    terms, enc = batch.resolved, batch.encoded
    leg = enc.legs[0]
    assert components_of(batch) == (["N26"], ["2026-05-26"], ["2026-06-25"], [31], [2_200.0])
    assert [str(d) for d in terms.period_start] == ["2026-05-26"]
    assert [str(d) for d in terms.period_end] == ["2026-06-25"]
    np.testing.assert_array_equal(
        terms.settlement_frequency, [FREQUENCIES.index(SettlementFrequency.ONETIME)]
    )
    assert labels(batch) == [WINDOW]
    assert [str(d) for d in leg.observations.date] == WINDOW_DAYS
    np.testing.assert_allclose(leg.observations.weight, np.full(22, 1 / 22))
    np.testing.assert_array_equal(leg.observations.component, np.zeros(22, dtype=np.intp))
    assert codes_of(batch, leg.slot_reference) == ["N26"] * 19 + ["Q26"] * 3
    np.testing.assert_allclose(leg.slot_exposure, np.full(22, 100.0))
    assert enc.group_head.tolist() == [0] and codes_of(batch, leg.group_contract) == ["N26"]
    np.testing.assert_allclose(enc.offset_of_group, [-156_200.0])
    assert terms.payment is not None
    assert [str(d) for d in terms.payment.date] == ["2026-06-29"]
    results = valued_on(batch, "2026-05-20", 70.0, 70.0, 72.0, 74.0)
    assert results.mark == pytest.approx(2_200 * (PROJECTED - 71)) == pytest.approx(-1_600.0)
    assert results.cash == 0.0
    assert deltas(results) == pytest.approx({"N26": 1_900.0, "Q26": 300.0})
    # The ticket's work table: one component, one group, 22 observations and slots, two pricing
    # references and one fee component, where the month-split booking had two of each but the
    # observations.
    counts = counter.freeze()
    assert counts["resolved_occurrences"] == 1 and counts["resolved_components"] == 1
    assert counts["encoded_components"] == 1 and counts["encoded_groups"] == 1
    assert counts["encoded_observations"] == 22 and counts["encoded_slots"] == 22
    assert leg.references.size == 2 and counts["reserved_fee_components"] == 1


def test_a_thousand_barrels_books_directly_and_the_window_equals_the_monthly_workaround() -> None:
    # 1,000 barrels over the window as one row, no fractional pieces: -727.27 of mark, 863.64 and
    # 136.36 of delta. And the 2,200-barrel window equals the desk's workaround, 400 barrels of
    # May and 1,800 of June as two monthly rows paying the same day, 4/22 and 18/22 of the
    # window: the same days, exposures, mark and delta, the workaround two components and two
    # groups where the window is one.
    thousand, _ = created(CL, {**TMA_TICKET, "quantity": [1_000.0]}, TMA_TEMPLATE)
    results = valued_on(thousand, "2026-05-20", 70.0, 70.0, 72.0, 74.0)
    assert results.mark == pytest.approx(-1_600 / 2.2)
    assert deltas(results) == pytest.approx({"N26": 1_900 / 2.2, "Q26": 300 / 2.2})
    window, _ = created(CL, TMA_TICKET, TMA_TEMPLATE)
    pieces, _ = created(
        CL,
        {
            "trade_id": [1, 2],
            "trade_date": ["2026-05-15"] * 2,
            "start_date": ["2026-05-26", "2026-06-01"],
            "end_date": ["2026-05-31", "2026-06-25"],
            "quantity": [400.0, 1_800.0],
            "fixed_price": [71.0, 71.0],
        },
        {**TMA_TEMPLATE, **MONTHLY},
    )
    one = valued_on(window, "2026-05-20", 70.0, 70.0, 72.0, 74.0)
    two = valued_on(pieces, "2026-05-20", 70.0, 70.0, 72.0, 74.0)
    assert one.mark == pytest.approx(two.mark) == pytest.approx(-1_600.0)
    assert deltas(one) == pytest.approx(deltas(two))
    np.testing.assert_array_equal(
        window.encoded.legs[0].slot_date, pieces.encoded.legs[0].slot_date
    )
    np.testing.assert_allclose(
        window.encoded.legs[0].slot_exposure, pieces.encoded.legs[0].slot_exposure
    )
    assert window.resolved.occurrence.size == 1 and pieces.resolved.occurrence.size == 2
    assert window.encoded.group_head.size == 1 and pieces.encoded.group_head.size == 2
    assert labels(pieces) == ["K26", "M26"]


def test_a_window_needs_no_contract_for_the_month_it_opens_in() -> None:
    # The review's first case on the third slice: the WTI window on a schedule without K26, the
    # contract of the month it opens in, books and prices as on the full schedule, since its
    # days price off N26 and Q26 alone; its contract is N26, the one pricing its first day, read
    # for nothing that prices. A window opening after the last day the schedule's contracts
    # price is refused by its row.
    without_k26 = an_index(
        "CL", CL_CONTRACTS[1:], CL_HOLIDAYS, (("BBL", 1.0, "BBL"),), ("VOLUME", "BBL")
    )
    batch, _ = created(without_k26, TMA_TICKET, TMA_TEMPLATE)
    full, _ = created(CL, TMA_TICKET, TMA_TEMPLATE)
    assert components_of(batch) == (["N26"], ["2026-05-26"], ["2026-06-25"], [31], [2_200.0])
    assert labels(batch) == [WINDOW]
    for name in ("slot_date", "slot_exposure"):
        np.testing.assert_array_equal(
            getattr(batch.encoded.legs[0], name), getattr(full.encoded.legs[0], name)
        )
    np.testing.assert_array_equal(batch.encoded.offset_of_group, full.encoded.offset_of_group)
    assert codes_of(batch, batch.encoded.legs[0].slot_reference) == ["N26"] * 19 + ["Q26"] * 3
    results = valued_on(batch, "2026-05-20", 70.0, 70.0, 72.0, 74.0)
    assert results.mark == pytest.approx(-1_600.0)
    assert deltas(results) == pytest.approx({"N26": 1_900.0, "Q26": 300.0})
    assert refused(
        CL,
        {**TMA_TICKET, "start_date": ["2027-04-01"], "end_date": ["2027-04-30"]},
        {**TMA_TEMPLATE, "payment_day": "+2bd"},
    ) == (
        "start_date row 1 is 2027-04-01 and end_date row 1 2027-04-30, expected a window priced "
        "by the contracts of the index's schedule; it opens on 2027-04-01, after the last day they "
        "price, 2027-03-22"
    )


def test_a_month_and_a_window_over_the_same_days_are_two_groups_whatever_the_row_order() -> None:
    # The review's second case: a monthly row of 1 to 15 June, whose period is June, and a
    # onetime row of 1 to 30 June, whose period is the same two days, both paying 2 July, are two
    # groups, a month and a window being periods of different kinds, so that every slot carries
    # its own row's label, `M26` on the month's eleven days and the two dates on the window's
    # twenty-one, in either row order, the groups the month's first; the mark is the same either
    # way.
    template: dict[str, object] = {
        **{
            name: value
            for name, value in TMA_TEMPLATE.items()
            if name not in ("quantity_per", "settlement_frequency")
        },
        "payment_day": day("2026-07-02"),
    }
    rows: dict[str, list[object]] = {
        "trade_id": [1, 2],
        "trade_date": ["2026-05-15", "2026-05-15"],
        "start_date": ["2026-06-01", "2026-06-01"],
        "end_date": ["2026-06-15", "2026-06-30"],
        "quantity": [1_100.0, 2_100.0],
        "fixed_price": [71.0, 71.0],
        "quantity_per": ["month", "period"],
        "settlement_frequency": ["monthly", "onetime"],
    }
    june = "2026-06-01 to 2026-06-30"
    month_days = [f"2026-06-{d:02d}" for d in (1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 15)]
    window_days = month_days + [
        f"2026-06-{d:02d}" for d in (16, 17, 18, 22, 23, 24, 25, 26, 29, 30)
    ]
    expected = sorted([(d, "M26") for d in month_days] + [(d, june) for d in window_days])
    marks: list[float] = []
    for order in ((0, 1), (1, 0)):
        picked = {name: [values[i] for i in order] for name, values in rows.items()}
        batch, _ = created(CL, picked, template)
        terms, leg = batch.resolved, batch.encoded.legs[0]
        assert terms.occurrence.size == 2 and batch.encoded.group_head.size == 2
        group_labels = booked_words(terms, terms.legs[0], batch.encoded.group_head)
        assert list(group_labels) == ["M26", june]
        slot_labels = group_labels[leg.slot_group]
        assert sorted(zip([str(d) for d in leg.slot_date], slot_labels, strict=True)) == expected
        marks.append(valued_on(batch, "2026-05-20", 70.0, 70.0, 72.0, 74.0).mark)
    assert marks[0] == pytest.approx(marks[1])


def test_calday_multiplies_the_daily_quantity_by_the_windows_calendar_days() -> None:
    # 100 barrels a day over the 31 calendar days of 26 May to 25 June, weekends and holidays
    # included, is 3,100 barrels for the one period, as 3,100 entered under period is; the fixing
    # weights stay 1/22 and the mark is 3,100 times the average less 71.
    by_day, _ = created(
        CL, {**TMA_TICKET, "quantity": [100.0]}, {**TMA_TEMPLATE, "quantity_per": "calday"}
    )
    total, _ = created(CL, {**TMA_TICKET, "quantity": [3_100.0]}, TMA_TEMPLATE)
    assert components_of(by_day) == (["N26"], ["2026-05-26"], ["2026-06-25"], [31], [3_100.0])
    assert components_of(by_day) == components_of(total)
    np.testing.assert_allclose(by_day.encoded.legs[0].observations.weight, np.full(22, 1 / 22))
    np.testing.assert_allclose(
        by_day.encoded.legs[0].slot_exposure, total.encoded.legs[0].slot_exposure
    )
    first = valued_on(by_day, "2026-05-20", 70.0, 70.0, 72.0, 74.0)
    second = valued_on(total, "2026-05-20", 70.0, 70.0, 72.0, 74.0)
    assert first.mark == pytest.approx(second.mark) == pytest.approx(3_100 * (PROJECTED - 71))


def test_within_one_calendar_month_onetime_and_monthly_agree_to_the_slot() -> None:
    # 1 to 25 June under onetime with 1,800 for the period and under monthly with 1,800 for the
    # month: the same 18 days, references, exposures, fixed leg, mark and delta, part fixed on 10
    # June; the labels differ, the window's two dates against the month's M26.
    june: dict[str, list[object]] = {
        **TMA_TICKET,
        "start_date": ["2026-06-01"],
        "quantity": [1_800.0],
    }
    window, _ = created(CL, june, TMA_TEMPLATE)
    month, _ = created(CL, june, {**TMA_TEMPLATE, **MONTHLY})
    for name in ("slot_date", "slot_reference", "slot_exposure"):
        np.testing.assert_array_equal(
            getattr(window.encoded.legs[0], name), getattr(month.encoded.legs[0], name)
        )
    # The fixed leg is the trade's since two-index-one-price.md, one per group.
    np.testing.assert_array_equal(window.encoded.offset_of_group, month.encoded.offset_of_group)
    assert window.encoded.legs[0].slot_date.size == 18
    assert labels(window) == ["2026-06-01 to 2026-06-25"] and labels(month) == ["M26"]
    one = valued_on(window, "2026-06-10", 69.0, 70.0, 72.0, 74.0)
    two = valued_on(month, "2026-06-10", 69.0, 70.0, 72.0, 74.0)
    assert one.mark == pytest.approx(two.mark)
    assert deltas(one) == pytest.approx(deltas(two))


def test_the_window_fixes_day_by_day_keeps_its_weights_and_pays_once() -> None:
    # 10 June, eleven days fixed at 69 and eleven live, eight of N26's and three of Q26's, N26 at
    # 70 and Q26 at 72: the average 69.7727 and the mark -2,700, the delta 800 to N26 and 300 to
    # Q26, the weights 1/22 as booked and never renormalized. 26 June, every day fixed at 69 and
    # unpaid: -4,400 of mark, nothing live. 30 June, the day after it paid: -4,400 of cash.
    batch, _ = created(CL, TMA_TICKET, TMA_TEMPLATE)
    partly = valued_on(batch, "2026-06-10", 69.0, 70.0, 72.0, 74.0)
    assert partly.prepared.legs[0].is_fixed.tolist() == [True] * 11 + [False] * 11
    average = (11 * 69.0 + 8 * 70.0 + 3 * 72.0) / 22
    assert partly.mark == pytest.approx(2_200 * (average - 71)) == pytest.approx(-2_700.0)
    assert partly.cash == 0.0
    assert deltas(partly) == pytest.approx({"N26": 800.0, "Q26": 300.0})
    fixed = valued_on(batch, "2026-06-26", 69.0, 72.0, 74.0)
    assert fixed.prepared.legs[0].is_fixed.all()
    assert fixed.mark == pytest.approx(-4_400.0) and fixed.cash == 0.0
    assert fixed.legs[0].nominal_delta_total == pytest.approx(0.0)
    paid = valued_on(batch, "2026-06-30", 69.0, 72.0, 74.0)
    assert paid.mark == pytest.approx(0.0) and paid.cash == pytest.approx(-4_400.0)


def test_a_window_whose_month_fragment_has_no_pricing_day_is_one_period_or_refused_by_name() -> (
    None
):
    # The review's case on the second slice: Saturday 30 January to Wednesday 10 February 2027,
    # the January fragment a weekend. Under onetime it is one period of eight pricing days, 1/8
    # each and H27's all, 1,200 barrels from 100 a day over twelve calendar days, paying two
    # business days after the 10th; a lastday row under onetime is refused by its method before
    # any period is built or observed, and the monthly twin under asian by its January fragment,
    # in the observation's words, since that fragment is a period of its own.
    ticket: dict[str, list[object]] = {
        **TMA_TICKET,
        "trade_date": ["2027-01-15"],
        "start_date": ["2027-01-30"],
        "end_date": ["2027-02-10"],
        "quantity": [100.0],
    }
    template: dict[str, object] = {**TMA_TEMPLATE, "quantity_per": "calday", "payment_day": "+2bd"}
    batch, _ = created(CL, ticket, template)
    assert components_of(batch) == (["H27"], ["2027-01-30"], ["2027-02-10"], [12], [1_200.0])
    leg = batch.encoded.legs[0]
    assert [str(d) for d in leg.observations.date] == [
        *("2027-02-01", "2027-02-02", "2027-02-03", "2027-02-04", "2027-02-05"),
        *("2027-02-08", "2027-02-09", "2027-02-10"),
    ]
    np.testing.assert_allclose(leg.observations.weight, np.full(8, 1 / 8))
    assert codes_of(batch, leg.slot_reference) == ["H27"] * 8
    assert labels(batch) == ["2027-01-30 to 2027-02-10"]
    assert batch.resolved.payment is not None
    assert [str(d) for d in batch.resolved.payment.date] == ["2027-02-12"]
    assert refused(CL, ticket, {**template, "schedule_method": "lastday"}) == (
        "schedule_method of trade 1 at row 1 is 'lastday', expected 'asian' under "
        "settlement_frequency = onetime; a onetime period averages every pricing day it covers, "
        "and the expiry-based methods take their contract's month"
    )
    assert refused(CL, ticket, {**template, "settlement_frequency": "monthly"}) == (
        "F27 of trade 1 at row 1 has no pricing day from 2027-01-30 to 2027-01-31, expected a "
        "Monday to Friday of the days it covers the index's market is open on; the asian method "
        "averages the pricing days a component covers"
    )


def test_the_combinations_the_kernel_does_not_average_are_refused_by_name() -> None:
    # Through the resolution, each in the kernel's words at the row that chose it: a physical
    # settlement, a quantity per month under onetime, a quantity per period under monthly, and a
    # payment on the window's last observation, the row's own day refused by its row; the
    # encoding's refusal of a group names it by its two dates, in test_trades.
    unpaid = {name: value for name, value in TMA_TEMPLATE.items() if not name.startswith("payment")}
    assert refused(CL, TMA_TICKET, {**unpaid, "settlement_method": "physical"}) == (
        "settlement_method is 'physical', expected 'financial' with settlement_frequency = "
        "onetime of trade 1 at row 1; a onetime period is cash settled on its average"
    )
    assert refused(CL, TMA_TICKET, {**TMA_TEMPLATE, "quantity_per": "month"}) == (
        "quantity_per of trade 1 at row 1 is 'month', expected 'period' or 'calday' under "
        "settlement_frequency = onetime; month says nothing of a window, period is its total and "
        "calday its days"
    )
    assert refused(CL, TMA_TICKET, {**TMA_TEMPLATE, "settlement_frequency": "monthly"}) == (
        "quantity_per of trade 1 at row 1 is 'period', expected 'month' or 'calday' under "
        "settlement_frequency = monthly; period is the total of a onetime period and says "
        "nothing of a month"
    )
    assert refused(CL, TMA_TICKET, {**TMA_TEMPLATE, "payment_day": day("2026-06-25")}) == (
        "trade 1 at row 1 pays on 2026-06-25, expected a day after its last observation, "
        "2026-06-25, when its final price exists"
    )
    # A rule counts from the window's final observation: +2bd from Thursday 25 June is Monday
    # the 29th, the ticket's payment day.
    ruled, _ = created(CL, TMA_TICKET, {**TMA_TEMPLATE, "payment_day": "+2bd"})
    assert ruled.resolved.payment is not None
    assert [str(d) for d in ruled.resolved.payment.date] == ["2026-06-29"]


# --- the NG strip: two meanings of settling once ------------------------------------------------
# A Henry Hub-like index, the MMBtu its specification so the ticket's quantities enter as written,
# each contract expiring three business days before its month, the market closed on Thanksgiving,
# Christmas and New Year's Day.
NG = an_index(
    "NG",
    (
        ("X26", "2026-10-28"),
        ("Z26", "2026-11-25"),
        ("F27", "2026-12-29"),
        ("G27", "2027-01-27"),
        ("H27", "2027-02-24"),
        ("J27", "2027-03-29"),
        ("K27", "2027-04-28"),
    ),
    ("2026-11-26", "2026-12-25", "2027-01-01"),
    (("MMBTU", 1.0, "MMBTU"),),
)
STRIP_TEMPLATE: dict[str, object] = {
    "quantity_unit": "MMBTU",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "CME Clearing",
    "payment_day": day("2027-04-07"),
    "payment_holiday_key": key_of(NG.holiday_calendar),
}
STRIP_FINALS = {day("2026-12-29"): 3.0, day("2027-01-27"): 5.0, day("2027-02-24"): 4.0}


def strip_final(d: np.datetime64) -> float:
    """Each month's final settlement on its contract's expiry day, 3 on every other day."""
    return STRIP_FINALS.get(d, 3.0)


def test_the_ng_strip_paid_once_keeps_each_months_fixing_and_quantity() -> None:
    # The ticket's regression: January 10,000, February 20,000 and March 10,000 MMBtu against
    # 3.5, each month's final settlement its own, 3, 5 and 4, every amount paid 7 April 2027:
    # -5,000, 30,000 and 5,000, 30,000 in all, the quantity-weighted reference 4.25 and not the
    # equal-month mean of 4; three groups, each reading the one payment day, never one average.
    batch, _ = created(
        NG,
        {
            "trade_id": [1, 2, 3],
            "trade_date": ["2026-12-01"] * 3,
            "contract_code": ["F27", "G27", "H27"],
            "quantity": [10_000.0, 20_000.0, 10_000.0],
            "fixed_price": [3.5, 3.5, 3.5],
        },
        STRIP_TEMPLATE,
    )
    assert labels(batch) == ["F27", "G27", "H27"]
    assert batch.encoded.group_head.size == 3 and batch.resolved.payment is not None
    assert [str(d) for d in batch.resolved.payment.date] == ["2027-04-07"] * 3
    unpaid = valued_on(batch, "2027-04-01", strip_final, 4.5)
    assert unpaid.mark == pytest.approx(30_000.0) and unpaid.cash == 0.0
    amounts = (
        unpaid.prepared.legs[0].set_amount + batch.encoded.offset_of_group
    )  # set and fixed leg
    assert amounts.tolist() == pytest.approx([-5_000.0, 30_000.0, 5_000.0])
    paid = valued_on(batch, "2027-04-08", strip_final, 4.5)
    assert paid.mark == pytest.approx(0.0) and paid.cash == pytest.approx(30_000.0)
    quantities, finals = np.array([10_000.0, 20_000.0, 10_000.0]), np.array([3.0, 5.0, 4.0])
    assert float(quantities @ finals / quantities.sum()) == pytest.approx(4.25)
    assert unpaid.mark == pytest.approx(float(quantities @ (finals - 3.5)))
    assert unpaid.mark != pytest.approx(float(quantities.sum() * (finals.mean() - 3.5)))


def test_an_ng_average_over_the_whole_strip_is_another_contract_and_books_as_onetime() -> None:
    # 30,000 MMBtu receiving the average of every pricing day from 1 January to 31 March 2027,
    # one onetime period over the three months, paid 7 April: 63 observations of 1/63, G27
    # pricing 18 through its expiry on 27 January, H27 20, J27 23 and K27 the last two; on
    # 1 December, G27 at 3, H27 at 5, J27 at 4 and K27 at 4.5, the average 4.0476 and the mark
    # 16,428.57, neither the strip's 30,000 nor an equal-month mean's 15,000.
    batch, _ = created(
        NG,
        {
            "trade_id": [1],
            "trade_date": ["2026-12-01"],
            "start_date": ["2027-01-01"],
            "end_date": ["2027-03-31"],
            "quantity": [30_000.0],
            "fixed_price": [3.5],
        },
        {
            **STRIP_TEMPLATE,
            "quantity_per": "period",
            "settlement_frequency": "onetime",
            "nearby": 1.0,
            "schedule_method": "asian",
        },
    )
    leg = batch.encoded.legs[0]
    assert components_of(batch) == (["G27"], ["2027-01-01"], ["2027-03-31"], [90], [30_000.0])
    assert labels(batch) == ["2027-01-01 to 2027-03-31"]
    assert leg.observations.date.size == 63
    np.testing.assert_allclose(leg.observations.weight, np.full(63, 1 / 63))
    assert codes_of(batch, leg.slot_reference) == (
        ["G27"] * 18 + ["H27"] * 20 + ["J27"] * 23 + ["K27"] * 2
    )
    results = valued_on(batch, "2026-12-01", 3.0, 3.0, 3.0, 5.0, 4.0, 4.5)
    average = (18 * 3.0 + 20 * 5.0 + 23 * 4.0 + 2 * 4.5) / 63
    assert results.mark == pytest.approx(30_000 * (average - 3.5)) == pytest.approx(16_428.5714)
    assert deltas(results) == pytest.approx(
        {code: 30_000 * n / 63 for code, n in (("G27", 18), ("H27", 20), ("J27", 23), ("K27", 2))}
    )


# --- through the seam ---------------------------------------------------------------------------


def test_the_window_crosses_the_seam_and_reads_back_its_dates_as_the_booked_period() -> None:
    # _CreateTrades with a onetime template: the trades readback shows the two dates under
    # booked_period, the frequency and the basis as entered, the window's days and the one
    # quantity; the preparation's and the results' slots carry the same label on every row;
    # _ReportValues spills the ticket's -1,600; a calday row reads back its daily quantity and
    # the period's total apart; and a lastday row under onetime is refused in the kernel's words.
    index, calendar = seam_index(
        "CL",
        list(CL_CONTRACTS),
        list(CL_HOLIDAYS),
        [("BBL", 1.0)],
        ("VOLUME", "BBL"),
    )
    fields = {
        "quantity_unit": "BBL",
        "quantity_per": "period",
        "settlement_frequency": "onetime",
        "nearby": 1.0,
        "schedule_method": "asian",
        "route": "cleared",
        "settlement_method": "financial",
        "clearing_house": "CME Clearing",
        "payment_day": serial("2026-06-29"),
        "payment_holiday_key": calendar,
    }
    headers = row("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price")
    booking = [1.0, serial("2026-05-15"), serial("2026-05-26"), serial("2026-06-25")]
    made = ENTRY["_CreateTrades"](
        index, headers, rows([*booking, 2_200.0, 71.0]), templated([*fields], [*fields.values()])
    )
    assert ":trades:CL:" in str(made), made
    table = spilled(ENTRY["util_ReadHandle"](made))
    line = dict(zip(table[0], table[2], strict=True))
    assert len(table) == 3 and line["booked_period"] == WINDOW
    assert (line["settlement_frequency"], line["quantity_per"]) == ("onetime", "period")
    assert (line["start_date"], line["end_date"]) == (serial("2026-05-26"), serial("2026-06-25"))
    assert (line["covered_days"], line["quantity"], line["component_quantity"]) == (
        31,
        2_200.0,
        2_200.0,
    )
    assert line["payment_date"] == serial("2026-06-29")
    assert line["entered_contract_code"] == "(not supplied)"
    history = seam_history(index, "2026-04-22", "2026-05-20", list(CL_HOLIDAYS), {})
    market = seam_market(history, "CL", 70.0, 72.0, 74.0)
    prepared = ENTRY["_PrepareTrades"](made, history)
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert slots[0][:4] == ["pricing_contract", "booked_period", "observation_date", "payment_date"]
    assert [slot[0] for slot in slots[2:]] == ["N26"] * 19 + ["Q26"] * 3
    assert {slot[1] for slot in slots[2:]} == {WINDOW}
    assert [slot[2] for slot in slots[2:]] == [serial(d) for d in WINDOW_DAYS]
    assert {slot[3] for slot in slots[2:]} == {serial("2026-06-29")}
    results = ENTRY["_EvaluateTrades"](prepared, market, bridge.MISSING)
    assert valued(str(results)) == (pytest.approx(-1_600.0), 0.0, pytest.approx(2_200.0))
    shown = spilled(ENTRY["util_ReadHandle"](results))
    assert {line[shown[0].index("booked_period")] for line in shown[2:]} == {WINDOW}
    by_day = ENTRY["_CreateTrades"](
        index,
        headers,
        rows([*booking, 100.0, 71.0]),
        templated([*fields], [*{**fields, "quantity_per": "calday"}.values()]),
    )
    daily = dict(zip(table[0], spilled(ENTRY["util_ReadHandle"](by_day))[2], strict=True))
    assert (daily["quantity"], daily["quantity_per"], daily["component_quantity"]) == (
        100.0,
        "calday",
        3_100.0,
    )
    assert str(
        ENTRY["_CreateTrades"](
            index,
            headers,
            rows([*booking, 2_200.0, 71.0]),
            templated([*fields], [*{**fields, "schedule_method": "lastday"}.values()]),
        )
    ) == (
        "#ERROR _CreateTrades: ValueError: schedule_method of trade 1 at row 1 is 'lastday', "
        "expected 'asian' under settlement_frequency = onetime; a onetime period averages every "
        "pricing day it covers, and the expiry-based methods take their contract's month"
    )


def test_the_library_builds_the_window_from_the_same_ticket_and_template_as_the_seam() -> None:
    # The resolution's own entry: the ticket and the template typed as the seam hands them over
    # give the terms the kernel tests supply, the one component's period the window.
    counter = WorkCounter()
    batch = trades(
        (CL,), a_ticket(TMA_TICKET), a_template(TMA_TEMPLATE), UNITS, counter, the_calendars()
    )
    assert labels(batch) == [WINDOW] and batch.encoded.group_head.tolist() == [0]
    assert counter.freeze()["encoded_groups"] == 1
