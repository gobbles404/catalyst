"""Result validation: what a function returns against what it declared, and what the host gets."""

import datetime
import re
from collections.abc import Callable
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import (
    Cells,
    Date,
    DateColumn,
    DateRow,
    MixedArray,
    NumberArray,
    NumberColumn,
    NumberRow,
    WholeNumberColumn,
    excel_function,
)
from goosedove.excel.probes import probe

# One function per declared result type. Each returns whatever the test put in _returns.
_returns: dict[str, object] = {}


@probe
def OutNumber() -> float:
    return cast(float, _returns["value"])


@probe
def OutWhole() -> int:
    return cast(int, _returns["value"])


@probe
def OutText() -> str:
    return cast(str, _returns["value"])


@probe
def OutBoolean() -> bool:
    return cast(bool, _returns["value"])


@probe
def OutDate() -> Date:
    return cast(Date, _returns["value"])


@probe
def OutArray() -> NumberArray:
    return cast(NumberArray, _returns["value"])


@probe
def OutColumn() -> NumberColumn:
    return cast(NumberColumn, _returns["value"])


@probe
def OutRow() -> NumberRow:
    return cast(NumberRow, _returns["value"])


@probe
def OutDateColumn() -> DateColumn:
    return cast(DateColumn, _returns["value"])


@probe
def OutDateRow() -> DateRow:
    return cast(DateRow, _returns["value"])


@probe
def OutMixed() -> MixedArray:
    return cast(MixedArray, _returns["value"])


@probe
def OutBuiltTable() -> MixedArray:
    headings, columns = cast(tuple[Any, Any], _returns["value"])
    return MixedArray.table(headings, *columns)


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
def test_accepted_array(function: str, value: object, sent: list[list[float]]) -> None:
    result = out(function, value)
    assert isinstance(result, np.ndarray)
    array = cast(NDArray[Any], result)
    assert array.tolist() == sent
    assert array.dtype == np.float64
    assert array.ndim == 2
    assert array.flags.c_contiguous


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
            np.array([[2**53 + 1]], dtype=np.uint64),
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
    array = np.ones((rows, cols))
    array[r - 1, c - 1] = np.nan
    array[rows - 1, cols - 1] = np.inf  # a later bad cell never wins
    assert (
        out("OutArray", array) == f"#ERROR OutArray: result cell ({r}, {c}) is not a finite number"
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


def test_a_column_of_booleans_may_be_taken_but_not_returned() -> None:
    # No function returns one, so the way out has no rule for it, as for the text ranges.
    def OutFlags() -> bridge.BooleanColumn:
        raise AssertionError("never called")

    with pytest.raises(
        TypeError, match=r"OutFlags declares goosedove\.excel\.bridge\.BooleanColumn as its result"
    ):
        excel_function(OutFlags)


# --- the mixed road out: a rectangle of three kinds, laid out cell by cell by the host --------


def mixed_out(value: object) -> tuple[list[list[int]], list[list[float]], str]:
    """What the host is handed for a mixed array: the kinds, the numbers, the texts joined."""
    result = out("OutMixed", value)
    assert isinstance(result, tuple), result
    kinds, slots, joined = cast(tuple[NDArray[np.uint8], NDArray[np.float64], str], result)
    assert kinds.dtype == np.uint8 and kinds.flags.c_contiguous and kinds.ndim == 2
    assert slots.dtype == np.float64 and slots.flags.c_contiguous and slots.shape == kinds.shape
    assert isinstance(joined, str)
    return kinds.tolist(), slots.tolist(), joined


def test_a_rectangle_goes_out_as_kinds_numbers_and_joined_text() -> None:
    kinds, slots, joined = mixed_out(
        MixedArray(
            np.array([[1, 0], [2, 0]], dtype=np.uint8),
            np.array([[np.nan, 46164.0], [1.0, 2.5]]),
            ("CL",),
        )
    )
    assert kinds == [[1, 0], [2, 0]]
    assert np.isnan(slots[0][0])  # the placeholder under a text cell crosses as it is
    assert slots[0][1] == 46164.0 and slots[1] == [1.0, 2.5]
    assert joined == "CL"


def test_the_echo_probe_sends_a_mixed_range_back_as_it_came() -> None:
    cells = Cells.from_rows([["CL", 46164.0], [True, 2.5], ["NG", 1.0]])
    result = bridge.call("EchoMixed", [cells])
    assert isinstance(result, tuple)
    kinds, slots, joined = cast(tuple[NDArray[np.uint8], NDArray[np.float64], str], result)
    assert kinds.tolist() == cells.kinds.tolist()
    assert slots[1].tolist() == [1.0, 2.5]
    assert joined == "CL\0NG"
    # What the way in refuses never reaches the way out.
    assert bridge.call("EchoMixed", [Cells.from_rows([["CL"], [""]])]) == (
        "#ERROR EchoMixed: values cell (2, 1) is empty text, "
        "expected number, nonempty text or boolean"
    )


def test_a_table_is_built_from_headings_and_columns_of_one_kind_each() -> None:
    table = MixedArray.table(
        [("code", "expiry", "size", "cleared"), ("str", "datetime64[D]", "float64", "bool")],
        ("m26", "n26"),
        days("2026-05-19", "2026-06-22"),
        np.array([1000.0, 250.5]),
        np.array([True, False]),
    )
    kinds, slots, joined = mixed_out(table)
    assert kinds == [[1, 1, 1, 1], [1, 1, 1, 1], [1, 0, 0, 2], [1, 0, 0, 2]]
    assert slots[2][1:] == [46161.0, 1000.0, 1.0]
    assert slots[3][1:] == [46195.0, 250.5, 0.0]
    # Sheet order: the two heading rows, then each body row's texts left to right.
    assert joined == "code\0expiry\0size\0cleared\0str\0datetime64[D]\0float64\0bool\0m26\0n26"


def test_a_table_of_headings_alone_and_one_of_a_single_number() -> None:
    kinds, _, joined = mixed_out(MixedArray.table([("only",)], ()))
    assert kinds == [[1]] and joined == "only"
    kinds, slots, joined = mixed_out(MixedArray.table([], np.array([7])))
    assert kinds == [[0]] and slots == [[7.0]] and joined == ""


@pytest.mark.parametrize(
    ("build", "text"),
    [
        (
            lambda: MixedArray.table([("a",)], ("x",), np.array([1.0])),
            "heading row 1 holds 1 texts, expected 2, one per column",
        ),
        (
            lambda: MixedArray.table([], ("x", "y"), np.array([1.0])),
            "column 2 holds 1 rows, expected 2, as column 1 does",
        ),
    ],
)
def test_a_table_whose_pieces_do_not_line_up_is_a_programming_error(
    build: Callable[[], MixedArray], text: str
) -> None:
    with pytest.raises(ValueError, match=text):
        build()


@pytest.mark.parametrize(
    ("column", "text"),
    [
        (np.array([[1.0], [2.0]]), "column 1 is 2x1 array of numbers, which a table cannot hold"),
        (
            np.array(["2026-05-22T12:00"], dtype="datetime64[m]"),
            "column 1 is list of 1 date with a time, which a table cannot hold",
        ),
        (np.array(["x"]), "column 1 is list of 1 text, which a table cannot hold"),
        # A masked array is an ndarray underneath: copying it would drop the mask and spill the
        # value it hides, so it is refused as the array results refuse it.
        (
            np.ma.array([1.0, 999.0], mask=[False, True]),
            "column 1 is a numpy MaskedArray, which a table cannot hold",
        ),
    ],
)
def test_a_column_a_table_cannot_hold_is_refused(column: NDArray[Any], text: str) -> None:
    with pytest.raises(TypeError, match=re.escape(text)):
        MixedArray.table([], column)


def test_a_masked_column_fails_the_call_rather_than_spilling_the_value_it_hides() -> None:
    assert out(
        "OutBuiltTable", ([("value",)], [np.ma.array([1.0, 999.0], mask=[False, True])])
    ) == (
        "#ERROR OutBuiltTable: TypeError: "
        "column 1 is a numpy MaskedArray, which a table cannot hold"
    )


# A whole number beyond 2^53 would round on its way into the slots, where the rule could no
# longer see it, so the bound is checked before the copy, as the array results check it.
@pytest.mark.parametrize(
    "column",
    [
        np.array([1, 2**53 + 1], dtype=np.int64),
        np.array([1, np.iinfo(np.int64).min], dtype=np.int64),
        np.array([1, 2**53 + 1], dtype=np.uint64),
    ],
    ids=["int64 above", "int64 below", "uint64 above"],
)
def test_a_whole_number_beyond_what_a_cell_holds_exactly_names_its_cell(
    column: NDArray[Any],
) -> None:
    assert out("OutBuiltTable", ([("value",)], [column])) == (
        "#ERROR OutBuiltTable: result cell (3, 1) is beyond what a cell holds exactly"
    )


def test_whole_numbers_at_the_bound_go_out_exactly() -> None:
    signed = np.array([2**53, -(2**53)], dtype=np.int64)
    unsigned = np.array([2**53, 2**53], dtype=np.uint64)
    kinds, slots, _ = mixed_out(MixedArray.table([], signed, unsigned))
    assert kinds == [[0, 0], [0, 0]]
    assert slots == [[2.0**53, 2.0**53], [-(2.0**53), 2.0**53]]


@pytest.mark.parametrize(
    ("dates", "text"),
    [
        (days("2026-05-22", "NaT"), "#ERROR OutBuiltTable: result cell (3, 1) is not a date"),
        (
            days("2026-05-22", "1900-02-28"),
            "#ERROR OutBuiltTable: result cell (3, 1) is a date outside 1900-03-01 to 9999-12-31",
        ),
    ],
)
def test_a_day_outside_the_calendar_in_a_table_names_its_cell_below_the_headings(
    dates: NDArray[np.datetime64], text: str
) -> None:
    assert out("OutBuiltTable", ([("d",)], [dates])) == text


def built_from(rows: list[list[object]]) -> MixedArray:
    """A record built by hand from cells, so a kind the way out refuses can be planted."""
    cells = Cells.from_rows(rows)
    return MixedArray(cells.kinds, cells.numbers, cells.texts)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ([[1.0]], "#ERROR OutMixed: returned a Python list, expected mixed array"),
        (1.0, "#ERROR OutMixed: returned number 1.0, expected mixed array"),
        (
            MixedArray(np.zeros((0, 2), dtype=np.uint8), np.zeros((0, 2)), ()),
            "#ERROR OutMixed: returned 0x2 mixed array, "
            "expected mixed array with at least one cell",
        ),
        (
            MixedArray(np.array([[1, 1]], dtype=np.uint8), np.array([[np.nan, np.nan]]), ("a",)),
            "#ERROR OutMixed: result holds 1 texts for 2 text cells",
        ),
        (
            built_from([[1.0, None], ["x", 2.0]]),
            "#ERROR OutMixed: result cell (1, 2) is blank, "
            "expected number, nonempty text or boolean",
        ),
        (
            built_from([[1.0, bridge.MISSING]]),
            "#ERROR OutMixed: result cell (1, 2) is missing, "
            "expected number, nonempty text or boolean",
        ),
        (
            built_from([["a", ""], [None, "b"]]),
            "#ERROR OutMixed: result cell (1, 2) is empty text, "
            "expected number, nonempty text or boolean",
        ),
        (
            MixedArray(np.array([[0, 0]], dtype=np.uint8), np.array([[1.0, np.inf]]), ()),
            "#ERROR OutMixed: result cell (1, 2) is not a finite number",
        ),
        (
            MixedArray(np.array([[2], [2]], dtype=np.uint8), np.array([[1.0], [2.0]]), ()),
            "#ERROR OutMixed: result cell (2, 1) is number 2.0, expected boolean",
        ),
        (
            MixedArray(
                np.array([[1, 1]], dtype=np.uint8), np.array([[np.nan, np.nan]]), ("a", "b\0c")
            ),
            "#ERROR OutMixed: result cell (1, 2) is text 'b\\x00c', "
            "expected text with no NUL character",
        ),
    ],
)
def test_a_rectangle_the_cell_cannot_show_is_refused_naming_the_cell(
    value: object, text: str
) -> None:
    assert out("OutMixed", value) == text


def test_a_text_in_a_rectangle_is_bounded_as_a_text_result_is() -> None:
    kinds = np.array([[1], [1]], dtype=np.uint8)
    slots = np.full((2, 1), np.nan)
    longest = "a" * 32767
    assert mixed_out(MixedArray(kinds, slots, (longest, "b")))[2] == longest + "\0b"
    assert out("OutMixed", MixedArray(kinds, slots, ("b", longest + "a"))) == (
        "#ERROR OutMixed: result cell (2, 1) is text of 32768 characters, expected at most 32767"
    )
    wide = "\U0001f600"  # two units, as LEN counts
    assert out("OutMixed", MixedArray(kinds, slots, (wide * 16384, "b"))) == (
        "#ERROR OutMixed: result cell (1, 1) is text of 32768 characters, expected at most 32767"
    )
    # Many short texts whose total runs past the limit: none is too long, so all go out.
    many = tuple("t" * 10 for _ in range(4000))
    joined = mixed_out(
        MixedArray(np.ones((4000, 1), dtype=np.uint8), np.full((4000, 1), np.nan), many)
    )[2]
    assert joined.count("\0") == 3999


def test_a_column_of_whole_numbers_may_be_taken_but_not_returned() -> None:
    def Lots() -> WholeNumberColumn:
        return WholeNumberColumn(np.array([1000]))

    with pytest.raises(
        TypeError,
        match=r"Lots declares goosedove\.excel\.bridge\.WholeNumberColumn as its result, "
        r"which the seam cannot send",
    ):
        excel_function(Lots)
