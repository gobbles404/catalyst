"""The globals through the seam: what each worksheet function shows for a right and a wrong call."""

import re
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

# Serials for 11, 12 and 13 September 2026.
SEP_11, SEP_12, SEP_13 = 46276.0, 46277.0, 46278.0

HEADERS = Cells.from_rows([["date", "discount_factor"]])
BODY = Cells.from_rows([[SEP_11, 1.0], [SEP_12, 0.9999], [SEP_13, 0.9998]])


def a_curve() -> str:
    text = bridge.call("_CreateDiscountCurve", [HEADERS, BODY])
    assert isinstance(text, str) and text.startswith("discount_curve:"), text
    return text


# --- _CreateValuationDate ---------------------------------------------------


def test_a_valuation_date_is_created_and_shown_as_a_handle() -> None:
    text = bridge.call("_CreateValuationDate", [SEP_11, 0.5])
    assert isinstance(text, str)
    assert re.fullmatch(r"valuation_date:[0-9]+", text)


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
    text = cast(str, bridge.call("_CreateDiscountCurve", [headers, body]))
    # Read back through the seam: the curve's own columns, dates first, whatever the sheet's order.
    spill = bridge.call("util_ReadHandle", [text])
    assert isinstance(spill, tuple)
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2:].tolist() == [[SEP_11, 1.0], [SEP_12, 0.9999], [SEP_13, 0.9998]]


@pytest.mark.parametrize(
    ("headers", "body", "text"),
    [
        (
            Cells.from_rows([["date", "df"]]),
            BODY,
            "#ERROR _CreateDiscountCurve: header_row cell (1, 2) is text 'df', "
            "expected one of date or discount_factor",
        ),
        (
            HEADERS,
            Cells.from_rows([[SEP_11, 1.0], ["x", 0.9999]]),
            "#ERROR _CreateDiscountCurve: table cell (2, 1) is text 'x', expected date",
        ),
        (
            HEADERS,
            Cells.from_rows([[SEP_11, 0.98], [SEP_12, 0.9]]),
            "#ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, "
            "expected exactly 1 at the curve's first date",
        ),
        (
            HEADERS,
            Cells.from_rows([[SEP_13, 1.0], [SEP_11, 0.9]]),
            "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 2026-09-11, "
            "expected a date after row 1's 2026-09-13",
        ),
        (
            HEADERS,
            Cells.from_rows([[SEP_11, 1.0], [1094850.0, 0.5]]),
            "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 4897-08-04, "
            "expected within 1048573 days of row 1's 2026-09-11",
        ),
    ],
    ids=[
        "an unknown header",
        "text in the date column",
        "a first factor not one",
        "dates backwards",
        "a span no sheet could show",
    ],
)
def test_a_curve_that_cannot_be_made_says_why(headers: Cells, body: Cells, text: str) -> None:
    assert bridge.call("_CreateDiscountCurve", [headers, body]) == text


# Anchors two days apart make a curve of three days: the day between is on the straight line,
# and util_ReadHandle shows every day, which is how a projection is checked.
def test_a_gap_between_anchors_is_filled_and_shown_day_by_day() -> None:
    text = cast(
        str,
        bridge.call(
            "_CreateDiscountCurve", [HEADERS, Cells.from_rows([[SEP_11, 1.0], [SEP_13, 0.9998]])]
        ),
    )
    spill = bridge.call("util_ReadHandle", [text])
    assert isinstance(spill, tuple)
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2:, 0].tolist() == [SEP_11, SEP_12, SEP_13]
    assert slots[2, 1] == 1.0 and slots[4, 1] == 0.9998
    assert abs(slots[3, 1] - 0.9999) < 1e-15
