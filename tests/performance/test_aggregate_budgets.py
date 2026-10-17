"""What a collection of evaluated batches costs, aggregate-risk-kernel.md. The collector reads the
saved vectors and nothing else: the counter's occurrences, groups, entries aligned, reductions and
report coordinates; the same functions and numpy calls at one source and at twenty-four, with no
quote, fixing or factor read, no trade resolved and no evaluation among them; the peak following
the saved entries stacked and the retained bytes exactly the new vectors'; and a view by reference
and by saved places, one copy per column and nothing discovered. The fixtures are the bilateral
budgets': each case's batch prepared once and valued twice over the same market and curve, two
result objects of one content, and for the lastday cases the cleared batch of the same index on
the same history beside them."""

import numpy as np
import pytest
from test_bilateral_budgets import CASES, IDS, bilateral_terms, curve_on, tick
from test_seam_allocation import SLACK, least_peak
from test_trade_budgets import GAS, CallProfile, a_batch, a_history, a_market, observed_of

from goosedove.globals.unit_conversions import UNITS
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.aggregation import AggregateResults, aggregate_results, aggregate_view
from goosedove.trades.encoding import PaymentAxes, encoded
from goosedove.trades.evaluation import trade_results
from goosedove.trades.preparation import prepared_trades
from goosedove.trades.results import Bucket, Risk, TradeResults
from goosedove.trades.terms import ScheduleMethod

COUNTS = [1, 2, 24]
COUNT_IDS = ["one source", "two sources", "twenty-four sources"]


def valued_sources(
    method: ScheduleMethod, components: int, contracts: int, as_of: str, count: int
) -> list[TradeResults]:
    """That many results of one bilateral batch, valued twice over one market and curve and the
    two repeated, every one on the same history and price-vector objects."""
    terms = bilateral_terms(components, contracts, method)
    history = a_history(as_of=as_of, ix=terms.index)
    market = a_market(history)
    curve = curve_on(as_of)
    prep = prepared_trades(
        encoded(terms, observed_of(terms), UNITS, WorkCounter()), history, WorkCounter()
    )
    pair = [tick(prep, market, curve), tick(prep, market, curve)]
    return (pair * (count // 2 + 1))[:count]


def payment_axes(source: TradeResults) -> PaymentAxes:
    axes = source.prepared.encoded.payment_axes
    assert axes is not None
    return axes


def retained_bytes(agg: AggregateResults) -> int:
    """The bytes of every array the collection made, none of a source's counted."""
    total = 0
    for g in agg.index_groups:
        total += sum(
            a.nbytes
            for a in (
                g.occurrences, g.references, g.lot_delta, g.discounted_lot_delta,
                g.days, g.daily_lots, g.discounted_daily_lots,
                g.months, g.monthly_lots, g.discounted_monthly_lots,
                g.years, g.yearly_lots, g.discounted_yearly_lots,
            )
        )  # fmt: skip
    for r in agg.rate_groups:
        total += sum(
            a.nbytes
            for a in (
                r.occurrences,
                r.days,
                r.dv01_by_day,
                r.months,
                r.dv01_by_month,
                r.years,
                r.dv01_by_year,
            )
        )
    for axes in (agg.by_day, agg.by_month, agg.by_year):
        total += axes.observed.nbytes + axes.paid.nbytes + axes.union.nbytes
        for places in (axes.observed_in, axes.paid_in, axes.observed_in_union, axes.paid_in_union):
            total += sum(a.nbytes for a in places)
    return total


@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
@pytest.mark.parametrize("count", COUNTS, ids=COUNT_IDS)
def test_a_collection_counts_its_sources_groups_entries_and_reductions(
    method: ScheduleMethod,
    components: int,
    contracts: int,
    as_of: str,
    live: int,
    unpaid: int,
    count: int,
) -> None:
    sources = valued_sources(method, components, contracts, as_of, count)
    counter = WorkCounter()
    agg = aggregate_results(sources, counter)
    enc = sources[0].prepared.encoded
    paid = payment_axes(sources[0])
    # Every occurrence counted; one group of each kind; every saved entry of every occurrence
    # aligned once, the four observation axes and the three payment axes; two lot vectors summed
    # onto each observation axis and the DV01 onto each payment axis, eleven reductions; and the
    # three buckets' axes saved, the observed, the paid and their union each.
    per_source = (
        enc.references.size + enc.days.size + enc.contract_months.size + enc.contract_years.size
    )
    per_source += paid.days.size + paid.months.size + paid.years.size
    coordinates = sum(
        axes.observed.size + axes.paid.size + axes.union.size
        for axes in (agg.by_day, agg.by_month, agg.by_year)
    )
    assert counter.freeze().as_dict() == {
        "aggregate_reductions": 11,
        "entries_aligned": count * per_source,
        "index_groups": 1,
        "rate_groups": 1,
        "report_coordinates": coordinates,
        "sources_collected": count,
    }
    # The axes are one source's, every source sharing them, and the sums are the source's times
    # the count, nothing of the batch's trades or days expanded again.
    np.testing.assert_array_equal(agg.index_groups[0].days, enc.days)
    np.testing.assert_array_equal(agg.rate_groups[0].days, paid.days)
    np.testing.assert_allclose(
        agg.index_groups[0].daily_lots,
        count * sources[0].prepared.daily_lots,
        rtol=1e-12,
        atol=1e-12,
    )
    assert agg.index_groups[0].lot_delta_total == pytest.approx(count * sources[0].lot_delta_total)
    assert agg.rate_groups[0].dv01 == pytest.approx(count * sources[0].dv01, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
@pytest.mark.parametrize("count", COUNTS, ids=COUNT_IDS)
def test_a_collection_runs_the_same_functions_at_any_size(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    method: ScheduleMethod,
    components: int,
    contracts: int,
    as_of: str,
    live: int,
    unpaid: int,
    count: int,
) -> None:
    sources = valued_sources(method, components, contracts, as_of, count)
    counter = WorkCounter()
    # The membership and the two groupings, one index group and one rate group summed over seven
    # axes by eleven compensated passes, three looks for a sum past the largest number and the
    # three buckets' axes; twenty counts; nothing of the kernel, the market, the curve or the
    # preparation is called.
    assert call_profile(lambda: aggregate_results(sources, counter)) == {
        "aggregate_results": 1,
        "_grouped_by_index": 1,
        "_grouped_by_curve": 1,
        "_index_group": 1,
        "_rate_group": 1,
        "_summed": 7,
        "_compensated": 11,
        "_outrun": 3,
        "_report_axes": 1,  # by day; since #186 the month and year axes are the display's
        "_period_report_axes": 2,
        "period_start": 2,
        "places_from": 4,
        "rows_through": 4,
        "display_periods": 2,
        "_early_lots": 2,
        "early_risk": 3,
        "early_fact": 6,
        "WorkCounter.hit": 20,
    }
    # Sixteen uniques, the seven unions of saved axes, the six report axes and the three unions of
    # both, each a flatten, a sort and a hash; nineteen searches for places; eleven compensated
    # passes, each two zeros and the flags set down once; the looks for a sum past the largest
    # number, eleven; the two position arrays; and forty-one arrays frozen. The same at one source
    # and at twenty-four: a pass adds each occurrence's entries at once, so more occurrences are
    # more steps of the same arithmetic and not more of these calls.
    assert numpy_calls(lambda: aggregate_results(sources, WorkCounter())) == {
        "generic.astype": 2,  # the valuation day to its month and its year, since #186
        "ndarray.any": 11,
        "ndarray.astype": 10,  # the display axes' keys, periods and first days, by group and bucket
        "ndarray.flatten": 10,
        "ndarray.nonzero": 6,  # the looks for risk before the start, three measures by two buckets
        "ndarray.ravel": 6,
        "ndarray.searchsorted": 15,
        "ndarray.setflags": 33,
        "ndarray.sort": 10,
        "numpy._make_extobj": 11,
        "numpy._unique_hash": 10,
        "numpy.arange": 2,  # the two display axes
        "numpy.array": 2,
        "numpy.asanyarray": 26,
        "numpy.zeros": 22,
        "ufunc.reduce": 11,
    }


# The peak follows the entries stacked: the largest union made is the observation days', every
# source's day axis concatenated with its places and the sort's copies, and the compensated pass's
# running sum, low part and one occurrence's step beside them, five arrays of eight bytes an entry
# in all, over the bytes retained and within twelve slacks of the records, lists and small arrays.
# Measured 2026-10-11 with the compensated reduction: 8,776 bytes for one five-trade lastday
# source, 9,880 for two and 12,721 for twenty-four; 55,839 for one asian source of 2,000 trades
# over 519 days, 64,607 for two and 251,943 for twenty-four, whose stacked days are 12,456. The
# retained bytes are exactly the new arrays', 560 for the one lastday source and 33,224 for the one
# asian, the sources' own vectors shared by reference and never copied.
@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
@pytest.mark.parametrize("count", COUNTS, ids=COUNT_IDS)
def test_a_collection_allocates_by_the_entries_stacked_and_retains_its_vectors(
    method: ScheduleMethod,
    components: int,
    contracts: int,
    as_of: str,
    live: int,
    unpaid: int,
    count: int,
) -> None:
    sources = valued_sources(method, components, contracts, as_of, count)
    agg = aggregate_results(sources, WorkCounter())
    retained = retained_bytes(agg)
    stacked = sum(s.prepared.encoded.days.size for s in sources)
    assert (
        least_peak(lambda: aggregate_results(sources, WorkCounter()))
        <= 40 * stacked + retained + 12 * SLACK
    )
    g, r = agg.index_groups[0], agg.rate_groups[0]
    d, m, y, refs = g.days.size, g.months.size, g.years.size, g.references.size
    p, pm, py = r.days.size, r.months.size, r.years.size
    # The report axes' bytes as the helper counts them: each axis, each group's places twice,
    # once per union they place onto; by month and by year, since #186, the display's rows.
    axes = 0
    for bucket in (agg.by_day, agg.by_month, agg.by_year):
        axes += bucket.observed.size + bucket.paid.size + bucket.union.size
        axes += 2 * sum(places.size for places in bucket.observed_in)
        axes += 2 * sum(places.size for places in bucket.paid_in)
    assert (d, p, m, pm, y, py) == (d, p, m, pm, y, py)  # the saved axes' sizes, read above
    assert (
        retained
        == 8 * (count + 3 * refs + 3 * d + 3 * m + 3 * y)
        + 8 * (count + 2 * p + 2 * pm + 2 * py)
        + 8 * axes
    )
    for source in sources:
        assert not source.prepared.daily_lots.flags.writeable
        assert agg.index_groups[0].daily_lots is not source.prepared.daily_lots


@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
def test_a_view_copies_through_saved_places_and_discovers_nothing(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    method: ScheduleMethod,
    components: int,
    contracts: int,
    as_of: str,
    live: int,
    unpaid: int,
) -> None:
    agg = aggregate_results(valued_sources(method, components, contracts, as_of, 2), WorkCounter())
    index_groups, rate_groups = len(agg.index_groups), len(agg.rate_groups)
    for risk, columns, chosen, refused in (
        (Risk.NOMINAL_DELTA, 1, "_lots", index_groups),
        (Risk.DELTA, 1, "_discounted_lots", index_groups),
        (Risk.DV01, 1, "_dv01", rate_groups),
    ):
        for bucket in Bucket:
            # One column of zeros over the axis, the saved vector copied through its places; by
            # month and by year, since #186, every selected group's saved facts read.
            assert numpy_calls(lambda r=risk, b=bucket: aggregate_view(agg, r, b)) == {
                "numpy.zeros": columns
            }
            early = {} if bucket is Bucket.DAY else {"_early_of": 1, "EarlyRisk.refuse": refused}
            assert call_profile(lambda r=risk, b=bucket: aggregate_view(agg, r, b)) == {
                "aggregate_view": 1,
                "_axes_of": 1,
                "_refuse_early": 1,
                **early,
                chosen: 1,
                "placed": 1,
            }
            view = aggregate_view(agg, risk, bucket)
            assert (
                least_peak(lambda r=risk, b=bucket: aggregate_view(agg, r, b))
                <= 8 * view.dates.size + SLACK
            )
    for bucket in Bucket:
        # All three: three columns over the union, each through its own places.
        assert numpy_calls(lambda b=bucket: aggregate_view(agg, Risk.ALL, b)) == {"numpy.zeros": 3}
        early = (
            {}
            if bucket is Bucket.DAY
            else {"_early_of": 1, "EarlyRisk.refuse": 2 * index_groups + rate_groups}
        )
        assert call_profile(lambda b=bucket: aggregate_view(agg, Risk.ALL, b)) == {
            "aggregate_view": 1,
            "_axes_of": 1,
            "_refuse_early": 1,
            **early,
            "_lots": 1,
            "_discounted_lots": 1,
            "_dv01": 1,
            "placed": 3,
        }
        view = aggregate_view(agg, Risk.ALL, bucket)
        # Three columns of eight bytes a row, and the lists of labels, totals, columns and places
        # beside them, within two slacks.
        assert (
            least_peak(lambda b=bucket: aggregate_view(agg, Risk.ALL, b))
            <= 24 * view.dates.size + 2 * SLACK
        )


@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES[:2], ids=IDS[:2]
)
def test_a_cleared_source_beside_a_bilateral_one_adds_its_entries_and_no_rate_group(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    method: ScheduleMethod,
    components: int,
    contracts: int,
    as_of: str,
    live: int,
    unpaid: int,
) -> None:
    # The cleared batch of the same index on the same history and market beside the bilateral one:
    # one index group of two occurrences, one rate group of one, the cleared source's observation
    # entries aligned and no payment entry of its own; the same functions and numpy calls.
    terms = bilateral_terms(components, contracts, method)
    assert terms.index is GAS
    history = a_history(as_of=as_of, ix=GAS)
    market = a_market(history)
    discounted = tick(
        prepared_trades(
            encoded(terms, observed_of(terms), UNITS, WorkCounter()), history, WorkCounter()
        ),
        market,
        curve_on(as_of),
    )
    cleared = trade_results(
        prepared_trades(a_batch(components, contracts), history, WorkCounter()),
        market,
        WorkCounter(),
    )
    counter = WorkCounter()
    agg = aggregate_results([discounted, cleared], counter)
    np.testing.assert_array_equal(agg.index_groups[0].occurrences, [0, 1])
    np.testing.assert_array_equal(agg.rate_groups[0].occurrences, [0])
    paid = payment_axes(discounted)
    observed = sum(
        s.prepared.encoded.references.size
        + s.prepared.encoded.days.size
        + s.prepared.encoded.contract_months.size
        + s.prepared.encoded.contract_years.size
        for s in (discounted, cleared)
    )
    assert (
        counter.freeze().as_dict()["entries_aligned"]
        == observed + paid.days.size + paid.months.size + paid.years.size
    )
    assert counter.freeze().as_dict()["rate_groups"] == 1
    assert (
        call_profile(lambda: aggregate_results([discounted, cleared], WorkCounter()))["_summed"]
        == 7
    )
    assert (
        numpy_calls(lambda: aggregate_results([discounted, cleared], WorkCounter()))[
            "ndarray.setflags"
        ]
        == 33
    )
