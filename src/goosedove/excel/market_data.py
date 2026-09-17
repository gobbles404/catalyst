"""The worksheet functions of the market data: the prices of one index, a futures curve and its
daily or monthly fixings, each set created once and reached by handle. docs/library/market-data/
holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

from goosedove.excel.bridge import (
    DateColumn,
    Handle,
    NumberColumn,
    Table,
    TextColumn,
    TextRow,
    excel_function,
)
from goosedove.index_definitions.expiry_schedule import ExpirySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.market_data.daily_fixings import DailyFixings, daily_fixings
from goosedove.market_data.futures_curve import FuturesCurve, futures_curve
from goosedove.market_data.monthly_fixings import MonthlyFixings, monthly_fixings

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_CreateDailyFixings", "_CreateFuturesCurve", "_CreateMonthlyFixings"]


@excel_function
def _CreateFuturesCurve(
    future_code: Annotated[
        TextColumn,
        "The column of contract codes, such as A2:A7 holding M26 to X26, one per contract.",
    ],
    price: Annotated[
        NumberColumn, "The column of prices beside the codes, such as B2:B7, one per code."
    ],
) -> Handle[FuturesCurve]:
    """Creates a futures curve from the contract codes of one index and their prices, and shows
    its handle, the text other formulas take as the curve."""
    return futures_curve(future_code, price)


class DailyFixingsTable(Table):
    """The fixings' table: one row per day the index fixed, the date and its settle."""

    date: DateColumn
    settle: NumberColumn


@excel_function
def _CreateDailyFixings(
    header_row: Annotated[
        TextRow,
        "The header cells of your fixings table, such as A1:B1, reading date and settle in "
        "either order.",
    ],
    table: Annotated[
        DailyFixingsTable,
        "The rows under the headers, such as A2:B5: one fixing per row, its date and settle, "
        "one for every business day from the first to the last.",
    ],
    holiday_calendar: Annotated[
        Handle[HolidayCalendar],
        "The market's holiday-calendar handle: the cell showing _CreateHolidayCalendar's "
        "result, such as D2, or a name for it.",
    ],
) -> Handle[DailyFixings]:
    """Creates the daily fixings of one index from the days it fixed and their settles, checked
    against its market's holiday calendar, and shows its handle, the text other formulas take as
    the fixings."""
    return daily_fixings(table.date, table.settle, holiday_calendar.holiday)


@excel_function
def _CreateMonthlyFixings(
    publication_date: Annotated[
        DateColumn,
        "The column of days the index's monthly settles were published, such as A2:A5 holding "
        "5-Jan-2026 to 1-Apr-2026, one per fixing.",
    ],
    price: Annotated[
        NumberColumn, "The column of prices beside the dates, such as B2:B5, one per date."
    ],
    expiry_schedule: Annotated[
        Handle[ExpirySchedule],
        "The index's expiry-schedule handle, built with its publication dates: the cell showing "
        "_CreateExpirySchedule's result, such as D6, or a name for it.",
    ],
) -> Handle[MonthlyFixings]:
    """Creates the monthly fixings of one index from the days its settles were published and
    their prices, checked against the publication dates of its expiry schedule, and shows its
    handle, the text other formulas take as the fixings."""
    return monthly_fixings(publication_date, price, expiry_schedule.publication_date)
