"""The encoded batch prepared against one market history: which slots have fixed and at what
settle, which payment groups have settled, what remains live and the exposure to each live
reference, and the risk that no tick changes, the price sensitivity in the settlement currency,
the delta in lots of the index's reporting lot by contract and the same lots by observation day
and, since #186, by the pricing contracts' calendar month and year, the three views _ReportRisk
selects among. One record per
history; a tick reads it and makes nothing of it again. docs/library/trades/kernel.md is the
page."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import assert_never, cast

import numpy as np
from numpy.typing import NDArray

from catalyst.calendar.calendar import Calendar
from catalyst.globals.payments import compensated, time_fractions
from catalyst.index_definitions.futures_schedule import FuturesSchedule
from catalyst.index_definitions.iferc_schedule import IfercSchedule
from catalyst.index_definitions.index_conventions import IndexConventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market_history import MarketHistory
from catalyst.trades.display_axes import EarlyRisk, PeriodAxis, early_risk, period_axis
from catalyst.trades.encoding import Encoded, EncodedLeg, PaymentAxes, counts_left, group_words
from catalyst.trades.terms import Route, price_words

PREPARED_SLOTS = "prepared_slots"  # slots placed on the calendar and told live from fixed
FIXINGS_READ = "fixings_read"  # settles read off the history, one per fixed slot
PAYMENT_DAYS_MAPPED = "payment_days_mapped"  # distinct unpaid payment days, bilateral, since #176
DISPLAY_PERIODS = "display_periods"  # periods of the month and year display axes made, since #186


@dataclass(frozen=True, slots=True)
class KeyPayments:
    """One key's unpaid groups, since named-curves-slice-3.md, for the factor reads off its curve:
    groups, their positions among the batch's groups, increasing; days, their distinct payment
    days, increasing; and day_of_group[i], the position among days of groups[i]'s day. A batch on
    one key holds the unpaid groups themselves, by reference."""

    groups: NDArray[np.intp]
    days: NDArray[np.datetime64]
    day_of_group: NDArray[np.intp]


@dataclass(frozen=True, slots=True)
class UnpaidPayments:
    """The unpaid payment groups, since #176, for the bilateral path to value and gather factors
    by: groups, the positions among the batch's groups of those not yet settled, increasing;
    tau[i], the calendar days from the valuation date to groups[i]'s payment day over 365,
    ACT/365F; and since named-curves-slice-3.md by_key, one KeyPayments per key of the batch in
    key order, each key's unpaid groups and their distinct days, the days a tick reads off that
    key's curve. Made once when the batch is prepared, since the groups settled and the valuation
    date change only then, so that a tick sorts and counts no day; None for a cleared batch,
    which discounts nothing, and for a physical one, which pays on no day."""

    groups: NDArray[np.intp]
    tau: NDArray[np.float64]
    by_key: tuple[KeyPayments, ...]


@dataclass(frozen=True, slots=True)
class PreparedLeg:
    """One leg's side of the preparation, since two-index-fixed-float.md: the leg's encoding and
    the history it was prepared against, by reference, and what the two make together, read-only.

    Per slot, aligned with the leg's slots: is_fixed[s], whether the slot's day is on the fixed
    side of the valuation date, so its price is the history's settle on that day, else a quote;
    dated_live_exposure[s], the slot's exposure where it is live and zero where it has fixed, a
    contribution of nothing rather than a price of nothing, the settlement currency per unit of
    quote price; dated_live_lots[s], the same exposure counted in lots of the index's reporting
    lot, the exposure over the lot's coefficient. Per payment group, aligned with the trade's
    groups: set_amount[g], the sum over the group's fixed slots on this leg of exposure times
    settle, the leg's fixed amount of the group. And since observation-prices-readback.md the
    two facts that sum is made of, kept beside it: settle[k], the settle read for the k-th fixed
    slot, in slot order and aligned with the fixed slots alone, the index's quote unit; and
    fixed_contribution[s], aligned with the leg's slots, each slot's exposure times its settle
    where it has fixed and zero where it is live, the floating leg's amount of a fixed slot,
    which the results readback shows and nothing prices again.

    Then the live side for the tick: live_slot, the positions of the live slots on the dated axis;
    live_references, the schedule rows of the distinct contracts those slots reference, in the
    schedule's order, which the market takes to answer their quotes; reference_of_live_slot, each
    live slot's place among them, so that one quote per reference is gathered onto the slots.
    And the risk, which no tick changes: price_sensitivity[r], the live exposure summed by
    reference over the leg's whole axis, the encoding's references, zero where every slot of a
    reference has fixed, the settlement currency the mark moves for a move of one unit of quote
    price in that contract; nominal_delta[r], the same sensitivity over the reporting lot's
    coefficient, the leg's exposure still to price in lots of that specification, signed and
    fractional, a fully live lot one and a lot half of whose observation weight has fixed a
    half; nominal_delta_total, their sum; and since #166 the same lots by time, daily_lots[d]
    the live lots summed onto the encoding's observation days, and since #186 monthly_lots[m]
    the nominal delta by reference summed onto the encoding's contract months and yearly_lots[y]
    onto its contract years, the month and the year a contract is named for whatever days it is
    observed on, the three views _ReportRisk selects among, a bucket's lots zero once its
    contracts have fixed and its row kept; every one of them checked finite before the record is
    made; the result shares them. And since #186, risk-contract-month-bucketing.md, by_month and
    by_year, the display axes of the month and the year reports, PeriodAxis, consecutive periods
    from the valuation day's through the farthest contract or payment period with every saved
    period's place, made here since the valuation day is the history's; and early_nominal, the
    facts refusing a month or a year report whose nominal lots stand in a period before the
    start, or none, which a reader words with the measure asked for and raises, scanning
    nothing; a cleared result's delta, the same lots, is refused from the same facts."""

    encoded: EncodedLeg
    history: MarketHistory
    is_fixed: NDArray[np.bool_]
    dated_live_exposure: NDArray[np.float64]
    dated_live_lots: NDArray[np.float64]
    set_amount: NDArray[np.float64]
    settle: NDArray[np.float64]
    fixed_contribution: NDArray[np.float64]
    live_slot: NDArray[np.intp]
    live_references: NDArray[np.intp]
    reference_of_live_slot: NDArray[np.intp]
    price_sensitivity: NDArray[np.float64]
    nominal_delta: NDArray[np.float64]
    nominal_delta_total: float
    daily_lots: NDArray[np.float64]
    monthly_lots: NDArray[np.float64]
    yearly_lots: NDArray[np.float64]
    by_month: PeriodAxis
    by_year: PeriodAxis
    early_nominal: EarlyRisk


@dataclass(frozen=True, slots=True)
class PreparedTrades:
    """The encoding by reference, the legs, one PreparedLeg per leg of the encoding in leg order,
    one today, each prepared against its own history, and what the trade makes of them together,
    read-only, since two-index-fixed-float.md.

    Per payment group, aligned with the encoding's groups, a contract paying on two days being
    two of them: is_settled[g], whether every slot of the group on every leg has fixed and it
    pays on or before the valuation date, so its amount is modeled as cash; under a physical
    settlement, which pays on no day, since expired-physical-cash.md whether the group's contract
    has expired, the batch holding no position on it, its fixed legs alone its cash; the set
    amounts stay each leg's, since two-index-one-price.md, never summed apart from the payment
    or the total they enter. Then the totals: offset_unsettled, the fixed legs of the groups not
    yet settled in all, and set_unsettled, each leg's set amounts of those groups in all, one
    per leg in leg order, which the tick sums with the legs' live amounts for the mark under one
    compensation; and cash, the whole amounts of the settled groups, fixed leg and set amounts
    together, moved out of the mark on the day they pay and never discounted. And since #176,
    for a bilateral financial batch,
    unpaid_payments, the distinct payment days of the groups not yet settled with each such
    group's place among them and its time fraction, made once here, since the groups settled and
    the valuation date change only when a batch is prepared again, so that a tick gathers the
    curve's factors and sorts nothing; None for a cleared batch and for a physical one."""

    encoded: Encoded
    legs: tuple[PreparedLeg, ...]
    is_settled: NDArray[np.bool_]
    offset_unsettled: float
    set_unsettled: tuple[float, ...]
    cash: float
    unpaid_payments: UnpaidPayments | None


def _the_slot_rows(leg: EncodedLeg, calendar: Calendar) -> NDArray[np.intp]:
    """Each slot's row of the calendar: calendar_rows over the leg's slots' days, a slot named by
    its first trade."""
    return calendar_rows(leg.leg.schedule, leg.slot_date, calendar, leg.slot_trade)


def calendar_rows(
    schedule: FuturesSchedule | IfercSchedule,
    days: NDArray[np.datetime64],
    calendar: Calendar,
    named: Callable[[int], str],
) -> NDArray[np.intp]:
    """Each day's row of the calendar, by the kind of schedule, for a batch's slots and since
    template-based-quoting.md for a quote's observations alike, named(i) the words a refusal
    gives the i-th day. On a futures schedule the day's offset from the calendar's first day, one
    subtraction, a day before it refused by name: the first contract only bounds the calendar
    and nothing prices its days. On an IFERC schedule, since #167, the row whose publication day
    is the day given, one searchsorted over the calendar's days, every day given being a
    publication day by the encoding's rule and the first month a month like any other, nothing
    bounding it."""
    match schedule:
        case FuturesSchedule():
            rows = (days - calendar.dates[0]).astype(np.intp)
            if (rows < 0).any():
                s = int((rows < 0).argmax())
                raise ValueError(
                    f"{named(s)} observes {days[s]}, before the calendar begins on "
                    f"{calendar.dates[0]}; the schedule's first contract, {schedule.codes[0]}, "
                    "bounds the calendar and nothing prices its days"
                )
            return rows
        case IfercSchedule():
            return np.searchsorted(calendar.dates, days).astype(np.intp)
        case _:
            assert_never(schedule)


def _unpaid_payments(
    encoded: Encoded, unsettled: NDArray[np.bool_], as_of: np.datetime64, counter: WorkCounter
) -> UnpaidPayments | None:
    """The mapping a bilateral batch's ticks gather the curves' factors by, since #176, made once
    here, where the groups settled and the valuation date are decided, and for a bilateral batch
    alone, a cleared one discounting nothing: None for a physical batch, which pays on no day and
    which the evaluation refuses a collection; else the groups not yet settled with their time
    fractions, ACT/365F, and since named-curves-slice-3.md per key, in key order, that key's
    unpaid groups and their distinct payment days with each group's place among them, one unique
    per key, a batch on one key holding the unpaid groups themselves; every array frozen. Work:
    one day mapped per distinct payment day of each key, a day two keys pay on mapped once per
    key, reported to the counter; nothing on a tick."""
    if encoded.payment_date is None:
        return None
    groups = np.flatnonzero(unsettled)
    pays = encoded.payment_date[groups]
    tau = time_fractions(as_of, pays)
    key_of_group = cast(NDArray[np.intp], encoded.key_of_group)  # bilateral: keyed
    by_key: list[KeyPayments] = []
    mapped = 0
    if len(encoded.keys) == 1:
        days, day_of_group = np.unique(pays, return_inverse=True)
        by_key.append(KeyPayments(groups, days, day_of_group))
    else:
        key_of_unpaid = key_of_group[groups]
        for key in range(len(encoded.keys)):
            picked = key_of_unpaid == key
            days, day_of_group = np.unique(pays[picked], return_inverse=True)
            picked_groups = groups[picked]
            picked_groups.setflags(write=False)
            by_key.append(KeyPayments(picked_groups, days, day_of_group))
    for keyed in by_key:
        for array in (keyed.days, keyed.day_of_group):
            array.setflags(write=False)
        mapped += int(keyed.days.size)
    for array in (groups, tau):
        array.setflags(write=False)
    counter.hit(PAYMENT_DAYS_MAPPED, mapped)
    return UnpaidPayments(groups, tau, tuple(by_key))


def _the_set_amounts(
    encoded: Encoded,
    leg: EncodedLeg,
    is_fixed: NDArray[np.bool_],
    settles: NDArray[np.float64],
    currency: str,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Each group's set amount: each fixed slot's, its exposure times its settle, summed by group,
    one bincount; since #190 each finite before anything is made of it, the arithmetic
    running with numpy's flags down, else the first slot that is not is refused by its trade, its
    day and its settle, and then the first group by its contract and payment day, a sum blamed on
    the group and never on one of its trades. The slots' amounts come back beside the sums,
    since observation-prices-readback.md, for the record to keep: the floating leg's amount of
    each fixed slot and zero for a live one."""
    with np.errstate(over="ignore", invalid="ignore"):
        set_of_slot = np.zeros(is_fixed.size)
        set_of_slot[is_fixed] = leg.slot_exposure[is_fixed] * settles
        set_amount = np.bincount(
            leg.slot_group, weights=set_of_slot, minlength=leg.group_contract.size
        )
    outrun = ~np.isfinite(set_of_slot)
    if outrun.any():
        s = int(outrun.argmax())
        settle = float(settles[int(np.count_nonzero(is_fixed[:s]))])  # the fixed slots before it
        raise ValueError(
            f"{leg.named_slot(s)}, fixed at {settle!r}, has {float(set_of_slot[s])!r} of set "
            f"amount, expected a finite amount of {currency}; its exposure times the settle "
            "outruns the largest number"
        )
    outrun = ~np.isfinite(set_amount)
    if outrun.any():
        g = int(outrun.argmax())
        group = group_words(
            encoded.terms,
            leg.leg,
            encoded.group_head,
            encoded.payment_date,
            g,
            encoded.keys,
            encoded.key_of_group,
        )
        raise ValueError(
            f"the set amount of {group} is {float(set_amount[g])!r}, expected a finite amount of "
            f"{currency}; its fixed slots' set amounts, each finite, sum past the largest number"
        )
    return set_amount, set_of_slot


def _the_sensitivity(
    leg: EncodedLeg, dated_live_exposure: NDArray[np.float64], conventions: IndexConventions
) -> NDArray[np.float64]:
    """The price sensitivity by reference, the live exposure summed over the batch's whole axis,
    one bincount, zero where every slot of a reference has fixed; since #190 finite by contract,
    the sum running with numpy's flags down, else the first that is not is refused by its
    contract."""
    with np.errstate(over="ignore", invalid="ignore"):
        price_sensitivity = np.bincount(
            leg.reference_of_slot,
            weights=dated_live_exposure,
            minlength=leg.references.size,
        )
    outrun = ~np.isfinite(price_sensitivity)
    if outrun.any():
        r = int(outrun.argmax())
        raise ValueError(
            f"{leg.leg.schedule.codes[int(leg.references[r])]} has "
            f"{float(price_sensitivity[r])!r} of price sensitivity, expected a finite amount of "
            f"{conventions.currency_unit} per {conventions.quote_currency_unit}/"
            f"{conventions.quote_quantity_unit}; its live exposures, each finite, sum past the "
            "largest number"
        )
    return price_sensitivity


def _the_totals(
    encoded: Encoded,
    legs: tuple[PreparedLeg, ...],
    is_settled: NDArray[np.bool_],
    unsettled: NDArray[np.bool_],
    currency: str,
) -> tuple[float, float, tuple[float, ...]]:
    """The cash, the settled groups' fixed legs and set amounts, and the totals a tick sums with
    the live amounts for the mark, kept for both routes: the unsettled groups' fixed legs in
    all and, since two-index-one-price.md one per leg, each leg's unsettled set amounts in all,
    kept apart so that the mark sums them with the legs' live amounts under one compensation.
    Each group's cash is its signed terms, the fixed leg and each leg's set amount, summed with
    Neumaier's compensation, so that a small leg's dollar survives a strike that cancelled the
    large leg's; every sum finite since #190, the arithmetic running with numpy's flags down,
    else refused for the batch by its total, the cash first, a pair's set amounts by the leg's
    index. A physical batch's settled groups are its closed contracts past their expiry, since
    expired-physical-cash.md, and their cash is their fixed legs alone, no set amount added and
    no compensated sum made: the quantity the final price would multiply is zero."""
    physical = encoded.payment_date is None
    with np.errstate(over="ignore", invalid="ignore"):
        if physical:
            settled_amounts = encoded.offset_of_group
        else:
            settled_amounts = compensated(
                [encoded.offset_of_group, *[leg.set_amount for leg in legs]]
            )
        cash = float(settled_amounts[is_settled].sum())
        offset_unsettled = float(encoded.offset_of_group[unsettled].sum())
        set_unsettled = tuple([float(leg.set_amount[unsettled].sum()) for leg in legs])
    if not np.isfinite(cash):
        summed = (
            "closed contracts' fixed legs"
            if physical
            else "settled groups' offsets and set amounts"
        )
        raise ValueError(
            f"the batch has {cash!r} of cash in all, expected a finite amount of {currency}; the "
            f"{summed} sum past the largest number"
        )
    if not np.isfinite(offset_unsettled):
        side = price_words(encoded.terms.instrument)[1]  # a float_float's is its spread leg
        raise ValueError(
            f"the batch has {offset_unsettled!r} of unsettled {side} in all, expected a finite "
            f"amount of {currency}; the unsettled groups' {side}s, each finite, sum past the "
            "largest number"
        )
    for leg, total in zip(legs, set_unsettled, strict=True):
        if not np.isfinite(total):
            whose = (
                "the batch"
                if len(legs) == 1
                else f"the leg of index {leg.encoded.leg.index.name!r}"
            )
            raise ValueError(
                f"{whose} has {total!r} of unsettled set amount in all, expected a finite amount "
                f"of {currency}; the unsettled groups' set amounts, each finite, sum past the "
                "largest number"
            )
    return cash, offset_unsettled, set_unsettled


def _open_past_expiry(encoded: Encoded, g: int, expiry: np.datetime64, as_of: np.datetime64) -> str:
    """The words for a physical contract past its expiry with a position left, since
    expired-physical-cash.md: the contract, its expiry and the valuation date, the first quantity
    unit whose count is not zero with that count, signed, and the first trade entered in that
    unit on the contract. The counts are made again here, on the failing path alone, the
    encoding having kept the flag and nothing else."""
    terms = encoded.terms
    leg = encoded.legs[0]
    left = counts_left(terms, encoded.group_of_component, encoded.offset_of_group.size)[g]
    unit = int((left != 0).argmax())
    entered = leg.leg.specification[terms.occurrence]
    k = int(((encoded.group_of_component == g) & (entered == unit)).argmax())
    code = leg.leg.schedule.codes[int(leg.group_contract[g])]
    return (
        f"{code} expired {expiry}, before valuation date {as_of}, with {float(left[unit])!r} of "
        f"{leg.leg.index.specifications.names[unit]!r} open, {terms.named(k)} among them; a "
        "physical position open past its expiry is a delivery, which is not modeled"
    )


def prepared_trades(
    encoded: Encoded, histories: Sequence[MarketHistory], counter: WorkCounter
) -> PreparedTrades:
    """The one way to make a PreparedTrades: four rules, checked once, in this order, the first
    failure being the message; then the arrays, one pass over the slots and one read per fixed slot.

    The histories are one per leg of the trades, since two-index-fixed-float.md, matched to the
    legs by the exact index object whatever their order, else refused: one history more or
    fewer by the count, a history over none of the legs' indexes or a second over one of them
    by its position, and the two valued on one day, the second's valuation day held to the
    first's; each is over its leg's index, the one object the leg holds, as the history
    itself requires of its fixings; another index of the same name is another index. A group
    is settled when every slot of every leg has fixed and its payment day has come, so a
    common payment is never cash while one leg's observation is live; the set amounts stay
    each leg's, since two-index-one-price.md, summed with the fixed leg and the live amounts
    only where a payment or a total is formed, with Neumaier's compensation. On a
    futures index each slot's day is a day of the calendar, which runs from the day after the
    schedule's first expiry to its last: the first contract only bounds the calendar, so a slot
    on or before its expiry is refused by name, nothing ever pricing it. On an IFERC index,
    since #167, each slot's
    day is a month's publication day and its row that month's, found by one search, the first
    month a month like any other. A slot has fixed when the calendar marks its day fixed, which
    is the day after it at the earliest, an observation staying live on its own day as the
    calendar's rule says. A physical fixed_float whose contract has expired, its expiry day marked
    fixed, is settled where the batch holds no position on it, since expired-physical-cash.md:
    the encoding's flag, the whole counts of each quantity unit on the contract adding to exactly
    zero, and the group's fixed legs alone are its cash, the final price multiplying a quantity
    of zero and entering nothing. Where a count is left it is refused, naming the contract, its
    expiry and the valuation date, the count, its unit and a trade holding it: delivery is not
    modeled, and nothing is omitted, zeroed, kept in mark or moved to cash in its place; the
    contract's expiry decides, not an earlier observation's fixing. A fixed slot takes
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
    in, and no specification is looked up and nothing is converted here or on a tick. Every
    number made here is finite, else the first that is not is refused by its operation, the
    fourth rule, the arithmetic running with numpy's flags down and the rules judging in this
    order since #190, reject-nonfinite-trade-arithmetic.md: each fixed slot's set amount, its
    exposure times its settle, named by the slot and the settle; each group's set amount, a sum
    blamed on the group by its contract and payment day; each contract's price sensitivity, its
    live exposures summed; then the live lots, the nominal deltas and their total, since #164, where
    a lot small enough, a BTU against quantities in the trillions of MMBTU, divides a finite
    exposure past the largest number once it is counted in lots; the lots by day, month and
    year; the cash, since #176, the settled groups' offsets and set amounts; and the unsettled
    fixed legs and set amounts in all, the two totals a tick adds to the live amount. Nothing
    is published that a reader would then fail on. For a bilateral financial batch the unpaid
    groups' payment days are mapped here
    once, _unpaid_payments, for the ticks to gather the curve's factors by.

    Work: one slot prepared per slot and one settle read per fixed slot, reported to the
    counter, and since #186 the periods of the two display axes made; nothing per component,
    nothing per observation, nothing per day of the calendar.
    """
    terms = encoded.terms
    legs = encoded.legs
    if len(histories) != len(legs):
        raise ValueError(
            f"histories are {len(histories)}, expected {len(legs)}, one per leg of the trades"
        )
    matched = _the_histories(legs, histories)
    first_calendar = matched[0].calendar
    as_of = first_calendar.valuation_date.as_of
    groups = encoded.offset_of_group.size
    # Each leg's slots on its own calendar, told live from fixed, before the groups are settled,
    # since a group is settled when every slot of every leg has fixed.
    placed = [
        _the_slot_rows(leg, history.calendar) for leg, history in zip(legs, matched, strict=True)
    ]
    fixed = [history.calendar.is_fixed[rows] for rows, history in zip(placed, matched, strict=True)]
    if encoded.payment_date is None:
        # A physical batch is a futures batch on one leg: the kernel refuses a physical IFERC one
        # and a physical pair. Since expired-physical-cash.md a contract past its expiry is
        # settled where the batch holds no position on it and refused where it holds one.
        leg = legs[0]
        closed = cast(NDArray[np.bool_], encoded.closed)  # physical: a flag per group
        expiries = cast(FuturesSchedule, leg.leg.schedule).future_expiry[leg.group_contract]
        expired = first_calendar.is_fixed[(expiries - first_calendar.dates[0]).astype(np.intp)]
        delivered = expired & ~closed
        if delivered.any():
            g = int(delivered.argmax())
            raise ValueError(_open_past_expiry(encoded, g, expiries[g], as_of))
        is_settled = expired
    else:
        unfixed = np.bincount(legs[0].slot_group, weights=~fixed[0], minlength=groups)
        for leg, is_fixed in zip(legs[1:], fixed[1:], strict=True):
            unfixed = unfixed + np.bincount(leg.slot_group, weights=~is_fixed, minlength=groups)
        is_settled = (unfixed == 0) & (encoded.payment_date <= as_of)
    paid = encoded.payment_axes
    prepared = tuple(
        [
            _the_prepared_leg(encoded, leg, history, rows, is_fixed, as_of, paid, counter)
            for leg, history, rows, is_fixed in zip(legs, matched, placed, fixed, strict=True)
        ]
    )
    currency = legs[0].leg.index.conventions.currency_unit
    unsettled = ~is_settled
    cash, offset_unsettled, set_unsettled = _the_totals(
        encoded, prepared, is_settled, unsettled, currency
    )
    # A cleared batch discounts nothing and runs nothing more here; its ledgers stand.
    unpaid_payments = (
        _unpaid_payments(encoded, unsettled, as_of, counter)
        if terms.route is Route.BILATERAL
        else None
    )
    is_settled.setflags(write=False)
    return PreparedTrades(
        encoded, prepared, is_settled, offset_unsettled, set_unsettled, cash, unpaid_payments
    )


def _the_histories(
    legs: tuple[EncodedLeg, ...], histories: Sequence[MarketHistory]
) -> tuple[MarketHistory, ...]:
    """Each leg's history among those given, in leg order: with one leg the one history, over the
    leg's index, the one object, else refused; with two, since two-index-fixed-float.md, each
    history matched to the leg whose index it is over whatever the order given, a history over
    none of the legs' indexes or a second over one of them refused by its position, and the
    two valued on one day, the second's valuation day held to the first's, since the trades are
    prepared on one day."""
    if len(legs) == 1:
        (history,) = histories
        index = legs[0].leg.index
        if history.calendar.index is not index:
            raise ValueError(
                f"history is over another index, {history.calendar.index.name!r}, "
                f"expected the trades', {index.name!r}"
            )
        return (history,)
    names = " and ".join(repr(leg.leg.index.name) for leg in legs)
    by_index: dict[int, tuple[int, MarketHistory]] = {}
    for k, history in enumerate(histories):
        index = history.calendar.index
        if not any(index is leg.leg.index for leg in legs):
            raise ValueError(
                f"history {k + 1} is over another index, {index.name!r}, expected the trades', "
                f"{names}"
            )
        seen = by_index.get(id(index))
        if seen is not None:
            raise ValueError(
                f"history {k + 1} is over index {index.name!r} as history {seen[0] + 1} is, "
                "expected one history per index of the trades"
            )
        by_index[id(index)] = (k, history)
    matched = tuple([by_index[id(leg.leg.index)][1] for leg in legs])
    as_of = matched[0].calendar.valuation_date.as_of
    for leg, history in zip(legs[1:], matched[1:], strict=True):
        day = history.calendar.valuation_date.as_of
        if day != as_of:
            raise ValueError(
                f"the history of index {leg.leg.index.name!r} is valued on {day}, expected "
                f"{as_of}, the valuation day of the history of index {legs[0].leg.index.name!r}; "
                "the trades are prepared on one day"
            )
    return matched


def _the_prepared_leg(
    encoded: Encoded,
    leg: EncodedLeg,
    history: MarketHistory,
    slot_rows: NDArray[np.intp],
    is_fixed: NDArray[np.bool_],
    as_of: np.datetime64,
    paid: PaymentAxes | None,
    counter: WorkCounter,
) -> PreparedLeg:
    """One leg prepared against its history over its placed slots: the fixed slots' settles read,
    the set amounts, the live side and the risk the leg owns, every number finite or refused as
    the builder's rules say, and the leg's display axes and early facts; the leg's slots and
    fixings reported to the counter."""
    index = leg.leg.index
    codes = leg.leg.schedule.codes
    fixed_rows = slot_rows[is_fixed]
    settles = history.fixed_prices(fixed_rows, leg.slot_reference[is_fixed])
    conventions = index.conventions
    currency = conventions.currency_unit
    # Since #190 each number made here is finite before the record is made, the arithmetic
    # running with numpy's flags down and the rules judging, else the first that is not is
    # refused by its operation and its slot, group, contract or the batch.
    set_amount, fixed_contribution = _the_set_amounts(encoded, leg, is_fixed, settles, currency)
    is_live = ~is_fixed
    dated_live_exposure = np.where(is_live, leg.slot_exposure, 0.0)
    live_slot = np.flatnonzero(is_live)
    live_references, reference_of_live_slot = np.unique(
        leg.slot_reference[live_slot], return_inverse=True
    )
    lot = leg.leg.reporting_lot
    price_sensitivity = _the_sensitivity(leg, dated_live_exposure, conventions)
    # Finite legs may outrun the largest number, each way at once; the overflow and the invalid
    # flags stay down and the rules judge, a sum of opposite infinities among them.
    with np.errstate(over="ignore", invalid="ignore"):
        dated_live_lots = dated_live_exposure / lot.coefficient
        nominal_delta = price_sensitivity / lot.coefficient
        nominal_delta_total = float(nominal_delta.sum())
    words = lot.words
    outrun = ~np.isfinite(dated_live_lots)
    if outrun.any():
        s = int(outrun.argmax())
        raise ValueError(
            f"{leg.named_slot(s)}, has {float(dated_live_lots[s])!r} live lots, expected a "
            f"finite number of {words}; the exposure in lots outruns the largest number"
        )
    outrun = ~np.isfinite(nominal_delta)
    if outrun.any():
        r = int(outrun.argmax())
        raise ValueError(
            f"{codes[int(leg.references[r])]} has {float(nominal_delta[r])!r} of nominal "
            "delta, "
            f"expected a finite number of {words}; the exposure in lots outruns the largest number"
        )
    if not np.isfinite(nominal_delta_total):
        raise ValueError(
            f"the batch has {nominal_delta_total!r} of nominal delta in all, expected a finite "
            "number of "
            f"{words}; the contracts' deltas, each finite, sum past the largest number"
        )
    daily_lots = np.bincount(leg.day_of_slot, weights=dated_live_lots, minlength=leg.days.size)
    monthly_lots = np.bincount(
        leg.contract_month_of_reference,
        weights=nominal_delta,
        minlength=leg.contract_months.size,
    )
    yearly_lots = np.bincount(
        leg.contract_year_of_month, weights=monthly_lots, minlength=leg.contract_years.size
    )
    for label, starts, lots in (
        ("the day", leg.days, daily_lots),
        ("the contract month from", leg.contract_months, monthly_lots),
        ("the contract year from", leg.contract_years, yearly_lots),
    ):  # the three views, not the rows: a bucket's sum can outrun what its parts did not
        outrun = ~np.isfinite(lots)
        if outrun.any():
            b = int(outrun.argmax())
            raise ValueError(
                f"{label} {starts[b]} has {float(lots[b])!r} of nominal delta in all, expected a "
                f"finite number of {words}; its exposures in lots sum past the largest number"
            )
    # Since #186 the month and year displays start at the valuation day's period: the axes made
    # once here, two searches a bucket, and the nominal lots before the start checked zero.
    by_month = period_axis(as_of, leg.contract_months, None if paid is None else paid.months, "M")
    by_year = period_axis(as_of, leg.contract_years, None if paid is None else paid.years, "Y")
    early_nominal = early_risk(
        f"index {index.name!r}",
        "contract",
        as_of,
        words,
        leg.contract_months,
        monthly_lots,
        by_month.contract_from,
        leg.contract_years,
        yearly_lots,
        by_year.contract_from,
    )
    counter.hit(DISPLAY_PERIODS, int(by_month.periods.size + by_year.periods.size))
    counter.hit(PREPARED_SLOTS, int(is_fixed.size))
    counter.hit(FIXINGS_READ, int(fixed_rows.size))
    arrays = (
        is_fixed,
        dated_live_exposure,
        dated_live_lots,
        set_amount,
        settles,
        fixed_contribution,
        live_slot,
        live_references,
        reference_of_live_slot,
        price_sensitivity,
        nominal_delta,
    )
    for array in (*arrays, daily_lots, monthly_lots, yearly_lots):
        array.setflags(write=False)
    return PreparedLeg(
        leg,
        history,
        *arrays,
        nominal_delta_total,
        daily_lots,
        monthly_lots,
        yearly_lots,
        by_month,
        by_year,
        early_nominal,
    )
