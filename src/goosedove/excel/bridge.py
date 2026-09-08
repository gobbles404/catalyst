"""The seam between the Excel host and this package.

The host imports this module and uses six names: function_specs, call,
numeric_block, flatten_block, is_block, and the value MISSING. A blank cell
arrives as None, an omitted argument as MISSING, and Excel errors never
arrive; the host returns them before calling. call guards every argument
against the function's own signature, once; past it nothing checks a kind or
a shape. docs/inputs.md is the map.
"""

import ctypes
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Final, cast

import numpy as np
from numpy.typing import NDArray

import goosedove


class Missing:
    """An argument the formula left out. Not a blank cell, which is None."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


MISSING: Final = Missing()


class GuardError(Exception):
    """An argument that is not what the function declared."""


class _Rejected(Exception):
    """Raised inside an accept function; the guard turns it into a GuardError."""


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _Rejected
    return float(value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise _Rejected
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise _Rejected
    return value


def _whole(value: object) -> int:
    number = _number(value)
    if not number.is_integer():
        raise _Rejected
    return int(number)


# What a function may declare, in the words of the sheet, and how each is accepted.
_KINDS: Final[dict[object, tuple[str, Callable[[object], object]]]] = {
    float: ("number", _number),
    str: ("text", _text),
    bool: ("boolean", _boolean),
    int: ("whole number", _whole),
}


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    expected: str
    accept: Callable[[object], object]
    default: object  # MISSING when the argument is required


@dataclass(frozen=True, slots=True)
class Registered:
    fn: Callable[..., object]
    description: str
    parameters: tuple[Parameter, ...]


_FUNCTIONS: dict[str, Registered] = {}


def describe(value: object) -> str:
    """What arrived, in the words of the sheet."""
    if value is MISSING:
        return "missing"
    if value is None:
        return "blank"
    if isinstance(value, bool):
        return f"boolean {'TRUE' if value else 'FALSE'}"
    if isinstance(value, int | float):
        return f"number {value!r}"
    if isinstance(value, str):
        return f"text {value!r}" if value else "empty text"
    if isinstance(value, np.ndarray):
        rows, cols = cast(NDArray[np.float64], value).shape
        return f"{rows}x{cols} array"
    if isinstance(value, list):
        grid = cast(list[list[object]], value)
        return f"{len(grid)}x{len(grid[0])} array"
    return type(value).__name__


_POSITIONAL: Final = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)


def _parameter(function: str, spec: inspect.Parameter) -> Parameter:
    if spec.kind not in _POSITIONAL:
        raise TypeError(
            f"{function}: {spec.name} is {spec.kind.description}, which the host cannot pass"
        )
    kind = _KINDS.get(spec.annotation)
    if kind is None:
        raise TypeError(
            f"{function}: {spec.name} declares {spec.annotation!r}, which the seam cannot receive"
        )
    expected, accept = kind
    default: object = MISSING
    if spec.default is not inspect.Parameter.empty:
        try:
            default = accept(spec.default)
        except _Rejected:
            raise TypeError(
                f"{function}: {spec.name} defaults to {describe(spec.default)}, expected {expected}"
            ) from None
    return Parameter(spec.name, expected, accept, default)


def excel_function[F: Callable[..., object]](fn: F) -> F:
    """Register a worksheet function under its own name; the signature is the contract."""
    name = fn.__name__
    if name in _FUNCTIONS:
        raise TypeError(f"{name} is already registered")
    parameters = tuple(_parameter(name, spec) for spec in inspect.signature(fn).parameters.values())
    _FUNCTIONS[name] = Registered(fn, (fn.__doc__ or "").strip(), parameters)
    return fn


def function_specs() -> list[tuple[str, str, list[str]]]:
    """Name, description, and parameter names for every registered function."""
    return [
        (name, registered.description, [p.name for p in registered.parameters])
        for name, registered in _FUNCTIONS.items()
    ]


def _guard(parameter: Parameter, value: object) -> object:
    if value is MISSING and parameter.default is not MISSING:
        return parameter.default
    try:
        return parameter.accept(value)
    except _Rejected:
        raise GuardError(
            f"{parameter.name} is {describe(value)}, expected {parameter.expected}"
        ) from None


def _arguments(registered: Registered, args: list[object]) -> list[object]:
    if len(args) != len(registered.parameters):
        raise GuardError(f"expected {len(registered.parameters)} arguments, got {len(args)}")
    return [_guard(p, value) for p, value in zip(registered.parameters, args, strict=True)]


def call(name: str, args: list[object]) -> object:
    """Guard every argument, run the function, and turn any failure into cell text."""
    registered = _FUNCTIONS[name]
    try:
        return registered.fn(*_arguments(registered, args))
    except GuardError as failure:
        return f"#ERROR {name}: {failure}"
    except Exception as exc:
        return f"#ERROR {name}: {type(exc).__name__}: {exc}"


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
