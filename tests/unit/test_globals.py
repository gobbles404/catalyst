"""The globals through the seam: what each worksheet function shows for a right and a wrong call."""

import re
from typing import cast

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

# Serials for 11, 12 and 13 September 2026, and one a week later.
SEP_11, SEP_12, SEP_13, SEP_20 = 46276.0, 46277.0, 46278.0, 46285.0

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
    assert bridge.call("util_ReadDiscountFactor", [text, SEP_12]) == 0.9999


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


# --- util_ReadDiscountFactor -----------------------------------------------


def test_a_factor_is_read_back_from_the_curve_the_handle_stands_for() -> None:
    curve = a_curve()
    assert bridge.call("util_ReadDiscountFactor", [curve, SEP_11]) == 1.0
    assert bridge.call("util_ReadDiscountFactor", [curve, SEP_12]) == 0.9999
    assert bridge.call("util_ReadDiscountFactor", [curve, SEP_13]) == 0.9998


def test_a_day_the_curve_does_not_cover_fails_naming_both_ends() -> None:
    assert bridge.call("util_ReadDiscountFactor", [a_curve(), SEP_20]) == (
        "#ERROR util_ReadDiscountFactor: ValueError: date is 2026-09-20, "
        "expected a date from 2026-09-11 to 2026-09-13, the curve's first and last"
    )


def test_a_valuation_date_handle_is_not_a_curve() -> None:
    other = cast(str, bridge.call("CreateValuationDate", [SEP_11, 0.5]))
    assert bridge.call("util_ReadDiscountFactor", [other, SEP_12]) == (
        f"#ERROR util_ReadDiscountFactor: curve is valuation date handle {other!r}, "
        "expected discount curve handle"
    )


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (
            "#ERROR CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, "
            "expected exactly 1 at the curve's first date",
            "#ERROR util_ReadDiscountFactor: curve is the creator's failure, expected discount "
            "curve handle: #ERROR CreateDiscountCurve: ValueError: discount_factor row 1 is "
            "0.98, expected exactly 1 at the curve's first date",
        ),
        (
            "discount_curve:000000:000001",
            "#ERROR util_ReadDiscountFactor: curve is text 'discount_curve:000000:000001' "
            "naming no live object, expected discount curve handle",
        ),
        (
            "x",
            "#ERROR util_ReadDiscountFactor: curve is text 'x' naming no live object, "
            "expected discount curve handle",
        ),
        (
            3.0,
            "#ERROR util_ReadDiscountFactor: curve is number 3.0, expected discount curve handle",
        ),
    ],
    ids=["a creator that failed", "a handle from another session", "any other text", "a number"],
)
def test_text_that_is_not_a_live_curve_fails(value: object, text: str) -> None:
    assert bridge.call("util_ReadDiscountFactor", [value, SEP_12]) == text
