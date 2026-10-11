"""The collection of saved risk across evaluated batches, aggregate-risk-kernel.md: one or many
results combined by the index object and by the curve object and currency, the saved vectors
summed onto the unions of the saved axes and nothing priced again. The figures are the ticket's,
priced by hand here: a one-barrel HNG observing 4 January 2027 at 80 against 70 and a one-barrel
WTI observing 5 January at 55 against 50, the bilateral sources on one USD curve of 0.95 a year out
and 0.90 two years out, every payment unpaid. The tolerances are the bilateral kernel's.
docs/library/trades/aggregate-results.md is the page."""

from dataclasses import fields
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
    curve_of,
    given,
    terms_of,
)
from test_trades import an_index, dates, history_on, numbers, observed_of, quoted

from goosedove.globals.discount_curve import DiscountCurve
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.index import index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory
from goosedove.trades.aggregation import (
    AggregateResults,
    aggregate_results,
    aggregate_view,
)
from goosedove.trades.encoding import encoded
from goosedove.trades.evaluation import (
    Bucket,
    Risk,
    RiskView,
    TradeResults,
    risk_view,
    trade_results,
)
from goosedove.trades.preparation import prepared_trades
from goosedove.trades.resolution import ResolvedTrades
from goosedove.trades.terms import Route

MONTHS = (("Z26", "2026-12-31"), ("F27", "2027-01-04"), ("F29", "2029-01-05"))
HNG = an_index(
    "HNG", MONTHS, ("2027-12-27",), ("USD", "BBL"), ("VOLUME", "BBL"), ("LOT", 1.0, "BBL")
)
# WTI's F27 expires a day later, so its lastday observation is 5 January: the two indexes observe
# on different days of one month, and D's payment on 4 January 2028 comes 364 days after it.
WTI = an_index(
    "WTI",
    (("Z26", "2026-12-31"), ("F27", "2027-01-05"), ("F29", "2029-01-05")),
    ("2027-12-27",),
    ("USD", "BBL"),
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
CURVE_1 = "curve_1 USD dv01 [USD per basis point]"
CLEARED_USD = "cleared USD dv01 [USD per basis point]"


def valued_on(
    terms: ResolvedTrades, history: MarketHistory, quoted_on: Market, curve: DiscountCurve | None
) -> TradeResults:
    """The terms prepared against that history and valued against that market, the same objects
    for every source that is to combine."""
    prep = prepared_trades(
        encoded(terms, observed_of(terms), UNITS, WorkCounter()), history, WorkCounter()
    )
    return trade_results(prep, quoted_on, WorkCounter(), curve)


def hng(
    quantities: tuple[float, ...], pays: tuple[str, ...], route: Route, fixed: float = 70.0
) -> ResolvedTrades:
    return terms_of(quantities, pays, (261,) * len(quantities), route=route, fixed=fixed, ix=HNG)


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


def collected(*results: TradeResults) -> AggregateResults:
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
    assert agg.as_of == A_DAY and agg.sources == (a, b) and agg.currencies == ("USD",)
    (group,) = agg.index_groups
    assert group.index is HNG and group.reporting_lot.name == "LOT"
    assert group.history is HNG_HISTORY and group.price_vector is HNG_MARKET.price_vector
    np.testing.assert_array_equal(group.occurrences, [0, 1])
    np.testing.assert_array_equal(group.references, [1])
    np.testing.assert_allclose(group.lot_delta, [10.0], **TIGHT)
    np.testing.assert_allclose(group.discounted_lot_delta, [10.5], **TIGHT)
    assert group.lot_delta_total == 10.0
    assert group.discounted_lot_delta_total == pytest.approx(10.5, **CLOSE)
    np.testing.assert_array_equal(group.days, dates(AS_OF))
    np.testing.assert_allclose(group.daily_lots, [10.0], **TIGHT)
    np.testing.assert_allclose(group.discounted_daily_lots, [10.5], **TIGHT)
    np.testing.assert_array_equal(group.months, dates(JAN_27))
    np.testing.assert_array_equal(group.years, dates(JAN_27))
    np.testing.assert_allclose(group.monthly_lots, [10.0], **TIGHT)
    np.testing.assert_allclose(group.discounted_yearly_lots, [10.5], **TIGHT)
    (rate,) = agg.rate_groups
    assert rate.curve is FLAT and rate.number == 1 and rate.currency == "USD"
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
    np.testing.assert_array_equal(agg.by_month.union, dates(JAN_27, JAN_28, JAN_29))
    # Two occurrences, one group of each kind; the entries of every saved vector aligned once,
    # eight over the index's four axes and six over the curve's three; eleven reductions; the
    # three buckets' axes, six coordinates each.
    assert counter.freeze().as_dict() == {
        "aggregate_reductions": 11,
        "entries_aligned": 14,
        "index_groups": 1,
        "rate_groups": 1,
        "report_coordinates": 18,
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
    assert [r.number for r in agg.rate_groups] == [1]
    np.testing.assert_array_equal(agg.rate_groups[0].occurrences, [1, 3])
    view = aggregate_view(agg, Risk.ALL, Bucket.DAY)
    np.testing.assert_array_equal(view.dates, dates(AS_OF, "2027-01-05", A_YEAR, TWO_YEARS))
    assert view.labels == (HNG_NOMINAL, HNG_DELTA, WTI_NOMINAL, WTI_DELTA, CURVE_1)
    assert view.totals == (
        10.0,
        pytest.approx(10.5, **CLOSE),
        6.0,
        pytest.approx(5.8, **CLOSE),
        pytest.approx(0.0066, **CLOSE),
    )
    expected = (
        [10.0, 0.0, 0.0, 0.0],
        [10.5, 0.0, 0.0, 0.0],
        [0.0, 6.0, 0.0, 0.0],
        [0.0, 5.8, 0.0, 0.0],
        [0.0, 0.0, -0.0114, 0.018],
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
        "aggregate_reductions": 19,
        "entries_aligned": 25,
        "index_groups": 2,
        "rate_groups": 1,
        "report_coordinates": 20,
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
    assert group.lot_delta_total == 20.0
    assert group.discounted_lot_delta_total == pytest.approx(20.5, **CLOSE)
    np.testing.assert_allclose(group.daily_lots, [20.0], **TIGHT)
    assert thrice.rate_groups[0].dv01 == pytest.approx(0.0085, **CLOSE)
    np.testing.assert_array_equal(thrice.rate_groups[0].occurrences, [1])
    base = aggregate_view(collected(a, b, c, d), Risk.ALL, Bucket.DAY)
    reordered = aggregate_view(collected(c, d, a, b), Risk.ALL, Bucket.DAY)
    assert reordered.labels == (WTI_NOMINAL, WTI_DELTA, HNG_NOMINAL, HNG_DELTA, CURVE_1)
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
        "HNG", MONTHS, ("2027-12-27",), ("USD", "BBL"), ("VOLUME", "BBL"), ("LOT", 1.0, "BBL")
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
    assert agg.index_groups[0].lot_delta_total == 20.0
    np.testing.assert_array_equal(agg.index_groups[0].occurrences, [0, 1])


def test_curves_group_by_object_and_currency_and_are_numbered_by_first_appearance(
    sources: dict[str, TradeResults],
) -> None:
    # B on FLAT and B again on a curve equal in every value but another object: one index group
    # and two rate groups, curve_1 and curve_2, each with B's DV01; then one curve valuing an index
    # settled in cents: the same curve_1 in two currencies, two groups, the cents a hundredfold.
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
    assert [(r.curve, r.number, r.currency) for r in agg.rate_groups] == [
        (FLAT, 1, "USD"),
        (equal_values, 2, "USD"),
    ]
    view = aggregate_view(agg, Risk.DV01, Bucket.DAY)
    assert view.labels == (CURVE_1, "curve_2 USD dv01 [USD per basis point]")
    assert view.totals == (pytest.approx(0.0085, **CLOSE), pytest.approx(0.0085, **CLOSE))
    np.testing.assert_allclose(view.columns[1], [-0.0095, 0.018], **TIGHT)
    assert len(aggregate_view(agg, Risk.ALL, Bucket.DAY).labels) == 4
    cents = index(
        "HNGC",
        "HNG settled in cents",
        futures_schedule(
            ("Z26", "F27", "F29"), dates("2026-12-31", "2027-01-04", "2029-01-05"), None
        ),
        index_conventions("USD", "BBL", "CENT", "VOLUME", "BBL", UNITS),
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
    assert in_cents.currency == "CENT" and in_cents.dv01 == pytest.approx(0.85, **CLOSE)
    agg = collected(b, in_cents)
    assert [(r.number, r.currency) for r in agg.rate_groups] == [(1, "USD"), (1, "CENT")]
    assert agg.currencies == ("USD", "CENT")
    view = aggregate_view(agg, Risk.DV01, Bucket.YEAR)
    assert view.labels == (CURVE_1, "curve_1 CENT dv01 [CENT per basis point]")
    np.testing.assert_allclose(view.columns[1], [-0.95, 1.8], **TIGHT)
    assert view.totals[1] == pytest.approx(0.85, **CLOSE)


def test_a_collection_with_no_curve_reports_a_dv01_of_nothing_per_currency(
    sources: dict[str, TradeResults],
) -> None:
    # A and C, both cleared: no rate group; the DV01 report one column of nothing for USD over no
    # day, and all three on the two observation days with that column zero on both.
    agg = collected(sources["a"], sources["c"])
    assert agg.rate_groups == () and agg.currencies == ("USD",)
    assert agg.by_day.paid.size == 0 and agg.by_day.paid_in == ()
    dv01 = aggregate_view(agg, Risk.DV01, Bucket.DAY)
    assert dv01.dates.size == 0 and dv01.labels == (CLEARED_USD,) and dv01.totals == (0.0,)
    assert dv01.columns[0].size == 0
    everything = aggregate_view(agg, Risk.ALL, Bucket.DAY)
    np.testing.assert_array_equal(everything.dates, dates(AS_OF, "2027-01-05"))
    assert everything.labels == (HNG_NOMINAL, HNG_DELTA, WTI_NOMINAL, WTI_DELTA, CLEARED_USD)
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
    assert rate.dv01 == 0.0 and rate.number == 1
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
        "lot_delta": a.lot_delta.copy(),
        "daily": b.discounted_daily_lots.copy(),
        "dv01": given(b.dv01_by_day).copy(),
        "days": b.prepared.encoded.days.copy(),
    }
    inputs = [a, b]
    agg = aggregate_results(inputs, WorkCounter())
    inputs.append(sources["c"])
    assert agg.sources == (a, b)
    np.testing.assert_array_equal(a.lot_delta, kept["lot_delta"])
    np.testing.assert_array_equal(b.discounted_daily_lots, kept["daily"])
    np.testing.assert_array_equal(given(b.dv01_by_day), kept["dv01"])
    np.testing.assert_array_equal(b.prepared.encoded.days, kept["days"])
    scalars = {
        "index", "reporting_lot", "history", "price_vector", "lot_delta_total",
        "discounted_lot_delta_total", "curve", "number", "currency", "dv01",
    }  # fmt: skip
    frozen: list[Any] = []
    for group in (*agg.index_groups, *agg.rate_groups):
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
    assert up.lot_delta_total == big and up.mark == 0.0 and down.lot_delta_total == -big
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
    assert bought.mark == 0.0 and bought.lot_delta_total == 1e16
    for order in (
        (bought, one, sold),
        (bought, sold, one),
        (one, bought, sold),
        (sold, one, bought),
    ):
        (group,) = collected(*order).index_groups
        assert group.lot_delta_total == 1.0 and group.discounted_lot_delta_total == 1.0
        for vector in (
            group.lot_delta,
            group.discounted_lot_delta,
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
    assert barrel.lot_delta_total == pytest.approx(1 / 3, **CLOSE)
    for order in ((million, barrel, sold_million), (million, sold_million, barrel)):
        (group,) = collected(*order).index_groups
        assert group.lot_delta_total == pytest.approx(1 / 3, **CLOSE)
        np.testing.assert_allclose(group.lot_delta, [1 / 3], **TIGHT)
        np.testing.assert_allclose(group.daily_lots, [1 / 3], **TIGHT)
        np.testing.assert_allclose(group.yearly_lots, [1 / 3], **TIGHT)
        assert float(group.daily_lots.sum()) == pytest.approx(group.lot_delta_total, **CLOSE)


def test_every_view_sums_to_the_total_above_it(sources: dict[str, TradeResults]) -> None:
    # The saved Totals are the scalars summed and the vectors the saved entries summed; each column
    # of each selection and bucket adds up to its Total within the kernel's tolerance.
    agg = collected(*(sources[k] for k in "abcd"))
    for risk in Risk:
        for bucket in Bucket:
            view = aggregate_view(agg, risk, bucket)
            for total, values in zip(view.totals, view.columns, strict=True):
                assert float(values.sum()) == pytest.approx(total, **CLOSE), (risk, bucket)
