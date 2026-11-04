"""The rules of the cashflow instrument's own fields, cashflow-instrument.md, which a template's
one value and a ticket's column share: an amount is a finite number, zero and fractions included,
the whole payment in whole units of the currency; and the currency is USD exactly, the one
currency this version books, one per batch, CENT a scale of the dollar and no currency, so that
an amount is never read as cents. A rule names the value in the caller's words for its place,
the field in a template and the field and the row in a ticket."""

from collections.abc import Callable
from typing import Final

import numpy as np
from numpy.typing import NDArray

CURRENCY: Final = "USD"


def finite_amounts(amounts: NDArray[np.float64], where: Callable[[int], str]) -> None:
    """Each amount a finite number, the first that is not refused in the caller's words."""
    unfinished = ~np.isfinite(amounts)
    if unfinished.any():
        k = int(unfinished.argmax())
        raise ValueError(f"{where(k)} is {float(amounts[k])!r}, expected a finite amount")


def currency_of(where: str, text: str) -> str:
    """The currency as typed, USD exactly: `usd`, `CENT` and every other text refused by name."""
    if text != CURRENCY:
        raise ValueError(
            f"{where} is {text!r}, expected {CURRENCY}, the one currency this version books"
        )
    return text
