"""Type validation of scalars: every kind Excel can send against every declared type."""

from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.excel import bridge
from goosedove.excel.bridge import (
    MISSING,
    Cells,
    DateColumn,
    Handle,
    MixedArray,
    NumberColumn,
    Table,
    TextRow,
    excel_function,
)
from goosedove.excel.probes import probe


@probe
def Number(x: float) -> float:
    return x


@probe
def Text(x: str) -> str:
    return x


@probe
def Boolean(x: bool) -> bool:
    return x


@probe
def Whole(x: int) -> str:
    return f"{type(x).__name__} {x}"


@probe
def Rate(x: float = 0.05) -> float:
    return x


@probe
def Boom(x: float) -> float:
    raise ValueError("no curve for that date")


# --- the matrix: rows arrive, columns are declared -------------------------

ARRIVES = {
    "number": 2.5,
    "text": "Brent",
    "boolean": True,
    "blank": None,
    "missing": MISSING,
    "array": Cells.from_rows([[1.0]]),
}
DECLARED = {"Number": "number", "Text": "text", "Boolean": "boolean", "Whole": "whole number"}
PASSES = {("Number", "number"), ("Text", "text"), ("Boolean", "boolean")}


@pytest.mark.parametrize("arrival", ARRIVES)
@pytest.mark.parametrize("function", DECLARED)
def test_scalar_matrix(function: str, arrival: str) -> None:
    value = ARRIVES[arrival]
    result = bridge.call(function, [value])
    if (function, arrival) in PASSES:
        assert result == value
    else:
        assert isinstance(result, str)
        assert result.startswith(f"#ERROR {function}: x is ")
        assert result.endswith(f", expected {DECLARED[function]}")


# --- messages, exactly ------------------------------------------------------


@pytest.mark.parametrize(
    ("function", "value", "text"),
    [
        ("Number", "Brent", "#ERROR Number: x is text 'Brent', expected number"),
        ("Number", "123", "#ERROR Number: x is text '123', expected number"),
        ("Number", True, "#ERROR Number: x is boolean TRUE, expected number"),
        ("Boolean", "TRUE", "#ERROR Boolean: x is text 'TRUE', expected boolean"),
        ("Number", None, "#ERROR Number: x is blank, expected number"),
        ("Number", MISSING, "#ERROR Number: x is missing, expected number"),
        ("Text", "", "#ERROR Text: x is empty text, expected text"),
        ("Text", 46273.0, "#ERROR Text: x is number 46273.0, expected text"),
        ("Boolean", 1.0, "#ERROR Boolean: x is number 1.0, expected boolean"),
        ("Whole", 2.5, "#ERROR Whole: x is number 2.5, expected whole number"),
        ("Whole", 2.9999999996, "#ERROR Whole: x is number 2.9999999996, expected whole number"),
        ("Whole", True, "#ERROR Whole: x is boolean TRUE, expected whole number"),
        (
            "Number",
            Cells.from_rows([[0.0], [0.0], [0.0]]),
            "#ERROR Number: x is 3x1 array, expected number",
        ),
        ("Number", Cells.from_rows([[1.0, "a"]]), "#ERROR Number: x is 1x2 array, expected number"),
        ("Number", Cells.from_rows([[5.0]]), "#ERROR Number: x is 1x1 array, expected number"),
    ],
)
def test_failure_names_argument_arrival_and_expectation(
    function: str, value: object, text: str
) -> None:
    assert bridge.call(function, [value]) == text


def test_library_failure_names_function_type_and_message() -> None:
    assert bridge.call("Boom", [1.0]) == "#ERROR Boom: ValueError: no curve for that date"


def test_wrong_number_of_arguments_fails() -> None:
    assert bridge.call("Ping", ["unexpected"]) == "#ERROR Ping: expected 0 arguments, got 1"


# --- whole numbers ----------------------------------------------------------


@given(st.integers(min_value=-(2**53), max_value=2**53))
def test_whole_accepts_every_integral_number(n: int) -> None:
    assert bridge.call("Whole", [float(n)]) == f"int {n}"


@given(st.floats(allow_nan=False, allow_infinity=False).filter(lambda f: not f.is_integer()))
def test_whole_rejects_every_fractional_number(f: float) -> None:
    result = bridge.call("Whole", [f])
    assert isinstance(result, str)
    assert result.endswith("expected whole number")


# --- optional arguments: only missing takes the default ---------------------


def test_missing_takes_the_declared_default() -> None:
    assert bridge.call("Rate", [MISSING]) == 0.05


def test_blank_never_takes_a_default() -> None:
    assert bridge.call("Rate", [None]) == "#ERROR Rate: x is blank, expected number"


def test_present_value_still_validated_with_a_default() -> None:
    assert bridge.call("Rate", [0.07]) == 0.07
    assert bridge.call("Rate", ["7%"]) == "#ERROR Rate: x is text '7%', expected number"


# --- the declaration itself is checked at registration ----------------------


def test_unknown_declared_kind_refuses_to_register() -> None:
    def Later(x: list[str]) -> str:
        return ""

    with pytest.raises(TypeError, match="Later: x declares list\\[str\\]"):
        excel_function(Later)


def test_default_of_the_wrong_kind_refuses_to_register() -> None:
    def Wrong(x: float = cast(float, "x")) -> float:
        return 0.0

    with pytest.raises(TypeError, match="Wrong: x defaults to text 'x', expected number"):
        excel_function(Wrong)


def test_parameter_the_host_cannot_pass_refuses_to_register() -> None:
    def Keyed(x: float, *, put: bool = False) -> float:
        return x

    with pytest.raises(TypeError, match="Keyed: put is keyword-only, which the host cannot pass"):
        excel_function(Keyed)


def test_duplicate_name_refuses_to_register() -> None:
    def Again(x: float) -> float:
        return x

    Again.__name__ = "Number"
    with pytest.raises(TypeError, match="Number is already registered"):
        excel_function(Again)


# --- a range lands in a scalar slot as an array ------------------------------


def test_range_into_a_scalar_slot_fails_with_its_shape() -> None:
    column = Cells.from_rows([[1.0], [2.0]])
    assert bridge.call("Add", [column, 1.0]) == "#ERROR Add: a is 2x1 array, expected number"


# --- an argument that may be left out, with nothing in its place -------------

DATES = Cells.from_rows([[46164.0], [46165.0]])  # 22 and 23 May 2026


@probe
def Maybe(x: float, y: float | None = None, dates: DateColumn | None = None) -> str:
    """Each argument that may be left out, as it arrived: nothing, or the typed value."""
    number = "nothing" if y is None else repr(y)
    column = "nothing" if dates is None else bridge.describe(dates)
    return f"{number} / {column}"


def test_a_left_out_argument_hands_the_function_nothing() -> None:
    assert bridge.call("Maybe", [1.0, MISSING, MISSING]) == "nothing / nothing"


def test_a_supplied_value_goes_through_the_types_own_rule() -> None:
    assert bridge.call("Maybe", [1.0, 2.0, DATES]) == "2.0 / list of 2 dates"
    assert bridge.call("Maybe", [1.0, "7%", MISSING]) == (
        "#ERROR Maybe: y is text '7%', expected number"
    )
    assert bridge.call("Maybe", [1.0, MISSING, Cells.from_rows([[46164.0], [None]])]) == (
        "#ERROR Maybe: dates cell (2, 1) is blank, expected date"
    )


# Blank and left out are different facts: a blank cell in the slot is a blank, never nothing.
def test_a_blank_cell_never_stands_for_an_argument_left_out() -> None:
    assert bridge.call("Maybe", [1.0, None, MISSING]) == "#ERROR Maybe: y is blank, expected number"
    assert bridge.call("Maybe", [1.0, MISSING, None]) == (
        "#ERROR Maybe: dates is blank, expected column of dates"
    )


def test_the_form_takes_none_as_its_default_and_nothing_else() -> None:
    def Undefaulted(x: float | None) -> float:
        return 0.0

    def Defaulted(x: float | None = 1.0) -> float:
        return 0.0

    with pytest.raises(
        TypeError, match=r"Undefaulted: x declares float \| None and no default, expected None"
    ):
        excel_function(Undefaulted)
    with pytest.raises(
        TypeError,
        match=r"Defaulted: x declares float \| None and defaults to number 1.0, expected None",
    ):
        excel_function(Defaulted)


class Curve:
    """A kind of the test's own, for a handle that may not be left out."""


class Rows(Table):
    values: NumberColumn


# A table, a handle and a bare mixed range take no default on their own, and the form does not
# change that: each is refused with the words it always had.
def test_what_takes_no_default_may_not_be_left_out_either() -> None:
    def Kept(header_row: TextRow, rows: Rows | None = None) -> float:
        return 0.0

    def Read(curve: Handle[Curve] | None = None) -> float:
        return 0.0

    def Bare(values: MixedArray | None = None) -> float:
        return 0.0

    def Later(x: list[str] | None = None) -> float:
        return 0.0

    with pytest.raises(TypeError, match="Kept: rows declares a table, which takes no default"):
        excel_function(Kept)
    with pytest.raises(TypeError, match="Read: curve declares a handle, which takes no default"):
        excel_function(Read)
    with pytest.raises(TypeError, match="Bare: values declares MixedArray, which a function Excel"):
        excel_function(Bare)
    with pytest.raises(
        TypeError, match=r"Later: x declares list\[str\] \| None, which the seam cannot receive"
    ):
        excel_function(Later)
