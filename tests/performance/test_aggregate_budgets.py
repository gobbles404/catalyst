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
from test_bilateral_budgets import CASES, IDS, bilateral_terms, curve_set, set_on, tick
from test_cashflow_budgets import AS_OF as CASHFLOW_AS_OF
from test_cashflow_budgets import a_batch as a_cashflow_batch
from test_cashflow_budgets import a_curve as a_cashflow_curve
from test_seam_allocation import SLACK, least_peak
from test_trade_budgets import GAS, CallProfile, a_batch, a_history, a_market, observed_of

from goosedove.cashflows.valuation import cashflow_results
from goosedove.globals.unit_conversions import UNITS
from goosedove.globals.valuation_date import valuation_date
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.aggregation import AggregateResults, aggregate_results, aggregate_view
from goosedove.trades.encoding import PaymentAxes, encoded
from goosedove.trades.evaluation import trade_results
from goosedove.trades.preparation import prepared_trades
from goosedove.trades.results import TradeResults
from goosedove.trades.risk_report import Bucket, Risk
from goosedove.trades.schedule_methods import ScheduleMethod

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
    curves = set_on(as_of)
    prep = prepared_trades(
        encoded(terms, observed_of(terms), UNITS, WorkCounter()), history, WorkCounter()
    )
    pair = [tick(prep, market, curves), tick(prep, market, curves)]
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
                g.occurrences, g.references, g.nominal_delta, g.delta,
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
    for c in agg.cross_groups:
        total += sum(
            a.nbytes
            for a in (
                c.occurrences,
                c.references,
                c.cross_gamma,
                c.days,
                c.cross_gamma_by_day,
                c.months,
                c.cross_gamma_by_month,
                c.years,
                c.cross_gamma_by_year,
            )
        )
    for axes in (agg.by_day, agg.by_month, agg.by_year):
        total += axes.observed.nbytes + axes.paid.nbytes + axes.union.nbytes
        for places in (
            axes.observed_in,
            axes.paid_in,
            axes.observed_in_union,
            axes.paid_in_union,
            axes.cross_in,
            axes.cross_in_union,
        ):
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
    # Every occurrence counted; one group of each kind, since #197 the cross group among them;
    # every saved entry of every occurrence aligned once per vector summed over its axis, the
    # four observation axes twice, for the lots and for the cross-gamma, and the three payment
    # axes; two lot vectors summed onto each observation axis, the DV01 onto each payment axis
    # and the cross-gamma onto each observation axis, fifteen reductions; and the three buckets'
    # axes saved, the observed, the paid and their union each.
    delta_axes = (
        enc.references.size + enc.days.size + enc.contract_months.size + enc.contract_years.size
    )
    per_source = 2 * delta_axes + paid.days.size + paid.months.size + paid.years.size
    coordinates = sum(
        axes.observed.size + axes.paid.size + axes.union.size
        for axes in (agg.by_day, agg.by_month, agg.by_year)
    )
    assert counter.freeze().as_dict() == {
        "aggregate_reductions": 15,
        "contributions_collected": 2 * count,  # a rate and a cross contribution per source
        "cross_groups": 1,
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
    assert agg.index_groups[0].nominal_delta_total == pytest.approx(
        count * sources[0].nominal_delta_total
    )
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
    # The membership and the three groupings, one index group, one rate group and since #197 one
    # cross group summed over eleven axes by fifteen compensated passes, four looks for a sum
    # past the largest number and the three buckets' axes with the cross group's places;
    # thirty counts, the contributions among them since slice 2, and the curves' words made
    # once; nothing of the kernel, the market, the curve or the preparation is called.
    assert call_profile(lambda: aggregate_results(sources, counter)) == {
        "aggregate_results": 1,
        "_grouped_by_index": 1,
        "_contributions_of": 1,
        "_cross_contributions": 2 * count,  # once for the count, once for the words
        "_curve_words": 1,
        "curve_words": 1,
        "_grouped_by_curve": 1,
        "_grouped_by_index_and_curve": 1,
        "_index_group": 1,
        "_rate_group": 1,
        "_cross_group": 1,
        "_summed": 11,
        "_compensated": 15,
        "_outrun": 4,
        "_report_axes": 1,  # by day; since #186 the month and year axes are the display's
        "_period_report_axes": 2,
        "period_start": 2,
        "places_from": 6,
        "rows_through": 4,
        "display_periods": 2,
        "_early_lots": 2,
        "early_risk": 4,
        "early_fact": 8,
        "WorkCounter.hit": 30,
    }
    # Fourteen uniques, the eleven unions of saved axes, the cross group's four among them since
    # #197, the day report axes and their union, each a flatten, a sort and a hash; twenty-three
    # searches for places; fifteen compensated passes, each two zeros and the flags set down once;
    # the looks for a sum past the largest number, fifteen; the three position arrays; and
    # forty-six arrays frozen. The same at one source and at twenty-four: a pass adds each
    # occurrence's entries at once, so more occurrences are more steps of the same arithmetic and
    # not more of these calls.
    assert numpy_calls(lambda: aggregate_results(sources, WorkCounter())) == {
        "generic.astype": 2,  # the valuation day to its month and its year, since #186
        "ndarray.any": 15,  # since #197 the cross group's four looks for a sum past the largest
        "ndarray.astype": 14,  # the display axes' keys, periods and first days
        "ndarray.flatten": 14,  # since #197 the cross group's four unions among the uniques
        "ndarray.nonzero": 8,  # the looks for risk before the start, four measures, two buckets
        "ndarray.ravel": 8,
        "ndarray.searchsorted": 23,  # since #197 eight more, the cross group's places
        "ndarray.setflags": 46,  # since #197 thirteen more, the cross group's arrays and places
        "ndarray.sort": 14,
        "numpy._make_extobj": 15,
        "numpy._unique_hash": 14,
        "numpy.arange": 2,  # the two display axes
        "numpy.array": 3,  # the three groups' positions
        "numpy.asanyarray": 36,
        "numpy.zeros": 30,  # fifteen compensated passes, two each
        "ufunc.reduce": 15,
    }


# The peak follows the entries stacked: the largest union made is the observation days', every
# source's day axis concatenated with its places and the sort's copies, and the compensated pass's
# running sum, low part and one occurrence's step beside them, five arrays of eight bytes an entry
# in all, over the bytes retained and within sixteen slacks of the records, lists and small
# arrays, the cross group's since #197 among them. Measured 2026-10-17 with the cross group:
# 10,280 bytes for one five-trade lastday source, 11,881 for two and 15,658 for twenty-four;
# 69,279 for one asian source of 2,000 trades over 519 days, 79,087 for two and 266,855 for
# twenty-four, whose stacked days are 12,456; against 8,776, 9,880, 12,721, 55,839, 64,607 and
# 251,943 on 2026-10-11 with the compensated reduction. The retained bytes are exactly the new
# arrays', 592 for the one lastday source and 50,752 for the one asian, the sources' own vectors
# shared by reference and never copied.
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
        <= 40 * stacked + retained + 16 * SLACK
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
        axes += 2 * sum(places.size for places in bucket.cross_in)
    assert (d, p, m, pm, y, py) == (d, p, m, pm, y, py)  # the saved axes' sizes, read above
    # Since #197 the cross group's positions, its four axes and its four vectors beside them,
    # the same axes as the index group's, every source being on the one curve.
    assert (
        retained
        == 8 * (count + 3 * refs + 3 * d + 3 * m + 3 * y)
        + 8 * (count + 2 * p + 2 * pm + 2 * py)
        + 8 * (count + 2 * refs + 2 * d + 2 * m + 2 * y)
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
    cross_groups = len(agg.cross_groups)
    for risk, columns, chosen, refused in (
        (Risk.NOMINAL_DELTA, 1, "_lots", index_groups),
        (Risk.DELTA, 1, "_discounted_lots", index_groups),
        (Risk.DV01, 1, "_dv01", rate_groups),
        (Risk.CROSS_GAMMA, 1, "_cross_gamma", cross_groups),
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
                "delta_labels": index_groups,  # the headings, spelled once in risk_report.py
                "dv01_label": rate_groups + len(agg.currencies),
                "cross_gamma_label": cross_groups,
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
        # All four, since #197: four columns over the union, each through its own places.
        assert numpy_calls(lambda b=bucket: aggregate_view(agg, Risk.ALL, b)) == {"numpy.zeros": 4}
        early = (
            {}
            if bucket is Bucket.DAY
            else {
                "_early_of": 1,
                "EarlyRisk.refuse": 2 * index_groups + rate_groups + cross_groups,
            }
        )
        assert call_profile(lambda b=bucket: aggregate_view(agg, Risk.ALL, b)) == {
            "aggregate_view": 1,
            "delta_labels": index_groups,
            "dv01_label": rate_groups + len(agg.currencies),
            "cross_gamma_label": cross_groups,
            "_axes_of": 1,
            "_refuse_early": 1,
            **early,
            "_aggregate_all": 1,
            "_lots": 1,
            "_discounted_lots": 1,
            "_dv01": 1,
            "_cross_gamma": 1,
            "placed": 4,
        }
        view = aggregate_view(agg, Risk.ALL, bucket)
        # Four columns of eight bytes a row, and the lists of labels, totals, columns and places
        # beside them, within two slacks.
        assert (
            least_peak(lambda b=bucket: aggregate_view(agg, Risk.ALL, b))
            <= 32 * view.dates.size + 2 * SLACK
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
    # one index group of two occurrences, one rate group of one and since #197 two cross groups,
    # the bilateral pair summed over its four delta axes again and the cleared pair the known
    # zero, nothing aligned; the cleared source's observation entries aligned and no payment
    # entry of its own; the same functions and numpy calls.
    terms = bilateral_terms(components, contracts, method)
    assert terms.index is GAS
    history = a_history(as_of=as_of, ix=GAS)
    market = a_market(history)
    discounted = tick(
        prepared_trades(
            encoded(terms, observed_of(terms), UNITS, WorkCounter()), history, WorkCounter()
        ),
        market,
        set_on(as_of),
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
    bilateral_delta_axes = (
        discounted.prepared.encoded.references.size
        + discounted.prepared.encoded.days.size
        + discounted.prepared.encoded.contract_months.size
        + discounted.prepared.encoded.contract_years.size
    )
    assert (
        counter.freeze().as_dict()["entries_aligned"]
        == observed + paid.days.size + paid.months.size + paid.years.size + bilateral_delta_axes
    )
    assert counter.freeze().as_dict()["rate_groups"] == 1
    assert counter.freeze().as_dict()["cross_groups"] == 2
    assert [c.word for c in agg.cross_groups] == ["SOFR", None]
    assert (
        call_profile(lambda: aggregate_results([discounted, cleared], WorkCounter()))["_summed"]
        == 11
    )
    assert (
        numpy_calls(lambda: aggregate_results([discounted, cleared], WorkCounter()))[
            "ndarray.setflags"
        ]
        == 51  # since #197 the bilateral pair's thirteen more and the cleared pair's five
    )


# A batch of cashflows beside a bilateral batch of trades valued on the cashflows' day over one
# curve, since named-curves-slice-2.md: one index group of the trades alone, one rate group of
# both, one cross group of the trades; the cashflows' payment days, months and years aligned onto
# the rate group's unions and nothing else of theirs read; the same eleven unions and fifteen
# compensated passes as two trade batches; three contributions counted.
def test_a_cashflow_source_adds_its_payment_entries_to_its_curves_group_and_nothing_else(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    as_of = str(CASHFLOW_AS_OF)
    terms = bilateral_terms(500, 12, ScheduleMethod.LASTDAY)
    history = a_history(as_of=as_of, ix=GAS)
    market = a_market(history)
    curve = a_cashflow_curve(2_000)  # from the cashflows' day, past every payment of either
    discounted = tick(
        prepared_trades(
            encoded(terms, observed_of(terms), UNITS, WorkCounter()), history, WorkCounter()
        ),
        market,
        curve_set(curve),
    )
    cashflows = cashflow_results(
        a_cashflow_batch(2_000, 20), valuation_date(CASHFLOW_AS_OF, 0.5), curve, WorkCounter()
    )
    counter = WorkCounter()
    agg = aggregate_results([discounted, cashflows], counter)
    np.testing.assert_array_equal(agg.index_groups[0].occurrences, [0])
    np.testing.assert_array_equal(agg.rate_groups[0].occurrences, [0, 1])
    np.testing.assert_array_equal(agg.cross_groups[0].occurrences, [0])
    paid = payment_axes(discounted)
    trade_axes = (
        discounted.prepared.encoded.references.size
        + discounted.prepared.encoded.days.size
        + discounted.prepared.encoded.contract_months.size
        + discounted.prepared.encoded.contract_years.size
    )
    batch = cashflows.cashflows
    counts = counter.freeze().as_dict()
    assert counts["sources_collected"] == 2 and counts["contributions_collected"] == 3
    assert (counts["index_groups"], counts["rate_groups"], counts["cross_groups"]) == (1, 1, 1)
    assert counts["entries_aligned"] == (
        2 * trade_axes  # the lots and, since #197, the cross-gamma on the four delta axes
        + paid.days.size
        + paid.months.size
        + paid.years.size
        + batch.payment_days.size
        + batch.months.size
        + batch.years.size
    )
    assert counts["aggregate_reductions"] == 15
    profile = call_profile(lambda: aggregate_results([discounted, cashflows], WorkCounter()))
    assert profile["_summed"] == 11 and profile["_compensated"] == 15
    assert profile["_cross_contributions"] == 4 and profile["_contributions_of"] == 1
    # Cashflows alone: no index group and no cross group, the rate group's three unions and
    # three passes, the report axes with no observation day.
    counter = WorkCounter()
    alone = aggregate_results([cashflows], counter)
    assert alone.index_groups == () and alone.cross_groups == ()
    counts = counter.freeze().as_dict()
    assert counts["sources_collected"] == 1 and counts["contributions_collected"] == 1
    assert (counts["index_groups"], counts["rate_groups"], counts["cross_groups"]) == (0, 1, 0)
    assert counts["entries_aligned"] == (
        batch.payment_days.size + batch.months.size + batch.years.size
    )
    assert counts["aggregate_reductions"] == 3
    profile = call_profile(lambda: aggregate_results([cashflows], WorkCounter()))
    assert profile["_summed"] == 3 and profile["_compensated"] == 3
    assert "_index_group" not in profile and "_cross_group" not in profile
    assert alone.by_day.observed.size == 0 and alone.by_day.paid.size == batch.payment_days.size
    # The views copy through saved places and nothing more, as a trade collection's do.
    for bucket in Bucket:
        for risk in (Risk.DV01, Risk.ALL):
            view = aggregate_view(alone, risk, bucket)
            assert (
                least_peak(lambda r=risk, b=bucket: aggregate_view(alone, r, b))
                <= 8 * view.dates.size + SLACK
            )
