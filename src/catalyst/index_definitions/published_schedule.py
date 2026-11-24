"""A published schedule: the dated prints of one index whose price is a listed set of prints,
each print's date and the contract month it counts toward, the months kept once each and the
prints in the order given. docs/library/index-definitions/published-schedule.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class PublishedSchedule:
    """The months and the prints, the two arrays read-only. codes[m] is one contract month, each
    once, in the order its prints were given, the month axis every reader of a schedule counts
    along, so a month has one forward price however many prints it has. contract[i] is the row of
    codes the i-th print counts toward, never decreasing down the prints, every month holding one
    print or more. publication_date[i] is the date the publisher puts on the i-th print, each
    after the one above: the print's identity, the day it is observed and the day it is fixed
    after. The codes are as the desk typed them and nothing is read out of one; which month a
    print counts toward is the code on its row and never its date."""

    codes: tuple[str, ...]
    contract: NDArray[np.intp]
    publication_date: NDArray[np.datetime64]


def published_schedule(
    contract_code: tuple[str, ...], publication_date: NDArray[np.datetime64]
) -> PublishedSchedule:
    """The one way to make a PublishedSchedule: one row per print, the code of the month it counts
    toward beside its date, three rules of meaning checked once, in this order, the first failure
    being the message; then the months, each print's month and the dates.

    One date per code, since the seam never compares two columns and a schedule is rows. Each
    month's prints stand in consecutive rows: a code repeats down the rows of its month and never
    returns once another has begun, since the months are read off the rows where the code
    changes and a code met a second time would be two months of one name. And each date is after
    the one above, which keeps the prints oldest first and refuses a date listed twice. Nothing
    is sorted, so a schedule pasted newest first fails at its second row. These are the record's
    own rules, checked here and not by a reader, because every reader counts along the months and
    searches the dates: a calendar, the fixings and a trade's prints all take them as given.

    The codes are compared as typed, spelling and case, and no code is read for its month: which
    month a print counts toward is the desk's to say, row by row. The date column is copied and
    then frozen, so the schedule owns its data and a later change to an input changes no
    schedule; the months are the seam's own texts, one kept per month. Rows count as the sheet
    counts them, the first row of a column being row 1. A schedule of no rows is a schedule of no
    months, the calendar's to refuse.

    Work: one comparison down the codes and one down the dates, one sum for each print's month,
    and a look at each month's code, never at each print's, only to name a month given twice.
    """
    count = len(contract_code)
    if publication_date.size != count:
        have = f"{publication_date.size} {'date' if publication_date.size == 1 else 'dates'}"
        raise ValueError(f"publication_date has {have}, expected {count}, one per contract_code")
    typed = np.array(contract_code, dtype=object)
    begins = np.ones(count, dtype=bool)  # whether a row is the first print of its month
    np.not_equal(typed[1:], typed[:-1], out=begins[1:])
    first = begins.nonzero()[0]
    codes: tuple[str, ...] = tuple(typed[first])
    del typed  # the column of codes is read no further, and is not held under the two made next
    if len(set(codes)) != len(codes):
        _each_month_together(codes, first, count)
    days = np.array(publication_date, dtype="datetime64[D]")
    unordered = days[1:] <= days[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # days[k + 1] is the first date not after the one above
        raise ValueError(
            f"publication_date row {k + 2} is {days[k + 1]}, "
            f"expected a date after row {k + 1}'s {days[k]}"
        )
    contract = begins.cumsum(dtype=np.intp)
    contract -= 1
    for column in (contract, days):
        column.setflags(write=False)
    return PublishedSchedule(codes, contract, days)


def _each_month_together(codes: tuple[str, ...], first: NDArray[np.intp], count: int) -> None:
    """Raises for the first month whose code was a month already, naming the row it returns at
    and the row the earlier run of it ended on; reached only when some code is two months."""
    ended: dict[str, int] = {}
    for month, code in enumerate(codes):
        if code in ended:
            raise ValueError(
                f"contract_code row {int(first[month]) + 1} is {code!r}, a month whose prints "
                f"ended at row {ended[code]}, expected each month's prints in consecutive rows"
            )
        ended[code] = int(first[month + 1]) if month + 1 < len(codes) else count
