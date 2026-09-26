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

from goosedove.excel.bridge import (
    DateColumn,
    Handle,
    NumberColumn,
    TextColumn,
    excel_function,
)
from goosedove.index_definitions.index import Index
from goosedove.market_data.futures_fixings import FuturesFixings, futures_fixings
from goosedove.market_data.gas_daily_fixings import GasDailyFixings, gas_daily_fixings
from goosedove.market_data.iferc_fixings import IfercFixings, iferc_fixings
from goosedove.market_data.price_vector import PriceVector, price_vector

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = [
    "_CreateFuturesFixings",
    "_CreateGasDailyFixings",
    "_CreateIfercFixings",
    "_CreatePriceVector",
]


@excel_function
def _CreateFuturesFixings(
    date: Annotated[
        DateColumn,
        "The column of days the index fixed, such as A2:A5 holding 1-May-2026 to 6-May-2026, "
        "one for every business day from the first to the last.",
    ],
    settle: Annotated[
        NumberColumn,
        "The column of settles beside the days, such as B2:B5, one per day.",
    ],
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as D3, or a name for "
        "it; a futures index, whose holiday calendar the days are checked against.",
    ],
) -> Handle[FuturesFixings]:
    """Creates the futures fixings of one index from the days it fixed and their settles, checked
    against the holiday calendar of its index, and shows its handle, the text other formulas
    take as the fixings."""
    return futures_fixings(date, settle, index)


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
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as E3, or a name for "
        "it; an IFERC index, whose months the codes are checked against.",
    ],
) -> Handle[IfercFixings]:
    """Creates the IFERC fixings of one index from the contract months whose index has been
    published and the index printed for each, checked against the months of its index, and
    shows its handle, the text other formulas take as the fixings."""
    return iferc_fixings(contract_code, price, index)


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
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as C4, or a name for "
        "it; a Gas Daily index, the one these fixings belong to.",
    ],
) -> Handle[GasDailyFixings]:
    """Creates the Gas Daily fixings of one index from the days gas flowed and the midpoint
    printed for each, one for every calendar day from the first to the last, and shows its
    handle, the text other formulas take as the fixings."""
    return gas_daily_fixings(flow_date, price, index)


@excel_function
def _CreatePriceVector(
    prices: Annotated[
        NumberColumn, "The column of futures prices, such as B2:B101, without a header."
    ],
) -> Handle[PriceVector]:
    """Creates a price vector from one column of prices and shows its handle, the text other
    formulas take as the price vector."""
    return price_vector(prices)
