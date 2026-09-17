"""The market definitions through the seam: what each creator shows for a right and a wrong
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
from goosedove.market_definitions.contract_spec import ContractSpec
from goosedove.market_definitions.expiry_schedule import ExpirySchedule
from goosedove.market_definitions.holiday_calendar import HolidayCalendar
from goosedove.market_definitions.market_conventions import MarketConventions

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

# The conventions page's sample as the sheet sends it: five texts, an index quoted in dollars per
# barrel, settled in dollars, its quantity a volume stated in barrels.
UNITS = ["USD", "BBL", "USD", "volume", "BBL"]
CONVENTIONS = re.compile(r"market_conventions:[0-9a-f]{6}:([0-9]{6})")

# The spec page's sample as the sheet sends it: a name, and three numbers, the lot size whole.
FACTS = ["WTI", 1000.0, 3.0, 2.0]
SPEC = re.compile(r"contract_spec:[0-9a-f]{6}:([0-9]{6})")


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


# --- CreateMarketConventions ----------------------------------------------------


# The library has no consumer of the conventions yet, so this hidden reader proves that a handle
# resolves to the conventions the seam kept, the five codes in their fields.
@probe
def ReadMarketConventions(conventions: Handle[MarketConventions]) -> str:
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
    text = bridge.call("CreateMarketConventions", list(codes))
    assert isinstance(text, str) and CONVENTIONS.fullmatch(text), text
    return text


def test_market_conventions_are_created_from_five_codes_and_read_back_in_order() -> None:
    assert bridge.call("ReadMarketConventions", [the_conventions(*UNITS)]) == (
        "USD BBL USD volume BBL"
    )


# Each argument alone, left to right: the first bad one is named, in the seam's words.
@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            ["USD", "BBL", "USD", "volume", None],
            "#ERROR CreateMarketConventions: quantity_unit is blank, expected text",
        ),
        (
            ["USD", "BBL", 1.0, "volume", "BBL"],
            "#ERROR CreateMarketConventions: currency_unit is number 1.0, expected text",
        ),
        (
            ["", "BBL", "USD", "volume", "BBL"],
            "#ERROR CreateMarketConventions: quote_currency_unit is empty text, expected text",
        ),
        (
            ["USD", Cells.from_rows([["BBL"]]), "USD", "volume", "BBL"],
            "#ERROR CreateMarketConventions: quote_quantity_unit is 1x1 array, expected text",
        ),
        (
            ["USD", "BBL", "USD", "volume", MISSING],
            "#ERROR CreateMarketConventions: quantity_unit is missing, expected text",
        ),
        (
            ["USD", "BBL", True, None, "BBL"],
            "#ERROR CreateMarketConventions: currency_unit is boolean TRUE, expected text",
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
def test_market_conventions_that_cannot_be_made_say_why(args: list[object], text: str) -> None:
    assert bridge.call("CreateMarketConventions", args) == text


def test_a_handle_of_another_kind_is_not_market_conventions() -> None:
    other = a_calendar(HOLIDAYS)
    assert bridge.call("ReadMarketConventions", [other]) == (
        f"#ERROR ReadMarketConventions: conventions is holiday calendar handle {other!r}, "
        "expected market conventions handle"
    )


# --- CreateContractSpec -----------------------------------------------------------


# The library has no consumer of a spec yet, so this hidden reader proves that a handle resolves
# to the spec the seam kept, typed: the name as text, the lot size whole, the fees as numbers.
@probe
def ReadContractSpec(spec: Handle[ContractSpec]) -> str:
    return f"{spec.name} {spec.lot_size} {spec.brokerage_rate_per_lot} {spec.clearing_rate_per_lot}"


def a_spec(*facts: object) -> str:
    text = bridge.call("CreateContractSpec", list(facts))
    assert isinstance(text, str) and SPEC.fullmatch(text), text
    return text


def test_a_contract_spec_is_created_from_four_facts_and_read_back_typed() -> None:
    assert bridge.call("ReadContractSpec", [a_spec(*FACTS)]) == "WTI 1000 3.0 2.0"


# Each argument alone, left to right: the first bad one is named, in the seam's words.
@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            ["WTI", 2.5, 3.0, 2.0],
            "#ERROR CreateContractSpec: lot_size is number 2.5, expected whole number",
        ),
        (
            ["WTI", True, 3.0, 2.0],
            "#ERROR CreateContractSpec: lot_size is boolean TRUE, expected whole number",
        ),
        ([None, 1000.0, 3.0, 2.0], "#ERROR CreateContractSpec: name is blank, expected text"),
        (
            ["WTI", 1000.0, "three", 2.0],
            "#ERROR CreateContractSpec: brokerage_rate_per_lot is text 'three', expected number",
        ),
        (
            ["WTI", 1000.0, 3.0, MISSING],
            "#ERROR CreateContractSpec: clearing_rate_per_lot is missing, expected number",
        ),
        (
            ["WTI", Cells.from_rows([[1000.0]]), 3.0, 2.0],
            "#ERROR CreateContractSpec: lot_size is 1x1 array, expected whole number",
        ),
        ([1.0, 2.5, 3.0, 2.0], "#ERROR CreateContractSpec: name is number 1.0, expected text"),
    ],
    ids=[
        "a lot size with a fraction",
        "a boolean lot size",
        "a blank name",
        "text where a fee is expected",
        "a fee left out",
        "a one-cell range",
        "two wrong, the earlier named",
    ],
)
def test_a_contract_spec_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("CreateContractSpec", args) == text


def test_a_handle_of_another_kind_is_not_a_contract_spec() -> None:
    other = the_conventions(*UNITS)
    assert bridge.call("ReadContractSpec", [other]) == (
        f"#ERROR ReadContractSpec: spec is market conventions handle {other!r}, "
        "expected contract spec handle"
    )


# The seam holds one line on both sides of a lot size: every whole number a cell holds exactly is
# created and read back through ReadHandle as it was, and one beyond it is refused on creation,
# in the way out's words, rather than making a spec the reader cannot show.
@given(lot_size=st.integers(-(2**53), 2**53))
def test_any_lot_size_a_cell_holds_exactly_is_created_and_read_back(lot_size: int) -> None:
    spill = bridge.call("ReadHandle", [a_spec("WTI", float(lot_size), 3.0, 2.0)])
    assert isinstance(spill, tuple), spill
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2, 1] == float(lot_size)


@pytest.mark.parametrize("lot_size", [1e16, 1e20, 9007199254740994.0, -1e16])
def test_a_lot_size_beyond_what_a_cell_holds_exactly_is_refused_on_creation(
    lot_size: float,
) -> None:
    assert bridge.call("CreateContractSpec", ["WTI", lot_size, 3.0, 2.0]) == (
        f"#ERROR CreateContractSpec: lot_size is number {lot_size!r}, "
        "beyond what a cell holds exactly"
    )
