"""The worksheet functions of the market: the history of one index, its calendar bound to the
settle fixed on each of its past business days, created once from two objects the sheet already
holds, and the market, the history with the current futures prices, created as often as the
prices move, each reached by handle. docs/library/market/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the page quotes the lines.
"""

from typing import Annotated

from goosedove.calendar.calendar import Calendar
from goosedove.excel.bridge import Handle, excel_function
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.daily_fixings import DailyFixings
from goosedove.market_data.price_vector import PriceVector

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_CreateMarket", "_CreateMarketHistory"]


@excel_function
def _CreateMarketHistory(
    calendar: Annotated[
        Handle[Calendar],
        "The index's calendar handle: the cell showing _CreateCalendar's result, such as B7, "
        "or a name for it.",
    ],
    daily_fixings: Annotated[
        Handle[DailyFixings],
        "The index's daily-fixings handle: the cell showing the result of _CreateDailyFixings, "
        "such as B10, or a name for it, with a fixing on every past business day of the calendar.",
    ],
) -> Handle[MarketHistory]:
    """Creates the market history of one index, its calendar with the settle fixed on each past
    business day, and shows its handle, the text other formulas take as the history."""
    return market_history(calendar, daily_fixings)


@excel_function
def _CreateMarket(
    market_history: Annotated[
        Handle[MarketHistory],
        "The market-history handle: the cell showing _CreateMarketHistory's result, such as B10, "
        "or a name for it.",
    ],
    price_vector: Annotated[
        Handle[PriceVector],
        "The price-vector handle from _CreatePriceVector, such as B12, with prices in schedule "
        "order from the valuation day's prompt through the last contract.",
    ],
) -> Handle[Market]:
    """Creates the daily market of one index from its history and current futures prices and
    shows its handle, the text other formulas take as the market."""
    return market(market_history, price_vector)
