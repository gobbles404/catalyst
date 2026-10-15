"""The encoded batch prepared against one market history: which slots have fixed and at what
settle, which payment groups have settled, what remains live and the exposure to each live
reference, and the risk that no tick changes, the price sensitivity in the settlement currency,
the delta in lots of the index's reporting lot by contract and the same lots by observation day,
calendar month and calendar year, the three views _ReportDelta selects among. One record per
history; a tick reads it and makes nothing of it again. docs/library/trades/kernel.md is the
page."""

from dataclasses import dataclass
from enum import Enum
from typing import assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market_history import MarketHistory
from goosedove.trades.encoding import Encoded

PREPARED_SLOTS = "prepared_slots"  # slots placed on the calendar and told live from fixed
FIXINGS_READ = "fixings_read"  # settles read off the history, one per fixed slot


@dataclass(frozen=True, slots=True)
class PreparedTrades:
    """The encoding and the history, by reference, and what the two make together, read-only.

    Per slot, aligned with the encoding's slots: is_fixed[s], whether the slot's day is on the
    fixed side of the valuation date, so its price is the history's settle on that day, else a
    quote; dated_live_exposure[s], the slot's exposure where it is live and zero where it has
    fixed, a contribution of nothing rather than a price of nothing, the settlement currency per
    unit of quote price; dated_live_lots[s], the same exposure counted in lots of the index's
    reporting lot, the exposure over the lot's coefficient. Per payment group, aligned
    with the encoding's groups, a contract paying on two days being two of them: set_amount[g],
    the sum over the group's fixed slots of exposure times settle; is_settled[g], whether every
    slot of the group has fixed and it pays on or before the valuation date, so its amount is
    modeled as cash.

    Then the live side for the tick: live_slot, the positions of the live slots on the dated axis;
    live_references, the schedule rows of the distinct contracts those slots reference, in the
    schedule's order, which the market takes to answer their quotes; reference_of_live_slot, each
    live slot's place among them, so that one quote per reference is gathered onto the slots.
    And three sums: offset_unsettled and set_unsettled, the entry-price offsets and set amounts
    of the groups not yet settled, which the tick adds to the live amount for the mark; and cash,
    the whole amounts of the settled groups, offset and set together, moved out of the mark on
    the day they pay and never discounted. And the risk, which no tick changes:
    price_sensitivity[r], the live exposure summed by reference over the batch's whole axis, the
    encoding's references, zero where every slot of a reference has fixed, the settlement
    currency the mark moves for a move of one unit of quote price in that contract; lot_delta[r],
    the same sensitivity over the reporting lot's coefficient, the batch's exposure still to
    price in lots of that specification, signed and fractional, a fully live lot one and a lot
    half of whose observation weight has fixed a half; lot_delta_total, their sum; and since #166
    the same lots by time, daily_lots[d] the live lots summed onto the encoding's observation
    days, monthly_lots[m] those summed onto its calendar months and yearly_lots[y] onto its
    calendar years, the three views _ReportDelta selects among, a bucket's lots zero once its
    days have fixed and its row kept; every one of them checked finite before the record is
    made; the result shares them."""

    encoded: Encoded
    history: MarketHistory
    is_fixed: NDArray[np.bool_]
    dated_live_exposure: NDArray[np.float64]
    dated_live_lots: NDArray[np.float64]
    set_amount: NDArray[np.float64]
    is_settled: NDArray[np.bool_]
    live_slot: NDArray[np.intp]
    live_references: NDArray[np.intp]
    reference_of_live_slot: NDArray[np.intp]
    offset_unsettled: float
    set_unsettled: float
    cash: float
    price_sensitivity: NDArray[np.float64]
    lot_delta: NDArray[np.float64]
    lot_delta_total: float
    daily_lots: NDArray[np.float64]
    monthly_lots: NDArray[np.float64]
    yearly_lots: NDArray[np.float64]


class Bucket(Enum):
    """What a delta report sums the live lots by: the observation day, the calendar month it
    falls in or the calendar year, _ReportDelta's three choices, a quarter none of them."""

    DAY = "day"
    MONTH = "month"
    YEAR = "year"


def bucketed(
    prepared: PreparedTrades, bucket: Bucket
) -> tuple[NDArray[np.datetime64], NDArray[np.float64]]:
    """One of the three retained views by reference, its bucket starts and its lots, the
    encoding's axis and the preparation's vector: nothing summed, sorted or converted here."""
    encoded = prepared.encoded
    match bucket:
        case Bucket.DAY:
            return encoded.days, prepared.daily_lots
        case Bucket.MONTH:
            return encoded.months, prepared.monthly_lots
        case Bucket.YEAR:
            return encoded.years, prepared.yearly_lots
        case _:
            assert_never(bucket)


def _the_slot_rows(encoded: Encoded, calendar: Calendar) -> NDArray[np.intp]:
    """Each slot's row of the calendar, by the kind of schedule the terms hold. On a futures
    schedule the day's offset from the calendar's first day, one subtraction, a slot before it
    refused by name: the first contract only bounds the calendar and nothing prices its days. On
    an IFERC schedule, since #167, the row whose publication day is the slot's, one searchsorted
    over the calendar's days, every slot's day being a publication day by the encoding's rule and
    the first month a month like any other, nothing bounding it."""
    match encoded.terms.schedule:
        case FuturesSchedule():
            slot_rows = (encoded.slot_date - calendar.dates[0]).astype(np.intp)
            if (slot_rows < 0).any():
                s = int((slot_rows < 0).argmax())
                raise ValueError(
                    f"{encoded.slot_trade(s)} observes {encoded.slot_date[s]}, before the "
                    f"calendar begins on {calendar.dates[0]}; the schedule's first contract, "
                    f"{encoded.terms.schedule.codes[0]}, bounds the calendar and nothing "
                    "prices its days"
                )
            return slot_rows
        case IfercSchedule():
            return np.searchsorted(calendar.dates, encoded.slot_date).astype(np.intp)
        case _:
            assert_never(encoded.terms.schedule)


def prepared_trades(
    encoded: Encoded, history: MarketHistory, counter: WorkCounter
) -> PreparedTrades:
    """The one way to make a PreparedTrades: four rules, checked once, in this order, the first
    failure being the message; then the arrays, one pass over the slots and one read per fixed slot.

    The history is over the trades' index, the one object the terms hold, as the history itself
    requires of its fixings; another index of the same name is another index. On a futures index
    each slot's day is a day of the calendar, which runs from the day after the schedule's first
    expiry to its last: the first contract only bounds the calendar, so a slot on or before its
    expiry is refused by name, nothing ever pricing it. On an IFERC index, since #167, each slot's
    day is a month's publication day and its row that month's, found by one search, the first
    month a month like any other. A slot has fixed when the calendar marks its day fixed, which
    is the day after it at the earliest, an observation staying live on its own day as the
    calendar's rule says. A physical fixed_float whose contract has expired, its expiry day marked
    fixed, is refused, naming the trade, the contract, its expiry and the valuation date:
    delivery is not modeled, and nothing is omitted, zeroed, kept in mark or moved to cash in its
    place; the contract's expiry decides, not an earlier observation's fixing. A fixed slot takes
    its settle off the history, the settle on its day, which the history holds for every fixed
    and priced day, and every slot's day is priced, since the encoding refused a closed one
    against the same holiday calendar the history's calendar was built from. A group is settled
    when every slot of it has fixed and its payment day is on or before the valuation date, the
    inclusive cutoff of the pipeline; fixed is not paid, and a contract whose components pay on
    two days is two groups, one of which may be cash while the other is live or unpaid. The risk
    is settled here too, since nothing a tick brings changes it: the live exposure summed by
    reference over the batch's axis, each contract once whatever groups hold it, zero where
    everything has fixed, and that sensitivity and the live exposure of each slot divided by the
    reporting lot's coefficient, the conversion the index resolved once, so that the delta is
    counted in lots of the index's reporting specification whatever words the rows were entered
    in, and no specification is looked up and nothing is converted here or on a tick. Every live
    lot, every lot delta and their total are finite, else the first that is not is refused by its
    slot, its contract or the batch, the fourth rule: a lot small enough, a BTU against quantities
    in the trillions of MMBTU, divides a finite exposure past the largest number once it is counted
    in lots, or two contracts' finite deltas sum past it, and nothing is published that a reader
    would then fail on.

    Work: one slot prepared per slot and one settle read per fixed slot, reported to the
    counter; nothing per component, nothing per observation, nothing per day of the calendar.
    """
    terms = encoded.terms
    calendar = history.calendar
    if calendar.index is not terms.index:
        raise ValueError(
            f"history is over another index, {calendar.index.name!r}, "
            f"expected the trades', {terms.index.name!r}"
        )
    codes = terms.schedule.codes
    slot_rows = _the_slot_rows(encoded, calendar)
    is_fixed = calendar.is_fixed[slot_rows]
    as_of = calendar.valuation_date.as_of
    if encoded.payment_date is None:
        # A physical batch is a futures batch: the kernel refuses a physical IFERC one.
        expiries = cast(FuturesSchedule, terms.schedule).future_expiry[encoded.group_contract]
        expired = calendar.is_fixed[(expiries - calendar.dates[0]).astype(np.intp)]
        if expired.any():
            g = int(expired.argmax())
            k = int((encoded.group_of_component == g).argmax())  # its first component
            raise ValueError(
                f"{terms.named(k)} on {codes[int(encoded.group_contract[g])]} expired "
                f"{expiries[g]}, "
                f"before valuation date {as_of}; "
                "a physical fixed_float after its expiry is not supported"
            )
        is_settled = np.zeros(encoded.group_contract.size, dtype=np.bool_)
    else:
        unfixed = np.bincount(
            encoded.slot_group, weights=~is_fixed, minlength=encoded.group_contract.size
        )
        is_settled = (unfixed == 0) & (encoded.payment_date <= as_of)
    fixed_rows = slot_rows[is_fixed]
    settles = history.fixing_prices[np.searchsorted(history.fixed_rows, fixed_rows)]
    set_of_slot = np.zeros(is_fixed.size)
    set_of_slot[is_fixed] = encoded.slot_exposure[is_fixed] * settles
    set_amount = np.bincount(
        encoded.slot_group, weights=set_of_slot, minlength=encoded.group_contract.size
    )
    is_live = ~is_fixed
    dated_live_exposure = np.where(is_live, encoded.slot_exposure, 0.0)
    live_slot = np.flatnonzero(is_live)
    live_references, reference_of_live_slot = np.unique(
        encoded.slot_reference[live_slot], return_inverse=True
    )
    price_sensitivity = np.bincount(
        encoded.reference_of_slot, weights=dated_live_exposure, minlength=encoded.references.size
    )
    lot = terms.reporting_lot
    with np.errstate(over="ignore"):  # a finite exposure may outrun the largest number in lots
        dated_live_lots = dated_live_exposure / lot.coefficient
        lot_delta = price_sensitivity / lot.coefficient
        lot_delta_total = float(lot_delta.sum())
    words = lot.words
    outrun = ~np.isfinite(dated_live_lots)
    if outrun.any():
        s = int(outrun.argmax())
        raise ValueError(
            f"{encoded.named_slot(s)}, has {float(dated_live_lots[s])!r} live lots, expected a "
            f"finite number of {words}; the exposure in lots outruns the largest number"
        )
    outrun = ~np.isfinite(lot_delta)
    if outrun.any():
        r = int(outrun.argmax())
        raise ValueError(
            f"{codes[int(encoded.references[r])]} has {float(lot_delta[r])!r} of lot delta, "
            f"expected a finite number of {words}; the exposure in lots outruns the largest number"
        )
    if not np.isfinite(lot_delta_total):
        raise ValueError(
            f"the batch has {lot_delta_total!r} of lot delta in all, expected a finite number of "
            f"{words}; the contracts' deltas, each finite, sum past the largest number"
        )
    daily_lots = np.bincount(
        encoded.day_of_slot, weights=dated_live_lots, minlength=encoded.days.size
    )
    monthly_lots = np.bincount(
        encoded.month_of_day, weights=daily_lots, minlength=encoded.months.size
    )
    yearly_lots = np.bincount(
        encoded.year_of_month, weights=monthly_lots, minlength=encoded.years.size
    )
    for label, starts, lots in (
        ("the day", encoded.days, daily_lots),
        ("the month from", encoded.months, monthly_lots),
        ("the year from", encoded.years, yearly_lots),
    ):  # the three views, not the rows: a bucket's sum can outrun what its parts did not
        outrun = ~np.isfinite(lots)
        if outrun.any():
            b = int(outrun.argmax())
            raise ValueError(
                f"{label} {starts[b]} has {float(lots[b])!r} of lot delta in all, expected a "
                f"finite number of {words}; its exposures in lots sum past the largest number"
            )
    unsettled = ~is_settled
    counter.hit(PREPARED_SLOTS, int(is_fixed.size))
    counter.hit(FIXINGS_READ, int(fixed_rows.size))
    arrays = (
        is_fixed,
        dated_live_exposure,
        dated_live_lots,
        set_amount,
        is_settled,
        live_slot,
        live_references,
        reference_of_live_slot,
    )
    for array in (*arrays, price_sensitivity, lot_delta, daily_lots, monthly_lots, yearly_lots):
        array.setflags(write=False)
    return PreparedTrades(
        encoded,
        history,
        *arrays,
        float(encoded.offset_of_group[unsettled].sum()),
        float(set_amount[unsettled].sum()),
        float((encoded.offset_of_group + set_amount)[is_settled].sum()),
        price_sensitivity,
        lot_delta,
        lot_delta_total,
        daily_lots,
        monthly_lots,
        yearly_lots,
    )
