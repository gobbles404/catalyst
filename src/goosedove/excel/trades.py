"""Worksheet creators for static trades. docs/library/trades/futures-trades.md is the page."""

from typing import Annotated

from goosedove.excel.bridge import (
    DateColumn,
    Handle,
    NumberColumn,
    Table,
    TextColumn,
    TextRow,
    excel_function,
)
from goosedove.index_definitions.index import Index
from goosedove.trades.futures_trades import FuturesTrades, futures_trades

__all__ = ["_CreateFuturesTrades"]


class FuturesTradesTable(Table):
    """One row per deal occurrence; the agreed price belongs to the trade."""

    trade_id: TextColumn
    trade_date: DateColumn
    contract_code: TextColumn
    signed_lots: NumberColumn
    trade_price: NumberColumn


@excel_function
def _CreateFuturesTrades(
    index: Annotated[
        Handle[Index],
        "The index handle from _CreateIndex, such as B3, shared by all trades in this table.",
    ],
    contract_specification: Annotated[
        str,
        "The specification name within that index, such as NYMEX NG, shared by all trades.",
    ],
    header_row: Annotated[
        TextRow,
        "The header cells, such as A7:E7, reading trade_id, trade_date, contract_code, "
        "signed_lots and trade_price in any order.",
    ],
    table: Annotated[
        FuturesTradesTable,
        "The rows under the headers, such as A8:E11, one deal per row with positive lots for "
        "buys and negative lots for sells.",
    ],
) -> Handle[FuturesTrades]:
    """Creates static futures trades from one or many rows of agreed deal terms and shows their
    handle, the text other formulas take as the trades."""
    return futures_trades(
        index,
        contract_specification,
        table.trade_id,
        table.trade_date,
        table.contract_code,
        table.signed_lots,
        table.trade_price,
    )
