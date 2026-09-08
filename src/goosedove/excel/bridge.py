"""The seam between the Excel host and this package.

The host imports this module and calls exactly five names: function_specs,
call, numeric_block, flatten_block, and is_block. Blanks arrive as None.
Excel errors never arrive; the host returns them before calling. Nothing
else in the package knows Excel exists.
"""

from __future__ import annotations

import ctypes
import inspect
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version

import numpy as np
from numpy.typing import NDArray

import goosedove

_FUNCTIONS: dict[str, Callable[..., object]] = {}


def numeric_block(pointer: int, rows: int, cols: int) -> NDArray[np.float64]:
    """Copy a pinned double[] from the host into a numpy array. NaN marks blanks."""
    buffer = (ctypes.c_double * (rows * cols)).from_address(pointer)
    return np.frombuffer(buffer, dtype=np.float64).reshape(rows, cols).copy()


def flatten_block(block: NDArray[np.float64]) -> NDArray[np.float64]:
    """One contiguous 1-D float64 view for the host's buffer read."""
    return np.ascontiguousarray(block, dtype=np.float64).reshape(-1)


def is_block(value: object) -> bool:
    """True when a result is a numeric array the host should return as a range."""
    return isinstance(value, np.ndarray)


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
    """Run one registered function; errors become text."""
    fn = _FUNCTIONS[name]
    try:
        return fn(*args)
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


Cell = float | str | None
Range = list[list[Cell]]


@excel_function
def SumRange(values: float | Range | NDArray[np.float64] | None) -> float:
    """Sum a numeric range; blanks count as zero, text is an error."""
    if isinstance(values, np.ndarray):
        return float(np.nansum(values))
    rows: Range = values if isinstance(values, list) else [[values]]
    total = 0.0
    for row in rows:
        for cell in row:
            if cell is None:
                continue
            if isinstance(cell, str):
                raise ValueError(f"text in numeric range: {cell!r}")
            total += cell
    return total


@excel_function
def ScaleBlock(
    values: float | Range | NDArray[np.float64] | None, factor: float
) -> NDArray[np.float64]:
    """Multiply every cell of a numeric range by a factor; returns a block."""
    if isinstance(values, np.ndarray):
        return values * factor
    rows: Range = values if isinstance(values, list) else [[values]]
    block = np.array(
        [[np.nan if cell is None else cell for cell in row] for row in rows], dtype=np.float64
    )
    return block * factor
