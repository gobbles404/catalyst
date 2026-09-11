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


# A rejected range still takes the look that names the bad cell: one 1-byte mask over the
# kinds, and a second one while the bad cell's text is found by counting the text cells before
# it. Measured 20,640 at ten thousand cells with the bad cell last, down from 87,239 when the
# compare against an IntEnum cast the kinds through numpy's 8-byte scratch buffer.
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
