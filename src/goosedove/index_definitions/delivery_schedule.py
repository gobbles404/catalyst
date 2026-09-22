"""A delivery schedule: the contract codes of one reference index and the first and last day
each contract delivers, both days included, kept as given.
docs/library/index-definitions/delivery-schedule.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class DeliverySchedule:
    """Codes and dates aligned by position, the dates read-only: codes[i], delivery_start[i] and
    delivery_end[i] describe one contract, the code labelling the reference period and the two
    dates its first and last day of delivery, both included, so equal dates are a period of one
    day. The codes are as the desk typed them, in the order given, and the dates as given."""

    codes: tuple[str, ...]
    delivery_start: NDArray[np.datetime64]
    delivery_end: NDArray[np.datetime64]


def delivery_schedule(
    codes: tuple[str, ...],
    delivery_start: NDArray[np.datetime64],
    delivery_end: NDArray[np.datetime64],
) -> DeliverySchedule:
    """The one way to make a DeliverySchedule: three rules of meaning, checked once, in this
    order, the first failure being the message.

    The columns line up, the starts first and then the ends, one date per code, since the seam
    never compares two columns. And no period ends before it starts: each end is on or after its
    start, the first row that is not being named, counted as the sheet counts rows, one
    comparison over the two columns and no walk. Each date column is copied and then frozen, so
    the schedule owns its data: a Python caller keeps whatever it passed, and a later change to
    an input never changes a schedule. The codes are the seam's tuple, kept as they are. Nothing
    else is checked: whether codes repeat, whether periods follow one another, overlap or leave
    gaps, and what a code means are a reader's rules, written when the reader is.
    """
    count = len(codes)
    starts = _one_per_code("delivery_start", delivery_start, count)
    ends = _one_per_code("delivery_end", delivery_end, count)
    reversed_ = ends < starts
    if reversed_.any():
        k = int(reversed_.argmax())  # the first period that ends before it starts
        raise ValueError(
            f"delivery_end row {k + 1} is {ends[k]}, "
            f"expected a date on or after row {k + 1}'s delivery_start {starts[k]}"
        )
    return DeliverySchedule(codes, starts, ends)


def _one_per_code(name: str, dates: NDArray[np.datetime64], count: int) -> NDArray[np.datetime64]:
    """The column copied and frozen, once it holds one date per code."""
    if dates.size != count:
        have = f"{dates.size} {'date' if dates.size == 1 else 'dates'}"
        raise ValueError(f"{name} has {have}, expected {count}, one per contract_code")
    days = np.array(dates, dtype="datetime64[D]")
    days.setflags(write=False)
    return days
