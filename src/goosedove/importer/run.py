"""The run of the first slice, import-cleared-futures.md: the IDs the workbook holds, read off its
participating Tables by the host, made whole; the filter asked; the walk over its answer; and
the run's line in the status cell's words, what was returned, what would be fetched and where
the walk stopped. No detail is fetched and nothing is inserted: a first run against the real API
proves the shortcut, the configuration, the Tables and the walk before any row moves."""

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from goosedove.importer.fetch import fetch_ids
from goosedove.importer.walk import Walk, walk
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.terms import whole_trade_ids

IDS_LISTED: Final = 20  # the most IDs to fetch the line names before counting the rest


def import_ids(
    endpoint: str,
    filter: str,
    trade_ids: NDArray[np.float64] | None,
    tables: Sequence[str] | None,
    counter: WorkCounter,
) -> str:
    """The line the status cell shows for one run: the trade IDs the host read off the
    participating Tables, each beside the name of the Table it came from, made whole; the
    filter's answer fetched from the endpoint; the walk; then the words. The two columns come
    together or not at all, one name per ID, the Tables' IDs in the order the destinations name
    them, each Table's together, so a refusal of an ID names its Table and its place among that
    Table's IDs: `Trades_NYMEX trade_id 2 is 90.5, expected a whole number of at most 15 digits`.
    The ID the walk stopped at is held by the first Table, in that order, whose IDs hold it."""
    if (trade_ids is None) != (tables is None):
        given, left = ("trade_ids", "tables") if tables is None else ("tables", "trade_ids")
        raise ValueError(f"{given} is given without {left}, expected both, one table per ID")
    if trade_ids is None or tables is None:
        held = np.zeros(0, dtype=np.int64)
        names: Sequence[str] = ()
    else:
        if len(tables) != trade_ids.size:
            raise ValueError(
                f"tables has {len(tables)} names, expected one per trade ID, {trade_ids.size}"
            )
        names = tables
        held = whole_trade_ids(trade_ids, lambda k: _place(names, k))
    returned = fetch_ids(endpoint, filter, counter)
    result = walk(returned, held, counter)
    holder = None if result.stopped_at is None else names[int(np.argmax(held == result.stopped_at))]
    return status_line(len(returned), result, holder)


def _place(tables: Sequence[str], k: int) -> str:
    """Where an ID sits, for a refusal: its Table and its place among that Table's IDs, counted
    from 1, the Tables' IDs standing together in the order the host read them."""
    names = np.asarray(tables)
    starts = np.flatnonzero(np.concatenate(([True], names[1:] != names[:-1])))
    first = int(starts[int(np.searchsorted(starts, k, side="right")) - 1])
    return f"{tables[k]} trade_id {k - first + 1}"


def status_line(returned: int, result: Walk, holder: str | None) -> str:
    """The run's words: how many IDs the filter returned; the IDs to fetch newest first, the
    first twenty named and the rest counted, or none new; and the ID the walk stopped at with
    the Table holding it, or that none was held."""
    count = f"{returned} ID returned" if returned == 1 else f"{returned} IDs returned"
    if result.to_fetch:
        named = ", ".join(str(trade_id) for trade_id in result.to_fetch[:IDS_LISTED])
        rest = len(result.to_fetch) - IDS_LISTED
        more = f" and {rest} more" if rest > 0 else ""
        fetching = f"{len(result.to_fetch)} to fetch: {named}{more}"
    else:
        fetching = "none new"
    stop = (
        "none held"
        if result.stopped_at is None
        else f"stopped at {result.stopped_at}, held by {holder}"
    )
    return f"{count}, {fetching}; {stop}"
