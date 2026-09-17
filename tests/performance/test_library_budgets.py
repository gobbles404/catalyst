"""What the library's own code costs, called directly: the code with no worksheet surface, whose
work no seam ledger sees. A ledger is exact and a ceiling is the peak measured plus slack, as in
the two seam files beside this one."""

from collections.abc import Callable

import numpy as np
from test_seam_allocation import SLACK, peak_bytes

from goosedove.globals.unit_conversions import UNITS

N = 10_000

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
NumpyCalls = Callable[[Callable[[], object]], dict[str, int]]


# A conversion forms its factor once, three lookups in the collection, and multiplies the array
# once; the definitions are not checked again, so no builder appears. The multiplication is a
# ufunc by operator, which cProfile does not see, so the numpy ledger is empty.
def test_a_conversion_looks_its_factor_up_once_and_checks_no_definition(
    call_profile: CallProfile, numpy_calls: NumpyCalls
) -> None:
    quantities = np.full(N, 2.0)

    def convert() -> object:
        return UNITS.convert(quantities, "volume", "BBL", "GAL")

    assert call_profile(convert) == {
        "UnitConversions.convert": 1,
        "UnitConversions.factor": 1,
        "UnitConversions.category": 1,
        "Category.size_of": 2,
    }
    assert numpy_calls(convert) == {}


# The result, 8 bytes per quantity, and nothing else: no copy of the quantities and no temporary
# for the factor. Measured 80,200 bytes at ten thousand quantities on 2026-09-17.
def test_a_conversion_allocates_its_result_and_nothing_else() -> None:
    quantities = np.full(N, 2.0)
    assert peak_bytes(lambda: UNITS.convert(quantities, "volume", "BBL", "GAL")) <= 8 * N + SLACK
