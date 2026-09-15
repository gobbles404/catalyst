"""The worksheet functions of the market definitions: what an index is, as opposed to the globals
every calculation starts from, each created once and reached by handle.
docs/library/market-definitions/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

from goosedove.excel.bridge import DateColumn, Handle, TextColumn, excel_function
from goosedove.market_definitions.expiry_schedule import ExpirySchedule, expiry_schedule


@excel_function
def CreateExpirySchedule(
    future_code: Annotated[
        TextColumn,
        "The column of contract codes, such as A2:A7 holding m26 to X26, one per contract.",
    ],
    future_expiry: Annotated[
        DateColumn,
        "The column of future expiry dates beside the codes, such as B2:B7, one per code.",
    ],
    option_expiry: Annotated[
        DateColumn | None,
        "The column of option expiry dates beside the codes, such as C2:C7, one per code.",
    ] = None,
) -> Handle[ExpirySchedule]:
    """Creates an expiry schedule from the contract codes of one index and their expiry dates,
    and shows its handle, the text other formulas take as the schedule."""
    return expiry_schedule(future_code, future_expiry, option_expiry)
