"""An IFERC schedule: the contract months of one index settled on Inside FERC's monthly index,
each month's code, the day its future stops trading and the day its index is published, kept as
given. docs/library/index-definitions/iferc-schedule.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class IfercSchedule:
    """Codes and dates aligned by position, the dates read-only: codes[i], last_trading_date[i]
    and publication_date[i] describe one contract month, the code labelling the delivery month
    the index is for, the first date the exchange's, the day the future on that month stops
    trading, and the second the publisher's, the day the index for that month prints. The codes
    are as the desk typed them, in the order given, and the dates as given."""

    codes: tuple[str, ...]
    last_trading_date: NDArray[np.datetime64]
    publication_date: NDArray[np.datetime64]


def iferc_schedule(
    codes: tuple[str, ...],
    last_trading_date: NDArray[np.datetime64],
    publication_date: NDArray[np.datetime64],
) -> IfercSchedule:
    """The one way to make an IfercSchedule: its one rule of meaning, that the columns line up,
    checked once, the last trading dates first and then the publication dates.

    Each date column is copied and then frozen, so the schedule owns its data: a Python caller
    keeps whatever it passed, and a later change to an input never changes a schedule. The codes
    are the seam's tuple, kept as they are. Nothing else is checked: each code once and the
    publication days increasing are the calendar's rules, checked when a calendar is made over
    an index holding this schedule; each fixing's code one of its months is the IFERC fixings'
    rule; whether a month's index prints after its future stops trading and what a code means
    are no reader's rule, since no reader needs them.
    """
    count = len(codes)
    return IfercSchedule(
        codes,
        _one_per_code("last_trading_date", last_trading_date, count),
        _one_per_code("publication_date", publication_date, count),
    )


def _one_per_code(name: str, dates: NDArray[np.datetime64], count: int) -> NDArray[np.datetime64]:
    """The column copied and frozen, once it holds one date per code."""
    if dates.size != count:
        have = f"{dates.size} {'date' if dates.size == 1 else 'dates'}"
        raise ValueError(f"{name} has {have}, expected {count}, one per contract_code")
    days = np.array(dates, dtype="datetime64[D]")
    days.setflags(write=False)
    return days
