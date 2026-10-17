"""The collection of saved risk across evaluated batches, aggregate-risk-kernel.md, the second
ticket of the risk reporting and aggregation series: one or many results, each already valued,
combined into one immutable record of risk, nothing priced, discounted or converted again.

A result's risk is already saved on it: the nominal lots and the discounted lots by pricing
reference, by observation day and since #186 by contract month and year, with their totals, and
for a bilateral batch
the DV01 by payment day, month and year with its total, each vector frozen when the batch was
prepared or valued, and since #197 the cross-gamma on the delta's four axes with its total. The
collector reads those vectors and nothing else. It groups the occurrences
by the index object they are on, the exact object and not its name, a distinct index of the same
name refused, every occurrence of a group over the same history object and the same price-vector
object as the group's first; the bilateral occurrences by the curve object they were valued
on and the result's currency; and, for the cross-gamma, every occurrence by the pair of its index
object and its curve object, a cleared occurrence's pair on no curve the known zero, nothing
summed for it. Within a group it forms the union of the saved axes and sums the
saved vectors onto it, a compensated sum over the occurrences so that what cancels is kept
whatever their order, the totals the saved scalars summed the same compensated way; across
groups it sums nothing, the lots of one index never added to another's, nor the DV01 of one
curve and currency to another's, nor the cross-gamma of one index and curve to another pair's.
Every occurrence counts, a repeated result twice. The report
axes, the union of the groups' observation axes, the union of their payment axes and the union of
both, are made here with every group's places on them, so that a report copies through saved
places and discovers, sorts and sums nothing; the day, month and year views are separate axes,
the saved month and year vectors summed onto their own unions and never bucketed again.

Positions name an occurrence in a refusal, counted from one as a sheet counts; the arrays hold
them from zero. Work is counted by the occurrences collected, the groups, the entries aligned,
the reductions and the report coordinates saved.
"""

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve import DiscountCurve
from goosedove.index_definitions.index import Index, ReportingLot
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market_history import MarketHistory
from goosedove.market_data.price_vector import PriceVector
from goosedove.trades.display_axes import (
    NONE_EARLY,
    EarlyRisk,
    Unit,
    display_periods,
    early_risk,
    period_start,
    places_from,
    rows_through,
)
from goosedove.trades.encoding import PaymentAxes
from goosedove.trades.results import TradeResults
from goosedove.trades.risk_report import (
    NO_DAYS,
    NOTHING,
    Bucket,
    Risk,
    RiskView,
    cross_gamma_label,
    delta_labels,
    dv01_label,
    placed,
)

SOURCES_COLLECTED = "sources_collected"  # occurrences, every one, a repeated result counted again
INDEX_GROUPS = "index_groups"  # one per distinct index object among the occurrences
RATE_GROUPS = "rate_groups"  # one per distinct curve object and currency among the bilateral ones
CROSS_GROUPS = (
    "cross_groups"  # since #197, one per index object and curve object pair, cleared none
)
ENTRIES_ALIGNED = "entries_aligned"  # saved vector entries placed on a union, over every reduction
AGGREGATE_REDUCTIONS = "aggregate_reductions"  # compensated sums of saved vectors onto a union
REPORT_COORDINATES = (
    "report_coordinates"  # entries of the report axes saved, over the three buckets
)


@dataclass(frozen=True, slots=True)
class IndexGroup:
    """One index's risk across the occurrences on it: the index object, its reporting lot, the
    history and the price vector every occurrence shares, and the occurrences' positions,
    increasing. references is the union of the occurrences' pricing references, rows of the
    index's schedule increasing, with the nominal lots and the discounted lots summed onto them
    and the two totals, the saved scalars summed; days are the union of the occurrences'
    observation days and months and years, since #186, the unions of their contract months and
    contract years, with both lot vectors summed onto each. Every array frozen."""

    index: Index
    reporting_lot: ReportingLot
    history: MarketHistory
    price_vector: PriceVector
    occurrences: NDArray[np.intp]
    references: NDArray[np.intp]
    lot_delta: NDArray[np.float64]
    discounted_lot_delta: NDArray[np.float64]
    lot_delta_total: float
    discounted_lot_delta_total: float
    days: NDArray[np.datetime64]
    daily_lots: NDArray[np.float64]
    discounted_daily_lots: NDArray[np.float64]
    months: NDArray[np.datetime64]
    monthly_lots: NDArray[np.float64]
    discounted_monthly_lots: NDArray[np.float64]
    years: NDArray[np.datetime64]
    yearly_lots: NDArray[np.float64]
    discounted_yearly_lots: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class RateGroup:
    """One curve's and one currency's DV01 across the bilateral occurrences valued on them: the
    curve object, its number by first appearance among the collection's curves, curve_1 the
    first, the currency, the occurrences' positions, the saved DV01s summed, and the unions of
    the occurrences' payment axes with the DV01 summed onto each. Every array frozen."""

    curve: DiscountCurve
    number: int
    currency: str
    occurrences: NDArray[np.intp]
    dv01: float
    days: NDArray[np.datetime64]
    dv01_by_day: NDArray[np.float64]
    months: NDArray[np.datetime64]
    dv01_by_month: NDArray[np.float64]
    years: NDArray[np.datetime64]
    dv01_by_year: NDArray[np.float64]


NO_REFERENCES: NDArray[np.intp] = np.empty(0, dtype=np.intp)
NO_REFERENCES.setflags(write=False)


@dataclass(frozen=True, slots=True)
class CrossGroup:
    """One index's cross-gamma on one curve across the occurrences on the pair, since #197,
    single-curve-cross-gamma.md: the index object and its reporting lot, the curve object and its
    number by first appearance among the collection's curves, the number the rate groups give it,
    and the occurrences' positions, increasing; references the union of the occurrences' pricing
    references with the saved cross-gamma summed onto them and the total the saved scalars summed;
    days, months and years the unions of their observation days, contract months and contract
    years, the delta's axes, with the cross-gamma summed onto each. A cleared occurrence is on no
    curve: its pair's curve and number are None and its risk the known zero, held as empty axes
    and vectors with a total of 0.0, nothing summed and no buffer made, so that a cleared source
    shows its zero column beside a bilateral one and nothing is summed across curves. Every array
    frozen."""

    index: Index
    reporting_lot: ReportingLot
    curve: DiscountCurve | None
    number: int | None
    occurrences: NDArray[np.intp]
    references: NDArray[np.intp]
    cross_gamma: NDArray[np.float64]
    cross_gamma_total: float
    days: NDArray[np.datetime64]
    cross_gamma_by_day: NDArray[np.float64]
    months: NDArray[np.datetime64]
    cross_gamma_by_month: NDArray[np.float64]
    years: NDArray[np.datetime64]
    cross_gamma_by_year: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class ReportAxes:
    """One bucket's report axes and every group's places on them. By day: observed, the union of
    the index groups' observation days, with each group's places; paid, the union of the rate
    groups' payment days, with each group's places, no day when no curve values; and union, the
    two together, with every group's places on it; observed_from and paid_from zero, every saved
    entry placed. By month or by year, since #186, risk-contract-month-bucketing.md: one display
    axis of consecutive periods from the valuation day's, observed its first rows through the
    last contract period of any index group, paid its rows through the last payment period of
    any rate group, no day when no curve values, and union the rows through the later; each
    group's places counted from the start, the same on every prefix, and observed_from and
    paid_from each group's first saved period on or after the start, the periods before it left
    out, their risk zero or the report refused. Since #197 cross_in, cross_in_union and
    cross_from the same for the cross groups, each on the observed axis and on the union, a
    cleared group's places none. Made once with the collection so that a report of one risk or
    of all four copies saved vectors through saved places."""

    observed: NDArray[np.datetime64]
    observed_in: tuple[NDArray[np.intp], ...]
    paid: NDArray[np.datetime64]
    paid_in: tuple[NDArray[np.intp], ...]
    union: NDArray[np.datetime64]
    observed_in_union: tuple[NDArray[np.intp], ...]
    paid_in_union: tuple[NDArray[np.intp], ...]
    observed_from: tuple[int, ...]
    paid_from: tuple[int, ...]
    cross_in: tuple[NDArray[np.intp], ...]
    cross_in_union: tuple[NDArray[np.intp], ...]
    cross_from: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AggregateResults:
    """The collection: the valuation day every source shares; the sources, the occurrences in the
    order given, every one and by reference, so that a held collection keeps its sources
    readable; the index groups, the rate groups and since #197 the cross groups, one per index
    and curve pair, a cleared source's pair with no curve, in first-appearance order; the
    currencies of
    the sources in first-appearance order, the DV01 columns of nothing a collection with no curve
    reports; and the report axes by day, by month and by year. Since #186 early_nominal and
    early_delta, one EarlyRisk per index group, and early_dv01, one per rate group: the facts
    refusing a month or a year report whose summed risk stands in a period before the valuation
    day's, or none, found here so that a report words them with the measure asked for and scans
    nothing, and since #197 early_cross_gamma, one per cross group, the same facts for the
    cross-gamma. Nothing here
    is a copy of a source's preparation, market or curve, and nothing is written after it is
    made."""

    as_of: np.datetime64
    sources: tuple[TradeResults, ...]
    index_groups: tuple[IndexGroup, ...]
    rate_groups: tuple[RateGroup, ...]
    cross_groups: tuple[CrossGroup, ...]
    currencies: tuple[str, ...]
    by_day: ReportAxes
    by_month: ReportAxes
    by_year: ReportAxes
    early_nominal: tuple[EarlyRisk, ...]
    early_delta: tuple[EarlyRisk, ...]
    early_dv01: tuple[EarlyRisk, ...]
    early_cross_gamma: tuple[EarlyRisk, ...]

    def report(self, risk: Risk, bucket: Bucket) -> RiskView:
        """The content of the risk report asked for: aggregate_view's selection of the collection's
        saved axes, totals and vectors through the saved places, what _ReportRisk formats for a
        collection as for a result. Selects and copies, and nothing else."""
        return aggregate_view(self, risk, bucket)


def aggregate_results(sources: Sequence[TradeResults], counter: WorkCounter) -> AggregateResults:
    """The one way to collect evaluated batches, aggregate-risk-kernel.md: the occurrences
    snapshotted as given, one or many on one path, none refused; each occurrence in order held to
    the first's valuation day and to its index's first occurrence's history and price vector,
    the objects themselves; a distinct index object of a name already seen refused; then the
    groups' saved vectors summed onto the unions of their saved axes, the totals the saved
    scalars summed, each new number and vector finite or the first that is not refused by its
    measure, group and coordinate, since #197 the cross-gamma by the pair of index object and
    curve object, a cleared source's pair on no curve the known zero and nothing summed; and
    the report axes made with every place saved.

    Work: one occurrence per source, one group per index object, per curve and currency and
    per index and curve pair, one entry aligned per saved entry, one reduction per vector
    summed and one coordinate per entry of the report axes, reported to the counter; no quote,
    fixing or factor read, no trade resolved, no conversion and no evaluation.
    """
    results = tuple(sources)
    if not results:
        raise ValueError("results are none, expected at least one evaluated batch")
    as_of = results[0].as_of
    by_index = _grouped_by_index(results, as_of)
    numbers = _curve_numbers(results)
    by_curve = _grouped_by_curve(results, numbers)
    by_pair = _grouped_by_index_and_curve(results)
    counter.hit(SOURCES_COLLECTED, len(results))
    counter.hit(INDEX_GROUPS, len(by_index))
    counter.hit(RATE_GROUPS, len(by_curve))
    counter.hit(CROSS_GROUPS, len(by_pair))
    index_groups = tuple([_index_group(results, positions, counter) for positions in by_index])
    rate_groups = tuple(
        [
            _rate_group(results, curve, number, currency, positions, counter)
            for curve, number, currency, positions in by_curve
        ]
    )
    cross_groups = tuple(
        [_cross_group(results, positions, numbers, counter) for positions in by_pair]
    )
    by_day = _report_axes(
        [g.days for g in index_groups],
        [r.days for r in rate_groups],
        [c.days for c in cross_groups],
        counter,
    )
    by_month = _period_report_axes(
        as_of,
        [g.months for g in index_groups],
        [r.months for r in rate_groups],
        [c.months for c in cross_groups],
        "M",
        counter,
    )
    by_year = _period_report_axes(
        as_of,
        [g.years for g in index_groups],
        [r.years for r in rate_groups],
        [c.years for c in cross_groups],
        "Y",
        counter,
    )
    currencies = tuple(dict.fromkeys([source.currency for source in results]))
    # Since #186 the facts refusing a month or a year report of a group's risk standing before
    # the valuation day's period, found once here against the display axes and worded by the
    # reader with the measure asked for.
    early_nominal = tuple(
        [
            _early_lots(g, g.monthly_lots, g.yearly_lots, m, y, as_of)
            for g, m, y in zip(
                index_groups, by_month.observed_from, by_year.observed_from, strict=True
            )
        ]
    )
    early_delta = tuple(
        [
            _early_lots(g, g.discounted_monthly_lots, g.discounted_yearly_lots, m, y, as_of)
            for g, m, y in zip(
                index_groups, by_month.observed_from, by_year.observed_from, strict=True
            )
        ]
    )
    early_dv01 = tuple(
        [
            early_risk(
                f"curve_{r.number} {r.currency}",
                "payment",
                as_of,
                f"{r.currency} per basis point",
                r.months,
                r.dv01_by_month,
                m,
                r.years,
                r.dv01_by_year,
                y,
            )
            for r, m, y in zip(rate_groups, by_month.paid_from, by_year.paid_from, strict=True)
        ]
    )
    # Since #197 the same facts for each cross group's cross-gamma, a cleared group's none,
    # its risk the known zero.
    early_cross = tuple(
        [
            NONE_EARLY
            if c.number is None
            else early_risk(
                f"index {c.index.name!r} on curve_{c.number}",
                "contract",
                as_of,
                f"{c.reporting_lot.words} per basis point",
                c.months,
                c.cross_gamma_by_month,
                m,
                c.years,
                c.cross_gamma_by_year,
                y,
            )
            for c, m, y in zip(cross_groups, by_month.cross_from, by_year.cross_from, strict=True)
        ]
    )
    return AggregateResults(
        as_of,
        results,
        index_groups,
        rate_groups,
        cross_groups,
        currencies,
        by_day,
        by_month,
        by_year,
        early_nominal,
        early_delta,
        early_dv01,
        early_cross,
    )


def _early_lots(
    group: IndexGroup,
    monthly: NDArray[np.float64],
    yearly: NDArray[np.float64],
    month_from: int,
    year_from: int,
    as_of: np.datetime64,
) -> EarlyRisk:
    """An index group's refusals of one vector by month and by year, or none, the facts naming its
    index and its reporting lot."""
    return early_risk(
        f"index {group.index.name!r}",
        "contract",
        as_of,
        group.reporting_lot.words,
        group.months,
        monthly,
        month_from,
        group.years,
        yearly,
        year_from,
    )


def _grouped_by_index(results: tuple[TradeResults, ...], as_of: np.datetime64) -> list[list[int]]:
    """The occurrences' positions grouped by the exact index object, in first-appearance order,
    each occurrence in the order given held to the valuation day, then to its group's first
    occurrence's history and price vector, the objects and not their values; a distinct index
    object whose name a group already has is refused, two indexes of one name being a mistake to
    show and not a group to make."""
    groups: list[list[int]] = []
    by_identity: dict[int, int] = {}
    by_name: dict[str, int] = {}
    for k, source in enumerate(results):
        if source.as_of != as_of:
            raise ValueError(
                f"results {k + 1} is valued on {source.as_of}, expected {as_of}, the valuation "
                "day of results 1"
            )
        ix = source.prepared.encoded.terms.index
        g = by_identity.get(id(ix))
        if g is None:
            named = by_name.get(ix.name)
            if named is not None:
                raise ValueError(
                    f"results {k + 1} is on another index named {ix.name!r} than results "
                    f"{groups[named][0] + 1}, expected one index for one name"
                )
            by_identity[id(ix)] = by_name[ix.name] = len(groups)
            groups.append([k])
            continue
        first = results[groups[g][0]]
        if source.prepared.history is not first.prepared.history:
            raise ValueError(
                f"results {k + 1} is on index {ix.name!r} over another history than results "
                f"{groups[g][0] + 1}, expected one history for one index"
            )
        if source.market.price_vector is not first.market.price_vector:
            raise ValueError(
                f"results {k + 1} is on index {ix.name!r} quoted off another price vector than "
                f"results {groups[g][0] + 1}, expected one price vector for one index"
            )
        groups[g].append(k)
    return groups


def _curve_numbers(results: tuple[TradeResults, ...]) -> dict[int, int]:
    """Each distinct curve object's number by its first appearance among the collection's
    curves, whatever the currency, curve_1 the first, by the object's identity; the rate groups
    and since #197 the cross groups read one numbering, so that curve_1 names one curve in every
    heading."""
    numbers: dict[int, int] = {}
    for source in results:
        if source.curve is not None:
            numbers.setdefault(id(source.curve), len(numbers) + 1)
    return numbers


def _grouped_by_curve(
    results: tuple[TradeResults, ...], numbers: dict[int, int]
) -> list[tuple[DiscountCurve, int, str, list[int]]]:
    """The bilateral occurrences' positions grouped by the exact curve object and the result's
    currency, in first-appearance order, each curve under the number its first appearance among
    the collection's curves gave it whatever the currency, so that one curve valuing two
    currencies is two groups of one number; a cleared occurrence, valued on no curve, is in no
    group."""
    groups: list[tuple[DiscountCurve, int, str, list[int]]] = []
    where: dict[tuple[int, str], int] = {}
    for k, source in enumerate(results):
        curve = source.curve
        if curve is None:
            continue
        number = numbers[id(curve)]
        g = where.get((id(curve), source.currency))
        if g is None:
            where[(id(curve), source.currency)] = len(groups)
            groups.append((curve, number, source.currency, [k]))
        else:
            groups[g][3].append(k)
    return groups


def _index_group(
    results: tuple[TradeResults, ...], positions: list[int], counter: WorkCounter
) -> IndexGroup:
    """One index group's risk: the saved reference, day, month and year vectors of its
    occurrences summed onto the unions of their saved axes, both lots on each, the totals the
    saved scalars summed, every new number finite or refused."""
    first = results[positions[0]]
    terms = first.prepared.encoded.terms
    members = [results[k] for k in positions]
    references, (lots, discounted) = _summed(
        [m.prepared.encoded.references for m in members],
        ([m.lot_delta for m in members], [m.discounted_lot_delta for m in members]),
        counter,
    )
    days, (daily, discounted_daily) = _summed(
        [m.prepared.encoded.days for m in members],
        ([m.prepared.daily_lots for m in members], [m.discounted_daily_lots for m in members]),
        counter,
    )
    months, (monthly, discounted_monthly) = _summed(
        [m.prepared.encoded.contract_months for m in members],
        (
            [m.prepared.monthly_lots for m in members],
            [m.discounted_monthly_lots for m in members],
        ),
        counter,
    )
    years, (yearly, discounted_yearly) = _summed(
        [m.prepared.encoded.contract_years for m in members],
        ([m.prepared.yearly_lots for m in members], [m.discounted_yearly_lots for m in members]),
        counter,
    )
    # Python's sum of floats is compensated and keeps a sum past the largest number as inf.
    total = sum([m.lot_delta_total for m in members])
    discounted_total = sum([m.discounted_lot_delta_total for m in members])
    codes = terms.schedule.codes
    for measure, by_reference, by_day, by_month, by_year, in_all in (
        ("nominal delta", lots, daily, monthly, yearly, total),
        (
            "delta",
            discounted,
            discounted_daily,
            discounted_monthly,
            discounted_yearly,
            discounted_total,
        ),
    ):
        where, value = _outrun(
            (
                ("for contract", lambda b: codes[int(references[b])], by_reference),
                ("on", lambda b: days[b], by_day),
                ("in the contract month from", lambda b: months[b], by_month),
                ("in the contract year from", lambda b: years[b], by_year),
            ),
            in_all,
        )
        if where is not None:
            raise ValueError(
                f"the {measure} of index {terms.index.name!r} {where} is {value!r}, expected a "
                "finite number of lots; the results' lots sum past the largest number"
            )
    occurrences = np.array(positions, dtype=np.intp)
    for array in (occurrences, references, days, months, years):
        array.setflags(write=False)
    return IndexGroup(
        terms.index,
        terms.reporting_lot,
        first.prepared.history,
        first.market.price_vector,
        occurrences,
        references,
        lots,
        discounted,
        total,
        discounted_total,
        days,
        daily,
        discounted_daily,
        months,
        monthly,
        discounted_monthly,
        years,
        yearly,
        discounted_yearly,
    )


def _rate_group(
    results: tuple[TradeResults, ...],
    curve: DiscountCurve,
    number: int,
    currency: str,
    positions: list[int],
    counter: WorkCounter,
) -> RateGroup:
    """One rate group's DV01: the saved payment day, month and year vectors of its occurrences
    summed onto the unions of their saved payment axes, the total the saved DV01s summed, every
    new number finite or refused."""
    members = [results[k] for k in positions]
    # Bilateral occurrences, valued on this curve: the axes and the vectors were made with them.
    axes = [cast(PaymentAxes, m.prepared.encoded.payment_axes) for m in members]
    days, (by_day,) = _summed(
        [a.days for a in axes],
        ([cast(NDArray[np.float64], m.dv01_by_day) for m in members],),
        counter,
    )
    months, (by_month,) = _summed(
        [a.months for a in axes],
        ([cast(NDArray[np.float64], m.dv01_by_month) for m in members],),
        counter,
    )
    years, (by_year,) = _summed(
        [a.years for a in axes],
        ([cast(NDArray[np.float64], m.dv01_by_year) for m in members],),
        counter,
    )
    total = sum([m.dv01 for m in members])  # compensated, an overflow kept as inf
    where, value = _outrun(
        (
            ("on", lambda b: days[b], by_day),
            ("in the payment month from", lambda b: months[b], by_month),
            ("in the payment year from", lambda b: years[b], by_year),
        ),
        total,
    )
    if where is not None:
        raise ValueError(
            f"the DV01 of curve_{number} {currency} {where} is {value!r}, expected a finite "
            f"amount of {currency} per basis point; the results' DV01s sum past the largest number"
        )
    occurrences = np.array(positions, dtype=np.intp)
    for array in (occurrences, days, months, years):
        array.setflags(write=False)
    return RateGroup(
        curve, number, currency, occurrences, total, days, by_day, months, by_month, years, by_year
    )


def _grouped_by_index_and_curve(results: tuple[TradeResults, ...]) -> list[list[int]]:
    """The occurrences' positions grouped by the exact index object and the exact curve object, a
    cleared occurrence's curve none, in first-appearance order of the pair, since #197; the rules
    over the indexes are _grouped_by_index's, checked before this groups, so that an index's
    occurrences are compatible whatever curves they are on."""
    groups: list[list[int]] = []
    where: dict[tuple[int, int | None], int] = {}
    for k, source in enumerate(results):
        curve = source.curve
        key = (id(source.prepared.encoded.terms.index), None if curve is None else id(curve))
        g = where.get(key)
        if g is None:
            where[key] = len(groups)
            groups.append([k])
        else:
            groups[g].append(k)
    return groups


def _cross_group(
    results: tuple[TradeResults, ...],
    positions: list[int],
    numbers: dict[int, int],
    counter: WorkCounter,
) -> CrossGroup:
    """One cross group's cross-gamma, since #197: the saved reference, day, month and year
    vectors of its occurrences summed onto the unions of their saved delta axes, the total the
    saved scalars summed, every new number finite or refused by the index, the curve and the
    coordinate; a cleared pair the known zero, empty axes and vectors, nothing summed and
    nothing counted."""
    first = results[positions[0]]
    terms = first.prepared.encoded.terms
    occurrences = np.array(positions, dtype=np.intp)
    occurrences.setflags(write=False)
    if first.curve is None:
        return CrossGroup(
            terms.index,
            terms.reporting_lot,
            None,
            None,
            occurrences,
            NO_REFERENCES,
            NOTHING,
            0.0,
            NO_DAYS,
            NOTHING,
            NO_DAYS,
            NOTHING,
            NO_DAYS,
            NOTHING,
        )
    members = [results[k] for k in positions]
    # Bilateral occurrences, valued on this curve: the four vectors were made with the axes.
    references, (by_reference,) = _summed(
        [m.prepared.encoded.references for m in members],
        ([cast(NDArray[np.float64], m.cross_gamma) for m in members],),
        counter,
    )
    days, (by_day,) = _summed(
        [m.prepared.encoded.days for m in members],
        ([cast(NDArray[np.float64], m.cross_gamma_by_day) for m in members],),
        counter,
    )
    months, (by_month,) = _summed(
        [m.prepared.encoded.contract_months for m in members],
        ([cast(NDArray[np.float64], m.cross_gamma_by_month) for m in members],),
        counter,
    )
    years, (by_year,) = _summed(
        [m.prepared.encoded.contract_years for m in members],
        ([cast(NDArray[np.float64], m.cross_gamma_by_year) for m in members],),
        counter,
    )
    total = sum([m.cross_gamma_total for m in members])  # compensated, an overflow kept as inf
    number = numbers[id(first.curve)]
    codes = terms.schedule.codes
    where, value = _outrun(
        (
            ("for contract", lambda b: codes[int(references[b])], by_reference),
            ("on", lambda b: days[b], by_day),
            ("in the contract month from", lambda b: months[b], by_month),
            ("in the contract year from", lambda b: years[b], by_year),
        ),
        total,
    )
    if where is not None:
        raise ValueError(
            f"the cross-gamma of index {terms.index.name!r} on curve_{number} {where} is "
            f"{value!r}, expected a finite number of {terms.reporting_lot.words} per basis point; "
            "the results' cross-gammas sum past the largest number"
        )
    for array in (references, days, months, years):
        array.setflags(write=False)
    return CrossGroup(
        terms.index,
        terms.reporting_lot,
        first.curve,
        number,
        occurrences,
        references,
        by_reference,
        total,
        days,
        by_day,
        months,
        by_month,
        years,
        by_year,
    )


def _summed(
    axes: list[NDArray[Any]],
    vectors: tuple[list[NDArray[np.float64]], ...],
    counter: WorkCounter,
) -> tuple[NDArray[Any], tuple[NDArray[np.float64], ...]]:
    """The union of the occurrences' saved axes, increasing, and each kind of saved vector summed
    onto it: the axes stacked once and their places on the union found once, then each kind
    summed over the occurrences with compensation, every entry of an occurrence at once, frozen;
    the entries aligned and the reductions reported to the counter. One occurrence takes the
    same path as many."""
    stacked = np.concatenate(axes)
    union = np.unique(stacked)
    place = np.searchsorted(union, stacked)
    stops = list(itertools.accumulate([axis.size for axis in axes]))
    pieces = [place[stop - axis.size : stop] for axis, stop in zip(axes, stops, strict=True)]
    sums = tuple([_compensated(union.size, pieces, kind) for kind in vectors])
    for array in sums:
        array.setflags(write=False)
    counter.hit(ENTRIES_ALIGNED, int(stacked.size))
    counter.hit(AGGREGATE_REDUCTIONS, len(vectors))
    return union, sums


def _compensated(
    size: int, places: list[NDArray[np.intp]], values: list[NDArray[np.float64]]
) -> NDArray[np.float64]:
    """One kind of saved vector summed onto the union, the occurrences added one at a time with
    Neumaier's compensation, every entry of an occurrence at once: the running sum and the low
    part each addition dropped, added back at the end, so that a lot bought against ten thousand
    trillion bought and sold is a lot whatever the order the occurrences came in, as the totals
    summed the same way say. An occurrence's places are distinct, its own axis having no
    repeated entry, so each step writes every place once."""
    held = np.zeros(size)
    dropped = np.zeros(size)
    # The flags down and the rules judging, as the kernel sums: a sum past the largest number
    # is inf here and refused by its coordinate after; the compensation is added back only where
    # it is finite, as Python's own sum of floats does, so an overflow stays inf and not nan.
    with np.errstate(over="ignore", invalid="ignore"):
        for at, entries in zip(places, values, strict=True):
            before = held[at]
            after = before + entries
            low = np.abs(before) >= np.abs(entries)
            dropped[at] += np.where(low, (before - after) + entries, (entries - after) + before)
            held[at] = after
        return np.where(np.isfinite(dropped), held + dropped, held)


def _outrun(
    views: tuple[tuple[str, Callable[[int], object], NDArray[np.float64]], ...], total: float
) -> tuple[str | None, float]:
    """The first coordinate whose sum is not finite, as words and the number, the vectors before
    the total since a coordinate can outrun what the total, cancelling elsewhere, does not; or
    None and the total when every number is finite. The coordinate's label is made only for the
    one named."""
    for words, label, values in views:
        outrun = ~np.isfinite(values)
        if outrun.any():
            b = int(outrun.argmax())
            return f"{words} {label(b)}", float(values[b])
    if not np.isfinite(total):
        return "in all", total
    return None, total


def _report_axes(
    observation_axes: list[NDArray[np.datetime64]],
    payment_axes: list[NDArray[np.datetime64]],
    cross_axes: list[NDArray[np.datetime64]],
    counter: WorkCounter,
) -> ReportAxes:
    """One bucket's report axes: the union of the index groups' delta axes with each group's
    places, the union of the rate groups' payment axes with each group's places, no day
    when no curve values, and the union of both with every group's places; since #197 each
    cross group's places on the delta union and on the union of both, a cleared group's none;
    every array frozen, the coordinates reported to the counter."""
    observed = np.unique(np.concatenate(observation_axes))
    paid = np.unique(np.concatenate(payment_axes)) if payment_axes else NO_DAYS
    union = np.union1d(observed, paid)
    observed_in = tuple([np.searchsorted(observed, axis) for axis in observation_axes])
    paid_in = tuple([np.searchsorted(paid, axis) for axis in payment_axes])
    observed_in_union = tuple([np.searchsorted(union, axis) for axis in observation_axes])
    paid_in_union = tuple([np.searchsorted(union, axis) for axis in payment_axes])
    cross_in = tuple([np.searchsorted(observed, axis) for axis in cross_axes])
    cross_in_union = tuple([np.searchsorted(union, axis) for axis in cross_axes])
    for array in (
        observed,
        paid,
        union,
        *observed_in,
        *paid_in,
        *observed_in_union,
        *paid_in_union,
        *cross_in,
        *cross_in_union,
    ):
        array.setflags(write=False)
    counter.hit(REPORT_COORDINATES, int(observed.size + paid.size + union.size))
    return ReportAxes(
        observed,
        observed_in,
        paid,
        paid_in,
        union,
        observed_in_union,
        paid_in_union,
        (0,) * len(observation_axes),
        (0,) * len(payment_axes),
        cross_in,
        cross_in_union,
        (0,) * len(cross_axes),
    )


def _period_report_axes(
    as_of: np.datetime64,
    contract_axes: list[NDArray[np.datetime64]],
    payment_axes: list[NDArray[np.datetime64]],
    cross_axes: list[NDArray[np.datetime64]],
    unit: Unit,
    counter: WorkCounter,
) -> ReportAxes:
    """One bucket's report axes by month or by year, since #186: the display periods from the
    valuation day's through the farthest saved period of any group, the index groups' rows through
    their last contract period and the rate groups' through their last payment period, no day
    when no curve values; each group's places counted from the start and its first saved period
    on or after it, one search a group, since #197 the cross groups' the same way, their periods
    among their index groups'; every array frozen, the coordinates reported to the counter."""
    start = period_start(as_of, unit)
    observed_places = [places_from(axis, start, unit) for axis in contract_axes]
    paid_places = [places_from(axis, start, unit) for axis in payment_axes]
    cross_places = [places_from(axis, start, unit) for axis in cross_axes]
    delta_rows = max([rows_through(p) for _, p in observed_places])
    dv01_rows = max([rows_through(p) for _, p in paid_places], default=0)
    periods = display_periods(start, max(delta_rows, dv01_rows))
    periods.setflags(write=False)  # before the views below, which take the flag as made
    observed = periods[:delta_rows]
    paid = periods[:dv01_rows] if payment_axes else NO_DAYS
    union = periods[: max(delta_rows, dv01_rows)]
    observed_in = tuple([p for _, p in observed_places])
    paid_in = tuple([p for _, p in paid_places])
    cross_in = tuple([p for _, p in cross_places])
    for array in (*observed_in, *paid_in, *cross_in):
        array.setflags(write=False)
    counter.hit(REPORT_COORDINATES, int(observed.size + paid.size + union.size))
    return ReportAxes(
        observed,
        observed_in,
        paid,
        paid_in,
        union,
        observed_in,
        paid_in,
        tuple([f for f, _ in observed_places]),
        tuple([f for f, _ in paid_places]),
        cross_in,
        cross_in,
        tuple([f for f, _ in cross_places]),
    )


def aggregate_view(aggregate: AggregateResults, risk: Risk, bucket: Bucket) -> RiskView:
    """The one way to read a collection's report, _ReportRisk's selection over a collection: the
    index groups' nominal lots or discounted lots on the union of their observation axes, one
    column per group under the index's name and its reporting lot's; the rate groups' DV01 on the
    union of their payment axes, one column per group under its curve's number and its currency,
    a collection with no curve one column of nothing per currency, `cleared USD dv01 [...]`, over
    no day; since #197 the cross groups' cross-gamma on the union of the observation axes, one
    column per index and curve pair under the index's name, `curve_1` or `cleared` and its
    reporting lot per basis point, a cleared pair's column zero; and all four on the union of
    both, each index group's two columns, then each rate group's, then each cross group's, every
    vector copied through the places the collection saved and zero where the group has no entry.
    The Totals are the groups' saved sums. Nothing is summed, sorted or discovered.

    Work: a copy per column, through the saved places; nothing else.
    """
    axes = _axes_of(aggregate, bucket)
    groups = aggregate.index_groups
    rates = aggregate.rate_groups
    crosses = aggregate.cross_groups
    _refuse_early(aggregate, risk, bucket)
    pairs = [delta_labels(g.index, g.reporting_lot) for g in groups]
    nominal = tuple([pair[0] for pair in pairs])
    delta = tuple([pair[1] for pair in pairs])
    dv01 = tuple([dv01_label(f"curve_{r.number}", r.currency) for r in rates])
    cleared = tuple([dv01_label("cleared", c) for c in aggregate.currencies])
    cross = tuple(
        [
            cross_gamma_label(
                c.index, "cleared" if c.number is None else f"curve_{c.number}", c.reporting_lot
            )
            for c in crosses
        ]
    )
    match risk:
        case Risk.NOMINAL_DELTA:
            columns = tuple(
                [
                    placed(axes.observed.size, places, _lots(g, bucket)[start:])
                    for g, places, start in zip(
                        groups, axes.observed_in, axes.observed_from, strict=True
                    )
                ]
            )
            totals = tuple([g.lot_delta_total for g in groups])
            return RiskView(axes.observed, nominal, totals, columns)
        case Risk.DELTA:
            columns = tuple(
                [
                    placed(axes.observed.size, places, _discounted_lots(g, bucket)[start:])
                    for g, places, start in zip(
                        groups, axes.observed_in, axes.observed_from, strict=True
                    )
                ]
            )
            totals = tuple([g.discounted_lot_delta_total for g in groups])
            return RiskView(axes.observed, delta, totals, columns)
        case Risk.DV01:
            if not rates:
                # No curve valued any source: a Total of nothing per currency over no day.
                nothing = (NOTHING,) * len(cleared)
                return RiskView(axes.paid, cleared, (0.0,) * len(cleared), nothing)
            columns = tuple(
                [
                    placed(axes.paid.size, places, _dv01(r, bucket)[start:])
                    for r, places, start in zip(rates, axes.paid_in, axes.paid_from, strict=True)
                ]
            )
            return RiskView(axes.paid, dv01, tuple([r.dv01 for r in rates]), columns)
        case Risk.CROSS_GAMMA:
            columns = tuple(
                [
                    placed(axes.observed.size, places, _cross_gamma(c, bucket)[start:])
                    for c, places, start in zip(
                        crosses, axes.cross_in, axes.cross_from, strict=True
                    )
                ]
            )
            totals = tuple([c.cross_gamma_total for c in crosses])
            return RiskView(axes.observed, cross, totals, columns)
        case Risk.ALL:
            labels: list[str] = []
            totals_all: list[float] = []
            every: list[NDArray[np.float64]] = []
            for g, label_n, label_d, places, start in zip(
                groups, nominal, delta, axes.observed_in_union, axes.observed_from, strict=True
            ):
                labels.extend((label_n, label_d))
                totals_all.extend((g.lot_delta_total, g.discounted_lot_delta_total))
                every.append(placed(axes.union.size, places, _lots(g, bucket)[start:]))
                every.append(placed(axes.union.size, places, _discounted_lots(g, bucket)[start:]))
            if rates:
                for r, label, places, start in zip(
                    rates, dv01, axes.paid_in_union, axes.paid_from, strict=True
                ):
                    labels.append(label)
                    totals_all.append(r.dv01)
                    every.append(placed(axes.union.size, places, _dv01(r, bucket)[start:]))
            else:
                for label in cleared:
                    labels.append(label)
                    totals_all.append(0.0)
                    every.append(np.zeros(axes.union.size))
            for c, label, places, start in zip(
                crosses, cross, axes.cross_in_union, axes.cross_from, strict=True
            ):
                labels.append(label)
                totals_all.append(c.cross_gamma_total)
                every.append(placed(axes.union.size, places, _cross_gamma(c, bucket)[start:]))
            return RiskView(axes.union, tuple(labels), tuple(totals_all), tuple(every))
        case _:
            assert_never(risk)


def _axes_of(aggregate: AggregateResults, bucket: Bucket) -> ReportAxes:
    match bucket:
        case Bucket.DAY:
            return aggregate.by_day
        case Bucket.MONTH:
            return aggregate.by_month
        case Bucket.YEAR:
            return aggregate.by_year
        case _:
            assert_never(bucket)


def _lots(group: IndexGroup, bucket: Bucket) -> NDArray[np.float64]:
    match bucket:
        case Bucket.DAY:
            return group.daily_lots
        case Bucket.MONTH:
            return group.monthly_lots
        case Bucket.YEAR:
            return group.yearly_lots
        case _:
            assert_never(bucket)


def _discounted_lots(group: IndexGroup, bucket: Bucket) -> NDArray[np.float64]:
    match bucket:
        case Bucket.DAY:
            return group.discounted_daily_lots
        case Bucket.MONTH:
            return group.discounted_monthly_lots
        case Bucket.YEAR:
            return group.discounted_yearly_lots
        case _:
            assert_never(bucket)


def _dv01(group: RateGroup, bucket: Bucket) -> NDArray[np.float64]:
    match bucket:
        case Bucket.DAY:
            return group.dv01_by_day
        case Bucket.MONTH:
            return group.dv01_by_month
        case Bucket.YEAR:
            return group.dv01_by_year
        case _:
            assert_never(bucket)


def _cross_gamma(group: CrossGroup, bucket: Bucket) -> NDArray[np.float64]:
    match bucket:
        case Bucket.DAY:
            return group.cross_gamma_by_day
        case Bucket.MONTH:
            return group.cross_gamma_by_month
        case Bucket.YEAR:
            return group.cross_gamma_by_year
        case _:
            assert_never(bucket)


def _refuse_early(aggregate: AggregateResults, risk: Risk, bucket: Bucket) -> None:
    """Raises the refusal prepared for a month or a year report whose selected groups hold risk
    before the valuation day's period, since #186, worded with the measure asked for; a day report
    is never refused."""
    match bucket:
        case Bucket.DAY:
            return
        case Bucket.MONTH:
            unit: Unit = "M"
        case Bucket.YEAR:
            unit = "Y"
        case _:
            assert_never(bucket)
    for measure, group_facts in _early_of(aggregate, risk):
        for early in group_facts:
            early.refuse(measure, unit)


def _early_of(
    aggregate: AggregateResults, risk: Risk
) -> tuple[tuple[str, tuple[EarlyRisk, ...]], ...]:
    """The saved facts a report of the risk reads, each with the measure it is worded as."""
    nominal = ("nominal delta", aggregate.early_nominal)
    delta = ("delta", aggregate.early_delta)
    dv01 = ("DV01", aggregate.early_dv01)
    cross = ("cross-gamma", aggregate.early_cross_gamma)
    match risk:
        case Risk.NOMINAL_DELTA:
            return (nominal,)
        case Risk.DELTA:
            return (delta,)
        case Risk.DV01:
            return (dv01,)
        case Risk.CROSS_GAMMA:
            return (cross,)
        case Risk.ALL:
            return (nominal, delta, dv01, cross)
        case _:
            assert_never(risk)
