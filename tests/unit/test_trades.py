"""The trade kernel on the NG example and the toy lifecycle of
docs/engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md: the resolved
terms and their rules, the static encoding, the preparation against a real history and the
evaluation against a real market, every hand answer of the pages pinned, the batch equal to its
singletons summed, duplicates counting, a fixed batch inside a live market, an expired physical
component refused, and nothing redone on a tick."""

import re
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.calendar.calendar import calendar
from goosedove.globals.unit_conversions import UNITS
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import FuturesSchedule, futures_schedule
from goosedove.index_definitions.gas_daily_schedule import gas_daily_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FUTURE
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.futures_fixings import futures_fixings
from goosedove.market_data.price_vector import price_vector
from goosedove.trades.encoding import encoded
from goosedove.trades.evaluation import Results, results
from goosedove.trades.preparation import prepared
from goosedove.trades.terms import (
    QuantityPer,
    ResolvedTrades,
    Route,
    ScheduleMethod,
    Settlement,
    resolved_trades,
)


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


def rows(*values: int) -> NDArray[np.intp]:
    return np.array(values, dtype=np.intp)


def numbers(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# --- the page's static facts ----------------------------------------------------------------
# Henry Hub NYMEX: USD per MMBTU, ENERGY measured in MMBTU; one specification, NYMEX NG, 10,000
# MMBTU a lot and no fees; the schedule X26, Z26 and F27, X26 the preceding contract the calendar
# needs as its left boundary; the pricing holidays 26 November and 25 December 2026.


def an_index(
    name: str = "Henry Hub NYMEX",
    contracts: tuple[tuple[str, str], ...] = (
        ("X26", "2026-10-28"),
        ("Z26", "2026-11-25"),
        ("F27", "2026-12-29"),
    ),
    holidays: tuple[str, ...] = ("2026-11-26", "2026-12-25"),
    quote: tuple[str, str] = ("USD", "MMBTU"),
    measure: tuple[str, str] = ("ENERGY", "MMBTU"),
    lot: tuple[str, float, str] = ("NYMEX NG", 10_000.0, "MMBTU"),
) -> Index:
    codes = tuple(code for code, _ in contracts)
    schedule = futures_schedule(codes, dates(*(expiry for _, expiry in contracts)), None)
    spec_name, lot_size, lot_unit = lot
    return index(
        name,
        schedule,
        index_conventions(quote[0], quote[1], "USD", measure[0], measure[1], UNITS),
        contract_specifications(
            (spec_name,), numbers(lot_size), (lot_unit,), numbers(0.0), numbers(0.0), UNITS
        ),
        holiday_calendar(dates(*holidays)),
        UNITS,
    )


NG = an_index()
# TOY_GAS: the same conventions and lot, a financial settlement, and G27 after F27 so that every
# state of the lifecycle has a market; its payment calendar also closes on New Year's Day.
TOY = an_index(
    "TOY_GAS",
    (("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29"), ("G27", "2027-01-27")),
    ("2026-11-26", "2026-12-25", "2027-01-01"),
    lot=("TOY", 10_000.0, "MMBTU"),
)

# The five occurrences: NG-001 twice, every value identical, the duplicate counting.
LABELS = ("NG-001", "NG-002", "NG-003", "NG-004", "NG-001")
TRADE_DATES = dates("2026-09-24", "2026-09-24", "2026-09-25", "2026-09-25", "2026-09-24")
CONTRACT = rows(1, 1, 2, 2, 1)  # Z26, Z26, F27, F27, Z26 as rows of the schedule
LOTS = numbers(10, -4, 7, -12, 10)
FIXED_PRICE = numbers(3.100, 3.150, 3.400, 3.350, 3.100)
# The toy pays two business days after each contract's last trading day: 30 November for Z26 and
# 31 December for F27, computed once on the page and supplied here as resolved dates.
TOY_PAYS = dates("2026-11-30", "2026-11-30", "2026-12-31", "2026-12-31", "2026-11-30")


def terms_of(
    ix: Index = NG,
    settlement: Settlement = Settlement.PHYSICAL,
    pays: NDArray[np.datetime64] | None = None,
    keep: slice = slice(None),
    route: Route = Route.CLEARED,
    labels: tuple[str, ...] | None = LABELS,
) -> ResolvedTrades:
    """The page's five rows resolved against an index, or the rows a slice keeps."""
    occurrences = TRADE_DATES[keep].size
    return resolved_trades(
        FUTURE,
        ix,
        0,
        route,
        settlement,
        ScheduleMethod.LASTDAY,
        "LOT",
        QuantityPer.MONTH,
        None if labels is None else labels[keep],
        None,
        None,
        TRADE_DATES[keep],
        np.arange(occurrences, dtype=np.intp),
        CONTRACT[keep],
        LOTS[keep],
        FIXED_PRICE[keep],
        None if pays is None else pays[keep],
    )


def history_on(ix: Index, as_of: str, finals: dict[str, float]) -> MarketHistory:
    """The index's history valued on that day: a settle of 3.00 on every fixed business day of
    its calendar, the final prices given standing on their contracts' expiry days, given newest
    first as the fixings creator takes them."""
    cal = calendar(valuation_date(day(as_of), 0.5), ix)
    schedule = cast(FuturesSchedule, ix.schedule)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = np.full(priced.size, 3.0)
    for code, price in finals.items():
        settles[priced == schedule.future_expiry[schedule.codes.index(code)]] = price
    return market_history(cal, futures_fixings(priced[::-1].copy(), settles[::-1].copy(), ix))


def quoted(history: MarketHistory, *quotes: float) -> Market:
    return market(history, price_vector(history.calendar.index.name, numbers(*quotes)))


def evaluated(
    ix: Index,
    as_of: str,
    finals: dict[str, float],
    quotes: tuple[float, ...],
    settlement: Settlement = Settlement.PHYSICAL,
    pays: NDArray[np.datetime64] | None = None,
    keep: slice = slice(None),
) -> tuple[Results, WorkCounter]:
    """The page's rows, or the rows kept, taken through the four steps on one counter."""
    counter = WorkCounter()
    enc = encoded(terms_of(ix, settlement, pays, keep), UNITS, counter)
    history = history_on(ix, as_of, finals)
    prep = prepared(enc, history, counter)
    return results(prep, quoted(history, *quotes), counter), counter


# --- the resolved terms ---------------------------------------------------------------------


def test_the_terms_own_frozen_copies_of_their_columns() -> None:
    lots, pays = LOTS.copy(), TOY_PAYS.copy()
    terms = resolved_trades(
        FUTURE, TOY, 0, Route.CLEARED, Settlement.FINANCIAL, ScheduleMethod.LASTDAY, "LOT",
        QuantityPer.MONTH, LABELS, ("CME Clearing",) * 5, None, TRADE_DATES,
        np.arange(5, dtype=np.intp), CONTRACT, lots, FIXED_PRICE, pays,
    )  # fmt: skip
    lots[0], pays[0] = 99.0, day("2030-01-01")  # the arrays that were passed, changed after
    assert terms.lots[0] == 10.0 and terms.schedule is TOY.schedule
    assert terms.payment_date is not None and terms.payment_date[0] == day("2026-11-30")
    for column in (terms.trade_dates, terms.occurrence, terms.contract, terms.lots):
        assert not column.flags.writeable
    assert terms.payment_date is not None and not terms.payment_date.flags.writeable
    assert terms.trade_dates.dtype == np.dtype("datetime64[D]")
    assert terms.named(4) == "trade 'NG-001' at row 5"
    assert terms_of(labels=None).named(2) == "trade at row 3"
    assert terms.instrument is FUTURE and terms.clearing_house == ("CME Clearing",) * 5
    assert terms.broker is None


GAS_DAILY = index(
    "daily",
    gas_daily_schedule(("c0",), dates("2026-01-01"), dates("2026-01-31")),
    NG.conventions,
    NG.specifications,
    None,
    UNITS,
)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {"ix": GAS_DAILY},
            "index is a Gas Daily index, expected a futures index for a future",
        ),
        (
            {"specification": 1},
            "specification is 1, expected a row of the index's specifications, 0 to 0",
        ),
        (
            {"quantity_unit": "MMBTU"},
            "quantity_unit is 'MMBTU', expected LOT, the one quantity unit built",
        ),
        (
            {"trade_dates": dates()},
            "trade_dates has 0 dates, expected at least 1, one per occurrence",
        ),
        (
            {"labels": ("a", "b")},
            "labels has 2 texts, expected 5, one per occurrence",
        ),
        (
            {"clearing_house": ("CME Clearing",)},
            "clearing_house has 1 texts, expected 5, one per occurrence",
        ),
        (
            {"broker": ("ION",) * 4},
            "broker has 4 texts, expected 5, one per occurrence",
        ),
        (
            {"occurrence": rows(), "contract": rows(), "lots": numbers(), "fixed_price": numbers()},
            "occurrence has 0 rows, expected at least 1, one per component",
        ),
        (
            {"contract": rows(1, 1)},
            "contract has 2 rows, expected 5, one per component",
        ),
        (
            {"lots": numbers(1.0)},
            "lots has 1 rows, expected 5, one per component",
        ),
        (
            {"occurrence": rows(0, 1, 2, 3, 5)},
            "occurrence row 5 is 5, expected an occurrence, 0 to 4",
        ),
        (
            {"occurrence": rows(0, 1, 2, 2, 3)},
            "trade 'NG-001' at row 5 has no component, expected at least one",
        ),
        (
            {"contract": rows(1, 1, 2, 3, 1)},
            "contract row 4 is 3, expected a row of the schedule, 0 to 2",
        ),
        (
            {"lots": numbers(10, -4, 7.5, -12, 10)},
            "lots of trade 'NG-003' at row 3 is 7.5, expected a whole number of lots",
        ),
        (
            {"lots": numbers(10, -4, np.nan, -12, 10)},
            "lots of trade 'NG-003' at row 3 is nan, expected a whole number of lots",
        ),
        (
            {"lots": numbers(10, 0, 7, -12, 10)},
            "lots of trade 'NG-002' at row 2 is 0.0, expected a nonzero quantity",
        ),
        (
            {"fixed_price": numbers(3.1, 3.15, 3.4, np.inf, 3.1)},
            "fixed_price of trade 'NG-004' at row 4 is inf, expected a finite price",
        ),
        (
            {"settlement": Settlement.FINANCIAL},
            "payment_date is missing, expected one date per component with a financial settlement",
        ),
        (
            {"settlement": Settlement.FINANCIAL, "payment_date": dates("2026-11-30")},
            "payment_date has 1 dates, expected 5, one per component",
        ),
        (
            {"payment_date": TOY_PAYS},
            "payment_date has 5 dates, expected none with a physical settlement, "
            "which pays on no day",
        ),
    ],
)
def test_terms_that_cannot_be_resolved_say_why(change: dict[str, Any], message: str) -> None:
    given_terms: dict[str, Any] = {
        "instrument": FUTURE,
        "ix": NG,
        "specification": 0,
        "route": Route.CLEARED,
        "settlement": Settlement.PHYSICAL,
        "schedule_method": ScheduleMethod.LASTDAY,
        "quantity_unit": "LOT",
        "quantity_per": QuantityPer.MONTH,
        "labels": LABELS,
        "clearing_house": None,
        "broker": None,
        "trade_dates": TRADE_DATES,
        "occurrence": rows(0, 1, 2, 3, 4),
        "contract": CONTRACT,
        "lots": LOTS,
        "fixed_price": FIXED_PRICE,
        "payment_date": None,
    }
    given_terms.update(change)
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        resolved_trades(*given_terms.values())


# --- the static encoding --------------------------------------------------------------------


def test_the_ng_rows_encode_as_the_page_says() -> None:
    counter = WorkCounter()
    enc = encoded(terms_of(), UNITS, counter)
    np.testing.assert_array_equal(enc.quantity, [100_000, -40_000, 70_000, -120_000, 100_000])
    np.testing.assert_array_equal(enc.coefficient, enc.quantity)  # dollars quoted, dollars paid
    np.testing.assert_array_equal(enc.offset, [-310_000, 126_000, -238_000, 402_000, -310_000])
    np.testing.assert_array_equal(enc.inputs, [1, 2])
    np.testing.assert_array_equal(enc.input_of_component, [0, 0, 1, 1, 0])
    np.testing.assert_array_equal(enc.quantity_of_input, [160_000, -50_000])
    np.testing.assert_array_equal(enc.exposure, [160_000, -50_000])
    np.testing.assert_array_equal(enc.offset_of_input, [-494_000, 164_000])
    assert enc.offset_of_input.sum() == -330_000
    assert enc.payment_date is None
    assert counter.freeze().as_dict() == {"encoded_components": 5, "encoded_inputs": 2}
    for array in (enc.quantity, enc.offset, enc.inputs, enc.exposure, enc.offset_of_input):
        assert not array.flags.writeable


def test_a_duplicate_occurrence_adds_its_exposure_twice() -> None:
    whole = encoded(terms_of(), UNITS, WorkCounter())
    without = encoded(terms_of(keep=slice(0, 4)), UNITS, WorkCounter())
    assert whole.exposure[0] - without.exposure[0] == 100_000
    assert whole.offset_of_input[0] - without.offset_of_input[0] == -310_000


def test_a_lot_in_another_unit_than_the_quote_is_converted_once() -> None:
    # Quoted in USD per gallon, a lot of 1,000 barrels: 42,000 gallons a lot.
    crude = an_index(
        "crude", quote=("USD", "GAL"), measure=("VOLUME", "BBL"), lot=("NYMEX", 1_000.0, "BBL")
    )
    enc = encoded(terms_of(crude), UNITS, WorkCounter())
    np.testing.assert_allclose(enc.quantity, LOTS * 42_000)
    np.testing.assert_allclose(enc.offset, -LOTS * 42_000 * FIXED_PRICE)


def test_a_price_in_cents_settles_in_dollars() -> None:
    cents = an_index("cents", quote=("CENT", "MMBTU"))
    enc = encoded(terms_of(cents), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.quantity, LOTS * 10_000)  # MMBTU, the physical quantity
    np.testing.assert_allclose(enc.coefficient, LOTS * 100)  # USD per cent per MMBTU
    np.testing.assert_allclose(enc.offset, -LOTS * 100 * FIXED_PRICE)
    np.testing.assert_allclose(enc.exposure, [1_600, -500])
    np.testing.assert_array_equal(enc.quantity_of_input, [160_000, -50_000])


# The review's case: one lot of 10,000 MMBTU bought at 300 cents, settled in dollars, through
# live, fixed and paid. At 300 cents everything is zero; a cent is 100 dollars; at 310 the mark
# is 1,000 dollars and so, once fixed and paid at 310, is the cash. The quotes, the final price
# and the fixed price are all in cents, and only the coefficient turns them into dollars.
CENTS = an_index(
    "cents",
    (("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29"), ("G27", "2027-01-27")),
    ("2026-11-26", "2026-12-25", "2027-01-01"),
    quote=("CENT", "MMBTU"),
)


def one_lot_in_cents(
    as_of: str, finals: dict[str, float], *quotes: float
) -> tuple[Results, WorkCounter]:
    counter = WorkCounter()
    terms = resolved_trades(
        FUTURE, CENTS, 0, Route.CLEARED, Settlement.FINANCIAL, ScheduleMethod.LASTDAY, "LOT",
        QuantityPer.MONTH, ("C-1",), None, None, dates("2026-09-24"), rows(0), rows(1),
        numbers(1), numbers(300.0), dates("2026-11-30"),
    )  # fmt: skip
    history = history_on(CENTS, as_of, finals)
    prep = prepared(encoded(terms, UNITS, counter), history, counter)
    return results(prep, quoted(history, *quotes), counter), counter


@pytest.mark.parametrize(
    ("as_of", "finals", "quotes", "mark", "cash", "delta"),
    [
        ("2026-11-24", {}, (300.0, 350.0, 360.0), 0, 0, 100),
        ("2026-11-24", {}, (310.0, 350.0, 360.0), 1_000, 0, 100),
        ("2026-11-26", {"Z26": 300.0}, (350.0, 360.0), 0, 0, 0),
        ("2026-11-26", {"Z26": 310.0}, (350.0, 360.0), 1_000, 0, 0),
        ("2026-11-30", {"Z26": 300.0}, (350.0, 360.0), 0, 0, 0),
        ("2026-11-30", {"Z26": 310.0}, (350.0, 360.0), 0, 1_000, 0),
    ],
    ids=[
        "live at cost",
        "live ten cents up",
        "fixed at cost",
        "fixed ten up",
        "paid at cost",
        "paid ten up",
    ],
)
def test_one_lot_quoted_in_cents_values_in_dollars_through_live_fixed_and_paid(
    as_of: str,
    finals: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
) -> None:
    result, _ = one_lot_in_cents(as_of, finals, *quotes)
    assert result.mark == pytest.approx(mark)
    assert result.cash == pytest.approx(cash)
    np.testing.assert_allclose(result.delta, [delta])
    assert result.delta_total == pytest.approx(delta)
    assert result.delta_unit == "USD per CENT/MMBTU" and result.currency == "USD"


def test_a_financial_settlement_keeps_one_payment_day_per_contract() -> None:
    enc = encoded(terms_of(TOY, Settlement.FINANCIAL, TOY_PAYS), UNITS, WorkCounter())
    assert enc.payment_date is not None
    np.testing.assert_array_equal(enc.payment_date, dates("2026-11-30", "2026-12-31"))
    assert not enc.payment_date.flags.writeable


@pytest.mark.parametrize(
    ("pays", "message"),
    [
        (
            dates("2026-11-30", "2026-12-01", "2026-12-31", "2026-12-31", "2026-11-30"),
            "payment_date of trade 'NG-002' at row 2 is 2026-12-01, expected 2026-11-30, "
            "the one day Z26 pays",
        ),
        (
            dates("2026-11-30", "2026-11-30", "2026-12-29", "2026-12-29", "2026-11-30"),
            "F27 pays on 2026-12-29, expected a day after its expiry 2026-12-29, "
            "when its final price exists",
        ),
    ],
)
def test_payment_days_that_cannot_be_encoded_say_why(
    pays: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        encoded(terms_of(TOY, Settlement.FINANCIAL, pays), UNITS, WorkCounter())


# --- the preparation ------------------------------------------------------------------------


def test_before_either_expiry_both_contracts_are_live_and_nothing_is_set() -> None:
    counter = WorkCounter()
    enc = encoded(terms_of(), UNITS, WorkCounter())
    prep = prepared(enc, history_on(NG, "2026-11-24", {}), counter)
    np.testing.assert_array_equal(prep.is_live, [True, True])
    np.testing.assert_array_equal(prep.is_settled, [False, False])
    np.testing.assert_array_equal(prep.set_amount, [0.0, 0.0])
    np.testing.assert_array_equal(prep.live_contracts, [1, 2])
    np.testing.assert_array_equal(prep.live_exposure, [160_000, -50_000])
    assert (prep.offset_unsettled, prep.set_unsettled, prep.cash) == (-330_000, 0.0, 0.0)
    assert counter.freeze().as_dict() == {"fixings_read": 0, "prepared_inputs": 2}
    for array in (prep.is_live, prep.is_settled, prep.set_amount, prep.live_exposure):
        assert not array.flags.writeable


def test_a_contract_stays_live_on_its_expiry_day_and_is_expired_the_day_after() -> None:
    enc = encoded(terms_of(), UNITS, WorkCounter())
    on_the_day = prepared(enc, history_on(NG, "2026-11-25", {}), WorkCounter())
    np.testing.assert_array_equal(on_the_day.is_live, [True, True])
    with pytest.raises(ValueError) as refused:
        prepared(enc, history_on(NG, "2026-11-26", {"Z26": 3.22}), WorkCounter())
    assert str(refused.value) == (
        "trade 'NG-001' at row 1 on Z26 expired 2026-11-25, before valuation date 2026-11-26; "
        "a physical future after its expiry is not supported"
    )


def test_a_history_over_another_index_is_refused_whatever_its_name() -> None:
    enc = encoded(terms_of(), UNITS, WorkCounter())
    twin = an_index()  # the same facts, another object
    with pytest.raises(ValueError) as refused:
        prepared(enc, history_on(twin, "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "history is over another index, 'Henry Hub NYMEX', expected the trades', 'Henry Hub NYMEX'"
    )


def test_a_trade_on_the_schedules_first_contract_is_refused_since_nothing_prices_it() -> None:
    boundary = resolved_trades(
        FUTURE, NG, 0, Route.CLEARED, Settlement.PHYSICAL, ScheduleMethod.LASTDAY, "LOT",
        QuantityPer.MONTH, None, None, None, dates("2026-09-24"), rows(0), rows(0), numbers(1),
        numbers(3.0), None,
    )  # fmt: skip
    enc = encoded(boundary, UNITS, WorkCounter())
    with pytest.raises(ValueError) as refused:
        prepared(enc, history_on(NG, "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "X26 expires 2026-10-28, before the calendar begins; "
        "the schedule's first contract bounds the calendar and nothing prices it"
    )


def test_a_financial_contract_expiring_on_a_closed_day_has_no_final_price() -> None:
    # A toy whose Z26 expires on Thanksgiving, which its own calendar closes.
    closed = an_index(
        "closed",
        (
            ("X26", "2026-10-28"),
            ("Z26", "2026-11-26"),
            ("F27", "2026-12-29"),
            ("G27", "2027-01-27"),
        ),
        ("2026-11-26", "2026-12-25"),
    )
    enc = encoded(terms_of(closed, Settlement.FINANCIAL, TOY_PAYS), UNITS, WorkCounter())
    with pytest.raises(ValueError) as refused:
        prepared(enc, history_on(closed, "2026-11-27", {}), WorkCounter())
    assert str(refused.value) == (
        "Z26 expires 2026-11-26, a day its calendar does not price; no final price exists"
    )


# --- the evaluation: the NG example ---------------------------------------------------------


def test_the_five_ng_rows_mark_7000_then_8600_on_the_tick() -> None:
    initial, counter = evaluated(NG, "2026-11-24", {}, (3.20, 3.50))
    assert (initial.mark, initial.cash) == (7_000, 0)
    np.testing.assert_array_equal(initial.delta, [160_000, -50_000])
    assert initial.delta_total == 110_000 and initial.dv01 == 0.0
    assert initial.delta_unit == "USD per USD/MMBTU"
    assert initial.codes() == ("Z26", "F27") and initial.currency == "USD"
    assert initial.route is Route.CLEARED and initial.as_of == day("2026-11-24")
    assert counter.freeze().as_dict() == {
        "encoded_components": 5,
        "encoded_inputs": 2,
        "fixings_read": 0,
        "kernel": 1,
        "live_prices_read": 2,
        "prepared_inputs": 2,
    }
    tick, _ = evaluated(NG, "2026-11-24", {}, (3.21, 3.50))
    assert tick.mark == pytest.approx(8_600)
    np.testing.assert_array_equal(tick.delta, initial.delta)
    assert not tick.delta.flags.writeable


def test_the_batch_equals_its_five_singletons_summed_and_the_duplicate_counts() -> None:
    whole, _ = evaluated(NG, "2026-11-24", {}, (3.20, 3.50))
    singles = [
        evaluated(NG, "2026-11-24", {}, (3.20, 3.50), keep=slice(i, i + 1))[0] for i in range(5)
    ]
    assert [s.mark for s in singles] == pytest.approx([10_000, -2_000, 7_000, -18_000, 10_000])
    assert sum(s.mark for s in singles) == pytest.approx(whole.mark)
    first_four, _ = evaluated(NG, "2026-11-24", {}, (3.20, 3.50), keep=slice(0, 4))
    assert first_four.mark == pytest.approx(-3_000)
    assert whole.mark - first_four.mark == pytest.approx(10_000)
    assert whole.delta[0] - first_four.delta[0] == 100_000


def test_a_tick_takes_the_preparation_as_it_is_and_folds_nothing() -> None:
    enc = encoded(terms_of(), UNITS, WorkCounter())
    history = history_on(NG, "2026-11-24", {})
    prep = prepared(enc, history, WorkCounter())
    before = (prep.live_exposure.copy(), prep.delta.copy(), prep.offset_unsettled, prep.cash)
    counter = WorkCounter()
    later = results(prep, quoted(history, 3.21, 3.50), counter)
    assert later.mark == pytest.approx(8_600)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 2}
    assert later.prepared is prep and later.market.market_history is history
    assert later.delta is prep.delta and not later.delta.flags.writeable  # shared, never written
    np.testing.assert_array_equal(prep.live_exposure, before[0])
    np.testing.assert_array_equal(prep.delta, before[1])
    assert (prep.offset_unsettled, prep.cash) == before[2:]


def test_a_market_over_another_history_is_refused_rather_than_prepared_again() -> None:
    enc = encoded(terms_of(), UNITS, WorkCounter())
    prep = prepared(enc, history_on(NG, "2026-11-24", {}), WorkCounter())
    other = history_on(NG, "2026-11-23", {})  # the same index, another valuation date
    with pytest.raises(ValueError) as refused:
        results(prep, quoted(other, 3.20, 3.50), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'Henry Hub NYMEX', "
        "expected the one the trades were prepared against"
    )


def test_a_vector_that_stops_before_a_traded_contract_is_refused_by_the_market() -> None:
    enc = encoded(terms_of(), UNITS, WorkCounter())
    history = history_on(NG, "2026-11-24", {})
    prep = prepared(enc, history, WorkCounter())
    with pytest.raises(
        ValueError, match=r"^requested contract 'F27' is beyond live-price coverage"
    ):
        results(prep, quoted(history, 3.20), WorkCounter())


def test_a_bilateral_batch_is_refused_until_rates_exist() -> None:
    enc = encoded(terms_of(route=Route.BILATERAL), UNITS, WorkCounter())
    history = history_on(NG, "2026-11-24", {})
    prep = prepared(enc, history, WorkCounter())
    with pytest.raises(ValueError) as refused:
        results(prep, quoted(history, 3.20, 3.50), WorkCounter())
    assert str(refused.value) == (
        "route is bilateral, expected cleared; bilateral valuation needs discount factors "
        "and a DV01 convention, not built yet"
    )


# --- the evaluation: the toy lifecycle ------------------------------------------------------

# The page's seven states: as-of, the final prices known, the quotes of the contracts still live
# in the toy market, G27's last, and then mark, cash, delta by contract, live reads and fixings
# read.
LIFECYCLE: list[
    tuple[str, dict[str, float], tuple[float, ...], int, int, tuple[int, int], int, int]
] = [
    ("2026-11-24", {}, (3.20, 3.50, 3.60), 7_000, 0, (160_000, -50_000), 2, 0),
    ("2026-11-24", {}, (3.21, 3.50, 3.60), 8_600, 0, (160_000, -50_000), 2, 0),
    ("2026-11-26", {"Z26": 3.22}, (3.50, 3.60), 10_200, 0, (0, -50_000), 1, 1),
    ("2026-11-26", {"Z26": 3.23}, (3.50, 3.60), 11_800, 0, (0, -50_000), 1, 1),
    ("2026-11-30", {"Z26": 3.23}, (3.50, 3.60), -11_000, 22_800, (0, -50_000), 1, 1),
    ("2026-12-30", {"Z26": 3.23, "F27": 3.45}, (3.60,), -8_500, 22_800, (0, 0), 0, 2),
    ("2026-12-31", {"Z26": 3.23, "F27": 3.45}, (3.60,), 0, 14_300, (0, 0), 0, 2),
]


@pytest.mark.parametrize(
    ("as_of", "finals", "quotes", "mark", "cash", "delta", "live_reads", "fixings_read"),
    LIFECYCLE,
    ids=[
        "initial",
        "a tick",
        "Z26 fixed, unpaid",
        "Z26 corrected",
        "Z26 paid",
        "both fixed, F27 unpaid",
        "both paid",
    ],
)
def test_the_toy_lifecycle_marks_and_pays_as_the_page_says(
    as_of: str,
    finals: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: tuple[float, float],
    live_reads: int,
    fixings_read: int,
) -> None:
    result, counter = evaluated(TOY, as_of, finals, quotes, Settlement.FINANCIAL, TOY_PAYS)
    assert result.mark == pytest.approx(mark)
    assert result.cash == pytest.approx(cash)
    np.testing.assert_array_equal(result.delta, delta)
    assert result.delta_total == pytest.approx(sum(delta))
    assert result.codes() == ("Z26", "F27")  # the axis stable, G27 on it nowhere
    counts = counter.freeze()
    assert (counts["live_prices_read"], counts["fixings_read"], counts["kernel"]) == (
        live_reads,
        fixings_read,
        1,
    )


def test_the_settled_contracts_amounts_are_the_singletons_summed() -> None:
    both_paid, _ = evaluated(
        TOY, "2026-12-31", {"Z26": 3.23, "F27": 3.45}, (3.60,), Settlement.FINANCIAL, TOY_PAYS
    )
    singles = [
        evaluated(
            TOY,
            "2026-12-31",
            {"Z26": 3.23, "F27": 3.45},
            (3.60,),
            Settlement.FINANCIAL,
            TOY_PAYS,
            slice(i, i + 1),
        )[0].cash
        for i in range(5)
    ]
    assert singles == pytest.approx([13_000, -3_200, 3_500, -12_000, 13_000])
    assert sum(singles) == pytest.approx(both_paid.cash) == pytest.approx(14_300)


def test_a_fully_fixed_batch_inside_a_live_market_reads_no_quote() -> None:
    enc = encoded(terms_of(TOY, Settlement.FINANCIAL, TOY_PAYS), UNITS, WorkCounter())
    history = history_on(TOY, "2026-12-30", {"Z26": 3.23, "F27": 3.45})
    prep = prepared(enc, history, WorkCounter())
    assert prep.live_contracts.size == 0 and not prep.is_live.any()
    counter = WorkCounter()
    result = results(prep, quoted(history, 3.60), counter)
    assert (result.mark, result.cash) == (pytest.approx(-8_500), pytest.approx(22_800))
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 0}
    assert result.market.first_contract == 3  # G27, quoted and held by no trade


# --- properties -------------------------------------------------------------------------------

lots_strategy = st.integers(min_value=-20, max_value=20).filter(lambda n: n != 0)
prices_strategy = st.floats(min_value=1.0, max_value=9.0, allow_nan=False, allow_infinity=False)


@settings(max_examples=60, deadline=None)
@given(
    trades=st.lists(
        st.tuples(st.integers(min_value=1, max_value=2), lots_strategy, prices_strategy),
        min_size=1,
        max_size=8,
    ),
    quotes=st.tuples(prices_strategy, prices_strategy),
)
def test_any_batch_equals_its_singletons_summed(
    trades: list[tuple[int, int, float]], quotes: tuple[float, float]
) -> None:
    def valued(selected: list[tuple[int, int, float]]) -> Results:
        n = len(selected)
        terms = resolved_trades(
            FUTURE, NG, 0, Route.CLEARED, Settlement.PHYSICAL, ScheduleMethod.LASTDAY, "LOT",
            QuantityPer.MONTH, None, None, None, np.repeat(day("2026-09-24"), n),
            np.arange(n, dtype=np.intp), rows(*(c for c, _, _ in selected)),
            numbers(*(q for _, q, _ in selected)), numbers(*(p for _, _, p in selected)), None,
        )  # fmt: skip
        history = history_on(NG, "2026-11-24", {})
        prep = prepared(encoded(terms, UNITS, WorkCounter()), history, WorkCounter())
        return results(prep, quoted(history, *quotes), WorkCounter())

    whole = valued(trades)
    singles = [valued([trade]) for trade in trades]
    assert whole.mark == pytest.approx(sum(s.mark for s in singles), abs=1e-6)
    assert whole.delta_total == pytest.approx(sum(s.delta_total for s in singles))
    by_hand = sum(q * 10_000 * (quotes[c - 1] - p) for c, q, p in trades)
    assert whole.mark == pytest.approx(by_hand, abs=1e-6)
    doubled = valued(trades + trades)
    assert doubled.mark == pytest.approx(2 * whole.mark, abs=1e-6)
    assert whole.codes() == tuple(
        sorted({("Z26", "F27")[c - 1] for c, _, _ in trades}, key=("Z26", "F27").index)
    )
