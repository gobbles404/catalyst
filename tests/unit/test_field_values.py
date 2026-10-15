"""A row or rows of an instrument's fields crossing the seam: the headers bound exactly against
the instrument another argument selects, each column typed by its field, a handle column
resolved to its objects, the order of failures the review's decision 11 fixed, the selector by
name and by handle kind, and what registration refuses. docs/seam/inputs.md decision 42."""

import re
from typing import Annotated, cast

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells, FieldRow, FieldRows, Handle, TextRow, register
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.instruments.definitions import FIXED_FLOAT, FieldType, Instrument
from goosedove.instruments.fields import FieldValues, selected

ENTRY = {
    name: bridge.entry(name)
    for name in ("EchoFieldRow", "CountFieldRows", "_CreateHolidayCalendar", "_CreateValuationDate")
}
FIELD_NAMES = ", ".join(field.name for field in FIXED_FLOAT.fields)


def row(*cells: object) -> Cells:
    return Cells.from_rows([list(cells)])


def rows(*lines: list[object]) -> Cells:
    return Cells.from_rows(lines)


@pytest.fixture
def calendar() -> str:
    return str(ENTRY["_CreateHolidayCalendar"](row(46023.0)))


# --- the record the function receives -------------------------------------------------------


def bound(instrument: str, headers: Cells, body: Cells, one_row: bool = True) -> FieldValues:
    """The record the probe received, caught on its way through."""
    caught: list[FieldValues] = []

    def catch(instrument: str, fields: TextRow, values: FieldRow[str]) -> float:
        caught.append(values)
        return 0.0

    def catch_rows(instrument: str, fields: TextRow, values: FieldRows[str]) -> float:
        caught.append(values)
        return 0.0

    name = f"Catch{'Row' if one_row else 'Rows'}{abs(hash((instrument, headers.texts)))}"
    fn = catch if one_row else catch_rows
    fn.__name__ = name
    register(fn, hidden=True)
    result = bridge.entry(name)(instrument, headers, body)
    assert result == 0.0, result
    return caught[0]


def test_a_row_of_fields_arrives_typed_by_its_fields_in_the_sheets_order(calendar: str) -> None:
    headers = row("quantity", "payment_holiday_calendar", "trade_date", "schedule_method")
    values = bound("fixed_float", headers, row(10.0, calendar, 46164.0, "lastday"))
    assert values.instrument is FIXED_FLOAT and values.rows == 1
    assert values.names == ("quantity", "payment_holiday_calendar", "trade_date", "schedule_method")
    np.testing.assert_array_equal(values.numbers("quantity"), [10.0])
    assert values.dates("trade_date").dtype == np.dtype("datetime64[D]")
    assert values.dates("trade_date")[0] == np.datetime64("2026-05-22")
    assert values.texts("schedule_method") == ("lastday",)
    (held,) = values.objects("payment_holiday_calendar")
    assert type(held) is HolidayCalendar
    assert values.has("quantity") and not values.has("fixed_price")
    assert values.field("quantity").type is FieldType.NUMBER


def test_rows_of_fields_arrive_as_columns_one_per_row() -> None:
    values = bound(
        "fixed_float",
        row("contract_code", "quantity", "fixed_price"),
        rows(["Z26", 10.0, 3.1], ["z26", -4.0, 3.15], ["F27", 7.0, 3.4]),
        one_row=False,
    )
    assert values.rows == 3
    assert values.texts("contract_code") == ("Z26", "z26", "F27")  # as typed, in either case
    np.testing.assert_array_equal(values.numbers("quantity"), [10.0, -4.0, 7.0])
    np.testing.assert_array_equal(values.numbers("fixed_price"), [3.1, 3.15, 3.4])


def test_the_echo_probe_spills_the_bound_row_back_under_its_field_names(calendar: str) -> None:
    headers = row("quantity_unit", "payment_holiday_calendar", "trade_date", "quantity")
    kinds, slots, text = cast(
        tuple[NDArray[np.uint8], NDArray[np.float64], str],
        ENTRY["EchoFieldRow"]("fixed_float", headers, row("lots", calendar, 46164.0, 10.0)),
    )
    assert kinds.shape == (2, 4)
    assert text.split("\0") == [
        "quantity_unit",
        "payment_holiday_calendar",
        "trade_date",
        "quantity",
        "lots",
        "a holiday calendar",
    ]
    assert slots[1, 2] == 46164.0 and slots[1, 3] == 10.0
    assert ENTRY["CountFieldRows"]("fixed_float", row("quantity"), rows([1.0], [2.0], [3.0])) == 3.0


# --- what is refused, in the order decided --------------------------------------------------


@pytest.mark.parametrize(
    ("instrument", "headers", "body", "message"),
    [
        (None, row("quantity"), row(1.0), "instrument is blank, expected text"),
        ("fixed_float", row(1.0), row(1.0), "fields cell (1, 1) is number 1.0, expected text"),
        (
            "fixed_float",
            row("quantity"),
            row(None),
            "values cell (1, 1) is blank, expected number",
        ),
        (
            "fixed_float",
            row("quantity"),
            row(""),
            "values cell (1, 1) is empty text, expected number",
        ),
        ("fixed_float", row("route"), row(""), "values cell (1, 1) is empty text, expected text"),
        ("fixed_float", row("trade_date"), row(None), "values cell (1, 1) is blank, expected date"),
        (
            "fixed_float",
            row("payment_holiday_calendar"),
            row(""),
            "values cell (1, 1) is empty text, expected holiday calendar handle",
        ),
        (
            "fixed_float",
            row("contract_code"),
            row(bridge.MISSING),
            "values cell (1, 1) is missing, expected text",
        ),
        (
            "fixed_float",
            row("quantity"),
            rows([1.0], [2.0]),
            "values is 2x1 array, expected one row of field values",
        ),
        (
            "fixed_float",
            row("quantity"),
            rows([1.0], [None]),
            "values is 2x1 array, expected one row of field values",
        ),
        (
            "fixed_float",
            row("quantity", "fixed_price"),
            rows([1.0, 3.1], [None, None]),
            "values is 2x2 array, expected one row of field values",
        ),
        (
            "Future",
            row("Quantity"),
            row("ten"),
            "ValueError: instrument is 'Future', expected one of: 'fixed_float'",
        ),
        (
            "fixed_float",
            row("quantity"),
            row(1.0, 2.0),
            "fields has 1 headers, expected 2, one per column of values",
        ),
        (
            "fixed_float",
            row("Quantity"),
            row(1.0),
            "fields cell (1, 1) is text 'Quantity', expected a field of fixed_float: "
            f"{FIELD_NAMES}",
        ),
        (
            "fixed_float",
            row("quantity "),
            row(1.0),
            "fields cell (1, 1) is text 'quantity ', expected a field of fixed_float: "
            f"{FIELD_NAMES}",
        ),
        (
            "fixed_float",
            row("quantity", "quantity"),
            row(1.0, 2.0),
            "fields cell (1, 2) is text 'quantity', already given at cell (1, 1)",
        ),
        (
            "fixed_float",
            row("quantity"),
            row("ten"),
            "values cell (1, 1) is text 'ten', expected number",
        ),
        (
            "fixed_float",
            row("trade_date"),
            row(46164.5),
            "values cell (1, 1) is number 46164.5, expected date",
        ),
        ("fixed_float", row("route"), row(1.0), "values cell (1, 1) is number 1.0, expected text"),
        (
            "fixed_float",
            row("payment_holiday_calendar"),
            row("x:holiday_calendar:9"),
            "values cell (1, 1) is text 'x:holiday_calendar:9' naming no live object, "
            "expected holiday calendar handle",
        ),
        (
            "fixed_float",
            row("payment_holiday_calendar"),
            row(46023.0),
            "values cell (1, 1) is number 46023.0, expected holiday calendar handle",
        ),
    ],
)
def test_a_row_that_cannot_be_bound_says_why_in_the_decided_order(
    instrument: object, headers: Cells, body: Cells, message: str
) -> None:
    assert ENTRY["EchoFieldRow"](instrument, headers, body) == f"#ERROR EchoFieldRow: {message}"


def test_handles_are_resolved_from_their_own_cells_in_row_order(calendar: str) -> None:
    # The review's case: a good handle, then text where a number is wanted. The handle column is
    # checked first and passes; the text is named in its own cell, not as a second handle in a row
    # that is not there.
    out = ENTRY["EchoFieldRow"](
        "fixed_float", row("payment_holiday_calendar", "quantity"), row(calendar, "ten")
    )
    assert out == "#ERROR EchoFieldRow: values cell (1, 2) is text 'ten', expected number"
    # Down a handle column the first bad cell is the one named, whichever way it is bad.
    dead_then_number = rows(["x:holiday_calendar:9"], [1.0])
    assert ENTRY["CountFieldRows"](
        "fixed_float", row("payment_holiday_calendar"), dead_then_number
    ) == (
        "#ERROR CountFieldRows: rows cell (1, 1) is text 'x:holiday_calendar:9' naming no live "
        "object, expected holiday calendar handle"
    )
    number_then_dead = rows([1.0], ["x:holiday_calendar:9"])
    assert ENTRY["CountFieldRows"](
        "fixed_float", row("payment_holiday_calendar"), number_then_dead
    ) == ("#ERROR CountFieldRows: rows cell (1, 1) is number 1.0, expected holiday calendar handle")
    # A text column before the handle column and a text column after it: each handle is found at
    # its own place among the body's texts, and the rows come through.
    good = rows(["cleared", calendar, "lastday"], ["bilateral", calendar, "lastday"])
    values = bound(
        "fixed_float",
        row("route", "payment_holiday_calendar", "schedule_method"),
        good,
        one_row=False,
    )
    assert values.texts("route") == ("cleared", "bilateral")
    assert values.texts("schedule_method") == ("lastday", "lastday")
    assert all(type(held) is HolidayCalendar for held in values.objects("payment_holiday_calendar"))
    mixed_rows = rows(
        ["cleared", calendar, "lastday"], ["bilateral", "x:holiday_calendar:9", "lastday"]
    )
    assert ENTRY["CountFieldRows"](
        "fixed_float", row("route", "payment_holiday_calendar", "schedule_method"), mixed_rows
    ) == (
        "#ERROR CountFieldRows: rows cell (2, 2) is text 'x:holiday_calendar:9' naming no live "
        "object, expected holiday calendar handle"
    )


def test_a_handle_of_another_kind_in_a_handle_column_is_refused_naming_the_cell() -> None:
    date = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    out = ENTRY["EchoFieldRow"](
        "fixed_float", row("payment_holiday_calendar", "quantity"), row(date, 1.0)
    )
    assert out == (
        f"#ERROR EchoFieldRow: values cell (1, 1) is valuation date handle {date!r}, "
        "expected holiday calendar handle"
    )


def test_the_instrument_is_read_before_the_headers_and_the_cells() -> None:
    # A wrong name, a wrong header and a wrong cell together: the name is refused first.
    out = ENTRY["EchoFieldRow"]("Future", row("Quantity"), row("ten"))
    assert (
        out
        == "#ERROR EchoFieldRow: ValueError: instrument is 'Future', expected one of: 'fixed_float'"
    )
    # The right name, a wrong width and a wrong header: the width is refused first.
    out = ENTRY["EchoFieldRow"]("fixed_float", row("Quantity"), row(1.0, 2.0))
    assert out == "#ERROR EchoFieldRow: fields has 1 headers, expected 2, one per column of values"
    # The right width, a wrong header and a wrong cell: the header is refused first.
    out = str(ENTRY["EchoFieldRow"]("fixed_float", row("quantity", "Quantity"), row("ten", "ten")))
    assert out.startswith(
        "#ERROR EchoFieldRow: fields cell (1, 2) is text 'Quantity', expected a field"
    )
    # Two wrong cells: the leftmost column's is refused first.
    out = ENTRY["EchoFieldRow"]("fixed_float", row("quantity", "fixed_price"), row("ten", "eleven"))
    assert out == "#ERROR EchoFieldRow: values cell (1, 1) is text 'ten', expected number"


# --- cells left unsupplied in the three period fields, since #172 -------------------------------


def test_a_blank_or_empty_cell_in_a_period_field_is_a_row_that_supplied_nothing(
    calendar: str,
) -> None:
    # Alternating rows: a code with formula-empty dates, a pair with a blank code, a pair with a
    # formula-empty code; text and a handle on both sides of the three columns, each cell's text
    # found at its own place whatever the cells around it hold.
    headers = row(
        "route", "contract_code", "start_date", "end_date", "payment_holiday_calendar", "broker"
    )
    values = bound(
        "fixed_float",
        headers,
        rows(
            ["cleared", "Z26", "", "", calendar, "ION"],
            ["cleared", None, 46357.0, 46387.0, calendar, "TP"],
            ["bilateral", "", 46388.0, 46418.0, calendar, "ION"],
        ),
        one_row=False,
    )
    assert values.rows == 3
    assert values.texts("route") == ("cleared", "cleared", "bilateral")
    assert values.texts("broker") == ("ION", "TP", "ION")
    assert all(type(held) is HolidayCalendar for held in values.objects("payment_holiday_calendar"))
    assert values.texts("contract_code") == ("Z26",)
    np.testing.assert_array_equal(values.supplied_rows("contract_code"), [True, False, False])
    np.testing.assert_array_equal(values.supplied_rows("start_date"), [False, True, True])
    np.testing.assert_array_equal(values.supplied_rows("end_date"), [False, True, True])
    np.testing.assert_array_equal(
        values.dates("start_date"), np.array(["2026-12-01", "2027-01-01"], dtype="datetime64[D]")
    )
    np.testing.assert_array_equal(
        values.dates("end_date"), np.array(["2026-12-31", "2027-01-31"], dtype="datetime64[D]")
    )
    assert set(values.supplied) == {"contract_code", "start_date", "end_date"}
    assert not values.supplied["start_date"].flags.writeable
    # A field without a mask was supplied on every row, as the record says.
    np.testing.assert_array_equal(values.supplied_rows("route"), [True, True, True])
    # One row with nothing in a period cell: the field is present and no row supplied it.
    one = bound("fixed_float", row("contract_code", "quantity"), row("", 10.0))
    assert one.names == ("contract_code", "quantity") and one.texts("contract_code") == ()
    np.testing.assert_array_equal(one.supplied_rows("contract_code"), [False])
    np.testing.assert_array_equal(one.numbers("quantity"), [10.0])


def test_a_populated_period_cell_is_held_to_its_type_and_a_blank_elsewhere_is_refused() -> None:
    count = ENTRY["CountFieldRows"]
    assert count("fixed_float", row("contract_code"), rows(["Z26"], [26.0])) == (
        "#ERROR CountFieldRows: rows cell (2, 1) is number 26.0, expected text"
    )
    assert count("fixed_float", row("start_date"), rows([46357.0], ["x"])) == (
        "#ERROR CountFieldRows: rows cell (2, 1) is text 'x', expected date"
    )
    assert count("fixed_float", row("end_date"), rows([None], [46387.5])) == (
        "#ERROR CountFieldRows: rows cell (2, 1) is number 46387.5, expected date"
    )
    # The cells are checked after the headers, since the field a header names says what a cell
    # may hold: a blank under a wrong header is a wrong header, and under quantity a blank.
    assert str(ENTRY["EchoFieldRow"]("fixed_float", row("Quantity"), row(None))).startswith(
        "#ERROR EchoFieldRow: fields cell (1, 1) is text 'Quantity', expected a field of "
        "fixed_float"
    )
    assert count(
        "fixed_float", row("quantity", "contract_code"), rows([1.0, "Z26"], [None, ""])
    ) == ("#ERROR CountFieldRows: rows cell (2, 1) is blank, expected number")
    # The echo probe shows the words where a row supplied nothing and the value where it did.
    kinds, slots, text = cast(
        tuple[NDArray[np.uint8], NDArray[np.float64], str],
        ENTRY["EchoFieldRow"](
            "fixed_float", row("contract_code", "start_date", "quantity"), row("", 46357.0, 10.0)
        ),
    )
    assert kinds.shape == (2, 3)
    assert text.split("\0") == ["contract_code", "start_date", "quantity", "(not supplied)"]
    assert slots[1, 1] == 46357.0 and slots[1, 2] == 10.0


# --- the selector by handle kind --------------------------------------------------------------


class Toy:
    """A kind that holds an instrument, as a template will: registered with `selected` here."""

    def __init__(self, definition: Instrument) -> None:
        self.definition = definition


@selected.register
def toy_selects(selector: Toy) -> Instrument:
    return selector.definition


def test_a_handle_whose_kind_holds_an_instrument_selects_it() -> None:
    def MakeToy() -> Handle[Toy]:
        return Toy(FIXED_FLOAT)

    def ToyRows(fields: TextRow, values: FieldRows[Toy], toy: Handle[Toy]) -> float:
        return float(values.rows) + len(values.names) / 10

    register(MakeToy, hidden=True)
    register(ToyRows, hidden=True)
    toy = bridge.entry("MakeToy")()
    assert (
        bridge.entry("ToyRows")(
            row("quantity", "route"), rows([1.0, "cleared"], [2.0, "cleared"]), toy
        )
        == 2.2
    )
    assert str(bridge.entry("ToyRows")(row("Quantity"), rows([1.0]), toy)).startswith(
        "#ERROR ToyRows: fields cell (1, 1) is text 'Quantity', expected a field of fixed_float"
    )
    date = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    assert bridge.entry("ToyRows")(row("quantity"), rows([1.0]), date) == (
        f"#ERROR ToyRows: toy is valuation date handle {date!r}, expected toy handle"
    )


def test_a_selector_of_a_kind_that_holds_no_instrument_says_so() -> None:
    with pytest.raises(ValueError, match=r"^a holiday calendar selects no instrument$"):
        selected(HolidayCalendar(np.array([], dtype="datetime64[D]")))


# --- what registration refuses --------------------------------------------------------------


def test_field_values_need_a_header_row_before_them() -> None:
    def NoHeaders(instrument: str, values: FieldRow[str]) -> float:
        return 0.0

    with pytest.raises(
        TypeError, match=r"NoHeaders: values declares field values with no row of text before it"
    ):
        register(NoHeaders, hidden=True)


def test_field_values_need_exactly_one_selector_of_their_type() -> None:
    def TwoTexts(instrument: str, other: str, fields: TextRow, values: FieldRow[str]) -> float:
        return 0.0

    def NoText(fields: TextRow, values: FieldRow[str]) -> float:
        return 0.0

    def NoHandle(fields: TextRow, values: FieldRows[Toy]) -> float:
        return 0.0

    for fn, count, words in (
        (TwoTexts, 2, "text"),
        (NoText, 0, "text"),
        (NoHandle, 0, "toy handle"),
    ):
        with pytest.raises(
            TypeError,
            match=re.escape(
                f"{fn.__name__}: values selects its instrument by the {words} parameter, "
                f"of which the function has {count}, expected exactly 1"
            ),
        ):
            register(fn, hidden=True)


def test_field_values_take_no_default_and_a_listed_function_declares_them_with_help() -> None:
    def Defaulted(instrument: str, fields: TextRow, values: FieldRow[str] | None = None) -> float:
        return 0.0

    with pytest.raises(
        TypeError, match=r"Defaulted: values declares field values, which take no default"
    ):
        register(Defaulted, hidden=True)

    def ListedFields(
        instrument: Annotated[str, "An instrument."],
        fields: Annotated[TextRow, "The headers."],
        values: Annotated[FieldRow[str], "The values."],
    ) -> float:
        """Lists, for the test of its help."""
        return 0.0

    register(ListedFields, hidden=False)
    arguments = next(a for name, _, a, _, _ in bridge.function_specs() if name == "ListedFields")
    assert arguments[2] == ("values", "The values.")
