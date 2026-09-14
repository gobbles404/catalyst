"""The seam's probes: worksheet functions that exist only to test the host and the bridge.

Each probe proves one thing the host can tell apart, or one rule the bridge applies
to what the host could not, and does no work beyond proving it, so its counts are
the seam's counts. Where a rule needs a control to be read against, the control is a
probe too, differing from it in the one thing being measured and nothing else. Together
they are the knobs a capacity run turns: how many calls, how many cells in, how
many cells out. They are registered hidden, so Excel's function wizard never lists
them, and they ship in the build everyone loads. They stay as long as the seam does.
"""

from collections.abc import Callable
from typing import Annotated

import numpy as np

from goosedove.excel.bridge import (
    BooleanColumn,
    DateColumn,
    MixedArray,
    NumberArray,
    NumberColumn,
    NumberRow,
    Table,
    TextColumn,
    TextRow,
    register,
)


def probe[F: Callable[..., object]](fn: F) -> F:
    """Register a probe: a worksheet function hidden from the function wizard."""
    return register(fn, hidden=True)


@probe
def Zero() -> float:
    """Probe: zero arguments and no work; the floor every other count is read against."""
    return 0.0


@probe
def Add(a: float, b: float) -> float:
    """Probe: a number in and a number out; the reference for the cost of one call."""
    return a + b


# The one probe with help beside its parameters: it shows what Excel says of an optional
# argument, [factor] and "1 when omitted", derived from the default and never written twice.
@probe
def Times(
    x: Annotated[float, "One number to multiply."],
    factor: Annotated[float, "One multiplier."] = 1.0,
) -> float:
    """Probe: only a missing argument takes the default; a blank cell fails."""
    return x * factor


@probe
def EchoText(label: str) -> str:
    """Probe: text in and the same text out."""
    return label


@probe
def EchoBoolean(flag: bool) -> bool:
    """Probe: TRUE arrives as a boolean, not as the number 1, and comes back as a boolean."""
    return flag


@probe
def SumArray(values: NumberArray) -> float:
    """Probe: a range of any shape arrives as cells; the sum proves every cell did."""
    return float(values.sum())


@probe
def CountArray(values: NumberArray) -> int:
    """Probe: the same count over a range of numbers, the control CountMixed is read against."""
    rows, cols = values.shape
    return rows * cols


@probe
def CountMixed(values: MixedArray) -> int:
    """Probe: a range of numbers, text and booleans together arrives as one record of its own."""
    rows, cols = values.shape
    return rows * cols


class Trades(Table):
    """The probe's schema: one column of each type a table may declare, laid out as a trade is."""

    date: DateColumn
    product: TextColumn
    quantity: NumberColumn
    cleared: BooleanColumn


@probe
def SumQuantity(header_row: TextRow, trades: Trades) -> float:
    """Probe: a header row and a body arrive as one table of typed columns; one sum proves it."""
    return float(trades.quantity.sum())


@probe
def Dot(a: NumberColumn, b: NumberColumn) -> float:
    """Probe: two ranges in one call arrive as two ranges."""
    return float(a @ b)


@probe
def EchoColumn(values: NumberColumn) -> NumberColumn:
    """Probe: a column in and the same column out, spilled down."""
    return NumberColumn(values)


@probe
def EchoRow(values: NumberRow) -> NumberRow:
    """Probe: a row in and the same row out, spilled across."""
    return NumberRow(values)


@probe
def RowSums(values: NumberArray) -> NumberColumn:
    """Probe: a grid in, one number per row out, spilled down: the shape of pricing every row."""
    return NumberColumn(values.sum(axis=1))


@probe
def Grid(rows: int, cols: int) -> NumberArray:
    """Probe: an array out, rows by cols, counting 1, 2, 3 across then down."""
    if rows < 1 or cols < 1:
        raise ValueError(f"a grid needs at least one row and one column, not {rows} by {cols}")
    return NumberArray(np.arange(1.0, rows * cols + 1).reshape(rows, cols))


@probe
def Fail() -> float:
    """Probe: an error in the function body reaches the cell with its type and message."""
    raise ValueError("as asked")
