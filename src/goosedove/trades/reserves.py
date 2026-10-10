"""The batch's booked reserves: the brokerage and the clearing each component incurs, its count of
its specification times that specification's rate per lot, summed for the batch once, when the
batch is made, since #175 the marketing reserve each row booked, summed once per row, zero when
no row booked one, and the currency they are in. Static booked amounts in the settlement
currency: a fixing, a payment, a tick or a roll of the valuation
date changes none of them, and they enter no mark, cash, delta or DV01.
docs/library/trades/report-reserves.md is the page."""

from dataclasses import dataclass

import numpy as np

from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.terms import ResolvedTrades

RESERVED_COMPONENTS = "reserved_components"  # components whose brokerage and clearing were booked
RESERVED_OCCURRENCES = "reserved_occurrences"  # rows whose marketing reserve was summed, since #175


@dataclass(frozen=True, slots=True)
class Reserves:
    """The batch's three totals and their currency. brokerage and clearing are the sums over the
    components of each component's count of its specification, the quantity its basis gave it
    taken without its sign, times the specification's rate per lot, the rates as the
    specifications hold them, costs per count of the row: a row named BBL with a lot size of one
    charges per barrel and a row named LOT of a thousand barrels per thousand, no lot size,
    coefficient or quote unit scaling either, and a buy and a sell that net to nothing both
    reserve. marketing, since #175, is the sum over the ticket's rows of the marketing_reserve
    each entered, the template's one value for every row or the ticket's column, counted once
    per row whatever its months, quantity, days or sign, a duplicate row twice and a row of
    zero quantity its full amount; 0.0 when neither supplied the field. currency is the index's
    settlement currency, the conventions' currency_unit, the one every rate and amount is in."""

    brokerage: float
    clearing: float
    marketing: float
    currency: str


def reserves(terms: ResolvedTrades, counter: WorkCounter) -> Reserves:
    """The one way to make Reserves: the amounts in one pass over the components, then two rules per
    category, brokerage before clearing, checked once, the first failure being the message.

    Each component's count is its component quantity without its sign, the entered quantity under
    month and the entered quantity times its covered days under calday, as the terms formed it;
    its rates are its occurrence's specification's, gathered onto the components; the amounts are
    the count times the rate, every component counted, a duplicate occurrence twice and a zero
    quantity as zero, and the totals their sums. Each amount is finite, else the first that is not
    is refused naming the category, the trade and its row, the count and the rate that made it: a
    product past the largest number, or a rate held as NaN or infinity, which the specifications'
    rule of zero or more lets pass, a zero count among them, since nothing here skips a row. Each
    total is finite, else refused for the batch, since amounts each finite can sum past the
    largest number, and nothing is published that a reader would then fail on; the
    multiplications and the sums run with numpy's flags down, the rules being the judge. The
    amounts are not kept: the totals are what the batch books. The marketing reserve, since #175,
    is the rows' amounts summed once, each finite and zero or more by the rule that read them,
    over the occurrences and never the components, so a strip books its amount once; the sum is
    held finite the same way, refused for the batch when finite amounts sum past the largest
    number; and a batch with no marketing field books 0.0 and sums nothing.

    Work: one component per component, reported to the counter as reserved_components, and one
    occurrence per occurrence where a marketing reserve stands, as reserved_occurrences; nothing
    per observation, group or slot, and nothing again at preparation, evaluation or reading.
    """
    specifications = terms.index.specifications
    selection = terms.specification[terms.occurrence]
    counts = np.abs(terms.component_quantity)
    currency = terms.index.conventions.currency_unit
    totals: list[float] = []
    for category, rates in (
        ("brokerage", specifications.brokerage_rates_per_lot),
        ("clearing", specifications.clearing_rates_per_lot),
    ):
        with np.errstate(over="ignore", invalid="ignore"):  # the two rules below are the judge
            amounts = counts * rates[selection]
            total = float(amounts.sum())
        unfinished = ~np.isfinite(amounts)
        if unfinished.any():
            k = int(unfinished.argmax())
            row = int(selection[k])
            raise ValueError(
                f"{category} reserve of {terms.named(k)} is {float(amounts[k])!r}, expected a "
                f"finite amount of {currency}; {float(counts[k])!r} of "
                f"{specifications.names[row]!r} at {float(rates[row])!r} a lot"
            )
        if not np.isfinite(total):
            raise ValueError(
                f"the batch has {total!r} of {category} reserve in all, expected a finite amount "
                f"of {currency}; the components' reserves, each finite, sum past the largest number"
            )
        totals.append(total)
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
    counter.hit(RESERVED_COMPONENTS, int(counts.size))
    return Reserves(totals[0], totals[1], marketing, currency)
