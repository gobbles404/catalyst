"""The worksheet functions of the trades: the template, shared field values under one instrument,
created once and taken last by the trades creator; the trades, a batch of one or many on one
index, resolved from a template and a ticket and encoded; the batch prepared against one market
history, as often as the history moves; the prepared batch evaluated against one market, as often
as the quotes move; since #180 one or many results collected into one record of saved risk,
handle to handle; and the reports of a result or a collection, its values, its risk by time
and, since #170, its reserves, each handle to handle. docs/library/trades/ holds a page per
function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from functools import singledispatch
from typing import Annotated

import numpy as np

from catalyst.cashflows.valuation import CashflowResults
from catalyst.excel.bridge import (
    NUMBER_CODE,
    TEXT_CODE,
    FieldRow,
    FieldRows,
    Handle,
    Handles,
    MixedArray,
    TextRow,
    excel_function,
)
from catalyst.globals.discount_curve_set import DiscountCurveSet
from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.payment_calendars import PaymentCalendars
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market import Market
from catalyst.market.market_history import MarketHistory
from catalyst.trades.aggregation import AggregateResults, aggregate_results
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import PreparedTrades, prepared_trades
from catalyst.trades.resolution import Trades, trades
from catalyst.trades.results import TradeResults
from catalyst.trades.risk_report import Bucket, Risk, RiskView
from catalyst.trades.template import TradeTemplate, choice, trade_template

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = [
    "_AggregateResults",
    "_CreateTradeTemplate",
    "_CreateTrades",
    "_EvaluateTrades",
    "_PrepareTrades",
    "_ReportReserves",
    "_ReportRisk",
    "_ReportValues",
]


@excel_function
def _CreateTradeTemplate(
    instrument: Annotated[str, "One instrument name from _ListInstruments, such as fixed_float."],
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
    indexes: Annotated[
        Handles[Index],
        "The index handle, or a row or column of two for a pair: the cells showing _CreateIndex's "
        "results, such as I3 or I3:I4, or names for them, the first leg's index first.",
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
    payment_calendars: Annotated[
        Handle[PaymentCalendars] | None,
        "The collection each row's payment_calendar_key selects from: the cell showing "
        "_CollectPaymentCalendars's result, such as I5. Leave it out for a physically settled "
        "batch.",
    ] = None,
) -> Handle[Trades]:
    """Creates a batch of trades on one index, or on a pair as two legs, from a
    template's shared fields and a ticket's rows, each contract code resolved against each
    index's schedule, and shows its handle, the text other formulas take as the trades."""
    return trades(indexes, trade_rows, template, UNITS, WorkCounter(), payment_calendars)


@excel_function
def _PrepareTrades(
    trades: Annotated[
        Handle[Trades],
        "The trades handle: the cell showing _CreateTrades's result, such as A10, or a name "
        "for it.",
    ],
    histories: Annotated[
        Handles[MarketHistory],
        "The market-history handle of the trades' index, or a row or column of one per index of a "
        "pair, such as I11 or I11:I12, each valued on the day the trades are prepared for.",
    ],
) -> Handle[PreparedTrades]:
    """Prepares a batch of trades against its market histories, one per index, each observation
    whose day has passed fixed at that day's settle and each payment fallen due settled, and
    shows its handle, the text _EvaluateTrades takes as the prepared trades."""
    return prepared_trades(trades.encoded, histories, WorkCounter())


@excel_function
def _EvaluateTrades(
    prepared: Annotated[
        Handle[PreparedTrades],
        "The prepared-trades handle: the cell showing _PrepareTrades's result, such as A11, or a "
        "name for it.",
    ],
    markets: Annotated[
        Handles[Market],
        "The market handle over the history the trades were prepared against, or a row or column "
        "of one per index of a pair, such as I12 or I12:I13, each with the day's quotes.",
    ],
    discount_curve_set: Annotated[
        Handle[DiscountCurveSet] | None,
        "The collection handle for a bilateral batch: the cell showing _CollectDiscountCurves's "
        "result, such as I13, or a name for it, holding every curve the rows name by "
        "discount_curve_key, each starting on the valuation day; left out for a cleared batch.",
    ] = None,
) -> Handle[TradeResults]:
    """Evaluates prepared trades against their markets, one per index, live observations at quotes
    and fixed at settles, each bilateral payment discounted on its curve, into mark, cash, delta
    and DV01, and shows the results' handle, which the reports take."""
    return trade_results(prepared, markets, WorkCounter(), discount_curve_set)


@excel_function
def _AggregateResults(
    result_handles: Annotated[
        Handles[TradeResults | CashflowResults],
        "The results handles to collect: a cell, a row or a column of cells showing "
        "_EvaluateTrades's or _EvaluateCashflows's results, in any mix, such as B2:B5, in the "
        "order given, a repeat counted again.",
    ],
) -> Handle[AggregateResults]:
    """Collects evaluated batches' saved risk, trades' and cashflows', into one collection, the
    lots by index, the DV01 by curve and currency unit and the cross-gamma by index and curve,
    nothing valued again, and shows its handle, which _ReportRisk takes."""
    return aggregate_results(result_handles, WorkCounter())


@singledispatch
def values_label(results: object) -> str:
    """The word _ReportValues labels a result's mark and cash with: a batch of trades' route,
    cleared or bilateral, here, and since #200 a batch of cashflows' instrument, cashflow,
    registered in the cashflows' own module; a kind nobody registered fails rather than
    guessing."""
    raise ValueError(f"{type(results).__name__} has no values report")


@values_label.register
def trade_values_label(results: TradeResults) -> str:
    return results.route.value


@excel_function
def _ReportValues(
    results: Annotated[
        Handle[TradeResults] | Handle[CashflowResults],
        "The results handle: the cell showing _EvaluateTrades's or _EvaluateCashflows's result, "
        "such as A12, or a name for it.",
    ],
) -> MixedArray:
    """Reports the batch's values from its results: the mark and the cash under the route's
    labels, or under cashflow for a batch of cashflows, the currency, the valuation day and the
    currency unit the two amounts are in, as evaluation stored them."""
    label = values_label(results)
    return MixedArray.table(
        [
            # currency_unit last, since currency-and-currency-unit.md, so that no column moves.
            (f"{label}_mark", f"{label}_cash", "currency", "as_of", "currency_unit"),
            ("float64", "float64", "str", "datetime64[D]", "str"),
        ],
        np.array([results.mark]),
        np.array([results.cash]),
        (results.currency,),
        np.array([results.as_of], dtype="datetime64[D]"),
        (results.currency_unit,),
    )


@excel_function
def _ReportRisk(
    results: Annotated[
        Handle[TradeResults] | Handle[AggregateResults] | Handle[CashflowResults],
        "The results handle, one evaluated batch's, a collection's or a batch of cashflows': the "
        "cell showing _EvaluateTrades's, _AggregateResults's or _EvaluateCashflows's result, "
        "such as A12, or a name for it.",
    ],
    risk: Annotated[
        str,
        "Which risk: nominal_delta, delta, dv01, cross_gamma or all, exactly so; the deltas and "
        "the cross_gamma in lots of the reporting specification by observation day or contract "
        "month or year, the DV01 in the currency unit per basis point by payment period.",
    ],
    bucket: Annotated[
        str,
        "What to sum by: day, month or year, exactly so; a month or a year is the pricing "
        "contract's for the deltas and the payment's for the DV01, labelled by its first day, "
        "and the Total is the saved number.",
    ],
) -> MixedArray:
    """Reports one risk of a batch or a collection, or all four, by day, month or year: the saved
    Total first, then a row per period, the deltas and the cross-gamma by observation day or
    contract period, the DV01 by payment period, as evaluation stored them."""
    view = results.report(
        choice("risk", risk, Risk, "nominal_delta, delta, dv01, cross_gamma or all"),
        choice("bucket", bucket, Bucket, "day, month or year"),
    )
    return _risk_table(results.as_of, view)


def _risk_table(as_of: np.datetime64, view: RiskView) -> MixedArray:
    """The risk report's rectangle, since #178: a context row, `as_of`, the valuation day and a
    dash in every other cell; a header row, `period` and the risk labels; a type row, `str |
    datetime64[D]` for the period column and `float64` for each risk; the Total row, the word and
    the saved scalars; then one row per date, the bucket start and the saved values. The period
    column holds a word above dates and the context row a word before a date, so the rectangle is
    written by kind, as the results readback's once-per-group columns are: the kinds, the slots
    and the texts in sheet order. The two date columns become serials through the table builder,
    the check a date result gets, and the numbers are placed as they are, the evaluation having
    checked them finite. Nothing is summed or converted here.

    Work: the rectangle filled once, a copy per column; one serial per date."""
    width = 1 + len(view.labels)
    rows = 4 + view.dates.size
    kinds = np.full((rows, width), NUMBER_CODE, dtype=np.uint8)
    kinds[:3] = TEXT_CODE
    kinds[0, 1] = NUMBER_CODE  # the valuation day
    kinds[3, 0] = TEXT_CODE  # the word Total
    slots = np.full((rows, width), np.nan)
    slots[0, 1] = MixedArray.table([], np.array([as_of], dtype="datetime64[D]")).numeric_slots[0, 0]
    slots[4:, 0] = MixedArray.table([], view.dates).numeric_slots[:, 0]
    slots[3, 1:] = view.totals
    for j, column in enumerate(view.columns):
        slots[4:, 1 + j] = column
    texts = (
        "as_of",
        *("-",) * (width - 2),
        "period",
        *view.labels,
        "str | datetime64[D]",
        *("float64",) * len(view.labels),
        "Total",
    )
    return MixedArray(kinds, slots, texts)


@excel_function
def _ReportReserves(
    results: Annotated[
        Handle[TradeResults],
        "The results handle: the cell showing _EvaluateTrades's result, such as A12, or a name "
        "for it.",
    ],
) -> MixedArray:
    """Reports the batch's booked reserves: brokerage on trades naming a broker and clearing on
    a cleared route, each trade's unsigned quantity times its specification's rate per lot,
    summed; marketing and the signed CVA, once a row; the currency and its unit."""
    reserves = results.reserves
    return MixedArray.table(
        [
            (
                "brokerage_reserve",
                "clearing_reserve",
                "marketing_reserve",
                "cva_reserve",
                "currency",
                "currency_unit",  # last, currency-and-currency-unit.md
            ),
            ("float64", "float64", "float64", "float64", "str", "str"),
        ],
        np.array([reserves.brokerage]),
        np.array([reserves.clearing]),
        np.array([reserves.marketing]),
        np.array([reserves.cva]),
        (reserves.currency,),
        (reserves.currency_unit,),
    )
