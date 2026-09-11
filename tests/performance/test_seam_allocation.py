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
    assert peak_bytes(lambda: bridge.call("Add", [1.0, 2.0])) <= SLACK
    assert peak_bytes(lambda: bridge.call("Zero", [])) <= SLACK
    assert peak_bytes(lambda: bridge.call("Fail", [])) <= SLACK


# Today the kinds compare against an IntEnum makes numpy build an 8-byte-per-cell temporary
# before the 1-byte mask; that is the 8 below, and the plain-integer compare lowers it to 1.
def test_a_range_in_peaks_at_one_temporary_per_cell() -> None:
    column = Cells.from_rows([[float(i)] for i in range(N)])
    assert peak_bytes(lambda: bridge.call("SumArray", [column])) <= 8 * N + SLACK


def test_a_column_out_adds_no_copy_of_its_own() -> None:
    column = Cells.from_rows([[float(i)] for i in range(N)])
    assert peak_bytes(lambda: bridge.call("EchoColumn", [column])) <= 8 * N + SLACK


def test_a_block_out_peaks_at_the_block_and_its_finite_mask() -> None:
    assert peak_bytes(lambda: bridge.call("Grid", [N // 2, 2])) <= 9 * N + SLACK


def test_owning_a_range_peaks_at_the_two_copies_and_the_text_look() -> None:
    kinds = (ctypes.c_uint8 * N)(*([0] * N))
    numbers = (ctypes.c_double * N)(*[float(i) for i in range(N)])
    pointers = ctypes.addressof(kinds), ctypes.addressof(numbers)
    assert peak_bytes(lambda: bridge.cells_from_buffers(*pointers, N, 1, "")) <= 9 * N + SLACK
