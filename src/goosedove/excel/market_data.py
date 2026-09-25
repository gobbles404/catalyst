"""The worksheet functions of the market data: the fixings of one index, a settle on each business
day, Inside FERC's index for each contract month or Gas Daily's midpoint for each flow day, each
series created once, and its futures prices, a column snapped as often as the sheet
recalculates, each reached by handle.
docs/library/market-data/ holds a page per function.

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
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.market_data.daily_fixings import DailyFixings, daily_fixings
from goosedove.market_data.gas_daily_fixings import GasDailyFixings, gas_daily_fixings
from goosedove.market_data.iferc_fixings import IfercFixings, iferc_fixings
from goosedove.market_data.price_vector import PriceVector, price_vector

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = [
    "_CreateDailyFixings",
    "_CreateGasDailyFixings",
    "_CreateIfercFixings",
    "_CreatePriceVector",
]


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
def _CreateIfercFixings(
    contract_code: Annotated[
        TextColumn,
        "The column of contract codes, such as A2:A5 holding F26 to J26, one per month published.",
    ],
    price: Annotated[
        NumberColumn,
        "The column of published indices beside the codes, such as B2:B5, one per code.",
    ],
) -> Handle[IfercFixings]:
    """Creates the IFERC fixings of one index from the contract months whose index has been
    published and the index printed for each, and shows its handle, the text other formulas
    take as the fixings."""
    return iferc_fixings(contract_code, price)


@excel_function
def _CreateGasDailyFixings(
    flow_date: Annotated[
        DateColumn,
        "The column of flow days, such as A2:A7 holding 4-Sep-2026 to 9-Sep-2026, one for every "
        "calendar day from the first to the last.",
    ],
    price: Annotated[
        NumberColumn,
        "The column of midpoints beside the flow days, such as B2:B7, one per day.",
    ],
) -> Handle[GasDailyFixings]:
    """Creates the Gas Daily fixings of one index from the days gas flowed and the midpoint
    printed for each, one for every calendar day from the first to the last, and shows its
    handle, the text other formulas take as the fixings."""
    return gas_daily_fixings(flow_date, price)


@excel_function
def _CreatePriceVector(
    prices: Annotated[
        NumberColumn, "The column of futures prices, such as B2:B101, without a header."
    ],
) -> Handle[PriceVector]:
    """Creates a price vector from one column of prices and shows its handle, the text other
    formulas take as the price vector."""
    return price_vector(prices)
