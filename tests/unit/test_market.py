"""The market: three rules on the history and the price vector, one number found, and
nothing built; a vector that may stop before the schedule does, and the live prices read by
contract inside what it covers and refused outside it. The daily price the market implies is
read through util_ReadHandle, tested with the utilities."""

import dataclasses

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
from goosedove.index_definitions.gas_daily_schedule import GasDailySchedule, gas_daily_schedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule, iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.futures_fixings import futures_fixings
from goosedove.market_data.gas_daily_fixings import gas_daily_fixings
from goosedove.market_data.iferc_fixings import iferc_fixings
from goosedove.market_data.price_vector import PriceVector, price_vector


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


def a_schedule(*contracts: tuple[str, str]) -> FuturesSchedule:
    codes = tuple(code for code, _ in contracts)
    return futures_schedule(codes, dates(*(expiry for _, expiry in contracts)), None)


def a_vector(*prices: float, name: str = "sample") -> PriceVector:
    """A vector of those quotes named for the index every history here is over, sample,
    unless named otherwise."""
    return price_vector(name, np.array(prices, dtype=np.float64))


# The page's sample: three contracts of one index, the valuation date 26 May 2026, the Monday
# before it a holiday, the fixings on the three past business days, and two quotes.
SCHEDULE = a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-07-21"))
CLOSED_MAY_25 = holiday_calendar(dates("2026-05-25"))
ELSEWHERE = holiday_calendar(dates("2026-01-01"))

CONVENTIONS = index_conventions("USD", "BBL", "USD", "VOLUME", "BBL", UNITS)
SPECIFICATIONS = contract_specifications(
    ("NYMEX",), np.array([1000.0]), ("BBL",), np.array([0.0]), np.array([0.0]), UNITS
)


def an_index(
    schedule: object = SCHEDULE, holidays: HolidayCalendar | None = CLOSED_MAY_25
) -> Index:
    """The index of that schedule and holiday calendar, with one set of conventions and
    specifications throughout, since nothing here reads either."""
    return index("sample", schedule, CONVENTIONS, SPECIFICATIONS, holidays, UNITS)


def a_history(
    as_of: str = "2026-05-26",
    schedule: FuturesSchedule = SCHEDULE,
    holidays: HolidayCalendar = CLOSED_MAY_25,
    fraction: float = 0.5,
) -> MarketHistory:
    """The history of that calendar, with a fixing on every business day from ten days before
    the calendar's first day to the day before the valuation date, 70 on the oldest and one more
    each day, handed to the builder as the sheet gives a series: the newest day in the first
    row, each settle beside its own day."""
    made = calendar(valuation_date(day(as_of), fraction), an_index(schedule, holidays))
    first = made.dates[0] - np.timedelta64(10, "D")
    days = np.arange(first, day(as_of), dtype="datetime64[D]")
    days = days[np.is_busday(days, holidays=holidays.holiday)]
    settles = 70.0 + np.arange(days.size, dtype=np.float64)
    fixings = futures_fixings(days[::-1], settles[::-1], made.index)
    return market_history(made, fixings)


HISTORY = a_history()
QUOTES = a_vector(72.10, 72.80)

# The schedule pages' samples: three months of Gas Daily, September to November 2026, and three
# IFERC months, October to December, each published on its first business day.
GAS_DAILY_SCHEDULE = gas_daily_schedule(
    ("U26", "V26", "X26"),
    dates("2026-09-01", "2026-10-01", "2026-11-01"),
    dates("2026-09-30", "2026-10-31", "2026-11-30"),
)
IFERC_SCHEDULE = iferc_schedule(
    ("V26", "X26", "Z26"),
    dates("2026-09-30", "2026-10-30", "2026-11-30"),
    dates("2026-10-01", "2026-11-02", "2026-12-01"),
)


def a_gas_daily_history(
    as_of: str, schedule: GasDailySchedule = GAS_DAILY_SCHEDULE, fraction: float = 0.5
) -> MarketHistory:
    """The Gas Daily history of that calendar, with a print on every flow day from ten days
    before the calendar's first day, or from the valuation day when that is earlier, through
    the valuation day, 2.80 on the oldest and a cent more each day, handed to the builder newest
    first, each print beside its own flow day."""
    made = calendar(valuation_date(day(as_of), fraction), an_index(schedule, None))
    start = min(made.dates[0] - np.timedelta64(10, "D"), day(as_of))
    days = np.arange(start, day(as_of) + np.timedelta64(1, "D"), dtype="datetime64[D]")
    prices = 2.8 + np.arange(days.size, dtype=np.float64) / 100
    prints = gas_daily_fixings(days[::-1], prices[::-1], made.index)
    return market_history(made, prints)


def an_iferc_history(
    as_of: str, schedule: IfercSchedule = IFERC_SCHEDULE, fraction: float = 0.5
) -> MarketHistory:
    """The IFERC history of that calendar, with an index for every month published before the
    valuation day, 1.80 for the oldest and ten cents more each month, handed to the builder as
    the desk keeps its months, the newest in the first row, each index beside its own code."""
    made = calendar(valuation_date(day(as_of), fraction), an_index(schedule, None))
    codes = tuple(schedule.codes[int(row)] for row in np.flatnonzero(made.is_fixed))
    prices = 1.8 + np.arange(len(codes), dtype=np.float64) / 10
    indices = iferc_fixings(codes[::-1], prices[::-1], made.index)
    return market_history(made, indices)


# --- the sample and the mapping ------------------------------------------------


def test_the_sample_quotes_the_prompt_contract_and_the_one_after_it() -> None:
    made = market(HISTORY, QUOTES)
    assert made.market_history is HISTORY
    assert made.price_vector is QUOTES
    assert made.first_contract == 1
    assert SCHEDULE.codes[made.first_contract] == "n26"


@pytest.mark.parametrize(
    ("as_of", "first_contract", "quotes"),
    [
        ("2026-05-20", 1, 2),
        ("2026-05-23", 1, 2),
        ("2026-05-25", 1, 2),
        ("2026-06-22", 1, 2),
        ("2026-06-23", 2, 1),
        ("2026-07-21", 2, 1),
    ],
    ids=[
        "the calendar's first day",
        "a Saturday: nothing moves to the Monday",
        "the holiday: nothing moves to the Tuesday",
        "n26's expiry day: n26 is still quoted",
        "the day after: q26 first",
        "the calendar's last day: one quote",
    ],
)
def test_the_valuation_days_prompt_is_the_first_contract_quoted(
    as_of: str, first_contract: int, quotes: int
) -> None:
    history = a_history(as_of)
    made = market(history, a_vector(*(72.0 + i for i in range(quotes))))
    assert made.first_contract == first_contract
    assert history.calendar.contract[history.calendar.dates == day(as_of)].tolist() == [
        first_contract
    ]
    assert len(SCHEDULE.codes) - first_contract == quotes


def test_the_fraction_of_the_valuation_day_changes_nothing() -> None:
    for fraction in (0.0, 0.5, 1.0):
        made = market(a_history("2026-06-22", fraction=fraction), QUOTES)
        assert made.first_contract == 1


# Valued on the calendar's last day, a holiday: the last contract has no open day left, and its
# quote is required all the same.
def test_a_contract_prompt_on_closed_days_alone_still_takes_a_quote() -> None:
    closed = holiday_calendar(dates("2026-05-25", "2026-07-21"))
    history = a_history("2026-07-21", holidays=closed)
    assert not history.calendar.is_priced[-1]
    made = market(history, a_vector(72.80))
    assert made.first_contract == 2
    with pytest.raises(ValueError) as failure:
        market(history, a_vector())
    assert str(failure.value) == (
        "price_vector has 0 prices, expected at least 1, one per contract from 'q26' through 'q26'"
    )


# A contract whose days are a weekend alone, b, valued on its Saturday: it is the first quoted,
# and c after it, two quotes for a calendar with no open day before the valuation date.
def test_a_contract_whose_days_are_all_closed_keeps_its_place_in_the_vector() -> None:
    schedule = a_schedule(("a", "2026-05-22"), ("b", "2026-05-24"), ("c", "2026-06-22"))
    history = a_history("2026-05-23", schedule=schedule, holidays=ELSEWHERE)
    made = market(history, a_vector(1.0, 2.0))
    assert made.first_contract == 1
    assert history.calendar.dates[0] == day("2026-05-23")
    assert not history.calendar.is_priced[:2].any()
    sunday = market(
        a_history("2026-05-24", schedule=schedule, holidays=ELSEWHERE), a_vector(1.0, 2.0)
    )
    assert sunday.first_contract == 1


def test_codes_are_labels_and_the_mapping_follows_the_schedules_order() -> None:
    schedule = a_schedule(
        ("zz", "2026-05-19"), ("1", "2026-06-05"), ("x y", "2026-06-22"), ("Q", "2026-07-21")
    )
    history = a_history("2026-06-10", schedule=schedule)
    made = market(history, a_vector(1.0, 2.0))
    assert made.first_contract == 2
    assert schedule.codes[made.first_contract :] == ("x y", "Q")
    assert schedule.codes[market(history, a_vector(1.0)).last_contract] == "x y"
    with pytest.raises(ValueError) as failure:
        market(history, a_vector(1.0, 2.0, 3.0))
    assert str(failure.value) == (
        "price_vector has 3 prices, expected at most 2, one per contract from 'x y' through 'Q'"
    )


# Five contracts, valued after the fourth expiry: four past contracts, one quote.
def test_many_past_contracts_and_one_quote() -> None:
    schedule = a_schedule(
        ("a", "2026-05-19"),
        ("b", "2026-05-26"),
        ("c", "2026-06-02"),
        ("d", "2026-06-09"),
        ("e", "2026-06-22"),
    )
    history = a_history("2026-06-10", schedule=schedule)
    made = market(history, a_vector(72.80))
    assert made.first_contract == 4
    past_prompts = history.calendar.contract[history.calendar.is_fixed]
    assert (past_prompts - made.first_contract).min() < 0  # what the reader must not index


# --- what is rejected, in the order the rules run -----------------------------


@pytest.mark.parametrize(
    ("as_of", "quotes", "message"),
    [
        (
            "2026-07-22",
            (72.80,),
            "market_history has no unfixed period, expected at least one to quote",
        ),
        (
            "2026-08-01",
            (),
            "market_history has no unfixed period, expected at least one to quote",
        ),
        (
            "2026-05-26",
            (72.10, 72.80, 73.0),
            "price_vector has 3 prices, expected at most 2, "
            "one per contract from 'n26' through 'q26'",
        ),
        (
            "2026-05-26",
            (72.10, 72.80, 73.0, 73.5, 74.0),
            "price_vector has 5 prices, expected at most 2, "
            "one per contract from 'n26' through 'q26'",
        ),
        (
            "2026-06-23",
            (72.10, 72.80),
            "price_vector has 2 prices, expected at most 1, "
            "one per contract from 'q26' through 'q26'",
        ),
        (
            "2026-05-26",
            (),
            "price_vector has 0 prices, expected at least 1, "
            "one per contract from 'n26' through 'q26'",
        ),
        (
            "2025-01-01",
            (),
            "price_vector has 0 prices, expected at least 1, "
            "one per contract from 'n26' through 'q26'",
        ),
    ],
    ids=[
        "valued the day after the calendar, with the one quote the last day would take",
        "valued after the calendar, with no quote at all",
        "one quote past the schedule's last contract",
        "three past it",
        "two quotes where the last contract alone remains",
        "no quote at all: a history alone is not a market",
        "valued long before, with no quote at all",
    ],
)
def test_a_market_that_cannot_be_made_says_why(
    as_of: str, quotes: tuple[float, ...], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market(a_history(as_of), a_vector(*quotes))
    assert str(failure.value) == message


# The name is the first rule: a vector named for another index is refused before the unfixed
# period and the count are looked at, on each kind of calendar, with a count that fits and with
# one that does not; the name is compared as text, so another case, a space at either end or no
# name at all is another name, and the message quotes the name given and the name wanted.
@pytest.mark.parametrize(
    ("history", "quotes"),
    [
        (HISTORY, (72.10, 72.80)),
        (HISTORY, (72.10,)),
        (HISTORY, (72.10, 72.80, 73.0)),
        (HISTORY, ()),
        (a_history("2026-07-22"), (72.80,)),
        (a_gas_daily_history("2026-09-10"), (2.95, 3.10, 3.40)),
        (a_gas_daily_history("2026-11-30"), (3.40,)),
        (an_iferc_history("2026-11-15"), (2.20,)),
        (an_iferc_history("2026-12-02"), (2.20,)),
    ],
    ids=[
        "the futures sample with its two quotes",
        "the futures sample with the first quote alone",
        "the futures sample with one quote too many",
        "the futures sample with no quote at all",
        "the futures sample valued after its calendar",
        "the Gas Daily sample with its three quotes",
        "the Gas Daily sample on its last flow day",
        "the IFERC sample with its one quote",
        "the IFERC sample after its last month published",
    ],
)
@pytest.mark.parametrize(
    "name",
    ["Brent", "Sample", "sample ", " sample", ""],
    ids=["another index", "another case", "a space after", "a space before", "no name"],
)
def test_a_vector_named_for_another_index_is_refused_first(
    history: MarketHistory, quotes: tuple[float, ...], name: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market(history, a_vector(*quotes, name=name))
    assert str(failure.value) == (
        f"price_vector names index {name!r}, expected market_history's index 'sample'"
    )


# The name is a label, not a lookup: the three sample histories are over three indices that
# share the name sample, and a vector named sample serves each, given its count of quotes.
def test_two_indices_of_one_name_take_a_vector_of_that_name() -> None:
    daily = a_gas_daily_history("2026-09-10")
    monthly = an_iferc_history("2026-11-15")
    assert HISTORY.calendar.index is not daily.calendar.index
    assert daily.calendar.index is not monthly.calendar.index
    assert {h.calendar.index.name for h in (HISTORY, daily, monthly)} == {"sample"}
    made = (
        market(HISTORY, a_vector(72.10, 72.80)),
        market(daily, a_vector(2.95, 3.10, 3.40)),
        market(monthly, a_vector(2.20)),
    )
    assert [m.price_vector.index_name for m in made] == ["sample"] * 3
    assert [m.first_contract for m in made] == [1, 0, 2]


# A calendar fixed through its last period has nothing to quote, whatever its kind: the futures
# sample valued after 21 July, the Gas Daily sample valued on 30 November, its last flow day,
# or after it, and the IFERC sample valued after Z26 publishes on 1 December.
def test_a_history_with_no_unfixed_period_has_no_market() -> None:
    for history in (
        a_history("2026-07-22"),
        a_history("2026-08-01"),
        a_gas_daily_history("2026-11-30"),
        a_gas_daily_history("2026-12-15"),
        an_iferc_history("2026-12-02"),
        an_iferc_history("2027-01-01"),
    ):
        assert history.calendar.is_fixed.all()
        for quotes in ((), (72.80,), (1.0, 2.0, 3.0)):
            with pytest.raises(ValueError) as failure:
                market(history, a_vector(*quotes))
            assert str(failure.value) == (
                "market_history has no unfixed period, expected at least one to quote"
            )


# --- a futures calendar valued before its first day --------------------------


# Valued on Friday 15 May 2026, before m26 expires, on 19 May, its expiry day, or long before:
# the calendar's days still run from 20 May, nothing is fixed, and the first unfixed day's
# contract is n26, so one quote or two make a market from the calendar's first day on, the
# first quote n26's either way; the days before the 20th are not rows.
def test_a_futures_calendar_valued_before_its_first_day_is_a_market_from_that_day_on() -> None:
    for as_of in ("2026-05-15", "2026-05-19", "2025-01-01"):
        history = a_history(as_of)
        assert not history.calendar.is_fixed.any()
        assert history.calendar.dates[0] == day("2026-05-20")
        made = market(history, QUOTES)
        assert made.first_contract == 1
        assert SCHEDULE.codes[made.first_contract] == "n26"
        alone = market(history, a_vector(72.10))
        assert alone.first_contract == alone.last_contract == 1
        with pytest.raises(ValueError) as failure:
            market(history, a_vector(72.10, 72.80, 73.0))
        assert str(failure.value) == (
            "price_vector has 3 prices, expected at most 2, "
            "one per contract from 'n26' through 'q26'"
        )


# --- a Gas Daily market ---------------------------------------------------------


# The page's sample: valued on 25 September 2026 with the prints through the 25th, the first
# unfixed day is the 26th, so the first quote is the balance of September, and up to three are
# taken, one per month through November.
def test_the_gas_daily_sample_quotes_the_balance_of_the_month_first() -> None:
    history = a_gas_daily_history("2026-09-25")
    assert history.fixed_rows.size == 25
    made = market(history, a_vector(2.95, 3.10, 3.40))
    assert made.first_contract == 0
    assert made.market_history is history
    with pytest.raises(ValueError) as failure:
        market(history, a_vector(2.95, 3.10, 3.40, 3.50))
    assert str(failure.value) == (
        "price_vector has 4 prices, expected at most 3, one per contract from 'U26' through 'X26'"
    )


@pytest.mark.parametrize(
    ("as_of", "first_contract", "quotes"),
    [
        ("2026-08-20", 0, 3),
        ("2026-09-01", 0, 3),
        ("2026-09-29", 0, 3),
        ("2026-09-30", 1, 2),
        ("2026-10-31", 2, 1),
        ("2026-11-29", 2, 1),
    ],
    ids=[
        "before the first day: every month quoted, the first whole",
        "the first day: its print fixed, the balance of September first",
        "the day before the month ends: one day of balance",
        "the month's last day: no balance left, October first",
        "October's last day: November alone",
        "the day before the calendar ends: one quote for one day",
    ],
)
def test_the_first_unfixed_flow_days_month_is_the_first_contract_quoted(
    as_of: str, first_contract: int, quotes: int
) -> None:
    for fraction in (0.0, 0.5, 1.0):
        history = a_gas_daily_history(as_of, fraction=fraction)
        made = market(history, a_vector(*(3.0 + i for i in range(quotes))))
        assert made.first_contract == first_contract
        unfixed = history.calendar.contract[~history.calendar.is_fixed]
        assert int(unfixed[0]) == first_contract
        assert len(GAS_DAILY_SCHEDULE.codes) - first_contract == quotes


def test_a_gas_daily_calendar_of_one_month_takes_one_quote() -> None:
    september = gas_daily_schedule(("U26",), dates("2026-09-01"), dates("2026-09-30"))
    made = market(a_gas_daily_history("2026-09-10", september), a_vector(2.95))
    assert made.first_contract == 0
    whole = market(a_gas_daily_history("2026-08-01", september), a_vector(2.95))
    assert whole.first_contract == 0


# --- an IFERC market -----------------------------------------------------------


# The page's sample: valued on 15 November 2026, October and November published, December not:
# one quote, December's.
def test_the_iferc_sample_quotes_the_unpublished_month() -> None:
    history = an_iferc_history("2026-11-15")
    assert history.fixed_rows.tolist() == [0, 1]
    made = market(history, a_vector(2.20))
    assert made.first_contract == 2
    assert IFERC_SCHEDULE.codes[made.first_contract] == "Z26"
    with pytest.raises(ValueError) as failure:
        market(history, a_vector(2.10, 2.20))
    assert str(failure.value) == (
        "price_vector has 2 prices, expected at most 1, one per contract from 'Z26' through 'Z26'"
    )


# The desk keeps its months as it keeps its days, the newest in the first row, and an IFERC
# series is taken in either direction, each index found by its code: the same months either way
# up make the same history, and a market over each prices every period alike, the fixed months
# from the history and the unpublished one from the vector.
def test_iferc_months_given_newest_first_make_the_same_history_and_market_prices() -> None:
    made = calendar(valuation_date(day("2026-11-15"), 0.5), an_index(IFERC_SCHEDULE, None))
    newest_first = market_history(
        made, iferc_fixings(("X26", "V26"), np.array([2.10, 1.85]), made.index)
    )
    oldest_first = market_history(
        made, iferc_fixings(("V26", "X26"), np.array([1.85, 2.10]), made.index)
    )
    assert newest_first.fixed_rows.tolist() == oldest_first.fixed_rows.tolist() == [0, 1]
    assert newest_first.fixing_prices.tolist() == [1.85, 2.10]
    assert oldest_first.fixing_prices.tolist() == [1.85, 2.10]
    quotes = a_vector(2.20)
    december = np.array([2], dtype=np.intp)
    for history in (newest_first, oldest_first):
        view = market(history, quotes)
        assert view.first_contract == 2 and view.last_contract == 2
        assert view.market_history.fixing_prices.tolist() == [1.85, 2.10]
        assert view.live_prices(december).tolist() == [2.20]


@pytest.mark.parametrize(
    ("as_of", "first_contract", "quotes"),
    [
        ("2026-09-15", 0, 3),
        ("2026-10-01", 0, 3),
        ("2026-10-02", 1, 2),
        ("2026-11-02", 1, 2),
        ("2026-11-03", 2, 1),
        ("2026-12-01", 2, 1),
    ],
    ids=[
        "before the first month: every month quoted",
        "the first publication day: that month still quoted",
        "the day after: the next month first",
        "the second publication day: that month still quoted",
        "the day after it: the last month alone",
        "the last publication day: one quote",
    ],
)
def test_the_first_unpublished_month_is_the_first_contract_quoted(
    as_of: str, first_contract: int, quotes: int
) -> None:
    for fraction in (0.0, 0.5, 1.0):
        history = an_iferc_history(as_of, fraction=fraction)
        made = market(history, a_vector(*(2.0 + i for i in range(quotes))))
        assert made.first_contract == first_contract
        assert len(IFERC_SCHEDULE.codes) - first_contract == quotes


# --- the general rule ---------------------------------------------------------


def any_history(data: st.DataObject) -> MarketHistory:
    """A history of two to eight contracts up to 45 days apart, any holidays, valued on any day
    from ten days before its calendar to its last day, with a fixing on every past business
    day."""
    count = data.draw(st.integers(2, 8))
    gaps = data.draw(st.lists(st.integers(1, 45), min_size=count, max_size=count))
    offsets = np.cumsum(gaps, dtype=np.int64)
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    expiries = start + offsets.astype("timedelta64[D]")
    schedule = futures_schedule(tuple(f"c{i}" for i in range(count)), expiries, None)
    listed = expiries[0] + np.array(
        data.draw(st.lists(st.integers(-20, 400), max_size=30)), dtype="timedelta64[D]"
    )
    holidays = holiday_calendar(listed)
    span = int(offsets[-1] - offsets[0])
    as_of = expiries[0] + np.timedelta64(data.draw(st.integers(-10, span)), "D")
    made = calendar(
        valuation_date(as_of, data.draw(st.sampled_from((0.0, 0.5, 1.0)))),
        an_index(schedule, holidays),
    )
    days = np.arange(made.dates[0] - np.timedelta64(10, "D"), as_of, dtype="datetime64[D]")
    days = days[np.is_busday(days, holidays=listed)]
    settles = 60.0 + np.arange(days.size, dtype=np.float64)
    fixings = futures_fixings(days[::-1], settles[::-1], made.index)  # newest first, as given
    return market_history(made, fixings)


@settings(deadline=None)
@given(data=st.data())
def test_every_live_business_day_has_its_prompts_quote_and_no_past_day_reads_one(
    data: st.DataObject,
) -> None:
    history = any_history(data)
    made = history.calendar
    first = int(made.contract[int(np.count_nonzero(made.is_fixed))])
    quotes = a_vector(*(100.0 + i for i in range(len(made.index.schedule.codes) - first)))
    view = market(history, quotes)
    assert view.first_contract == first
    if made.valuation_date.as_of >= made.dates[0]:
        assert first == int(made.contract[made.dates == made.valuation_date.as_of][0])
    assert view.market_history is history and view.price_vector is quotes
    live = made.is_priced & ~made.is_fixed
    places = made.contract[live] - first
    assert places.size == 0 or (places.min() >= 0 and places.max() < quotes.prices.size)
    assert np.all(made.contract[~made.is_fixed] >= first)
    assert set(np.flatnonzero(made.is_priced & made.is_fixed).tolist()) == set(
        history.fixed_rows.tolist()
    )
    with pytest.raises(ValueError):
        market(history, a_vector(*(100.0 + i for i in range(quotes.prices.size + 1))))


def any_gas_daily_history(data: st.DataObject) -> MarketHistory:
    """A Gas Daily history of one to eight months of up to 40 days, valued on any day from ten
    days before its calendar to the day before its last, with a print on every flow day through
    the valuation day."""
    count = data.draw(st.integers(1, 8))
    lengths = np.array(
        data.draw(st.lists(st.integers(1, 40), min_size=count, max_size=count)), dtype=np.int64
    )
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    one_day = np.timedelta64(1, "D")
    lasts = start + np.cumsum(lengths).astype("timedelta64[D]") - one_day
    firsts = lasts - lengths.astype("timedelta64[D]") + one_day
    schedule = gas_daily_schedule(tuple(f"c{i}" for i in range(count)), firsts, lasts)
    as_of = start + np.timedelta64(data.draw(st.integers(-10, int(lengths.sum()) - 2)), "D")
    made = calendar(valuation_date(as_of, 0.5), an_index(schedule, None))
    days = np.arange(min(firsts[0], as_of) - one_day, as_of + one_day, dtype="datetime64[D]")
    prices = 1.0 + np.arange(days.size, dtype=np.float64)
    prints = gas_daily_fixings(days[::-1], prices[::-1], made.index)  # newest first, as given
    return market_history(made, prints)


def any_iferc_history(data: st.DataObject) -> MarketHistory:
    """An IFERC history of one to eight months publishing up to 60 days apart, valued on any day
    from ten days before the first publication day to the last one, with an index for every
    month published before it."""
    count = data.draw(st.integers(1, 8))
    gaps = np.array(
        data.draw(st.lists(st.integers(1, 60), min_size=count, max_size=count)), dtype=np.int64
    )
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    published = start + np.cumsum(gaps).astype("timedelta64[D]")
    codes = tuple(f"c{i}" for i in range(count))
    schedule = iferc_schedule(codes, published - np.timedelta64(1, "D"), published)
    as_of = published[0] + np.timedelta64(data.draw(st.integers(-10, int(gaps[1:].sum()))), "D")
    made = calendar(valuation_date(as_of, 0.5), an_index(schedule, None))
    fixed = np.flatnonzero(made.is_fixed)[::-1]  # the newest month first, as the desk keeps them
    indices = iferc_fixings(
        tuple(codes[int(i)] for i in fixed),
        100.0 + fixed.astype(np.float64),
        made.index,
    )
    return market_history(made, indices)


@settings(deadline=None)
@given(data=st.data())
def test_every_unfixed_period_of_the_other_two_kinds_has_its_contracts_quote(
    data: st.DataObject,
) -> None:
    history = data.draw(st.sampled_from((any_gas_daily_history, any_iferc_history)))(data)
    made = history.calendar
    assert not made.is_fixed.all()
    fixed = int(np.count_nonzero(made.is_fixed))
    assert made.is_fixed[:fixed].all() and not made.is_fixed[fixed:].any()
    first = int(made.contract[fixed])
    quotes = a_vector(*(100.0 + i for i in range(len(made.index.schedule.codes) - first)))
    view = market(history, quotes)
    assert view.first_contract == first
    assert view.market_history is history and view.price_vector is quotes
    places = made.contract[~made.is_fixed] - first
    assert places.min() == 0 and places.max() == quotes.prices.size - 1
    assert np.array_equal(np.flatnonzero(made.is_fixed), history.fixed_rows)
    with pytest.raises(ValueError):
        market(history, a_vector(*(100.0 + i for i in range(quotes.prices.size + 1))))
    with pytest.raises(ValueError):
        market(history, a_vector())


# --- a vector that stops before the schedule does -----------------------------

# Six futures contracts, the first bounding the calendar, so that the quotes can stop short of
# the last: valued on 26 May 2026 the first contract quoted is n26 and four remain.
LONG_SCHEDULE = a_schedule(
    ("k26", "2026-04-21"),
    ("m26", "2026-05-19"),
    ("n26", "2026-06-22"),
    ("q26", "2026-07-21"),
    ("u26", "2026-08-20"),
    ("v26", "2026-09-22"),
)


def rows_of(*contracts: int) -> NDArray[np.intp]:
    """Those rows of a schedule as a reader asks for them."""
    return np.array(contracts, dtype=np.intp)


# On each kind: one price, the first required contract's alone, is a market; so is every length
# up to one per remaining contract; the first contract is the calendar's whatever the length,
# and the coverage ends that many contracts on. One price more than the schedule has is refused.
@pytest.mark.parametrize(
    ("history", "first", "remaining"),
    [
        (a_history("2026-05-26", schedule=LONG_SCHEDULE), 2, 4),
        (a_gas_daily_history("2026-09-25"), 0, 3),
        (an_iferc_history("2026-09-15"), 0, 3),
    ],
    ids=["futures", "Gas Daily", "IFERC"],
)
def test_a_vector_may_stop_at_any_contract_from_the_first_required_through_the_last(
    history: MarketHistory, first: int, remaining: int
) -> None:
    codes = history.calendar.index.schedule.codes
    assert len(codes) - first == remaining
    for count in range(1, remaining + 1):
        vector = a_vector(*(50.0 + i for i in range(count)))
        made = market(history, vector)
        assert made.market_history is history and made.price_vector is vector
        assert made.first_contract == first
        assert made.last_contract == first + count - 1
        asked = rows_of(*range(first, first + count))
        assert made.live_prices(asked).tolist() == vector.prices.tolist()
    with pytest.raises(ValueError) as failure:
        market(history, a_vector(*(50.0 + i for i in range(remaining + 1))))
    assert str(failure.value) == (
        f"price_vector has {remaining + 1} prices, expected at most {remaining}, "
        f"one per contract from {codes[first]!r} through {codes[-1]!r}"
    )


MONTH_CODES = "FGHJKMNQUVXZ"


def a_monthly_iferc_history(first_year: int, last_year: int, as_of: str) -> MarketHistory:
    """An IFERC history of every month from January of the first year through December of the
    last, coded F23 to Z30 as the desk codes months, each published on its first day."""
    months: NDArray[np.datetime64] = np.arange(
        f"{first_year}-01", f"{last_year + 1}-01", dtype="datetime64[M]"
    ).astype("datetime64[D]")
    codes = tuple(
        f"{MONTH_CODES[i % 12]}{(first_year + i // 12) % 100}" for i in range(months.size)
    )
    schedule = iferc_schedule(codes, months - np.timedelta64(1, "D"), months)
    return an_iferc_history(as_of, schedule)


# The ticket's example: a schedule from F23 through Z30, the calendar's first required contract
# Z26, and prices for Z26 through Z28, twenty-five of them. The market is made, its coverage
# ends at Z28, and F29 is refused by name. The whole remaining schedule is forty-nine contracts,
# taken too, and a fiftieth price is past the schedule.
def test_a_schedule_through_z30_takes_prices_through_z28() -> None:
    history = a_monthly_iferc_history(2023, 2030, "2026-11-15")
    codes = history.calendar.index.schedule.codes
    assert (codes[0], codes[-1], len(codes)) == ("F23", "Z30", 96)
    made = market(history, a_vector(*(2.0 + i / 100 for i in range(25))))
    assert codes[made.first_contract] == "Z26" and codes[made.last_contract] == "Z28"
    assert made.live_prices(rows_of(codes.index("Z28"))).tolist() == [2.0 + 24 / 100]
    with pytest.raises(ValueError) as failure:
        made.live_prices(rows_of(codes.index("F29")))
    assert str(failure.value) == (
        "requested contract 'F29' is beyond live-price coverage ending at 'Z28'"
    )
    whole = market(history, a_vector(*(2.0 + i / 100 for i in range(49))))
    assert codes[whole.last_contract] == "Z30"
    with pytest.raises(ValueError) as failure:
        market(history, a_vector(*(2.0 + i / 100 for i in range(50))))
    assert str(failure.value) == (
        "price_vector has 50 prices, expected at most 49, one per contract from 'Z26' through 'Z30'"
    )
    ending_z28 = a_monthly_iferc_history(2023, 2028, "2026-11-15")
    with pytest.raises(ValueError) as failure:
        market(ending_z28, a_vector(*(2.0 + i / 100 for i in range(26))))
    assert str(failure.value) == (
        "price_vector has 26 prices, expected at most 25, one per contract from 'Z26' through 'Z28'"
    )


# --- live prices, by contract ---------------------------------------------------


# The reader hands back the quote of each contract asked for, in the order asked, a contract
# asked twice answered twice, and nothing asked answered with nothing; what it hands back is its
# own array, and the vector is left as it was.
def test_live_prices_are_the_quotes_of_the_contracts_asked_for() -> None:
    history = a_history("2026-05-26", schedule=LONG_SCHEDULE)
    vector = a_vector(72.10, 72.80)  # n26 and q26, of the four contracts that remain
    made = market(history, vector)
    assert made.live_prices(rows_of(2, 3, 2)).tolist() == [72.10, 72.80, 72.10]
    assert made.live_prices(rows_of(3)).tolist() == [72.80]
    assert made.live_prices(rows_of()).size == 0
    read = made.live_prices(rows_of(2, 3))
    assert read.dtype == np.float64 and not np.shares_memory(read, vector.prices)
    assert vector.prices.tolist() == [72.10, 72.80] and not vector.prices.flags.writeable
    calendar = history.calendar
    live = calendar.is_priced & ~calendar.is_fixed & (calendar.contract <= made.last_contract)
    assert set(made.live_prices(calendar.contract[live]).tolist()) == {72.10, 72.80}


# A contract outside the coverage is refused by name, on either side: past the last contract
# quoted, where NumPy would stop in its own words, and before the first, where NumPy would
# count back from the end of the vector and hand over another contract's quote with no failure
# at all. The first contract asked for that is outside is the one named, and nothing is read.
@pytest.mark.parametrize(
    ("asked", "message"),
    [
        ((4,), "requested contract 'u26' is beyond live-price coverage ending at 'q26'"),
        ((5,), "requested contract 'v26' is beyond live-price coverage ending at 'q26'"),
        ((1,), "requested contract 'm26' is before live-price coverage starting at 'n26'"),
        ((0,), "requested contract 'k26' is before live-price coverage starting at 'n26'"),
        ((2, 4, 1), "requested contract 'u26' is beyond live-price coverage ending at 'q26'"),
        ((1, 4), "requested contract 'm26' is before live-price coverage starting at 'n26'"),
        ((3, 2, 5, 4), "requested contract 'v26' is beyond live-price coverage ending at 'q26'"),
    ],
    ids=[
        "the contract after the last quoted",
        "the schedule's last contract",
        "the contract before the first quoted, which NumPy would read as the last price",
        "the schedule's first contract",
        "one beyond among contracts inside, then one before: the first outside is named",
        "one before, then one beyond: the first outside is named",
        "two beyond, the later contract asked first",
    ],
)
def test_a_contract_outside_the_live_price_coverage_is_refused_by_name(
    asked: tuple[int, ...], message: str
) -> None:
    made = market(a_history("2026-05-26", schedule=LONG_SCHEDULE), a_vector(72.10, 72.80))
    assert (made.first_contract, made.last_contract) == (2, 3)
    with pytest.raises(ValueError) as failure:
        made.live_prices(rows_of(*asked))
    assert str(failure.value) == message


# The same rule on the other two kinds, and on a vector that reaches the schedule's end, where
# nothing is beyond the coverage and a contract whose periods have all fixed is still before it.
def test_the_coverage_rule_is_the_same_on_every_kind_and_for_a_whole_vector() -> None:
    daily = market(a_gas_daily_history("2026-09-30"), a_vector(3.10))  # October alone
    assert daily.live_prices(rows_of(1)).tolist() == [3.10]
    with pytest.raises(ValueError) as failure:
        daily.live_prices(rows_of(2))
    assert str(failure.value) == (
        "requested contract 'X26' is beyond live-price coverage ending at 'V26'"
    )
    with pytest.raises(ValueError) as failure:
        daily.live_prices(rows_of(0))
    assert str(failure.value) == (
        "requested contract 'U26' is before live-price coverage starting at 'V26'"
    )
    monthly = market(an_iferc_history("2026-10-02"), a_vector(2.10))  # November alone
    assert monthly.live_prices(rows_of(1)).tolist() == [2.10]
    with pytest.raises(ValueError) as failure:
        monthly.live_prices(rows_of(2))
    assert str(failure.value) == (
        "requested contract 'Z26' is beyond live-price coverage ending at 'X26'"
    )
    with pytest.raises(ValueError) as failure:
        monthly.live_prices(rows_of(0))
    assert str(failure.value) == (
        "requested contract 'V26' is before live-price coverage starting at 'X26'"
    )
    whole = market(HISTORY, QUOTES)
    assert whole.last_contract == len(SCHEDULE.codes) - 1
    assert whole.live_prices(rows_of(1, 2)).tolist() == [72.10, 72.80]
    with pytest.raises(ValueError) as failure:
        whole.live_prices(rows_of(0))
    assert str(failure.value) == (
        "requested contract 'm26' is before live-price coverage starting at 'n26'"
    )


# The last contract covered may have no open day left: b expires on the Friday and c on the
# Sunday, so c is prompt on a weekend alone; or c's two days are both holidays. Valued on the
# Wednesday with two quotes, b's and c's, c keeps its place in the vector, the coverage ends
# with it, its quote is there to be read, and d after it is refused.
@pytest.mark.parametrize(
    ("contracts", "closed"),
    [
        (
            (("a", "2026-05-19"), ("b", "2026-05-22"), ("c", "2026-05-24"), ("d", "2026-06-22")),
            ELSEWHERE,
        ),
        (
            (("a", "2026-05-19"), ("b", "2026-05-26"), ("c", "2026-05-28"), ("d", "2026-06-22")),
            holiday_calendar(dates("2026-05-27", "2026-05-28")),
        ),
    ],
    ids=["a weekend alone", "two holidays alone"],
)
def test_a_last_covered_contract_with_no_open_day_keeps_its_place(
    contracts: tuple[tuple[str, str], ...], closed: HolidayCalendar
) -> None:
    history = a_history("2026-05-20", schedule=a_schedule(*contracts), holidays=closed)
    calendar = history.calendar
    days_of_c = calendar.contract == 2
    assert int(days_of_c.sum()) == 2 and not calendar.is_priced[days_of_c].any()
    made = market(history, a_vector(1.0, 2.0))
    assert (made.first_contract, made.last_contract) == (1, 2)
    assert made.live_prices(rows_of(2)).tolist() == [2.0]
    with pytest.raises(ValueError) as failure:
        made.live_prices(rows_of(3))
    assert str(failure.value) == (
        "requested contract 'd' is beyond live-price coverage ending at 'c'"
    )
    assert market(history, a_vector(1.0)).last_contract == 1


# --- a roll ---------------------------------------------------------------------


# Valued on n26's expiry day the first contract quoted is n26; the day after, it is q26. A
# vector the sheet moved on with the calendar keeps its first price on the first contract, and
# its coverage ends one contract later than before.
def test_after_a_roll_a_vector_moved_on_starts_at_the_new_first_contract() -> None:
    codes = LONG_SCHEDULE.codes
    held = market(a_history("2026-06-22", schedule=LONG_SCHEDULE), a_vector(70.0, 71.0))
    assert [codes[held.first_contract], codes[held.last_contract]] == ["n26", "q26"]
    moved = market(a_history("2026-06-23", schedule=LONG_SCHEDULE), a_vector(71.0, 72.0))
    assert [codes[moved.first_contract], codes[moved.last_contract]] == ["q26", "u26"]
    assert moved.live_prices(rows_of(3, 4)).tolist() == [71.0, 72.0]
    with pytest.raises(ValueError) as failure:
        moved.live_prices(rows_of(2))
    assert str(failure.value) == (
        "requested contract 'n26' is before live-price coverage starting at 'q26'"
    )


# The limitation the page records: the vector carries prices and no contract, so one left as it
# was when the first contract rolled is taken, and each price is read one contract later than
# the desk meant it. A vector that reached the schedule's end is one price too many after the
# roll, which is the one case the count still catches.
def test_a_vector_left_unchanged_through_a_roll_is_read_one_contract_later() -> None:
    before = a_history("2026-06-22", schedule=LONG_SCHEDULE)
    after = a_history("2026-06-23", schedule=LONG_SCHEDULE)
    unchanged = a_vector(70.0, 71.0)
    assert market(before, unchanged).live_prices(rows_of(2, 3)).tolist() == [70.0, 71.0]
    stale = market(after, unchanged)
    assert stale.live_prices(rows_of(3, 4)).tolist() == [70.0, 71.0]
    whole = a_vector(70.0, 71.0, 72.0, 73.0)
    assert market(before, whole).last_contract == 5
    with pytest.raises(ValueError) as failure:
        market(after, whole)
    assert str(failure.value) == (
        "price_vector has 4 prices, expected at most 3, one per contract from 'q26' through 'v26'"
    )


# For any history of any kind and any number of quotes from one to one per remaining contract:
# the market is made, its first contract is the calendar's whatever the count, its coverage
# ends that many contracts on, every unfixed period of a covered contract reads its contract's
# quote, and the first unfixed period past the coverage, where there is one, is refused.
@settings(deadline=None)
@given(data=st.data())
def test_any_count_of_quotes_from_one_to_the_remaining_contracts_is_a_market(
    data: st.DataObject,
) -> None:
    history = data.draw(st.sampled_from((any_history, any_gas_daily_history, any_iferc_history)))(
        data
    )
    made = history.calendar
    first = int(made.contract[made.first_unfixed])
    remaining = len(made.index.schedule.codes) - first
    count = data.draw(st.integers(1, remaining))
    quotes = a_vector(*(100.0 + i for i in range(count)))
    view = market(history, quotes)
    assert view.first_contract == first and view.last_contract == first + count - 1
    unfixed = made.contract[made.first_unfixed :]
    inside = unfixed[unfixed <= view.last_contract]
    assert np.array_equal(view.live_prices(inside), quotes.prices[inside - first])
    beyond = unfixed[unfixed > view.last_contract]
    assert beyond.size or count == remaining  # only a whole vector leaves nothing beyond it
    if beyond.size:
        with pytest.raises(ValueError, match="is beyond live-price coverage ending at"):
            view.live_prices(beyond[:1])
    with pytest.raises(ValueError, match="expected at most"):
        market(history, a_vector(*(100.0 + i for i in range(remaining + 1))))


# --- ownership ----------------------------------------------------------------


def test_the_market_keeps_both_objects_themselves_and_makes_no_array() -> None:
    made = market(HISTORY, QUOTES)
    assert made.market_history is HISTORY
    assert made.price_vector is QUOTES
    assert made.market_history.calendar is HISTORY.calendar
    assert made.price_vector.prices is QUOTES.prices
    assert Market.__slots__ == ("market_history", "price_vector", "first_contract")
    field = "first_contract"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(made, field, 0)


def test_making_a_market_changes_neither_input_and_two_markets_share_the_history() -> None:
    rows_before, prices_before = HISTORY.fixed_rows.copy(), HISTORY.fixing_prices.copy()
    quotes_before = QUOTES.prices.copy()
    first = market(HISTORY, QUOTES)
    other = a_vector(1.0, 2.0)
    second = market(HISTORY, other)
    again = market(HISTORY, QUOTES)
    assert np.array_equal(HISTORY.fixed_rows, rows_before)
    assert np.array_equal(HISTORY.fixing_prices, prices_before)
    assert np.array_equal(QUOTES.prices, quotes_before)
    assert first.market_history is second.market_history is HISTORY
    assert first.price_vector is QUOTES and second.price_vector is other
    assert again is not first and again.first_contract == first.first_contract == 1
