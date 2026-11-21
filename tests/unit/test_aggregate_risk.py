"""The collection of saved risk across evaluated batches, aggregate-risk-kernel.md: one or many
results combined by the index object and by the curve object and currency, the saved vectors
summed onto the unions of the saved axes and nothing priced again. The figures are the ticket's,
priced by hand here: a one-barrel HNG observing 4 January 2027 at 80 against 70 and a one-barrel
WTI observing 5 January at 55 against 50, the bilateral sources on one USD curve of 0.95 a year out
and 0.90 two years out, every payment unpaid. The tolerances are the bilateral kernel's.
docs/library/trades/aggregate-results.md is the page."""

from dataclasses import fields, replace
from typing import Any

import numpy as np
import pytest
from test_bilateral_kernel import (
    A_YEAR,
    AS_OF,
    CLOSE,
    FLAT,
    TIGHT,
    TRIO,
    TWO_YEARS,
    cross,
    curve_of,
    curve_set,
    rate,
    terms_of,
)
from test_cashflows import DAY_BEFORE, booked, booked_on
from test_cashflows import valued as cashflows_valued
from test_trades import an_index, dates, history_on, numbers, observed_of, quoted

from catalyst.cashflows.valuation import CashflowResults
from catalyst.globals.discount_curve import DiscountCurve
from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.holiday_calendar import holiday_calendar
from catalyst.index_definitions.index import index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market import Market, market
from catalyst.market.market_history import MarketHistory
from catalyst.trades.aggregation import (
    AggregateResults,
    aggregate_results,
    aggregate_view,
)
from catalyst.trades.contributions import RateContribution
from catalyst.trades.encoding import encoded
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import ResolvedTrades
from catalyst.trades.results import TradeResults, risk_view
from catalyst.trades.risk_report import (
    Bucket,
    Risk,
    RiskView,
    cross_gamma_label,
    delta_labels,
    dv01_label,
    placed,
)
from catalyst.trades.terms import Route

MONTHS = (("Z26", "2026-12-31"), ("F27", "2027-01-04"), ("F29", "2029-01-05"))
HNG = an_index(
    "HNG", MONTHS, ("2027-12-27",), ("DOLLAR", "BBL"), ("VOLUME", "BBL"), ("LOT", 1.0, "BBL")
)
# WTI's F27 expires a day later, so its lastday observation is 5 January: the two indexes observe
# on different days of one month, and D's payment on 4 January 2028 comes 364 days after it.
WTI = an_index(
    "WTI",
    (("Z26", "2026-12-31"), ("F27", "2027-01-05"), ("F29", "2029-01-05")),
    ("2027-12-27",),
    ("DOLLAR", "BBL"),
    ("VOLUME", "BBL"),
    ("LOT", 1.0, "BBL"),
)
HNG_HISTORY = history_on(HNG, AS_OF, {})
HNG_MARKET = quoted(HNG_HISTORY, 80.0, 50.0)
WTI_HISTORY = history_on(WTI, AS_OF, {})
WTI_MARKET = quoted(WTI_HISTORY, 55.0, 50.0)
A_DAY, B_DAY = np.datetime64(AS_OF), np.datetime64("2027-01-05")
JAN_27, JAN_28, JAN_29 = "2027-01-01", "2028-01-01", "2029-01-01"
HNG_NOMINAL, HNG_DELTA = "HNG nominal_delta [LOT]", "HNG delta [LOT]"
WTI_NOMINAL, WTI_DELTA = "WTI nominal_delta [LOT]", "WTI delta [LOT]"
CURVE_1 = "SOFR USD dv01 [DOLLAR per basis point]"
CLEARED_USD = "cleared USD dv01 [DOLLAR per basis point]"
HNG_CROSS = "HNG SOFR cross_gamma [LOT per basis point]"
HNG_CLEARED_CROSS = "HNG cleared cross_gamma [LOT per basis point]"
WTI_CROSS = "WTI SOFR cross_gamma [LOT per basis point]"
WTI_CLEARED_CROSS = "WTI cleared cross_gamma [LOT per basis point]"


def valued_on(
    terms: ResolvedTrades, history: MarketHistory, quoted_on: Market, curve: DiscountCurve | None
) -> TradeResults:
    """The terms prepared against that history and valued against that market, the same objects
    for every source that is to combine."""
    prep = prepared_trades(
        encoded(terms, (observed_of(terms),), UNITS, WorkCounter()), (history,), WorkCounter()
    )
    return trade_results(
        prep, (quoted_on,), WorkCounter(), None if curve is None else curve_set(curve)
    )


def hng(
    quantities: tuple[float, ...],
    pays: tuple[str, ...],
    route: Route,
    fixed: float = 70.0,
    key: str = "SOFR",
) -> ResolvedTrades:
    return terms_of(
        quantities, pays, (261,) * len(quantities), route=route, fixed=fixed, ix=HNG, key=key
    )


def wti(quantities: tuple[float, ...], route: Route) -> ResolvedTrades:
    return terms_of(
        quantities,
        (A_YEAR,) * len(quantities),
        (261,) * len(quantities),
        route=route,
        fixed=50.0,
        ix=WTI,
    )


@pytest.fixture(scope="module")
def sources() -> dict[str, TradeResults]:
    """The ticket's four: A HNG cleared +10, B HNG bilateral +10 paying a year out and -10 two years
    out, C WTI cleared +2, D WTI bilateral +4 paying a year out, every bilateral source on FLAT."""
    return {
        "a": valued_on(hng((10.0,), (A_YEAR,), Route.CLEARED), HNG_HISTORY, HNG_MARKET, None),
        "b": valued_on(
            hng((10.0, -10.0), (A_YEAR, TWO_YEARS), Route.BILATERAL), HNG_HISTORY, HNG_MARKET, FLAT
        ),
        "c": valued_on(wti((2.0,), Route.CLEARED), WTI_HISTORY, WTI_MARKET, None),
        "d": valued_on(wti((4.0,), Route.BILATERAL), WTI_HISTORY, WTI_MARKET, FLAT),
    }


def collected(*results: TradeResults | CashflowResults) -> AggregateResults:
    return aggregate_results(list(results), WorkCounter())


def column(view: RiskView, label: str) -> tuple[float, Any]:
    """A report column by its label: the Total and the dated vector."""
    j = view.labels.index(label)
    return view.totals[j], view.columns[j]


def test_the_two_hng_sources_combine_by_index_and_by_curve(
    sources: dict[str, TradeResults],
) -> None:
    # A and B on one index object, one history and one price vector: one group, the nominal lots
    # 10 and the discounted 10.5 on F27 and on the one observation day; B alone on the curve: one
    # rate group, curve_1 USD, the two payment days with -0.0095 and 0.018 and the Total 0.0085.
    a, b = sources["a"], sources["b"]
    counter = WorkCounter()
    agg = aggregate_results([a, b], counter)
    assert (
        agg.as_of == A_DAY and agg.sources == (a, b) and agg.currency_units == (("USD", "DOLLAR"),)
    )
    (group,) = agg.index_groups
    assert group.index is HNG and group.reporting_lot.name == "LOT"
    assert group.history is HNG_HISTORY and group.price_vector is HNG_MARKET.price_vector
    np.testing.assert_array_equal(group.occurrences, [0, 1])
    np.testing.assert_array_equal(group.references, [1])
    np.testing.assert_allclose(group.nominal_delta, [10.0], **TIGHT)
    np.testing.assert_allclose(group.delta, [10.5], **TIGHT)
    assert group.nominal_delta_total == 10.0
    assert group.delta_total == pytest.approx(10.5, **CLOSE)
    np.testing.assert_array_equal(group.days, dates(AS_OF))
    np.testing.assert_allclose(group.daily_lots, [10.0], **TIGHT)
    np.testing.assert_allclose(group.discounted_daily_lots, [10.5], **TIGHT)
    np.testing.assert_array_equal(group.months, dates(JAN_27))
    np.testing.assert_array_equal(group.years, dates(JAN_27))
    np.testing.assert_allclose(group.monthly_lots, [10.0], **TIGHT)
    np.testing.assert_allclose(group.discounted_yearly_lots, [10.5], **TIGHT)
    (rate,) = agg.rate_groups
    assert rate.curve is FLAT and rate.word == "SOFR" and rate.currency == "USD"
    np.testing.assert_array_equal(rate.occurrences, [1])
    np.testing.assert_array_equal(rate.days, dates(A_YEAR, TWO_YEARS))
    np.testing.assert_allclose(rate.dv01_by_day, [-0.0095, 0.018], **TIGHT)
    np.testing.assert_array_equal(rate.months, dates(JAN_28, JAN_29))
    np.testing.assert_allclose(rate.dv01_by_month, [-0.0095, 0.018], **TIGHT)
    np.testing.assert_array_equal(rate.years, dates(JAN_28, JAN_29))
    assert rate.dv01 == pytest.approx(0.0085, **CLOSE)
    # The report axes: the observation day, the two payment days, and their union of three.
    np.testing.assert_array_equal(agg.by_day.observed, dates(AS_OF))
    np.testing.assert_array_equal(agg.by_day.paid, dates(A_YEAR, TWO_YEARS))
    np.testing.assert_array_equal(agg.by_day.union, dates(AS_OF, A_YEAR, TWO_YEARS))
    np.testing.assert_array_equal(agg.by_day.observed_in_union[0], [0])
    np.testing.assert_array_equal(agg.by_day.paid_in_union[0], [1, 2])
    # Since #186 the month axis is dense from the valuation month: January 2027 through January
    # 2029, the contract month its first row and the two payment months the 13th and the 25th.
    assert agg.by_month.union.size == 25 and agg.by_month.observed.size == 1
    np.testing.assert_array_equal(agg.by_month.union[[0, 12, 24]], dates(JAN_27, JAN_28, JAN_29))
    np.testing.assert_array_equal(agg.by_month.paid_in[0], [12, 24])
    assert agg.by_month.observed_from == (0,) and agg.by_month.paid_from == (0,)
    # Two occurrences, one group of each kind and since #197 two cross groups, A's cleared pair
    # and B's on the curve; the entries of every saved vector aligned once, eight over the
    # index's four axes, six over the curve's three and four over B's delta axes again for the
    # cross-gamma, the cleared pair aligning nothing; fifteen reductions; the three buckets'
    # axes, six coordinates each.
    assert counter.freeze().as_dict() == {
        "aggregate_reductions": 15,
        "contributions_collected": 2,
        "cross_groups": 2,
        "entries_aligned": 18,
        "index_groups": 1,
        "rate_groups": 1,
        "report_coordinates": 64,
        "sources_collected": 2,
    }


def test_the_four_sources_make_two_index_groups_and_one_rate_group(
    sources: dict[str, TradeResults],
) -> None:
    # The ticket's table, all by day: HNG's lots on 4 January, WTI's on the 5th, the one curve's
    # DV01 on the two payment days, the first payment HNG's -0.0095 and WTI's -0.0019 together;
    # the Totals the saved sums, 10 and 10.5, 6 and 5.8, 0.0066.
    counter = WorkCounter()
    agg = aggregate_results([sources[k] for k in "abcd"], counter)
    assert [g.index for g in agg.index_groups] == [HNG, WTI]
    assert [r.word for r in agg.rate_groups] == ["SOFR"]
    np.testing.assert_array_equal(agg.rate_groups[0].occurrences, [1, 3])
    view = aggregate_view(agg, Risk.ALL, Bucket.DAY)
    np.testing.assert_array_equal(view.dates, dates(AS_OF, "2027-01-05", A_YEAR, TWO_YEARS))
    # Since #197 the four cross groups after the rate group, one per pair in first appearance:
    # HNG cleared, nothing; HNG on curve_1, B's -0.00095 + 0.0018 on its observation day; WTI
    # cleared, nothing; WTI on curve_1, D's -0.00038 on the 5th.
    assert view.labels == (
        HNG_NOMINAL,
        HNG_DELTA,
        WTI_NOMINAL,
        WTI_DELTA,
        CURVE_1,
        HNG_CLEARED_CROSS,
        HNG_CROSS,
        WTI_CLEARED_CROSS,
        WTI_CROSS,
    )
    assert view.totals == (
        10.0,
        pytest.approx(10.5, **CLOSE),
        6.0,
        pytest.approx(5.8, **CLOSE),
        pytest.approx(0.0066, **CLOSE),
        0.0,
        pytest.approx(0.00085, **CLOSE),
        0.0,
        pytest.approx(-0.00038, **CLOSE),
    )
    expected = (
        [10.0, 0.0, 0.0, 0.0],
        [10.5, 0.0, 0.0, 0.0],
        [0.0, 6.0, 0.0, 0.0],
        [0.0, 5.8, 0.0, 0.0],
        [0.0, 0.0, -0.0114, 0.018],
        [0.0, 0.0, 0.0, 0.0],
        [0.00085, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0],
        [0.0, -0.00038, 0.0, 0.0],
    )
    for got, want in zip(view.columns, expected, strict=True):
        np.testing.assert_allclose(got, want, **TIGHT)
    # One risk at a time keeps its own axis: the deltas the two observation days, the DV01 the
    # two payment days; by month the two observation days are one January and the payments two
    # more, by year the same three.
    nominal = aggregate_view(agg, Risk.NOMINAL_DELTA, Bucket.DAY)
    np.testing.assert_array_equal(nominal.dates, dates(AS_OF, "2027-01-05"))
    assert nominal.labels == (HNG_NOMINAL, WTI_NOMINAL) and nominal.totals == (10.0, 6.0)
    np.testing.assert_allclose(nominal.columns[0], [10.0, 0.0], **TIGHT)
    np.testing.assert_allclose(nominal.columns[1], [0.0, 6.0], **TIGHT)
    delta = aggregate_view(agg, Risk.DELTA, Bucket.MONTH)
    np.testing.assert_array_equal(delta.dates, dates(JAN_27))
    np.testing.assert_allclose(delta.columns[0], [10.5], **TIGHT)
    np.testing.assert_allclose(delta.columns[1], [5.8], **TIGHT)
    dv01 = aggregate_view(agg, Risk.DV01, Bucket.DAY)
    np.testing.assert_array_equal(dv01.dates, dates(A_YEAR, TWO_YEARS))
    assert dv01.labels == (CURVE_1,) and dv01.totals == (pytest.approx(0.0066, **CLOSE),)
    np.testing.assert_allclose(dv01.columns[0], [-0.0114, 0.018], **TIGHT)
    by_year = aggregate_view(agg, Risk.ALL, Bucket.YEAR)
    np.testing.assert_array_equal(by_year.dates, dates(JAN_27, JAN_28, JAN_29))
    np.testing.assert_allclose(by_year.columns[1], [10.5, 0.0, 0.0], **TIGHT)
    np.testing.assert_allclose(by_year.columns[4], [0.0, -0.0114, 0.018], **TIGHT)
    assert counter.freeze().as_dict() == {
        "aggregate_reductions": 27,  # eight more since #197, B's and D's cross-gamma on four axes
        "contributions_collected": 4,
        "cross_groups": 4,
        "entries_aligned": 33,  # eight more, the two bilateral sources' delta axes again
        "index_groups": 2,
        "rate_groups": 1,
        "report_coordinates": 66,
        "sources_collected": 4,
    }


def test_one_source_collects_as_itself_through_the_same_path(
    sources: dict[str, TradeResults],
) -> None:
    # B alone: every selection and bucket of the collection reads as B's own report, the labels,
    # the dates, the Totals and the vectors, the aggregate record and not the source handed back.
    b = sources["b"]
    single = collected(b)
    assert single.sources == (b,) and len(single.index_groups) == 1
    for risk in Risk:
        for bucket in Bucket:
            own = risk_view(b, risk, bucket)
            view = aggregate_view(single, risk, bucket)
            assert view.labels == own.labels, (risk, bucket)
            assert view.totals == own.totals, (risk, bucket)
            np.testing.assert_array_equal(view.dates, own.dates)
            for got, want in zip(view.columns, own.columns, strict=True):
                np.testing.assert_array_equal(got, want)


def test_every_occurrence_counts_and_the_groups_follow_first_appearance(
    sources: dict[str, TradeResults],
) -> None:
    # A twice: 20 nominal lots and 20.5 discounted, the DV01 B's alone; the four reordered: WTI's
    # group and columns first, every number the same under its label.
    a, b, c, d = (sources[k] for k in "abcd")
    thrice = collected(a, b, a)
    (group,) = thrice.index_groups
    np.testing.assert_array_equal(group.occurrences, [0, 1, 2])
    assert group.nominal_delta_total == 20.0
    assert group.delta_total == pytest.approx(20.5, **CLOSE)
    np.testing.assert_allclose(group.daily_lots, [20.0], **TIGHT)
    assert thrice.rate_groups[0].dv01 == pytest.approx(0.0085, **CLOSE)
    np.testing.assert_array_equal(thrice.rate_groups[0].occurrences, [1])
    base = aggregate_view(collected(a, b, c, d), Risk.ALL, Bucket.DAY)
    reordered = aggregate_view(collected(c, d, a, b), Risk.ALL, Bucket.DAY)
    assert reordered.labels == (
        WTI_NOMINAL,
        WTI_DELTA,
        HNG_NOMINAL,
        HNG_DELTA,
        CURVE_1,
        WTI_CLEARED_CROSS,
        WTI_CROSS,
        HNG_CLEARED_CROSS,
        HNG_CROSS,
    )
    np.testing.assert_array_equal(reordered.dates, base.dates)
    for label in base.labels:
        total, values = column(base, label)
        other_total, other_values = column(reordered, label)
        assert other_total == total, label
        np.testing.assert_array_equal(other_values, values)


def test_a_quote_or_a_curve_moved_and_reevaluated_flows_through(
    sources: dict[str, TradeResults],
) -> None:
    # HNG quoted 81, A and B valued again on the new vector: the lots stand and the payment days'
    # DV01s move to -0.01235 and 0.0198, the Total 0.00745. The curve 0.96 and 0.92, B and D
    # valued again: HNG's delta 10.4, WTI's 5.84, the DV01s -0.01152 and 0.0184, the Total 0.00688.
    c, d = sources["c"], sources["d"]
    hot = quoted(HNG_HISTORY, 81.0, 50.0)
    a_hot = valued_on(hng((10.0,), (A_YEAR,), Route.CLEARED), HNG_HISTORY, hot, None)
    b_hot = valued_on(
        hng((10.0, -10.0), (A_YEAR, TWO_YEARS), Route.BILATERAL), HNG_HISTORY, hot, FLAT
    )
    view = aggregate_view(collected(a_hot, b_hot, c, d), Risk.ALL, Bucket.DAY)
    assert column(view, HNG_NOMINAL)[0] == 10.0
    assert column(view, HNG_DELTA)[0] == pytest.approx(10.5, **CLOSE)
    total, dv01 = column(view, CURVE_1)
    assert total == pytest.approx(0.00745, **CLOSE)
    np.testing.assert_allclose(dv01, [0.0, 0.0, -0.01235, 0.0198], **TIGHT)
    other = curve_of((AS_OF, 1.0), (A_YEAR, 0.96), (TWO_YEARS, 0.92))
    b_other = valued_on(
        hng((10.0, -10.0), (A_YEAR, TWO_YEARS), Route.BILATERAL), HNG_HISTORY, HNG_MARKET, other
    )
    d_other = valued_on(wti((4.0,), Route.BILATERAL), WTI_HISTORY, WTI_MARKET, other)
    view = aggregate_view(collected(sources["a"], b_other, c, d_other), Risk.ALL, Bucket.DAY)
    assert column(view, HNG_DELTA)[0] == pytest.approx(10.4, **CLOSE)
    assert column(view, WTI_DELTA)[0] == pytest.approx(5.84, **CLOSE)
    total, dv01 = column(view, CURVE_1)
    assert total == pytest.approx(0.00688, **CLOSE)
    np.testing.assert_allclose(dv01, [0.0, 0.0, -0.01152, 0.0184], **TIGHT)


def test_the_collection_refuses_what_does_not_belong_in_the_order_given(
    sources: dict[str, TradeResults],
) -> None:
    # Nothing given; another valuation day; a distinct index of the same name; the same index
    # over another history object, equal in every value; the same history quoted off another
    # price-vector object, equal in every value; and, in the order given, the earlier occurrence's
    # conflict named first. Another Market wrapper over the same two objects combines.
    a = sources["a"]
    with pytest.raises(
        ValueError, match=r"^results are none, expected at least one evaluated batch$"
    ):
        aggregate_results([], WorkCounter())
    later = history_on(HNG, "2027-01-05", {"F27": 82.0})
    on_later = valued_on(
        hng((10.0, -10.0), (A_YEAR, TWO_YEARS), Route.BILATERAL),
        later,
        quoted(later, 50.0),
        curve_of(("2027-01-05", 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90)),
    )
    with pytest.raises(ValueError) as refused:
        collected(a, on_later)
    assert str(refused.value) == (
        "results 2 is valued on 2027-01-05, expected 2027-01-04, the valuation day of results 1"
    )
    twin = an_index(
        "HNG", MONTHS, ("2027-12-27",), ("DOLLAR", "BBL"), ("VOLUME", "BBL"), ("LOT", 1.0, "BBL")
    )
    twin_history = history_on(twin, AS_OF, {})
    on_twin = valued_on(
        terms_of((10.0,), (A_YEAR,), (261,), route=Route.CLEARED, ix=twin),
        twin_history,
        quoted(twin_history, 80.0, 50.0),
        None,
    )
    with pytest.raises(ValueError) as refused:
        collected(a, on_twin)
    assert str(refused.value) == (
        "results 2 is on another index named 'HNG' than results 1, expected one index for one name"
    )
    equal_history = history_on(HNG, AS_OF, {})
    on_equal_history = valued_on(
        hng((10.0,), (A_YEAR,), Route.CLEARED),
        equal_history,
        quoted(equal_history, 80.0, 50.0),
        None,
    )
    with pytest.raises(ValueError) as refused:
        collected(a, on_equal_history)
    assert str(refused.value) == (
        "results 2 is on index 'HNG' over another history than results 1, expected one history "
        "for one index"
    )
    on_equal_vector = valued_on(
        hng((10.0,), (A_YEAR,), Route.CLEARED), HNG_HISTORY, quoted(HNG_HISTORY, 80.0, 50.0), None
    )
    with pytest.raises(ValueError) as refused:
        collected(a, on_equal_vector)
    assert str(refused.value) == (
        "results 2 is on index 'HNG' quoted off another price vector than results 1, expected one "
        "price vector for one index"
    )
    with pytest.raises(ValueError, match=r"^results 2 is on index 'HNG' over another history"):
        collected(a, on_equal_history, on_later)
    wrapper = market(HNG_HISTORY, HNG_MARKET.price_vector)
    on_wrapper = valued_on(hng((10.0,), (A_YEAR,), Route.CLEARED), HNG_HISTORY, wrapper, None)
    agg = collected(a, on_wrapper)
    assert agg.index_groups[0].nominal_delta_total == 20.0
    np.testing.assert_array_equal(agg.index_groups[0].occurrences, [0, 1])


def test_curves_group_by_object_and_currency_unit_and_are_named_by_first_appearance(
    sources: dict[str, TradeResults],
) -> None:
    # B on FLAT and B again on a curve equal in every value but another object, both named SOFR:
    # one index group and two rate groups, SOFR (curve_1) and SOFR (curve_2), both qualified, each
    # with B's DV01; then one curve valuing an index settled in cents: the same SOFR in two
    # currencies, two groups under one bare word, the cents a hundredfold.
    b = sources["b"]
    equal_values = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90))
    b_equal = valued_on(
        hng((10.0, -10.0), (A_YEAR, TWO_YEARS), Route.BILATERAL),
        HNG_HISTORY,
        HNG_MARKET,
        equal_values,
    )
    agg = collected(b, b_equal)
    assert len(agg.index_groups) == 1
    assert [(r.curve, r.word, r.currency) for r in agg.rate_groups] == [
        (FLAT, "SOFR (curve_1)", "USD"),
        (equal_values, "SOFR (curve_2)", "USD"),
    ]
    view = aggregate_view(agg, Risk.DV01, Bucket.DAY)
    assert view.labels == (
        "SOFR (curve_1) USD dv01 [DOLLAR per basis point]",
        "SOFR (curve_2) USD dv01 [DOLLAR per basis point]",
    )
    assert view.totals == (pytest.approx(0.0085, **CLOSE), pytest.approx(0.0085, **CLOSE))
    np.testing.assert_allclose(view.columns[1], [-0.0095, 0.018], **TIGHT)
    assert len(aggregate_view(agg, Risk.ALL, Bucket.DAY).labels) == 6  # two cross groups too
    cents = index(
        "HNGC",
        "HNG settled in cents",
        futures_schedule(
            ("Z26", "F27", "F29"), dates("2026-12-31", "2027-01-04", "2029-01-05"), None
        ),
        index_conventions("DOLLAR", "BBL", "CENT", "VOLUME", "BBL", UNITS),
        contract_specifications(
            ("LOT",), numbers(1.0), ("BBL",), numbers(0.0), numbers(0.0), UNITS
        ),
        holiday_calendar(dates("2027-12-27")),
        "LOT",
        UNITS,
    )
    cents_history = history_on(cents, AS_OF, {})
    in_cents = valued_on(
        terms_of((10.0, -10.0), (A_YEAR, TWO_YEARS), (261, 522), ix=cents),
        cents_history,
        quoted(cents_history, 80.0, 50.0),
        FLAT,
    )
    # Two facts since currency-and-currency-unit.md: the currency is USD whatever the index
    # settles in, and the unit of it says cents. The group is its own, as it was, the two
    # columns told apart by the unit in the brackets and never added.
    assert (in_cents.currency, in_cents.currency_unit) == ("USD", "CENT")
    assert in_cents.dv01 == pytest.approx(0.85, **CLOSE)
    assert [(c.currency, c.currency_unit) for c in in_cents.rate_contributions] == [("USD", "CENT")]
    assert (in_cents.reserves.currency, in_cents.reserves.currency_unit) == ("USD", "CENT")
    agg = collected(b, in_cents)
    assert [(r.word, r.currency, r.currency_unit) for r in agg.rate_groups] == [
        ("SOFR", "USD", "DOLLAR"),
        ("SOFR", "USD", "CENT"),
    ]
    assert agg.currency_units == (("USD", "DOLLAR"), ("USD", "CENT"))
    view = aggregate_view(agg, Risk.DV01, Bucket.YEAR)
    assert view.labels == (CURVE_1, "SOFR USD dv01 [CENT per basis point]")
    np.testing.assert_allclose(view.columns[1], [0.0, -0.95, 1.8], **TIGHT)  # 2027 to 2029
    assert view.totals[1] == pytest.approx(0.85, **CLOSE)


def test_a_collection_with_no_curve_reports_a_dv01_of_nothing_per_currency(
    sources: dict[str, TradeResults],
) -> None:
    # A and C, both cleared: no rate group; the DV01 report one column of nothing for USD over no
    # day, and all three on the two observation days with that column zero on both.
    agg = collected(sources["a"], sources["c"])
    assert agg.rate_groups == () and agg.currency_units == (("USD", "DOLLAR"),)
    assert agg.by_day.paid.size == 0 and agg.by_day.paid_in == ()
    dv01 = aggregate_view(agg, Risk.DV01, Bucket.DAY)
    assert dv01.dates.size == 0 and dv01.labels == (CLEARED_USD,) and dv01.totals == (0.0,)
    assert dv01.columns[0].size == 0
    everything = aggregate_view(agg, Risk.ALL, Bucket.DAY)
    np.testing.assert_array_equal(everything.dates, dates(AS_OF, "2027-01-05"))
    assert everything.labels == (
        HNG_NOMINAL,
        HNG_DELTA,
        WTI_NOMINAL,
        WTI_DELTA,
        CLEARED_USD,
        HNG_CLEARED_CROSS,
        WTI_CLEARED_CROSS,
    )
    assert everything.totals[4] == 0.0
    np.testing.assert_array_equal(everything.columns[4], [0.0, 0.0])
    np.testing.assert_allclose(everything.columns[3], [0.0, 2.0], **TIGHT)


def test_a_fully_paid_source_keeps_its_payment_axis_and_its_rate_group() -> None:
    # B valued on 4 January 2029 with F27 fixed at 82 and both payments made, on a curve of its
    # day alone: a rate group of nothing, its two payment days kept with zeros on them.
    paid_history = history_on(HNG, "2029-01-04", {"F27": 82.0})
    paid = valued_on(
        hng((10.0, -10.0), (A_YEAR, TWO_YEARS), Route.BILATERAL),
        paid_history,
        quoted(paid_history, 50.0),
        curve_of(("2029-01-04", 1.0)),
    )
    assert paid.dv01 == 0.0 and paid.cash == pytest.approx(0.0, abs=1e-9)
    agg = collected(paid)
    (rate,) = agg.rate_groups
    assert rate.dv01 == 0.0 and rate.word == "SOFR"
    np.testing.assert_array_equal(rate.days, dates(A_YEAR, TWO_YEARS))
    np.testing.assert_array_equal(rate.dv01_by_day, [0.0, 0.0])
    view = aggregate_view(agg, Risk.ALL, Bucket.DAY)
    np.testing.assert_array_equal(view.dates, dates(AS_OF, A_YEAR, TWO_YEARS))
    np.testing.assert_array_equal(view.columns[0], [0.0, 0.0, 0.0])  # fixed: no lots


def test_the_collection_owns_its_membership_and_writes_nothing(
    sources: dict[str, TradeResults],
) -> None:
    # The input list appended to after collecting changes nothing; every source array is as it
    # was; every new array is frozen; a new valuation of the same batch leaves an old collection's
    # numbers as they were.
    a, b = sources["a"], sources["b"]
    kept = {
        "nominal_delta": a.legs[0].nominal_delta.copy(),
        "daily": b.legs[0].discounted_daily_lots.copy(),
        "dv01": rate(b).dv01_by_day.copy(),
        "days": b.prepared.encoded.legs[0].days.copy(),
    }
    inputs = [a, b]
    agg = aggregate_results(inputs, WorkCounter())
    inputs.append(sources["c"])
    assert agg.sources == (a, b)
    np.testing.assert_array_equal(a.legs[0].nominal_delta, kept["nominal_delta"])
    np.testing.assert_array_equal(b.legs[0].discounted_daily_lots, kept["daily"])
    np.testing.assert_array_equal(rate(b).dv01_by_day, kept["dv01"])
    np.testing.assert_array_equal(b.prepared.encoded.legs[0].days, kept["days"])
    scalars = {
        "index", "reporting_lot", "history", "price_vector", "nominal_delta_total",
        "delta_total", "curve", "word", "currency", "currency_unit", "dv01",
        "cross_gamma_total",
    }  # fmt: skip
    frozen: list[Any] = []
    for group in (*agg.index_groups, *agg.rate_groups, *agg.cross_groups):
        frozen.extend(getattr(group, f.name) for f in fields(group) if f.name not in scalars)
    for axes in (agg.by_day, agg.by_month, agg.by_year):
        frozen.extend((axes.observed, axes.paid, axes.union))
        for places in (axes.observed_in, axes.paid_in, axes.observed_in_union, axes.paid_in_union):
            frozen.extend(places)
    assert len(frozen) >= 40 and all(not array.flags.writeable for array in frozen)
    before = agg.index_groups[0].daily_lots
    valued_on(
        hng((10.0,), (A_YEAR,), Route.CLEARED), HNG_HISTORY, quoted(HNG_HISTORY, 99.0, 50.0), None
    )
    assert agg.index_groups[0].daily_lots is before
    np.testing.assert_allclose(before, [10.0], **TIGHT)


def test_sums_past_the_largest_number_are_refused_by_their_coordinate() -> None:
    # Four cleared HNG sources of 1e308 lots each, bought on F27 and sold on F29 at their quotes so
    # that every source values to nothing: the lots cancel in all but the F27 contract's sum is
    # past the largest number, refused by the contract; two bought, F27 and F29, are finite by
    # contract and by day and past the largest number in all.
    # Quoted and fixed at 1, so that a lot's offset is a lot and nothing multiplies past the
    # largest number before the collector sums; F29 observes on 5 January 2029 and pays after it.
    big = 1e308
    at_one = quoted(HNG_HISTORY, 1.0, 1.0)
    up = valued_on(hng((big,), (A_YEAR,), Route.CLEARED, fixed=1.0), HNG_HISTORY, at_one, None)
    down = valued_on(
        terms_of(
            (-big,), ("2029-01-10",), (3,), route=Route.CLEARED, contracts=(2,), fixed=1.0, ix=HNG
        ),
        HNG_HISTORY,
        at_one,
        None,
    )
    up_too = valued_on(
        terms_of(
            (big,), ("2029-01-10",), (3,), route=Route.CLEARED, contracts=(2,), fixed=1.0, ix=HNG
        ),
        HNG_HISTORY,
        at_one,
        None,
    )
    assert (
        up.legs[0].nominal_delta_total == big
        and up.mark == 0.0
        and down.legs[0].nominal_delta_total == -big
    )
    with pytest.raises(ValueError) as refused:
        collected(up, down, up, down)
    assert str(refused.value) == (
        "the nominal delta of index 'HNG' for contract F27 is inf, expected a finite number of "
        "lots; the results' lots sum past the largest number"
    )
    with pytest.raises(ValueError) as refused:
        collected(up, up_too)
    assert str(refused.value) == (
        "the nominal delta of index 'HNG' in all is inf, expected a finite number of lots; the "
        "results' lots sum past the largest number"
    )


def test_cancelling_sources_keep_the_lot_in_every_vector_whatever_their_order() -> None:
    # The review's cases, on HNG at a quote equal to the fixed price so that nothing values past
    # the largest number: ten thousand trillion lots bought, one lot bought and ten thousand
    # trillion sold are one lot in all and one lot on the contract, the day, the month and the
    # year, in whichever order the three come; the vectors say what the Total says. On the
    # three-barrel lot, a million barrels, a barrel and a million sold are a third of a lot the
    # same way, within the kernel's tolerance.
    def hng_at_eighty(lots: float) -> TradeResults:
        return valued_on(
            hng((lots,), (A_YEAR,), Route.CLEARED, fixed=80.0), HNG_HISTORY, HNG_MARKET, None
        )

    bought, one, sold = hng_at_eighty(1e16), hng_at_eighty(1.0), hng_at_eighty(-1e16)
    assert bought.mark == 0.0 and bought.legs[0].nominal_delta_total == 1e16
    for order in (
        (bought, one, sold),
        (bought, sold, one),
        (one, bought, sold),
        (sold, one, bought),
    ):
        (group,) = collected(*order).index_groups
        assert group.nominal_delta_total == 1.0 and group.delta_total == 1.0
        for vector in (
            group.nominal_delta,
            group.delta,
            group.daily_lots,
            group.discounted_daily_lots,
            group.monthly_lots,
            group.yearly_lots,
        ):
            np.testing.assert_array_equal(vector, [1.0])
    trio_history = history_on(TRIO, AS_OF, {})
    trio_market = quoted(trio_history, 80.0, 50.0)

    def trio_at_eighty(barrels: float) -> TradeResults:
        terms = terms_of((barrels,), (A_YEAR,), (261,), route=Route.CLEARED, fixed=80.0, ix=TRIO)
        return valued_on(terms, trio_history, trio_market, None)

    million, barrel, sold_million = trio_at_eighty(1e6), trio_at_eighty(1.0), trio_at_eighty(-1e6)
    assert barrel.legs[0].nominal_delta_total == pytest.approx(1 / 3, **CLOSE)
    for order in ((million, barrel, sold_million), (million, sold_million, barrel)):
        (group,) = collected(*order).index_groups
        assert group.nominal_delta_total == pytest.approx(1 / 3, **CLOSE)
        np.testing.assert_allclose(group.nominal_delta, [1 / 3], **TIGHT)
        np.testing.assert_allclose(group.daily_lots, [1 / 3], **TIGHT)
        np.testing.assert_allclose(group.yearly_lots, [1 / 3], **TIGHT)
        assert float(group.daily_lots.sum()) == pytest.approx(group.nominal_delta_total, **CLOSE)


def test_every_view_sums_to_the_total_above_it(sources: dict[str, TradeResults]) -> None:
    # The saved Totals are the scalars summed and the vectors the saved entries summed; each column
    # of each selection and bucket adds up to its Total within the kernel's tolerance.
    agg = collected(*(sources[k] for k in "abcd"))
    for risk in Risk:
        for bucket in Bucket:
            view = aggregate_view(agg, risk, bucket)
            for total, values in zip(view.totals, view.columns, strict=True):
                assert float(values.sum()) == pytest.approx(total, **CLOSE), (risk, bucket)


def test_the_headings_are_spelled_once_for_both_paths(sources: dict[str, TradeResults]) -> None:
    """risk_report.py's two helpers are the one spelling of every column heading: the single
    result's view and the collection's carry what they return and nothing else."""
    results = tuple(sources.values())
    terms = results[0].prepared.encoded.terms
    assert delta_labels(terms.legs[0].index, terms.legs[0].reporting_lot) == (
        HNG_NOMINAL,
        HNG_DELTA,
    )
    assert dv01_label("SOFR", "USD", "DOLLAR") == CURVE_1
    assert dv01_label("cleared", "USD", "DOLLAR") == CLEARED_USD
    # The currency, then in the brackets the unit of it, currency-and-currency-unit.md.
    assert dv01_label("SOFR", "USD", "CENT") == "SOFR USD dv01 [CENT per basis point]"
    for result in results:
        terms = result.prepared.encoded.terms
        group = result.curves[0].name if result.curves else "cleared"
        for bucket in Bucket:
            view = risk_view(result, Risk.ALL, bucket)
            assert view.labels == (
                *delta_labels(terms.legs[0].index, terms.legs[0].reporting_lot),
                dv01_label(group, result.currency, result.currency_unit),
                cross_gamma_label(terms.legs[0].index, group, terms.legs[0].reporting_lot),
            )
    agg = collected(*results)
    view = aggregate_view(agg, Risk.ALL, Bucket.DAY)
    pairs = [label for g in agg.index_groups for label in delta_labels(g.index, g.reporting_lot)]
    assert list(view.labels[: len(pairs)]) == pairs
    rate_labels = {dv01_label(r.word, r.currency, r.currency_unit) for r in agg.rate_groups}
    rate_labels |= {dv01_label("cleared", c, u) for c, u in agg.currency_units}
    cross_labels = {
        cross_gamma_label(c.index, "cleared" if c.word is None else c.word, c.reporting_lot)
        for c in agg.cross_groups
    }
    assert set(view.labels[len(pairs) :]) <= rate_labels | cross_labels
    assert len(view.labels) == len(pairs) + (len(agg.rate_groups) or len(agg.currency_units)) + len(
        cross_labels
    )


# --- several contributions from one result, the shape slice 3 fills -------------------------------


def on_two_curves(
    sources: dict[str, TradeResults], second: DiscountCurve
) -> tuple[TradeResults, TradeResults, TradeResults]:
    """B's two rows as two single-row batches, +10 paying a year out on FLAT and -10 paying two
    years out on the second curve, and B remade as one result valued on both: its discounted
    risk the two rows' summed, its batch scalars the sums and both pairs of contributions kept,
    as a result valued on two curves will be kept in slice 3; nothing is valued again. The two
    rows share B's one contract and observation day, so the summed vectors align entry for
    entry."""
    first = valued_on(hng((10.0,), (A_YEAR,), Route.BILATERAL), HNG_HISTORY, HNG_MARKET, FLAT)
    second_row = valued_on(
        hng((-10.0,), (TWO_YEARS,), Route.BILATERAL, key=second.name),
        HNG_HISTORY,
        HNG_MARKET,
        second,
    )
    axes = sources["b"].prepared.encoded.payment_axes
    assert axes is not None

    def on_the_batch_axes(c: RateContribution) -> RateContribution:
        # A row's contribution stands on its own batch's payment days; the two-curve result
        # keeps each on the whole batch's, as the evaluation will sum them in slice 3.
        return RateContribution(
            c.curve,
            c.currency,
            c.currency_unit,
            c.dv01,
            axes.days,
            placed(axes.days.size, np.searchsorted(axes.days, c.days), c.dv01_by_day),
            axes.months,
            placed(axes.months.size, np.searchsorted(axes.months, c.months), c.dv01_by_month),
            axes.years,
            placed(axes.years.size, np.searchsorted(axes.years, c.years), c.dv01_by_year),
            c.early_dv01,
        )

    a, b = first.legs[0], second_row.legs[0]
    leg = replace(
        sources["b"].legs[0],
        delta=a.delta + b.delta,
        delta_total=a.delta_total + b.delta_total,
        discounted_price_sensitivity=(
            a.discounted_price_sensitivity + b.discounted_price_sensitivity
        ),
        discounted_daily_lots=a.discounted_daily_lots + b.discounted_daily_lots,
        discounted_monthly_lots=a.discounted_monthly_lots + b.discounted_monthly_lots,
        discounted_yearly_lots=a.discounted_yearly_lots + b.discounted_yearly_lots,
        cross_gamma_total=a.cross_gamma_total + b.cross_gamma_total,
        cross_contributions=(cross(first), cross(second_row)),
    )
    mixed = replace(
        sources["b"],
        legs=(leg,),
        mark=first.mark + second_row.mark,
        dv01=first.dv01 + second_row.dv01,
        rate_contributions=(on_the_batch_axes(rate(first)), on_the_batch_axes(rate(second_row))),
    )
    return first, second_row, mixed


def same_view(one: RiskView, other: RiskView) -> None:
    """Two views alike column for column: the labels, the dates, the Totals and every vector."""
    assert one.labels == other.labels
    np.testing.assert_array_equal(one.dates, other.dates)
    assert len(one.totals) == len(other.totals) == len(one.columns) == len(other.columns)
    for a, b in zip(one.totals, other.totals, strict=True):
        assert a == pytest.approx(b, **CLOSE)
    for a, b in zip(one.columns, other.columns, strict=True):
        np.testing.assert_allclose(a, b, **TIGHT)


def test_a_result_on_two_curves_collected_alone_reports_what_its_single_curve_results_do_together(
    sources: dict[str, TradeResults],
) -> None:
    other = curve_of((AS_OF, 1.0), (A_YEAR, 0.96), (TWO_YEARS, 0.92), name="FFOIS")
    first, second_row, mixed = on_two_curves(sources, other)
    alone, apart = collected(mixed), collected(first, second_row)
    assert [r.word for r in alone.rate_groups] == ["SOFR", "FFOIS"]
    assert [r.word for r in apart.rate_groups] == ["SOFR", "FFOIS"]
    assert [c.word for c in alone.cross_groups] == ["SOFR", "FFOIS"]
    assert len(alone.index_groups) == 1
    # One source contributing twice: a position once per group; apart, the second source's.
    np.testing.assert_array_equal(alone.rate_groups[1].occurrences, [0])
    np.testing.assert_array_equal(apart.rate_groups[1].occurrences, [1])
    for risk in Risk:
        for bucket in Bucket:
            same_view(aggregate_view(alone, risk, bucket), aggregate_view(apart, risk, bucket))
    # The result's own view agrees with the collection of it, and each curve keeps its own
    # DV01, never netted with the other's.
    for bucket in Bucket:
        same_view(risk_view(mixed, Risk.ALL, bucket), aggregate_view(alone, Risk.ALL, bucket))
    view = aggregate_view(alone, Risk.DV01, Bucket.DAY)
    assert column(view, CURVE_1)[0] == pytest.approx(-0.0095, **CLOSE)  # the first row's
    ffois = column(view, "FFOIS USD dv01 [DOLLAR per basis point]")
    assert ffois[0] == pytest.approx(0.0184, **CLOSE)  # -10 at 0.92 two years out
    assert first.dv01 == pytest.approx(-0.0095, **CLOSE)
    assert second_row.dv01 == pytest.approx(0.0184, **CLOSE)


def test_a_result_on_two_snapshots_of_one_name_qualifies_both_in_every_heading(
    sources: dict[str, TradeResults],
) -> None:
    again = curve_of((AS_OF, 1.0), (A_YEAR, 0.96), (TWO_YEARS, 0.92))  # named SOFR too
    first, second_row, mixed = on_two_curves(sources, again)
    alone, apart = collected(mixed), collected(first, second_row)
    for agg in (alone, apart):
        assert [r.word for r in agg.rate_groups] == ["SOFR (curve_1)", "SOFR (curve_2)"]
    view = aggregate_view(alone, Risk.ALL, Bucket.YEAR)
    assert view.labels[2:] == (
        "SOFR (curve_1) USD dv01 [DOLLAR per basis point]",
        "SOFR (curve_2) USD dv01 [DOLLAR per basis point]",
        "HNG SOFR (curve_1) cross_gamma [LOT per basis point]",
        "HNG SOFR (curve_2) cross_gamma [LOT per basis point]",
    )
    same_view(view, aggregate_view(apart, Risk.ALL, Bucket.YEAR))
    # On its own the result names its two curves the same way, two objects of one name.
    assert risk_view(mixed, Risk.DV01, Bucket.DAY).labels == view.labels[2:4]


# --- a batch of cashflows as a source -------------------------------------------------------------


def test_a_cashflow_source_joins_its_curves_rate_group_and_moves_nothing_else(
    sources: dict[str, TradeResults],
) -> None:
    # The cashflow ticket's batch, 0.85 of DV01, -0.95 a year out and +1.80 two years out, valued
    # on b's curve: one rate group of both, b's lots and cross-gamma untouched.
    b = sources["b"]
    cashflow = cashflows_valued(booked(), curve=FLAT)
    counter = WorkCounter()
    agg = aggregate_results([b, cashflow], counter)
    counts = counter.freeze().as_dict()
    assert counts["sources_collected"] == 2 and counts["contributions_collected"] == 3
    assert (counts["index_groups"], counts["rate_groups"], counts["cross_groups"]) == (1, 1, 1)
    (rate_group,) = agg.rate_groups
    assert rate_group.curve is FLAT and rate_group.word == "SOFR"
    np.testing.assert_array_equal(rate_group.occurrences, [0, 1])
    assert rate_group.dv01 == pytest.approx(0.0085 + 0.85, **CLOSE)
    np.testing.assert_array_equal(rate_group.days, dates(DAY_BEFORE, A_YEAR, TWO_YEARS))
    np.testing.assert_allclose(rate_group.dv01_by_day, [0.0, -0.0095 - 0.95, 0.018 + 1.8], **TIGHT)
    np.testing.assert_array_equal(agg.index_groups[0].occurrences, [0])
    np.testing.assert_array_equal(agg.cross_groups[0].occurrences, [0])
    assert agg.sources == (b, cashflow)
    alone = collected(b)
    for bucket in Bucket:
        for risk in (Risk.NOMINAL_DELTA, Risk.DELTA, Risk.CROSS_GAMMA):
            same_view(aggregate_view(agg, risk, bucket), aggregate_view(alone, risk, bucket))
    view = aggregate_view(agg, Risk.ALL, Bucket.YEAR)
    assert view.labels == (HNG_NOMINAL, HNG_DELTA, CURVE_1, HNG_CROSS)
    np.testing.assert_array_equal(view.dates, dates("2027-01-01", "2028-01-01", "2029-01-01"))
    total, dv01 = column(view, CURVE_1)
    assert total == pytest.approx(0.8585, **CLOSE)
    np.testing.assert_allclose(dv01, [0.0, -0.9595, 1.818], **TIGHT)
    assert column(view, HNG_CROSS)[0] == pytest.approx(0.00085, **CLOSE)
    assert column(view, HNG_DELTA)[0] == pytest.approx(0.5, **CLOSE)


def test_a_cashflow_on_another_curve_is_a_column_of_its_own(
    sources: dict[str, TradeResults],
) -> None:
    b = sources["b"]
    ffois = curve_of((AS_OF, 1.0), (A_YEAR, 0.96), (TWO_YEARS, 0.92), name="FFOIS")
    agg = collected(b, cashflows_valued(booked_on(ffois), curve=ffois))
    assert [r.word for r in agg.rate_groups] == ["SOFR", "FFOIS"]
    view = aggregate_view(agg, Risk.DV01, Bucket.YEAR)
    assert view.labels == (CURVE_1, "FFOIS USD dv01 [DOLLAR per basis point]")
    total, by_year = column(view, "FFOIS USD dv01 [DOLLAR per basis point]")
    assert total == pytest.approx(0.88, **CLOSE)
    np.testing.assert_allclose(by_year, [0.0, -0.96, 1.84], **TIGHT)
    unmoved = aggregate_view(collected(b), Risk.DV01, Bucket.YEAR)
    assert column(view, CURVE_1)[0] == pytest.approx(column(unmoved, CURVE_1)[0], **CLOSE)
    np.testing.assert_allclose(column(view, CURVE_1)[1], column(unmoved, CURVE_1)[1], **TIGHT)


def test_a_collection_of_cashflows_alone_reports_the_dv01_and_refuses_the_commodity_selectors() -> (
    None
):
    cashflow = cashflows_valued(booked(), curve=FLAT)
    agg = collected(cashflow)
    assert agg.index_groups == () and agg.cross_groups == () and len(agg.rate_groups) == 1
    assert agg.currency_units == (("USD", "DOLLAR"),)
    for bucket in Bucket:
        same_view(aggregate_view(agg, Risk.DV01, bucket), cashflow.report(Risk.DV01, bucket))
        same_view(aggregate_view(agg, Risk.ALL, bucket), cashflow.report(Risk.ALL, bucket))
        for risk in (Risk.NOMINAL_DELTA, Risk.DELTA, Risk.CROSS_GAMMA):
            with pytest.raises(ValueError) as caught:
                aggregate_view(agg, risk, bucket)
            assert str(caught.value) == (
                f"risk is {risk.value!r}, expected dv01 or all for a collection of cashflows "
                "alone, which has no commodity risk"
            )
    twice = aggregate_view(collected(cashflow, cashflow), Risk.DV01, Bucket.DAY)
    assert twice.totals == (pytest.approx(1.7, **CLOSE),)
    np.testing.assert_allclose(twice.columns[0], [0.0, -1.9, 3.6], **TIGHT)


def test_a_cashflow_source_is_held_to_the_valuation_day() -> None:
    later_curve = curve_of(("2027-01-05", 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90))
    later = cashflows_valued(booked(), as_of="2027-01-05", curve=later_curve)
    with pytest.raises(ValueError) as caught:
        collected(cashflows_valued(booked(), curve=FLAT), later)
    assert str(caught.value) == (
        "results 2 is valued on 2027-01-05, expected 2027-01-04, the valuation day of results 1"
    )
