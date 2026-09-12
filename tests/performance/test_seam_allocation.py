"""What one call through the seam allocates on the Python heap, at its peak.

tracemalloc sees Python objects and numpy's data buffers, which numpy registers with it.
It does not see the host's pinned buffers or anything in the CLR. Each ceiling is the
peak measured on 2026-09-11 plus slack, so a change that allocates a new full-size
temporary fails here and a change that removes one lowers the ceiling in its own PR.
"""

import ctypes
import tracemalloc
from collections.abc import Callable

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

# Each function's prepared path, fetched once as the host does at registration.
ENTRY = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}

N = 10_000
SLACK = 1024  # bytes of small objects a call may make on top of its per-cell temporaries


def peak_bytes(fn: Callable[[], object]) -> int:
    """The peak of the Python heap during one warm call, above where it stood before."""
    fn()
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        fn()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_a_scalar_call_allocates_only_small_objects() -> None:
    assert peak_bytes(lambda: ENTRY["Add"](1.0, 2.0)) <= SLACK
    assert peak_bytes(lambda: ENTRY["Zero"]()) <= SLACK
    assert peak_bytes(lambda: ENTRY["Fail"]()) <= SLACK


# A range of numbers is accepted on the host's summary alone: no look at the kinds, so no
# temporary per cell. Measured 192 bytes at ten thousand cells on 2026-09-11, down from 77,008
# when every range paid a look and its 8-byte-per-cell scratch.
def test_a_range_of_numbers_in_makes_no_temporary() -> None:
    column = Cells.from_rows([[float(i)] for i in range(N)])
    assert peak_bytes(lambda: ENTRY["SumArray"](column)) <= SLACK


# A column of text is accepted on the summary too, and the host's tuple of text cells is
# handed over as it is. Measured 192 bytes at ten thousand cells on 2026-09-11, down from
# 160,635 when the tuple went into an object array and came back out as a second tuple.
def test_a_column_of_text_in_makes_no_temporary() -> None:
    names = Cells.from_rows([[f"name{i}"] for i in range(N)])
    assert peak_bytes(lambda: ENTRY["FirstOfNames"](names)) <= SLACK


# A rejected range still takes the look that names the bad cell: one 1-byte mask over the
# kinds, and a second one while the bad cell's text is found by counting the text cells before
# it. Measured 20,640 at ten thousand cells with the bad cell last, down from 87,239 when the
# compare against an IntEnum cast the kinds through numpy's 8-byte scratch buffer.
# A mixed range is accepted on the host's summary too, and the record holds the storage the
# range already had, so nothing is made per cell. Measured 248 bytes at ten thousand cells on
# 2026-09-12: the record, its shape, and the small objects any call makes.
def test_a_mixed_range_in_makes_no_temporary() -> None:
    cells = Cells.from_rows([[f"n{i}", 46164.0 + i, float(i), i % 2 == 0] for i in range(N // 4)])
    assert peak_bytes(lambda: ENTRY["CountMixed"](cells)) <= SLACK


# A scalar becomes a one-cell range, which is the only mixed input that allocates storage of
# its own: two one-element arrays. Measured 473 bytes on 2026-09-12.
def test_a_scalar_promoted_to_a_mixed_range_stays_small() -> None:
    assert peak_bytes(lambda: ENTRY["CountMixed"](5.0)) <= SLACK


# Naming the bad cell is the rejection path's work. A blank is one mask over the kinds, measured
# 13,008 at ten thousand cells. An empty text costs more, because its place among the texts has
# to be turned into its place among the cells: measured 103,372, about 10 bytes per cell.
def test_a_rejected_mixed_range_pays_to_locate_the_cell_it_names() -> None:
    rows: list[list[object]] = [[float(i)] for i in range(N)]
    rows[N // 2][0] = None
    blank = Cells.from_rows(rows)
    assert peak_bytes(lambda: ENTRY["CountMixed"](blank)) <= 2 * N + SLACK
    texts: list[list[object]] = [[f"n{i}"] for i in range(N)]
    texts[N // 2][0] = ""
    empty = Cells.from_rows(texts)
    assert peak_bytes(lambda: ENTRY["CountMixed"](empty)) <= 11 * N + SLACK


def test_a_rejected_range_pays_one_look_and_its_two_masks() -> None:
    rows: list[list[object]] = [[float(i)] for i in range(N)]
    rows[-1][0] = "x"
    column = Cells.from_rows(rows)
    assert peak_bytes(lambda: ENTRY["SumArray"](column)) <= 2 * N + SLACK


# The way out still looks once, for finite numbers: one byte per cell. Measured 10,385.
def test_a_column_out_adds_only_its_finite_mask() -> None:
    column = Cells.from_rows([[float(i)] for i in range(N)])
    assert peak_bytes(lambda: ENTRY["EchoColumn"](column)) <= N + SLACK


def test_an_array_out_peaks_at_the_array_and_its_finite_mask() -> None:
    assert peak_bytes(lambda: ENTRY["Grid"](N // 2, 2)) <= 9 * N + SLACK


def test_owning_a_range_peaks_at_the_two_copies() -> None:
    kinds = (ctypes.c_uint8 * N)(*([0] * N))
    numbers = (ctypes.c_double * N)(*[float(i) for i in range(N)])
    pointers = ctypes.addressof(kinds), ctypes.addressof(numbers)
    assert peak_bytes(lambda: bridge.cells_from_buffers(*pointers, N, 1, "", 1)) <= 9 * N + SLACK
