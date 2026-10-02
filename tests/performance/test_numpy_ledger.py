"""The numpy ledger itself, on real profiles: what it sees, under which name, and what it cannot."""

import math
from collections.abc import Callable

import numpy as np
import pytest

NumpyCalls = Callable[[Callable[[], object]], dict[str, int]]

VALUES = np.arange(10.0)
MASK = VALUES > 4
BUFFER = b"\0" * 16
DAYS = np.array(["2026-05-19", "2026-05-20", "2026-05-22"], dtype="datetime64[D]")
AT = np.array([0.5, 1.5])
ANCHORS = np.array([0.0, 1.0, 2.0])
FACTORS = np.array([1.0, 0.9, 0.8])


def repeated(times: int, call: Callable[[], object]) -> Callable[[], object]:
    """The call made that many times inside one profile."""

    def run() -> None:
        for _ in range(times):
            call()

    return run


# numpy reports a C function behind a Python wrapper under the module that holds it,
# "<built-in method numpy._core._multiarray_umath.count_nonzero>". The ledger reads it by its
# leaf, the name the caller wrote, and counts every call; read as "numpy.NAME" alone, both
# functions below were dropped, and a call added to either could not fail a pin.
@pytest.mark.parametrize("times", [1, 2])
def test_count_nonzero_is_counted_under_its_leaf_name(times: int, numpy_calls: NumpyCalls) -> None:
    assert numpy_calls(repeated(times, lambda: np.count_nonzero(MASK))) == {
        "numpy.count_nonzero": times
    }


# The wrapper's own conversion sits beside it and is numpy's to change; the call is what is pinned.
@pytest.mark.parametrize("times", [1, 2])
def test_interp_is_counted_under_its_leaf_name(times: int, numpy_calls: NumpyCalls) -> None:
    calls = numpy_calls(repeated(times, lambda: np.interp(AT, ANCHORS, FACTORS)))
    assert calls["numpy.interp"] == times


@pytest.mark.parametrize("times", [1, 2])
def test_a_function_reported_under_numpy_itself_keeps_its_label_and_count(
    times: int, numpy_calls: NumpyCalls
) -> None:
    assert numpy_calls(repeated(times, lambda: np.frombuffer(BUFFER, dtype=np.float64))) == {
        "numpy.frombuffer": times
    }


def test_a_call_outside_numpy_is_no_entry(numpy_calls: NumpyCalls) -> None:
    assert numpy_calls(lambda: (len(VALUES), sorted([3, 1, 2]), math.fsum([1.0, 2.0]))) == {}


# What the ledger cannot see, pinned so the page that says so stays measured: cProfile raises an
# event when a C function is called as one and when a method of a numpy object is called, an
# array's or a ufunc's, and not otherwise. A ufunc called raises none, by operator or by name,
# and neither does a function numpy dispatches in C straight to its C implementation. A ledger
# is a floor on what numpy did, never the whole of it.
@pytest.mark.parametrize(
    "unseen",
    [
        lambda: VALUES + VALUES,
        lambda: np.isfinite(VALUES),
        lambda: np.concatenate((VALUES, VALUES)),
        lambda: np.is_busday(DAYS),
        lambda: np.busday_offset(DAYS, 1, roll="forward"),
        lambda: np.busday_count(DAYS[:1], DAYS[-1:]),
    ],
    ids=[
        "a ufunc by operator",
        "a ufunc by name",
        "concatenate",
        "is_busday",
        "busday_offset",
        "busday_count",
    ],
)
def test_a_ufunc_and_a_function_dispatched_in_c_raise_no_event(
    unseen: Callable[[], object], numpy_calls: NumpyCalls
) -> None:
    assert numpy_calls(unseen) == {}
