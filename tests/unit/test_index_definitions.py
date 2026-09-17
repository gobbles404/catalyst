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
from goosedove.index_definitions.contract_specs import ContractSpecs
from goosedove.index_definitions.expiry_schedule import ExpirySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index_conventions import IndexConventions

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
CONVENTIONS = re.compile(r"index_conventions:[0-9a-f]{6}:([0-9]{6})")

# The specs page's sample as the sheet sends it: the header row, then one row per contract, gas
# traded as NYMEX lots and as ICE lots, the name as text and the lot size and fees as numbers.
SPEC_HEADERS = Cells.from_rows(
    [["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)
SPEC_BODY = Cells.from_rows([["NYMEX NG", 10000.0, 3.0, 2.0], ["ICE NG", 2500.0, 0.75, 0.5]])
SPECS = re.compile(r"contract_specs:[0-9a-f]{6}:([0-9]{6})")


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
    text = bridge.call("_CreateExpirySchedule", list(columns))
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
            "#ERROR _CreateExpirySchedule: ValueError: future_expiry has 2 dates, expected 3, "
            "one per future_code",
        ),
        (
            [CODES, FUTURES, Cells.from_rows([[46156.0], [None], [46219.0]])],
            "#ERROR _CreateExpirySchedule: option_expiry cell (2, 1) is blank, expected date",
        ),
        (
            [CODES, FUTURES, None],
            "#ERROR _CreateExpirySchedule: option_expiry is blank, expected column of dates",
        ),
        (
            [Cells.from_rows([["m26"], [46161.0], ["q26"]]), FUTURES, MISSING],
            "#ERROR _CreateExpirySchedule: future_code cell (2, 1) is number 46161.0, "
            "expected text",
        ),
        (
            [CODES, Cells.from_rows([[46161.0, 46195.0, 46224.0]]), MISSING],
            "#ERROR _CreateExpirySchedule: future_expiry is 1x3 array, expected column of dates",
        ),
        (
            [CODES, MISSING, MISSING],
            "#ERROR _CreateExpirySchedule: future_expiry is missing, expected column of dates",
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
    assert bridge.call("_CreateExpirySchedule", args) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap.
def test_a_failed_construction_publishes_no_object_and_no_handle() -> None:
    before = number(a_schedule(CODES, FUTURES, MISSING))
    short = Cells.from_rows([[46161.0], [46195.0]])
    assert bridge.call("_CreateExpirySchedule", [CODES, short, OPTIONS]) == (
        "#ERROR _CreateExpirySchedule: ValueError: future_expiry has 2 dates, expected 3, "
        "one per future_code"
    )
    assert number(a_schedule(CODES, FUTURES, MISSING)) == before + 1


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
    other = a_schedule(CODES, FUTURES, MISSING)
    assert bridge.call("ReadHolidayCalendar", [other]) == (
        f"#ERROR ReadHolidayCalendar: calendar is expiry schedule handle {other!r}, "
        "expected holiday calendar handle"
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


# --- _CreateContractSpecs ----------------------------------------------------------


# The library has no consumer of the specs yet, so this hidden reader proves that a handle
# resolves to the specs the seam kept, typed: names as text, lot sizes whole, fees as numbers.
@probe
def ReadContractSpecs(specs: Handle[ContractSpecs]) -> str:
    return (
        f"{' '.join(specs.names)} | {specs.lot_sizes.dtype} {specs.lot_sizes.tolist()} | "
        f"{specs.brokerage_rates_per_lot.tolist()} {specs.clearing_rates_per_lot.tolist()}"
    )


def the_specs(headers: object, body: object) -> str:
    text = bridge.call("_CreateContractSpecs", [headers, body])
    assert isinstance(text, str) and SPECS.fullmatch(text), text
    return text


def test_contract_specs_are_created_from_a_table_and_read_back_typed() -> None:
    assert bridge.call("ReadContractSpecs", [the_specs(SPEC_HEADERS, SPEC_BODY)]) == (
        "NYMEX NG ICE NG | float64 [10000.0, 2500.0] | [3.0, 0.75] [2.0, 0.5]"
    )


def test_the_specs_headers_bind_in_any_order_and_one_row_is_a_table() -> None:
    headers = Cells.from_rows(
        [["CLEARING_RATE_PER_LOT", "Name", "lot_size", "brokerage_rate_per_lot"]]
    )
    body = Cells.from_rows([[2.0, "NYMEX NG", 10000.0, 3.0]])
    assert bridge.call("ReadContractSpecs", [the_specs(headers, body)]) == (
        "NYMEX NG | float64 [10000.0] | [3.0] [2.0]"
    )


@pytest.mark.parametrize(
    ("headers", "body", "text"),
    [
        (
            Cells.from_rows([["name", "lot_size", "brokerage", "clearing_rate_per_lot"]]),
            SPEC_BODY,
            "#ERROR _CreateContractSpecs: header_row cell (1, 3) is text 'brokerage', expected one "
            "of name, lot_size, brokerage_rate_per_lot or clearing_rate_per_lot",
        ),
        (
            SPEC_HEADERS,
            Cells.from_rows([["NYMEX NG", 2.5, 3.0, 2.0]]),
            "#ERROR _CreateContractSpecs: ValueError: lot_size row 1 is 2.5, "
            "expected a whole number",
        ),
        (
            SPEC_HEADERS,
            Cells.from_rows([["NYMEX NG", True, 3.0, 2.0]]),
            "#ERROR _CreateContractSpecs: table cell (1, 2) is boolean TRUE, expected number",
        ),
        (
            SPEC_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, "three", 2.0]]),
            "#ERROR _CreateContractSpecs: table cell (1, 3) is text 'three', expected number",
        ),
        (
            SPEC_HEADERS,
            Cells.from_rows([[1.0, 10000.0, 3.0, 2.0]]),
            "#ERROR _CreateContractSpecs: table cell (1, 1) is number 1.0, expected text",
        ),
        (
            SPEC_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, 3.0, 2.0], ["NYMEX NG", 2500.0, 0.75, 0.5]]),
            "#ERROR _CreateContractSpecs: ValueError: name row 2 is 'NYMEX NG', "
            "already given at row 1",
        ),
        (
            SPEC_HEADERS,
            Cells.from_rows([["NYMEX NG", 10000.0, 3.0]]),
            "#ERROR _CreateContractSpecs: header_row has 4 headers, expected 3, "
            "one per column of table",
        ),
        (SPEC_HEADERS, None, "#ERROR _CreateContractSpecs: table is blank, expected table"),
        (SPEC_HEADERS, MISSING, "#ERROR _CreateContractSpecs: table is missing, expected table"),
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
def test_contract_specs_that_cannot_be_made_say_why(
    headers: object, body: object, text: str
) -> None:
    assert bridge.call("_CreateContractSpecs", [headers, body]) == text


def test_a_failed_specs_construction_publishes_no_object_and_no_handle() -> None:
    before = number(the_specs(SPEC_HEADERS, SPEC_BODY), SPECS)
    twice = Cells.from_rows([["NYMEX NG", 10000.0, 3.0, 2.0], ["NYMEX NG", 2500.0, 0.75, 0.5]])
    assert bridge.call("_CreateContractSpecs", [SPEC_HEADERS, twice]) == (
        "#ERROR _CreateContractSpecs: ValueError: name row 2 is 'NYMEX NG', already given at row 1"
    )
    assert number(the_specs(SPEC_HEADERS, SPEC_BODY), SPECS) == before + 1


def test_a_handle_of_another_kind_is_not_contract_specs() -> None:
    other = the_conventions(*UNITS)
    assert bridge.call("ReadContractSpecs", [other]) == (
        f"#ERROR ReadContractSpecs: specs is index conventions handle {other!r}, "
        "expected contract specs handle"
    )


# A lot size crosses as the double the cell holds and goes back out as it came: every whole number
# from -2^53 to 2^53 is read back exactly, and a whole double beyond, 1E16 say, is kept as it is.
# A double with a fraction is the builder's to refuse.
@given(lot_size=st.integers(-(2**53), 2**53))
def test_any_lot_size_a_cell_holds_exactly_is_created_and_read_back(lot_size: int) -> None:
    body = Cells.from_rows([["NYMEX NG", float(lot_size), 3.0, 2.0]])
    spill = bridge.call("util_ReadHandle", [the_specs(SPEC_HEADERS, body)])
    assert isinstance(spill, tuple), spill
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2, 1] == float(lot_size)


@pytest.mark.parametrize("lot_size", [1e16, 1e20, -1e16])
def test_a_whole_double_beyond_two_to_the_fifty_three_is_kept_and_read_back(
    lot_size: float,
) -> None:
    body = Cells.from_rows([["NYMEX NG", lot_size, 3.0, 2.0]])
    spill = bridge.call("util_ReadHandle", [the_specs(SPEC_HEADERS, body)])
    assert isinstance(spill, tuple), spill
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2, 1] == lot_size
