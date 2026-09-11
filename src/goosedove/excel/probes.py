"""The seam's probes: worksheet functions that exist only to test the host and the bridge.

Each probe proves one thing the host can tell apart, on the way in or the way out,
and does no work beyond proving it, so its counts are the seam's counts. Together
they are the knobs a capacity run turns: how many calls, how many cells in, how
many cells out. They are registered hidden, so Excel's function wizard never lists
them, and they ship in the build everyone loads. They stay as long as the seam does.
"""

from collections.abc import Callable

import numpy as np

from goosedove.excel.bridge import Array, Column, Row, register


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


@probe
def Times(x: float, factor: float = 1.0) -> float:
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
def SumArray(values: Array) -> float:
    """Probe: a range of any shape arrives as cells; the sum proves every cell did."""
    return float(values.sum())


@probe
def Dot(a: Column, b: Column) -> float:
    """Probe: two ranges in one call arrive as two ranges."""
    return float(a @ b)


@probe
def EchoColumn(values: Column) -> Column:
    """Probe: a column in and the same column out, spilled down."""
    return Column(values)


@probe
def EchoRow(values: Row) -> Row:
    """Probe: a row in and the same row out, spilled across."""
    return Row(values)


@probe
def RowSums(values: Array) -> Column:
    """Probe: a grid in, one number per row out, spilled down: the shape of pricing every row."""
    return Column(values.sum(axis=1))


@probe
def Grid(rows: int, cols: int) -> Array:
    """Probe: a block out, rows by cols, counting 1, 2, 3 across then down."""
    if rows < 1 or cols < 1:
        raise ValueError(f"a grid needs at least one row and one column, not {rows} by {cols}")
    return Array(np.arange(1.0, rows * cols + 1).reshape(rows, cols))


@probe
def Fail() -> float:
    """Probe: an error in the function body reaches the cell with its type and message."""
    raise ValueError("as asked")
