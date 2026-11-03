"""The globals through the seam: what each worksheet function shows for a right and a wrong call."""

import os
import re
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from catalyst.excel import bridge
from catalyst.excel.bridge import MISSING, Cells

PID = os.getpid()  # leads every handle this Python publishes

# Serials for 11, 12 and 13 September 2026.
SEP_11, SEP_12, SEP_13 = 46276.0, 46277.0, 46278.0

HEADERS = Cells.from_rows([["date", "discount_factor"]])
BODY = Cells.from_rows([[SEP_11, 1.0], [SEP_12, 0.9999], [SEP_13, 0.9998]])


def a_curve() -> str:
    text = bridge.call("_CreateDiscountCurve", ["SOFR", HEADERS, BODY])
    assert isinstance(text, str) and text.startswith(f"{PID}:discount_curve:SOFR:"), text
    return text


# --- _CreateValuationDate ---------------------------------------------------


def test_a_valuation_date_is_created_and_shown_as_a_handle() -> None:
    text = bridge.call("_CreateValuationDate", [SEP_11, 0.5])
    assert isinstance(text, str)
    assert re.fullmatch(r"[0-9]+:valuation_date:[0-9]+", text)


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [SEP_11, 1.5],
            "#ERROR _CreateValuationDate: ValueError: day_fraction_elapsed is number 1.5, "
            "expected a number from 0 to 1",
        ),
        (
            [SEP_11 + 0.5, 0.5],
            "#ERROR _CreateValuationDate: as_of is number 46276.5, expected date",
        ),
        (
            [SEP_11, None],
            "#ERROR _CreateValuationDate: day_fraction_elapsed is blank, expected number",
        ),
    ],
    ids=["a fraction outside 0 to 1", "a date with a time", "a blank fraction"],
)
def test_a_valuation_date_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreateValuationDate", args) == text


# --- _CreateDiscountCurve ---------------------------------------------------


def test_a_curve_is_created_from_a_header_row_and_a_body() -> None:
    a_curve()


def test_the_headers_bind_in_either_order() -> None:
    headers = Cells.from_rows([["Discount_Factor", "DATE"]])
    body = Cells.from_rows([[1.0, SEP_11], [0.9999, SEP_12], [0.9998, SEP_13]])
    text = cast(str, bridge.call("_CreateDiscountCurve", ["SOFR", headers, body]))
    # Read back through the seam: the curve's own columns, dates first, whatever the sheet's
    # order, and the name's column of text last.
    spill = bridge.call("util_ReadHandle", [text])
    assert isinstance(spill, tuple)
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2:, :2].tolist() == [[SEP_11, 1.0], [SEP_12, 0.9999], [SEP_13, 0.9998]]


@pytest.mark.parametrize(
    ("name", "headers", "body", "text"),
    [
        (
            "SOFR",
            Cells.from_rows([["date", "df"]]),
            BODY,
            "#ERROR _CreateDiscountCurve: header_row cell (1, 2) is text 'df', "
            "expected one of date or discount_factor",
        ),
        (
            "SOFR",
            HEADERS,
            Cells.from_rows([[SEP_11, 1.0], ["x", 0.9999]]),
            "#ERROR _CreateDiscountCurve: table cell (2, 1) is text 'x', expected date",
        ),
        (
            "SOFR",
            HEADERS,
            Cells.from_rows([[SEP_11, 0.98], [SEP_12, 0.9]]),
            "#ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, "
            "expected exactly 1 at the curve's first date",
        ),
        (
            "SOFR",
            HEADERS,
            Cells.from_rows([[SEP_13, 1.0], [SEP_11, 0.9]]),
            "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 2026-09-11, "
            "expected a date after row 1's 2026-09-13",
        ),
        (
            "SOFR",
            HEADERS,
            Cells.from_rows([[SEP_11, 1.0], [1094850.0, 0.5]]),
            "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 4897-08-04, "
            "expected within 1048573 days of row 1's 2026-09-11",
        ),
        # The name, since #201: the seam's text rule, then the library's two.
        (
            None,
            HEADERS,
            BODY,
            "#ERROR _CreateDiscountCurve: name is blank, expected text",
        ),
        (
            1.0,
            HEADERS,
            BODY,
            "#ERROR _CreateDiscountCurve: name is number 1.0, expected text",
        ),
        (
            "",
            HEADERS,
            BODY,
            "#ERROR _CreateDiscountCurve: name is empty text, expected text",
        ),
        (
            HEADERS,
            HEADERS,
            BODY,
            "#ERROR _CreateDiscountCurve: name is 1x2 array, expected text",
        ),
        (
            " SOFR",
            HEADERS,
            BODY,
            "#ERROR _CreateDiscountCurve: ValueError: name is ' SOFR', expected a name with "
            "no whitespace around it",
        ),
        (
            "  ",
            HEADERS,
            BODY,
            "#ERROR _CreateDiscountCurve: ValueError: name is '  ', expected a name, not "
            "whitespace alone",
        ),
    ],
    ids=[
        "an unknown header",
        "text in the date column",
        "a first factor not one",
        "dates backwards",
        "a span no sheet could show",
        "a blank name",
        "a number for a name",
        "empty text for a name",
        "a range for a name",
        "a name with a space before it",
        "spaces for a name",
    ],
)
def test_a_curve_that_cannot_be_made_says_why(
    name: object, headers: Cells, body: Cells, text: str
) -> None:
    assert bridge.call("_CreateDiscountCurve", [name, headers, body]) == text


# The name is in the handle, as typed, and two names over one table are two curves.
def test_a_curves_handle_carries_its_name_as_typed() -> None:
    for name in ("SOFR", "Fed Funds OIS", "€STR"):
        text = bridge.call("_CreateDiscountCurve", [name, HEADERS, BODY])
        assert isinstance(text, str) and re.fullmatch(
            rf"{PID}:discount_curve:{re.escape(name)}:[0-9]+", text
        ), text
    assert bridge.call("_CreateDiscountCurve", ["SOFR", HEADERS, BODY]) != bridge.call(
        "_CreateDiscountCurve", ["FFOIS", HEADERS, BODY]
    )


# Anchors two days apart make a curve of three days: the day between is on the straight line,
# and util_ReadHandle shows every day, which is how a projection is checked.
def test_a_gap_between_anchors_is_filled_and_shown_day_by_day() -> None:
    text = cast(
        str,
        bridge.call(
            "_CreateDiscountCurve",
            ["SOFR", HEADERS, Cells.from_rows([[SEP_11, 1.0], [SEP_13, 0.9998]])],
        ),
    )
    spill = bridge.call("util_ReadHandle", [text])
    assert isinstance(spill, tuple)
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2:, 0].tolist() == [SEP_11, SEP_12, SEP_13]
    assert slots[2, 1] == 1.0 and slots[4, 1] == 0.9998
    assert abs(slots[3, 1] - 0.9999) < 1e-15


# --- _CollectDiscountCurves, named-curves-slice-1.md ------------------------


SET = re.compile(rf"^{PID}:discount_curve_set:[0-9]+$")  # compact: the members are the readback's


def a_named_curve(name: str, body: Cells = BODY) -> str:
    text = bridge.call("_CreateDiscountCurve", [name, HEADERS, body])
    assert isinstance(text, str) and text.startswith(f"{PID}:discount_curve:{name}:"), text
    return text


def collect(handles: object) -> object:
    return bridge.call("_CollectDiscountCurves", [handles])


def members(collection: object) -> list[str]:
    """The names a collection reads back, in order: the texts after the four headers and the
    four types."""
    spill = bridge.call("util_ReadHandle", [collection])
    assert isinstance(spill, tuple)
    _, _, joined = cast(tuple[object, object, str], spill)
    return joined.split("\0")[8:]


def test_a_column_a_row_and_a_cell_of_curves_collect_under_a_compact_handle() -> None:
    sofr, ffois = a_named_curve("SOFR"), a_named_curve("FFOIS")
    before = cast(tuple[object, NDArray[np.float64], str], bridge.call("util_ReadHandle", [sofr]))
    column = collect(Cells.from_rows([[sofr], [ffois]]))
    row = collect(Cells.from_rows([[ffois, sofr]]))
    one = collect(sofr)
    for text in (column, row, one):
        assert isinstance(text, str) and SET.fullmatch(text), text
    assert len({column, row, one}) == 3  # each call publishes anew
    assert members(column) == ["SOFR", "FFOIS"]  # the order given
    assert members(row) == ["FFOIS", "SOFR"]
    assert members(one) == ["SOFR"]
    # A bumped curve collects under its source's name, and a collection of a scenario is made
    # through cells referring to its members.
    bumped = bridge.call("util_BumpDiscountCurve", [ffois, 1.0])
    assert members(collect(Cells.from_rows([[sofr, bumped]]))) == ["SOFR", "FFOIS"]
    # The curves stand as they were: the collection holds references and copies nothing.
    after = cast(tuple[object, NDArray[np.float64], str], bridge.call("util_ReadHandle", [sofr]))
    assert after[2] == before[2] and np.array_equal(after[1], before[1], equal_nan=True)


def test_each_name_once_through_the_seam_the_same_handle_twice_included() -> None:
    sofr, ffois = a_named_curve("SOFR"), a_named_curve("FFOIS")
    again = a_named_curve("SOFR", Cells.from_rows([[SEP_11, 1.0], [SEP_13, 0.9]]))
    bumped = bridge.call("util_BumpDiscountCurve", [sofr, 1.0])
    live = bridge.live_handles()
    assert collect(Cells.from_rows([[sofr], [sofr]])) == (
        "#ERROR _CollectDiscountCurves: ValueError: curve_handles cell 1 and cell 2 are both "
        "named 'SOFR', expected each name once"
    )
    assert collect(Cells.from_rows([[sofr, ffois, again]])) == (
        "#ERROR _CollectDiscountCurves: ValueError: curve_handles cell 1 and cell 3 are both "
        "named 'SOFR', expected each name once"
    )
    assert collect(Cells.from_rows([[ffois], [sofr], [bumped]])) == (
        "#ERROR _CollectDiscountCurves: ValueError: curve_handles cell 2 and cell 3 are both "
        "named 'SOFR', expected each name once"
    )
    assert bridge.live_handles() == live  # nothing published by a refusal


def test_a_collection_refuses_its_cells_in_the_seams_words_and_publishes_nothing() -> None:
    sofr, ffois = a_named_curve("SOFR"), a_named_curve("FFOIS")
    date = bridge.call("_CreateValuationDate", [SEP_11, 0.5])
    nested = collect(sofr)
    failed = bridge.call(
        "_CreateDiscountCurve", ["SOFR", HEADERS, Cells.from_rows([[SEP_11, 0.98]])]
    )
    assert failed == (
        "#ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected "
        "exactly 1 at the curve's first date"
    )
    live = bridge.live_handles()
    for handles, text in (
        (
            Cells.from_rows([[sofr, ffois], [ffois, sofr]]),
            "curve_handles is 2x2 array, expected one cell, one row or one column of discount "
            "curve handles",
        ),
        (
            Cells.from_rows([[sofr], [None]]),
            "curve_handles cell (2, 1) is blank, expected discount curve handle",
        ),
        (
            Cells.from_rows([[sofr, 3.0]]),
            "curve_handles cell (1, 2) is number 3.0, expected discount curve handle",
        ),
        (
            Cells.from_rows([[sofr], [True]]),
            "curve_handles cell (2, 1) is boolean TRUE, expected discount curve handle",
        ),
        (
            Cells.from_rows([[sofr], [""]]),
            "curve_handles cell (2, 1) is empty text, expected discount curve handle",
        ),
        (
            Cells.from_rows([[sofr], ["x"]]),
            "curve_handles cell (2, 1) is text 'x' naming no live object, expected discount "
            "curve handle",
        ),
        (
            Cells.from_rows([[sofr], [date]]),
            f"curve_handles cell (2, 1) is valuation date handle {date!r}, expected discount "
            "curve handle",
        ),
        (
            Cells.from_rows([[nested], [sofr]]),
            f"curve_handles cell (1, 1) is discount curve set handle {nested!r}, expected "
            "discount curve handle",
        ),
        (
            Cells.from_rows([[sofr], [failed]]),
            "curve_handles cell (2, 1) is the creator's failure, expected discount curve "
            f"handle: {failed}",
        ),
        (
            MISSING,
            "curve_handles is missing, expected discount curve handles in a cell, a row or a "
            "column",
        ),
        (
            None,
            "curve_handles is blank, expected discount curve handles in a cell, a row or a column",
        ),
        (
            3.0,
            "curve_handles is number 3.0, expected discount curve handles in a cell, a row or "
            "a column",
        ),
    ):
        assert collect(handles) == "#ERROR _CollectDiscountCurves: " + text
    # A consumer of a failed collection shows the creator's text once, through the relay rule.
    broken = collect(Cells.from_rows([[sofr], [failed]]))
    assert bridge.call("util_ReadHandle", [broken]) == (
        f"#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: {failed}"
    )
    assert bridge.live_handles() == live
