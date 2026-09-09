"""The seam between the Excel host and this package.

The host imports this module and uses six names: function_specs, call,
numeric_block, flatten_block, is_block, and the value MISSING. A blank cell
arrives as None, an omitted argument as MISSING, a range of numbers and
blanks as a 2-D float64 array with NaN for the blanks, any other range as
nested rows of cells, and Excel errors never arrive; the host returns them
before calling. call validates the type of every argument against the
function's own signature, once, by type and shape and never by meaning;
past it nothing checks. docs/inputs.md is the map.
"""

import ctypes
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Final, NewType, cast

import numpy as np
from numpy.typing import NDArray

import goosedove

# --- what a function may declare, beyond float, int, str, and bool ----------

Date = NewType("Date", np.datetime64)
Array = NewType("Array", NDArray[np.float64])  # any shape, laid out as on the sheet
Column = NewType("Column", NDArray[np.float64])  # one column, handed over as a 1-D array
Row = NewType("Row", NDArray[np.float64])  # one row, handed over as a 1-D array
DateColumn = NewType("DateColumn", NDArray[np.datetime64])
DateRow = NewType("DateRow", NDArray[np.datetime64])
TextColumn = NewType("TextColumn", tuple[str, ...])
TextRow = NewType("TextRow", tuple[str, ...])


class Missing:
    """An argument the formula left out. Not a blank cell, which is None."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


MISSING: Final = Missing()


class TypeValidationError(Exception):
    """An argument whose type or shape is not what the function declared."""


class _Rejected(Exception):
    """Raised inside an accept rule. Names the cell when the failure is inside a range."""

    def __init__(
        self, cell: tuple[int, int] | None = None, value: object = None, expected: str = ""
    ) -> None:
        super().__init__()
        self.cell = cell
        self.value = value
        self.expected = expected


# --- one cell ---------------------------------------------------------------

EXCEL_EPOCH: Final = np.datetime64("1899-12-30", "D")

# A date is a whole serial inside Excel's own calendar. Serial 61 is 1 March
# 1900, the first day on which Excel's serial numbers and the real calendar
# agree: 1 to 60 straddle a 29 February 1900 that never happened. Serial
# 2958465 is 31 December 9999, the last day Excel can show. This is the one
# place the boundary looks at what a value means. 75 passes, as 15 March 1900;
# whether that makes sense is the library's question.
FIRST_SERIAL: Final = 61
LAST_SERIAL: Final = 2958465


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _Rejected
    return float(value)


def _whole(value: object) -> int:
    number = _number(value)
    if not number.is_integer():
        raise _Rejected
    return int(number)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise _Rejected
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise _Rejected
    return value


def _date(value: object) -> np.datetime64:
    serial = _whole(value)
    if not FIRST_SERIAL <= serial <= LAST_SERIAL:
        raise _Rejected
    return EXCEL_EPOCH + np.timedelta64(serial, "D")


# --- every cell of a range --------------------------------------------------


def _cells[T](
    rule: Callable[[object], T], expected: str, rows: list[list[object]]
) -> list[list[T]]:
    """Apply one cell rule to nested rows; the first cell that fails is named as INDEX counts."""
    grid: list[list[T]] = []
    for r, row in enumerate(rows, start=1):
        line: list[T] = []
        for c, cell in enumerate(row, start=1):
            try:
                line.append(rule(cell))
            except _Rejected:
                raise _Rejected((r, c), cell, expected) from None
        grid.append(line)
    return grid


def _cell_of(block: NDArray[np.float64], r: int, c: int) -> float | None:
    """One cell of a numeric block as it arrived: a number, or None for a blank."""
    cell = float(block[r, c])
    return None if np.isnan(cell) else cell


def _first_bad(bad: NDArray[np.bool_], block: NDArray[np.float64], expected: str) -> _Rejected:
    """The rejection for the first flagged cell of a numeric block, named as INDEX counts."""
    r, c = divmod(int(bad.argmax()), block.shape[1])
    return _Rejected((r + 1, c + 1), _cell_of(block, r, c), expected)


def _numbers(value: object) -> NDArray[np.float64]:
    """Every cell a number, kept in sheet order. A scalar is a 1x1 range."""
    if isinstance(value, np.ndarray):
        block = cast(NDArray[np.float64], value)
        blanks = np.isnan(block)
        if blanks.any():
            raise _first_bad(blanks, block, "number")
        return block
    if isinstance(value, list):
        rows = cast(list[list[object]], value)
        return np.array(_cells(_number, "number", rows), dtype=np.float64)
    return np.array([[_number(value)]])


def _dates(value: object) -> NDArray[np.datetime64]:
    """Every cell a date, kept in sheet order. A scalar is a 1x1 range."""
    if isinstance(value, np.ndarray):
        return _dates_of(cast(NDArray[np.float64], value))
    if isinstance(value, list):
        rows = cast(list[list[object]], value)
        return np.array(_cells(_date, "date", rows), dtype="datetime64[D]")
    return np.array([[_date(value)]])


def _dates_of(block: NDArray[np.float64]) -> NDArray[np.datetime64]:
    """Whole serials inside Excel's calendar become dates; the first other cell is named."""
    bad = (
        np.isnan(block)
        | (block != np.floor(block))
        | (block < FIRST_SERIAL)
        | (block > LAST_SERIAL)
    )
    if bad.any():
        raise _first_bad(bad, block, "date")
    return EXCEL_EPOCH + block.astype(np.int64).astype("timedelta64[D]")


def _texts(value: object) -> list[list[str]]:
    """Every cell text, kept in sheet order. A scalar is a 1x1 range."""
    if isinstance(value, np.ndarray):
        # A numeric block holds only numbers and blanks, so its first cell already fails.
        raise _Rejected((1, 1), _cell_of(cast(NDArray[np.float64], value), 0, 0), "text")
    if isinstance(value, list):
        rows = cast(list[list[object]], value)
        return _cells(_text, "text", rows)
    return [[_text(value)]]


# --- one column or one row: the shape is checked before any cell is --------


def _shape(value: object) -> tuple[int, int]:
    """Rows and columns of what arrived. A scalar is 1x1."""
    if isinstance(value, np.ndarray):
        rows, cols = cast(NDArray[np.float64], value).shape
        return rows, cols
    if isinstance(value, list):
        grid = cast(list[list[object]], value)
        return len(grid), len(grid[0])
    return 1, 1


def _one_column(value: object) -> None:
    if _shape(value)[1] != 1:
        raise _Rejected


def _one_row(value: object) -> None:
    if _shape(value)[0] != 1:
        raise _Rejected


def _column(value: object) -> NDArray[np.float64]:
    _one_column(value)
    return _numbers(value)[:, 0]


def _row(value: object) -> NDArray[np.float64]:
    _one_row(value)
    return _numbers(value)[0]


def _date_column(value: object) -> NDArray[np.datetime64]:
    _one_column(value)
    return _dates(value)[:, 0]


def _date_row(value: object) -> NDArray[np.datetime64]:
    _one_row(value)
    return _dates(value)[0]


def _text_column(value: object) -> tuple[str, ...]:
    _one_column(value)
    return tuple([row[0] for row in _texts(value)])


def _text_row(value: object) -> tuple[str, ...]:
    _one_row(value)
    return tuple(_texts(value)[0])


# Every declared type, in the words of the sheet, and the rule that accepts it.
_DECLARED: Final[dict[object, tuple[str, Callable[[object], object]]]] = {
    float: ("number", _number),
    int: ("whole number", _whole),
    str: ("text", _text),
    bool: ("boolean", _boolean),
    Date: ("date", _date),
    Array: ("array of numbers", _numbers),
    Column: ("column of numbers", _column),
    Row: ("row of numbers", _row),
    DateColumn: ("column of dates", _date_column),
    DateRow: ("row of dates", _date_row),
    TextColumn: ("column of text", _text_column),
    TextRow: ("row of text", _text_row),
}


# --- registration -----------------------------------------------------------


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
    declared = _DECLARED.get(spec.annotation)
    if declared is None:
        raise TypeError(
            f"{function}: {spec.name} declares {spec.annotation!r}, which the seam cannot receive"
        )
    expected, accept = declared
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


# --- type validation --------------------------------------------------------


def _validate(parameter: Parameter, value: object) -> object:
    if value is MISSING and parameter.default is not MISSING:
        return parameter.default
    try:
        return parameter.accept(value)
    except _Rejected as rejected:
        if rejected.cell is None:
            raise TypeValidationError(
                f"{parameter.name} is {describe(value)}, expected {parameter.expected}"
            ) from None
        r, c = rejected.cell
        raise TypeValidationError(
            f"{parameter.name} cell ({r}, {c}) is {describe(rejected.value)}, "
            f"expected {rejected.expected}"
        ) from None


def _arguments(registered: Registered, args: list[object]) -> list[object]:
    if len(args) != len(registered.parameters):
        raise TypeValidationError(
            f"expected {len(registered.parameters)} arguments, got {len(args)}"
        )
    return [_validate(p, value) for p, value in zip(registered.parameters, args, strict=True)]


def call(name: str, args: list[object]) -> object:
    """Validate every argument, run the function, and turn any failure into cell text."""
    registered = _FUNCTIONS[name]
    try:
        return registered.fn(*_arguments(registered, args))
    except TypeValidationError as failure:
        return f"#ERROR {name}: {failure}"
    except Exception as exc:
        return f"#ERROR {name}: {type(exc).__name__}: {exc}"


# --- the host's buffers -----------------------------------------------------


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


# --- placeholders: each proves one declared type crosses. Delete as real functions arrive.


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


@excel_function
def DateText(day: Date) -> str:
    """A date cell, written out; proves a date crosses."""
    return str(day)


@excel_function
def SumArray(values: Array) -> float:
    """Sum a range of numbers of any shape; proves an array crosses."""
    return float(values.sum())


@excel_function
def SumColumn(values: Column) -> float:
    """Sum one column of numbers; proves a column crosses."""
    return float(values.sum())


@excel_function
def SumRow(values: Row) -> float:
    """Sum one row of numbers; proves a row crosses."""
    return float(values.sum())


@excel_function
def FirstDate(dates: DateColumn) -> str:
    """The first date in a column of dates, as given; proves a column of dates crosses."""
    return str(dates[0])


@excel_function
def LastDate(dates: DateRow) -> str:
    """The last date in a row of dates, as given; proves a row of dates crosses."""
    return str(dates[-1])


@excel_function
def JoinColumn(names: TextColumn) -> str:
    """One column of text, joined with commas; proves a column of text crosses."""
    return ", ".join(names)


@excel_function
def JoinRow(names: TextRow) -> str:
    """One row of text, joined with commas; proves a row of text crosses."""
    return ", ".join(names)
