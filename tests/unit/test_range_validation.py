"""Type validation of ranges: every shape Excel can send against every declared range type."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.excel import bridge
from goosedove.excel.bridge import (
    MISSING,
    Array,
    Column,
    DateColumn,
    Row,
    TextRow,
    excel_function,
)

# What the host sends: a numeric block for numbers and blanks, nested rows otherwise.
BLOCK = np.array([[1.0, 2.0], [3.0, 4.0]])
COLUMN = np.array([[1.0], [2.0], [3.0]])
ROW = np.array([[1.0, 2.0, 3.0]])
ONE = np.array([[5.0]])
BLANK_INSIDE = np.array([[1.0, np.nan]])
TEXT_INSIDE = [[1.0, "n/a"]]
BOOLEAN_INSIDE = [[True]]
MISSING_INSIDE = [[1.0, MISSING]]
NAMES_ROW = [["x", "y"]]
NAMES_COLUMN = [["x"], ["y"]]
NAMES_BLOCK = [["a", "b"], ["c", "d"]]
DATES_COLUMN = np.array([[46164.0], [46165.0]])  # 22 and 23 May 2026
DATES_ROW = np.array([[46164.0, 46165.0]])
DATES_BLOCK = np.array([[46164.0, 46165.0], [46166.0, 46167.0]])


# --- what passes, and what the function receives ---------------------------


@pytest.mark.parametrize(
    ("function", "value", "result"),
    [
        ("SumArray", BLOCK, 10.0),
        ("SumArray", COLUMN, 6.0),
        ("SumArray", 5.0, 5.0),
        ("SumArray", np.array([[-1.0, 0.0], [0.0, -1.0]]), -2.0),
        ("SumColumn", COLUMN, 6.0),
        ("SumColumn", np.array([[3.0], [1.0], [2.0]]), 6.0),
        ("SumColumn", ONE, 5.0),
        ("SumColumn", 5.0, 5.0),
        ("SumRow", ROW, 6.0),
        ("SumRow", 5.0, 5.0),
        ("JoinRow", NAMES_ROW, "x, y"),
        ("JoinRow", "x", "x"),
        ("JoinColumn", NAMES_COLUMN, "x, y"),
        ("DateText", 46164.0, "2026-05-22"),
        ("DateText", 61.0, "1900-03-01"),
        ("DateText", 75.0, "1900-03-15"),
        ("DateText", 2958465.0, "9999-12-31"),
        ("FirstDate", DATES_COLUMN, "2026-05-22"),
        ("FirstDate", np.array([[46165.0], [46164.0]]), "2026-05-23"),
        ("FirstDate", np.array([[61.0]]), "1900-03-01"),
        ("FirstDate", 46164.0, "2026-05-22"),
        ("LastDate", DATES_ROW, "2026-05-23"),
        ("LastDate", np.array([[46165.0, 46164.0]]), "2026-05-22"),
        ("LastDate", [[46164.0, 46165.0]], "2026-05-23"),
    ],
)
def test_accepted(function: str, value: object, result: object) -> None:
    assert bridge.call(function, [value]) == result


@excel_function
def Shape(values: Column) -> str:
    return str(values.shape)


@excel_function
def RowShape(values: Row) -> str:
    return str(values.shape)


@excel_function
def ArrayShape(values: Array) -> str:
    return str(values.shape)


@excel_function
def Kind(dates: DateColumn) -> str:
    return str(dates.dtype)


@excel_function
def Names(names: TextRow) -> str:
    return repr(names)


@excel_function
def FirstOfColumn(values: Column) -> float:
    return float(values[0])


@excel_function
def FirstOfRow(values: Row) -> float:
    return float(values[0])


@excel_function
def TopLeft(values: Array) -> float:
    return float(values[0, 0])


def test_column_and_row_are_handed_over_as_plain_lists() -> None:
    assert bridge.call("Shape", [COLUMN]) == "(3,)"
    assert bridge.call("RowShape", [ROW]) == "(3,)"


def test_array_keeps_the_shape_on_the_sheet() -> None:
    assert bridge.call("ArrayShape", [BLOCK]) == "(2, 2)"
    assert bridge.call("ArrayShape", [5.0]) == "(1, 1)"


def test_nothing_is_reordered() -> None:
    assert bridge.call("FirstOfColumn", [np.array([[3.0], [1.0], [2.0]])]) == 3.0
    assert bridge.call("FirstOfRow", [np.array([[3.0, 1.0, 2.0]])]) == 3.0
    assert bridge.call("TopLeft", [np.array([[4.0, 3.0], [2.0, 1.0]])]) == 4.0


def test_dates_are_real_dates() -> None:
    assert bridge.call("Kind", [DATES_COLUMN]) == "datetime64[D]"


def test_text_is_handed_over_as_a_tuple() -> None:
    assert bridge.call("Names", [NAMES_ROW]) == "('x', 'y')"


# --- messages, exactly: the cell as INDEX counts, or the whole argument -----


@pytest.mark.parametrize(
    ("function", "value", "text"),
    [
        ("SumArray", BLANK_INSIDE, "#ERROR SumArray: values cell (1, 2) is blank, expected number"),
        (
            "SumArray",
            TEXT_INSIDE,
            "#ERROR SumArray: values cell (1, 2) is text 'n/a', expected number",
        ),
        (
            "SumArray",
            BOOLEAN_INSIDE,
            "#ERROR SumArray: values cell (1, 1) is boolean TRUE, expected number",
        ),
        (
            "SumArray",
            MISSING_INSIDE,
            "#ERROR SumArray: values cell (1, 2) is missing, expected number",
        ),
        (
            "SumArray",
            np.array([[1.0, np.nan], [np.nan, 4.0]]),
            "#ERROR SumArray: values cell (1, 2) is blank, expected number",
        ),
        (
            "SumArray",
            [[1.0, "a"], ["b", 2.0]],
            "#ERROR SumArray: values cell (1, 2) is text 'a', expected number",
        ),
        ("SumArray", "x", "#ERROR SumArray: values is text 'x', expected array of numbers"),
        ("SumArray", None, "#ERROR SumArray: values is blank, expected array of numbers"),
        ("SumArray", MISSING, "#ERROR SumArray: values is missing, expected array of numbers"),
        ("SumColumn", BLOCK, "#ERROR SumColumn: values is 2x2 array, expected column of numbers"),
        ("SumColumn", ROW, "#ERROR SumColumn: values is 1x3 array, expected column of numbers"),
        (
            "SumColumn",
            BLANK_INSIDE,
            "#ERROR SumColumn: values is 1x2 array, expected column of numbers",
        ),
        (
            "SumColumn",
            TEXT_INSIDE,
            "#ERROR SumColumn: values is 1x2 array, expected column of numbers",
        ),
        (
            "SumColumn",
            [[1.0], ["n/a"]],
            "#ERROR SumColumn: values cell (2, 1) is text 'n/a', expected number",
        ),
        ("SumRow", COLUMN, "#ERROR SumRow: values is 3x1 array, expected row of numbers"),
        ("SumRow", BLOCK, "#ERROR SumRow: values is 2x2 array, expected row of numbers"),
        ("SumRow", True, "#ERROR SumRow: values is boolean TRUE, expected row of numbers"),
        ("JoinRow", NAMES_COLUMN, "#ERROR JoinRow: names is 2x1 array, expected row of text"),
        ("JoinRow", NAMES_BLOCK, "#ERROR JoinRow: names is 2x2 array, expected row of text"),
        ("JoinRow", [["x", ""]], "#ERROR JoinRow: names cell (1, 2) is empty text, expected text"),
        ("JoinRow", [["x", 2.0]], "#ERROR JoinRow: names cell (1, 2) is number 2.0, expected text"),
        ("JoinRow", ONE, "#ERROR JoinRow: names cell (1, 1) is number 5.0, expected text"),
        ("JoinRow", ROW, "#ERROR JoinRow: names cell (1, 1) is number 1.0, expected text"),
        (
            "JoinRow",
            np.array([[np.nan]]),
            "#ERROR JoinRow: names cell (1, 1) is blank, expected text",
        ),
        ("JoinRow", 2.0, "#ERROR JoinRow: names is number 2.0, expected row of text"),
        ("JoinRow", "", "#ERROR JoinRow: names is empty text, expected row of text"),
        ("JoinColumn", NAMES_ROW, "#ERROR JoinColumn: names is 1x2 array, expected column of text"),
        (
            "JoinColumn",
            NAMES_BLOCK,
            "#ERROR JoinColumn: names is 2x2 array, expected column of text",
        ),
        ("DateText", 46164.5, "#ERROR DateText: day is number 46164.5, expected date"),
        ("DateText", 60.0, "#ERROR DateText: day is number 60.0, expected date"),
        ("DateText", 2958466.0, "#ERROR DateText: day is number 2958466.0, expected date"),
        ("DateText", 1e19, "#ERROR DateText: day is number 1e+19, expected date"),
        ("DateText", "2026-05-22", "#ERROR DateText: day is text '2026-05-22', expected date"),
        ("DateText", ONE, "#ERROR DateText: day is 1x1 array, expected date"),
        (
            "FirstDate",
            np.array([[46164.5]]),
            "#ERROR FirstDate: dates cell (1, 1) is number 46164.5, expected date",
        ),
        (
            "FirstDate",
            np.array([[46164.0], [np.nan]]),
            "#ERROR FirstDate: dates cell (2, 1) is blank, expected date",
        ),
        (
            "FirstDate",
            np.array([[46164.5], [np.nan]]),
            "#ERROR FirstDate: dates cell (1, 1) is number 46164.5, expected date",
        ),
        (
            "FirstDate",
            np.array([[46164.0], [60.0]]),
            "#ERROR FirstDate: dates cell (2, 1) is number 60.0, expected date",
        ),
        (
            "FirstDate",
            [[46164.0], ["May"]],
            "#ERROR FirstDate: dates cell (2, 1) is text 'May', expected date",
        ),
        (
            "FirstDate",
            46164.5,
            "#ERROR FirstDate: dates is number 46164.5, expected column of dates",
        ),
        ("FirstDate", 60.0, "#ERROR FirstDate: dates is number 60.0, expected column of dates"),
        ("FirstDate", DATES_ROW, "#ERROR FirstDate: dates is 1x2 array, expected column of dates"),
        ("LastDate", DATES_COLUMN, "#ERROR LastDate: dates is 2x1 array, expected row of dates"),
        ("LastDate", DATES_BLOCK, "#ERROR LastDate: dates is 2x2 array, expected row of dates"),
        (
            "LastDate",
            [[46164.0, 46164.5]],
            "#ERROR LastDate: dates cell (1, 2) is number 46164.5, expected date",
        ),
        (
            "LastDate",
            [[46164.0, 60.0]],
            "#ERROR LastDate: dates cell (1, 2) is number 60.0, expected date",
        ),
        (
            "LastDate",
            np.array([[46164.0, 1e19]]),
            "#ERROR LastDate: dates cell (1, 2) is number 1e+19, expected date",
        ),
    ],
)
def test_rejected(function: str, value: object, text: str) -> None:
    assert bridge.call(function, [value]) == text


# --- the general rule: the first failing cell is named as INDEX counts ------


@given(rows=st.integers(1, 12), cols=st.integers(1, 12), data=st.data())
def test_the_first_failing_cell_is_named(rows: int, cols: int, data: st.DataObject) -> None:
    r = data.draw(st.integers(1, rows))
    c = data.draw(st.integers(1, cols))

    block = np.full((rows, cols), 46164.0)
    block[r - 1, c - 1] = np.nan
    block[rows - 1, cols - 1] = np.nan  # a later bad cell never wins
    assert bridge.call("SumArray", [block]) == (
        f"#ERROR SumArray: values cell ({r}, {c}) is blank, expected number"
    )

    grid: list[list[object]] = [[46164.0] * cols for _ in range(rows)]
    grid[r - 1][c - 1] = "x"
    grid[rows - 1][cols - 1] = "x"
    assert bridge.call("SumArray", [grid]) == (
        f"#ERROR SumArray: values cell ({r}, {c}) is text 'x', expected number"
    )

    dates = np.full((rows, 1), 46164.0)
    dates[r - 1, 0] = 60.0
    dates[rows - 1, 0] = 60.0
    assert bridge.call("FirstDate", [dates]) == (
        f"#ERROR FirstDate: dates cell ({r}, 1) is number 60.0, expected date"
    )
