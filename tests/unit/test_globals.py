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
    text = bridge.call("CreateDiscountCurve", [HEADERS, BODY])
    assert isinstance(text, str) and text.startswith("discount_curve:"), text
    return text


# --- CreateValuationDate ---------------------------------------------------


def test_a_valuation_date_is_created_and_shown_as_a_handle() -> None:
    text = bridge.call("CreateValuationDate", [SEP_11, 0.5])
    assert isinstance(text, str)
    assert re.fullmatch(r"valuation_date:[0-9a-f]{6}:[0-9]{6}", text)


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [SEP_11, 1.5],
            "#ERROR CreateValuationDate: ValueError: day_fraction_elapsed is number 1.5, "
            "expected a number from 0 to 1",
        ),
        ([SEP_11 + 0.5, 0.5], "#ERROR CreateValuationDate: as_of is number 46276.5, expected date"),
        (
            [SEP_11, None],
            "#ERROR CreateValuationDate: day_fraction_elapsed is blank, expected number",
        ),
    ],
    ids=["a fraction outside 0 to 1", "a date with a time", "a blank fraction"],
)
def test_a_valuation_date_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("CreateValuationDate", args) == text


# --- CreateDiscountCurve ---------------------------------------------------


def test_a_curve_is_created_from_a_header_row_and_a_body() -> None:
    a_curve()


def test_the_headers_bind_in_either_order() -> None:
    headers = Cells.from_rows([["Discount_Factor", "DATE"]])
    body = Cells.from_rows([[1.0, SEP_11], [0.9999, SEP_12], [0.9998, SEP_13]])
    text = cast(str, bridge.call("CreateDiscountCurve", [headers, body]))
    # Read back through the seam: the curve's own columns, dates first, whatever the sheet's order.
    spill = bridge.call("ReadHandle", [text])
    assert isinstance(spill, tuple)
    _, slots, _ = cast(tuple[object, NDArray[np.float64], str], spill)
    assert slots[2:].tolist() == [[SEP_11, 1.0], [SEP_12, 0.9999], [SEP_13, 0.9998]]


@pytest.mark.parametrize(
    ("headers", "body", "text"),
    [
        (
            Cells.from_rows([["date", "df"]]),
            BODY,
            "#ERROR CreateDiscountCurve: header_row cell (1, 2) is text 'df', "
            "expected one of date or discount_factor",
        ),
        (
            HEADERS,
            Cells.from_rows([[SEP_11, 1.0], ["x", 0.9999]]),
            "#ERROR CreateDiscountCurve: table cell (2, 1) is text 'x', expected date",
        ),
        (
            HEADERS,
            Cells.from_rows([[SEP_11, 0.98], [SEP_12, 0.9]]),
            "#ERROR CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, "
            "expected exactly 1 at the curve's first date",
        ),
        (
            HEADERS,
            Cells.from_rows([[SEP_11, 1.0], [SEP_13, 0.9]]),
            "#ERROR CreateDiscountCurve: ValueError: date row 2 is 2026-09-13, "
            "expected 2026-09-12, one day after the row above",
        ),
    ],
    ids=["an unknown header", "text in the date column", "a first factor not one", "a gap"],
)
def test_a_curve_that_cannot_be_made_says_why(headers: Cells, body: Cells, text: str) -> None:
    assert bridge.call("CreateDiscountCurve", [headers, body]) == text
