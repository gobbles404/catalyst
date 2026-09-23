"""The market history: three rules on the fixings against the calendar, and the two columns made
once from two objects, the calendar kept as it is."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar, calendar
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.expiry_schedule import ExpirySchedule, expiry_schedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.daily_fixings import DailyFixings, daily_fixings


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


def a_schedule(*contracts: tuple[str, str]) -> ExpirySchedule:
    codes = tuple(code for code, _ in contracts)
    return expiry_schedule(codes, dates(*(expiry for _, expiry in contracts)), None, None)


# The page's sample: three contracts of one index, the valuation date 26 May 2026 at midday, a
# Tuesday, and the Monday before it a holiday, so the calendar's past business days are
# Wednesday 20 to Friday 22 May, and the settle fixed on each.
SCHEDULE = a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-07-21"))
MAY_26 = valuation_date(day("2026-05-26"), 0.5)
CLOSED_MAY_25 = holiday_calendar(dates("2026-05-25"))
# A calendar of one day, New Year's Day, outside every calendar built here.
ELSEWHERE = holiday_calendar(dates("2026-01-01"))
CALENDAR = calendar(MAY_26, SCHEDULE, CLOSED_MAY_25)


def fixings_on(
    *days: str, prices: tuple[float, ...] = (), holidays: HolidayCalendar = CLOSED_MAY_25
) -> DailyFixings:
    settles = np.array(prices or tuple(70.0 + i for i in range(len(days))), dtype=np.float64)
    return daily_fixings(dates(*days), settles, holidays.holiday)


FIXINGS = fixings_on("2026-05-20", "2026-05-21", "2026-05-22", prices=(70.85, 71.10, 71.25))


def a_history(made: Calendar = CALENDAR, fixings: DailyFixings = FIXINGS) -> MarketHistory:
    return market_history(made, fixings)


def priced(made: MarketHistory) -> dict[str, float]:
    """The days that carry a price, each with its price, as the history aligns them."""
    days = made.calendar.dates[made.fixed_rows]
    return {str(d): float(p) for d, p in zip(days, made.fixing_prices, strict=True)}


def business_days(first: str, last: str, holidays: HolidayCalendar) -> NDArray[np.datetime64]:
    """Every business day from the first day to the last under that calendar's list."""
    days = np.arange(day(first), day(last) + np.timedelta64(1, "D"), dtype="datetime64[D]")
    return days[np.is_busday(days, holidays=holidays.holiday)]


def whole_fixings(first: str, last: str, holidays: HolidayCalendar = CLOSED_MAY_25) -> DailyFixings:
    """A fixing on every business day from the first day to the last, priced by position."""
    days = business_days(first, last, holidays)
    return daily_fixings(days, 60.0 + np.arange(days.size, dtype=np.float64), holidays.holiday)


# --- the sample ---------------------------------------------------------------


def test_the_sample_prices_the_three_past_business_days_and_no_other_day() -> None:
    made = a_history()
    assert made.calendar is CALENDAR
    assert made.fixed_rows.tolist() == [0, 1, 2]
    assert made.fixing_prices.tolist() == [70.85, 71.10, 71.25]
    assert made.fixed_rows.dtype == np.dtype(np.intp)
    assert made.fixing_prices.dtype == np.dtype(np.float64)
    assert priced(made) == {"2026-05-20": 70.85, "2026-05-21": 71.10, "2026-05-22": 71.25}


# The calendar decides the days: every row it had it keeps, in its order, with its prompts and
# flags, and the days without a price are the weekend, the holiday, the valuation day and the
# days after it.
def test_the_rows_the_page_shows() -> None:
    made = a_history()
    codes: list[str] = [SCHEDULE.codes[int(row)] for row in made.calendar.prompt]
    prices = priced(made)
    shown: dict[str, tuple[str, bool, bool, float | str]] = {
        str(date): (code, bool(open_), bool(past), prices.get(str(date), "-"))
        for date, code, open_, past in zip(
            made.calendar.dates,
            codes,
            made.calendar.is_business_day,
            made.calendar.is_past,
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
    one_day = calendar(
        valuation_date(day("2026-05-21"), 0.5),
        a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-20")),
        CLOSED_MAY_25,
    )
    made = market_history(one_day, fixings_on("2026-05-20", prices=(71.0,)))
    assert made.fixed_rows.tolist() == [0]
    assert made.fixing_prices.tolist() == [71.0]
    longer = market_history(one_day, fixings_on("2026-05-18", "2026-05-19", "2026-05-20"))
    assert priced(longer) == {"2026-05-20": 72.0}


def test_a_settle_of_zero_or_below_is_a_price() -> None:
    made = a_history(
        fixings=fixings_on("2026-05-20", "2026-05-21", "2026-05-22", prices=(0.0, -37.63, 71.25))
    )
    assert made.fixed_rows.tolist() == [0, 1, 2]
    assert made.fixing_prices.tolist() == [0.0, -37.63, 71.25]


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
    past = calendar(valuation_date(day("2026-08-01"), 0.0), SCHEDULE, CLOSED_MAY_25)
    fixings = whole_fixings("2026-05-20", "2026-07-31")
    made = market_history(past, fixings)
    assert made.calendar is past
    assert past.is_past.all()
    assert made.fixed_rows.tolist() == np.flatnonzero(past.is_business_day).tolist()
    assert made.fixed_rows.size == 44
    assert str(past.dates[made.fixed_rows][-1]) == "2026-07-21"
    where = np.searchsorted(fixings.dates, past.dates[made.fixed_rows])
    assert np.array_equal(made.fixing_prices, fixings.settles[where])
    assert priced(made)["2026-07-21"] == float(fixings.settles[where][-1])


# --- what is rejected, in the order the rules run -----------------------------


@pytest.mark.parametrize(
    ("made", "fixings", "message"),
    [
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26"),
            "daily_fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            CALENDAR,
            whole_fixings("2026-05-20", "2026-05-29"),
            "daily_fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            calendar(
                MAY_26, a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-22")), CLOSED_MAY_25
            ),
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26", "2026-05-27"),
            "daily_fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-25", holidays=ELSEWHERE),
            "daily_fixings date 2026-05-25 is a non-business day in calendar, expected no fixing",
        ),
        (
            calendar(MAY_26, SCHEDULE, holiday_calendar(dates("2026-05-21", "2026-05-22"))),
            FIXINGS,
            "daily_fixings date 2026-05-21 is a non-business day in calendar, expected no fixing",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21", "2026-05-22"),
            "daily_fixings has no fixing for 2026-05-20, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21"),
            "daily_fixings has no fixing for 2026-05-22, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-22", holidays=holiday_calendar(dates("2026-05-21"))),
            "daily_fixings has no fixing for 2026-05-21, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21"),
            "daily_fixings has no fixing for 2026-05-20, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            calendar(MAY_26, SCHEDULE, ELSEWHERE),
            FIXINGS,
            "daily_fixings has no fixing for 2026-05-25, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            calendar(valuation_date(day("2026-08-01"), 0.0), SCHEDULE, CLOSED_MAY_25),
            FIXINGS,
            "daily_fixings has no fixing for 2026-05-26, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-11", "2026-05-12", "2026-05-13"),
            "daily_fixings has no fixing for 2026-05-20, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            CALENDAR,
            fixings_on(
                "2026-05-20",
                "2026-05-21",
                "2026-05-22",
                "2026-05-25",
                "2026-05-26",
                holidays=ELSEWHERE,
            ),
            "daily_fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21", "2026-05-22", "2026-05-25", holidays=ELSEWHERE),
            "daily_fixings date 2026-05-25 is a non-business day in calendar, expected no fixing",
        ),
    ],
    ids=[
        "a fixing on the valuation date",
        "fixings running past the valuation date, the earliest named",
        "a fixing on the valuation date outside the calendar's days",
        "a fixing on a day the calendar closes, the fixings' own calendar open",
        "two closed days with fixings, the earliest named",
        "the first past business day without a fixing",
        "the last past business day without a fixing",
        "a day between without a fixing, the fixings' own calendar closed on it",
        "both ends without a fixing, the earliest named",
        "a calendar open on the holiday the fixings skip",
        "a calendar entirely past with fixings for its first days alone",
        "fixings entirely before the calendar",
        "the valuation date is checked before the closed days",
        "the closed days are checked before the missing days",
    ],
)
def test_a_history_that_cannot_be_made_says_why(
    made: Calendar, fixings: DailyFixings, message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market_history(made, fixings)
    assert str(failure.value) == message


def test_the_fraction_of_the_valuation_day_admits_no_fixing_on_it() -> None:
    late = fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26")
    for fraction in (0.0, 0.5, 1.0):
        made = calendar(valuation_date(day("2026-05-26"), fraction), SCHEDULE, CLOSED_MAY_25)
        with pytest.raises(ValueError) as failure:
            market_history(made, late)
        assert str(failure.value).startswith("daily_fixings date 2026-05-26 is on or after")
        assert priced(market_history(made, FIXINGS)) == priced(a_history())


# --- calendars with nothing to price ------------------------------------------


# Valued on 1 May 2026, before any of its days: no day is past, so no fixing is required, and
# the fixings, the last week of April, are before the valuation date, outside the calendar and
# unused.
def test_a_calendar_entirely_to_come_is_a_history_without_a_price() -> None:
    future = calendar(valuation_date(day("2026-05-01"), 0.5), SCHEDULE, CLOSED_MAY_25)
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
    closed = calendar(
        MAY_26, a_schedule(("m26", "2026-05-22"), ("n26", "2026-05-25")), CLOSED_MAY_25
    )
    assert closed.is_past.all() and not closed.is_business_day.any()
    made = market_history(closed, FIXINGS)
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
    schedule = expiry_schedule(tuple(f"c{i}" for i in range(count)), expiries, None, None)
    listed = expiries[0] + np.array(
        data.draw(st.lists(st.integers(-20, 400), max_size=30)), dtype="timedelta64[D]"
    )
    span = int(offsets[-1] - offsets[0])
    as_of = expiries[0] + np.timedelta64(data.draw(st.integers(-10, span + 10)), "D")
    fraction = data.draw(st.sampled_from((0.0, 0.5, 1.0)))
    return calendar(valuation_date(as_of, fraction), schedule, holiday_calendar(listed))


@settings(deadline=None)
@given(data=st.data())
def test_every_past_business_day_takes_its_own_fixing_and_no_other_day_takes_one(
    data: st.DataObject,
) -> None:
    made = any_calendar(data)
    as_of = made.valuation_date.as_of
    # Fixings on every business day, under the calendar's own list, from before the calendar's
    # first day to the day before the valuation date: whole over every past business day.
    span = made.dates.size + 20 + data.draw(st.integers(0, 10))
    days = np.arange(as_of - np.timedelta64(span, "D"), as_of, dtype="datetime64[D]")
    days = days[np.is_busday(days, holidays=made.holiday_calendar.holiday)]
    settles = data.draw(st.floats(-100, 100)) + np.arange(days.size, dtype=np.float64)
    fixings = daily_fixings(days, settles, made.holiday_calendar.holiday)
    history = market_history(made, fixings)
    required = np.flatnonzero(made.is_past & made.is_business_day)
    assert history.calendar is made
    assert history.fixed_rows.tolist() == required.tolist()
    where = np.searchsorted(fixings.dates, made.dates[required])
    assert np.array_equal(fixings.dates[where], made.dates[required])
    assert np.array_equal(history.fixing_prices, fixings.settles[where])
    assert history.fixing_prices.size == required.size


# --- ownership ----------------------------------------------------------------


def test_the_history_keeps_the_calendar_itself_and_its_columns_read_only() -> None:
    made = a_history()
    assert made.calendar is CALENDAR
    assert made.calendar.dates is CALENDAR.dates
    assert made.calendar.is_business_day is CALENDAR.is_business_day
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
        for column in (CALENDAR.dates, CALENDAR.prompt, CALENDAR.is_business_day, CALENDAR.is_past)
    )
    dates_before, settles_before = FIXINGS.dates.copy(), FIXINGS.settles.copy()
    first = a_history()
    second = a_history(
        fixings=fixings_on("2026-05-20", "2026-05-21", "2026-05-22", prices=(1.0, 2.0, 3.0))
    )
    for column, before in zip(
        (CALENDAR.dates, CALENDAR.prompt, CALENDAR.is_business_day, CALENDAR.is_past),
        columns_before,
        strict=True,
    ):
        assert np.array_equal(column, before)
    assert np.array_equal(FIXINGS.dates, dates_before)
    assert np.array_equal(FIXINGS.settles, settles_before)
    assert first.calendar is second.calendar is CALENDAR
    assert first.fixing_prices.tolist() == [70.85, 71.10, 71.25]
    assert second.fixing_prices.tolist() == [1.0, 2.0, 3.0]
    assert first.fixing_prices is not second.fixing_prices
    assert np.array_equal(first.fixed_rows, second.fixed_rows)
