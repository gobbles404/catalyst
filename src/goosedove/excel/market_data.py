"""The worksheet functions of the market data: the fixings of one index, daily or monthly, each
series created once, and its futures prices, a column snapped as often as the sheet recalculates,
each reached by handle. docs/library/market-data/ holds a page per function.

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
    TextRow,
    excel_function,
)
from goosedove.index_definitions.expiry_schedule import ExpirySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.market_data.daily_fixings import DailyFixings, daily_fixings
from goosedove.market_data.monthly_fixings import MonthlyFixings, monthly_fixings
from goosedove.market_data.price_vector import PriceVector, price_vector

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_CreateDailyFixings", "_CreateMonthlyFixings", "_CreatePriceVector"]


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
        "The column of days the index's monthly settles are published, as its schedule states "
        "them, such as A2:A5 holding 5-Jan-2026 to 1-Apr-2026, one per fixing.",
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
    """Creates the monthly fixings of one index from its prices, published or provisional, each
    dated the day its expiry schedule says the settle is published, and shows its handle, the
    text other formulas take as the fixings."""
    return monthly_fixings(publication_date, price, expiry_schedule.publication_date)


@excel_function
def _CreatePriceVector(
    prices: Annotated[
        NumberColumn, "The column of futures prices, such as B2:B101, without a header."
    ],
) -> Handle[PriceVector]:
    """Creates a price vector from one column of prices and shows its handle, the text other
    formulas take as the price vector."""
    return price_vector(prices)
