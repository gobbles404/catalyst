"""The static encoding of a batch: what the resolved terms and their observations amount to in
numbers before any price or fixing is known. Per component, its signed quantity in the index's
quote quantity unit, its coefficient, the settlement currency it makes per unit of quote price,
and its entry-price offset in the settlement currency. Per payment group, the components of one
calculation period that pay on one day, since onetime-averaging.md the period a component's
calendar month or a onetime row's whole window, a period whose components pay on two days being
two groups, or the components of one period under a physical settlement, which pays on no day:
the period's label, a month's contract code or a window's two dates, the summed offset and, for a
financial settlement, the day it pays. Per slot, the dated market
input the batch consumes, an observation date within a payment group: the date, the contract
pricing that date, derived by the calendar's rule and retained, the group's own under the
expiry-based methods and whichever the calendar gives under asian, and the summed exposure
every settle or quote of that date multiplies. Per pricing reference, since #186, the contract's
calendar month and year, the axes a delta report by month or by year sums onto. And the
reserves, since #170, the brokerage the brokered rows' components incur and the clearing every
component incurs on a cleared route, charged where the booking says so since #188, summed for the
batch. And for a physical batch, since expired-physical-cash.md, which of its contracts hold no
position, the counts of each quantity unit adding to zero.
Nothing here changes on a tick, a fixing
or a roll of the valuation date. docs/library/trades/kernel.md is the page."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, assert_never

import numpy as np
from numpy.typing import NDArray

from catalyst.calendar.calendar import contract_on, open_days
from catalyst.globals.unit_conversions import UnitConversions
from catalyst.index_definitions.futures_schedule import FuturesSchedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.index_conventions import CURRENCY, a_unit_of, listed
from catalyst.index_definitions.kind import with_holiday_calendar
from catalyst.index_definitions.published_schedule import PublishedSchedule
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FLOAT_FLOAT
from catalyst.trades.observations import Observations
from catalyst.trades.reserves import Reserves, reserves
from catalyst.trades.schedule_methods import METHODS, requires_booked_reference
from catalyst.trades.terms import (
    ELECTRICITY,
    LegTerms,
    PriceUnit,
    ResolvedTrades,
    Route,
    TradeSchedule,
    booked_words,
    named_trade,
    onetime_components,
    payments_after_observations,
    price_words,
)

ENCODED_COMPONENTS = "encoded_components"  # components turned into quantities and offsets
ENCODED_GROUPS = "encoded_groups"  # payment groups formed, summed into and checked
ENCODED_OBSERVATIONS = "encoded_observations"  # observations placed on their slots
ENCODED_SLOTS = "encoded_slots"  # dated slots named and summed over
ENCODED_PAYMENT_DAYS = (
    "encoded_payment_days"  # a bilateral batch's distinct payment days, since #178
)
ENCODED_PAIR_DAYS = "encoded_pair_days"  # a pair's distinct observation days over both legs
# The allowance two legs' sizes per entered unit may differ by and be one quantity, relative,
# since two-index-fixed-float.md: the unit tables' products of a few factors agree to a few
# ulps, 1e-16 of the size, and two quantities that are not one differ by a ratio of units.
UNIT_ROUNDOFF = 1e-12
# The whole numbers a number adds exactly, since expired-physical-cash.md: while the counts of
# one contract and unit are under 2^53 in all, every count and every partial sum is a whole
# number a float holds; a physical batch holding that many or more is refused when it is made.
EXACT_COUNTS = 2.0**53


@dataclass(frozen=True, slots=True)
class PaymentAxes:
    """The payment-time axes a DV01 report is summed onto, since #178, for a bilateral batch and for
    no other, static for the batch: days, the distinct payment days of every group, increasing,
    paid or not, and day_of_group[g]; months, the first day of each calendar month those days fall
    in, increasing, and month_of_day[d]; years, the first day of each calendar year, and
    year_of_month[m]. Then, for the report of every risk at once by day, the union of the
    observation days of every leg and the payment days, increasing, union_days, with the
    payment days' places on it, paid_in_days, each leg's observation days' places being the
    leg's own, EncodedLeg.day_in_union; the month and year displays are the preparation's
    since #186, made from the valuation day. Made once when the batch is made, so
    that a report copies saved vectors through saved places and discovers, sorts and sums
    nothing; None for a cleared batch, whose DV01 has no dated axis, and for a physical one."""

    days: NDArray[np.datetime64]
    day_of_group: NDArray[np.intp]
    months: NDArray[np.datetime64]
    month_of_day: NDArray[np.intp]
    years: NDArray[np.datetime64]
    year_of_month: NDArray[np.intp]
    union_days: NDArray[np.datetime64]
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
    price settles in dollars, and the quote quantity itself where the two are one, what every
    price of the leg multiplies. No offset: since two-index-one-price.md the fixed leg is the
    trade's, Encoded.offset, made once from the first leg's coefficient and the trade's one
    price, so the coefficient times the contract's price is the component's floating side on
    this leg and nothing of the entry price is a leg's.

    Per payment group, aligned with the trade's groups: group_contract[g], the schedule row of
    the g-th group's contract on this leg's schedule, the contract of the calendar month its
    components were booked on, which with its payment day names the group, the group itself
    keyed since onetime-averaging.md by its calculation period, that month, and not by the
    contract.

    Per slot, the dated inputs: slot_group[s], the group the slot belongs to; slot_date[s], the
    observation day; slot_reference[s], the schedule row of the contract pricing that day, the
    calendar's rule derived once and retained, whose settle on the day fixes the slot and whose
    quote projects it while live, the group's own contract under the expiry-based methods and,
    under asian, whichever contract the calendar prices the day with, F27 and then G27 for a
    December booked as Z26 on a schedule whose contracts expire the month before;
    slot_exposure[s], the sum over the slot's observations of the component's coefficient times
    the observation's weight, what every price of the slot multiplies. A slot is a group, a day
    and a contract, since nearby-selection.md, where it was a group and a day: two observations
    of one group on one day that read two contracts are two slots, two exposures. The slots
    are in group order, by date within a group and by contract within a day, so a group's
    slots are together with its last observation day last, and one day observed by two groups
    of one contract is two slots. slot_of_observation[j]
    places each observation. references[r], the distinct slot references, increasing, is the
    leg's delta axis, each contract once whatever groups hold it, and reference_of_slot[s] each
    slot's place on it. A slot's position is its position in this list and nothing else: not a
    position in any price vector, and never a slot of another leg, two legs observing one day
    being two slots.

    Then the time axes a delta report is summed onto, static for the leg: since #166 days[d],
    the distinct observation days, increasing, and day_of_slot[s] each slot's day, a day
    holding the slots of whatever contracts are read on it; and
    since #186, risk-contract-month-bucketing.md, contract_months[m], the first day of the
    calendar month of each distinct contract among the references, increasing, the month the
    contract is named for and not the month its days are observed in,
    contract_month_of_reference[r] each reference's place, contract_years[y], the first day of
    each of those months' calendar years, increasing, and contract_year_of_month[m]. A day
    bucket is a day the leg observes on, a month or a year bucket a contract month or year the
    leg prices off, and nothing else: no period without a reference, and a payment day moves
    nothing. And curve_axes, since named-curves-slice-3.md, the places the by-curve risk arrays
    are summed into, CurveAxes, for a bilateral batch and None for the rest, the leg's slot and
    reference places beside the trade's group places; and day_in_union, the leg's observation
    days' places on the trade's union of observation and payment days, PaymentAxes.union_days,
    for a bilateral batch and None for the rest, so that a report of every risk by day copies
    the leg's saved vectors through saved places."""

    terms: ResolvedTrades
    leg: LegTerms
    observations: Observations
    quote_quantity: NDArray[np.float64]
    coefficient: NDArray[np.float64]
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
    contract_months: NDArray[np.datetime64]
    contract_month_of_reference: NDArray[np.intp]
    contract_years: NDArray[np.datetime64]
    contract_year_of_month: NDArray[np.intp]
    curve_axes: CurveAxes | None
    day_in_union: NDArray[np.intp] | None

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
class PairAxes:
    """A pair's observation-day axis, since two-index-fixed-float.md's third pull request: days,
    the union of the two legs' observation days, increasing, and day_in[k], each leg's days'
    places on it, so that a pair's delta or cross-gamma report by day copies each leg's saved
    vector through saved places onto one axis, as a collection of the two legs would; the month
    and year displays are each leg's, made from the one valuation day and placed by their own
    rows. Made once when the batch is made; None for one leg, whose days are the axis."""

    days: NDArray[np.datetime64]
    day_in: tuple[NDArray[np.intp], ...]


@dataclass(frozen=True, slots=True)
class Encoded:
    """The terms by reference, the trade's own arrays derived from them once, all read-only, and
    the legs, one EncodedLeg per leg of the terms in leg order, one today, each holding what its
    index owns, since two-index-fixed-float.md.

    Per payment group, the components of one calculation period and one frequency that pay on
    one day and, since named-curves-slice-3.md, under one discount_curve_key, the period since
    onetime-averaging.md the terms' period_start and period_end, a monthly component's calendar
    month or a onetime row's window, and the frequency since the review of that ticket's third
    slice, so that a month and a window over the same days are two groups, each labelled as its
    own, whatever order the rows came in: the groups in period order, within a period a month's
    before a window's, then by the day they pay and within a day by their key, the keys in the
    order the rows first name them, so that a month whose components pay on two days is two
    groups, two components paying on one day under two keys two groups never netted before
    discounting, and a month under a physical settlement, which pays on no day, one; each
    group's contract on each leg's schedule is the leg's group_contract, the contract of its
    month, and group_head[g], since onetime-averaging.md, its head component, the first in
    component order, from which the group's label is made when a readback or a refusal asks,
    booked_words over the heads, the contract's code of a month and the two dates of a window,
    no text kept; keys, the batch's distinct keys in that
    order, and key_of_group[g] each group's place among them, None with no key, a cleared
    batch's; group_of_component[k]; offset[k], since two-index-one-price.md the trade's fixed
    leg per component, minus the trade's one fixed price times the coefficient of the unit it
    is in, since #273 its row's own and the first leg's where that is the index's, the
    entry-price side of the component's payment in the settlement currency, booked once
    whatever the legs; offset_of_group[g], those summed by group, the trade's fixed leg of the
    group; payment_date[g], the day the group pays, an array for a financial settlement and
    None for a physical one.

    Then reserves, since #170, the batch's booked brokerage and clearing, each charged component's
    count of the first leg's specification times the specification's rate per lot, summed, since
    #188 the brokered rows' components charged brokerage and every component clearing on a
    cleared route and none on a bilateral one, since #175 the marketing reserve the rows booked,
    summed once per row, their currency and its unit, the Reserves record, static for the batch and
    entering no number here; _ReportReserves spills the totals and the results readback shows
    them once.

    Then, since #178, payment_axes, the payment-time axes a DV01 report is summed onto and the
    union of their days with the first leg's observation days, PaymentAxes, made once here for a
    bilateral batch and None for a cleared or a physical one; the month and year displays are
    the preparation's since #186. And pair, since the ticket's third pull request, a pair's
    observation-day axis with each leg's places, PairAxes, None for one leg.

    And closed, since expired-physical-cash.md, for a physical batch and None for a financial
    one: closed[g], whether the group's contract holds no position, the component quantities
    of each quantity unit entered on it adding to exactly zero, whole counts added as whole
    numbers, nothing converted and no allowance, a contract of zero rows alone among them. A
    fact of the rows and of no valuation date, made once here; the preparation settles a closed
    contract past its expiry and refuses an open one."""

    terms: ResolvedTrades
    legs: tuple[EncodedLeg, ...]
    group_of_component: NDArray[np.intp]
    group_head: NDArray[np.intp]
    offset: NDArray[np.float64]
    offset_of_group: NDArray[np.float64]
    payment_date: NDArray[np.datetime64] | None
    reserves: Reserves
    payment_axes: PaymentAxes | None
    keys: tuple[str, ...]
    key_of_group: NDArray[np.intp] | None
    pair: PairAxes | None
    closed: NDArray[np.bool_] | None


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
    currency, DOLLAR or CENT to DOLLAR or CENT, so that a price in cents times it is an amount in
    dollars; every price the batch meets, a quote, a settle or the fixed price, multiplies the
    coefficient and never the quantity. The trade's fixed leg, since two-index-one-price.md
    once whatever the legs: minus the first leg's coefficient times the trade's one fixed
    price, per component, the first leg's coefficient the trade's since the pair rule below
    holds the two legs' equal to within the roundoff of their conversions, as the first leg
    supplies the fees and the handle's first word. Since #273 a row's fixed price may be in a
    unit its index does not quote in, dollars a tonne on an index quoted per pound, and then it
    multiplies the coefficient of its own unit, _the_fixed_coefficient: the component's
    quantity restated in the fixed price's quantity unit through the first leg's specification,
    times the factor from its currency unit to the settlement currency, the price kept as
    entered and no market price touched, the first leg's coefficient itself where every row is
    priced in the index's unit. A float_float, since float-float-spread.md,
    takes its second leg's sign here and nowhere else: a subtracted leg's quote quantities and
    coefficients are made negated, so its exposures, and every amount, delta and lot a later
    stage makes from them, are the price a positive quantity pays; its own side, the spread
    leg, is minus the spread price times the coefficient of the spread price's own unit, since
    float-float-units.md: the component's quantity restated in the spread price's quantity
    unit through the first index's specification, times the factor from its currency unit to
    the settlement currency, _the_spread_coefficient, which reads the unit's two codes for
    their meaning against the tables, so that RB in dollars a gallon less WTI in dollars a
    barrel at a spread price in dollars a barrel is three quantities, each in its own price's
    unit, and no price is converted.
    For a pair, since two-index-fixed-float.md, each occurrence's quantity unit is one quantity
    per entered unit on both indexes: the specification it names on each index restates one
    entered unit in one unit, a fixed_float pair's shared quote quantity unit and a
    float_float's spread price's quantity unit, and the two sizes agree to within
    UNIT_ROUNDOFF, whatever the row's quantity, zero included, a `LOT` of 10,000 MMBTU on one
    index and 2,500 on the other refused as an ambiguous common quantity and not a conversion
    to invent, a THERM on one and 100,000 BTU on the other one quantity; the first occurrence
    that differs is refused by its unit, its trade and the two sizes. Each leg's own arrays are
    made over its leg, the groups shared.
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
    more, and the union of the payment days with every leg's observation days with the payment
    days' places and each leg's places on it, one union and a search each, so that a DV01
    report by payment day and a report of every risk by day copy saved vectors through saved
    places; for a pair the union of the two legs' observation days with each leg's places,
    PairAxes, one unique and two searches, the axis a pair's delta report by day stands on, the
    month and year displays
    being the preparation's since #186; a cleared batch, whose DV01 has no dated axis, makes none
    of this and its ledger stands.

    For a financial settlement, each group pays after its last observation, else its contract and
    its two days are named, since a payment before the last settle exists would have nothing to
    pay. For a physical settlement, since expired-physical-cash.md, the contracts that hold no
    position are found, _the_closed_groups, the component quantities summed by group and
    quantity unit as the whole counts they are, a group and unit holding 2^53 or more in all
    refused, since a number adds whole counts exactly only below it, for the preparation to
    settle a closed contract past its expiry and refuse an open one. The fees of the
    specification are read once, since #170, for the reserves, each
    charged component's count times its specification's rate per lot and the batch's two sums,
    brokerage over the brokered rows' components and clearing over every component of a cleared
    batch since #188,
    and since #175 the rows' marketing reserves summed once each, since cva-reserve.md the
    rows' signed CVA reserves the same, kept beside the encoding and never a contribution to
    value, docs/library/trades/report-reserves.md.

    Work: one component per component, one group per payment group, one observation per
    observation and one slot per slot, reported to the counter; one conversion per distinct
    specification the batch selects, and since #273, where a row's fixed price is in a unit
    its index does not quote in, one more per distinct specification and fixed price unit
    with one currency factor per unit, none where every row is priced in the index's unit;
    the reserves once over the components each fee charges; for
    a physical batch, the components' counts summed once more by group and quantity unit; and,
    for a bilateral batch, one payment day per distinct payment day, the axes made once.
    """
    if len(observations) != len(terms.legs):
        raise ValueError(
            f"observations are {len(observations)} legs' worth, expected {len(terms.legs)}, one "
            "per leg of the terms"
        )
    heads, payment_date, group_of_component, keys, key_of_group = _the_groups(terms)
    groups = heads.size
    # Each leg's quantities and coefficients, a pair held to one quantity per entered unit; then
    # the trade's fixed leg, since two-index-one-price.md once, from the first leg's
    # coefficient, each finite or refused before any slot, the order the one-leg path had.
    amounts = [_the_amounts(terms, leg, units) for leg in terms.legs]
    if terms.instrument is FLOAT_FLOAT:
        # A float_float's spread price has a unit of its own, float-float-units.md, one for
        # the batch: its coefficient is made in that unit, and the quantity rule compares
        # there, each leg's sizes restated through the distinct selections its amounts found.
        priced = _the_spread_coefficient(
            terms, terms.price_units[0], units, [selected for _, _, _, selected in amounts]
        )
    else:
        shared = terms.legs[0].index.conventions.quote_quantity_unit  # the kernel's pair rule
        for leg, (_, _, sizes, _) in zip(terms.legs[1:], amounts[1:], strict=True):
            _the_same_quantity(terms, terms.legs[0], amounts[0][2], leg, sizes, shared)
        priced = _the_fixed_coefficient(terms, amounts[0][1], units)
    offset = _the_price_leg(terms, priced)
    offset_of_group = _the_group_offsets(
        terms, terms.legs[0], heads, group_of_component, offset, payment_date, keys, key_of_group
    )
    parts: list[_LegParts] = []
    for leg, observed, (quote_quantity, coefficient, _, _) in zip(
        terms.legs, observations, amounts, strict=True
    ):
        group_contract = leg.contract[heads]
        reference = _the_references(terms, leg, observed)
        slot_of_observation, slot_group, slot_date, slot_reference = _the_slots(
            group_of_component[observed.component], observed.date, reference
        )
        slot_exposure = _the_exposures(
            terms,
            leg,
            observed,
            coefficient,
            slot_of_observation,
            slot_group.size,
            slot_date,
            slot_reference,
        )
        references, reference_of_slot = np.unique(slot_reference, return_inverse=True)
        days = _the_day_axis(slot_date)
        periods = _the_contract_periods(leg.schedule_month[references])
        if payment_date is not None:
            _payments_after_observations(terms, leg, heads, payment_date, slot_group, slot_date)
        counter.hit(ENCODED_COMPONENTS, int(leg.contract.size))
        counter.hit(ENCODED_OBSERVATIONS, int(observed.component.size))
        counter.hit(ENCODED_SLOTS, int(slot_group.size))
        parts.append(
            _LegParts(
                leg,
                observed,
                (
                    quote_quantity,
                    coefficient,
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
                ),
                days[0],
                days[1],
                references.size,
                periods[1],
                periods[3],
                periods[0].size,
                periods[2].size,
                slot_group,
                reference_of_slot,
            )
        )
    counter.hit(ENCODED_GROUPS, int(groups))
    # A pair's observation-day axis, the two legs' days united, since the ticket's third pull
    # request; one leg's days are its own axis.
    pair = _the_pair_axes([p.days for p in parts], counter) if len(parts) > 1 else None
    # A cleared batch's DV01 has no dated axis; nothing more is made for it and its ledger
    # stands. The payment-time axes are the trade's, over every leg's observation days.
    payment_axes: PaymentAxes | None = None
    day_in_union: tuple[NDArray[np.intp] | None, ...] = (None,) * len(parts)
    if terms.route is Route.BILATERAL and payment_date is not None:
        payment_axes, day_in_union = _the_payment_axes(
            payment_date,
            parts[0].days if pair is None else pair.days,
            [p.days for p in parts],
            counter,
        )
    legs: list[EncodedLeg] = []
    for part, places in zip(parts, day_in_union, strict=True):
        # Since named-curves-slice-3.md the places every curve's risk is summed into at once, made
        # here for a bilateral batch, each leg's over its own slots and references; a batch on
        # one key holds the places above by reference.
        curve_axes = (
            _the_curve_axes(
                len(keys),
                key_of_group,
                part.slot_group,
                part.reference_of_slot,
                part.day_of_slot,
                part.references,
                part.days.size,
                payment_axes,
                part.contract_month_of_reference,
                part.contract_year_of_month,
                part.contract_months,
                part.contract_years,
            )
            if payment_axes is not None and key_of_group is not None
            else None
        )
        for array in part.arrays:
            array.setflags(write=False)
        legs.append(
            EncodedLeg(
                terms,
                part.leg,
                part.observed,
                *part.arrays,
                curve_axes=curve_axes,
                day_in_union=places,
            )
        )
    offset.setflags(write=False)
    offset_of_group.setflags(write=False)
    if payment_date is not None:
        payment_date.setflags(write=False)
    if key_of_group is not None:
        key_of_group.setflags(write=False)
    group_of_component.setflags(write=False)
    heads.setflags(write=False)
    reserved = reserves(terms, counter)
    # A physical batch's closed contracts, expired-physical-cash.md: one sum over its components,
    # here, where the rows are; a financial batch pays on its days and makes none of it.
    closed = (
        _the_closed_groups(terms, heads, group_of_component, groups)
        if payment_date is None
        else None
    )
    return Encoded(
        terms,
        tuple(legs),
        group_of_component,
        heads,
        offset,
        offset_of_group,
        payment_date,
        reserved,
        payment_axes,
        keys,
        key_of_group,
        pair,
        closed,
    )


@dataclass(frozen=True, slots=True)
class _LegParts:
    """One leg's arrays as the first pass over the legs made them, before the axes the trade
    makes over every leg: the leg's terms and observations, the arrays an EncodedLeg holds in
    its order, and the few the curve axes and the unions read, by name."""

    leg: LegTerms
    observed: Observations
    arrays: tuple[NDArray[Any], ...]
    days: NDArray[np.datetime64]
    day_of_slot: NDArray[np.intp]
    references: int
    contract_month_of_reference: NDArray[np.intp]
    contract_year_of_month: NDArray[np.intp]
    contract_months: int
    contract_years: int
    slot_group: NDArray[np.intp]
    reference_of_slot: NDArray[np.intp]


def _the_amounts(
    terms: ResolvedTrades, leg: LegTerms, units: UnitConversions
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.intp]]:
    """A leg's two amounts per component, the quote quantity and the coefficient, each finite or
    refused by its trade and its operation, the quote-unit size of each of the leg's
    specifications, the conversion formed once per distinct specification the batch selects,
    and those distinct specifications, found here once, one unique; the arithmetic runs with
    numpy's flags down and the rules judge."""
    conventions = leg.index.conventions
    selection = leg.specification[terms.occurrence]  # each component's specification row
    selected = np.unique(selection)  # the distinct selections of the batch
    quote_unit = conventions.quote_quantity_unit
    per_price = f"{conventions.currency_unit} per {conventions.quote_currency_unit}/{quote_unit}"
    to_quote_unit = _the_sizes(leg, selected, quote_unit, units)
    with np.errstate(over="ignore", invalid="ignore"):
        to_currency = units.factor(
            CURRENCY, conventions.quote_currency_unit, conventions.currency_unit
        )
        # A subtracted leg's sign, taken here once, float-float-spread.md: its sizes negated
        # before the gather, a handful of numbers, so that its quote quantities, its
        # coefficients and everything later made from them carry it with no step of their own.
        per_unit = -to_quote_unit if leg.subtracted else to_quote_unit
        quote_quantity = terms.component_quantity * per_unit[selection]
        coefficient = quote_quantity * to_currency
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
    ):  # the two products, each checked where it is made and named by its operation
        outrun = ~np.isfinite(values)
        if outrun.any():
            k = int(outrun.argmax())
            raise ValueError(
                f"{terms.named(k)} has {float(values[k])!r} of {what}, expected a finite {unit}; "
                f"{why}"
            )
    return quote_quantity, coefficient, to_quote_unit, selected


def _the_sizes(
    leg: LegTerms, selected: NDArray[np.intp], unit: str, units: UnitConversions
) -> NDArray[np.float64]:
    """The size of each of a leg's specifications in one unit of its quantity type, by
    specification row: the lot size times the unit tables' factor from the lot unit, formed
    once per distinct specification the batch selects, the rows handed in, zero on a row it
    does not, each finite or the first that is not refused by its specification; the
    arithmetic runs with numpy's flags down and the rule judges. The leg's quote quantity unit
    for its own amounts and, since float-float-units.md, the spread price's quantity unit for a
    float_float's spread leg and its quantity rule."""
    conventions = leg.index.conventions
    specifications = leg.index.specifications
    sizes = np.zeros(len(specifications.names))
    with np.errstate(over="ignore", invalid="ignore"):
        for row in selected:  # the distinct selections of the batch, converted once each
            chosen = int(row)
            sizes[chosen] = float(specifications.lot_sizes[chosen]) * units.factor(
                conventions.quantity_type, specifications.lot_units[chosen], unit
            )
            if not np.isfinite(sizes[chosen]):
                raise ValueError(
                    f"specification {specifications.names[chosen]!r} is {sizes[chosen]!r} "
                    f"{unit} a lot, expected a finite number; its lot size times the factor "
                    f"from {specifications.lot_units[chosen]} to {unit} outruns the largest "
                    "number"
                )
    return sizes


def _the_spread_coefficient(
    terms: ResolvedTrades,
    price_unit: PriceUnit,
    units: UnitConversions,
    selected: Sequence[NDArray[np.intp]],
) -> NDArray[np.float64]:
    """What a float_float's spread price multiplies, per component, since float-float-units.md:
    the component's quantity restated in the spread price's quantity unit through the first
    index's specification, times the factor from the spread price's currency unit to the
    settlement currency unit, so that the spread price times it is an amount of the payment's
    currency whatever unit either leg quotes in; the first leg's coefficient to the last bit
    where the spread price's unit is the first index's.

    The unit's two codes are read for their meaning here, once, against the unit tables, the
    first failure being the message: the currency unit a unit of the tables' currency
    category; the quantity unit a unit of the indexes' quantity type, the one both share by
    the kernel's rule; and of heat or of electricity as the two indexes quote in, the kernel's
    rule over the legs carried to the third unit. Then the pair's quantity rule, each
    occurrence's quantity unit one amount on both indexes, the two sizes compared in the
    spread price's quantity unit, _the_same_quantity, each leg's sizes made over selected,
    the distinct specifications its amounts found, in leg order. Each coefficient finite, or
    the first that is not refused by its trade and its operation."""
    first = terms.legs[0]
    conventions = first.index.conventions
    money = units.categories[CURRENCY].sizes
    if price_unit.currency_unit not in money:
        raise ValueError(
            f"spread_price_currency_unit is {price_unit.currency_unit!r}, expected {listed(money)}"
        )
    measure = units.categories[conventions.quantity_type].sizes
    unit = price_unit.quantity_unit
    if unit not in measure:
        raise ValueError(
            f"spread_price_quantity_unit is {unit!r}, expected "
            f"{a_unit_of(conventions.quantity_type, measure)}"
        )
    electric = conventions.quote_quantity_unit in ELECTRICITY
    if (unit in ELECTRICITY) != electric:
        side = [each for each in measure if (each in ELECTRICITY) == electric]
        raise ValueError(
            f"spread_price_quantity_unit is {unit!r}, expected a unit of "
            f"{'electricity' if electric else 'heat'} as the two indexes quote in, {listed(side)}"
        )
    sizes = _the_sizes(first, selected[0], unit, units)
    for leg, rows in zip(terms.legs[1:], selected[1:], strict=True):
        _the_same_quantity(terms, first, sizes, leg, _the_sizes(leg, rows, unit, units), unit)
    selection = first.specification[terms.occurrence]  # each component's specification row
    per_price = f"{conventions.currency_unit} per {price_unit.currency_unit}/{unit}"
    with np.errstate(over="ignore", invalid="ignore"):
        coefficient = (terms.component_quantity * sizes[selection]) * units.factor(
            CURRENCY, price_unit.currency_unit, conventions.currency_unit
        )
    outrun = ~np.isfinite(coefficient)
    if outrun.any():
        k = int(outrun.argmax())
        raise ValueError(
            f"{terms.named(k)} has {float(coefficient[k])!r} of spread coefficient, expected a "
            f"finite amount of {per_price}; its count times its specification's size in the "
            "spread price's unit and the currency factor outruns the largest number"
        )
    return coefficient


def _the_fixed_coefficient(
    terms: ResolvedTrades, floating: NDArray[np.float64], units: UnitConversions
) -> NDArray[np.float64]:
    """What a fixed_float's fixed price multiplies, per component, since #273: the component's
    quantity restated in its row's fixed price's quantity unit through the first index's
    specification, times the factor from that unit's currency unit to the settlement currency
    unit, so that the price as entered times it is an amount of the payment's currency, 50
    tonnes at 1,870 dollars a tonne being 93,500 dollars on an index that quotes per pound. No
    price is converted and the floating side is untouched: `floating`, the first leg's
    coefficient, stays what every market price multiplies.

    A batch priced throughout in the unit its index quotes in, the unit typed or left out, is
    handed `floating` itself, the same numbers, made once. Otherwise each unit the rows are
    priced in is read for its meaning here, once, against the unit tables, _the_fixed_unit, in
    the order the rows first name them, so that the first row from the top with a unit that
    means nothing is the one refused; then one size per distinct specification and unit the
    rows select, _the_sizes, and one currency factor per unit, a handful of numbers gathered
    onto the components, and one product over the array, the first leg's coefficient to the
    last bit on a row priced in the index's own unit. Each coefficient finite, or the first
    that is not refused by its trade and its operation."""
    first = terms.legs[0]
    conventions = first.index.conventions
    if terms.price_units == (
        PriceUnit(conventions.quote_currency_unit, conventions.quote_quantity_unit),
    ):
        return floating
    sizes = np.zeros((len(terms.price_units), len(first.index.specifications.names)))
    to_currency = np.zeros(len(terms.price_units))
    places, first_rows = np.unique(terms.price_unit, return_index=True)
    for at in np.argsort(first_rows):  # the units the rows are priced in, by their first rows
        place = int(places[at])
        unit = terms.price_units[place]
        _the_fixed_unit(terms, unit, int(first_rows[at]), units)
        selected = np.unique(first.specification[terms.price_unit == place])
        sizes[place] = _the_sizes(first, selected, unit.quantity_unit, units)
        to_currency[place] = units.factor(CURRENCY, unit.currency_unit, conventions.currency_unit)
    priced_in = terms.price_unit[terms.occurrence]  # each component's price unit
    selection = first.specification[terms.occurrence]  # and its specification row
    with np.errstate(over="ignore", invalid="ignore"):
        coefficient = (terms.component_quantity * sizes[priced_in, selection]) * to_currency[
            priced_in
        ]
    outrun = ~np.isfinite(coefficient)
    if outrun.any():
        k = int(outrun.argmax())
        unit = terms.price_units[int(priced_in[k])]
        raise ValueError(
            f"{terms.named(k)} has {float(coefficient[k])!r} of fixed coefficient, expected a "
            f"finite amount of {conventions.currency_unit} per {unit.currency_unit}/"
            f"{unit.quantity_unit}; its count times its specification's size in the fixed "
            "price's unit and the currency factor outruns the largest number"
        )
    return coefficient


def _the_fixed_unit(
    terms: ResolvedTrades, unit: PriceUnit, row: int, units: UnitConversions
) -> None:
    """A fixed price's unit read for its meaning against the unit tables, since #273, the first
    failure being the message, named by its own field, the unit's first row and its trade: the
    currency unit a unit of the tables' currency category, DOLLAR or CENT and never the
    currency's own name; the quantity unit a unit of the first index's quantity type, so a
    barrel under a mass index is refused, a price across two measures needing a density the
    tables do not carry, and so is the desk's word for a specification, a lot being a quantity
    and no unit a price is per; and of heat or of electricity as the index quotes in,
    ELECTRICITY, since a megawatt hour is 3.412 MMBTU as energy while a price of power against
    fuel is struck at a heat rate. Each code is matched exactly, never trimmed or re-cased."""
    conventions = terms.legs[0].index.conventions

    def refused(field: str, code: str, expected: str) -> ValueError:
        """The refusal, its trade named only when its unit is refused."""
        return ValueError(
            f"{field} of {named_trade(terms.trade_ids, row)} is {code!r}, expected {expected}"
        )

    money = units.categories[CURRENCY].sizes
    if unit.currency_unit not in money:
        raise refused("fixed_price_currency_unit", unit.currency_unit, listed(money))
    measure = units.categories[conventions.quantity_type].sizes
    per = "fixed_price_quantity_unit", unit.quantity_unit
    if unit.quantity_unit not in measure:
        raise refused(*per, a_unit_of(conventions.quantity_type, measure))
    electric = conventions.quote_quantity_unit in ELECTRICITY
    if (unit.quantity_unit in ELECTRICITY) != electric:
        side = [each for each in measure if (each in ELECTRICITY) == electric]
        raise refused(
            *per,
            f"a unit of {'electricity' if electric else 'heat'} as the index quotes in, "
            f"{listed(side)}; a price of power against fuel is struck at a heat rate, which "
            "is not built",
        )


def _the_price_leg(terms: ResolvedTrades, coefficient: NDArray[np.float64]) -> NDArray[np.float64]:
    """The trade's own side of each component's payment, since two-index-one-price.md: minus
    the coefficient its price multiplies times the trade's one price, in the settlement
    currency, booked once whatever the legs, a fixed_float's fixed leg, since #273 from the
    coefficient of its row's fixed price's own unit, the first leg's where that is the unit
    the index quotes in, and since float-float-spread.md a float_float's spread leg, since
    float-float-units.md from the spread price's own coefficient, named so in a refusal; each
    finite or the first that is not refused by its trade and its operation, the arithmetic
    running with numpy's flags down."""
    currency_unit = terms.legs[0].index.conventions.currency_unit
    with np.errstate(over="ignore", invalid="ignore"):
        offset = -coefficient * terms.price
    outrun = ~np.isfinite(offset)
    if outrun.any():
        k = int(outrun.argmax())
        field, side = price_words(terms.instrument)
        raise ValueError(
            f"{terms.named(k)} has {float(offset[k])!r} of {side}, expected a finite amount "
            f"of {currency_unit}; its coefficient times its {field.replace('_', ' ')} outruns "
            "the largest number"
        )
    return offset


def _the_same_quantity(
    terms: ResolvedTrades,
    first: LegTerms,
    first_sizes: NDArray[np.float64],
    leg: LegTerms,
    sizes: NDArray[np.float64],
    unit: str,
) -> None:
    """The pair's rule, since two-index-fixed-float.md: each occurrence's quantity unit is one
    quantity per entered unit on both indexes, the size of the specification it names on each,
    one entered unit restated in one unit, a fixed_float pair's shared quote quantity unit and
    since float-float-units.md a float_float's spread price's quantity unit, agreeing to within
    UNIT_ROUNDOFF, relative, whatever the row's quantity, zero included; else the first
    occurrence that differs is refused by its unit, its trade and the two sizes, a `LOT` of
    10,000 MMBTU on one index and 2,500 on the other being an ambiguous common quantity and not a
    conversion to invent, while a THERM on one and 100,000 BTU on the other, or a `LOT` of
    42,000 GAL on one and of 1,000 BBL on the other, are one quantity to the roundoff of their
    conversions."""
    theirs = first_sizes[first.specification]
    mine = sizes[leg.specification]
    differs = ~np.isclose(mine, theirs, rtol=UNIT_ROUNDOFF, atol=0.0)
    if not differs.any():
        return
    i = int(differs.argmax())
    name = first.index.specifications.names[int(first.specification[i])]
    raise ValueError(
        f"quantity_unit {name!r} of {named_trade(terms.trade_ids, i)} is {float(theirs[i])!r} "
        f"{unit} on index {first.index.name!r} and {float(mine[i])!r} {unit} on index "
        f"{leg.index.name!r}, expected one quantity per entered unit on both legs"
    )


def _the_group_offsets(
    terms: ResolvedTrades,
    leg: LegTerms,
    heads: NDArray[np.intp],
    group_of_component: NDArray[np.intp],
    offset: NDArray[np.float64],
    payment_date: NDArray[np.datetime64] | None,
    keys: tuple[str, ...],
    key_of_group: NDArray[np.intp] | None,
) -> NDArray[np.float64]:
    """The trade's own sides summed by group, a fixed_float's fixed legs or a float_float's
    spread legs, one bincount, each finite or the first that is not refused by its group, a sum
    blamed on the group and never on one of its trades; the leg given names the group's
    contract in the refusal, the first leg's."""
    with np.errstate(over="ignore", invalid="ignore"):
        offset_of_group = np.bincount(group_of_component, weights=offset, minlength=heads.size)
    outrun = ~np.isfinite(offset_of_group)
    if outrun.any():
        g = int(outrun.argmax())
        group = group_words(terms, leg, heads, payment_date, g, keys, key_of_group)
        side = price_words(terms.instrument)[1]
        raise ValueError(
            f"the {side} of {group} is {float(offset_of_group[g])!r}, expected a finite amount "
            f"of {leg.index.conventions.currency_unit}; its components' {side}s, each finite, "
            "sum past the largest number"
        )
    return offset_of_group


def _the_exposures(
    terms: ResolvedTrades,
    leg: LegTerms,
    observed: Observations,
    coefficient: NDArray[np.float64],
    slot_of_observation: NDArray[np.intp],
    slots: int,
    slot_date: NDArray[np.datetime64],
    slot_reference: NDArray[np.intp],
) -> NDArray[np.float64]:
    """Each slot's exposure, the leg's coefficients times the observations' weights summed onto
    the slots, one bincount; a weight is at most one, so a finite coefficient's weighted exposure
    is finite and only the slot's sum can outrun, the first that does refused by its first trade,
    its day and the contract pricing it."""
    with np.errstate(over="ignore", invalid="ignore"):
        slot_exposure = np.bincount(
            slot_of_observation,
            weights=coefficient[observed.component] * observed.weight,
            minlength=slots,
        )
    outrun = ~np.isfinite(slot_exposure)
    if outrun.any():
        s = int(outrun.argmax())
        j = int((slot_of_observation == s).argmax())  # its first observation
        code = leg.schedule.codes[int(slot_reference[s])]
        conventions = leg.index.conventions
        raise ValueError(
            f"{terms.named(int(observed.component[j]))} on {slot_date[s]}, a day {code} "
            f"prices, has {float(slot_exposure[s])!r} of exposure, expected a finite amount of "
            f"{conventions.currency_unit} per {conventions.quote_currency_unit}/"
            f"{conventions.quote_quantity_unit}; its observations' coefficients times their "
            "weights sum past the largest number"
        )
    return slot_exposure


def group_label(terms: ResolvedTrades, leg: LegTerms, heads: NDArray[np.intp], g: int) -> str:
    """One group's label, since onetime-averaging.md, made from its head component when a
    refusal names the group: the contract's code of a month on that leg's schedule and the two
    dates of a window, booked_words over the one head."""
    return str(booked_words(terms, leg, heads[g : g + 1])[0])


def group_words(
    terms: ResolvedTrades,
    leg: LegTerms,
    heads: NDArray[np.intp],
    payment_date: NDArray[np.datetime64] | None,
    g: int,
    keys: tuple[str, ...] = (),
    key_of_group: NDArray[np.intp] | None = None,
) -> str:
    """A payment group named in a message, since #190: its label, the contract's code of a month
    and since onetime-averaging.md the two dates of a window, and, under a financial settlement,
    the day it pays, `F27 paying on 2027-01-04`, `2026-05-26 to 2026-06-25 paying on 2026-06-29`,
    and since named-curves-slice-3.md its key where the batch has keys, `F27 paying on 2027-01-04
    on SOFR`; a physical group its label alone, since it pays on no day. A sum over a group is
    blamed on the group, never on one of its trades."""
    label = group_label(terms, leg, heads, g)
    words = label if payment_date is None else f"{label} paying on {payment_date[g]}"
    if key_of_group is None:
        return words
    return f"{words} on {keys[int(key_of_group[g])]}"


def _the_groups(
    terms: ResolvedTrades,
) -> tuple[
    NDArray[np.intp],
    NDArray[np.datetime64] | None,
    NDArray[np.intp],
    tuple[str, ...],
    NDArray[np.intp] | None,
]:
    """The payment groups, keyed since onetime-averaging.md by the terms' calculation period, its
    first and its last day, a monthly component's calendar month or a onetime row's window, and
    since the review of that ticket's third slice by the frequency, so that a month and a window
    over the same days, `M26` and `2026-06-01 to 2026-06-30`, are two groups whatever order the
    rows came in, each labelled as its own, and not by the contract: under a financial
    settlement the distinct tuples of period, frequency and payment day among the components, in
    period order, a month's group before a window's within a period and by day, and since
    named-curves-slice-3.md the distinct tuples with the row's key where the batch has keys, by
    key within a day, the keys in the order the rows first name them; under a physical
    settlement, which pays on no day, the distinct periods and frequencies; one lexsort either
    way. Each group's first component, its head, whose
    contract row on each leg's schedule is the group's contract there, the contract of its month,
    its payment day or None, each component's group, the batch's distinct keys and each group's
    key, the keys empty and the key of each group None where the batch has none. The trade's
    periods name the groups; a second leg's components stand in the same periods, so its groups
    are the same."""
    period = (
        terms.period_start.astype(np.int64),
        terms.period_end.astype(np.int64),
        onetime_components(terms),
    )
    if terms.payment is None:
        group_of_component, heads = _distinct(*period)
        return heads, None, group_of_component, (), None
    day = terms.payment.date.astype(np.int64)
    if terms.discount_curve_key is None:
        group_of_component, heads = _distinct(*period, day)
        return heads, terms.payment.date[heads], group_of_component, (), None
    keys = tuple(dict.fromkeys(terms.discount_curve_key))  # distinct, by first appearance
    place = {key: i for i, key in enumerate(keys)}
    key_of_occurrence = np.array([place[key] for key in terms.discount_curve_key], dtype=np.intp)
    key_of_component = key_of_occurrence[terms.occurrence]
    group_of_component, heads = _distinct(*period, day, key_of_component)
    return heads, terms.payment.date[heads], group_of_component, keys, key_of_component[heads]


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


def _the_closed_groups(
    terms: ResolvedTrades,
    heads: NDArray[np.intp],
    group_of_component: NDArray[np.intp],
    groups: int,
) -> NDArray[np.bool_]:
    """Which groups of a physical batch are closed, since expired-physical-cash.md: those whose
    counts left are zero in every quantity unit, position_counts', frozen. A group of a physical
    batch is one contract month. First the one rule that makes the counts exact: the counts a
    group holds in a unit, buys and sells together, are under EXACT_COUNTS in all, else the
    first that are not are refused by their contract and their unit, since a count is the
    entered quantity under month and the entered quantity times its covered days under calday,
    a product and then a running sum of whole numbers, each exact only while it is under 2^53;
    at or past it a lot may be rounded away or in, and a position read closed that is not."""
    left, held = position_counts(terms, group_of_component, groups)
    past = held >= EXACT_COUNTS
    if past.any():
        g, unit = np.unravel_index(int(past.argmax()), past.shape)
        leg = terms.legs[0]
        raise ValueError(
            f"{group_label(terms, leg, heads, int(g))} holds {float(held[g, unit])!r} of "
            f"{leg.index.specifications.names[int(unit)]!r} in all, buys and sells together, "
            f"expected under {EXACT_COUNTS!r}; a physical position is closed by its whole counts "
            "adding to zero, and past 2^53 a number does not add them exactly"
        )
    closed = ~left.any(axis=1)
    closed.setflags(write=False)
    return closed


def position_counts(
    terms: ResolvedTrades, group_of_component: NDArray[np.intp], groups: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """The position each group of a physical batch holds, by quantity unit, since
    expired-physical-cash.md: left[g, u], the sum of the group's component quantities entered in
    the first leg's specification u, the counts the terms formed, the entered quantity under
    month and the entered quantity times its covered days under calday, signed and whole; and
    held[g, u], the sum of their sizes, buys and sells together. Each unit is counted by itself:
    nothing is converted, so a lot bought and its size in a smaller unit sold are two counts and
    no closed position, and no allowance is made, the counts being whole numbers. One bincount
    each. Where held is under EXACT_COUNTS every count and every partial sum is a whole number
    a float holds, so left is exact; the encoding refuses a batch where it is not, once, and
    the preparation's refusal reads left again for the count it names, on the failing path
    alone."""
    leg = terms.legs[0]  # a physical batch has one leg, the kernel's rule
    units = len(leg.index.specifications.names)
    place = group_of_component * units + leg.specification[terms.occurrence]
    counts = terms.component_quantity
    with np.errstate(over="ignore", invalid="ignore"):  # the encoding's rule is the judge
        left = np.bincount(place, weights=counts, minlength=groups * units)
        held = np.bincount(place, weights=np.abs(counts), minlength=groups * units)
    return left.reshape(groups, units), held.reshape(groups, units)


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
    holiday calendar, contracts and methods and the trade's nearbys, each component named as
    the terms name its trade."""
    return observation_references(
        leg.schedule,
        leg.index.holiday_calendar,
        observations,
        leg.contract,
        leg.schedule_method[terms.occurrence],
        terms.nearby[terms.occurrence],
        terms.named,
    )


def observation_references(
    schedule: TradeSchedule,
    holiday_calendar: HolidayCalendar | None,
    observations: Observations,
    contract: NDArray[np.intp],
    method: NDArray[np.intp],
    nearby: NDArray[np.intp],
    named: Callable[[int], str],
) -> NDArray[np.intp]:
    """Each observation's reference, the contract pricing its day, for a batch of trades and
    since template-based-quoting.md for a quote alike: contract[k], method[k] and nearby[k] the
    k-th component's schedule row, method and nearby, and named(k) the words a refusal gives
    it. On a futures index: the day open on the index's market, within the schedule, and under
    the expiry-based methods the component's own contract; under asian whichever contract the
    calendar gives, one gather of the methods onto the observations. Since nearby-selection.md
    the contract is the component's nearby counted from the day's prompt, the calendar's
    contract for the day: the prompt's row plus the nearby less one, the prompt itself at 1,
    found afresh for every day so that it moves on the day after an expiry; a nearby the
    schedule lists no contract for on a day is refused by the trade, the day, the day's
    prompt and the schedule's last contract. On a published index: the month the day's print
    counts toward, read off the schedule's row for that print, a day that is no print's date
    refused; no calendar is read, a published index having none."""
    match schedule:
        case PublishedSchedule() as published:
            # The month the print counts toward, read off the schedule's row for that print: one
            # search of the schedule's dates, each day given being a print's date, else refused.
            # No calendar is read, a published index having no holiday calendar.
            listed = published.publication_date
            rows = np.searchsorted(listed, observations.date)
            unlisted = rows >= listed.size
            inside = ~unlisted
            unlisted[inside] = listed[rows[inside]] != observations.date[inside]
            if unlisted.any():
                j = int(unlisted.argmax())
                raise ValueError(
                    f"{named(int(observations.component[j]))} observes "
                    f"{observations.date[j]}, expected the publication date of one of the "
                    "index's prints; a published index prices on its prints alone"
                )
            return published.contract[rows]
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
    reference = contract_on(schedule, observations.date)  # each day's prompt, then its nearby
    beyond = reference >= len(codes)
    if beyond.any():
        j = int(beyond.argmax())
        raise ValueError(
            f"{named(int(observations.component[j]))} observes {observations.date[j]}, "
            f"after the schedule's last expiry, {schedule.future_expiry[-1]}; nothing prices it"
        )
    position = nearby[observations.component]
    reference += position
    reference -= 1
    unlisted = reference >= len(codes)
    if unlisted.any():
        j = int(unlisted.argmax())
        prompt = int(reference[j]) - int(position[j]) + 1
        raise ValueError(
            f"{named(int(observations.component[j]))} observes {observations.date[j]} at nearby "
            f"{int(position[j])}, expected at most {len(codes) - prompt} that day, "
            f"{codes[prompt]!r} being prompt and {codes[-1]!r} the schedule's last contract; the "
            "schedule lists no contract for a later nearby"
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
    date: NDArray[np.datetime64],
) -> tuple[NDArray[np.datetime64], NDArray[np.intp]]:
    """The day axis a delta report by day is summed onto, static for the batch: the distinct
    observation days, increasing, with each slot's day. One unique over the slots, nothing per
    trade and no day without an observation; no contract per day, since nearby-selection.md,
    a day being read on whatever contracts its slots name."""
    days, day_of_slot = np.unique(date, return_inverse=True)
    return days, day_of_slot


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
    observed: NDArray[np.datetime64],
    leg_days: list[NDArray[np.datetime64]],
    counter: WorkCounter,
) -> tuple[PaymentAxes, tuple[NDArray[np.intp], ...]]:
    """The payment-time axes of a bilateral batch, since #178: the distinct payment days of every
    group with each group's place, the months those days fall in with each day's, the years with
    each month's, three uniques; and the union of the observation days given, one leg's or a
    pair's united, and the payment days, one union, with the payment days' places and each leg's
    days' places on it, a search each, so that a report of every risk by day copies the saved
    vectors onto one axis through saved places; the month and year displays are the
    preparation's since #186. Every array frozen; one payment day per distinct payment day
    reported to the counter. The axes, and each leg's places in leg order."""
    paid, day_of_group = np.unique(payment_date, return_inverse=True)
    month_keys, month_of_day = np.unique(paid.astype("datetime64[M]"), return_inverse=True)
    year_keys, year_of_month = np.unique(month_keys.astype("datetime64[Y]"), return_inverse=True)
    paid_months = month_keys.astype("datetime64[D]")
    paid_years = year_keys.astype("datetime64[D]")
    union, places, paid_in = _the_union(observed, paid, leg_days)
    arrays = (
        paid,
        day_of_group,
        paid_months,
        month_of_day,
        paid_years,
        year_of_month,
        union,
        paid_in,
    )
    for array in (*arrays, *places):
        array.setflags(write=False)
    counter.hit(ENCODED_PAYMENT_DAYS, int(paid.size))
    return PaymentAxes(*arrays), places


def _the_union(
    observed: NDArray[np.datetime64],
    paid: NDArray[np.datetime64],
    leg_days: list[NDArray[np.datetime64]],
) -> tuple[NDArray[np.datetime64], tuple[NDArray[np.intp], ...], NDArray[np.intp]]:
    """The union of the observation days and the payment days, increasing, with each leg's days'
    places and the payment days' places on it: one union, a search per leg and one more."""
    union = np.union1d(observed, paid)
    places = tuple([np.searchsorted(union, days) for days in leg_days])
    return union, places, np.searchsorted(union, paid)


def _the_pair_axes(leg_days: list[NDArray[np.datetime64]], counter: WorkCounter) -> PairAxes:
    """A pair's observation-day axis, since two-index-fixed-float.md's third pull request: the
    two legs' days united, one unique over their concatenation, with each leg's places, one
    search each; every array frozen, the days reported to the counter."""
    days = np.unique(np.concatenate(leg_days))
    day_in = tuple([np.searchsorted(days, each) for each in leg_days])
    for array in (days, *day_in):
        array.setflags(write=False)
    counter.hit(ENCODED_PAIR_DAYS, int(days.size))
    return PairAxes(days, day_in)


def _the_slots(
    group: NDArray[np.intp], date: NDArray[np.datetime64], reference: NDArray[np.intp]
) -> tuple[NDArray[np.intp], NDArray[np.intp], NDArray[np.datetime64], NDArray[np.intp]]:
    """The distinct triples of group, day and contract among the observations, since
    nearby-selection.md, in group order, by day within a group and by contract within a day,
    and each observation's slot; a slot's group, day and reference are its first
    observation's, and every observation of the slot shares them."""
    slot_of_observation, heads = _distinct(group, date.astype(np.int64), reference)
    return slot_of_observation, group[heads], date[heads], reference[heads]


def _payments_after_observations(
    terms: ResolvedTrades,
    leg: LegTerms,
    heads: NDArray[np.intp],
    payment_date: NDArray[np.datetime64],
    slot_group: NDArray[np.intp],
    slot_date: NDArray[np.datetime64],
) -> None:
    """A financial settlement's rule, the kernel's one owner of it since
    payment-day-date-or-rule.md, applied here to the groups: each group pays after its last
    observation, the day its final price exists; the first group paying on or before it is
    refused by its label and the two days. The slots stand in group order and by day, so each
    group's last slot is its last observation, and every group has one, every component
    observing at least once."""
    last = np.ones(slot_group.size, dtype=np.bool_)
    last[:-1] = slot_group[1:] != slot_group[:-1]
    payments_after_observations(
        payment_date, slot_date[last], lambda g: group_label(terms, leg, heads, g)
    )
