"""The collection of saved risk across evaluated batches, aggregate-risk-kernel.md, the second
ticket of the risk reporting and aggregation series: one or many results, each already valued,
combined into one immutable record of risk, nothing priced, discounted or converted again.

A result's risk is already saved on it: the nominal lots and the discounted lots by pricing
reference and by observation day, month and year, with their totals, and for a bilateral batch
the DV01 by payment day, month and year with its total, each vector frozen when the batch was
prepared or valued. The collector reads those vectors and nothing else. It groups the occurrences
by the index object they are on, the exact object and not its name, a distinct index of the same
name refused, every occurrence of a group over the same history object and the same price-vector
object as the group's first; and the bilateral occurrences by the curve object they were valued
on and the result's currency. Within a group it forms the union of the saved axes and sums the
saved vectors onto it, one bincount per vector, the totals the saved scalars summed; across
groups it sums nothing, the lots of one index never added to another's, nor the DV01 of one
curve and currency to another's. Every occurrence counts, a repeated result twice. The report
axes, the union of the groups' observation axes, the union of their payment axes and the union of
both, are made here with every group's places on them, so that a report copies through saved
places and discovers, sorts and sums nothing; the day, month and year views are separate axes,
the saved month and year vectors summed onto their own unions and never bucketed again.

Positions name an occurrence in a refusal, counted from one as a sheet counts; the arrays hold
them from zero. Work is counted by the occurrences collected, the groups, the entries aligned,
the reductions and the report coordinates saved.
"""

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
from goosedove.trades.encoding import PaymentAxes
from goosedove.trades.evaluation import NO_DAYS, NOTHING, Bucket, Risk, RiskView, TradeResults

SOURCES_COLLECTED = "sources_collected"  # occurrences, every one, a repeated result counted again
INDEX_GROUPS = "index_groups"  # one per distinct index object among the occurrences
RATE_GROUPS = "rate_groups"  # one per distinct curve object and currency among the bilateral ones
ENTRIES_ALIGNED = "entries_aligned"  # saved vector entries placed on a union, over every reduction
AGGREGATE_REDUCTIONS = "aggregate_reductions"  # bincounts of saved vectors onto a union
REPORT_COORDINATES = (
    "report_coordinates"  # entries of the report axes saved, over the three buckets
)


@dataclass(frozen=True, slots=True)
class IndexGroup:
    """One index's risk across the occurrences on it: the index object, its reporting lot, the
    history and the price vector every occurrence shares, and the occurrences' positions,
    increasing. references is the union of the occurrences' pricing references, rows of the
    index's schedule increasing, with the nominal lots and the discounted lots summed onto them
    and the two totals, the saved scalars summed; days, months and years are the unions of the
    occurrences' observation axes with both lot vectors summed onto each. Every array frozen."""

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


@dataclass(frozen=True, slots=True)
class ReportAxes:
    """One bucket's report axes and every group's places on them: observed, the union of the
    index groups' observation axes, with each group's places; paid, the union of the rate groups'
    payment axes, with each group's places, no day when no curve values; and union, the two
    together, with every group's places on it. Made once with the collection so that a report of
    one risk or of all three copies saved vectors through saved places."""

    observed: NDArray[np.datetime64]
    observed_in: tuple[NDArray[np.intp], ...]
    paid: NDArray[np.datetime64]
    paid_in: tuple[NDArray[np.intp], ...]
    union: NDArray[np.datetime64]
    observed_in_union: tuple[NDArray[np.intp], ...]
    paid_in_union: tuple[NDArray[np.intp], ...]


@dataclass(frozen=True, slots=True)
class AggregateResults:
    """The collection: the valuation day every source shares; the sources, the occurrences in the
    order given, every one and by reference, so that a held collection keeps its sources
    readable; the index groups and the rate groups in first-appearance order; the currencies of
    the sources in first-appearance order, the DV01 columns of nothing a collection with no curve
    reports; and the report axes by day, by month and by year. Nothing here is a copy of a
    source's preparation, market or curve, and nothing is written after it is made."""

    as_of: np.datetime64
    sources: tuple[TradeResults, ...]
    index_groups: tuple[IndexGroup, ...]
    rate_groups: tuple[RateGroup, ...]
    currencies: tuple[str, ...]
    by_day: ReportAxes
    by_month: ReportAxes
    by_year: ReportAxes


def aggregate_results(sources: Sequence[TradeResults], counter: WorkCounter) -> AggregateResults:
    """The one way to collect evaluated batches, aggregate-risk-kernel.md: the occurrences
    snapshotted as given, one or many on one path, none refused; each occurrence in order held to
    the first's valuation day and to its index's first occurrence's history and price vector,
    the objects themselves; a distinct index object of a name already seen refused; then the
    groups' saved vectors summed onto the unions of their saved axes, the totals the saved
    scalars summed, each new number and vector finite or the first that is not refused by its
    measure, group and coordinate; and the report axes made with every place saved.

    Work: one occurrence per source, one group per index object and per curve and currency,
    one entry aligned per saved entry, one reduction per vector summed and one coordinate per
    entry of the report axes, reported to the counter; no quote, fixing or factor read, no
    trade resolved, no conversion and no evaluation.
    """
    results = tuple(sources)
    if not results:
        raise ValueError("results are none, expected at least one evaluated batch")
    as_of = results[0].as_of
    by_index = _grouped_by_index(results, as_of)
    by_curve = _grouped_by_curve(results)
    counter.hit(SOURCES_COLLECTED, len(results))
    counter.hit(INDEX_GROUPS, len(by_index))
    counter.hit(RATE_GROUPS, len(by_curve))
    index_groups = tuple([_index_group(results, positions, counter) for positions in by_index])
    rate_groups = tuple(
        [
            _rate_group(results, curve, number, currency, positions, counter)
            for curve, number, currency, positions in by_curve
        ]
    )
    by_day = _report_axes([g.days for g in index_groups], [r.days for r in rate_groups], counter)
    by_month = _report_axes(
        [g.months for g in index_groups], [r.months for r in rate_groups], counter
    )
    by_year = _report_axes([g.years for g in index_groups], [r.years for r in rate_groups], counter)
    currencies = tuple(dict.fromkeys([source.currency for source in results]))
    return AggregateResults(
        as_of, results, index_groups, rate_groups, currencies, by_day, by_month, by_year
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


def _grouped_by_curve(
    results: tuple[TradeResults, ...],
) -> list[tuple[DiscountCurve, int, str, list[int]]]:
    """The bilateral occurrences' positions grouped by the exact curve object and the result's
    currency, in first-appearance order, each curve numbered by its first appearance among the
    collection's curves whatever the currency, so that one curve valuing two currencies is two
    groups of one number; a cleared occurrence, valued on no curve, is in no group."""
    numbers: dict[int, int] = {}
    groups: list[tuple[DiscountCurve, int, str, list[int]]] = []
    where: dict[tuple[int, str], int] = {}
    for k, source in enumerate(results):
        curve = source.curve
        if curve is None:
            continue
        number = numbers.setdefault(id(curve), len(numbers) + 1)
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
        [m.prepared.encoded.months for m in members],
        (
            [m.prepared.monthly_lots for m in members],
            [m.discounted_monthly_lots for m in members],
        ),
        counter,
    )
    years, (yearly, discounted_yearly) = _summed(
        [m.prepared.encoded.years for m in members],
        ([m.prepared.yearly_lots for m in members], [m.discounted_yearly_lots for m in members]),
        counter,
    )
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
                ("in the month from", lambda b: months[b], by_month),
                ("in the year from", lambda b: years[b], by_year),
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
    total = sum([m.dv01 for m in members])
    where, value = _outrun(
        (
            ("on", lambda b: days[b], by_day),
            ("in the month from", lambda b: months[b], by_month),
            ("in the year from", lambda b: years[b], by_year),
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


def _summed(
    axes: list[NDArray[Any]],
    vectors: tuple[list[NDArray[np.float64]], ...],
    counter: WorkCounter,
) -> tuple[NDArray[Any], tuple[NDArray[np.float64], ...]]:
    """The union of the occurrences' saved axes, increasing, and each kind of saved vector summed
    onto it: the axes stacked once and their places on the union found once, then one bincount
    per kind over every entry of every occurrence, frozen; the entries aligned and the reductions
    reported to the counter. One occurrence takes the same path as many."""
    stacked = np.concatenate(axes)
    union = np.unique(stacked)
    place = np.searchsorted(union, stacked)
    sums = tuple(
        [np.bincount(place, weights=np.concatenate(kind), minlength=union.size) for kind in vectors]
    )
    for array in sums:
        array.setflags(write=False)
    counter.hit(ENTRIES_ALIGNED, int(stacked.size))
    counter.hit(AGGREGATE_REDUCTIONS, len(vectors))
    return union, sums


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
    counter: WorkCounter,
) -> ReportAxes:
    """One bucket's report axes: the union of the index groups' observation axes with each
    group's places, the union of the rate groups' payment axes with each group's places, no day
    when no curve values, and the union of both with every group's places; every array frozen,
    the coordinates reported to the counter."""
    observed = np.unique(np.concatenate(observation_axes))
    paid = np.unique(np.concatenate(payment_axes)) if payment_axes else NO_DAYS
    union = np.union1d(observed, paid)
    observed_in = tuple([np.searchsorted(observed, axis) for axis in observation_axes])
    paid_in = tuple([np.searchsorted(paid, axis) for axis in payment_axes])
    observed_in_union = tuple([np.searchsorted(union, axis) for axis in observation_axes])
    paid_in_union = tuple([np.searchsorted(union, axis) for axis in payment_axes])
    for array in (
        observed,
        paid,
        union,
        *observed_in,
        *paid_in,
        *observed_in_union,
        *paid_in_union,
    ):
        array.setflags(write=False)
    counter.hit(REPORT_COORDINATES, int(observed.size + paid.size + union.size))
    return ReportAxes(observed, observed_in, paid, paid_in, union, observed_in_union, paid_in_union)


def aggregate_view(aggregate: AggregateResults, risk: Risk, bucket: Bucket) -> RiskView:
    """The one way to read a collection's report, _ReportRisk's selection over a collection: the
    index groups' nominal lots or discounted lots on the union of their observation axes, one
    column per group under the index's name and its reporting lot's; the rate groups' DV01 on the
    union of their payment axes, one column per group under its curve's number and its currency,
    a collection with no curve one column of nothing per currency, `cleared USD dv01 [...]`, over
    no day; and all three on the union of both, each index group's two columns then each rate
    group's, every vector copied through the places the collection saved and zero where the group
    has no entry. The Totals are the groups' saved sums. Nothing is summed, sorted or discovered.

    Work: a copy per column, through the saved places; nothing else.
    """
    axes = _axes_of(aggregate, bucket)
    groups = aggregate.index_groups
    rates = aggregate.rate_groups
    nominal = tuple([f"{g.index.name} nominal_delta [{g.reporting_lot.name}]" for g in groups])
    delta = tuple([f"{g.index.name} delta [{g.reporting_lot.name}]" for g in groups])
    dv01 = tuple(
        [f"curve_{r.number} {r.currency} dv01 [{r.currency} per basis point]" for r in rates]
    )
    cleared = tuple([f"cleared {c} dv01 [{c} per basis point]" for c in aggregate.currencies])
    match risk:
        case Risk.NOMINAL_DELTA:
            columns = tuple(
                [
                    _placed(axes.observed.size, places, _lots(g, bucket))
                    for g, places in zip(groups, axes.observed_in, strict=True)
                ]
            )
            totals = tuple([g.lot_delta_total for g in groups])
            return RiskView(axes.observed, nominal, totals, columns)
        case Risk.DELTA:
            columns = tuple(
                [
                    _placed(axes.observed.size, places, _discounted_lots(g, bucket))
                    for g, places in zip(groups, axes.observed_in, strict=True)
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
                    _placed(axes.paid.size, places, _dv01(r, bucket))
                    for r, places in zip(rates, axes.paid_in, strict=True)
                ]
            )
            return RiskView(axes.paid, dv01, tuple([r.dv01 for r in rates]), columns)
        case Risk.ALL:
            labels: list[str] = []
            totals_all: list[float] = []
            placed: list[NDArray[np.float64]] = []
            for g, label_n, label_d, places in zip(
                groups, nominal, delta, axes.observed_in_union, strict=True
            ):
                labels.extend((label_n, label_d))
                totals_all.extend((g.lot_delta_total, g.discounted_lot_delta_total))
                placed.append(_placed(axes.union.size, places, _lots(g, bucket)))
                placed.append(_placed(axes.union.size, places, _discounted_lots(g, bucket)))
            if rates:
                for r, label, places in zip(rates, dv01, axes.paid_in_union, strict=True):
                    labels.append(label)
                    totals_all.append(r.dv01)
                    placed.append(_placed(axes.union.size, places, _dv01(r, bucket)))
            else:
                for label in cleared:
                    labels.append(label)
                    totals_all.append(0.0)
                    placed.append(np.zeros(axes.union.size))
            return RiskView(axes.union, tuple(labels), tuple(totals_all), tuple(placed))
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


def _placed(
    size: int, places: NDArray[np.intp], vector: NDArray[np.float64]
) -> NDArray[np.float64]:
    """A saved vector copied onto a report axis through its saved places, zero elsewhere."""
    column = np.zeros(size)
    column[places] = vector
    return column
