"""The worksheet functions of quoting: the quote template, the static terms of a quote under the
fixed_float's definition, created once and taken by every quote made under it; and the quote, one
whole-period indicative fixed price for a contract or strip on one market, with a collection of
named discount curves when the template's route is bilateral. docs/library/quoting/ holds a page
per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

from goosedove.excel.bridge import FieldRow, Handle, TextRow, excel_function
from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market import Market
from goosedove.quoting.quote import quote
from goosedove.quoting.template import QuoteTemplate, quote_template

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_CreateQuoteTemplate", "_Quote"]


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
