"""Contract prices interpolated between a few anchors on an index's monthly schedule: every
month from the first anchor's through the last's, inclusive, each with the index's futures
expiry, and a price on the straight line between the adjacent anchors' prices weighted by the
calendar days between their expiries, the library's one rule for interpolation,
docs/library/conventions.md under What holds everywhere, with the expiries as the coordinates.
Static: the index's definition and the anchors alone, no market, history, valuation date or
prompt, and no price-unit conversion, the prices being in the index's quote convention as
supplied. docs/library/utilities/interpolate-contracts.md is the page."""

from dataclasses import dataclass
from typing import Final, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.contract_codes import (
    MONTH_LETTERS,
    month_and_year,
    month_label,
    schedule_months,
)
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import Kind, described
from goosedove.instrumentation.work_counts import WorkCounter

ANCHORS_READ = "anchors_read"  # anchor labels read and paired with their prices, one per row
SCHEDULE_ROWS_READ = "schedule_rows_read"  # the schedule's codes read for their months, every row
MONTHS_GENERATED = "months_generated"  # the months from the first anchor's through the last's
INTERPOLATIONS = "interpolations"  # one straight-line pass over every generated month
ONE_DAY: Final = np.timedelta64(1, "D")


@dataclass(frozen=True, slots=True)
class InterpolatedContracts:
    """The months from the first anchor's through the last's, one row each in contract-month
    order: codes, as the index's schedule spells them; expiries, the schedule's futures expiry of
    each, increasing; and prices, an anchor's own exactly and the straight line between the
    adjacent anchors elsewhere, weighted by the calendar days between the expiries. The two
    arrays are frozen; nothing of the index is copied or changed."""

    codes: tuple[str, ...]
    expiries: NDArray[np.datetime64]
    prices: NDArray[np.float64]


def interpolate_contracts(
    index: Index,
    anchor_contracts: tuple[str, ...],
    anchor_prices: NDArray[np.float64],
    counter: WorkCounter,
) -> InterpolatedContracts:
    """The one way to make InterpolatedContracts: the rules, checked once, in this order, the
    first failure being the message; then one interpolation.

    The index is a futures index, whose schedule has a futures expiry per contract; an IFERC or a
    Gas Daily index is refused by kind rather than given a publication or a flow date. The prices
    are one per anchor and the anchors at least two; each label is a contract code, F26 or f26,
    or the month as CME's feeds spell it, 202601, read whole, no other label; each price is
    finite; the months are distinct, a repeat named by both rows, and increasing by row, never
    reordered. The schedule's months are read once, every row, by the reader the trades'
    resolution uses, which refuses a code that is no month and two rows of one month in its own
    words; every month from the first anchor's through the last's is on the schedule, the first
    missing refused by its month and code; the selected expiries are dates increasing in month
    order, the first pair that is not named with its contracts. Then the prices: numpy's interp
    over day offsets from the first anchor's expiry, the anchors' offsets and prices the line
    and the generated months the points, which the range keeps inside the anchors, so no
    endpoint is repeated and nothing is extrapolated; an anchor keeps its price exactly; each
    price is finite or the first that is not is refused by its contract with the anchors on
    either side. Nothing is rounded.

    Work: one anchor per row, one schedule row per code, one month per month generated and one
    interpolation, reported to the counter; nothing per day between the expiries, no market,
    history or valuation date read, nothing published.
    """
    if index.kind is not Kind.FUTURES:
        raise ValueError(
            f"index is {described(index.kind, 'index')}, expected a futures index, whose schedule "
            "has a futures expiry per contract"
        )
    schedule = cast(FuturesSchedule, index.schedule)  # what the kind said
    anchors = len(anchor_contracts)
    given = int(anchor_prices.size)
    if given != anchors:
        raise ValueError(
            f"anchor_prices has {given} {'price' if given == 1 else 'prices'}, expected {anchors}, "
            "one per anchor contract"
        )
    if anchors < 2:
        raise ValueError(
            f"anchor_contracts has {anchors} {'contract' if anchors == 1 else 'contracts'}, "
            "expected at least two to interpolate between"
        )
    months = _anchor_months(anchor_contracts, anchor_prices)
    counter.hit(ANCHORS_READ, anchors)
    codes = schedule.codes
    month_of_row = schedule_months(schedule)
    counter.hit(SCHEDULE_ROWS_READ, len(codes))
    first, last = int(months[0]), int(months[-1])
    wanted = np.arange(first, last + 1, dtype=np.int64)
    counter.hit(MONTHS_GENERATED, int(wanted.size))
    by_row = np.argsort(month_of_row, kind="stable")
    sorted_months = month_of_row[by_row]
    place = np.searchsorted(sorted_months, wanted)
    found = place < sorted_months.size
    found[found] = sorted_months[place[found]] == wanted[found]
    if not found.all():
        m = int(wanted[int((~found).argmax())])
        raise ValueError(
            f"the index's schedule has no contract for {month_label(m)}, {_code_of(m)}, expected "
            f"every month from {month_label(first)} to {month_label(last)}, the anchors' range"
        )
    rows = by_row[place]
    selected = tuple([codes[int(r)] for r in rows])
    expiries = schedule.future_expiry[rows]
    unset = np.isnat(expiries)
    if unset.any():
        k = int(unset.argmax())
        raise ValueError(
            f"the index's schedule row {int(rows[k]) + 1}, {selected[k]!r}, has no futures expiry "
            "date, expected a date to weight the months by"
        )
    not_after = np.flatnonzero(expiries[1:] <= expiries[:-1])
    if not_after.size:
        k = int(not_after[0])
        raise ValueError(
            f"the futures expiry of {selected[k + 1]!r}, {expiries[k + 1]}, is not after that of "
            f"{selected[k]!r}, {expiries[k]}, expected the expiries of the months from "
            f"{month_label(first)} to {month_label(last)} increasing"
        )
    offsets = np.asarray((expiries - expiries[0]) / ONE_DAY, dtype=np.float64)  # days, exact
    at = months - first  # each anchor's place among the generated months
    with np.errstate(over="ignore", invalid="ignore"):  # the rule below is the judge
        prices = np.interp(offsets, offsets[at], anchor_prices)
    counter.hit(INTERPOLATIONS)
    finite = np.isfinite(prices)
    if not finite.all():
        k = int((~finite).argmax())
        right = int(np.searchsorted(at, k))  # an anchor's own price is finite: k lies between two
        left = right - 1
        raise ValueError(
            f"the price of {selected[k]!r} is {float(prices[k])!r}, expected a finite price; the "
            f"line from row {left + 1}'s {float(anchor_prices[left])!r} to row {right + 1}'s "
            f"{float(anchor_prices[right])!r} outruns the largest number"
        )
    expiries.setflags(write=False)
    prices.setflags(write=False)
    return InterpolatedContracts(selected, expiries, prices)


def _anchor_months(
    anchor_contracts: tuple[str, ...], anchor_prices: NDArray[np.float64]
) -> NDArray[np.int64]:
    """The anchors' months as numpy counts them, one per row, under the rules on the anchors
    alone: each label a code or a CME month, each price finite, the months distinct, a repeat
    named by both rows, and increasing by row, the first row out of order named with the row
    before it; the rows' own order throughout, nothing reordered."""
    anchors = len(anchor_contracts)
    months = np.empty(anchors, dtype=np.int64)
    for i, label in enumerate(anchor_contracts):
        month = _month_of(label)
        if month is None:
            raise ValueError(
                f"anchor_contracts row {i + 1} is {label!r}, expected a contract code such as F26 "
                "or the month as CME spells it, such as 202601"
            )
        months[i] = month
    finite = np.isfinite(anchor_prices)
    if not finite.all():
        i = int((~finite).argmax())
        raise ValueError(
            f"anchor_prices row {i + 1} is {float(anchor_prices[i])!r}, expected a finite price"
        )
    order = np.argsort(months, kind="stable")
    by_month = months[order]
    same = np.flatnonzero(by_month[1:] == by_month[:-1])
    if same.size:
        # The repeat whose later row comes first, in the rows' own order.
        a, b = min([(int(order[k]), int(order[k + 1])) for k in same], key=lambda pair: pair[1])
        raise ValueError(
            f"anchor_contracts rows {a + 1} and {b + 1} are {anchor_contracts[a]!r} and "
            f"{anchor_contracts[b]!r}, both {month_label(months[a])}, expected each month once"
        )
    earlier = np.flatnonzero(months[1:] < months[:-1])
    if earlier.size:
        k = int(earlier[0])
        raise ValueError(
            f"anchor_contracts row {k + 2} is {anchor_contracts[k + 1]!r}, "
            f"{month_label(months[k + 1])}, expected a month after row {k + 1}'s "
            f"{anchor_contracts[k]!r}, {month_label(months[k])}"
        )
    return months


def _month_of(label: str) -> int | None:
    """The month a label names, as numpy counts months, or None: a contract code in either case,
    F26, through the codes' own reading, or the month as CME's feeds spell it, 202601, six digits,
    the year 2000 to 2099 and the month 01 to 12, read whole, nothing trimmed and no other form.
    The six-digit form is this utility's alone; the ticket's code reading is as it was."""
    if len(label) == 6 and label.isascii() and label.isdigit():
        year, month = int(label[:4]), int(label[4:])
        if 2000 <= year <= 2099 and 1 <= month <= 12:
            return (year - 1970) * 12 + month - 1
        return None
    try:
        month, year = month_and_year(label)
    except ValueError:
        return None
    return (year - 1970) * 12 + month - 1


def _code_of(month: int) -> str:
    """The code of a month as numpy counts them, in capitals, the way a missing month is named."""
    years, place = divmod(month, 12)
    return f"{MONTH_LETTERS[place]}{(1970 + years) % 100:02d}"
