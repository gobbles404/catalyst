"""The market history: the fixings' kind against the calendar's, that market's rules on the
fixings against the calendar, and the two columns made once from two objects, the calendar kept
as it is."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar, calendar
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import FuturesSchedule, futures_schedule
from goosedove.index_definitions.gas_daily_schedule import gas_daily_schedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.futures_fixings import FuturesFixings, futures_fixings
from goosedove.market_data.gas_daily_fixings import GasDailyFixings, gas_daily_fixings
from goosedove.market_data.iferc_fixings import IfercFixings, iferc_fixings


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
CLOSED_MAY_25 = holiday_calendar(dates("2026-05-25"))
# A calendar of one day, New Year's Day, outside every calendar built here.
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


CALENDAR = calendar(MAY_26, an_index(SCHEDULE, CLOSED_MAY_25))


def fixings_on(
    *days: str, prices: tuple[float, ...] = (), holidays: HolidayCalendar = CLOSED_MAY_25
) -> FuturesFixings:
    settles = np.array(prices or tuple(70.0 + i for i in range(len(days))), dtype=np.float64)
    return futures_fixings(dates(*days), settles, an_index(SCHEDULE, holidays))


FIXINGS = fixings_on("2026-05-20", "2026-05-21", "2026-05-22", prices=(70.85, 71.10, 71.25))


def a_history(made: Calendar = CALENDAR, fixings: FuturesFixings = FIXINGS) -> MarketHistory:
    return market_history(made, fixings)


def priced(made: MarketHistory) -> dict[str, float]:
    """The days that carry a price, each with its price, as the history aligns them."""
    days = made.calendar.dates[made.fixed_rows]
    return {str(d): float(p) for d, p in zip(days, made.fixing_prices, strict=True)}


def business_days(first: str, last: str, holidays: HolidayCalendar) -> NDArray[np.datetime64]:
    """Every business day from the first day to the last under that calendar's list."""
    days = np.arange(day(first), day(last) + np.timedelta64(1, "D"), dtype="datetime64[D]")
    return days[np.is_busday(days, holidays=holidays.holiday)]


def whole_fixings(
    first: str, last: str, holidays: HolidayCalendar = CLOSED_MAY_25
) -> FuturesFixings:
    """A fixing on every business day from the first day to the last, priced by position."""
    days = business_days(first, last, holidays)
    return futures_fixings(
        days, 60.0 + np.arange(days.size, dtype=np.float64), an_index(SCHEDULE, holidays)
    )


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
    one_day = calendar(
        valuation_date(day("2026-05-21"), 0.5),
        an_index(a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-20")), CLOSED_MAY_25),
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
    past = calendar(valuation_date(day("2026-08-01"), 0.0), an_index(SCHEDULE, CLOSED_MAY_25))
    fixings = whole_fixings("2026-05-20", "2026-07-31")
    made = market_history(past, fixings)
    assert made.calendar is past
    assert past.is_fixed.all()
    assert made.fixed_rows.tolist() == np.flatnonzero(past.is_priced).tolist()
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
                an_index(a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-22")), CLOSED_MAY_25),
            ),
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26", "2026-05-27"),
            "fixings date 2026-05-26 is on or after valuation date 2026-05-26, "
            "expected dates before the valuation date",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-25", holidays=ELSEWHERE),
            "fixings date 2026-05-25 is a closed day in calendar, expected no fixing",
        ),
        (
            calendar(
                MAY_26, an_index(SCHEDULE, holiday_calendar(dates("2026-05-21", "2026-05-22")))
            ),
            FIXINGS,
            "fixings date 2026-05-21 is a closed day in calendar, expected no fixing",
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
            fixings_on("2026-05-20", "2026-05-22", holidays=holiday_calendar(dates("2026-05-21"))),
            "fixings has no fixing for 2026-05-21, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            CALENDAR,
            fixings_on("2026-05-21"),
            "fixings has no fixing for 2026-05-20, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            calendar(MAY_26, an_index(SCHEDULE, ELSEWHERE)),
            FIXINGS,
            "fixings has no fixing for 2026-05-25, "
            "expected a fixing for every fixed day in calendar",
        ),
        (
            calendar(valuation_date(day("2026-08-01"), 0.0), an_index(SCHEDULE, CLOSED_MAY_25)),
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
            "fixings date 2026-05-25 is a closed day in calendar, expected no fixing",
        ),
    ],
    ids=[
        "a fixing on the valuation date",
        "fixings running past the valuation date, the earliest named",
        "a fixing on the valuation date outside the calendar's days",
        "a fixing on a day the calendar closes, the fixings' own calendar open",
        "two closed days with fixings, the earliest named",
        "the first fixed day without a fixing",
        "the last fixed day without a fixing",
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
    made: Calendar, fixings: FuturesFixings, message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market_history(made, fixings)
    assert str(failure.value) == message


def test_the_fraction_of_the_valuation_day_admits_no_fixing_on_it() -> None:
    late = fixings_on("2026-05-20", "2026-05-21", "2026-05-22", "2026-05-26")
    for fraction in (0.0, 0.5, 1.0):
        made = calendar(
            valuation_date(day("2026-05-26"), fraction), an_index(SCHEDULE, CLOSED_MAY_25)
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
    future = calendar(valuation_date(day("2026-05-01"), 0.5), an_index(SCHEDULE, CLOSED_MAY_25))
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
        MAY_26, an_index(a_schedule(("m26", "2026-05-22"), ("n26", "2026-05-25")), CLOSED_MAY_25)
    )
    assert closed.is_fixed.all() and not closed.is_priced.any()
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
    schedule = futures_schedule(tuple(f"c{i}" for i in range(count)), expiries, None)
    listed = expiries[0] + np.array(
        data.draw(st.lists(st.integers(-20, 400), max_size=30)), dtype="timedelta64[D]"
    )
    span = int(offsets[-1] - offsets[0])
    as_of = expiries[0] + np.timedelta64(data.draw(st.integers(-10, span + 10)), "D")
    fraction = data.draw(st.sampled_from((0.0, 0.5, 1.0)))
    return calendar(valuation_date(as_of, fraction), an_index(schedule, holiday_calendar(listed)))


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
    fixings = futures_fixings(days, settles, made.index)
    history = market_history(made, fixings)
    required = np.flatnonzero(made.is_fixed & made.is_priced)
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
    assert first.fixing_prices.tolist() == [70.85, 71.10, 71.25]
    assert second.fixing_prices.tolist() == [1.0, 2.0, 3.0]
    assert first.fixing_prices is not second.fixing_prices
    assert np.array_equal(first.fixed_rows, second.fixed_rows)


# --- a Gas Daily calendar and its prints -------------------------------------------------


def a_gas_daily_calendar(as_of: str = "2026-09-25", fraction: float = 0.5) -> Calendar:
    """The Gas Daily schedule page's three months, valued on the given day."""
    schedule = gas_daily_schedule(
        ("U26", "V26", "X26"),
        dates("2026-09-01", "2026-10-01", "2026-11-01"),
        dates("2026-09-30", "2026-10-31", "2026-11-30"),
    )
    return calendar(valuation_date(day(as_of), fraction), an_index(schedule, None))


def prints_on(first: str, last: str) -> GasDailyFixings:
    """A print on every flow day from the first to the last, 2.80 rising by a cent a day."""
    days = np.arange(day(first), day(last) + np.timedelta64(1, "D"), dtype="datetime64[D]")
    return gas_daily_fixings(days, 2.80 + np.arange(days.size, dtype=np.float64) / 100)


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


# --- an IFERC calendar and its indices ----------------------------------------------------


IFERC_SCHEDULE = iferc_schedule(
    ("V26", "X26", "Z26"),
    dates("2026-09-30", "2026-10-30", "2026-11-30"),
    dates("2026-10-01", "2026-11-02", "2026-12-01"),
)


def an_iferc_calendar(as_of: str = "2026-11-15") -> Calendar:
    """The IFERC schedule page's three months, valued on the given day."""
    return calendar(valuation_date(day(as_of), 0.5), an_index(IFERC_SCHEDULE, None))


def indices_for(*pairs: tuple[str, float]) -> IfercFixings:
    codes = tuple(code for code, _ in pairs)
    return iferc_fixings(codes, np.array([price for _, price in pairs], dtype=np.float64))


IFERC = an_iferc_calendar()


def test_the_iferc_sample_prices_the_published_months_and_no_other() -> None:
    made = market_history(IFERC, indices_for(("V26", 1.85), ("X26", 2.10)))
    assert made.calendar is IFERC
    assert made.fixed_rows.tolist() == [0, 1]
    assert made.fixing_prices.tolist() == [1.85, 2.10]


def test_iferc_indices_come_back_in_the_calendars_order_whatever_order_they_came_in() -> None:
    made = market_history(IFERC, indices_for(("X26", 2.10), ("V26", 1.85)))
    assert made.fixed_rows.tolist() == [0, 1]
    assert made.fixing_prices.tolist() == [1.85, 2.10]


def test_an_iferc_calendar_of_one_month_and_one_with_nothing_published() -> None:
    one = calendar(
        valuation_date(day("2026-11-15"), 0.5),
        an_index(iferc_schedule(("V26",), dates("2026-09-30"), dates("2026-10-01")), None),
    )
    made = market_history(one, indices_for(("V26", 1.85)))
    assert made.fixed_rows.tolist() == [0] and made.fixing_prices.tolist() == [1.85]
    nothing = market_history(
        an_iferc_calendar("2026-09-15"), iferc_fixings((), np.array([], dtype=np.float64))
    )
    assert nothing.fixed_rows.size == 0 and nothing.fixing_prices.size == 0


def test_an_index_for_the_month_published_on_the_valuation_day_is_refused() -> None:
    with pytest.raises(ValueError) as failure:
        market_history(an_iferc_calendar("2026-11-02"), indices_for(("V26", 1.85), ("X26", 2.10)))
    assert str(failure.value) == (
        "fixings contract_code 'X26' is a month not yet fixed in calendar, "
        "expected an index for fixed months alone"
    )
    the_day_after = market_history(
        an_iferc_calendar("2026-11-03"), indices_for(("V26", 1.85), ("X26", 2.10))
    )
    assert the_day_after.fixed_rows.tolist() == [0, 1]


@pytest.mark.parametrize(
    ("pairs", "message"),
    [
        (
            (("K26", 1.85),),
            "fixings contract_code 'K26' is not a month of calendar, expected one of its codes",
        ),
        (
            (("V26", 1.85), ("X26", 2.10), ("Z26", 2.20)),
            "fixings contract_code 'Z26' is a month not yet fixed in calendar, "
            "expected an index for fixed months alone",
        ),
        (
            (("V26", 1.85),),
            "fixings has no index for X26, expected an index for every fixed month in calendar",
        ),
        (
            (("X26", 2.10),),
            "fixings has no index for V26, expected an index for every fixed month in calendar",
        ),
        (
            (("Z26", 2.20), ("K26", 1.0)),
            "fixings contract_code 'K26' is not a month of calendar, expected one of its codes",
        ),
        (
            (("Z26", 2.20), ("V26", 1.85)),
            "fixings contract_code 'Z26' is a month not yet fixed in calendar, "
            "expected an index for fixed months alone",
        ),
    ],
    ids=[
        "a code the calendar does not hold",
        "an index for a month not yet fixed",
        "the second fixed month without an index",
        "the first fixed month without an index",
        "the codes are checked before the fixed months",
        "the fixed months are checked before the missing ones",
    ],
)
def test_an_iferc_history_that_cannot_be_made_says_why(
    pairs: tuple[tuple[str, float], ...], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        market_history(IFERC, indices_for(*pairs))
    assert str(failure.value) == message


# --- the fixings are the calendar's market's --------------------------------------------


def test_fixings_of_another_market_are_refused_naming_both() -> None:
    gas_daily = prints_on("2026-09-01", "2026-09-25")
    iferc = indices_for(("V26", 1.85))
    for made, fixings, message in (
        (
            CALENDAR,
            gas_daily,
            "fixings is Gas Daily fixings, expected futures fixings with a futures calendar",
        ),
        (
            CALENDAR,
            iferc,
            "fixings is IFERC fixings, expected futures fixings with a futures calendar",
        ),
        (
            GAS_DAILY,
            FIXINGS,
            "fixings is futures fixings, expected Gas Daily fixings with a Gas Daily calendar",
        ),
        (
            GAS_DAILY,
            iferc,
            "fixings is IFERC fixings, expected Gas Daily fixings with a Gas Daily calendar",
        ),
        (
            IFERC,
            FIXINGS,
            "fixings is futures fixings, expected IFERC fixings with an IFERC calendar",
        ),
        (
            IFERC,
            gas_daily,
            "fixings is Gas Daily fixings, expected IFERC fixings with an IFERC calendar",
        ),
    ):
        with pytest.raises(ValueError) as failure:
            market_history(made, fixings)
        assert str(failure.value) == message


def test_an_object_that_is_not_fixings_is_refused_naming_what_it_is() -> None:
    for wrong, what in (
        (CLOSED_MAY_25, "a holiday calendar"),
        (CALENDAR, "a calendar"),
        (SCHEDULE, "a futures schedule"),
    ):
        with pytest.raises(ValueError) as failure:
            market_history(CALENDAR, wrong)
        assert str(failure.value) == (
            f"fixings is {what}, expected futures, IFERC or Gas Daily fixings"
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
    prints = gas_daily_fixings(days, 1.0 + np.arange(days.size, dtype=np.float64))
    history = market_history(made, prints)
    required = np.flatnonzero(made.is_fixed)
    assert history.fixed_rows.tolist() == required.tolist()
    assert np.array_equal(history.fixing_prices, prints.prices[np.isin(days, made.dates[required])])
    assert history.calendar is made


@settings(deadline=None)
@given(data=st.data())
def test_every_fixed_month_takes_its_own_index_in_the_calendars_order(
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
    schedule = iferc_schedule(codes, published - np.timedelta64(1, "D"), published)
    as_of = start + np.timedelta64(data.draw(st.integers(-10, int(gaps.sum()) + 10)), "D")
    made = calendar(valuation_date(as_of, 0.5), an_index(schedule, None))
    fixed = np.flatnonzero(made.is_fixed).tolist()
    order = data.draw(st.permutations(fixed))
    fixings = iferc_fixings(
        tuple(codes[i] for i in order), np.array([100.0 + i for i in order], dtype=np.float64)
    )
    history = market_history(made, fixings)
    assert history.fixed_rows.tolist() == fixed
    assert history.fixing_prices.tolist() == [100.0 + i for i in fixed]
    assert not history.fixed_rows.flags.writeable and not history.fixing_prices.flags.writeable
