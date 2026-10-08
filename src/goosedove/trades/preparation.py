"""The encoded batch prepared against one market history: which slots have fixed and at what
settle, which payment groups have settled, what remains live and the exposure to each live
reference, and the risk that no tick changes, the price sensitivity in the settlement currency
and the delta in lots of the index's reporting lot. One record per history; a tick reads it and
makes nothing of it again. docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

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
    half of whose observation weight has fixed a half; and lot_delta_total, their sum; the result
    shares them."""

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


def prepared_trades(
    encoded: Encoded, history: MarketHistory, counter: WorkCounter
) -> PreparedTrades:
    """The one way to make a PreparedTrades: three rules, checked once, in this order, the first
    failure being the message; then the arrays, one pass over the slots and one read per fixed slot.

    The history is over the trades' index, the one object the terms hold, as the history itself
    requires of its fixings; another index of the same name is another index. Each slot's day is
    a day of the calendar, which runs from the day after the schedule's first expiry to its last:
    the first contract only bounds the calendar, so a slot on or before its expiry is refused by
    name, nothing ever pricing it. A slot has fixed when the calendar marks its day fixed, which
    is the day after it at the earliest, an observation staying live on its own day as the
    calendar's rule says. A physical future whose contract has expired, its expiry day marked
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
    in, and no specification is looked up and nothing is converted here or on a tick.

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
    slot_rows = (encoded.slot_date - calendar.dates[0]).astype(np.intp)
    if (slot_rows < 0).any():
        s = int((slot_rows < 0).argmax())
        raise ValueError(
            f"{encoded.named_slot(s)}, before the calendar begins; "
            "the schedule's first contract bounds the calendar and nothing prices it"
        )
    is_fixed = calendar.is_fixed[slot_rows]
    as_of = calendar.valuation_date.as_of
    if encoded.payment_date is None:
        expiries = terms.schedule.future_expiry[encoded.group_contract]
        expired = calendar.is_fixed[(expiries - calendar.dates[0]).astype(np.intp)]
        if expired.any():
            g = int(expired.argmax())
            k = int((encoded.group_of_component == g).argmax())  # its first component
            raise ValueError(
                f"{terms.named(k)} on {codes[int(encoded.group_contract[g])]} expired "
                f"{expiries[g]}, "
                f"before valuation date {as_of}; "
                "a physical future after its expiry is not supported"
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
    per_lot = terms.reporting_lot.coefficient
    dated_live_lots = dated_live_exposure / per_lot
    live_slot = np.flatnonzero(is_live)
    live_references, reference_of_live_slot = np.unique(
        encoded.slot_reference[live_slot], return_inverse=True
    )
    price_sensitivity = np.bincount(
        encoded.reference_of_slot, weights=dated_live_exposure, minlength=encoded.references.size
    )
    lot_delta = price_sensitivity / per_lot
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
    for array in (*arrays, price_sensitivity, lot_delta):
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
        float(lot_delta.sum()),
    )
