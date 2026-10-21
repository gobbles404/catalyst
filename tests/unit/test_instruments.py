"""The instrument catalog: the definitions as library data and their integrity, _ListInstruments
and _ShowInstrument through the seam, the Show page's table kept equal to the spill cell for
cell, and the cell-wise builder the Show layout needs."""

import re
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import BOOLEAN_CODE, MISSING, NUMBER_CODE, TEXT_CODE, MixedArray
from goosedove.excel.instruments import (
    _ListInstruments,
    _ShowInstrument,
    catalog_cells,
    schema_cells,
)
from goosedove.instruments.definitions import (
    CASHFLOW,
    CATALOG,
    FIXED_FLOAT,
    NONE,
    ROWS,
    Field,
    FieldType,
    Instrument,
    catalog,
    instrument,
)

ENTRY = {name: bridge.entry(name) for name in ("_ListInstruments", "_ShowInstrument")}


def spilled(result: object) -> tuple[NDArray[np.uint8], NDArray[np.float64], str]:
    """A mixed array as the prepared path hands it to the host: the kinds, the slots, the texts
    joined with NUL."""
    return cast(tuple[NDArray[np.uint8], NDArray[np.float64], str], result)


FIELDS = tuple([field.name for field in FIXED_FLOAT.fields])


# --- the definitions ------------------------------------------------------------------------


def test_the_catalog_holds_the_fixed_float_with_its_nineteen_fields_in_order() -> None:
    assert [each.name for each in CATALOG] == ["fixed_float", "cashflow"]
    assert FIELDS == (
        "trade_id",
        "trade_date",
        "contract_code",
        "start_date",
        "end_date",
        "schedule_method",
        "route",
        "settlement_method",
        "clearing_house",
        "counterparty",
        "discount_curve_key",
        "broker",
        "quantity",
        "quantity_unit",
        "quantity_per",
        "fixed_price",
        "payment_day",
        "payment_holiday_calendar",
        "marketing_reserve",
    )
    by_name = {field.name: field for field in FIXED_FLOAT.fields}
    assert [field.name for field in FIXED_FLOAT.fields if field.required] == [
        "trade_date",
        "schedule_method",
        "route",
        "settlement_method",
        "quantity",
        "quantity_unit",
        "quantity_per",
        "fixed_price",
    ]
    assert by_name["clearing_house"].required_when == "route = cleared"
    assert by_name["contract_code"].required_when == "no start_date and end_date on the row"
    assert by_name["start_date"].required_when == "no contract_code on the row, or with end_date"
    assert by_name["end_date"].required_when == "no contract_code on the row, or with start_date"
    assert by_name["end_date"].type is FieldType.DATE
    # Since #172 the three period fields alone let a cell go unsupplied, a blank or an empty text
    # meaning the row supplies no value; every other field's cell must hold one.
    assert [field.name for field in FIXED_FLOAT.fields if field.may_be_unsupplied] == [
        "contract_code",
        "start_date",
        "end_date",
    ]
    assert by_name["payment_day"].required_when == "settlement_method = financial"
    assert by_name["payment_holiday_calendar"].required_when == "settlement_method = financial"
    assert by_name["payment_holiday_calendar"].type is FieldType.HOLIDAY_CALENDAR
    assert by_name["payment_day"].type is FieldType.DATE_OR_TEXT  # a date or a rule
    assert {field.name for field in FIXED_FLOAT.fields if field.type is FieldType.CODE} == {
        "schedule_method",
        "route",
        "settlement_method",
        "quantity_per",
    }
    assert by_name["quantity_unit"].type is FieldType.TEXT
    assert by_name["quantity_unit"].options == "the index's specification names"
    assert all(field.required_when == NONE for field in FIXED_FLOAT.fields if field.required)


def test_the_quote_metadata_says_what_a_quote_template_may_hold_and_a_quote_requires() -> None:
    # template-based-quoting.md: a quote template holds the seven fields of a trade's terms a
    # quote reads and none of the booking facts; four are always required, the two payment
    # fields with a financial settlement and the curve key on the bilateral route; a cashflow
    # has no quote.
    by_name = {field.name: field for field in FIXED_FLOAT.fields}
    assert [field.name for field in FIXED_FLOAT.fields if field.quote_allowed] == [
        "schedule_method",
        "route",
        "settlement_method",
        "discount_curve_key",
        "quantity_per",
        "payment_day",
        "payment_holiday_calendar",
    ]
    assert [field.name for field in FIXED_FLOAT.fields if field.quote_required] == [
        "schedule_method",
        "route",
        "settlement_method",
        "quantity_per",
    ]
    assert by_name["discount_curve_key"].quote_required_when == "route = bilateral"
    assert by_name["payment_day"].quote_required_when == "settlement_method = financial"
    assert by_name["payment_holiday_calendar"].quote_required_when == (
        "settlement_method = financial"
    )
    assert all(
        field.quote_required_when == NONE
        for field in FIXED_FLOAT.fields
        if not field.quote_allowed or field.quote_required
    )
    assert not any(field.quote_allowed for field in CASHFLOW.fields)
    assert all(
        not field.quote_required and field.quote_required_when == NONE for field in CASHFLOW.fields
    )


def a_field(
    name: str = "f",
    required_when: str = NONE,
    rule: str = "r",
    quote_allowed: bool = False,
    quote_required: bool = False,
    quote_required_when: str = NONE,
) -> Field:
    return Field(
        name,
        "d",
        True,
        required_when,
        FieldType.TEXT,
        "o",
        rule,
        quote_allowed=quote_allowed,
        quote_required=quote_required,
        quote_required_when=quote_required_when,
    )


@pytest.mark.parametrize(
    ("instruments", "message"),
    [
        ((Instrument("", "d", ()),), "instrument '' needs a nonempty name and description"),
        ((Instrument("x", "", ()),), "instrument 'x' needs a nonempty name and description"),
        (
            (Instrument("x", "d", ()), Instrument("x", "e", ())),
            "instrument 'x' is defined twice",
        ),
        ((Instrument("x", "d", (a_field(), a_field())),), "x defines field 'f' twice"),
        ((Instrument("x", "d", (a_field(rule=""),)),), "x field 'f' has an empty cell"),
        ((Instrument("x", "d", (a_field(required_when=""),)),), "x field 'f' has an empty cell"),
        (
            (Instrument("x", "d", (a_field(quote_allowed=True, quote_required_when=""),)),),
            "x field 'f' has an empty cell",
        ),
        (
            (Instrument("x", "d", (a_field(quote_required=True),)),),
            "x field 'f' is required by a quote but not allowed in one",
        ),
        (
            (Instrument("x", "d", (a_field(quote_required_when="route = bilateral"),)),),
            "x field 'f' is required by a quote but not allowed in one",
        ),
    ],
)
def test_a_definition_that_cannot_be_authored_says_why(
    instruments: tuple[Instrument, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        catalog(*instruments)


def test_an_instrument_is_found_by_its_exact_name_or_refused_with_the_names_there_are() -> None:
    assert instrument("fixed_float") is FIXED_FLOAT
    assert instrument("cashflow") is CASHFLOW
    with pytest.raises(
        ValueError,
        match=r"^instrument is 'Future', expected one of: 'fixed_float', 'cashflow'$",
    ):
        instrument("Future")
    with pytest.raises(
        ValueError,
        match=r"^instrument is ' fixed_float', expected one of: 'fixed_float', 'cashflow'$",
    ):
        instrument(" fixed_float")
    with pytest.raises(
        ValueError,
        match=r"^instrument is 'fixed_float', expected a listed instrument; none are defined$",
    ):
        instrument("fixed_float", ())
    with pytest.raises(
        ValueError,
        match=r"^instrument is 'future', expected one of: 'fixed_float', 'cashflow'$",
    ):
        instrument("future")  # the name until #174, refused as any other word
    two = (FIXED_FLOAT, Instrument("swap", "d", (a_field(),)))
    with pytest.raises(
        ValueError, match=r"^instrument is 'x', expected one of: 'fixed_float', 'swap'$"
    ):
        instrument("x", two)


# --- the spills -----------------------------------------------------------------------------


def test_the_list_spills_a_header_and_one_row_per_instrument() -> None:
    listed = _ListInstruments()
    assert listed.shape == (3, 2)
    assert listed.texts == (
        "instrument",
        "description",
        "fixed_float",
        "A fixed-for-floating position on a specified reference contract, with explicit "
        "observation and settlement terms.",
        "cashflow",
        "A known signed amount in one currency, payable on one explicit date.",
    )
    assert (listed.kinds == TEXT_CODE).all()


def test_an_empty_catalog_lists_its_header_alone() -> None:
    header = catalog_cells(())
    assert header.shape == (1, 2) and header.texts == ("instrument", "description")


def test_every_listed_instrument_is_shown_by_its_listed_name() -> None:
    listed = _ListInstruments()
    names = listed.texts[2::2]
    assert names == tuple([each.name for each in CATALOG])
    for name in names:
        kinds, _, _ = spilled(ENTRY["_ShowInstrument"](name))
        assert kinds.shape[0] == 10


def test_a_one_field_definition_shows_ten_rows_and_two_columns() -> None:
    one = schema_cells(Instrument("one", "d", (a_field("only"),)))
    assert one.shape == (10, 2)
    assert one.texts == (
        "field",
        "only",
        "description",
        "d",
        "required",
        "required_when",
        NONE,
        "type",
        "text",
        "options",
        "o",
        "rule",
        "r",
        "quote_allowed",
        "quote_required",
        "quote_required_when",
        NONE,
    )
    assert one.kinds[2, 1] == BOOLEAN_CODE and one.numeric_slots[2, 1] == 1.0
    assert one.kinds[7, 1] == BOOLEAN_CODE and one.numeric_slots[7, 1] == 0.0
    assert one.kinds[8, 1] == BOOLEAN_CODE and one.numeric_slots[8, 1] == 0.0


def test_the_show_spills_ten_rows_and_a_column_per_field() -> None:
    shown = _ShowInstrument("fixed_float")
    assert shown.shape == (10, 20)
    labels = (0, 20, 40, 41, 61, 81, 101, 121, 122, 123)  # column one, among the texts
    assert tuple([shown.texts[i] for i in labels]) == ROWS
    assert shown.texts[:20] == ("field", *FIELDS)
    # The required row and, since template-based-quoting.md, the two quote rows of booleans
    # after their labels: what a quote template may hold and what a quote always requires.
    for row, fact in ((2, "required"), (7, "quote_allowed"), (8, "quote_required")):
        kinds = shown.kinds[row]
        assert kinds[0] == TEXT_CODE and (kinds[1:] == BOOLEAN_CODE).all()
        np.testing.assert_array_equal(
            shown.numeric_slots[row, 1:],
            [getattr(field, fact) for field in FIXED_FLOAT.fields],
        )
    other_rows = np.delete(shown.kinds, (2, 7, 8), axis=0)
    assert (other_rows == TEXT_CODE).all()
    assert len(shown.texts) == 10 * 20 - 3 * 19
    assert "" not in shown.texts


@pytest.mark.parametrize(("definition", "columns"), [(FIXED_FLOAT, 20), (CASHFLOW, 8)])
def test_the_show_page_shows_the_same_cells_as_the_spill(
    definition: Instrument, columns: int
) -> None:
    page = Path(__file__).resolve().parents[2] / "docs/library/instruments/show-instrument.md"
    lines = page.read_text(encoding="utf-8").split("\n")
    first = "| field | " + " | ".join(field.name for field in definition.fields[:3]) + " |"
    start = next(i for i, line in enumerate(lines) if line.startswith(first))
    table = [[cell.strip() for cell in line.split("|")[1:-1]] for line in lines[start : start + 11]]
    del table[1]  # the markdown separator row
    shown = schema_cells(definition)
    texts = iter(shown.texts)
    for r in range(10):
        for c in range(columns):
            kind = shown.kinds[r, c]
            if kind == TEXT_CODE:
                cell = next(texts)
            else:
                cell = "TRUE" if shown.numeric_slots[r, c] == 1.0 else "FALSE"
            assert cell == table[r][c], (r, c)


def test_the_two_functions_through_the_seam_and_their_errors() -> None:
    kinds, slots, text = spilled(ENTRY["_ListInstruments"]())
    assert kinds.shape == (3, 2) and text.split("\0")[2::2] == ["fixed_float", "cashflow"]
    kinds, slots, text = spilled(ENTRY["_ShowInstrument"]("fixed_float"))
    assert kinds.shape == (10, 20) and slots[2, 1] == 0.0 and slots[2, 2] == 1.0
    assert slots[7, 6] == 1.0 and slots[8, 6] == 1.0 and slots[7, 1] == 0.0
    assert ENTRY["_ShowInstrument"]("Future") == (
        "#ERROR _ShowInstrument: ValueError: instrument is 'Future', expected one of: "
        "'fixed_float', 'cashflow'"
    )
    assert ENTRY["_ShowInstrument"]("future") == (  # the name until #174
        "#ERROR _ShowInstrument: ValueError: instrument is 'future', expected one of: "
        "'fixed_float', 'cashflow'"
    )
    assert (
        ENTRY["_ShowInstrument"](None)
        == "#ERROR _ShowInstrument: instrument is blank, expected text"
    )
    assert ENTRY["_ShowInstrument"]("") == (
        "#ERROR _ShowInstrument: instrument is empty text, expected text"
    )
    assert ENTRY["_ShowInstrument"](3.0) == (
        "#ERROR _ShowInstrument: instrument is number 3.0, expected text"
    )
    assert ENTRY["_ShowInstrument"](MISSING) == (
        "#ERROR _ShowInstrument: instrument is missing, expected text"
    )


def test_reading_the_catalog_publishes_nothing() -> None:
    live = len(bridge.live_handles())
    for _ in range(3):
        ENTRY["_ListInstruments"]()
        ENTRY["_ShowInstrument"]("fixed_float")
    assert len(bridge.live_handles()) == live


# --- the cell-wise builder ------------------------------------------------------------------


def test_the_cell_builder_lays_cells_out_as_given_with_the_texts_in_sheet_order() -> None:
    grid = MixedArray.cells([["a", True, 2.5], ["b", False, 3]])
    assert grid.shape == (2, 3)
    np.testing.assert_array_equal(
        grid.kinds,
        [[TEXT_CODE, BOOLEAN_CODE, NUMBER_CODE], [TEXT_CODE, BOOLEAN_CODE, NUMBER_CODE]],
    )
    np.testing.assert_array_equal(grid.numeric_slots[:, 1:], [[1.0, 2.5], [0.0, 3.0]])
    assert grid.texts == ("a", "b")
    assert MixedArray.cells([["x"]]).shape == (1, 1)
    # A whole number a cell holds exactly, 2^53 either side, goes out as the float it is; one
    # beyond is refused rather than rounded, as the number and table results refuse it.
    edge = MixedArray.cells([[2**53, -(2**53), 0.5]])
    np.testing.assert_array_equal(
        edge.numeric_slots, [[9007199254740992.0, -9007199254740992.0, 0.5]]
    )
    assert (edge.kinds == NUMBER_CODE).all()


BAD_GRIDS: list[tuple[list[list[object]], str]] = [
    ([], "cells need at least one row of at least one cell"),
    ([[]], "cells need at least one row of at least one cell"),
    ([["a", "b"], ["c"]], "row 2 holds 1 cells, expected 2, as row 1 does"),
    ([["a", None]], r"cell \(1, 2\) holds nothing, expected a value"),
    ([["a"], [MISSING]], r"cell \(2, 1\) holds nothing, expected a value"),
    ([[2**53 + 1]], r"cell \(1, 1\) is 9007199254740993, beyond what a cell holds exactly"),
    (
        [["a", -(2**53) - 1]],
        r"cell \(1, 2\) is -9007199254740993, beyond what a cell holds exactly",
    ),
]


@pytest.mark.parametrize(("rows", "message"), BAD_GRIDS)
def test_a_grid_that_cannot_be_laid_out_says_why(rows: list[list[object]], message: str) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        MixedArray.cells(rows)
