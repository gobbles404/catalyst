"""The index definitions through the seam: what each creator shows for a right and a wrong
call, and that its handle resolves to the object the seam kept."""

import re
from typing import cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle
from goosedove.excel.probes import probe
from goosedove.index_definitions.contract_specifications import ContractSpecifications
from goosedove.index_definitions.delivery_schedule import DeliverySchedule
from goosedove.index_definitions.expiry_schedule import ExpirySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index_conventions import IndexConventions
from goosedove.index_definitions.publication_schedule import PublicationSchedule

# The first three contracts of the page's sample as the sheet sends them: codes as text, dates as
# serials, 19 May, 22 June and 21 July 2026 for the futures and a few days earlier for the options.
CODES = Cells.from_rows([["m26"], ["n26"], ["q26"]])
FUTURES = Cells.from_rows([[46161.0], [46195.0], [46224.0]])
OPTIONS = Cells.from_rows([[46156.0], [46189.0], [46219.0]])
PUBLICATIONS = Cells.from_rows([[46162.0], [46196.0], [46225.0]])
HANDLE = re.compile(r"expiry_schedule:[0-9a-f]{6}:([0-9]{6})")

# The first three days of the calendar page's sample as the sheet sends them: serials for
# 1 January, 19 January and 16 February 2026.
HOLIDAYS = Cells.from_rows([[46023.0], [46041.0], [46069.0]])
CALENDAR = re.compile(r"holiday_calendar:[0-9a-f]{6}:([0-9]{6})")

# The conventions page's sample as the sheet sends it: five texts, an index quoted in dollars per
# barrel, settled in dollars, its quantity a volume stated in barrels.
UNITS = ["USD", "BBL", "USD", "volume", "BBL"]
CONVENTIONS = re.compile(r"index_conventions:[0-9a-f]{6}:([0-9]{6})")

# The specifications page's sample as the sheet sends it: the header row, then one row per
# contract, gas traded as NYMEX lots and as ICE lots, the name as text and the lot size and fees
# as numbers.
SPECIFICATION_HEADERS = Cells.from_rows(
    [["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)
SPECIFICATION_BODY = Cells.from_rows(
    [["NYMEX NG", 10000.0, 3.0, 2.0], ["ICE NG", 2500.0, 0.75, 0.5]]
)
SPECIFICATIONS = re.compile(r"contract_specifications:[0-9a-f]{6}:([0-9]{6})")


def days_or_none(days: NDArray[np.datetime64] | None) -> str:
    return "none" if days is None else " ".join(str(day) for day in days)


# The library has no consumer of a schedule yet, so this hidden reader proves that a handle
# resolves to the schedule the seam kept, with its columns as they arrived, a column left out
# reading none.
@probe
def ReadExpirySchedule(schedule: Handle[ExpirySchedule]) -> str:
    return (
        f"{' '.join(schedule.codes)} | {days_or_none(schedule.future_expiry)} | "
        f"{days_or_none(schedule.option_expiry)} | {days_or_none(schedule.publication_date)}"
    )


def a_schedule(*columns: object) -> str:
    text = bridge.call("_CreateExpirySchedule", list(columns))
    assert isinstance(text, str) and HANDLE.fullmatch(text), text
    return text


def number(text: str, handle: re.Pattern[str] = HANDLE) -> int:
    match = handle.fullmatch(text)
    assert match, text
    return int(match.group(1))


def test_a_schedule_is_created_from_three_columns_and_read_back_through_its_handle() -> None:
    assert bridge.call("ReadExpirySchedule", [a_schedule(CODES, FUTURES, OPTIONS, MISSING)]) == (
        "m26 n26 q26 | 2026-05-19 2026-06-22 2026-07-21 | 2026-05-14 2026-06-16 2026-07-16 | none"
    )


def test_the_third_column_left_out_is_an_index_without_options() -> None:
    assert bridge.call("ReadExpirySchedule", [a_schedule(CODES, FUTURES, MISSING, MISSING)]) == (
        "m26 n26 q26 | 2026-05-19 2026-06-22 2026-07-21 | none | none"
    )


def test_the_fourth_column_is_the_publication_dates() -> None:
    schedule = a_schedule(CODES, FUTURES, OPTIONS, PUBLICATIONS)
    assert bridge.call("ReadExpirySchedule", [schedule]) == (
        "m26 n26 q26 | 2026-05-19 2026-06-22 2026-07-21 | 2026-05-14 2026-06-16 2026-07-16 | "
        "2026-05-20 2026-06-23 2026-07-22"
    )


# The options left out and the publication dates given: the formula reads
# =_CreateExpirySchedule(A2:A4, B2:B4, , D2:D4), and the empty slot arrives as missing.
def test_publication_dates_are_taken_without_options() -> None:
    schedule = a_schedule(CODES, FUTURES, MISSING, PUBLICATIONS)
    assert bridge.call("ReadExpirySchedule", [schedule]) == (
        "m26 n26 q26 | 2026-05-19 2026-06-22 2026-07-21 | none | 2026-05-20 2026-06-23 2026-07-22"
    )


def test_a_one_row_schedule_with_every_column_is_a_schedule() -> None:
    one = [Cells.from_rows([[x]]) for x in ("m26", 46161.0, 46156.0, 46162.0)]
    assert bridge.call("ReadExpirySchedule", [a_schedule(*one)]) == (
        "m26 | 2026-05-19 | 2026-05-14 | 2026-05-20"
    )


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [CODES, Cells.from_rows([[46161.0], [46195.0]]), OPTIONS, MISSING],
            "#ERROR _CreateExpirySchedule: ValueError: future_expiry has 2 dates, expected 3, "
            "one per future_code",
        ),
        (
            [CODES, FUTURES, Cells.from_rows([[46156.0], [None], [46219.0]]), MISSING],
            "#ERROR _CreateExpirySchedule: option_expiry cell (2, 1) is blank, expected date",
        ),
        (
            [CODES, FUTURES, None, MISSING],
            "#ERROR _CreateExpirySchedule: option_expiry is blank, expected column of dates",
        ),
        (
            [Cells.from_rows([["m26"], [46161.0], ["q26"]]), FUTURES, MISSING, MISSING],
            "#ERROR _CreateExpirySchedule: future_code cell (2, 1) is number 46161.0, "
            "expected text",
        ),
        (
            [CODES, Cells.from_rows([[46161.0, 46195.0, 46224.0]]), MISSING, MISSING],
            "#ERROR _CreateExpirySchedule: future_expiry is 1x3 array, expected column of dates",
        ),
        (
            [CODES, MISSING, MISSING, MISSING],
            "#ERROR _CreateExpirySchedule: future_expiry is missing, expected column of dates",
        ),
        (
            [CODES, FUTURES, OPTIONS, Cells.from_rows([[46162.0], [46196.0]])],
            "#ERROR _CreateExpirySchedule: ValueError: publication_date has 2 dates, expected 3, "
            "one per future_code",
        ),
        (
            [CODES, FUTURES, MISSING, Cells.from_rows([[46162.0]])],
            "#ERROR _CreateExpirySchedule: ValueError: publication_date has 1 date, expected 3, "
            "one per future_code",
        ),
        (
            [CODES, FUTURES, OPTIONS, Cells.from_rows([[46162.0], [None], [46225.0]])],
            "#ERROR _CreateExpirySchedule: publication_date cell (2, 1) is blank, expected date",
        ),
        (
            [CODES, FUTURES, OPTIONS, Cells.from_rows([["x"], [46196.0], [46225.0]])],
            "#ERROR _CreateExpirySchedule: publication_date cell (1, 1) is text 'x', expected date",
        ),
        (
            [CODES, FUTURES, MISSING, None],
            "#ERROR _CreateExpirySchedule: publication_date is blank, expected column of dates",
        ),
        (
            [CODES, FUTURES, MISSING, Cells.from_rows([[46162.0, 46196.0, 46225.0]])],
            "#ERROR _CreateExpirySchedule: publication_date is 1x3 array, expected column of dates",
        ),
        (
            [CODES, FUTURES, Cells.from_rows([[46156.0]]), Cells.from_rows([[46162.0]])],
            "#ERROR _CreateExpirySchedule: ValueError: option_expiry has 1 date, expected 3, "
            "one per future_code",
        ),
    ],
    ids=[
        "a futures column one row short",
        "a blank in the options column",
        "a blank cell where the options column should be",
        "a number among the codes",
        "a row of dates",
        "the futures column left out",
        "a publication column one row short",
        "one publication date for three codes, without options",
        "a blank in the publication column",
        "text in the publication column",
        "a blank cell where the publication column should be",
        "a row of publication dates",
        "options and publications both short, the options named first",
    ],
)
def test_a_schedule_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreateExpirySchedule", args) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap.
def test_a_failed_construction_publishes_no_object_and_no_handle() -> None:
    before = number(a_schedule(CODES, FUTURES, MISSING, MISSING))
    short = Cells.from_rows([[46161.0], [46195.0]])
    assert bridge.call("_CreateExpirySchedule", [CODES, short, OPTIONS, MISSING]) == (
        "#ERROR _CreateExpirySchedule: ValueError: future_expiry has 2 dates, expected 3, "
        "one per future_code"
    )
    assert bridge.call("_CreateExpirySchedule", [CODES, FUTURES, OPTIONS, short]) == (
        "#ERROR _CreateExpirySchedule: ValueError: publication_date has 2 dates, expected 3, "
        "one per future_code"
    )
    assert number(a_schedule(CODES, FUTURES, MISSING, MISSING)) == before + 1


def test_a_handle_of_another_kind_is_not_a_schedule() -> None:
    other = cast(str, bridge.call("_CreateValuationDate", [46161.0, 0.5]))
    assert bridge.call("ReadExpirySchedule", [other]) == (
        f"#ERROR ReadExpirySchedule: schedule is valuation date handle {other!r}, "
        "expected expiry schedule handle"
    )


# --- _CreateHolidayCalendar ------------------------------------------------------


# The library has no consumer of a calendar yet, so this hidden reader proves that a handle
# resolves to the calendar the seam kept, with its column as it arrived.
@probe
def ReadHolidayCalendar(calendar: Handle[HolidayCalendar]) -> str:
    return " ".join(str(day) for day in calendar.holiday)


def a_calendar(column: object) -> str:
    text = bridge.call("_CreateHolidayCalendar", [column])
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
    assert bridge.call("_CreateHolidayCalendar", [column]) == text


# A rejected column stops the call before the function runs, so nothing is published and the
# publication number does not move.
def test_a_rejected_column_publishes_no_object_and_no_handle() -> None:
    before = number(a_calendar(HOLIDAYS), CALENDAR)
    assert bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46023.0], [None]])]) == (
        "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date"
    )
    assert number(a_calendar(HOLIDAYS), CALENDAR) == before + 1


def test_a_handle_of_another_kind_is_not_a_calendar() -> None:
    other = a_schedule(CODES, FUTURES, MISSING, MISSING)
    assert bridge.call("ReadHolidayCalendar", [other]) == (
        f"#ERROR ReadHolidayCalendar: calendar is expiry schedule handle {other!r}, "
        "expected holiday calendar handle"
    )


# --- _CreatePublicationSchedule ---------------------------------------------------


# The publication schedule page's sample as the sheet sends it: two codes as text and two
# serials, 2 November and 1 December 2026.
PUBLISHED_CODES = Cells.from_rows([["X26"], ["Z26"]])
PUBLISHED_DATES = Cells.from_rows([[46328.0], [46357.0]])
PUBLICATION = re.compile(r"publication_schedule:[0-9a-f]{6}:([0-9]{6})")


# The library has no consumer of a publication schedule yet, so this hidden reader proves that
# a handle resolves to the schedule the seam kept, with its columns as they arrived.
@probe
def ReadPublicationSchedule(schedule: Handle[PublicationSchedule]) -> str:
    return f"{' '.join(schedule.codes)} | {days_or_none(schedule.publication_date)}"


def a_publication_schedule(codes: object, published: object) -> str:
    text = bridge.call("_CreatePublicationSchedule", [codes, published])
    assert isinstance(text, str) and PUBLICATION.fullmatch(text), text
    return text


def test_a_publication_schedule_is_created_from_two_columns_and_read_back() -> None:
    schedule = a_publication_schedule(PUBLISHED_CODES, PUBLISHED_DATES)
    assert bridge.call("ReadPublicationSchedule", [schedule]) == "X26 Z26 | 2026-11-02 2026-12-01"


# Two single cells are two columns of one, so a schedule of one contract needs no range.
def test_two_single_cells_are_a_publication_schedule_of_one_contract() -> None:
    schedule = a_publication_schedule("X26", 46328.0)
    assert bridge.call("ReadPublicationSchedule", [schedule]) == "X26 | 2026-11-02"


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [PUBLISHED_CODES, Cells.from_rows([[46328.0], [46357.0], [46391.0]])],
            "#ERROR _CreatePublicationSchedule: ValueError: publication_date has 3 dates, "
            "expected 2, one per contract_code",
        ),
        (
            ["X26", PUBLISHED_DATES],
            "#ERROR _CreatePublicationSchedule: ValueError: publication_date has 2 dates, "
            "expected 1, one per contract_code",
        ),
        (
            [PUBLISHED_CODES, Cells.from_rows([[46328.0], [None]])],
            "#ERROR _CreatePublicationSchedule: publication_date cell (2, 1) is blank, "
            "expected date",
        ),
        (
            [PUBLISHED_CODES, Cells.from_rows([[46328.0], [46357.5]])],
            "#ERROR _CreatePublicationSchedule: publication_date cell (2, 1) is number 46357.5, "
            "expected date",
        ),
        (
            [PUBLISHED_CODES, Cells.from_rows([["2-Nov-2026"], [46357.0]])],
            "#ERROR _CreatePublicationSchedule: publication_date cell (1, 1) is text "
            "'2-Nov-2026', expected date",
        ),
        (
            [Cells.from_rows([["X26"], [46023.0]]), PUBLISHED_DATES],
            "#ERROR _CreatePublicationSchedule: contract_code cell (2, 1) is number 46023.0, "
            "expected text",
        ),
        (
            [Cells.from_rows([["X26"], [""]]), PUBLISHED_DATES],
            "#ERROR _CreatePublicationSchedule: contract_code cell (2, 1) is empty text, "
            "expected text",
        ),
        (
            [Cells.from_rows([["X26", "Z26"]]), PUBLISHED_DATES],
            "#ERROR _CreatePublicationSchedule: contract_code is 1x2 array, "
            "expected column of text",
        ),
        (
            [PUBLISHED_CODES, Cells.from_rows([[46328.0, 46357.0]])],
            "#ERROR _CreatePublicationSchedule: publication_date is 1x2 array, "
            "expected column of dates",
        ),
        (
            [MISSING, PUBLISHED_DATES],
            "#ERROR _CreatePublicationSchedule: contract_code is missing, expected column of text",
        ),
        (
            [PUBLISHED_CODES, MISSING],
            "#ERROR _CreatePublicationSchedule: publication_date is missing, "
            "expected column of dates",
        ),
        (
            [None, PUBLISHED_DATES],
            "#ERROR _CreatePublicationSchedule: contract_code is blank, expected column of text",
        ),
        (
            [PUBLISHED_CODES, None],
            "#ERROR _CreatePublicationSchedule: publication_date is blank, "
            "expected column of dates",
        ),
        (
            [Cells.from_rows([["X26"], [46023.0]]), Cells.from_rows([[46328.0], [None]])],
            "#ERROR _CreatePublicationSchedule: contract_code cell (2, 1) is number 46023.0, "
            "expected text",
        ),
    ],
    ids=[
        "a date column one row long",
        "two dates for one code",
        "a blank in the date column",
        "a date with a time",
        "text in the date column",
        "a number among the codes",
        "empty text among the codes",
        "a row of codes",
        "a row of dates",
        "the codes left out",
        "the dates left out",
        "a blank cell where the codes should be",
        "a blank cell where the dates should be",
        "both columns wrong, the codes named first",
    ],
)
def test_a_publication_schedule_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreatePublicationSchedule", args) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap,
# whether the library or the seam refused the call.
def test_a_failed_publication_schedule_publishes_no_object_and_no_handle() -> None:
    before = number(a_publication_schedule(PUBLISHED_CODES, PUBLISHED_DATES), PUBLICATION)
    assert bridge.call(
        "_CreatePublicationSchedule", [PUBLISHED_CODES, Cells.from_rows([[46328.0]])]
    ) == (
        "#ERROR _CreatePublicationSchedule: ValueError: publication_date has 1 date, "
        "expected 2, one per contract_code"
    )
    assert (
        bridge.call(
            "_CreatePublicationSchedule", [PUBLISHED_CODES, Cells.from_rows([[46328.0], [None]])]
        )
        == "#ERROR _CreatePublicationSchedule: publication_date cell (2, 1) is blank, expected date"
    )
    assert number(a_publication_schedule(PUBLISHED_CODES, PUBLISHED_DATES), PUBLICATION) == (
        before + 1
    )


def test_a_handle_of_another_kind_is_not_a_publication_schedule() -> None:
    other = a_schedule(CODES, FUTURES, MISSING, PUBLICATIONS)
    assert bridge.call("ReadPublicationSchedule", [other]) == (
        f"#ERROR ReadPublicationSchedule: schedule is expiry schedule handle {other!r}, "
        "expected publication schedule handle"
    )


# --- _CreateDeliverySchedule -------------------------------------------------------


# The delivery schedule page's sample as the sheet sends it: two codes as text and the serials
# of 1 and 30 November and 1 and 31 December 2026.
DELIVERY_CODES = Cells.from_rows([["X26"], ["Z26"]])
DELIVERY_STARTS = Cells.from_rows([[46327.0], [46357.0]])
DELIVERY_ENDS = Cells.from_rows([[46356.0], [46387.0]])
DELIVERY = re.compile(r"delivery_schedule:[0-9a-f]{6}:([0-9]{6})")


# The library has no consumer of a delivery schedule yet, so this hidden reader proves that a
# handle resolves to the schedule the seam kept, with its columns as they arrived.
@probe
def ReadDeliverySchedule(schedule: Handle[DeliverySchedule]) -> str:
    return (
        f"{' '.join(schedule.codes)} | {days_or_none(schedule.delivery_start)} | "
        f"{days_or_none(schedule.delivery_end)}"
    )


def a_delivery_schedule(codes: object, starts: object, ends: object) -> str:
    text = bridge.call("_CreateDeliverySchedule", [codes, starts, ends])
    assert isinstance(text, str) and DELIVERY.fullmatch(text), text
    return text


def test_a_delivery_schedule_is_created_from_three_columns_and_read_back() -> None:
    schedule = a_delivery_schedule(DELIVERY_CODES, DELIVERY_STARTS, DELIVERY_ENDS)
    assert bridge.call("ReadDeliverySchedule", [schedule]) == (
        "X26 Z26 | 2026-11-01 2026-12-01 | 2026-11-30 2026-12-31"
    )


# Three single cells are three columns of one, so a schedule of one contract needs no range; and
# equal dates are a period of one day.
def test_three_single_cells_are_a_delivery_schedule_of_one_contract() -> None:
    schedule = a_delivery_schedule("X26", 46327.0, 46356.0)
    assert bridge.call("ReadDeliverySchedule", [schedule]) == "X26 | 2026-11-01 | 2026-11-30"
    one_day = a_delivery_schedule("Z26", 46357.0, 46357.0)
    assert bridge.call("ReadDeliverySchedule", [one_day]) == "Z26 | 2026-12-01 | 2026-12-01"


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [DELIVERY_CODES, Cells.from_rows([[46327.0]]), DELIVERY_ENDS],
            "#ERROR _CreateDeliverySchedule: ValueError: delivery_start has 1 date, expected 2, "
            "one per contract_code",
        ),
        (
            [DELIVERY_CODES, DELIVERY_STARTS, Cells.from_rows([[46356.0], [46387.0], [46418.0]])],
            "#ERROR _CreateDeliverySchedule: ValueError: delivery_end has 3 dates, expected 2, "
            "one per contract_code",
        ),
        (
            [DELIVERY_CODES, DELIVERY_STARTS, Cells.from_rows([[46356.0], [46356.0]])],
            "#ERROR _CreateDeliverySchedule: ValueError: delivery_end row 2 is 2026-11-30, "
            "expected a date on or after row 2's delivery_start 2026-12-01",
        ),
        (
            [DELIVERY_CODES, DELIVERY_ENDS, DELIVERY_STARTS],
            "#ERROR _CreateDeliverySchedule: ValueError: delivery_end row 1 is 2026-11-01, "
            "expected a date on or after row 1's delivery_start 2026-11-30",
        ),
        (
            [DELIVERY_CODES, DELIVERY_STARTS, Cells.from_rows([[46356.0], [None]])],
            "#ERROR _CreateDeliverySchedule: delivery_end cell (2, 1) is blank, expected date",
        ),
        (
            [DELIVERY_CODES, Cells.from_rows([[46327.5], [46357.0]]), DELIVERY_ENDS],
            "#ERROR _CreateDeliverySchedule: delivery_start cell (1, 1) is number 46327.5, "
            "expected date",
        ),
        (
            [DELIVERY_CODES, DELIVERY_STARTS, Cells.from_rows([["30-Nov-2026"], [46387.0]])],
            "#ERROR _CreateDeliverySchedule: delivery_end cell (1, 1) is text '30-Nov-2026', "
            "expected date",
        ),
        (
            [Cells.from_rows([["X26"], [46023.0]]), DELIVERY_STARTS, DELIVERY_ENDS],
            "#ERROR _CreateDeliverySchedule: contract_code cell (2, 1) is number 46023.0, "
            "expected text",
        ),
        (
            [Cells.from_rows([["X26", "Z26"]]), DELIVERY_STARTS, DELIVERY_ENDS],
            "#ERROR _CreateDeliverySchedule: contract_code is 1x2 array, expected column of text",
        ),
        (
            [DELIVERY_CODES, DELIVERY_STARTS, Cells.from_rows([[46356.0, 46387.0]])],
            "#ERROR _CreateDeliverySchedule: delivery_end is 1x2 array, expected column of dates",
        ),
        (
            [MISSING, DELIVERY_STARTS, DELIVERY_ENDS],
            "#ERROR _CreateDeliverySchedule: contract_code is missing, expected column of text",
        ),
        (
            [DELIVERY_CODES, MISSING, DELIVERY_ENDS],
            "#ERROR _CreateDeliverySchedule: delivery_start is missing, expected column of dates",
        ),
        (
            [DELIVERY_CODES, DELIVERY_STARTS, MISSING],
            "#ERROR _CreateDeliverySchedule: delivery_end is missing, expected column of dates",
        ),
        (
            [DELIVERY_CODES, None, DELIVERY_ENDS],
            "#ERROR _CreateDeliverySchedule: delivery_start is blank, expected column of dates",
        ),
        (
            [DELIVERY_CODES, DELIVERY_STARTS, None],
            "#ERROR _CreateDeliverySchedule: delivery_end is blank, expected column of dates",
        ),
        (
            [DELIVERY_CODES, Cells.from_rows([[46327.0]]), Cells.from_rows([[46356.0], [None]])],
            "#ERROR _CreateDeliverySchedule: delivery_end cell (2, 1) is blank, expected date",
        ),
    ],
    ids=[
        "a start column one row short",
        "an end column one row long",
        "an end before its start",
        "the columns swapped",
        "a blank in the end column",
        "a start with a time",
        "text in the end column",
        "a number among the codes",
        "a row of codes",
        "a row of ends",
        "the codes left out",
        "the starts left out",
        "the ends left out",
        "a blank cell where the starts should be",
        "a blank cell where the ends should be",
        "the seam's blank before the library's short column",
    ],
)
def test_a_delivery_schedule_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreateDeliverySchedule", args) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap,
# whether the library or the seam refused the call.
def test_a_failed_delivery_schedule_publishes_no_object_and_no_handle() -> None:
    before = number(a_delivery_schedule(DELIVERY_CODES, DELIVERY_STARTS, DELIVERY_ENDS), DELIVERY)
    assert bridge.call(
        "_CreateDeliverySchedule", [DELIVERY_CODES, DELIVERY_STARTS, Cells.from_rows([[46356.0]])]
    ) == (
        "#ERROR _CreateDeliverySchedule: ValueError: delivery_end has 1 date, expected 2, "
        "one per contract_code"
    )
    assert bridge.call(
        "_CreateDeliverySchedule", [DELIVERY_CODES, DELIVERY_ENDS, DELIVERY_STARTS]
    ) == (
        "#ERROR _CreateDeliverySchedule: ValueError: delivery_end row 1 is 2026-11-01, "
        "expected a date on or after row 1's delivery_start 2026-11-30"
    )
    assert (
        bridge.call(
            "_CreateDeliverySchedule",
            [DELIVERY_CODES, DELIVERY_STARTS, Cells.from_rows([[46356.0], [None]])],
        )
        == "#ERROR _CreateDeliverySchedule: delivery_end cell (2, 1) is blank, expected date"
    )
    assert number(
        a_delivery_schedule(DELIVERY_CODES, DELIVERY_STARTS, DELIVERY_ENDS), DELIVERY
    ) == (before + 1)


def test_a_handle_of_another_kind_is_not_a_delivery_schedule() -> None:
    other = a_schedule(CODES, FUTURES, MISSING, MISSING)
    assert bridge.call("ReadDeliverySchedule", [other]) == (
        f"#ERROR ReadDeliverySchedule: schedule is expiry schedule handle {other!r}, "
        "expected delivery schedule handle"
    )


# --- _CreateIndexConventions ----------------------------------------------------


# The library has no consumer of the conventions yet, so this hidden reader proves that a handle
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
        "USD BBL USD volume BBL"
    )


# Each argument alone, left to right: the first bad one is named, in the seam's words.
@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            ["USD", "BBL", "USD", "volume", None],
            "#ERROR _CreateIndexConventions: quantity_unit is blank, expected text",
        ),
        (
            ["USD", "BBL", 1.0, "volume", "BBL"],
            "#ERROR _CreateIndexConventions: currency_unit is number 1.0, expected text",
        ),
        (
            ["", "BBL", "USD", "volume", "BBL"],
            "#ERROR _CreateIndexConventions: quote_currency_unit is empty text, expected text",
        ),
        (
            ["USD", Cells.from_rows([["BBL"]]), "USD", "volume", "BBL"],
            "#ERROR _CreateIndexConventions: quote_quantity_unit is 1x1 array, expected text",
        ),
        (
            ["USD", "BBL", "USD", "volume", MISSING],
            "#ERROR _CreateIndexConventions: quantity_unit is missing, expected text",
        ),
        (
            ["USD", "BBL", True, None, "BBL"],
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


# --- _CreateContractSpecifications ----------------------------------------------------------


# The library has no consumer of the specifications yet, so this hidden reader proves that a
# handle resolves to the specifications the seam kept, typed: names as text, lot sizes whole, fees
# as numbers.
@probe
def ReadContractSpecifications(specifications: Handle[ContractSpecifications]) -> str:
    lots = specifications.lot_sizes
    return (
        f"{' '.join(specifications.names)} | {lots.dtype} {lots.tolist()} | "
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
    ) == ("NYMEX NG ICE NG | float64 [10000.0, 2500.0] | [3.0, 0.75] [2.0, 0.5]")


def test_the_specifications_headers_bind_in_any_order_and_one_row_is_a_table() -> None:
    headers = Cells.from_rows(
        [["CLEARING_RATE_PER_LOT", "Name", "lot_size", "brokerage_rate_per_lot"]]
    )
    body = Cells.from_rows([[2.0, "NYMEX NG", 10000.0, 3.0]])
    assert bridge.call("ReadContractSpecifications", [the_specifications(headers, body)]) == (
        "NYMEX NG | float64 [10000.0] | [3.0] [2.0]"
    )


@pytest.mark.parametrize(
    ("headers", "body", "text"),
    [
        (
            Cells.from_rows([["name", "lot_size", "brokerage", "clearing_rate_per_lot"]]),
            SPECIFICATION_BODY,
            "#ERROR _CreateContractSpecifications: header_row cell (1, 3) is text 'brokerage', "
            "expected one of name, lot_size, brokerage_rate_per_lot or clearing_rate_per_lot",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 2.5, 3.0, 2.0]]),
            "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 2.5, "
            "expected a whole number",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", True, 3.0, 2.0]]),
            "#ERROR _CreateContractSpecifications: table cell (1, 2) is boolean TRUE, "
            "expected number",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, "three", 2.0]]),
            "#ERROR _CreateContractSpecifications: table cell (1, 3) is text 'three', "
            "expected number",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([[1.0, 10000.0, 3.0, 2.0]]),
            "#ERROR _CreateContractSpecifications: table cell (1, 1) is number 1.0, expected text",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, 3.0, 2.0], ["NYMEX NG", 2500.0, 0.75, 0.5]]),
            "#ERROR _CreateContractSpecifications: ValueError: name row 2 is 'NYMEX NG', "
            "already given at row 1",
        ),
        (
            SPECIFICATION_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, 3.0]]),
            "#ERROR _CreateContractSpecifications: header_row has 4 headers, expected 3, "
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
        "a name given twice",
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
    twice = Cells.from_rows([["NYMEX NG", 10000.0, 3.0, 2.0], ["NYMEX NG", 2500.0, 0.75, 0.5]])
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
# from -2^53 to 2^53 is read back exactly, and a whole double beyond, 1E16 say, is kept as it is.
# A double with a fraction is the builder's to refuse.
@given(lot_size=st.integers(-(2**53), 2**53))
def test_any_lot_size_a_cell_holds_exactly_is_created_and_read_back(lot_size: int) -> None:
    body = Cells.from_rows([["NYMEX NG", float(lot_size), 3.0, 2.0]])
    spill = bridge.call("util_ReadHandle", [the_specifications(SPECIFICATION_HEADERS, body)])
    assert isinstance(spill, tuple), spill
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2, 1] == float(lot_size)


@pytest.mark.parametrize("lot_size", [1e16, 1e20, -1e16])
def test_a_whole_double_beyond_two_to_the_fifty_three_is_kept_and_read_back(
    lot_size: float,
) -> None:
    body = Cells.from_rows([["NYMEX NG", lot_size, 3.0, 2.0]])
    spill = bridge.call("util_ReadHandle", [the_specifications(SPECIFICATION_HEADERS, body)])
    assert isinstance(spill, tuple), spill
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2, 1] == lot_size
