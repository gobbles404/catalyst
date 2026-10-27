"""What the walk over a filter's IDs costs, import-cleared-futures.md: the IDs returned and the
IDs to fetch counted, the walk one function over arrays whatever the count, one sort, one look
for a repeat, one membership test and one search, no per-ID Python call, and the peak within a
few dozen bytes an ID; the reader of the filter's answer one function and its peak likewise; and
the run of the first slice, one request, the IDs made whole once, the walk and the line, counted
and itemized through the seam's entry against the stand-in of tools/import_standin.py in a
process of its own."""

import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pytest
from test_seam_allocation import SLACK, least_peak

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells
from goosedove.importer.run import import_ids
from goosedove.importer.walk import ids_from_json, walk
from goosedove.instrumentation.work_counts import WorkCounter

CallProfile = Callable[[Callable[[], object]], dict[str, int]]


def returned(n: int) -> list[int]:
    """n distinct IDs, 1 to n, in a shuffled order, as a filter might return them."""
    return [int(x) for x in np.random.default_rng(7).permutation(np.arange(1, n + 1))]


@pytest.mark.parametrize("n", [1, 10_000], ids=["one ID", "ten thousand"])
def test_the_walk_counts_the_ids_returned_and_the_ids_to_fetch(n: int) -> None:
    # The workbook holds the middle ID, so the newer half is fetched and the older half unseen;
    # with one ID returned and none held, the one is fetched.
    counter = WorkCounter()
    result = walk(returned(n), [n // 2] if n > 1 else [], counter)
    assert counter.freeze().as_dict() == {"ids_returned": n, "ids_to_fetch": n // 2 if n > 1 else 1}
    assert len(result.to_fetch) == (n // 2 if n > 1 else 1)


def test_the_walk_and_the_reader_run_one_function_each_whatever_the_count(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    one, many = returned(1), returned(10_000)
    once = {"walk": 1, "WorkCounter.__init__": 1, "WorkCounter.hit": 2}
    assert call_profile(lambda: walk(one, [], WorkCounter())) == once
    assert call_profile(lambda: walk(many, [5_000], WorkCounter())) == once
    text = '{"tradeIds": [' + ", ".join(str(x) for x in many) + "]}"
    assert call_profile(lambda: ids_from_json(text)) == {"ids_from_json": 1}
    # The numpy calls the walk makes: the IDs as an array, sorted, reversed as a view and copied
    # for the repeat check, the imported IDs as an array for the membership test, the stop
    # searched once where one is held, and the IDs to fetch handed over in one call.
    assert numpy_calls(lambda: walk(many, [5_000], WorkCounter())) == {
        "ndarray.any": 2,
        "ndarray.argmax": 1,
        "ndarray.copy": 1,
        "ndarray.ravel": 2,
        "ndarray.reshape": 1,
        "ndarray.sort": 1,
        "ndarray.tolist": 1,
        "numpy.array": 1,
        "numpy.asarray": 5,
        "numpy.asanyarray": 1,
        "numpy.zeros": 2,
        "ufunc.reduce": 4,
    }
    assert numpy_calls(lambda: walk(one, [], WorkCounter())) == {
        "ndarray.any": 2,
        "ndarray.copy": 1,
        "ndarray.ravel": 2,
        "ndarray.reshape": 1,
        "ndarray.sort": 1,
        "ndarray.tolist": 1,
        "numpy.asarray": 5,
        "numpy.asanyarray": 1,
        "numpy.zeros": 1,
        "ufunc.reduce": 2,
    }


@pytest.mark.parametrize("n", [1, 10_000], ids=["one ID", "ten thousand"])
def test_the_walk_and_the_reader_allocate_within_a_few_dozen_bytes_an_id(n: int) -> None:
    # Measured on 2026-10-26: the walk 1,299 bytes for one ID and 340,895 for ten thousand with
    # the middle one held, about 34 an ID, the sorted copy, the reversed copy, the membership
    # mask and the five thousand plain numbers handed on; the reader 1,246 and 523,140, about 52
    # an ID, the JSON parser's list and numbers.
    ids = returned(n)
    held = [n // 2] if n > 1 else []
    assert least_peak(lambda: walk(ids, held, WorkCounter())) <= 1_500 + 40 * n + SLACK
    text = '{"tradeIds": [' + ", ".join(str(x) for x in ids) + "]}"
    assert least_peak(lambda: ids_from_json(text)) <= 2_000 + 60 * n + SLACK


# --- the run of the first slice -----------------------------------------------------------


@pytest.fixture(scope="module")
def standin() -> Iterator[str]:
    """The stand-in's address, the server in a process of its own: with its threads in this
    process, running while the request waited, cProfile counted the waiting frames twice in
    about one profile of thirty, measured on 2026-10-27, and in another process never."""
    script = Path(__file__).resolve().parents[2] / "tools" / "import_standin.py"
    process = subprocess.Popen(
        [sys.executable, str(script)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    assert process.stdin is not None and process.stdout is not None
    port = int(process.stdout.readline())
    yield f"http://127.0.0.1:{port}/gettradeids"
    process.stdin.close()  # the stand-in exits when its standard input closes
    process.wait(timeout=10)
    process.stdout.close()


def test_the_run_counts_the_request_the_bytes_and_the_walk(standin: str) -> None:
    endpoint = standin
    counter = WorkCounter()
    import_ids(
        endpoint, "three", np.asarray([104.0, 90.0]), ("Trades_NYMEX", "Trades_NYMEX"), counter
    )
    assert counter.freeze().as_dict() == {
        "requests_made": 1,
        "bytes_received": 29,
        "ids_returned": 3,
        "ids_to_fetch": 1,
    }


def test_the_run_is_one_request_one_whole_and_one_walk(
    standin: str, call_profile: CallProfile
) -> None:
    # The IDs made whole once, the request, the reader, the walk and the line, each once; the
    # line's generator over the IDs named, started and finished; no function per ID.
    endpoint = standin
    held = np.asarray([104.0, 90.0])
    names = ("Trades_NYMEX", "Trades_NYMEX")
    assert call_profile(lambda: import_ids(endpoint, "three", held, names, WorkCounter())) == {
        "import_ids": 1,
        "whole_trade_ids": 1,
        "fetch_ids": 1,
        "address": 1,
        "ids_from_json": 1,
        "walk": 1,
        "status_line": 1,
        "status_line.<locals>.<genexpr>": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 4,
    }
    # Through the seam's entry, as the host calls it: the four arguments checked, the two columns
    # by their shape and their cells, and the line sent as text.
    column = Cells.from_rows([[104.0], [90.0]])
    tables = Cells.from_rows([["Trades_NYMEX"], ["Trades_NYMEX"]])
    assert call_profile(
        lambda: bridge.call("_ImportTradeIds", [endpoint, "three", column, tables])
    ) == {
        "call": 1,
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,
        "_text": 2,
        "_column": 1,
        "_numbers": 1,
        "_one_column": 2,
        "_shape": 2,
        "_text_column": 1,
        "_texts": 1,
        "_ImportTradeIds": 1,
        "import_ids": 1,
        "whole_trade_ids": 1,
        "fetch_ids": 1,
        "address": 1,
        "ids_from_json": 1,
        "walk": 1,
        "status_line": 1,
        "status_line.<locals>.<genexpr>": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 4,
        "_text_out": 1,
        "_scalar": 1,
    }
    # With no Table holding an ID the host leaves both columns out: nothing made whole.
    assert call_profile(
        lambda: bridge.call("_ImportTradeIds", [endpoint, "three", MISSING, MISSING])
    ) == {
        "call": 1,
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,
        "_text": 2,
        "_ImportTradeIds": 1,
        "import_ids": 1,
        "fetch_ids": 1,
        "address": 1,
        "ids_from_json": 1,
        "walk": 1,
        "status_line": 1,
        "status_line.<locals>.<genexpr>": 4,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 4,
        "_text_out": 1,
        "_scalar": 1,
    }
