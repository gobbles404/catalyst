"""The worksheet functions of the instrument catalog: the list of the library's definitions, and
one definition shown with its fields across the columns and its seven metadata rows down, the
same records a template and a ticket are bound against. Both read, neither creates a handle.
docs/library/instruments/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the page quotes the lines.
"""

from typing import Annotated

from goosedove.excel.bridge import MixedArray, excel_function
from goosedove.instruments import definitions
from goosedove.instruments.definitions import CATALOG, ROWS, Instrument

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_ListInstruments", "_ShowInstrument"]


@excel_function
def _ListInstruments() -> MixedArray:
    """Lists the library-defined instruments and their descriptions."""
    return catalog_cells(CATALOG)


def catalog_cells(instruments: tuple[Instrument, ...]) -> MixedArray:
    """The catalog as the sheet sees it: two text columns, instrument and description, a header
    and one row per definition in the library's order; the header alone for an empty catalog."""
    return MixedArray.table(
        [("instrument", "description")],
        tuple([each.name for each in instruments]),
        tuple([each.description for each in instruments]),
    )


@excel_function
def _ShowInstrument(
    instrument: Annotated[str, "One instrument name from _ListInstruments, such as fixed_float."],
) -> MixedArray:
    """Shows an instrument's fields, requirements, types and rules."""
    return schema_cells(definitions.instrument(instrument))


def schema_cells(definition: Instrument) -> MixedArray:
    """The definition as the sheet sees it: seven rows, their labels down the first column, and a
    column per field to the right, the field's name in the first row, its description, whether
    it is required, as a boolean, the condition that otherwise requires it, its type, its options
    and its rule beneath. One cell per fact, none of them blank."""
    fields = definition.fields
    rows: list[list[object]] = [
        [ROWS[0], *(field.name for field in fields)],
        [ROWS[1], *(field.description for field in fields)],
        [ROWS[2], *(field.required for field in fields)],
        [ROWS[3], *(field.required_when for field in fields)],
        [ROWS[4], *(field.type.value for field in fields)],
        [ROWS[5], *(field.options for field in fields)],
        [ROWS[6], *(field.rule for field in fields)],
    ]
    return MixedArray.cells(rows)
