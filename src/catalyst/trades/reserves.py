"""The batch's booked reserves: the brokerage the brokered rows' components incur and, on a cleared
route, the clearing every component incurs, each a component's count of its specification times
that specification's rate per lot, summed for the batch once, when the batch is made, since #188
charged only where the booking says so, reserve-fee-applicability.md; since #175 the marketing
reserve each row booked, summed once per row, zero when no row booked one; since cva-reserve.md
the CVA reserve each row booked, a signed amount summed once per row the same way; and the
currency they are in. Static booked amounts in the settlement currency: a fixing, a payment, a
tick or a roll of the valuation date changes none of them, and they enter no mark, cash, delta
or DV01. docs/library/trades/report-reserves.md is the page."""

import math
from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.trades.terms import ResolvedTrades, Route

# Components charged a fee, once per fee they incur, since #188: the brokered rows' components for
# brokerage and every component for clearing on a cleared route, so nothing for a bilateral batch
# without a broker, one per component with one fee and two with both.
RESERVED_FEE_COMPONENTS = "reserved_fee_components"
# Rows whose entered reserve was summed, once per reserve field a row booked: the marketing
# reserve since #175 and the CVA reserve since cva-reserve.md, so the rows once for a batch
# booking one of the two and twice for a batch booking both.
RESERVED_OCCURRENCES = "reserved_occurrences"


@dataclass(frozen=True, slots=True)
class Reserves:
    """The batch's four totals and their currency. brokerage is the sum over the components of the
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
    twice and a row of zero quantity its full amount; 0.0 when neither supplied the field. cva,
    since cva-reserve.md, is the same sum of the cva_reserve each row entered, a credit valuation
    adjustment the desk books as an amount of either sign, so the total carries the rows' signs
    and may be negative; 0.0 when neither supplied the field. currency is the index's settlement
    currency, the conventions' currency_unit, the one every rate and amount is in."""

    brokerage: float
    clearing: float
    marketing: float
    cva: float
    currency: str


def reserves(terms: ResolvedTrades, counter: WorkCounter) -> Reserves:
    """The one way to make Reserves: each fee charged where the booking says so, since #188, the
    amounts of each in one pass over the components it charges, then two rules per fee charged,
    brokerage before clearing, checked once, the first failure being the message; then the two
    entered reserves, marketing before CVA, each the rows' amounts summed once.

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
    and the CVA reserve, since cva-reserve.md, are each the rows' amounts summed once, each amount
    finite by the rule that read it, zero or more for marketing and of either sign for CVA, over
    the occurrences and never the components, so a strip books its amount once; each sum is the
    exact one, the correctly rounded total of the rows' amounts whatever their order and however
    they cancel, refused for the batch only when the total itself passes the largest number in
    either direction; and a batch without the field books 0.0 and sums nothing.

    Work: one fee component per component charged, reported to the counter as
    reserved_fee_components, the brokered components once for brokerage and every component once
    for clearing on a cleared route, so none for a bilateral batch without a broker and twice the
    components for a cleared batch brokered throughout; and one occurrence per occurrence per
    entered reserve the batch books, as reserved_occurrences, the rows once with one of the two
    fields and twice with both; nothing per observation, group or slot, and nothing again at
    preparation, evaluation or reading.
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
    marketing = _summed_once("marketing", terms.marketing_reserve, currency, counter)
    cva = _summed_once("cva", terms.cva_reserve, currency, counter)
    counter.hit(RESERVED_FEE_COMPONENTS, charged)
    return Reserves(brokerage, clearing, marketing, cva, currency)


def _summed_once(
    name: str, amounts: NDArray[np.float64] | None, currency: str, counter: WorkCounter
) -> float:
    """One entered reserve's total: the rows' amounts summed once each, exactly, and the one rule
    the judge, that the total is finite, since amounts each finite by the rule that read them can
    sum past the largest number, in either direction for a signed reserve; refused for the batch
    naming the reserve, never a row, since every row's amount was good. 0.0 and nothing summed
    or counted when the batch has no such field, else the rows reported to the counter as
    reserved_occurrences."""
    if amounts is None:
        return 0.0
    total = _exact_total(amounts)
    if not math.isfinite(total):
        raise ValueError(
            f"the batch has {total!r} of {name} reserve in all, expected a finite amount of "
            f"{currency}; the rows' amounts, each finite, sum past the largest number"
        )
    counter.hit(RESERVED_OCCURRENCES, int(amounts.size))
    return total


def _exact_total(amounts: NDArray[np.float64]) -> float:
    """The amounts' one total, the correctly rounded sum of the finite amounts whatever their order
    and however they cancel, since cva-reserve.md's review: a dollar beside ten thousand trillion
    and its negative is a dollar in whichever row it stands, where a running sum rounds it away or
    keeps it by the order the rows came in. Shewchuk's exact partials, math.fsum, over the amounts
    scaled down by the power of two that is at least their count, one multiplication over the
    rows, exact for every amount above the subnormal range, so that no running sum can pass the
    largest number on the way to a total that does not; and the total scaled back up once, exact
    again, an infinity of its sign when the total itself passes the largest number, so that the
    caller's one rule judges the total and never a step."""
    shift = (int(amounts.size) - 1).bit_length()  # 2 ** shift is at least the count, 0 for one
    return math.fsum(amounts * math.ldexp(1.0, -shift)) * math.ldexp(1.0, shift)


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
