"""A date shifted by a text offset: the ticket's worked answers, the signed zeros, the suffixes in
any case, a count with leading zeros, the sheet's calendar as the bound either side, and
everything else refused naming the offset; the round trip of business days from an open day. Since
#181 a chain of instructions, compound-date-offsets.md: the requested chain through a holiday, the
ticket's answers, a chain as its instructions in turn, and a chain malformed late refused whole,
naming where. Since holiday-keys.md the calendar is chosen by key from a collection: one name,
a union of several, and the refusals of a key."""

import numpy as np
import pytest
from holiday_fixtures import closed_on, holding
from hypothesis import given
from hypothesis import strategies as st

from catalyst.index_definitions.date_offsets import (
    FORMS,
    MOST_DIGITS,
    Instruction,
    Unit,
    read_offset,
    shift_date,
)
from catalyst.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from catalyst.index_definitions.holiday_calendars import collect_holiday_calendars
from catalyst.index_definitions.sheet_days import SHEET_FIRST_DAY, SHEET_LAST_DAY
from catalyst.instrumentation.work_counts import WorkCounter


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


# The ticket's synthetic calendar: Monday 12 October 2026 closed, and nothing else.
SYNTHETIC = closed_on(np.array(["2026-10-12"], dtype="datetime64[D]"))
# The compound ticket's calendar H: Friday 25 December 2026 closed, and nothing else.
H = closed_on(np.array(["2026-12-25"], dtype="datetime64[D]"))


def shift_on(date: np.datetime64, offset: str, calendar: HolidayCalendar | None) -> np.datetime64:
    """shift_date on a calendar the test holds: its name the key and a collection of that one
    calendar what the key selects from; no key and no collection for none."""
    key = None if calendar is None else calendar.name
    return shift_date(date, offset, key, holding(calendar), WorkCounter())


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
    shifted = shift_on(day(date), offset, calendar)
    assert shifted == day(expected)
    assert shifted.dtype == np.dtype("datetime64[D]")


def test_more_of_the_same_rules() -> None:
    assert shift_on(day("2027-01-31"), "+1em", None) == day("2027-02-28")  # no leap day
    assert shift_on(day("2026-10-08"), "+3bd", SYNTHETIC) == day("2026-10-14")  # over the holiday
    assert shift_on(day("2026-10-15"), "-3bd", SYNTHETIC) == day("2026-10-09")
    assert shift_on(day("2026-10-09"), "+10bd", None) == day("2026-10-23")  # two weekends
    for offset in ("+1Bd", "+1bD", "-2Cd", "+1EM", "-1Em"):
        assert shift_on(day("2026-10-09"), offset, None) == shift_on(
            day("2026-10-09"), offset.lower(), None
        )
    for offset in ("+0bd", "-0bd", "+0cd", "-0cd", "+000bd"):
        assert shift_on(day("2026-10-11"), offset, SYNTHETIC) == day("2026-10-11")  # a Sunday
    for offset in ("+0em", "-0em", "+00em"):
        assert shift_on(day("2026-10-11"), offset, None) == day("2026-10-31")


# --- the sheet's calendar bounds the result -------------------------------------------------


def test_the_last_day_of_the_sheet_keeps_its_month_end_and_nothing_past_it() -> None:
    assert shift_on(SHEET_LAST_DAY, "+0em", None) == SHEET_LAST_DAY
    assert shift_on(SHEET_FIRST_DAY, "+0cd", None) == SHEET_FIRST_DAY
    assert shift_on(SHEET_FIRST_DAY, "+2958404cd", None) == SHEET_LAST_DAY  # end to end
    assert shift_on(SHEET_LAST_DAY, "-2958404cd", None) == SHEET_FIRST_DAY


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
        shift_on(day(date), offset, None)
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
            shift_on(day("2026-10-09"), offset, None)
        assert str(refused.value) == (
            f"offset has a count of {digits} digits, expected at most {MOST_DIGITS}; the sheet's "
            "calendar runs 1900-03-01 to 9999-12-31"
        )
    # Seven digits are read, leading zeros and all, and held to the calendar like any count.
    assert shift_on(day("2026-10-09"), "+00000001234567cd", None) == day("5406-11-26")


def test_leading_zeros_are_dropped_before_the_count_is_read() -> None:
    # Five thousand leading zeros are no digits of the count: the digits after them are read,
    # none after them is zero, and eight after them are refused by those eight; nothing is ever
    # converted whole, so no count runs into Python's own limit on the digits it converts.
    zeros = "0" * 5000
    assert shift_on(day("2026-10-09"), "+" + zeros + "1cd", None) == day("2026-10-10")
    assert shift_on(day("2026-10-09"), "-" + zeros + "1bd", SYNTHETIC) == day("2026-10-08")
    assert shift_on(day("2026-10-09"), "+" + zeros + "1em", None) == day("2026-11-30")
    assert shift_on(day("2026-10-09"), "+" + zeros + "bd", SYNTHETIC) == day("2026-10-09")
    assert shift_on(day("2026-10-09"), "-" + zeros + "cd", None) == day("2026-10-09")
    assert shift_on(day("2026-10-09"), "+" + zeros + "em", None) == day("2026-10-31")
    with pytest.raises(ValueError) as refused:
        shift_on(day("2026-10-09"), "+" + zeros + "12345678cd", None)
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
        " +1bd",
        "+ 1bd",
        "+1 bd",
        "+bd",
        "+1",
        "bd",
        "",
        "++1bd",
        "+-1bd",
        "+1b",
        "+\N{ARABIC-INDIC DIGIT ONE}bd",  # no ASCII digit, however it reads
        "1",
    ],
)
def test_anything_else_is_refused_naming_the_offset_and_the_form(offset: str) -> None:
    with pytest.raises(ValueError) as refused:
        shift_on(day("2026-10-09"), offset, SYNTHETIC)
    assert str(refused.value) == f"offset is {offset!r}, expected {FORMS}"


# Past the first instruction the reading names where it stood and the text from there, so a
# chain malformed late fails whole: a space, a letter, a sign on its own, a second instruction
# with no unit or a decimal, a digit that is no ASCII digit, a bracket.
@pytest.mark.parametrize(
    ("offset", "at", "rest"),
    [
        ("+1bd ", 5, " "),
        ("+1bdd", 5, "d"),
        ("+1BDX", 5, "X"),
        ("+1bd+", 5, "+"),
        ("+1bd-", 5, "-"),
        ("+1bd+2xd", 5, "+2xd"),
        ("+1bd+2xd+1bd", 5, "+2xd+1bd"),
        ("+1bd 2cd", 5, " 2cd"),
        ("+1bd+1.5cd", 5, "+1.5cd"),
        ("+1bd+\N{ARABIC-INDIC DIGIT ONE}bd", 5, "+\N{ARABIC-INDIC DIGIT ONE}bd"),
        ("+3em+25cd-1bd+1bd)", 18, ")"),
    ],
)
def test_a_chain_malformed_late_is_refused_whole_naming_where(
    offset: str, at: int, rest: str
) -> None:
    with pytest.raises(ValueError) as refused:
        shift_on(day("2026-10-09"), offset, SYNTHETIC)
    assert str(refused.value) == (
        f"offset is {offset!r}, expected {FORMS}; from character {at}, {rest!r} begins with no "
        "instruction"
    )


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
    forward = shift_on(anchor, f"+{count}bd", calendar)
    assert np.is_busday(forward, holidays=holidays)
    assert np.busday_count(anchor, forward, holidays=holidays) == count
    assert shift_on(forward, f"-{count}bd", calendar) == anchor


@given(st.integers(min_value=0, max_value=40_000), st.integers(min_value=-600, max_value=600))
def test_a_month_end_is_the_last_day_of_the_month_the_count_names(days_on: int, count: int) -> None:
    anchor = day("1960-01-01") + np.timedelta64(
        days_on, "D"
    )  # to 2069, 600 months either way inside
    shifted = shift_on(anchor, f"{'+' if count >= 0 else '-'}{abs(count)}em", None)
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
    assert shift_on(anchor, offset, SYNTHETIC) == anchor + np.timedelta64(count, "D")
    assert shift_on(anchor, offset, None) == anchor + np.timedelta64(count, "D")


# --- a chain of instructions, compound-date-offsets.md -------------------------------------------


def test_the_requested_chain_steps_through_the_holiday() -> None:
    # From 12 August 2026 on H: the end of the month three ahead, 30 November; 25 calendar days on,
    # Christmas Day, which H closes; the business day before, Thursday the 24th; and the one after
    # it, which skips the closed Friday and the weekend to Monday the 28th. Without H the Friday
    # is open and stands.
    start = day("2026-08-12")
    assert shift_on(start, "+3em", H) == day("2026-11-30")
    assert shift_on(start, "+3em+25cd", H) == day("2026-12-25")
    assert shift_on(start, "+3em+25cd-1bd", H) == day("2026-12-24")
    assert shift_on(start, "+3em+25cd-1bd+1bd", H) == day("2026-12-28")
    assert shift_on(start, "+3em+25cd-1bd+1bd", None) == day("2026-12-25")


@pytest.mark.parametrize(
    ("date", "offset", "calendar", "expected"),
    [
        ("2026-08-12", "+3em+25cd-1bd+1bd", None, "2026-12-25"),
        ("2026-08-12", "+003EM+025cD-01BD+001bd", H, "2026-12-28"),  # zeros and cases, as one
        ("2026-10-09", "-1bd+1bd", None, "2026-10-09"),  # an open day comes back to itself
        ("2026-10-10", "-1bd+1bd", None, "2026-10-12"),  # a closed day moves to the next open
        ("2026-01-30", "+1cd+0em", None, "2026-01-31"),
        ("2026-01-30", "+0em+1cd", None, "2026-02-01"),  # the order is the rule
        ("2028-01-31", "+1em+1cd", None, "2028-03-01"),
        ("2026-10-10", "+0bd+0cd", None, "2026-10-10"),
        ("2026-10-09", "+1cd", None, "2026-10-10"),  # a Saturday, and no roll is added
    ],
)
def test_the_compound_tickets_answers(
    date: str, offset: str, calendar: HolidayCalendar | None, expected: str
) -> None:
    assert shift_on(day(date), offset, calendar) == day(expected)


def test_an_offset_is_read_whole_into_its_instructions() -> None:
    assert read_offset("offset", "+003EM+025cD-01BD+001bd") == (
        Instruction("+003EM", Unit.MONTH_ENDS, 3),
        Instruction("+025cD", Unit.CALENDAR_DAYS, 25),
        Instruction("-01BD", Unit.BUSINESS_DAYS, -1),
        Instruction("+001bd", Unit.BUSINESS_DAYS, 1),
    )
    assert read_offset("offset", "-0cd") == (Instruction("-0cd", Unit.CALENDAR_DAYS, 0),)


def test_a_count_of_too_many_digits_in_a_chain_names_its_instruction() -> None:
    for offset, digits, k, text in (
        ("+1bd+99999999cd", 8, 2, "+99999999cd"),
        ("+99999999cd+1bd", 8, 1, "+99999999cd"),
        ("+1bd+" + "9" * 5000 + "em+1cd", 5000, 2, "+" + "9" * 5000 + "em"),
    ):
        with pytest.raises(ValueError) as refused:
            shift_on(day("2026-10-09"), offset, None)
        assert str(refused.value) == (
            f"offset has a count of {digits} digits in instruction {k}, {text!r}, expected at most "
            f"{MOST_DIGITS}; the sheet's calendar runs 1900-03-01 to 9999-12-31"
        )


def test_an_instruction_that_leaves_the_sheet_is_refused_whatever_a_later_one_would_do() -> None:
    # The first day made outside the sheet's calendar is the refusal, named with its instruction
    # when the offset has more than one, though the next instruction would come back inside; the
    # sheet's last day keeps its own month end, the month after being reached and a day taken
    # before the rule applies.
    for date, offset, made, k, text in (
        ("9999-12-31", "+1cd-1cd", "10000-01-01", 1, "+1cd"),
        ("1900-03-01", "-1cd+1cd", "1900-02-28", 1, "-1cd"),
        ("2026-10-09", "+1bd+9999999cd", "29405-11-06", 2, "+9999999cd"),
        ("9999-12-31", "+0em+1em-1em", "10000-01-31", 2, "+1em"),
    ):
        with pytest.raises(ValueError) as refused:
            shift_on(day(date), offset, None)
        assert str(refused.value) == (
            f"date {date} shifted by {offset!r} is {made} at instruction {k}, {text!r}, outside "
            "the sheet's calendar, 1900-03-01 to 9999-12-31"
        )
    assert shift_on(SHEET_LAST_DAY, "+0em+0em", None) == SHEET_LAST_DAY
    assert shift_on(SHEET_LAST_DAY, "-1cd+1cd", None) == SHEET_LAST_DAY


@given(
    st.lists(
        st.tuples(
            st.sampled_from("+-"),
            st.integers(min_value=0, max_value=40),
            st.sampled_from(["bd", "cd", "em", "BD", "Cd", "eM"]),
        ),
        min_size=1,
        max_size=6,
    ),
    st.integers(min_value=0, max_value=20_000),
    st.booleans(),
)
def test_a_chain_is_its_instructions_applied_in_turn(
    steps: list[tuple[str, int, str]], days_on: int, with_calendar: bool
) -> None:
    anchor = day("2026-01-05") + np.timedelta64(days_on, "D")
    calendar = SYNTHETIC if with_calendar else None
    one_by_one = anchor
    for sign, count, unit in steps:
        one_by_one = shift_on(one_by_one, f"{sign}{count}{unit}", calendar)
    assert shift_on(anchor, "".join(f"{s}{n}{u}" for s, n, u in steps), calendar) == one_by_one


# --- the calendar by key, holiday-keys.md -----------------------------------------------------
NYFED = holiday_calendar("NYFED", np.array(["2026-11-26"], dtype="datetime64[D]"))
LON = holiday_calendar("LON", np.array(["2026-11-27", "2026-11-30"], dtype="datetime64[D]"))
BOTH = collect_holiday_calendars((NYFED, LON), WorkCounter())


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (None, "2026-11-26"),  # Monday to Friday with no holidays
        ("NYFED", "2026-11-27"),  # Thursday closed
        ("LON", "2026-11-26"),  # Friday and Monday closed, neither reached
        ("NYFED+LON", "2026-12-01"),  # closed when either is: Thursday, Friday and Monday
        ("LON+NYFED", "2026-12-01"),  # the same calendar, the names in any order
    ],
)
def test_the_key_selects_the_calendar_business_days_skip(key: str | None, expected: str) -> None:
    # The ticket's hand-worked table: one business day on from Wednesday 25 November 2026.
    assert shift_date(day("2026-11-25"), "+1bd", key, BOTH, WorkCounter()) == day(expected)


def test_a_key_left_out_reads_no_collection_and_a_key_needs_one() -> None:
    # A collection nothing selects from is read for nothing; a key with none is refused by the
    # argument, in the one sentence every reader of a key shares.
    assert shift_date(day("2026-11-25"), "+1bd", None, BOTH, WorkCounter()) == day("2026-11-26")
    assert shift_date(day("2026-11-25"), "+1bd", None, None, WorkCounter()) == day("2026-11-26")
    with pytest.raises(ValueError) as caught:
        shift_date(day("2026-11-25"), "+1bd", "NYFED", None, WorkCounter())
    assert str(caught.value) == (
        "holiday_calendars is missing, expected a _CollectHolidayCalendars collection, which "
        "holiday_key selects a calendar from"
    )


@pytest.mark.parametrize(
    ("key", "message"),
    [
        (
            "NYMX",
            "holiday_key is 'NYMX', expected names of the collection's calendars, 'NYFED' and "
            "'LON'; it holds no 'NYMX'",
        ),
        (
            "nyfed",  # matched exactly, case and all
            "holiday_key is 'nyfed', expected names of the collection's calendars, 'NYFED' and "
            "'LON'; it holds no 'nyfed'",
        ),
        (
            "NYFED+TOK",
            "holiday_key is 'NYFED+TOK', expected names of the collection's calendars, 'NYFED' "
            "and 'LON'; it holds no 'TOK'",
        ),
        (
            "NYFED + LON",
            "holiday_key is 'NYFED + LON', expected a calendar's name, or several joined by "
            "'+', each with no whitespace around it",
        ),
        (
            "NYFED+",
            "holiday_key is 'NYFED+', expected a calendar's name, or several joined by '+'; a "
            "name is missing",
        ),
        (
            "LON+LON",
            "holiday_key is 'LON+LON', expected a calendar's name, or several joined by '+', "
            "each once; 'LON' is given twice",
        ),
    ],
)
def test_a_key_is_refused_by_the_rule_every_key_has(key: str, message: str) -> None:
    with pytest.raises(ValueError) as caught:
        shift_date(day("2026-11-25"), "+1bd", key, BOTH, WorkCounter())
    assert str(caught.value) == message


def test_the_offset_is_read_before_the_key() -> None:
    # Two faults at once: the offset's is the message, the arguments read in their order.
    with pytest.raises(ValueError) as caught:
        shift_date(day("2026-11-25"), "tomorrow", "NYMX", BOTH, WorkCounter())
    assert str(caught.value) == f"offset is 'tomorrow', expected {FORMS}"


def test_the_work_of_a_key_is_counted_on_every_call() -> None:
    # No key counts nothing; one name binds one key and makes nothing; several add the union's
    # own counts, on each call.
    def counted(key: str | None) -> dict[str, int]:
        counter = WorkCounter()
        shift_date(day("2026-11-25"), "+1bd", key, BOTH, counter)
        return counter.freeze().as_dict()

    assert counted(None) == {}
    assert counted("NYFED") == {"holiday_keys_bound": 1}
    assert counted("NYFED+LON") == {
        "calendars_combined": 2,
        "holidays_read": 3,
        "holidays_kept": 3,
        "holiday_keys_bound": 1,
    }
