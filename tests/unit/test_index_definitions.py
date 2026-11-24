"""The index definitions through the seam: what each creator shows for a right and a wrong
call, and that its handle resolves to the object the seam kept."""

import os
import re
from typing import cast

import numpy as np
import pytest
from holiday_fixtures import a_name
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray
from test_create_trades import seam_calendars, seam_key
from test_utilities import read, rows

from catalyst.excel import bridge
from catalyst.excel.bridge import BOOLEAN_CODE, MISSING, NUMBER_CODE, TEXT_CODE, Cells, Handle
from catalyst.index_definitions.contract_specifications import ContractSpecifications
from catalyst.index_definitions.futures_schedule import FuturesSchedule
from catalyst.index_definitions.gas_daily_schedule import GasDailySchedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.index_conventions import IndexConventions
from catalyst.index_definitions.published_schedule import PublishedSchedule
from catalyst_probes import probe

PID = os.getpid()  # leads every handle this Python publishes

# The first three contracts of the page's sample as the sheet sends them: codes as text, dates as
# serials, 19 May, 22 June and 21 July 2026 for the futures and a few days earlier for the options.
CODES = Cells.from_rows([["m26"], ["n26"], ["q26"]])
FUTURES = Cells.from_rows([[46161.0], [46195.0], [46224.0]])
OPTIONS = Cells.from_rows([[46156.0], [46189.0], [46219.0]])
HANDLE = re.compile(r"[0-9]+:futures_schedule:([0-9]+)")

# The first three days of the calendar page's sample as the sheet sends them: serials for
# 1 January, 19 January and 16 February 2026.
HOLIDAYS = Cells.from_rows([[46023.0], [46041.0], [46069.0]])
CALENDAR = re.compile(r"[0-9]+:holiday_calendar:CAL[0-9]+:([0-9]+)")

# The conventions page's sample as the sheet sends it: five texts, an index quoted in dollars per
# barrel, settled in dollars, its quantity a volume stated in barrels.
UNITS = ["DOLLAR", "BBL", "DOLLAR", "VOLUME", "BBL"]
CONVENTIONS = re.compile(r"[0-9]+:index_conventions:([0-9]+)")

# The specifications page's sample as the sheet sends it: the header row, then one row per word
# for a quantity of gas, NYMEX lots and ICE lots, the name and the lot's unit as text and the
# lot size and fees as numbers.
SPECIFICATION_HEADERS = Cells.from_rows(
    [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)
SPECIFICATION_BODY = Cells.from_rows(
    [["NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0], ["ICE NG", 2500.0, "MMBTU", 0.75, 0.5]]
)
GAS = ["DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU"]
SPECIFICATIONS = re.compile(r"[0-9]+:contract_specifications:([0-9]+)")


def days_or_none(days: NDArray[np.datetime64] | None) -> str:
    return "none" if days is None else " ".join(str(day) for day in days)


# The calendar reads a futures schedule, but this hidden reader proves on its own that a handle
# resolves to the schedule the seam kept, with its columns as they arrived, a column left out
# reading none.
@probe
def ReadFuturesSchedule(schedule: Handle[FuturesSchedule]) -> str:
    return (
        f"{' '.join(schedule.codes)} | {days_or_none(schedule.future_expiry)} | "
        f"{days_or_none(schedule.option_expiry)}"
    )


def a_schedule(*columns: object) -> str:
    text = bridge.call("_CreateFuturesSchedule", list(columns))
    assert isinstance(text, str) and HANDLE.fullmatch(text), text
    return text


def number(text: str, handle: re.Pattern[str] = HANDLE) -> int:
    match = handle.fullmatch(text)
    assert match, text
    return int(match.group(1))


def test_a_schedule_is_created_from_three_columns_and_read_back_through_its_handle() -> None:
    assert bridge.call("ReadFuturesSchedule", [a_schedule(CODES, FUTURES, OPTIONS)]) == (
        "m26 n26 q26 | 2026-05-19 2026-06-22 2026-07-21 | 2026-05-14 2026-06-16 2026-07-16"
    )


def test_the_third_column_left_out_is_an_index_without_options() -> None:
    assert bridge.call("ReadFuturesSchedule", [a_schedule(CODES, FUTURES, MISSING)]) == (
        "m26 n26 q26 | 2026-05-19 2026-06-22 2026-07-21 | none"
    )


# A single cell is a column of one, so a schedule of one contract needs no range.
def test_three_single_cells_make_a_one_row_schedule() -> None:
    assert bridge.call("ReadFuturesSchedule", [a_schedule("m26", 46161.0, 46156.0)]) == (
        "m26 | 2026-05-19 | 2026-05-14"
    )


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [CODES, Cells.from_rows([[46161.0], [46195.0]]), OPTIONS],
            "#ERROR _CreateFuturesSchedule: ValueError: future_expiry has 2 dates, expected 3, "
            "one per contract_code",
        ),
        (
            [CODES, FUTURES, Cells.from_rows([[46156.0]])],
            "#ERROR _CreateFuturesSchedule: ValueError: option_expiry has 1 date, expected 3, "
            "one per contract_code",
        ),
        (
            [CODES, Cells.from_rows([[46161.0], [46195.0]]), Cells.from_rows([[46156.0]])],
            "#ERROR _CreateFuturesSchedule: ValueError: future_expiry has 2 dates, expected 3, "
            "one per contract_code",
        ),
        (
            [CODES, FUTURES, Cells.from_rows([[46156.0], [None], [46219.0]])],
            "#ERROR _CreateFuturesSchedule: option_expiry cell (2, 1) is blank, expected date",
        ),
        (
            [CODES, FUTURES, Cells.from_rows([["x"], [46189.0], [46219.0]])],
            "#ERROR _CreateFuturesSchedule: option_expiry cell (1, 1) is text 'x', expected date",
        ),
        (
            [CODES, FUTURES, None],
            "#ERROR _CreateFuturesSchedule: option_expiry is blank, expected column of dates",
        ),
        (
            [CODES, FUTURES, Cells.from_rows([[46156.0, 46189.0, 46219.0]])],
            "#ERROR _CreateFuturesSchedule: option_expiry is 1x3 array, expected column of dates",
        ),
        (
            [Cells.from_rows([["m26"], [46161.0], ["q26"]]), FUTURES, MISSING],
            "#ERROR _CreateFuturesSchedule: contract_code cell (2, 1) is number 46161.0, "
            "expected text",
        ),
        (
            [CODES, Cells.from_rows([[46161.0, 46195.0, 46224.0]]), MISSING],
            "#ERROR _CreateFuturesSchedule: future_expiry is 1x3 array, expected column of dates",
        ),
        (
            [CODES, MISSING, MISSING],
            "#ERROR _CreateFuturesSchedule: future_expiry is missing, expected column of dates",
        ),
        (
            [CODES, FUTURES, OPTIONS, Cells.from_rows([[46162.0], [46196.0], [46225.0]])],
            "#ERROR _CreateFuturesSchedule: expected 3 arguments, got 4",
        ),
    ],
    ids=[
        "a futures column one row short",
        "an options column one row short",
        "both columns short, the futures column named first",
        "a blank in the options column",
        "text in the options column",
        "a blank cell where the options column should be",
        "a row of option dates",
        "a number among the codes",
        "a row of dates",
        "the futures column left out",
        "a fourth column, one argument too many",
    ],
)
def test_a_schedule_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreateFuturesSchedule", args) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap.
def test_a_failed_construction_publishes_no_object_and_no_handle() -> None:
    before = number(a_schedule(CODES, FUTURES, MISSING))
    short = Cells.from_rows([[46161.0], [46195.0]])
    assert bridge.call("_CreateFuturesSchedule", [CODES, short, OPTIONS]) == (
        "#ERROR _CreateFuturesSchedule: ValueError: future_expiry has 2 dates, expected 3, "
        "one per contract_code"
    )
    assert bridge.call("_CreateFuturesSchedule", [CODES, FUTURES, short]) == (
        "#ERROR _CreateFuturesSchedule: ValueError: option_expiry has 2 dates, expected 3, "
        "one per contract_code"
    )
    assert number(a_schedule(CODES, FUTURES, MISSING)) == before + 1


def test_a_handle_of_another_kind_is_not_a_schedule() -> None:
    other = cast(str, bridge.call("_CreateValuationDate", [46161.0, 0.5]))
    assert bridge.call("ReadFuturesSchedule", [other]) == (
        f"#ERROR ReadFuturesSchedule: schedule is valuation date handle {other!r}, "
        "expected futures schedule handle"
    )
    published = cast(str, bridge.call("_CreatePublishedSchedule", ["V26", 46296.0]))
    assert bridge.call("ReadFuturesSchedule", [published]) == (
        f"#ERROR ReadFuturesSchedule: schedule is published schedule handle {published!r}, "
        "expected futures schedule handle"
    )


# --- _CreateHolidayCalendar ------------------------------------------------------


# The library has no consumer of a calendar yet, so this hidden reader proves that a handle
# resolves to the calendar the seam kept, with its column as it arrived.
@probe
def ReadHolidayCalendar(calendar: Handle[HolidayCalendar]) -> str:
    return " ".join(str(day) for day in calendar.holiday)


def a_calendar(column: object) -> str:
    text = bridge.call("_CreateHolidayCalendar", [a_name(), column])
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
            "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date",
        ),
        (
            Cells.from_rows([[46023.0], ["Christmas"], [46069.0]]),
            "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is text 'Christmas', expected date",
        ),
        (
            Cells.from_rows([[46023.0], [46041.5], [46069.0]]),
            "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is number 46041.5, expected date",
        ),
        (
            Cells.from_rows([[46023.0, 46041.0, 46069.0]]),
            "#ERROR _CreateHolidayCalendar: holiday is 1x3 array, expected column of dates",
        ),
        (None, "#ERROR _CreateHolidayCalendar: holiday is blank, expected column of dates"),
        (MISSING, "#ERROR _CreateHolidayCalendar: holiday is missing, expected column of dates"),
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
    assert bridge.call("_CreateHolidayCalendar", [a_name(), column]) == text


# A rejected column stops the call before the function runs, so nothing is published and the
# publication number does not move.
def test_a_rejected_column_publishes_no_object_and_no_handle() -> None:
    before = number(a_calendar(HOLIDAYS), CALENDAR)
    assert bridge.call(
        "_CreateHolidayCalendar", [a_name(), Cells.from_rows([[46023.0], [None]])]
    ) == ("#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date")
    assert number(a_calendar(HOLIDAYS), CALENDAR) == before + 1


def test_a_handle_of_another_kind_is_not_a_calendar() -> None:
    other = a_schedule(CODES, FUTURES, MISSING)
    assert bridge.call("ReadHolidayCalendar", [other]) == (
        f"#ERROR ReadHolidayCalendar: calendar is futures schedule handle {other!r}, "
        "expected holiday calendar handle"
    )


# The union's two calendars as the sheet sends them: A lists 14, 12 and 14 October 2026, B the
# 13th and the 14th.
CALENDAR_A = Cells.from_rows([[46309.0], [46307.0], [46309.0]])
CALENDAR_B = Cells.from_rows([[46308.0], [46309.0]])


# --- _CreatePublishedSchedule -------------------------------------------------------


# The published schedule page's sample as the sheet sends it: six prints, the code of the month
# each counts toward as text and its date as a serial, 31 August, the four Mondays of September
# and 5 October 2026.
PUBLISHED_CODES = Cells.from_rows([["Q26"], ["U26"], ["U26"], ["U26"], ["U26"], ["V26"]])
PUBLISHED_DATES = Cells.from_rows(
    [[46265.0], [46272.0], [46279.0], [46286.0], [46293.0], [46300.0]]
)
PUBLISHED = re.compile(r"[0-9]+:published_schedule:([0-9]+)")


# This hidden reader proves that a handle resolves to the schedule the seam kept: the months,
# each once, each print's month and the publication dates.
@probe
def ReadPublishedSchedule(schedule: Handle[PublishedSchedule]) -> str:
    months = " ".join(str(row) for row in schedule.contract.tolist())
    return f"{' '.join(schedule.codes)} | {months} | {days_or_none(schedule.publication_date)}"


def a_published_schedule(codes: object, published: object) -> str:
    text = bridge.call("_CreatePublishedSchedule", [codes, published])
    assert isinstance(text, str) and PUBLISHED.fullmatch(text), text
    return text


def test_a_published_schedule_is_created_from_two_columns_and_read_back() -> None:
    schedule = a_published_schedule(PUBLISHED_CODES, PUBLISHED_DATES)
    assert bridge.call("ReadPublishedSchedule", [schedule]) == (
        "Q26 U26 V26 | 0 1 1 1 1 2 | "
        "2026-08-31 2026-09-07 2026-09-14 2026-09-21 2026-09-28 2026-10-05"
    )


# Two single cells are two columns of one, so a schedule of one print needs no range.
def test_two_single_cells_are_a_published_schedule_of_one_print() -> None:
    schedule = a_published_schedule("U26", 46272.0)
    assert bridge.call("ReadPublishedSchedule", [schedule]) == "U26 | 0 | 2026-09-07"


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [PUBLISHED_CODES, Cells.from_rows([[46265.0], [46272.0], [46279.0]])],
            "#ERROR _CreatePublishedSchedule: ValueError: publication_date has 3 dates, "
            "expected 6, one per contract_code",
        ),
        (
            ["U26", PUBLISHED_DATES],
            "#ERROR _CreatePublishedSchedule: ValueError: publication_date has 6 dates, "
            "expected 1, one per contract_code",
        ),
        (
            [
                Cells.from_rows([["U26"], ["U26"], ["V26"], ["U26"], ["U26"], ["V26"]]),
                PUBLISHED_DATES,
            ],
            "#ERROR _CreatePublishedSchedule: ValueError: contract_code row 4 is 'U26', a month "
            "whose prints ended at row 2, expected each month's prints in consecutive rows",
        ),
        (
            [
                PUBLISHED_CODES,
                Cells.from_rows([[46265.0], [46272.0], [46272.0], [46286.0], [46293.0], [46300.0]]),
            ],
            "#ERROR _CreatePublishedSchedule: ValueError: publication_date row 3 is 2026-09-07, "
            "expected a date after row 2's 2026-09-07",
        ),
        (
            [
                PUBLISHED_CODES,
                Cells.from_rows([[46300.0], [46293.0], [46286.0], [46279.0], [46272.0], [46265.0]]),
            ],
            "#ERROR _CreatePublishedSchedule: ValueError: publication_date row 2 is 2026-09-28, "
            "expected a date after row 1's 2026-10-05",
        ),
        (
            [
                PUBLISHED_CODES,
                Cells.from_rows([[46265.0], [None], [46279.0], [46286.0], [46293.0], [46300.0]]),
            ],
            "#ERROR _CreatePublishedSchedule: publication_date cell (2, 1) is blank, expected date",
        ),
        (
            [
                PUBLISHED_CODES,
                Cells.from_rows([[46265.0], [46272.5], [46279.0], [46286.0], [46293.0], [46300.0]]),
            ],
            "#ERROR _CreatePublishedSchedule: publication_date cell (2, 1) is number 46272.5, "
            "expected date",
        ),
        (
            [
                PUBLISHED_CODES,
                Cells.from_rows(
                    [["31-Aug-2026"], [46272.0], [46279.0], [46286.0], [46293.0], [46300.0]]
                ),
            ],
            "#ERROR _CreatePublishedSchedule: publication_date cell (1, 1) is text "
            "'31-Aug-2026', expected date",
        ),
        (
            [
                Cells.from_rows([["Q26"], [46023.0], ["U26"], ["U26"], ["U26"], ["V26"]]),
                PUBLISHED_DATES,
            ],
            "#ERROR _CreatePublishedSchedule: contract_code cell (2, 1) is number 46023.0, "
            "expected text",
        ),
        (
            [
                Cells.from_rows([["Q26"], [""], ["U26"], ["U26"], ["U26"], ["V26"]]),
                PUBLISHED_DATES,
            ],
            "#ERROR _CreatePublishedSchedule: contract_code cell (2, 1) is empty text, "
            "expected text",
        ),
        (
            [Cells.from_rows([["Q26", "U26", "V26"]]), PUBLISHED_DATES],
            "#ERROR _CreatePublishedSchedule: contract_code is 1x3 array, expected column of text",
        ),
        (
            [PUBLISHED_CODES, Cells.from_rows([[46265.0, 46272.0, 46279.0]])],
            "#ERROR _CreatePublishedSchedule: publication_date is 1x3 array, expected column of "
            "dates",
        ),
        (
            [MISSING, PUBLISHED_DATES],
            "#ERROR _CreatePublishedSchedule: contract_code is missing, expected column of text",
        ),
        (
            [PUBLISHED_CODES, MISSING],
            "#ERROR _CreatePublishedSchedule: publication_date is missing, expected column of "
            "dates",
        ),
        (
            [None, PUBLISHED_DATES],
            "#ERROR _CreatePublishedSchedule: contract_code is blank, expected column of text",
        ),
        (
            [PUBLISHED_CODES, None],
            "#ERROR _CreatePublishedSchedule: publication_date is blank, expected column of dates",
        ),
        (
            [
                Cells.from_rows([["Q26"], [46023.0], ["U26"]]),
                Cells.from_rows([[46265.0], [None]]),
            ],
            "#ERROR _CreatePublishedSchedule: contract_code cell (2, 1) is number 46023.0, "
            "expected text",
        ),
    ],
    ids=[
        "a publication column three rows short",
        "six publication dates for one code",
        "a month whose code returns after another began",
        "a publication date listed twice",
        "a schedule pasted newest first",
        "a blank in the publication column",
        "a date with a time",
        "text in the publication column",
        "a number among the codes",
        "empty text among the codes",
        "a row of codes",
        "a row of dates",
        "the codes left out",
        "the publication dates left out",
        "a blank cell where the codes should be",
        "a blank cell where the publication dates should be",
        "both columns wrong, the codes named first",
    ],
)
def test_a_published_schedule_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreatePublishedSchedule", args) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap,
# whether the library or the seam refused the call.
def test_a_failed_published_schedule_publishes_no_object_and_no_handle() -> None:
    before = number(a_published_schedule(PUBLISHED_CODES, PUBLISHED_DATES), PUBLISHED)
    assert bridge.call(
        "_CreatePublishedSchedule",
        [PUBLISHED_CODES, Cells.from_rows([[46265.0], [46272.0], [46279.0]])],
    ) == (
        "#ERROR _CreatePublishedSchedule: ValueError: publication_date has 3 dates, "
        "expected 6, one per contract_code"
    )
    assert bridge.call(
        "_CreatePublishedSchedule",
        [PUBLISHED_CODES, Cells.from_rows([[46265.0], [None], [46279.0]])],
    ) == ("#ERROR _CreatePublishedSchedule: publication_date cell (2, 1) is blank, expected date")
    assert number(a_published_schedule(PUBLISHED_CODES, PUBLISHED_DATES), PUBLISHED) == (before + 1)


def test_a_handle_of_another_kind_is_not_a_published_schedule() -> None:
    other = a_schedule(CODES, FUTURES, MISSING)
    assert bridge.call("ReadPublishedSchedule", [other]) == (
        f"#ERROR ReadPublishedSchedule: schedule is futures schedule handle {other!r}, "
        "expected published schedule handle"
    )


# --- _CreateGasDailySchedule ----------------------------------------------------


# The Gas Daily schedule page's sample as the sheet sends it: three codes as text and two
# columns of serials, 1 September, 1 October and 1 November 2026 for the first days and
# 30 September, 31 October and 30 November for the last.
GAS_CODES = Cells.from_rows([["U26"], ["V26"], ["X26"]])
FIRST_DATES = Cells.from_rows([[46266.0], [46296.0], [46327.0]])
LAST_DATES = Cells.from_rows([[46295.0], [46326.0], [46356.0]])
GAS_DAILY = re.compile(r"[0-9]+:gas_daily_schedule:([0-9]+)")


# The library has no consumer of a Gas Daily schedule yet, so this hidden reader proves that a
# handle resolves to the schedule the seam kept, with its columns as they arrived.
@probe
def ReadGasDailySchedule(schedule: Handle[GasDailySchedule]) -> str:
    return (
        f"{' '.join(schedule.codes)} | {days_or_none(schedule.first_date)} | "
        f"{days_or_none(schedule.last_date)}"
    )


def a_gas_daily_schedule(codes: object, first: object, last: object) -> str:
    text = bridge.call("_CreateGasDailySchedule", [codes, first, last])
    assert isinstance(text, str) and GAS_DAILY.fullmatch(text), text
    return text


def test_a_gas_daily_schedule_is_created_from_three_columns_and_read_back() -> None:
    schedule = a_gas_daily_schedule(GAS_CODES, FIRST_DATES, LAST_DATES)
    assert bridge.call("ReadGasDailySchedule", [schedule]) == (
        "U26 V26 X26 | 2026-09-01 2026-10-01 2026-11-01 | 2026-09-30 2026-10-31 2026-11-30"
    )


# Three single cells are three columns of one, so a schedule of one contract month needs no range.
def test_three_single_cells_are_a_gas_daily_schedule_of_one_contract_month() -> None:
    schedule = a_gas_daily_schedule("U26", 46266.0, 46295.0)
    assert bridge.call("ReadGasDailySchedule", [schedule]) == "U26 | 2026-09-01 | 2026-09-30"


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [GAS_CODES, Cells.from_rows([[46266.0], [46296.0], [46327.0], [46357.0]]), LAST_DATES],
            "#ERROR _CreateGasDailySchedule: ValueError: first_date has 4 dates, expected 3, "
            "one per contract_code",
        ),
        (
            [GAS_CODES, Cells.from_rows([[46266.0], [46296.0]]), LAST_DATES],
            "#ERROR _CreateGasDailySchedule: ValueError: first_date has 2 dates, expected 3, "
            "one per contract_code",
        ),
        (
            [GAS_CODES, FIRST_DATES, Cells.from_rows([[46295.0], [46326.0], [46356.0], [46387.0]])],
            "#ERROR _CreateGasDailySchedule: ValueError: last_date has 4 dates, expected 3, "
            "one per contract_code",
        ),
        (
            ["U26", FIRST_DATES, LAST_DATES],
            "#ERROR _CreateGasDailySchedule: ValueError: first_date has 3 dates, expected 1, "
            "one per contract_code",
        ),
        (
            [GAS_CODES, Cells.from_rows([[46266.0], [46296.0]]), Cells.from_rows([[46295.0]])],
            "#ERROR _CreateGasDailySchedule: ValueError: first_date has 2 dates, expected 3, "
            "one per contract_code",
        ),
        (
            [GAS_CODES, FIRST_DATES, Cells.from_rows([[46295.0], [None], [46356.0]])],
            "#ERROR _CreateGasDailySchedule: last_date cell (2, 1) is blank, expected date",
        ),
        (
            [GAS_CODES, FIRST_DATES, Cells.from_rows([[46295.0], [46326.5], [46356.0]])],
            "#ERROR _CreateGasDailySchedule: last_date cell (2, 1) is number 46326.5, "
            "expected date",
        ),
        (
            [GAS_CODES, Cells.from_rows([["1-Sep-2026"], [46296.0], [46327.0]]), LAST_DATES],
            "#ERROR _CreateGasDailySchedule: first_date cell (1, 1) is text '1-Sep-2026', "
            "expected date",
        ),
        (
            [Cells.from_rows([["U26"], [46023.0], ["X26"]]), FIRST_DATES, LAST_DATES],
            "#ERROR _CreateGasDailySchedule: contract_code cell (2, 1) is number 46023.0, "
            "expected text",
        ),
        (
            [Cells.from_rows([["U26"], [""], ["X26"]]), FIRST_DATES, LAST_DATES],
            "#ERROR _CreateGasDailySchedule: contract_code cell (2, 1) is empty text, "
            "expected text",
        ),
        (
            [Cells.from_rows([["U26", "V26", "X26"]]), FIRST_DATES, LAST_DATES],
            "#ERROR _CreateGasDailySchedule: contract_code is 1x3 array, expected column of text",
        ),
        (
            [GAS_CODES, Cells.from_rows([[46266.0, 46296.0, 46327.0]]), LAST_DATES],
            "#ERROR _CreateGasDailySchedule: first_date is 1x3 array, expected column of dates",
        ),
        (
            [MISSING, FIRST_DATES, LAST_DATES],
            "#ERROR _CreateGasDailySchedule: contract_code is missing, expected column of text",
        ),
        (
            [GAS_CODES, MISSING, LAST_DATES],
            "#ERROR _CreateGasDailySchedule: first_date is missing, expected column of dates",
        ),
        (
            [GAS_CODES, FIRST_DATES, MISSING],
            "#ERROR _CreateGasDailySchedule: last_date is missing, expected column of dates",
        ),
        (
            [None, FIRST_DATES, LAST_DATES],
            "#ERROR _CreateGasDailySchedule: contract_code is blank, expected column of text",
        ),
        (
            [GAS_CODES, None, LAST_DATES],
            "#ERROR _CreateGasDailySchedule: first_date is blank, expected column of dates",
        ),
        (
            [GAS_CODES, FIRST_DATES, None],
            "#ERROR _CreateGasDailySchedule: last_date is blank, expected column of dates",
        ),
        (
            [
                Cells.from_rows([["U26"], [46023.0], ["X26"]]),
                Cells.from_rows([[46266.0], [None], [46327.0]]),
                Cells.from_rows([[46295.0], [46326.0]]),
            ],
            "#ERROR _CreateGasDailySchedule: contract_code cell (2, 1) is number 46023.0, "
            "expected text",
        ),
    ],
    ids=[
        "a first-date column one row long",
        "a first-date column one row short",
        "a last-date column one row long",
        "three first dates for one code",
        "both date columns wrong, the first dates named first",
        "a blank in the last-date column",
        "a date with a time",
        "text in the first-date column",
        "a number among the codes",
        "empty text among the codes",
        "a row of codes",
        "a row of dates",
        "the codes left out",
        "the first dates left out",
        "the last dates left out",
        "a blank cell where the codes should be",
        "a blank cell where the first dates should be",
        "a blank cell where the last dates should be",
        "every column wrong, the codes named first",
    ],
)
def test_a_gas_daily_schedule_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreateGasDailySchedule", args) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap,
# whether the library or the seam refused the call.
def test_a_failed_gas_daily_schedule_publishes_no_object_and_no_handle() -> None:
    before = number(a_gas_daily_schedule(GAS_CODES, FIRST_DATES, LAST_DATES), GAS_DAILY)
    assert bridge.call(
        "_CreateGasDailySchedule",
        [GAS_CODES, Cells.from_rows([[46266.0], [46296.0]]), LAST_DATES],
    ) == (
        "#ERROR _CreateGasDailySchedule: ValueError: first_date has 2 dates, expected 3, "
        "one per contract_code"
    )
    assert bridge.call(
        "_CreateGasDailySchedule",
        [GAS_CODES, FIRST_DATES, Cells.from_rows([[46295.0], [None], [46356.0]])],
    ) == ("#ERROR _CreateGasDailySchedule: last_date cell (2, 1) is blank, expected date")
    assert number(a_gas_daily_schedule(GAS_CODES, FIRST_DATES, LAST_DATES), GAS_DAILY) == (
        before + 1
    )


def test_a_handle_of_another_kind_is_not_a_gas_daily_schedule() -> None:
    other = a_published_schedule(PUBLISHED_CODES, PUBLISHED_DATES)
    assert bridge.call("ReadGasDailySchedule", [other]) == (
        f"#ERROR ReadGasDailySchedule: schedule is published schedule handle {other!r}, "
        "expected gas daily schedule handle"
    )


# --- _CreateIndexConventions ----------------------------------------------------


# The index holds the conventions, but this hidden reader proves on its own that a handle
# resolves to the conventions the seam kept, the five codes in their fields.
@probe
def ReadIndexConventions(conventions: Handle[IndexConventions]) -> str:
    return " ".join(
        (
            conventions.quote_currency_unit,
            conventions.quote_quantity_unit,
            conventions.currency_unit,
            conventions.quantity_type,
            conventions.quantity_unit,
        )
    )


def the_conventions(*codes: object) -> str:
    text = bridge.call("_CreateIndexConventions", list(codes))
    assert isinstance(text, str) and CONVENTIONS.fullmatch(text), text
    return text


def test_index_conventions_are_created_from_five_codes_and_read_back_in_order() -> None:
    assert bridge.call("ReadIndexConventions", [the_conventions(*UNITS)]) == (
        "DOLLAR BBL DOLLAR VOLUME BBL"
    )


# Each argument alone, left to right: the first bad one is named, in the seam's words.
@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            ["DOLLAR", "BBL", "DOLLAR", "VOLUME", None],
            "#ERROR _CreateIndexConventions: quantity_unit is blank, expected text",
        ),
        (
            ["DOLLAR", "BBL", 1.0, "VOLUME", "BBL"],
            "#ERROR _CreateIndexConventions: currency_unit is number 1.0, expected text",
        ),
        (
            ["", "BBL", "DOLLAR", "VOLUME", "BBL"],
            "#ERROR _CreateIndexConventions: quote_currency_unit is empty text, expected text",
        ),
        (
            ["DOLLAR", Cells.from_rows([["BBL"]]), "DOLLAR", "VOLUME", "BBL"],
            "#ERROR _CreateIndexConventions: quote_quantity_unit is 1x1 array, expected text",
        ),
        (
            ["DOLLAR", "BBL", "DOLLAR", "VOLUME", MISSING],
            "#ERROR _CreateIndexConventions: quantity_unit is missing, expected text",
        ),
        (
            ["DOLLAR", "BBL", True, None, "BBL"],
            "#ERROR _CreateIndexConventions: currency_unit is boolean TRUE, expected text",
        ),
    ],
    ids=[
        "a blank where a code is expected",
        "a number where a code is expected",
        "empty text",
        "a one-cell range",
        "a code left out",
        "two wrong, the earlier named",
    ],
)
def test_index_conventions_that_cannot_be_made_say_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreateIndexConventions", args) == text


def test_a_handle_of_another_kind_is_not_index_conventions() -> None:
    other = a_calendar(HOLIDAYS)
    assert bridge.call("ReadIndexConventions", [other]) == (
        f"#ERROR ReadIndexConventions: conventions is holiday calendar handle {other!r}, "
        "expected index conventions handle"
    )


# The library's rules reach the sheet in its words: a code nobody defined, one in another case
# and a unit of another category; and two units of one category are accepted, cents a gallon
# quoted and dollars a barrel settled.
def test_the_conventions_rules_reach_the_sheet_in_the_librarys_words() -> None:
    assert bridge.call("_CreateIndexConventions", ["DOLLAR", "BBL", "DOLLAR", "Volume", "BBL"]) == (
        "#ERROR _CreateIndexConventions: ValueError: quantity_type is 'Volume', "
        "expected VOLUME, MASS or ENERGY"
    )
    assert bridge.call(
        "_CreateIndexConventions", ["DOLLAR", "MMBTU", "DOLLAR", "VOLUME", "BBL"]
    ) == (
        "#ERROR _CreateIndexConventions: ValueError: quote_quantity_unit is 'MMBTU', "
        "expected a VOLUME unit, GAL, BBL, L or M3"
    )
    assert bridge.call("_CreateIndexConventions", ["usd", "BBL", "DOLLAR", "VOLUME", "BBL"]) == (
        "#ERROR _CreateIndexConventions: ValueError: quote_currency_unit is 'usd', "
        "expected DOLLAR or CENT"
    )
    assert bridge.call("_CreateIndexConventions", ["DOLLAR", "BBL", "EUR", "VOLUME", "BBL"]) == (
        "#ERROR _CreateIndexConventions: ValueError: currency_unit is 'EUR', "
        "expected DOLLAR or CENT"
    )
    gasoline = the_conventions("CENT", "GAL", "DOLLAR", "VOLUME", "BBL")
    assert bridge.call("ReadIndexConventions", [gasoline]) == "CENT GAL DOLLAR VOLUME BBL"


def test_a_failed_conventions_construction_publishes_no_object_and_no_handle() -> None:
    before = number(the_conventions(*UNITS), CONVENTIONS)
    assert bridge.call("_CreateIndexConventions", ["DOLLAR", "BBL", "DOLLAR", "weight", "BBL"]) == (
        "#ERROR _CreateIndexConventions: ValueError: quantity_type is 'weight', "
        "expected VOLUME, MASS or ENERGY"
    )
    assert number(the_conventions(*UNITS), CONVENTIONS) == before + 1


# --- _CreateContractSpecifications ----------------------------------------------------------


# The index holds the specifications, but this hidden reader proves on its own that a handle
# resolves to the specifications the seam kept, typed: names as text, lot sizes whole, fees as
# numbers.
@probe
def ReadContractSpecifications(specifications: Handle[ContractSpecifications]) -> str:
    lots = specifications.lot_sizes
    return (
        f"{' '.join(specifications.names)} | {lots.dtype} {lots.tolist()} "
        f"{' '.join(specifications.lot_units)} | "
        f"{specifications.brokerage_rates_per_lot.tolist()} "
        f"{specifications.clearing_rates_per_lot.tolist()}"
    )


def the_specifications(headers: object, body: object) -> str:
    text = bridge.call("_CreateContractSpecifications", [headers, body])
    assert isinstance(text, str) and SPECIFICATIONS.fullmatch(text), text
    return text


def test_contract_specifications_are_created_from_a_table_and_read_back_typed() -> None:
    assert bridge.call(
        "ReadContractSpecifications",
        [the_specifications(SPECIFICATION_HEADERS, SPECIFICATION_BODY)],
    ) == ("NYMEX NG ICE NG | float64 [10000.0, 2500.0] MMBTU MMBTU | [3.0, 0.75] [2.0, 0.5]")


def test_the_specifications_headers_bind_in_any_order_and_one_row_is_a_table() -> None:
    headers = Cells.from_rows(
        [["CLEARING_RATE_PER_LOT", "Name", "Lot_Unit", "lot_size", "brokerage_rate_per_lot"]]
    )
    body = Cells.from_rows([[2.0, "NYMEX NG", "MMBTU", 10000.0, 3.0]])
    assert bridge.call("ReadContractSpecifications", [the_specifications(headers, body)]) == (
        "NYMEX NG | float64 [10000.0] MMBTU | [3.0] [2.0]"
    )


@pytest.mark.parametrize(
    ("headers", "body", "text"),
    [
        (
            Cells.from_rows(
                [["name", "lot_size", "lot_unit", "brokerage", "clearing_rate_per_lot"]]
            ),
            SPECIFICATION_BODY,
            "#ERROR _CreateContractSpecifications: header_row cell (1, 4) is text 'brokerage', "
            "expected one of name, lot_size, lot_unit, brokerage_rate_per_lot or "
            "clearing_rate_per_lot",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 2.5, "MMBTU", 3.0, 2.0]]),
            "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 2.5, "
            "expected a whole number",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", True, "MMBTU", 3.0, 2.0]]),
            "#ERROR _CreateContractSpecifications: table cell (1, 2) is boolean TRUE, "
            "expected number",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, "MMBTU", "three", 2.0]]),
            "#ERROR _CreateContractSpecifications: table cell (1, 4) is text 'three', "
            "expected number",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([[1.0, 10000.0, "MMBTU", 3.0, 2.0]]),
            "#ERROR _CreateContractSpecifications: table cell (1, 1) is number 1.0, expected text",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, 42.0, 3.0, 2.0]]),
            "#ERROR _CreateContractSpecifications: table cell (1, 3) is number 42.0, expected text",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, "usd", 3.0, 2.0]]),
            "#ERROR _CreateContractSpecifications: ValueError: lot_unit row 1 is 'usd', "
            "expected a VOLUME, MASS or ENERGY unit",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows(
                [["NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0], ["NYMEX NG", 2500.0, "MMBTU", 0.75, 0.5]]
            ),
            "#ERROR _CreateContractSpecifications: ValueError: name row 2 is 'NYMEX NG', "
            "already given at row 1",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 0.0, "MMBTU", 3.0, 2.0]]),
            "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 0.0, "
            "expected 1 or more",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, "MMBTU", -0.5, 2.0]]),
            "#ERROR _CreateContractSpecifications: ValueError: brokerage_rate_per_lot row 1 is "
            "-0.5, expected 0 or more",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, "MMBTU", 3.0]]),
            "#ERROR _CreateContractSpecifications: header_row has 5 headers, expected 4, "
            "one per column of table",
        ),
        (
            SPECIFICATION_HEADERS,
            None,
            "#ERROR _CreateContractSpecifications: table is blank, expected table",
        ),
        (
            SPECIFICATION_HEADERS,
            MISSING,
            "#ERROR _CreateContractSpecifications: table is missing, expected table",
        ),
    ],
    ids=[
        "an unknown header",
        "a lot size with a fraction",
        "a boolean lot size",
        "text where a fee is expected",
        "a number where a name is expected",
        "a number where the lot unit is expected",
        "a currency unit in another case where the lot unit is expected",
        "a name given twice",
        "a lot size of zero",
        "a negative fee",
        "a body one column narrower than its headers",
        "a blank cell where the body should be",
        "the body left out",
    ],
)
def test_contract_specifications_that_cannot_be_made_say_why(
    headers: object, body: object, text: str
) -> None:
    assert bridge.call("_CreateContractSpecifications", [headers, body]) == text


def test_a_failed_specifications_construction_publishes_no_object_and_no_handle() -> None:
    before = number(the_specifications(SPECIFICATION_HEADERS, SPECIFICATION_BODY), SPECIFICATIONS)
    twice = Cells.from_rows(
        [["NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0], ["NYMEX NG", 2500.0, "MMBTU", 0.75, 0.5]]
    )
    assert bridge.call("_CreateContractSpecifications", [SPECIFICATION_HEADERS, twice]) == (
        "#ERROR _CreateContractSpecifications: ValueError: name row 2 is 'NYMEX NG', "
        "already given at row 1"
    )
    assert (
        number(the_specifications(SPECIFICATION_HEADERS, SPECIFICATION_BODY), SPECIFICATIONS)
        == before + 1
    )


def test_a_handle_of_another_kind_is_not_contract_specifications() -> None:
    other = the_conventions(*UNITS)
    assert bridge.call("ReadContractSpecifications", [other]) == (
        f"#ERROR ReadContractSpecifications: specifications is index conventions handle {other!r}, "
        "expected contract specifications handle"
    )


# A lot size crosses as the double the cell holds and goes back out as it came: every whole number
# from 1 to 2^53 is read back exactly, and a whole double beyond, 1E16 say, is kept as it is. A
# double with a fraction, and one below one, are the builder's to refuse.
@given(lot_size=st.integers(1, 2**53))
def test_any_lot_size_a_cell_holds_exactly_is_created_and_read_back(lot_size: int) -> None:
    body = Cells.from_rows([["NYMEX NG", float(lot_size), "MMBTU", 3.0, 2.0]])
    spill = bridge.call("util_ReadHandle", [the_specifications(SPECIFICATION_HEADERS, body)])
    assert isinstance(spill, tuple), spill
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2, 1] == float(lot_size)


@pytest.mark.parametrize("lot_size", [1e16, 1e20])
def test_a_whole_double_beyond_two_to_the_fifty_three_is_kept_and_read_back(
    lot_size: float,
) -> None:
    body = Cells.from_rows([["NYMEX NG", lot_size, "MMBTU", 3.0, 2.0]])
    spill = bridge.call("util_ReadHandle", [the_specifications(SPECIFICATION_HEADERS, body)])
    assert isinstance(spill, tuple), spill
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2, 1] == lot_size


# --- _CreateIndex -------------------------------------------------------------------


INDEX = re.compile(r"[0-9]+:index:.+:([0-9]+)")
# A monthly published schedule and the Gas Daily schedule page's sample as the sheet sends
# them: three months each, with the day each month's one print is published, and the first
# and last day of gas of each.
INDEX_MONTHLY_CODES = Cells.from_rows([["V26"], ["X26"], ["Z26"]])
INDEX_MONTHLY_PUBLISHED = Cells.from_rows([[46296.0], [46328.0], [46357.0]])
INDEX_GAS_DAILY_CODES = Cells.from_rows([["U26"], ["V26"], ["X26"]])
INDEX_GAS_DAILY_FIRST = Cells.from_rows([[46266.0], [46296.0], [46327.0]])
INDEX_GAS_DAILY_LAST = Cells.from_rows([[46295.0], [46326.0], [46356.0]])
INDEX_HEADERS = [
    "name",
    "display_name",
    "kind",
    "contracts",
    "specifications",
    "has_holiday_calendar",
    "reporting_lot",
]
INDEX_TYPES = ["str", "str", "str", "int64", "int64", "bool", "str"]


def the_parts() -> tuple[str, str, str, str]:
    """A futures schedule of the sample's three contracts, its holiday calendar, the conventions
    and the specifications, each a handle."""
    return (
        a_schedule(CODES, FUTURES, OPTIONS),
        a_calendar(HOLIDAYS),
        the_conventions(*GAS),
        the_specifications(SPECIFICATION_HEADERS, SPECIFICATION_BODY),
    )


def an_index(*args: object) -> str:
    """The index of seven arguments as these tests state them, the sixth a calendar's handle or
    MISSING: the handle's key in its place and the tests' collection last, as a formula names
    the calendar by key and the collection's cell since holiday-keys.md."""
    text = bridge.call("_CreateIndex", [*args[:5], seam_key(args[5]), args[6], seam_calendars()])
    assert isinstance(text, str) and INDEX.fullmatch(text), text
    return text


def test_a_futures_index_is_created_from_text_and_four_handles_and_read_back_as_one_row() -> None:
    schedule, holidays, conventions, specifications = the_parts()
    made = an_index(
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specifications,
        holidays,
        MISSING,
    )
    kinds, slots, joined = read(made)
    assert rows((kinds, slots, joined)) == [
        INDEX_HEADERS,
        INDEX_TYPES,
        ["Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", "futures", 3.0, 2.0, 1.0, "unset"],
    ]
    assert kinds[2].tolist() == [
        TEXT_CODE,
        TEXT_CODE,
        TEXT_CODE,
        NUMBER_CODE,
        NUMBER_CODE,
        BOOLEAN_CODE,
        TEXT_CODE,
    ]
    spaced = an_index(
        " Henry Hub NYMEX ",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specifications,
        holidays,
        MISSING,
    )
    assert rows(read(spaced))[2][0] == " Henry Hub NYMEX "


def test_a_published_and_a_gas_daily_index_are_created_without_a_holiday_calendar() -> None:
    _, _, conventions, specifications = the_parts()
    monthly_schedule = a_published_schedule(INDEX_MONTHLY_CODES, INDEX_MONTHLY_PUBLISHED)
    monthly = an_index(
        "Henry Hub IFERC",
        "Henry Hub natural gas - Inside FERC monthly index",
        monthly_schedule,
        conventions,
        specifications,
        MISSING,
        MISSING,
    )
    assert rows(read(monthly))[2] == [
        "Henry Hub IFERC",
        "Henry Hub natural gas - Inside FERC monthly index",
        "published",
        3.0,
        2.0,
        0.0,
        "unset",
    ]
    gas_daily = a_gas_daily_schedule(
        INDEX_GAS_DAILY_CODES, INDEX_GAS_DAILY_FIRST, INDEX_GAS_DAILY_LAST
    )
    daily = an_index(
        "Henry Hub Gas Daily",
        "Henry Hub natural gas - Platts Gas Daily",
        gas_daily,
        conventions,
        specifications,
        MISSING,
        MISSING,
    )
    kinds, slots, joined = read(daily)
    assert rows((kinds, slots, joined)) == [
        INDEX_HEADERS,
        INDEX_TYPES,
        [
            "Henry Hub Gas Daily",
            "Henry Hub natural gas - Platts Gas Daily",
            "Gas Daily",
            3.0,
            2.0,
            0.0,
            "unset",
        ],
    ]
    assert kinds[2].tolist() == [
        TEXT_CODE,
        TEXT_CODE,
        TEXT_CODE,
        NUMBER_CODE,
        NUMBER_CODE,
        BOOLEAN_CODE,
        TEXT_CODE,
    ]


# A published index reads back its months, not its prints: six prints of three months are three
# contracts, the count every reader of a schedule's codes takes.
def test_a_published_index_is_created_without_a_holiday_calendar_and_counts_its_months() -> None:
    _, holidays, conventions, specifications = the_parts()
    published = a_published_schedule(PUBLISHED_CODES, PUBLISHED_DATES)
    weekly = an_index(
        "DOE Diesel",
        "U.S. national retail diesel - EIA weekly",
        published,
        conventions,
        specifications,
        MISSING,
        MISSING,
    )
    assert rows(read(weekly)) == [
        INDEX_HEADERS,
        INDEX_TYPES,
        [
            "DOE Diesel",
            "U.S. national retail diesel - EIA weekly",
            "published",
            3.0,
            2.0,
            0.0,
            "unset",
        ],
    ]
    assert bridge.call(
        "_CreateIndex",
        [
            "DOE Diesel",
            "U.S. national retail diesel - EIA weekly",
            published,
            conventions,
            specifications,
            seam_key(holidays),
            MISSING,
            seam_calendars(),
        ],
    ) == (
        f"#ERROR _CreateIndex: ValueError: holiday_key is {seam_key(holidays)!r}, "
        "expected none with a published schedule"
    )


def test_the_librarys_rules_reach_the_sheet_in_its_words_for_the_index() -> None:
    schedule, holidays, conventions, specifications = the_parts()
    assert bridge.call(
        "_CreateIndex",
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            conventions,
            specifications,
            MISSING,
            MISSING,
            MISSING,
        ],
    ) == (
        "#ERROR _CreateIndex: ValueError: holiday_key is missing, "
        "expected a holiday calendar's key with a futures schedule"
    )
    gas_daily = a_gas_daily_schedule(
        INDEX_GAS_DAILY_CODES, INDEX_GAS_DAILY_FIRST, INDEX_GAS_DAILY_LAST
    )
    assert bridge.call(
        "_CreateIndex",
        [
            "Henry Hub Gas Daily",
            "Henry Hub natural gas - Platts Gas Daily",
            gas_daily,
            conventions,
            specifications,
            seam_key(holidays),
            MISSING,
            seam_calendars(),
        ],
    ) == (
        f"#ERROR _CreateIndex: ValueError: holiday_key is {seam_key(holidays)!r}, "
        "expected none with a Gas Daily schedule"
    )
    monthly_schedule = a_published_schedule(INDEX_MONTHLY_CODES, INDEX_MONTHLY_PUBLISHED)
    assert bridge.call(
        "_CreateIndex",
        [
            "Henry Hub IFERC",
            "Henry Hub natural gas - Inside FERC monthly index",
            monthly_schedule,
            conventions,
            specifications,
            seam_key(holidays),
            MISSING,
            seam_calendars(),
        ],
    ) == (
        f"#ERROR _CreateIndex: ValueError: holiday_key is {seam_key(holidays)!r}, "
        "expected none with a published schedule"
    )
    for wrong, what in (
        (holidays, "a holiday calendar"),
        (conventions, "index conventions"),
        (specifications, "contract specifications"),
    ):
        assert bridge.call(
            "_CreateIndex",
            [
                "Henry Hub NYMEX",
                "Henry Hub natural gas - NYMEX",
                wrong,
                conventions,
                specifications,
                seam_key(holidays),
                MISSING,
                seam_calendars(),
            ],
        ) == (
            f"#ERROR _CreateIndex: ValueError: schedule is {what}, "
            "expected a futures, Gas Daily or published schedule"
        )
    made = an_index(
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specifications,
        holidays,
        MISSING,
    )
    assert bridge.call(
        "_CreateIndex",
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            made,
            conventions,
            specifications,
            MISSING,
            MISSING,
            MISSING,
        ],
    ) == (
        "#ERROR _CreateIndex: ValueError: schedule is an index, "
        "expected a futures, Gas Daily or published schedule"
    )


THE_SCHEDULE, THE_HOLIDAYS = object(), object()
THE_CONVENTIONS, THE_SPECIFICATIONS = object(), object()


# Each argument alone, left to right: the first bad one is named, in the seam's words.
@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [None, THE_SCHEDULE, THE_CONVENTIONS, THE_SPECIFICATIONS, THE_HOLIDAYS, MISSING],
            "#ERROR _CreateIndex: name is blank, expected text",
        ),
        (
            [MISSING, THE_SCHEDULE, THE_CONVENTIONS, THE_SPECIFICATIONS, THE_HOLIDAYS, MISSING],
            "#ERROR _CreateIndex: name is missing, expected text",
        ),
        (
            [1.0, THE_SCHEDULE, THE_CONVENTIONS, THE_SPECIFICATIONS, THE_HOLIDAYS, MISSING],
            "#ERROR _CreateIndex: name is number 1.0, expected text",
        ),
        (
            ["", THE_SCHEDULE, THE_CONVENTIONS, THE_SPECIFICATIONS, THE_HOLIDAYS, MISSING],
            "#ERROR _CreateIndex: name is empty text, expected text",
        ),
        (
            [
                Cells.from_rows([["Henry Hub NYMEX"]]),
                THE_SCHEDULE,
                THE_CONVENTIONS,
                THE_SPECIFICATIONS,
                THE_HOLIDAYS,
                MISSING,
            ],
            "#ERROR _CreateIndex: name is 1x1 array, expected text",
        ),
        (
            [
                "Henry Hub NYMEX",
                MISSING,
                THE_CONVENTIONS,
                THE_SPECIFICATIONS,
                THE_HOLIDAYS,
                MISSING,
            ],
            "#ERROR _CreateIndex: schedule is missing, expected a handle",
        ),
        (
            ["Henry Hub NYMEX", None, THE_CONVENTIONS, THE_SPECIFICATIONS, THE_HOLIDAYS, MISSING],
            "#ERROR _CreateIndex: schedule is blank, expected a handle",
        ),
        (
            [
                "Henry Hub NYMEX",
                46161.0,
                THE_CONVENTIONS,
                THE_SPECIFICATIONS,
                THE_HOLIDAYS,
                MISSING,
            ],
            "#ERROR _CreateIndex: schedule is number 46161.0, expected a handle",
        ),
        (
            ["Henry Hub NYMEX", "x", THE_CONVENTIONS, THE_SPECIFICATIONS, THE_HOLIDAYS, MISSING],
            "#ERROR _CreateIndex: schedule is text 'x' naming no live object, expected a handle",
        ),
        (
            [
                "Henry Hub NYMEX",
                "#ERROR _CreateFuturesSchedule: contract_code is blank, expected column of text",
                THE_CONVENTIONS,
                THE_SPECIFICATIONS,
                THE_HOLIDAYS,
                MISSING,
            ],
            "#ERROR _CreateIndex: schedule is the creator's failure, expected a handle: "
            "#ERROR _CreateFuturesSchedule: contract_code is blank, expected column of text",
        ),
        (
            ["Henry Hub NYMEX", THE_SCHEDULE, MISSING, THE_SPECIFICATIONS, THE_HOLIDAYS, MISSING],
            "#ERROR _CreateIndex: index_conventions is missing, expected index conventions handle",
        ),
        (
            ["Henry Hub NYMEX", THE_SCHEDULE, None, THE_SPECIFICATIONS, THE_HOLIDAYS, MISSING],
            "#ERROR _CreateIndex: index_conventions is blank, expected index conventions handle",
        ),
        (
            ["Henry Hub NYMEX", THE_SCHEDULE, THE_CONVENTIONS, MISSING, THE_HOLIDAYS, MISSING],
            "#ERROR _CreateIndex: contract_specifications is missing, "
            "expected contract specifications handle",
        ),
        (
            [
                "Henry Hub NYMEX",
                THE_SCHEDULE,
                THE_CONVENTIONS,
                "contract_specifications:9999999",
                THE_HOLIDAYS,
                MISSING,
            ],
            "#ERROR _CreateIndex: contract_specifications is text "
            "'contract_specifications:9999999' naming no live object, "
            "expected contract specifications handle",
        ),
        (
            ["Henry Hub NYMEX", THE_SCHEDULE, THE_CONVENTIONS, THE_SPECIFICATIONS, None, MISSING],
            "#ERROR _CreateIndex: holiday_key is blank, expected text",
        ),
        (
            [
                "Henry Hub NYMEX",
                THE_SCHEDULE,
                THE_CONVENTIONS,
                THE_SPECIFICATIONS,
                46167.0,
                MISSING,
            ],
            "#ERROR _CreateIndex: holiday_key is number 46167.0, expected text",
        ),
    ],
    ids=[
        "a blank where the name should be",
        "the name left out",
        "a number where the name should be",
        "empty text for the name",
        "a one-cell range for the name",
        "the schedule left out",
        "a blank where the schedule should be",
        "a number where the schedule should be",
        "text naming no live schedule",
        "the schedule creator's failure relayed",
        "the conventions left out",
        "a blank where the conventions should be",
        "the specifications left out",
        "text naming no live specifications",
        "a blank where the holiday key should be",
        "a number where the holiday key should be",
    ],
)
def test_an_index_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    schedule, holidays, conventions, specifications = the_parts()
    stand_ins = {
        id(THE_SCHEDULE): schedule,
        id(THE_HOLIDAYS): seam_key(holidays),  # the calendar's key, since holiday-keys.md
        id(THE_CONVENTIONS): conventions,
        id(THE_SPECIFICATIONS): specifications,
    }
    given = [stand_ins.get(id(arg), arg) for arg in args]
    given.insert(
        1, "Henry Hub natural gas - NYMEX"
    )  # the display name, since #169, never at fault here
    given.append(seam_calendars())  # the collection the key selects from, never at fault here
    assert bridge.call("_CreateIndex", given) == text


def test_a_handle_of_another_kind_in_a_typed_slot_of_the_index_is_refused_by_name() -> None:
    schedule, holidays, conventions, specifications = the_parts()
    assert bridge.call(
        "_CreateIndex",
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            holidays,
            specifications,
            seam_key(holidays),
            MISSING,
            seam_calendars(),
        ],
    ) == (
        f"#ERROR _CreateIndex: index_conventions is holiday calendar handle {holidays!r}, "
        "expected index conventions handle"
    )
    assert bridge.call(
        "_CreateIndex",
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            conventions,
            conventions,
            seam_key(holidays),
            MISSING,
            seam_calendars(),
        ],
    ) == (
        f"#ERROR _CreateIndex: contract_specifications is index conventions handle "
        f"{conventions!r}, expected contract specifications handle"
    )
    made = an_index(
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specifications,
        holidays,
        MISSING,
    )
    assert bridge.call(
        "_CreateIndex",
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            conventions,
            specifications,
            seam_key(holidays),
            MISSING,
            made,
        ],
    ) == (
        f"#ERROR _CreateIndex: holiday_calendars is index handle {made!r}, "
        "expected holiday calendars handle"
    )
    # A single calendar's handle is no collection, however alike the two kinds read.
    assert bridge.call(
        "_CreateIndex",
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            conventions,
            specifications,
            seam_key(holidays),
            MISSING,
            holidays,
        ],
    ) == (
        f"#ERROR _CreateIndex: holiday_calendars is holiday calendar handle {holidays!r}, "
        "expected holiday calendars handle"
    )


def test_the_holiday_key_selects_from_the_collection_and_is_refused_in_the_librarys_words() -> None:
    # holiday-keys.md: the key is text, one name of the collection or several joined by a plus
    # sign; the collection is the last argument, required with a key and read for nothing
    # without one.
    schedule, _, conventions, specifications = the_parts()
    nymex = bridge.call("_CreateHolidayCalendar", ["IDX_NYMEX", CALENDAR_A])
    ice = bridge.call("_CreateHolidayCalendar", ["IDX_ICE", CALENDAR_B])
    both = bridge.call("_CollectHolidayCalendars", [Cells.from_rows([[nymex, ice]])])

    def made(key: object, collection: object, on: object = schedule) -> object:
        return bridge.call(
            "_CreateIndex",
            ["HH", "Henry Hub", on, conventions, specifications, key, MISSING, collection],
        )

    for key in ("IDX_NYMEX", "IDX_ICE", "IDX_NYMEX+IDX_ICE", "IDX_ICE+IDX_NYMEX"):
        text = made(key, both)
        assert isinstance(text, str) and INDEX.fullmatch(text), text
        assert rows(read(text))[2][5] == 1.0  # has_holiday_calendar
    assert made("IDX_NYMEX", MISSING) == (
        "#ERROR _CreateIndex: ValueError: holiday_calendars is missing, expected a "
        "_CollectHolidayCalendars collection, which holiday_key selects a calendar from"
    )
    assert made("IDX_CME", both) == (
        "#ERROR _CreateIndex: ValueError: holiday_key is 'IDX_CME', expected names of the "
        "collection's calendars, 'IDX_NYMEX' and 'IDX_ICE'; it holds no 'IDX_CME'"
    )
    assert made("IDX_NYMEX + IDX_ICE", both) == (
        "#ERROR _CreateIndex: ValueError: holiday_key is 'IDX_NYMEX + IDX_ICE', expected a "
        "calendar's name, or several joined by '+', each with no whitespace around it"
    )
    # A calendar's handle typed where the key goes is text, read as a name the collection lacks.
    assert made(nymex, both) == (
        f"#ERROR _CreateIndex: ValueError: holiday_key is {nymex!r}, expected names of the "
        f"collection's calendars, 'IDX_NYMEX' and 'IDX_ICE'; it holds no {nymex!r}"
    )
    # A published index refuses a key before anything is looked up, and reads a collection given
    # with no key for nothing.
    monthly_schedule = a_published_schedule(INDEX_MONTHLY_CODES, INDEX_MONTHLY_PUBLISHED)
    assert made("IDX_NOWHERE", MISSING, monthly_schedule) == (
        "#ERROR _CreateIndex: ValueError: holiday_key is 'IDX_NOWHERE', expected none with a "
        "published schedule"
    )
    monthly = made(MISSING, both, monthly_schedule)
    assert isinstance(monthly, str) and INDEX.fullmatch(monthly), monthly
    assert rows(read(monthly))[2][5] == 0.0


# The index's own rule for the lot units reaches the sheet in the library's words: the volume
# conventions of the conventions page with the gas specifications, and a table of barrels and
# gallons under them accepted.
def test_lot_units_of_another_measure_are_refused_by_the_index_in_the_librarys_words() -> None:
    schedule, holidays, _, gas = the_parts()
    volume = the_conventions(*UNITS)
    assert bridge.call(
        "_CreateIndex",
        [
            "WTI NYMEX",
            "West Texas Intermediate crude oil - NYMEX",
            schedule,
            volume,
            gas,
            seam_key(holidays),
            MISSING,
            seam_calendars(),
        ],
    ) == (
        "#ERROR _CreateIndex: ValueError: specifications row 1 lot_unit is 'MMBTU', "
        "expected a VOLUME unit, GAL, BBL, L or M3"
    )
    barrels_and_gallons = the_specifications(
        SPECIFICATION_HEADERS,
        Cells.from_rows([["lots", 1000.0, "BBL", 3.0, 2.0], ["gal", 1.0, "GAL", 0.0, 0.0]]),
    )
    made = an_index(
        "WTI NYMEX",
        "West Texas Intermediate crude oil - NYMEX",
        schedule,
        volume,
        barrels_and_gallons,
        holidays,
        MISSING,
    )
    assert rows(read(made))[2] == [
        "WTI NYMEX",
        "West Texas Intermediate crude oil - NYMEX",
        "futures",
        3.0,
        2.0,
        1.0,
        "unset",
    ]


def test_a_failed_index_publishes_no_object_and_reading_one_publishes_nothing() -> None:
    schedule, holidays, conventions, specifications = the_parts()
    before = number(
        an_index(
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            conventions,
            specifications,
            holidays,
            MISSING,
        ),
        INDEX,
    )
    refused = bridge.call(
        "_CreateIndex",
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            conventions,
            specifications,
            MISSING,
            MISSING,
            MISSING,
        ],
    )
    assert cast(str, refused).startswith("#ERROR _CreateIndex: ValueError: holiday_key is missing")
    made = an_index(
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specifications,
        holidays,
        MISSING,
    )
    assert number(made, INDEX) == before + 1
    read(made)
    read(made)
    again = an_index(
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specifications,
        holidays,
        MISSING,
    )
    assert number(again, INDEX) == before + 2


# The handle carries the index's name as typed between the tag and the count: another case,
# spaces at either end, a colon and any character kept whole; two indices of one name are
# told apart by the count alone.
@pytest.mark.parametrize(
    "name",
    [
        "Henry Hub NYMEX",
        "henry hub nymex",
        " Henry Hub NYMEX ",
        "Henry Hub: NYMEX",
        "Brent Dated €/bbl",
        "C2",
    ],
    ids=[
        "as the desk calls it",
        "another case",
        "spaces at either end",
        "a colon",
        "Unicode",
        "two characters",
    ],
)
def test_an_index_handle_carries_its_name_as_typed(name: str) -> None:
    schedule, holidays, conventions, specifications = the_parts()
    made = an_index(name, f"{name} index", schedule, conventions, specifications, holidays, MISSING)
    assert made.startswith(f"{PID}:index:{name}:")
    assert made[len(f"{PID}:index:{name}:") :].isdigit()
    again = an_index(
        name, f"{name} index", schedule, conventions, specifications, holidays, MISSING
    )
    assert again.startswith(f"{PID}:index:{name}:")
    assert number(again, INDEX) == number(made, INDEX) + 1


# The whole text is measured as Excel counts text before anything is stored: a name that takes
# the handle past 32,767 UTF-16 units fails in the result voice, whether its characters are one
# unit each or two, nothing is stored, and the count does not move.
@pytest.mark.parametrize(
    ("name", "units"),
    [("x" * 32_761, 32_761), ("\U0001d11e" * 16_381, 32_762)],
    ids=["one unit per character", "two units per character"],
)
def test_a_name_too_long_for_a_cell_fails_before_the_index_is_stored(name: str, units: int) -> None:
    schedule, holidays, conventions, specifications = the_parts()
    before = number(
        an_index(
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            conventions,
            specifications,
            holidays,
            MISSING,
        ),
        INDEX,
    )
    count = before + 1  # the count the refused text would have carried
    total = len(f"{PID}:index:") + units + len(":") + len(str(count))
    assert bridge.call(
        "_CreateIndex",
        [
            name,
            f"{name} index",
            schedule,
            conventions,
            specifications,
            seam_key(holidays),
            MISSING,
            seam_calendars(),
        ],
    ) == (f"#ERROR _CreateIndex: returned handle of {total} characters, expected at most 32767")
    made = an_index(
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specifications,
        holidays,
        MISSING,
    )
    assert number(made, INDEX) == count


def test_a_dead_index_handle_cannot_be_read() -> None:
    assert bridge.call("util_ReadHandle", ["index:9999999"]) == (
        "#ERROR util_ReadHandle: handle is text 'index:9999999' naming no live object, "
        "expected a handle"
    )


def test_the_reporting_lot_is_named_resolved_and_read_back_or_left_unset() -> None:
    schedule, holidays, conventions, specifications = the_parts()
    made = an_index(
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specifications,
        holidays,
        "ICE NG",
    )
    kinds, slots, joined = read(made)
    assert rows((kinds, slots, joined)) == [
        [*INDEX_HEADERS, "lot_size", "lot_unit", "lot_quote_quantity", "lot_coefficient"],
        [*INDEX_TYPES, "float64", "str", "float64", "float64"],
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            "futures",
            3.0,
            2.0,
            1.0,
            "ICE NG",
            2500.0,
            "MMBTU",
            2500.0,
            2500.0,
        ],
    ]
    assert kinds[2].tolist()[6:] == [TEXT_CODE, NUMBER_CODE, TEXT_CODE, NUMBER_CODE, NUMBER_CODE]
    assert bridge.call(
        "_CreateIndex",
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            conventions,
            specifications,
            seam_key(holidays),
            "LOT",
            seam_calendars(),
        ],
    ) == (
        "#ERROR _CreateIndex: ValueError: reporting_lot is 'LOT', expected one of the "
        "specifications: 'NYMEX NG', 'ICE NG'"
    )
    assert (
        bridge.call(
            "_CreateIndex",
            [
                "Henry Hub NYMEX",
                "Henry Hub natural gas - NYMEX",
                schedule,
                conventions,
                specifications,
                seam_key(holidays),
                None,
                seam_calendars(),
            ],
        )
        == "#ERROR _CreateIndex: reporting_lot is blank, expected text"
    )
    assert (
        bridge.call(
            "_CreateIndex",
            [
                "Henry Hub NYMEX",
                "Henry Hub natural gas - NYMEX",
                schedule,
                conventions,
                specifications,
                seam_key(holidays),
                1.0,
                seam_calendars(),
            ],
        )
        == "#ERROR _CreateIndex: reporting_lot is number 1.0, expected text"
    )


# --- the display name, readable-index-names.md ---------------------------------------------------


def test_the_display_name_reads_back_beside_the_name_and_is_text_as_typed() -> None:
    schedule, holidays, conventions, specifications = the_parts()
    made = an_index(
        "WTI",
        "West Texas Intermediate crude oil - NYMEX",
        schedule,
        conventions,
        specifications,
        holidays,
        MISSING,
    )
    assert ":index:WTI:" in made  # the handle keeps the name
    kinds, slots, joined = read(made)
    assert rows((kinds, slots, joined))[0][:3] == ["name", "display_name", "kind"]
    assert rows((kinds, slots, joined))[1][:3] == ["str", "str", "str"]
    assert rows((kinds, slots, joined))[2][:3] == [
        "WTI",
        "West Texas Intermediate crude oil - NYMEX",
        "futures",
    ]
    assert kinds[2].tolist()[:3] == [TEXT_CODE, TEXT_CODE, TEXT_CODE]
    same = an_index("WTI", "WTI", schedule, conventions, specifications, holidays, MISSING)
    assert rows(read(same))[2][:2] == ["WTI", "WTI"]
    spaced = an_index(
        "WTI", " West Texas Intermediate ", schedule, conventions, specifications, holidays, MISSING
    )
    assert rows(read(spaced))[2][1] == " West Texas Intermediate "


@pytest.mark.parametrize(
    ("value", "words"),
    [(MISSING, "missing"), (None, "blank"), (1.0, "number 1.0"), ("", "empty text")],
    ids=["left out", "a blank", "a number", "empty text"],
)
def test_a_display_name_that_is_not_text_is_refused_in_the_seams_words(
    value: object, words: str
) -> None:
    schedule, holidays, conventions, specifications = the_parts()
    assert (
        bridge.call(
            "_CreateIndex",
            [
                "WTI",
                value,
                schedule,
                conventions,
                specifications,
                seam_key(holidays),
                MISSING,
                seam_calendars(),
            ],
        )
        == f"#ERROR _CreateIndex: display_name is {words}, expected text"
    )
