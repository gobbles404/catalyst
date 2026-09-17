"""The worksheet functions of the market data: the prices of one index, each set created once
and reached by handle. docs/library/market-data/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

from goosedove.excel.bridge import Handle, NumberColumn, TextColumn, excel_function
from goosedove.market_data.futures_curve import FuturesCurve, futures_curve

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_CreateFuturesCurve"]


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
