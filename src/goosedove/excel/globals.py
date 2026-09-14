"""The worksheet functions of the globals: the shared objects every calculation starts from,
each created once and reached by handle. docs/library/globals/ holds a page per function."""

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
def CreateValuationDate(as_of: Date, day_fraction_elapsed: float) -> Handle[ValuationDate]:
    """Creates a valuation-date handle from a date and the fraction of that day elapsed."""
    return valuation_date(as_of, day_fraction_elapsed)


class DiscountCurveTable(Table):
    """The curve's table: one row per calendar day, the date and its discount factor."""

    date: DateColumn
    discount_factor: NumberColumn


@excel_function
def CreateDiscountCurve(header_row: TextRow, table: DiscountCurveTable) -> Handle[DiscountCurve]:
    """Creates a daily discount-curve handle. Its last date is the latest the library prices."""
    return discount_curve(table.date, table.discount_factor)


# Temporary: the reader that proves a handle resolves to its curve. It goes when a real
# consumer of a curve exists.
@excel_function
def util_ReadDiscountFactor(curve: Handle[DiscountCurve], date: Date) -> float:
    """Reads the discount factor for one day from a discount-curve handle."""
    return factor_on(curve, date)
