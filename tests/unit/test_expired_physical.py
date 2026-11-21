"""A closed physical contract past its expiry, as cash:
docs/engineering-tickets/trade-valuation-pipeline/expired-physical-cash.md. The page's hand-priced
lifecycle through the kernel and on the sheet, the positions that close and the ones that do not,
each quantity unit counted by itself, the one clearing house a physical batch names, the counts a
number cannot add exactly, refused, and the fees that stand as booked."""

import itertools
import re
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray

from catalyst.calendar.calendar import calendar
from catalyst.excel import bridge
from catalyst.excel.bridge import Cells
from catalyst.globals.unit_conversions import UNITS
from catalyst.globals.valuation_date import valuation_date
from catalyst.index_definitions.contract_codes import schedule_months
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import FuturesSchedule, futures_schedule
from catalyst.index_definitions.holiday_calendar import holiday_calendar
from catalyst.index_definitions.index import Index, index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.instruments.fields import DatesOrTexts
from catalyst.market.market import market
from catalyst.market.market_history import MarketHistory, market_history
from catalyst.market_data.futures_fixings import futures_fixings
from catalyst.market_data.price_vector import price_vector
from catalyst.trades.encoding import EXACT_COUNTS, Encoded, encoded, position_counts
from catalyst.trades.evaluation import trade_results
from catalyst.trades.observations import observed
from catalyst.trades.preparation import PreparedTrades, prepared_trades
from catalyst.trades.results import TradeResults
from catalyst.trades.schedule_methods import METHODS, ScheduleMethod
from catalyst.trades.terms import (
    BASES,
    FREQUENCIES,
    PaymentTerms,
    QuantityPer,
    ResolvedTrades,
    Route,
    Settlement,
    SettlementFrequency,
    month_bounds,
    one_choice,
    resolved_trades,
)

ENTRY = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}
FIRST = np.datetime64("1899-12-30", "D")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def numbers(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# --- the page's index -----------------------------------------------------------------------
# USD per MMBTU. Two quantity units: LOT, 10,000 MMBTU, charging 10.00 of brokerage and 4.00 of
# clearing a lot, and MMBTU, one, charging nothing. X26 bounds the calendar; Z26 expires on 18
# November 2026, F27 on 29 December and G27 on 27 January 2027; no pricing holiday.

CONTRACTS = (
    ("X26", "2026-10-28"),
    ("Z26", "2026-11-18"),
    ("F27", "2026-12-29"),
    ("G27", "2027-01-27"),
)
Z26, F27 = 1, 2  # rows of the schedule
LOT, MMBTU = 0, 1  # rows of the specifications
OPEN = "a physical position open past its expiry is a delivery, which is not modeled"


def an_index() -> Index:
    schedule = futures_schedule(
        tuple(code for code, _ in CONTRACTS), dates(*(expiry for _, expiry in CONTRACTS)), None
    )
    return index(
        "GAS",
        "GAS index",
        schedule,
        index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
        contract_specifications(
            ("LOT", "MMBTU"),
            numbers(10_000.0, 1.0),
            ("MMBTU", "MMBTU"),
            numbers(10.0, 0.0),
            numbers(4.0, 0.0),
            UNITS,
        ),
        holiday_calendar(dates()),
        "LOT",
        UNITS,
    )


GAS = an_index()
# One row of a ticket: the contract's schedule row, the quantity and the entry price, then the
# quantity unit's row and the basis where they are not a lot a month.
Row = tuple[int, float, float] | tuple[int, float, float, int] | tuple[int, float, float, int, str]
BUY: Row = (Z26, 1.0, 3.00)
SELL: Row = (Z26, -1.0, 3.10)


def terms_of(
    *rows: Row,
    houses: tuple[str, ...] | None = None,
    route: Route = Route.CLEARED,
    pays: str | None = None,
) -> ResolvedTrades:
    """The rows as a physical lastday batch on the page's index, each naming a broker; on the
    cleared route under one clearing house unless houses are given, and bilateral under SOFR;
    with a day to pay on, a financial batch paying every row on it."""
    count = len(rows)
    contract = np.array([row[0] for row in rows], dtype=np.intp)
    unit = np.array([row[3] if len(row) > 3 else LOT for row in rows], dtype=np.intp)
    basis = [QuantityPer(row[4]) if len(row) > 4 else QuantityPer.MONTH for row in rows]
    months = schedule_months(cast(FuturesSchedule, GAS.schedule))
    cleared = route is Route.CLEARED
    return resolved_trades(
        FIXED_FLOAT,
        GAS,
        unit,
        route,
        Settlement.PHYSICAL if pays is None else Settlement.FINANCIAL,
        one_choice(METHODS, ScheduleMethod.LASTDAY, count),
        np.array([BASES.index(each) for each in basis], dtype=np.intp),
        one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, count),
        np.ones(count, dtype=np.intp),
        np.arange(1001, 1001 + count, dtype=np.int64),
        (houses or ("CME Clearing",) * count) if cleared else None,
        ("ION",) * count,
        dates(*["2026-10-06"] * count),
        np.arange(count, dtype=np.intp),
        contract,
        numbers(*[row[1] for row in rows]),
        *month_bounds(months[contract]),
        numbers(*[row[2] for row in rows]),
        None
        if pays is None
        else PaymentTerms(
            DatesOrTexts.of_dates(dates(*[pays] * count)),
            (holiday_calendar(dates()),) * count,
            dates(*[pays] * count),
        ),
        counterparty=None if cleared else ("ACME",) * count,
        discount_curve_key=None if cleared else ("SOFR",) * count,
    )


def encoded_of(terms: ResolvedTrades) -> Encoded:
    leg = terms.legs[0]
    seen = observed(
        leg.schedule_method[terms.occurrence],
        leg.index,
        leg.contract,
        terms.start_date,
        terms.end_date,
        terms.named,
    )
    return encoded(terms, (seen,), UNITS, WorkCounter())


def history_on(as_of: str, finals: dict[str, float] | None = None) -> MarketHistory:
    """The index's history valued on that day: 3.00 on every fixed business day, the settles
    given standing on their contracts' expiry days."""
    cal = calendar(valuation_date(np.datetime64(as_of, "D"), 0.5), GAS)
    schedule = cast(FuturesSchedule, GAS.schedule)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = np.full(priced.size, 3.0)
    for code, price in (finals or {}).items():
        settles[priced == schedule.future_expiry[schedule.codes.index(code)]] = price
    return market_history(
        cal, futures_fixings(priced[::-1].copy(), settles[::-1, None].copy(), GAS)
    )


def prepared_on(enc: Encoded, as_of: str, finals: dict[str, float] | None = None) -> PreparedTrades:
    return prepared_trades(enc, (history_on(as_of, finals),), WorkCounter())


def valued(prep: PreparedTrades, *quotes: float) -> TradeResults:
    """The prepared batch evaluated at those quotes, the prompt contract's first."""
    history = prep.legs[0].history
    quoted = market(history, price_vector("GAS", numbers(*quotes)))
    return trade_results(prep, (quoted,), WorkCounter())


def refusal(enc: Encoded, as_of: str) -> str:
    with pytest.raises(ValueError) as refused:
        prepared_on(enc, as_of)
    return str(refused.value)


# --- the page's lifecycle -------------------------------------------------------------------


def test_a_closed_contract_is_mark_on_its_expiry_day_and_cash_from_the_day_after() -> None:
    enc = encoded_of(terms_of(BUY, SELL))
    assert enc.closed is not None and not enc.closed.flags.writeable
    np.testing.assert_array_equal(enc.closed, [True])
    np.testing.assert_array_equal(enc.offset, [-30_000.0, 31_000.0])
    # On the expiry day the contract is live: the locked-in 1,000 is the mark at any quote, the
    # position's two lots netting to no exposure and no delta.
    on_the_day = prepared_on(enc, "2026-11-18")
    np.testing.assert_array_equal(on_the_day.is_settled, [False])
    for quote in (3.00, 9.00):
        live = valued(on_the_day, quote, 3.50)
        assert (live.mark, live.cash) == (1_000.0, 0.0)
    assert on_the_day.legs[0].nominal_delta_total == 0.0
    # The day after, and any later day, it is cash: the fixed legs alone, whatever the expiry
    # settled at, with nothing left in the mark and nothing at risk.
    for as_of, settle in itertools.product(("2026-11-19", "2026-11-20"), (3.00, 9.00)):
        past = prepared_on(enc, as_of, {"Z26": settle})
        np.testing.assert_array_equal(past.is_settled, [True])
        np.testing.assert_array_equal(past.legs[0].is_fixed, [True])
        assert (past.cash, past.offset_unsettled, past.set_unsettled) == (1_000.0, 0.0, (0.0,))
        assert past.legs[0].nominal_delta_total == 0.0 and past.legs[0].live_slot.size == 0
        cash = valued(past, 3.50)
        assert (cash.mark, cash.cash) == (0.0, 1_000.0)
        assert not past.is_settled.flags.writeable


def test_the_fees_stand_as_booked_before_and_after_the_expiry() -> None:
    # Two lots traded through a broker on a cleared route: 20 of brokerage and 8 of clearing,
    # booked once when the batch is made, so that mark plus cash less the fees is 972 each day.
    enc = encoded_of(terms_of(BUY, SELL))
    assert (enc.reserves.brokerage, enc.reserves.clearing) == (20.0, 8.0)
    totals: list[float] = []
    for as_of, quotes in (("2026-11-18", (3.20, 3.50)), ("2026-11-19", (3.50,))):
        results = valued(prepared_on(enc, as_of), *quotes)
        assert results.reserves is enc.reserves
        fees = results.reserves.brokerage + results.reserves.clearing
        totals.append(results.mark + results.cash - fees)
    assert totals == [972.0, 972.0]


def test_a_loss_closes_to_a_loss() -> None:
    enc = encoded_of(terms_of((Z26, 1.0, 3.10), (Z26, -1.0, 3.00)))
    assert valued(prepared_on(enc, "2026-11-18"), 3.00, 3.50).mark == -1_000.0
    assert prepared_on(enc, "2026-11-19").cash == -1_000.0


def test_a_closed_contract_beside_a_live_one_moves_alone() -> None:
    # Z26 closed and F27 two lots bought at 3.40: on 19 November the cash is Z26's 1,000 and the
    # mark and the delta are F27's, 2,000 at 3.50 and two lots.
    enc = encoded_of(terms_of(BUY, SELL, (F27, 2.0, 3.40)))
    np.testing.assert_array_equal(enc.closed, [True, False])
    prep = prepared_on(enc, "2026-11-19")
    np.testing.assert_array_equal(prep.is_settled, [True, False])
    results = valued(prep, 3.50)
    assert (results.mark, results.cash) == (pytest.approx(2_000.0), 1_000.0)
    np.testing.assert_array_equal(prep.legs[0].nominal_delta, [0.0, 2.0])  # Z26, then F27
    # The live contract alone is the batch it was: the same mark and the same delta.
    alone = prepared_on(encoded_of(terms_of((F27, 2.0, 3.40))), "2026-11-19")
    assert valued(alone, 3.50).mark == results.mark
    np.testing.assert_array_equal(alone.legs[0].nominal_delta, [2.0])
    # A later expiry is judged on its own day: live on 29 December, a delivery the day after.
    np.testing.assert_array_equal(prepared_on(enc, "2026-12-29").is_settled, [True, False])
    assert refusal(enc, "2026-12-30") == (
        "F27 expired 2026-12-29, before valuation date 2026-12-30, with 2.0 of 'LOT' open, "
        f"trade 1003 at row 3 among them; {OPEN}"
    )
    # Closed in its turn, both are cash and nothing is live.
    both = encoded_of(terms_of(BUY, SELL, (F27, 2.0, 3.40), (F27, -2.0, 3.45)))
    past = prepared_on(both, "2026-12-30")
    np.testing.assert_array_equal(past.is_settled, [True, True])
    assert past.cash == pytest.approx(2_000.0) and valued(past, 3.60).mark == 0.0


# --- open positions -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rows", "left", "trade"),
    [
        ((BUY,), "1.0", "trade 1001 at row 1"),
        ((SELL,), "-1.0", "trade 1001 at row 1"),
        ((BUY, BUY, SELL), "1.0", "trade 1001 at row 1"),
        ((BUY, SELL, SELL), "-1.0", "trade 1001 at row 1"),
        (((Z26, 3.0, 3.00), (Z26, -2.0, 3.10)), "1.0", "trade 1001 at row 1"),
    ],
)
def test_a_count_left_past_the_expiry_is_refused_by_the_contract_and_the_count(
    rows: tuple[Row, ...], left: str, trade: str
) -> None:
    enc = encoded_of(terms_of(*rows))
    np.testing.assert_array_equal(enc.closed, [False])
    prepared_on(enc, "2026-11-18")  # live on its expiry day, as any contract
    assert refusal(enc, "2026-11-19") == (
        f"Z26 expired 2026-11-18, before valuation date 2026-11-19, with {left} of 'LOT' open, "
        f"{trade} among them; {OPEN}"
    )


def test_each_quantity_unit_is_counted_by_itself() -> None:
    # A lot bought and its 10,000 MMBTU sold in the smaller unit net to no exposure and are two
    # counts all the same: nothing is converted, and the first unit with a count left is named.
    enc = encoded_of(terms_of(BUY, (Z26, -10_000.0, 3.10, MMBTU)))
    left, _ = position_counts(enc.terms, enc.group_of_component, 1)
    np.testing.assert_array_equal(left, [[1, -10_000]])
    np.testing.assert_array_equal(enc.closed, [False])
    assert prepared_on(enc, "2026-11-18").legs[0].nominal_delta_total == 0.0
    assert refusal(enc, "2026-11-19") == (
        "Z26 expired 2026-11-18, before valuation date 2026-11-19, with 1.0 of 'LOT' open, "
        f"trade 1001 at row 1 among them; {OPEN}"
    )
    # The smaller unit alone, named as its own with the first trade entered in it.
    small = encoded_of(terms_of(BUY, SELL, (Z26, 5.0, 3.00, MMBTU)))
    assert refusal(small, "2026-11-19") == (
        "Z26 expired 2026-11-18, before valuation date 2026-11-19, with 5.0 of 'MMBTU' open, "
        f"trade 1003 at row 3 among them; {OPEN}"
    )
    # Closed in each unit by itself, it is closed.
    each = encoded_of(
        terms_of(BUY, SELL, (Z26, 5.0, 3.00, MMBTU), (Z26, -5.0, 3.20, MMBTU)),
    )
    np.testing.assert_array_equal(each.closed, [True])
    assert prepared_on(each, "2026-11-19").cash == pytest.approx(1_001.0)


def test_one_open_contract_fails_a_batch_whose_other_expired_contract_is_closed() -> None:
    enc = encoded_of(terms_of(BUY, SELL, (F27, 2.0, 3.40)))
    assert refusal(enc, "2027-01-04").startswith("F27 expired 2026-12-29, before valuation date")
    late = encoded_of(terms_of((Z26, 1.0, 3.00), (F27, 2.0, 3.40), (F27, -2.0, 3.45)))
    assert refusal(late, "2027-01-04").startswith("Z26 expired 2026-11-18, before valuation date")


# --- closed positions -----------------------------------------------------------------------

CLOSED: tuple[tuple[tuple[Row, ...], float], ...] = (
    ((BUY, SELL), 1_000.0),
    (((Z26, 2.0, 3.00), SELL, SELL), 2_000.0),
    ((BUY, SELL, BUY, SELL), 2_000.0),
    (((Z26, 3.0, 3.00), (Z26, -1.0, 3.10), (Z26, -2.0, 3.20)), 5_000.0),
    # 1 lot a day over December's 31 days against 31 lots a month: one count, two bases.
    (((Z26, 1.0, 3.00, LOT, "calday"), (Z26, -31.0, 3.10)), 31_000.0),
    (((Z26, 0.0, 3.00), (Z26, 0.0, 9.00)), 0.0),
)


@pytest.mark.parametrize(("rows", "cash"), CLOSED)
def test_a_position_that_adds_to_nothing_is_closed_whatever_the_rows_order(
    rows: tuple[Row, ...], cash: float
) -> None:
    for ordered in itertools.permutations(rows):
        enc = encoded_of(terms_of(*ordered))
        np.testing.assert_array_equal(enc.closed, [True])
        prep = prepared_on(enc, "2026-11-19")
        np.testing.assert_array_equal(prep.is_settled, [True])
        assert prep.cash == pytest.approx(cash)
        assert valued(prep, 3.50).mark == 0.0


def test_a_batch_prepares_where_each_of_its_rows_alone_is_a_delivery() -> None:
    assert prepared_on(encoded_of(terms_of(BUY, SELL)), "2026-11-19").cash == 1_000.0
    for row in (BUY, SELL):
        assert refusal(encoded_of(terms_of(row)), "2026-11-19").endswith(OPEN)


def test_a_correction_that_leaves_a_count_open_fails_and_the_row_put_right_recovers() -> None:
    assert refusal(encoded_of(terms_of(BUY, (Z26, -2.0, 3.10))), "2026-11-19") == (
        "Z26 expired 2026-11-18, before valuation date 2026-11-19, with -1.0 of 'LOT' open, "
        f"trade 1001 at row 1 among them; {OPEN}"
    )
    assert prepared_on(encoded_of(terms_of(BUY, SELL)), "2026-11-19").cash == 1_000.0


# --- counts a number cannot add -------------------------------------------------------------

HELD = (
    "buys and sells together, expected under 9007199254740992.0; a physical position is closed "
    "by its whole counts adding to zero, and past 2^53 a number does not add them exactly"
)


def refused_when_made(*rows: Row) -> str:
    with pytest.raises(ValueError) as refused:
        encoded_of(terms_of(*rows))
    return str(refused.value)


def test_counts_under_what_a_number_adds_exactly_close_and_leave_exactly() -> None:
    half = EXACT_COUNTS / 2  # 2^52
    # Under 2^53 in all, buys and sells together, every count and every sum is a whole number
    # a float holds: nine quadrillion lots bought and sold are closed, and one lot left among
    # them is one lot.
    closed = encoded_of(terms_of((Z26, half - 1, 3.0), (Z26, -(half - 1), 3.0)))
    np.testing.assert_array_equal(closed.closed, [True])
    one = encoded_of(terms_of((Z26, half - 1, 3.0), (Z26, -(half - 2), 3.0)))
    left, held = position_counts(one.terms, one.group_of_component, 1)
    np.testing.assert_array_equal(left, [[1, 0]])
    np.testing.assert_array_equal(held, [[EXACT_COUNTS - 3, 0]])
    assert refusal(one, "2026-11-19") == (
        "Z26 expired 2026-11-18, before valuation date 2026-11-19, with 1.0 of 'LOT' open, "
        f"trade 1001 at row 1 among them; {OPEN}"
    )


def test_counts_a_number_cannot_add_exactly_are_refused_when_the_batch_is_made() -> None:
    half = EXACT_COUNTS / 2
    # At 2^53 one count more is no number: the batch is refused when it is made, by the contract
    # and the unit, whatever its rows add to and whether or not the contract has expired.
    assert refused_when_made((Z26, half, 3.0), (Z26, -half, 3.0)) == (
        f"Z26 holds 9007199254740992.0 of 'LOT' in all, {HELD}"
    )
    assert refused_when_made(BUY, SELL, (F27, half, 3.0, MMBTU), (F27, -half, 3.0, MMBTU)) == (
        f"F27 holds 9007199254740992.0 of 'MMBTU' in all, {HELD}"
    )
    assert refused_when_made((Z26, 1e300, 3.0), (Z26, 1.0, 3.0), (Z26, -1e300, 3.0)) == (
        f"Z26 holds 2e+300 of 'LOT' in all, {HELD}"
    )
    # One unit past it and another under: the first unit past it is the one named.
    assert refused_when_made(BUY, SELL, (Z26, EXACT_COUNTS, 3.0, MMBTU)).startswith(
        "Z26 holds 9007199254740992.0 of 'MMBTU' in all, "
    )


def test_a_quantity_per_day_whose_product_rounds_is_refused_and_never_read_closed() -> None:
    # The review of #258. A quantity per calendar day is counted as the quantity times its
    # days, and 2^49 + 1 a day over December's 31 days is a count no number holds: it rounds
    # up by one. Against 2^49 a day sold, 32 a month more sold leaves one short in truth and
    # read as closed, and 31 closes in truth and read as one long. Neither is told now: the
    # counts are past what a number adds, and the batch is refused when it is made.
    day = 2.0**49
    for last in (-32.0, -31.0):
        told = refused_when_made(
            (Z26, day + 1, 3.0, LOT, "calday"), (Z26, -day, 3.0, LOT, "calday"), (Z26, last, 3.0)
        )
        assert told.startswith("Z26 holds 3.49028971121214") and told.endswith(HELD)
    # The same shape a quarter the size is under 2^53 in all and exact both ways: 2^47 + 1 a
    # day against 2^47 a day leaves 31, which 31 a month closes and 32 a month oversells by one.
    day = 2.0**47
    rows = ((Z26, day + 1, 3.0, LOT, "calday"), (Z26, -day, 3.0, LOT, "calday"))
    closed = encoded_of(terms_of(*rows, (Z26, -31.0, 3.0)))
    np.testing.assert_array_equal(closed.closed, [True])
    np.testing.assert_array_equal(prepared_on(closed, "2026-11-19").is_settled, [True])
    short = encoded_of(terms_of(*rows, (Z26, -32.0, 3.0)))
    np.testing.assert_array_equal(short.closed, [False])
    assert refusal(short, "2026-11-19") == (
        "Z26 expired 2026-11-18, before valuation date 2026-11-19, with -1.0 of 'LOT' open, "
        f"trade 1001 at row 1 among them; {OPEN}"
    )


# --- the clearing house ---------------------------------------------------------------------


def test_a_physical_batch_clears_through_one_clearing_house() -> None:
    with pytest.raises(ValueError) as refused:
        terms_of(BUY, SELL, BUY, houses=("CME Clearing", "ICE Clear Europe", "LCH"))
    assert str(refused.value) == (
        "clearing_house of trade 1002 at row 2 is 'ICE Clear Europe', expected 'CME Clearing' as "
        "at row 1; a physical batch clears through one clearing house"
    )
    # The labels are compared as given, so another spelling is another house.
    with pytest.raises(
        ValueError, match=r"^clearing_house of trade 1002 at row 2 is 'cme clearing'"
    ):
        terms_of(BUY, SELL, houses=("CME Clearing", "cme clearing"))
    assert terms_of(BUY, SELL, houses=("ICE", "ICE")).clearing_house == ("ICE", "ICE")


def test_a_bilateral_physical_batch_names_no_house_and_is_refused_at_evaluation_as_before() -> None:
    enc = encoded_of(terms_of(BUY, SELL, route=Route.BILATERAL))
    prep = prepared_on(enc, "2026-11-19")
    assert prep.cash == 1_000.0 and prep.unpaid_payments is None
    with pytest.raises(ValueError) as refused:
        valued(prep, 3.50)
    assert str(refused.value) == (
        "settlement_method is 'physical', expected 'financial' with a bilateral batch; a "
        "physical delivery has no payment to discount"
    )


def test_a_financial_batch_keeps_no_flags_names_two_houses_and_pays_on_its_day() -> None:
    # The same two rows paid on 20 November under two clearing houses: nothing of this ticket
    # touches them. Fixed and unpaid on the 19th, the 1,000 is still the mark; paid on the 20th.
    terms = terms_of(BUY, SELL, houses=("CME Clearing", "ICE Clear Europe"), pays="2026-11-20")
    enc = encoded_of(terms)
    assert enc.closed is None and terms.clearing_house == ("CME Clearing", "ICE Clear Europe")
    unpaid = prepared_on(enc, "2026-11-19")
    np.testing.assert_array_equal(unpaid.is_settled, [False])
    assert (valued(unpaid, 3.50).mark, unpaid.cash) == (1_000.0, 0.0)
    paid = prepared_on(enc, "2026-11-20")
    np.testing.assert_array_equal(paid.is_settled, [True])
    assert (valued(paid, 3.50).mark, paid.cash) == (0.0, 1_000.0)


# --- on the sheet ---------------------------------------------------------------------------


def serial(text: str) -> float:
    return float((np.datetime64(text, "D") - FIRST).astype(np.int64))


def row(*cells: object) -> Cells:
    return Cells.from_rows([list(cells)])


def rows(*lines: list[Any]) -> Cells:
    return Cells.from_rows(list(lines))


def column(values: list[float]) -> Cells:
    return Cells.from_rows([[float(v)] for v in values])


def spilled(result: object) -> list[list[object]]:
    kinds, slots, text = cast(tuple[NDArray[np.uint8], NDArray[np.float64], str], result)
    texts = iter(text.split("\0"))
    return [
        [
            next(texts) if kinds[r, c] == bridge.TEXT_CODE else slots[r, c]
            for c in range(kinds.shape[1])
        ]
        for r in range(kinds.shape[0])
    ]


HEADERS = ("trade_id", "trade_date", "contract_code", "quantity", "fixed_price")
TEMPLATE: dict[str, object] = {
    "quantity_unit": "LOT",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "physical",
    "clearing_house": "CME Clearing",
    "broker": "ION",
}
CLOSED_DAY = "2026-12-25"  # the sheet's index needs a holiday; the kernel's has none
PAIR: list[list[object]] = [
    [1001.0, serial("2026-10-06"), "Z26", 1.0, 3.00],
    [1002.0, serial("2026-10-06"), "Z26", -1.0, 3.10],
]


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """The page's index and template through the seam, and a history valued on a day."""
    holidays = ENTRY["_CreateHolidayCalendar"](column([serial(CLOSED_DAY)]))
    schedule = ENTRY["_CreateFuturesSchedule"](
        rows(*[[code] for code, _ in CONTRACTS]),
        column([serial(expiry) for _, expiry in CONTRACTS]),
        bridge.MISSING,
    )
    made = ENTRY["_CreateIndex"](
        "GAS",
        "GAS index",
        schedule,
        ENTRY["_CreateIndexConventions"]("USD", "MMBTU", "USD", "ENERGY", "MMBTU"),
        ENTRY["_CreateContractSpecifications"](
            row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
            rows(["LOT", 10_000.0, "MMBTU", 10.0, 4.0], ["MMBTU", 1.0, "MMBTU", 0.0, 0.0]),
        ),
        holidays,
        "LOT",
    )

    def history(as_of: str, settle: float = 3.0) -> str:
        days = np.arange(np.datetime64("2026-10-29", "D"), np.datetime64(as_of, "D"))
        days = days[np.is_busday(days, holidays=dates(CLOSED_DAY))]
        prices = np.full(days.size, 3.0)
        prices[days == np.datetime64("2026-11-18", "D")] = settle
        fixings = ENTRY["_CreateFuturesFixings"](
            column([serial(str(d)) for d in days[::-1]]), column(list(prices[::-1])), made
        )
        cal = ENTRY["_CreateCalendar"](ENTRY["_CreateValuationDate"](serial(as_of), 0.5), made)
        return str(ENTRY["_CreateMarketHistory"](cal, fixings))

    return {
        "index": str(made),
        "holidays": holidays,
        "template": ENTRY["_CreateTradeTemplate"](
            "fixed_float", row(*TEMPLATE), row(*TEMPLATE.values())
        ),
        "history": history,
    }


def booked(sheet: dict[str, Any], *lines: list[object], template: object = None) -> object:
    return ENTRY["_CreateTrades"](
        sheet["index"], row(*HEADERS), rows(*lines), template or sheet["template"]
    )


def evaluated(sheet: dict[str, Any], trades: object, as_of: str, *quotes: float) -> object:
    history = sheet["history"](as_of)
    quoted = ENTRY["_CreateMarket"](history, ENTRY["_CreatePriceVector"]("GAS", column([*quotes])))
    return ENTRY["_EvaluateTrades"](
        ENTRY["_PrepareTrades"](trades, history), quoted, bridge.MISSING
    )


def test_the_sheet_reads_the_closed_contract_as_cash_with_its_fees_and_no_risk(
    sheet: dict[str, Any],
) -> None:
    trades = booked(sheet, *PAIR)
    for as_of, quotes, mark, cash in (
        ("2026-11-18", (3.20, 3.50), 1_000.0, 0.0),
        ("2026-11-19", (3.50,), 0.0, 1_000.0),
        ("2026-11-20", (3.50,), 0.0, 1_000.0),
    ):
        results = evaluated(sheet, trades, as_of, *quotes)
        assert spilled(ENTRY["_ReportValues"](results)) == [
            ["cleared_mark", "cleared_cash", "currency", "as_of", "currency_unit"],
            ["float64", "float64", "str", "datetime64[D]", "str"],
            [mark, cash, "USD", serial(as_of), "USD"],
        ]
        assert spilled(ENTRY["_ReportReserves"](results))[2] == [20.0, 8.0, 0.0, 0.0, "USD", "USD"]
        for bucket in ("day", "month", "year"):
            total = spilled(ENTRY["_ReportRisk"](results, "nominal_delta", bucket))[3]
            assert total == ["Total", 0.0]
    # The prepared readback shows the slot fixed and its contract settled, with nothing live;
    # a physical contract pays on no day and shows none.
    prepared = ENTRY["_PrepareTrades"](trades, sheet["history"]("2026-11-19", 9.0))
    assert spilled(ENTRY["util_ReadHandle"](prepared)) == [
        [
            "pricing_contract",
            "booked_period",
            "observation_date",
            "is_fixed",
            "is_settled",
            "live_coefficient",
            "live_lots",
        ],
        ["str", "str", "datetime64[D]", "bool", "bool", "float64", "float64"],
        ["Z26", "Z26", serial("2026-11-18"), True, True, 0.0, 0.0],
    ]


def test_the_sheet_reads_a_later_month_with_the_closed_contract_behind_the_valuation_day(
    sheet: dict[str, Any],
) -> None:
    # In January the closed December contract stands before the first month a report shows:
    # it holds no lots, so the month and year reports stand and the cash is still read.
    results = evaluated(sheet, booked(sheet, *PAIR), "2027-01-05", 3.50)
    assert spilled(ENTRY["_ReportValues"](results))[2][:2] == [0.0, 1_000.0]
    for bucket in ("month", "year"):
        assert spilled(ENTRY["_ReportRisk"](results, "all", bucket))[3][:2] == ["Total", 0.0]


def test_the_sheet_refuses_an_open_contract_and_a_second_clearing_house(
    sheet: dict[str, Any],
) -> None:
    held = booked(sheet, PAIR[0])
    assert ENTRY["_PrepareTrades"](held, sheet["history"]("2026-11-19")) == (
        "#ERROR _PrepareTrades: ValueError: Z26 expired 2026-11-18, before valuation date "
        "2026-11-19, with 1.0 of 'LOT' open, trade 1001 at row 1 among them; a physical position "
        "open past its expiry is a delivery, which is not modeled"
    )
    houses = {name: value for name, value in TEMPLATE.items() if name != "clearing_house"}
    template = ENTRY["_CreateTradeTemplate"]("fixed_float", row(*houses), row(*houses.values()))
    ticket = [
        [*PAIR[0], "CME Clearing"],
        [*PAIR[1], "ICE Clear Europe"],
    ]
    assert ENTRY["_CreateTrades"](
        sheet["index"], row(*HEADERS, "clearing_house"), rows(*ticket), template
    ) == (
        "#ERROR _CreateTrades: ValueError: clearing_house of trade 1002 at row 2 is "
        "'ICE Clear Europe', expected 'CME Clearing' as at row 1; a physical batch clears through "
        "one clearing house"
    )
    # A financial batch may name two, as before.
    financial = {
        **houses,
        "settlement_method": "financial",
        "payment_day": "+2bd",
        "payment_holiday_calendar": sheet["holidays"],
    }
    template = ENTRY["_CreateTradeTemplate"](
        "fixed_float", row(*financial), row(*financial.values())
    )
    made = ENTRY["_CreateTrades"](
        sheet["index"], row(*HEADERS, "clearing_house"), rows(*ticket), template
    )
    assert re.fullmatch(r"\d+:trades:GAS:\d+", str(made))
