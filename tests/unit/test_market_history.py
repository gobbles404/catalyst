"""The market history: the fixings over the calendar's index, that kind's rules on the fixings
against the calendar, and the two columns made once from two objects, the calendar kept as it
is."""

import numpy as np
import pytest
from holiday_fixtures import closed_on, index_on
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from catalyst.calendar.calendar import Calendar, calendar
from catalyst.globals.unit_conversions import UNITS
from catalyst.globals.valuation_date import valuation_date
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import FuturesSchedule, futures_schedule
from catalyst.index_definitions.gas_daily_schedule import gas_daily_schedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.index_definitions.published_schedule import published_schedule
from catalyst.market.market_history import MarketHistory, market_history
from catalyst.market_data.futures_fixings import FuturesFixings, futures_fixings
from catalyst.market_data.gas_daily_fixings import GasDailyFixings, gas_daily_fixings
from catalyst.market_data.published_fixings import PublishedFixings, published_fixings


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


def a_schedule(*contracts: tuple[str, str]) -> FuturesSchedule:
    codes = tuple(code for code, _ in contracts)
    return futures_schedule(codes, dates(*(expiry for _, expiry in contracts)), None)


# The page's sample: three contracts of one index, the valuation date 26 May 2026 at midday, a
# Tuesday, and the Monday before it a holiday, so the calendar's past business days are
# Wednesday 20 to Friday 22 May, and the settle fixed on each.
SCHEDULE = a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-07-21"))
MAY_26 = valuation_date(day("2026-05-26"), 0.5)
CLOSED_MAY_25 = closed_on(dates("2026-05-25"))
# A calendar of one day, New Year's Day, outside every calendar built here.
ELSEWHERE = closed_on(dates("2026-01-01"))

CONVENTIONS = index_conventions("DOLLAR", "BBL", "DOLLAR", "VOLUME", "BBL", UNITS)
SPECIFICATIONS = contract_specifications(
    ("NYMEX",), np.array([1000.0]), ("BBL",), np.array([0.0]), np.array([0.0]), UNITS
)


def an_index(
    schedule: object = SCHEDULE,
    holidays: HolidayCalendar | None = CLOSED_MAY_25,
    name: str = "WTI NYMEX",
) -> Index:
    """The index of that schedule and holiday calendar, with one set of conventions and
    specifications throughout, since nothing here reads either. Each call is a new index, as
    every call of the library's builder is; a calendar and the fixings it binds must share one."""
    return index_on(
        name, f"{name} index", schedule, CONVENTIONS, SPECIFICATIONS, holidays, None, UNITS
    )


INDEX = an_index()
CALENDAR = calendar(MAY_26, INDEX)


def fixings_on(*days: str, prices: tuple[float, ...] = (), over: Index = INDEX) -> FuturesFixings:
    """Fixings on those days, named here oldest first, the order a history reads them in, each
    with the settle at its own place, 70 on the first named and one more each day unless given.
    They are handed to the builder as the sheet gives a series: the newest day in the first
    row, the two columns turned over together."""
    settles = np.array(prices or tuple(70.0 + i for i in range(len(days))), dtype=np.float64)
    return futures_fixings(dates(*days)[::-1], settles[::-1, None], over)


FIXINGS = fixings_on("2026-05-20", "2026-05-21", "2026-05-22", prices=(70.85, 71.10, 71.25))


def a_history(made: Calendar = CALENDAR, fixings: FuturesFixings = FIXINGS) -> MarketHistory:
    return market_history(made, fixings)


def priced(made: MarketHistory) -> dict[str, float]:
    """The days that carry a price, each with its price, as the history aligns them."""
    days = made.calendar.dates[made.fixed_rows]
    return {str(d): float(p) for d, p in zip(days, made.fixing_prices[:, 0], strict=True)}


def business_days(first: str, last: str, holidays: HolidayCalendar) -> NDArray[np.datetime64]:
    """Every business day from the first day to the last under that calendar's list."""
    days = np.arange(day(first), day(last) + np.timedelta64(1, "D"), dtype="datetime64[D]")
    return days[np.is_busday(days, holidays=holidays.holiday)]


def whole_fixings(first: str, last: str, over: Index = INDEX) -> FuturesFixings:
    """A fixing on every business day of the index's market from the first day to the last,
    60 on the first and one more each day, handed to the builder newest first."""
    assert over.holiday_calendar is not None
    days = business_days(first, last, over.holiday_calendar)
    settles = 60.0 + np.arange(days.size, dtype=np.float64)
    return futures_fixings(days[::-1], settles[::-1, None], over)


# --- the sample ---------------------------------------------------------------


def test_the_sample_prices_the_three_past_business_days_and_no_other_day() -> None:
    made = a_history()
    assert made.calendar is CALENDAR
    assert made.fixed_rows.tolist() == [0, 1, 2]
    assert made.fixing_prices[:, 0].tolist() == [70.85, 71.10, 71.25]
    assert made.fixed_rows.dtype == np.dtype(np.intp)
    assert made.fixing_prices.dtype == np.dtype(np.float64)
    assert priced(made) == {"2026-05-20": 70.85, "2026-05-21": 71.10, "2026-05-22": 71.25}


# The calendar decides the days: every row it had it keeps, in its order, with its prompts and
# flags, and the days without a price are the weekend, the holiday, the valuation day and the
# days after it.
def test_the_rows_the_page_shows() -> None:
    made = a_history()
    codes: list[str] = [SCHEDULE.codes[int(row)] for row in made.calendar.contract]
    prices = priced(made)
    shown: dict[str, tuple[str, bool, bool, float | str]] = {
        str(date): (code, bool(open_), bool(past), prices.get(str(date), "-"))
        for date, code, open_, past in zip(
            made.calendar.dates,
            codes,
            made.calendar.is_priced,
            made.calendar.is_fixed,
            strict=True,
        )
    }
    assert len(shown) == 63
    assert shown["2026-05-20"] == ("n26", True, True, 70.85)
    assert shown["2026-05-22"] == ("n26", True, True, 71.25)
    assert shown["2026-05-23"] == ("n26", False, True, "-")
    assert shown["2026-05-24"] == ("n26", False, True, "-")
    assert shown["2026-05-25"] == ("n26", False, True, "-")
    assert shown["2026-05-26"] == ("n26", True, False, "-")
    assert shown["2026-05-27"] == ("n26", True, False, "-")
    assert shown["2026-06-23"] == ("q26", True, False, "-")
    assert shown["2026-07-21"] == ("q26", True, False, "-")


def test_a_single_required_fixing_is_a_history() -> None:
    short = an_index(a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-20")))
    one_day = calendar(valuation_date(day("2026-05-21"), 0.5), short)
    made = market_history(one_day, fixings_on("2026-05-20", prices=(71.0,), over=short))
    assert made.fixed_rows.tolist() == [0]
    assert made.fixing_prices[:, 0].tolist() == [71.0]
    longer = market_history(
        one_day, fixings_on("2026-05-18", "2026-05-19", "2026-05-20", over=short)
    )
    assert priced(longer) == {"2026-05-20": 72.0}


def test_a_settle_of_zero_or_below_is_a_price() -> None:
    made = a_history(
        fixings=fixings_on("2026-05-20", "2026-05-21", "2026-05-22", prices=(0.0, -37.63, 71.25))
    )
    assert made.fixed_rows.tolist() == [0, 1, 2]
    assert made.fixing_prices[:, 0].tolist() == [0.0, -37.63, 71.25]


# --- the fixings may reach beyond the calendar, and the ends need not meet -----------------


def test_fixings_before_the_calendars_first_day_are_allowed_and_unused() -> None:
    made = a_history(fixings=whole_fixings("2026-05-11", "2026-05-22"))
    assert made.fixed_rows.tolist() == [0, 1, 2]
    assert priced(made) == {"2026-05-20": 67.0, "2026-05-21": 68.0, "2026-05-22": 69.0}
    assert made.calendar.dates.size == 63
    assert made.calendar.dates[0] == day("2026-05-20")


# A calendar entirely in the past, valued on 1 August 2026: every business day from 20 May to
# 21 July needs a fixing, and the fixings running on to the end of July are allowed and unused.
def test_fixings_after_the_calendars_last_day_are_allowed_and_unused() -> None:
    past = calendar(valuation_date(day("2026-08-01"), 0.0), INDEX)
    fixings = whole_fixings("2026-05-20", "2026-07-31")
    made = market_history(past, fixings)
    assert made.calendar is past
    assert past.is_fixed.all()
    assert made.fixed_rows.tolist() == np.flatnonzero(past.is_priced).tolist()
    assert made.fixed_rows.size == 44
    assert str(past.dates[made.fixed_rows][-1]) == "2026-07-21"
    where = np.searchsorted(fixings.dates, past.dates[made.fixed_rows])
    assert np.array_equal(made.fixing_prices, fixings.settles[where])
    assert priced(made)["2026-07-21"] == float(fixings.settles[where][-1, 0])


# --- what is rejected, in the order the rules run -----------------------------


# A two-contract index whose calendar ends on 22 May, for a fixing on the valuation date to fall
# outside the calendar's days.
SHORT = an_index(a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-22")))


@pytest.mark.parametrize(
    ("made", "fixings", "message"),
    [
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26"),
            "fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            CALENDAR,
            whole_fixings("2026-05-20", "2026-05-29"),
            "fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            calendar(MAY_26, SHORT),
            fixings_on(
                "2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26", "2026-05-27", over=SHORT
            ),
            "fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21", "2026-05-22"),
            "fixings has no fixing for 2026-05-20, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21"),
            "fixings has no fixing for 2026-05-22, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21"),
            "fixings has no fixing for 2026-05-20, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            calendar(valuation_date(day("2026-08-01"), 0.0), INDEX),
            FIXINGS,
            "fixings has no fixing for 2026-05-26, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-11", "2026-05-12", "2026-05-13"),
            "fixings has no fixing for 2026-05-20, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21", "2026-05-22", "2026-05-26"),
            "fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
    ],
    ids=[
        "a fixing on the valuation date",
        "fixings running past the valuation date, the earliest named",
        "a fixing on the valuation date outside the calendar's days",
        "the first fixed day without a fixing",
        "the last fixed day without a fixing",
        "both ends without a fixing, the earliest named",
        "a calendar entirely past with fixings for its first days alone",
        "fixings entirely before the calendar",
        "the valuation date is checked before the missing days",
    ],
)
def test_a_history_that_cannot_be_made_says_why(
    made: Calendar, fixings: FuturesFixings, message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market_history(made, fixings)
    assert str(failure.value) == message


def test_the_fraction_of_the_valuation_day_admits_no_fixing_on_it() -> None:
    late = fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26")
    for fraction in (0.0, 0.5, 1.0):
        made = calendar(valuation_date(day("2026-05-26"), fraction), INDEX)
        with pytest.raises(ValueError) as failure:
            market_history(made, late)
        assert str(failure.value).startswith("fixings date 2026-05-26 is on or after")
        assert priced(market_history(made, FIXINGS)) == priced(a_history())


# --- calendars with nothing to price ------------------------------------------


# Valued on 1 May 2026, before any of its days: no day is past, so no fixing is required, and
# the fixings, the last week of April, are before the valuation date, outside the calendar and
# unused.
def test_a_calendar_entirely_to_come_is_a_history_without_a_price() -> None:
    future = calendar(valuation_date(day("2026-05-01"), 0.5), INDEX)
    made = market_history(future, whole_fixings("2026-04-27", "2026-04-30"))
    assert made.calendar is future
    assert made.fixed_rows.size == 0
    assert made.fixing_prices.size == 0
    assert made.fixed_rows.dtype == np.dtype(np.intp)
    assert made.fixing_prices.dtype == np.dtype(np.float64)
    assert future.dates.size == 63


# Saturday 23 May to Monday 25 May, the holiday, valued on the 26th: three past days and none
# a business day, so nothing is required; the fixings, on the days before, are unused.
def test_a_calendar_whose_past_days_are_all_closed_is_a_history_without_a_price() -> None:
    weekend = an_index(a_schedule(("m26", "2026-05-22"), ("n26", "2026-05-25")))
    closed = calendar(MAY_26, weekend)
    assert closed.is_fixed.all() and not closed.is_priced.any()
    made = market_history(
        closed, fixings_on("2026-05-20", "2026-05-21", "2026-05-22", over=weekend)
    )
    assert made.fixed_rows.size == 0 and made.fixing_prices.size == 0
    assert closed.dates.tolist() == [day("2026-05-23"), day("2026-05-24"), day("2026-05-25")]


# --- the general rule ---------------------------------------------------------


def any_calendar(data: st.DataObject) -> Calendar:
    """A calendar of two to eight contracts up to 45 days apart from any year, any holidays
    around it, and a valuation date from ten days before its first day to ten after its last."""
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
    span = int(offsets[-1] - offsets[0])
    as_of = expiries[0] + np.timedelta64(data.draw(st.integers(-10, span + 10)), "D")
    fraction = data.draw(st.sampled_from((0.0, 0.5, 1.0)))
    return calendar(valuation_date(as_of, fraction), an_index(schedule, closed_on(listed)))


@settings(deadline=None)
@given(data=st.data())
def test_every_past_business_day_takes_its_own_fixing_and_no_other_day_takes_one(
    data: st.DataObject,
) -> None:
    made = any_calendar(data)
    assert made.index.holiday_calendar is not None
    as_of = made.valuation_date.as_of
    # Fixings on every business day, under the calendar's own list, from before the calendar's
    # first day to the day before the valuation date: whole over every past business day.
    span = made.dates.size + 20 + data.draw(st.integers(0, 10))
    days = np.arange(as_of - np.timedelta64(span, "D"), as_of, dtype="datetime64[D]")
    days = days[np.is_busday(days, holidays=made.index.holiday_calendar.holiday)]
    settles = data.draw(st.floats(-100, 100)) + np.arange(days.size, dtype=np.float64)
    fixings = futures_fixings(days[::-1], settles[::-1, None], made.index)  # newest first, as given
    history = market_history(made, fixings)
    required = np.flatnonzero(made.is_fixed & made.is_priced)
    assert history.calendar is made
    assert history.fixed_rows.tolist() == required.tolist()
    where = np.searchsorted(fixings.dates, made.dates[required])
    assert np.array_equal(fixings.dates[where], made.dates[required])
    assert np.array_equal(history.fixing_prices, fixings.settles[where])
    assert history.fixing_prices.size == required.size


# Fixings over the calendar's index are checked against the holiday calendar the calendar
# closes on, so none can fall on a day it closes: the closed-day rule of #84 has nothing to
# catch and is gone.
@settings(deadline=None)
@given(data=st.data())
def test_no_fixing_over_the_calendars_index_falls_on_a_day_it_closes(
    data: st.DataObject,
) -> None:
    made = any_calendar(data)
    assert made.index.holiday_calendar is not None
    ten = np.timedelta64(10, "D")
    days = np.arange(made.dates[0] - ten, made.dates[-1] + ten, dtype="datetime64[D]")
    days = days[np.is_busday(days, holidays=made.index.holiday_calendar.holiday)]
    fixings = futures_fixings(days[::-1], np.zeros((days.size, 1)), made.index)
    inside = (fixings.dates >= made.dates[0]) & (fixings.dates <= made.dates[-1])
    rows = (fixings.dates[inside] - made.dates[0]).astype(np.intp)
    assert made.is_priced[rows].all()


# --- ownership ----------------------------------------------------------------


def test_the_history_keeps_the_calendar_itself_and_its_columns_read_only() -> None:
    made = a_history()
    assert made.calendar is CALENDAR
    assert made.calendar.dates is CALENDAR.dates
    assert made.calendar.is_priced is CALENDAR.is_priced
    assert not made.fixed_rows.flags.writeable
    assert not made.fixing_prices.flags.writeable
    with pytest.raises(ValueError):
        made.fixing_prices[0] = 0.0
    with pytest.raises(ValueError):
        made.fixed_rows[0] = 5
    assert not np.shares_memory(made.fixing_prices, FIXINGS.settles)


def test_making_a_history_changes_neither_input_and_a_second_history_shares_the_calendar() -> None:
    columns_before = tuple(
        column.copy()
        for column in (CALENDAR.dates, CALENDAR.contract, CALENDAR.is_priced, CALENDAR.is_fixed)
    )
    dates_before, settles_before = FIXINGS.dates.copy(), FIXINGS.settles.copy()
    first = a_history()
    second = a_history(
        fixings=fixings_on("2026-05-20", "2026-05-21", "2026-05-22", prices=(1.0, 2.0, 3.0))
    )
    for column, before in zip(
        (CALENDAR.dates, CALENDAR.contract, CALENDAR.is_priced, CALENDAR.is_fixed),
        columns_before,
        strict=True,
    ):
        assert np.array_equal(column, before)
    assert np.array_equal(FIXINGS.dates, dates_before)
    assert np.array_equal(FIXINGS.settles, settles_before)
    assert first.calendar is second.calendar is CALENDAR
    assert first.fixing_prices[:, 0].tolist() == [70.85, 71.10, 71.25]
    assert second.fixing_prices[:, 0].tolist() == [1.0, 2.0, 3.0]
    assert first.fixing_prices is not second.fixing_prices
    assert np.array_equal(first.fixed_rows, second.fixed_rows)


# --- a Gas Daily calendar and its prints -------------------------------------------------


# The Gas Daily schedule page's three months, as one index.
GAS_DAILY_INDEX = an_index(
    gas_daily_schedule(
        ("U26", "V26", "X26"),
        dates("2026-09-01", "2026-10-01", "2026-11-01"),
        dates("2026-09-30", "2026-10-31", "2026-11-30"),
    ),
    None,
    "Henry Hub Gas Daily",
)


def a_gas_daily_calendar(as_of: str = "2026-09-25", fraction: float = 0.5) -> Calendar:
    """The Gas Daily index's calendar, valued on the given day."""
    return calendar(valuation_date(day(as_of), fraction), GAS_DAILY_INDEX)


def prints_on(first: str, last: str, over: Index = GAS_DAILY_INDEX) -> GasDailyFixings:
    """A print on every flow day from the first to the last, 2.80 on the first rising by a
    cent a day, handed to the builder newest first, each print beside its own flow day."""
    days = np.arange(day(first), day(last) + np.timedelta64(1, "D"), dtype="datetime64[D]")
    prices = 2.80 + np.arange(days.size, dtype=np.float64) / 100
    return gas_daily_fixings(days[::-1], prices[::-1], over)


GAS_DAILY = a_gas_daily_calendar()


def test_the_gas_daily_sample_prices_every_flow_day_through_the_valuation_day() -> None:
    made = market_history(GAS_DAILY, prints_on("2026-09-01", "2026-09-25"))
    assert made.calendar is GAS_DAILY
    assert made.fixed_rows.tolist() == list(range(25))
    assert priced(made)["2026-09-01"] == 2.80
    assert priced(made)["2026-09-25"] == pytest.approx(3.04)
    assert "2026-09-26" not in priced(made)
    assert made.fixing_prices.size == 25


def test_gas_daily_prints_beyond_the_calendar_are_allowed_and_unused() -> None:
    made = market_history(GAS_DAILY, prints_on("2026-08-20", "2026-09-25"))
    assert made.fixed_rows.tolist() == list(range(25))
    assert priced(made)["2026-09-01"] == pytest.approx(2.80 + 12 / 100)
    later = market_history(
        a_gas_daily_calendar("2027-01-15"), prints_on("2026-08-20", "2026-12-15")
    )
    assert later.fixed_rows.tolist() == list(range(91))
    assert priced(later)["2026-11-30"] == pytest.approx(2.80 + 102 / 100)


def test_the_fraction_of_the_valuation_day_admits_the_flow_day_itself() -> None:
    for fraction in (0.0, 0.5, 1.0):
        made = market_history(
            a_gas_daily_calendar("2026-09-25", fraction), prints_on("2026-09-01", "2026-09-25")
        )
        assert made.fixed_rows.size == 25


def test_a_gas_daily_calendar_entirely_to_come_is_a_history_without_a_price() -> None:
    made = market_history(a_gas_daily_calendar("2026-08-15"), prints_on("2026-08-01", "2026-08-15"))
    assert made.fixed_rows.size == 0 and made.fixing_prices.size == 0


@pytest.mark.parametrize(
    ("as_of", "first", "last", "message"),
    [
        (
            "2026-09-25",
            "2026-09-01",
            "2026-09-26",
            "fixings flow_date 2026-09-26 is after valuation date 2026-09-25, "
            "expected flow days on or before the valuation date",
        ),
        (
            "2026-09-25",
            "2026-09-01",
            "2026-12-15",
            "fixings flow_date 2026-09-26 is after valuation date 2026-09-25, "
            "expected flow days on or before the valuation date",
        ),
        (
            "2026-08-15",
            "2026-08-01",
            "2026-08-20",
            "fixings flow_date 2026-08-16 is after valuation date 2026-08-15, "
            "expected flow days on or before the valuation date",
        ),
        (
            "2026-09-25",
            "2026-09-02",
            "2026-09-25",
            "fixings has no fixing for 2026-09-01, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            "2026-09-25",
            "2026-09-01",
            "2026-09-24",
            "fixings has no fixing for 2026-09-25, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            "2026-09-25",
            "2026-08-01",
            "2026-08-31",
            "fixings has no fixing for 2026-09-01, "
            "expected a fixing for every fixed day in calendar",
        ),
    ],
    ids=[
        "a print for the day after the valuation day",
        "prints running past the valuation day, the earliest named",
        "prints past the valuation day, outside the calendar",
        "the first fixed day without a print",
        "the valuation day without a print",
        "prints entirely before the calendar",
    ],
)
def test_a_gas_daily_history_that_cannot_be_made_says_why(
    as_of: str, first: str, last: str, message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market_history(a_gas_daily_calendar(as_of), prints_on(first, last))
    assert str(failure.value) == message


# --- a published calendar and its prints' prices -------------------------------------------


# The published fixings page's sample: six weekly prints of three months, valued on Wednesday
# 16 September 2026, when the prints dated 31 August and 7 and 14 September have fixed.
PUBLISHED_PRINTS = dates(
    "2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"
)
PUBLISHED_INDEX = an_index(
    published_schedule(("Q26", "U26", "U26", "U26", "U26", "V26"), PUBLISHED_PRINTS),
    None,
    "DOE Diesel",
)


def a_published_calendar(as_of: str = "2026-09-16", fraction: float = 0.5) -> Calendar:
    return calendar(valuation_date(day(as_of), fraction), PUBLISHED_INDEX)


def priced_on(*pairs: tuple[str, float], over: Index = PUBLISHED_INDEX) -> PublishedFixings:
    """Published fixings from date and price pairs as the desk keeps them, the newest first."""
    dated = dates(*(date for date, _ in pairs))
    return published_fixings(dated, np.array([price for _, price in pairs]), over)


PUBLISHED = a_published_calendar()
THREE_PRICES = (("2026-09-14", 3.20), ("2026-09-07", 3.00), ("2026-08-31", 2.95))


def test_the_published_sample_prices_the_fixed_prints_and_no_other() -> None:
    fixings = priced_on(*THREE_PRICES)
    made = market_history(PUBLISHED, fixings)
    assert made.calendar is PUBLISHED
    assert made.fixed_rows.tolist() == [0, 1, 2]
    assert made.fixing_prices.shape == (3, 1)
    assert made.fixing_prices[:, 0].tolist() == [2.95, 3.00, 3.20]
    # The fixings' own two arrays, read-only already: the history copies neither.
    assert made.fixed_rows is fixings.rows
    assert np.shares_memory(made.fixing_prices, fixings.prices)
    assert not made.fixing_prices.flags.writeable


def test_a_published_calendar_of_one_print_and_one_with_nothing_fixed() -> None:
    one = an_index(published_schedule(("U26",), dates("2026-09-07")), None, "DOE Diesel")
    made = market_history(
        calendar(valuation_date(day("2026-09-16"), 0.5), one),
        priced_on(("2026-09-07", 3.0), over=one),
    )
    assert made.fixed_rows.tolist() == [0] and made.fixing_prices[:, 0].tolist() == [3.0]
    nothing = market_history(a_published_calendar("2026-08-15"), priced_on())
    assert nothing.fixed_rows.size == 0 and nothing.fixing_prices.size == 0


# A print is fixed from the day after its date: Monday's price is refused on the Monday, at any
# fraction of the day, and required from the Tuesday.
def test_a_price_for_the_print_dated_the_valuation_day_is_refused_and_required_the_day_after() -> (
    None
):
    for fraction in (0.0, 0.5, 1.0):
        with pytest.raises(ValueError) as failure:
            market_history(a_published_calendar("2026-09-14", fraction), priced_on(*THREE_PRICES))
        assert str(failure.value) == (
            "fixings publication_date 2026-09-14 is a print not yet fixed in calendar, "
            "expected a price for fixed prints alone; a print is fixed from the day after its date"
        )
    with pytest.raises(ValueError) as missing:
        market_history(a_published_calendar("2026-09-15"), priced_on(*THREE_PRICES[1:]))
    assert str(missing.value) == (
        "fixings has no price for the print dated 2026-09-14, expected a price for every fixed "
        "print in calendar, a stand-in where its publisher has not released it"
    )
    # The stand-in: a price the desk enters for the fixed print its publisher has not released.
    stood_in = market_history(
        a_published_calendar("2026-09-15"), priced_on(("2026-09-14", 3.50), *THREE_PRICES[1:])
    )
    assert stood_in.fixing_prices[:, 0].tolist() == [2.95, 3.00, 3.50]


@pytest.mark.parametrize(
    ("pairs", "message"),
    [
        (
            (("2026-09-21", 3.5), *THREE_PRICES),
            "fixings publication_date 2026-09-21 is a print not yet fixed in calendar, "
            "expected a price for fixed prints alone; a print is fixed from the day after its date",
        ),
        (
            (("2026-10-05", 3.7), ("2026-09-21", 3.5), *THREE_PRICES),
            "fixings publication_date 2026-09-21 is a print not yet fixed in calendar, "
            "expected a price for fixed prints alone; a print is fixed from the day after its date",
        ),
        (
            THREE_PRICES[1:],
            "fixings has no price for the print dated 2026-09-14, expected a price for every "
            "fixed print in calendar, a stand-in where its publisher has not released it",
        ),
        (
            (THREE_PRICES[0], THREE_PRICES[2]),
            "fixings has no price for the print dated 2026-09-07, expected a price for every "
            "fixed print in calendar, a stand-in where its publisher has not released it",
        ),
        (
            THREE_PRICES[:2],
            "fixings has no price for the print dated 2026-08-31, expected a price for every "
            "fixed print in calendar, a stand-in where its publisher has not released it",
        ),
        (
            (),
            "fixings has no price for the print dated 2026-08-31, expected a price for every "
            "fixed print in calendar, a stand-in where its publisher has not released it",
        ),
        (
            (("2026-09-21", 3.5), THREE_PRICES[0]),
            "fixings publication_date 2026-09-21 is a print not yet fixed in calendar, "
            "expected a price for fixed prints alone; a print is fixed from the day after its date",
        ),
    ],
    ids=[
        "a price for a print not yet fixed",
        "two of them: the earliest is named",
        "the newest fixed print without a price",
        "a fixed print between two priced ones without a price",
        "the oldest fixed print without a price",
        "no price at all",
        "the unfixed prints are checked before the missing ones",
    ],
)
def test_a_published_history_that_cannot_be_made_says_why(
    pairs: tuple[tuple[str, float], ...], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market_history(PUBLISHED, priced_on(*pairs))
    assert str(failure.value) == message


# --- the direction the fixings were given in ----------------------------------------------


# The series as the sheet gives it, the newest day in the first row and no two settles alike:
# the history prices each past business day with the settle given beside that day.
def test_fixings_given_newest_first_price_each_day_with_its_own_settle() -> None:
    fixings = futures_fixings(
        dates("2026-05-22", "2026-05-21", "2026-05-20"),
        np.array([[71.25], [71.10], [70.85]]),
        INDEX,
    )
    made = market_history(CALENDAR, fixings)
    assert priced(made) == {"2026-05-20": 70.85, "2026-05-21": 71.10, "2026-05-22": 71.25}
    assert made.fixed_rows.tolist() == [0, 1, 2]
    assert made.fixing_prices[:, 0].tolist() == [70.85, 71.10, 71.25]


def test_prints_given_newest_first_price_each_flow_day_with_its_own_print() -> None:
    prints = gas_daily_fixings(
        dates("2026-09-03", "2026-09-02", "2026-09-01"),
        np.array([2.93, 2.87, 2.81]),
        GAS_DAILY_INDEX,
    )
    made = market_history(a_gas_daily_calendar("2026-09-03"), prints)
    assert priced(made) == {"2026-09-01": 2.81, "2026-09-02": 2.87, "2026-09-03": 2.93}
    assert made.fixed_rows.tolist() == [0, 1, 2]


# Two fixings on or after the valuation date, given newest first: the 27th is the sheet's first
# row and the 26th its second, and the message names the 26th, the earliest, and no row. The
# history reads what the fixings keep, oldest first, and not the sheet.
def test_a_late_fixing_is_named_by_the_earliest_date_whichever_row_it_was_given_on() -> None:
    late = futures_fixings(
        dates("2026-05-27", "2026-05-26", "2026-05-22", "2026-05-21", "2026-05-20"),
        np.array([[5.0], [4.0], [3.0], [2.0], [1.0]]),
        INDEX,
    )
    with pytest.raises(ValueError) as failure:
        market_history(CALENDAR, late)
    assert str(failure.value) == (
        "fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
        "expected dates before the valuation date"
    )
    late_prints = gas_daily_fixings(
        dates("2026-09-28", "2026-09-27", "2026-09-26", "2026-09-25"),
        np.array([4.0, 3.0, 2.0, 1.0]),
        GAS_DAILY_INDEX,
    )
    with pytest.raises(ValueError) as failure:
        market_history(GAS_DAILY, late_prints)
    assert str(failure.value) == (
        "fixings flow_date 2026-09-26 is after valuation date 2026-09-25, "
        "expected flow days on or before the valuation date"
    )


# --- the fixings are over the calendar's index -------------------------------------------


def test_fixings_over_another_index_are_refused_naming_both() -> None:
    gas_daily = prints_on("2026-09-01", "2026-09-25")
    published = priced_on(*THREE_PRICES)
    same_name = an_index(SCHEDULE, CLOSED_MAY_25)
    other_name = an_index(SCHEDULE, CLOSED_MAY_25, "Brent ICE")
    for made, fixings, arrived, expected in (
        (CALENDAR, gas_daily, "Henry Hub Gas Daily", "WTI NYMEX"),
        (CALENDAR, published, "DOE Diesel", "WTI NYMEX"),
        (GAS_DAILY, FIXINGS, "WTI NYMEX", "Henry Hub Gas Daily"),
        (GAS_DAILY, published, "DOE Diesel", "Henry Hub Gas Daily"),
        (PUBLISHED, FIXINGS, "WTI NYMEX", "DOE Diesel"),
        (PUBLISHED, gas_daily, "Henry Hub Gas Daily", "DOE Diesel"),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", over=other_name),
            "Brent ICE",
            "WTI NYMEX",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", over=same_name),
            "WTI NYMEX",
            "WTI NYMEX",
        ),
    ):
        with pytest.raises(ValueError) as failure:
            market_history(made, fixings)
        assert str(failure.value) == (
            f"fixings is over another index, {arrived!r}, expected the calendar's, {expected!r}"
        )


def test_the_index_is_checked_before_the_fixings_dates() -> None:
    other = an_index(SCHEDULE, CLOSED_MAY_25)
    late = fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26", over=other)
    with pytest.raises(ValueError) as failure:
        market_history(CALENDAR, late)
    assert str(failure.value).startswith("fixings is over another index")


def test_a_calendar_and_fixings_over_one_index_are_accepted_whatever_its_name() -> None:
    for name in ("WTI NYMEX", "Brent ICE", "anything at all"):
        one = an_index(SCHEDULE, CLOSED_MAY_25, name)
        made = market_history(
            calendar(MAY_26, one),
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", over=one),
        )
        assert made.fixed_rows.tolist() == [0, 1, 2]


# The index made twice from unchanged inputs, as the builder does on every call and a worksheet
# does once the first was released: the old calendar with fixings over the new index is refused,
# the name shown twice; with both remade over the new index, the history is the same as before.
def test_an_index_remade_from_the_same_inputs_is_another_index_until_both_are_remade() -> None:
    remade = an_index(SCHEDULE, CLOSED_MAY_25)
    fixings = fixings_on(
        "2026-05-20", "2026-05-21", "2026-05-22", prices=(70.85, 71.10, 71.25), over=remade
    )
    with pytest.raises(ValueError) as failure:
        market_history(CALENDAR, fixings)
    assert str(failure.value) == (
        "fixings is over another index, 'WTI NYMEX', expected the calendar's, 'WTI NYMEX'"
    )
    made = market_history(calendar(MAY_26, remade), fixings)
    assert priced(made) == priced(a_history())
    assert made.calendar.index is remade


def test_an_object_that_is_not_fixings_is_refused_naming_what_it_is() -> None:
    for wrong, what in (
        (CLOSED_MAY_25, "a holiday calendar"),
        (CALENDAR, "a calendar"),
        (SCHEDULE, "a futures schedule"),
    ):
        with pytest.raises(ValueError) as failure:
            market_history(CALENDAR, wrong)
        assert str(failure.value) == (
            f"fixings is {what}, expected futures, Gas Daily or published fixings"
        )


# --- the general rules of the two other kinds --------------------------------------------


@settings(deadline=None)
@given(data=st.data())
def test_every_fixed_flow_day_takes_its_own_print_and_no_other_day_takes_one(
    data: st.DataObject,
) -> None:
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
    as_of = start + np.timedelta64(data.draw(st.integers(-10, int(lengths.sum()) + 10)), "D")
    made = calendar(valuation_date(as_of, 0.5), an_index(schedule, None))
    before = data.draw(st.integers(0, 10))
    days = np.arange(
        firsts[0] - np.timedelta64(before, "D"), as_of + one_day, dtype="datetime64[D]"
    )
    prices = 1.0 + np.arange(days.size, dtype=np.float64)
    prints = gas_daily_fixings(days[::-1], prices[::-1], made.index)  # newest first, as given
    history = market_history(made, prints)
    required = np.flatnonzero(made.is_fixed)
    assert history.fixed_rows.tolist() == required.tolist()
    assert np.array_equal(
        history.fixing_prices[:, 0], prints.prices[np.isin(days, made.dates[required])]
    )
    assert history.calendar is made


@settings(deadline=None)
@given(data=st.data())
def test_every_fixed_month_of_one_print_takes_its_own_price_in_the_calendars_order(
    data: st.DataObject,
) -> None:
    count = data.draw(st.integers(1, 8))
    gaps = np.array(
        data.draw(st.lists(st.integers(1, 60), min_size=count, max_size=count)), dtype=np.int64
    )
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    published = start + np.cumsum(gaps).astype("timedelta64[D]")
    codes = tuple(f"c{i}" for i in range(count))
    schedule = published_schedule(codes, published)
    as_of = start + np.timedelta64(data.draw(st.integers(-10, int(gaps.sum()) + 10)), "D")
    made = calendar(valuation_date(as_of, 0.5), an_index(schedule, None))
    fixed = np.flatnonzero(made.is_fixed).tolist()
    newest_first = fixed[::-1]  # as the desk keeps them, the one order the creator takes
    fixings = published_fixings(
        published[newest_first],
        np.array([100.0 + i for i in newest_first], dtype=np.float64),
        made.index,
    )
    history = market_history(made, fixings)
    assert history.fixed_rows.tolist() == fixed
    assert history.fixing_prices[:, 0].tolist() == [100.0 + i for i in fixed]
    assert not history.fixed_rows.flags.writeable and not history.fixing_prices.flags.writeable
