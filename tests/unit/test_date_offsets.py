"""A date shifted by a text offset: the ticket's worked answers, the signed zeros, the suffixes in
any case, a count with leading zeros, the sheet's calendar as the bound either side, and
everything else refused naming the offset; the round trip of business days from an open day."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.index_definitions.date_offsets import FORMS, MOST_DIGITS, shift_date
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from goosedove.index_definitions.sheet_days import SHEET_FIRST_DAY, SHEET_LAST_DAY


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


# The ticket's synthetic calendar: Monday 12 October 2026 closed, and nothing else.
SYNTHETIC = holiday_calendar(np.array(["2026-10-12"], dtype="datetime64[D]"))


# --- the ticket's worked examples -----------------------------------------------------------


@pytest.mark.parametrize(
    ("date", "offset", "calendar", "expected"),
    [
        ("2026-10-09", "+1bd", None, "2026-10-12"),  # Friday to Monday
        ("2026-10-09", "+1BD", SYNTHETIC, "2026-10-13"),  # the Monday closed, to Tuesday
        ("2026-10-10", "+1bd", None, "2026-10-12"),  # Saturday to Monday
        ("2026-10-11", "-1bd", None, "2026-10-09"),  # Sunday back to Friday
        ("2026-10-12", "+1bd", SYNTHETIC, "2026-10-13"),  # the closed Monday on to Tuesday
        ("2026-10-12", "-1bd", SYNTHETIC, "2026-10-09"),  # and back to Friday
        ("2026-10-10", "+0bd", SYNTHETIC, "2026-10-10"),  # a closed day stays with zero
        ("2026-10-09", "+7cd", SYNTHETIC, "2026-10-16"),  # the calendar is not read
        ("2026-10-09", "-7cd", None, "2026-10-02"),
        ("2026-10-10", "-0cd", None, "2026-10-10"),
        ("2026-10-09", "+0em", SYNTHETIC, "2026-10-31"),  # a Saturday month end
        ("2026-10-09", "+1em", None, "2026-11-30"),
        ("2026-10-09", "-1em", None, "2026-09-30"),
        ("2028-01-31", "+1em", None, "2028-02-29"),  # a leap February
        ("2026-12-15", "+1em", None, "2027-01-31"),  # across the year end
        ("2026-10-09", "+001cD", None, "2026-10-10"),  # leading zeros, a mixed-case suffix
    ],
)
def test_the_tickets_examples_shift_as_it_says(
    date: str, offset: str, calendar: HolidayCalendar | None, expected: str
) -> None:
    shifted = shift_date(day(date), offset, calendar)
    assert shifted == day(expected)
    assert shifted.dtype == np.dtype("datetime64[D]")


def test_more_of_the_same_rules() -> None:
    assert shift_date(day("2027-01-31"), "+1em", None) == day("2027-02-28")  # no leap day
    assert shift_date(day("2026-10-08"), "+3bd", SYNTHETIC) == day("2026-10-14")  # over the holiday
    assert shift_date(day("2026-10-15"), "-3bd", SYNTHETIC) == day("2026-10-09")
    assert shift_date(day("2026-10-09"), "+10bd", None) == day("2026-10-23")  # two weekends
    for offset in ("+1Bd", "+1bD", "-2Cd", "+1EM", "-1Em"):
        assert shift_date(day("2026-10-09"), offset, None) == shift_date(
            day("2026-10-09"), offset.lower(), None
        )
    for offset in ("+0bd", "-0bd", "+0cd", "-0cd", "+000bd"):
        assert shift_date(day("2026-10-11"), offset, SYNTHETIC) == day("2026-10-11")  # a Sunday
    for offset in ("+0em", "-0em", "+00em"):
        assert shift_date(day("2026-10-11"), offset, None) == day("2026-10-31")


# --- the sheet's calendar bounds the result -------------------------------------------------


def test_the_last_day_of_the_sheet_keeps_its_month_end_and_nothing_past_it() -> None:
    assert shift_date(SHEET_LAST_DAY, "+0em", None) == SHEET_LAST_DAY
    assert shift_date(SHEET_FIRST_DAY, "+0cd", None) == SHEET_FIRST_DAY
    assert shift_date(SHEET_FIRST_DAY, "+2958404cd", None) == SHEET_LAST_DAY  # end to end
    assert shift_date(SHEET_LAST_DAY, "-2958404cd", None) == SHEET_FIRST_DAY


@pytest.mark.parametrize(
    ("date", "offset", "shifted"),
    [
        ("1900-03-01", "-1cd", "1900-02-28"),
        ("9999-12-31", "+1cd", "10000-01-01"),
        ("9999-12-31", "+1bd", "10000-01-03"),
        ("1900-03-01", "-1bd", "1900-02-28"),
        ("9999-12-31", "+1em", "10000-01-31"),
        ("1900-03-01", "-1em", "1900-02-28"),
        ("2026-10-09", "+9999999cd", "29405-11-03"),
        ("2026-10-09", "-9999999bd", "-36304-01-30"),
        ("2026-10-09", "+9999999em", "835360-01-31"),
    ],
)
def test_a_result_outside_the_sheets_calendar_is_refused_naming_the_date_and_the_offset(
    date: str, offset: str, shifted: str
) -> None:
    with pytest.raises(ValueError) as refused:
        shift_date(day(date), offset, None)
    assert str(refused.value) == (
        f"date {date} shifted by {offset!r} is {shifted}, outside the sheet's calendar, "
        "1900-03-01 to 9999-12-31"
    )


def test_a_count_of_more_than_seven_digits_is_refused_before_any_arithmetic() -> None:
    for offset, digits in (
        ("+99999999cd", 8),
        ("-00012345678bd", 8),
        ("+" + "9" * 5000 + "em", 5000),
    ):
        with pytest.raises(ValueError) as refused:
            shift_date(day("2026-10-09"), offset, None)
        assert str(refused.value) == (
            f"offset has a count of {digits} digits, expected at most {MOST_DIGITS}; the sheet's "
            "calendar runs 1900-03-01 to 9999-12-31"
        )
    # Seven digits are read, leading zeros and all, and held to the calendar like any count.
    assert shift_date(day("2026-10-09"), "+00000001234567cd", None) == day("5406-11-26")


def test_leading_zeros_are_dropped_before_the_count_is_read() -> None:
    # Five thousand leading zeros are no digits of the count: the digits after them are read,
    # none after them is zero, and eight after them are refused by those eight; nothing is ever
    # converted whole, so no count runs into Python's own limit on the digits it converts.
    zeros = "0" * 5000
    assert shift_date(day("2026-10-09"), "+" + zeros + "1cd", None) == day("2026-10-10")
    assert shift_date(day("2026-10-09"), "-" + zeros + "1bd", SYNTHETIC) == day("2026-10-08")
    assert shift_date(day("2026-10-09"), "+" + zeros + "1em", None) == day("2026-11-30")
    assert shift_date(day("2026-10-09"), "+" + zeros + "bd", SYNTHETIC) == day("2026-10-09")
    assert shift_date(day("2026-10-09"), "-" + zeros + "cd", None) == day("2026-10-09")
    assert shift_date(day("2026-10-09"), "+" + zeros + "em", None) == day("2026-10-31")
    with pytest.raises(ValueError) as refused:
        shift_date(day("2026-10-09"), "+" + zeros + "12345678cd", None)
    assert str(refused.value) == (
        f"offset has a count of 8 digits, expected at most {MOST_DIGITS}; the sheet's "
        "calendar runs 1900-03-01 to 9999-12-31"
    )


# --- what is no offset -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "offset",
    [
        "1bd",
        "+1.5bd",
        "+1wd",
        "+1bd+2cd",
        " +1bd",
        "+1bd ",
        "+ 1bd",
        "+1 bd",
        "+bd",
        "+1",
        "bd",
        "",
        "++1bd",
        "+-1bd",
        "+1b",
        "+1bdd",
        "+\N{ARABIC-INDIC DIGIT ONE}bd",  # no ASCII digit, however it reads
        "+1BDX",
        "1",
    ],
)
def test_anything_else_is_refused_naming_the_offset_and_the_form(offset: str) -> None:
    with pytest.raises(ValueError) as refused:
        shift_date(day("2026-10-09"), offset, SYNTHETIC)
    assert str(refused.value) == f"offset is {offset!r}, expected {FORMS}"


# --- properties -------------------------------------------------------------------------------


@given(
    st.integers(min_value=0, max_value=20_000),
    st.integers(min_value=1, max_value=400),
    st.booleans(),
)
def test_business_days_forward_and_back_from_an_open_day_round_trip(
    days_on: int, count: int, with_calendar: bool
) -> None:
    anchor = day("2026-01-05") + np.timedelta64(days_on, "D")  # Monday 5 January 2026 and on
    calendar = SYNTHETIC if with_calendar else None
    holidays = SYNTHETIC.holiday if with_calendar else np.array([], dtype="datetime64[D]")
    if not np.is_busday(anchor, holidays=holidays):
        return  # a closed anchor is not recovered by reversing an offset
    forward = shift_date(anchor, f"+{count}bd", calendar)
    assert np.is_busday(forward, holidays=holidays)
    assert np.busday_count(anchor, forward, holidays=holidays) == count
    assert shift_date(forward, f"-{count}bd", calendar) == anchor


@given(st.integers(min_value=0, max_value=40_000), st.integers(min_value=-600, max_value=600))
def test_a_month_end_is_the_last_day_of_the_month_the_count_names(days_on: int, count: int) -> None:
    anchor = day("1960-01-01") + np.timedelta64(
        days_on, "D"
    )  # to 2069, 600 months either way inside
    shifted = shift_date(anchor, f"{'+' if count >= 0 else '-'}{abs(count)}em", None)
    month = anchor.astype("datetime64[M]") + np.timedelta64(count, "M")
    assert shifted.astype("datetime64[M]") == month
    assert (shifted + np.timedelta64(1, "D")).astype("datetime64[M]") == month + np.timedelta64(
        1, "M"
    )


@given(st.integers(min_value=0, max_value=40_000), st.integers(min_value=-5_000, max_value=5_000))
def test_calendar_days_add_and_subtract_whatever_the_calendar_says(
    days_on: int, count: int
) -> None:
    anchor = day("1950-01-01") + np.timedelta64(days_on, "D")
    offset = f"{'+' if count >= 0 else '-'}{abs(count)}cd"
    assert shift_date(anchor, offset, SYNTHETIC) == anchor + np.timedelta64(count, "D")
    assert shift_date(anchor, offset, None) == anchor + np.timedelta64(count, "D")
