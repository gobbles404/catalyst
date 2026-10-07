"""The worksheet functions of the trades: the template, shared field values under one instrument,
created once and taken last by the trades creator; the trades, a batch of one or many on one
index, resolved from a template and a ticket and encoded; the batch prepared against one market
history, as often as the history moves; the prepared batch evaluated against one market, as often
as the quotes move; and the two reports of a result, its values and its risk, each handle to
handle. docs/library/trades/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

import numpy as np

from goosedove.excel.bridge import (
    FieldRow,
    FieldRows,
    Handle,
    MixedArray,
    TextRow,
    excel_function,
)
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.index import Index
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market import Market
from goosedove.market.market_history import MarketHistory
from goosedove.trades.evaluation import TradeResults, trade_results
from goosedove.trades.preparation import PreparedTrades, prepared_trades
from goosedove.trades.resolution import Trades, trades
from goosedove.trades.template import TradeTemplate, trade_template

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = [
    "_CreateTradeTemplate",
    "_CreateTrades",
    "_EvaluateTrades",
    "_PrepareTrades",
    "_ReportRisk",
    "_ReportValues",
]


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


@excel_function
def _PrepareTrades(
    trades: Annotated[
        Handle[Trades],
        "The trades handle: the cell showing _CreateTrades's result, such as A10, or a name "
        "for it.",
    ],
    history: Annotated[
        Handle[MarketHistory],
        "The market-history handle of the trades' index: the cell showing _CreateMarketHistory's "
        "result, such as B12, or a name for it, valued on the day the trades are prepared for.",
    ],
) -> Handle[PreparedTrades]:
    """Prepares a batch of trades against one market history, each observation whose day has
    passed fixed at that day's settle and each payment that has fallen due settled, and shows
    its handle, the text _EvaluateTrades takes as the prepared trades."""
    return prepared_trades(trades.encoded, history, WorkCounter())


@excel_function
def _EvaluateTrades(
    prepared: Annotated[
        Handle[PreparedTrades],
        "The prepared-trades handle: the cell showing _PrepareTrades's result, such as A11, or a "
        "name for it.",
    ],
    market: Annotated[
        Handle[Market],
        "The market handle over the history the trades were prepared against: the cell showing "
        "_CreateMarket's result, such as B13, or a name for it, with the day's quotes.",
    ],
) -> Handle[TradeResults]:
    """Evaluates prepared trades against one market, the live observations at their contracts'
    quotes and the fixed at their settles, into the batch's mark, cash and delta, and shows its
    handle, the text the two reports take as the results."""
    return trade_results(prepared, market, WorkCounter())


@excel_function
def _ReportValues(
    results: Annotated[
        Handle[TradeResults],
        "The results handle: the cell showing _EvaluateTrades's result, such as A12, or a name "
        "for it.",
    ],
) -> MixedArray:
    """Reports the batch's values from its results: the mark and the cash under the route's
    labels, the currency and the valuation day, as evaluation stored them."""
    route = results.route.value
    return MixedArray.table(
        [
            (f"{route}_mark", f"{route}_cash", "currency", "as_of"),
            ("float64", "float64", "str", "datetime64[D]"),
        ],
        np.array([results.mark]),
        np.array([results.cash]),
        (results.currency,),
        np.array([results.as_of], dtype="datetime64[D]"),
    )


@excel_function
def _ReportRisk(
    results: Annotated[
        Handle[TradeResults],
        "The results handle: the cell showing _EvaluateTrades's result, such as A12, or a name "
        "for it.",
    ],
) -> MixedArray:
    """Reports the batch's risk from its results: the total delta, the change in mark for a move
    of one quote unit in every contract, with its unit, the DV01 and the valuation day, as
    evaluation stored them, and the DV01's unit, the currency per basis point."""
    return MixedArray.table(
        [
            ("delta_total", "delta_unit", "dv01", "dv01_unit", "as_of"),
            ("float64", "str", "float64", "str", "datetime64[D]"),
        ],
        np.array([results.delta_total]),
        (results.delta_unit,),
        np.array([results.dv01]),
        (f"{results.currency} per basis point",),
        np.array([results.as_of], dtype="datetime64[D]"),
    )
