"""The trade kernel on the NG example and the toy lifecycle of
docs/engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md, and on the
dated axis of dated-exposure.md: the resolved terms and their rules, the observations and theirs,
the static encoding on dated slots, the preparation against a real history and the evaluation
against a real market, every hand answer of the pages pinned, the batch equal to its singletons
summed, duplicates counting, a fixed batch inside a live market, an expired physical component
refused, the daily toy's four states and the offsetting dates, and nothing redone on a tick."""

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
from goosedove.trades.evaluation import TradeResults, trade_results
from goosedove.trades.observations import Observations, observations, observed
from goosedove.trades.preparation import prepared_trades
from goosedove.trades.terms import (
    PaymentTerms,
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
# The toy pays two business days after each contract's last trading day on its payment calendar,
# closed on 26 November, 25 December and New Year's Day: 30 November for Z26 and 31 December for
# F27, computed once on the page and supplied here as resolved dates beside the lag and the
# calendar that gave them.
TOY_PAYS = dates("2026-11-30", "2026-11-30", "2026-12-31", "2026-12-31", "2026-11-30")
PAYMENT_CALENDAR = holiday_calendar(dates("2026-11-26", "2026-12-25", "2027-01-01"))


def paying(pays: NDArray[np.datetime64], occurrences: int, lag: int = 2) -> PaymentTerms:
    """The toy's terms over those days: the lag and the calendar for every occurrence."""
    return PaymentTerms(np.full(occurrences, lag), (PAYMENT_CALENDAR,) * occurrences, pays)


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
        None if pays is None else paying(pays[keep], occurrences),
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
) -> tuple[TradeResults, WorkCounter]:
    """The page's rows, or the rows kept, taken through the four steps on one counter."""
    counter = WorkCounter()
    enc = encoded(
        terms_of(ix, settlement, pays, keep),
        observed(terms_of(ix, settlement, pays, keep)),
        UNITS,
        counter,
    )
    history = history_on(ix, as_of, finals)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


# --- the resolved terms ---------------------------------------------------------------------


def test_the_terms_own_frozen_copies_of_their_columns() -> None:
    lots, pays, lags = LOTS.copy(), TOY_PAYS.copy(), np.full(5, 2)
    terms = resolved_trades(
        FUTURE, TOY, 0, Route.CLEARED, Settlement.FINANCIAL, ScheduleMethod.LASTDAY, "LOT",
        QuantityPer.MONTH, LABELS, ("CME Clearing",) * 5, None, TRADE_DATES,
        np.arange(5, dtype=np.intp), CONTRACT, lots, FIXED_PRICE,
        PaymentTerms(lags, (PAYMENT_CALENDAR,) * 5, pays),
    )  # fmt: skip
    lots[0], pays[0], lags[0] = 99.0, day("2030-01-01"), 9  # the arrays passed, changed after
    assert terms.lots[0] == 10.0 and terms.schedule is TOY.schedule
    assert terms.payment is not None and terms.payment.date[0] == day("2026-11-30")
    assert terms.payment.lag_days[0] == 2 and terms.payment.calendar[0] is PAYMENT_CALENDAR
    for column in (terms.trade_dates, terms.occurrence, terms.contract, terms.lots):
        assert not column.flags.writeable
    assert not terms.payment.date.flags.writeable and not terms.payment.lag_days.flags.writeable
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
            "payment is missing, expected a lag and a calendar per occurrence and one date per "
            "component with a financial settlement",
        ),
        (
            {"settlement": Settlement.FINANCIAL, "payment": paying(dates("2026-11-30"), 5)},
            "payment date has 1 dates, expected 5, one per component",
        ),
        (
            {"settlement": Settlement.FINANCIAL, "payment": paying(TOY_PAYS, 4)},
            "payment lag_days has 4, expected 5, one per occurrence",
        ),
        (
            {
                "settlement": Settlement.FINANCIAL,
                "payment": PaymentTerms(np.full(5, 2), (PAYMENT_CALENDAR,) * 3, TOY_PAYS),
            },
            "payment calendar has 3, expected 5, one per occurrence",
        ),
        (
            {"payment": paying(TOY_PAYS, 5)},
            "payment has 5 dates, expected none with a physical settlement, which pays on no day",
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
        "payment": None,
    }
    given_terms.update(change)
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        resolved_trades(*given_terms.values())


# --- the static encoding --------------------------------------------------------------------


def test_the_ng_rows_encode_as_the_page_says() -> None:
    counter = WorkCounter()
    enc = encoded(terms_of(), observed(terms_of()), UNITS, counter)
    np.testing.assert_array_equal(enc.quantity, [100_000, -40_000, 70_000, -120_000, 100_000])
    np.testing.assert_array_equal(enc.coefficient, enc.quantity)  # dollars quoted, dollars paid
    np.testing.assert_array_equal(enc.offset, [-310_000, 126_000, -238_000, 402_000, -310_000])
    np.testing.assert_array_equal(enc.groups, [1, 2])
    np.testing.assert_array_equal(enc.group_of_component, [0, 0, 1, 1, 0])
    np.testing.assert_array_equal(enc.offset_of_group, [-494_000, 164_000])
    assert enc.offset_of_group.sum() == -330_000
    assert enc.payment_date is None
    # The dated axis of a lastday future: one slot per contract, on its expiry day, referencing
    # itself, the two occurrences on Z26 and the duplicate summed into one exposure.
    np.testing.assert_array_equal(enc.slot_group, [0, 1])
    np.testing.assert_array_equal(enc.slot_date, dates("2026-11-25", "2026-12-29"))
    np.testing.assert_array_equal(enc.slot_reference, [1, 2])
    np.testing.assert_array_equal(enc.slot_exposure, [160_000, -50_000])
    np.testing.assert_array_equal(enc.slot_of_observation, [0, 0, 1, 1, 0])
    np.testing.assert_array_equal(enc.references, [1, 2])
    np.testing.assert_array_equal(enc.reference_of_slot, [0, 1])
    assert enc.named_slot(0) == "trade 'NG-001' at row 1 observes Z26 on 2026-11-25"
    assert counter.freeze().as_dict() == {
        "encoded_components": 5,
        "encoded_observations": 5,
        "encoded_slots": 2,
    }
    for array in (enc.quantity, enc.offset, enc.groups, enc.slot_exposure, enc.offset_of_group):
        assert not array.flags.writeable


def test_a_duplicate_occurrence_adds_its_exposure_twice() -> None:
    whole = encoded(terms_of(), observed(terms_of()), UNITS, WorkCounter())
    without = encoded(
        terms_of(keep=slice(0, 4)), observed(terms_of(keep=slice(0, 4))), UNITS, WorkCounter()
    )
    assert whole.slot_exposure[0] - without.slot_exposure[0] == 100_000
    assert whole.offset_of_group[0] - without.offset_of_group[0] == -310_000


def test_a_lot_in_another_unit_than_the_quote_is_converted_once() -> None:
    # Quoted in USD per gallon, a lot of 1,000 barrels: 42,000 gallons a lot.
    crude = an_index(
        "crude", quote=("USD", "GAL"), measure=("VOLUME", "BBL"), lot=("NYMEX", 1_000.0, "BBL")
    )
    enc = encoded(terms_of(crude), observed(terms_of(crude)), UNITS, WorkCounter())
    np.testing.assert_allclose(enc.quantity, LOTS * 42_000)
    np.testing.assert_allclose(enc.offset, -LOTS * 42_000 * FIXED_PRICE)


def test_a_price_in_cents_settles_in_dollars() -> None:
    cents = an_index("cents", quote=("CENT", "MMBTU"))
    enc = encoded(terms_of(cents), observed(terms_of(cents)), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.quantity, LOTS * 10_000)  # MMBTU, the physical quantity
    np.testing.assert_allclose(enc.coefficient, LOTS * 100)  # USD per cent per MMBTU
    np.testing.assert_allclose(enc.offset, -LOTS * 100 * FIXED_PRICE)
    np.testing.assert_allclose(enc.slot_exposure, [1_600, -500])


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
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = resolved_trades(
        FUTURE, CENTS, 0, Route.CLEARED, Settlement.FINANCIAL, ScheduleMethod.LASTDAY, "LOT",
        QuantityPer.MONTH, ("C-1",), None, None, dates("2026-09-24"), rows(0), rows(1),
        numbers(1), numbers(300.0), paying(dates("2026-11-30"), 1),
    )  # fmt: skip
    history = history_on(CENTS, as_of, finals)
    prep = prepared_trades(encoded(terms, observed(terms), UNITS, counter), history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


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
    enc = encoded(
        terms_of(TOY, Settlement.FINANCIAL, TOY_PAYS),
        observed(terms_of(TOY, Settlement.FINANCIAL, TOY_PAYS)),
        UNITS,
        WorkCounter(),
    )
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
            "F27 pays on 2026-12-29, expected a day after its last observation, 2026-12-29, "
            "when its final price exists",
        ),
    ],
)
def test_payment_days_that_cannot_be_encoded_say_why(
    pays: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        encoded(
            terms_of(TOY, Settlement.FINANCIAL, pays),
            observed(terms_of(TOY, Settlement.FINANCIAL, pays)),
            UNITS,
            WorkCounter(),
        )


# --- the preparation ------------------------------------------------------------------------


def test_before_either_expiry_both_contracts_are_live_and_nothing_is_set() -> None:
    counter = WorkCounter()
    enc = encoded(terms_of(), observed(terms_of()), UNITS, WorkCounter())
    prep = prepared_trades(enc, history_on(NG, "2026-11-24", {}), counter)
    np.testing.assert_array_equal(prep.is_fixed, [False, False])
    np.testing.assert_array_equal(prep.is_settled, [False, False])
    np.testing.assert_array_equal(prep.set_amount, [0.0, 0.0])
    np.testing.assert_array_equal(prep.live_slot, [0, 1])
    np.testing.assert_array_equal(prep.live_references, [1, 2])
    np.testing.assert_array_equal(prep.reference_of_live_slot, [0, 1])
    np.testing.assert_array_equal(prep.dated_live_exposure, [160_000, -50_000])
    assert (prep.offset_unsettled, prep.set_unsettled, prep.cash) == (-330_000, 0.0, 0.0)
    assert counter.freeze().as_dict() == {"fixings_read": 0, "prepared_slots": 2}
    for array in (prep.is_fixed, prep.is_settled, prep.set_amount, prep.dated_live_exposure):
        assert not array.flags.writeable


def test_a_contract_stays_live_on_its_expiry_day_and_is_expired_the_day_after() -> None:
    enc = encoded(terms_of(), observed(terms_of()), UNITS, WorkCounter())
    on_the_day = prepared_trades(enc, history_on(NG, "2026-11-25", {}), WorkCounter())
    np.testing.assert_array_equal(on_the_day.is_fixed, [False, False])
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(NG, "2026-11-26", {"Z26": 3.22}), WorkCounter())
    assert str(refused.value) == (
        "trade 'NG-001' at row 1 on Z26 expired 2026-11-25, before valuation date 2026-11-26; "
        "a physical future after its expiry is not supported"
    )


def test_a_history_over_another_index_is_refused_whatever_its_name() -> None:
    enc = encoded(terms_of(), observed(terms_of()), UNITS, WorkCounter())
    twin = an_index()  # the same facts, another object
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(twin, "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "history is over another index, 'Henry Hub NYMEX', expected the trades', 'Henry Hub NYMEX'"
    )


def test_a_trade_on_the_schedules_first_contract_is_refused_since_nothing_prices_it() -> None:
    boundary = resolved_trades(
        FUTURE, NG, 0, Route.CLEARED, Settlement.PHYSICAL, ScheduleMethod.LASTDAY, "LOT",
        QuantityPer.MONTH, None, None, None, dates("2026-09-24"), rows(0), rows(0), numbers(1),
        numbers(3.0), None,
    )  # fmt: skip
    enc = encoded(boundary, observed(boundary), UNITS, WorkCounter())
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(NG, "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "trade at row 1 observes X26 on 2026-10-28, before the calendar begins; "
        "the schedule's first contract bounds the calendar and nothing prices it"
    )


def test_a_contract_expiring_on_a_closed_day_is_refused_when_the_batch_is_encoded() -> None:
    # A toy whose Z26 expires on Thanksgiving, which its own calendar closes: no settle will ever
    # exist for that day, so the batch is refused when it is made, before any history and
    # whatever the valuation date would have been.
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
    terms = terms_of(closed, Settlement.FINANCIAL, TOY_PAYS)
    with pytest.raises(ValueError) as refused:
        encoded(terms, observed(terms), UNITS, WorkCounter())
    assert str(refused.value) == (
        "trade 'NG-001' at row 1 observes Z26 on 2026-11-26, a day the index's market is closed; "
        "no settle exists or will"
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
    np.testing.assert_allclose(initial.dated_live_contribution, [512_000, -175_000])
    assert counter.freeze().as_dict() == {
        "encoded_components": 5,
        "encoded_observations": 5,
        "encoded_slots": 2,
        "fixings_read": 0,
        "kernel": 1,
        "live_prices_read": 2,
        "prepared_slots": 2,
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
    enc = encoded(terms_of(), observed(terms_of()), UNITS, WorkCounter())
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(enc, history, WorkCounter())
    before = (
        prep.dated_live_exposure.copy(),
        prep.delta.copy(),
        prep.offset_unsettled,
        prep.cash,
    )
    counter = WorkCounter()
    later = trade_results(prep, quoted(history, 3.21, 3.50), counter)
    assert later.mark == pytest.approx(8_600)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 2}
    assert later.prepared is prep and later.market.market_history is history
    assert later.delta is prep.delta and not later.delta.flags.writeable  # shared, never written
    np.testing.assert_array_equal(prep.dated_live_exposure, before[0])
    np.testing.assert_array_equal(prep.delta, before[1])
    assert (prep.offset_unsettled, prep.cash) == before[2:]


def test_a_market_over_another_history_is_refused_rather_than_prepared_again() -> None:
    enc = encoded(terms_of(), observed(terms_of()), UNITS, WorkCounter())
    prep = prepared_trades(enc, history_on(NG, "2026-11-24", {}), WorkCounter())
    other = history_on(NG, "2026-11-23", {})  # the same index, another valuation date
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(other, 3.20, 3.50), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'Henry Hub NYMEX', "
        "expected the one the trades were prepared against"
    )


def test_a_vector_that_stops_before_a_traded_contract_is_refused_by_the_market() -> None:
    enc = encoded(terms_of(), observed(terms_of()), UNITS, WorkCounter())
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(enc, history, WorkCounter())
    with pytest.raises(
        ValueError, match=r"^requested contract 'F27' is beyond live-price coverage"
    ):
        trade_results(prep, quoted(history, 3.20), WorkCounter())


def test_a_bilateral_batch_is_refused_until_rates_exist() -> None:
    enc = encoded(
        terms_of(route=Route.BILATERAL),
        observed(terms_of(route=Route.BILATERAL)),
        UNITS,
        WorkCounter(),
    )
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(enc, history, WorkCounter())
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(history, 3.20, 3.50), WorkCounter())
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
    enc = encoded(
        terms_of(TOY, Settlement.FINANCIAL, TOY_PAYS),
        observed(terms_of(TOY, Settlement.FINANCIAL, TOY_PAYS)),
        UNITS,
        WorkCounter(),
    )
    history = history_on(TOY, "2026-12-30", {"Z26": 3.23, "F27": 3.45})
    prep = prepared_trades(enc, history, WorkCounter())
    assert prep.live_references.size == 0 and prep.is_fixed.all()
    counter = WorkCounter()
    result = trade_results(prep, quoted(history, 3.60), counter)
    assert (result.mark, result.cash) == (pytest.approx(-8_500), pytest.approx(22_800))
    assert result.dated_live_contribution.size == 0
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 0}
    assert result.market.first_contract == 3  # G27, quoted and held by no trade


# --- the dated axis: the daily toy of dated-exposure.md ---------------------------------------
# One index quoted in USD per MMBTU with a lot of one MMBTU; X26 expiring 30 November 2026 bounds
# the calendar, Z26 expires 31 December and G27 29 January; two components on Z26, A of 60 at 70
# and B of -30 at 72, each observed on 1, 2 and 3 December with a third of its quantity, both
# paying on 5 January 2027.

DAILY = an_index(
    "TOY_DAILY",
    (("X26", "2026-11-30"), ("Z26", "2026-12-31"), ("G27", "2027-01-29")),
    ("2026-12-25", "2027-01-01"),
    lot=("unit", 1.0, "MMBTU"),
)
DAILY_DATES = dates("2026-12-01", "2026-12-02", "2026-12-03")


def daily_terms(
    lots: tuple[float, ...] = (60.0, -30.0),
    prices: tuple[float, ...] = (70.0, 72.0),
    pays: str = "2027-01-05",
) -> ResolvedTrades:
    n = len(lots)
    return resolved_trades(
        FUTURE, DAILY, 0, Route.CLEARED, Settlement.FINANCIAL, ScheduleMethod.LASTDAY, "LOT",
        QuantityPer.MONTH, None, None, None, np.repeat(day("2026-11-20"), n),
        np.arange(n, dtype=np.intp), np.ones(n, dtype=np.intp), numbers(*lots), numbers(*prices),
        paying(np.repeat(day(pays), n), n),
    )  # fmt: skip


def daily_observations(terms: ResolvedTrades, when: tuple[tuple[str, ...], ...]) -> Observations:
    """Each component observed on its own days, equal weights."""
    component = np.concatenate([np.full(len(days), k) for k, days in enumerate(when)])
    date = np.concatenate([dates(*days) for days in when])
    weight = np.concatenate([np.full(len(days), 1 / len(days)) for days in when])
    return observations(component.astype(np.intp), date, weight, terms.contract.size)


def daily_history(as_of: str, settles: dict[str, float]) -> MarketHistory:
    """The toy's history valued on that day: 70 on every fixed business day, the settles given
    standing on their days."""
    cal = calendar(valuation_date(day(as_of), 0.5), DAILY)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    prices = np.full(priced.size, 70.0)
    for text, price in settles.items():
        prices[priced == day(text)] = price
    return market_history(cal, futures_fixings(priced[::-1].copy(), prices[::-1].copy(), DAILY))


SETTLES = {"2026-12-01": 71.0, "2026-12-02": 75.0, "2026-12-03": 73.0}


def daily_evaluated(
    as_of: str,
    lots: tuple[float, ...] = (60.0, -30.0),
    prices: tuple[float, ...] = (70.0, 72.0),
) -> tuple[TradeResults, WorkCounter]:
    terms = daily_terms(lots, prices)
    counter = WorkCounter()
    enc = encoded(terms, daily_observations(terms, (DAILY_DATES_TEXT,) * len(lots)), UNITS, counter)
    history = daily_history(as_of, SETTLES)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, daily_market(history), counter), counter


def daily_market(history: MarketHistory) -> Market:
    """Z26 at 74 and G27 at 74.5, from whichever is prompt on the valuation day."""
    cal = history.calendar
    prompt = int(cal.contract[cal.first_unfixed])
    return quoted(history, *(74.0, 74.5)[prompt - 1 :])


DAILY_DATES_TEXT = ("2026-12-01", "2026-12-02", "2026-12-03")


def test_the_daily_toy_encodes_three_slots_off_one_contract_for_two_components() -> None:
    terms = daily_terms()
    counter = WorkCounter()
    enc = encoded(terms, daily_observations(terms, (DAILY_DATES_TEXT,) * 2), UNITS, counter)
    np.testing.assert_array_equal(enc.quantity, [60, -30])
    np.testing.assert_array_equal(enc.offset, [-4_200, 2_160])
    np.testing.assert_array_equal(enc.groups, [1])
    np.testing.assert_array_equal(enc.offset_of_group, [-2_040])
    np.testing.assert_array_equal(enc.slot_date, DAILY_DATES)
    np.testing.assert_array_equal(enc.slot_group, [0, 0, 0])
    np.testing.assert_array_equal(enc.slot_reference, [1, 1, 1])  # Z26 prices each December day
    np.testing.assert_allclose(enc.slot_exposure, [10, 10, 10])  # 20 of A and -10 of B a day
    np.testing.assert_array_equal(enc.slot_of_observation, [0, 1, 2, 0, 1, 2])
    np.testing.assert_array_equal(enc.references, [1])
    assert enc.payment_date is not None
    np.testing.assert_array_equal(enc.payment_date, dates("2027-01-05"))
    assert counter.freeze().as_dict() == {
        "encoded_components": 2,
        "encoded_observations": 6,
        "encoded_slots": 3,
    }


@pytest.mark.parametrize(
    ("as_of", "live", "set_amount", "live_amount", "mark", "delta", "fixings", "quotes"),
    [
        ("2026-12-01", [10, 10, 10], 0, 2_220, 180, 30, 0, 1),
        ("2026-12-02", [0, 10, 10], 710, 1_480, 150, 20, 1, 1),
        ("2026-12-03", [0, 0, 10], 1_460, 740, 160, 10, 2, 1),
        ("2026-12-04", [0, 0, 0], 2_190, 0, 150, 0, 3, 0),
    ],
    ids=["none fixed", "1 Dec fixed", "2 Dec fixed", "all fixed, unpaid"],
)
def test_the_daily_toy_marks_as_the_page_says_date_by_date(
    as_of: str,
    live: list[float],
    set_amount: float,
    live_amount: float,
    mark: float,
    delta: float,
    fixings: int,
    quotes: int,
) -> None:
    result, counter = daily_evaluated(as_of)
    prep = result.prepared
    np.testing.assert_allclose(prep.dated_live_exposure, live)
    assert prep.set_unsettled == pytest.approx(set_amount)
    assert result.dated_live_contribution.sum() == pytest.approx(live_amount)
    np.testing.assert_allclose(result.dated_live_contribution, [x * 74 for x in live if x])
    assert (result.mark, result.cash) == (pytest.approx(mark), 0.0)
    np.testing.assert_allclose(result.delta, [delta])
    assert result.delta_total == pytest.approx(delta) and result.codes() == ("Z26",)
    counts = counter.freeze()
    assert (counts["fixings_read"], counts["live_prices_read"]) == (fixings, quotes)
    assert counts["prepared_slots"] == 3 and counts["kernel"] == 1
    assert prep.history.calendar.valuation_date.as_of == day(as_of)


def test_the_daily_toy_pays_on_its_day_and_the_whole_amount_becomes_cash() -> None:
    paid, _ = daily_evaluated("2027-01-05")
    assert (paid.mark, paid.cash) == (0.0, pytest.approx(150))
    assert paid.dated_live_contribution.size == 0 and paid.delta_total == 0.0
    unpaid, _ = daily_evaluated("2027-01-04")
    assert (unpaid.mark, unpaid.cash) == (pytest.approx(150), 0.0)


def test_the_daily_toy_equals_its_two_singletons_summed() -> None:
    whole, _ = daily_evaluated("2026-12-02")
    a, _ = daily_evaluated("2026-12-02", (60.0,), (70.0,))
    assert a.mark == pytest.approx(-4_200 + 20 * 71 + 2 * 20 * 74)
    assert whole.mark == pytest.approx(150)
    # B alone: its own lots and price, through the same path.
    terms = daily_terms((-30.0,), (72.0,))
    enc = encoded(terms, daily_observations(terms, (DAILY_DATES_TEXT,)), UNITS, WorkCounter())
    history = daily_history("2026-12-02", SETTLES)
    b = trade_results(
        prepared_trades(enc, history, WorkCounter()), daily_market(history), WorkCounter()
    )
    assert b.mark == pytest.approx(2_160 - 10 * 71 - 2 * 10 * 74)
    assert a.mark + b.mark == pytest.approx(whole.mark)


def test_offsetting_dates_keep_their_slots_though_the_contract_delta_nets_to_zero() -> None:
    # +10 on 1 December and -10 on 2 December, both projecting off Z26 at 74, no offset: live
    # value and contract delta net to zero; after 1 December fixes at 71 the mark is -30 and the
    # live delta -10.
    terms = daily_terms((10.0, -10.0), (0.0, 0.0))
    enc = encoded(
        terms, daily_observations(terms, (("2026-12-01",), ("2026-12-02",))), UNITS, WorkCounter()
    )
    np.testing.assert_allclose(enc.slot_exposure, [10, -10])
    np.testing.assert_array_equal(enc.slot_date, dates("2026-12-01", "2026-12-02"))
    before = daily_history("2026-12-01", SETTLES)
    live = trade_results(
        prepared_trades(enc, before, WorkCounter()), daily_market(before), WorkCounter()
    )
    assert live.mark == pytest.approx(0.0) and live.delta_total == pytest.approx(0.0)
    np.testing.assert_allclose(live.dated_live_contribution, [740, -740])
    after = daily_history("2026-12-02", SETTLES)
    fixed = trade_results(
        prepared_trades(enc, after, WorkCounter()), daily_market(after), WorkCounter()
    )
    assert fixed.mark == pytest.approx(-30)
    np.testing.assert_allclose(fixed.delta, [-10])
    np.testing.assert_allclose(fixed.dated_live_contribution, [-740])


def test_the_daily_toys_results_read_back_slot_by_slot_with_the_contracts_delta_named() -> None:
    # The review's case: after 1 December fixes, the slots' live exposure is 0, 10, 10, their
    # contributions 0, 740, 740, and Z26's delta 20 stands beside each as the contract's.
    from goosedove.excel.utilities import shown

    result, _ = daily_evaluated("2026-12-02")
    table = shown(result)
    assert table.texts[:6] == (
        "contract_code",
        "observation_date",
        "is_fixed",
        "live_exposure",
        "live_contribution",
        "contract_delta",
    )
    np.testing.assert_array_equal(table.numeric_slots[2:, 2], [1.0, 0.0, 0.0])  # is_fixed
    np.testing.assert_allclose(table.numeric_slots[2:, 3], [0.0, 10.0, 10.0])
    np.testing.assert_allclose(table.numeric_slots[2:, 4], [0.0, 740.0, 740.0])
    np.testing.assert_allclose(table.numeric_slots[2:, 5], [20.0, 20.0, 20.0])


def test_a_tick_on_the_daily_toy_reads_one_quote_and_gathers_it_onto_the_live_slots() -> None:
    terms = daily_terms()
    enc = encoded(terms, daily_observations(terms, (DAILY_DATES_TEXT,) * 2), UNITS, WorkCounter())
    history = daily_history("2026-12-02", SETTLES)
    prep = prepared_trades(enc, history, WorkCounter())
    counter = WorkCounter()
    later = trade_results(prep, quoted(history, 75.0, 74.5), counter)
    assert later.mark == pytest.approx(-2_040 + 710 + 2 * 10 * 75)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 1}
    assert later.delta is prep.delta


def test_an_observation_of_another_contract_than_the_days_is_refused_as_unsupported() -> None:
    # A component on G27 observed on 1 December, a day Z26 prices: the history holds no G27
    # settle for it, so it is refused rather than priced off Z26.
    terms = resolved_trades(
        FUTURE, DAILY, 0, Route.CLEARED, Settlement.FINANCIAL, ScheduleMethod.LASTDAY, "LOT",
        QuantityPer.MONTH, ("G-1",), None, None, dates("2026-11-20"), rows(0), rows(2), numbers(1),
        numbers(70.0), paying(dates("2027-02-02"), 1),
    )  # fmt: skip
    with pytest.raises(ValueError) as refused:
        encoded(terms, daily_observations(terms, (("2026-12-01",),)), UNITS, WorkCounter())
    assert str(refused.value) == (
        "trade 'G-1' at row 1 observes G27 on 2026-12-01, a day Z26 prices; an observation of a "
        "contract other than the day's pricing contract has no settle in a futures history, "
        "not supported"
    )
    with pytest.raises(ValueError) as refused:
        encoded(terms, daily_observations(terms, (("2027-02-01",),)), UNITS, WorkCounter())
    assert str(refused.value) == (
        "trade 'G-1' at row 1 observes 2027-02-01, after the schedule's last expiry, 2027-01-29; "
        "nothing prices it"
    )


@pytest.mark.parametrize(
    ("closed_day", "why"),
    [("2026-12-05", "a Saturday"), ("2026-12-25", "a holiday the index lists")],
)
def test_an_observation_on_a_closed_day_is_refused_before_it_could_fix(
    closed_day: str, why: str
) -> None:
    # The review's case: ten units at 70 observing Saturday 5 December would have marked 40 with
    # delta 10 on 1 December off a quote of 74, and failed only once the day had passed. It fails
    # at creation instead, and the same for a holiday, with no history in sight.
    terms = daily_terms((10.0,), (70.0,))
    with pytest.raises(ValueError) as refused:
        encoded(terms, daily_observations(terms, ((closed_day,),)), UNITS, WorkCounter())
    assert str(refused.value) == (
        f"trade at row 1 observes Z26 on {closed_day}, a day the index's market is closed; "
        "no settle exists or will"
    ), why


def test_a_payment_before_the_last_observation_is_refused() -> None:
    terms = daily_terms(pays="2026-12-03")
    with pytest.raises(ValueError) as refused:
        encoded(terms, daily_observations(terms, (DAILY_DATES_TEXT,) * 2), UNITS, WorkCounter())
    assert str(refused.value) == (
        "Z26 pays on 2026-12-03, expected a day after its last observation, 2026-12-03, "
        "when its final price exists"
    )


@pytest.mark.parametrize(
    ("component", "date", "weight", "message"),
    [
        (
            rows(0, 0),
            dates("2026-12-01"),
            numbers(0.5, 0.5),
            "date has 1, expected 2, one per observation",
        ),
        (
            rows(),
            dates(),
            numbers(),
            "component has 0 observations, expected at least one per component",
        ),
        (
            rows(0, 2),
            dates("2026-12-01", "2026-12-02"),
            numbers(1, 1),
            "observation 2 is of component 2, expected a component, 0 to 1",
        ),
        (
            rows(1, 0),
            dates("2026-12-01", "2026-12-02"),
            numbers(1, 1),
            "observation 2 is of component 0, after one of component 1; expected component order",
        ),
        (
            rows(0, 0, 1),
            dates("2026-12-02", "2026-12-02", "2026-12-01"),
            numbers(0.5, 0.5, 1),
            "observation 2 of component 0 is on 2026-12-02, expected a day after 2026-12-02, "
            "the observation before it",
        ),
        (
            rows(0, 0),
            dates("2026-12-01", "2026-12-02"),
            numbers(0.5, 0.5),
            "component 1 has no observation, expected at least one",
        ),
        (
            rows(0, 1),
            dates("2026-12-01", "2026-12-01"),
            numbers(1, 0),
            "weight 2 is 0.0, expected a positive share",
        ),
        (
            rows(0, 0, 1),
            dates("2026-12-01", "2026-12-02", "2026-12-01"),
            numbers(0.5, 0.6, 1),
            "the weights of component 0 sum to 1.1, expected 1, the whole quantity shared out",
        ),
    ],
)
def test_observations_that_cannot_be_made_say_why(
    component: NDArray[np.intp],
    date: NDArray[np.datetime64],
    weight: NDArray[np.float64],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        observations(component, date, weight, 2)


def test_observations_own_frozen_copies_and_a_seventh_shared_seven_times_is_one() -> None:
    component, date, weight = rows(0, 0), dates("2026-12-01", "2026-12-02"), numbers(0.5, 0.5)
    made = observations(component, date, weight, 1)
    weight[0] = 9.0
    assert made.weight[0] == 0.5 and not made.weight.flags.writeable
    sevenths = observations(
        np.zeros(7, dtype=np.intp),
        dates(*[f"2026-12-{d:02d}" for d in range(1, 8)]),
        np.full(7, 1 / 7),
        1,
    )
    assert sevenths.component.size == 7


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
    def valued(selected: list[tuple[int, int, float]]) -> TradeResults:
        n = len(selected)
        terms = resolved_trades(
            FUTURE, NG, 0, Route.CLEARED, Settlement.PHYSICAL, ScheduleMethod.LASTDAY, "LOT",
            QuantityPer.MONTH, None, None, None, np.repeat(day("2026-09-24"), n),
            np.arange(n, dtype=np.intp), rows(*(c for c, _, _ in selected)),
            numbers(*(q for _, q, _ in selected)), numbers(*(p for _, _, p in selected)), None,
        )  # fmt: skip
        history = history_on(NG, "2026-11-24", {})
        prep = prepared_trades(
            encoded(terms, observed(terms), UNITS, WorkCounter()), history, WorkCounter()
        )
        return trade_results(prep, quoted(history, *quotes), WorkCounter())

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
