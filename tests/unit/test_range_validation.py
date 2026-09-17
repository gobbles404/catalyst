"""Type validation of ranges: every shape Excel can send against every declared range type."""

from collections.abc import Callable

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from goosedove.excel import bridge
from goosedove.excel.bridge import (
    MISSING,
    BooleanColumn,
    Cells,
    Date,
    DateColumn,
    DateRow,
    MixedArray,
    NumberArray,
    NumberColumn,
    NumberRow,
    TextColumn,
    TextRow,
    WholeNumberColumn,
    register,
)
from goosedove.excel.probes import probe

# --- one function per declared range type and Date, the fixtures of this matrix --------
# SumArray is a probe and needs no fixture here.


@probe
def DateText(day: Date) -> str:
    return str(day)


@probe
def SumColumn(values: NumberColumn) -> float:
    return float(values.sum())


@probe
def SumRow(values: NumberRow) -> float:
    return float(values.sum())


@probe
def SumWholes(values: WholeNumberColumn) -> float:
    return float(values.sum())


@probe
def WholeKind(values: WholeNumberColumn) -> str:
    return f"{values.dtype} {values.tolist()}"


@probe
def FirstDate(dates: DateColumn) -> str:
    return str(dates[0])


@probe
def LastDate(dates: DateRow) -> str:
    return str(dates[-1])


@probe
def JoinColumn(names: TextColumn) -> str:
    return ", ".join(names)


@probe
def JoinRow(names: TextRow) -> str:
    return ", ".join(names)


@probe
def AnyTrue(flags: BooleanColumn) -> bool:
    return bool(flags.any())


@probe
def FlagKind(flags: BooleanColumn) -> str:
    return str(flags.dtype)


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
# A trade's row: a product, an expiry serial, a whole quantity, a price, a flag.
TRADES = cells([["CL", 46164.0, 10, 72.5, True], ["NG", 46165.0, 3, 3.25, False]])
EMPTY_TEXT_INSIDE = cells([["a", ""]])


def hidden[F: Callable[..., object]](fn: F) -> F:
    """A mixed range on its own is the seam's instrument, which only a hidden function may take."""
    return register(fn, hidden=True)


@hidden
def CountCells(values: MixedArray) -> float:
    return float(values.shape[0] * values.shape[1])


@hidden
def Payload(values: MixedArray) -> str:
    """Everything one mixed range handed over, so an assertion sees all of it, not a count."""
    return (
        f"{values.shape} {values.kinds.tolist()} {values.numeric_slots.tolist()} {values.texts!r}"
    )


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
        ("AnyTrue", cells([[False], [True]]), True),
        ("AnyTrue", cells([[False], [False]]), False),
        ("AnyTrue", True, True),
        ("AnyTrue", False, False),
    ],
)
def test_accepted(function: str, value: object, result: object) -> None:
    assert bridge.call(function, [value]) == result


@probe
def Shape(values: NumberColumn) -> str:
    return str(values.shape)


@probe
def RowShape(values: NumberRow) -> str:
    return str(values.shape)


@probe
def ArrayShape(values: NumberArray) -> str:
    return str(values.shape)


@probe
def Kind(dates: DateColumn) -> str:
    return str(dates.dtype)


@probe
def Names(names: TextRow) -> str:
    return repr(names)


@probe
def FirstOfColumn(values: NumberColumn) -> float:
    return float(values[0])


@probe
def FirstOfRow(values: NumberRow) -> float:
    return float(values[0])


@probe
def TopLeft(values: NumberArray) -> float:
    return float(values[0, 0])


# A column of whole numbers is handed over as int64, converted once; a scalar is a column of one,
# and 2^53 itself passes either side, as the scalar rule has it.
def test_a_column_of_whole_numbers_is_handed_over_as_int64() -> None:
    assert (
        bridge.call("WholeKind", [cells([[1000.0], [2500.0], [-3.0]])]) == "int64 [1000, 2500, -3]"
    )
    assert bridge.call("WholeKind", [1000.0]) == "int64 [1000]"
    assert bridge.call("WholeKind", [cells([[9007199254740992.0], [-9007199254740992.0]])]) == (
        "int64 [9007199254740992, -9007199254740992]"
    )
    assert bridge.call("SumWholes", [cells([[1.0], [2.0], [3.0]])]) == 6.0


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


def test_booleans_are_real_booleans() -> None:
    assert bridge.call("FlagKind", [cells([[True], [False]])]) == "bool"


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
        (
            "SumWholes",
            cells([[1000.0], [2.5]]),
            "#ERROR SumWholes: values cell (2, 1) is number 2.5, expected whole number",
        ),
        (
            "SumWholes",
            cells([[1000.0], ["x"]]),
            "#ERROR SumWholes: values cell (2, 1) is text 'x', expected whole number",
        ),
        (
            "SumWholes",
            cells([[1000.0], [True]]),
            "#ERROR SumWholes: values cell (2, 1) is boolean TRUE, expected whole number",
        ),
        (
            "SumWholes",
            cells([[1000.0], [None]]),
            "#ERROR SumWholes: values cell (2, 1) is blank, expected whole number",
        ),
        # A whole number beyond 2^53 says why, in the way out's words, as the scalar rule does.
        (
            "SumWholes",
            cells([[1e16], [1.0]]),
            "#ERROR SumWholes: values cell (1, 1) is number 1e+16, "
            "beyond what a cell holds exactly",
        ),
        (
            "SumWholes",
            cells([[1.0], [-9007199254740994.0]]),
            "#ERROR SumWholes: values cell (2, 1) is number -9007199254740994.0, "
            "beyond what a cell holds exactly",
        ),
        (
            "SumWholes",
            ROW,
            "#ERROR SumWholes: values is 1x3 array, expected column of whole numbers",
        ),
        (
            "SumWholes",
            2.5,
            "#ERROR SumWholes: values is number 2.5, expected column of whole numbers",
        ),
        (
            "SumWholes",
            1e16,
            "#ERROR SumWholes: values is number 1e+16, beyond what a cell holds exactly",
        ),
        (
            "SumWholes",
            "x",
            "#ERROR SumWholes: values is text 'x', expected column of whole numbers",
        ),
        (
            "SumWholes",
            MISSING,
            "#ERROR SumWholes: values is missing, expected column of whole numbers",
        ),
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
        (
            "AnyTrue",
            cells([[True], [1.0]]),
            "#ERROR AnyTrue: flags cell (2, 1) is number 1.0, expected boolean",
        ),
        (
            "AnyTrue",
            cells([[True], ["TRUE"]]),
            "#ERROR AnyTrue: flags cell (2, 1) is text 'TRUE', expected boolean",
        ),
        (
            "AnyTrue",
            cells([[None]]),
            "#ERROR AnyTrue: flags cell (1, 1) is blank, expected boolean",
        ),
        (
            "AnyTrue",
            cells([[True, False]]),
            "#ERROR AnyTrue: flags is 1x2 array, expected column of booleans",
        ),
        ("AnyTrue", 1.0, "#ERROR AnyTrue: flags is number 1.0, expected column of booleans"),
        ("AnyTrue", None, "#ERROR AnyTrue: flags is blank, expected column of booleans"),
    ],
)
def test_rejected(function: str, value: object, text: str) -> None:
    assert bridge.call(function, [value]) == text


# --- the mixed range: three kinds in one rectangle, and the earliest bad cell wins ------

MIXED = "number, nonempty text or boolean"


@pytest.mark.parametrize(
    ("value", "cells_in"),
    [
        (TRADES, 10.0),  # text, a serial, a whole number, a decimal and a flag together
        (ARRAY, 4.0),  # all of one kind is a mix of one
        (NAMES_ARRAY, 4.0),
        (cells([[True, False]]), 2.0),
        (ONE, 1.0),  # an explicit 1x1 range
        (ROW, 3.0),
        (COLUMN, 3.0),
        (5.0, 1.0),  # a scalar becomes a 1x1 range
        ("x", 1.0),
        (True, 1.0),
        (cells([[60.0]]), 1.0),  # a serial below the calendar is a number here
        (cells([[2.5]]), 1.0),
        (cells([[" "]]), 1.0),  # whitespace is text; only empty text is not
        (cells([["2026-05-22"]]), 1.0),  # text that looks like a date stays text
    ],
)
def test_a_mixed_range_accepts_every_kind_that_holds_a_value(
    value: object, cells_in: float
) -> None:
    assert bridge.call("CountCells", [value]) == cells_in


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (BLANK_INSIDE, f"#ERROR CountCells: values cell (1, 2) is blank, expected {MIXED}"),
        (MISSING_INSIDE, f"#ERROR CountCells: values cell (1, 2) is missing, expected {MIXED}"),
        (
            EMPTY_TEXT_INSIDE,
            f"#ERROR CountCells: values cell (1, 2) is empty text, expected {MIXED}",
        ),
        # An empty text and a blank compete: the earlier cell wins, whichever kind of failure.
        (
            cells([["a", ""], [None, "b"]]),
            f"#ERROR CountCells: values cell (1, 2) is empty text, expected {MIXED}",
        ),
        (
            cells([["a", None], ["", "b"]]),
            f"#ERROR CountCells: values cell (1, 2) is blank, expected {MIXED}",
        ),
        (
            cells([["", ""]]),
            f"#ERROR CountCells: values cell (1, 1) is empty text, expected {MIXED}",
        ),
        (None, "#ERROR CountCells: values is blank, expected mixed array"),
        ("", "#ERROR CountCells: values is empty text, expected mixed array"),
        (MISSING, "#ERROR CountCells: values is missing, expected mixed array"),
    ],
)
def test_a_mixed_range_rejects_a_cell_that_holds_no_value(value: object, text: str) -> None:
    assert bridge.call("CountCells", [value]) == text


def test_a_mixed_range_hands_over_every_cell_as_it_arrived() -> None:
    assert bridge.call("Payload", [TRADES]) == (
        "(2, 5) [[1, 0, 0, 0, 2], [1, 0, 0, 0, 2]] "
        "[[nan, 46164.0, 10.0, 72.5, 1.0], [nan, 46165.0, 3.0, 3.25, 0.0]] ('CL', 'NG')"
    )


def test_a_boolean_is_not_a_number_and_text_is_not_its_digits() -> None:
    # TRUE and 1 share a slot; only the kind tells them apart. "123" never becomes a number.
    assert bridge.call("Payload", [cells([[True, 1.0, "123"]])]) == (
        "(1, 3) [[2, 0, 1]] [[1.0, 1.0, nan]] ('123',)"
    )


def test_a_promoted_scalar_is_a_one_cell_range() -> None:
    assert bridge.call("Payload", ["CL"]) == "(1, 1) [[1]] [[nan]] ('CL',)"
    assert bridge.call("Payload", [72.5]) == "(1, 1) [[0]] [[72.5]] ()"
    assert bridge.call("Payload", [False]) == "(1, 1) [[2]] [[0.0]] ()"


def test_the_three_mixed_kinds_are_the_lowest_codes() -> None:
    # The rejection mask is one compare against the highest mixed code, which only holds while
    # number, text and boolean are the three lowest. Reordering Kind must fail here, loudly.
    assert {k for k in bridge.Kind if k <= bridge.Kind.BOOLEAN} == {
        bridge.Kind.NUMBER,
        bridge.Kind.TEXT,
        bridge.Kind.BOOLEAN,
    }


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
    wholes = cells([[2.5 if i in (r, rows) else 1000.0] for i in range(1, rows + 1)])
    assert bridge.call("SumWholes", [wholes]) == (
        f"#ERROR SumWholes: values cell ({r}, 1) is number 2.5, expected whole number"
    )


# A mixed range can fail two ways at once, and the earlier cell must win whichever way it is.
# No other declared type has two causes to choose between, so this is its own property.
@given(rows=st.integers(1, 12), cols=st.integers(1, 12), data=st.data())
def test_the_earliest_bad_cell_wins_whichever_way_it_is_bad(
    rows: int, cols: int, data: st.DataObject
) -> None:
    size = rows * cols
    assume(size >= 2)  # two bad cells need two cells
    first = data.draw(st.integers(0, size - 2))
    second = data.draw(st.integers(first + 1, size - 1))
    kinds = data.draw(st.permutations([None, ""]))

    grid: list[list[object]] = [["ok"] * cols for _ in range(rows)]
    grid[first // cols][first % cols] = kinds[0]
    grid[second // cols][second % cols] = kinds[1]
    expected = "blank" if kinds[0] is None else "empty text"

    assert bridge.call("CountCells", [cells(grid)]) == (
        f"#ERROR CountCells: values cell ({first // cols + 1}, {first % cols + 1}) "
        f"is {expected}, expected {MIXED}"
    )
