"""The batch's booked reserves: the brokerage and the clearing each component incurs, its count of
its specification times that specification's rate per lot, summed for the batch once, when the
batch is made, with marketing at zero until it is built and the currency they are in. Static
booked amounts in the settlement currency: a fixing, a payment, a tick or a roll of the valuation
date changes none of them, and they enter no mark, cash, delta or DV01.
docs/library/trades/report-reserves.md is the page."""

from dataclasses import dataclass

import numpy as np

from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.terms import ResolvedTrades

RESERVED_COMPONENTS = "reserved_components"  # components whose brokerage and clearing were booked


@dataclass(frozen=True, slots=True)
class Reserves:
    """The batch's three totals and their currency. brokerage and clearing are the sums over the
    components of each component's count of its specification, the quantity its basis gave it
    taken without its sign, times the specification's rate per lot, the rates as the
    specifications hold them, costs per count of the row: a row named BBL with a lot size of one
    charges per barrel and a row named LOT of a thousand barrels per thousand, no lot size,
    coefficient or quote unit scaling either, and a buy and a sell that net to nothing both
    reserve. marketing is 0.0, the amount until the marketing reserve is built after bilateral,
    no field entering it. currency is the index's settlement currency, the conventions'
    currency_unit, the one every rate is in."""

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
    amounts are not kept: the totals are what the batch books.

    Work: one component per component, reported to the counter as reserved_components; nothing per
    observation, group or slot, and nothing again at preparation, evaluation or reading.
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
    counter.hit(RESERVED_COMPONENTS, int(counts.size))
    return Reserves(totals[0], totals[1], 0.0, currency)
