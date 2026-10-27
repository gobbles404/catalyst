"""The run of the first slice, import-cleared-futures.md: the status line's words over the
issue's table, the Table holding the ID the walk stopped at, the cap on the IDs the line names,
the two columns the host hands over coming together, the whole-ID refusal naming the Table and
the ID's place in it, and the seam's entry `_ImportTradeIds` reached by name, registered for the
host alone and checked as every function is, its refusals in the form a cell shows."""

import re
from collections.abc import Iterator

import numpy as np
import pytest
from import_standin import StandIn, serve

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells
from goosedove.importer.run import import_ids, status_line
from goosedove.importer.walk import Walk
from goosedove.instrumentation.work_counts import WorkCounter


@pytest.fixture(scope="module")
def standin() -> Iterator[StandIn]:
    server = serve()
    yield server
    server.shutdown()
    server.server_close()


def address(standin: StandIn) -> str:
    return f"http://127.0.0.1:{standin.server_address[1]}/gettradeids"


def ran(
    standin: StandIn, ids: list[float] | None, tables: list[str] | None, filter: str = "three"
) -> str:
    held = None if ids is None else np.asarray(ids, dtype=np.float64)
    names = None if tables is None else tuple(tables)
    return import_ids(address(standin), filter, held, names, WorkCounter())


def test_the_lines_words() -> None:
    assert (
        status_line(7, Walk((107, 106, 105), 104), "Trades_NYMEX_CME")
        == "7 IDs returned, 3 to fetch: 107, 106, 105; stopped at 104, held by Trades_NYMEX_CME"
    )
    assert status_line(7, Walk((), 107), "Trades_NYMEX_CME") == (
        "7 IDs returned, none new; stopped at 107, held by Trades_NYMEX_CME"
    )
    assert status_line(3, Walk((105, 104, 103), None), None) == (
        "3 IDs returned, 3 to fetch: 105, 104, 103; none held"
    )
    assert status_line(0, Walk((), None), None) == "0 IDs returned, none new; none held"
    assert status_line(1, Walk((5,), None), None) == "1 ID returned, 1 to fetch: 5; none held"
    # Twenty named and the rest counted, so a long first run never writes a cell's worth of IDs.
    many = tuple(range(30, 0, -1))
    assert status_line(30, Walk(many, None), None) == (
        "30 IDs returned, 30 to fetch: 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, "
        "16, 15, 14, 13, 12, 11 and 10 more; none held"
    )
    assert status_line(21, Walk(tuple(range(21, 0, -1)), None), None).endswith(
        ", 3, 2 and 1 more; none held"
    )
    assert status_line(20, Walk(tuple(range(20, 0, -1)), None), None).endswith(", 2, 1; none held")


def test_the_issues_table_through_the_run(standin: StandIn) -> None:
    # 105, 104 and 103 returned in no particular order with 104 in the workbook's one Table.
    assert ran(standin, [104, 90], ["Trades_NYMEX", "Trades_NYMEX"]) == (
        "3 IDs returned, 1 to fetch: 105; stopped at 104, held by Trades_NYMEX"
    )
    assert ran(standin, [50, 90], ["Trades_NYMEX", "Trades_NYMEX"]) == (
        "3 IDs returned, 3 to fetch: 105, 104, 103; none held"
    )
    assert ran(standin, None, None) == "3 IDs returned, 3 to fetch: 105, 104, 103; none held"
    # The newest held in the second Table: the walk stops at once and names that Table.
    assert ran(standin, [104, 90, 105], ["Trades_NYMEX", "Trades_NYMEX", "Trades_NG"]) == (
        "3 IDs returned, none new; stopped at 105, held by Trades_NG"
    )
    # An ID two Tables hold is held by the first in the destinations' order.
    assert ran(standin, [104, 104], ["Trades_NG", "Trades_NYMEX"]) == (
        "3 IDs returned, 1 to fetch: 105; stopped at 104, held by Trades_NG"
    )
    assert ran(standin, None, None, "none") == "0 IDs returned, none new; none held"
    assert ran(standin, None, None, "many").startswith(
        "30 IDs returned, 30 to fetch: 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, "
        "16, 15, 14, 13, 12, 11 and 10 more; none held"
    )


def test_the_run_reports_its_work(standin: StandIn) -> None:
    counter = WorkCounter()
    import_ids(address(standin), "three", np.asarray([104.0, 90.0]), ("A", "A"), counter)
    assert counter.freeze().as_dict() == {
        "requests_made": 1,
        "bytes_received": 29,
        "ids_returned": 3,
        "ids_to_fetch": 1,
    }


def test_the_two_columns_come_together_one_table_per_id(standin: StandIn) -> None:
    with pytest.raises(
        ValueError, match=r"^trade_ids is given without tables, expected both, one table per ID$"
    ):
        ran(standin, [104], None)
    with pytest.raises(
        ValueError, match=r"^tables is given without trade_ids, expected both, one table per ID$"
    ):
        ran(standin, None, ["Trades_NYMEX"])
    with pytest.raises(ValueError, match=r"^tables has 1 names, expected one per trade ID, 2$"):
        ran(standin, [104, 90], ["Trades_NYMEX"])


def test_an_id_that_is_no_whole_number_is_refused_by_its_table_and_its_place(
    standin: StandIn,
) -> None:
    # Before any request: nothing is asked of the API for a workbook the run cannot read.
    before = len(standin.requests)
    for ids, tables, message in (
        (
            [104, 90.5],
            ["A", "A"],
            "A trade_id 2 is 90.5, expected a whole number of at most 15 digits",
        ),
        (
            [1, 2, 3.5],
            ["A", "B", "B"],
            "B trade_id 2 is 3.5, expected a whole number of at most 15 digits",
        ),
        (
            [1e16],
            ["A"],
            "A trade_id 1 is 10000000000000000, expected a whole number of at most 15 digits",
        ),
        (
            [1, 2, 3, 4.5],
            ["A", "B", "A", "A"],
            "A trade_id 2 is 4.5, expected a whole number of at most 15 digits",
        ),
    ):
        with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
            ran(standin, ids, tables)
    assert len(standin.requests) == before


# --- the seam's entry ---------------------------------------------------------------------


def column(*cells: object) -> Cells:
    return Cells.from_rows([[cell] for cell in cells])


def test_the_entry_is_prepared_for_the_host_and_never_told_to_excel() -> None:
    assert "_ImportTradeIds" not in {name for name, *_ in bridge.function_specs()}
    assert callable(bridge.entry("_ImportTradeIds"))


def test_the_entry_runs_the_line_and_refuses_in_the_cells_form(standin: StandIn) -> None:
    endpoint = address(standin)
    assert (
        bridge.call(
            "_ImportTradeIds",
            [endpoint, "three", column(104.0, 90.0), column("Trades_NYMEX", "Trades_NYMEX")],
        )
        == "3 IDs returned, 1 to fetch: 105; stopped at 104, held by Trades_NYMEX"
    )
    assert bridge.call("_ImportTradeIds", [endpoint, "three", MISSING, MISSING]) == (
        "3 IDs returned, 3 to fetch: 105, 104, 103; none held"
    )
    # The seam's own refusals, each argument alone, before anything is asked of the API.
    before = len(standin.requests)
    assert bridge.call("_ImportTradeIds", [None, "three", MISSING, MISSING]) == (
        "#ERROR _ImportTradeIds: endpoint is blank, expected text"
    )
    assert bridge.call("_ImportTradeIds", [5.0, "three", MISSING, MISSING]) == (
        "#ERROR _ImportTradeIds: endpoint is number 5.0, expected text"
    )
    assert bridge.call("_ImportTradeIds", [endpoint, "", MISSING, MISSING]) == (
        "#ERROR _ImportTradeIds: filter is empty text, expected text"
    )
    assert bridge.call(
        "_ImportTradeIds", [endpoint, "three", column(104.0, None), column("A", "A")]
    ) == ("#ERROR _ImportTradeIds: trade_ids cell (2, 1) is blank, expected number")
    assert (
        bridge.call(
            "_ImportTradeIds",
            [endpoint, "three", Cells.from_rows([[104.0, 90.0]]), column("A", "A")],
        )
        == "#ERROR _ImportTradeIds: trade_ids is 1x2 array, expected column of numbers"
    )
    assert bridge.call("_ImportTradeIds", [endpoint, "three", column(104.0), column(7.0)]) == (
        "#ERROR _ImportTradeIds: tables cell (1, 1) is number 7.0, expected text"
    )
    assert len(standin.requests) == before
    # The library's and the reader's refusals carry their type, as a cell shows them.
    assert bridge.call("_ImportTradeIds", [address(standin), "repeat", MISSING, MISSING]) == (
        "#ERROR _ImportTradeIds: ValueError: the filter returned 104 more than once, expected each "
        "trade ID once"
    )
    assert bridge.call("_ImportTradeIds", [endpoint, "three", column(90.5), column("A")]) == (
        "#ERROR _ImportTradeIds: ValueError: A trade_id 1 is 90.5, expected a whole number of at "
        "most 15 digits"
    )
