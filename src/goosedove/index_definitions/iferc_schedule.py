"""An IFERC schedule: the contract months of one index settled on Inside FERC's monthly index,
each month's code and the day its index is published, kept as given.
docs/library/index-definitions/iferc-schedule.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class IfercSchedule:
    """Codes and dates aligned by position, the dates read-only: codes[i] and publication_date[i]
    describe one contract month, the code labelling the delivery month the index is for and the
    date the publisher's, the day the index for that month prints, the one day the month is
    observed on and, since iferc-publication-payment-anchor.md, the day its payment counts from.
    The codes are as the desk typed them, in the order given, and the dates as given."""

    codes: tuple[str, ...]
    publication_date: NDArray[np.datetime64]


def iferc_schedule(
    codes: tuple[str, ...], publication_date: NDArray[np.datetime64]
) -> IfercSchedule:
    """The one way to make an IfercSchedule: its one rule of meaning, that the column lines up
    with the codes, checked once.

    The date column is copied and then frozen, so the schedule owns its data: a Python caller
    keeps whatever it passed, and a later change to an input never changes a schedule. The codes
    are the seam's tuple, kept as they are. Nothing else is checked: each code once and the
    publication days increasing are the calendar's rules, checked when a calendar is made over
    an index holding this schedule; each fixing's code one of its months is the IFERC fixings'
    rule; what a code means is no reader's rule, since no reader needs it.
    """
    return IfercSchedule(codes, _one_per_code("publication_date", publication_date, len(codes)))


def _one_per_code(name: str, dates: NDArray[np.datetime64], count: int) -> NDArray[np.datetime64]:
    """The column copied and frozen, once it holds one date per code."""
    if dates.size != count:
        have = f"{dates.size} {'date' if dates.size == 1 else 'dates'}"
        raise ValueError(f"{name} has {have}, expected {count}, one per contract_code")
    days = np.array(dates, dtype="datetime64[D]")
    days.setflags(write=False)
    return days
