"""Futures fixings: the settlement price of one index on each day it fixed, date beside settle, as
the desk keeps them, one for every business day of its market from the first to the last, and
the index they are the fixings of. docs/library/market-data/futures-fixings.md is the page."""

from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import Kind, described, with_holiday_calendar

# The days of the week as Python's calendar numbers them, Monday first.
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass(frozen=True, slots=True)
class FuturesFixings:
    """The index whose fixings these are, kept by reference, and dates and settles aligned by
    position, both read-only: dates[i] and settles[i] describe one fixing. The dates are the
    business days of the index's market from the first to the last, every one and no other,
    increasing; a settle is any number a cell holds, zero and below included."""

    index: Index
    dates: NDArray[np.datetime64]
    settles: NDArray[np.float64]


def futures_fixings(
    dates: NDArray[np.datetime64],
    settles: NDArray[np.float64],
    index: Index,
) -> FuturesFixings:
    """The one way to make a FuturesFixings: its five rules of meaning, checked once, vectorized,
    in this order, the first failure being the message.

    The index is a futures index, since the days are checked against a holiday calendar and only
    a futures index has one. One settle per date, since the seam never compares two columns and
    a series is rows. Each date is after the row above, which keeps one fixing per day in the
    order a reader searches; nothing is sorted, so a series pasted newest first fails at its
    second row, and the desk sorts it. Each date is a business day, Monday to Friday and not a
    holiday of the index's calendar, since an index fixes only when its market is open: a
    weekend day or a holiday in the series is refused, at either end as in the middle. And no
    business day between the first date and the last is without a fixing, since a gap is a row
    the desk did not paste: with every date a business day and the dates increasing, the series
    is whole exactly when each date is the business day after the one above, one numpy call
    over the column. The first and last dates bound the check, so nothing is asked for before
    the first or after the last, and a holiday outside them changes nothing. The holidays are
    read as numpy reads them: a day listed twice counts once, and a day listed on a weekend adds
    nothing. Both columns are copied and then frozen, so the fixings own their data: a Python
    caller keeps whatever it passed, and a later change to an input never changes a fixing; the
    index is kept by reference, the one the desk paired the series with. Rows count as the sheet
    counts them, the first row of the column being row 1.
    """
    if index.kind is not Kind.FUTURES:
        raise ValueError(f"index is {described(index.kind, 'index')}, expected a futures index")
    holidays = with_holiday_calendar(index.holiday_calendar).holiday  # a futures index has one
    if settles.size != dates.size:
        have = f"{settles.size} {'settle' if settles.size == 1 else 'settles'}"
        raise ValueError(f"settle has {have}, expected {dates.size}, one per date")
    days = np.array(dates, dtype="datetime64[D]")
    unordered = days[1:] <= days[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # days[k + 1] is the first date not after the one before it
        raise ValueError(
            f"date row {k + 2} is {days[k + 1]}, expected a date after row {k + 1}'s {days[k]}"
        )
    calendar = np.busdaycalendar(holidays=holidays)
    closed = ~np.is_busday(days, busdaycal=calendar)
    if closed.any():
        k = int(closed.argmax())  # days[k] is the first weekend day or holiday
        weekday = WEEKDAYS[date.fromisoformat(str(days[k])).weekday()]
        reason = weekday if weekday in ("Saturday", "Sunday") else "holiday"
        raise ValueError(f"date row {k + 1} is {days[k]}, a {reason}, expected a business day")
    following = np.busday_offset(days[:-1], 1, busdaycal=calendar)
    skipped = following != days[1:]
    if skipped.any():
        k = int(skipped.argmax())  # following[k] is the first business day without a fixing
        raise ValueError(
            f"date row {k + 2} is {days[k + 1]}, expected {following[k]}, "
            f"the business day after row {k + 1}'s {days[k]}"
        )
    prices = np.array(settles, dtype=np.float64)
    days.setflags(write=False)
    prices.setflags(write=False)
    return FuturesFixings(index, days, prices)
