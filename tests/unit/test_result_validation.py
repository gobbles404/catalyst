"""Result validation: what a function returns against what it declared, and what the host gets."""

import datetime
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import Array, Column, Date, DateColumn, DateRow, Row, excel_function

# One function per declared result type. Each returns whatever the test put in _returns.
_returns: dict[str, object] = {}


@excel_function
def OutNumber() -> float:
    return cast(float, _returns["value"])


@excel_function
def OutWhole() -> int:
    return cast(int, _returns["value"])


@excel_function
def OutText() -> str:
    return cast(str, _returns["value"])


@excel_function
def OutBoolean() -> bool:
    return cast(bool, _returns["value"])


@excel_function
def OutDate() -> Date:
    return cast(Date, _returns["value"])


@excel_function
def OutArray() -> Array:
    return cast(Array, _returns["value"])


@excel_function
def OutColumn() -> Column:
    return cast(Column, _returns["value"])


@excel_function
def OutRow() -> Row:
    return cast(Row, _returns["value"])


@excel_function
def OutDateColumn() -> DateColumn:
    return cast(DateColumn, _returns["value"])


@excel_function
def OutDateRow() -> DateRow:
    return cast(DateRow, _returns["value"])


def out(function: str, value: object) -> object:
    _returns["value"] = value
    return bridge.call(function, [])


def days(*dates: str) -> NDArray[np.datetime64]:
    return np.array(dates, dtype="datetime64[D]")


# --- what passes, and what the host is handed --------------------------------


@pytest.mark.parametrize(
    ("function", "value", "sent"),
    [
        ("OutNumber", 2.5, 2.5),
        ("OutNumber", 3, 3.0),
        ("OutNumber", np.float64(1.5), 1.5),
        ("OutNumber", np.int64(4), 4.0),
        ("OutNumber", 2**53, float(2**53)),
        ("OutWhole", 3, 3.0),
        ("OutWhole", np.int64(3), 3.0),
        ("OutWhole", 3.0, 3.0),
        ("OutWhole", np.float64(3.0), 3.0),
        ("OutWhole", -(2**53), -float(2**53)),
        ("OutText", "x", "x"),
        ("OutText", np.str_("x"), "x"),
        ("OutBoolean", True, True),
        ("OutBoolean", np.bool_(False), False),
        ("OutDate", np.datetime64("2026-05-22"), 46164.0),
        ("OutDate", np.datetime64("1900-03-01"), 61.0),
        ("OutDate", np.datetime64("9999-12-31"), 2958465.0),
    ],
)
def test_accepted_scalar(function: str, value: object, sent: object) -> None:
    result = out(function, value)
    assert result == sent
    assert type(result) is type(sent)


@pytest.mark.parametrize(
    ("function", "value", "sent"),
    [
        ("OutArray", np.array([[1.0, 2.0], [3.0, 4.0]]), [[1.0, 2.0], [3.0, 4.0]]),
        ("OutArray", np.array([[1, 2], [3, 4]]), [[1.0, 2.0], [3.0, 4.0]]),
        ("OutArray", np.array([[5.0]]), [[5.0]]),
        ("OutArray", np.asfortranarray([[1.0, 2.0], [3.0, 4.0]]), [[1.0, 2.0], [3.0, 4.0]]),
        ("OutColumn", np.array([1.0, 2.0, 3.0]), [[1.0], [2.0], [3.0]]),
        ("OutColumn", np.array([7.0]), [[7.0]]),
        ("OutRow", np.array([1.0, 2.0, 3.0]), [[1.0, 2.0, 3.0]]),
        ("OutDateColumn", days("2026-05-22", "2026-05-23"), [[46164.0], [46165.0]]),
        ("OutDateRow", days("2026-05-22", "2026-05-23"), [[46164.0, 46165.0]]),
    ],
)
def test_accepted_block(function: str, value: object, sent: list[list[float]]) -> None:
    result = out(function, value)
    assert isinstance(result, np.ndarray)
    block = cast(NDArray[Any], result)
    assert block.tolist() == sent
    assert block.dtype == np.float64
    assert block.ndim == 2
    assert block.flags.c_contiguous


# --- messages, exactly ------------------------------------------------------


@pytest.mark.parametrize(
    ("function", "value", "text"),
    [
        ("OutNumber", "x", "#ERROR OutNumber: returned text 'x', expected number"),
        ("OutNumber", True, "#ERROR OutNumber: returned boolean TRUE, expected number"),
        ("OutNumber", None, "#ERROR OutNumber: returned nothing, expected number"),
        ("OutNumber", float("nan"), "#ERROR OutNumber: result is not a finite number"),
        ("OutNumber", float("inf"), "#ERROR OutNumber: result is not a finite number"),
        (
            "OutNumber",
            2**53 + 1,
            "#ERROR OutNumber: returned number 9007199254740993, beyond what a cell holds exactly",
        ),
        (
            "OutNumber",
            np.array([[1.0]]),
            "#ERROR OutNumber: returned 1x1 array of numbers, expected number",
        ),
        ("OutNumber", [1.0], "#ERROR OutNumber: returned a Python list, expected number"),
        (
            "OutNumber",
            np.longdouble(1.5),
            "#ERROR OutNumber: returned a numpy longdouble, expected number",
        ),
        ("OutWhole", 2.5, "#ERROR OutWhole: returned number 2.5, expected whole number"),
        ("OutWhole", float("nan"), "#ERROR OutWhole: result is not a finite number"),
        ("OutWhole", True, "#ERROR OutWhole: returned boolean TRUE, expected whole number"),
        ("OutText", "", "#ERROR OutText: returned empty text, expected text"),
        ("OutText", 1.0, "#ERROR OutText: returned number 1.0, expected text"),
        ("OutBoolean", 1, "#ERROR OutBoolean: returned number 1, expected boolean"),
        ("OutBoolean", "TRUE", "#ERROR OutBoolean: returned text 'TRUE', expected boolean"),
        ("OutDate", 46164.0, "#ERROR OutDate: returned number 46164.0, expected date"),
        (
            "OutDate",
            np.datetime64("1900-02-28"),
            "#ERROR OutDate: result is a date outside 1900-03-01 to 9999-12-31",
        ),
        (
            "OutDate",
            np.datetime64("10000-01-01"),
            "#ERROR OutDate: result is a date outside 1900-03-01 to 9999-12-31",
        ),
        (
            "OutDate",
            np.datetime64("2026-05-22T12:00"),
            "#ERROR OutDate: returned date with a time 2026-05-22T12:00, expected date",
        ),
        ("OutDate", np.datetime64("NaT", "D"), "#ERROR OutDate: result is not a date"),
        (
            "OutDate",
            np.datetime64("2026-05"),
            "#ERROR OutDate: returned date in months 2026-05, expected date",
        ),
        (
            "OutDate",
            np.datetime64("2026"),
            "#ERROR OutDate: returned date in years 2026, expected date",
        ),
        (
            "OutDate",
            datetime.date(2026, 5, 22),
            "#ERROR OutDate: returned a Python date, expected date",
        ),
        (
            "OutArray",
            np.array([1.0, 2.0]),
            "#ERROR OutArray: returned list of 2 numbers, expected array of numbers",
        ),
        (
            "OutArray",
            np.zeros((0, 3)),
            "#ERROR OutArray: returned 0x3 array of numbers, "
            "expected array of numbers with at least one cell",
        ),
        (
            "OutArray",
            np.array([["a"]]),
            "#ERROR OutArray: returned 1x1 array of text, expected array of numbers",
        ),
        (
            "OutArray",
            np.array([[True]]),
            "#ERROR OutArray: returned 1x1 array of booleans, expected array of numbers",
        ),
        (
            "OutArray",
            np.array([[1.0, float("nan")]]),
            "#ERROR OutArray: result cell (1, 2) is not a finite number",
        ),
        (
            "OutArray",
            np.array([[1.0], [float("-inf")]]),
            "#ERROR OutArray: result cell (2, 1) is not a finite number",
        ),
        (
            "OutArray",
            np.array([[2**53 + 1]]),
            "#ERROR OutArray: result cell (1, 1) is beyond what a cell holds exactly",
        ),
        (
            "OutArray",
            np.array([[np.iinfo(np.int64).min]]),
            "#ERROR OutArray: result cell (1, 1) is beyond what a cell holds exactly",
        ),
        (
            "OutArray",
            np.ma.masked_array([[1.0, 2.0]], mask=[[False, True]]),
            "#ERROR OutArray: returned a numpy MaskedArray, expected array of numbers",
        ),
        ("OutArray", [[1.0]], "#ERROR OutArray: returned a Python list, expected array of numbers"),
        ("OutArray", 1.0, "#ERROR OutArray: returned number 1.0, expected array of numbers"),
        (
            "OutColumn",
            np.array([[1.0], [2.0]]),
            "#ERROR OutColumn: returned 2x1 array of numbers, expected column of numbers",
        ),
        (
            "OutColumn",
            np.array([]),
            "#ERROR OutColumn: returned list of 0 numbers, "
            "expected column of numbers with at least one cell",
        ),
        (
            "OutColumn",
            np.array([1.0, float("nan")]),
            "#ERROR OutColumn: result cell (2, 1) is not a finite number",
        ),
        (
            "OutRow",
            np.array([[1.0, 2.0]]),
            "#ERROR OutRow: returned 1x2 array of numbers, expected row of numbers",
        ),
        (
            "OutRow",
            np.array([1.0, float("nan")]),
            "#ERROR OutRow: result cell (1, 2) is not a finite number",
        ),
        (
            "OutDateColumn",
            np.array([46164.0]),
            "#ERROR OutDateColumn: returned list of 1 number, expected column of dates",
        ),
        (
            "OutDateColumn",
            np.array(["2026-05-22T12:00"], dtype="datetime64[m]"),
            "#ERROR OutDateColumn: returned list of 1 date with a time, expected column of dates",
        ),
        (
            "OutDateColumn",
            np.array(["2026-05", "2026-06"], dtype="datetime64[M]"),
            "#ERROR OutDateColumn: returned list of 2 dates in months, expected column of dates",
        ),
        (
            "OutDateColumn",
            days("2026-05-22", "NaT"),
            "#ERROR OutDateColumn: result cell (2, 1) is not a date",
        ),
        (
            "OutDateColumn",
            days("1900-02-28"),
            "#ERROR OutDateColumn: result cell (1, 1) is a date outside 1900-03-01 to 9999-12-31",
        ),
        (
            "OutDateColumn",
            days(),
            "#ERROR OutDateColumn: returned list of 0 dates, "
            "expected column of dates with at least one cell",
        ),
        (
            "OutDateRow",
            days("2026-05-22", "10000-01-01"),
            "#ERROR OutDateRow: result cell (1, 2) is a date outside 1900-03-01 to 9999-12-31",
        ),
    ],
)
def test_rejected(function: str, value: object, text: str) -> None:
    assert out(function, value) == text


# The longest text a cell holds passes; one character more fails. Plain tests, because a
# 32,767-character parameter would make the test id longer than Windows lets an environment
# variable be, and pytest records the id in one.
def test_text_up_to_the_cell_limit_passes() -> None:
    text = "a" * 32767
    assert out("OutText", text) == text


def test_text_over_the_cell_limit_fails() -> None:
    assert out("OutText", "a" * 32768) == (
        "#ERROR OutText: returned text of 32768 characters, expected at most 32767"
    )


# Excel counts a character outside the Basic Multilingual Plane as two, as LEN does.
def test_text_is_counted_as_excel_counts_it() -> None:
    wide = "\U0001f600"
    assert out("OutText", wide * 16383 + "a") == wide * 16383 + "a"
    assert out("OutText", wide * 16384) == (
        "#ERROR OutText: returned text of 32768 characters, expected at most 32767"
    )


# --- the general rule: the first bad cell is named as INDEX counts ------------


@given(rows=st.integers(1, 12), cols=st.integers(1, 12), data=st.data())
def test_the_first_bad_cell_is_named(rows: int, cols: int, data: st.DataObject) -> None:
    r = data.draw(st.integers(1, rows))
    c = data.draw(st.integers(1, cols))
    block = np.ones((rows, cols))
    block[r - 1, c - 1] = np.nan
    block[rows - 1, cols - 1] = np.inf  # a later bad cell never wins
    assert (
        out("OutArray", block) == f"#ERROR OutArray: result cell ({r}, {c}) is not a finite number"
    )


# --- the declaration itself is checked at registration ----------------------


def test_returning_nothing_refuses_to_register() -> None:
    def Silent() -> None:
        return None

    with pytest.raises(TypeError, match="Silent declares that it returns nothing"):
        excel_function(Silent)


def test_no_declared_result_refuses_to_register() -> None:
    def Vague():
        return 1.0

    with pytest.raises(TypeError, match="Vague declares no result"):
        excel_function(Vague)


def test_unknown_declared_result_refuses_to_register() -> None:
    def Listed() -> list[str]:
        return []

    with pytest.raises(TypeError, match="Listed declares list\\[str\\] as its result"):
        excel_function(Listed)
