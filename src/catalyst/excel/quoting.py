"""The worksheet functions of quoting: the quote template, the static terms of a quote under the
fixed_float's definition, created once and taken by every quote made under it; the quote, one
whole-period indicative fixed price for a contract or strip on one market, with a collection of
named discount curves when the template's route is bilateral; since dated-quotes.md the quote by
dates, the same price for the days between two dates, one average over the window under a
onetime template; and since rfq-quoting.md the request for quote, a saved quantity and payment
schedule on one index under a template's terms, and its price on a market by the quote's
calculation; since fit-to-curve-price.md each of the three quotes takes the pricing, flat or
ftc, the one fixed price or the fit-to-curve one; and since ftc-monthly-prices.md the
fit-to-curve prices of a request, the fixed price of each of its months from one agreed
price. docs/library/quoting/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

import numpy as np

from catalyst.excel.bridge import (
    NUMBER_CODE,
    TEXT_CODE,
    Date,
    FieldRow,
    FieldRows,
    Handle,
    MixedArray,
    TextRow,
    excel_function,
)
from catalyst.globals.discount_curve_set import DiscountCurveSet
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.payment_calendars import PaymentCalendars
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market import Market
from catalyst.quoting.ftc_prices import FtcPrices, ftc_prices
from catalyst.quoting.quote import quote, quote_by_dates
from catalyst.quoting.rfq import Rfq, quote_rfq, rfq
from catalyst.quoting.template import QuoteTemplate, quote_template

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = [
    "_CreateQuoteTemplate",
    "_CreateRFQ",
    "_Quote",
    "_QuoteByDates",
    "_QuoteFTCPrices",
    "_QuoteRFQ",
]


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
    payment_calendars: Annotated[
        Handle[PaymentCalendars] | None,
        "The collection payment_calendar_key selects from: the cell showing "
        "_CollectPaymentCalendars's result, such as B4. Leave it out where the row holds no "
        "payment_calendar_key.",
    ] = None,
) -> Handle[QuoteTemplate]:
    """Creates the static terms of a quote under an instrument and shows their handle, the text
    _Quote takes as the quote template."""
    return quote_template(values, payment_calendars, WorkCounter())


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
    pricing: Annotated[
        str,
        "The price to quote, flat or ftc: flat is one fixed price for the whole period, each "
        "month weighed by its quantity and its payment's discount factor; ftc, fit to curve, is "
        "the months' own prices averaged by quantity alone.",
    ],
    discount_curve_set: Annotated[
        Handle[DiscountCurveSet] | None,
        "The collection handle for a bilateral quote, under either pricing: the cell showing "
        "_CollectDiscountCurves's result, such as I13, or a name for it, holding the curve the "
        "template names; left out for a cleared quote.",
    ] = None,
) -> float:
    """Quotes one fixed price, flat or fit to curve, for a contract or strip on a market from a
    quote template's terms, fixings for the observations that have passed and the day's quotes
    for the rest, a flat bilateral price discounted on the template's curve."""
    return quote(market, contract_code, template, pricing, discount_curve_set, WorkCounter())


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
    pricing: Annotated[
        str,
        "The price to quote, flat or ftc: flat is one fixed price for the days, each component "
        "weighed by its quantity and its payment's discount factor; ftc, fit to curve, is the "
        "components' own prices averaged by quantity alone.",
    ],
    discount_curve_set: Annotated[
        Handle[DiscountCurveSet] | None,
        "The collection handle for a bilateral quote, under either pricing: the cell showing "
        "_CollectDiscountCurves's result, such as I13, or a name for it, holding the curve the "
        "template names; left out for a cleared quote.",
    ] = None,
) -> float:
    """Quotes one fixed price, flat or fit to curve, from start_date to end_date on a market
    under a quote template, one average over the window under onetime and a strip by the month
    under monthly, fixings for days passed and the day's quotes for the rest."""
    return quote_by_dates(
        market, start_date, end_date, template, pricing, discount_curve_set, WorkCounter()
    )


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
    pricing: Annotated[
        str,
        "The price to quote, flat or ftc: flat is one fixed price for the request, each component "
        "weighed by its quantity and its payment's discount factor; ftc, fit to curve, is the "
        "components' own prices averaged by quantity alone.",
    ],
    discount_curve_set: Annotated[
        Handle[DiscountCurveSet] | None,
        "The collection handle for a bilateral request, under either pricing: the cell showing "
        "_CollectDiscountCurves's result, such as I13, or a name for it, holding the curve the "
        "template names; left out for a cleared request.",
    ] = None,
) -> float:
    """Quotes one fixed price, flat or fit to curve, for a saved request on one market, each
    month at its quantity, fixings for the observations that have passed and the day's quotes
    for the rest, a flat bilateral price discounted on each month's own day."""
    return quote_rfq(market, rfq, pricing, discount_curve_set, WorkCounter())


@excel_function
def _QuoteFTCPrices(
    market: Annotated[
        Handle[Market],
        "The market handle over the request's index: the cell showing _CreateMarket's result, "
        "such as I12, or a name for it, with the day's quotes over the history they follow.",
    ],
    rfq: Annotated[
        Handle[Rfq],
        "The request handle: the cell showing _CreateRFQ's result, such as B5, or a name for it.",
    ],
    price: Annotated[
        float,
        "The one price agreed for the request, a fit-to-curve price, such as B7 or 3.95; every "
        "month's own price is moved by the same amount, this price less the request's "
        "fit-to-curve quote.",
    ],
    decimals: Annotated[
        int,
        "The decimals a fixed price may hold, a whole number from 0 to 15, such as 2; each "
        "fixed price is rounded alone, as ROUND rounds.",
    ],
) -> MixedArray:
    """Quotes the fixed price of each month of a saved request from one agreed fit-to-curve
    price, each month's own price moved by the same amount and rounded, and above them the
    agreed price, the average the fixed prices come back to and the difference."""
    return ftc_prices_table(ftc_prices(market, rfq, price, decimals, WorkCounter()))


def ftc_prices_table(prices: FtcPrices) -> MixedArray:
    """The fit-to-curve prices' rectangle, four cells wide: three rows of the check, a word and
    its number and a dash in the two cells beside them, `agreed_price`, `average_fixed_price`
    and `difference`, the average less the agreed, first so that they sit in the same cells
    whatever the request holds; a header row, `period`, `quantity`, `curve_price` and
    `fixed_price`; a type row, `str` and `float64` three times; then one row per component in
    the request's order. A column holds a word above numbers and a check row a word before a
    number, so the rectangle is written by kind, as the risk report's is: the kinds, the slots
    and the texts in sheet order. The numbers are placed as they are, the pricing having held
    them finite. Nothing is priced, summed or rounded here.

    Work: the rectangle filled once, a copy per column."""
    rows = 5 + len(prices.period)
    kinds = np.full((rows, 4), TEXT_CODE, dtype=np.uint8)
    kinds[:3, 1] = NUMBER_CODE
    kinds[5:, 1:] = NUMBER_CODE
    slots = np.full((rows, 4), np.nan)
    slots[:3, 1] = (prices.agreed, prices.average, prices.difference)
    slots[5:, 1] = prices.quantity
    slots[5:, 2] = prices.curve_price
    slots[5:, 3] = prices.fixed_price
    texts = (
        "agreed_price",
        "-",
        "-",
        "average_fixed_price",
        "-",
        "-",
        "difference",
        "-",
        "-",
        "period",
        "quantity",
        "curve_price",
        "fixed_price",
        "str",
        "float64",
        "float64",
        "float64",
        *prices.period,
    )
    return MixedArray(kinds, slots, texts)
