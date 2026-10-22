"""The static encoding of a batch: what the resolved terms and their observations amount to in
numbers before any price or fixing is known. Per component, its signed quantity in the index's
quote quantity unit, its coefficient, the settlement currency it makes per unit of quote price,
and its entry-price offset in the settlement currency. Per payment group, the components of one
contract that pay on one day, a contract whose components pay on two days being two groups, or
the components of one contract under a physical settlement, which pays on no day: the contract,
the summed offset and, for a financial settlement, the day it pays. Per slot, the dated market
input the batch consumes, an observation date within a payment group: the date, the contract
pricing that date, derived by the calendar's rule and retained, the group's own under the
expiry-based methods and whichever the calendar gives under asian, and the summed exposure
every settle or quote of that date multiplies. Per pricing reference, since #186, the contract's
calendar month and year, the axes a delta report by month or by year sums onto. And the
reserves, since #170, the brokerage the brokered rows' components incur and the clearing every
component incurs on a cleared route, charged where the booking says so since #188, summed for the
batch.
Nothing here changes on a tick, a fixing
or a roll of the valuation date. docs/library/trades/kernel.md is the page."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import contract_on, open_days
from goosedove.globals.unit_conversions import UnitConversions
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index_conventions import CURRENCY
from goosedove.index_definitions.kind import with_holiday_calendar
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.observations import Observations
from goosedove.trades.reserves import Reserves, reserves
from goosedove.trades.schedule_methods import METHODS, requires_booked_reference
from goosedove.trades.terms import LegTerms, ResolvedTrades, Route, payments_after_observations

ENCODED_COMPONENTS = "encoded_components"  # components turned into quantities and offsets
ENCODED_GROUPS = "encoded_groups"  # payment groups formed, summed into and checked
ENCODED_OBSERVATIONS = "encoded_observations"  # observations placed on their slots
ENCODED_SLOTS = "encoded_slots"  # dated slots named and summed over
ENCODED_PAYMENT_DAYS = (
    "encoded_payment_days"  # a bilateral batch's distinct payment days, since #178
)


@dataclass(frozen=True, slots=True)
class PaymentAxes:
    """The payment-time axes a DV01 report is summed onto, since #178, for a bilateral batch and for
    no other, static for the batch: days, the distinct payment days of every group, increasing,
    paid or not, and day_of_group[g]; months, the first day of each calendar month those days fall
    in, increasing, and month_of_day[d]; years, the first day of each calendar year, and
    year_of_month[m]. Then, for the report of every risk at once by day, the union of the
    observation days and the payment days, increasing, with each axis's places on it:
    union_days, observed_in_days and paid_in_days; the month and year displays are the
    preparation's since #186, made from the valuation day. Made once when the batch is made, so
    that a report copies saved vectors through saved places and discovers, sorts and sums
    nothing; None for a cleared batch, whose DV01 has no dated axis, and for a physical one."""

    days: NDArray[np.datetime64]
    day_of_group: NDArray[np.intp]
    months: NDArray[np.datetime64]
    month_of_day: NDArray[np.intp]
    years: NDArray[np.datetime64]
    year_of_month: NDArray[np.intp]
    union_days: NDArray[np.datetime64]
    observed_in_days: NDArray[np.intp]
    paid_in_days: NDArray[np.intp]


@dataclass(frozen=True, slots=True)
class CurveAxes:
    """The places the by-curve risk arrays are summed into, since named-curves-slice-3.md, for a
    bilateral batch and for no other, static for the batch: every curve's seven vectors stand in
    one array per axis, a row per curve of the batch's keys in key order, so that one reduction
    over the groups or the slots writes every curve's row at once with the group's curve beside
    the axis in its key. slot_reference[s] and slot_day[s], each slot's place by its group's
    curve among the references and the observation days; group_payment_day[g], each group's
    place by its curve among the payment days; payment_month_of_day and payment_year_of_month,
    the place of each row's payment day among the months and of each row's month among the
    years, the rows flattened; contract_month_of_reference and contract_year_of_month, the same
    for the delta's axes. A batch on one key holds the encoding's own places by reference,
    nothing made; curves is the number of keys."""

    curves: int
    slot_reference: NDArray[np.intp]
    slot_day: NDArray[np.intp]
    group_payment_day: NDArray[np.intp]
    payment_month_of_day: NDArray[np.intp]
    payment_year_of_month: NDArray[np.intp]
    contract_month_of_reference: NDArray[np.intp]
    contract_year_of_month: NDArray[np.intp]


@dataclass(frozen=True, slots=True)
class EncodedLeg:
    """One leg's side of the encoding, since two-index-fixed-float.md: the arrays an index owns,
    derived once from the trade's terms, the leg's terms and the leg's observations, all read-only;
    terms and leg by reference, the leg's observations too.

    Per component, aligned with the terms' components: quote_quantity[k], the signed quantity in
    the leg's quote quantity unit, the component's count, the quantity the basis formed, times
    the specification's lot size, converted where the lot unit differs; coefficient[k], the
    settlement currency the component makes for a move of one unit of quote price, the quote
    quantity converted from the quote currency to the settlement currency, so that a cent-quoted
    price settles in dollars, and the quote quantity itself where the two are one; and
    offset[k], the leg's entry-price offset in the settlement currency, minus the coefficient
    times the leg's fixed price, so that the coefficient times the contract's price plus the
    offset is the component's entry-to-price P&L on this leg.

    Per payment group, aligned with the trade's groups: group_contract[g], the schedule row of
    the g-th group's contract on this leg's schedule, the contract its components were booked on,
    which owns the fixed leg and, with its payment day, names the group.

    Per slot, the dated inputs: slot_group[s], the group the slot belongs to; slot_date[s], the
    observation day; slot_reference[s], the schedule row of the contract pricing that day, the
    calendar's rule derived once and retained, whose settle on the day fixes the slot and whose
    quote projects it while live, the group's own contract under the expiry-based methods and,
    under asian, whichever contract the calendar prices the day with, F27 and then G27 for a
    December booked as Z26 on a schedule whose contracts expire the month before;
    slot_exposure[s], the sum over the slot's observations of the component's coefficient times
    the observation's weight, what every price of the slot multiplies. The slots are in group
    order and by date within a group, so a group's slots are together with its last observation
    last, and one day observed by two groups of one contract is two slots. slot_of_observation[j]
    places each observation. references[r], the distinct slot references, increasing, is the
    leg's delta axis, each contract once whatever groups hold it, and reference_of_slot[s] each
    slot's place on it. A slot's position is its position in this list and nothing else: not a
    position in any price vector, and never a slot of another leg, two legs observing one day
    being two slots.

    Then the time axes a delta report is summed onto, static for the leg: since #166 days[d],
    the distinct observation days, increasing, day_of_slot[s] each slot's day and
    day_reference[d] the contract pricing each day, one per day by the calendar's rule; and
    since #186, risk-contract-month-bucketing.md, contract_months[m], the first day of the
    calendar month of each distinct contract among the references, increasing, the month the
    contract is named for and not the month its days are observed in,
    contract_month_of_reference[r] each reference's place, contract_years[y], the first day of
    each of those months' calendar years, increasing, and contract_year_of_month[m]. A day
    bucket is a day the leg observes on, a month or a year bucket a contract month or year the
    leg prices off, and nothing else: no period without a reference, and a payment day moves
    nothing. And curve_axes, since named-curves-slice-3.md, the places the by-curve risk arrays
    are summed into, CurveAxes, for a bilateral batch and None for the rest, the leg's slot and
    reference places beside the trade's group places."""

    terms: ResolvedTrades
    leg: LegTerms
    observations: Observations
    quote_quantity: NDArray[np.float64]
    coefficient: NDArray[np.float64]
    offset: NDArray[np.float64]
    group_contract: NDArray[np.intp]
    slot_group: NDArray[np.intp]
    slot_date: NDArray[np.datetime64]
    slot_reference: NDArray[np.intp]
    slot_exposure: NDArray[np.float64]
    slot_of_observation: NDArray[np.intp]
    references: NDArray[np.intp]
    reference_of_slot: NDArray[np.intp]
    days: NDArray[np.datetime64]
    day_of_slot: NDArray[np.intp]
    day_reference: NDArray[np.intp]
    contract_months: NDArray[np.datetime64]
    contract_month_of_reference: NDArray[np.intp]
    contract_years: NDArray[np.datetime64]
    contract_year_of_month: NDArray[np.intp]
    curve_axes: CurveAxes | None

    def slot_trade(self, slot: int) -> str:
        """The words for a slot's first trade, as ResolvedTrades.named gives them: `trade
        'NG-001' at row 1`."""
        j = int((self.slot_of_observation == slot).argmax())  # its first observation
        return self.terms.named(int(self.observations.component[j]))

    def named_slot(self, slot: int) -> str:
        """A slot's first trade named in a message with the slot's day and the contract pricing
        it, which under asian need not be the trade's own: `trade 'NG-001' at row 1 on
        2026-11-25, a day Z26 prices`."""
        code = self.leg.schedule.codes[int(self.slot_reference[slot])]
        return f"{self.slot_trade(slot)} on {self.slot_date[slot]}, a day {code} prices"


@dataclass(frozen=True, slots=True)
class Encoded:
    """The terms by reference, the trade's own arrays derived from them once, all read-only, and
    the legs, one EncodedLeg per leg of the terms in leg order, one today, each holding what its
    index owns, since two-index-fixed-float.md.

    Per payment group, the components of one contract that pay on one day and, since
    named-curves-slice-3.md, under one discount_curve_key: the groups in the schedule's order,
    within a contract by the day they pay and within a day by their key, the keys in the order
    the rows first name them, so that a contract whose components pay on two days is two groups,
    two components paying on one day under two keys two groups never netted before discounting,
    and a contract under a physical settlement, which pays on no day, one; each group's contract
    on each leg's schedule is the leg's group_contract; keys, the batch's distinct keys in that
    order, and key_of_group[g] each group's place among them, None with no key, a cleared
    batch's; group_of_component[k]; offset_of_group[g], the legs' offsets summed, the trade's
    fixed leg of the group; payment_date[g], the day the group pays, an array for a financial
    settlement and None for a physical one.

    Then reserves, since #170, the batch's booked brokerage and clearing, each charged component's
    count of the first leg's specification times the specification's rate per lot, summed, since
    #188 the brokered rows' components charged brokerage and every component clearing on a
    cleared route and none on a bilateral one, since #175 the marketing reserve the rows booked,
    summed once per row, and their currency, the Reserves record, static for the batch and
    entering no number here; _ReportReserves spills the totals and the results readback shows
    them once.

    Then, since #178, payment_axes, the payment-time axes a DV01 report is summed onto and the
    union of their days with the first leg's observation days, PaymentAxes, made once here for a
    bilateral batch and None for a cleared or a physical one; the month and year displays are
    the preparation's since #186."""

    terms: ResolvedTrades
    legs: tuple[EncodedLeg, ...]
    group_of_component: NDArray[np.intp]
    offset_of_group: NDArray[np.float64]
    payment_date: NDArray[np.datetime64] | None
    reserves: Reserves
    payment_axes: PaymentAxes | None
    keys: tuple[str, ...]
    key_of_group: NDArray[np.intp] | None


def encoded(
    terms: ResolvedTrades,
    observations: Sequence[Observations],
    units: UnitConversions,
    counter: WorkCounter,
) -> Encoded:
    """The one way to make an Encoded: one Observations per leg of the terms, in leg order, else
    refused; the conversions formed once, the arrays made in one pass each over the components,
    the groups, the observations and the slots, and the rules of the dated axis and of a
    financial settlement, checked once, the first failure being the message; the index's own
    arrays kept in the leg, since two-index-fixed-float.md, and the trade's own in the record.

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
    the components, and since named-curves-slice-3.md the distinct triples with the row's
    discount_curve_key where the batch has keys, the components sorted by contract, then by day,
    then by key, one lexsort, which puts the groups in the schedule's order, a contract's groups by
    the day they pay and a day's by the key in the order the rows first name the keys, and each
    component's place among them; under a physical settlement, which pays on no day, the distinct
    contracts, one unique. The offsets summed by group, one bincount, so that two occurrences on
    one contract paying on one day are one group with their offsets added, a duplicate occurrence
    added twice, and two paying on different days are two groups, each to move from mark to cash
    on its own day; the grouping is by the day itself, whatever lag and calendar made it.

    Since #190, reject-nonfinite-trade-arithmetic.md, each of these numbers is finite before it
    enters the record or feeds the next stage, the arithmetic running with numpy's flags down
    and the rules judging in this order: a specification's lot size times its factor to the
    quote unit, then each component's quote quantity, its coefficient and its fixed leg, named
    by the trade and the operation, then each group's fixed leg, a sum blamed on the group by
    its contract and payment day and never on one of its trades, and then each slot's exposure,
    named by its first trade, its day and the contract pricing it; a weight is at most one, so a
    finite coefficient's weighted exposure is finite and only the slot's sum can outrun. The
    first that is not finite is refused, whatever a later netting might have made of it, since
    the record would hold what cannot be represented.

    The slots: each observation's day is one the index's market is open on, Monday to Friday
    less the index's holidays, by the calendar's own rule, else refused, since no settle exists
    for a closed day or ever will, and a live observation on one would take a quote now and fail
    the day it fixed. Each observation's reference is the contract pricing its day by the
    calendar's rule, the first whose expiry is on or after it, one search over the schedule; a
    day after the last expiry prices nothing and is refused. Under the expiry-based methods the
    reference is the component's own contract, else the observation is refused by its method,
    since those methods take the contract's own days and a futures history holds one settle a
    day, the pricing contract's, never Z26's on a day X26 prices; under asian the reference is
    whatever the calendar gives, F27 and then G27 for a December booked as Z26 on a schedule
    whose contracts expire the month before, the booked contract keeping the fixed leg and the
    payment and the day's contract supplying its settle and its quote. Then the observations are
    sorted by group and date, one lexsort, the distinct pairs are the slots, and each
    observation's coefficient times its weight is summed into its slot, one bincount: two
    occurrences observing one day in one group are one slot with their exposures added, and one
    day observed by two groups of one contract is two slots, each with its own payment. The delta
    axis is the distinct references, one unique, each contract once whatever groups hold it, the
    contracts that price the batch's days and not the ones it was booked on. The time axes are
    the distinct observation days, one unique, each day's pricing contract its first slot's,
    and since #186 the distinct calendar months of the references' contracts, the terms'
    schedule months gathered by reference, and those months' years, two uniques, so that a
    delta report by day sums what the preparation leaves live onto the days, a report by month
    or by year sums the delta by reference onto the contracts' periods, and nothing is sorted
    or grouped when it is read. For a bilateral batch, since #178, the payment-time axes too:
    the distinct payment days of every group, their months and their years, three uniques
    more, and the union of the payment days with the observation days with each axis's places
    on it, one union and two searches, so that a DV01 report by payment day and a report of
    every risk by day copy saved vectors through saved places, the month and year displays
    being the preparation's since #186; a cleared batch, whose DV01 has no dated axis, makes none
    of this and its ledger stands.

    For a financial settlement, each group pays after its last observation, else its contract and
    its two days are named, since a payment before the last settle exists would have nothing to
    pay. The fees of the specification are read once, since #170, for the reserves, each
    charged component's count times its specification's rate per lot and the batch's two sums,
    brokerage over the brokered rows' components and clearing over every component of a cleared
    batch since #188,
    and since #175 the rows' marketing reserves summed once each, kept beside the encoding and
    never a contribution to value,
    docs/library/trades/report-reserves.md.

    Work: one component per component, one group per payment group, one observation per
    observation and one slot per slot, reported to the counter; one conversion per distinct
    specification the batch selects; the reserves once over the components each fee charges; and,
    for a bilateral batch, one payment day per distinct payment day, the axes made once.
    """
    if len(observations) != len(terms.legs):
        raise ValueError(
            f"observations are {len(observations)} legs' worth, expected {len(terms.legs)}, one "
            "per leg of the terms"
        )
    leg = terms.legs[0]
    observed = observations[0]
    index = leg.index
    conventions = index.conventions
    specifications = index.specifications
    selection = leg.specification[terms.occurrence]  # each component's specification row
    currency = conventions.currency_unit
    quote_unit = conventions.quote_quantity_unit
    per_price = f"{currency} per {conventions.quote_currency_unit}/{quote_unit}"
    to_quote_unit = np.zeros(len(specifications.names))
    # The arithmetic runs with numpy's flags down and the rules judge, since #190: each number
    # made here is finite before it enters the record or feeds the next stage, else the first
    # that is not is refused by its operation and its trade, group or slot.
    with np.errstate(over="ignore", invalid="ignore"):
        for row in np.unique(
            selection
        ):  # the distinct selections of the batch, converted once each
            chosen = int(row)
            to_quote_unit[chosen] = float(specifications.lot_sizes[chosen]) * units.factor(
                conventions.quantity_type,
                specifications.lot_units[chosen],
                conventions.quote_quantity_unit,
            )
            if not np.isfinite(to_quote_unit[chosen]):
                raise ValueError(
                    f"specification {specifications.names[chosen]!r} is {to_quote_unit[chosen]!r} "
                    f"{quote_unit} a lot, expected a finite number; its lot size times the factor "
                    f"from {specifications.lot_units[chosen]} to {quote_unit} outruns the largest "
                    "number"
                )
        to_currency = units.factor(
            CURRENCY, conventions.quote_currency_unit, conventions.currency_unit
        )
        quote_quantity = terms.component_quantity * to_quote_unit[selection]
        coefficient = quote_quantity * to_currency
        offset = -coefficient * leg.fixed_price
    for values, what, unit, why in (
        (
            quote_quantity,
            "quote quantity",
            f"number of {quote_unit}",
            "its count times its specification's size in the quote unit outruns the largest number",
        ),
        (
            coefficient,
            "coefficient",
            f"amount of {per_price}",
            "its quote quantity times the currency factor outruns the largest number",
        ),
        (
            offset,
            "fixed leg",
            f"amount of {currency}",
            "its coefficient times its fixed price outruns the largest number",
        ),
    ):  # the three products, each checked where it is made and named by its operation
        outrun = ~np.isfinite(values)
        if outrun.any():
            k = int(outrun.argmax())
            raise ValueError(
                f"{terms.named(k)} has {float(values[k])!r} of {what}, expected a finite {unit}; "
                f"{why}"
            )
    group_contract, payment_date, group_of_component, keys, key_of_group = _the_groups(terms, leg)
    with np.errstate(over="ignore", invalid="ignore"):
        offset_of_group = np.bincount(
            group_of_component, weights=offset, minlength=group_contract.size
        )
    outrun = ~np.isfinite(offset_of_group)
    if outrun.any():
        g = int(outrun.argmax())
        group = group_words(leg.schedule.codes, group_contract, payment_date, g, keys, key_of_group)
        raise ValueError(
            f"the fixed leg of {group} is {float(offset_of_group[g])!r}, expected a finite amount "
            f"of {currency}; its components' fixed legs, each finite, sum past the largest number"
        )
    reference = _the_references(terms, leg, observed)
    slot_of_observation, slot_group, slot_date, slot_reference = _the_slots(
        group_of_component[observed.component], observed.date, reference
    )
    with np.errstate(over="ignore", invalid="ignore"):
        # A weight is at most one, so a finite coefficient's weighted exposure is finite; the
        # slot's sum of them is what can outrun, and is what the record keeps.
        slot_exposure = np.bincount(
            slot_of_observation,
            weights=coefficient[observed.component] * observed.weight,
            minlength=slot_group.size,
        )
    outrun = ~np.isfinite(slot_exposure)
    if outrun.any():
        s = int(outrun.argmax())
        j = int((slot_of_observation == s).argmax())  # its first observation
        code = leg.schedule.codes[int(slot_reference[s])]
        raise ValueError(
            f"{terms.named(int(observed.component[j]))} on {slot_date[s]}, a day {code} "
            f"prices, has {float(slot_exposure[s])!r} of exposure, expected a finite amount of "
            f"{per_price}; its observations' coefficients times their weights sum past the "
            "largest number"
        )
    references, reference_of_slot = np.unique(slot_reference, return_inverse=True)
    days = _the_day_axis(slot_date, slot_reference)
    periods = _the_contract_periods(leg.schedule_month[references])
    # A cleared batch's DV01 has no dated axis; nothing more is made for it and its ledger stands.
    payment_axes = (
        _the_payment_axes(payment_date, days[0], counter)
        if terms.route is Route.BILATERAL and payment_date is not None
        else None
    )
    # Since named-curves-slice-3.md the places every curve's risk is summed into at once, made
    # here for a bilateral batch; a batch on one key holds the places above by reference.
    curve_axes = (
        _the_curve_axes(
            len(keys),
            key_of_group,
            slot_group,
            reference_of_slot,
            days[1],
            references.size,
            days[0].size,
            payment_axes,
            periods[1],
            periods[3],
            periods[0].size,
            periods[2].size,
        )
        if payment_axes is not None and key_of_group is not None
        else None
    )
    if payment_date is not None:
        _payments_after_observations(leg, group_contract, payment_date, slot_group, slot_date)
        payment_date.setflags(write=False)
    if key_of_group is not None:
        key_of_group.setflags(write=False)
    counter.hit(ENCODED_COMPONENTS, int(leg.contract.size))
    counter.hit(ENCODED_GROUPS, int(group_contract.size))
    counter.hit(ENCODED_OBSERVATIONS, int(observed.component.size))
    counter.hit(ENCODED_SLOTS, int(slot_group.size))
    reserved = reserves(terms, counter)
    arrays = (
        quote_quantity,
        coefficient,
        offset,
        group_contract,
        slot_group,
        slot_date,
        slot_reference,
        slot_exposure,
        slot_of_observation,
        references,
        reference_of_slot,
        *days,
        *periods,
    )
    for array in (*arrays, group_of_component, offset_of_group):
        array.setflags(write=False)
    return Encoded(
        terms,
        (EncodedLeg(terms, leg, observed, *arrays, curve_axes),),
        group_of_component,
        offset_of_group,
        payment_date,
        reserved,
        payment_axes,
        keys,
        key_of_group,
    )


def group_words(
    codes: tuple[str, ...],
    group_contract: NDArray[np.intp],
    payment_date: NDArray[np.datetime64] | None,
    g: int,
    keys: tuple[str, ...] = (),
    key_of_group: NDArray[np.intp] | None = None,
) -> str:
    """A payment group named in a message, since #190: its contract and, under a financial
    settlement, the day it pays, `F27 paying on 2027-01-04`, and since named-curves-slice-3.md
    its key where the batch has keys, `F27 paying on 2027-01-04 on SOFR`; a physical group its
    contract alone, since it pays on no day. A sum over a group is blamed on the group, never on
    one of its trades."""
    code = codes[int(group_contract[g])]
    words = code if payment_date is None else f"{code} paying on {payment_date[g]}"
    if key_of_group is None:
        return words
    return f"{words} on {keys[int(key_of_group[g])]}"


def _the_groups(
    terms: ResolvedTrades,
    leg: LegTerms,
) -> tuple[
    NDArray[np.intp],
    NDArray[np.datetime64] | None,
    NDArray[np.intp],
    tuple[str, ...],
    NDArray[np.intp] | None,
]:
    """The payment groups: under a financial settlement the distinct pairs of contract and payment
    day among the components, in the schedule's order and by day within a contract, and since
    named-curves-slice-3.md the distinct triples with the row's key where the batch has keys, by
    key within a day, the keys in the order the rows first name them; under a physical settlement,
    which pays on no day, the distinct contracts. Each group's contract, its payment day or None,
    each component's group, the batch's distinct keys and each group's key, the keys empty and
    the key of each group None where the batch has none. The contracts are the leg's rows of
    its schedule, the first leg's naming the groups."""
    contract = leg.contract
    if terms.payment is None:
        group_contract, group_of_component = np.unique(contract, return_inverse=True)
        return group_contract, None, group_of_component, (), None
    day = terms.payment.date.astype(np.int64)
    if terms.discount_curve_key is None:
        group_of_component, heads = _distinct(contract, day)
        return contract[heads], terms.payment.date[heads], group_of_component, (), None
    keys = tuple(dict.fromkeys(terms.discount_curve_key))  # distinct, by first appearance
    place = {key: i for i, key in enumerate(keys)}
    key_of_occurrence = np.array([place[key] for key in terms.discount_curve_key], dtype=np.intp)
    key_of_component = key_of_occurrence[terms.occurrence]
    group_of_component, heads = _distinct(contract, day, key_of_component)
    return (
        contract[heads],
        terms.payment.date[heads],
        group_of_component,
        keys,
        key_of_component[heads],
    )


def _distinct(*keys: NDArray[Any]) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """The distinct tuples of the keys among the items, in order of the first key, then the second
    and so on: each item's tuple, counted from zero in that order, and the first item of each
    tuple, in tuple order, one lexsort over the items."""
    order = np.lexsort(keys[::-1])
    sorted_keys = [key[order] for key in keys]
    first = np.ones(order.size, dtype=np.bool_)
    first[1:] = sorted_keys[0][1:] != sorted_keys[0][:-1]
    for sorted_key in sorted_keys[1:]:
        first[1:] |= sorted_key[1:] != sorted_key[:-1]
    tuple_of_sorted = np.cumsum(first) - 1
    tuple_of_item = np.empty(order.size, dtype=np.intp)
    tuple_of_item[order] = tuple_of_sorted
    return tuple_of_item, order[first]


def _the_curve_axes(
    curves: int,
    key_of_group: NDArray[np.intp],
    slot_group: NDArray[np.intp],
    reference_of_slot: NDArray[np.intp],
    day_of_slot: NDArray[np.intp],
    references: int,
    days: int,
    payment_axes: PaymentAxes,
    contract_month_of_reference: NDArray[np.intp],
    contract_year_of_month: NDArray[np.intp],
    contract_months: int,
    contract_years: int,
) -> CurveAxes:
    """The places every curve's risk is summed into at once, since named-curves-slice-3.md: each
    slot's and each group's place offset by its curve's row, and each row's places among the
    months and the years, the rows flattened; a batch on one key holds the encoding's own places
    by reference and makes nothing, its ledger standing."""
    if curves == 1:
        return CurveAxes(
            1,
            reference_of_slot,
            day_of_slot,
            payment_axes.day_of_group,
            payment_axes.month_of_day,
            payment_axes.year_of_month,
            contract_month_of_reference,
            contract_year_of_month,
        )
    key_of_slot = key_of_group[slot_group]
    rows = np.arange(curves, dtype=np.intp)[:, None]
    arrays = (
        key_of_slot * references + reference_of_slot,
        key_of_slot * days + day_of_slot,
        key_of_group * payment_axes.days.size + payment_axes.day_of_group,
        (rows * payment_axes.months.size + payment_axes.month_of_day).ravel(),
        (rows * payment_axes.years.size + payment_axes.year_of_month).ravel(),
        (rows * contract_months + contract_month_of_reference).ravel(),
        (rows * contract_years + contract_year_of_month).ravel(),
    )
    for array in arrays:
        array.setflags(write=False)
    return CurveAxes(curves, *arrays)


def _the_references(
    terms: ResolvedTrades, leg: LegTerms, observations: Observations
) -> NDArray[np.intp]:
    """Each observation's reference for a leg: observation_references over the leg's schedule,
    holiday calendar, contracts and methods, each component named as the terms name its trade."""
    return observation_references(
        leg.schedule,
        leg.index.holiday_calendar,
        observations,
        leg.contract,
        leg.schedule_method[terms.occurrence],
        terms.named,
    )


def observation_references(
    schedule: FuturesSchedule | IfercSchedule,
    holiday_calendar: HolidayCalendar | None,
    observations: Observations,
    contract: NDArray[np.intp],
    method: NDArray[np.intp],
    named: Callable[[int], str],
) -> NDArray[np.intp]:
    """Each observation's reference, the contract pricing its day, for a batch of trades and
    since template-based-quoting.md for a quote alike: contract[k] and method[k] the k-th
    component's schedule row and method, and named(k) the words a refusal gives it. On a futures
    index: the day open on the index's market, within the schedule, and under the expiry-based
    methods the component's own contract; under asian whichever contract the calendar gives,
    one gather of the methods onto the observations. On an IFERC index, since #167: the
    component's own contract, whose index publishes on that very day, else refused, an IFERC
    month pricing once; no calendar is read, an IFERC index having none."""
    match schedule:
        case IfercSchedule() as iferc:
            own_contract = contract[observations.component]
            published = iferc.publication_date[own_contract]
            off = published != observations.date
            if off.any():
                j = int(off.argmax())
                raise ValueError(
                    f"{named(int(observations.component[j]))} observes "
                    f"{observations.date[j]}, expected {published[j]}, the day "
                    f"{iferc.codes[int(own_contract[j])]}'s index publishes; an IFERC month "
                    "prices once, on that day"
                )
            return own_contract
        case FuturesSchedule():
            pass
        case _:
            assert_never(schedule)
    codes = schedule.codes
    closed = ~open_days(with_holiday_calendar(holiday_calendar), observations.date)
    if closed.any():
        j = int(closed.argmax())
        raise ValueError(
            f"{named(int(observations.component[j]))} observes {observations.date[j]}, "
            "a day the index's market is closed; no settle exists or will"
        )
    reference = contract_on(schedule, observations.date)
    beyond = reference >= len(codes)
    if beyond.any():
        j = int(beyond.argmax())
        raise ValueError(
            f"{named(int(observations.component[j]))} observes {observations.date[j]}, "
            f"after the schedule's last expiry, {schedule.future_expiry[-1]}; nothing prices it"
        )
    of_observation = method[observations.component]
    own = requires_booked_reference(of_observation)
    other = own & (reference != contract[observations.component])
    if other.any():
        j = int(other.argmax())
        component = int(observations.component[j])
        code = codes[int(contract[component])]
        pricing = codes[int(reference[j])]
        raise ValueError(
            f"{named(component)} observes {code} on {observations.date[j]}, a day "
            f"{pricing} prices; the {METHODS[int(of_observation[j])].value} method takes the "
            f"contract's own days, and a futures history holds no settle of {code} for a day "
            f"{pricing} prices"
        )
    return reference


def _the_day_axis(
    date: NDArray[np.datetime64], reference: NDArray[np.intp]
) -> tuple[NDArray[np.datetime64], NDArray[np.intp], NDArray[np.intp]]:
    """The day axis a delta report by day is summed onto, static for the batch: the distinct
    observation days, increasing, with each slot's day and each day's pricing contract, its first
    slot's, the calendar giving a day one contract. One unique over the slots, nothing per trade
    and no day without an observation."""
    days, first, day_of_slot = np.unique(date, return_index=True, return_inverse=True)
    return days, day_of_slot, reference[first]


def _the_contract_periods(
    months: NDArray[np.int64],
) -> tuple[NDArray[np.datetime64], NDArray[np.intp], NDArray[np.datetime64], NDArray[np.intp]]:
    """The month and year axes a delta report by month or by year is summed onto, since #186,
    static for the batch: the distinct calendar months of the references' contracts, as the terms
    count them, increasing, as the first day of each, with each reference's place; and the first
    day of each of those months' calendar years, increasing, with each month's place. Two uniques
    over the references, nothing per slot: a reference prices one contract, whose month is its own
    whatever days it is observed on."""
    month_keys, month_of_reference = np.unique(months, return_inverse=True)
    first_days = month_keys.astype("datetime64[M]").astype("datetime64[D]")
    year_keys, year_of_month = np.unique(first_days.astype("datetime64[Y]"), return_inverse=True)
    return first_days, month_of_reference, year_keys.astype("datetime64[D]"), year_of_month


def _the_payment_axes(
    payment_date: NDArray[np.datetime64],
    days: NDArray[np.datetime64],
    counter: WorkCounter,
) -> PaymentAxes:
    """The payment-time axes of a bilateral batch, since #178: the distinct payment days of every
    group with each group's place, the months those days fall in with each day's, the years with
    each month's, three uniques; and the union of the observation days given and the payment
    days, one union, with each axis's places on it, two searches, so that a report of every risk
    by day copies the saved vectors onto one axis through saved places; the month and year
    displays are the preparation's since #186. Every array frozen; one payment day per distinct
    payment day reported to the counter."""
    paid, day_of_group = np.unique(payment_date, return_inverse=True)
    month_keys, month_of_day = np.unique(paid.astype("datetime64[M]"), return_inverse=True)
    year_keys, year_of_month = np.unique(month_keys.astype("datetime64[Y]"), return_inverse=True)
    paid_months = month_keys.astype("datetime64[D]")
    paid_years = year_keys.astype("datetime64[D]")
    arrays = (
        paid,
        day_of_group,
        paid_months,
        month_of_day,
        paid_years,
        year_of_month,
        *_the_union(days, paid),
    )
    for array in arrays:
        array.setflags(write=False)
    counter.hit(ENCODED_PAYMENT_DAYS, int(paid.size))
    return PaymentAxes(*arrays)


def _the_union(
    observed: NDArray[np.datetime64], paid: NDArray[np.datetime64]
) -> tuple[NDArray[np.datetime64], NDArray[np.intp], NDArray[np.intp]]:
    """The union of the observation days and the payment days, increasing, with each axis's
    places on it: one union, two searches."""
    union = np.union1d(observed, paid)
    return union, np.searchsorted(union, observed), np.searchsorted(union, paid)


def _the_slots(
    group: NDArray[np.intp], date: NDArray[np.datetime64], reference: NDArray[np.intp]
) -> tuple[NDArray[np.intp], NDArray[np.intp], NDArray[np.datetime64], NDArray[np.intp]]:
    """The distinct pairs of group and day among the observations, in group order and by day
    within a group, and each observation's slot; a slot's group, day and reference are its first
    observation's."""
    slot_of_observation, heads = _distinct(group, date.astype(np.int64))
    return slot_of_observation, group[heads], date[heads], reference[heads]


def _payments_after_observations(
    leg: LegTerms,
    group_contract: NDArray[np.intp],
    payment_date: NDArray[np.datetime64],
    slot_group: NDArray[np.intp],
    slot_date: NDArray[np.datetime64],
) -> None:
    """A financial settlement's rule, the kernel's one owner of it since
    payment-day-date-or-rule.md, applied here to the groups: each group pays after its last
    observation, the day its final price exists; the first group paying on or before it is
    refused by its contract and the two days. The slots stand in group order and by day, so
    each group's last slot is its last observation, and every group has one, every component
    observing at least once."""
    last = np.ones(slot_group.size, dtype=np.bool_)
    last[:-1] = slot_group[1:] != slot_group[:-1]
    payments_after_observations(
        payment_date,
        slot_date[last],
        lambda g: leg.schedule.codes[int(group_contract[g])],
    )
