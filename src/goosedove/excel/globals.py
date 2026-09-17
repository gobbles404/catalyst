"""The worksheet functions of the globals: the shared objects every calculation starts from,
each created once and reached by handle. docs/library/globals/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line, one
sentence that says what to select, gives an example, and names at most one thing that must
hold, is docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

from goosedove.excel.bridge import (
    Date,
    DateColumn,
    Handle,
    NumberColumn,
    Table,
    TextRow,
    excel_function,
)
from goosedove.globals.discount_curve import DiscountCurve, discount_curve
from goosedove.globals.valuation_date import ValuationDate, valuation_date


@excel_function
def CreateValuationDate(
    as_of: Annotated[
        Date, "The valuation date, a date cell such as 11-Sep-2026, with no time of day."
    ],
    day_fraction_elapsed: Annotated[
        float, "How far through as_of: 0 at the start of the day, 0.5 at midday, 1 at the end."
    ],
) -> Handle[ValuationDate]:
    """Creates a valuation date and shows its handle, the text other formulas take as the
    valuation date."""
    return valuation_date(as_of, day_fraction_elapsed)


class DiscountCurveTable(Table):
    """The curve's table: one row per anchor, the date and its discount factor."""

    date: DateColumn
    discount_factor: NumberColumn


@excel_function
def CreateDiscountCurve(
    header_row: Annotated[
        TextRow,
        "The header cells of your curve table, such as A1:B1, reading date and discount_factor "
        "in either order.",
    ],
    table: Annotated[
        DiscountCurveTable,
        "The rows under the headers, such as A2:B12: one anchor per row, its date and discount "
        "factor, dates increasing from the valuation date at 1, the factors never rising.",
    ],
) -> Handle[DiscountCurve]:
    """Creates a discount curve from anchor dates and their discount factors, every day between
    filled in, and shows its handle, the text other formulas take as the curve."""
    return discount_curve(table.date, table.discount_factor)
