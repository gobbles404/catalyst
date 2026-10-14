"""The worksheet functions of the trades: the template, shared field values under one instrument,
created once and taken last by the trades creator, and the trades, a batch of one or many on one
index, resolved from a template and a ticket and encoded, each reached by handle.
docs/library/trades/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

from goosedove.excel.bridge import FieldRow, FieldRows, Handle, TextRow, excel_function
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.index import Index
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.resolution import Trades, trades
from goosedove.trades.template import TradeTemplate, trade_template

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_CreateTradeTemplate", "_CreateTrades"]


@excel_function
def _CreateTradeTemplate(
    instrument: Annotated[str, "One instrument name from _ListInstruments, such as future."],
    fields: Annotated[
        TextRow,
        "The field-name cells in one row, such as A1:B1, using names shown by _ShowInstrument.",
    ],
    values: Annotated[FieldRow[str], "The values in one row beneath those fields, such as A2:B2."],
) -> Handle[TradeTemplate]:
    """Creates shared defaults for an instrument and shows their handle, the text other formulas
    take as the trade template."""
    return trade_template(values)


@excel_function
def _CreateTrades(
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as I3, or a name for it, "
        "the one index every trade of the batch is on.",
    ],
    fields: Annotated[
        TextRow,
        "The ticket's header cells in one row, such as A4:E4, using names shown by "
        "_ShowInstrument and none the template supplies.",
    ],
    trade_rows: Annotated[
        FieldRows[TradeTemplate],
        "The rows under the headers, such as A5:E9, one trade per row, a repeated row a second "
        "trade.",
    ],
    template: Annotated[
        Handle[TradeTemplate],
        "The trade-template handle: the cell showing _CreateTradeTemplate's result, such as B3, "
        "or a name for it, which selects the instrument and supplies the shared fields.",
    ],
) -> Handle[Trades]:
    """Creates a batch of trades on one index from a template's shared fields and a ticket's rows,
    each contract code resolved against the index's schedule, and shows its handle, the text other
    formulas take as the trades."""
    return trades(index, trade_rows, template, UNITS, WorkCounter())
