"""The trade kernel on the NG example and the toy lifecycle of
docs/engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md, and on the
dated axis of dated-exposure.md: the resolved terms and their rules, the observations and theirs,
the static encoding on dated slots, the preparation against a real history and the evaluation
against a real market, every hand answer of the pages pinned, the batch equal to its singletons
summed, duplicates counting, a fixed batch inside a live market, an expired physical component
refused, the daily toy's four states and the offsetting dates, and nothing redone on a tick."""

import itertools
import re
from typing import Any, NamedTuple, cast

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
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.futures_fixings import futures_fixings
from goosedove.market_data.iferc_fixings import iferc_fixings
from goosedove.market_data.price_vector import price_vector
from goosedove.trades.encoding import encoded
from goosedove.trades.evaluation import TradeResults, trade_results
from goosedove.trades.observations import Observations, observations, observed
from goosedove.trades.preparation import PreparedTrades, prepared_trades
from goosedove.trades.resolution import month_bounds, schedule_months
from goosedove.trades.terms import (
    BASES,
    METHODS,
    PaymentTerms,
    QuantityPer,
    ResolvedTrades,
    Route,
    ScheduleMethod,
    Settlement,
    marketing_reserves,
    named_trade,
    one_choice,
    resolved_trades,
    whole_trade_ids,
)


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


def rows(*values: int) -> NDArray[np.intp]:
    return np.array(values, dtype=np.intp)


def ids(*values: int) -> NDArray[np.int64]:
    """Trade IDs as the kernel holds them, whole numbers of at most 15 digits."""
    return np.array(values, dtype=np.int64)


def numbers(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def months_of(ix: Index) -> NDArray[np.int64]:
    """The schedule's months as the resolution reads them once, for the observations builder."""
    return schedule_months(cast(FuturesSchedule, ix.schedule))


def bounds_of(
    ix: Index, contract: NDArray[np.intp]
) -> tuple[NDArray[np.datetime64], NDArray[np.datetime64]]:
    """The first and the last day of each component's contract month, the days a whole-month
    component covers, as the resolution hands the kernel."""
    return month_bounds(months_of(ix)[contract])


def observed_of(terms: ResolvedTrades) -> Observations:
    """The observations the terms' schedule method gives them, as resolution makes them."""
    return observed(
        terms.schedule_method[terms.occurrence],
        terms.index,
        terms.contract,
        terms.start_date,
        terms.end_date,
        terms.named,
    )


def spec(occurrences: int, row: int = 0) -> NDArray[np.intp]:
    """The specification row every occurrence counts, as the kernel holds the selection."""
    return np.full(occurrences, row, dtype=np.intp)


def picks(
    method: ScheduleMethod, basis: QuantityPer, occurrences: int
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """One method and one basis for every occurrence, the kernel's two selections."""
    return one_choice(METHODS, method, occurrences), one_choice(BASES, basis, occurrences)


def by(method: ScheduleMethod, components: int) -> NDArray[np.intp]:
    """One method for every component, as observed takes them."""
    return one_choice(METHODS, method, components)


def unlabeled(k: int) -> str:
    """Component k's trade when observed is called on bare arrays, each component a row of its
    own with no label, as named_trade words it: `trade at row 1`."""
    return named_trade(None, k)


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
    reporting_lot: str | None = "",
) -> Index:
    # The one specification is the reporting lot unless another name is given; None makes
    # an index without one, as an index that only builds markets is made.
    codes = tuple(code for code, _ in contracts)
    schedule = futures_schedule(codes, dates(*(expiry for _, expiry in contracts)), None)
    spec_name, lot_size, lot_unit = lot
    return index(
        name,
        f"{name} index",
        schedule,
        index_conventions(quote[0], quote[1], "USD", measure[0], measure[1], UNITS),
        contract_specifications(
            (spec_name,), numbers(lot_size), (lot_unit,), numbers(0.0), numbers(0.0), UNITS
        ),
        holiday_calendar(dates(*holidays)),
        spec_name if reporting_lot == "" else reporting_lot,
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
TRADE_IDS = ids(1001, 1002, 1003, 1004, 1001)
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
    trade_ids: NDArray[np.int64] | None = TRADE_IDS,
) -> ResolvedTrades:
    """The page's five rows resolved against an index, or the rows a slice keeps."""
    occurrences = TRADE_DATES[keep].size
    return resolved_trades(
        FIXED_FLOAT,
        ix,
        spec(occurrences),
        route,
        settlement,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, occurrences),
        None if trade_ids is None else trade_ids[keep],
        None,
        None,
        TRADE_DATES[keep],
        np.arange(occurrences, dtype=np.intp),
        CONTRACT[keep],
        LOTS[keep],
        *bounds_of(ix, CONTRACT[keep]),
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
        observed_of(terms_of(ix, settlement, pays, keep)),
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
        FIXED_FLOAT, TOY, spec(5), Route.CLEARED, Settlement.FINANCIAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 5), TRADE_IDS, ("CME Clearing",) * 5,
        None, TRADE_DATES,
        np.arange(5, dtype=np.intp), CONTRACT, lots, *bounds_of(TOY, CONTRACT), FIXED_PRICE,
        PaymentTerms(lags, (PAYMENT_CALENDAR,) * 5, pays),
    )  # fmt: skip
    lots[0], pays[0], lags[0] = 99.0, day("2030-01-01"), 9  # the arrays passed, changed after
    assert terms.quantity[0] == 10.0 and terms.schedule is TOY.schedule
    np.testing.assert_array_equal(terms.covered_days, [31, 31, 31, 31, 31])  # December, January
    np.testing.assert_array_equal(terms.component_quantity, terms.quantity)  # month: as entered
    assert terms.payment is not None and terms.payment.date[0] == day("2026-11-30")
    assert terms.payment.lag_days[0] == 2 and terms.payment.calendar[0] is PAYMENT_CALENDAR
    for column in (
        terms.trade_dates,
        terms.occurrence,
        terms.contract,
        terms.quantity,
        terms.start_date,
        terms.end_date,
        terms.covered_days,
        terms.component_quantity,
    ):
        assert not column.flags.writeable
    assert not terms.payment.date.flags.writeable and not terms.payment.lag_days.flags.writeable
    assert terms.trade_dates.dtype == np.dtype("datetime64[D]")
    assert terms.named(4) == "trade 1001 at row 5"
    assert terms_of(trade_ids=None).named(2) == "trade at row 3"
    assert terms.instrument is FIXED_FLOAT and terms.clearing_house == ("CME Clearing",) * 5
    assert terms.broker is None


GAS_DAILY = index(
    "daily",
    "Sample Gas Daily index",
    gas_daily_schedule(("c0",), dates("2026-01-01"), dates("2026-01-31")),
    NG.conventions,
    NG.specifications,
    None,
    None,
    UNITS,
)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {"ix": GAS_DAILY},
            "index is a Gas Daily index, expected a futures or an IFERC index for a fixed_float",
        ),
        (
            {"specification": spec(5, 1)},
            "specification row 1 is 1, expected a row of the index's specifications, 0 to 0",
        ),
        (
            {"specification": spec(4)},
            "specification has 4 rows, expected 5, one per occurrence",
        ),
        (
            {"schedule_method": np.full(5, 4, dtype=np.intp)},
            "schedule_method row 1 is 4, expected a method, its position among METHODS, 0 to 3",
        ),
        (
            {"quantity_per": one_choice(BASES, QuantityPer.MONTH, 2)},
            "quantity_per has 2 rows, expected 5, one per occurrence",
        ),
        (
            {"schedule_method": np.array([0, 2, 1, 0, 0], dtype=np.intp)},
            "settlement_method is 'physical', expected 'financial' with the last3day method of "
            "trade 1002 at row 2; a last3day future is cash settled on the average of its last "
            "three pricing days",
        ),
        (
            {"trade_dates": dates()},
            "trade_dates has 0 dates, expected at least 1, one per occurrence",
        ),
        (
            {"trade_ids": ids(1, 2)},
            "trade_ids has 2 ids, expected 5, one per occurrence",
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
            {
                "occurrence": rows(),
                "contract": rows(),
                "quantity": numbers(),
                "fixed_price": numbers(),
            },
            "occurrence has 0 rows, expected at least 1, one per component",
        ),
        (
            {"contract": rows(1, 1)},
            "contract has 2 rows, expected 5, one per component",
        ),
        (
            {"quantity": numbers(1.0)},
            "quantity has 1 rows, expected 5, one per component",
        ),
        (
            {"occurrence": rows(0, 1, 2, 3, 5)},
            "occurrence row 5 is 5, expected an occurrence, 0 to 4",
        ),
        (
            {"occurrence": rows(0, 1, 2, 2, 3)},
            "trade 1001 at row 5 has no component, expected at least one",
        ),
        (
            {"contract": rows(1, 1, 2, 3, 1)},
            "contract row 4 is 3, expected a row of the schedule, 0 to 2",
        ),
        (
            {"quantity": numbers(10, -4, 7.5, -12, 10)},
            "quantity of trade 1003 at row 3 is 7.5, expected a whole number",
        ),
        (
            {"quantity": numbers(10, -4, np.nan, -12, 10)},
            "quantity of trade 1003 at row 3 is nan, expected a whole number",
        ),
        (
            {"quantity": numbers(10, -4, np.inf, -12, 10)},
            "quantity of trade 1003 at row 3 is inf, expected a whole number",
        ),
        (
            {"fixed_price": numbers(3.1, 3.15, 3.4, np.inf, 3.1)},
            "fixed_price of trade 1004 at row 4 is inf, expected a finite price",
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
        "instrument": FIXED_FLOAT,
        "ix": NG,
        "specification": spec(5),
        "route": Route.CLEARED,
        "settlement": Settlement.PHYSICAL,
        "schedule_method": one_choice(METHODS, ScheduleMethod.LASTDAY, 5),
        "quantity_per": one_choice(BASES, QuantityPer.MONTH, 5),
        "trade_ids": TRADE_IDS,
        "clearing_house": None,
        "broker": None,
        "trade_dates": TRADE_DATES,
        "occurrence": rows(0, 1, 2, 3, 4),
        "contract": CONTRACT,
        "quantity": LOTS,
        "start_date": bounds_of(NG, CONTRACT)[0],
        "end_date": bounds_of(NG, CONTRACT)[1],
        "fixed_price": FIXED_PRICE,
        "payment": None,
    }
    given_terms.update(change)
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        resolved_trades(*given_terms.values())


# --- the static encoding --------------------------------------------------------------------


def test_the_ng_rows_encode_as_the_page_says() -> None:
    counter = WorkCounter()
    enc = encoded(terms_of(), observed_of(terms_of()), UNITS, counter)
    np.testing.assert_array_equal(enc.quote_quantity, [100_000, -40_000, 70_000, -120_000, 100_000])
    np.testing.assert_array_equal(
        enc.coefficient, enc.quote_quantity
    )  # dollars quoted, dollars paid
    np.testing.assert_array_equal(enc.offset, [-310_000, 126_000, -238_000, 402_000, -310_000])
    np.testing.assert_array_equal(enc.group_contract, [1, 2])
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
    assert enc.named_slot(0) == "trade 1001 at row 1 on 2026-11-25, a day Z26 prices"
    assert counter.freeze().as_dict() == {
        "encoded_components": 5,
        "encoded_groups": 2,
        "encoded_observations": 5,
        "encoded_slots": 2,
        "reserved_components": 5,
    }
    for array in (
        enc.quote_quantity,
        enc.offset,
        enc.group_contract,
        enc.slot_exposure,
        enc.offset_of_group,
    ):
        assert not array.flags.writeable


def test_a_duplicate_occurrence_adds_its_exposure_twice() -> None:
    whole = encoded(terms_of(), observed_of(terms_of()), UNITS, WorkCounter())
    without = encoded(
        terms_of(keep=slice(0, 4)), observed_of(terms_of(keep=slice(0, 4))), UNITS, WorkCounter()
    )
    assert whole.slot_exposure[0] - without.slot_exposure[0] == 100_000
    assert whole.offset_of_group[0] - without.offset_of_group[0] == -310_000


def test_a_lot_in_another_unit_than_the_quote_is_converted_once() -> None:
    # Quoted in USD per gallon, a lot of 1,000 barrels: 42,000 gallons a lot.
    crude = an_index(
        "crude", quote=("USD", "GAL"), measure=("VOLUME", "BBL"), lot=("NYMEX", 1_000.0, "BBL")
    )
    enc = encoded(terms_of(crude), observed_of(terms_of(crude)), UNITS, WorkCounter())
    np.testing.assert_allclose(enc.quote_quantity, LOTS * 42_000)
    np.testing.assert_allclose(enc.offset, -LOTS * 42_000 * FIXED_PRICE)


def test_a_price_in_cents_settles_in_dollars() -> None:
    cents = an_index("cents", quote=("CENT", "MMBTU"))
    enc = encoded(terms_of(cents), observed_of(terms_of(cents)), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.quote_quantity, LOTS * 10_000)  # MMBTU, the physical quantity
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
        FIXED_FLOAT, CENTS, spec(1), Route.CLEARED, Settlement.FINANCIAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 1), ids(1), None, None,
        dates("2026-09-24"), rows(0), rows(1),
        numbers(1), *bounds_of(CENTS, rows(1)), numbers(300.0), paying(dates("2026-11-30"), 1),
    )  # fmt: skip
    history = history_on(CENTS, as_of, finals)
    prep = prepared_trades(encoded(terms, observed_of(terms), UNITS, counter), history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


@pytest.mark.parametrize(
    ("as_of", "finals", "quotes", "mark", "cash", "delta"),
    [
        ("2026-11-24", {}, (300.0, 350.0, 360.0), 0, 0, 1),
        ("2026-11-24", {}, (310.0, 350.0, 360.0), 1_000, 0, 1),
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
    np.testing.assert_allclose(result.price_sensitivity, [100 * delta])  # 100 dollars a cent a lot
    assert result.lot_delta_total == pytest.approx(delta)
    assert result.price_sensitivity_unit == "USD per CENT/MMBTU" and result.currency == "USD"
    assert result.lot_unit == "lots of NYMEX NG (10000 MMBTU)"


# Quoted in dollars and settled in cents, the other way round from CENTS: four rows on the toy's
# four contracts, a strip among them, valued live on 20 November. By hand, in dollars: Z26's
# six lots at 3.10 against 3.20 make 6,000; F27's two lots sold at 3.40 against 3.50 make
# -2,000; the strip's lot sold at 3.55 makes +500 on F27 against 3.50 and -1,000 on G27 against
# 3.65. The mark is 3,500 dollars, 350,000 cents, and a dollar's move is 100 cents per MMBTU of
# exposure: the coefficient is the quote quantity times 100, the delta 6,000,000, -3,000,000 and
# -1,000,000 cents per dollar per MMBTU, and the unit names both currencies.
CENT_SETTLED = index(
    "cents settled",
    "Gas settled in cents",
    futures_schedule(
        ("X26", "Z26", "F27", "G27"),
        dates("2026-10-28", "2026-11-25", "2026-12-29", "2027-01-27"),
        None,
    ),
    index_conventions("USD", "MMBTU", "CENT", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("NG",), numbers(10_000.0), ("MMBTU",), numbers(0.0), numbers(0.0), UNITS
    ),
    holiday_calendar(dates("2026-11-26", "2026-12-25", "2027-01-01")),
    "NG",
    UNITS,
)


def test_a_price_in_dollars_settles_in_cents_with_the_unit_naming_both() -> None:
    terms = resolved_trades(
        FIXED_FLOAT, CENT_SETTLED, spec(4), Route.CLEARED, Settlement.PHYSICAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 4), ids(1, 2, 3, 4), None, None,
        dates(*["2026-09-24"] * 4),
        rows(0, 1, 2, 2, 3), rows(1, 2, 2, 3, 1), numbers(3, -2, -1, -1, 3),
        *bounds_of(CENT_SETTLED, rows(1, 2, 2, 3, 1)), numbers(3.10, 3.40, 3.55, 3.55, 3.10), None,
    )  # fmt: skip
    counter = WorkCounter()
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    np.testing.assert_array_equal(enc.quote_quantity, [30_000, -20_000, -10_000, -10_000, 30_000])
    np.testing.assert_allclose(enc.coefficient, enc.quote_quantity * 100)
    history = history_on(CENT_SETTLED, "2026-11-20", {})
    prep = prepared_trades(enc, history, counter)
    result = trade_results(prep, quoted(history, 3.20, 3.50, 3.65), counter)
    assert result.mark == pytest.approx(350_000) and result.cash == 0
    np.testing.assert_allclose(result.price_sensitivity, [6_000_000, -3_000_000, -1_000_000])
    assert result.lot_delta_total == pytest.approx(2)  # a lot is 1,000,000 cents a dollar
    assert result.codes() == ("Z26", "F27", "G27")
    assert result.price_sensitivity_unit == "CENT per USD/MMBTU" and result.currency == "CENT"
    assert result.lot_unit == "lots of NG (10000 MMBTU)"


# Fees are reserves, outside value: the index's brokerage and clearing rates per lot change no
# offset, no mark and no delta, the owner's decision the valuation pages record.
def test_fees_per_lot_are_reserves_and_move_no_value() -> None:
    with_fees = index(
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        NG.schedule,
        NG.conventions,
        contract_specifications(
            ("NYMEX NG",), numbers(10_000.0), ("MMBTU",), numbers(12.5), numbers(3.75), UNITS
        ),
        NG.holiday_calendar,
        "NYMEX NG",
        UNITS,
    )
    plain, _ = evaluated(NG, "2026-11-24", {}, (3.20, 3.50))
    charged, _ = evaluated(with_fees, "2026-11-24", {}, (3.20, 3.50))
    assert charged.mark == pytest.approx(plain.mark) == pytest.approx(7_000)
    np.testing.assert_array_equal(charged.price_sensitivity, plain.price_sensitivity)
    np.testing.assert_array_equal(charged.price_sensitivity, [160_000, -50_000])
    np.testing.assert_array_equal(charged.prepared.encoded.offset, plain.prepared.encoded.offset)


def test_a_financial_settlement_groups_each_contract_by_its_payment_day() -> None:
    # Paying as the toy pays, one day per contract, the five rows make two groups, Z26 and F27;
    # NG-002 paying a day after the other Z26 rows makes Z26 two groups, the earlier day first,
    # each with its own offset and its own slot on the one expiry day, while the delta axis
    # holds Z26 once.
    terms = terms_of(TOY, Settlement.FINANCIAL, TOY_PAYS)
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    assert enc.payment_date is not None
    np.testing.assert_array_equal(enc.group_contract, [1, 2])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-11-30", "2026-12-31"))
    assert not enc.payment_date.flags.writeable
    pays = dates("2026-11-30", "2026-12-01", "2026-12-31", "2026-12-31", "2026-11-30")
    split = terms_of(TOY, Settlement.FINANCIAL, pays)
    counter = WorkCounter()
    enc = encoded(split, observed_of(split), UNITS, counter)
    assert enc.payment_date is not None
    np.testing.assert_array_equal(enc.group_contract, [1, 1, 2])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-11-30", "2026-12-01", "2026-12-31"))
    np.testing.assert_array_equal(enc.group_of_component, [0, 1, 2, 2, 0])
    np.testing.assert_array_equal(enc.offset_of_group, [-620_000, 126_000, 164_000])
    np.testing.assert_array_equal(enc.slot_group, [0, 1, 2])
    np.testing.assert_array_equal(enc.slot_date, dates("2026-11-25", "2026-11-25", "2026-12-29"))
    np.testing.assert_array_equal(enc.slot_reference, [1, 1, 2])
    np.testing.assert_array_equal(enc.slot_exposure, [200_000, -40_000, -50_000])
    np.testing.assert_array_equal(enc.slot_of_observation, [0, 1, 2, 2, 0])
    np.testing.assert_array_equal(enc.references, [1, 2])
    np.testing.assert_array_equal(enc.reference_of_slot, [0, 0, 1])
    assert enc.named_slot(1) == "trade 1002 at row 2 on 2026-11-25, a day Z26 prices"
    assert counter.freeze()["encoded_groups"] == 3


def test_a_payment_on_or_before_the_groups_last_observation_is_refused() -> None:
    pays = dates("2026-11-30", "2026-11-30", "2026-12-29", "2026-12-29", "2026-11-30")
    terms = terms_of(TOY, Settlement.FINANCIAL, pays)
    with pytest.raises(ValueError) as refused:
        encoded(terms, observed_of(terms), UNITS, WorkCounter())
    assert str(refused.value) == (
        "F27 pays on 2026-12-29, expected a day after its last observation, 2026-12-29, when its "
        "final price exists"
    )


# --- the preparation ------------------------------------------------------------------------


def test_before_either_expiry_both_contracts_are_live_and_nothing_is_set() -> None:
    counter = WorkCounter()
    enc = encoded(terms_of(), observed_of(terms_of()), UNITS, WorkCounter())
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
    enc = encoded(terms_of(), observed_of(terms_of()), UNITS, WorkCounter())
    on_the_day = prepared_trades(enc, history_on(NG, "2026-11-25", {}), WorkCounter())
    np.testing.assert_array_equal(on_the_day.is_fixed, [False, False])
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(NG, "2026-11-26", {"Z26": 3.22}), WorkCounter())
    assert str(refused.value) == (
        "trade 1001 at row 1 on Z26 expired 2026-11-25, before valuation date 2026-11-26; "
        "a physical fixed_float after its expiry is not supported"
    )


def test_a_history_over_another_index_is_refused_whatever_its_name() -> None:
    enc = encoded(terms_of(), observed_of(terms_of()), UNITS, WorkCounter())
    twin = an_index()  # the same facts, another object
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(twin, "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "history is over another index, 'Henry Hub NYMEX', expected the trades', 'Henry Hub NYMEX'"
    )


def test_a_trade_on_the_schedules_first_contract_is_refused_since_nothing_prices_it() -> None:
    boundary = resolved_trades(
        FIXED_FLOAT, NG, spec(1), Route.CLEARED, Settlement.PHYSICAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 1), None, None, None,
        dates("2026-09-24"), rows(0), rows(0), numbers(1),
        *bounds_of(NG, rows(0)), numbers(3.0), None,
    )  # fmt: skip
    enc = encoded(boundary, observed_of(boundary), UNITS, WorkCounter())
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(NG, "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "trade at row 1 observes 2026-10-28, before the calendar begins on 2026-10-29; the "
        "schedule's first contract, X26, bounds the calendar and nothing prices its days"
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
        encoded(terms, observed_of(terms), UNITS, WorkCounter())
    assert str(refused.value) == (
        "trade 1001 at row 1 observes 2026-11-26, a day the index's market is closed; "
        "no settle exists or will"
    )


# --- the evaluation: the NG example ---------------------------------------------------------


def test_the_five_ng_rows_mark_7000_then_8600_on_the_tick() -> None:
    initial, counter = evaluated(NG, "2026-11-24", {}, (3.20, 3.50))
    assert (initial.mark, initial.cash) == (7_000, 0)
    np.testing.assert_array_equal(initial.price_sensitivity, [160_000, -50_000])
    assert initial.lot_delta_total == 11 and initial.dv01 == 0.0  # lots of ten thousand
    assert initial.price_sensitivity_unit == "USD per USD/MMBTU"
    assert initial.codes() == ("Z26", "F27") and initial.currency == "USD"
    assert initial.route is Route.CLEARED and initial.as_of == day("2026-11-24")
    np.testing.assert_allclose(initial.dated_live_contribution, [512_000, -175_000])
    assert counter.freeze().as_dict() == {
        "encoded_components": 5,
        "encoded_groups": 2,
        "encoded_observations": 5,
        "encoded_slots": 2,
        "reserved_components": 5,
        "fixings_read": 0,
        "kernel": 1,
        "live_prices_read": 2,
        "prepared_slots": 2,
    }
    tick, _ = evaluated(NG, "2026-11-24", {}, (3.21, 3.50))
    assert tick.mark == pytest.approx(8_600)
    np.testing.assert_array_equal(tick.price_sensitivity, initial.price_sensitivity)
    assert not tick.price_sensitivity.flags.writeable


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
    assert whole.price_sensitivity[0] - first_four.price_sensitivity[0] == 100_000


def test_a_tick_takes_the_preparation_as_it_is_and_folds_nothing() -> None:
    enc = encoded(terms_of(), observed_of(terms_of()), UNITS, WorkCounter())
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(enc, history, WorkCounter())
    before = (
        prep.dated_live_exposure.copy(),
        prep.price_sensitivity.copy(),
        prep.offset_unsettled,
        prep.cash,
    )
    counter = WorkCounter()
    later = trade_results(prep, quoted(history, 3.21, 3.50), counter)
    assert later.mark == pytest.approx(8_600)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 2}
    assert later.prepared is prep and later.market.market_history is history
    assert (
        later.price_sensitivity is prep.price_sensitivity
        and not later.price_sensitivity.flags.writeable
    )  # shared, never written
    np.testing.assert_array_equal(prep.dated_live_exposure, before[0])
    np.testing.assert_array_equal(prep.price_sensitivity, before[1])
    assert (prep.offset_unsettled, prep.cash) == before[2:]


def test_a_market_over_another_history_is_refused_rather_than_prepared_again() -> None:
    enc = encoded(terms_of(), observed_of(terms_of()), UNITS, WorkCounter())
    prep = prepared_trades(enc, history_on(NG, "2026-11-24", {}), WorkCounter())
    other = history_on(NG, "2026-11-23", {})  # the same index, another valuation date
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(other, 3.20, 3.50), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'Henry Hub NYMEX', "
        "expected the one the trades were prepared against"
    )


def test_a_corrected_history_of_the_same_day_is_another_history_until_prepared_again() -> None:
    # The toy on 26 November with Z26's final at 3.22, and the same index on the same day with
    # the final corrected to 3.23: the market over the corrected history is refused by object,
    # the index and the day being the same, and preparing again against it gives the page's
    # 11,800 where the first history gave 10,200.
    terms = terms_of(TOY, Settlement.FINANCIAL, TOY_PAYS)
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    first = history_on(TOY, "2026-11-26", {"Z26": 3.22})
    corrected = history_on(TOY, "2026-11-26", {"Z26": 3.23})
    prep = prepared_trades(enc, first, WorkCounter())
    on_first = trade_results(prep, quoted(first, 3.50, 3.60), WorkCounter())
    assert on_first.mark == pytest.approx(10_200)
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(corrected, 3.50, 3.60), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'TOY_GAS', "
        "expected the one the trades were prepared against"
    )
    again = prepared_trades(enc, corrected, WorkCounter())
    on_corrected = trade_results(again, quoted(corrected, 3.50, 3.60), WorkCounter())
    assert on_corrected.mark == pytest.approx(11_800)


def test_a_vector_that_stops_before_a_traded_contract_is_refused_by_the_market() -> None:
    enc = encoded(terms_of(), observed_of(terms_of()), UNITS, WorkCounter())
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(enc, history, WorkCounter())
    with pytest.raises(
        ValueError, match=r"^requested contract 'F27' is beyond live-price coverage"
    ):
        trade_results(prep, quoted(history, 3.20), WorkCounter())


def test_a_physical_bilateral_batch_is_refused_by_its_settlement() -> None:
    # Since #176 a bilateral batch is valued on a curve, tests/unit/test_bilateral_kernel.py; the
    # physical rows of the page under the bilateral route have no payment to discount.
    enc = encoded(
        terms_of(route=Route.BILATERAL),
        observed_of(terms_of(route=Route.BILATERAL)),
        UNITS,
        WorkCounter(),
    )
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(enc, history, WorkCounter())
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(history, 3.20, 3.50), WorkCounter())
    assert str(refused.value) == (
        "settlement_method is 'physical', expected 'financial' with a bilateral batch; a physical "
        "delivery has no payment to discount"
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
    np.testing.assert_array_equal(result.price_sensitivity, delta)
    assert result.lot_delta_total == pytest.approx(sum(delta) / 10_000)  # TOY lots
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
        observed_of(terms_of(TOY, Settlement.FINANCIAL, TOY_PAYS)),
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


# --- the penultimate method: ICE PHH on the NYMEX NG index -----------------------------------
# penultimate-trades.md's N27 example: the NG index of 2027 with M27 before and Q27 after, each
# expiring on the third-last business day of the month before, the pricing calendar closing
# Memorial Day and the observed Independence Day; the ICE lot of 2,500 MMBTU a specification of
# the index; two long lots at 3.00. The pen observes the business day before N27's expiry, Friday
# 25 June, and pays one clearing business day after it, Monday 28 June, the resolved day supplied
# here beside the lag and the calendar that gave it, as the toy's are.

PHH = an_index(
    "Henry Hub NYMEX",
    (("M27", "2027-05-26"), ("N27", "2027-06-28"), ("Q27", "2027-07-28")),
    ("2027-05-31", "2027-07-05"),
    lot=("ICE PHH", 2_500.0, "MMBTU"),
)
CLEARING_CALENDAR = holiday_calendar(dates("2027-05-31", "2027-08-30"))


def pen_terms(
    lots: float = 2.0,
    method: ScheduleMethod = ScheduleMethod.PENULTIMATE,
    settlement: Settlement = Settlement.FINANCIAL,
    pays: str = "2027-06-28",
) -> ResolvedTrades:
    """One trade of that many lots of N27 at 3.00 on the PHH index, financial unless said."""
    payment = (
        None
        if settlement is Settlement.PHYSICAL
        else PaymentTerms(np.full(1, 1), (CLEARING_CALENDAR,), dates(pays))
    )
    return resolved_trades(
        FIXED_FLOAT,
        PHH,
        spec(1),
        Route.CLEARED,
        settlement,
        *picks(method, QuantityPer.MONTH, 1),
        ids(1),
        ("ICE Clear Europe",),
        None,
        dates("2027-06-01"),
        rows(0),
        rows(1),
        numbers(lots),
        *bounds_of(PHH, rows(1)),
        numbers(3.0),
        payment,
    )


def history_by_day(ix: Index, as_of: str, settles: dict[str, float]) -> MarketHistory:
    """The index's history valued on that day: a settle of 3.00 on every fixed business day of
    its calendar, the settles given standing on their days, newest first as the creator takes
    them."""
    cal = calendar(valuation_date(day(as_of), 0.5), ix)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    prices = np.full(priced.size, 3.0)
    for text, price in settles.items():
        prices[priced == day(text)] = price
    return market_history(cal, futures_fixings(priced[::-1].copy(), prices[::-1].copy(), ix))


def pen_evaluated(
    as_of: str, settles: dict[str, float], quotes: tuple[float, ...], lots: float = 2.0
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = pen_terms(lots)
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = history_by_day(PHH, as_of, settles)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


def test_the_penultimate_method_observes_the_business_day_before_each_expiry() -> None:
    obs = observed(
        by(ScheduleMethod.PENULTIMATE, 3),
        PHH,
        rows(0, 1, 2),
        *bounds_of(PHH, rows(0, 1, 2)),
        unlabeled,
    )
    np.testing.assert_array_equal(obs.date, dates("2027-05-25", "2027-06-25", "2027-07-27"))
    np.testing.assert_array_equal(obs.component, [0, 1, 2])
    np.testing.assert_array_equal(obs.weight, [1.0, 1.0, 1.0])
    # The synthetic case: a Friday the market closes before a Monday expiry gives Thursday, the
    # pricing calendar's business day, whatever the payment calendar says of that Friday.
    friday_closed = an_index(
        "x",
        (("M27", "2027-05-26"), ("N27", "2027-06-28")),
        ("2027-06-25",),
        lot=("p", 1.0, "MMBTU"),
    )
    assert observed(
        by(ScheduleMethod.PENULTIMATE, 1),
        friday_closed,
        rows(1),
        *bounds_of(friday_closed, rows(1)),
        unlabeled,
    ).date[0] == day("2027-06-24")
    # lastday is the expiry itself, as before.
    np.testing.assert_array_equal(
        observed(
            by(ScheduleMethod.LASTDAY, 2), PHH, rows(0, 1), *bounds_of(PHH, rows(0, 1)), unlabeled
        ).date,
        dates("2027-05-26", "2027-06-28"),
    )


def test_an_expiry_the_market_closes_is_refused_under_penultimate_rather_than_rolled() -> None:
    thanksgiving = an_index(
        "x",
        (("X26", "2026-10-28"), ("Z26", "2026-11-26")),
        ("2026-11-26",),
        lot=("p", 1.0, "MMBTU"),
    )
    with pytest.raises(ValueError) as refused:
        observed(
            by(ScheduleMethod.PENULTIMATE, 1),
            thanksgiving,
            rows(1),
            *bounds_of(thanksgiving, rows(1)),
            unlabeled,
        )
    assert str(refused.value) == (
        "Z26 expires on 2026-11-26, a day the index's market is closed; the penultimate method "
        "takes the business day before an expiry the market prices"
    )


def test_a_physical_penultimate_future_is_refused_by_the_kernel() -> None:
    with pytest.raises(ValueError) as refused:
        pen_terms(settlement=Settlement.PHYSICAL)
    assert str(refused.value) == (
        "settlement_method is 'physical', expected 'financial' with the penultimate method of "
        "trade 1 at row 1; a penultimate future is cash settled on the business day before "
        "its contract's expiry"
    )


def test_the_pen_encodes_one_slot_on_the_day_before_expiry_referencing_its_contract() -> None:
    terms = pen_terms()
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.slot_date, dates("2027-06-25"))
    np.testing.assert_array_equal(enc.slot_reference, [1])  # N27 prices its own pen day
    np.testing.assert_array_equal(enc.slot_exposure, [5_000.0])  # two lots of 2,500 MMBTU
    np.testing.assert_array_equal(enc.offset, [-15_000.0])
    np.testing.assert_array_equal(enc.payment_date, dates("2027-06-28"))
    assert enc.named_slot(0) == "trade 1 at row 1 on 2027-06-25, a day N27 prices"


# The page's three states and the hand answers: live on the pen day itself, fixed on the Saturday
# after with Monday's payment ahead, paid on the Monday; the quotes those of N27 and Q27, the
# contracts the market still quotes, and the quotes and fixings read.
PEN_LIFECYCLE: list[tuple[str, dict[str, float], tuple[float, ...], int, int, int, int, int]] = [
    ("2027-06-25", {}, (3.10, 3.15), 500, 0, 5_000, 1, 0),
    ("2027-06-26", {"2027-06-25": 3.20}, (3.10, 3.15), 1_000, 0, 0, 0, 1),
    ("2027-06-28", {"2027-06-25": 3.20}, (3.10, 3.15), 0, 1_000, 0, 0, 1),
]


@pytest.mark.parametrize(
    ("as_of", "settles", "quotes", "mark", "cash", "delta", "live_reads", "fixings_read"),
    PEN_LIFECYCLE,
    ids=["live on the pen day", "fixed, unpaid", "paid"],
)
@pytest.mark.parametrize("lots", [2.0, -2.0], ids=["long", "short"])
def test_the_phh_pen_marks_fixes_and_pays_as_the_page_says(
    as_of: str,
    settles: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
    live_reads: int,
    fixings_read: int,
    lots: float,
) -> None:
    sign = 1 if lots > 0 else -1
    result, counter = pen_evaluated(as_of, settles, quotes, lots)
    assert result.mark == pytest.approx(sign * mark)
    assert result.cash == pytest.approx(sign * cash)
    assert result.lot_delta_total == pytest.approx(sign * delta / 2_500)  # ICE PHH lots
    assert result.codes() == ("N27",)
    assert result.dv01 == 0.0
    counts = counter.freeze()
    assert (counts["live_prices_read"], counts["fixings_read"], counts["kernel"]) == (
        live_reads,
        fixings_read,
        1,
    )


def test_a_tick_moves_the_live_pen_and_a_corrected_fixing_takes_a_new_history() -> None:
    terms = pen_terms()
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    live = history_by_day(PHH, "2027-06-25", {})
    prep = prepared_trades(enc, live, WorkCounter())
    assert trade_results(prep, quoted(live, 3.10, 3.15), WorkCounter()).mark == pytest.approx(500)
    assert trade_results(prep, quoted(live, 3.11, 3.15), WorkCounter()).mark == pytest.approx(550)
    fixed = history_by_day(PHH, "2027-06-26", {"2027-06-25": 3.20})
    corrected = history_by_day(PHH, "2027-06-26", {"2027-06-25": 3.21})
    assert trade_results(
        prepared_trades(enc, fixed, WorkCounter()), quoted(fixed, 3.10, 3.15), WorkCounter()
    ).mark == pytest.approx(1_000)
    assert trade_results(
        prepared_trades(enc, corrected, WorkCounter()),
        quoted(corrected, 3.10, 3.15),
        WorkCounter(),
    ).mark == pytest.approx(1_050)
    # The underlying's own final settle, on 28 June, is another day's fixing: it stands in the
    # history and changes nothing of the pen, which read the 25th.
    for final in (3.25, 3.35):
        paid = history_by_day(PHH, "2027-06-29", {"2027-06-25": 3.21, "2027-06-28": final})
        result = trade_results(
            prepared_trades(enc, paid, WorkCounter()), quoted(paid, 3.15), WorkCounter()
        )
        assert (result.mark, result.cash) == (0.0, pytest.approx(1_050))


def test_a_fixed_pen_inside_a_live_market_reads_no_quote_whatever_the_underlying_does() -> None:
    results = [
        pen_evaluated("2027-06-26", {"2027-06-25": 3.20}, quotes)
        for quotes in ((3.10, 3.15), (3.50, 3.55))
    ]
    for result, counter in results:
        assert (result.mark, result.lot_delta_total) == (pytest.approx(1_000), 0.0)
        assert counter.freeze()["live_prices_read"] == 0
        assert result.prepared.live_references.size == 0
    assert results[0][0].market.first_contract == 1  # N27, still quoted, read by no slot


# --- the penultimate method: a strip, a duplicate and a signed lot through one path -----------
# R1's acceptance list: A, two lots of the N27-Q27 strip at 3.00, A again, and C, one lot of Q27
# sold at 3.05, on the PHH index with U27 after Q27 so that every state has a market. By hand: a
# strip lot is 2,500 MMBTU on each of its months, so A holds 5,000 on N27 and 5,000 on Q27, the
# two As 10,000 and 10,000, and C takes Q27 to 7,500. Live, N27 at 3.10 and Q27 at 3.40: 10,000
# of N27 ten cents up is 1,000, 10,000 of Q27 forty cents up is 4,000, and C's 2,500 sold at 3.05
# against 3.40 is -875, 4,125 in all, a delta of 10,000 and 7,500. N27 fixed at 3.20 on its pen
# day, Friday 25 June, is 2,000, unpaid on the Saturday and cash on Monday the 28th, one clearing
# day after; Q27 fixed at 3.45 on its pen day, Tuesday 27 July, is 4,500 less C's 1,000, cash on
# the 28th, 5,500 in all and nothing live.

STRIP_INDEX = an_index(
    "Henry Hub NYMEX",
    (("M27", "2027-05-26"), ("N27", "2027-06-28"), ("Q27", "2027-07-28"), ("U27", "2027-08-27")),
    ("2027-05-31", "2027-07-05"),
    lot=("ICE PHH", 2_500.0, "MMBTU"),
)
# Each row: its label, the schedule rows of its months, its lots and its price.
STRIP_ROWS: tuple[tuple[int, tuple[int, ...], float, float], ...] = (
    (1, (1, 2), 2.0, 3.00),
    (1, (1, 2), 2.0, 3.00),
    (3, (2,), -1.0, 3.05),
)
STRIP_PAYS = {1: "2027-06-28", 2: "2027-07-28"}  # one clearing day after each month's pen day


def strip_terms(order: tuple[tuple[int, tuple[int, ...], float, float], ...]) -> ResolvedTrades:
    """Those rows resolved on the PHH index with U27, a strip one component per month on its one
    occurrence, each component paying one clearing day after its month's pen day."""
    n = len(order)
    components = [(i, c, q, p) for i, (_, months, q, p) in enumerate(order) for c in months]
    return resolved_trades(
        FIXED_FLOAT, STRIP_INDEX, spec(n), Route.CLEARED, Settlement.FINANCIAL,
        *picks(ScheduleMethod.PENULTIMATE, QuantityPer.MONTH, n),
        ids(*(label for label, _, _, _ in order)), ("ICE Clear Europe",) * n,
        None, np.repeat(day("2027-06-01"), n), rows(*(i for i, _, _, _ in components)),
        rows(*(c for _, c, _, _ in components)), numbers(*(q for _, _, q, _ in components)),
        *bounds_of(STRIP_INDEX, rows(*(c for _, c, _, _ in components))),
        numbers(*(p for _, _, _, p in components)),
        PaymentTerms(
            np.full(n, 1),
            (CLEARING_CALENDAR,) * n,
            dates(*(STRIP_PAYS[c] for _, c, _, _ in components)),
        ),
    )  # fmt: skip


def strip_valued(
    order: tuple[tuple[int, tuple[int, ...], float, float], ...],
    as_of: str,
    settles: dict[str, float],
    quotes: tuple[float, ...],
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = strip_terms(order)
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = history_by_day(STRIP_INDEX, as_of, settles)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


# The six states by hand: as-of, the settles on their pen days, the quotes of the contracts the
# market still quotes, then mark, cash, delta on N27 and Q27, and the quotes and fixings read.
STRIP_LIFECYCLE: list[
    tuple[str, dict[str, float], tuple[float, ...], int, int, tuple[int, int], int, int]
] = [
    ("2027-06-24", {}, (3.10, 3.40), 4_125, 0, (10_000, 7_500), 2, 0),
    ("2027-06-25", {}, (3.10, 3.40), 4_125, 0, (10_000, 7_500), 2, 0),
    ("2027-06-26", {"2027-06-25": 3.20}, (3.10, 3.40), 5_125, 0, (0, 7_500), 1, 1),
    ("2027-06-28", {"2027-06-25": 3.20}, (3.10, 3.40), 3_125, 2_000, (0, 7_500), 1, 1),
    ("2027-07-27", {"2027-06-25": 3.20}, (3.40,), 3_125, 2_000, (0, 7_500), 1, 1),
    ("2027-07-28", {"2027-06-25": 3.20, "2027-07-27": 3.45}, (3.50,), 0, 5_500, (0, 0), 0, 2),
]
STRIP_IDS = [
    "24 Jun, both live",
    "25 Jun, N27 live on its pen day",
    "26 Jun, N27 fixed, unpaid",
    "28 Jun, N27 paid",
    "27 Jul, Q27 live on its pen day",
    "28 Jul, both paid",
]


@pytest.mark.parametrize(
    ("as_of", "settles", "quotes", "mark", "cash", "delta", "live_reads", "fixings_read"),
    STRIP_LIFECYCLE,
    ids=STRIP_IDS,
)
def test_the_pen_strip_batch_marks_fixes_and_pays_as_the_hand_says(
    as_of: str,
    settles: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: tuple[float, float],
    live_reads: int,
    fixings_read: int,
) -> None:
    result, counter = strip_valued(STRIP_ROWS, as_of, settles, quotes)
    assert result.mark == pytest.approx(mark) and result.cash == pytest.approx(cash)
    np.testing.assert_array_equal(result.price_sensitivity, delta)
    assert result.lot_delta_total == pytest.approx(sum(delta) / 2_500)  # ICE PHH lots
    assert result.codes() == ("N27", "Q27")
    counts = counter.freeze()
    assert (counts["live_prices_read"], counts["fixings_read"], counts["kernel"]) == (
        live_reads,
        fixings_read,
        1,
    )
    # The rows the other way round make the same batch, and the three rows each alone sum to it.
    turned, _ = strip_valued(STRIP_ROWS[::-1], as_of, settles, quotes)
    assert turned.mark == pytest.approx(mark) and turned.cash == pytest.approx(cash)
    np.testing.assert_array_equal(turned.price_sensitivity, delta)
    singles = [strip_valued((line,), as_of, settles, quotes)[0] for line in STRIP_ROWS]
    assert sum(s.mark for s in singles) == pytest.approx(mark)
    assert sum(s.cash for s in singles) == pytest.approx(cash)


def test_the_pen_strip_encodes_one_slot_per_month_paying_one_clearing_day_after_each() -> None:
    terms = strip_terms(STRIP_ROWS)
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.quote_quantity, [5_000, 5_000, 5_000, 5_000, -2_500])
    np.testing.assert_array_equal(enc.slot_date, dates("2027-06-25", "2027-07-27"))
    np.testing.assert_array_equal(enc.slot_exposure, [10_000, 7_500])
    np.testing.assert_array_equal(enc.payment_date, dates("2027-06-28", "2027-07-28"))
    assert terms.named(4) == "trade 3 at row 3"


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
        FIXED_FLOAT, DAILY, spec(n), Route.CLEARED, Settlement.FINANCIAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, n), None, None, None,
        np.repeat(day("2026-11-20"), n),
        np.arange(n, dtype=np.intp), np.ones(n, dtype=np.intp), numbers(*lots),
        *bounds_of(DAILY, np.ones(n, dtype=np.intp)), numbers(*prices),
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
    np.testing.assert_array_equal(enc.quote_quantity, [60, -30])
    np.testing.assert_array_equal(enc.offset, [-4_200, 2_160])
    np.testing.assert_array_equal(enc.group_contract, [1])
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
        "encoded_groups": 1,
        "encoded_observations": 6,
        "encoded_slots": 3,
        "reserved_components": 2,
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
    np.testing.assert_allclose(result.price_sensitivity, [delta])
    assert result.lot_delta_total == pytest.approx(delta) and result.codes() == ("Z26",)
    counts = counter.freeze()
    assert (counts["fixings_read"], counts["live_prices_read"]) == (fixings, quotes)
    assert counts["prepared_slots"] == 3 and counts["kernel"] == 1
    assert prep.history.calendar.valuation_date.as_of == day(as_of)


def test_the_daily_toy_pays_on_its_day_and_the_whole_amount_becomes_cash() -> None:
    paid, _ = daily_evaluated("2027-01-05")
    assert (paid.mark, paid.cash) == (0.0, pytest.approx(150))
    assert paid.dated_live_contribution.size == 0 and paid.lot_delta_total == 0.0
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
    assert live.mark == pytest.approx(0.0) and live.lot_delta_total == pytest.approx(0.0)
    np.testing.assert_allclose(live.dated_live_contribution, [740, -740])
    after = daily_history("2026-12-02", SETTLES)
    fixed = trade_results(
        prepared_trades(enc, after, WorkCounter()), daily_market(after), WorkCounter()
    )
    assert fixed.mark == pytest.approx(-30)
    np.testing.assert_allclose(fixed.price_sensitivity, [-10])
    np.testing.assert_allclose(fixed.dated_live_contribution, [-740])


def test_the_daily_toys_results_read_back_slot_by_slot_with_the_contracts_delta_named() -> None:
    # The review's case: after 1 December fixes, the slots' live exposure is 0, 10, 10, their
    # contributions 0, 740, 740, and Z26's delta 20 stands beside each as the contract's.
    from goosedove.excel.utilities import shown

    result, _ = daily_evaluated("2026-12-02")
    table = shown(result)
    assert table.texts[:12] == (
        "pricing_contract",
        "booked_contract",
        "observation_date",
        "payment_date",
        "is_fixed",
        "live_coefficient",
        "live_lots",
        "live_contribution",
        "contract_sensitivity",
        "contract_discounted_sensitivity",
        "contract_lot_delta",
        "contract_delta",
    )
    np.testing.assert_array_equal(table.numeric_slots[2:, 3], [46_392.0] * 3)  # 5 January
    np.testing.assert_array_equal(table.numeric_slots[2:, 4], [1.0, 0.0, 0.0])  # is_fixed
    np.testing.assert_allclose(table.numeric_slots[2:, 5], [0.0, 10.0, 10.0])
    np.testing.assert_allclose(table.numeric_slots[2:, 6], [0.0, 10.0, 10.0])  # a unit lot
    np.testing.assert_allclose(table.numeric_slots[2:, 7], [0.0, 740.0, 740.0])
    # The contract's sensitivity and lot delta, and their discounted twins, the same for a
    # cleared batch, on every slot of the contract.
    for column in (8, 9, 10, 11):
        np.testing.assert_allclose(table.numeric_slots[2:, column], [20.0, 20.0, 20.0])


def test_a_tick_on_the_daily_toy_reads_one_quote_and_gathers_it_onto_the_live_slots() -> None:
    terms = daily_terms()
    enc = encoded(terms, daily_observations(terms, (DAILY_DATES_TEXT,) * 2), UNITS, WorkCounter())
    history = daily_history("2026-12-02", SETTLES)
    prep = prepared_trades(enc, history, WorkCounter())
    counter = WorkCounter()
    later = trade_results(prep, quoted(history, 75.0, 74.5), counter)
    assert later.mark == pytest.approx(-2_040 + 710 + 2 * 10 * 75)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 1}
    assert later.price_sensitivity is prep.price_sensitivity


def test_an_observation_of_another_contract_than_the_days_is_refused_as_unsupported() -> None:
    # A component on G27 observed on 1 December, a day Z26 prices: the history holds no G27
    # settle for it, so it is refused rather than priced off Z26.
    terms = resolved_trades(
        FIXED_FLOAT, DAILY, spec(1), Route.CLEARED, Settlement.FINANCIAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 1), ids(1), None, None,
        dates("2026-11-20"), rows(0), rows(2), numbers(1),
        *bounds_of(DAILY, rows(2)), numbers(70.0), paying(dates("2027-02-02"), 1),
    )  # fmt: skip
    with pytest.raises(ValueError) as refused:
        encoded(terms, daily_observations(terms, (("2026-12-01",),)), UNITS, WorkCounter())
    assert str(refused.value) == (
        "trade 1 at row 1 observes G27 on 2026-12-01, a day Z26 prices; the lastday method "
        "takes the contract's own days, and a futures history holds no settle of G27 for a day "
        "Z26 prices"
    )
    with pytest.raises(ValueError) as refused:
        encoded(terms, daily_observations(terms, (("2027-02-01",),)), UNITS, WorkCounter())
    assert str(refused.value) == (
        "trade 1 at row 1 observes 2027-02-01, after the schedule's last expiry, 2027-01-29; "
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
        f"trade at row 1 observes {closed_day}, a day the index's market is closed; "
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


# --- a quantity of zero: a row kept ready ----------------------------------------------------
# zero-quantities.md: a numeric zero is a whole count like any other, encoded, prepared and
# evaluated through the one path, contributing nothing and keeping its contract on the axis. The
# page's example: NG-001, two lots of Z26 at 3.00, and ENTRY-002, a row of F27 at 3.30 kept ready.


def entry_terms(quantities: tuple[float, float] = (2.0, 0.0)) -> ResolvedTrades:
    return resolved_trades(
        FIXED_FLOAT, NG, spec(2), Route.CLEARED, Settlement.PHYSICAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 2), ids(1001, 1002), None, None,
        dates("2026-10-06", "2026-10-06"),
        rows(0, 1), rows(1, 2), numbers(*quantities), *bounds_of(NG, rows(1, 2)),
        numbers(3.0, 3.3), None,
    )  # fmt: skip


def zero_toy_terms() -> ResolvedTrades:
    """One row kept ready on the toy: nothing of Z26 at 3.10, financial, paying 30 November."""
    return resolved_trades(
        FIXED_FLOAT, TOY, spec(1), Route.CLEARED, Settlement.FINANCIAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 1), ids(1000), None, None,
        dates("2026-10-06"), rows(0), rows(1),
        numbers(0.0), *bounds_of(TOY, rows(1)), numbers(3.1), paying(dates("2026-11-30"), 1),
    )  # fmt: skip


def valued_entry(
    quantities: tuple[float, float], *quotes: float
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = entry_terms(quantities)
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


def test_a_zero_quantity_is_a_whole_count_the_terms_keep() -> None:
    terms = entry_terms()
    np.testing.assert_array_equal(terms.quantity, [2.0, 0.0])
    assert terms.named(1) == "trade 1002 at row 2"
    assert entry_terms((2.0, -0.0)).quantity[1] == 0.0  # numeric negative zero is whole too
    with pytest.raises(ValueError) as refused:
        entry_terms((2.0, 0.5))
    assert str(refused.value) == "quantity of trade 1002 at row 2 is 0.5, expected a whole number"


def test_a_zero_row_encodes_zero_amounts_and_keeps_its_contract_and_slot() -> None:
    counter = WorkCounter()
    terms = entry_terms()
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    np.testing.assert_array_equal(enc.quote_quantity, [20_000, 0])
    np.testing.assert_array_equal(enc.coefficient, [20_000, 0])
    np.testing.assert_array_equal(enc.offset, [-60_000, 0])
    np.testing.assert_array_equal(enc.group_contract, [1, 2])  # F27 held, at nothing
    np.testing.assert_array_equal(enc.slot_exposure, [20_000, 0])
    np.testing.assert_array_equal(enc.references, [1, 2])
    assert enc.named_slot(1) == "trade 1002 at row 2 on 2026-12-29, a day F27 prices"
    assert counter.freeze().as_dict() == {
        "encoded_components": 2,
        "encoded_groups": 2,
        "encoded_observations": 2,
        "encoded_slots": 2,
        "reserved_components": 2,
    }


def test_the_pages_example_marks_2000_with_the_row_kept_ready_and_1000_once_it_is_sold() -> None:
    kept, counter = valued_entry((2.0, 0.0), 3.10, 3.40)
    assert (kept.mark, kept.cash) == (pytest.approx(2_000), 0.0)
    np.testing.assert_array_equal(kept.price_sensitivity, [20_000, 0])
    assert kept.lot_delta_total == 2 and kept.codes() == ("Z26", "F27")
    np.testing.assert_allclose(kept.dated_live_contribution, [62_000, 0])
    assert counter.freeze()["live_prices_read"] == 2  # the zero slot takes its quote like any other
    sold, _ = valued_entry((2.0, -1.0), 3.10, 3.40)
    assert sold.mark == pytest.approx(1_000)
    np.testing.assert_array_equal(sold.price_sensitivity, [20_000, -10_000])
    assert sold.lot_delta_total == 1


def test_an_all_zero_batch_values_to_nothing_with_its_axis_kept() -> None:
    nothing, counter = valued_entry((0.0, 0.0), 3.10, 3.40)
    assert (nothing.mark, nothing.cash, nothing.lot_delta_total, nothing.dv01) == (
        0.0,
        0.0,
        0.0,
        0.0,
    )
    np.testing.assert_array_equal(nothing.price_sensitivity, [0, 0])
    assert nothing.codes() == ("Z26", "F27")
    np.testing.assert_array_equal(nothing.dated_live_contribution, [0, 0])
    assert counter.freeze()["live_prices_read"] == 2


def test_a_row_kept_ready_before_a_held_contract_keeps_its_place_on_the_axis() -> None:
    # The zero row on Z26 sorts before the held F27: Z26 stays on the axis at nothing and F27
    # carries the lot, so a delta on the wrong contract would show while the mark and the total
    # stayed right. By hand: one lot of F27 sold at 3.30 against 3.40 is -1,000, and -10,000
    # per dollar on F27 alone.
    first_nothing = resolved_trades(
        FIXED_FLOAT, NG, spec(2), Route.CLEARED, Settlement.PHYSICAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 2), ids(1002, 1001), None, None,
        dates("2026-10-06", "2026-10-06"),
        rows(0, 1), rows(1, 2), numbers(0.0, -1.0), *bounds_of(NG, rows(1, 2)),
        numbers(3.0, 3.3), None,
    )  # fmt: skip
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(
        encoded(first_nothing, observed_of(first_nothing), UNITS, WorkCounter()),
        history,
        WorkCounter(),
    )
    result = trade_results(prep, quoted(history, 3.10, 3.40), WorkCounter())
    assert result.mark == pytest.approx(-1_000) and result.lot_delta_total == pytest.approx(-1)
    np.testing.assert_array_equal(result.price_sensitivity, [0, -10_000])
    assert result.codes() == ("Z26", "F27")


def test_four_rows_with_two_kept_ready_value_alike_in_every_order() -> None:
    # Two lots of Z26 at 3.00, a row of F27 at 3.30 kept ready, one lot of Z26 sold at 3.05 and
    # a row of F27 at 3.20 kept ready, against 3.10 and 3.40. By hand: 2,000 less 500 is 1,500 of
    # mark, 10,000 of delta on Z26 and nothing on F27, in whichever of the 24 orders the rows come.
    given_rows = (
        (1, 1, 2.0, 3.00),
        (2, 2, 0.0, 3.30),
        (3, 1, -1.0, 3.05),
        (4, 2, 0.0, 3.20),
    )
    history = history_on(NG, "2026-11-24", {})
    for order in itertools.permutations(given_rows):
        labels, contracts, quantities, prices = zip(*order, strict=True)
        terms = resolved_trades(
            FIXED_FLOAT, NG, spec(4), Route.CLEARED, Settlement.PHYSICAL,
            *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 4), ids(*labels), None, None,
            np.repeat(day("2026-10-06"), 4),
            np.arange(4, dtype=np.intp), rows(*contracts), numbers(*quantities),
            *bounds_of(NG, rows(*contracts)), numbers(*prices), None,
        )  # fmt: skip
        prep = prepared_trades(
            encoded(terms, observed_of(terms), UNITS, WorkCounter()), history, WorkCounter()
        )
        result = trade_results(prep, quoted(history, 3.10, 3.40), WorkCounter())
        assert result.mark == pytest.approx(1_500), order
        np.testing.assert_array_equal(result.price_sensitivity, [10_000, 0])
        assert result.codes() == ("Z26", "F27") and result.lot_delta_total == pytest.approx(1)


def test_adding_rows_kept_ready_changes_no_number_of_the_batch() -> None:
    whole, _ = evaluated(NG, "2026-11-24", {}, (3.20, 3.50))
    spares = resolved_trades(
        FIXED_FLOAT, NG, spec(7), Route.CLEARED, Settlement.PHYSICAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 7),
        np.concatenate([TRADE_IDS, ids(2001, 2002)]),
        None, None,
        np.concatenate([TRADE_DATES, dates("2026-10-06", "2026-10-06")]),
        np.arange(7, dtype=np.intp), np.concatenate([CONTRACT, rows(1, 2)]),
        np.concatenate([LOTS, numbers(0, 0)]),
        *bounds_of(NG, np.concatenate([CONTRACT, rows(1, 2)])),
        np.concatenate([FIXED_PRICE, numbers(3.0, 3.3)]), None,
    )  # fmt: skip
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(
        encoded(spares, observed_of(spares), UNITS, WorkCounter()), history, WorkCounter()
    )
    spared = trade_results(prep, quoted(history, 3.20, 3.50), WorkCounter())
    assert spared.mark == pytest.approx(whole.mark) == pytest.approx(7_000)
    np.testing.assert_array_equal(spared.price_sensitivity, whole.price_sensitivity)
    assert spared.codes() == whole.codes() and prep.live_slot.size == 2


def test_a_zero_row_bypasses_no_rule_of_the_market_the_calendar_or_identity() -> None:
    # A quote missing for the zero row's contract is still missing, a physical contract past its
    # expiry is still past it, and an all-zero batch is held to the identity rules, whether
    # anything is held on a contract or nothing.
    terms = entry_terms((2.0, 0.0))
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    history = history_on(NG, "2026-11-24", {})
    prep = prepared_trades(enc, history, WorkCounter())
    with pytest.raises(
        ValueError, match=r"^requested contract 'F27' is beyond live-price coverage"
    ):
        trade_results(prep, quoted(history, 3.10), WorkCounter())
    nothing = entry_terms((0.0, 0.0))
    enc = encoded(nothing, observed_of(nothing), UNITS, WorkCounter())
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(NG, "2026-11-26", {"Z26": 3.22}), WorkCounter())
    assert str(refused.value) == (
        "trade 1001 at row 1 on Z26 expired 2026-11-25, before valuation date 2026-11-26; "
        "a physical fixed_float after its expiry is not supported"
    )
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(an_index(), "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "history is over another index, 'Henry Hub NYMEX', expected the trades', 'Henry Hub NYMEX'"
    )
    prep = prepared_trades(enc, history, WorkCounter())
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(history_on(NG, "2026-11-23", {}), 3.10, 3.40), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'Henry Hub NYMEX', "
        "expected the one the trades were prepared against"
    )


@pytest.mark.parametrize(
    ("as_of", "finals", "quotes", "live_reads", "fixings_read"),
    [
        ("2026-11-24", {}, (3.20, 3.50, 3.60), 1, 0),
        ("2026-11-26", {"Z26": 3.23}, (3.50, 3.60), 0, 1),
        ("2026-11-30", {"Z26": 3.23}, (3.50, 3.60), 0, 1),
    ],
    ids=["live", "fixed, unpaid", "paid"],
)
def test_a_zero_financial_trade_stays_at_nothing_live_fixed_and_paid(
    as_of: str,
    finals: dict[str, float],
    quotes: tuple[float, ...],
    live_reads: int,
    fixings_read: int,
) -> None:
    counter = WorkCounter()
    terms = zero_toy_terms()
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = history_on(TOY, as_of, finals)
    prep = prepared_trades(enc, history, counter)
    result = trade_results(prep, quoted(history, *quotes), counter)
    assert (result.mark, result.cash, result.lot_delta_total) == (0.0, 0.0, 0.0)
    np.testing.assert_array_equal(result.price_sensitivity, [0.0])
    assert result.codes() == ("Z26",)
    counts = counter.freeze()
    assert (counts["live_prices_read"], counts["fixings_read"]) == (live_reads, fixings_read)


# --- properties -------------------------------------------------------------------------------

lots_strategy = st.integers(min_value=-20, max_value=20)  # zero included, a row kept ready
prices_strategy = st.floats(min_value=1.0, max_value=9.0, allow_nan=False, allow_infinity=False)


# Bounded and repeatable: sixty examples drawn from a fixed seed, so a failure here is the same
# failure on every machine and every run.
@settings(max_examples=60, deadline=None, derandomize=True)
@given(
    trades=st.lists(
        st.tuples(st.integers(min_value=1, max_value=2), lots_strategy, prices_strategy),
        min_size=1,
        max_size=8,
    ),
    quotes=st.tuples(prices_strategy, prices_strategy),
)
def test_any_batch_equals_its_singletons_summed_with_its_delta_on_its_own_contracts(
    trades: list[tuple[int, int, float]], quotes: tuple[float, float]
) -> None:
    def valued(selected: list[tuple[int, int, float]]) -> TradeResults:
        n = len(selected)
        terms = resolved_trades(
            FIXED_FLOAT, NG, spec(n), Route.CLEARED, Settlement.PHYSICAL,
            *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, n), None, None, None,
            np.repeat(day("2026-09-24"), n),
            np.arange(n, dtype=np.intp), rows(*(c for c, _, _ in selected)),
            numbers(*(q for _, q, _ in selected)),
            *bounds_of(NG, rows(*(c for c, _, _ in selected))),
            numbers(*(p for _, _, p in selected)), None,
        )  # fmt: skip
        history = history_on(NG, "2026-11-24", {})
        prep = prepared_trades(
            encoded(terms, observed_of(terms), UNITS, WorkCounter()), history, WorkCounter()
        )
        return trade_results(prep, quoted(history, *quotes), WorkCounter())

    whole = valued(trades)
    singles = [valued([trade]) for trade in trades]
    assert whole.mark == pytest.approx(sum(s.mark for s in singles), abs=1e-6)
    assert whole.lot_delta_total == pytest.approx(sum(s.lot_delta_total for s in singles))
    by_hand = sum(q * 10_000 * (quotes[c - 1] - p) for c, q, p in trades)
    assert whole.mark == pytest.approx(by_hand, abs=1e-6)
    doubled = valued(trades + trades)
    assert doubled.mark == pytest.approx(2 * whole.mark, abs=1e-6)
    np.testing.assert_allclose(doubled.price_sensitivity, 2 * whole.price_sensitivity)
    axis = tuple(sorted({("Z26", "F27")[c - 1] for c, _, _ in trades}, key=("Z26", "F27").index))
    assert whole.codes() == axis
    # The delta contract by contract, by hand on the batch's own axis: the lots held on each
    # contract times the lot size, nothing where only rows kept ready hold it.
    by_contract = [
        sum(q * 10_000 for c, q, _ in trades if ("Z26", "F27")[c - 1] == code) for code in axis
    ]
    np.testing.assert_allclose(whole.price_sensitivity, by_contract)
    # The rows the other way round make the same batch: mark, axis and delta.
    turned = valued(trades[::-1])
    assert turned.mark == pytest.approx(whole.mark, abs=1e-6) and turned.codes() == axis
    np.testing.assert_allclose(turned.price_sensitivity, whole.price_sensitivity)


# --- the last3day method: three equally weighted observations, one payment --------------------
# last3day-trades.md's synthetic example: an index quoted in USD per MMBTU and settling in USD,
# one specification UNIT of one MMBTU, X26 expiring 30 November 2026, Z26 7 December and F27
# 7 January 2027, the market closed on 4 December; the payment calendar open every weekday. Two
# trades of Z26, A 60 at 70 and B -30 at 72, pay two business days after the last observation,
# 9 December. By hand: each component's quantity is shared over 2, 3 and 7 December, 20 and -10
# a day, 10 a day compressed, and the fixed leg is -60 * 70 + 30 * 72 = -2,040, once; live at 74
# the mark is -2,040 + 30 * 74 = 180 and the delta 30; 2 December fixed at 71, 150 and 20; 2 and
# 3 December at 71 and 75, 160 and 10, on the 4th and still on the 7th, the last observation live
# on its own day; all three fixed, the 7th at 73, 150 unpaid on the 8th; paid on the 9th, 150 of
# cash and no mark. The quotes are Z26's and F27's while Z26 is live, F27's alone after.

SYN = an_index(
    "SYN",
    (("X26", "2026-11-30"), ("Z26", "2026-12-07"), ("F27", "2027-01-07")),
    ("2026-12-04",),
    lot=("UNIT", 1.0, "MMBTU"),
)
WEEKDAYS = holiday_calendar(dates("2026-01-01"))  # a payment calendar closing no day of the example
SYN_SETTLES = {
    "2026-12-01": 70.0,
    "2026-12-02": 71.0,
    "2026-12-03": 75.0,
    "2026-12-07": 73.0,
    "2026-12-08": 80.0,
}
L3D_DAYS = dates("2026-12-02", "2026-12-03", "2026-12-07")
L3D_PAYS = {1: "2026-12-09", 2: "2027-01-11"}  # two weekdays after each contract's last observation


def l3d_terms(
    quantities: tuple[float, ...] = (60.0, -30.0),
    prices: tuple[float, ...] = (70.0, 72.0),
    contracts: tuple[int, ...] = (1, 1),
    settlement: Settlement = Settlement.FINANCIAL,
    ix: Index = SYN,
) -> ResolvedTrades:
    """Trades on the synthetic index under last3day, A and B of Z26 unless said, each paying two
    weekdays after its contract's last observation, the dates the resolution would make."""
    n = len(quantities)
    payment = (
        None
        if settlement is Settlement.PHYSICAL
        else PaymentTerms(np.full(n, 2), (WEEKDAYS,) * n, dates(*(L3D_PAYS[c] for c in contracts)))
    )
    return resolved_trades(
        FIXED_FLOAT,
        ix,
        spec(n),
        Route.CLEARED,
        settlement,
        *picks(ScheduleMethod.LAST3DAY, QuantityPer.MONTH, n),
        np.arange(1, n + 1, dtype=np.int64),
        ("Prototype Clearing",) * n,
        None,
        dates(*(["2026-11-20"] * n)),
        np.arange(n, dtype=np.intp),
        rows(*contracts),
        numbers(*quantities),
        *bounds_of(ix, rows(*contracts)),
        numbers(*prices),
        payment,
    )


def l3d_evaluated(
    as_of: str,
    quotes: tuple[float, ...],
    terms: ResolvedTrades | None = None,
    settles: dict[str, float] = SYN_SETTLES,
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = l3d_terms() if terms is None else terms
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = history_by_day(SYN, as_of, settles)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


def test_last3day_observes_the_expiry_and_the_two_business_days_before_it() -> None:
    obs = observed(
        by(ScheduleMethod.LAST3DAY, 2), SYN, rows(1, 2), *bounds_of(SYN, rows(1, 2)), unlabeled
    )
    np.testing.assert_array_equal(obs.component, [0, 0, 0, 1, 1, 1])
    np.testing.assert_array_equal(
        obs.date,
        dates("2026-12-02", "2026-12-03", "2026-12-07", "2027-01-05", "2027-01-06", "2027-01-07"),
    )
    np.testing.assert_allclose(obs.weight, [1 / 3] * 6)
    # Z26's days step over the closed Friday the 4th; lastday and penultimate are as they were.
    np.testing.assert_array_equal(
        observed(
            by(ScheduleMethod.LASTDAY, 1), SYN, rows(1), *bounds_of(SYN, rows(1)), unlabeled
        ).date,
        L3D_DAYS[2:],
    )
    np.testing.assert_array_equal(
        observed(
            by(ScheduleMethod.PENULTIMATE, 1), SYN, rows(1), *bounds_of(SYN, rows(1)), unlabeled
        ).date,
        L3D_DAYS[1:2],
    )


def test_an_expiry_the_market_closes_is_refused_under_last3day_rather_than_rolled() -> None:
    closed = an_index(
        "x",
        (("X26", "2026-11-30"), ("Z26", "2026-12-04"), ("F27", "2027-01-07")),
        ("2026-12-04",),
        lot=("UNIT", 1.0, "MMBTU"),
    )
    with pytest.raises(ValueError) as refused:
        observed(
            by(ScheduleMethod.LAST3DAY, 1), closed, rows(1), *bounds_of(closed, rows(1)), unlabeled
        )
    assert str(refused.value) == (
        "Z26 expires on 2026-12-04, a day the index's market is closed; the last3day method takes "
        "an expiry the market prices and the two business days before it"
    )


def test_an_observation_crossing_the_preceding_contracts_window_is_refused() -> None:
    # X26 expiring on 3 December prices the 2nd and the 3rd: Z26's first two days are another
    # contract's, and no settle of Z26 exists for them, so the batch is refused and nothing
    # substituted.
    crossing = an_index(
        "x",
        (("X26", "2026-12-03"), ("Z26", "2026-12-07"), ("F27", "2027-01-07")),
        ("2026-12-04",),
        lot=("UNIT", 1.0, "MMBTU"),
    )
    terms = l3d_terms(ix=crossing)
    with pytest.raises(ValueError) as refused:
        encoded(terms, observed_of(terms), UNITS, WorkCounter())
    assert str(refused.value) == (
        "trade 1 at row 1 observes Z26 on 2026-12-02, a day X26 prices; the last3day method "
        "takes the contract's own days, and a futures history holds no settle of Z26 for a day "
        "X26 prices"
    )


def test_a_physical_last3day_future_is_refused_by_the_kernel() -> None:
    with pytest.raises(ValueError) as refused:
        l3d_terms(settlement=Settlement.PHYSICAL)
    assert str(refused.value) == (
        "settlement_method is 'physical', expected 'financial' with the last3day method of "
        "trade 1 at row 1; a last3day future is cash settled on the average of its last three "
        "pricing days"
    )


def test_the_last3day_batch_encodes_three_slots_of_ten_and_one_fixed_leg() -> None:
    terms = l3d_terms()
    counter = WorkCounter()
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    np.testing.assert_array_equal(enc.slot_date, L3D_DAYS)
    np.testing.assert_array_equal(enc.slot_reference, [1, 1, 1])  # Z26 prices its own three days
    np.testing.assert_allclose(enc.slot_exposure, [10.0, 10.0, 10.0])  # 20 and -10 a day
    np.testing.assert_array_equal(enc.offset, [-4_200.0, 2_160.0])  # the fixed leg, once each
    np.testing.assert_array_equal(enc.offset_of_group, [-2_040.0])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-09"))
    np.testing.assert_array_equal(enc.references, [1])
    assert enc.named_slot(0) == "trade 1 at row 1 on 2026-12-02, a day Z26 prices"
    counts = counter.freeze().as_dict()
    assert (
        counts["encoded_components"],
        counts["encoded_observations"],
        counts["encoded_slots"],
    ) == (
        2,
        6,
        3,
    )


# The page's six states and the hand answers, with the quotes read per live reference, one while
# Z26 is live and none after, and the settles read, one per fixed slot.
L3D_LIFECYCLE: list[tuple[str, tuple[float, ...], int, int, int, int, int]] = [
    ("2026-12-02", (74.0, 80.0), 180, 0, 30, 1, 0),
    ("2026-12-03", (74.0, 80.0), 150, 0, 20, 1, 1),
    ("2026-12-04", (74.0, 80.0), 160, 0, 10, 1, 2),
    ("2026-12-07", (74.0, 80.0), 160, 0, 10, 1, 2),
    ("2026-12-08", (80.0,), 150, 0, 0, 0, 3),
    ("2026-12-09", (80.0,), 0, 150, 0, 0, 3),
]
L3D_IDS = [
    "2 Dec, all three live",
    "3 Dec, the 2nd fixed",
    "4 Dec, the 2nd and 3rd fixed",
    "7 Dec, the last live on its own day",
    "8 Dec, all three fixed, unpaid",
    "9 Dec, paid",
]


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta", "live_reads", "fixings_read"),
    L3D_LIFECYCLE,
    ids=L3D_IDS,
)
def test_the_last3day_batch_marks_fixes_and_pays_as_the_page_says(
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
    live_reads: int,
    fixings_read: int,
) -> None:
    result, counter = l3d_evaluated(as_of, quotes)
    assert result.mark == pytest.approx(mark)
    assert result.cash == pytest.approx(cash)
    assert result.lot_delta_total == pytest.approx(delta)
    np.testing.assert_allclose(
        result.price_sensitivity, [delta]
    )  # Z26, the one contract on the axis
    assert result.codes() == ("Z26",)
    assert result.dv01 == 0.0
    counts = counter.freeze().as_dict()
    assert (counts["live_prices_read"], counts["fixings_read"], counts["kernel"]) == (
        live_reads,
        fixings_read,
        1,
    )
    assert counts["prepared_slots"] == 3


def test_a_tick_moves_the_live_last3day_slots_and_a_corrected_fixing_takes_a_new_history() -> None:
    terms = l3d_terms()
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    history = history_by_day(SYN, "2026-12-03", SYN_SETTLES)
    prep = prepared_trades(enc, history, WorkCounter())
    assert trade_results(prep, quoted(history, 74.0, 80.0), WorkCounter()).mark == pytest.approx(
        150
    )
    ticked = trade_results(prep, quoted(history, 75.0, 80.0), WorkCounter())
    assert (ticked.mark, ticked.lot_delta_total) == (pytest.approx(170), pytest.approx(20))
    corrected = history_by_day(SYN, "2026-12-03", {**SYN_SETTLES, "2026-12-02": 72.0})
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(corrected, 74.0, 80.0), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'SYN', expected the one the trades were prepared "
        "against"
    )
    again = prepared_trades(enc, corrected, WorkCounter())
    assert trade_results(again, quoted(corrected, 74.0, 80.0), WorkCounter()).mark == pytest.approx(
        160
    )


def test_the_last3day_batch_equals_its_singletons_summed_whatever_the_order() -> None:
    both, _ = l3d_evaluated("2026-12-03", (74.0, 80.0))
    a, _ = l3d_evaluated("2026-12-03", (74.0, 80.0), l3d_terms((60.0,), (70.0,), (1,)))
    b, _ = l3d_evaluated("2026-12-03", (74.0, 80.0), l3d_terms((-30.0,), (72.0,), (1,)))
    reversed_rows, _ = l3d_evaluated(
        "2026-12-03", (74.0, 80.0), l3d_terms((-30.0, 60.0), (72.0, 70.0), (1, 1))
    )
    twice, _ = l3d_evaluated(
        "2026-12-03", (74.0, 80.0), l3d_terms((60.0, -30.0, 60.0), (70.0, 72.0, 70.0), (1, 1, 1))
    )
    assert (a.mark, b.mark) == (pytest.approx(180), pytest.approx(-30))  # 1,420 + 2,960 - 4,200
    assert both.mark == pytest.approx(a.mark + b.mark) == pytest.approx(150)
    assert reversed_rows.mark == pytest.approx(both.mark)
    assert reversed_rows.lot_delta_total == pytest.approx(both.lot_delta_total) == pytest.approx(20)
    assert twice.mark == pytest.approx(both.mark + a.mark)
    assert twice.lot_delta_total == pytest.approx(both.lot_delta_total + a.lot_delta_total)


def test_a_zero_quantity_row_keeps_its_three_slots_and_its_contract_at_nothing() -> None:
    # A row kept ready on F27 adds F27's three days to the axis at no exposure and changes no
    # number of A and B; one on Z26 adds nothing at all, its days being theirs.
    with_f27 = l3d_terms((60.0, -30.0, 0.0), (70.0, 72.0, 71.0), (1, 1, 2))
    enc = encoded(with_f27, observed_of(with_f27), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.slot_group, [0, 0, 0, 1, 1, 1])
    np.testing.assert_allclose(enc.slot_exposure, [10.0, 10.0, 10.0, 0.0, 0.0, 0.0])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-09", "2027-01-11"))
    result, _ = l3d_evaluated("2026-12-03", (74.0, 80.0), with_f27)
    assert (result.mark, result.cash) == (pytest.approx(150), 0.0)
    np.testing.assert_allclose(result.price_sensitivity, [20.0, 0.0])
    assert result.codes() == ("Z26", "F27")
    with_zero_z26 = l3d_terms((60.0, -30.0, 0.0), (70.0, 72.0, 71.0), (1, 1, 1))
    same, _ = l3d_evaluated("2026-12-03", (74.0, 80.0), with_zero_z26)
    assert (same.mark, same.lot_delta_total) == (pytest.approx(150), pytest.approx(20))
    assert same.prepared.encoded.slot_group.size == 3


# --- the asian method: every pricing day of the month, an equal share each, one payment -------
# asian-trades.md's synthetic ethane example: an index quoted in USD per gallon and settling in
# USD, one specification GAL of one gallon, X26 expiring 30 November 2026, Z26 31 December, F27
# 29 January 2027 and G27 26 February, the market closed on 25 December and 1 January; the
# payment calendar closed on 1 January. Two trades of Z26, A 4,400 gallons at 0.25 and B -2,200
# at 0.26, pay two business days after the month's last pricing day, 31 December: 5 January, the
# 1st closed and the 4th the first business day. By hand: December has 22 pricing days, so A puts
# 200 gallons on each and B -100, 100 a day compressed, and the fixed leg is -4,400 * 0.25 +
# 2,200 * 0.26 = -528, once; live at a projection of 0.28 the mark is -528 + 2,200 * 0.28 = 88
# and the delta 2,200; the 1st fixed at 0.24, -528 + 24 + 2,100 * 0.28 = 84 and 2,100; the 2nd at
# 0.30 too, 86 and 2,000; eighteen fixed on the 25th, the 1st, the 2nd and sixteen at 0.28, 86 and
# 400; twenty-one fixed on the 31st with the last live, 86 and 100; all fixed on 1 January, the
# 31st at 0.26, 84 unpaid through the 4th; paid on the 5th, 84 of cash and no mark. The daily
# series: 0.24, 0.30, 0.28 on every other December day, 0.26 on the 31st, 0.30 in January; the
# live input is the projection of the month's remaining days, not a quote of the whole month's
# average, and the delta is to that input.

ETHANE_HOLIDAYS = ("2026-12-25", "2027-01-01")
ETHANE = an_index(
    "ETHANE",
    (("X26", "2026-11-30"), ("Z26", "2026-12-31"), ("F27", "2027-01-29"), ("G27", "2027-02-26")),
    ETHANE_HOLIDAYS,
    ("USD", "GAL"),
    ("VOLUME", "GAL"),
    ("GAL", 1.0, "GAL"),
)
PAY_JAN_1 = holiday_calendar(dates("2027-01-01"))


def pricing_days(first: str, after: str) -> list[str]:
    """Every Monday to Friday from the first day to the day before the next, less the ethane
    market's holidays: the fixture's own arithmetic, never the kernel's."""
    days = np.arange(np.datetime64(first), np.datetime64(after))
    return [str(d) for d in days[np.is_busday(days, holidays=dates(*ETHANE_HOLIDAYS))]]


DECEMBER = pricing_days("2026-12-01", "2027-01-01")
JANUARY = pricing_days("2027-01-01", "2027-02-01")
ETHANE_SETTLES = {
    **{d: 0.28 for d in pricing_days("2026-11-30", "2027-01-01")},
    **{d: 0.30 for d in JANUARY},
    "2026-12-01": 0.24,
    "2026-12-02": 0.30,
    "2026-12-31": 0.26,
}
ASIAN_PAYS = {1: "2027-01-05", 2: "2027-02-02"}  # two weekdays after each month's last pricing day


def asian_terms(
    quantities: tuple[float, ...] = (4_400.0, -2_200.0),
    prices: tuple[float, ...] = (0.25, 0.26),
    contracts: tuple[int, ...] = (1, 1),
    settlement: Settlement = Settlement.FINANCIAL,
    ix: Index = ETHANE,
    pays: dict[int, str] = ASIAN_PAYS,
) -> ResolvedTrades:
    """Trades on the ethane index under asian, A and B of Z26 unless said, each paying two
    weekdays after its contract's last pricing day, the dates the resolution would make."""
    n = len(quantities)
    payment = (
        None
        if settlement is Settlement.PHYSICAL
        else PaymentTerms(np.full(n, 2), (PAY_JAN_1,) * n, dates(*(pays[c] for c in contracts)))
    )
    return resolved_trades(
        FIXED_FLOAT,
        ix,
        spec(n),
        Route.CLEARED,
        settlement,
        *picks(ScheduleMethod.ASIAN, QuantityPer.MONTH, n),
        np.arange(1, n + 1, dtype=np.int64),
        ("Prototype Clearing",) * n,
        None,
        dates(*(["2026-11-20"] * n)),
        np.arange(n, dtype=np.intp),
        rows(*contracts),
        numbers(*quantities),
        *bounds_of(ix, rows(*contracts)),
        numbers(*prices),
        payment,
    )


def asian_evaluated(
    as_of: str,
    quotes: tuple[float, ...],
    terms: ResolvedTrades | None = None,
    settles: dict[str, float] = ETHANE_SETTLES,
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = asian_terms() if terms is None else terms
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = history_by_day(ETHANE, as_of, settles)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


def test_asian_observes_every_pricing_day_of_the_contracts_month() -> None:
    obs = observed(
        by(ScheduleMethod.ASIAN, 2), ETHANE, rows(1, 2), *bounds_of(ETHANE, rows(1, 2)), unlabeled
    )
    assert len(DECEMBER) == 22 and len(JANUARY) == 20
    np.testing.assert_array_equal(obs.component, [0] * 22 + [1] * 20)
    np.testing.assert_array_equal(obs.date, dates(*DECEMBER, *JANUARY))
    np.testing.assert_allclose(obs.weight, [1 / 22] * 22 + [1 / 20] * 20)
    assert DECEMBER[:5] == ["2026-12-01", "2026-12-02", "2026-12-03", "2026-12-04", "2026-12-07"]
    assert DECEMBER[-4:] == ["2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31"]
    assert JANUARY[0] == "2027-01-04" and JANUARY[-1] == "2027-01-29"


def test_a_month_without_a_pricing_day_is_refused_by_its_contract_under_asian() -> None:
    closed = an_index(
        "x",
        (("F27", "2027-01-29"), ("G27", "2027-02-26"), ("H27", "2027-03-31")),
        tuple(pricing_days("2027-02-01", "2027-03-01")),
        ("USD", "GAL"),
        ("VOLUME", "GAL"),
        ("GAL", 1.0, "GAL"),
    )
    with pytest.raises(ValueError) as refused:
        observed(
            by(ScheduleMethod.ASIAN, 1), closed, rows(1), *bounds_of(closed, rows(1)), unlabeled
        )
    assert str(refused.value) == (
        "G27 of trade at row 1 has no pricing day from 2027-02-01 to 2027-02-28, expected a Monday "
        "to Friday of the days it covers the index's market is open on; the asian method averages "
        "the pricing days a component covers"
    )


def test_an_asian_month_another_contract_prices_takes_the_days_contracts_when_encoded() -> None:
    # NYMEX NG's Z26 expires on 25 November: F27 prices December's days through its own expiry on
    # the 29th and G27 the 30th and 31st, so an asian Z26 on that schedule observes its 22 days
    # with F27 and then G27 as their references, the booked contract keeping the fixed leg and
    # the payment, nothing truncated or substituted; calendar-driven-asian-references.md.
    ng_like = an_index(
        "x",
        (
            ("X26", "2026-10-28"),
            ("Z26", "2026-11-25"),
            ("F27", "2026-12-29"),
            ("G27", "2027-01-27"),
        ),
        ("2026-11-26", "2026-12-25"),
        ("USD", "GAL"),
        ("VOLUME", "GAL"),
        ("GAL", 1.0, "GAL"),
    )
    terms = asian_terms(ix=ng_like)
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.group_contract, [1])  # booked as Z26, one group
    np.testing.assert_array_equal(enc.slot_reference, [2] * 20 + [3] * 2)  # F27, then G27
    np.testing.assert_array_equal(enc.references, [2, 3])
    np.testing.assert_array_equal(enc.payment_date, dates("2027-01-05"))
    np.testing.assert_allclose(enc.slot_exposure, [100.0] * 22)
    assert enc.named_slot(0) == "trade 1 at row 1 on 2026-12-01, a day F27 prices"
    assert enc.named_slot(21) == "trade 1 at row 1 on 2026-12-31, a day G27 prices"


def test_a_physical_asian_future_is_refused_by_the_kernel() -> None:
    with pytest.raises(ValueError) as refused:
        asian_terms(settlement=Settlement.PHYSICAL)
    assert str(refused.value) == (
        "settlement_method is 'physical', expected 'financial' with the asian method of trade 1 "
        "at row 1; an asian future is cash settled on the average of its month's pricing days"
    )


def test_the_asian_batch_encodes_22_slots_of_100_and_one_fixed_leg() -> None:
    terms = asian_terms()
    counter = WorkCounter()
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    np.testing.assert_array_equal(enc.slot_date, dates(*DECEMBER))
    np.testing.assert_array_equal(enc.slot_reference, [1] * 22)  # Z26 prices its own month
    np.testing.assert_allclose(enc.slot_exposure, [100.0] * 22)  # 200 and -100 a day
    np.testing.assert_allclose(enc.offset, [-1_100.0, 572.0])  # the fixed leg, once each
    np.testing.assert_allclose(enc.offset_of_group, [-528.0])
    np.testing.assert_array_equal(enc.payment_date, dates("2027-01-05"))
    np.testing.assert_array_equal(enc.references, [1])
    assert enc.named_slot(0) == "trade 1 at row 1 on 2026-12-01, a day Z26 prices"
    counts = counter.freeze().as_dict()
    assert (
        counts["encoded_components"],
        counts["encoded_observations"],
        counts["encoded_slots"],
    ) == (
        2,
        44,
        22,
    )


# The page's eight states and the hand answers, with the quotes read per live reference, one
# while Z26 is live and none after, and the settles read, one per fixed slot.
LIVE_QUOTES = (0.28, 0.30, 0.32)
LATER_QUOTES = (0.30, 0.32)
ASIAN_LIFECYCLE: list[tuple[str, tuple[float, ...], int, int, int, int, int]] = [
    ("2026-12-01", LIVE_QUOTES, 88, 0, 2_200, 1, 0),
    ("2026-12-02", LIVE_QUOTES, 84, 0, 2_100, 1, 1),
    ("2026-12-03", LIVE_QUOTES, 86, 0, 2_000, 1, 2),
    ("2026-12-25", LIVE_QUOTES, 86, 0, 400, 1, 18),
    ("2026-12-31", LIVE_QUOTES, 86, 0, 100, 1, 21),
    ("2027-01-01", LATER_QUOTES, 84, 0, 0, 0, 22),
    ("2027-01-04", LATER_QUOTES, 84, 0, 0, 0, 22),
    ("2027-01-05", LATER_QUOTES, 0, 84, 0, 0, 22),
]
ASIAN_IDS = [
    "1 Dec, all live",
    "2 Dec, one fixed",
    "3 Dec, two fixed",
    "25 Dec, eighteen fixed",
    "31 Dec, the last live on its own day",
    "1 Jan, all fixed, unpaid",
    "4 Jan, still unpaid",
    "5 Jan, paid",
]


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta", "live_reads", "fixings_read"),
    ASIAN_LIFECYCLE,
    ids=ASIAN_IDS,
)
def test_the_asian_batch_marks_fixes_and_pays_as_the_page_says(
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
    live_reads: int,
    fixings_read: int,
) -> None:
    result, counter = asian_evaluated(as_of, quotes)
    assert result.mark == pytest.approx(mark)
    assert result.cash == pytest.approx(cash)
    assert result.lot_delta_total == pytest.approx(delta)
    np.testing.assert_allclose(
        result.price_sensitivity, [delta]
    )  # Z26, the one contract on the axis
    assert result.codes() == ("Z26",)
    assert result.dv01 == 0.0
    counts = counter.freeze().as_dict()
    assert (counts["live_prices_read"], counts["fixings_read"], counts["kernel"]) == (
        live_reads,
        fixings_read,
        1,
    )
    assert counts["prepared_slots"] == 22
    live_slots = int((result.prepared.dated_live_exposure != 0).sum())
    assert live_slots * 100 == delta


def test_a_tick_moves_the_live_asian_slots_and_a_corrected_fixing_takes_a_new_history() -> None:
    terms = asian_terms()
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    history = history_by_day(ETHANE, "2026-12-02", ETHANE_SETTLES)
    prep = prepared_trades(enc, history, WorkCounter())
    assert trade_results(prep, quoted(history, *LIVE_QUOTES), WorkCounter()).mark == pytest.approx(
        84
    )
    ticked = trade_results(prep, quoted(history, 0.29, 0.30, 0.32), WorkCounter())
    assert (ticked.mark, ticked.lot_delta_total) == (pytest.approx(105), pytest.approx(2_100))
    corrected = history_by_day(ETHANE, "2026-12-02", {**ETHANE_SETTLES, "2026-12-01": 0.25})
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(corrected, *LIVE_QUOTES), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'ETHANE', expected the one the trades were "
        "prepared against"
    )
    again = prepared_trades(enc, corrected, WorkCounter())
    assert trade_results(
        again, quoted(corrected, *LIVE_QUOTES), WorkCounter()
    ).mark == pytest.approx(85)


def test_a_payment_calendar_closed_on_the_fourth_pays_on_the_sixth() -> None:
    # The same batch under a payment calendar closed on 1 and 4 January pays on the 6th: 84 of
    # mark and no cash on the 5th, the whole amount cash on the 6th. The dates are the
    # resolution's rule, counted by hand here; the creation tests count them through it.
    terms = asian_terms(pays={1: "2027-01-06", 2: "2027-02-02"})
    on_fifth, _ = asian_evaluated("2027-01-05", LATER_QUOTES, terms)
    on_sixth, _ = asian_evaluated("2027-01-06", LATER_QUOTES, terms)
    assert (on_fifth.mark, on_fifth.cash) == (pytest.approx(84), 0.0)
    assert (on_sixth.mark, on_sixth.cash) == (0.0, pytest.approx(84))


def test_the_asian_batch_equals_its_singletons_summed_whatever_the_order() -> None:
    both, _ = asian_evaluated("2026-12-02", LIVE_QUOTES)
    a, _ = asian_evaluated("2026-12-02", LIVE_QUOTES, asian_terms((4_400.0,), (0.25,), (1,)))
    b, _ = asian_evaluated("2026-12-02", LIVE_QUOTES, asian_terms((-2_200.0,), (0.26,), (1,)))
    reversed_rows, _ = asian_evaluated(
        "2026-12-02", LIVE_QUOTES, asian_terms((-2_200.0, 4_400.0), (0.26, 0.25), (1, 1))
    )
    twice, _ = asian_evaluated(
        "2026-12-02",
        LIVE_QUOTES,
        asian_terms((4_400.0, -2_200.0, 4_400.0), (0.25, 0.26, 0.25), (1, 1, 1)),
    )
    assert (a.mark, b.mark) == (pytest.approx(124), pytest.approx(-40))  # 48 + 1,176 - 1,100
    assert both.mark == pytest.approx(a.mark + b.mark) == pytest.approx(84)
    assert reversed_rows.mark == pytest.approx(both.mark)
    assert (
        reversed_rows.lot_delta_total == pytest.approx(both.lot_delta_total) == pytest.approx(2_100)
    )
    assert twice.mark == pytest.approx(both.mark + a.mark)
    assert twice.lot_delta_total == pytest.approx(both.lot_delta_total + a.lot_delta_total)


def test_a_zero_quantity_row_keeps_its_months_days_at_nothing_under_asian() -> None:
    with_f27 = asian_terms((4_400.0, -2_200.0, 0.0), (0.25, 0.26, 0.27), (1, 1, 2))
    enc = encoded(with_f27, observed_of(with_f27), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.slot_group, [0] * 22 + [1] * 20)
    np.testing.assert_allclose(enc.slot_exposure, [100.0] * 22 + [0.0] * 20)
    np.testing.assert_array_equal(enc.payment_date, dates("2027-01-05", "2027-02-02"))
    result, _ = asian_evaluated("2026-12-02", LIVE_QUOTES, with_f27)
    assert (result.mark, result.cash) == (pytest.approx(84), 0.0)
    np.testing.assert_allclose(result.price_sensitivity, [2_100.0, 0.0])
    assert result.codes() == ("Z26", "F27")


# --- the calendar day basis: the entered quantity times the days each month covers ------------
# trade-periods-and-bal.md, slice A: under month the entered quantity stands in every contract
# month, unprorated; under calday it is per calendar day, weekends and holidays included, and the
# kernel forms each component's quantity once, the entered quantity times the days the resolution
# says it covers, the whole month here. The encoding converts that quantity and nothing later
# scales again, so a calday batch values as the month batch of its component quantities.

# An index of the months the ticket's acceptance list names: November and December 2026, 30 and
# 31 days, February 2027, 28, and February 2028, 29.
LEAP = an_index(
    "LEAP",
    (("X26", "2026-11-25"), ("Z26", "2026-12-29"), ("G27", "2027-02-24"), ("G28", "2028-02-25")),
)


def basis_terms(
    ix: Index,
    contracts: tuple[int, ...],
    quantities: tuple[float, ...],
    basis: QuantityPer = QuantityPer.CALDAY,
    period: tuple[NDArray[np.datetime64], NDArray[np.datetime64]] | None = None,
    occurrence: tuple[int, ...] | None = None,
) -> ResolvedTrades:
    """Physical lastday trades at 3.0 on an index under the basis given, one occurrence per
    component unless said, each covering its whole month unless a period is given."""
    n = len(contracts)
    on = rows(*contracts)
    occurrences = n if occurrence is None else max(occurrence) + 1
    return resolved_trades(
        FIXED_FLOAT,
        ix,
        spec(occurrences),
        Route.CLEARED,
        Settlement.PHYSICAL,
        *picks(ScheduleMethod.LASTDAY, basis, occurrences),
        np.arange(1, occurrences + 1, dtype=np.int64),
        None,
        None,
        np.repeat(day("2026-10-06"), occurrences),
        np.arange(n, dtype=np.intp) if occurrence is None else rows(*occurrence),
        on,
        numbers(*quantities),
        *(bounds_of(ix, on) if period is None else period),
        numbers(*([3.0] * n)),
        None,
    )


def test_a_calday_quantity_is_the_entered_quantity_times_the_days_its_month_covers() -> None:
    terms = basis_terms(LEAP, (0, 1, 2, 3), (100, 100, 100, 100))
    np.testing.assert_array_equal(terms.covered_days, [30, 31, 28, 29])
    np.testing.assert_array_equal(terms.component_quantity, [3_000, 3_100, 2_800, 2_900])
    np.testing.assert_array_equal(terms.quantity, [100, 100, 100, 100])  # kept as entered
    assert (terms.quantity_per == BASES.index(QuantityPer.CALDAY)).all()
    assert terms.covered_days.dtype == np.dtype(np.int64)
    assert not terms.covered_days.flags.writeable
    assert not terms.component_quantity.flags.writeable
    # Under month the same rows hold the entered quantity in every month, whatever its length.
    month = basis_terms(LEAP, (0, 1, 2, 3), (100, 100, 100, 100), QuantityPer.MONTH)
    np.testing.assert_array_equal(month.covered_days, [30, 31, 28, 29])
    np.testing.assert_array_equal(month.component_quantity, [100, 100, 100, 100])


def test_a_strip_at_100_a_day_covers_3000_and_3100_and_at_100_a_month_100_and_100() -> None:
    # X26-Z26 as the two components of one occurrence, on the NG index: November and December.
    strip = basis_terms(NG, (0, 1), (100, 100), occurrence=(0, 0))
    np.testing.assert_array_equal(strip.component_quantity, [3_000, 3_100])
    month = basis_terms(NG, (0, 1), (100, 100), QuantityPer.MONTH, occurrence=(0, 0))
    np.testing.assert_array_equal(month.component_quantity, [100, 100])
    # Signed and duplicate rows, and a row kept ready at nothing, keep the arithmetic.
    signed = basis_terms(
        NG,
        (0, 1) * 4,
        (-100, -100, 100, 100, -100, -100, 0, 0),
        occurrence=(0, 0, 1, 1, 2, 2, 3, 3),
    )
    np.testing.assert_array_equal(signed.covered_days, [30, 31] * 4)
    np.testing.assert_array_equal(
        signed.component_quantity, [-3_000, -3_100, 3_000, 3_100, -3_000, -3_100, 0, 0]
    )
    np.testing.assert_array_equal(signed.quantity, [-100, -100, 100, 100, -100, -100, 0, 0])


def test_the_encoding_converts_the_component_quantity_and_nothing_later_scales_again() -> None:
    # One lot of Z26 a day at 3.0 against one lot a month: 31 lots of 10,000 MMBtu, a quote
    # quantity of 310,000 against 10,000; valued on 24 November at 3.20, a mark of 62,000 against
    # 2,000 and a delta of 310,000 against 10,000, each number 31 times the month's, since the
    # quantity was formed once and the encoding, the preparation and the evaluation take it as
    # it is.
    def valued(basis: QuantityPer) -> tuple[NDArray[np.float64], TradeResults]:
        terms = basis_terms(NG, (1,), (1,), basis)
        enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
        history = history_on(NG, "2026-11-24", {})
        prep = prepared_trades(enc, history, WorkCounter())
        return enc.quote_quantity, trade_results(prep, quoted(history, 3.20, 3.50), WorkCounter())

    by_day_quoted, by_day = valued(QuantityPer.CALDAY)
    by_month_quoted, by_month = valued(QuantityPer.MONTH)
    np.testing.assert_array_equal(by_day_quoted, [310_000])
    np.testing.assert_array_equal(by_month_quoted, [10_000])
    assert by_day.mark == pytest.approx(62_000) and by_month.mark == pytest.approx(2_000)
    assert by_day.lot_delta_total == pytest.approx(31)  # a lot a day, 31 days
    assert by_month.lot_delta_total == pytest.approx(1)
    assert by_day.codes() == by_month.codes() == ("Z26",)


def test_a_components_days_are_per_component_in_order_in_one_month_and_the_product_finite() -> None:
    with pytest.raises(ValueError) as refused:
        basis_terms(
            NG, (1, 2), (1, 1), period=(dates("2026-12-01"), dates("2026-12-31", "2027-01-31"))
        )
    assert str(refused.value) == "start_date has 1 rows, expected 2, one per component"
    with pytest.raises(ValueError) as refused:
        basis_terms(
            NG,
            (1, 2),
            (1, 1),
            period=(dates("2026-12-01", "2027-01-15"), dates("2026-12-31", "2027-01-14")),
        )
    assert str(refused.value) == (
        "end_date of trade 2 at row 2 is 2027-01-14, expected a day on or after its "
        "start_date, 2027-01-15"
    )
    with pytest.raises(ValueError) as refused:
        basis_terms(NG, (1,), (1,), period=(dates("2026-12-01"), dates("2027-01-31")))
    assert str(refused.value) == (
        "trade 1 at row 1 covers 2026-12-01 to 2027-01-31, expected one calendar month per "
        "component"
    )
    with pytest.raises(ValueError) as refused:
        basis_terms(NG, (1,), (1e308,))
    assert str(refused.value) == (
        "quantity of trade 1 at row 1 is 1e+308 over 31 days, expected a finite quantity"
    )
    # The same entered quantity is a whole, finite count under month and stands.
    assert basis_terms(NG, (1,), (1e308,), QuantityPer.MONTH).component_quantity[0] == 1e308


def test_a_quantity_at_the_rounded_bound_is_refused_with_its_infinite_product() -> None:
    # The review of #159: the largest finite number over 31 days is a quotient that rounds up, so a
    # quantity exactly at it passed a look at the bound and its product was infinite, the offset a
    # NaN. The product itself is looked at now, the overflow handled where it happens, positive or
    # negative; one step below the bound the product is finite and stands.
    at_bound = 5.799010112459083e306
    assert at_bound * 31 == float("inf")
    for quantity in (at_bound, -at_bound):
        with pytest.raises(ValueError) as refused:
            basis_terms(NG, (1,), (quantity,))
        assert str(refused.value) == (
            f"quantity of trade 1 at row 1 is {quantity!r} over 31 days, expected a finite quantity"
        )
    below = float(np.nextafter(at_bound, 0))
    terms = basis_terms(NG, (1,), (below,))
    assert terms.component_quantity[0] == below * 31 and np.isfinite(terms.component_quantity[0])
    month = basis_terms(NG, (1,), (-below,), QuantityPer.MONTH)  # a whole count under month
    assert month.component_quantity[0] == -below and month.covered_days[0] == 31


# --- explicit dates: a booked period within a month, its days and its value --------------------
# trade-periods-and-bal.md, slice C: a component covers the days it is given, start to end, within
# its contract's month; the kernel counts the days and the schedule method prices over them, asian
# over a part of a month and the expiry-based methods refusing one. The page's booked period, 15 to
# 31 December 2026 on the ethane index: 17 covered days, 12 observations a twelfth each, the fixed
# leg -500 and the payment 5 January; the fixings 0.24 on the 15th, 0.26 on the 31st and 0.28 on
# every other pricing day; the live projection 0.28.

PERIOD_SETTLES = {
    **{d: 0.28 for d in pricing_days("2026-11-30", "2027-01-01")},
    "2026-12-15": 0.24,
    "2026-12-31": 0.26,
}
PERIOD_DAYS = [
    "2026-12-15",
    "2026-12-16",
    "2026-12-17",
    "2026-12-18",
    "2026-12-21",
    "2026-12-22",
    "2026-12-23",
    "2026-12-24",
    "2026-12-28",
    "2026-12-29",
    "2026-12-30",
    "2026-12-31",
]


def period_terms(
    periods: tuple[tuple[str, str], ...] = (("2026-12-15", "2026-12-31"),),
    quantities: tuple[float, ...] = (2_000.0,),
    basis: QuantityPer = QuantityPer.MONTH,
    pays: tuple[str, ...] | None = None,
    price: float = 0.25,
) -> ResolvedTrades:
    """Asian trades of Z26 on the ethane index at 0.25 unless said, financial and cleared, each
    covering the days given and paying on the day given, the dates the resolution would make."""
    n = len(periods)
    return resolved_trades(
        FIXED_FLOAT,
        ETHANE,
        spec(n),
        Route.CLEARED,
        Settlement.FINANCIAL,
        *picks(ScheduleMethod.ASIAN, basis, n),
        np.arange(1, n + 1, dtype=np.int64),
        ("Prototype Clearing",) * n,
        None,
        np.repeat(day("2026-11-20"), n),
        np.arange(n, dtype=np.intp),
        rows(*([1] * n)),
        numbers(*quantities),
        dates(*(start for start, _ in periods)),
        dates(*(end for _, end in periods)),
        numbers(*([price] * n)),
        PaymentTerms(
            np.full(n, 2), (PAY_JAN_1,) * n, dates(*(("2027-01-05",) * n if pays is None else pays))
        ),
    )


def period_valued(
    terms: ResolvedTrades,
    as_of: str,
    quotes: tuple[float, ...],
    settles: dict[str, float] = PERIOD_SETTLES,
) -> TradeResults:
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    history = history_by_day(ETHANE, as_of, settles)
    prep = prepared_trades(enc, history, WorkCounter())
    return trade_results(prep, quoted(history, *quotes), WorkCounter())


def test_a_booked_period_within_a_month_covers_its_days_and_observes_its_pricing_days() -> None:
    terms = period_terms()
    np.testing.assert_array_equal(terms.start_date, dates("2026-12-15"))
    np.testing.assert_array_equal(terms.end_date, dates("2026-12-31"))
    np.testing.assert_array_equal(terms.covered_days, [17])
    np.testing.assert_array_equal(terms.component_quantity, [2_000])
    np.testing.assert_array_equal(
        period_terms(basis=QuantityPer.CALDAY).component_quantity, [34_000]
    )
    obs = observed_of(terms)
    assert [str(d) for d in obs.date] == PERIOD_DAYS
    assert obs.component.tolist() == [0] * 12
    np.testing.assert_allclose(obs.weight, np.full(12, 1 / 12))
    enc = encoded(terms, obs, UNITS, WorkCounter())
    np.testing.assert_allclose(enc.offset, [-500.0])
    np.testing.assert_allclose(enc.slot_exposure, np.full(12, 2_000 / 12))
    assert enc.payment_date is not None and str(enc.payment_date[0]) == "2027-01-05"


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta"),
    [
        ("2026-12-15", (0.28, 0.30, 0.32), 60, 0, 2_000),
        ("2026-12-16", (0.28, 0.30, 0.32), 160 / 3, 0, 5_500 / 3),
        ("2027-01-01", (0.30, 0.32), 50, 0, 0),
        ("2027-01-05", (0.30, 0.32), 0, 50, 0),
    ],
    ids=["15 Dec, all live", "16 Dec, one fixed", "1 Jan, all fixed, unpaid", "5 Jan, paid"],
)
def test_the_booked_period_values_as_the_page_says_and_calday_scales_it_by_its_days(
    as_of: str, quotes: tuple[float, ...], mark: float, cash: float, delta: float
) -> None:
    result = period_valued(period_terms(), as_of, quotes)
    assert result.mark == pytest.approx(mark) and result.cash == pytest.approx(cash)
    assert result.lot_delta_total == pytest.approx(delta)
    # 2,000 a calendar day over 17 days is 34,000 units: every number seventeen times the month's,
    # the dates and the twelve weights unchanged; 1,020 of mark on the 15th and 850 of cash paid.
    by_day = period_valued(period_terms(basis=QuantityPer.CALDAY), as_of, quotes)
    assert by_day.mark == pytest.approx(17 * mark) and by_day.cash == pytest.approx(17 * cash)
    assert by_day.lot_delta_total == pytest.approx(17 * delta)


def test_a_fixing_before_the_period_moves_nothing_of_it() -> None:
    changed = {**PERIOD_SETTLES, "2026-12-14": 0.50, "2026-12-01": 0.10}
    for as_of, quotes in (("2026-12-16", (0.28, 0.30, 0.32)), ("2027-01-05", (0.30, 0.32))):
        before = period_valued(period_terms(), as_of, quotes)
        after = period_valued(period_terms(), as_of, quotes, changed)
        assert (before.mark, before.cash) == (after.mark, after.cash)
        np.testing.assert_array_equal(before.price_sensitivity, after.price_sensitivity)


def test_two_rows_on_one_contract_from_different_starts_value_like_their_singletons() -> None:
    # P from the 15th and Q from the 1st, both to the 31st and so both paying 5 January: one batch
    # on 2 December is the two alone summed, Q's 1 December fixed at 0.28 and the rest live.
    both = period_terms(
        (("2026-12-15", "2026-12-31"), ("2026-12-01", "2026-12-31")), (2_000, 2_200)
    )
    quotes = (0.28, 0.30, 0.32)
    together = period_valued(both, "2026-12-02", quotes)
    p = period_valued(period_terms(), "2026-12-02", quotes)
    q = period_valued(period_terms((("2026-12-01", "2026-12-31"),), (2_200,)), "2026-12-02", quotes)
    assert together.mark == pytest.approx(p.mark + q.mark) == pytest.approx(126)
    assert (
        together.lot_delta_total
        == pytest.approx(p.lot_delta_total + q.lot_delta_total)
        == pytest.approx(4_100)
    )
    np.testing.assert_array_equal(observed_of(both).component, [0] * 12 + [1] * 22)
    # Ending on different days they pay on different days, P2 on 4 January and P1 on the 5th:
    # two groups of Z26, the earlier day first, the two singletons summed in every state and
    # each cash on its own day, P2's 1,298/21, twenty days at 0.28 and the 15th at 0.24 over
    # its 21 days, on the 4th beside P1's 50 still in mark, and both cash on the 5th.
    ends = period_terms(
        (("2026-12-15", "2026-12-31"), ("2026-12-01", "2026-12-30")),
        (2_000, 2_200),
        pays=("2027-01-05", "2027-01-04"),
    )
    enc = encoded(ends, observed_of(ends), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.group_contract, [1, 1])
    np.testing.assert_array_equal(enc.payment_date, dates("2027-01-04", "2027-01-05"))
    np.testing.assert_array_equal(enc.group_of_component, [1, 0])
    assert enc.slot_group.size == 21 + 12 and enc.references.size == 1
    shorter = period_terms((("2026-12-01", "2026-12-30"),), (2_200,), pays=("2027-01-04",))
    for as_of, state_quotes in (
        ("2026-12-02", quotes),
        ("2027-01-04", (0.30, 0.32)),
        ("2027-01-05", (0.30, 0.32)),
    ):
        apart = period_valued(ends, as_of, state_quotes)
        p1 = period_valued(period_terms(), as_of, state_quotes)
        p2 = period_valued(shorter, as_of, state_quotes)
        assert apart.mark == pytest.approx(p1.mark + p2.mark)
        assert apart.cash == pytest.approx(p1.cash + p2.cash)
        np.testing.assert_allclose(
            apart.price_sensitivity, p1.price_sensitivity + p2.price_sensitivity
        )
    on_fourth = period_valued(ends, "2027-01-04", (0.30, 0.32))
    assert (on_fourth.mark, on_fourth.cash) == (pytest.approx(50), pytest.approx(1_298 / 21))
    np.testing.assert_array_equal(on_fourth.prepared.is_settled, [True, False])
    on_fifth = period_valued(ends, "2027-01-05", (0.30, 0.32))
    assert (on_fifth.mark, on_fifth.cash) == (pytest.approx(0), pytest.approx(50 + 1_298 / 21))


def test_the_expiry_based_methods_refuse_a_part_of_a_month_and_asian_a_part_without_a_day() -> None:
    for method, ix in (
        (ScheduleMethod.LASTDAY, NG),
        (ScheduleMethod.PENULTIMATE, NG),
        (ScheduleMethod.LAST3DAY, SYN),
    ):
        with pytest.raises(ValueError) as refused:
            observed(
                by(method, 1), ix, rows(1), dates("2026-12-15"), dates("2026-12-31"), unlabeled
            )
        assert str(refused.value) == (
            "Z26 of trade at row 1 is covered from 2026-12-15 to 2026-12-31, part of its month, "
            f"expected the whole month under {method.value}; the expiry-based methods take the "
            "contract's month entire, and a part of it prices under asian"
        )
    with pytest.raises(ValueError) as refused:
        observed(
            by(ScheduleMethod.ASIAN, 1),
            ETHANE,
            rows(1),
            dates("2026-12-26"),
            dates("2026-12-27"),
            unlabeled,
        )
    assert str(refused.value) == (
        "Z26 of trade at row 1 has no pricing day from 2026-12-26 to 2026-12-27, expected a Monday "
        "to Friday of the days it covers the index's market is open on; the asian method averages "
        "the pricing days a component covers"
    )


# --- payment groups: two payment days on one contract, multiple-payment-groups.md -------------
# The ticket's synthetic index: USD per MMBTU, one UNIT of one MMBTU, X26 expiring 30 November
# 2026, Z26 Friday 4 December and F27 8 January 2027, no holiday on either calendar. A, 60 of Z26
# at 70 paying one weekday after the last observation, Monday 7 December, and B, -30 at 72 paying
# three weekdays after, Wednesday the 9th, both last3day, so each observes the 2nd, the 3rd and
# the 4th with a third of its quantity. By hand: two components, two groups, six observations and
# six slots off one reference, the fixed legs -4,200 and 2,160, A's 20 and B's -10 a day; all
# three days live at 74, the mark is 60 * 4 - 30 * 2 = 180 and the delta 30; the 2nd fixed at 71,
# 150 and 20; the 3rd at 75 too, 160 and 10; the 4th at 73, the average 73, 150 and nothing live;
# A paid on the 7th, 180 of cash beside B's -30 of mark; B paid on the 9th, 150 of cash, 180 - 30,
# and nothing in mark.
PAYS = an_index(
    "PAYS",
    (("X26", "2026-11-30"), ("Z26", "2026-12-04"), ("F27", "2027-01-08")),
    (),
    lot=("UNIT", 1.0, "MMBTU"),
)
PAYS_SETTLES = {"2026-12-02": 71.0, "2026-12-03": 75.0, "2026-12-04": 73.0}
PAYS_DAYS = dates("2026-12-02", "2026-12-03", "2026-12-04")
# The payment days the resolution would make on the open calendar, by schedule row and lag: Z26's
# last observation is Friday 4 December, F27's Friday 8 January, and 28 weekdays after the one is
# three after the other, Wednesday 13 January.
PAYS_BY_LAG = {
    (1, 1): "2026-12-07",
    (1, 2): "2026-12-08",
    (1, 3): "2026-12-09",
    (1, 28): "2027-01-13",
    (2, 1): "2027-01-11",
    (2, 3): "2027-01-13",
}


def group_terms(
    quantities: tuple[float, ...] = (60.0, -30.0),
    prices: tuple[float, ...] = (70.0, 72.0),
    contracts: tuple[int, ...] = (1, 1),
    lags: tuple[int, ...] = (1, 3),
    pays: tuple[str, ...] | None = None,
    calendars: tuple[HolidayCalendar, ...] | None = None,
) -> ResolvedTrades:
    """Last3day trades on the PAYS index, A and B of Z26 at +1bd and +3bd unless said, each paying
    the weekdays after its contract's last observation its lag counts, on the open calendar unless
    a calendar is given, the dates the resolution would make unless given."""
    n = len(quantities)
    days = (
        dates(*(PAYS_BY_LAG[c, lag] for c, lag in zip(contracts, lags, strict=True)))
        if pays is None
        else dates(*pays)
    )
    return resolved_trades(
        FIXED_FLOAT,
        PAYS,
        spec(n),
        Route.CLEARED,
        Settlement.FINANCIAL,
        *picks(ScheduleMethod.LAST3DAY, QuantityPer.MONTH, n),
        np.arange(1, n + 1, dtype=np.int64),
        ("Prototype Clearing",) * n,
        None,
        dates(*(["2026-11-30"] * n)),
        np.arange(n, dtype=np.intp),
        rows(*contracts),
        numbers(*quantities),
        *bounds_of(PAYS, rows(*contracts)),
        numbers(*prices),
        PaymentTerms(
            np.array(lags, dtype=np.int64),
            (WEEKDAYS,) * n if calendars is None else calendars,
            days,
        ),
    )


def group_evaluated(
    as_of: str,
    quotes: tuple[float, ...],
    terms: ResolvedTrades | None = None,
    settles: dict[str, float] = PAYS_SETTLES,
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = group_terms() if terms is None else terms
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = history_by_day(PAYS, as_of, settles)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


def test_two_payment_days_on_one_contract_encode_as_two_groups_off_one_reference() -> None:
    terms = group_terms()
    counter = WorkCounter()
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    assert enc.payment_date is not None
    np.testing.assert_array_equal(enc.group_contract, [1, 1])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-07", "2026-12-09"))
    np.testing.assert_array_equal(enc.group_of_component, [0, 1])
    np.testing.assert_array_equal(enc.offset, [-4_200.0, 2_160.0])
    np.testing.assert_array_equal(enc.offset_of_group, [-4_200.0, 2_160.0])
    np.testing.assert_array_equal(enc.slot_group, [0, 0, 0, 1, 1, 1])
    np.testing.assert_array_equal(enc.slot_date, np.concatenate([PAYS_DAYS, PAYS_DAYS]))
    np.testing.assert_array_equal(enc.slot_reference, [1] * 6)  # Z26 prices its own three days
    np.testing.assert_allclose(enc.slot_exposure, [20.0] * 3 + [-10.0] * 3)
    np.testing.assert_array_equal(enc.slot_of_observation, [0, 1, 2, 3, 4, 5])
    np.testing.assert_array_equal(enc.references, [1])  # the axis holds Z26 once
    np.testing.assert_array_equal(enc.reference_of_slot, [0] * 6)
    assert enc.named_slot(3) == "trade 2 at row 2 on 2026-12-02, a day Z26 prices"
    assert counter.freeze().as_dict() == {
        "encoded_components": 2,
        "encoded_groups": 2,
        "encoded_observations": 6,
        "encoded_slots": 6,
        "reserved_components": 2,
    }
    # Six slots where one payment day has three: the growth is the payment ownership, eight bytes
    # a slot in each slot column and a day per group, no calendar widened and no history copied.
    assert enc.slot_exposure.nbytes == 48 and enc.payment_date.nbytes == 16


# The ticket's six states and the hand answers, with the quotes read per live reference, one while
# Z26 is live and none after, and the settles read, one per fixed slot, two a day for the two
# groups; and which groups have settled.
GROUP_LIFECYCLE: list[tuple[str, tuple[float, ...], float, float, float, int, int, list[bool]]] = [
    ("2026-12-02", (74.0, 80.0), 180, 0, 30, 1, 0, [False, False]),
    ("2026-12-03", (74.0, 80.0), 150, 0, 20, 1, 2, [False, False]),
    ("2026-12-04", (74.0, 80.0), 160, 0, 10, 1, 4, [False, False]),
    ("2026-12-05", (80.0,), 150, 0, 0, 0, 6, [False, False]),
    ("2026-12-07", (80.0,), -30, 180, 0, 0, 6, [True, False]),
    ("2026-12-09", (80.0,), 0, 150, 0, 0, 6, [True, True]),
]
GROUP_IDS = [
    "2 Dec, all three live",
    "3 Dec, the 2nd fixed",
    "4 Dec, the 3rd fixed too",
    "5 Dec, both final, neither paid",
    "7 Dec, A paid, B unpaid",
    "9 Dec, B paid",
]


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta", "live_reads", "fixings_read", "settled"),
    GROUP_LIFECYCLE,
    ids=GROUP_IDS,
)
def test_two_payment_days_on_one_contract_mark_and_pay_as_the_ticket_says(
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
    live_reads: int,
    fixings_read: int,
    settled: list[bool],
) -> None:
    result, counter = group_evaluated(as_of, quotes)
    assert result.mark == pytest.approx(mark)
    assert result.cash == pytest.approx(cash)
    assert result.lot_delta_total == pytest.approx(delta)
    np.testing.assert_allclose(
        result.price_sensitivity, [delta]
    )  # Z26, the one contract on the axis
    assert result.codes() == ("Z26",)
    counts = counter.freeze().as_dict()
    assert (counts["live_prices_read"], counts["fixings_read"], counts["kernel"]) == (
        live_reads,
        fixings_read,
        1,
    )
    assert (counts["encoded_groups"], counts["prepared_slots"]) == (2, 6)
    np.testing.assert_array_equal(result.prepared.is_settled, settled)  # each on its own day


def test_a_tick_moves_both_groups_live_slots_and_a_corrected_fixing_takes_a_new_history() -> None:
    terms = group_terms()
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    history = history_by_day(PAYS, "2026-12-03", PAYS_SETTLES)
    prep = prepared_trades(enc, history, WorkCounter())
    assert trade_results(prep, quoted(history, 74.0, 80.0), WorkCounter()).mark == pytest.approx(
        150
    )
    counter = WorkCounter()
    ticked = trade_results(prep, quoted(history, 75.0, 80.0), counter)
    assert (ticked.mark, ticked.lot_delta_total) == (pytest.approx(170), pytest.approx(20))
    assert counter.freeze().as_dict() == {
        "kernel": 1,
        "live_prices_read": 1,
    }  # one quote, two groups
    corrected = history_by_day(PAYS, "2026-12-03", {**PAYS_SETTLES, "2026-12-02": 72.0})
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(corrected, 74.0, 80.0), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'PAYS', expected the one the trades were prepared "
        "against"
    )
    again = prepared_trades(enc, corrected, WorkCounter())
    assert trade_results(again, quoted(corrected, 74.0, 80.0), WorkCounter()).mark == pytest.approx(
        160
    )
    assert again.encoded is enc  # the payment days, the weights and the slots stand
    np.testing.assert_allclose(again.price_sensitivity, prep.price_sensitivity)


def test_opposite_positions_paying_on_different_days_net_to_nothing_and_both_pay() -> None:
    # B at -60 and 70: nothing in mark and no delta while both are unpaid, both groups standing;
    # A paid on the 7th, 180 of cash beside -180 of mark; both paid on the 9th, nothing anywhere.
    flat = group_terms((60.0, -60.0), (70.0, 70.0))
    for as_of, quotes in (
        ("2026-12-02", (74.0, 80.0)),
        ("2026-12-04", (74.0, 80.0)),
        ("2026-12-05", (80.0,)),
    ):
        result, _ = group_evaluated(as_of, quotes, flat)
        assert (result.mark, result.cash, result.lot_delta_total) == (
            pytest.approx(0),
            0.0,
            pytest.approx(0),
        )
        enc = result.prepared.encoded
        assert enc.group_contract.size == 2 and enc.slot_group.size == 6
    paid_a, _ = group_evaluated("2026-12-07", (80.0,), flat)
    assert (paid_a.mark, paid_a.cash) == (pytest.approx(-180), pytest.approx(180))
    paid_both, _ = group_evaluated("2026-12-09", (80.0,), flat)
    assert (paid_both.mark, paid_both.cash) == (pytest.approx(0), pytest.approx(0))


def test_matching_payment_days_compress_into_one_group_whatever_made_them() -> None:
    # Both at +3bd: one group of Z26 paying the 9th, three slots and the one-payment answers, 160
    # on the 4th and 150 unpaid on the 7th. +1bd on a payment calendar closed on the 7th and the
    # 8th reaches the 9th as +3bd on the open calendar does, and the two are one group too, the
    # grouping by the day and not by the lag or the calendar. Two contracts paying on one day, Z26
    # at +28bd and F27 at +3bd both on 13 January, stay two groups.
    same = group_terms(lags=(3, 3))
    enc = encoded(same, observed_of(same), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.group_contract, [1])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-09"))
    assert enc.slot_group.size == 3
    on_fourth, _ = group_evaluated("2026-12-04", (74.0, 80.0), same)
    on_seventh, _ = group_evaluated("2026-12-07", (80.0,), same)
    assert (on_fourth.mark, on_seventh.mark, on_seventh.cash) == (
        pytest.approx(160),
        pytest.approx(150),
        0.0,
    )
    closed = holiday_calendar(dates("2026-12-07", "2026-12-08"))
    coalesced = group_terms(
        lags=(1, 3), pays=("2026-12-09", "2026-12-09"), calendars=(closed, WEEKDAYS)
    )
    enc = encoded(coalesced, observed_of(coalesced), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.group_contract, [1])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-09"))
    assert enc.slot_group.size == 3
    apart = group_terms((60.0, 10.0), (70.0, 80.0), (1, 2), (28, 3))
    enc = encoded(apart, observed_of(apart), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.group_contract, [1, 2])
    np.testing.assert_array_equal(enc.payment_date, dates("2027-01-13", "2027-01-13"))
    np.testing.assert_array_equal(enc.references, [1, 2])


def test_one_quote_serves_every_group_of_a_contract_and_the_axis_holds_each_once() -> None:
    # Z26 at +1bd and +3bd beside F27 at +1bd and +3bd, C 10 and D 20 at 80: four groups, twelve
    # slots, two references; on 3 December the tick reads two quotes, Z26's and F27's, for the
    # four groups' ten live slots, the fixings two, the 2nd in each Z26 group, and the delta stands
    # on the two contracts, 20 and 30.
    four = group_terms(
        (60.0, -30.0, 10.0, 20.0), (70.0, 72.0, 80.0, 80.0), (1, 1, 2, 2), (1, 3, 1, 3)
    )
    result, counter = group_evaluated("2026-12-03", (74.0, 80.0), four)
    enc = result.prepared.encoded
    np.testing.assert_array_equal(enc.group_contract, [1, 1, 2, 2])
    np.testing.assert_array_equal(
        enc.payment_date, dates("2026-12-07", "2026-12-09", "2027-01-11", "2027-01-13")
    )
    np.testing.assert_array_equal(enc.references, [1, 2])
    assert enc.slot_group.size == 12
    counts = counter.freeze().as_dict()
    assert (
        counts["encoded_groups"],
        counts["encoded_slots"],
        counts["live_prices_read"],
        counts["fixings_read"],
    ) == (4, 12, 2, 2)
    np.testing.assert_array_equal(result.prepared.live_references, [1, 2])
    assert result.prepared.live_slot.size == 10
    assert result.mark == pytest.approx(150) and result.codes() == ("Z26", "F27")
    np.testing.assert_allclose(result.price_sensitivity, [20.0, 30.0])


def test_a_group_paying_on_or_before_its_last_observation_is_still_refused() -> None:
    # B paying on the 4th, its last observation: its group, the earlier day's and so the first,
    # is refused by its contract and the two days, as one payment day was.
    early = group_terms(pays=("2026-12-07", "2026-12-04"))
    with pytest.raises(ValueError) as refused:
        encoded(early, observed_of(early), UNITS, WorkCounter())
    assert str(refused.value) == (
        "Z26 pays on 2026-12-04, expected a day after its last observation, 2026-12-04, when its "
        "final price exists"
    )


def test_two_payment_days_equal_their_singletons_summed_in_every_state_and_order() -> None:
    # In each of the six states: A and B alone summed, the rows reversed, A twice, a row kept
    # ready at +2bd, a third group paying the 8th and changing nothing, and C of F27 at +1bd
    # beside them, its own group and its own contract on the axis.
    a = group_terms((60.0,), (70.0,), (1,), (1,))
    b = group_terms((-30.0,), (72.0,), (1,), (3,))
    c = group_terms((5.0,), (80.0,), (2,), (1,))
    reversed_rows = group_terms((-30.0, 60.0), (72.0, 70.0), (1, 1), (3, 1))
    twice = group_terms((60.0, -30.0, 60.0), (70.0, 72.0, 70.0), (1, 1, 1), (1, 3, 1))
    with_zero = group_terms((60.0, -30.0, 0.0), (70.0, 72.0, 71.0), (1, 1, 1), (1, 3, 2))
    with_f27 = group_terms((60.0, -30.0, 5.0), (70.0, 72.0, 80.0), (1, 1, 2), (1, 3, 1))
    for as_of, quotes, *_ in GROUP_LIFECYCLE:
        both, _ = group_evaluated(as_of, quotes)
        only_a, _ = group_evaluated(as_of, quotes, a)
        only_b, _ = group_evaluated(as_of, quotes, b)
        only_c, _ = group_evaluated(as_of, quotes, c)
        assert both.mark == pytest.approx(only_a.mark + only_b.mark)
        assert both.cash == pytest.approx(only_a.cash + only_b.cash)
        np.testing.assert_allclose(
            both.price_sensitivity, only_a.price_sensitivity + only_b.price_sensitivity
        )
        swapped, _ = group_evaluated(as_of, quotes, reversed_rows)
        assert (swapped.mark, swapped.cash) == (pytest.approx(both.mark), pytest.approx(both.cash))
        np.testing.assert_allclose(swapped.price_sensitivity, both.price_sensitivity)
        doubled, _ = group_evaluated(as_of, quotes, twice)
        assert doubled.mark == pytest.approx(both.mark + only_a.mark)
        assert doubled.cash == pytest.approx(both.cash + only_a.cash)
        kept, _ = group_evaluated(as_of, quotes, with_zero)
        assert (kept.mark, kept.cash) == (pytest.approx(both.mark), pytest.approx(both.cash))
        assert kept.prepared.encoded.group_contract.size == 3
        spread, _ = group_evaluated(as_of, quotes, with_f27)
        assert spread.mark == pytest.approx(both.mark + only_c.mark)
        assert spread.cash == pytest.approx(both.cash + only_c.cash)
        np.testing.assert_allclose(
            spread.price_sensitivity,
            np.concatenate([both.price_sensitivity, only_c.price_sensitivity]),
        )
        assert spread.codes() == ("Z26", "F27")


def test_partial_asian_periods_on_one_contract_settle_independently() -> None:
    # The ticket's case on the ethane index: A covering 1 to 3 December, 30 at 70, and B 1 to 7
    # December, 50 at 70, both at +2bd, A paying the 7th and B the 9th. Every settle 72 and the
    # projection 74: on the 7th A is cash, 30 * (72 - 70) = 60, and B mark, its 1st to 4th fixed
    # at 72 and its 7th live at 74, 10 * (4 * 72 + 74) - 50 * 70 = 120, with 10 of delta, a fifth
    # of 50; the group that paid does not retire the contract. On the 9th B is cash too, 100.
    terms = period_terms(
        (("2026-12-01", "2026-12-03"), ("2026-12-01", "2026-12-07")),
        (30.0, 50.0),
        pays=("2026-12-07", "2026-12-09"),
        price=70.0,
    )
    settles = {text: 72.0 for text in pricing_days("2026-12-01", "2027-01-01")}
    result = period_valued(terms, "2026-12-07", (74.0, 80.0, 80.0), settles)
    assert (result.mark, result.cash, result.lot_delta_total) == (
        pytest.approx(120),
        pytest.approx(60),
        pytest.approx(10),
    )
    assert result.codes() == ("Z26",)
    prep = result.prepared
    np.testing.assert_array_equal(prep.encoded.group_contract, [1, 1])
    np.testing.assert_array_equal(prep.encoded.payment_date, dates("2026-12-07", "2026-12-09"))
    np.testing.assert_array_equal(prep.is_settled, [True, False])
    assert prep.encoded.slot_group.size == 3 + 5
    on_ninth = period_valued(terms, "2026-12-09", (74.0, 80.0, 80.0), settles)
    assert (on_ninth.mark, on_ninth.cash, on_ninth.lot_delta_total) == (
        pytest.approx(0),
        pytest.approx(160),
        0.0,
    )


# --- mixed fields in one batch: units, bases and methods row by row, mixed-trade-fields.md -------
# The ticket's synthetic index: USD per GAL, VOLUME measured in GAL, two specifications, GAL of one
# gallon and BBL of one barrel, 42 gallons; X26 expiring 30 November 2026, Z26 31 December, F27
# 29 January 2027 and G27 26 February, the market closed on 25 December, the payment calendar on
# 1 January. Four rows of Z26 at 10 struck on 30 November, all at +1bd: A, 1 BBL a month under
# lastday, 42 gallons on the 31st paying Monday 4 January; B, -2 GAL a day under penultimate, -62
# gallons on the 30th paying the 31st; C, 3 BBL a month under last3day, 42 gallons on each of the
# 29th, 30th and 31st paying 4 January; D, 22 GAL a month under asian, a gallon on each of
# December's 22 pricing days paying 4 January. By hand: quote quantities 42, -62, 126 and 22, the
# fixed legs -420, 620, -1,260 and -220; two groups, Z26 paying the 31st with B alone, 620 and one
# slot of -62 on the 30th, and Z26 paying 4 January with the rest, -1,900 over 22 slots, a gallon on
# each of the nineteen pricing days to the 28th, 43 on the 29th and the 30th and 85 on the 31st;
# four components, 27 observations, 23 slots and one reference, the delta 190 - 62 = 128. Every
# settle 11 and the projection 12: on 1 December everything live, -1,280 + 128 * 12 = 256; on the
# 30th the 29th and before fixed, the 30th and the 31st live, 66 of exposure, 194 and 66; on the
# 31st B fixed and paid, -62 of cash, 275 and 85 for the rest; on 1 January everything fixed, 190
# unpaid; on 4 January 128 of cash and nothing in mark. The payment days and the anchors they count
# from are the fixture's own arithmetic, never the kernel's.
MIXED = index(
    "MIXED",
    "Synthetic volume index for the mixed-fields example",
    futures_schedule(
        ("X26", "Z26", "F27", "G27"),
        dates("2026-11-30", "2026-12-31", "2027-01-29", "2027-02-26"),
        None,
    ),
    index_conventions("USD", "GAL", "USD", "VOLUME", "GAL", UNITS),
    contract_specifications(
        ("GAL", "BBL"),
        numbers(1.0, 1.0),
        ("GAL", "BBL"),
        numbers(0.0, 0.0),
        numbers(0.0, 0.0),
        UNITS,
    ),
    holiday_calendar(dates("2026-12-25")),
    "GAL",
    UNITS,
)
MIXED_DECEMBER = pricing_days(
    "2026-12-01", "2027-01-01"
)  # closed on the 25th, as the ethane market
MIXED_SETTLES = {text: 11.0 for text in MIXED_DECEMBER}
MIXED_QUOTES = (12.0, 13.0, 14.0)  # Z26, F27 and G27 while Z26 is live
MIXED_LATER = (13.0, 14.0)


class Mixed(NamedTuple):
    """A row of the mixed example: its label, quantity, unit, basis, method and clearing house, the
    schedule rows it covers, one unless a strip, and a booked part of its one month where given."""

    label: int
    quantity: float
    unit: str
    basis: str
    method: str
    clearer: str = "Clearer A"
    contracts: tuple[int, ...] = (1,)
    period: tuple[str, str] | None = None


MIXED_ROWS = (
    Mixed(1, 1.0, "BBL", "month", "lastday", "Clearer A"),
    Mixed(2, -2.0, "GAL", "calday", "penultimate", "Clearer B"),
    Mixed(3, 3.0, "BBL", "month", "last3day", "Clearer A"),
    Mixed(4, 22.0, "GAL", "month", "asian", "Clearer B"),
)


def mixed_terms(
    entries: tuple[Mixed, ...] = MIXED_ROWS,
    price: float = 10.0,
    ix: Index = MIXED,
    settlement: Settlement = Settlement.FINANCIAL,
    lags: tuple[int, ...] | None = None,
    market_closed: tuple[str, ...] = ("2026-12-25",),
    pay_closed: tuple[str, ...] = ("2027-01-01",),
) -> ResolvedTrades:
    """The rows resolved on the MIXED index unless said, each row its own unit, basis and method,
    each component paying one business day after its last observation unless lags are given, on a
    payment calendar closed on the days given, the anchors by the fixture's own arithmetic: the
    expiry under lastday and last3day, the business day before it under penultimate and the last
    pricing day on or before the end under asian."""
    names = ix.specifications.names
    schedule = cast(FuturesSchedule, ix.schedule)
    occurrence = rows(*(i for i, entry in enumerate(entries) for _ in entry.contracts))
    contract = rows(*(c for entry in entries for c in entry.contracts))
    start, end = bounds_of(ix, contract)
    for k, i in enumerate(occurrence.tolist()):
        period = entries[int(i)].period
        if period is not None:
            start[k], end[k] = day(period[0]), day(period[1])
    closed = dates(*market_closed)
    expiry = schedule.future_expiry[contract]
    anchors = np.array(
        [
            {
                "lastday": expiry[k],
                "last3day": expiry[k],
                "penultimate": np.busday_offset(expiry[k], -1, holidays=closed),
                "asian": np.busday_offset(end[k], 0, roll="backward", holidays=closed),
            }[entries[int(i)].method]
            for k, i in enumerate(occurrence.tolist())
        ],
        dtype="datetime64[D]",
    )
    n = len(entries)
    lag_days = np.array([1] * n if lags is None else lags, dtype=np.int64)
    pay_calendar = holiday_calendar(dates(*pay_closed))
    payment = (
        None
        if settlement is Settlement.PHYSICAL
        else PaymentTerms(
            lag_days,
            (pay_calendar,) * n,
            np.busday_offset(anchors, lag_days[occurrence], holidays=pay_calendar.holiday),
        )
    )
    return resolved_trades(
        FIXED_FLOAT,
        ix,
        np.array([names.index(entry.unit) for entry in entries], dtype=np.intp),
        Route.CLEARED,
        settlement,
        np.array([METHODS.index(ScheduleMethod(entry.method)) for entry in entries], dtype=np.intp),
        np.array([BASES.index(QuantityPer(entry.basis)) for entry in entries], dtype=np.intp),
        ids(*(entry.label for entry in entries)),
        tuple(entry.clearer for entry in entries),
        None,
        np.repeat(day("2026-11-30"), n),
        occurrence,
        contract,
        numbers(*(entries[int(i)].quantity for i in occurrence.tolist())),
        start,
        end,
        numbers(*([price] * occurrence.size)),
        payment,
    )


def mixed_evaluated(
    as_of: str,
    quotes: tuple[float, ...],
    terms: ResolvedTrades | None = None,
    settles: dict[str, float] = MIXED_SETTLES,
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = mixed_terms() if terms is None else terms
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = history_by_day(terms.index, as_of, settles)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


def test_the_mixed_rows_resolve_each_to_its_own_unit_basis_and_method() -> None:
    terms = mixed_terms()
    np.testing.assert_array_equal(terms.specification, [1, 0, 1, 0])  # BBL, GAL, BBL, GAL
    np.testing.assert_array_equal(
        terms.schedule_method,
        [METHODS.index(ScheduleMethod(m)) for m in ("lastday", "penultimate", "last3day", "asian")],
    )
    np.testing.assert_array_equal(
        terms.quantity_per,
        [BASES.index(QuantityPer(b)) for b in ("month", "calday", "month", "month")],
    )
    np.testing.assert_array_equal(terms.covered_days, [31, 31, 31, 31])
    np.testing.assert_array_equal(terms.component_quantity, [1.0, -62.0, 3.0, 22.0])
    assert terms.clearing_house == ("Clearer A", "Clearer B", "Clearer A", "Clearer B")
    assert terms.payment is not None
    np.testing.assert_array_equal(
        terms.payment.date, dates("2027-01-04", "2026-12-31", "2027-01-04", "2027-01-04")
    )
    for array in (terms.specification, terms.schedule_method, terms.quantity_per):
        assert not array.flags.writeable
    obs = observed_of(terms)
    np.testing.assert_array_equal(obs.component, [0, 1, 2, 2, 2] + [3] * 22)
    assert [str(d) for d in obs.date[:5]] == [
        "2026-12-31",
        "2026-12-30",
        "2026-12-29",
        "2026-12-30",
        "2026-12-31",
    ]
    assert [str(d) for d in obs.date[5:]] == MIXED_DECEMBER
    np.testing.assert_allclose(obs.weight, [1.0, 1.0, 1 / 3, 1 / 3, 1 / 3] + [1 / 22] * 22)


def test_the_mixed_rows_encode_as_the_ticket_says() -> None:
    terms = mixed_terms()
    counter = WorkCounter()
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    np.testing.assert_allclose(enc.quote_quantity, [42.0, -62.0, 126.0, 22.0])
    np.testing.assert_allclose(enc.coefficient, enc.quote_quantity)  # dollars quoted and paid
    np.testing.assert_allclose(enc.offset, [-420.0, 620.0, -1_260.0, -220.0])
    np.testing.assert_array_equal(enc.group_contract, [1, 1])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-31", "2027-01-04"))
    np.testing.assert_array_equal(enc.group_of_component, [1, 0, 1, 1])
    np.testing.assert_allclose(enc.offset_of_group, [620.0, -1_900.0])
    np.testing.assert_array_equal(enc.slot_group, [0] + [1] * 22)
    assert [str(d) for d in enc.slot_date] == ["2026-12-30", *MIXED_DECEMBER]
    np.testing.assert_allclose(enc.slot_exposure, [-62.0] + [1.0] * 19 + [43.0, 43.0, 85.0])
    np.testing.assert_array_equal(enc.slot_reference, [1] * 23)
    np.testing.assert_array_equal(enc.references, [1])  # one contract on the axis
    assert enc.named_slot(0) == "trade 2 at row 2 on 2026-12-30, a day Z26 prices"
    assert enc.named_slot(21) == "trade 3 at row 3 on 2026-12-30, a day Z26 prices"
    assert counter.freeze().as_dict() == {
        "encoded_components": 4,
        "encoded_groups": 2,
        "encoded_observations": 27,
        "encoded_slots": 23,
        "reserved_components": 4,
    }


# The ticket's five states and the hand answers, with the quotes read per live reference, one
# while Z26 is live and none after, the settles read per fixed slot, and the groups settled.
MIXED_LIFECYCLE: list[tuple[str, tuple[float, ...], float, float, float, int, int, list[bool]]] = [
    ("2026-12-01", MIXED_QUOTES, 256, 0, 128, 1, 0, [False, False]),
    ("2026-12-30", MIXED_QUOTES, 194, 0, 66, 1, 20, [False, False]),
    ("2026-12-31", MIXED_QUOTES, 275, -62, 85, 1, 22, [True, False]),
    ("2027-01-01", MIXED_LATER, 190, -62, 0, 0, 23, [True, False]),
    ("2027-01-04", MIXED_LATER, 0, 128, 0, 0, 23, [True, True]),
]
MIXED_IDS = [
    "1 Dec, everything live",
    "30 Dec, the 29th and before fixed",
    "31 Dec, B paid",
    "1 Jan, everything fixed, the rest unpaid",
    "4 Jan, both paid",
]


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta", "live_reads", "fixings_read", "settled"),
    MIXED_LIFECYCLE,
    ids=MIXED_IDS,
)
def test_the_mixed_batch_marks_fixes_and_pays_as_the_ticket_says(
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
    live_reads: int,
    fixings_read: int,
    settled: list[bool],
) -> None:
    result, counter = mixed_evaluated(as_of, quotes)
    assert result.mark == pytest.approx(mark)
    assert result.cash == pytest.approx(cash)
    assert result.lot_delta_total == pytest.approx(delta)
    np.testing.assert_allclose(result.price_sensitivity, [delta])
    assert result.codes() == ("Z26",) and result.price_sensitivity_unit == "USD per USD/GAL"
    counts = counter.freeze().as_dict()
    assert (counts["live_prices_read"], counts["fixings_read"], counts["kernel"]) == (
        live_reads,
        fixings_read,
        1,
    )
    assert (counts["encoded_groups"], counts["prepared_slots"]) == (2, 23)
    np.testing.assert_array_equal(result.prepared.is_settled, settled)


def test_a_tick_moves_the_mixed_batch_and_a_corrected_fixing_takes_a_new_history() -> None:
    terms = mixed_terms()
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    history = history_by_day(MIXED, "2026-12-30", MIXED_SETTLES)
    prep = prepared_trades(enc, history, WorkCounter())
    assert trade_results(prep, quoted(history, *MIXED_QUOTES), WorkCounter()).mark == pytest.approx(
        194
    )
    counter = WorkCounter()
    ticked = trade_results(prep, quoted(history, 13.0, 13.0, 14.0), counter)
    assert (ticked.mark, ticked.lot_delta_total) == (pytest.approx(260), pytest.approx(66))
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 1}
    corrected = history_by_day(MIXED, "2026-12-30", {**MIXED_SETTLES, "2026-12-29": 12.0})
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(corrected, *MIXED_QUOTES), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'MIXED', expected the one the trades were "
        "prepared against"
    )
    again = prepared_trades(enc, corrected, WorkCounter())
    assert trade_results(
        again, quoted(corrected, *MIXED_QUOTES), WorkCounter()
    ).mark == pytest.approx(
        237
    )  # the 29th's 43 of exposure, C's 42 and D's gallon, a dollar higher


def test_the_mixed_batch_equals_its_singletons_in_every_state_and_order() -> None:
    # The four rows alone summed, mark, cash and the delta on the axis; the rows reversed; A twice;
    # a row kept ready at nothing under asian; and a strip of a gallon a day over January and
    # February, 31 and 28 gallons on F27 and G27 at 13 and 14 against 10, 93 + 112 = 205 of mark
    # live in every state and 31 and 28 of delta on two more contracts.
    strip = Mixed(19, 1.0, "GAL", "calday", "lastday", "Clearer A", contracts=(2, 3))
    for as_of, quotes, mark, cash, delta, *_ in MIXED_LIFECYCLE:
        batch, _ = mixed_evaluated(as_of, quotes)
        alone = [mixed_evaluated(as_of, quotes, mixed_terms((entry,)))[0] for entry in MIXED_ROWS]
        assert batch.mark == pytest.approx(sum(one.mark for one in alone)) == pytest.approx(mark)
        assert batch.cash == pytest.approx(sum(one.cash for one in alone)) == pytest.approx(cash)
        np.testing.assert_allclose(
            batch.price_sensitivity, sum(one.price_sensitivity for one in alone)
        )
        swapped, _ = mixed_evaluated(as_of, quotes, mixed_terms(MIXED_ROWS[::-1]))
        assert (swapped.mark, swapped.cash) == (pytest.approx(mark), pytest.approx(cash))
        np.testing.assert_allclose(swapped.price_sensitivity, batch.price_sensitivity)
        twice, _ = mixed_evaluated(as_of, quotes, mixed_terms((*MIXED_ROWS, MIXED_ROWS[0])))
        assert twice.mark == pytest.approx(mark + alone[0].mark)
        assert twice.cash == pytest.approx(cash + alone[0].cash)
        kept, _ = mixed_evaluated(
            as_of, quotes, mixed_terms((*MIXED_ROWS, Mixed(26, 0.0, "GAL", "month", "asian")))
        )
        assert (kept.mark, kept.cash) == (pytest.approx(mark), pytest.approx(cash))
        assert kept.prepared.encoded.slot_group.size == 23
        spread, _ = mixed_evaluated(as_of, quotes, mixed_terms((*MIXED_ROWS, strip)))
        assert spread.mark == pytest.approx(mark + 205) and spread.cash == pytest.approx(cash)
        np.testing.assert_allclose(spread.price_sensitivity, [delta, 31.0, 28.0])
        assert spread.codes() == ("Z26", "F27", "G27")
    with_strip = mixed_terms((*MIXED_ROWS, strip))
    np.testing.assert_array_equal(with_strip.component_quantity, [1, -62, 3, 22, 31, 28])
    assert with_strip.payment is not None
    np.testing.assert_array_equal(with_strip.payment.date[4:], dates("2027-02-01", "2027-03-01"))


def test_equivalent_quantities_compress_alike_whatever_unit_states_them() -> None:
    # A as 42 gallons a month: the same quote quantity, fixed leg, slots and risk, and the same
    # numbers in every state; a lot of ten thousand beside ten thousand units on a cent-quoted
    # index settling in dollars, one slot of twenty thousand, 2,000 dollars ten cents up, the price
    # in cents for both rows whatever unit counts the quantity.
    in_gallons = mixed_terms((Mixed(1, 42.0, "GAL", "month", "lastday"), *MIXED_ROWS[1:]))
    enc, twin = (
        encoded(t, observed_of(t), UNITS, WorkCounter()) for t in (mixed_terms(), in_gallons)
    )
    np.testing.assert_allclose(twin.quote_quantity, enc.quote_quantity)
    np.testing.assert_allclose(twin.offset, enc.offset)
    np.testing.assert_allclose(twin.slot_exposure, enc.slot_exposure)
    np.testing.assert_array_equal(twin.payment_date, enc.payment_date)
    for as_of, quotes, mark, cash, delta, *_ in MIXED_LIFECYCLE:
        result, _ = mixed_evaluated(as_of, quotes, in_gallons)
        assert (result.mark, result.cash, result.lot_delta_total) == (
            pytest.approx(mark),
            pytest.approx(cash),
            pytest.approx(delta),
        )
    cents = index(
        "cents lots",
        "Gas quoted in cents with lot specifications",
        CENTS.schedule,
        CENTS.conventions,
        contract_specifications(
            ("lot", "MMBTU"),
            numbers(10_000.0, 1.0),
            ("MMBTU", "MMBTU"),
            numbers(0.0, 0.0),
            numbers(0.0, 0.0),
            UNITS,
        ),
        CENTS.holiday_calendar,
        "lot",
        UNITS,
    )
    pair = mixed_terms(
        (
            Mixed(12, 1.0, "lot", "month", "lastday"),
            Mixed(13, 10_000.0, "MMBTU", "month", "lastday"),
        ),
        price=300.0,
        ix=cents,
        market_closed=("2026-11-26", "2026-12-25", "2027-01-01"),
        pay_closed=("2026-11-26", "2026-12-25", "2027-01-01"),
    )
    enc = encoded(pair, observed_of(pair), UNITS, WorkCounter())
    np.testing.assert_allclose(enc.quote_quantity, [10_000.0, 10_000.0])
    np.testing.assert_allclose(enc.coefficient, [100.0, 100.0])  # dollars per cent per MMBTU
    np.testing.assert_allclose(enc.offset, [-30_000.0, -30_000.0])
    np.testing.assert_allclose(enc.slot_exposure, [200.0])
    result, _ = mixed_evaluated("2026-11-24", (310.0, 350.0, 360.0), pair)
    assert result.mark == pytest.approx(2_000) and result.lot_delta_total == pytest.approx(2)
    assert result.price_sensitivity_unit == "USD per CENT/MMBTU"
    assert result.lot_unit == "lots of lot (10000 MMBTU)"


def test_the_payment_conventions_combine_with_mixed_methods() -> None:
    # The clearing labels swapped change no group, slot or day: a label is attribution. B at +2bd
    # pays 4 January as the rest do, one group of 22 slots, the 30th's -62 and 43 one slot of -19;
    # A on a payment calendar closed on 4 January pays the 5th, a third group.
    relabeled = mixed_terms(
        tuple(
            entry._replace(clearer="Clearer B" if entry.clearer == "Clearer A" else "Clearer A")
            for entry in MIXED_ROWS
        )
    )
    enc, same = (
        encoded(t, observed_of(t), UNITS, WorkCounter()) for t in (mixed_terms(), relabeled)
    )
    np.testing.assert_array_equal(same.group_contract, enc.group_contract)
    np.testing.assert_array_equal(same.payment_date, enc.payment_date)
    np.testing.assert_allclose(same.slot_exposure, enc.slot_exposure)
    assert relabeled.clearing_house == ("Clearer B", "Clearer A", "Clearer B", "Clearer A")
    coalesced = mixed_terms(lags=(1, 2, 1, 1))
    enc = encoded(coalesced, observed_of(coalesced), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.group_contract, [1])
    np.testing.assert_array_equal(enc.payment_date, dates("2027-01-04"))
    assert enc.slot_group.size == 22
    np.testing.assert_allclose(enc.slot_exposure[-3:], [43.0, -19.0, 85.0])
    result, _ = mixed_evaluated("2026-12-31", MIXED_QUOTES, coalesced)
    assert (result.mark, result.cash) == (pytest.approx(213), 0.0)  # 275 - 62, nothing paid yet
    apart = mixed_terms(
        (Mixed(1, 1.0, "BBL", "month", "lastday"), *MIXED_ROWS[1:]),
        lags=(1, 1, 1, 1),
        pay_closed=("2027-01-01", "2027-01-04"),
    )
    enc = encoded(apart, observed_of(apart), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-31", "2027-01-05"))


def test_a_partial_asian_row_stands_beside_whole_months_under_other_methods() -> None:
    # D covering 1 to 15 December, eleven pricing days a 15 gallons' eleventh each, paying the
    # 16th, beside A under lastday: two groups; on the 16th D fixed and paid at 11, 15 of cash, and
    # A live, 84 of mark and 42 of delta. B under penultimate over the same part is refused by its
    # contract, its days and its own method, though A, expiry-based too, stands whole.
    whole_and_part = mixed_terms(
        (
            Mixed(1, 1.0, "BBL", "month", "lastday"),
            Mixed(
                4, 15.0, "GAL", "month", "asian", "Clearer B", period=("2026-12-01", "2026-12-15")
            ),
        )
    )
    np.testing.assert_array_equal(whole_and_part.covered_days, [31, 15])
    obs = observed_of(whole_and_part)
    np.testing.assert_array_equal(obs.component, [0] + [1] * 11)
    assert [str(d) for d in obs.date[1:]] == MIXED_DECEMBER[:11]
    enc = encoded(whole_and_part, obs, UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-16", "2027-01-04"))
    result, counter = mixed_evaluated("2026-12-16", MIXED_QUOTES, whole_and_part)
    assert (result.mark, result.cash, result.lot_delta_total) == (
        pytest.approx(84),
        pytest.approx(15),
        pytest.approx(42),
    )
    assert counter.freeze()["encoded_slots"] == 12
    part_under_pen = mixed_terms(
        (
            Mixed(1, 1.0, "BBL", "month", "lastday"),
            Mixed(
                2,
                -2.0,
                "GAL",
                "calday",
                "penultimate",
                "Clearer B",
                period=("2026-12-01", "2026-12-15"),
            ),
        )
    )
    with pytest.raises(ValueError) as refused:
        observed_of(part_under_pen)
    assert str(refused.value) == (
        "Z26 of trade 2 at row 2 is covered from 2026-12-01 to 2026-12-15, part of its month, "
        "expected the whole month under penultimate; the expiry-based methods take the contract's "
        "month entire, and a part of it prices under asian"
    )


def test_interleaved_methods_and_a_strip_keep_their_components_and_anchors() -> None:
    # A under lastday, S a strip of Z26 and F27 under last3day, D a part of December under asian
    # and B under penultimate: the observations come back in component order with each
    # component's days increasing, the strip's January component among them, and each component
    # pays from its own last day, S's F27 on 1 February, D on the 16th and B on the 31st.
    terms = mixed_terms(
        (
            Mixed(1, 1.0, "BBL", "month", "lastday"),
            Mixed(19, 1.0, "GAL", "month", "last3day", "Clearer A", contracts=(1, 2)),
            Mixed(
                4, 15.0, "GAL", "month", "asian", "Clearer B", period=("2026-12-01", "2026-12-15")
            ),
            Mixed(2, -2.0, "GAL", "calday", "penultimate", "Clearer B"),
        )
    )
    obs = observed_of(terms)
    np.testing.assert_array_equal(obs.component, [0] + [1] * 3 + [2] * 3 + [3] * 11 + [4])
    assert [str(d) for d in obs.date[:7]] == [
        "2026-12-31",
        "2026-12-29",
        "2026-12-30",
        "2026-12-31",
        "2027-01-27",
        "2027-01-28",
        "2027-01-29",
    ]
    assert str(obs.date[-1]) == "2026-12-30"
    assert terms.payment is not None
    np.testing.assert_array_equal(
        terms.payment.date,
        dates("2027-01-04", "2027-01-04", "2027-02-01", "2026-12-16", "2026-12-31"),
    )
    enc = encoded(terms, obs, UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.group_contract, [1, 1, 1, 2])
    np.testing.assert_array_equal(
        enc.payment_date, dates("2026-12-16", "2026-12-31", "2027-01-04", "2027-02-01")
    )
    np.testing.assert_array_equal(enc.references, [1, 2])
    np.testing.assert_array_equal(enc.group_of_component, [2, 2, 3, 0, 1])


def test_the_mixed_batchs_refusals_keep_their_meaning() -> None:
    # A physical batch takes lastday rows alone, the first other row named with its method; a
    # method per
    # component is one per component; a row's selection out of range is refused by its row.
    with pytest.raises(ValueError) as refused:
        mixed_terms(MIXED_ROWS[:2], settlement=Settlement.PHYSICAL)
    assert str(refused.value) == (
        "settlement_method is 'physical', expected 'financial' with the penultimate method of "
        "trade 2 at row 2; a penultimate future is cash settled on the business day before its "
        "contract's expiry"
    )
    lastday_rows = (
        Mixed(1, 1.0, "BBL", "month", "lastday"),
        Mixed(7, 10.0, "GAL", "calday", "lastday"),
    )
    physical = mixed_terms(lastday_rows, settlement=Settlement.PHYSICAL)
    np.testing.assert_array_equal(physical.component_quantity, [1.0, 310.0])
    with pytest.raises(ValueError) as refused:
        observed(
            by(ScheduleMethod.LASTDAY, 2), MIXED, rows(1), *bounds_of(MIXED, rows(1)), unlabeled
        )
    assert str(refused.value) == "method has 2, expected 1, one per component"


# The review's extreme input: a BTU as the reporting lot on the cent-quoted index, a coefficient
# of 1e-8 dollars a cent an MMBTU a lot, so that quantities hundreds of orders of magnitude above
# any book count their lots past the largest number while every monetary number stays finite.
TINY_LOT = index(
    "tiny lot",
    "Gas with a one BTU lot",
    CENTS.schedule,
    CENTS.conventions,
    contract_specifications(
        ("BTU", "MMBTU"),
        numbers(1.0, 1.0),
        ("BTU", "MMBTU"),
        numbers(0.0, 0.0),
        numbers(0.0, 0.0),
        UNITS,
    ),
    CENTS.holiday_calendar,
    "BTU",
    UNITS,
)


def test_a_live_lot_that_outruns_the_largest_number_is_refused_at_preparation() -> None:
    # The review's case: a BTU as the reporting lot on a cent-quoted index and a quantity of 1e303
    # MMBTU, whole and finite as a quantity, finite as a sensitivity, 1e301 dollars a cent, and not
    # as lots, 1e301 over a coefficient of 1e-8; refused when the batch is prepared, by its slot,
    # before anything a reader would fail on is published. Extreme-input hardening, not pricing.
    tiny = TINY_LOT
    assert tiny.reporting_lot is not None
    assert tiny.reporting_lot.coefficient == pytest.approx(1e-8)
    terms = resolved_trades(
        FIXED_FLOAT, tiny, spec(1, 1), Route.CLEARED, Settlement.FINANCIAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 1), ids(8), None, None,
        dates("2026-09-24"), rows(0), rows(1),
        numbers(1e303), *bounds_of(tiny, rows(1)), numbers(300.0), paying(dates("2026-11-30"), 1),
    )  # fmt: skip
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_allclose(enc.coefficient, [1e301])  # finite, in dollars a cent an MMBTU
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(tiny, "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "trade 8 at row 1 on 2026-11-25, a day Z26 prices, has inf live lots, expected a finite "
        "number of lots of BTU (1 BTU); the exposure in lots outruns the largest number"
    )


def test_a_lot_delta_that_outruns_the_largest_number_is_refused_by_its_contract() -> None:
    # The aggregate: two rows of Z26 paying on two days, so two slots, each 9e303 lots of 10,000
    # MMBTU, 9e307 MMBTU, finite as an exposure and as lots, 9e303 each, and their sum past the
    # largest number as the contract's sensitivity and so as its lot delta; the sum is bincount's,
    # which raises no flag, so the rule looks at the vector and refuses by the contract before
    # anything is published. Paying on one day, the two rows would share a slot whose exposure
    # is already infinite, and the slot rule would speak first. A price of zero keeps the offsets
    # finite; this is the arithmetic's edge, not a trade anyone books.
    terms = resolved_trades(
        FIXED_FLOAT, NG, spec(2), Route.CLEARED, Settlement.FINANCIAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 2), ids(1, 2), None, None,
        dates("2026-09-24", "2026-09-24"), rows(0, 1), rows(1, 1),
        numbers(9e303, 9e303), *bounds_of(NG, rows(1, 1)), numbers(0.0, 0.0),
        paying(dates("2026-11-30", "2026-12-01"), 2),
    )  # fmt: skip
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_allclose(enc.slot_exposure, [9e307, 9e307])  # two slots, finite each
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(NG, "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "Z26 has inf of lot delta, expected a finite number of lots of NYMEX NG (10000 MMBTU); "
        "the exposure in lots outruns the largest number"
    )


def test_a_lot_delta_total_that_outruns_the_largest_number_is_refused_for_the_batch() -> None:
    # The review's third case: Z26 and F27 each 1e302 MMBTU, 1e300 dollars a cent of sensitivity
    # and 1e308 lots, finite by the slot and by the contract, and their sum past the largest
    # number; refused for the batch before the record is made, so that the risk report never
    # meets an infinite total. The sum runs with the overflow flag down and the rule judges.
    terms = resolved_trades(
        FIXED_FLOAT, TINY_LOT, spec(2, 1), Route.CLEARED, Settlement.FINANCIAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 2), ids(26, 6), None, None,
        dates("2026-09-24", "2026-09-24"), rows(0, 1), rows(1, 2),
        numbers(1e302, 1e302), *bounds_of(TINY_LOT, rows(1, 2)), numbers(300.0, 300.0),
        paying(dates("2026-11-30", "2026-12-31"), 2),
    )  # fmt: skip
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_allclose(enc.coefficient, [1e300, 1e300])  # finite, in dollars a cent
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, history_on(TINY_LOT, "2026-11-24", {}), WorkCounter())
    assert str(refused.value) == (
        "the batch has inf of lot delta in all, expected a finite number of lots of BTU (1 BTU); "
        "the contracts' deltas, each finite, sum past the largest number"
    )


# --- calendar-driven asian references ----------------------------------------------------------
# calendar-driven-asian-references.md: an asian observation takes the contract the index's calendar
# prices its day with, which need not be the contract the trade was booked on. A WTI-like index
# whose contracts expire the month before their code's month, Z26 on 20 November, F27 on Monday
# 21 December, G27 on 20 January and H27 on 22 February, the market and the payment calendar both
# closed on 25 December and New Year's Day, quoted in dollars a barrel and settled in dollars, a
# barrel the specification entered and a thousand-barrel LOT the reporting lot. A December asian
# booked as Z26 observes December's pricing days, F27 pricing them through its expiry on the 21st
# and G27 from the 22nd: the booked contract keeps the fixed leg and the payment, the day's
# contract supplies its settle and its quote.
WTI_HOLIDAYS = ("2026-12-25", "2027-01-01")
WTI_CONTRACTS = (
    ("Z26", "2026-11-20"),
    ("F27", "2026-12-21"),
    ("G27", "2027-01-20"),
    ("H27", "2027-02-22"),
)


def wti_like(name: str, contracts: tuple[tuple[str, str], ...]) -> Index:
    """An index of those contracts with the WTI-like conventions, the barrel and the lot."""
    return index(
        name,
        f"{name} index",
        futures_schedule(
            tuple(code for code, _ in contracts), dates(*(expiry for _, expiry in contracts)), None
        ),
        index_conventions("USD", "BBL", "USD", "VOLUME", "BBL", UNITS),
        contract_specifications(
            ("BBL", "LOT"),
            numbers(1.0, 1_000.0),
            ("BBL", "BBL"),
            numbers(0.0, 0.0),
            numbers(0.0, 0.0),
            UNITS,
        ),
        holiday_calendar(dates(*WTI_HOLIDAYS)),
        "LOT",
        UNITS,
    )


WTI = wti_like("WTI", WTI_CONTRACTS)
WTI_PAYS = holiday_calendar(dates(*WTI_HOLIDAYS))
# The ticket's six observation days, the 19th, 20th, 26th and 27th weekends and the 25th a
# holiday, with their fixings as they arrive; 60 on every other fixed day and 78 on the 29th, a
# day outside the window whose fixing must change nothing of this trade.
WTI_WINDOW = ("2026-12-18", "2026-12-21", "2026-12-22", "2026-12-23", "2026-12-24", "2026-12-28")
WTI_FIXINGS = dict(zip(WTI_WINDOW, (71.0, 73.0, 74.0, 76.0, 75.0, 77.0), strict=True))
WTI_SETTLES = {**WTI_FIXINGS, "2026-12-29": 78.0}
JANUARY_BOUNDS = ("2027-01-01", "2027-01-31")  # F27's own month, which a lastday row covers whole


def wti_terms(
    periods: tuple[tuple[str, str], ...] = (("2026-12-18", "2026-12-28"),),
    quantities: tuple[float, ...] = (1_200.0,),
    contracts: tuple[int, ...] = (0,),
    pays: tuple[str, ...] = ("2026-12-30",),
    methods: tuple[ScheduleMethod, ...] | None = None,
    ix: Index = WTI,
    price: float = 70.0,
    units: tuple[int, ...] | None = None,
    bases: tuple[QuantityPer, ...] | None = None,
) -> ResolvedTrades:
    """Trades on the WTI-like index, asian unless said, cleared and financial at 70 dollars a
    barrel in barrels, the first specification row, or the rows given, a month's quantity or the
    bases given, each covering the days given on the contract row given and paying on the day
    given, two business days after its last observation as the resolution would count."""
    n = len(periods)
    method = (
        one_choice(METHODS, ScheduleMethod.ASIAN, n)
        if methods is None
        else np.array([METHODS.index(m) for m in methods], dtype=np.intp)
    )
    basis = (
        one_choice(BASES, QuantityPer.MONTH, n)
        if bases is None
        else np.array([BASES.index(b) for b in bases], dtype=np.intp)
    )
    return resolved_trades(
        FIXED_FLOAT,
        ix,
        spec(n) if units is None else rows(*units),
        Route.CLEARED,
        Settlement.FINANCIAL,
        method,
        basis,
        np.arange(1, n + 1, dtype=np.int64),
        ("Prototype Clearing",) * n,
        None,
        np.repeat(day("2026-11-20"), n),
        np.arange(n, dtype=np.intp),
        rows(*contracts),
        numbers(*quantities),
        dates(*(start for start, _ in periods)),
        dates(*(end for _, end in periods)),
        numbers(*([price] * n)),
        PaymentTerms(np.full(n, 2), (WTI_PAYS,) * n, dates(*pays)),
    )


def wti_history(
    as_of: str, settles: dict[str, float] = WTI_SETTLES, ix: Index = WTI, default: float = 60.0
) -> MarketHistory:
    """The index's history valued on that day: the default settle, 60, on every fixed pricing day
    from the day after the first contract expires, Saturday 21 November, so from Monday the 23rd,
    and the settles given standing on their days, newest first as the creator takes them."""
    cal = calendar(valuation_date(day(as_of), 0.5), ix)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    prices = np.full(priced.size, default)
    for text, price in settles.items():
        prices[priced == day(text)] = price
    return market_history(cal, futures_fixings(priced[::-1].copy(), prices[::-1].copy(), ix))


def wti_valued(
    as_of: str,
    quotes: tuple[float, ...],
    terms: ResolvedTrades | None = None,
    settles: dict[str, float] = WTI_SETTLES,
    default: float = 60.0,
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = wti_terms() if terms is None else terms
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = wti_history(as_of, settles, terms.index, default)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


def test_a_december_asian_on_the_wti_like_index_references_f27_and_then_g27() -> None:
    # The ticket's booking: 18 to 28 December, six pricing days of 200 barrels, F27 pricing the
    # 18th and the 21st, its expiry day, and G27 the four from the 22nd; one group, Z26's, paying
    # 30 December, two business days after the 28th; the delta axis F27 and G27, never Z26.
    terms = wti_terms()
    obs = observed_of(terms)
    assert [str(d) for d in obs.date] == list(WTI_WINDOW)
    np.testing.assert_allclose(obs.weight, np.full(6, 1 / 6))
    counter = WorkCounter()
    enc = encoded(terms, obs, UNITS, counter)
    np.testing.assert_array_equal(enc.group_contract, [0])  # booked as Z26
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-30"))
    np.testing.assert_array_equal(enc.slot_reference, [1, 1, 2, 2, 2, 2])  # F27 twice, G27 four
    np.testing.assert_array_equal(enc.references, [1, 2])
    np.testing.assert_allclose(enc.slot_exposure, [200.0] * 6)
    np.testing.assert_allclose(enc.offset, [-84_000.0])
    assert enc.named_slot(0) == "trade 1 at row 1 on 2026-12-18, a day F27 prices"
    assert enc.named_slot(2) == "trade 1 at row 1 on 2026-12-22, a day G27 prices"
    counts = counter.freeze().as_dict()
    assert (counts["encoded_groups"], counts["encoded_observations"], counts["encoded_slots"]) == (
        1,
        6,
        6,
    )


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "sensitivity", "lots", "live_reads", "fixings_read"),
    [
        ("2026-12-18", (72.0, 75.0), 4_800, 0, (400.0, 800.0), (0.4, 0.8), 2, 0),
        ("2026-12-19", (72.0, 75.0), 4_600, 0, (200.0, 800.0), (0.2, 0.8), 2, 1),
        ("2026-12-22", (75.0,), 4_800, 0, (0.0, 800.0), (0.0, 0.8), 1, 2),
        ("2026-12-22", (76.0,), 5_600, 0, (0.0, 800.0), (0.0, 0.8), 1, 2),
        ("2026-12-29", (75.0,), 5_200, 0, (0.0, 0.0), (0.0, 0.0), 0, 6),
        ("2026-12-30", (75.0,), 0, 5_200, (0.0, 0.0), (0.0, 0.0), 0, 6),
    ],
    ids=[
        "18 Dec, all live",
        "19 Dec, the first fixed",
        "22 Dec, both F27 days fixed",
        "22 Dec, G27 at 76",
        "29 Dec, all fixed, unpaid",
        "30 Dec, paid",
    ],
)
def test_the_wti_asian_marks_fixes_and_pays_as_the_ticket_says(
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    sensitivity: tuple[float, float],
    lots: tuple[float, float],
    live_reads: int,
    fixings_read: int,
) -> None:
    # The fixed leg -84,000; F27 at 72 and G27 at 75 while live; the vector starting at the
    # contract of the first unfixed day, F27 through the 21st and G27 from the 22nd, when the
    # retained F27 entry at zero asks the market for nothing.
    result, counter = wti_valued(as_of, quotes)
    assert (result.mark, result.cash) == (pytest.approx(mark), pytest.approx(cash))
    assert result.codes() == ("F27", "G27")
    np.testing.assert_allclose(result.price_sensitivity, sensitivity)
    np.testing.assert_allclose(result.lot_delta, lots)
    assert result.lot_delta_total == pytest.approx(sum(lots))
    counts = counter.freeze().as_dict()
    assert (counts["live_prices_read"], counts["fixings_read"], counts["prepared_slots"]) == (
        live_reads,
        fixings_read,
        6,
    )


def test_a_tick_a_correction_and_an_unrelated_fixing_act_on_the_wti_asian_as_the_ticket_says() -> (
    None
):
    # A tick to 76 over the same preparation: 5,600 from 4,800. The first fixing corrected from 71
    # to 70: 200 less at the end, through a new history and a new preparation, the old results
    # standing. The 29th's fixing, a day outside the window, moved from 78 to 90: nothing of the
    # trade changes. Each live reference bumped by one on the 18th moves the mark by its own delta.
    terms = wti_terms()
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    history = wti_history("2026-12-22")
    prep = prepared_trades(enc, history, WorkCounter())
    assert trade_results(prep, quoted(history, 75.0), WorkCounter()).mark == pytest.approx(4_800)
    assert trade_results(prep, quoted(history, 76.0), WorkCounter()).mark == pytest.approx(5_600)
    corrected = {**WTI_SETTLES, "2026-12-18": 70.0}
    with pytest.raises(ValueError) as refused:
        trade_results(prep, quoted(wti_history("2026-12-22", corrected), 75.0), WorkCounter())
    assert str(refused.value) == (
        "market is over another history of index 'WTI', expected the one the trades were "
        "prepared against"
    )
    assert wti_valued("2026-12-29", (75.0,))[0].mark == pytest.approx(5_200)
    assert wti_valued("2026-12-29", (75.0,), settles=corrected)[0].mark == pytest.approx(5_000)
    paid = wti_valued("2026-12-30", (75.0,), settles={**WTI_SETTLES, "2026-12-29": 90.0})[0]
    assert (paid.mark, paid.cash) == (0.0, pytest.approx(5_200))
    assert wti_valued("2026-12-18", (73.0, 75.0))[0].mark == pytest.approx(4_800 + 400)
    assert wti_valued("2026-12-18", (72.0, 76.0))[0].mark == pytest.approx(4_800 + 800)


def test_a_full_december_on_the_wti_like_index_splits_22_days_15_to_f27_and_7_to_g27() -> None:
    # 2,200 barrels over the whole of December at 70: 100 a day, F27 pricing 15 of the 22 days and
    # G27 the 7 from the 22nd, exposure 1,500 and 700, the mark 6,500 all live at 72 and 75; the
    # month's bounds the ones a code entry of Z26 gives, so the two forms agree.
    starts, ends = bounds_of(WTI, rows(0))
    assert (str(starts[0]), str(ends[0])) == ("2026-12-01", "2026-12-31")
    terms = wti_terms(
        periods=(("2026-12-01", "2026-12-31"),), quantities=(2_200.0,), pays=("2027-01-05",)
    )
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.slot_reference, [1] * 15 + [2] * 7)
    np.testing.assert_allclose(enc.slot_exposure, [100.0] * 22)
    result, _ = wti_valued("2026-12-01", (72.0, 75.0), terms)
    np.testing.assert_allclose(result.price_sensitivity, [1_500.0, 700.0])
    assert result.mark == pytest.approx(6_500)
    assert result.lot_delta_total == pytest.approx(2.2)


def test_two_groups_on_one_pricing_day_stay_apart_by_their_booked_contracts() -> None:
    # A December asian booked as Z26 over the 1st to the 21st and a lastday F27 both observe
    # Monday 21 December, F27's expiry, off F27, and both pay the 22nd: two groups, Z26's and
    # F27's, two slots on that day, one reference; the pair values as its singletons summed.
    pair = wti_terms(
        periods=(("2026-12-01", "2026-12-21"), JANUARY_BOUNDS),
        quantities=(1_500.0, 1_000.0),
        contracts=(0, 1),
        pays=("2026-12-22", "2026-12-22"),
        methods=(ScheduleMethod.ASIAN, ScheduleMethod.LASTDAY),
    )
    enc = encoded(pair, observed_of(pair), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.group_contract, [0, 1])
    np.testing.assert_array_equal(enc.references, [1])  # F27 prices every day of both
    on_the_21st = np.flatnonzero(enc.slot_date == day("2026-12-21"))
    np.testing.assert_array_equal(enc.slot_group[on_the_21st], [0, 1])
    asian = wti_terms(
        periods=(("2026-12-01", "2026-12-21"),), quantities=(1_500.0,), pays=("2026-12-22",)
    )
    future = wti_terms(
        periods=(JANUARY_BOUNDS,),
        quantities=(1_000.0,),
        contracts=(1,),
        pays=("2026-12-22",),
        methods=(ScheduleMethod.LASTDAY,),
    )
    both, _ = wti_valued("2026-12-01", (72.0, 75.0), pair)  # every day live
    a, _ = wti_valued("2026-12-01", (72.0, 75.0), asian)
    f, _ = wti_valued("2026-12-01", (72.0, 75.0), future)
    assert both.codes() == a.codes() == f.codes() == ("F27",)
    assert both.mark == pytest.approx(a.mark + f.mark)
    np.testing.assert_allclose(both.price_sensitivity, [1_500.0 + 1_000.0])
    np.testing.assert_allclose(a.price_sensitivity + f.price_sensitivity, [2_500.0])


def test_the_roll_takes_the_calendars_contract_on_each_day_whatever_the_schedule() -> None:
    # A schedule whose F27 expires Thursday 24 December, the 25th closed and the 26th and 27th a
    # weekend: the 24th is F27's and Monday the 28th G27's, nothing observed between. A window
    # within one contract's days references it alone. Contracts expiring every ten days or so
    # give December four references: one rule, no lead or count assumed.
    holiday_roll = wti_like(
        "roll",
        (
            ("Z26", "2026-11-20"),
            ("F27", "2026-12-24"),
            ("G27", "2027-01-20"),
            ("H27", "2027-02-22"),
        ),
    )
    terms = wti_terms(ix=holiday_roll)
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    assert [str(d) for d in enc.slot_date] == list(WTI_WINDOW)
    np.testing.assert_array_equal(enc.slot_reference, [1, 1, 1, 1, 1, 2])
    within = wti_terms(periods=(("2026-12-01", "2026-12-18"),), pays=("2026-12-22",))
    enc = encoded(within, observed_of(within), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.references, [1])
    assert enc.slot_group.size == 14
    tens = wti_like(
        "tens",
        (
            ("Z26", "2026-11-20"),
            ("F27", "2026-12-04"),
            ("G27", "2026-12-14"),
            ("H27", "2026-12-24"),
            ("J27", "2027-01-20"),
        ),
    )
    terms = wti_terms(
        periods=(("2026-12-01", "2026-12-31"),),
        quantities=(2_200.0,),
        pays=("2027-01-05",),
        ix=tens,
    )
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.slot_reference, [1] * 4 + [2] * 6 + [3] * 8 + [4] * 4)
    np.testing.assert_array_equal(enc.references, [1, 2, 3, 4])
    result, _ = wti_valued("2026-12-01", (72.0, 73.0, 74.0, 75.0), terms)
    np.testing.assert_allclose(result.price_sensitivity, [400.0, 600.0, 800.0, 400.0])
    assert result.mark == pytest.approx(-154_000 + 400 * 72 + 600 * 73 + 800 * 74 + 400 * 75)


def test_an_asian_outside_the_calendars_coverage_is_refused_at_either_end() -> None:
    # March 2027 lies after H27's expiry, so nothing prices it and the encoding says so; November's
    # days before Z26 expires are the boundary contract's, which the calendar does not hold, so
    # the preparation refuses the batch by its first slot, the day named and the contract that
    # bounds the calendar.
    march = wti_terms(periods=(("2027-03-01", "2027-03-31"),), contracts=(3,), pays=("2027-04-05",))
    with pytest.raises(ValueError) as refused:
        encoded(march, observed_of(march), UNITS, WorkCounter())
    assert str(refused.value) == (
        "trade 1 at row 1 observes 2027-03-01, after the schedule's last expiry, 2027-02-22; "
        "nothing prices it"
    )
    november = wti_terms(periods=(("2026-11-02", "2026-11-19"),), pays=("2026-11-23",))
    enc = encoded(november, observed_of(november), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.references, [0])
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, wti_history("2026-12-01"), WorkCounter())
    assert str(refused.value) == (
        "trade 1 at row 1 observes 2026-11-02, before the calendar begins on 2026-11-21; the "
        "schedule's first contract, Z26, bounds the calendar and nothing prices its days"
    )


def test_an_asian_strip_on_the_wti_like_index_keeps_each_months_quantity_days_and_payment() -> None:
    # December and January as one strip, 1,200 then 2,400 barrels: December's 22 days 15 to F27
    # and 7 to G27, January's 20 days 13 to G27 and 7 to H27, each month its own group paying two
    # business days after its last day, 5 January and 2 February; three references on the axis,
    # each month's quantity shared over its own days.
    terms = wti_terms(
        periods=(("2026-12-01", "2026-12-31"), JANUARY_BOUNDS),
        quantities=(1_200.0, 2_400.0),
        contracts=(0, 1),
        pays=("2027-01-05", "2027-02-02"),
    )
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.group_contract, [0, 1])
    np.testing.assert_array_equal(enc.payment_date, dates("2027-01-05", "2027-02-02"))
    np.testing.assert_array_equal(enc.slot_reference, [1] * 15 + [2] * 7 + [2] * 13 + [3] * 7)
    np.testing.assert_array_equal(enc.references, [1, 2, 3])
    result, _ = wti_valued("2026-12-01", (72.0, 75.0, 78.0), terms)
    a_day = (1_200 / 22, 2_400 / 20)
    sensitivity = (15 * a_day[0], 7 * a_day[0] + 13 * a_day[1], 7 * a_day[1])
    np.testing.assert_allclose(result.price_sensitivity, sensitivity)
    assert result.codes() == ("F27", "G27", "H27")
    assert result.mark == pytest.approx(
        -84_000 - 168_000 + 72 * sensitivity[0] + 75 * sensitivity[1] + 78 * sensitivity[2]
    )
    assert result.lot_delta_total == pytest.approx(3.6)


def test_the_wti_asian_doubles_when_booked_twice_and_sums_into_one_group() -> None:
    twice = wti_terms(
        periods=(("2026-12-18", "2026-12-28"),) * 2,
        quantities=(1_200.0, 1_200.0),
        contracts=(0, 0),
        pays=("2026-12-30", "2026-12-30"),
    )
    one, _ = wti_valued("2026-12-19", (72.0, 75.0))
    both, _ = wti_valued("2026-12-19", (72.0, 75.0), twice)
    assert both.mark == pytest.approx(2 * one.mark)
    np.testing.assert_allclose(both.lot_delta, 2 * one.lot_delta)
    assert both.prepared.encoded.slot_group.size == 6  # one group, the two rows' days summed


# --- delta by day, month and year, daily-risk-vector.md ------------------------------------------
# A month-aligned index for the ticket's asian-and-pen example: X26 expiring 30 November bounds
# the calendar, Z26 expires 31 December and F27 29 January, the market and the payment calendar
# closed on 25 December and New Year's Day, dollars a barrel, a barrel and a thousand-barrel LOT.
MONTHLY = wti_like("monthly", (("X26", "2026-11-30"), ("Z26", "2026-12-31"), ("F27", "2027-01-29")))
DECEMBER_BOUNDS = ("2026-12-01", "2026-12-31")
ASIAN_AND_PEN_STATES = [
    ("2026-12-01", 25, 125_000, 0),
    ("2026-12-30", 5, 125_000, 0),
    ("2026-12-31", 1, 110_000, 15_000),
    ("2027-01-01", 0, 110_000, 15_000),
    ("2027-01-04", 0, 0, 125_000),
]


def asian_and_pen(pen_pays: str = "2026-12-31", reverse: bool = False) -> ResolvedTrades:
    """The ticket's two rows on the month-aligned index: 22 LOT of a December asian paying
    4 January and 3 LOT of a Z26 penultimate paying the 31st, or the 4th at +2bd, both at 70."""
    order = slice(None, None, -1) if reverse else slice(None)
    return wti_terms(
        periods=(DECEMBER_BOUNDS, DECEMBER_BOUNDS)[order],
        quantities=(22.0, 3.0)[order],
        contracts=(1, 1),
        pays=("2027-01-04", pen_pays)[order],
        methods=(ScheduleMethod.ASIAN, ScheduleMethod.PENULTIMATE)[order],
        units=(1, 1),
        ix=MONTHLY,
    )


def views(
    prepared: PreparedTrades,
) -> tuple[list[str], list[float], list[str], list[float], list[str], list[float]]:
    """The three retained views as lists: the days and their lots, the months and theirs, the
    years and theirs, each bucket start spelled as a day, read off the preparation as the
    result's selector reads them."""
    encoded = prepared.encoded
    days, daily = encoded.days, prepared.daily_lots
    months, monthly = encoded.months, prepared.monthly_lots
    years, yearly = encoded.years, prepared.yearly_lots
    return (
        [str(d) for d in days],
        [float(x) for x in daily],
        [str(m) for m in months],
        [float(x) for x in monthly],
        [str(y) for y in years],
        [float(x) for x in yearly],
    )


@pytest.mark.parametrize(
    ("as_of", "live", "mark", "cash"),
    ASIAN_AND_PEN_STATES,
    ids=[s[0] for s in ASIAN_AND_PEN_STATES],
)
def test_the_asian_and_pen_report_their_delta_by_day_month_and_year_as_the_ticket_says(
    as_of: str, live: float, mark: float, cash: float
) -> None:
    # Fixings of 75 on every day and a quote of 75: the asian a lot a day over December's 22
    # pricing days and the pen 3 lots on the 30th, 4 lots that day and 25 in all while every day
    # is live; a day's lots fall to zero once it has fixed, the day stays on the axis, and the one
    # December bucket and the one 2026 bucket read the batch's live lots in every state. The rows
    # reversed give the same vectors; two groups, 23 slots, one contract on the risk axis.
    for terms in (asian_and_pen(), asian_and_pen(reverse=True)):
        result, _ = wti_valued(as_of, (75.0,), terms, settles={}, default=75.0)
        assert (result.mark, result.cash) == (pytest.approx(mark), pytest.approx(cash))
        assert result.prepared.encoded.slot_group.size == 23
        days, daily, months, monthly, years, yearly = views(result.prepared)
        assert days == DECEMBER and months == ["2026-12-01"] and years == ["2026-01-01"]
        expected = [0.0 if d < as_of else (4.0 if d == "2026-12-30" else 1.0) for d in DECEMBER]
        assert daily == pytest.approx(expected)
        assert monthly == pytest.approx([live]) and yearly == pytest.approx([live])
        assert result.lot_delta_total == pytest.approx(live) and result.codes() == ("Z26",)
        np.testing.assert_allclose(result.lot_delta, [live])


def test_the_pen_at_two_days_coalesces_the_slots_and_changes_no_view() -> None:
    # Both paying 4 January: one group, 22 slots, the 30th's slot the asian's and the pen's
    # together; the three views as before in every state, and the mark on the 31st and 1 January
    # 125,000 with no cash, the pen's amount fixed but unpaid.
    later = asian_and_pen("2027-01-04")
    for as_of, _, mark, cash in ASIAN_AND_PEN_STATES:
        result, _ = wti_valued(as_of, (75.0,), later, settles={}, default=75.0)
        assert result.prepared.encoded.slot_group.size == 22
        before, _ = wti_valued(as_of, (75.0,), asian_and_pen(), settles={}, default=75.0)
        assert views(result.prepared) == views(before.prepared)
        if as_of in ("2026-12-31", "2027-01-01"):
            assert (result.mark, result.cash) == (pytest.approx(125_000), 0.0)
        else:
            assert (result.mark, result.cash) == (pytest.approx(mark), pytest.approx(cash))


def test_bucket_membership_follows_the_observation_day_and_not_payment_or_booking() -> None:
    # The ticket's boundary case on the WTI-like index: 1 LOT a calendar day over 30 December to
    # 5 January, two December pricing days of a lot and two January ones of 2.5, and 3 LOT over
    # 1 and 2 February, 1.5 each; the months paying 5 January, 7 January and 4 February. Daily lots
    # 1, 1, 2.5, 2.5, 1.5 and 1.5 off G27 then H27, months 2, 5 and 3, years 2 and 8, contracts 7
    # and 3, every view 10; the December days fix by 1 January and the 4th by the 5th, the axes
    # standing, and a payment in January moves nothing into January.
    terms = wti_terms(
        periods=(
            ("2026-12-30", "2026-12-31"),
            ("2027-01-01", "2027-01-05"),
            ("2027-02-01", "2027-02-02"),
        ),
        quantities=(1.0, 1.0, 3.0),
        contracts=(0, 1, 2),
        pays=("2027-01-05", "2027-01-07", "2027-02-04"),
        units=(1, 1, 1),
        bases=(QuantityPer.CALDAY, QuantityPer.CALDAY, QuantityPer.MONTH),
    )
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    np.testing.assert_array_equal(enc.payment_date, dates("2027-01-05", "2027-01-07", "2027-02-04"))
    assert [str(d) for d in enc.days] == [
        "2026-12-30",
        "2026-12-31",
        "2027-01-04",
        "2027-01-05",
        "2027-02-01",
        "2027-02-02",
    ]
    assert [WTI.schedule.codes[int(r)] for r in enc.day_reference] == ["G27"] * 4 + ["H27"] * 2
    assert [str(m) for m in enc.months] == ["2026-12-01", "2027-01-01", "2027-02-01"]
    assert [str(y) for y in enc.years] == ["2026-01-01", "2027-01-01"]
    np.testing.assert_array_equal(enc.month_of_day, [0, 0, 1, 1, 2, 2])
    np.testing.assert_array_equal(enc.year_of_month, [0, 1, 1])
    for as_of, daily, monthly, yearly, by_contract in (
        ("2026-12-30", [1, 1, 2.5, 2.5, 1.5, 1.5], [2, 5, 3], [2, 8], [7, 3]),
        ("2027-01-01", [0, 0, 2.5, 2.5, 1.5, 1.5], [0, 5, 3], [0, 8], [5, 3]),
        ("2027-01-05", [0, 0, 0, 2.5, 1.5, 1.5], [0, 2.5, 3], [0, 5.5], [2.5, 3]),
    ):
        result, _ = wti_valued(as_of, (80.0, 81.0), terms)
        got = views(result.prepared)
        assert got[1] == pytest.approx(daily), as_of
        assert got[3] == pytest.approx(monthly) and got[5] == pytest.approx(yearly), as_of
        np.testing.assert_allclose(result.lot_delta, by_contract)
        assert result.codes() == ("G27", "H27")
        assert result.lot_delta_total == pytest.approx(sum(daily))


def test_a_lastday_f27_in_december_counts_in_december_and_the_six_day_asian_in_its_month() -> None:
    # 3 LOT of F27 under lastday over its own January month observes 21 December and pays the 23rd:
    # on 18 December its 3 lots stand on the 21st, in December 2026 and in 2026, never in January,
    # its booked month. The ticket's six-day asian: 0.2 a day, F27 twice then G27, one December
    # bucket of 1.2 and one 2026 bucket; after the roll the first two days read zero, the rest 0.2,
    # and the axes stand.
    future = wti_terms(
        periods=(JANUARY_BOUNDS,),
        quantities=(3.0,),
        contracts=(1,),
        pays=("2026-12-23",),
        methods=(ScheduleMethod.LASTDAY,),
        units=(1,),
    )
    result, _ = wti_valued("2026-12-18", (72.0, 75.0), future)
    assert views(result.prepared) == (
        ["2026-12-21"],
        [3.0],
        ["2026-12-01"],
        [3.0],
        ["2026-01-01"],
        [3.0],
    )
    live, _ = wti_valued("2026-12-18", (72.0, 75.0))
    days, daily, months, monthly, years, yearly = views(live.prepared)
    assert days == list(WTI_WINDOW) and daily == pytest.approx([0.2] * 6)
    references = [WTI.schedule.codes[int(r)] for r in live.prepared.encoded.day_reference]
    assert references == ["F27"] * 2 + ["G27"] * 4
    assert (months, years) == (["2026-12-01"], ["2026-01-01"])
    assert monthly == pytest.approx([1.2]) and yearly == pytest.approx([1.2])
    rolled, _ = wti_valued("2026-12-22", (75.0,))
    assert views(rolled.prepared)[0] == list(WTI_WINDOW)
    assert views(rolled.prepared)[1] == pytest.approx([0, 0, 0.2, 0.2, 0.2, 0.2])


def test_opposite_quantities_net_by_day_keep_their_dates_and_net_again_by_month() -> None:
    # The same day bought and sold: one slot of nothing, the day kept at zero in every view. Two
    # days bought and sold: both kept, 1.2 and -1.2 off F27 and G27, the month and the year at zero.
    same = wti_terms(
        periods=(("2026-12-18", "2026-12-18"),) * 2,
        quantities=(1_200.0, -1_200.0),
        contracts=(0, 0),
        pays=("2026-12-22", "2026-12-22"),
    )
    result, _ = wti_valued("2026-12-01", (72.0, 75.0), same)
    assert views(result.prepared) == (
        ["2026-12-18"],
        [0.0],
        ["2026-12-01"],
        [0.0],
        ["2026-01-01"],
        [0.0],
    )
    apart = wti_terms(
        periods=(("2026-12-18", "2026-12-18"), ("2026-12-22", "2026-12-22")),
        quantities=(1_200.0, -1_200.0),
        contracts=(0, 0),
        pays=("2026-12-22", "2026-12-24"),
    )
    result, _ = wti_valued("2026-12-01", (72.0, 75.0), apart)
    days, daily, _, monthly, _, yearly = views(result.prepared)
    assert days == ["2026-12-18", "2026-12-22"] and daily == pytest.approx([1.2, -1.2])
    assert monthly == pytest.approx([0.0]) and yearly == pytest.approx([0.0])
    np.testing.assert_allclose(result.lot_delta, [1.2, -1.2])
    assert result.lot_delta_total == pytest.approx(0.0)


def test_two_decembers_are_two_months_in_two_years() -> None:
    # Fifteen monthly contracts from Z26 to G28, each expiring the month before its own: a December
    # 2026 asian and a December 2027 asian of 2,200 barrels each, 100 a day, are two month buckets
    # a year apart and two year buckets, 2.2 lots each while live on 1 December 2026.
    letters = "FGHJKMNQUVXZ"
    months = np.arange("2026-12", "2028-03", dtype="datetime64[M]")
    expiries = np.busday_offset(
        (months - np.timedelta64(1, "M")).astype("datetime64[D]") + np.timedelta64(19, "D"),
        0,
        roll="backward",
        holidays=dates(*WTI_HOLIDAYS),
    )
    contracts = tuple(
        (f"{letters[int(m.astype(int)) % 12]}{str(m)[2:4]}", str(e))
        for m, e in zip(months, expiries, strict=True)
    )
    long = wti_like("long", contracts)
    terms = wti_terms(
        periods=(("2026-12-01", "2026-12-31"), ("2027-12-01", "2027-12-31")),
        quantities=(2_200.0, 2_200.0),
        contracts=(0, 12),
        pays=("2027-01-05", "2028-01-04"),
        ix=long,
    )
    result, _ = wti_valued("2026-12-01", tuple([70.0] * 14), terms)
    days, daily, months_, monthly, years, yearly = views(result.prepared)
    assert len(days) == 45 and sum(daily) == pytest.approx(4.4)
    assert months_ == ["2026-12-01", "2027-12-01"] and monthly == pytest.approx([2.2, 2.2])
    assert years == ["2026-01-01", "2027-01-01"] and yearly == pytest.approx([2.2, 2.2])


def test_a_days_or_a_months_lots_past_the_largest_number_are_refused_by_their_bucket() -> None:
    # Each slot finite, each contract and the batch finite in the order the slots are summed, and
    # a day's own sum past the largest number: on the BTU-lot index, group one, paying the 27th,
    # holds 1e308 lots on 23 November and -1e308 on the 24th, group two, paying the 30th, 1e308 on
    # the 23rd again; the contract sums 1e308, 0 and 1e308 and stays finite, the 23rd sums to
    # infinity and is refused by its day. With the negative lot on the 25th instead, every day is
    # finite and November sums past the largest number, its two positive days coming first.
    def tiny(
        periods: tuple[tuple[str, str], ...], quantities: tuple[float, ...], pays: tuple[str, ...]
    ) -> ResolvedTrades:
        return wti_terms(
            periods=periods,
            quantities=quantities,
            contracts=(1,) * len(periods),
            pays=pays,
            units=(1,) * len(periods),
            ix=TINY_LOT,
            price=300.0,
        )

    pays = ("2026-11-27", "2026-11-27", "2026-11-30")
    by_day = tiny(
        (("2026-11-23", "2026-11-23"), ("2026-11-24", "2026-11-24"), ("2026-11-23", "2026-11-23")),
        (1e302, -1e302, 1e302),
        pays,
    )
    enc = encoded(by_day, observed_of(by_day), UNITS, WorkCounter())
    np.testing.assert_allclose(enc.slot_exposure / 1e-8, [1e308, -1e308, 1e308])  # finite each
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, wti_history("2026-11-20", {}, TINY_LOT), WorkCounter())
    assert str(refused.value) == (
        "the day 2026-11-23 has inf of lot delta in all, expected a finite number of lots of BTU "
        "(1 BTU); its exposures in lots sum past the largest number"
    )
    by_month = tiny(
        (("2026-11-23", "2026-11-23"), ("2026-11-25", "2026-11-25"), ("2026-11-24", "2026-11-24")),
        (1e302, -1e302, 1e302),
        pays,
    )
    enc = encoded(by_month, observed_of(by_month), UNITS, WorkCounter())
    with pytest.raises(ValueError) as refused:
        prepared_trades(enc, wti_history("2026-11-20", {}, TINY_LOT), WorkCounter())
    assert str(refused.value) == (
        "the month from 2026-11-01 has inf of lot delta in all, expected a finite number of lots "
        "of BTU (1 BTU); its exposures in lots sum past the largest number"
    )


# --- an IFERC basis future, iferc-basis-futures.md ------------------------------------------
# The ticket's synthetic Waha-like index: three months, X26, Z26 and F27, each last trading on the
# last business day before its month and its index published on the first business day of it,
# dollars an MMBtu settled in dollars, a 2,500 MMBtu LOT and a bare MMBTU, the LOT reported, and no
# pricing calendar, an IFERC index having none; the payment calendar closes New Year's Day. WAH001,
# 1 LOT of Z26 at -0.50: 2,500 MMBtu of exposure and a fixed leg of 1,250, so an amount of
# 1,250 + 2,500 times the basis, observed once, on 1 December, the day Z26's index publishes, and
# paid 3 December, three business days after the 30 November last trading day.

WAHA_SCHEDULE = iferc_schedule(
    ("X26", "Z26", "F27"),
    dates("2026-10-30", "2026-11-30", "2026-12-31"),
    dates("2026-11-02", "2026-12-01", "2027-01-04"),
)
WAHA = index(
    "WAHA",
    "Waha basis - ICE",
    WAHA_SCHEDULE,
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("LOT", "MMBTU"),
        numbers(2_500.0, 1.0),
        ("MMBTU", "MMBTU"),
        numbers(0.0, 0.0),
        numbers(0.0, 0.0),
        UNITS,
    ),
    None,
    "LOT",
    UNITS,
)
WAHA_PAYS = holiday_calendar(dates("2027-01-01"))
WAHA_MONTHS = schedule_months(WAHA_SCHEDULE)
# Each month's payment day at +3bd from its last trading day on that calendar, the ticket's table:
# 4 November, 3 December and, New Year's Day closed, 6 January.
WAHA_PAYMENT = ("2026-11-04", "2026-12-03", "2027-01-06")
WAHA_LOT = "lots of LOT (2500 MMBTU)"
X26_INDEX = {"X26": -0.40}  # the earlier month's index, which every December history must hold
Z26_FIXED = {**X26_INDEX, "Z26": -0.20}
Z26_CORRECTED = {**X26_INDEX, "Z26": -0.10}


def waha_terms(
    quantities: tuple[float, ...] = (1.0,),
    contracts: tuple[int, ...] = (1,),
    occurrence: tuple[int, ...] | None = None,
    pays: tuple[str, ...] | None = None,
    lags: tuple[int, ...] | None = None,
    units: tuple[int, ...] | None = None,
    bases: tuple[QuantityPer, ...] | None = None,
    methods: tuple[ScheduleMethod, ...] | None = None,
    settlement: Settlement = Settlement.FINANCIAL,
    prices: tuple[float, ...] | None = None,
    trade_date: str = "2026-11-30",
    periods: tuple[tuple[str, str], ...] | None = None,
) -> ResolvedTrades:
    """Trades on the Waha-like index: lastday, cleared and financial in LOT, a month's quantity at
    -0.50, or the units, bases, methods and prices given, each component on the schedule row given,
    its own occurrence unless said, covering its whole month unless periods are given, and paying
    its month's day at +3bd unless other days and lags are given; the labels WAH001 on."""
    n = len(quantities)
    occ = np.arange(n, dtype=np.intp) if occurrence is None else rows(*occurrence)
    m = int(occ[-1]) + 1
    contract = rows(*contracts)
    if periods is None:
        start, end = month_bounds(WAHA_MONTHS[contract])
    else:
        start, end = dates(*(s for s, _ in periods)), dates(*(e for _, e in periods))
    method = (
        one_choice(METHODS, ScheduleMethod.LASTDAY, m)
        if methods is None
        else np.array([METHODS.index(x) for x in methods], dtype=np.intp)
    )
    basis = (
        one_choice(BASES, QuantityPer.MONTH, m)
        if bases is None
        else np.array([BASES.index(b) for b in bases], dtype=np.intp)
    )
    payment = None
    if settlement is Settlement.FINANCIAL:
        pay_days = (
            dates(*(WAHA_PAYMENT[int(c)] for c in contract)) if pays is None else dates(*pays)
        )
        lag = np.full(m, 3) if lags is None else np.array(lags, dtype=np.int64)
        payment = PaymentTerms(lag, (WAHA_PAYS,) * m, pay_days)
    return resolved_trades(
        FIXED_FLOAT,
        WAHA,
        spec(m) if units is None else rows(*units),
        Route.CLEARED,
        settlement,
        method,
        basis,
        1000 + np.arange(1, m + 1, dtype=np.int64),
        ("ICE Clear Europe",) * m,
        None,
        np.repeat(day(trade_date), m),
        occ,
        contract,
        numbers(*quantities),
        start,
        end,
        numbers(*([-0.50] * n)) if prices is None else numbers(*prices),
        payment,
    )


def waha_history(as_of: str, indices: dict[str, float], ix: Index = WAHA) -> MarketHistory:
    """The index's history valued on that day with the months' indices given, newest first as the
    desk keeps them; every month published before the day is among them, the history's own rule."""
    cal = calendar(valuation_date(day(as_of), 0.5), ix)
    codes = tuple(reversed(indices))
    return market_history(cal, iferc_fixings(codes, numbers(*(indices[c] for c in codes)), ix))


def waha_valued(
    as_of: str,
    indices: dict[str, float],
    quotes: tuple[float, ...],
    terms: ResolvedTrades | None = None,
) -> tuple[TradeResults, WorkCounter]:
    counter = WorkCounter()
    terms = waha_terms() if terms is None else terms
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    history = waha_history(as_of, indices, terms.index)
    prep = prepared_trades(enc, history, counter)
    return trade_results(prep, quoted(history, *quotes), counter), counter


def test_an_iferc_future_observes_its_months_index_once_on_its_publication_day() -> None:
    # The terms hold the IFERC schedule as the kind rule found it; the one observation is Z26's
    # publication day with the whole weight, no pricing calendar read; the encoding converts the
    # lot once, 2,500 MMBtu and a fixed leg of 1,250, one slot on 1 December referencing Z26, one
    # group paying 3 December, and the day, month and year axes that one day.
    terms = waha_terms()
    assert terms.schedule is WAHA_SCHEDULE and terms.index is WAHA
    np.testing.assert_array_equal(terms.start_date, dates("2026-12-01"))
    np.testing.assert_array_equal(terms.end_date, dates("2026-12-31"))
    np.testing.assert_array_equal(terms.covered_days, [31])
    obs = observed_of(terms)
    np.testing.assert_array_equal(obs.component, [0])
    np.testing.assert_array_equal(obs.date, dates("2026-12-01"))
    np.testing.assert_array_equal(obs.weight, [1.0])
    counter = WorkCounter()
    enc = encoded(terms, obs, UNITS, counter)
    np.testing.assert_array_equal(enc.quote_quantity, [2_500.0])
    np.testing.assert_array_equal(enc.offset, [1_250.0])
    np.testing.assert_array_equal(enc.group_contract, [1])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-03"))
    np.testing.assert_array_equal(enc.slot_date, dates("2026-12-01"))
    np.testing.assert_array_equal(enc.slot_reference, [1])
    np.testing.assert_array_equal(enc.slot_exposure, [2_500.0])
    np.testing.assert_array_equal(enc.references, [1])
    assert [str(d) for d in enc.days] == ["2026-12-01"]
    assert [str(m) for m in enc.months] == ["2026-12-01"]
    assert [str(y) for y in enc.years] == ["2026-01-01"]
    assert counter.freeze().as_dict() == {
        "encoded_components": 1,
        "encoded_groups": 1,
        "encoded_observations": 1,
        "encoded_slots": 1,
        "reserved_components": 1,
    }


WAHA_STATES = [
    ("2026-11-30", X26_INDEX, (-0.30, -0.10), 500, 0, 1),
    ("2026-12-01", X26_INDEX, (-0.30, -0.10), 500, 0, 1),
    ("2026-12-01", X26_INDEX, (-0.25, -0.10), 625, 0, 1),
    ("2026-12-02", Z26_FIXED, (-0.10,), 750, 0, 0),
    ("2026-12-03", Z26_FIXED, (-0.10,), 0, 750, 0),
    ("2026-12-02", Z26_CORRECTED, (-0.10,), 1_000, 0, 0),
]
WAHA_IDS = [
    "30 Nov, booked, live at -0.30",
    "1 Dec, publication day, live at -0.30",
    "1 Dec, a tick to -0.25",
    "2 Dec, fixed at -0.20 and unpaid",
    "3 Dec, paid",
    "2 Dec, the index corrected to -0.10",
]


@pytest.mark.parametrize(
    ("as_of", "indices", "quotes", "mark", "cash", "live"), WAHA_STATES, ids=WAHA_IDS
)
def test_the_waha_basis_future_marks_fixes_and_pays_as_the_ticket_says(
    as_of: str,
    indices: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    live: int,
) -> None:
    # 1,250 + 2,500 times the basis: 500 at -0.30, 625 at -0.25, 750 once the index prints -0.20,
    # cash on 3 December, the payment day, and 1,000 under a corrected index. Live on its
    # publication day and fixed the day after; the one slot's lot is the live delta, on Z26 and on
    # 1 December, zero once fixed with the day kept; 2,500 dollars per dollar an MMBtu of
    # sensitivity while live; one fixing read once fixed and one quote read while live.
    result, counter = waha_valued(as_of, indices, quotes)
    assert (result.mark, result.cash) == (pytest.approx(mark), pytest.approx(cash))
    np.testing.assert_array_equal(result.contracts, [1])
    np.testing.assert_allclose(result.lot_delta, [live])
    assert result.lot_delta_total == pytest.approx(live)
    np.testing.assert_allclose(result.price_sensitivity, [2_500.0 * live])
    assert result.lot_unit == WAHA_LOT
    prep = result.prepared
    np.testing.assert_array_equal(prep.is_fixed, [as_of > "2026-12-01"])
    np.testing.assert_array_equal(prep.is_settled, [as_of >= "2026-12-03"])
    days, daily, months, monthly, years, yearly = views(prep)
    assert (days, months, years) == (["2026-12-01"], ["2026-12-01"], ["2026-01-01"])
    assert (daily, monthly, yearly) == ([live], [live], [live])
    counts = counter.freeze().as_dict()
    assert counts["prepared_slots"] == 1 and counts["fixings_read"] == 1 - live
    assert counts["live_prices_read"] == live


def test_a_tick_on_the_waha_future_reads_one_quote_and_prepares_nothing_again() -> None:
    first, _ = waha_valued("2026-12-01", X26_INDEX, (-0.30, -0.10))
    counter = WorkCounter()
    ticked = trade_results(first.prepared, quoted(first.prepared.history, -0.25, -0.10), counter)
    assert ticked.prepared is first.prepared and ticked.mark == pytest.approx(625)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 1}
    assert first.mark == pytest.approx(500)  # the first results stand


def test_a_lot_and_its_2500_mmbtu_value_alike_and_a_calendar_day_quantity_scales_once() -> None:
    # 1 LOT a month and 2,500 MMBtu a month are one exposure and one reporting lot; 1 MMBtu a
    # calendar day over December is 31 MMBtu, one observation still, 6.20 of mark at -0.30 and
    # 9.30 once fixed at -0.20, 31/2500 of a lot while live.
    in_mmbtu = waha_terms(quantities=(2_500.0,), units=(1,))
    lot, _ = waha_valued("2026-12-01", X26_INDEX, (-0.30, -0.10))
    mmbtu, _ = waha_valued("2026-12-01", X26_INDEX, (-0.30, -0.10), in_mmbtu)
    assert mmbtu.mark == pytest.approx(lot.mark) and mmbtu.lot_delta_total == pytest.approx(1)
    np.testing.assert_array_equal(mmbtu.prepared.encoded.quote_quantity, [2_500.0])
    daily = waha_terms(quantities=(1.0,), units=(1,), bases=(QuantityPer.CALDAY,))
    np.testing.assert_array_equal(daily.component_quantity, [31.0])
    assert observed_of(daily).date.size == 1
    live, _ = waha_valued("2026-12-01", X26_INDEX, (-0.30, -0.10), daily)
    assert live.mark == pytest.approx(6.20) and live.lot_delta_total == pytest.approx(31 / 2_500)
    fixed, _ = waha_valued("2026-12-02", Z26_FIXED, (-0.10,), daily)
    assert (fixed.mark, fixed.cash, fixed.lot_delta_total) == (pytest.approx(9.30), 0, 0)


def test_two_waha_occurrences_double_the_answers_in_either_order_and_a_zero_row_stands() -> None:
    # Two identical rows: twice the mark, twice the delta, one slot since one contract, one day
    # and one payment day; a batch of unlike rows equals its singletons summed whatever the order;
    # a zero row validates, contributes nothing and keeps its slot.
    twice = waha_terms(quantities=(1.0, 1.0), contracts=(1, 1))
    both, counter = waha_valued("2026-12-01", X26_INDEX, (-0.30, -0.10), twice)
    one, _ = waha_valued("2026-12-01", X26_INDEX, (-0.30, -0.10))
    assert both.mark == pytest.approx(2 * one.mark) and both.lot_delta_total == pytest.approx(2)
    assert both.prepared.encoded.slot_group.size == 1
    assert counter.freeze().as_dict()["encoded_components"] == 2
    paid, _ = waha_valued("2026-12-03", Z26_FIXED, (-0.10,), twice)
    assert (paid.mark, paid.cash) == (0, pytest.approx(1_500))
    mixed = waha_terms(quantities=(1.0, 2.0), contracts=(1, 1), prices=(-0.50, -0.40))
    turned = waha_terms(quantities=(2.0, 1.0), contracts=(1, 1), prices=(-0.40, -0.50))
    for as_of, indices, quotes in (
        ("2026-12-01", X26_INDEX, (-0.30, -0.10)),
        ("2026-12-02", Z26_FIXED, (-0.10,)),
        ("2026-12-03", Z26_FIXED, (-0.10,)),
    ):
        a, _ = waha_valued(as_of, indices, quotes, mixed)
        b, _ = waha_valued(as_of, indices, quotes, turned)
        singles = [
            waha_valued(as_of, indices, quotes, waha_terms(quantities=(q,), prices=(p,)))[0]
            for q, p in ((1.0, -0.50), (2.0, -0.40))
        ]
        assert a.mark == pytest.approx(b.mark)
        assert a.mark == pytest.approx(sum(s.mark for s in singles))
        assert a.cash == pytest.approx(b.cash)
        assert a.cash == pytest.approx(sum(s.cash for s in singles))
        assert a.lot_delta_total == pytest.approx(b.lot_delta_total)
    zero, _ = waha_valued("2026-12-01", X26_INDEX, (-0.30, -0.10), waha_terms(quantities=(0.0,)))
    assert (zero.mark, zero.lot_delta_total) == (0, 0)
    assert zero.prepared.encoded.slot_group.size == 1  # the row kept ready, its slot standing


def test_a_long_and_a_short_lot_paying_on_two_days_keep_their_groups_as_the_risk_nets() -> None:
    # Long 1 LOT at +3bd and short 1 LOT at +4bd, both Z26 at -0.50: two groups and two slots on
    # one day, the live risk netting to zero and nothing disappearing, the one quote still read;
    # after the index prints -0.20, 3 December has the long's 750 of cash and the short's -750 of
    # mark, and 4 December both as cash, zero net.
    pair = waha_terms(
        quantities=(1.0, -1.0), contracts=(1, 1), pays=("2026-12-03", "2026-12-04"), lags=(3, 4)
    )
    live, counter = waha_valued("2026-12-01", X26_INDEX, (-0.30, -0.10), pair)
    enc = live.prepared.encoded
    np.testing.assert_array_equal(enc.group_contract, [1, 1])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-03", "2026-12-04"))
    assert enc.slot_group.size == 2 and enc.references.size == 1
    assert (live.mark, live.cash) == (pytest.approx(0), 0)
    assert live.lot_delta_total == pytest.approx(0)
    assert live.prepared.live_references.size == 1
    assert counter.freeze().as_dict()["live_prices_read"] == 1
    third, _ = waha_valued("2026-12-03", Z26_FIXED, (-0.10,), pair)
    assert (third.mark, third.cash) == (pytest.approx(-750), pytest.approx(750))
    np.testing.assert_array_equal(third.prepared.is_settled, [True, False])
    fourth, _ = waha_valued("2026-12-04", Z26_FIXED, (-0.10,), pair)
    assert (fourth.mark, fourth.cash) == (pytest.approx(0), pytest.approx(0))
    np.testing.assert_array_equal(fourth.prepared.is_settled, [True, True])


def test_a_z26_f27_strip_fixes_one_month_and_quotes_the_other_with_its_own_payment_days() -> None:
    # One occurrence, two components, one index and one payment day a month: on 2 December Z26's
    # index at -0.20 stands and F27 quotes -0.10, 750 and 1,000 of mark against -0.50, the delta
    # zero on Z26 and a lot on F27; F27 pays 6 January, its 31 December last trading day plus
    # three business days with New Year's Day closed.
    strip = waha_terms(quantities=(1.0, 1.0), contracts=(1, 2), occurrence=(0, 0))
    np.testing.assert_array_equal(observed_of(strip).date, dates("2026-12-01", "2027-01-04"))
    result, _ = waha_valued("2026-12-02", Z26_FIXED, (-0.10,), strip)
    enc = result.prepared.encoded
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-03", "2027-01-06"))
    np.testing.assert_array_equal(enc.group_contract, [1, 2])
    assert (result.mark, result.cash) == (pytest.approx(1_750), 0)
    np.testing.assert_array_equal(result.contracts, [1, 2])
    np.testing.assert_allclose(result.lot_delta, [0.0, 1.0])
    days, daily, months, monthly, years, yearly = views(result.prepared)
    assert days == ["2026-12-01", "2027-01-04"] and daily == [0.0, 1.0]
    assert months == ["2026-12-01", "2027-01-01"] and monthly == [0.0, 1.0]
    assert years == ["2026-01-01", "2027-01-01"] and yearly == [0.0, 1.0]


def test_the_first_iferc_month_is_a_month_to_trade_and_the_existing_refusals_hold() -> None:
    # X26 booked on 15 October, its index published 2 November and paying 4 November: on the 3rd
    # fixed at -0.40 and unpaid, 250 of mark, nothing bounding the calendar; on the 4th cash. A
    # history without the month's index, a history over another index of the same name and a
    # vector stopping short of a traded month are the history's and the market's refusals.
    x26 = waha_terms(contracts=(0,), trade_date="2026-10-15")
    np.testing.assert_array_equal(observed_of(x26).date, dates("2026-11-02"))
    third, counter = waha_valued("2026-11-03", X26_INDEX, (-0.30, -0.10), x26)
    assert (third.mark, third.cash, third.lot_delta_total) == (pytest.approx(250), 0, 0)
    np.testing.assert_array_equal(third.prepared.encoded.payment_date, dates("2026-11-04"))
    assert counter.freeze().as_dict()["fixings_read"] == 1
    fourth, _ = waha_valued("2026-11-04", X26_INDEX, (-0.30, -0.10), x26)
    assert (fourth.mark, fourth.cash) == (0, pytest.approx(250))
    with pytest.raises(ValueError) as missing:
        waha_history("2026-11-03", {})
    assert str(missing.value) == (
        "fixings has no index for X26, expected an index for every fixed month in calendar"
    )
    twin = index(
        "WAHA",
        "Waha basis - ICE",
        WAHA_SCHEDULE,
        WAHA.conventions,
        WAHA.specifications,
        None,
        "LOT",
        UNITS,
    )
    enc = encoded(x26, observed_of(x26), UNITS, WorkCounter())
    with pytest.raises(ValueError) as other:
        prepared_trades(enc, waha_history("2026-11-03", X26_INDEX, twin), WorkCounter())
    assert str(other.value) == (
        "history is over another index, 'WAHA', expected the trades', 'WAHA'"
    )
    strip = waha_terms(quantities=(1.0, 1.0), contracts=(1, 2), occurrence=(0, 0))
    history = waha_history("2026-11-30", X26_INDEX)
    prep = prepared_trades(
        encoded(strip, observed_of(strip), UNITS, WorkCounter()), history, WorkCounter()
    )
    with pytest.raises(
        ValueError,
        match=r"^requested contract 'F27' is beyond live-price coverage ending at 'Z26'$",
    ):
        trade_results(prep, quoted(history, -0.30), WorkCounter())


def test_a_payment_on_the_publication_day_is_refused_when_the_iferc_batch_is_encoded() -> None:
    # +1bd from 30 November is 1 December, the day the index prints: no final price exists by the
    # day-based cutoff, the existing rule, and nothing is delayed in its place.
    same_day = waha_terms(pays=("2026-12-01",), lags=(1,))
    with pytest.raises(ValueError) as refused:
        encoded(same_day, observed_of(same_day), UNITS, WorkCounter())
    assert str(refused.value) == (
        "Z26 pays on 2026-12-01, expected a day after its last observation, 2026-12-01, when its "
        "final price exists"
    )


def test_an_iferc_index_takes_a_financial_lastday_future_alone_and_says_so() -> None:
    with pytest.raises(ValueError) as physical:
        waha_terms(settlement=Settlement.PHYSICAL)
    assert str(physical.value) == (
        "settlement_method is 'physical', expected 'financial' on an IFERC index; an IFERC basis "
        "future is cash settled on its month's published index"
    )
    with pytest.raises(ValueError) as asian:
        waha_terms(methods=(ScheduleMethod.ASIAN,))
    assert str(asian.value) == (
        "schedule_method of trade 1001 at row 1 is 'asian', expected 'lastday' on an IFERC "
        "index; an IFERC month has one index, published once"
    )
    with pytest.raises(ValueError) as second:
        waha_terms(
            quantities=(1.0, 1.0),
            contracts=(1, 2),
            methods=(ScheduleMethod.LASTDAY, ScheduleMethod.PENULTIMATE),
        )
    assert str(second.value) == (
        "schedule_method of trade 1002 at row 2 is 'penultimate', expected 'lastday' on an "
        "IFERC index; an IFERC month has one index, published once"
    )
    # The observations builder says the same of a method on bare arrays, and a part of a month
    # under lastday is refused as the whole month's one price.
    start, end = month_bounds(WAHA_MONTHS[rows(1)])
    with pytest.raises(ValueError) as bare:
        observed(by(ScheduleMethod.LAST3DAY, 1), WAHA, rows(1), start, end, unlabeled)
    assert str(bare.value) == (
        "schedule_method of trade at row 1 is 'last3day', expected 'lastday' on an IFERC index; "
        "an IFERC month has one index, published once"
    )
    half = waha_terms(periods=(("2026-12-01", "2026-12-15"),))
    with pytest.raises(ValueError) as part:
        observed_of(half)
    assert str(part.value) == (
        "Z26 of trade 1001 at row 1 is covered from 2026-12-01 to 2026-12-15, part of its "
        "month, expected the whole month under lastday; an IFERC month's index is one price for "
        "the whole month"
    )
    # An observation on any day but the month's publication day is refused when encoded.
    off = observations(rows(0), dates("2026-12-02"), numbers(1.0), 1)
    with pytest.raises(ValueError) as wrong_day:
        encoded(waha_terms(), off, UNITS, WorkCounter())
    assert str(wrong_day.value) == (
        "trade 1001 at row 1 observes 2026-12-02, expected 2026-12-01, the day Z26's index "
        "publishes; an IFERC month prices once, on that day"
    )


# --- numeric trade IDs, numeric-trade-ids.md ------------------------------------------------


def test_whole_trade_ids_keeps_15_digits_either_side_of_zero_and_names_the_first_bad_one() -> None:
    # The rule the template and the resolution read through: finite, whole and within the 15
    # digits, converted once to int64 and frozen; a whole value shown without a fraction, the
    # others as they are; the kernel then takes the integers and checks their count alone.
    kept = whole_trade_ids(
        numbers(999_999_999_999_999, -999_999_999_999_999, 0, 123456.0),
        lambda k: f"trade_id row {k + 1}",
    )
    assert kept.dtype == np.int64 and not kept.flags.writeable
    assert kept.tolist() == [999_999_999_999_999, -999_999_999_999_999, 0, 123456]
    for value, shown in (
        (123456.5, "123456.5"),
        (1e15, "1000000000000000"),
        (-1e15, "-1000000000000000"),
        (float("nan"), "nan"),
        (float("inf"), "inf"),
    ):
        with pytest.raises(ValueError) as refused:
            whole_trade_ids(numbers(1, value), lambda k: f"trade_id row {k + 1}")
        assert str(refused.value) == (
            f"trade_id row 2 is {shown}, expected a whole number of at most 15 digits"
        )
    assert named_trade(ids(123456, 7), 1) == "trade 7 at row 2"
    assert named_trade(None, 1) == "trade at row 2"
    terms = terms_of(trade_ids=ids(999_999_999_999_999, 2, 3, 4, 5))
    assert terms.trade_ids is not None and not terms.trade_ids.flags.writeable
    assert terms.named(0) == "trade 999999999999999 at row 1"


# --- the reserves, reserve-totals.md --------------------------------------------------------------
# The ticket's specifications on a dollars-a-barrel index over the NG schedule: LOT, a thousand
# barrels at 10.00 brokerage and 4.00 clearing a lot, and BBL, one barrel at 0.01 and 0.004, the
# LOT the reporting lot unless another is named; and the four trades of its worked example, each
# one Z26 month, 2 LOT, -2 LOT, 1,000 BBL and 0 LOT: 20 + 20 + 10 + 0 of brokerage and
# 8 + 8 + 4 + 0 of clearing, 50 and 20 USD, marketing nought, since #170.


def a_fee_index(
    brokerage: tuple[float, float] = (10.0, 0.01),
    clearing: tuple[float, float] = (4.0, 0.004),
    reporting_lot: str = "LOT",
    schedule: object = NG.schedule,
) -> Index:
    return index(
        "FEES",
        "Dollars a barrel with the ticket's two specifications",
        schedule,
        index_conventions("USD", "BBL", "USD", "VOLUME", "BBL", UNITS),
        contract_specifications(
            ("LOT", "BBL"),
            numbers(1000.0, 1.0),
            ("BBL", "BBL"),
            numbers(*brokerage),
            numbers(*clearing),
            UNITS,
        ),
        NG.holiday_calendar,
        reporting_lot,
        UNITS,
    )


def fee_terms(
    ix: Index,
    quantities: tuple[float, ...] = (2.0, -2.0, 1000.0, 0.0),
    specs: tuple[int, ...] = (0, 0, 1, 0),
    trade_ids: tuple[int, ...] = (101, 102, 103, 104),
) -> ResolvedTrades:
    """The example's rows, or others shaped like them, each one Z26 month at 70."""
    n = len(quantities)
    return resolved_trades(
        FIXED_FLOAT, ix, rows(*specs), Route.CLEARED, Settlement.PHYSICAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, n), ids(*trade_ids), None, None,
        dates(*["2026-11-20"] * n), np.arange(n, dtype=np.intp), rows(*([1] * n)),
        numbers(*quantities), *bounds_of(ix, rows(*([1] * n))), numbers(*([70.0] * n)), None,
    )  # fmt: skip


def reserves_of(terms: ResolvedTrades) -> tuple[float, float]:
    booked = encoded(terms, observed_of(terms), UNITS, WorkCounter()).reserves
    return booked.brokerage, booked.clearing


def test_the_tickets_four_trades_reserve_fifty_and_twenty_dollars() -> None:
    ix = a_fee_index()
    counter = WorkCounter()
    terms = fee_terms(ix)
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    booked = enc.reserves
    assert (booked.brokerage, booked.clearing, booked.marketing) == (50.0, 20.0, 0.0)
    assert booked.currency == "USD"
    assert counter.freeze()["reserved_components"] == 4
    # The results carry the encoding's record itself, summed once and never again, and the value
    # is the free index's: the two LOT rows net, the barrels mark half a dollar on a thousand.
    history = history_on(ix, "2026-11-24", {})
    prepared = prepared_trades(enc, history, counter)
    result = trade_results(prepared, quoted(history, 70.5, 71.0), counter)
    assert result.reserves is booked
    assert result.mark == pytest.approx(500.0) and result.cash == 0.0
    free = a_fee_index((0.0, 0.0), (0.0, 0.0))
    plain = encoded(fee_terms(free), observed_of(fee_terms(free)), UNITS, WorkCounter())
    np.testing.assert_array_equal(plain.offset, enc.offset)
    assert (plain.reserves.brokerage, plain.reserves.clearing) == (0.0, 0.0)
    assert counter.freeze()["reserved_components"] == 4  # nothing reserved again downstream


def test_singletons_sum_to_the_batch_and_order_and_duplicates_count() -> None:
    ix = a_fee_index()
    parts = [
        reserves_of(fee_terms(ix, (quantity,), (spec,), (trade_id,)))
        for quantity, spec, trade_id in (
            (2.0, 0, 101),
            (-2.0, 0, 102),
            (1000.0, 1, 103),
            (0.0, 0, 104),
        )
    ]
    assert [p[0] for p in parts] == [20.0, 20.0, 10.0, 0.0]
    assert [p[1] for p in parts] == [8.0, 8.0, 4.0, 0.0]
    assert reserves_of(fee_terms(ix)) == (50.0, 20.0)
    reversed_rows = fee_terms(ix, (0.0, 1000.0, -2.0, 2.0), (0, 1, 0, 0), (104, 103, 102, 101))
    assert reserves_of(reversed_rows) == (50.0, 20.0)
    duplicate = fee_terms(ix, (2.0, 2.0), (0, 0), (101, 101))
    assert reserves_of(duplicate) == (40.0, 16.0)  # the same trade twice reserves twice


def test_a_calday_strip_reserves_per_barrel_day_and_the_reporting_lot_changes_nothing() -> None:
    # 2 BBL a calendar day over X26 and Z26, November's 30 days and December's 31, 122 BBL:
    # 1.22 of brokerage and 0.488 of clearing, the ticket's numbers, carried through evaluation on
    # a schedule whose first contract, V26, bounds the calendar; with BBL as the reporting lot the
    # batch reserves the same, the lot being the delta's unit and no rate's.
    schedule = futures_schedule(
        ("V26", "X26", "Z26", "F27"),
        dates("2026-09-28", "2026-10-28", "2026-11-25", "2026-12-29"),
        None,
    )
    for lot in ("LOT", "BBL"):
        ix = a_fee_index(reporting_lot=lot, schedule=schedule)
        terms = resolved_trades(
            FIXED_FLOAT, ix, rows(1), Route.CLEARED, Settlement.PHYSICAL,
            *picks(ScheduleMethod.LASTDAY, QuantityPer.CALDAY, 1), ids(201), None, None,
            dates("2026-10-20"), rows(0, 0), rows(1, 2), numbers(2.0, 2.0),
            *bounds_of(ix, rows(1, 2)), numbers(70.0, 70.0), None,
        )  # fmt: skip
        np.testing.assert_array_equal(terms.component_quantity, [60.0, 62.0])
        enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
        assert enc.reserves.brokerage == pytest.approx(1.22)
        assert enc.reserves.clearing == pytest.approx(0.488)
        history = history_on(ix, "2026-10-20", {})
        prepared = prepared_trades(enc, history, WorkCounter())
        result = trade_results(prepared, quoted(history, 70.5, 71.0), WorkCounter())
        assert result.reserves is enc.reserves


def test_a_rate_that_is_not_a_number_is_refused_by_category_trade_and_row() -> None:
    terms = fee_terms(a_fee_index(brokerage=(10.0, np.nan)))
    with pytest.raises(ValueError) as refused:
        encoded(terms, observed_of(terms), UNITS, WorkCounter())
    assert str(refused.value) == (
        "brokerage reserve of trade 103 at row 3 is nan, expected a finite amount of USD; "
        "1000.0 of 'BBL' at nan a lot"
    )
    # A zero quantity hides nothing: nought times an infinite rate is not a number, and the
    # clearing rule runs after the brokerage one.
    terms = fee_terms(a_fee_index(clearing=(np.inf, 0.004)), (0.0,), (0,), (104,))
    with pytest.raises(ValueError) as refused:
        encoded(terms, observed_of(terms), UNITS, WorkCounter())
    assert str(refused.value) == (
        "clearing reserve of trade 104 at row 1 is nan, expected a finite amount of USD; "
        "0.0 of 'LOT' at inf a lot"
    )


def test_reserves_that_sum_past_the_largest_number_are_refused_for_the_batch() -> None:
    terms = fee_terms(a_fee_index(brokerage=(1e308, 0.0)), (1.0, 1.0), (0, 0), (101, 102))
    with pytest.raises(ValueError) as refused:
        encoded(terms, observed_of(terms), UNITS, WorkCounter())
    assert str(refused.value) == (
        "the batch has inf of brokerage reserve in all, expected a finite amount of USD; the "
        "components' reserves, each finite, sum past the largest number"
    )


# --- the marketing reserve, booking-fields-and-marketing-reserve.md ------------------------------
# The ticket's four rows on the fee index, LOT each: 2 and -2 of Z26, 1 of the strip Z26-F27, two
# components, and 0 of Z26, booking 15, 20, 25 and 5 of marketing: 65 USD, the strip's amount once
# and the zero row's whole, over 60 of brokerage and 24 of clearing on the five components; since
# #175. The amounts are per occurrence and the sum runs over them, never the components.


def marketed_terms(
    ix: Index,
    amounts: tuple[float, ...] | None,
    occurrence: tuple[int, ...] = (0, 1, 2, 2, 3),
    contract: tuple[int, ...] = (1, 1, 1, 2, 1),
    quantities: tuple[float, ...] = (2.0, -2.0, 1.0, 1.0, 0.0),
    trade_ids: tuple[int, ...] = (1001, 1002, 1003, 1004),
) -> ResolvedTrades:
    n = len(trade_ids)
    return resolved_trades(
        FIXED_FLOAT, ix, spec(n), Route.CLEARED, Settlement.PHYSICAL,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, n), ids(*trade_ids), None, None,
        dates(*["2026-09-24"] * n), rows(*occurrence), rows(*contract), numbers(*quantities),
        *bounds_of(ix, rows(*contract)), numbers(*([70.0] * len(contract))), None,
        marketing_reserve=None if amounts is None else numbers(*amounts),
    )  # fmt: skip


def test_the_tickets_rows_book_sixty_five_of_marketing_once_per_row() -> None:
    ix = a_fee_index()
    counter = WorkCounter()
    terms = marketed_terms(ix, (15.0, 20.0, 25.0, 5.0))
    np.testing.assert_array_equal(terms.marketing_reserve, [15.0, 20.0, 25.0, 5.0])
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    booked = enc.reserves
    assert (booked.brokerage, booked.clearing, booked.marketing) == (60.0, 24.0, 65.0)
    assert booked.currency == "USD"
    assert counter.freeze()["reserved_occurrences"] == 4  # the rows, not the five components
    assert counter.freeze()["reserved_components"] == 5
    # The duplicate row counts again, a template's one amount books once per row, and no field at
    # all books nought and sums nothing.
    twice = marketed_terms(
        ix,
        (15.0, 20.0, 25.0, 5.0, 15.0),
        occurrence=(0, 1, 2, 2, 3, 4),
        contract=(1, 1, 1, 2, 1, 1),
        quantities=(2.0, -2.0, 1.0, 1.0, 0.0, 2.0),
        trade_ids=(1001, 1002, 1003, 1004, 1001),
    )
    assert encoded(twice, observed_of(twice), UNITS, WorkCounter()).reserves.marketing == 80.0
    seven = marketed_terms(ix, (7.0, 7.0, 7.0, 7.0))
    assert encoded(seven, observed_of(seven), UNITS, WorkCounter()).reserves.marketing == 28.0
    plain = marketed_terms(ix, None)
    quiet = WorkCounter()
    nought = encoded(plain, observed_of(plain), UNITS, quiet).reserves
    assert plain.marketing_reserve is None and nought.marketing == 0.0
    assert (nought.brokerage, nought.clearing) == (60.0, 24.0)
    assert "reserved_occurrences" not in quiet.freeze().as_dict()
    # Value and risk are the same with the amounts and without: the reserves enter no number.
    history = history_on(ix, "2026-10-20", {})
    with_amounts = trade_results(
        prepared_trades(enc, history, WorkCounter()),
        quoted(history, 70.5, 71.0),
        WorkCounter(),
    )
    without = trade_results(
        prepared_trades(
            encoded(plain, observed_of(plain), UNITS, WorkCounter()), history, WorkCounter()
        ),
        quoted(history, 70.5, 71.0),
        WorkCounter(),
    )
    assert with_amounts.mark == without.mark and with_amounts.cash == without.cash
    assert with_amounts.lot_delta_total == without.lot_delta_total
    assert with_amounts.reserves is booked and with_amounts.reserves.marketing == 65.0


def test_a_marketing_reserve_is_a_finite_amount_of_zero_or_more_the_first_bad_row_named() -> None:
    def where(k: int) -> str:
        return f"marketing_reserve row {k + 1}"

    good = marketing_reserves(numbers(0.0, 0.5, 1e300), where)
    np.testing.assert_array_equal(good, [0.0, 0.5, 1e300])
    for bad, text in ((-5.0, "-5.0"), (np.inf, "inf"), (-np.inf, "-inf"), (np.nan, "nan")):
        with pytest.raises(ValueError) as refused:
            marketing_reserves(numbers(1.0, bad, -3.0), where)
        assert str(refused.value) == (
            f"marketing_reserve row 2 is {text}, expected a finite amount of zero or more"
        )


def test_finite_marketing_amounts_summing_past_the_largest_number_are_refused_for_the_batch() -> (
    None
):
    ix = a_fee_index()
    terms = marketed_terms(ix, (1e308, 1e308, 0.0, 0.0))
    with pytest.raises(ValueError) as refused:
        encoded(terms, observed_of(terms), UNITS, WorkCounter())
    assert str(refused.value) == (
        "the batch has inf of marketing reserve in all, expected a finite amount of USD; the rows' "
        "amounts, each finite, sum past the largest number"
    )
    # The terms take one amount per occurrence and one counterparty per occurrence, no more.
    with pytest.raises(
        ValueError, match=r"^marketing_reserve has 3 amounts, expected 4, one per occurrence$"
    ):
        marketed_terms(ix, (1.0, 2.0, 3.0))
    with pytest.raises(
        ValueError, match=r"^counterparty has 2 texts, expected 4, one per occurrence$"
    ):
        resolved_trades(
            FIXED_FLOAT, ix, spec(4), Route.BILATERAL, Settlement.PHYSICAL,
            *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, 4), ids(1001, 1002, 1003, 1004),
            None, None, dates(*["2026-09-24"] * 4), rows(0, 1, 2, 3), rows(1, 1, 1, 1),
            numbers(2.0, -2.0, 1.0, 0.0), *bounds_of(ix, rows(1, 1, 1, 1)), numbers(*([70.0] * 4)),
            None, counterparty=("ACME Trading", "Beta Energy"),
        )  # fmt: skip
