"""The market definitions through the seam: what each creator shows for a right and a wrong
call, and that its handle resolves to the object the seam kept."""

import re
from typing import cast

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle
from goosedove.excel.probes import probe
from goosedove.market_definitions.expiry_schedule import ExpirySchedule
from goosedove.market_definitions.holiday_calendar import HolidayCalendar

# The first three contracts of the page's sample as the sheet sends them: codes as text, dates as
# serials, 19 May, 22 June and 21 July 2026 for the futures and a few days earlier for the options.
CODES = Cells.from_rows([["m26"], ["n26"], ["q26"]])
FUTURES = Cells.from_rows([[46161.0], [46195.0], [46224.0]])
OPTIONS = Cells.from_rows([[46156.0], [46189.0], [46219.0]])
HANDLE = re.compile(r"expiry_schedule:[0-9a-f]{6}:([0-9]{6})")

# The first three days of the calendar page's sample as the sheet sends them: serials for
# 1 January, 19 January and 16 February 2026.
HOLIDAYS = Cells.from_rows([[46023.0], [46041.0], [46069.0]])
CALENDAR = re.compile(r"holiday_calendar:[0-9a-f]{6}:([0-9]{6})")


# The library has no consumer of a schedule yet, so this hidden reader proves that a handle
# resolves to the schedule the seam kept, with its columns as they arrived.
@probe
def ReadExpirySchedule(schedule: Handle[ExpirySchedule]) -> str:
    futures = " ".join(str(day) for day in schedule.future_expiry)
    options = (
        "none"
        if schedule.option_expiry is None
        else " ".join(str(day) for day in schedule.option_expiry)
    )
    return f"{' '.join(schedule.codes)} | {futures} | {options}"


def a_schedule(*columns: object) -> str:
    text = bridge.call("CreateExpirySchedule", list(columns))
    assert isinstance(text, str) and HANDLE.fullmatch(text), text
    return text


def number(text: str, handle: re.Pattern[str] = HANDLE) -> int:
    match = handle.fullmatch(text)
    assert match, text
    return int(match.group(1))


def test_a_schedule_is_created_from_three_columns_and_read_back_through_its_handle() -> None:
    assert bridge.call("ReadExpirySchedule", [a_schedule(CODES, FUTURES, OPTIONS)]) == (
        "m26 n26 q26 | 2026-05-19 2026-06-22 2026-07-21 | 2026-05-14 2026-06-16 2026-07-16"
    )


def test_the_third_column_left_out_is_an_index_without_options() -> None:
    assert bridge.call("ReadExpirySchedule", [a_schedule(CODES, FUTURES, MISSING)]) == (
        "m26 n26 q26 | 2026-05-19 2026-06-22 2026-07-21 | none"
    )


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [CODES, Cells.from_rows([[46161.0], [46195.0]]), OPTIONS],
            "#ERROR CreateExpirySchedule: ValueError: future_expiry has 2 dates, expected 3, "
            "one per future_code",
        ),
        (
            [CODES, FUTURES, Cells.from_rows([[46156.0], [None], [46219.0]])],
            "#ERROR CreateExpirySchedule: option_expiry cell (2, 1) is blank, expected date",
        ),
        (
            [CODES, FUTURES, None],
            "#ERROR CreateExpirySchedule: option_expiry is blank, expected column of dates",
        ),
        (
            [Cells.from_rows([["m26"], [46161.0], ["q26"]]), FUTURES, MISSING],
            "#ERROR CreateExpirySchedule: future_code cell (2, 1) is number 46161.0, expected text",
        ),
        (
            [CODES, Cells.from_rows([[46161.0, 46195.0, 46224.0]]), MISSING],
            "#ERROR CreateExpirySchedule: future_expiry is 1x3 array, expected column of dates",
        ),
        (
            [CODES, MISSING, MISSING],
            "#ERROR CreateExpirySchedule: future_expiry is missing, expected column of dates",
        ),
    ],
    ids=[
        "a futures column one row short",
        "a blank in the options column",
        "a blank cell where the options column should be",
        "a number among the codes",
        "a row of dates",
        "the futures column left out",
    ],
)
def test_a_schedule_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("CreateExpirySchedule", args) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap.
def test_a_failed_construction_publishes_no_object_and_no_handle() -> None:
    before = number(a_schedule(CODES, FUTURES, MISSING))
    short = Cells.from_rows([[46161.0], [46195.0]])
    assert bridge.call("CreateExpirySchedule", [CODES, short, OPTIONS]) == (
        "#ERROR CreateExpirySchedule: ValueError: future_expiry has 2 dates, expected 3, "
        "one per future_code"
    )
    assert number(a_schedule(CODES, FUTURES, MISSING)) == before + 1


def test_a_handle_of_another_kind_is_not_a_schedule() -> None:
    other = cast(str, bridge.call("CreateValuationDate", [46161.0, 0.5]))
    assert bridge.call("ReadExpirySchedule", [other]) == (
        f"#ERROR ReadExpirySchedule: schedule is valuation date handle {other!r}, "
        "expected expiry schedule handle"
    )


# --- CreateHolidayCalendar ------------------------------------------------------


# The library has no consumer of a calendar yet, so this hidden reader proves that a handle
# resolves to the calendar the seam kept, with its column as it arrived.
@probe
def ReadHolidayCalendar(calendar: Handle[HolidayCalendar]) -> str:
    return " ".join(str(day) for day in calendar.holiday)


def a_calendar(column: object) -> str:
    text = bridge.call("CreateHolidayCalendar", [column])
    assert isinstance(text, str) and CALENDAR.fullmatch(text), text
    return text


def test_a_calendar_is_created_from_one_column_and_read_back_through_its_handle() -> None:
    assert bridge.call("ReadHolidayCalendar", [a_calendar(HOLIDAYS)]) == (
        "2026-01-01 2026-01-19 2026-02-16"
    )


# A single cell is a column of one, so a market closed on one day needs no range.
def test_a_single_cell_is_a_calendar_of_one_day() -> None:
    assert bridge.call("ReadHolidayCalendar", [a_calendar(46023.0)]) == "2026-01-01"


@pytest.mark.parametrize(
    ("column", "text"),
    [
        (
            Cells.from_rows([[46023.0], [None], [46069.0]]),
            "#ERROR CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date",
        ),
        (
            Cells.from_rows([[46023.0], ["Christmas"], [46069.0]]),
            "#ERROR CreateHolidayCalendar: holiday cell (2, 1) is text 'Christmas', expected date",
        ),
        (
            Cells.from_rows([[46023.0], [46041.5], [46069.0]]),
            "#ERROR CreateHolidayCalendar: holiday cell (2, 1) is number 46041.5, expected date",
        ),
        (
            Cells.from_rows([[46023.0, 46041.0, 46069.0]]),
            "#ERROR CreateHolidayCalendar: holiday is 1x3 array, expected column of dates",
        ),
        (None, "#ERROR CreateHolidayCalendar: holiday is blank, expected column of dates"),
        (MISSING, "#ERROR CreateHolidayCalendar: holiday is missing, expected column of dates"),
    ],
    ids=[
        "a blank in the column",
        "text in the column",
        "a date with a time",
        "a row of dates",
        "a blank cell where the column should be",
        "the column left out",
    ],
)
def test_a_calendar_that_cannot_be_made_says_why(column: object, text: str) -> None:
    assert bridge.call("CreateHolidayCalendar", [column]) == text


# A rejected column stops the call before the function runs, so nothing is published and the
# publication number does not move.
def test_a_rejected_column_publishes_no_object_and_no_handle() -> None:
    before = number(a_calendar(HOLIDAYS), CALENDAR)
    assert bridge.call("CreateHolidayCalendar", [Cells.from_rows([[46023.0], [None]])]) == (
        "#ERROR CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date"
    )
    assert number(a_calendar(HOLIDAYS), CALENDAR) == before + 1


def test_a_handle_of_another_kind_is_not_a_calendar() -> None:
    other = a_schedule(CODES, FUTURES, MISSING)
    assert bridge.call("ReadHolidayCalendar", [other]) == (
        f"#ERROR ReadHolidayCalendar: calendar is expiry schedule handle {other!r}, "
        "expected holiday calendar handle"
    )
