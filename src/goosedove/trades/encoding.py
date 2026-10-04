"""The static encoding of a batch: what the resolved terms amount to in numbers before any price
or fixing is known. Each component's signed quantity in the index's quote quantity unit, its
coefficient, the settlement currency it makes per unit of quote price, and its entry-price offset
in the settlement currency; the market inputs the batch consumes, one per contract it holds, in
the schedule's order; and per input the summed quantity, the summed coefficient, the summed
offset and, for a financial settlement, the day it pays. Nothing here changes on a tick, a fixing
or a roll of the valuation date. docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.unit_conversions import UnitConversions
from goosedove.index_definitions.index_conventions import CURRENCY
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.terms import ResolvedTrades

ENCODED_COMPONENTS = "encoded_components"  # components turned into quantities and offsets
ENCODED_INPUTS = "encoded_inputs"  # market inputs named and summed over


@dataclass(frozen=True, slots=True)
class Encoded:
    """The terms, by reference, and the arrays derived from them once, all read-only. Per
    component, aligned with the terms' components: quantity[k], the signed quantity in the
    quote quantity unit, lots times the lot size, converted where the lot unit differs;
    coefficient[k], the settlement currency the component makes for a move of one unit of quote
    price, the quantity converted from the quote currency to the settlement currency, so that a
    cent-quoted price settles in dollars, and the quantity itself where the two are one; and
    offset[k], the entry-price offset in the settlement currency, minus the coefficient times the
    fixed price, so that the coefficient times the contract's price plus the offset is the
    component's entry-to-price P&L. Per input: inputs[m], the schedule row of the m-th contract
    the batch holds, increasing, each once; quantity_of_input[m], exposure[m] and
    offset_of_input[m], the sums of the quantities, the coefficients and the offsets over the
    components on it, the exposure being what every price multiplies; payment_date[m], the one
    day its components pay, an array for a financial settlement and None for a physical one.
    input_of_component[k] is the input of component k. An input's position is its position in
    this list and nothing else: not a position in any price vector."""

    terms: ResolvedTrades
    quantity: NDArray[np.float64]
    coefficient: NDArray[np.float64]
    offset: NDArray[np.float64]
    inputs: NDArray[np.intp]
    input_of_component: NDArray[np.intp]
    quantity_of_input: NDArray[np.float64]
    exposure: NDArray[np.float64]
    offset_of_input: NDArray[np.float64]
    payment_date: NDArray[np.datetime64] | None


def encoded(terms: ResolvedTrades, units: UnitConversions, counter: WorkCounter) -> Encoded:
    """The one way to make an Encoded: the conversions formed once, the arrays made in one pass
    each over the components and one over the inputs, and two rules on a financial settlement,
    checked once, the first failure being the message.

    The quantity: lots times the specification's lot size restates a count of lots in the lot
    unit, and the unit tables' factor restates that in the conventions' quote quantity unit,
    both units of the conventions' quantity type, as the index checked when it was made; one
    multiplication over the array, the sign kept. The coefficient: the quantity times the factor
    from the quote currency to the settlement currency, USD or CENT to USD or CENT, so that a
    price in cents times it is an amount in dollars; every price the batch meets, a quote, a
    final settlement or the fixed price, multiplies the coefficient and never the quantity. The
    offset: minus the coefficient times the fixed price. The inputs: the distinct contracts the
    components hold, sorted, which is the schedule's order, and each component's place among
    them, one search; the sums over components by input, one bincount each, so that two
    occurrences on one contract are one input with their coefficients added, a duplicate
    occurrence added twice. For a financial settlement, every component on a
    contract pays on the one day that contract pays, else the trade, the contract and its two
    days are named, since a group that paid on two days could not be settled as one; and that day is
    after the contract's expiry, else named, since a payment before the final price exists
    would have nothing to pay. The fees of the specification are read by nothing here: they are
    reserves, never a contribution to value.

    Work: one component encoded per component and one input per input, reported to the counter.
    """
    index = terms.index
    conventions = index.conventions
    specifications = index.specifications
    lot_size = float(specifications.lot_sizes[terms.specification])
    lot_unit = specifications.lot_units[terms.specification]
    to_quote_unit = units.factor(
        conventions.quantity_type, lot_unit, conventions.quote_quantity_unit
    )
    to_currency = units.factor(CURRENCY, conventions.quote_currency_unit, conventions.currency_unit)
    quantity = terms.lots * (lot_size * to_quote_unit)
    coefficient = quantity * to_currency
    offset = -coefficient * terms.fixed_price
    inputs = np.unique(terms.contract)
    input_of_component = np.searchsorted(inputs, terms.contract).astype(np.intp)
    quantity_of_input = np.bincount(input_of_component, weights=quantity, minlength=inputs.size)
    exposure = np.bincount(input_of_component, weights=coefficient, minlength=inputs.size)
    offset_of_input = np.bincount(input_of_component, weights=offset, minlength=inputs.size)
    payment_date = _one_payment_day_per_input(terms, inputs, input_of_component)
    counter.hit(ENCODED_COMPONENTS, terms.contract.size)
    counter.hit(ENCODED_INPUTS, int(inputs.size))
    arrays = (quantity, coefficient, offset, inputs, input_of_component, quantity_of_input)
    for array in (*arrays, exposure, offset_of_input):
        array.setflags(write=False)
    return Encoded(terms, *arrays, exposure, offset_of_input, payment_date)


def _one_payment_day_per_input(
    terms: ResolvedTrades, inputs: NDArray[np.intp], input_of_component: NDArray[np.intp]
) -> NDArray[np.datetime64] | None:
    """A financial settlement's one payment day per input, after the input's expiry; None for a
    physical settlement, which pays on no day."""
    if terms.payment_date is None:
        return None
    codes = terms.schedule.codes
    pays = np.empty(inputs.size, dtype="datetime64[D]")
    pays[input_of_component] = terms.payment_date  # the last component's day on each input
    differs = pays[input_of_component] != terms.payment_date
    if differs.any():
        k = int(differs.argmax())
        code = codes[int(terms.contract[k])]
        day = pays[input_of_component[k]]
        raise ValueError(
            f"payment_date of {terms.named(k)} is {terms.payment_date[k]}, expected {day}, "
            f"the one day {code} pays"
        )
    expiries = terms.schedule.future_expiry[inputs]
    early = pays <= expiries
    if early.any():
        m = int(early.argmax())
        raise ValueError(
            f"{codes[int(inputs[m])]} pays on {pays[m]}, "
            f"expected a day after its expiry {expiries[m]}, when its final price exists"
        )
    pays.setflags(write=False)
    return pays
