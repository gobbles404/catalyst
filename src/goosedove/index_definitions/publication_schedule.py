"""A publication schedule: the contract codes of one reference index and the day each contract's
reference price is published, kept as given.
docs/library/index-definitions/publication-schedule.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class PublicationSchedule:
    """Codes and dates aligned by position, the dates read-only: codes[i] and publication_date[i]
    describe one contract, the code labelling the reference period, a month for a monthly index.
    The codes are as the desk typed them, in the order given, and the dates as given."""

    codes: tuple[str, ...]
    publication_date: NDArray[np.datetime64]


def publication_schedule(
    codes: tuple[str, ...], publication_date: NDArray[np.datetime64]
) -> PublicationSchedule:
    """The one way to make a PublicationSchedule: its one rule of meaning, that the columns line
    up, checked once.

    The dates are copied and then frozen, so the schedule owns its data: a Python caller keeps
    whatever it passed, and a later change to an input never changes a schedule. The codes are
    the seam's tuple, kept as they are. Nothing else is checked: whether codes repeat, whether
    dates increase and what a code means are a reader's rules, written when the reader is.
    """
    count = len(codes)
    if publication_date.size != count:
        have = f"{publication_date.size} {'date' if publication_date.size == 1 else 'dates'}"
        raise ValueError(f"publication_date has {have}, expected {count}, one per contract_code")
    days = np.array(publication_date, dtype="datetime64[D]")
    days.setflags(write=False)
    return PublicationSchedule(codes, days)
