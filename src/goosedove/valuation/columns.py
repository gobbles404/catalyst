"""What the valuation's builders share: the check that a column holds finite numbers, the copy
that a record keeps frozen, and the word for a count of rows."""

import numpy as np
from numpy.typing import NDArray


def finite(name: str, values: NDArray[np.float64]) -> None:
    """Every value a finite number, the first that is not being named, since a number that is
    not one would come out as an amount that looks like one."""
    bad = ~np.isfinite(values)
    if bad.any():
        i = int(bad.argmax())
        raise ValueError(f"{name} row {i + 1} is {float(values[i])!r}, expected a finite number")


def kept[T: np.generic](column: NDArray[T]) -> NDArray[T]:
    """One copy of the column, frozen: the record owns its data, a caller keeps whatever it
    passed, and nothing changes underneath the record."""
    copy = column.copy()
    copy.setflags(write=False)
    return copy


def frozen[T: np.generic](column: NDArray[T]) -> NDArray[T]:
    """A column the builder made itself, frozen where it is: no copy, since nobody else holds
    it."""
    column.setflags(write=False)
    return column


def rows(count: int) -> str:
    return "row" if count == 1 else "rows"
