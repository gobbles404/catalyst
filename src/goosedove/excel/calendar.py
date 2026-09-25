"""The worksheet function of the calendar: every day of one index from its first contract's
expiry to its last, with the contract prompt on each day and two flags, created once from three
objects the sheet already holds and reached by handle. docs/library/calendar/calendar.md is the
page.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the page quotes the lines.
"""

from typing import Annotated

from goosedove.calendar.calendar import Calendar, calendar
from goosedove.excel.bridge import Handle, excel_function
from goosedove.globals.valuation_date import ValuationDate
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar

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
    futures_schedule: Annotated[
        Handle[FuturesSchedule],
        "The index's futures-schedule handle: the cell showing _CreateFuturesSchedule's result, "
        "such as B8, or a name for it, two contracts or more.",
    ],
    holiday_calendar: Annotated[
        Handle[HolidayCalendar],
        "The market's holiday-calendar handle: the cell showing _CreateHolidayCalendar's "
        "result, such as B12, or a name for it.",
    ],
) -> Handle[Calendar]:
    """Creates the calendar of one index, every day after its first contract's expiry to its
    last, with the contract prompt on each, whether the market is open and whether the day is
    past, and shows its handle, the text other formulas take as the calendar."""
    return calendar(valuation_date, futures_schedule, holiday_calendar)
