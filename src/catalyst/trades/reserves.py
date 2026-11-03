"""The batch's booked reserves: the brokerage the brokered rows' components incur and, on a cleared
route, the clearing every component incurs, each a component's count of its specification times
that specification's rate per lot, summed for the batch once, when the batch is made, since #188
charged only where the booking says so, reserve-fee-applicability.md; since #175 the marketing
reserve each row booked, summed once per row, zero when no row booked one; and the currency they
are in. Static booked amounts in the settlement currency: a fixing, a payment, a tick or a roll of
the valuation date changes none of them, and they enter no mark, cash, delta or DV01.
docs/library/trades/report-reserves.md is the page."""

from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.terms import ResolvedTrades, Route

# Components charged a fee, once per fee they incur, since #188: the brokered rows' components for
# brokerage and every component for clearing on a cleared route, so nothing for a bilateral batch
# without a broker, one per component with one fee and two with both.
RESERVED_FEE_COMPONENTS = "reserved_fee_components"
RESERVED_OCCURRENCES = "reserved_occurrences"  # rows whose marketing reserve was summed, since #175


@dataclass(frozen=True, slots=True)
class Reserves:
    """The batch's three totals and their currency. brokerage is the sum over the components of the
    rows naming a broker, since #188, of each component's count of its specification, the quantity
    its basis gave it taken without its sign, times the specification's brokerage rate per lot; a
    row whose broker field was not given, or whose text is none in any case, a screen trade,
    charges nothing. clearing is the same sum over every component with the specification's
    clearing rate on a cleared route, and 0.0 on a bilateral one, which has no clearing house to
    pay. The rates are as the specifications hold them, costs per count of the row: a row named
    BBL with a lot size of one charges per barrel and a row named LOT of a thousand barrels per
    thousand, no lot size, coefficient or quote unit scaling either, and a buy and a sell that net
    to nothing both reserve. marketing, since #175, is the sum over the ticket's rows of the
    marketing_reserve each entered, the template's one value for every row or the ticket's
    column, counted once per row whatever its months, quantity, days or sign, a duplicate row
    twice and a row of zero quantity its full amount; 0.0 when neither supplied the field.
    currency is the index's settlement currency, the conventions' currency_unit, the one every
    rate and amount is in."""

    brokerage: float
    clearing: float
    marketing: float
    currency: str


def reserves(terms: ResolvedTrades, counter: WorkCounter) -> Reserves:
    """The one way to make Reserves: each fee charged where the booking says so, since #188, the
    amounts of each in one pass over the components it charges, then two rules per fee charged,
    brokerage before clearing, checked once, the first failure being the message.

    Brokerage charges the components of the rows the terms found brokered, the rows naming a
    broker, and nothing else: a batch without the field, or with none in every row, makes no
    brokerage amount at all, so a brokerage rate the specifications' rule of zero or more lets
    pass as NaN or infinity is never read where no row is brokered. Clearing charges every
    component on a cleared route and none on a bilateral one, the route the batch's own, the
    clearing house a label beside it. Each charged component's count is its component quantity
    without its sign, the entered quantity under month and the entered quantity times its covered
    days under calday, as the terms formed it; its rate is its occurrence's specification's,
    gathered onto the charged components; the amounts are the count times the rate, every charged
    component counted, a duplicate occurrence twice and a zero quantity as zero, and the totals
    their sums. Each amount is finite, else the first that is not is refused naming the fee, the
    trade and its row, the count and the rate that made it: a product past the largest number, or
    a rate held as NaN or infinity, a zero count among them, since nothing here skips a charged
    row. Each total is finite, else refused for the batch, since amounts each finite can sum past
    the largest number, and nothing is published that a reader would then fail on; the
    multiplications and the sums run with numpy's flags down, the rules being the judge. The
    amounts are not kept: the totals are what the batch books. The marketing reserve, since #175,
    is the rows' amounts summed once, each finite and zero or more by the rule that read them,
    over the occurrences and never the components, so a strip books its amount once; the sum is
    held finite the same way, refused for the batch when finite amounts sum past the largest
    number; and a batch with no marketing field books 0.0 and sums nothing.

    Work: one fee component per component charged, reported to the counter as
    reserved_fee_components, the brokered components once for brokerage and every component once
    for clearing on a cleared route, so none for a bilateral batch without a broker and twice the
    components for a cleared batch brokered throughout; and one occurrence per occurrence where a
    marketing reserve stands, as reserved_occurrences; nothing per observation, group or slot, and
    nothing again at preparation, evaluation or reading.
    """
    leg = terms.legs[0]  # the first leg's index charges the fees, two-index-fixed-float.md
    specifications = leg.index.specifications
    selection = leg.specification[terms.occurrence]
    counts = np.abs(terms.component_quantity)
    currency = leg.index.conventions.currency_unit
    charged = 0
    brokerage = 0.0
    brokered = terms.brokered[terms.occurrence]
    if brokered.any():
        positions = np.flatnonzero(brokered)
        brokerage = _charged(
            "brokerage",
            terms,
            positions,
            counts[positions],
            selection[positions],
            specifications.brokerage_rates_per_lot,
            currency,
        )
        charged += int(positions.size)
    match terms.route:
        case Route.CLEARED:
            clearing = _charged(
                "clearing",
                terms,
                None,
                counts,
                selection,
                specifications.clearing_rates_per_lot,
                currency,
            )
            charged += int(counts.size)
        case Route.BILATERAL:
            clearing = 0.0
        case _:
            assert_never(terms.route)
    marketing = 0.0
    if terms.marketing_reserve is not None:
        with np.errstate(over="ignore"):  # the rule below is the judge
            marketing = float(terms.marketing_reserve.sum())
        if not np.isfinite(marketing):
            raise ValueError(
                f"the batch has {marketing!r} of marketing reserve in all, expected a finite "
                f"amount of {currency}; the rows' amounts, each finite, sum past the largest number"
            )
        counter.hit(RESERVED_OCCURRENCES, int(terms.marketing_reserve.size))
    counter.hit(RESERVED_FEE_COMPONENTS, charged)
    return Reserves(brokerage, clearing, marketing, currency)


def _charged(
    fee: str,
    terms: ResolvedTrades,
    positions: NDArray[np.intp] | None,
    counts: NDArray[np.float64],
    rows: NDArray[np.intp],
    rates: NDArray[np.float64],
    currency: str,
) -> float:
    """One fee's total over the components it charges: their counts, the specification rows they
    select and the fee's rates by row, the positions their places among the batch's components
    when they are a selection and None when they are every one. The two rules in order, each
    amount finite, the first that is not named by the fee, the trade and its row, the count and
    the rate, and then the total finite."""
    with np.errstate(over="ignore", invalid="ignore"):  # the two rules below are the judge
        amounts = counts * rates[rows]
        total = float(amounts.sum())
    unfinished = ~np.isfinite(amounts)
    if unfinished.any():
        j = int(unfinished.argmax())
        k = j if positions is None else int(positions[j])
        row = int(rows[j])
        raise ValueError(
            f"{fee} reserve of {terms.named(k)} is {float(amounts[j])!r}, expected a finite "
            f"amount of {currency}; {float(counts[j])!r} of "
            f"{terms.legs[0].index.specifications.names[row]!r} at {float(rates[row])!r} a lot"
        )
    if not np.isfinite(total):
        raise ValueError(
            f"the batch has {total!r} of {fee} reserve in all, expected a finite amount of "
            f"{currency}; the components' reserves, each finite, sum past the largest number"
        )
    return total
