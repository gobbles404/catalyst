"""The static encoding of a batch: what the resolved terms and their observations amount to in
numbers before any price or fixing is known. Per component, its signed quantity in the index's
quote quantity unit, its coefficient, the settlement currency it makes per unit of quote price,
and its entry-price offset in the settlement currency. Per payment group, the components of one
contract that pay on one day, a contract whose components pay on two days being two groups, or
the components of one contract under a physical settlement, which pays on no day: the contract,
the summed offset and, for a financial settlement, the day it pays. Per slot, the dated market
input the batch consumes, an observation date within a payment group: the date, the contract
pricing that date, derived by the calendar's rule and retained, and the summed exposure every
settle or quote of that date multiplies. Nothing here changes on a tick, a fixing or a roll of
the valuation date. docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import contract_on, open_days
from goosedove.globals.unit_conversions import UnitConversions
from goosedove.index_definitions.index_conventions import CURRENCY
from goosedove.index_definitions.kind import with_holiday_calendar
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.observations import Observations
from goosedove.trades.terms import ResolvedTrades

ENCODED_COMPONENTS = "encoded_components"  # components turned into quantities and offsets
ENCODED_GROUPS = "encoded_groups"  # payment groups formed, summed into and checked
ENCODED_OBSERVATIONS = "encoded_observations"  # observations placed on their slots
ENCODED_SLOTS = "encoded_slots"  # dated slots named and summed over


@dataclass(frozen=True, slots=True)
class Encoded:
    """The terms and the observations, by reference, and the arrays derived from them once, all
    read-only.

    Per component, aligned with the terms' components: quote_quantity[k], the signed quantity in
    the quote quantity unit, the component's count, the quantity the basis formed, times the
    specification's lot size, converted where the lot unit differs; coefficient[k], the
    settlement currency the component makes for a move of one unit of quote price, the quote
    quantity converted from the quote currency to the settlement currency, so that a cent-quoted
    price settles in dollars, and the quote quantity itself where the two are one; and
    offset[k], the entry-price offset in the settlement currency, minus the coefficient times the
    fixed price, so that the coefficient times the contract's price plus the offset is the
    component's entry-to-price P&L.

    Per payment group, the components of one contract that pay on one day: group_contract[g], the
    schedule row of the g-th group's contract, the groups in the schedule's order and, within a
    contract, by the day they pay, so that a contract whose components pay on two days is two
    groups and a contract under a physical settlement, which pays on no day, one;
    group_of_component[k]; offset_of_group[g], the components' offsets summed; payment_date[g],
    the day the group pays, an array for a financial settlement and None for a physical one.

    Per slot, the dated inputs: slot_group[s], the group the slot belongs to; slot_date[s], the
    observation day; slot_reference[s], the schedule row of the contract pricing that day, the
    calendar's rule derived once and retained, whose settle on the day fixes the slot and whose
    quote projects it while live; slot_exposure[s], the sum over the slot's observations of the
    component's coefficient times the observation's weight, what every price of the slot
    multiplies. The slots are in group order and by date within a group, so a group's slots are
    together with its last observation last, and one day observed by two groups of one contract
    is two slots. slot_of_observation[j] places each observation. references[r], the distinct
    slot references, increasing, is the batch's delta axis, each contract once whatever groups
    hold it, and reference_of_slot[s] each slot's place on it. A slot's position is its position
    in this list and nothing else: not a position in any price vector."""

    terms: ResolvedTrades
    observations: Observations
    quote_quantity: NDArray[np.float64]
    coefficient: NDArray[np.float64]
    offset: NDArray[np.float64]
    group_contract: NDArray[np.intp]
    group_of_component: NDArray[np.intp]
    offset_of_group: NDArray[np.float64]
    payment_date: NDArray[np.datetime64] | None
    slot_group: NDArray[np.intp]
    slot_date: NDArray[np.datetime64]
    slot_reference: NDArray[np.intp]
    slot_exposure: NDArray[np.float64]
    slot_of_observation: NDArray[np.intp]
    references: NDArray[np.intp]
    reference_of_slot: NDArray[np.intp]

    def named_slot(self, slot: int) -> str:
        """A slot's first trade named in a message, with the slot's contract and day: `trade
        'NG-001' at row 1 observes Z26 on 2026-11-25`."""
        j = int((self.slot_of_observation == slot).argmax())  # its first observation
        component = int(self.observations.component[j])
        code = self.terms.schedule.codes[int(self.slot_reference[slot])]
        return f"{self.terms.named(component)} observes {code} on {self.slot_date[slot]}"


def encoded(
    terms: ResolvedTrades,
    observations: Observations,
    units: UnitConversions,
    counter: WorkCounter,
) -> Encoded:
    """The one way to make an Encoded: the conversions formed once, the arrays made in one pass
    each over the components, the groups, the observations and the slots, and the rules of the
    dated axis and of a financial settlement, checked once, the first failure being the message.

    The quote quantity: the component quantity, the count the terms formed by its occurrence's
    basis, the entered quantity times its covered days under calday, times its occurrence's
    specification's lot size restates a count of that row in its lot unit, and the unit tables'
    factor restates that in the conventions' quote quantity unit, both units of the conventions'
    quantity type, as the index checked when it was made, the lot size and the factor formed once
    per distinct specification the batch selects and gathered onto the components; one
    multiplication over the array, the sign kept. The
    coefficient: the quote quantity times the factor from the quote currency to the settlement
    currency, USD or CENT to USD or CENT, so that a price in cents times it is an amount in
    dollars; every price the batch meets, a quote, a settle or the fixed price, multiplies the
    coefficient and never the quantity. The offset: minus the coefficient times the fixed price.
    The groups: under a financial settlement the distinct pairs of contract and payment day among
    the components, the components sorted by contract and then by day, one lexsort, which puts
    the groups in the schedule's order and a contract's groups by the day they pay, and each
    component's place among them; under a physical settlement, which pays on no day, the distinct
    contracts, one unique. The offsets summed by group, one bincount, so that two occurrences on
    one contract paying on one day are one group with their offsets added, a duplicate occurrence
    added twice, and two paying on different days are two groups, each to move from mark to cash
    on its own day; the grouping is by the day itself, whatever lag and calendar made it.

    The slots: each observation's day is one the index's market is open on, Monday to Friday
    less the index's holidays, by the calendar's own rule, else refused, since no settle exists
    for a closed day or ever will, and a live observation on one would take a quote now and fail
    the day it fixed. Each observation's reference is the contract pricing its day by the
    calendar's rule, the first whose expiry is on or after it, one search over the schedule; a
    day after the last expiry prices nothing and is refused; and the reference is the component's
    own contract, else the observation is refused as unsupported, since a futures history holds
    one settle a day, the pricing contract's, and would never fix another contract's observation
    on it, F27's on a day Z26 prices. Then the observations are sorted by group and date, one
    lexsort, the distinct pairs are the slots, and each observation's coefficient times its
    weight is summed into its slot, one bincount: two occurrences observing one day in one group
    are one slot with their exposures added, and one day observed by two groups of one contract
    is two slots, each with its own payment. The delta axis is the distinct references, one
    unique, each contract once whatever groups hold it.

    For a financial settlement, each group pays after its last observation, else its contract and
    its two days are named, since a payment before the last settle exists would have nothing to
    pay. The fees of the specification are read by nothing here: they are reserves, never a
    contribution to value.

    Work: one component per component, one group per payment group, one observation per
    observation and one slot per slot, reported to the counter; one conversion per distinct
    specification the batch selects.
    """
    index = terms.index
    conventions = index.conventions
    specifications = index.specifications
    selection = terms.specification[terms.occurrence]  # each component's specification row
    to_quote_unit = np.zeros(len(specifications.names))
    for row in np.unique(selection):  # the distinct selections of the batch, converted once each
        chosen = int(row)
        to_quote_unit[chosen] = float(specifications.lot_sizes[chosen]) * units.factor(
            conventions.quantity_type,
            specifications.lot_units[chosen],
            conventions.quote_quantity_unit,
        )
    to_currency = units.factor(CURRENCY, conventions.quote_currency_unit, conventions.currency_unit)
    quote_quantity = terms.component_quantity * to_quote_unit[selection]
    coefficient = quote_quantity * to_currency
    offset = -coefficient * terms.fixed_price
    group_contract, payment_date, group_of_component = _the_groups(terms)
    offset_of_group = np.bincount(group_of_component, weights=offset, minlength=group_contract.size)
    reference = _the_references(terms, observations)
    slot_of_observation, slot_group, slot_date, slot_reference = _the_slots(
        group_of_component[observations.component], observations.date, reference
    )
    slot_exposure = np.bincount(
        slot_of_observation,
        weights=coefficient[observations.component] * observations.weight,
        minlength=slot_group.size,
    )
    references, reference_of_slot = np.unique(slot_reference, return_inverse=True)
    if payment_date is not None:
        _payments_after_observations(terms, group_contract, payment_date, slot_group, slot_date)
        payment_date.setflags(write=False)
    counter.hit(ENCODED_COMPONENTS, int(terms.contract.size))
    counter.hit(ENCODED_GROUPS, int(group_contract.size))
    counter.hit(ENCODED_OBSERVATIONS, int(observations.component.size))
    counter.hit(ENCODED_SLOTS, int(slot_group.size))
    arrays = (
        quote_quantity,
        coefficient,
        offset,
        group_contract,
        group_of_component,
        offset_of_group,
        slot_group,
        slot_date,
        slot_reference,
        slot_exposure,
        slot_of_observation,
        references,
        reference_of_slot,
    )
    for array in arrays:
        array.setflags(write=False)
    return Encoded(terms, observations, *arrays[:6], payment_date, *arrays[6:])


def _the_groups(
    terms: ResolvedTrades,
) -> tuple[NDArray[np.intp], NDArray[np.datetime64] | None, NDArray[np.intp]]:
    """The payment groups: under a financial settlement the distinct pairs of contract and payment
    day among the components, in the schedule's order and by day within a contract; under a
    physical settlement, which pays on no day, the distinct contracts. Each group's contract, its
    payment day or None, and each component's group."""
    contract = terms.contract
    if terms.payment is None:
        group_contract, group_of_component = np.unique(contract, return_inverse=True)
        return group_contract, None, group_of_component
    group_of_component, heads = _distinct(contract, terms.payment.date.astype(np.int64))
    return contract[heads], terms.payment.date[heads], group_of_component


def _distinct(
    major: NDArray[np.intp], minor: NDArray[np.int64]
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """The distinct pairs of major and minor among the items, in order of major and then minor:
    each item's pair, counted from zero in that order, and the first item of each pair, in pair
    order, one lexsort over the items."""
    order = np.lexsort((minor, major))
    sorted_major, sorted_minor = major[order], minor[order]
    first = np.ones(order.size, dtype=np.bool_)
    first[1:] = (sorted_major[1:] != sorted_major[:-1]) | (sorted_minor[1:] != sorted_minor[:-1])
    pair_of_sorted = np.cumsum(first) - 1
    pair_of_item = np.empty(order.size, dtype=np.intp)
    pair_of_item[order] = pair_of_sorted
    return pair_of_item, order[first]


def _the_references(terms: ResolvedTrades, observations: Observations) -> NDArray[np.intp]:
    """Each observation's reference, the contract pricing its day: the day open on the index's
    market, within the schedule, and the component's own contract."""
    schedule = terms.schedule
    codes = schedule.codes
    closed = ~open_days(with_holiday_calendar(terms.index.holiday_calendar), observations.date)
    if closed.any():
        j = int(closed.argmax())
        component = int(observations.component[j])
        raise ValueError(
            f"{terms.named(component)} observes {codes[int(terms.contract[component])]} on "
            f"{observations.date[j]}, a day the index's market is closed; no settle exists or will"
        )
    reference = contract_on(schedule, observations.date)
    beyond = reference >= len(codes)
    if beyond.any():
        j = int(beyond.argmax())
        raise ValueError(
            f"{terms.named(int(observations.component[j]))} observes {observations.date[j]}, "
            f"after the schedule's last expiry, {schedule.future_expiry[-1]}; nothing prices it"
        )
    other = reference != terms.contract[observations.component]
    if other.any():
        j = int(other.argmax())
        component = int(observations.component[j])
        raise ValueError(
            f"{terms.named(component)} observes {codes[int(terms.contract[component])]} on "
            f"{observations.date[j]}, a day {codes[int(reference[j])]} prices; an observation of "
            "a contract other than the day's pricing contract has no settle in a futures history, "
            "not supported"
        )
    return reference


def _the_slots(
    group: NDArray[np.intp], date: NDArray[np.datetime64], reference: NDArray[np.intp]
) -> tuple[NDArray[np.intp], NDArray[np.intp], NDArray[np.datetime64], NDArray[np.intp]]:
    """The distinct pairs of group and day among the observations, in group order and by day
    within a group, and each observation's slot; a slot's group, day and reference are its first
    observation's."""
    slot_of_observation, heads = _distinct(group, date.astype(np.int64))
    return slot_of_observation, group[heads], date[heads], reference[heads]


def _payments_after_observations(
    terms: ResolvedTrades,
    group_contract: NDArray[np.intp],
    payment_date: NDArray[np.datetime64],
    slot_group: NDArray[np.intp],
    slot_date: NDArray[np.datetime64],
) -> None:
    """A financial settlement's rule: each group pays after its last observation, the day its
    final price exists; the first group paying on or before it is refused by its contract and the
    two days. The slots stand in group order and by day, so each group's last slot is its last
    observation, and every group has one, every component observing at least once."""
    last = np.ones(slot_group.size, dtype=np.bool_)
    last[:-1] = slot_group[1:] != slot_group[:-1]
    last_observed = slot_date[last]
    early = payment_date <= last_observed
    if early.any():
        g = int(early.argmax())
        raise ValueError(
            f"{terms.schedule.codes[int(group_contract[g])]} pays on {payment_date[g]}, expected "
            f"a day after its last observation, {last_observed[g]}, when its final price exists"
        )
