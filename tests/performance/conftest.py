"""Shared instruments for budget tests."""

import cProfile
import re
from collections.abc import Callable
from pathlib import Path

import pytest

import goosedove
from goosedove.excel.bridge import DateColumn, NumberColumn, TextColumn, WholeNumberColumn
from goosedove.excel.probes import probe

PACKAGE_DIR = str(Path(goosedove.__file__).parent)


# The column, whole-number, date, and text looks have no probe, because the host cannot tell
# those ranges from any other; these four exist only to count the Python side of each look. Defined
# here, outside the package, they are not themselves counted, and pytest registers them
# before any budget module builds its table of prepared paths.
@probe
def FirstOfNumbers(values: NumberColumn) -> float:
    return float(values[0])


@probe
def FirstOfWholes(values: WholeNumberColumn) -> float:
    return float(values[0])


@probe
def FirstOfDates(dates: DateColumn) -> str:
    return str(dates[0])


@probe
def FirstOfNames(names: TextColumn) -> str:
    return names[0]


def _call_profile(fn: Callable[[], object]) -> dict[str, int]:
    """Which of the package's own functions ran, and how many times each."""
    profiler = cProfile.Profile()
    profiler.enable()
    fn()
    profiler.disable()
    profile: dict[str, int] = {}
    for entry in profiler.getstats():
        code = entry.code
        if isinstance(code, str):
            continue
        if code.co_filename.startswith(PACKAGE_DIR):
            profile[code.co_qualname] = profile.get(code.co_qualname, 0) + entry.callcount
    return profile


@pytest.fixture
def call_profile() -> Callable[[Callable[[], object]], dict[str, int]]:
    return _call_profile


# cProfile names a C call like "<method 'any' of 'numpy.ndarray' objects>" or
# "<built-in method numpy.frombuffer>"; these read the type and the name out of that.
_NUMPY_METHOD = re.compile(r"<method '(\w+)' of 'numpy\.(\w+)' objects>")
_NUMPY_FUNCTION = re.compile(r"<built-in method numpy\.(\w+)>")


def _numpy_calls(fn: Callable[[], object]) -> dict[str, int]:
    """Which numpy C calls ran, and how many times each: the copies and reductions.

    Measured, not derived: these are the C functions cProfile saw. A ufunc applied by an
    operator, such as kinds != NUMBER or isfinite, raises no cProfile event and is not here;
    ufunc.reduce is the reduction behind any, all, and sum, so it appears beside them.
    """
    profiler = cProfile.Profile()
    profiler.enable()
    fn()
    profiler.disable()
    calls: dict[str, int] = {}
    for entry in profiler.getstats():
        code = entry.code
        if not isinstance(code, str):
            continue
        method = _NUMPY_METHOD.fullmatch(code)
        function = _NUMPY_FUNCTION.fullmatch(code)
        if method:
            name = f"{method.group(2)}.{method.group(1)}"
        elif function:
            name = f"numpy.{function.group(1)}"
        else:
            continue
        calls[name] = calls.get(name, 0) + entry.callcount
    return calls


@pytest.fixture
def numpy_calls() -> Callable[[Callable[[], object]], dict[str, int]]:
    return _numpy_calls
