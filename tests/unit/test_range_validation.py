"""Type validation of ranges: every shape Excel can send against every declared range type."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.excel import bridge
from goosedove.excel.bridge import (
    MISSING,
    Cells,
    Column,
    Date,
    DateColumn,
    DateRow,
    NumberArray,
    Row,
    TextColumn,
    TextRow,
    excel_function,
)

# --- one function per declared range type and Date, the fixtures of this matrix --------
# SumArray is a probe and needs no fixture here.


@excel_function
def DateText(day: Date) -> str:
    return str(day)


@excel_function
def SumColumn(values: Column) -> float:
    return float(values.sum())


@excel_function
def SumRow(values: Row) -> float:
    return float(values.sum())


@excel_function
def FirstDate(dates: DateColumn) -> str:
    return str(dates[0])


@excel_function
def LastDate(dates: DateRow) -> str:
    return str(dates[-1])


@excel_function
def JoinColumn(names: TextColumn) -> str:
    return ", ".join(names)


@excel_function
def JoinRow(names: TextRow) -> str:
    return ", ".join(names)


# Every range arrives as Cells, whatever it holds. from_rows builds what the host would send.
cells = Cells.from_rows
ARRAY = cells([[1.0, 2.0], [3.0, 4.0]])
COLUMN = cells([[1.0], [2.0], [3.0]])
ROW = cells([[1.0, 2.0, 3.0]])
ONE = cells([[5.0]])
BLANK_INSIDE = cells([[1.0, None]])
TEXT_INSIDE = cells([[1.0, "n/a"]])
BOOLEAN_INSIDE = cells([[True]])
MISSING_INSIDE = cells([[1.0, MISSING]])
NAMES_ROW = cells([["x", "y"]])
NAMES_COLUMN = cells([["x"], ["y"]])
NAMES_ARRAY = cells([["a", "b"], ["c", "d"]])
DATES_COLUMN = cells([[46164.0], [46165.0]])  # 22 and 23 May 2026
DATES_ROW = cells([[46164.0, 46165.0]])
DATES_ARRAY = cells([[46164.0, 46165.0], [46166.0, 46167.0]])


# --- what passes, and what the function receives ---------------------------


@pytest.mark.parametrize(
    ("function", "value", "result"),
    [
        ("SumArray", ARRAY, 10.0),
        ("SumArray", COLUMN, 6.0),
        ("SumArray", 5.0, 5.0),
        ("SumArray", cells([[-1.0, 0.0], [0.0, -1.0]]), -2.0),
        ("SumColumn", COLUMN, 6.0),
        ("SumColumn", cells([[3.0], [1.0], [2.0]]), 6.0),
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
        ("FirstDate", cells([[46165.0], [46164.0]]), "2026-05-23"),
        ("FirstDate", cells([[61.0]]), "1900-03-01"),
        ("FirstDate", 46164.0, "2026-05-22"),
        ("LastDate", DATES_ROW, "2026-05-23"),
        ("LastDate", cells([[46165.0, 46164.0]]), "2026-05-22"),
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
def ArrayShape(values: NumberArray) -> str:
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
def TopLeft(values: NumberArray) -> float:
    return float(values[0, 0])


def test_column_and_row_are_handed_over_as_plain_lists() -> None:
    assert bridge.call("Shape", [COLUMN]) == "(3,)"
    assert bridge.call("RowShape", [ROW]) == "(3,)"


def test_array_keeps_the_shape_on_the_sheet() -> None:
    assert bridge.call("ArrayShape", [ARRAY]) == "(2, 2)"
    assert bridge.call("ArrayShape", [5.0]) == "(1, 1)"


def test_nothing_is_reordered() -> None:
    assert bridge.call("FirstOfColumn", [cells([[3.0], [1.0], [2.0]])]) == 3.0
    assert bridge.call("FirstOfRow", [cells([[3.0, 1.0, 2.0]])]) == 3.0
    assert bridge.call("TopLeft", [cells([[4.0, 3.0], [2.0, 1.0]])]) == 4.0


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
            cells([[1.0, None], [None, 4.0]]),
            "#ERROR SumArray: values cell (1, 2) is blank, expected number",
        ),
        (
            "SumArray",
            cells([[1.0, "a"], ["b", 2.0]]),
            "#ERROR SumArray: values cell (1, 2) is text 'a', expected number",
        ),
        (
            "SumArray",
            cells([["a", 1.0], [2.0, "b"]]),
            "#ERROR SumArray: values cell (1, 1) is text 'a', expected number",
        ),
        ("SumArray", "x", "#ERROR SumArray: values is text 'x', expected array of numbers"),
        ("SumArray", None, "#ERROR SumArray: values is blank, expected array of numbers"),
        ("SumArray", MISSING, "#ERROR SumArray: values is missing, expected array of numbers"),
        ("SumColumn", ARRAY, "#ERROR SumColumn: values is 2x2 array, expected column of numbers"),
        ("SumColumn", ROW, "#ERROR SumColumn: values is 1x3 array, expected column of numbers"),
        (
            "SumColumn",
            BLANK_INSIDE,
            "#ERROR SumColumn: values is 1x2 array, expected column of numbers",
        ),
        (
            "SumColumn",
            cells([[1.0], ["n/a"]]),
            "#ERROR SumColumn: values cell (2, 1) is text 'n/a', expected number",
        ),
        ("SumRow", COLUMN, "#ERROR SumRow: values is 3x1 array, expected row of numbers"),
        ("SumRow", ARRAY, "#ERROR SumRow: values is 2x2 array, expected row of numbers"),
        ("SumRow", True, "#ERROR SumRow: values is boolean TRUE, expected row of numbers"),
        ("JoinRow", NAMES_COLUMN, "#ERROR JoinRow: names is 2x1 array, expected row of text"),
        ("JoinRow", NAMES_ARRAY, "#ERROR JoinRow: names is 2x2 array, expected row of text"),
        (
            "JoinRow",
            cells([["x", ""]]),
            "#ERROR JoinRow: names cell (1, 2) is empty text, expected text",
        ),
        (
            "JoinRow",
            cells([["x", 2.0]]),
            "#ERROR JoinRow: names cell (1, 2) is number 2.0, expected text",
        ),
        (
            "JoinRow",
            cells([["x", True]]),
            "#ERROR JoinRow: names cell (1, 2) is boolean TRUE, expected text",
        ),
        ("JoinRow", ONE, "#ERROR JoinRow: names cell (1, 1) is number 5.0, expected text"),
        ("JoinRow", ROW, "#ERROR JoinRow: names cell (1, 1) is number 1.0, expected text"),
        ("JoinRow", cells([[None]]), "#ERROR JoinRow: names cell (1, 1) is blank, expected text"),
        ("JoinRow", 2.0, "#ERROR JoinRow: names is number 2.0, expected row of text"),
        ("JoinRow", "", "#ERROR JoinRow: names is empty text, expected row of text"),
        ("JoinColumn", NAMES_ROW, "#ERROR JoinColumn: names is 1x2 array, expected column of text"),
        (
            "JoinColumn",
            NAMES_ARRAY,
            "#ERROR JoinColumn: names is 2x2 array, expected column of text",
        ),
        (
            "JoinColumn",
            cells([["x"], [""], ["y"]]),
            "#ERROR JoinColumn: names cell (2, 1) is empty text, expected text",
        ),
        ("DateText", 46164.5, "#ERROR DateText: day is number 46164.5, expected date"),
        ("DateText", 60.0, "#ERROR DateText: day is number 60.0, expected date"),
        ("DateText", 2958466.0, "#ERROR DateText: day is number 2958466.0, expected date"),
        ("DateText", 1e19, "#ERROR DateText: day is number 1e+19, expected date"),
        ("DateText", "2026-05-22", "#ERROR DateText: day is text '2026-05-22', expected date"),
        ("DateText", ONE, "#ERROR DateText: day is 1x1 array, expected date"),
        (
            "FirstDate",
            cells([[46164.5]]),
            "#ERROR FirstDate: dates cell (1, 1) is number 46164.5, expected date",
        ),
        (
            "FirstDate",
            cells([[46164.0], [None]]),
            "#ERROR FirstDate: dates cell (2, 1) is blank, expected date",
        ),
        (
            "FirstDate",
            cells([[46164.5], [None]]),
            "#ERROR FirstDate: dates cell (1, 1) is number 46164.5, expected date",
        ),
        (
            "FirstDate",
            cells([[46164.0], [60.0]]),
            "#ERROR FirstDate: dates cell (2, 1) is number 60.0, expected date",
        ),
        (
            "FirstDate",
            cells([[46164.0], ["May"]]),
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
        ("LastDate", DATES_ARRAY, "#ERROR LastDate: dates is 2x2 array, expected row of dates"),
        (
            "LastDate",
            cells([[46164.0, 46164.5]]),
            "#ERROR LastDate: dates cell (1, 2) is number 46164.5, expected date",
        ),
        (
            "LastDate",
            cells([[46164.0, 60.0]]),
            "#ERROR LastDate: dates cell (1, 2) is number 60.0, expected date",
        ),
        (
            "LastDate",
            cells([[46164.0, 1e19]]),
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

    def poisoned(good: object, bad: object) -> Cells:
        grid: list[list[object]] = [[good] * cols for _ in range(rows)]
        grid[r - 1][c - 1] = bad
        grid[rows - 1][cols - 1] = bad  # a later bad cell never wins
        return cells(grid)

    assert bridge.call("SumArray", [poisoned(46164.0, None)]) == (
        f"#ERROR SumArray: values cell ({r}, {c}) is blank, expected number"
    )
    assert bridge.call("SumArray", [poisoned(46164.0, "x")]) == (
        f"#ERROR SumArray: values cell ({r}, {c}) is text 'x', expected number"
    )
    names = cells([[2.0 if i in (r, rows) else "ok"] for i in range(1, rows + 1)])
    assert bridge.call("JoinColumn", [names]) == (
        f"#ERROR JoinColumn: names cell ({r}, 1) is number 2.0, expected text"
    )
    dates = cells([[60.0 if i in (r, rows) else 46164.0] for i in range(1, rows + 1)])
    assert bridge.call("FirstDate", [dates]) == (
        f"#ERROR FirstDate: dates cell ({r}, 1) is number 60.0, expected date"
    )
