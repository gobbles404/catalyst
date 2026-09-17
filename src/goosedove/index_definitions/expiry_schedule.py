"""An expiry schedule: the contract months of one index, each contract's code, the day its future
expires, for an index that has options, the day its option expires, and, for an index whose
settles are published, the day each contract's settle is published.
docs/library/index-definitions/expiry-schedule.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class ExpirySchedule:
    """Codes and dates aligned by position, the dates read-only: codes[i], future_expiry[i],
    option_expiry[i] and publication_date[i] describe one contract. The codes are as the desk
    typed them, in the order given; option_expiry is None for an index that has no options, and
    publication_date is None for one whose settles are not published on a day of their own."""

    codes: tuple[str, ...]
    future_expiry: NDArray[np.datetime64]
    option_expiry: NDArray[np.datetime64] | None
    publication_date: NDArray[np.datetime64] | None


def expiry_schedule(
    codes: tuple[str, ...],
    future_expiry: NDArray[np.datetime64],
    option_expiry: NDArray[np.datetime64] | None,
    publication_date: NDArray[np.datetime64] | None,
) -> ExpirySchedule:
    """The one way to make an ExpirySchedule: its one rule of meaning, that the columns line up,
    checked once, the futures first, then the options, then the publication dates.

    Each date column is copied and then frozen, so the schedule owns its data: a Python caller
    keeps whatever it passed, and a later change to an input never changes a schedule. The codes
    are the seam's tuple, kept as they are. A column not given is kept as None.
    """
    count = len(codes)
    return ExpirySchedule(
        codes,
        _one_per_code("future_expiry", future_expiry, count),
        None if option_expiry is None else _one_per_code("option_expiry", option_expiry, count),
        None
        if publication_date is None
        else _one_per_code("publication_date", publication_date, count),
    )


def _one_per_code(name: str, dates: NDArray[np.datetime64], count: int) -> NDArray[np.datetime64]:
    """The column copied and frozen, once it holds one date per code."""
    if dates.size != count:
        have = f"{dates.size} {'date' if dates.size == 1 else 'dates'}"
        raise ValueError(f"{name} has {have}, expected {count}, one per future_code")
    days = np.array(dates, dtype="datetime64[D]")
    days.setflags(write=False)
    return days
