"""Action-count budgets: exact, deterministic, run with every check."""

from __future__ import annotations

import cProfile
from collections.abc import Callable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

import goosedove
from goosedove.instrumentation.work_counts import (
    CACHE_HIT,
    CACHE_MISS,
    HASH,
    KERNEL,
    WorkCounter,
    WorkCounts,
)

# --- stand-in for a real instrument; replace with the real evaluate --------

_cache: dict[bytes, NDArray[np.float64]] = {}


def price_group(
    quantities: NDArray[np.float64],
    prices: NDArray[np.float64],
    counter: WorkCounter,
) -> tuple[NDArray[np.float64], WorkCounts]:
    key = quantities.tobytes() + prices.tobytes()
    counter.hit(HASH)
    cached = _cache.get(key)
    if cached is not None:
        counter.hit(CACHE_HIT)
        return cached, counter.freeze()
    counter.hit(CACHE_MISS)
    counter.hit(KERNEL)
    marks = quantities * prices
    _cache[key] = marks
    return marks, counter.freeze()


# --- helpers ---------------------------------------------------------------

PACKAGE_DIR = str(Path(goosedove.__file__).parent)


def call_profile(fn: Callable[[], object]) -> dict[str, int]:
    """Which of the package's own functions ran, and how many times each."""
    profiler = cProfile.Profile()
    profiler.enable()
    fn()
    profiler.disable()
    profile: dict[str, int] = {}
    for entry in profiler.getstats():  # type: ignore[attr-defined]
        code = entry.code
        if isinstance(code, str):
            continue
        if code.co_filename.startswith(PACKAGE_DIR):
            profile[code.co_qualname] = profile.get(code.co_qualname, 0) + entry.callcount
    return profile


def fixed_group() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    q = np.array([1000.0, -500.0, 250.0])
    p = np.array([71.25, 71.40, 71.10])
    return q, p


# --- budgets ---------------------------------------------------------------


def test_cold_evaluation_counts() -> None:
    _cache.clear()
    q, p = fixed_group()
    _, trace = price_group(q, p, WorkCounter())
    assert trace.as_dict() == {CACHE_MISS: 1, HASH: 1, KERNEL: 1}


def test_warm_evaluation_does_no_pricing_work() -> None:
    _cache.clear()
    q, p = fixed_group()
    price_group(q, p, WorkCounter())
    _, trace = price_group(q, p, WorkCounter())
    assert trace.as_dict() == {CACHE_HIT: 1, HASH: 1}
    assert trace[KERNEL] == 0


# Characterization, not specification: this records the shape of work today so
# that a change to it is visible in review. The two tests above state what must hold.
def test_warm_evaluation_itemized() -> None:
    _cache.clear()
    q, p = fixed_group()
    price_group(q, p, WorkCounter())
    profile = call_profile(lambda: price_group(q, p, WorkCounter()))
    assert profile == {
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
        "WorkCounter.freeze": 1,
    }
