"""The market: two rules on the history and the price vector, one number found, and nothing
built; the daily price it implies is read through util_ReadHandle, tested with the utilities."""

import dataclasses

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.calendar.calendar import calendar
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.expiry_schedule import ExpirySchedule, expiry_schedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.daily_fixings import daily_fixings
from goosedove.market_data.monthly_fixings import monthly_fixings
from goosedove.market_data.price_vector import PriceVector, price_vector


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


def a_schedule(*contracts: tuple[str, str]) -> ExpirySchedule:
    codes = tuple(code for code, _ in contracts)
    return expiry_schedule(codes, dates(*(expiry for _, expiry in contracts)), None, None)


def a_vector(*prices: float) -> PriceVector:
    return price_vector(np.array(prices, dtype=np.float64))


# The page's sample: three contracts of one index, the valuation date 26 May 2026, the Monday
# before it a holiday, the fixings on the three past business days, and two quotes.
SCHEDULE = a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-07-21"))
CLOSED_MAY_25 = holiday_calendar(dates("2026-05-25"))
ELSEWHERE = holiday_calendar(dates("2026-01-01"))


def a_history(
    as_of: str = "2026-05-26",
    schedule: ExpirySchedule = SCHEDULE,
    holidays: HolidayCalendar = CLOSED_MAY_25,
    fraction: float = 0.5,
) -> MarketHistory:
    """The history of that calendar, with a fixing on every business day from ten days before
    the calendar's first day to the day before the valuation date."""
    made = calendar(valuation_date(day(as_of), fraction), "daily", schedule, holidays)
    first = made.dates[0] - np.timedelta64(10, "D")
    days = np.arange(first, day(as_of), dtype="datetime64[D]")
    days = days[np.is_busday(days, holidays=holidays.holiday)]
    fixings = daily_fixings(days, 70.0 + np.arange(days.size, dtype=np.float64), holidays.holiday)
    return market_history(made, fixings)


HISTORY = a_history()
QUOTES = a_vector(72.10, 72.80)


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
    assert history.calendar.prompt[history.calendar.dates == day(as_of)].tolist() == [
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
    assert not history.calendar.is_business_day[-1]
    made = market(history, a_vector(72.80))
    assert made.first_contract == 2
    with pytest.raises(ValueError) as failure:
        market(history, a_vector())
    assert str(failure.value) == (
        "price_vector has 0 prices, expected 1, one per contract from 'q26' through 'q26'"
    )


# A contract whose days are a weekend alone, b, valued on its Saturday: it is the first quoted,
# and c after it, two quotes for a calendar with no open day before the valuation date.
def test_a_contract_whose_days_are_all_closed_keeps_its_place_in_the_vector() -> None:
    schedule = a_schedule(("a", "2026-05-22"), ("b", "2026-05-24"), ("c", "2026-06-22"))
    history = a_history("2026-05-23", schedule=schedule, holidays=ELSEWHERE)
    made = market(history, a_vector(1.0, 2.0))
    assert made.first_contract == 1
    assert history.calendar.dates[0] == day("2026-05-23")
    assert not history.calendar.is_business_day[:2].any()
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
    with pytest.raises(ValueError) as failure:
        market(history, a_vector(1.0))
    assert str(failure.value) == (
        "price_vector has 1 price, expected 2, one per contract from 'x y' through 'Q'"
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
    past_prompts = history.calendar.prompt[history.calendar.is_past]
    assert (past_prompts - made.first_contract).min() < 0  # what the reader must not index


# --- what is rejected, in the order the rules run -----------------------------


@pytest.mark.parametrize(
    ("as_of", "quotes", "message"),
    [
        (
            "2026-05-19",
            (72.10, 72.80),
            "market_history valuation date is 2026-05-19, "
            "expected a date from 2026-05-20 through 2026-07-21",
        ),
        (
            "2026-07-22",
            (72.80,),
            "market_history valuation date is 2026-07-22, "
            "expected a date from 2026-05-20 through 2026-07-21",
        ),
        (
            "2025-01-01",
            (),
            "market_history valuation date is 2025-01-01, "
            "expected a date from 2026-05-20 through 2026-07-21",
        ),
        (
            "2026-05-26",
            (72.10,),
            "price_vector has 1 price, expected 2, one per contract from 'n26' through 'q26'",
        ),
        (
            "2026-05-26",
            (72.10, 72.80, 73.0),
            "price_vector has 3 prices, expected 2, one per contract from 'n26' through 'q26'",
        ),
        (
            "2026-06-23",
            (72.10, 72.80),
            "price_vector has 2 prices, expected 1, one per contract from 'q26' through 'q26'",
        ),
    ],
    ids=[
        "valued the day before the calendar, the boundary expiry",
        "valued the day after the calendar, with the one quote the last day would take",
        "valued long before, with no quote at all",
        "one quote too few",
        "one quote too many",
        "two quotes where the last contract alone remains",
    ],
)
def test_a_market_that_cannot_be_made_says_why(
    as_of: str, quotes: tuple[float, ...], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market(a_history(as_of), a_vector(*quotes))
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


def any_history(data: st.DataObject) -> MarketHistory:
    """A history of two to eight contracts up to 45 days apart, any holidays, valued on any day
    of its calendar, with a fixing on every past business day."""
    count = data.draw(st.integers(2, 8))
    gaps = data.draw(st.lists(st.integers(1, 45), min_size=count, max_size=count))
    offsets = np.cumsum(gaps, dtype=np.int64)
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    expiries = start + offsets.astype("timedelta64[D]")
    schedule = expiry_schedule(tuple(f"c{i}" for i in range(count)), expiries, None, None)
    listed = expiries[0] + np.array(
        data.draw(st.lists(st.integers(-20, 400), max_size=30)), dtype="timedelta64[D]"
    )
    holidays = holiday_calendar(listed)
    span = int(offsets[-1] - offsets[0])
    as_of = expiries[0] + np.timedelta64(data.draw(st.integers(1, span)), "D")
    made = calendar(
        valuation_date(as_of, data.draw(st.sampled_from((0.0, 0.5, 1.0)))),
        "daily",
        schedule,
        holidays,
    )
    days = np.arange(made.dates[0] - np.timedelta64(10, "D"), as_of, dtype="datetime64[D]")
    days = days[np.is_busday(days, holidays=listed)]
    fixings = daily_fixings(days, 60.0 + np.arange(days.size, dtype=np.float64), listed)
    return market_history(made, fixings)


@settings(deadline=None)
@given(data=st.data())
def test_every_live_business_day_has_its_prompts_quote_and_no_past_day_reads_one(
    data: st.DataObject,
) -> None:
    history = any_history(data)
    made = history.calendar
    as_of = made.valuation_date.as_of
    first = int(made.prompt[made.dates == as_of][0])
    quotes = a_vector(*(100.0 + i for i in range(len(made.expiry_schedule.codes) - first)))
    view = market(history, quotes)
    assert view.first_contract == first
    assert view.market_history is history and view.price_vector is quotes
    live = made.is_business_day & ~made.is_past
    places = made.prompt[live] - first
    assert places.size == 0 or (places.min() >= 0 and places.max() < quotes.prices.size)
    assert np.all(made.prompt[~made.is_past] >= first)
    assert set(np.flatnonzero(made.is_business_day & made.is_past).tolist()) == set(
        history.fixed_rows.tolist()
    )
    with pytest.raises(ValueError):
        market(history, a_vector(*(100.0 + i for i in range(quotes.prices.size + 1))))


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


# --- a monthly market ------------------------------------------------------------


# The page's example: the monthly history valued on 25 June with n26's fixing, and two quotes,
# q26's and u26's: q26 is prompt on the valuation day, so it is the first quoted, and every day
# of q26 and u26, the past 23rd and 24th included, is the market's to price from the vector.
def test_a_monthly_market_quotes_the_contracts_not_yet_expired() -> None:
    schedule = expiry_schedule(
        ("m26", "n26", "q26", "u26"),
        dates("2026-05-19", "2026-06-22", "2026-07-21", "2026-08-20"),
        None,
        dates("2026-05-20", "2026-06-23", "2026-07-22", "2026-08-21"),
    )
    published = schedule.publication_date
    assert published is not None
    made = calendar(
        valuation_date(day("2026-06-25"), 0.5),
        "monthly",
        schedule,
        holiday_calendar(dates("2026-06-24")),
    )
    history = market_history(
        made, monthly_fixings(dates("2026-06-23"), np.array([2.95]), published)
    )
    quotes = a_vector(3.10, 3.20)
    view = market(history, quotes)
    assert view.first_contract == 2
    assert view.market_history is history and view.price_vector is quotes
    live = made.prompt >= view.first_contract
    assert live.sum() == 93 - 34
    assert (made.prompt[live] - view.first_contract).min() == 0
    assert (made.prompt[live] - view.first_contract).max() == 1
    assert not np.isin(np.flatnonzero(live), history.fixed_rows).any()
    with pytest.raises(ValueError) as failure:
        market(history, a_vector(3.10))
    assert str(failure.value) == (
        "price_vector has 1 price, expected 2, one per contract from 'q26' through 'u26'"
    )
    on_expiry = calendar(
        valuation_date(day("2026-06-22"), 1.0),
        "monthly",
        schedule,
        holiday_calendar(dates("2026-06-24")),
    )
    still_live = market(
        market_history(on_expiry, monthly_fixings(dates("2026-05-20"), np.array([1.0]), published)),
        a_vector(2.95, 3.10, 3.20),
    )
    assert still_live.first_contract == 1
