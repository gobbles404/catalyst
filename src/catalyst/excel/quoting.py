"""The worksheet functions of quoting: the quote template, the static terms of a quote under the
fixed_float's definition, created once and taken by every quote made under it; the quote, one
whole-period indicative fixed price for a contract or strip on one market, with a collection of
named discount curves when the template's route is bilateral; since dated-quotes.md the quote by
dates, the same price for the days between two dates, one average over the window under a
onetime template; and since rfq-quoting.md the request for quote, a saved quantity and payment
schedule on one index under a template's terms, and its price on a market by the quote's
calculation. docs/library/quoting/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

from goosedove.excel.bridge import (
    Date,
    FieldRow,
    FieldRows,
    Handle,
    TextRow,
    excel_function,
)
from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.index_definitions.index import Index
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market import Market
from goosedove.quoting.quote import quote, quote_by_dates
from goosedove.quoting.rfq import Rfq, quote_rfq, rfq
from goosedove.quoting.template import QuoteTemplate, quote_template

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_CreateQuoteTemplate", "_CreateRFQ", "_Quote", "_QuoteByDates", "_QuoteRFQ"]


@excel_function
def _CreateQuoteTemplate(
    instrument: Annotated[
        str, "One instrument name from _ListInstruments; fixed_float, the one a quote prices."
    ],
    fields: Annotated[
        TextRow,
        "The field-name cells in one row, such as A1:G1, using names _ShowInstrument marks "
        "quote_allowed.",
    ],
    values: Annotated[FieldRow[str], "The values in one row beneath those fields, such as A2:G2."],
) -> Handle[QuoteTemplate]:
    """Creates the static terms of a quote under an instrument and shows their handle, the text
    _Quote takes as the quote template."""
    return quote_template(values)


@excel_function
def _Quote(
    market: Annotated[
        Handle[Market],
        "The market handle: the cell showing _CreateMarket's result, such as I12, or a name for "
        "it, with the day's quotes over the history they follow.",
    ],
    contract_code: Annotated[
        str,
        "The contract, strip or balance to quote, such as Z26, F27-G27, CAL27 or BALZ26, the "
        "balance from the market's valuation day, every month of it a contract of the market's "
        "schedule.",
    ],
    template: Annotated[
        Handle[QuoteTemplate],
        "The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as B3, "
        "or a name for it, which supplies the quote's terms.",
    ],
    discount_curve_set: Annotated[
        Handle[DiscountCurveSet] | None,
        "The collection handle for a bilateral quote: the cell showing _CollectDiscountCurves's "
        "result, such as I13, or a name for it, holding the curve the template names; left out "
        "for a cleared quote.",
    ] = None,
) -> float:
    """Quotes one whole-period fixed price for a contract or strip on one market from a quote
    template's terms, fixings for the observations that have passed and the day's quotes for the
    rest, a bilateral payment discounted on the template's curve."""
    return quote(market, contract_code, template, discount_curve_set, WorkCounter())


@excel_function
def _QuoteByDates(
    market: Annotated[
        Handle[Market],
        "The market handle: the cell showing _CreateMarket's result, such as I12, or a name for "
        "it, with the day's quotes over the history they follow.",
    ],
    start_date: Annotated[Date, "The first day the quote covers, such as A2 or DATE(2026,5,26)."],
    end_date: Annotated[
        Date,
        "The last day it covers, inclusive, such as B2 or DATE(2026,6,25), on or after start_date.",
    ],
    template: Annotated[
        Handle[QuoteTemplate],
        "The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as B3, "
        "or a name for it, whose settlement_frequency makes the days one average or a strip by "
        "the month.",
    ],
    discount_curve_set: Annotated[
        Handle[DiscountCurveSet] | None,
        "The collection handle for a bilateral quote: the cell showing _CollectDiscountCurves's "
        "result, such as I13, or a name for it, holding the curve the template names; left out "
        "for a cleared quote.",
    ] = None,
) -> float:
    """Quotes one fixed price from start_date to end_date on one market from a quote template's
    terms, one average over the window under onetime and a strip by the month under monthly,
    fixings for the days passed and the day's quotes for the rest."""
    return quote_by_dates(market, start_date, end_date, template, discount_curve_set, WorkCounter())


@excel_function
def _CreateRFQ(
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as I3, or a name for it, "
        "the one index every row of the request is on.",
    ],
    fields: Annotated[
        TextRow,
        "The request's header cells in one row, such as A1:D1, from contract_code, start_date, "
        "end_date, quantity and payment_day, in any order.",
    ],
    rows: Annotated[
        FieldRows[QuoteTemplate],
        "The rows under the headers, such as A2:D4, each a contract month or two dates with its "
        "quantity, and a payment date where that column is given.",
    ],
    template: Annotated[
        Handle[QuoteTemplate],
        "The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as B3, "
        "or a name for it, which supplies the request's terms and its frequency.",
    ],
) -> Handle[Rfq]:
    """Creates a request for quote on one index from a ticket's rows under a quote template's
    terms, a month or two dates and a quantity per row, paying on the template's days or the
    dates given, and shows its handle, the text _QuoteRFQ takes as the request."""
    return rfq(index, rows, template, WorkCounter())


@excel_function
def _QuoteRFQ(
    market: Annotated[
        Handle[Market],
        "The market handle over the request's index: the cell showing _CreateMarket's result, "
        "such as I12, or a name for it, with the day's quotes over the history they follow.",
    ],
    rfq: Annotated[
        Handle[Rfq],
        "The request handle: the cell showing _CreateRFQ's result, such as B5, or a name for it.",
    ],
    discount_curve_set: Annotated[
        Handle[DiscountCurveSet] | None,
        "The collection handle for a bilateral request: the cell showing _CollectDiscountCurves's "
        "result, such as I13, or a name for it, holding the curve the template names; left out "
        "for a cleared request.",
    ] = None,
) -> float:
    """Quotes one fixed price for a saved request on one market, each month at its quantity,
    fixings for the observations that have passed and the day's quotes for the rest, a bilateral
    payment discounted on the template's curve on each month's own day."""
    return quote_rfq(market, rfq, discount_curve_set, WorkCounter())
