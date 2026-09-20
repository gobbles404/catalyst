"""The market history: the fixings that fit the calendar's mode, the daily rules and the monthly
rules, and the two columns made once from two objects, the calendar kept as it is."""

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
from goosedove.market_data.monthly_fixings import MonthlyFixings, monthly_fixings


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
CALENDAR = calendar(MAY_26, "daily", SCHEDULE, CLOSED_MAY_25)


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
        "daily",
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
    past = calendar(valuation_date(day("2026-08-01"), 0.0), "daily", SCHEDULE, CLOSED_MAY_25)
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
            calendar(
                MAY_26,
                "daily",
                a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-22")),
                CLOSED_MAY_25,
            ),
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26", "2026-05-27"),
            "fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-25", holidays=ELSEWHERE),
            "fixings date 2026-05-25 is a non-business day in calendar, expected no fixing",
        ),
        (
            calendar(
                MAY_26, "daily", SCHEDULE, holiday_calendar(dates("2026-05-21", "2026-05-22"))
            ),
            FIXINGS,
            "fixings date 2026-05-21 is a non-business day in calendar, expected no fixing",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21", "2026-05-22"),
            "fixings has no fixing for 2026-05-20, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21"),
            "fixings has no fixing for 2026-05-22, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-22", holidays=holiday_calendar(dates("2026-05-21"))),
            "fixings has no fixing for 2026-05-21, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21"),
            "fixings has no fixing for 2026-05-20, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            calendar(MAY_26, "daily", SCHEDULE, ELSEWHERE),
            FIXINGS,
            "fixings has no fixing for 2026-05-25, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            calendar(valuation_date(day("2026-08-01"), 0.0), "daily", SCHEDULE, CLOSED_MAY_25),
            FIXINGS,
            "fixings has no fixing for 2026-05-26, "
            "expected a fixing for every past business day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-11", "2026-05-12", "2026-05-13"),
            "fixings has no fixing for 2026-05-20, "
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
            "fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21", "2026-05-22", "2026-05-25", holidays=ELSEWHERE),
            "fixings date 2026-05-25 is a non-business day in calendar, expected no fixing",
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
        made = calendar(
            valuation_date(day("2026-05-26"), fraction), "daily", SCHEDULE, CLOSED_MAY_25
        )
        with pytest.raises(ValueError) as failure:
            market_history(made, late)
        assert str(failure.value).startswith("fixings date 2026-05-26 is on or after")
        assert priced(market_history(made, FIXINGS)) == priced(a_history())


# --- calendars with nothing to price ------------------------------------------


# Valued on 1 May 2026, before any of its days: no day is past, so no fixing is required, and
# the fixings, the last week of April, are before the valuation date, outside the calendar and
# unused.
def test_a_calendar_entirely_to_come_is_a_history_without_a_price() -> None:
    future = calendar(valuation_date(day("2026-05-01"), 0.5), "daily", SCHEDULE, CLOSED_MAY_25)
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
        MAY_26, "daily", a_schedule(("m26", "2026-05-22"), ("n26", "2026-05-25")), CLOSED_MAY_25
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
    return calendar(valuation_date(as_of, fraction), "daily", schedule, holiday_calendar(listed))


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


# --- the fixings that fit the calendar's mode ------------------------------------


PUBLISHED = expiry_schedule(
    SCHEDULE.codes,
    SCHEDULE.future_expiry,
    None,
    dates("2026-05-20", "2026-06-23", "2026-07-22"),
)


def monthly_fixings_on(
    *pairs: tuple[str, float], schedule: ExpirySchedule = PUBLISHED
) -> MonthlyFixings:
    published = schedule.publication_date
    assert published is not None
    return monthly_fixings(
        dates(*(d for d, _ in pairs)), np.array([p for _, p in pairs], dtype=np.float64), published
    )


# The calendar says how the index fixes, and the fixings must be of that kind: never read off
# the fixings themselves, and never a monthly series along a daily calendar or the reverse.
def test_the_fixings_must_be_of_the_calendars_kind() -> None:
    daily = calendar(MAY_26, "daily", PUBLISHED, CLOSED_MAY_25)
    monthly = calendar(MAY_26, "monthly", PUBLISHED, CLOSED_MAY_25)
    with pytest.raises(ValueError) as failure:
        market_history(daily, monthly_fixings_on(("2026-05-20", 2.5)))
    assert str(failure.value) == (
        "fixings is monthly fixings, expected daily fixings for a daily calendar"
    )
    with pytest.raises(ValueError) as failure:
        market_history(monthly, FIXINGS)
    assert str(failure.value) == (
        "fixings is daily fixings, expected monthly fixings for a monthly calendar"
    )
    assert priced(market_history(daily, FIXINGS)) == priced(a_history())
    assert market_history(monthly, monthly_fixings_on(("2026-05-20", 2.5))).fixed_rows.size == 0


# --- a monthly calendar ---------------------------------------------------------


# The page's example: four contracts, the first the anchor, each with the day its price is
# published; valued on 25 June 2026 with the 24th a holiday, n26 expired on the 22nd and its
# fixing supplied, q26 and u26 live.
TOY = expiry_schedule(
    ("m26", "n26", "q26", "u26"),
    dates("2026-05-19", "2026-06-22", "2026-07-21", "2026-08-20"),
    None,
    dates("2026-05-20", "2026-06-23", "2026-07-22", "2026-08-21"),
)
CLOSED_JUN_24 = holiday_calendar(dates("2026-06-24"))
MONTHLY = calendar(valuation_date(day("2026-06-25"), 0.5), "monthly", TOY, CLOSED_JUN_24)
N26 = monthly_fixings_on(("2026-06-23", 2.95), schedule=TOY)


def a_monthly_calendar(
    as_of: str, fraction: float = 0.5, schedule: ExpirySchedule = TOY
) -> Calendar:
    return calendar(valuation_date(day(as_of), fraction), "monthly", schedule, CLOSED_JUN_24)


def test_the_example_prices_every_day_of_the_expired_contract_and_no_other() -> None:
    made = market_history(MONTHLY, N26)
    assert made.calendar is MONTHLY
    assert made.fixed_rows.tolist() == list(range(34))  # 20 May to 22 June, n26's days
    assert made.fixing_prices.tolist() == [2.95] * 34
    assert made.fixed_rows.dtype == np.dtype(np.intp)
    assert made.fixing_prices.dtype == np.dtype(np.float64)
    shown = priced(made)
    assert shown["2026-05-20"] == shown["2026-06-20"] == shown["2026-06-22"] == 2.95
    for text in (
        "2026-06-23",
        "2026-06-24",
        "2026-06-25",
        "2026-06-27",
        "2026-07-22",
        "2026-08-20",
    ):
        assert text not in shown
    flags = dict(
        zip((str(d) for d in MONTHLY.dates), MONTHLY.is_business_day.tolist(), strict=True)
    )
    assert (
        flags["2026-06-20"] is False and flags["2026-06-24"] is False
    )  # priced or live, still closed


# Valued on 1 August: n26 and q26 expired, each day of each taking its own fixing, u26 live.
def test_several_expired_contracts_each_take_their_own_fixing_on_every_day() -> None:
    made = market_history(
        a_monthly_calendar("2026-08-01"),
        monthly_fixings_on(("2026-06-23", 2.95), ("2026-07-22", 3.05), schedule=TOY),
    )
    assert made.fixed_rows.tolist() == list(range(63))  # 20 May to 21 July
    shown = priced(made)
    assert (
        shown["2026-06-22"] == 2.95 and shown["2026-06-23"] == 3.05 and shown["2026-07-21"] == 3.05
    )
    assert "2026-07-22" not in shown
    assert made.fixing_prices.tolist() == [2.95] * 34 + [3.05] * 29


# Expiry day is live whatever fraction of it has elapsed; the day after, the contract has
# expired and its fixing is required.
def test_the_expiring_contract_is_live_on_its_expiry_day_and_expired_the_day_after() -> None:
    anchor_only = monthly_fixings_on(("2026-05-20", 1.0), schedule=TOY)
    for fraction in (0.0, 0.5, 1.0):
        made = market_history(a_monthly_calendar("2026-06-22", fraction), anchor_only)
        assert made.fixed_rows.size == 0 and made.fixing_prices.size == 0
        with pytest.raises(ValueError) as failure:
            market_history(a_monthly_calendar("2026-06-23", fraction), anchor_only)
        assert str(failure.value) == (
            "fixings has no fixing for 'n26' published 2026-06-23, "
            "expected a fixing for every expired contract in calendar"
        )
        assert market_history(a_monthly_calendar("2026-06-23", fraction), N26).fixed_rows.size == 34


# The days of a contract still live take nothing, past or not, open or closed: 23 and 24 June
# are past and q26's, and stay unfixed for the market's quote.
def test_past_days_of_a_live_contract_stay_unfixed() -> None:
    made = market_history(MONTHLY, N26)
    past_live = MONTHLY.is_past & (MONTHLY.prompt == 2)
    assert past_live.sum() == 2
    assert not np.isin(np.flatnonzero(past_live), made.fixed_rows).any()


# A publication date may fall after the valuation date, or after the calendar's last day, and
# the schedule's publication dates need no order: the fixing keyed by it is still the contract's.
def test_a_publication_date_after_valuation_or_after_the_calendar_still_keys_the_fixing() -> None:
    late = expiry_schedule(
        TOY.codes,
        TOY.future_expiry,
        None,
        dates("2026-05-20", "2026-09-01", "2026-07-22", "2026-08-21"),
    )
    made = market_history(
        a_monthly_calendar("2026-06-25", schedule=late),
        monthly_fixings_on(("2026-09-01", 2.95), schedule=late),
    )
    assert (
        made.fixed_rows.tolist() == list(range(34)) and made.fixing_prices.tolist() == [2.95] * 34
    )
    soon = expiry_schedule(
        TOY.codes,
        TOY.future_expiry,
        None,
        dates("2026-05-20", "2026-06-24", "2026-07-22", "2026-08-21"),
    )
    provisional = market_history(
        a_monthly_calendar("2026-06-23", schedule=soon),
        monthly_fixings_on(("2026-06-24", 2.90), schedule=soon),
    )
    assert provisional.fixing_prices.tolist() == [2.90] * 34


def test_a_missing_required_fixing_names_the_contract_and_its_publication_date() -> None:
    with pytest.raises(ValueError) as failure:
        market_history(a_monthly_calendar("2026-08-01"), N26)
    assert str(failure.value) == (
        "fixings has no fixing for 'q26' published 2026-07-22, "
        "expected a fixing for every expired contract in calendar"
    )
    with pytest.raises(ValueError) as failure:
        market_history(MONTHLY, monthly_fixings_on(("2026-05-20", 1.0), schedule=TOY))
    assert str(failure.value) == (
        "fixings has no fixing for 'n26' published 2026-06-23, "
        "expected a fixing for every expired contract in calendar"
    )


def test_two_contracts_sharing_a_publication_date_are_refused_by_name() -> None:
    shared = expiry_schedule(
        TOY.codes,
        TOY.future_expiry,
        None,
        dates("2026-05-20", "2026-06-23", "2026-06-23", "2026-08-21"),
    )
    with pytest.raises(ValueError) as failure:
        market_history(
            a_monthly_calendar("2026-06-25", schedule=shared),
            monthly_fixings_on(("2026-06-23", 2.95), schedule=shared),
        )
    assert str(failure.value) == (
        "calendar publication date 2026-06-23 is 'n26' and 'q26', "
        "expected one contract per publication date"
    )
    thrice = expiry_schedule(
        TOY.codes,
        TOY.future_expiry,
        None,
        dates("2026-06-23", "2026-06-23", "2026-06-23", "2026-08-21"),
    )
    with pytest.raises(ValueError) as failure:
        market_history(
            a_monthly_calendar("2026-06-25", schedule=thrice),
            monthly_fixings_on(("2026-06-23", 2.95), schedule=thrice),
        )
    assert str(failure.value) == (
        "calendar publication date 2026-06-23 is 'm26', 'n26' and 'q26', "
        "expected one contract per publication date"
    )


# The anchor's fixing and a fixing of another schedule are unused; a fixing of a contract not
# yet expired is refused, since its price is the live quote's.
def test_extra_fixings_are_unused_unless_they_are_a_live_contracts() -> None:
    with_anchor = monthly_fixings_on(("2026-05-20", 1.0), ("2026-06-23", 2.95), schedule=TOY)
    assert priced(market_history(MONTHLY, with_anchor)) == priced(market_history(MONTHLY, N26))
    other = monthly_fixings(dates("2026-01-05"), np.array([1.85]), dates("2026-01-05"))
    assert market_history(a_monthly_calendar("2026-06-22"), other).fixed_rows.size == 0
    with pytest.raises(ValueError) as failure:
        market_history(
            MONTHLY, monthly_fixings_on(("2026-06-23", 2.95), ("2026-07-22", 3.05), schedule=TOY)
        )
    assert str(failure.value) == (
        "fixings date 2026-07-22 is 'q26', not expired on 2026-06-25, "
        "expected fixings of expired contracts only"
    )
    with pytest.raises(ValueError) as failure:
        market_history(
            a_monthly_calendar("2026-05-01"),
            monthly_fixings_on(("2026-05-20", 1.0), ("2026-06-23", 2.95), schedule=TOY),
        )
    assert str(failure.value) == (
        "fixings date 2026-06-23 is 'n26', not expired on 2026-05-01, "
        "expected fixings of expired contracts only"
    )


# The provisional roll: on expiry day n26 is live; the day after, the desk supplies a value
# keyed by n26's scheduled publication date, whatever it is; when the published price arrives
# the desk replaces it, and the earlier history stands as it was.
def test_the_provisional_roll() -> None:
    soon = expiry_schedule(
        TOY.codes,
        TOY.future_expiry,
        None,
        dates("2026-05-20", "2026-06-24", "2026-07-22", "2026-08-21"),
    )
    on_expiry = market_history(
        a_monthly_calendar("2026-06-22", 1.0, schedule=soon),
        monthly_fixings_on(("2026-05-20", 1.0), schedule=soon),
    )
    assert on_expiry.fixed_rows.size == 0
    provisional = market_history(
        a_monthly_calendar("2026-06-23", 0.0, schedule=soon),
        monthly_fixings_on(("2026-06-24", 2.90), schedule=soon),
    )
    assert provisional.fixing_prices.tolist() == [2.90] * 34
    published = market_history(
        provisional.calendar, monthly_fixings_on(("2026-06-24", 2.95), schedule=soon)
    )
    assert published.fixing_prices.tolist() == [2.95] * 34
    assert provisional.fixing_prices.tolist() == [2.90] * 34
    assert published.calendar is provisional.calendar


# Valued before the calendar, nothing is required and nothing priced; inside, the expired
# contracts; after its last day, every contract but the anchor.
def test_valuation_before_inside_and_after_the_calendar() -> None:
    before = market_history(
        a_monthly_calendar("2026-05-01"), monthly_fixings_on(("2026-05-20", 1.0), schedule=TOY)
    )
    assert before.fixed_rows.size == 0 and before.calendar.dates.size == 93
    inside = market_history(MONTHLY, N26)
    assert inside.fixed_rows.size == 34
    after = market_history(
        a_monthly_calendar("2026-09-01"),
        monthly_fixings_on(
            ("2026-06-23", 2.95), ("2026-07-22", 3.05), ("2026-08-21", 3.15), schedule=TOY
        ),
    )
    assert after.fixed_rows.tolist() == list(range(93))
    assert after.fixing_prices.tolist() == [2.95] * 34 + [3.05] * 29 + [3.15] * 30


def test_a_monthly_fixing_of_zero_or_below_is_a_price() -> None:
    made = market_history(
        a_monthly_calendar("2026-08-01"),
        monthly_fixings_on(("2026-06-23", 0.0), ("2026-07-22", -1.5), schedule=TOY),
    )
    assert made.fixing_prices.tolist() == [0.0] * 34 + [-1.5] * 29


def test_a_monthly_history_keeps_the_calendar_itself_and_changes_no_input() -> None:
    dates_before, prompt_before = MONTHLY.dates.copy(), MONTHLY.prompt.copy()
    fixings_before = N26.prices.copy()
    first = market_history(MONTHLY, N26)
    second = market_history(MONTHLY, monthly_fixings_on(("2026-06-23", 3.33), schedule=TOY))
    assert first.calendar is MONTHLY and second.calendar is MONTHLY
    assert np.array_equal(MONTHLY.dates, dates_before) and np.array_equal(
        MONTHLY.prompt, prompt_before
    )
    assert np.array_equal(N26.prices, fixings_before)
    assert not first.fixed_rows.flags.writeable and not first.fixing_prices.flags.writeable
    with pytest.raises(ValueError):
        first.fixing_prices[0] = 1.0
    assert (
        first.fixing_prices.tolist() == [2.95] * 34 and second.fixing_prices.tolist() == [3.33] * 34
    )
    assert not np.shares_memory(first.fixing_prices, N26.prices)


# --- the general monthly rule ----------------------------------------------------


def any_monthly_history(data: st.DataObject) -> MarketHistory:
    """A monthly history of two to eight contracts up to 45 days apart, published in the order
    they expire on days of their own, the run of publications up to 40 days before or after
    the run of expiries, any holidays, valued on any day from the calendar's first to the day
    after its last, with a fixing for every expired contract and for nothing else."""
    count = data.draw(st.integers(2, 8))
    gaps = data.draw(st.lists(st.integers(1, 45), min_size=count, max_size=count))
    offsets = np.cumsum(gaps, dtype=np.int64)
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    expiries = start + offsets.astype("timedelta64[D]")
    lags = data.draw(st.lists(st.integers(1, 45), min_size=count, max_size=count))
    lead = data.draw(st.integers(-40, 40))
    published: NDArray[np.datetime64] = start + (lead + np.cumsum(lags, dtype=np.int64)).astype(
        "timedelta64[D]"
    )
    schedule = expiry_schedule(tuple(f"c{i}" for i in range(count)), expiries, None, published)
    listed = expiries[0] + np.array(
        data.draw(st.lists(st.integers(-20, 400), max_size=30)), dtype="timedelta64[D]"
    )
    span = int(offsets[-1] - offsets[0])
    as_of: np.datetime64 = expiries[0] + np.timedelta64(data.draw(st.integers(1, span + 1)), "D")
    made = calendar(
        valuation_date(as_of, data.draw(st.sampled_from((0.0, 0.5, 1.0)))),
        "monthly",
        schedule,
        holiday_calendar(listed),
    )
    expired = int(np.searchsorted(expiries, as_of, side="left"))
    supplied = published[1:expired]
    prices = 50.0 + np.arange(supplied.size, dtype=np.float64)
    return market_history(made, monthly_fixings(supplied, prices, published))


# For any monthly history: the fixed rows are exactly the days whose prompt contract expired
# before the valuation day, and each takes the price supplied for its contract, 50 for the
# schedule's second contract, 51 for its third, and so on, the anchor never among them.
@settings(deadline=None)
@given(data=st.data())
def test_every_day_of_an_expired_contract_takes_its_fixing_and_no_other_day_takes_one(
    data: st.DataObject,
) -> None:
    history = any_monthly_history(data)
    made = history.calendar
    expired = made.expiry_schedule.future_expiry < made.valuation_date.as_of
    assert history.fixed_rows.tolist() == np.flatnonzero(expired[made.prompt]).tolist()
    assert history.fixing_prices.tolist() == (49.0 + made.prompt[history.fixed_rows]).tolist()
    assert 0 not in made.prompt[history.fixed_rows]


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
