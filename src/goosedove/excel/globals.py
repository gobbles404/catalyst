"""The worksheet functions of the globals: the shared objects every calculation starts from,
each created once and reached by handle. docs/library/globals/ holds a page per function.

The words beside each parameter are what Excel shows the desk about that argument, as the
docstring is what it shows about the function; the pages quote them.
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
    as_of: Annotated[Date, "One date, from 1-Mar-1900 to 31-Dec-9999, with no time of day."],
    day_fraction_elapsed: Annotated[
        float,
        "One number from 0 to 1: 0 is the start of as_of, 1 its end. The date is kept as given.",
    ],
) -> Handle[ValuationDate]:
    """Creates a valuation-date handle from a date and the fraction of that day elapsed."""
    return valuation_date(as_of, day_fraction_elapsed)


class DiscountCurveTable(Table):
    """The curve's table: one row per calendar day, the date and its discount factor."""

    date: DateColumn
    discount_factor: NumberColumn


@excel_function
def CreateDiscountCurve(
    header_row: Annotated[
        TextRow,
        "One row holding the two headers, date and discount_factor, in either order; capitals do "
        "not matter.",
    ],
    table: Annotated[
        DiscountCurveTable,
        "The body under the headers: one row per calendar day, the date and its discount factor, "
        "no day missing. The first factor is 1, and factors never rise and stay above 0.",
    ],
) -> Handle[DiscountCurve]:
    """Creates a daily discount-curve handle. Its last date is the latest the library prices."""
    return discount_curve(table.date, table.discount_factor)


# Temporary: the reader that proves a handle resolves to its curve. It goes when a real
# consumer of a curve exists.
@excel_function
def util_ReadDiscountFactor(
    curve: Annotated[
        Handle[DiscountCurve], "The cell holding a discount-curve handle, or a name for that cell."
    ],
    date: Annotated[Date, "One date between the curve's first and last dates, inclusive."],
) -> float:
    """Reads the discount factor for one day from a discount-curve handle."""
    return factor_on(curve, date)
