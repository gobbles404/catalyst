"""The seam's entry for the host's import command, import-cleared-futures.md: registered for the
host alone and never with Excel, so no formula reaches it and nothing fetches on a recalculation.
The host calls it from GoosedoveImportTrades, Ctrl+Shift+F, with what it read off the workbook's
Tables, the endpoint and the filter from import_settings and the trade IDs of every participating
Table beside the Table's name, and writes the text that comes back into the status cell, the
run's line or the seam's own refusal in the form a cell would show. docs/library/importer/
import-trades.md is the page.

The docstring is what Excel would show about the function, kept as every function's is although
no wizard lists this one.
"""

from goosedove.excel.bridge import NumberColumn, TextColumn, host_function
from goosedove.importer.run import import_ids
from goosedove.instrumentation.work_counts import WorkCounter

__all__ = ["_ImportTradeIds"]


@host_function
def _ImportTradeIds(
    endpoint: str,
    filter: str,
    trade_ids: NumberColumn | None = None,
    tables: TextColumn | None = None,
) -> str:
    """Asks the endpoint for the filter's trade IDs, walks them newest first against the IDs the
    workbook holds, and shows what the run would fetch and where it stopped; the host's command
    alone calls it."""
    return import_ids(endpoint, filter, trade_ids, tables, WorkCounter())
