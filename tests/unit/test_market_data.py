"""The market data through the seam: what each creator shows for a right and a wrong call, and
that its handle resolves to the object the seam kept."""

import functools
import re
from typing import cast

import pytest
from test_utilities import read, rows

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle
from goosedove.excel.probes import probe
from goosedove.market_data.daily_fixings import DailyFixings
from goosedove.market_data.iferc_fixings import IfercFixings


def number(text: str, handle: re.Pattern[str]) -> int:
    """The running publication number a handle carries; it moves only when an object is stored."""
    match = handle.fullmatch(text)
    assert match, text
    return int(match.group(1))


def a_valuation_date() -> str:
    """A handle of another kind, for the tests that hand a creator the wrong one."""
    return cast(str, bridge.call("_CreateValuationDate", [46161.0, 0.5]))


# --- _CreateDailyFixings ---------------------------------------------------------


# The page's sample as the sheet sends it: the header row, then four rows of a serial and a
# settle, 1, 4, 5 and 6 May 2026, a Friday and the Monday to Wednesday after it.
MAY_1, MAY_2, MAY_4, MAY_5, MAY_6 = 46143.0, 46144.0, 46146.0, 46147.0, 46148.0
HEADERS = Cells.from_rows([["date", "settle"]])
BODY = Cells.from_rows([[MAY_1, 101.94], [MAY_4, 106.42], [MAY_5, 102.27], [MAY_6, 95.08]])
FIXINGS = re.compile(r"daily_fixings:[0-9a-f]{6}:([0-9]{6})")

# The calendar page's sample as the sheet sends it, the ten days one market is closed in 2026,
# one serial per row; the one in May is the 25th, a Monday. Made once into the handle every
# fixings call takes, so a test that counts publications sees the fixings' alone.
MAY_25 = 46167.0
HOLIDAYS = Cells.from_rows(
    [
        [s]
        for s in (
            46023.0,
            46041.0,
            46069.0,
            46115.0,
            MAY_25,
            46192.0,
            46206.0,
            46272.0,
            46352.0,
            46381.0,
        )
    ]
)
CALENDAR = re.compile(r"holiday_calendar:[0-9a-f]{6}:([0-9]{6})")
THE_CALENDAR = object()  # in a case's arguments: the calendar's handle, made below


@functools.cache
def the_calendar() -> str:
    text = bridge.call("_CreateHolidayCalendar", [HOLIDAYS])
    assert isinstance(text, str) and CALENDAR.fullmatch(text), text
    return text


# The library has no consumer of daily fixings yet, so this hidden reader proves that a handle
# resolves to the fixings the seam kept, with their columns as they arrived.
@probe
def ReadDailyFixings(fixings: Handle[DailyFixings]) -> str:
    days = " ".join(str(day) for day in fixings.dates)
    return f"{days} | {' '.join(repr(float(s)) for s in fixings.settles)}"


def the_fixings(headers: object, body: object) -> str:
    text = bridge.call("_CreateDailyFixings", [headers, body, the_calendar()])
    assert isinstance(text, str) and FIXINGS.fullmatch(text), text
    return text


def test_fixings_are_created_from_a_table_and_a_calendar_and_read_back() -> None:
    assert bridge.call("ReadDailyFixings", [the_fixings(HEADERS, BODY)]) == (
        "2026-05-01 2026-05-04 2026-05-05 2026-05-06 | 101.94 106.42 102.27 95.08"
    )


def test_the_fixings_headers_bind_in_either_order_and_any_case() -> None:
    headers = Cells.from_rows([["SETTLE", "Date"]])
    body = Cells.from_rows([[101.94, MAY_1], [106.42, MAY_4]])
    assert bridge.call("ReadDailyFixings", [the_fixings(headers, body)]) == (
        "2026-05-01 2026-05-04 | 101.94 106.42"
    )


# Friday 22 May and Tuesday 26 May 2026: the weekend and the holiday between them are the days
# without a fixing, and the calendar's handle is what says so.
def test_a_listed_holiday_is_a_day_without_a_fixing() -> None:
    body = Cells.from_rows([[46164.0, 101.94], [46168.0, 106.42]])
    assert bridge.call("ReadDailyFixings", [the_fixings(HEADERS, body)]) == (
        "2026-05-22 2026-05-26 | 101.94 106.42"
    )


@pytest.mark.parametrize(
    ("headers", "body", "calendar", "text"),
    [
        (
            Cells.from_rows([["date", "price"]]),
            BODY,
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: header_row cell (1, 2) is text 'price', "
            "expected one of date or settle",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, "x"], [MAY_4, 106.42]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: table cell (1, 2) is text 'x', expected number",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_4, 106.42], [MAY_1, 101.94]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-01, "
            "expected a date after row 1's 2026-05-04",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, 101.94], [MAY_2, 100.0]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-02, a Saturday, "
            "expected a business day",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_25, 100.0]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: ValueError: date row 1 is 2026-05-25, a holiday, "
            "expected a business day",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, 101.94], [MAY_5, 102.27]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-05, "
            "expected 2026-05-04, the business day after row 1's 2026-05-01",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, 101.94, 1.0]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: header_row has 2 headers, expected 3, "
            "one per column of table",
        ),
        (HEADERS, None, THE_CALENDAR, "#ERROR _CreateDailyFixings: table is blank, expected table"),
        (
            HEADERS,
            MISSING,
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: table is missing, expected table",
        ),
        (
            Cells.from_rows([["date"], ["settle"]]),
            BODY,
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: header_row is 2x1 array, expected row of text",
        ),
        (
            HEADERS,
            BODY,
            3.0,
            "#ERROR _CreateDailyFixings: holiday_calendar is number 3.0, "
            "expected holiday calendar handle",
        ),
        (
            HEADERS,
            BODY,
            None,
            "#ERROR _CreateDailyFixings: holiday_calendar is blank, "
            "expected holiday calendar handle",
        ),
        (
            HEADERS,
            BODY,
            MISSING,
            "#ERROR _CreateDailyFixings: holiday_calendar is missing, "
            "expected holiday calendar handle",
        ),
        (
            HEADERS,
            BODY,
            "holiday_calendar:000000:000001",
            "#ERROR _CreateDailyFixings: holiday_calendar is text "
            "'holiday_calendar:000000:000001' naming no live object, "
            "expected holiday calendar handle",
        ),
        (
            HEADERS,
            BODY,
            "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date",
            "#ERROR _CreateDailyFixings: holiday_calendar is the creator's failure, "
            "expected holiday calendar handle: #ERROR _CreateHolidayCalendar: holiday cell "
            "(2, 1) is blank, expected date",
        ),
    ],
    ids=[
        "an unknown header",
        "text in the settle column",
        "dates backwards",
        "a Saturday in the series",
        "a listed holiday in the series",
        "a business day without a fixing",
        "a body one column wider than its headers",
        "a blank cell where the body should be",
        "the body left out",
        "headers down a column",
        "a number where the calendar should be",
        "a blank cell where the calendar should be",
        "the calendar left out",
        "text naming no live calendar",
        "the calendar creator's failure relayed",
    ],
)
def test_fixings_that_cannot_be_made_say_why(
    headers: object, body: object, calendar: object, text: str
) -> None:
    calendar = the_calendar() if calendar is THE_CALENDAR else calendar
    assert bridge.call("_CreateDailyFixings", [headers, body, calendar]) == text


def test_a_failed_fixings_construction_publishes_no_object_and_no_handle() -> None:
    before = number(the_fixings(HEADERS, BODY), FIXINGS)
    gap = Cells.from_rows([[MAY_1, 101.94], [MAY_5, 102.27]])
    assert bridge.call("_CreateDailyFixings", [HEADERS, gap, the_calendar()]) == (
        "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-05, "
        "expected 2026-05-04, the business day after row 1's 2026-05-01"
    )
    assert number(the_fixings(HEADERS, BODY), FIXINGS) == before + 1


def test_a_handle_of_another_kind_is_not_daily_fixings() -> None:
    other = a_valuation_date()
    assert bridge.call("ReadDailyFixings", [other]) == (
        f"#ERROR ReadDailyFixings: fixings is valuation date handle {other!r}, "
        "expected daily fixings handle"
    )


def test_a_handle_of_another_kind_is_not_a_holiday_calendar() -> None:
    other = a_valuation_date()
    assert bridge.call("_CreateDailyFixings", [HEADERS, BODY, other]) == (
        f"#ERROR _CreateDailyFixings: holiday_calendar is valuation date handle {other!r}, "
        "expected holiday calendar handle"
    )


# --- _CreateIfercFixings ---------------------------------------------------------


# The page's sample as the sheet sends it, Waha IFERC gas: the first four months of 2026 as
# codes, and an illustrative index beside each.
IFERC_CODES = Cells.from_rows([["F26"], ["G26"], ["H26"], ["J26"]])
IFERC_PRICES = Cells.from_rows([[1.85], [2.10], [1.95], [1.60]])
IFERC_HANDLE = re.compile(r"iferc_fixings:[0-9a-f]{6}:([0-9]{6})")


# The library has no consumer of IFERC fixings yet, so this hidden reader proves that a handle
# resolves to the fixings the seam kept, the codes as typed and the prices as numbers.
@probe
def ReadIfercFixings(fixings: Handle[IfercFixings]) -> str:
    return f"{' '.join(fixings.codes)} | {' '.join(repr(float(p)) for p in fixings.prices)}"


def iferc(codes: object, prices: object) -> str:
    text = bridge.call("_CreateIfercFixings", [codes, prices])
    assert isinstance(text, str) and IFERC_HANDLE.fullmatch(text), text
    return text


def test_iferc_fixings_are_created_from_two_columns_and_read_back() -> None:
    assert bridge.call("ReadIfercFixings", [iferc(IFERC_CODES, IFERC_PRICES)]) == (
        "F26 G26 H26 J26 | 1.85 2.1 1.95 1.6"
    )


# A single cell is a column of one, so the fixings of one month need no range.
def test_two_single_cells_make_the_fixings_of_one_month() -> None:
    assert bridge.call("ReadIfercFixings", [iferc("F26", 1.85)]) == "F26 | 1.85"


@pytest.mark.parametrize(
    ("codes", "prices", "text"),
    [
        (
            IFERC_CODES,
            Cells.from_rows([[1.85], [2.10], [1.95]]),
            "#ERROR _CreateIfercFixings: ValueError: price has 3 prices, expected 4, "
            "one per contract_code",
        ),
        (
            IFERC_CODES,
            Cells.from_rows([[1.85], [2.10], [1.95], [1.60], [1.50]]),
            "#ERROR _CreateIfercFixings: ValueError: price has 5 prices, expected 4, "
            "one per contract_code",
        ),
        (
            Cells.from_rows([["F26"], ["G26"], ["G26"], ["J26"]]),
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: ValueError: contract_code row 3 is 'G26', "
            "already given at row 2",
        ),
        (
            IFERC_CODES,
            Cells.from_rows([[1.85], [None], [1.95], [1.60]]),
            "#ERROR _CreateIfercFixings: price cell (2, 1) is blank, expected number",
        ),
        (
            IFERC_CODES,
            Cells.from_rows([[1.85], ["2.10"], [1.95], [1.60]]),
            "#ERROR _CreateIfercFixings: price cell (2, 1) is text '2.10', expected number",
        ),
        (
            Cells.from_rows([["F26"], [46027.0], ["H26"], ["J26"]]),
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code cell (2, 1) is number 46027.0, "
            "expected text",
        ),
        (
            Cells.from_rows([["F26"], [""], ["H26"], ["J26"]]),
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code cell (2, 1) is empty text, expected text",
        ),
        (
            Cells.from_rows([["F26", "G26"]]),
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code is 1x2 array, expected column of text",
        ),
        (
            IFERC_CODES,
            Cells.from_rows([[1.85, 2.10]]),
            "#ERROR _CreateIfercFixings: price is 1x2 array, expected column of numbers",
        ),
        (
            MISSING,
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code is missing, expected column of text",
        ),
        (
            IFERC_CODES,
            MISSING,
            "#ERROR _CreateIfercFixings: price is missing, expected column of numbers",
        ),
        (
            None,
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code is blank, expected column of text",
        ),
        (
            IFERC_CODES,
            None,
            "#ERROR _CreateIfercFixings: price is blank, expected column of numbers",
        ),
        (
            Cells.from_rows([["F26"], [46027.0]]),
            Cells.from_rows([[1.85], [None]]),
            "#ERROR _CreateIfercFixings: contract_code cell (2, 1) is number 46027.0, "
            "expected text",
        ),
    ],
    ids=[
        "a price column one row short",
        "a price column one row long",
        "a code given twice",
        "a blank among the prices",
        "text where a price should be",
        "a number among the codes",
        "empty text among the codes",
        "a row of codes",
        "a row of prices",
        "the codes left out",
        "the prices left out",
        "a blank cell where the codes should be",
        "a blank cell where the prices should be",
        "both columns wrong, the codes named first",
    ],
)
def test_iferc_fixings_that_cannot_be_made_say_why(
    codes: object, prices: object, text: str
) -> None:
    assert bridge.call("_CreateIfercFixings", [codes, prices]) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap,
# whether the library or the seam refused the call.
def test_a_failed_iferc_construction_publishes_no_object_and_no_handle() -> None:
    before = number(iferc(IFERC_CODES, IFERC_PRICES), IFERC_HANDLE)
    assert bridge.call("_CreateIfercFixings", [IFERC_CODES, Cells.from_rows([[1.85]])]) == (
        "#ERROR _CreateIfercFixings: ValueError: price has 1 price, expected 4, "
        "one per contract_code"
    )
    twice = Cells.from_rows([["F26"], ["F26"]])
    assert bridge.call("_CreateIfercFixings", [twice, Cells.from_rows([[1.85], [2.10]])]) == (
        "#ERROR _CreateIfercFixings: ValueError: contract_code row 2 is 'F26', "
        "already given at row 1"
    )
    assert (
        bridge.call(
            "_CreateIfercFixings", [IFERC_CODES, Cells.from_rows([[1.85], [None], [1.95], [1.60]])]
        )
        == "#ERROR _CreateIfercFixings: price cell (2, 1) is blank, expected number"
    )
    assert number(iferc(IFERC_CODES, IFERC_PRICES), IFERC_HANDLE) == before + 1


def test_a_handle_of_another_kind_is_not_iferc_fixings() -> None:
    other = the_fixings(HEADERS, BODY)
    assert bridge.call("ReadIfercFixings", [other]) == (
        f"#ERROR ReadIfercFixings: fixings is daily fixings handle {other!r}, "
        "expected iferc fixings handle"
    )
    schedule = cast(
        str,
        bridge.call(
            "_CreateIfercSchedule",
            [
                Cells.from_rows([["F26"], ["G26"]]),
                Cells.from_rows([[46022.0], [46052.0]]),
                Cells.from_rows([[46027.0], [46055.0]]),
            ],
        ),
    )
    assert bridge.call("ReadIfercFixings", [schedule]) == (
        f"#ERROR ReadIfercFixings: fixings is iferc schedule handle {schedule!r}, "
        "expected iferc fixings handle"
    )


# --- _CreatePriceVector -----------------------------------------------------------


# The page's sample as the sheet sends it: four prices, a zero and a negative among them and the
# first repeated, selected without a header.
PRICES = Cells.from_rows([[74.25], [0.0], [-0.5], [74.25]])
VECTOR = re.compile(r"price_vector:[0-9a-f]{6}:([0-9]{6})")


def a_vector(prices: object = PRICES) -> str:
    text = bridge.call("_CreatePriceVector", [prices])
    assert isinstance(text, str) and VECTOR.fullmatch(text), text
    return text


def test_a_price_vector_is_created_from_a_column_and_read_back_in_order() -> None:
    assert rows(read(a_vector())) == [["price"], ["float64"], [74.25], [0.0], [-0.5], [74.25]]


def test_one_cell_is_a_vector_of_one_price() -> None:
    assert rows(read(a_vector(74.25))) == [["price"], ["float64"], [74.25]]


# Each call publishes anew, over the same prices or a different number of them, and an earlier
# handle still reads its own snapshot.
def test_every_vector_call_publishes_a_fresh_handle_and_the_earlier_ones_stand() -> None:
    first = a_vector()
    same = a_vector()
    longer = a_vector(Cells.from_rows([[74.25], [0.0], [-0.5], [74.25], [75.0]]))
    assert number(same, VECTOR) == number(first, VECTOR) + 1
    assert number(longer, VECTOR) == number(same, VECTOR) + 1
    assert rows(read(first))[2:] == [[74.25], [0.0], [-0.5], [74.25]]
    assert rows(read(same))[2:] == [[74.25], [0.0], [-0.5], [74.25]]
    assert rows(read(longer))[2:] == [[74.25], [0.0], [-0.5], [74.25], [75.0]]


@pytest.mark.parametrize(
    ("prices", "text"),
    [
        (
            Cells.from_rows([[74.25, 0.0, -0.5]]),
            "#ERROR _CreatePriceVector: prices is 1x3 array, expected column of numbers",
        ),
        (
            Cells.from_rows([[74.25, 1.0], [0.0, 2.0]]),
            "#ERROR _CreatePriceVector: prices is 2x2 array, expected column of numbers",
        ),
        (
            Cells.from_rows([["price"], [74.25]]),
            "#ERROR _CreatePriceVector: prices cell (1, 1) is text 'price', expected number",
        ),
        (
            Cells.from_rows([[74.25], ["74.25"]]),
            "#ERROR _CreatePriceVector: prices cell (2, 1) is text '74.25', expected number",
        ),
        (
            Cells.from_rows([[74.25], [True]]),
            "#ERROR _CreatePriceVector: prices cell (2, 1) is boolean TRUE, expected number",
        ),
        (
            Cells.from_rows([[74.25], [None]]),
            "#ERROR _CreatePriceVector: prices cell (2, 1) is blank, expected number",
        ),
        (None, "#ERROR _CreatePriceVector: prices is blank, expected column of numbers"),
        (MISSING, "#ERROR _CreatePriceVector: prices is missing, expected column of numbers"),
        ("74.25", "#ERROR _CreatePriceVector: prices is text '74.25', expected column of numbers"),
        (True, "#ERROR _CreatePriceVector: prices is boolean TRUE, expected column of numbers"),
    ],
    ids=[
        "a row where a column is expected",
        "two columns",
        "the header taken with the prices",
        "numeric text among the prices",
        "a boolean among the prices",
        "a blank among the prices",
        "a blank cell where the column should be",
        "the column left out",
        "numeric text where the column should be",
        "a boolean where the column should be",
    ],
)
def test_a_vector_that_cannot_be_made_says_why(prices: object, text: str) -> None:
    assert bridge.call("_CreatePriceVector", [prices]) == text


def test_a_failed_vector_publishes_no_object_and_no_handle() -> None:
    before = number(a_vector(), VECTOR)
    assert bridge.call("_CreatePriceVector", [Cells.from_rows([[74.25], [None]])]) == (
        "#ERROR _CreatePriceVector: prices cell (2, 1) is blank, expected number"
    )
    assert number(a_vector(), VECTOR) == before + 1
