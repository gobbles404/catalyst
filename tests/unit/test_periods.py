"""Periods read from their labels: a month, a quarter, a calendar year, a winter, a summer and a
range of two, their first and last calendar days, the letters in either case, and everything else
refused naming the whole expression."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.index_definitions.contract_codes import MONTH_LETTERS
from goosedove.index_definitions.periods import FORMS, end_date, period_months, start_date


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


def span(period: str) -> tuple[str, str]:
    return str(start_date(period)), str(end_date(period))


# --- the forms, each by the ticket's examples ---------------------------------


@pytest.mark.parametrize(
    ("period", "first", "last"),
    [
        ("f26", "2026-01-01", "2026-01-31"),
        ("F26", "2026-01-01", "2026-01-31"),
        ("1q27", "2027-01-01", "2027-03-31"),
        ("2Q27", "2027-04-01", "2027-06-30"),
        ("3Q27", "2027-07-01", "2027-09-30"),
        ("4Q27", "2027-10-01", "2027-12-31"),
        ("cal28", "2028-01-01", "2028-12-31"),
        ("CAL28", "2028-01-01", "2028-12-31"),
        ("Cal28", "2028-01-01", "2028-12-31"),
        ("w29", "2029-11-01", "2030-03-31"),
        ("W29", "2029-11-01", "2030-03-31"),
        ("s28", "2028-04-01", "2028-10-31"),
        ("S28", "2028-04-01", "2028-10-31"),
        ("f26-z28", "2026-01-01", "2028-12-31"),
        ("F26-Z28", "2026-01-01", "2028-12-31"),
        ("w28-w29", "2028-11-01", "2030-03-31"),
        ("F26-F26", "2026-01-01", "2026-01-31"),
        ("1Q27-CAL27", "2027-01-01", "2027-12-31"),
        ("W99", "2099-11-01", "2100-03-31"),
        ("G00", "2000-02-01", "2000-02-29"),
        ("G28", "2028-02-01", "2028-02-29"),
        ("G27", "2027-02-01", "2027-02-28"),
        ("Z99", "2099-12-01", "2099-12-31"),
        ("f00-cAL99", "2000-01-01", "2099-12-31"),
    ],
    ids=[
        "a month in lowercase",
        "a month in capitals",
        "the first quarter in lowercase",
        "the second quarter",
        "the third quarter",
        "the fourth quarter",
        "a calendar year in lowercase",
        "a calendar year in capitals",
        "a calendar year in mixed case",
        "a winter in lowercase, November to the March after",
        "a winter in capitals",
        "a summer in lowercase, April to October",
        "a summer in capitals",
        "a range of months in lowercase, three years",
        "a range of months in capitals",
        "two winters, the summer between them included",
        "a range of one month",
        "a quarter to its own year, all of the year",
        "the last winter two digits name, ending in the next century",
        "February 2000, a leap year",
        "February 2028, a leap year",
        "February 2027, no leap",
        "the last month two digits name",
        "the whole horizon, in mixed case",
    ],
)
def test_a_periods_first_and_last_days_follow_its_label(period: str, first: str, last: str) -> None:
    assert span(period) == (first, last)
    assert start_date(period).dtype == np.dtype("datetime64[D]")
    assert end_date(period).dtype == np.dtype("datetime64[D]")


# Q27 is August 2027, a month and not a quarter: a quarter always leads with its number.
def test_q_alone_is_august_and_a_quarter_leads_with_its_number() -> None:
    assert span("Q27") == ("2027-08-01", "2027-08-31")
    assert span("3Q27") == ("2027-07-01", "2027-09-30")


def test_the_twelve_month_letters_are_the_twelve_months_in_either_case() -> None:
    for place, letter in enumerate(MONTH_LETTERS):
        first, after = period_months(f"{letter}26")
        assert str(first) == f"2026-{place + 1:02d}"
        assert after == first + np.timedelta64(1, "M")
        assert period_months(f"{letter.lower()}26") == (first, after)


# --- what is refused ----------------------------------------------------------


@pytest.mark.parametrize(
    "period",
    [
        "W8-W9",
        "W8",
        "F2026",
        "Q1 27",
        "5Q27",
        "0Q27",
        "1Q 27",
        "F26 ",
        " F26",
        "F26 -Z28",
        "F26-",
        "-F26",
        "F26--Z28",
        "F26-Z28-F29",
        "Jan26",
        "I26",
        "A26",
        "CAL2028",
        "CA28",
        "CALS28",
        "WS28",
        "F",
        "26",
        "F2",
        "FQ27",
    ],
    ids=[
        "one-digit years in a range",
        "a one-digit year",
        "a four-digit year",
        "a quarter with a space",
        "a fifth quarter",
        "a zeroth quarter",
        "a quarter split by a space",
        "a trailing space",
        "a leading space",
        "a space before the hyphen",
        "an empty right end",
        "an empty left end",
        "two hyphens together",
        "three labels",
        "a month by name",
        "I, which the exchanges skip",
        "a letter that is no month",
        "a four-digit calendar year",
        "CA for CAL",
        "CALS",
        "WS",
        "a letter alone",
        "a year alone",
        "a one-digit year after a letter",
        "a letter where the quarter number should be",
    ],
)
def test_anything_but_the_forms_is_refused_naming_the_whole_expression(period: str) -> None:
    message = f"period is {period!r}, expected {FORMS}"
    for read in (start_date, end_date):
        with pytest.raises(ValueError) as failure:
            read(period)
        assert str(failure.value) == message


@pytest.mark.parametrize(
    "period",
    ["Z28-F26", "CAL28-F28", "G26-F26", "W29-S29", "S28-1Q28", "CAL27-4Q26"],
    ids=[
        "the right end before the left",
        "the right end ending before the left does",
        "two months the wrong way round",
        "a winter then the summer that began before it",
        "a summer then the quarter that began before it",
        "a year then the quarter before it",
    ],
)
def test_a_range_whose_right_end_starts_or_ends_before_the_left_is_refused(period: str) -> None:
    for read in (start_date, end_date):
        with pytest.raises(ValueError) as failure:
            read(period)
        assert str(failure.value) == (
            f"period is {period!r}, expected range endpoints in chronological order"
        )


def test_the_forms_message_names_every_form() -> None:
    assert FORMS == (
        "a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28"
    )


# --- the general rules --------------------------------------------------------


# Any month of the horizon: its first day is the first of the month, its last the day before the
# next month's first, 28 to 31 days long, in either case; and the range from it to any month on
# or after it runs from its first day to that month's last.
@given(
    month=st.integers(0, 11),
    year=st.integers(0, 99),
    lower=st.booleans(),
    later=st.integers(0, 200),
)
def test_any_month_and_any_range_of_months_are_whole_months(
    month: int, year: int, lower: bool, later: int
) -> None:
    letter = MONTH_LETTERS[month]
    code = (letter.lower() if lower else letter) + f"{year:02d}"
    first = np.datetime64(f"{2000 + year}-{month + 1:02d}", "M")
    assert start_date(code) == first.astype("datetime64[D]")
    assert end_date(code) == (first + np.timedelta64(1, "M")).astype(
        "datetime64[D]"
    ) - np.timedelta64(1, "D")
    assert 28 <= int((end_date(code) - start_date(code)).astype(np.int64)) + 1 <= 31
    last_month = first + np.timedelta64(later, "M")
    if last_month < np.datetime64("2100-01", "M"):
        year_after, place = divmod(int(last_month.astype(np.int64)), 12)
        right = f"{MONTH_LETTERS[place]}{(1970 + year_after) % 100:02d}"
        assert start_date(f"{code}-{right}") == start_date(code)
        assert end_date(f"{code}-{right}") == end_date(right)


# Any quarter, year, winter and summer: three, twelve, five and seven months long, from the month
# the form names, and a range of two labels is the left's start and the right's end.
@given(year=st.integers(0, 99), quarter=st.integers(1, 4))
def test_the_strips_are_their_months_long(year: int, quarter: int) -> None:
    yy = f"{year:02d}"
    first, after = period_months(f"{quarter}Q{yy}")
    assert str(first) == f"{2000 + year}-{3 * (quarter - 1) + 1:02d}"
    assert after - first == np.timedelta64(3, "M")
    first, after = period_months(f"CAL{yy}")
    assert str(first) == f"{2000 + year}-01" and after - first == np.timedelta64(12, "M")
    first, after = period_months(f"W{yy}")
    assert str(first) == f"{2000 + year}-11" and after - first == np.timedelta64(5, "M")
    first, after = period_months(f"S{yy}")
    assert str(first) == f"{2000 + year}-04" and after - first == np.timedelta64(7, "M")
    assert period_months(f"1Q{yy}-CAL{yy}") == (
        period_months(f"1Q{yy}")[0],
        period_months(f"CAL{yy}")[1],
    )
    if quarter > 1:  # a later quarter starts after its year does, so the range is refused
        with pytest.raises(ValueError, match="chronological order"):
            period_months(f"{quarter}Q{yy}-CAL{yy}")
