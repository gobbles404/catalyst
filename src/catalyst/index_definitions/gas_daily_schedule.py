"""A Gas Daily schedule: the contract months of one index settled on Gas Daily's daily midpoint,
each month's code and the first and last day of gas its price covers, kept as given.
docs/library/index-definitions/gas-daily-schedule.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class GasDailySchedule:
    """Codes and dates aligned by position, the dates read-only: codes[i], first_date[i] and
    last_date[i] describe one contract month, the code labelling the month the gas flows in and
    the two dates its first and last calendar days, typed by the desk rather than read from the
    code. The codes are as the desk typed them, in the order given, and the dates as given."""

    codes: tuple[str, ...]
    first_date: NDArray[np.datetime64]
    last_date: NDArray[np.datetime64]


def gas_daily_schedule(
    codes: tuple[str, ...],
    first_date: NDArray[np.datetime64],
    last_date: NDArray[np.datetime64],
) -> GasDailySchedule:
    """The one way to make a GasDailySchedule: its one rule of meaning, that the columns line
    up, checked once, the first dates first and then the last dates.

    Each date column is copied and then frozen, so the schedule owns its data: a Python caller
    keeps whatever it passed, and a later change to an input never changes a schedule. The codes
    are the seam's tuple, kept as they are. Nothing else is checked: each code once, each
    month's last day on or after its first and the months following one another are the
    calendar's rules, checked when a calendar is made over an index holding this schedule;
    whether the two dates are a calendar month's and what a code means are no reader's rule,
    since no reader needs them.
    """
    count = len(codes)
    return GasDailySchedule(
        codes,
        _one_per_code("first_date", first_date, count),
        _one_per_code("last_date", last_date, count),
    )


def _one_per_code(name: str, dates: NDArray[np.datetime64], count: int) -> NDArray[np.datetime64]:
    """The column copied and frozen, once it holds one date per code."""
    if dates.size != count:
        have = f"{dates.size} {'date' if dates.size == 1 else 'dates'}"
        raise ValueError(f"{name} has {have}, expected {count}, one per contract_code")
    days = np.array(dates, dtype="datetime64[D]")
    days.setflags(write=False)
    return days
