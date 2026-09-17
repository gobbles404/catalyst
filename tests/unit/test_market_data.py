"""The market data through the seam: what the creator shows for a right and a wrong call, and
that its handle resolves to the object the seam kept."""

import re
from typing import cast

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle
from goosedove.excel.probes import probe
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


def number(text: str) -> int:
    match = HANDLE.fullmatch(text)
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
