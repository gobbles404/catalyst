"""The worksheet functions of the market data: the fixings of one index, a settle on each business
day, Inside FERC's index for each contract month or Gas Daily's midpoint for each flow day, each
series created once over the index it belongs to, and its futures prices, a column snapped as
often as the sheet recalculates, each reached by handle.
docs/library/market-data/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

from catalyst.excel.bridge import (
    DateColumn,
    Handle,
    NumberArray,
    NumberColumn,
    excel_function,
)
from catalyst.index_definitions.index import Index
from catalyst.market_data.futures_fixings import FuturesFixings, futures_fixings
from catalyst.market_data.gas_daily_fixings import GasDailyFixings, gas_daily_fixings
from catalyst.market_data.price_vector import PriceVector, price_vector
from catalyst.market_data.published_fixings import PublishedFixings, published_fixings

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = [
    "_CreateFuturesFixings",
    "_CreateGasDailyFixings",
    "_CreatePriceVector",
    "_CreatePublishedFixings",
]


@excel_function
def _CreateFuturesFixings(
    date: Annotated[
        DateColumn,
        "The column of days the index fixed, newest first, such as A2:A5 holding 6-May-2026 "
        "down to 1-May-2026, one for every business day between them.",
    ],
    settle: Annotated[
        NumberArray,
        "The settles beside the days, such as B2:B5, one row per day; a wider range, such as "
        "B2:C5, holds a column for each nearby contract, the prompt's first.",
    ],
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as D3, or a name for "
        "it; a futures index, whose holiday calendar the days are checked against.",
    ],
) -> Handle[FuturesFixings]:
    """Creates the futures fixings of one index from the days it fixed and their settles, a
    column for each nearby contract, checked against the holiday calendar of its index, and
    shows its handle, the text other formulas take as the fixings."""
    return futures_fixings(date, settle, index)


@excel_function
def _CreateGasDailyFixings(
    flow_date: Annotated[
        DateColumn,
        "The column of flow days, newest first, such as A2:A7 holding 9-Sep-2026 down to "
        "4-Sep-2026, one for every calendar day between them.",
    ],
    price: Annotated[
        NumberColumn,
        "The column of midpoints beside the flow days, such as B2:B7, one per day.",
    ],
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as C4, or a name for "
        "it; a Gas Daily index, the one these fixings belong to.",
    ],
) -> Handle[GasDailyFixings]:
    """Creates the Gas Daily fixings of one index from the days gas flowed and the midpoint
    printed for each, one for every calendar day between the newest and the oldest, and shows its
    handle, the text other formulas take as the fixings."""
    return gas_daily_fixings(flow_date, price, index)


@excel_function
def _CreatePublishedFixings(
    publication_date: Annotated[
        DateColumn,
        "The column of dates on the prints that have a price, newest first, such as A2:A4 "
        "holding 14-Sep-2026 down to 31-Aug-2026, each a date of the index's schedule.",
    ],
    price: Annotated[
        NumberColumn,
        "The column of prices beside the dates, such as B2:B4, one per date; a stand-in where "
        "a print has fixed and its publisher has not released it.",
    ],
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as D3, or a name for "
        "it; a published index, whose schedule the dates are checked against.",
    ],
) -> Handle[PublishedFixings]:
    """Creates the published fixings of one index from the dates of its prints that have a
    price, newest first, and the price of each, checked against the dates of its index's
    schedule, and shows its handle, the text other formulas take as the fixings."""
    return published_fixings(publication_date, price, index)


@excel_function
def _CreatePriceVector(
    index_name: Annotated[
        str,
        'The name the index was created with, such as A1 or "WTI NYMEX", typed as '
        "_CreateIndex was given it; the market checks it against its history's index.",
    ],
    prices: Annotated[
        NumberColumn, "The column of futures prices, such as B2:B101, without a header."
    ],
) -> Handle[PriceVector]:
    """Creates a price vector of one index from the index's name and one column of prices, and
    shows its handle, the text other formulas take as the price vector."""
    return price_vector(index_name, prices)
