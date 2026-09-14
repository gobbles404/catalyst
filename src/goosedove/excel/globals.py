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
from goosedove.globals.discount_curve import DiscountCurve, discount_curve, factor_on
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
    """The curve's table: one row per calendar day, the date and its discount factor."""

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
        "The rows under the headers, such as A2:B400: one calendar day per row with its "
        "discount factor, starting at 1 and never rising.",
    ],
) -> Handle[DiscountCurve]:
    """Creates a discount curve from a daily table and shows its handle, the text other
    formulas take as the curve."""
    return discount_curve(table.date, table.discount_factor)


# Temporary: the reader that proves a handle resolves to its curve. It goes when a real
# consumer of a curve exists.
@excel_function
def util_ReadDiscountFactor(
    curve: Annotated[
        Handle[DiscountCurve],
        "A discount-curve handle: the cell showing CreateDiscountCurve's result, such as B5, "
        "or a name for it.",
    ],
    date: Annotated[
        Date, "The day to read, such as 12-Sep-2026, between the curve's first and last dates."
    ],
) -> float:
    """Reads the discount factor for one day from a discount curve."""
    return factor_on(curve, date)
