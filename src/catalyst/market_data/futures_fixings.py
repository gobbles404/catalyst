"""Futures fixings: the settlement prices of one index on each day it fixed, date beside settles,
as the desk keeps them, the newest at the top, one row for every business day of its market from
the last row's day to the first row's, a column for each nearby contract the desk keeps a series
of, the prompt's first, and the index they are the fixings of.
docs/library/market-data/futures-fixings.md is the page."""

from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray

from catalyst.index_definitions.index import Index
from catalyst.index_definitions.kind import Kind, described, with_holiday_calendar

# The days of the week as Python's calendar numbers them, Monday first.
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass(frozen=True, slots=True)
class FuturesFixings:
    """The index whose fixings these are, kept by reference, and dates and settles aligned by
    row, both read-only: dates[i] is one day and settles[i, n] the settle on it of that day's
    nearby n + 1, the contract n places after the prompt in the index's schedule, so that column 0
    is the prompt contract's settle, the first nearby's, and since nearby-selection.md column 1
    the second nearby's where the desk gave one, and so on; one column is a series of the prompt
    alone. A nearby is a position counted afresh each day, and which contract it is that day is
    the calendar's to say, the history reading it there. The dates are the business days of the
    index's market from the first to the last, every one and no other, increasing: the sheet
    gives the series newest first, and it is kept oldest first, the order the history reads it
    in. A settle is any number a cell holds, zero and below included."""

    index: Index
    dates: NDArray[np.datetime64]
    settles: NDArray[np.float64]


def futures_fixings(
    dates: NDArray[np.datetime64],
    settles: NDArray[np.float64],
    index: Index,
) -> FuturesFixings:
    """The one way to make a FuturesFixings: its five rules of meaning, checked once, vectorized,
    in this order, the first failure being the message, then the dates and the settles kept the
    other way up.

    The series is given as the desk keeps it, the newest fixing in the first row, so that a new
    day is a row added at the top. The index is a futures index, since the days are checked
    against a holiday calendar and only a futures index has one. The settles are a grid, one row
    per date and one column per nearby, since nearby-selection.md: the first column the prompt
    contract's settle on each day and each column after it the next nearby's, a grid one column
    wide being the series of the prompt alone, as every series was. One row of settles per date,
    since the seam never compares two ranges and a series is rows. Each date is before the row
    above, which keeps one fixing per day and the newest first; nothing is sorted, so a series
    pasted oldest first fails at its second row, as a date given twice does, and one direction is
    the only one taken. Each date is a business day, Monday to Friday and not a holiday of the
    index's calendar, since an index fixes only when its market is open: a weekend day or a
    holiday in the series is refused, at either end as in the middle. And no business day
    between the last row's date and the first row's is without a fixing, since a gap is a row
    the desk did not paste: with every date a business day and the dates decreasing, the series
    is whole exactly when the business days from the last row's date up to the first row's
    number one fewer than the rows, one numpy count of two dates, and the business day before
    each date is found only to name the first one missing. The two end dates bound the check,
    so nothing is asked for after the first row's date or before the last row's, and a holiday
    outside them changes nothing. The holidays are read as numpy reads them: a day listed twice
    counts once, and a day listed on a weekend adds nothing.

    Which contract a column's settle is of on a day is not read here: the fixings hold positions,
    and the market history, which has the calendar, holds each to a listed contract.

    The rules run on the rows as the sheet gave them, a column of days, datetime64[D], and a
    grid of numbers, as the seam hands them over and as a Python caller passes them, so each
    message names the sheet's own row, the first row of the column being row 1, and within a rule
    the first row from the top that breaks it; a rule earlier in the order is reported before a
    later one, whichever row each is on. Then the dates and the grid are copied from the last
    row to the first and frozen: one copy each, as before, and what is kept runs oldest first,
    each date beside its own row of settles, the order the market history reads. The fixings own
    their data, so a Python caller keeps whatever it passed and a later change to an input never
    changes a fixing; the index is kept by reference, the one the desk paired the series with.
    """
    if index.kind is not Kind.FUTURES:
        raise ValueError(f"index is {described(index.kind, 'index')}, expected a futures index")
    holidays = with_holiday_calendar(index.holiday_calendar).holiday  # a futures index has one
    rows = settles.shape[0]
    if rows != dates.size:
        have = f"{rows} {'row' if rows == 1 else 'rows'}"
        raise ValueError(f"settle has {have}, expected {dates.size}, one per date")
    # The rules run on the column as the sheet gave it, the newest first, nothing copied yet.
    unordered = dates[1:] >= dates[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # dates[k + 1] is the first date not before the row above
        raise ValueError(
            f"date row {k + 2} is {dates[k + 1]}, expected a date before row {k + 1}'s {dates[k]}"
        )
    calendar = np.busdaycalendar(holidays=holidays)
    closed = ~np.is_busday(dates, busdaycal=calendar)
    if closed.any():
        k = int(closed.argmax())  # dates[k] is the first weekend day or holiday from the top
        weekday = WEEKDAYS[date.fromisoformat(str(dates[k])).weekday()]
        reason = weekday if weekday in ("Saturday", "Sunday") else "holiday"
        raise ValueError(f"date row {k + 1} is {dates[k]}, a {reason}, expected a business day")
    # Every date a business day and the dates decreasing, the rows but the first are that many
    # business days from the last row's date up to the first row's, so the series is whole
    # exactly when those business days number one fewer than the rows: one np.busday_count of
    # the two end dates. The ends are taken as slices, the last row and the first, so a series
    # of one row asks the same question, no days counted against none expected, and a series of
    # no rows asks it of nothing: one path, with no case for either. The business day before
    # each date is made only when one is missing, to name the first.
    short = np.busday_count(dates[-1:], dates[:1], busdaycal=calendar) != dates.size - 1
    if short.any():
        preceding = np.busday_offset(dates[:-1], -1, busdaycal=calendar)
        skipped = preceding != dates[1:]
        k = int(skipped.argmax())  # preceding[k] is the first business day without a fixing
        raise ValueError(
            f"date row {k + 2} is {dates[k + 1]}, expected {preceding[k]}, "
            f"the business day before row {k + 1}'s {dates[k]}"
        )
    # The one copy of each, read from the last row back: oldest first, and contiguous, a row of
    # settles beside its day.
    days = np.array(dates[::-1], dtype="datetime64[D]")
    prices = np.array(settles[::-1], dtype=np.float64)
    days.setflags(write=False)
    prices.setflags(write=False)
    return FuturesFixings(index, days, prices)
