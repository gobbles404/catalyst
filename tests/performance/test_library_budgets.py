"""What the library's own code costs, called directly: the code with no worksheet surface, whose
work no seam ledger sees. A ledger is exact and a ceiling is the peak measured plus slack, pinned
on the least of three warm calls, as in the two seam files beside this one."""

from collections.abc import Callable

import numpy as np
from test_seam_allocation import SLACK, least_peak

from catalyst.globals.unit_conversions import UNITS

N = 10_000

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
NumpyCalls = Callable[[Callable[[], object]], dict[str, int]]


# A conversion forms its factor once, three probes of the collection's mappings, the category by
# name and the two sizes by unit code, each retrieved once and reused, and multiplies the array
# once; the definitions are not checked again, so no builder appears, and no per-unit lookup
# method runs. The multiplication is a ufunc by operator, which cProfile does not see, so the
# numpy ledger is empty. Review of #71 counted five probes when the two sizes were checked for
# and then looked up again.
def test_a_conversion_looks_its_factor_up_once_and_checks_no_definition(
    call_profile: CallProfile, numpy_calls: NumpyCalls
) -> None:
    quantities = np.full(N, 2.0)

    def convert() -> object:
        return UNITS.convert(quantities, "VOLUME", "BBL", "GAL")

    assert call_profile(convert) == {
        "UnitConversions.convert": 1,
        "UnitConversions.factor": 1,
        "UnitConversions.category": 1,
    }
    assert numpy_calls(convert) == {}


# The result, 8 bytes per quantity, and nothing else: no copy of the quantities and no temporary
# for the factor. Measured 80,200 bytes at ten thousand quantities on 2026-09-17.
def test_a_conversion_allocates_its_result_and_nothing_else() -> None:
    quantities = np.full(N, 2.0)
    assert least_peak(lambda: UNITS.convert(quantities, "VOLUME", "BBL", "GAL")) <= 8 * N + SLACK
