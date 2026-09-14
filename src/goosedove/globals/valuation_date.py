"""A valuation date: the calendar day, and the progress through it, at which a calculation is
evaluated. docs/library/globals/valuation-date.md is the page."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class ValuationDate:
    """A calendar day and the fraction of it elapsed, kept exactly as supplied.

    (2026-09-11, 1.0) is the end of Friday and is not the same record as (2026-09-12, 0.0).
    """

    as_of: np.datetime64
    day_fraction_elapsed: float


def valuation_date(as_of: np.datetime64, day_fraction_elapsed: float) -> ValuationDate:
    """The one way to make a ValuationDate: the fraction is checked once, here, and never again.

    NaN and the infinities fail the same comparison, so one line holds both rules of the page.
    """
    if not 0.0 <= day_fraction_elapsed <= 1.0:
        raise ValueError(
            f"day_fraction_elapsed is number {day_fraction_elapsed!r}, "
            "expected a number from 0 to 1"
        )
    return ValuationDate(as_of, day_fraction_elapsed)
