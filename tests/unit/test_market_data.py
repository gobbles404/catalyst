"""The market data through the seam: what each creator shows for a right and a wrong call, and
that its handle resolves to the object the seam kept."""

import re
from typing import cast

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle
from goosedove.excel.probes import probe
from goosedove.market_data.daily_fixings import DailyFixings
from goosedove.market_data.futures_curve import FuturesCurve

# The first three contracts of the page's sample as the sheet sends them: codes as text, prices
# as numbers, dollars per barrel.
CODES = Cells.from_rows([["M26"], ["N26"], ["Q26"]])
PRICES = Cells.from_rows([[71.25], [71.4], [71.1]])
HANDLE = re.compile(r"futures_curve:[0-9a-f]{6}:([0-9]{6})")


# The library has no consumer of a futures curve yet, so this hidden reader proves that a handle
# resolves to the curve the seam kept, with its columns as they arrived.
@probe
def ReadFuturesCurve(curve: Handle[FuturesCurve]) -> str:
    return f"{' '.join(curve.codes)} | {' '.join(repr(float(p)) for p in curve.prices)}"


def a_curve(*columns: object) -> str:
    text = bridge.call("_CreateFuturesCurve", list(columns))
    assert isinstance(text, str) and HANDLE.fullmatch(text), text
    return text


def number(text: str, handle: re.Pattern[str] = HANDLE) -> int:
    match = handle.fullmatch(text)
    assert match, text
    return int(match.group(1))


def test_a_curve_is_created_from_two_columns_and_read_back_through_its_handle() -> None:
    assert bridge.call("ReadFuturesCurve", [a_curve(CODES, PRICES)]) == (
        "M26 N26 Q26 | 71.25 71.4 71.1"
    )


# A single cell is a column of one, so a curve of one contract needs no range.
def test_two_single_cells_make_a_curve_of_one_contract() -> None:
    assert bridge.call("ReadFuturesCurve", [a_curve("M26", 71.25)]) == "M26 | 71.25"


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [CODES, Cells.from_rows([[71.25], [71.4]])],
            "#ERROR _CreateFuturesCurve: ValueError: price has 2 prices, expected 3, "
            "one per future_code",
        ),
        (
            [CODES, Cells.from_rows([[71.25], [None], [71.1]])],
            "#ERROR _CreateFuturesCurve: price cell (2, 1) is blank, expected number",
        ),
        (
            [CODES, Cells.from_rows([["71.25"], ["71.4"], ["71.1"]])],
            "#ERROR _CreateFuturesCurve: price cell (1, 1) is text '71.25', expected number",
        ),
        (
            [Cells.from_rows([["M26"], [46161.0], ["Q26"]]), PRICES],
            "#ERROR _CreateFuturesCurve: future_code cell (2, 1) is number 46161.0, expected text",
        ),
        (
            [CODES, Cells.from_rows([[71.25, 71.4, 71.1]])],
            "#ERROR _CreateFuturesCurve: price is 1x3 array, expected column of numbers",
        ),
        (
            [CODES, None],
            "#ERROR _CreateFuturesCurve: price is blank, expected column of numbers",
        ),
        (
            [CODES, MISSING],
            "#ERROR _CreateFuturesCurve: price is missing, expected column of numbers",
        ),
    ],
    ids=[
        "a price column one row short",
        "a blank among the prices",
        "prices typed as text",
        "a number among the codes",
        "a row of prices",
        "a blank cell where the price column should be",
        "the price column left out",
    ],
)
def test_a_curve_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreateFuturesCurve", args) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap.
def test_a_failed_construction_publishes_no_object_and_no_handle() -> None:
    before = number(a_curve(CODES, PRICES))
    short = Cells.from_rows([[71.25], [71.4]])
    assert bridge.call("_CreateFuturesCurve", [CODES, short]) == (
        "#ERROR _CreateFuturesCurve: ValueError: price has 2 prices, expected 3, "
        "one per future_code"
    )
    assert number(a_curve(CODES, PRICES)) == before + 1


def test_a_handle_of_another_kind_is_not_a_futures_curve() -> None:
    other = cast(str, bridge.call("_CreateValuationDate", [46161.0, 0.5]))
    assert bridge.call("ReadFuturesCurve", [other]) == (
        f"#ERROR ReadFuturesCurve: curve is valuation date handle {other!r}, "
        "expected futures curve handle"
    )


# --- _CreateDailyFixings ---------------------------------------------------------


# The page's sample as the sheet sends it: the header row, then four rows of a serial and a
# settle, 1, 4, 5 and 6 May 2026.
MAY_1, MAY_4, MAY_5, MAY_6 = 46143.0, 46146.0, 46147.0, 46148.0
HEADERS = Cells.from_rows([["date", "settle"]])
BODY = Cells.from_rows([[MAY_1, 101.94], [MAY_4, 106.42], [MAY_5, 102.27], [MAY_6, 95.08]])
FIXINGS = re.compile(r"daily_fixings:[0-9a-f]{6}:([0-9]{6})")


# The library has no consumer of daily fixings yet, so this hidden reader proves that a handle
# resolves to the fixings the seam kept, with their columns as they arrived.
@probe
def ReadDailyFixings(fixings: Handle[DailyFixings]) -> str:
    days = " ".join(str(day) for day in fixings.dates)
    return f"{days} | {' '.join(repr(float(s)) for s in fixings.settles)}"


def the_fixings(headers: object, body: object) -> str:
    text = bridge.call("_CreateDailyFixings", [headers, body])
    assert isinstance(text, str) and FIXINGS.fullmatch(text), text
    return text


def test_fixings_are_created_from_a_header_row_and_a_body_and_read_back() -> None:
    assert bridge.call("ReadDailyFixings", [the_fixings(HEADERS, BODY)]) == (
        "2026-05-01 2026-05-04 2026-05-05 2026-05-06 | 101.94 106.42 102.27 95.08"
    )


def test_the_fixings_headers_bind_in_either_order_and_any_case() -> None:
    headers = Cells.from_rows([["SETTLE", "Date"]])
    body = Cells.from_rows([[101.94, MAY_1], [106.42, MAY_4]])
    assert bridge.call("ReadDailyFixings", [the_fixings(headers, body)]) == (
        "2026-05-01 2026-05-04 | 101.94 106.42"
    )


@pytest.mark.parametrize(
    ("headers", "body", "text"),
    [
        (
            Cells.from_rows([["date", "price"]]),
            BODY,
            "#ERROR _CreateDailyFixings: header_row cell (1, 2) is text 'price', "
            "expected one of date or settle",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, "x"], [MAY_4, 106.42]]),
            "#ERROR _CreateDailyFixings: table cell (1, 2) is text 'x', expected number",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_4, 106.42], [MAY_1, 101.94]]),
            "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-01, "
            "expected a date after row 1's 2026-05-04",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, 101.94, 1.0]]),
            "#ERROR _CreateDailyFixings: header_row has 2 headers, expected 3, "
            "one per column of table",
        ),
        (HEADERS, None, "#ERROR _CreateDailyFixings: table is blank, expected table"),
        (HEADERS, MISSING, "#ERROR _CreateDailyFixings: table is missing, expected table"),
        (
            Cells.from_rows([["date"], ["settle"]]),
            BODY,
            "#ERROR _CreateDailyFixings: header_row is 2x1 array, expected row of text",
        ),
    ],
    ids=[
        "an unknown header",
        "text in the settle column",
        "dates backwards",
        "a body one column wider than its headers",
        "a blank cell where the body should be",
        "the body left out",
        "headers down a column",
    ],
)
def test_fixings_that_cannot_be_made_say_why(headers: object, body: object, text: str) -> None:
    assert bridge.call("_CreateDailyFixings", [headers, body]) == text


def test_a_failed_fixings_construction_publishes_no_object_and_no_handle() -> None:
    before = number(the_fixings(HEADERS, BODY), FIXINGS)
    backwards = Cells.from_rows([[MAY_4, 106.42], [MAY_1, 101.94]])
    assert bridge.call("_CreateDailyFixings", [HEADERS, backwards]) == (
        "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-01, "
        "expected a date after row 1's 2026-05-04"
    )
    assert number(the_fixings(HEADERS, BODY), FIXINGS) == before + 1


def test_a_handle_of_another_kind_is_not_daily_fixings() -> None:
    other = a_curve(CODES, PRICES)
    assert bridge.call("ReadDailyFixings", [other]) == (
        f"#ERROR ReadDailyFixings: fixings is futures curve handle {other!r}, "
        "expected daily fixings handle"
    )
