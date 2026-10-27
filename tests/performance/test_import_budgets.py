"""What the walk over a filter's IDs costs, import-cleared-futures.md: the IDs returned and the
IDs to fetch counted, the walk one function over arrays whatever the count, one sort, one look
for a repeat, one membership test and one search, no per-ID Python call, and the peak within a
few dozen bytes an ID; the reader of the filter's answer one function and its peak likewise."""

from collections.abc import Callable

import numpy as np
import pytest
from test_seam_allocation import SLACK, least_peak

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
    text = "[" + ", ".join(str(x) for x in many) + "]"
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
    text = "[" + ", ".join(str(x) for x in ids) + "]"
    assert least_peak(lambda: ids_from_json(text)) <= 2_000 + 60 * n + SLACK
