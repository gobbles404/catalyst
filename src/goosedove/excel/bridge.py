"""The seam between the Excel host and this package.

The host imports this module and uses four names: function_specs, call,
cells_block, and the value MISSING. Importing it imports goosedove.excel
first, the catalogue of every module that registers worksheet functions, so
the function list is complete by the time the host asks. A blank cell arrives
as None, an omitted argument as MISSING, and every range as Cells: one kind
code per cell, one number per cell, and the text cells in sheet order, which
cells_block builds from the host's buffers. Excel errors never arrive; the
host returns them before calling. call validates the type of every argument
against the function's own signature, once, by type and shape and never by
meaning; past it nothing checks. On the way back, call converts the result by
the function's declared return type, once, into the four things the host can
show: a number, text, a boolean, or a block of numbers. docs/inputs.md and
docs/outputs.md are the map.
"""

import ctypes
import inspect
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Final, NewType, assert_never, cast

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


# --- what arrives ------------------------------------------------------------


class Kind(IntEnum):
    """What one cell of a range holds. The codes are shared with the host."""

    NUMBER = 0
    TEXT = 1
    BOOLEAN = 2
    BLANK = 3
    MISSING = 4


@dataclass(frozen=True, slots=True, eq=False)
class Cells:
    """A range as the host sends it: a kind per cell, a number per cell, the text cells in order.

    numbers holds the value of number and boolean cells and NaN elsewhere. texts holds every
    text cell in sheet order, so the k-th text cell is the k-th TEXT in kinds.
    """

    kinds: NDArray[np.uint8]
    numbers: NDArray[np.float64]
    texts: tuple[str, ...]

    @classmethod
    def from_rows(cls, rows: Sequence[Sequence[object]]) -> "Cells":
        """What the host would send for these cells, from Python values. Tests build ranges here."""
        kinds = np.empty((len(rows), len(rows[0])), dtype=np.uint8)
        numbers = np.full(kinds.shape, np.nan)
        texts: list[str] = []
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                kind, number = _classify(cell)
                kinds[r, c] = kind
                numbers[r, c] = number
                if kind is Kind.TEXT:
                    texts.append(cast(str, cell))
        return cls(kinds, numbers, tuple(texts))


def _classify(cell: object) -> tuple[Kind, float]:
    if cell is MISSING:
        return Kind.MISSING, np.nan
    if cell is None:
        return Kind.BLANK, np.nan
    if isinstance(cell, bool):
        return Kind.BOOLEAN, 1.0 if cell else 0.0
    if isinstance(cell, int | float):
        return Kind.NUMBER, float(cell)
    if isinstance(cell, str):
        return Kind.TEXT, np.nan
    raise TypeError(f"a cell cannot hold {type(cell).__name__}")


def cells_block(kinds_pointer: int, numbers_pointer: int, rows: int, cols: int, text: str) -> Cells:
    """Copy the host's pinned buffers into Cells. The text cells arrive joined with NUL."""
    count = rows * cols
    kinds = np.frombuffer((ctypes.c_uint8 * count).from_address(kinds_pointer), dtype=np.uint8)
    numbers = np.frombuffer(
        (ctypes.c_double * count).from_address(numbers_pointer), dtype=np.float64
    )
    kinds = kinds.reshape(rows, cols).copy()
    texts = tuple(text.split("\0")) if (kinds == Kind.TEXT).any() else ()
    return Cells(kinds, numbers.reshape(rows, cols).copy(), texts)


def _cell(cells: Cells, i: int) -> object:
    """The value at flat index i, as it arrived."""
    kind = Kind(int(cells.kinds.flat[i]))
    match kind:
        case Kind.NUMBER:
            return float(cells.numbers.flat[i])
        case Kind.TEXT:
            return cells.texts[int(np.count_nonzero(cells.kinds.ravel()[:i] == Kind.TEXT))]
        case Kind.BOOLEAN:
            return bool(cells.numbers.flat[i])
        case Kind.BLANK:
            return None
        case Kind.MISSING:
            return MISSING
        case _:
            assert_never(kind)


def _first_bad(cells: Cells, bad: NDArray[np.bool_], expected: str) -> _Rejected:
    """The rejection for the first flagged cell, named as INDEX counts."""
    i = int(bad.argmax())
    r, c = divmod(i, cells.kinds.shape[1])
    return _Rejected((r + 1, c + 1), _cell(cells, i), expected)


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


# --- every cell of a range, in one vectorized look ----------------------------


def _numbers(value: object) -> NDArray[np.float64]:
    """Every cell a number, kept in sheet order. A scalar is a 1x1 range."""
    if isinstance(value, Cells):
        bad = value.kinds != Kind.NUMBER
        if bad.any():
            raise _first_bad(value, bad, "number")
        return value.numbers
    return np.array([[_number(value)]])


def _dates(value: object) -> NDArray[np.datetime64]:
    """Every cell a date, kept in sheet order. A scalar is a 1x1 range."""
    if isinstance(value, Cells):
        block = value.numbers
        bad = (
            (value.kinds != Kind.NUMBER)
            | (block != np.floor(block))
            | (block < FIRST_SERIAL)
            | (block > LAST_SERIAL)
        )
        if bad.any():
            raise _first_bad(value, bad, "date")
        return EXCEL_EPOCH + block.astype(np.int64).astype("timedelta64[D]")
    return np.array([[_date(value)]])


def _texts(value: object) -> NDArray[np.object_]:
    """Every cell text with a character in it, kept in sheet order. A scalar is a 1x1 range."""
    if isinstance(value, Cells):
        bad = value.kinds != Kind.TEXT
        if bad.any():
            raise _first_bad(value, bad, "text")
        if "" in value.texts:
            r, c = divmod(value.texts.index(""), value.kinds.shape[1])
            raise _Rejected((r + 1, c + 1), "", "text")
        return np.array(value.texts, dtype=object).reshape(value.kinds.shape)
    return np.array([[_text(value)]], dtype=object)


# --- one column or one row: the shape is checked before any cell is --------


def _shape(value: object) -> tuple[int, int]:
    """Rows and columns of what arrived. A scalar is 1x1."""
    if isinstance(value, Cells):
        rows, cols = value.kinds.shape
        return rows, cols
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
    return tuple(_texts(value)[:, 0])


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


# --- the way out: every declared result, in the words of the sheet, and the rule that sends it


class _BadResult(Exception):
    """Raised inside a result rule. Carries the message that follows the function's name."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


MAX_TEXT: Final = 32767  # the longest text a cell holds; Excel cuts longer text without a word
EXACT: Final = 2**53  # the largest whole number a cell holds exactly
CALENDAR: Final = "1900-03-01 to 9999-12-31"


def _returned(value: object, expected: str) -> _BadResult:
    what = "nothing" if value is None else describe(value)
    return _BadResult(f"returned {what}, expected {expected}")


def _scalar(value: object) -> object:
    """A numpy scalar as the Python value it holds; anything else as it is."""
    return cast(Any, value).item() if isinstance(value, np.generic) else value


def _unit(dated: object) -> str:
    """The unit of a numpy date, or of an array of them: "D" when they are days."""
    return np.datetime_data(cast(Any, dated).dtype)[0]


_FINER_THAN_A_DAY: Final = frozenset({"h", "m", "s", "ms", "us", "ns", "ps", "fs", "as"})
_COARSER_THAN_A_DAY: Final = {"Y": "years", "M": "months", "W": "weeks"}


def _date_word(unit: str) -> str:
    """What a numpy date of that unit is, in the words of the sheet."""
    if unit == "D":
        return "date"
    if unit in _FINER_THAN_A_DAY:
        return "date with a time"
    if unit in _COARSER_THAN_A_DAY:
        return f"date in {_COARSER_THAN_A_DAY[unit]}"
    return "date without a unit"  # numpy's NaT with no unit


def _number_out(value: object) -> float:
    """A number goes out as a float. A whole number is a number on the sheet."""
    number = _scalar(value)
    if isinstance(number, bool) or not isinstance(number, int | float):
        raise _returned(value, "number")
    if isinstance(number, int) and abs(number) > EXACT:
        raise _BadResult(f"returned {describe(value)}, beyond what a cell holds exactly")
    if not math.isfinite(number):
        raise _BadResult("result is not a finite number")
    return float(number)


def _whole_out(value: object) -> float:
    """A whole number, in or out, is a number with no fraction."""
    number = _scalar(value)
    if isinstance(number, bool) or not isinstance(number, int | float):
        raise _returned(value, "whole number")
    if not math.isfinite(number):
        raise _BadResult("result is not a finite number")
    if isinstance(number, float) and not number.is_integer():
        raise _returned(value, "whole number")
    if abs(number) > EXACT:
        raise _BadResult(f"returned {describe(value)}, beyond what a cell holds exactly")
    return float(number)


def _text_out(value: object) -> str:
    text = _scalar(value)
    if not isinstance(text, str):
        raise _returned(value, "text")
    if not text:
        raise _BadResult("returned empty text, expected text")
    units = len(text.encode("utf-16-le")) // 2  # Excel counts UTF-16 units, as LEN does
    if units > MAX_TEXT:
        raise _BadResult(f"returned text of {units} characters, expected at most {MAX_TEXT}")
    return text


def _boolean_out(value: object) -> bool:
    flag = _scalar(value)
    if not isinstance(flag, bool):
        raise _returned(value, "boolean")
    return flag


def _serials(days: NDArray[Any]) -> tuple[NDArray[np.float64], int | None, str]:
    """Serials for an array of days, or the flat index and reason of the first that is not one."""
    missing = np.isnat(days)
    if missing.any():
        return np.empty(0), int(missing.argmax()), "is not a date"
    serials = (days - EXCEL_EPOCH) / np.timedelta64(1, "D")
    outside = (serials < FIRST_SERIAL) | (serials > LAST_SERIAL)
    if outside.any():
        return np.empty(0), int(outside.argmax()), f"is a date outside {CALENDAR}"
    return serials, None, ""


def _date_out(value: object) -> float:
    """A date goes out as its whole serial, the meaning exception mirrored."""
    if not isinstance(value, np.datetime64):
        raise _returned(value, "date")
    day = cast(Any, value)
    if _unit(day) != "D":
        raise _returned(day, "date")
    serials, bad, reason = _serials(np.array([day]))
    if bad is not None:
        raise _BadResult(f"result {reason}")
    return float(serials[0])


def _dimensions(value: object, ndim: int, expected: str) -> NDArray[Any]:
    """The value as a plain numpy array of that many dimensions, or the rejection."""
    # Exactly an ndarray: a subclass, a masked array say, could hide cells behind its buffer.
    if type(value) is not np.ndarray:
        raise _returned(value, expected)
    if value.ndim != ndim:
        raise _returned(value, expected)
    return value


def _finite(block: NDArray[Any], value: NDArray[Any], expected: str) -> NDArray[np.float64]:
    """A block of finite numbers as contiguous float64, or the first bad cell as INDEX counts it."""
    if block.size == 0:
        raise _BadResult(f"returned {describe(value)}, expected {expected} with at least one cell")
    if block.dtype.kind not in "fiu":
        raise _returned(value, expected)
    if block.dtype.kind in "iu":
        big = (block > EXACT) | (block < -EXACT)  # two-sided: abs overflows on the int64 minimum
        if big.any():
            r, c = divmod(int(big.argmax()), block.shape[1])
            raise _BadResult(f"result cell ({r + 1}, {c + 1}) is beyond what a cell holds exactly")
    out = np.ascontiguousarray(block, dtype=np.float64)
    finite = np.isfinite(out)
    if not finite.all():
        r, c = divmod(int((~finite).argmax()), out.shape[1])
        raise _BadResult(f"result cell ({r + 1}, {c + 1}) is not a finite number")
    return out


def _array_out(value: object) -> NDArray[np.float64]:
    block = _dimensions(value, 2, "array of numbers")
    return _finite(block, block, "array of numbers")


def _column_out(value: object) -> NDArray[np.float64]:
    """A column spills down: one row per value."""
    column = _dimensions(value, 1, "column of numbers")
    return _finite(column.reshape(-1, 1), column, "column of numbers")


def _row_out(value: object) -> NDArray[np.float64]:
    """A row spills across: one column per value."""
    row = _dimensions(value, 1, "row of numbers")
    return _finite(row.reshape(1, -1), row, "row of numbers")


def _days(value: object, expected: str) -> NDArray[Any]:
    """A one-dimensional array of numpy days with at least one cell, or the rejection."""
    days = _dimensions(value, 1, expected)
    if days.dtype.kind != "M" or _unit(days) != "D":
        raise _returned(days, expected)
    if days.size == 0:
        raise _BadResult(f"returned {describe(days)}, expected {expected} with at least one cell")
    return days


def _date_column_out(value: object) -> NDArray[np.float64]:
    serials, bad, reason = _serials(_days(value, "column of dates"))
    if bad is not None:
        raise _BadResult(f"result cell ({bad + 1}, 1) {reason}")
    return np.ascontiguousarray(serials.reshape(-1, 1))


def _date_row_out(value: object) -> NDArray[np.float64]:
    serials, bad, reason = _serials(_days(value, "row of dates"))
    if bad is not None:
        raise _BadResult(f"result cell (1, {bad + 1}) {reason}")
    return np.ascontiguousarray(serials.reshape(1, -1))


# Every declared result and the rule that converts it; each rule knows the words of the sheet.
_RESULTS: Final[dict[object, Callable[[object], object]]] = {
    float: _number_out,
    int: _whole_out,
    str: _text_out,
    bool: _boolean_out,
    Date: _date_out,
    Array: _array_out,
    Column: _column_out,
    Row: _row_out,
    DateColumn: _date_column_out,
    DateRow: _date_row_out,
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
    hidden: bool  # absent from Excel's function wizard, still callable by name
    convert: Callable[[object], object]  # the declared result's rule, from _RESULTS


_FUNCTIONS: dict[str, Registered] = {}

_KINDS: Final = {"f": "number", "i": "number", "u": "number", "b": "boolean", "U": "text"}


def describe(value: object) -> str:
    """What arrived, or what a function returned, in the words of the sheet.

    A blank cell is None on the way in; _returned says "nothing" for a None result.
    """
    if value is MISSING:
        return "missing"
    if value is None:
        return "blank"
    if isinstance(value, bool):
        return f"boolean {'TRUE' if value else 'FALSE'}"
    if isinstance(value, int | float):
        return f"number {_scalar(value)!r}"
    if isinstance(value, str):
        return f"text {str(value)!r}" if value else "empty text"
    if isinstance(value, Cells):
        rows, cols = value.kinds.shape
        return f"{rows}x{cols} array"
    if isinstance(value, np.datetime64):
        day = cast(Any, value)
        return f"{_date_word(_unit(day))} {day}"
    if isinstance(value, np.ndarray):
        array = cast(NDArray[Any], value)
        if type(array) is not np.ndarray:
            return f"a numpy {type(array).__name__}"
        return _describe_array(array)
    if isinstance(value, np.generic):
        scalar = cast(Any, value)
        held = _scalar(scalar)  # a numpy boolean or integer, in the words above
        if isinstance(held, np.generic):
            return f"a numpy {type(scalar).__name__}"  # one that .item() cannot unwrap
        return describe(held)
    return f"a Python {type(value).__name__}"


def _plural(word: str) -> str:
    if word == "text":
        return word
    if word.startswith("date"):
        return "dates" + word[len("date") :]
    return word + "s"


def _describe_array(array: NDArray[Any]) -> str:
    word = _KINDS.get(array.dtype.kind, array.dtype.name)
    if array.dtype.kind == "M":
        word = _date_word(_unit(array))
    if array.ndim == 2:
        rows, cols = array.shape
        return f"{rows}x{cols} array of {_plural(word)}"
    if array.ndim == 1:
        return f"list of {array.size} {word if array.size == 1 else _plural(word)}"
    return f"{array.ndim}-dimensional array of {_plural(word)}"


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


def _result(function: str, annotation: object) -> Callable[[object], object]:
    if annotation is inspect.Signature.empty:
        raise TypeError(f"{function} declares no result; a worksheet function returns something")
    if annotation is None:
        raise TypeError(
            f"{function} declares that it returns nothing; "
            "a worksheet function returns something or fails"
        )
    convert = _RESULTS.get(annotation)
    if convert is None:
        raise TypeError(
            f"{function} declares {annotation!r} as its result, which the seam cannot send"
        )
    return convert


def register[F: Callable[..., object]](fn: F, *, hidden: bool) -> F:
    """Register a worksheet function under its own name; the signature is the contract."""
    name = fn.__name__
    if name in _FUNCTIONS:
        raise TypeError(f"{name} is already registered")
    signature = inspect.signature(fn)
    parameters = tuple(_parameter(name, spec) for spec in signature.parameters.values())
    convert = _result(name, signature.return_annotation)
    _FUNCTIONS[name] = Registered(fn, (fn.__doc__ or "").strip(), parameters, hidden, convert)
    return fn


def excel_function[F: Callable[..., object]](fn: F) -> F:
    """Register a worksheet function that Excel lists in its function wizard."""
    return register(fn, hidden=False)


def function_specs() -> list[tuple[str, str, list[str], bool]]:
    """Name, description, parameter names, and whether hidden, for every registered function."""
    return [
        (name, registered.description, [p.name for p in registered.parameters], registered.hidden)
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
    """Validate the arguments, run the function, convert the result; a failure becomes cell text."""
    registered = _FUNCTIONS[name]
    try:
        return registered.convert(registered.fn(*_arguments(registered, args)))
    except TypeValidationError as failure:
        return f"#ERROR {name}: {failure}"
    except _BadResult as bad:
        return f"#ERROR {name}: {bad.text}"
    except Exception as exc:
        return f"#ERROR {name}: {type(exc).__name__}: {exc}"


# --- the bridge's own worksheet function; the probes live in probes.py --------


@excel_function
def Ping() -> str:
    """Confirm which goosedove Excel is running."""
    try:
        release = version("goosedove")
    except PackageNotFoundError:
        release = "source checkout"
    return f"goosedove {release} from {goosedove.__file__}"
