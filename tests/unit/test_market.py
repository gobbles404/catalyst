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


def a_vector(*prices: float) -> PriceVector:
    return price_vector(np.array(prices, dtype=np.float64))


# The page's sample: three contracts of one index, the valuation date 26 May 2026, the Monday
# before it a holiday, the fixings on the three past business days, and two quotes.
SCHEDULE = a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-07-21"))
CLOSED_MAY_25 = holiday_calendar(dates("2026-05-25"))
ELSEWHERE = holiday_calendar(dates("2026-01-01"))

CONVENTIONS = index_conventions("USD", "BBL", "USD", "volume", "BBL")
SPECIFICATIONS = contract_specifications(
    ("NYMEX",), np.array([1000.0]), np.array([0.0]), np.array([0.0])
)


def an_index(
    schedule: object = SCHEDULE, holidays: HolidayCalendar | None = CLOSED_MAY_25
) -> Index:
    """The index of that schedule and holiday calendar, with one set of conventions and
    specifications throughout, since nothing here reads either."""
    return index("sample", schedule, CONVENTIONS, SPECIFICATIONS, holidays)


def a_history(
    as_of: str = "2026-05-26",
    schedule: FuturesSchedule = SCHEDULE,
    holidays: HolidayCalendar = CLOSED_MAY_25,
    fraction: float = 0.5,
) -> MarketHistory:
    """The history of that calendar, with a fixing on every business day from ten days before
    the calendar's first day to the day before the valuation date."""
    made = calendar(valuation_date(day(as_of), fraction), an_index(schedule, holidays))
    first = made.dates[0] - np.timedelta64(10, "D")
    days = np.arange(first, day(as_of), dtype="datetime64[D]")
    days = days[np.is_busday(days, holidays=holidays.holiday)]
    fixings = futures_fixings(
        days, 70.0 + np.arange(days.size, dtype=np.float64), an_index(schedule, holidays)
    )
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
    the valuation day."""
    made = calendar(valuation_date(day(as_of), fraction), an_index(schedule, None))
    start = min(made.dates[0] - np.timedelta64(10, "D"), day(as_of))
    days = np.arange(start, day(as_of) + np.timedelta64(1, "D"), dtype="datetime64[D]")
    prints = gas_daily_fixings(days, 2.8 + np.arange(days.size, dtype=np.float64) / 100)
    return market_history(made, prints)


def an_iferc_history(
    as_of: str, schedule: IfercSchedule = IFERC_SCHEDULE, fraction: float = 0.5
) -> MarketHistory:
    """The IFERC history of that calendar, with an index for every month published before the
    valuation day."""
    made = calendar(valuation_date(day(as_of), fraction), an_index(schedule, None))
    codes = tuple(schedule.codes[int(row)] for row in np.flatnonzero(made.is_fixed))
    indices = iferc_fixings(codes, 1.8 + np.arange(len(codes), dtype=np.float64) / 10)
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
        (
            "2025-01-01",
            (),
            "price_vector has 0 prices, expected 2, one per contract from 'n26' through 'q26'",
        ),
    ],
    ids=[
        "valued the day after the calendar, with the one quote the last day would take",
        "valued after the calendar, with no quote at all",
        "one quote too few",
        "one quote too many",
        "two quotes where the last contract alone remains",
        "valued long before, with no quote at all: two required",
    ],
)
def test_a_market_that_cannot_be_made_says_why(
    as_of: str, quotes: tuple[float, ...], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market(a_history(as_of), a_vector(*quotes))
    assert str(failure.value) == message


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
# contract is n26, so two quotes make a market from the calendar's first day on; the days before
# the 20th are not rows.
def test_a_futures_calendar_valued_before_its_first_day_is_a_market_from_that_day_on() -> None:
    for as_of in ("2026-05-15", "2026-05-19", "2025-01-01"):
        history = a_history(as_of)
        assert not history.calendar.is_fixed.any()
        assert history.calendar.dates[0] == day("2026-05-20")
        made = market(history, QUOTES)
        assert made.first_contract == 1
        assert SCHEDULE.codes[made.first_contract] == "n26"
        with pytest.raises(ValueError) as failure:
            market(history, a_vector(72.80))
        assert str(failure.value) == (
            "price_vector has 1 price, expected 2, one per contract from 'n26' through 'q26'"
        )


# --- a Gas Daily market ---------------------------------------------------------


# The page's sample: valued on 25 September 2026 with the prints through the 25th, the first
# unfixed day is the 26th, so the first quote is the balance of September and three are required.
def test_the_gas_daily_sample_quotes_the_balance_of_the_month_first() -> None:
    history = a_gas_daily_history("2026-09-25")
    assert history.fixed_rows.size == 25
    made = market(history, a_vector(2.95, 3.10, 3.40))
    assert made.first_contract == 0
    assert made.market_history is history
    for quotes in ((2.95, 3.10), (2.95, 3.10, 3.40, 3.50)):
        with pytest.raises(ValueError) as failure:
            market(history, a_vector(*quotes))
        assert str(failure.value) == (
            f"price_vector has {len(quotes)} prices, expected 3, "
            "one per contract from 'U26' through 'X26'"
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
        "price_vector has 2 prices, expected 1, one per contract from 'Z26' through 'Z26'"
    )


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
    fixings = futures_fixings(
        days, 60.0 + np.arange(days.size, dtype=np.float64), an_index(schedule, holidays)
    )
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
    prints = gas_daily_fixings(days, 1.0 + np.arange(days.size, dtype=np.float64))
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
    fixed = np.flatnonzero(made.is_fixed)
    indices = iferc_fixings(
        tuple(codes[int(i)] for i in fixed), 100.0 + np.arange(fixed.size, dtype=np.float64)
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
        market(history, a_vector(*(100.0 + i for i in range(quotes.prices.size - 1))))


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
