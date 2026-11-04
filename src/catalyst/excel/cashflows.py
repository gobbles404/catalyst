"""The cashflow instrument's two worksheet functions, cashflow-instrument.md: a batch of
cashflows from a template and a ticket, and its valuation on a valuation day over a discount
curve; the readers and the reports take the results as they take a batch of trades'. The
docstrings and the words beside each parameter are what Excel shows, as
docs/library/conventions.md says under Excel help; docs/library/cashflows/ holds the pages."""

from typing import Annotated

from catalyst.cashflows.booking import Cashflows, cashflows
from catalyst.cashflows.valuation import CashflowResults, cashflow_results
from catalyst.excel.bridge import FieldRows, Handle, TextRow, excel_function
from catalyst.excel.trades import values_label
from catalyst.globals.discount_curve import DiscountCurve
from catalyst.globals.valuation_date import ValuationDate
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.trades.template import TradeTemplate

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = ["_CreateCashflows", "_EvaluateCashflows"]


@excel_function
def _CreateCashflows(
    fields: Annotated[
        TextRow,
        "The ticket's header cells in one row, such as A4:E4, using names shown by "
        "_ShowInstrument for cashflow and none the template supplies.",
    ],
    cashflow_rows: Annotated[
        FieldRows[TradeTemplate],
        "The rows under the headers, such as A5:E9, one payment per row, a repeated row a second "
        "payment.",
    ],
    template: Annotated[
        Handle[TradeTemplate],
        "The trade-template handle: the cell showing _CreateTradeTemplate's result for the "
        "cashflow instrument, such as B3, or a name for it, which supplies the shared fields.",
    ],
) -> Handle[Cashflows]:
    """Creates a batch of cashflows, known signed amounts in one currency each on its own payment
    date, from a template's shared fields and a ticket's rows, and shows its handle, the text
    _EvaluateCashflows takes as the cashflows."""
    return cashflows(cashflow_rows, template, WorkCounter())


@excel_function
def _EvaluateCashflows(
    cashflows: Annotated[
        Handle[Cashflows],
        "The cashflows handle: the cell showing _CreateCashflows's result, such as A10, or a "
        "name for it.",
    ],
    valuation_date: Annotated[
        Handle[ValuationDate],
        "The valuation-date handle: the cell showing _CreateValuationDate's result, such as B2, "
        "or a name for it; the day the unpaid payments are discounted to.",
    ],
    discount_curve: Annotated[
        Handle[DiscountCurve],
        "The discount-curve handle: the cell showing _CreateDiscountCurve's result, such as B5, "
        "or a name for it, starting on the valuation day and covering every unpaid payment day.",
    ],
) -> Handle[CashflowResults]:
    """Values a batch of cashflows on the valuation day: each unpaid payment discounted on the
    curve's factor for its day with its DV01, each paid one cash, and shows the results' handle,
    the text the reports and util_ReadHandle take."""
    return cashflow_results(cashflows, valuation_date, discount_curve, WorkCounter())


@values_label.register
def cashflow_values_label(results: CashflowResults) -> str:
    """The word the values report labels a batch of cashflows' mark and cash with: the
    instrument's, as a batch of trades' is its route's."""
    return "cashflow"
