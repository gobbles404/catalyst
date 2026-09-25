"""The calendar: three rules on the schedule, and the four columns made once from three objects."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar, calendar
from goosedove.globals.valuation_date import ValuationDate, valuation_date
from goosedove.index_definitions.futures_schedule import FuturesSchedule, futures_schedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


def a_schedule(*contracts: tuple[str, str]) -> FuturesSchedule:
    codes = tuple(code for code, _ in contracts)
    return futures_schedule(codes, dates(*(expiry for _, expiry in contracts)), None)


def codes_of(made: Calendar) -> list[str]:
    return [made.futures_schedule.codes[row] for row in made.prompt.tolist()]


# The page's sample: three contracts of one index, the valuation date 25 May 2026 at midday,
# and that day, a Monday, a holiday.
SCHEDULE = a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-07-21"))
MAY_25 = valuation_date(day("2026-05-25"), 0.5)
CLOSED_MAY_25 = holiday_calendar(dates("2026-05-25"))
# A calendar of one day, New Year's Day, outside every calendar built here.
ELSEWHERE = holiday_calendar(dates("2026-01-01"))


def a_calendar(
    valuation: ValuationDate = MAY_25,
    schedule: FuturesSchedule = SCHEDULE,
    holidays: HolidayCalendar = CLOSED_MAY_25,
) -> Calendar:
    return calendar(valuation, schedule, holidays)


# --- the sample ---------------------------------------------------------------


def test_the_sample_runs_from_the_day_after_the_first_expiry_to_the_last() -> None:
    made = a_calendar()
    assert made.dates.size == 63
    assert made.dates[0] == day("2026-05-20")
    assert made.dates[-1] == day("2026-07-21")
    assert np.all(np.diff(made.dates) == np.timedelta64(1, "D"))
    assert made.dates.dtype == np.dtype("datetime64[D]")
    assert made.prompt.dtype == np.dtype(np.intp)
    assert made.is_business_day.dtype == np.dtype(bool)
    assert made.is_past.dtype == np.dtype(bool)
    assert made.prompt.size == made.is_business_day.size == made.is_past.size == 63


def test_the_rows_the_page_shows() -> None:
    made = a_calendar()
    shown = {
        str(date): (code, bool(open_), bool(past))
        for date, code, open_, past in zip(
            made.dates, codes_of(made), made.is_business_day, made.is_past, strict=True
        )
    }
    assert shown["2026-05-20"] == ("n26", True, True)
    assert shown["2026-05-22"] == ("n26", True, True)
    assert shown["2026-05-23"] == ("n26", False, True)
    assert shown["2026-05-24"] == ("n26", False, True)
    assert shown["2026-05-25"] == ("n26", False, False)
    assert shown["2026-05-26"] == ("n26", True, False)
    assert shown["2026-06-22"] == ("n26", True, False)
    assert shown["2026-06-23"] == ("q26", True, False)
    assert shown["2026-07-21"] == ("q26", True, False)


def test_the_boundary_contract_is_never_prompt() -> None:
    made = a_calendar()
    assert 0 not in made.prompt
    assert "m26" not in codes_of(made)
    assert made.prompt.min() == 1


# Every interior expiry keeps its contract, and the next calendar day switches to the next one;
# each contract after the boundary holds exactly the days from the expiry before its own to its
# own, weekends and holidays counted like any day.
def test_prompt_transitions_fall_the_day_after_each_expiry() -> None:
    schedule = a_schedule(
        ("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-07-21"), ("u26", "2026-08-20")
    )
    made = a_calendar(schedule=schedule)
    shown = dict(zip((str(d) for d in made.dates), codes_of(made), strict=True))
    assert shown["2026-05-20"] == "n26"
    assert shown["2026-06-22"] == "n26"
    assert shown["2026-06-23"] == "q26"
    assert shown["2026-07-21"] == "q26"
    assert shown["2026-07-22"] == "u26"
    assert shown["2026-08-20"] == "u26"
    assert np.bincount(made.prompt, minlength=4).tolist() == [0, 34, 29, 30]


def test_two_expiries_a_day_apart_make_one_row_for_the_second_contract() -> None:
    made = a_calendar(schedule=a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-20")))
    assert made.dates.tolist() == [day("2026-05-20")]
    assert codes_of(made) == ["n26"]
    assert made.is_business_day.tolist() == [True]
    assert made.is_past.tolist() == [True]


# --- what is rejected, in the order the rules run -----------------------------


@pytest.mark.parametrize(
    ("schedule", "message"),
    [
        (a_schedule(("m26", "2026-05-19")), "futures_schedule has 1 contract, expected at least 2"),
        (
            futures_schedule((), dates(), None),
            "futures_schedule has 0 contracts, expected at least 2",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("m26", "2026-06-22")),
            "contract_code row 2 is 'm26', already given at row 1",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("m26", "2026-07-21")),
            "contract_code row 3 is 'm26', already given at row 1",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("n26", "2026-07-21")),
            "contract_code row 3 is 'n26', already given at row 2",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("n26", "2026-05-19")),
            "future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-05-19",
        ),
        (
            a_schedule(("m26", "2026-06-22"), ("n26", "2026-05-19")),
            "future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22",
        ),
        (
            a_schedule(("m26", "2026-05-19"), ("n26", "2026-06-22"), ("q26", "2026-06-01")),
            "future_expiry row 3 is 2026-06-01, expected a date after row 2's 2026-06-22",
        ),
        (
            a_schedule(("m26", "2026-06-22"), ("m26", "2026-05-19")),
            "contract_code row 2 is 'm26', already given at row 1",
        ),
        (
            a_schedule(("M26", "2026-05-19"), ("m26", "2026-06-22")),
            "future_expiry row 2 is 2026-06-22, expected a date after row 1's 2026-05-19",
        ),
    ],
    ids=[
        "one contract",
        "no contract",
        "the boundary code given again",
        "the boundary code given a third row",
        "a code given twice after the boundary",
        "two expiries equal",
        "expiries backwards",
        "a later expiry before the one above",
        "the codes are checked before the expiries",
        "M26 and m26 are two codes",
    ],
)
def test_a_schedule_that_cannot_make_a_calendar_says_why(
    schedule: FuturesSchedule, message: str
) -> None:
    if message.startswith("future_expiry row 2 is 2026-06-22"):
        a_calendar(schedule=schedule)  # two codes, so the calendar is made
        return
    with pytest.raises(ValueError) as failure:
        a_calendar(schedule=schedule)
    assert str(failure.value) == message


# The bound the discount curve holds too: a calendar of a sheet's rows less the two heading rows
# is read back in full, and one day longer is refused, naming both expiries.
def test_the_longest_calendar_a_sheet_shows_is_made_and_one_day_longer_is_refused() -> None:
    longest = a_calendar(schedule=a_schedule(("a", "2026-05-19"), ("b", "4897-04-11")))
    assert longest.dates.size == 1_048_574
    assert longest.dates[-1] == day("4897-04-11")
    with pytest.raises(ValueError) as failure:
        a_calendar(schedule=a_schedule(("a", "2026-05-19"), ("b", "4897-04-12")))
    assert str(failure.value) == (
        "future_expiry row 2 is 4897-04-12, expected within 1048574 days of row 1's 2026-05-19"
    )
    with pytest.raises(ValueError) as failure:
        a_calendar(
            schedule=a_schedule(("a", "2026-05-19"), ("b", "2026-06-22"), ("c", "9999-12-31"))
        )
    assert str(failure.value) == (
        "future_expiry row 3 is 9999-12-31, expected within 1048574 days of row 1's 2026-05-19"
    )


# --- calendar arithmetic ------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        ("2026-04-30", "2026-05-31", [f"2026-05-{d:02d}" for d in range(1, 32)]),
        ("2026-12-30", "2027-01-02", ["2026-12-31", "2027-01-01", "2027-01-02"]),
        ("2028-02-27", "2028-03-01", ["2028-02-28", "2028-02-29", "2028-03-01"]),
        ("2027-02-27", "2027-03-01", ["2027-02-28", "2027-03-01"]),
        ("1900-03-01", "1900-03-02", ["1900-03-02"]),
        ("9999-12-30", "9999-12-31", ["9999-12-31"]),
        ("1900-03-01", "1900-03-04", ["1900-03-02", "1900-03-03", "1900-03-04"]),
    ],
    ids=[
        "a month end",
        "a year end",
        "a leap day",
        "no leap day",
        "the first days a cell holds",
        "the last days a cell holds",
        "a short range at the start of the sheet's calendar",
    ],
)
def test_every_calendar_day_between_the_expiries_is_a_row(
    first: str, last: str, expected: list[str]
) -> None:
    made = a_calendar(schedule=a_schedule(("a", first), ("b", last)), holidays=ELSEWHERE)
    assert [str(date) for date in made.dates] == expected
    assert codes_of(made) == ["b"] * len(expected)


# --- the business-day flag ----------------------------------------------------


def flags(made: Calendar) -> dict[str, tuple[bool, bool]]:
    return {
        str(date): (bool(open_), bool(past))
        for date, open_, past in zip(made.dates, made.is_business_day, made.is_past, strict=True)
    }


def test_weekdays_are_business_days_and_both_weekend_days_are_not() -> None:
    open_ = {date: open_ for date, (open_, _) in flags(a_calendar(holidays=ELSEWHERE)).items()}
    assert [open_[f"2026-05-{d}"] for d in range(20, 27)] == [
        True,  # Wednesday
        True,
        True,  # Friday
        False,  # Saturday
        False,  # Sunday
        True,  # Monday
        True,
    ]


def test_a_holiday_on_a_weekday_closes_it_and_one_on_a_weekend_changes_nothing() -> None:
    weekday = flags(a_calendar())
    assert weekday["2026-05-25"][0] is False
    assert weekday["2026-05-26"][0] is True
    on_a_saturday = flags(a_calendar(holidays=holiday_calendar(dates("2026-05-23"))))
    assert on_a_saturday == flags(a_calendar(holidays=ELSEWHERE))


def test_consecutive_holidays_close_each_day() -> None:
    closed = holiday_calendar(dates("2026-05-25", "2026-05-26", "2026-05-27"))
    shown = flags(a_calendar(holidays=closed))
    assert [shown[f"2026-05-{d}"][0] for d in (22, 25, 26, 27, 28)] == [
        True,
        False,
        False,
        False,
        True,
    ]


# --- holiday invariance -------------------------------------------------------


def test_duplicate_unordered_and_out_of_range_holidays_change_nothing() -> None:
    plain = a_calendar(holidays=holiday_calendar(dates("2026-05-25", "2026-06-19")))
    messy = a_calendar(
        holidays=holiday_calendar(
            dates(
                "2026-06-19",
                "2026-05-25",
                "2026-05-25",
                "2025-01-01",
                "2027-12-25",
                "2026-05-19",
                "2026-07-22",
            )
        )
    )
    assert np.array_equal(plain.is_business_day, messy.is_business_day)
    assert np.array_equal(plain.dates, messy.dates)
    assert np.array_equal(plain.prompt, messy.prompt)
    assert np.array_equal(plain.is_past, messy.is_past)


def test_a_holiday_on_an_expiry_changes_the_business_day_flag_alone() -> None:
    plain = a_calendar(holidays=ELSEWHERE)
    closed = a_calendar(holidays=holiday_calendar(dates("2026-06-22")))
    assert np.array_equal(plain.dates, closed.dates)
    assert np.array_equal(plain.prompt, closed.prompt)
    assert np.array_equal(plain.is_past, closed.is_past)
    changed = plain.is_business_day != closed.is_business_day
    assert plain.dates[changed].tolist() == [day("2026-06-22")]
    assert flags(closed)["2026-06-22"][0] is False
    assert codes_of(closed)[33] == "n26"


# --- the past flag ------------------------------------------------------------


@pytest.mark.parametrize(
    ("as_of", "past_days"),
    [
        ("2026-01-01", 0),
        ("2026-05-19", 0),
        ("2026-05-20", 0),
        ("2026-05-21", 1),
        ("2026-05-25", 5),
        ("2026-07-21", 62),
        ("2026-07-22", 63),
        ("2027-01-01", 63),
    ],
    ids=[
        "before the calendar",
        "the boundary expiry, the day before the calendar",
        "the first day",
        "the second day",
        "inside",
        "the last day",
        "the day after the calendar",
        "well after the calendar",
    ],
)
def test_the_days_before_the_valuation_date_are_past_and_the_day_itself_is_not(
    as_of: str, past_days: int
) -> None:
    made = a_calendar(valuation=valuation_date(day(as_of), 0.5))
    assert int(made.is_past.sum()) == past_days
    assert made.is_past.tolist() == [bool(date < day(as_of)) for date in made.dates]
    if past_days:
        assert made.is_past[:past_days].all() and not made.is_past[past_days:].any()


def test_the_fraction_of_the_valuation_day_changes_nothing() -> None:
    whole = [a_calendar(valuation=valuation_date(day("2026-05-25"), f)) for f in (0.0, 0.5, 1.0)]
    for made in whole[1:]:
        assert np.array_equal(made.is_past, whole[0].is_past)
    assert not flags(whole[0])["2026-05-25"][1]
    assert not flags(whole[2])["2026-05-25"][1]


def test_the_two_flags_are_independent() -> None:
    shown = flags(a_calendar())
    assert shown["2026-05-23"] == (False, True)  # a past Saturday
    assert shown["2026-05-25"] == (False, False)  # the valuation date, a holiday
    assert shown["2026-05-22"] == (True, True)  # a past Friday
    assert shown["2026-05-26"] == (True, False)  # a Tuesday to come


# --- what the schedule's other columns do: nothing ---------------------------------


def test_option_expiries_change_nothing() -> None:
    codes = ("m26", "n26", "q26")
    futures = dates("2026-05-19", "2026-06-22", "2026-07-21")
    options = dates("2026-05-14", "2026-06-16", "2026-07-16")
    plain = a_calendar()
    for schedule in (
        futures_schedule(codes, futures, options),
        futures_schedule(codes, futures, dates("2027-01-01", "2027-01-02", "2027-01-03")),
    ):
        made = a_calendar(schedule=schedule)
        assert np.array_equal(made.dates, plain.dates)
        assert np.array_equal(made.prompt, plain.prompt)
        assert np.array_equal(made.is_business_day, plain.is_business_day)
        assert np.array_equal(made.is_past, plain.is_past)


# --- the general rule ---------------------------------------------------------


def any_schedule(data: st.DataObject) -> FuturesSchedule:
    count = data.draw(st.integers(2, 40))
    codes = tuple(
        data.draw(
            st.lists(st.text(min_size=1, max_size=6), unique=True, min_size=count, max_size=count)
        )
    )
    gaps = data.draw(st.lists(st.integers(1, 60), min_size=count, max_size=count))
    offsets = np.cumsum(gaps, dtype=np.int64)
    start = np.datetime64("2000-01-01", "D") + np.timedelta64(
        data.draw(st.integers(0, 20_000)), "D"
    )
    return futures_schedule(codes, start + offsets.astype("timedelta64[D]"), None)


@settings(deadline=None)
@given(data=st.data())
def test_every_day_between_the_first_expiry_and_the_last_is_one_row_with_one_prompt(
    data: st.DataObject,
) -> None:
    schedule = any_schedule(data)
    expiries = schedule.future_expiry
    listed = expiries[0] + np.array(
        data.draw(st.lists(st.integers(-10, 2500), max_size=30)), dtype="timedelta64[D]"
    )
    as_of = expiries[0] + np.timedelta64(data.draw(st.integers(-10, 2500)), "D")
    made = calendar(valuation_date(as_of, 0.5), schedule, holiday_calendar(listed))
    span = int((expiries[-1] - expiries[0]).astype(np.int64))
    assert made.dates.size == span
    assert np.all(np.diff(made.dates) == np.timedelta64(1, "D"))
    assert made.dates[0] == expiries[0] + np.timedelta64(1, "D")
    assert made.dates[-1] == expiries[-1]
    before = expiries[made.prompt - 1]
    own = expiries[made.prompt]
    assert np.all((before < made.dates) & (made.dates <= own))
    assert made.prompt.min() >= 1
    days_per_contract = np.diff(expiries).astype(np.int64)
    assert (
        np.bincount(made.prompt, minlength=expiries.size)[1:].tolist() == days_per_contract.tolist()
    )
    assert np.array_equal(made.is_past, made.dates < as_of)


# --- ownership ----------------------------------------------------------------


def test_the_calendar_keeps_its_sources_by_reference_and_its_columns_read_only() -> None:
    made = a_calendar()
    assert made.valuation_date is MAY_25
    assert made.futures_schedule is SCHEDULE
    assert made.holiday_calendar is CLOSED_MAY_25
    for column in (made.dates, made.prompt, made.is_business_day, made.is_past):
        assert not column.flags.writeable
    with pytest.raises(ValueError):
        made.dates[0] = day("2030-01-01")
    with pytest.raises(ValueError):
        made.is_past[0] = False


def test_making_a_calendar_changes_no_source_and_a_second_calendar_leaves_the_first() -> None:
    holidays = holiday_calendar(dates("2026-06-19", "2026-05-25", "2026-05-25"))
    listed_before = holidays.holiday.copy()
    first = a_calendar(holidays=holidays)
    assert np.array_equal(holidays.holiday, listed_before)
    assert np.array_equal(SCHEDULE.future_expiry, dates("2026-05-19", "2026-06-22", "2026-07-21"))
    assert SCHEDULE.codes == ("m26", "n26", "q26")
    past_before = first.is_past.copy()
    second = a_calendar(valuation=valuation_date(day("2026-07-01"), 0.0), holidays=holidays)
    assert np.array_equal(first.is_past, past_before)
    assert second.is_past.sum() > first.is_past.sum()
    assert first.dates is not second.dates
