"""The batch prepared against one market history: which of its inputs have fixed and at what
final price, which have been paid under the modeled settlement rule, and the exposure to each
input still live, summed once for the batch so that a tick multiplies and adds and does nothing
else. The history carries the valuation date; a new history, a fixing arrived or corrected or
the date rolled, is a new preparation from the same encoding, never a patch on the old.
docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market_history import MarketHistory
from goosedove.trades.encoding import Encoded

PREPARED_INPUTS = "prepared_inputs"  # inputs placed as live, fixed or settled
FIXINGS_READ = "fixings_read"  # final prices read off the history, one per fixed input


@dataclass(frozen=True, slots=True)
class Prepared:
    """The encoding and the history, by reference, and what the two make together, read-only.
    Per input, aligned with the encoding's inputs: is_live[m], whether the contract's expiry day
    is still on the unfixed side of the valuation date, so its price is a quote; is_settled[m],
    whether it has fixed and pays on or before the valuation date, so its amount is modeled as
    cash; set_amount[m], the exposure times the final price where the input has fixed and zero
    where it is live, a contribution of nothing rather than a price of nothing. Then the live
    side for the tick: live_contracts, the schedule rows of the live inputs in the schedule's
    order, which the market takes to answer their quotes, and live_exposure beside them. And
    three sums: offset_unsettled and set_unsettled, the entry-price offsets and set amounts of
    the inputs not yet settled, which the tick adds to the live amount for the mark; and cash,
    the whole amounts of the settled inputs, offset and set together, moved out of the mark on the
    day they pay and never discounted. And the risk, which no tick changes: delta[m], the exposure
    where the input is live and zero where it has fixed, over the whole axis, and delta_total,
    their sum, the change for a common move of one in every contract; the result shares them."""

    encoded: Encoded
    history: MarketHistory
    is_live: NDArray[np.bool_]
    is_settled: NDArray[np.bool_]
    set_amount: NDArray[np.float64]
    live_contracts: NDArray[np.intp]
    live_exposure: NDArray[np.float64]
    offset_unsettled: float
    set_unsettled: float
    cash: float
    delta: NDArray[np.float64]
    delta_total: float


def prepared(encoded: Encoded, history: MarketHistory, counter: WorkCounter) -> Prepared:
    """The one way to make a Prepared: four rules, checked once, in this order, the first failure
    being the message; then the arrays, one pass over the inputs and one read per fixed input.

    The history is over the trades' index, the one object the terms hold, as the history itself
    requires of its fixings; another index of the same name is another index. Each input's expiry
    is a day of the calendar, which runs from the day after the schedule's first expiry to its
    last: the first contract only bounds the calendar, so a trade on it is refused by name,
    nothing ever pricing it. An input has fixed when the calendar marks its expiry day fixed,
    which is the day after the expiry at the earliest, the contract staying live on its expiry
    day as the calendar's rule says. A physical future that has fixed is refused, naming the
    trade, the contract, its expiry and the valuation date: delivery is not modeled, and nothing
    is omitted, zeroed, kept in mark or moved to cash in its place. A financial future that has
    fixed takes its final price off the history, the settle on its expiry day, which the history
    holds for every fixed and priced day; an expiry on a day the calendar does not price, a
    weekend or a holiday of the schedule's own making, has no settle and is refused by name. It
    is settled when it has fixed and its payment day is on or before the valuation date, the
    inclusive cutoff of the pipeline; fixed is not paid. Delta is settled here too, since nothing
    a tick brings changes it: the exposure on the live inputs, zero on the fixed.

    Work: one input prepared per input and one fixing read per fixed input, reported to the
    counter; nothing per component, nothing per day of the calendar.
    """
    terms = encoded.terms
    calendar = history.calendar
    if calendar.index is not terms.index:
        raise ValueError(
            f"history is over another index, {calendar.index.name!r}, "
            f"expected the trades', {terms.index.name!r}"
        )
    codes = terms.schedule.codes
    expiries = terms.schedule.future_expiry[encoded.inputs]
    expiry_rows = (expiries - calendar.dates[0]).astype(np.intp)
    if (expiry_rows < 0).any():
        m = int((expiry_rows < 0).argmax())
        raise ValueError(
            f"{codes[int(encoded.inputs[m])]} expires {expiries[m]}, before the calendar begins; "
            "the schedule's first contract bounds the calendar and nothing prices it"
        )
    is_fixed = calendar.is_fixed[expiry_rows]
    as_of = calendar.valuation_date.as_of
    if encoded.payment_date is None:
        if is_fixed.any():
            m = int(is_fixed.argmax())
            k = int((encoded.input_of_component == m).argmax())  # its first component
            raise ValueError(
                f"{terms.named(k)} on {codes[int(encoded.inputs[m])]} expired {expiries[m]}, "
                f"before valuation date {as_of}; "
                "a physical future after its expiry is not supported"
            )
        is_settled = np.zeros(is_fixed.size, dtype=np.bool_)
    else:
        is_settled = is_fixed & (encoded.payment_date <= as_of)
    unpriced = is_fixed & ~calendar.is_priced[expiry_rows]
    if unpriced.any():
        m = int(unpriced.argmax())
        raise ValueError(
            f"{codes[int(encoded.inputs[m])]} expires {expiries[m]}, a day its calendar does not "
            "price; no final price exists"
        )
    set_amount = np.zeros(is_fixed.size)
    fixed_expiry_rows = expiry_rows[is_fixed]
    finals = history.fixing_prices[np.searchsorted(history.fixed_rows, fixed_expiry_rows)]
    set_amount[is_fixed] = encoded.exposure[is_fixed] * finals
    is_live = ~is_fixed
    live_contracts = encoded.inputs[is_live]
    live_exposure = encoded.exposure[is_live]
    unsettled = ~is_settled
    delta = np.where(is_live, encoded.exposure, 0.0)
    counter.hit(PREPARED_INPUTS, int(is_fixed.size))
    counter.hit(FIXINGS_READ, int(fixed_expiry_rows.size))
    for array in (is_live, is_settled, set_amount, live_contracts, live_exposure, delta):
        array.setflags(write=False)
    return Prepared(
        encoded,
        history,
        is_live,
        is_settled,
        set_amount,
        live_contracts,
        live_exposure,
        float(encoded.offset_of_input[unsettled].sum()),
        float(set_amount[unsettled].sum()),
        float((encoded.offset_of_input + set_amount)[is_settled].sum()),
        delta,
        float(delta.sum()),
    )
