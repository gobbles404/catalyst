"""Periods read from their labels: a month, a quarter, since #182 a half-year, a calendar year, a
winter, a summer and a range of two, their first and last calendar days, the letters in either
case, and everything else refused naming the whole expression; and the balance of any of them from
a valuation day, the later of that day and the label's first day to the label's last, a period that
has ended refused."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.index_definitions.contract_codes import MONTH_LETTERS
from goosedove.index_definitions.periods import (
    FORMS,
    balance_of,
    end_date,
    period_months,
    start_date,
)


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
        ("1h27", "2027-01-01", "2027-06-30"),
        ("1H27", "2027-01-01", "2027-06-30"),
        ("2h27", "2027-07-01", "2027-12-31"),
        ("2H27", "2027-07-01", "2027-12-31"),
        ("H27", "2027-03-01", "2027-03-31"),
        ("1H28", "2028-01-01", "2028-06-30"),
        ("1H27-2H27", "2027-01-01", "2027-12-31"),
        ("2h27-1h28", "2027-07-01", "2028-06-30"),
        ("1Q27-1H27", "2027-01-01", "2027-06-30"),
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
        "the first half in lowercase, since #182",
        "the first half in capitals",
        "the second half in lowercase",
        "the second half in capitals",
        "H alone is March, the contract month",
        "a leap-year first half",
        "the two halves of a year, all of the year",
        "a second half to the first half after it",
        "a quarter to the half it begins",
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
        "0H27",
        "3H27",
        "1H7",
        "1H2027",
        " 1H27",
        "1H27 ",
        "1H27x",
        "1HH27",
        "H127",
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
        "a zeroth half",
        "a third half",
        "a half with a one-digit year",
        "a half with a four-digit year",
        "a half with a leading space",
        "a half with a trailing space",
        "a half with trailing text",
        "HH for H",
        "H with a number after it",
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
    [
        "Z28-F26",
        "CAL28-F28",
        "G26-F26",
        "W29-S29",
        "S28-1Q28",
        "CAL27-4Q26",
        "2H27-1H27",
        "1H28-2H27",
    ],
    ids=[
        "the right end before the left",
        "the right end ending before the left does",
        "two months the wrong way round",
        "a winter then the summer that began before it",
        "a summer then the quarter that began before it",
        "a year then the quarter before it",
        "the second half then the first, since #182",
        "a first half then the half before it",
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
        "a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or "
        "F26-Z28"
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
    for half in (1, 2):  # since #182: six months from January or July
        first, after = period_months(f"{half}H{yy}")
        assert str(first) == f"{2000 + year}-{6 * (half - 1) + 1:02d}"
        assert after - first == np.timedelta64(6, "M")
        assert period_months(f"{half}h{yy}") == (first, after)
    assert period_months(f"1H{yy}-2H{yy}") == period_months(f"CAL{yy}")
    assert period_months(f"1Q{yy}-1H{yy}") == period_months(f"1H{yy}")
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


# --- the balance of a period --------------------------------------------------
# trade-periods-and-bal.md slice B gave the balance a reference date held inside the period;
# date-helper-inputs.md, since #173, gives it the valuation day: the balance runs from the later
# of that day and the label's first day to the label's last day, a future period being the whole
# period, a current one running from the day itself, and a period that ended before the day
# refused by both readers, naming the label, the day and the end. An ordinary label reads as
# before whether or not a day is given, so one formula serves a column of both.


@pytest.mark.parametrize(
    ("period", "as_of", "first", "last"),
    [
        ("balv26", "2026-09-20", "2026-10-01", "2026-10-31"),
        ("BALV26", "2026-10-12", "2026-10-12", "2026-10-31"),
        ("BalV26", "2026-10-31", "2026-10-31", "2026-10-31"),
        ("balf26", "2025-12-20", "2026-01-01", "2026-01-31"),
        ("balf26", "2026-01-15", "2026-01-15", "2026-01-31"),
        ("balf26", "2026-01-31", "2026-01-31", "2026-01-31"),
        ("balx26-z26", "2026-11-12", "2026-11-12", "2026-12-31"),
        ("balx26-z26", "2026-10-01", "2026-11-01", "2026-12-31"),
        ("balcal27", "2026-10-12", "2027-01-01", "2027-12-31"),
        ("balx27", "2027-11-12", "2027-11-12", "2027-11-30"),
        ("balcal26", "2026-10-07", "2026-10-07", "2026-12-31"),
        ("BALZ26", "2026-12-15", "2026-12-15", "2026-12-31"),
        ("Bal1Q27", "2027-02-10", "2027-02-10", "2027-03-31"),
        ("BALW29", "2030-01-01", "2030-01-01", "2030-03-31"),
        ("balS28", "2028-10-31", "2028-10-31", "2028-10-31"),
        ("BALZ26", "2026-12-01", "2026-12-01", "2026-12-31"),
        ("BALZ26", "2026-12-12", "2026-12-12", "2026-12-31"),
        ("BALG28", "2028-02-29", "2028-02-29", "2028-02-29"),
        ("BALG28", "2028-02-01", "2028-02-01", "2028-02-29"),
        ("BALG27", "2026-06-30", "2027-02-01", "2027-02-28"),
        ("BALZ26-F27", "2026-12-31", "2026-12-31", "2027-01-31"),
        ("BALW99", "2100-03-15", "2100-03-15", "2100-03-31"),
        ("BAL1H27", "2027-03-15", "2027-03-15", "2027-06-30"),
        ("bal1h27", "2026-10-12", "2027-01-01", "2027-06-30"),
        ("Bal2H27", "2027-12-31", "2027-12-31", "2027-12-31"),
        ("BAL2h27-1H28", "2027-10-01", "2027-10-01", "2028-06-30"),
    ],
    ids=[
        "the ticket's October from September, the whole month",
        "the ticket's October from the 12th, in capitals",
        "the ticket's October on its last day, one day, in mixed case",
        "the ticket's January from December, the whole month",
        "the ticket's January from the 15th",
        "the ticket's January on its last day, one day",
        "the ticket's November-December strip from 12 November",
        "the same strip from October, the whole strip",
        "the ticket's calendar year from the October before, the whole year",
        "slice B's November balance",
        "slice B's balance of a year",
        "slice B's December balance, in capitals",
        "a quarter in mixed case",
        "a winter from a day of its second year",
        "a summer on its last day, one day",
        "December on its first day, the whole month",
        "a Saturday, a day like any other",
        "the leap day, one day",
        "a leap February from its first day, 29 days",
        "a February without a leap day, from the summer before",
        "a year-end range from its last December day",
        "the last winter, into the next century",
        "the ticket's half from mid-March, since #182",
        "a future half, the whole of it, in lowercase",
        "a half on its last day, one day, in mixed case",
        "a range of halves from a day inside it",
    ],
)
def test_the_balance_of_a_period_runs_from_the_later_of_the_valuation_day_and_its_first_day(
    period: str, as_of: str, first: str, last: str
) -> None:
    assert str(start_date(period, day(as_of))) == first
    assert str(end_date(period, day(as_of))) == last
    assert start_date(period, day(as_of)).dtype == np.dtype("datetime64[D]")


def test_an_ordinary_label_reads_the_same_with_a_valuation_day_or_without() -> None:
    as_of = day("2026-12-15")
    for period in ("Z26", "z26", "1Q27", "CAL28", "W29", "F26-Z28", "F26"):
        assert span(period) == (str(start_date(period, as_of)), str(end_date(period, as_of)))
    assert balance_of("Z26") is None
    assert balance_of("balz26") == "z26" and balance_of("BALZ26") == "Z26"
    assert balance_of("BAL") == "" and balance_of("BALBALZ26") == "BALZ26"


ENDED = "expected a valuation day on or before the period's last day"


@pytest.mark.parametrize(
    ("period", "as_of", "message"),
    [
        (
            "BALZ26",
            None,
            "valuation_date is missing, expected a valuation-date handle with 'BALZ26', whose day "
            "starts the balance of a period",
        ),
        (
            "balx26-z26",
            None,
            "valuation_date is missing, expected a valuation-date handle with 'balx26-z26', whose "
            "day starts the balance of a period",
        ),
        (
            "balv26",
            "2026-11-01",
            f"valuation_date is 2026-11-01, after 'balv26' ended on 2026-10-31, {ENDED}",
        ),
        (
            "balf26",
            "2026-02-01",
            f"valuation_date is 2026-02-01, after 'balf26' ended on 2026-01-31, {ENDED}",
        ),
        (
            "BALZ26",
            "2027-01-01",
            f"valuation_date is 2027-01-01, after 'BALZ26' ended on 2026-12-31, {ENDED}",
        ),
        (
            "balx26-z26",
            "2027-01-05",
            f"valuation_date is 2027-01-05, after 'balx26-z26' ended on 2026-12-31, {ENDED}",
        ),
        (
            "BALW29",
            "2030-04-01",
            f"valuation_date is 2030-04-01, after 'BALW29' ended on 2030-03-31, {ENDED}",
        ),
        (
            "BALG28",
            "2028-03-01",
            f"valuation_date is 2028-03-01, after 'BALG28' ended on 2028-02-29, {ENDED}",
        ),
        (
            "BAL1H27",
            "2027-07-01",
            f"valuation_date is 2027-07-01, after 'BAL1H27' ended on 2027-06-30, {ENDED}",
        ),
    ],
    ids=[
        "no day for a month",
        "no day for a strip",
        "the day after the ticket's October",
        "the day after the ticket's January",
        "the day after December",
        "a day after a strip",
        "the day after a winter",
        "the day after a leap February",
        "the day after a first half, since #182",
    ],
)
def test_a_balance_without_its_day_or_of_a_period_that_has_ended_is_refused(
    period: str, as_of: str | None, message: str
) -> None:
    # Both readers refuse, so asking for an end cannot hide a period that has ended, which would
    # otherwise read as a one-day deal at the month's end.
    for read in (start_date, end_date):
        with pytest.raises(ValueError) as failure:
            read(period, None if as_of is None else day(as_of))
        assert str(failure.value) == message


@pytest.mark.parametrize(
    "period",
    ["BAL", "BALBALZ26", "BALZ2026", "BAL-Z26", "BALZ26-", "BALQ1 27", "BALJan26", "BAL Z26"],
    ids=[
        "the prefix alone",
        "the prefix twice",
        "a four-digit year under the prefix",
        "a hyphen after the prefix",
        "an empty right end under the prefix",
        "a quarter with a space under the prefix",
        "a month by name under the prefix",
        "a space after the prefix",
    ],
)
def test_the_balance_of_no_label_is_refused_naming_the_whole_expression(period: str) -> None:
    message = f"period is {period!r}, expected {FORMS}"
    for read in (start_date, end_date):
        with pytest.raises(ValueError) as failure:
            read(period, day("2026-12-15"))
        assert str(failure.value) == message


def test_the_balance_of_a_reversed_range_is_refused_as_the_range_is() -> None:
    for read in (start_date, end_date):
        with pytest.raises(ValueError) as failure:
            read("BALZ28-F26", day("2026-12-15"))
        assert str(failure.value) == (
            "period is 'BALZ28-F26', expected range endpoints in chronological order"
        )


# Any month of the horizon and any day from forty before its first to forty after: the balance
# runs from the later of that day and the first to the month's last while the day is on or before
# the last, the whole month from any earlier day, and is refused once the day is past it.
@given(
    month=st.integers(0, 11),
    year=st.integers(0, 99),
    offset=st.integers(-40, 40),
    lower=st.booleans(),
)
def test_the_balance_of_any_month_from_any_day_ends_with_the_month_or_is_refused(
    month: int, year: int, offset: int, lower: bool
) -> None:
    letter = MONTH_LETTERS[month]
    code = (letter.lower() if lower else letter) + f"{year:02d}"
    label = ("bal" if lower else "BAL") + code
    first, last = start_date(code), end_date(code)
    as_of = first + np.timedelta64(offset, "D")
    if as_of <= last:
        assert start_date(label, as_of) == max(as_of, first)
        assert end_date(label, as_of) == last
    else:
        for read in (start_date, end_date):
            with pytest.raises(ValueError, match="ended on"):
                read(label, as_of)
