"""The worksheet function of the calendar: the periods one index prices, from the index, with the
contract on each and two flags, created once from the valuation date and the index the sheet
already holds, and reached by handle. docs/library/calendar/calendar.md is the page.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the page quotes the lines.
"""

from typing import Annotated

from goosedove.calendar.calendar import Calendar, calendar
from goosedove.excel.bridge import Handle, excel_function
from goosedove.globals.valuation_date import ValuationDate
from goosedove.index_definitions.index import Index

# The worksheet function this module registers, named here so that its leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_CreateCalendar"]


@excel_function
def _CreateCalendar(
    valuation_date: Annotated[
        Handle[ValuationDate],
        "The valuation-date handle: the cell showing _CreateValuationDate's result, such as B2, "
        "or a name for it.",
    ],
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as B10, or a name for "
        "it; a futures index needs two contracts or more.",
    ],
) -> Handle[Calendar]:
    """Creates the calendar of one index, one row per day it prices, or per month for an index
    published monthly, each with its contract and whether it has fixed, and shows its handle,
    the text other formulas take as the calendar."""
    return calendar(valuation_date, index)
