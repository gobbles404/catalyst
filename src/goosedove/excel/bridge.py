"""The seam between the Excel host and this package.

The host imports this module and uses exactly four names: MISSING,
function_specs, call, and the module itself. Nothing else in the package
knows Excel exists.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version

import goosedove

MISSING = object()
"""Marker the host passes for an argument the user left blank."""

_FUNCTIONS: dict[str, Callable[..., object]] = {}


def excel_function[F: Callable[..., object]](fn: F) -> F:
    """Register a plain function as a worksheet function under its own name."""
    _FUNCTIONS[fn.__name__] = fn
    return fn


def function_specs() -> list[tuple[str, str, list[str]]]:
    """Name, description, and parameter names for every registered function."""
    return [
        (name, (fn.__doc__ or "").strip(), list(inspect.signature(fn).parameters))
        for name, fn in _FUNCTIONS.items()
    ]


def call(name: str, args: list[object]) -> object:
    """Run one registered function; blanks become None, errors become text."""
    fn = _FUNCTIONS[name]
    try:
        return fn(*[None if a is MISSING else a for a in args])
    except Exception as exc:
        return f"#ERROR {type(exc).__name__}: {exc}"


@excel_function
def Ping() -> str:
    """Confirm which goosedove Excel is running."""
    try:
        release = version("goosedove")
    except PackageNotFoundError:
        release = "source checkout"
    return f"goosedove {release} from {goosedove.__file__}"


@excel_function
def Add(a: float, b: float) -> float:
    """Add two numbers; proves arguments cross the seam."""
    return a + b
