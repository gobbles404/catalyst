"""The seam between the Excel host and this package.

The host imports this module and uses four names: function_specs and entry
at registration, and cells_from_buffers and the value MISSING, fetched once
at start. Importing it imports goosedove.excel first, the catalogue of every
module that registers worksheet functions, so the function list is complete by
the time the host asks. For each function the host fetches its prepared path,
entry(name), once, and calls it with each recalculation's inputs. A blank cell
arrives as None, an omitted argument as MISSING, and every range as Cells: one
kind code per cell, one number per cell, the text cells in sheet order, and
the host's summary of which kinds occurred, which cells_from_buffers builds
from the host's buffers. Excel errors never
arrive; the host returns them before calling. The prepared path validates the
type of every argument against the function's own signature, once, by type
and shape and never by meaning; past it nothing checks. A table crosses as two
arguments, a row of text for its headers and a mixed range for its body, and
the prepared path binds the headers to the function's declared schema and
hands the function typed columns. On the way back it
converts the result by the function's declared return type, once, into the
five things the host can show: a number, text, a boolean, an array of
numbers, or a rectangle of numbers, text and booleans that the host lays out
cell by cell. An object a creator returns is kept here, in one store, and
crosses as its handle: text that a later call hands back to receive the object.
docs/seam/inputs.md and docs/seam/outputs.md are the map.
"""

import ctypes
import inspect
import itertools
import math
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields, replace
from enum import IntEnum
from functools import partial
from importlib.metadata import PackageNotFoundError, version
from operator import attrgetter
from types import NoneType, UnionType
from typing import (
    Annotated,
    Any,
    Final,
    NewType,
    Union,
    assert_never,
    cast,
    dataclass_transform,
    get_args,
    get_origin,
)

import numpy as np
from numpy.typing import NDArray

import goosedove
from goosedove.calendar.calendar import Calendar
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index import Index
from goosedove.instruments.definitions import FieldType, Instrument
from goosedove.instruments.fields import FieldValues, selected
from goosedove.market.market import Market
from goosedove.market.market_history import MarketHistory
from goosedove.market_data.futures_fixings import FuturesFixings
from goosedove.market_data.gas_daily_fixings import GasDailyFixings
from goosedove.market_data.iferc_fixings import IfercFixings
from goosedove.market_data.price_vector import PriceVector
from goosedove.trades.evaluation import TradeResults
from goosedove.trades.preparation import PreparedTrades
from goosedove.trades.resolution import Trades

# --- what a function may declare, beyond float, int, str, and bool ----------

Date = NewType("Date", np.datetime64)
NumberArray = NewType("NumberArray", NDArray[np.float64])  # any shape, laid out as on the sheet
NumberColumn = NewType(
    "NumberColumn", NDArray[np.float64]
)  # one column, handed over as a 1-D array
NumberRow = NewType("NumberRow", NDArray[np.float64])  # one row, handed over as a 1-D array
DateColumn = NewType("DateColumn", NDArray[np.datetime64])
DateRow = NewType("DateRow", NDArray[np.datetime64])
TextColumn = NewType("TextColumn", tuple[str, ...])
TextRow = NewType("TextRow", tuple[str, ...])
BooleanColumn = NewType("BooleanColumn", NDArray[np.bool_])  # one column, handed over 1-D

# A handle: text in a cell that stands for an object the seam holds. Declared around a class the
# library defines, `-> Handle[DiscountCurve]` returns the object and the cell shows its handle,
# and `curve: Handle[DiscountCurve]` receives the object the handle stands for. To the type
# checker it is the class itself, so a function body needs no cast; to registration it is the
# mark that selects publishing on the way out and resolving on the way in.
type Handle[T] = T
# A template's one row, or a ticket's rows, of an instrument's fields: a mixed range that a row of
# text before it heads, bound at the call against the instrument another argument selects, the
# one parameter whose type is S: `FieldRow[str]` takes the instrument named by the function's text
# parameter, `FieldRows[TradeTemplate]` the instrument its template handle holds. Any subset of the
# instrument's fields, in any order, the headers matched exactly, case and all; the function
# receives a FieldValues, each column typed by its field. docs/seam/inputs.md decision 42.
type FieldRow[S] = FieldValues
type FieldRows[S] = FieldValues


@dataclass(frozen=True, slots=True, eq=False)
class MixedArray:
    """A range whose cells may be numbers, nonempty text and booleans together, in any shape.

    The others above are names for a shape numpy or Python already has, so a function receives a
    bare array or tuple. This one is a record, because a mixed range needs its kinds beside its
    values to be read at all. The three fields are the storage the host already sent, handed over
    and not copied.

    numeric_slots is storage, not an array of numbers. It holds the number where a cell holds a
    number, 1.0 or 0.0 where a cell holds a boolean, and NaN where a cell holds text: that NaN is
    a placeholder the host wrote, not a value anyone sent. So kinds says what each slot means, and
    summing numeric_slots on its own would count TRUE as one and poison every text cell. texts
    holds the text cells in sheet order, so the k-th TEXT in kinds is the k-th entry of texts.

    A date is a number here, as it is everywhere at the seam: Excel sends the serial and the
    formatting never travels, so 22 May 2026 arrives as 46164.0 and nothing checks a calendar.

    Nothing may replace a field, but the arrays a field points at can still be written to, so two
    of these are never compared and none is ever used as a key.
    """

    kinds: NDArray[np.uint8]
    numeric_slots: NDArray[np.float64]
    texts: tuple[str, ...]

    @property
    def shape(self) -> tuple[int, int]:
        """Rows and columns of the rectangle, which is the kinds array's own shape."""
        rows, cols = self.kinds.shape
        return rows, cols

    @classmethod
    def table(
        cls, headings: Sequence[Sequence[str]], *columns: NDArray[Any] | tuple[str, ...]
    ) -> "MixedArray":
        """A rectangle for the way out: rows of text over columns of one kind each.

        Each heading row holds one text per column. Each column is a tuple of texts, an array
        of numbers, an array of numpy days, which go out as the serials the sheet formats, or an
        array of booleans, all of one length. The kinds and the slots are filled a column at a
        time and the texts gathered in sheet order, so nothing runs per cell. A day outside the
        calendar fails as a date result fails, naming the cell.
        """
        width = len(columns)
        rows = len(columns[0]) if columns else 0
        top = len(headings)
        for r, row in enumerate(headings):
            if len(row) != width:
                raise ValueError(
                    f"heading row {r + 1} holds {len(row)} texts, expected {width}, one per column"
                )
        kinds = np.empty((top + rows, width), dtype=np.uint8)
        slots = np.full((top + rows, width), np.nan)
        kinds[:top] = TEXT_CODE
        text_columns: list[tuple[str, ...]] = []
        for j, column in enumerate(columns):
            if len(column) != rows:
                raise ValueError(
                    f"column {j + 1} holds {len(column)} rows, expected {rows}, as column 1 does"
                )
            if isinstance(column, tuple):
                kinds[top:, j] = TEXT_CODE
                text_columns.append(column)
                continue
            # Exactly a plain one-dimensional array: a subclass, a masked array say, could hide
            # cells behind the storage the copy below would take, as the array results refuse.
            if type(column) is not np.ndarray or column.ndim != 1:
                raise TypeError(f"column {j + 1} is {describe(column)}, which a table cannot hold")
            kinds[top:, j], slots[top:, j] = _table_column(column, top + 1, j + 1)
        # Sheet order: the heading rows, then each body row's texts left to right, which is the
        # transpose of the text columns laid side by side: of every k texts of the body, the j-th
        # is from text column j. One list is made at its full length, the headings assigned to its
        # head and each column whole into its own stride of the rest, and the list becomes the
        # tuple. No array of the texts is built, nothing runs per cell, and no second copy of the
        # body's texts is alive beside the list and the tuple. With no column of text the list is
        # the headings alone, and with no rows each column fills an empty stride: one path for all.
        start, k = top * width, len(text_columns)
        texts = [""] * (start + k * rows)
        texts[:start] = itertools.chain.from_iterable(headings)
        for j, column in enumerate(text_columns):
            texts[start + j :: k] = column
        return cls(kinds, slots, tuple(texts))

    @classmethod
    def cells(cls, rows: Sequence[Sequence[object]]) -> "MixedArray":
        """A rectangle for the way out, cell by cell: nonempty text, booleans and numbers in any
        arrangement, for a small descriptive grid whose columns hold more than one kind, such as
        an instrument's schema with its fields across the columns and a row of booleans among its
        rows of text. Every row holds the same count of cells, at least one, and every cell holds
        a value: a blank or a missing cell is refused here, naming it, before the way out would,
        and so is a whole number beyond what a cell holds exactly, 2^53 either side, as the
        number and table results refuse one, before the float it would become could hide it.

        Each cell is classified once, the one classification the way in uses, so this costs a
        Python step per cell and is for grids of a few hundred cells, never for data: the table
        builder above fills a column at a time and is the builder for anything with rows.
        """
        height = len(rows)
        width = len(rows[0]) if height else 0
        if width == 0:
            raise ValueError("cells need at least one row of at least one cell")
        kinds = np.empty((height, width), dtype=np.uint8)
        slots = np.full((height, width), np.nan)
        texts: list[str] = []
        for r, row in enumerate(rows):
            if len(row) != width:
                raise ValueError(
                    f"row {r + 1} holds {len(row)} cells, expected {width}, as row 1 does"
                )
            for c, cell in enumerate(row):
                kind, number = _classify(cell)
                if kind is Kind.BLANK or kind is Kind.MISSING:
                    raise ValueError(f"cell ({r + 1}, {c + 1}) holds nothing, expected a value")
                if kind is Kind.NUMBER and isinstance(cell, int) and abs(cell) > EXACT:
                    raise ValueError(
                        f"cell ({r + 1}, {c + 1}) is {cell}, beyond what a cell holds exactly"
                    )
                kinds[r, c], slots[r, c] = int(kind), number
                if kind is Kind.TEXT:
                    texts.append(str(cell))
        return cls(kinds, slots, tuple(texts))


@dataclass_transform(frozen_default=True, eq_default=False)
class Table:
    """The schema of a table argument, and the record its function receives.

    A table crosses as two arguments: a row of text holding the headers, then the body as a
    mixed range. A subclass names the columns, one line each, the header name and the column
    type, so the schema is part of the signature and is read once at registration:

        class Trades(Table):
            date: DateColumn
            product: TextColumn
            quantity: NumberColumn
            cleared: BooleanColumn

    A header is to a column what a parameter name is to an argument. On each call the prepared
    path binds every header to its column by name, in any order and without regard to case,
    checks each body column against its declared column type, converts what that type converts,
    and hands the function one of these: a frozen record with one typed attribute per column,
    aligned by row. The headers are consumed by the binding and are not carried.
    """

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        dataclass(frozen=True, eq=False)(cls)


class Missing:
    """An argument the formula left out. Not a blank cell, which is None."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


MISSING: Final = Missing()


class TypeValidationError(Exception):
    """An argument whose type or shape is not what the function declared."""


class _Rejected(Exception):
    """Raised inside an accept rule. Names the cell when the failure is inside a range. For a
    scalar of the expected kind that is still refused, a whole number beyond what a cell holds
    exactly, it says why in place of what was expected."""

    def __init__(
        self,
        cell: tuple[int, int] | None = None,
        value: object = None,
        expected: str = "",
        reason: str = "",
    ) -> None:
        super().__init__()
        self.cell = cell
        self.value = value
        self.expected = expected
        self.reason = reason


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
    """A range as the host sends it: a kind per cell, a number per cell, the text cells in order,
    and which kinds occurred at all.

    numbers holds the value of number and boolean cells and NaN elsewhere. texts holds every
    text cell in sheet order, so the k-th text cell is the k-th TEXT in kinds. seen is what the
    host learned while it walked the range, one bit per kind that occurred, so a range of only
    numbers is known to be one without a look at the kinds; the kinds still name the offending
    cell when a look is needed.
    """

    kinds: NDArray[np.uint8]
    numbers: NDArray[np.float64]
    texts: tuple[str, ...]
    seen: int

    @classmethod
    def from_rows(cls, rows: Sequence[Sequence[object]]) -> "Cells":
        """What the host would send for these cells, from Python values. Tests build ranges here.

        A range is a rectangle, so every row holds as many cells as the first. A row of another
        length is refused, never padded or cut: the cells a short row leaves out would keep
        whatever kind the memory last held, a different range from one run to the next. A blank
        cell is written as None.
        """
        if not rows or not rows[0]:
            raise ValueError("a range has at least one cell; Excel never sends fewer")
        width = len(rows[0])
        kinds = np.empty((len(rows), width), dtype=np.uint8)
        numbers = np.full(kinds.shape, np.nan)
        texts: list[str] = []
        seen = 0
        for r, row in enumerate(rows):
            if len(row) != width:
                raise ValueError(
                    f"row {r + 1} holds {len(row)} cells, expected {width}, as row 1 does"
                )
            for c, cell in enumerate(row):
                kind, number = _classify(cell)
                kinds[r, c] = kind
                numbers[r, c] = number
                seen |= 1 << kind
                if kind is Kind.TEXT:
                    texts.append(cast(str, cell))
        return cls(kinds, numbers, tuple(texts), seen)


# The host's summary of a range: one bit per Kind that occurred. A range of only numbers
# is ONLY_NUMBERS; anything else needs a look at the kinds to name the first bad cell.
ONLY_NUMBERS: Final = 1 << Kind.NUMBER
ONLY_TEXT: Final = 1 << Kind.TEXT
ONLY_BOOLEANS: Final = 1 << Kind.BOOLEAN

# The codes as plain integers, for comparing a whole array of kinds. numpy takes an IntEnum
# member as a strong 64-bit integer and casts the uint8 kinds through a scratch buffer to
# compare them: at ten thousand cells, 7.9 us and 76,792 bytes. A plain int is a weak scalar
# and is compared in place: 1.5 us and the 1-byte mask alone.
NUMBER_CODE: Final = int(Kind.NUMBER)
TEXT_CODE: Final = int(Kind.TEXT)
BOOLEAN_CODE: Final = int(Kind.BOOLEAN)

# The kinds a mixed range may hold, as bits of the host's summary: number, text and boolean.
# NOT_MIXED is every other bit, which today is blank and missing, so seen & NOT_MIXED is set
# exactly when some cell holds no value at all. Written as the complement, so a kind added
# later is refused by the mixed rule until someone allows it here.
MIXED_KINDS: Final = (1 << Kind.NUMBER) | (1 << Kind.TEXT) | (1 << Kind.BOOLEAN)
NOT_MIXED: Final = ~MIXED_KINDS


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


def cells_from_buffers(
    kinds_pointer: int, numbers_pointer: int, rows: int, cols: int, text: str, seen: int
) -> Cells:
    """Copy the host's pinned buffers into Cells. The text cells arrive joined with NUL.

    The host keeps its buffers and fills them again for the next range, so the copies made
    here are all that survives this call. seen is the host's summary of the kinds it met, so
    no look at the kinds is needed here.
    """
    count = rows * cols
    kinds = np.frombuffer((ctypes.c_uint8 * count).from_address(kinds_pointer), dtype=np.uint8)
    numbers = np.frombuffer(
        (ctypes.c_double * count).from_address(numbers_pointer), dtype=np.float64
    )
    texts = tuple(text.split("\0")) if seen & ONLY_TEXT else ()
    return Cells(kinds.reshape(rows, cols).copy(), numbers.reshape(rows, cols).copy(), texts, seen)


def _cell(
    kinds: NDArray[np.uint8], numbers: NDArray[np.float64], texts: tuple[str, ...], i: int
) -> object:
    """The value at flat index i of a range's storage, as it arrived."""
    kind = Kind(int(kinds.flat[i]))
    match kind:
        case Kind.NUMBER:
            return float(numbers.flat[i])
        case Kind.TEXT:
            return texts[int(np.count_nonzero(kinds.ravel()[:i] == TEXT_CODE))]
        case Kind.BOOLEAN:
            return bool(numbers.flat[i])
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
    return _Rejected((r + 1, c + 1), _cell(cells.kinds, cells.numbers, cells.texts, i), expected)


# --- one cell ---------------------------------------------------------------

EXCEL_EPOCH: Final = np.datetime64("1899-12-30", "D")
# The same epoch as a count of days from numpy's own, read off the value above so the two can
# never disagree: a serial plus this count is the day's number in numpy's calendar.
EPOCH_DAYS: Final = int(EXCEL_EPOCH.astype(np.int64))

# A date is a whole serial inside Excel's own calendar. Serial 61 is 1 March
# 1900, the first day on which Excel's serial numbers and the real calendar
# agree: 1 to 60 straddle a 29 February 1900 that never happened. Serial
# 2958465 is 31 December 9999, the last day Excel can show. This is the one
# place the boundary looks at what a value means. 75 passes, as 15 March 1900;
# whether that makes sense is the library's question.
FIRST_SERIAL: Final = 61
LAST_SERIAL: Final = 2958465

# A whole number is one a cell holds exactly: 2^53 is the largest, either side, and the way out
# holds the same line, so whatever a creator keeps can be read back.
EXACT: Final = 2**53


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _Rejected
    return float(value)


def _whole(value: object) -> int:
    """A number with no fraction, within 2^53 either side, in the words of the way out when it
    is not: 1e16 is whole and is refused, as the same number would be refused on its way back."""
    number = _number(value)
    if not number.is_integer():
        raise _Rejected
    if abs(number) > EXACT:
        raise _Rejected(reason="beyond what a cell holds exactly")
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
    """A whole serial inside the calendar, the three tests the range rule makes over every cell:
    a fraction, or a serial outside the calendar either side, is not a date, whatever else it is."""
    serial = _number(value)
    if not serial.is_integer() or not FIRST_SERIAL <= serial <= LAST_SERIAL:
        raise _Rejected
    # One construction from the day's own number; no span of days is built and added.
    return np.datetime64(int(serial) + EPOCH_DAYS, "D")


# --- every cell of a range: no look when the host's summary settles it, one look otherwise ---


def _numbers(value: object) -> NDArray[np.float64]:
    """Every cell a number, kept in sheet order. A scalar is a 1x1 range."""
    if isinstance(value, Cells):
        if value.seen != ONLY_NUMBERS:
            raise _first_bad(value, value.kinds != NUMBER_CODE, "number")
        return value.numbers
    return np.array([[_number(value)]])


def _not_dates(slots: NDArray[np.float64]) -> NDArray[np.bool_]:
    """Flags every slot that is not a whole serial inside the calendar, in one look.

    A text or blank slot holds NaN and fails the first test; a boolean holds 1.0 or 0.0 and
    fails the second. So the slots alone find every cell that is not a date.
    """
    return (slots != np.floor(slots)) | (slots < FIRST_SERIAL) | (slots > LAST_SERIAL)


def _as_days(serials: NDArray[np.float64]) -> NDArray[np.datetime64]:
    """Whole serials as numpy days, converted once."""
    return EXCEL_EPOCH + serials.astype(np.int64).astype("timedelta64[D]")


def _dates(value: object) -> NDArray[np.datetime64]:
    """Every cell a date, kept in sheet order. A scalar is a 1x1 range."""
    if isinstance(value, Cells):
        bad = _not_dates(value.numbers)
        if value.seen != ONLY_NUMBERS:
            bad |= value.kinds != NUMBER_CODE
        if bad.any():
            raise _first_bad(value, bad, "date")
        return _as_days(value.numbers)
    return np.array([[_date(value)]])


def _texts(value: object) -> tuple[str, ...]:
    """Every cell text with a character in it, kept in sheet order. A scalar is one text."""
    if isinstance(value, Cells):
        if value.seen != ONLY_TEXT:
            raise _first_bad(value, value.kinds != TEXT_CODE, "text")
        if "" in value.texts:
            r, c = divmod(value.texts.index(""), value.kinds.shape[1])
            raise _Rejected((r + 1, c + 1), "", "text")
        return value.texts
    return (_text(value),)


def _booleans(value: object) -> NDArray[np.bool_]:
    """Every cell a boolean, kept in sheet order. A scalar is a 1x1 range."""
    if isinstance(value, Cells):
        if value.seen != ONLY_BOOLEANS:
            raise _first_bad(value, value.kinds != BOOLEAN_CODE, "boolean")
        return value.numbers.astype(bool)
    return np.array([[_boolean(value)]])


# --- every cell one of three kinds: the mixed range, which mixes rather than requires ------


def _mixed(value: object) -> MixedArray:
    """Every cell a number, nonempty text or boolean, kept in sheet order. A scalar is a 1x1 range.

    The host's summary settles the kinds in one test. Only an empty text has to be looked for,
    because the summary records which kinds occurred and not whether a text has characters in it.
    """
    if isinstance(value, Cells):
        empty = value.texts.index("") if "" in value.texts else -1
        if value.seen & NOT_MIXED or empty >= 0:
            raise _first_bad(
                value, _bad_mixed(value.kinds, empty), "number, nonempty text or boolean"
            )
        return MixedArray(value.kinds, value.numbers, value.texts)
    return _mixed_scalar(value)


def _bad_mixed(kinds: NDArray[np.uint8], empty: int) -> NDArray[np.bool_]:
    """Every cell a mixed range may not hold, flagged in one array so the earliest one wins.

    The three mixed kinds are the three lowest codes, so one compare flags every other kind.
    An empty text is not a kind, so its cell is flagged here too: its place among the texts is
    turned into its place among the cells, which is what _cell does in reverse to read it back.
    """
    bad = kinds > BOOLEAN_CODE
    if empty >= 0:
        bad.flat[np.flatnonzero(kinds.ravel() == TEXT_CODE)[empty]] = True
    return bad


def _mixed_scalar(value: object) -> MixedArray:
    """One value as the 1x1 range the host would have sent. A blank or empty text is not one."""
    if isinstance(value, bool):
        return _one_cell(BOOLEAN_CODE, 1.0 if value else 0.0, ())
    if isinstance(value, int | float):
        return _one_cell(NUMBER_CODE, float(value), ())
    if isinstance(value, str) and value:
        return _one_cell(TEXT_CODE, np.nan, (value,))
    raise _Rejected


def _one_cell(code: int, number: float, texts: tuple[str, ...]) -> MixedArray:
    """The one-cell storage a promoted scalar needs, laid out as the host lays out a range."""
    return MixedArray(np.array([[code]], dtype=np.uint8), np.array([[number]]), texts)


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


def _field_row(value: object) -> MixedArray:
    """A mixed range of one row: a template's values."""
    mixed = _mixed(value)
    if mixed.shape[0] != 1:
        raise _Rejected(reason="expected one row of field values")
    return mixed


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


# The host delivers a range's text cells as a tuple in sheet order, which for one column or
# one row is the declared representation itself: once the shape is checked, it is handed over
# as it is, with nothing built to carry it.
def _text_column(value: object) -> tuple[str, ...]:
    _one_column(value)
    return _texts(value)


def _text_row(value: object) -> tuple[str, ...]:
    _one_row(value)
    return _texts(value)


def _boolean_column(value: object) -> NDArray[np.bool_]:
    _one_column(value)
    return _booleans(value)[:, 0]


# Every declared type, in the words of the sheet, and the rule that accepts it.
_DECLARED: Final[dict[object, tuple[str, Callable[[object], object]]]] = {
    float: ("number", _number),
    int: ("whole number", _whole),
    str: ("text", _text),
    bool: ("boolean", _boolean),
    Date: ("date", _date),
    NumberArray: ("array of numbers", _numbers),
    NumberColumn: ("column of numbers", _column),
    NumberRow: ("row of numbers", _row),
    DateColumn: ("column of dates", _date_column),
    DateRow: ("row of dates", _date_row),
    TextColumn: ("column of text", _text_column),
    TextRow: ("row of text", _text_row),
    BooleanColumn: ("column of booleans", _boolean_column),
    MixedArray: ("mixed array", _mixed),
}


# --- a table: a header row and a body, bound by name into typed columns -------------------


@dataclass(frozen=True, slots=True)
class _Body:
    """One body under refinement: its storage, the table argument's name for messages, and the
    positions of the columns bound to text, in sheet order, which place each one's texts."""

    mixed: MixedArray
    argument: str
    text_columns: tuple[int, ...]


def _bad_cell(body: _Body, j: int, bad: NDArray[np.bool_], expected: str) -> TypeValidationError:
    """The failure for the first flagged cell of column j, named within the whole body."""
    r = int(bad.argmax())
    mixed = body.mixed
    value = _cell(mixed.kinds, mixed.numeric_slots, mixed.texts, r * mixed.kinds.shape[1] + j)
    return TypeValidationError(
        f"{body.argument} cell ({r + 1}, {j + 1}) is {describe(value)}, expected {expected}"
    )


# One rule per column type. Each takes one look at its column: the kinds settle number, text
# and boolean, and the slots settle a date, as the whole-range rules do. Number columns are
# views of the mixed storage; dates and booleans are converted once; text is a slice of the
# host's tuple.
def _numbers_of(body: _Body, j: int) -> NDArray[np.float64]:
    bad = body.mixed.kinds[:, j] != NUMBER_CODE
    if bad.any():
        raise _bad_cell(body, j, bad, "number")
    return body.mixed.numeric_slots[:, j]


def _dates_of(body: _Body, j: int) -> NDArray[np.datetime64]:
    slots = body.mixed.numeric_slots[:, j]
    bad = _not_dates(slots)
    if bad.any():
        raise _bad_cell(body, j, bad, "date")
    return _as_days(slots)


def _texts_of(body: _Body, j: int) -> tuple[str, ...]:
    bad = body.mixed.kinds[:, j] != TEXT_CODE
    if bad.any():
        raise _bad_cell(body, j, bad, "text")
    # A record is built only when every column has passed, and then every text cell of the body
    # lies in a column bound to text: _bind binds every column, and each other column type
    # refuses a text cell, the number and boolean columns by its kind and the date column by its
    # NaN slot. The texts are in sheet order, so they are the text columns' cells row by row, and
    # this column's are every T-th from its rank among the T. A slice taken while a later column
    # will still refuse is never seen. A column type that accepted text would break this.
    # With one text column the slice is the host's tuple itself, handed over as a TextColumn is.
    columns = body.text_columns
    return body.mixed.texts[columns.index(j) :: len(columns)]


def _booleans_of(body: _Body, j: int) -> NDArray[np.bool_]:
    bad = body.mixed.kinds[:, j] != BOOLEAN_CODE
    if bad.any():
        raise _bad_cell(body, j, bad, "boolean")
    return body.mixed.numeric_slots[:, j].astype(bool)


# Every column type a schema may declare, in the words of the sheet, and the rule for a column.
_COLUMNS: Final[dict[object, tuple[str, Callable[[_Body, int], object]]]] = {
    NumberColumn: ("number", _numbers_of),
    DateColumn: ("date", _dates_of),
    TextColumn: ("text", _texts_of),
    BooleanColumn: ("boolean", _booleans_of),
}

# The column types a table may declare, in the registry's order: public so that a test can hold
# every one of them to the rule the slice in _texts_of rests on.
COLUMN_TYPES: Final = tuple(_COLUMNS)


@dataclass(frozen=True, slots=True)
class Column:
    """One column of a schema: its header name, the name as headers are matched, without regard
    to case, the words of the sheet for its cells, and its rule."""

    name: str
    key: str
    expected: str
    refine: Callable[[_Body, int], object]


@dataclass(frozen=True, slots=True)
class Schema:
    """A table parameter as registration resolved it: the record to build, the names of the
    header-row and table parameters for messages, and the columns, by position and by key."""

    record: type[Table]
    header_row: str
    table: str
    columns: tuple[Column, ...]
    by_key: dict[str, Column]


def _names(columns: tuple[Column, ...], last: str) -> str:
    """The columns' names in declaration order: "date, product, quantity or cleared"."""
    names = [column.name for column in columns]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} {last} {names[-1]}"


def _bind(schema: Schema, headers: tuple[str, ...], cols: int) -> tuple[Column, ...]:
    """The schema's column for each header, in header order.

    The count comes first, then each header in order, unknown or already given, then any name
    of the schema the headers left out; so the earliest offending header wins.
    """
    if len(headers) != cols:
        raise TypeValidationError(
            f"{schema.header_row} has {len(headers)} headers, expected {cols}, "
            f"one per column of {schema.table}"
        )
    found: dict[str, int] = {}
    bound: list[Column] = []
    for j, header in enumerate(headers):
        key = header.casefold()
        column = schema.by_key.get(key)
        if column is None:
            raise TypeValidationError(
                f"{schema.header_row} cell (1, {j + 1}) is {describe(header)}, "
                f"expected one of {_names(schema.columns, 'or')}"
            )
        if key in found:
            raise TypeValidationError(
                f"{schema.header_row} cell (1, {j + 1}) is {describe(header)}, "
                f"already given at cell (1, {found[key] + 1})"
            )
        found[key] = j
        bound.append(column)
    for column in schema.columns:
        if column.key not in found:
            raise TypeValidationError(
                f"{schema.header_row} has no {column.name}, "
                f"expected {_names(schema.columns, 'and')}"
            )
    return tuple(bound)


def _refine(schema: Schema, headers: tuple[str, ...], body: MixedArray) -> Table:
    """Bind the headers, check each column against its type in sheet order, build the record."""
    bound = _bind(schema, headers, body.shape[1])
    text_columns = tuple([j for j, column in enumerate(bound) if column.refine is _texts_of])
    under = _Body(body, schema.table, text_columns)
    return schema.record(**{column.name: column.refine(under, j) for j, column in enumerate(bound)})


# --- a row or rows of an instrument's fields: the schema another argument selects ---------------


@dataclass(frozen=True, slots=True)
class FieldsSchema:
    """A FieldRow or FieldRows parameter as registration resolved it: the names of the header-row
    and body parameters for messages, the position of the parameter whose value selects the
    instrument, and whether the body is one row, a template's, or one or more, a ticket's."""

    header_row: str
    body: str
    selector: int
    one_row: bool


def _handles_of(kind: type[object], expected: str, body: _Body, j: int) -> tuple[object, ...]:
    """A column of handles resolved to the objects they stand for, one per row, in row order:
    each cell text, else named as a text column names a cell that is not, then its text through
    the handle rule, which names the cell as the argument a scalar handle names: a creator's
    failure relayed, text naming no live object, or a handle of another kind. The first bad cell
    down the column is the one named, whichever way it is bad.

    Each cell's text is found at its own place in the body's texts, counted in sheet order over
    the whole body once: the resolution acts on the texts here, before the columns to the right
    have been checked, so the text column's slice, which is right only once every column has
    passed, would hand a text from a number column over as a handle and name a cell that is not
    there. Per cell, since each is its own lookup.
    """
    mixed = body.mixed
    kinds = mixed.kinds
    places = np.cumsum(kinds.ravel() == TEXT_CODE).reshape(kinds.shape) - 1
    not_text = kinds[:, j] != TEXT_CODE
    held: list[object] = []
    for r in range(kinds.shape[0]):
        if not_text[r]:
            raise _bad_cell(body, j, not_text, expected)
        text = mixed.texts[int(places[r, j])]
        held.append(_resolve(kind, expected, f"{body.argument} cell ({r + 1}, {j + 1})", text))
    return tuple(held)


# Each field type's words for a cell and its column rule: the four of the tables, text for a code,
# and a handle column for a field that holds one. _texts_of's slice rests on every column bound to
# text being listed in the body's text columns, so a handle column, text at the seam, is one.
_FIELD_COLUMNS: Final[dict[FieldType, tuple[str, Callable[[_Body, int], object]]]] = {
    FieldType.TEXT: ("text", _texts_of),
    FieldType.CODE: ("text", _texts_of),
    FieldType.NUMBER: ("number", _numbers_of),
    FieldType.DATE: ("date", _dates_of),
    FieldType.HOLIDAY_CALENDAR: (
        "holiday calendar handle",
        partial(_handles_of, HolidayCalendar, "holiday calendar handle"),
    ),
}
_TEXT_FIELDS: Final = frozenset(
    {field_type for field_type, (_, rule) in _FIELD_COLUMNS.items() if rule is _texts_of}
    | {FieldType.HOLIDAY_CALENDAR}
)


def _bind_fields(
    schema: FieldsSchema, definition: Instrument, headers: tuple[str, ...], body: MixedArray
) -> FieldValues:
    """The headers bound to the instrument's fields, exactly, then each column checked against
    its field's type in sheet order, then the record. The order of failures is the table's: the
    count first, then each header in order, unknown or already given, then the cells column by
    column, left to right, the first bad cell named. A header matches a field name as typed,
    case and all, decision 2 of the review: `Quantity` is unknown where `quantity` is a field,
    and the message lists the instrument's fields; no field is required here, since a template
    supplies a subset and the ticket the rest, which the creator checks."""
    cols = body.shape[1]
    if len(headers) != cols:
        raise TypeValidationError(
            f"{schema.header_row} has {len(headers)} headers, expected {cols}, "
            f"one per column of {schema.body}"
        )
    by_name = {field.name: field for field in definition.fields}
    found: dict[str, int] = {}
    for j, header in enumerate(headers):
        if header not in by_name:
            names = ", ".join(by_name)
            raise TypeValidationError(
                f"{schema.header_row} cell (1, {j + 1}) is {describe(header)}, "
                f"expected a field of {definition.name}: {names}"
            )
        if header in found:
            raise TypeValidationError(
                f"{schema.header_row} cell (1, {j + 1}) is {describe(header)}, "
                f"already given at cell (1, {found[header] + 1})"
            )
        found[header] = j
    kinds = [by_name[header].type for header in headers]
    text_columns = tuple([j for j, kind in enumerate(kinds) if kind in _TEXT_FIELDS])
    under = _Body(body, schema.body, text_columns)
    columns = {
        header: _FIELD_COLUMNS[kind][1](under, j)
        for j, (header, kind) in enumerate(zip(headers, kinds, strict=True))
    }
    return FieldValues(definition, body.shape[0], headers, columns)


# --- the way out: every declared result, in the words of the sheet, and the rule that sends it


class _BadResult(Exception):
    """Raised inside a result rule. Carries the message that follows the function's name."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


MAX_TEXT: Final = 32767  # the longest text a cell holds; Excel cuts longer text without a word
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


def _beyond_exact(array: NDArray[Any]) -> NDArray[np.bool_]:
    """Flags every whole number a cell would hold inexactly, beyond 2^53 either side. Two-sided,
    because taking absolute values overflows on the int64 minimum."""
    return (array > EXACT) | (array < -EXACT)


def _table_column(column: NDArray[Any], row: int, col: int) -> tuple[int, NDArray[Any]]:
    """A table column's kind code and what fills its slots, checked before the copy into the
    slots would hide what the rule could no longer see, as the array results check before their
    conversion; a bad cell is named as INDEX counts it, `row` being the first body row."""
    kind = column.dtype.kind
    if kind == "M" and _unit(column) == "D":
        serials, bad, reason = _serials(column)
        if bad is not None:
            raise _BadResult(f"result cell ({row + bad}, {col}) {reason}")
        return NUMBER_CODE, serials
    if kind == "b":
        return BOOLEAN_CODE, column
    if kind in "iu":
        big = _beyond_exact(column)
        if big.any():
            raise _BadResult(
                f"result cell ({row + int(big.argmax())}, {col}) "
                "is beyond what a cell holds exactly"
            )
        return NUMBER_CODE, column
    if kind == "f":
        return NUMBER_CODE, column
    raise TypeError(f"column {col} is {describe(column)}, which a table cannot hold")


def _finite(array: NDArray[Any], value: NDArray[Any], expected: str) -> NDArray[np.float64]:
    """Finite numbers as contiguous float64, or the first bad cell as INDEX counts it."""
    if array.size == 0:
        raise _BadResult(f"returned {describe(value)}, expected {expected} with at least one cell")
    if array.dtype.kind not in "fiu":
        raise _returned(value, expected)
    if array.dtype.kind in "iu":
        big = _beyond_exact(array)
        if big.any():
            r, c = divmod(int(big.argmax()), array.shape[1])
            raise _BadResult(f"result cell ({r + 1}, {c + 1}) is beyond what a cell holds exactly")
    out = np.ascontiguousarray(array, dtype=np.float64)
    finite = np.isfinite(out)
    if not finite.all():
        r, c = divmod(int((~finite).argmax()), out.shape[1])
        raise _BadResult(f"result cell ({r + 1}, {c + 1}) is not a finite number")
    return out


def _array_out(value: object) -> NDArray[np.float64]:
    array = _dimensions(value, 2, "array of numbers")
    return _finite(array, array, "array of numbers")


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


def _place(kinds: NDArray[np.uint8], bad: NDArray[np.bool_]) -> tuple[int, int, int]:
    """The first flagged cell of a rectangle, as INDEX counts, and its flat index."""
    i = int(bad.argmax())
    r, c = divmod(i, kinds.shape[1])
    return r + 1, c + 1, i


def _text_place(kinds: NDArray[np.uint8], k: int) -> tuple[int, int]:
    """The cell of the k-th text, as INDEX counts: its place among the texts turned into its
    place among the cells."""
    i = int(np.flatnonzero(kinds.ravel() == TEXT_CODE)[k])
    r, c = divmod(i, kinds.shape[1])
    return r + 1, c + 1


def _mixed_out(value: object) -> tuple[NDArray[np.uint8], NDArray[np.float64], str]:
    """A rectangle of numbers, text and booleans, checked as the way in checks one and handed
    to the host as the way in hands one over: the kinds, the numbers, and the texts joined
    with NUL, for the host to lay out cell by cell.

    The earliest cell holding no value, a blank, a missing or an empty text, is named as on the
    way in. Then a number cell must hold a finite number and a boolean cell 1.0 or 0.0; no text
    may hold a NUL, since NUL separates the texts on their way across; and every text is at
    most what a cell holds, counted as Excel counts, checked on the joined text in one encode
    and split per text only when the total runs past the limit.
    """
    if type(value) is not MixedArray:
        raise _returned(value, "mixed array")
    kinds, slots, texts = value.kinds, value.numeric_slots, value.texts
    if kinds.size == 0:
        raise _BadResult(f"returned {describe(value)}, expected mixed array with at least one cell")
    text_cells = int(np.count_nonzero(kinds == TEXT_CODE))
    if len(texts) != text_cells:
        raise _BadResult(f"result holds {len(texts)} texts for {text_cells} text cells")
    empty = texts.index("") if "" in texts else -1
    bad = _bad_mixed(kinds, empty)
    if bad.any():
        r, c, i = _place(kinds, bad)
        raise _BadResult(
            f"result cell ({r}, {c}) is {describe(_cell(kinds, slots, texts, i))}, "
            "expected number, nonempty text or boolean"
        )
    unfinished = (kinds == NUMBER_CODE) & ~np.isfinite(slots)
    if unfinished.any():
        r, c, _ = _place(kinds, unfinished)
        raise _BadResult(f"result cell ({r}, {c}) is not a finite number")
    not_flags = (kinds == BOOLEAN_CODE) & (slots != 0.0) & (slots != 1.0)
    if not_flags.any():
        r, c, i = _place(kinds, not_flags)
        raise _BadResult(
            f"result cell ({r}, {c}) is {describe(float(slots.flat[i]))}, expected boolean"
        )
    joined = "\0".join(texts)
    if texts and joined.count("\0") != len(texts) - 1:
        k = next(k for k, text in enumerate(texts) if "\0" in text)  # the price of a failure
        r, c = _text_place(kinds, k)
        raise _BadResult(
            f"result cell ({r}, {c}) is text {texts[k]!r}, expected text with no NUL character"
        )
    encoded = joined.encode("utf-16-le")
    if len(encoded) // 2 - max(len(texts) - 1, 0) > MAX_TEXT:
        # Only now can any one text be too long: split the units at the separators, one look.
        units = np.frombuffer(encoded, dtype=np.uint16)
        separators = np.flatnonzero(units == 0)
        lengths = np.concatenate((separators, [units.size])) - np.concatenate(([0], separators + 1))
        over = lengths > MAX_TEXT
        if over.any():
            k = int(over.argmax())
            r, c = _text_place(kinds, k)
            raise _BadResult(
                f"result cell ({r}, {c}) is text of {int(lengths[k])} characters, "
                f"expected at most {MAX_TEXT}"
            )
    return (
        np.ascontiguousarray(kinds, dtype=np.uint8),
        np.ascontiguousarray(slots, dtype=np.float64),
        joined,
    )


# Every declared result and the rule that converts it; each rule knows the words of the sheet.
_RESULTS: Final[dict[object, Callable[[object], object]]] = {
    float: _number_out,
    int: _whole_out,
    str: _text_out,
    bool: _boolean_out,
    Date: _date_out,
    NumberArray: _array_out,
    NumberColumn: _column_out,
    NumberRow: _row_out,
    DateColumn: _date_column_out,
    DateRow: _date_row_out,
    MixedArray: _mixed_out,
}


# --- a handle: one store, the text, and the two rules that publish and resolve -------------


@dataclass(frozen=True, slots=True)
class _Held:
    """One entry of the store: the kind the seam verified, and a strong reference to the object."""

    kind: type[object]
    value: object


_HANDLES: Final[dict[str, _Held]] = {}
# The process ID of the Excel this Python runs inside, read once: it leads every handle's text,
# so two Excels running at once never publish one text for two objects, and a text from one
# names nothing in the other. The runtime's publication count follows it, shared by every kind
# and never reset while Python runs; a release moves it not at all. Both start again with the
# next Python, so a handle text a workbook saved can equal a later runtime's publication only
# when Windows has reused the process ID and that runtime publishes the same kind, name and
# count: docs/seam/handles.md records the case under the known limitation, accepted by the owner.
_PID: Final = os.getpid()
_published = 0

# The kinds whose text carries an index's name, and where each keeps it. Registration prepares
# the path once, so publishing reads two or three attributes and builds one string; the
# library's records learn nothing of handles, and a kind absent here shows its tag and the
# count alone. docs/seam/handles.md is the page.
_NAMED: Final[dict[type[object], str]] = {
    Index: "name",
    Calendar: "index.name",
    FuturesFixings: "index.name",
    IfercFixings: "index.name",
    GasDailyFixings: "index.name",
    MarketHistory: "calendar.index.name",
    PriceVector: "index_name",
    Market: "market_history.calendar.index.name",
    Trades: "resolved.index.name",
    PreparedTrades: "encoded.terms.index.name",
    TradeResults: "prepared.encoded.terms.index.name",
}


def _is_handle(annotation: object) -> bool:
    return get_origin(annotation) is Handle


def _handle_kind(annotation: object) -> type[object] | None:
    """The class inside Handle[...]: any class but the seam's own, or None when it is not one."""
    kind = get_args(annotation)[0]
    if (
        not isinstance(kind, type)
        or kind in _DECLARED
        or kind in _RESULTS
        or kind is Cells
        or issubclass(kind, Table)
    ):
        return None
    return cast(type[object], kind)


def _words(kind: type[object]) -> str:
    """A kind in the words of the sheet: DiscountCurve is "discount curve"."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", kind.__name__).lower()


def _publish(
    kind: type[object],
    tag: str,
    words: str,
    name: Callable[[object], str] | None,
    value: object,
) -> str:
    """Retain the object a creator returned and hand back the text that stands for it: the
    process ID, the tag, the index's name where the kind carries one, and the runtime's
    publication count.

    A creator that raised never reaches here, so a failure is never published and the count
    does not move; nor does it move for a text longer than a cell holds, refused before
    anything is stored. The process ID, the tag and the name describe the object for a reader
    of the sheet;
    the entry's kind proves it, and nothing ever parses the text.
    """
    global _published
    if type(value) is not kind:
        raise _returned(value, words)
    count = _published + 1
    text = f"{_PID}:{tag}:{count}" if name is None else f"{_PID}:{tag}:{name(value)}:{count}"
    units = len(text.encode("utf-16-le")) // 2  # Excel counts UTF-16 units, as LEN does
    if units > MAX_TEXT:
        raise _BadResult(f"returned handle of {units} characters, expected at most {MAX_TEXT}")
    _published = count
    _HANDLES[text] = _Held(kind, value)
    return text


# A relayed failure: what a consumer's cell shows when the creator it refers to failed. The
# creator's own text comes last, whole, so a consumer of that consumer finds it here and relays
# it unchanged, and a chain of any length shows one text. Quoting the previous text instead
# compounded its escaping, and Excel cut the creator's words after a dozen relays.
_RELAY: Final = re.compile(r"#ERROR \w+: \w+ is the creator's failure, expected [^:]+: (.+)", re.S)


def _resolve(kind: type[object], expected: str, name: str, value: object) -> object:
    """The object a handle stands for, or the failure.

    The text's own faults come first, through the text rule, so a number, a blank, a missing
    argument or an empty text fail in the seam's usual words. Then a creator's failure relayed
    by a reference to its cell, carried whole; then text naming no live object; then an object
    of another kind. A declaration of `object` takes any kind, so that last comparison is the
    one step it skips: whatever the key finds is handed over.
    """
    text = _text(value)
    if text.startswith("#ERROR "):
        relayed = _RELAY.fullmatch(text)
        root = relayed.group(1) if relayed else text
        raise TypeValidationError(f"{name} is the creator's failure, expected {expected}: {root}")
    held = _HANDLES.get(text)
    if held is None:
        raise TypeValidationError(
            f"{name} is text {text!r} naming no live object, expected {expected}"
        )
    if kind is not object and held.kind is not kind:
        raise TypeValidationError(
            f"{name} is {_words(held.kind)} handle {text!r}, expected {expected}"
        )
    return held.value


# --- registration -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    expected: str
    accept: Callable[[object], object]
    # MISSING when the argument is required; None when it may be left out with nothing in its
    # place, which is then what the function receives for a left-out argument and never for a
    # blank cell, since only MISSING takes a default.
    default: object
    label: str  # the name as Excel shows it: in brackets when the argument is optional
    help: str  # what Excel says about it: the words beside the declaration, then the default


@dataclass(frozen=True, slots=True)
class Registered:
    fn: Callable[..., object]
    description: str
    parameters: tuple[Parameter, ...]
    hidden: bool  # absent from Excel's function wizard, still callable by name
    convert: Callable[[object], object]  # the declared result's rule, from _RESULTS
    tables: tuple[tuple[int, Schema], ...]  # each table parameter's position and its schema
    fields: tuple[tuple[int, FieldsSchema], ...]  # each field-values parameter's, likewise
    publishes: bool  # the declared result is a handle, so the host observes the call

    def run(self, *args: object) -> object:
        """The prepared path: validate the arguments, run the function, convert the result.

        Everything that depends on the function alone was resolved at registration: the
        validators, the result's rule, the name. A call supplies the inputs and runs it;
        a failure becomes cell text.
        """
        name = self.fn.__name__
        try:
            return self.convert(self.fn(*_arguments(self, args)))
        except TypeValidationError as failure:
            return f"#ERROR {name}: {failure}"
        except _BadResult as bad:
            return f"#ERROR {name}: {bad.text}"
        except Exception as exc:
            return f"#ERROR {name}: {type(exc).__name__}: {exc}"

    def publish(self, *args: object) -> tuple[object, bool]:
        """The prepared path of a creator, for the host's observed delegate: the cell's value,
        and whether this call published it, told by the count having moved, since the store gains
        an entry exactly when a creator succeeds. Nothing parses the text and nothing looks the
        store up; a failure's text comes back with no, as does a consumer's value."""
        before = _published
        value = self.run(*args)
        return value, _published != before


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
    if isinstance(value, MixedArray):
        rows, cols = value.shape
        return f"{rows}x{cols} mixed array"
    if isinstance(value, np.datetime64):
        day = cast(Any, value)
        return f"{_date_word(_unit(day))} {day}"
    if isinstance(value, np.ndarray | np.generic):
        return _describe_numpy(cast(Any, value))
    return f"a Python {type(value).__name__}"


def _describe_numpy(value: np.ndarray[Any, Any] | np.generic) -> str:
    """A numpy array by its dimensions and kind, or a numpy scalar by the value it holds."""
    if isinstance(value, np.ndarray):
        array = cast(NDArray[Any], value)
        if type(array) is not np.ndarray:
            return f"a numpy {type(array).__name__}"
        return _describe_array(array)
    scalar = cast(Any, value)
    held = _scalar(scalar)  # a numpy boolean or integer, in the words above
    if isinstance(held, np.generic):
        return f"a numpy {type(scalar).__name__}"  # one that .item() cannot unwrap
    return describe(held)


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

# The most Excel shows of a function's or an argument's help. Excel-DNA cuts longer text without
# a word, so registration refuses it instead.
HELP_LIMIT: Final = 253


def _units(text: str) -> int:
    """Characters as Excel counts them, in UTF-16 units, the way LEN does."""
    return len(text.encode("utf-16-le")) // 2


def _authored(function: str, spec: inspect.Parameter) -> tuple[inspect.Parameter, str]:
    """A parameter with its declared type alone, and the help written beside it.

    Annotated[Date, "One date."] declares a date and says so to Excel: the type checker reads
    the type and ignores the words, and registration reads both. Nothing else may sit there.
    """
    if get_origin(spec.annotation) is not Annotated:
        return spec, ""
    parts = cast(tuple[object, ...], get_args(spec.annotation))
    if len(parts) != 2 or not isinstance(parts[1], str):
        raise TypeError(
            f"{function}: {spec.name} declares {spec.annotation!r}, "
            "expected one text beside the type, the argument's help"
        )
    return spec.replace(annotation=parts[0]), parts[1]


def _shown(function: str, name: str, default: object) -> str:
    """A stored default in the words of the sheet: 1 for 1.0, "WTI", TRUE, 2026-05-22."""
    if isinstance(default, np.datetime64):
        return str(cast(Any, default))
    value = _scalar(default)
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(int(value)) if float(value).is_integer() and abs(value) < EXACT else repr(value)
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, np.ndarray) and value.size == 1:
        return _shown(function, name, cast(NDArray[Any], value).flat[0])
    if isinstance(value, tuple):
        texts = cast(tuple[object, ...], value)  # a one-cell range of text, handed over as a tuple
        if len(texts) == 1:
            return _shown(function, name, texts[0])
    raise TypeError(
        f"{function}: {name} defaults to {describe(default)}, which the help cannot show"
    )


def _help(function: str, name: str, authored: str, default: object, hidden: bool) -> str:
    """What Excel says about an argument: the words beside the declaration and, for an optional
    argument, what it takes when omitted. An argument that may be left out with nothing in its
    place has nothing to name, so its sentence stands alone and the brackets on its label say
    it. A function Excel lists explains every argument; a hidden one may say nothing."""
    if not authored:
        if hidden:
            return ""
        raise TypeError(
            f"{function}: {name} has no help; a function Excel lists says what each argument takes"
        )
    if not authored.endswith("."):
        # What registration adds for an optional argument follows this sentence.
        raise TypeError(f"{function}: {name}'s help does not end with a period")
    text = (
        authored
        if default is MISSING or default is None
        else f"{authored} {_shown(function, name, default)} when omitted."
    )
    if _units(text) > HELP_LIMIT:
        raise TypeError(
            f"{function}: {name}'s help is {_units(text)} characters, expected at most {HELP_LIMIT}"
        )
    return text


def _description(function: str, fn: Callable[..., object], hidden: bool) -> str:
    """The docstring, as Excel shows it: its lines joined into one, so a long line may wrap in
    the code without a line break reaching the sheet."""
    text = " ".join((fn.__doc__ or "").split())
    if not text and not hidden:
        raise TypeError(f"{function} has no docstring; a function Excel lists says what it does")
    if _units(text) > HELP_LIMIT:
        raise TypeError(
            f"{function}'s description is {_units(text)} characters, expected at most {HELP_LIMIT}"
        )
    return text


def _is_schema(annotation: object) -> bool:
    """Whether an annotation is a table's schema: a subclass of Table, never Table itself."""
    return (
        isinstance(annotation, type) and issubclass(annotation, Table) and annotation is not Table
    )


def _schema(function: str, specs: Sequence[inspect.Parameter], i: int) -> Schema:
    """A table parameter's schema, resolved once: its columns, and the header row before it."""
    spec = specs[i]
    if i == 0 or specs[i - 1].annotation is not TextRow:
        raise TypeError(
            f"{function}: {spec.name} declares a table with no row of text before it "
            "to hold its headers"
        )
    columns: list[Column] = []
    keys: dict[str, str] = {}
    for field in fields(spec.annotation):
        column = _COLUMNS.get(field.type)
        if column is None:
            raise TypeError(
                f"{function}: {spec.name} column {field.name} declares {field.type!r}, "
                "which is not a column type"
            )
        key = field.name.casefold()
        if key in keys:
            raise TypeError(
                f"{function}: {spec.name} declares columns {keys[key]} and {field.name}, "
                "which are one header"
            )
        keys[key] = field.name
        columns.append(Column(field.name, key, *column))
    if not columns:
        raise TypeError(f"{function}: {spec.name} declares a table with no columns")
    return Schema(
        spec.annotation,
        specs[i - 1].name,
        spec.name,
        tuple(columns),
        {column.key: column for column in columns},
    )


def _fields_form(annotation: object) -> bool | None:
    """Whether an annotation is FieldRow[S], True, or FieldRows[S], False; None for any other."""
    origin = get_origin(annotation)
    if origin is FieldRow:
        return True
    if origin is FieldRows:
        return False
    return None


def _fields_schema(function: str, specs: Sequence[inspect.Parameter], i: int) -> FieldsSchema:
    """A FieldRow or FieldRows parameter's schema, resolved once: the row of text before it that
    holds its headers, as a table has, and the one parameter whose type is the selector inside
    the brackets, text for an instrument named, or a handle of the kind that holds one; a
    function with none or two such parameters cannot say which selects, and is refused."""
    spec = specs[i]
    if i == 0 or specs[i - 1].annotation is not TextRow:
        raise TypeError(
            f"{function}: {spec.name} declares field values with no row of text before it "
            "to hold their headers"
        )
    selector = get_args(spec.annotation)[0]
    if selector is str:
        candidates = [k for k, other in enumerate(specs) if other.annotation is str]
    elif isinstance(selector, type):
        candidates = [
            k
            for k, other in enumerate(specs)
            if _is_handle(other.annotation) and _handle_kind(other.annotation) is selector
        ]
    else:
        raise TypeError(f"{function}: {spec.name} selects by {selector!r}, which is not a type")
    if len(candidates) != 1:
        words = "text" if selector is str else f"{_words(selector)} handle"
        raise TypeError(
            f"{function}: {spec.name} selects its instrument by the {words} parameter, "
            f"of which the function has {len(candidates)}, expected exactly 1"
        )
    one_row = _fields_form(spec.annotation)
    return FieldsSchema(specs[i - 1].name, spec.name, candidates[0], bool(one_row))


def _declared(
    function: str, spec: inspect.Parameter, hidden: bool
) -> tuple[str, Callable[[object], object]] | None:
    """The words and the accept rule an annotation selects, or None when the seam has none."""
    one_row = _fields_form(spec.annotation)
    if one_row is not None:
        # Two arguments that mean something only together, as a table is, bound on the call
        # against a definition a third argument selects: no default could be checked here.
        if spec.default is not inspect.Parameter.empty:
            raise TypeError(f"{function}: {spec.name} declares field values, which take no default")
        if one_row:
            return "one row of field values", _field_row
        return "rows of field values", _mixed
    if spec.annotation is MixedArray and not hidden:
        # Without headers the columns of a mixed range mean nothing, and a function would have to
        # guess by position. A hidden probe keeps the bare range as the seam's own instrument.
        raise TypeError(
            f"{function}: {spec.name} declares MixedArray, which a function Excel lists takes "
            "only as a table, a row of text and a schema"
        )
    if _is_schema(spec.annotation):
        # A table is two arguments that mean something only together, and its columns are checked
        # against the schema on the call, so a default could not be checked at registration as
        # every other default is. None is allowed, and none is wanted.
        if spec.default is not inspect.Parameter.empty:
            raise TypeError(f"{function}: {spec.name} declares a table, which takes no default")
        return "table", _mixed
    if _is_handle(spec.annotation):
        kind = _handle_kind(spec.annotation)
        if kind is None:
            return None
        # A handle resolves against the store, which holds nothing at registration.
        if spec.default is not inspect.Parameter.empty:
            raise TypeError(f"{function}: {spec.name} declares a handle, which takes no default")
        # Handle[object] takes the object behind any handle, so its words name no kind.
        expected = "a handle" if kind is object else f"{_words(kind)} handle"
        return expected, partial(_resolve, kind, expected, spec.name)
    return _DECLARED.get(spec.annotation)


def _left_out(annotation: object) -> object | None:
    """The declared type inside `X | None`, the form of an argument that may be left out with
    nothing in its place; None for any other annotation."""
    args = get_args(annotation)
    if get_origin(annotation) not in (Union, UnionType) or len(args) != 2 or NoneType not in args:
        return None
    return args[0] if args[1] is NoneType else args[1]


def _parameter(function: str, spec: inspect.Parameter, hidden: bool) -> Parameter:
    if spec.kind not in _POSITIONAL:
        raise TypeError(
            f"{function}: {spec.name} is {spec.kind.description}, which the host cannot pass"
        )
    inner = _left_out(spec.annotation)
    if inner is not None and spec.default is not None:
        # The form says the argument may be left out with nothing in its place, and None is
        # that nothing: any other default, or no default, contradicts it.
        what = (
            "no default"
            if spec.default is inspect.Parameter.empty
            else f"defaults to {describe(spec.default)}"
        )
        raise TypeError(
            f"{function}: {spec.name} declares {spec.annotation!r} and {what}, expected None"
        )
    # The type inside the form selects the rule and the words. A handle inside it is declared
    # as if required: the form's None is the argument's absence, not a default the store would
    # have to hold. A table or a bare mixed range inside it is refused as it is on its own,
    # since neither takes a default.
    if inner is None:
        declared = _declared(function, spec, hidden)
    elif _is_handle(inner):
        declared = _declared(
            function, spec.replace(annotation=inner, default=inspect.Parameter.empty), hidden
        )
    else:
        declared = _declared(function, spec.replace(annotation=inner), hidden)
    if declared is None:
        raise TypeError(
            f"{function}: {spec.name} declares {spec.annotation!r}, which the seam cannot receive"
        )
    expected, accept = declared
    default: object = MISSING
    if inner is not None:
        default = None  # never run through the rule, which would call it blank
    elif spec.default is not inspect.Parameter.empty:
        try:
            default = accept(spec.default)
        except _Rejected:
            raise TypeError(
                f"{function}: {spec.name} defaults to {describe(spec.default)}, expected {expected}"
            ) from None
    label = spec.name if default is MISSING else f"[{spec.name}]"
    return Parameter(spec.name, expected, accept, default, label, "")  # the help is added last


def _result(function: str, annotation: object) -> Callable[[object], object]:
    if annotation is inspect.Signature.empty:
        raise TypeError(f"{function} declares no result; a worksheet function returns something")
    if annotation is None:
        raise TypeError(
            f"{function} declares that it returns nothing; "
            "a worksheet function returns something or fails"
        )
    convert = _RESULTS.get(annotation)
    if convert is None and _is_handle(annotation):
        kind = _handle_kind(annotation)
        if kind is object:
            # A store entry of kind "any" could never be told apart, and no typed consumer
            # could take it: Handle[object] is a parameter's declaration only.
            raise TypeError(
                f"{function} declares Handle[object] as its result; a creator names what it makes"
            )
        if kind is not None:
            words = _words(kind)
            path = _NAMED.get(kind)
            name = None if path is None else attrgetter(path)
            return partial(_publish, kind, words.replace(" ", "_"), words, name)
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
    declared = tuple(_authored(name, spec) for spec in signature.parameters.values())
    specs = tuple(spec for spec, _ in declared)
    parameters = tuple(_parameter(name, spec, hidden) for spec in specs)
    tables = tuple(
        (i, _schema(name, specs, i)) for i, spec in enumerate(specs) if _is_schema(spec.annotation)
    )
    field_values = tuple(
        (i, _fields_schema(name, specs, i))
        for i, spec in enumerate(specs)
        if _fields_form(spec.annotation) is not None
    )
    convert = _result(name, signature.return_annotation)
    # What Excel is told comes last, once the declaration itself has passed.
    parameters = tuple(
        replace(p, help=_help(name, p.name, authored, p.default, hidden))
        for p, (_, authored) in zip(parameters, declared, strict=True)
    )
    description = _description(name, fn, hidden)
    publishes = _is_handle(signature.return_annotation)
    _FUNCTIONS[name] = Registered(
        fn, description, parameters, hidden, convert, tables, field_values, publishes
    )
    return fn


def excel_function[F: Callable[..., object]](fn: F) -> F:
    """Register a worksheet function that Excel lists in its function wizard."""
    return register(fn, hidden=False)


def function_specs() -> list[tuple[str, str, list[tuple[str, str]], bool, bool]]:
    """Name, description, each argument's label and help, whether hidden, and whether it creates
    a handle, for every registered function: what the host registers with Excel, the last
    choosing the observed path for a creator."""
    return [
        (
            name,
            registered.description,
            [(p.label, p.help) for p in registered.parameters],
            registered.hidden,
            registered.publishes,
        )
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
            why = rejected.reason or f"expected {parameter.expected}"
            raise TypeValidationError(f"{parameter.name} is {describe(value)}, {why}") from None
        r, c = rejected.cell
        raise TypeValidationError(
            f"{parameter.name} cell ({r}, {c}) is {describe(rejected.value)}, "
            f"expected {rejected.expected}"
        ) from None


def _arguments(registered: Registered, args: Sequence[object]) -> list[object]:
    """Every argument checked alone, left to right; then each table bound to its header row;
    then each row or rows of field values bound to the instrument their selector names, the
    selector read once the arguments have passed, as the review's decision 11 orders it: the
    arguments in signature order, the instrument, the width, the headers, the cells."""
    if len(args) != len(registered.parameters):
        raise TypeValidationError(
            f"expected {len(registered.parameters)} arguments, got {len(args)}"
        )
    values = [_validate(p, value) for p, value in zip(registered.parameters, args, strict=True)]
    for i, schema in registered.tables:
        headers, body = cast(tuple[str, ...], values[i - 1]), cast(MixedArray, values[i])
        values[i] = _refine(schema, headers, body)
    for i, fields_schema in registered.fields:
        definition = selected(values[fields_schema.selector])
        headers, body = cast(tuple[str, ...], values[i - 1]), cast(MixedArray, values[i])
        values[i] = _bind_fields(fields_schema, definition, headers, body)
    return values


def entry(name: str) -> Callable[..., object]:
    """The prepared path of one registered function, for the host to fetch once and keep."""
    return _FUNCTIONS[name].run


def publisher(name: str) -> Callable[..., tuple[object, bool]]:
    """A creator's prepared path for the host's observed delegate, fetched once and kept: the
    value and whether the call published."""
    return _FUNCTIONS[name].publish


def release(text: str) -> bool:
    """Lets one publication go, by its whole text, when Excel has disconnected the last creator
    subscribed to it: the entry leaves the store and its reference with it, and nothing else is
    touched, so an object another live object holds lives on through that object's own
    reference while the text names nothing. Whether an entry went; a text already gone, or never
    published, is nothing to do. The count does not move."""
    return _HANDLES.pop(text, None) is not None


def live_handles() -> tuple[int, int]:
    """The store's live count and the bytes of prices the live price vectors hold, for the host's
    status function and the lifetime tests: a diagnostic read, never part of a call."""
    prices = sum(
        cast(PriceVector, held.value).prices.nbytes
        for held in _HANDLES.values()
        if held.kind is PriceVector
    )
    return len(_HANDLES), prices


def call(name: str, args: Sequence[object]) -> object:
    """The prepared path reached by name, for callers that hold no entry: the tests."""
    return _FUNCTIONS[name].run(*args)


def publish(name: str, args: Sequence[object]) -> tuple[object, bool]:
    """A creator's observed path reached by name, for the tests: the value and whether it
    published."""
    return _FUNCTIONS[name].publish(*args)


# --- the bridge's own worksheet function; the probes live in probes.py --------


@excel_function
def Ping() -> str:
    """Confirm which goosedove Excel is running."""
    try:
        release = version("goosedove")
    except PackageNotFoundError:
        release = "source checkout"
    return f"goosedove {release} from {goosedove.__file__}"
