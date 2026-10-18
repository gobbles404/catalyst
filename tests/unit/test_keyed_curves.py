"""A bilateral batch on several curves, named-curves-slice-3.md: each row names its curve by
discount_curve_key, the collection holds every curve the rows name, each payment group is
discounted on its own key's curve, the discounted lots are one combined delta, and the DV01 and
the cross-gamma stand per curve. The figures are the parent's hand-worked acceptance,
multiple-discount-curves.md: a one-lot index of 10,000 barrels quoted in dollars a barrel, A ten
lots of G27 keyed SOFR and B five lots short keyed FFOIS, both at 4.00 against a quote of 4.10,
observed on 1 February 2027 and paying 4 January 2028, 365 days after the valuation day 4 January
2027, SOFR 0.95 and FFOIS 0.90 on the payment day. The tolerances are the bilateral kernel's.
docs/library/trades/evaluate-trades.md is the page."""

from dataclasses import replace

import numpy as np
import pytest
from numpy.typing import NDArray
from test_aggregate_risk import collected, same_view
from test_bilateral_kernel import (
    A_YEAR,
    AS_OF,
    CLOSE,
    TIGHT,
    TWO_YEARS,
    curve_of,
    curve_set,
    given,
    terms_of,
)
from test_trades import an_index, dates, history_on, observed_of, quoted

from goosedove.globals.discount_curve import DiscountCurve, bump_discount_curve
from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.globals.unit_conversions import UNITS
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market import Market
from goosedove.market.market_history import MarketHistory
from goosedove.trades.aggregation import aggregate_view
from goosedove.trades.encoding import Encoded, encoded
from goosedove.trades.evaluation import trade_results
from goosedove.trades.preparation import PreparedTrades, prepared_trades
from goosedove.trades.results import TradeResults, risk_view
from goosedove.trades.risk_report import Bucket, Risk
from goosedove.trades.terms import ResolvedTrades

# The parent's index: a reporting lot of 10,000 barrels, G27 expiring 1 February 2027 so that its
# lastday observation is live on the valuation day, and F29 keeping a quote in every market.
TENK = an_index(
    "TENK",
    (("Z26", "2026-12-31"), ("G27", "2027-02-01"), ("F29", "2029-01-05")),
    ("2027-12-27",),
    ("USD", "BBL"),
    ("VOLUME", "BBL"),
    ("TENK", 10_000.0, "BBL"),
)
TEN_LOTS, FIVE_SHORT = 10.0, -5.0  # the quantity counts lots of the specification, 10,000 barrels
SOFR = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90))
FFOIS = curve_of((AS_OF, 1.0), (A_YEAR, 0.90), (TWO_YEARS, 0.80), name="FFOIS")
SONIA = curve_of((AS_OF, 1.0), (A_YEAR, 0.97), (TWO_YEARS, 0.94), name="SONIA")
HISTORY = history_on(TENK, AS_OF, {})
MARKET = quoted(HISTORY, 4.10, 50.0)  # G27 at 4.10, F29 at a quote that matters to nothing
MARCH_29 = "2029-03-01"  # a payment day after F29's last observation, 5 January 2029
SOFR_DV01 = "SOFR USD dv01 [USD per basis point]"
FFOIS_DV01 = "FFOIS USD dv01 [USD per basis point]"
SOFR_CROSS = "TENK SOFR cross_gamma [TENK per basis point]"
FFOIS_CROSS = "TENK FFOIS cross_gamma [TENK per basis point]"


def keyed(
    quantities: tuple[float, ...] = (TEN_LOTS, FIVE_SHORT),
    keys: tuple[str, ...] = ("SOFR", "FFOIS"),
    pays: tuple[str, ...] | None = None,
    lags: tuple[int, ...] | None = None,
    contracts: tuple[int, ...] | None = None,
) -> ResolvedTrades:
    """The parent's rows at 4.00 on G27 of TENK, each naming its curve: A and B by default."""
    n = len(quantities)
    terms = terms_of(
        quantities,
        pays or (A_YEAR,) * n,
        lags or (261,) * n,
        contracts=contracts,
        fixed=4.0,
        ix=TENK,
    )
    return replace(terms, discount_curve_key=keys)


def prepared(terms: ResolvedTrades, history: MarketHistory = HISTORY) -> PreparedTrades:
    return prepared_trades(
        encoded(terms, observed_of(terms), UNITS, WorkCounter()), history, WorkCounter()
    )


def valued_on(
    prep: PreparedTrades,
    curves: DiscountCurveSet | None,
    market: Market = MARKET,
    counter: WorkCounter | None = None,
) -> TradeResults:
    return trade_results(prep, market, counter or WorkCounter(), curves)


def dv01s(result: TradeResults) -> tuple[float, ...]:
    return tuple(c.dv01 for c in result.rate_contributions)


def cross_gammas(result: TradeResults) -> tuple[float, ...]:
    return tuple(c.cross_gamma_total for c in result.cross_contributions)


def keys_of_groups(encoding: Encoded) -> NDArray[np.intp]:
    """Each group's key, which a keyed batch always holds."""
    assert encoding.key_of_group is not None
    return encoding.key_of_group


# --- the parent's hand numbers --------------------------------------------------------------------


def test_the_two_rows_are_discounted_on_their_own_curves_and_the_risk_stands_per_curve() -> None:
    prep = prepared(keyed())
    counter = WorkCounter()
    result = valued_on(prep, curve_set(SOFR, FFOIS), counter=counter)
    assert result.curves == (SOFR, FFOIS)
    assert result.curves[0] is SOFR and result.curves[1] is FFOIS  # the objects, in key order
    assert result.cash == 0.0
    assert result.mark == pytest.approx(5_000.0, **CLOSE)
    np.testing.assert_allclose(given(result.payment_amount), [10_000.0, -5_000.0], **TIGHT)
    np.testing.assert_array_equal(given(result.payment_factor), [0.95, 0.90])
    np.testing.assert_allclose(given(result.npv_by_group), [9_500.0, -4_500.0], **TIGHT)
    np.testing.assert_allclose(given(result.dv01_by_group), [-0.95, 0.45], **TIGHT)
    # One combined delta for the batch: five nominal lots, five discounted, 9.5 less 4.5.
    np.testing.assert_allclose(result.lot_delta, [5.0], **TIGHT)
    assert result.lot_delta_total == pytest.approx(5.0, **CLOSE)
    np.testing.assert_allclose(result.discounted_lot_delta, [5.0], **TIGHT)
    assert result.discounted_lot_delta_total == pytest.approx(5.0, **CLOSE)
    np.testing.assert_allclose(result.discounted_daily_lots, [5.0], **TIGHT)
    # The batch scalars sum the curves, both shifted together, which no report selects.
    assert result.dv01 == pytest.approx(-0.50, **CLOSE)
    assert result.cross_gamma_total == pytest.approx(-0.0005, **CLOSE)
    # Each curve's own share, in key order.
    sofr, ffois = result.rate_contributions
    assert sofr.curve is SOFR and ffois.curve is FFOIS
    assert sofr.currency == ffois.currency == "USD"
    assert sofr.dv01 == pytest.approx(-0.95, **CLOSE)
    assert ffois.dv01 == pytest.approx(0.45, **CLOSE)
    np.testing.assert_array_equal(sofr.days, dates(A_YEAR))
    np.testing.assert_allclose(sofr.dv01_by_day, [-0.95], **TIGHT)
    np.testing.assert_allclose(ffois.dv01_by_day, [0.45], **TIGHT)
    np.testing.assert_allclose(sofr.dv01_by_month, [-0.95], **TIGHT)
    np.testing.assert_allclose(ffois.dv01_by_year, [0.45], **TIGHT)
    sofr_cross, ffois_cross = result.cross_contributions
    assert sofr_cross.curve is SOFR and ffois_cross.curve is FFOIS
    np.testing.assert_allclose(sofr_cross.cross_gamma, [-0.00095], **TIGHT)
    np.testing.assert_allclose(ffois_cross.cross_gamma, [0.00045], **TIGHT)
    assert sofr_cross.cross_gamma_total == pytest.approx(-0.00095, **CLOSE)
    assert ffois_cross.cross_gamma_total == pytest.approx(0.00045, **CLOSE)
    np.testing.assert_allclose(sofr_cross.cross_gamma_by_day, [-0.00095], **TIGHT)
    np.testing.assert_allclose(ffois_cross.cross_gamma_by_month, [0.00045], **TIGHT)
    np.testing.assert_allclose(ffois_cross.cross_gamma_by_year, [0.00045], **TIGHT)
    assert counter.freeze().as_dict() == {
        "curves_selected": 2,
        "groups_valued": 2,
        "kernel": 1,
        "live_prices_read": 1,
        "payment_factors_read": 2,  # one day on each curve
        "risk_reductions": 12,
        "slots_discounted": 2,
        "slots_weighted": 2,
    }
    for contribution in (*result.rate_contributions, *result.cross_contributions):
        for name in ("dv01_by_day", "dv01_by_month", "dv01_by_year"):
            array = getattr(contribution, name, None)
            assert array is None or not array.flags.writeable
        for name in ("cross_gamma", "cross_gamma_by_day", "cross_gamma_by_month"):
            array = getattr(contribution, name, None)
            assert array is None or not array.flags.writeable


def test_offsetting_rows_on_two_curves_keep_each_curves_ownership() -> None:
    # B at ten lots short: no nominal delta, 500 of mark and 0.5 of delta from the factors alone,
    # and the two curves' risks never netted before discounting.
    result = valued_on(prepared(keyed((TEN_LOTS, -TEN_LOTS))), curve_set(SOFR, FFOIS))
    assert result.lot_delta_total == 0.0
    assert result.mark == pytest.approx(500.0, **CLOSE)
    assert result.discounted_lot_delta_total == pytest.approx(0.5, **CLOSE)
    assert dv01s(result) == (pytest.approx(-0.95, **CLOSE), pytest.approx(0.90, **CLOSE))
    assert cross_gammas(result) == (
        pytest.approx(-0.00095, **CLOSE),
        pytest.approx(0.0009, **CLOSE),
    )


def test_a_new_curve_under_one_key_moves_that_curves_numbers_alone() -> None:
    prep = prepared(keyed())
    before = valued_on(prep, curve_set(SOFR, FFOIS))
    sofr_96 = curve_of((AS_OF, 1.0), (A_YEAR, 0.96), (TWO_YEARS, 0.92))
    after = valued_on(prep, curve_set(sofr_96, FFOIS))
    assert after.curves == (sofr_96, FFOIS)
    assert after.mark == pytest.approx(5_100.0, **CLOSE)
    assert after.discounted_lot_delta_total == pytest.approx(5.1, **CLOSE)
    assert dv01s(after) == (pytest.approx(-0.96, **CLOSE), pytest.approx(0.45, **CLOSE))
    assert cross_gammas(after) == (
        pytest.approx(-0.00096, **CLOSE),
        pytest.approx(0.00045, **CLOSE),
    )
    # FFOIS's share unmoved to the last digit, and the old result holding the old curve and the
    # old numbers.
    assert after.rate_contributions[1].dv01 == before.rate_contributions[1].dv01
    np.testing.assert_array_equal(
        after.cross_contributions[1].cross_gamma, before.cross_contributions[1].cross_gamma
    )
    assert before.curves == (SOFR, FFOIS)
    assert before.mark == pytest.approx(5_000.0, **CLOSE)
    assert dv01s(before) == (pytest.approx(-0.95, **CLOSE), pytest.approx(0.45, **CLOSE))


def test_a_collection_of_one_is_todays_single_curve_number_exactly() -> None:
    alone = valued_on(prepared(keyed((TEN_LOTS,), ("SOFR",))), curve_set(SOFR))
    mixed = valued_on(prepared(keyed()), curve_set(SOFR, FFOIS))
    assert alone.curves == (SOFR,)
    assert alone.mark == pytest.approx(9_500.0, **CLOSE)
    assert dv01s(alone) == (pytest.approx(-0.95, **CLOSE),)
    assert cross_gammas(alone) == (pytest.approx(-0.00095, **CLOSE),)
    # The mixed batch's SOFR share is A alone's, entry for entry.
    assert mixed.rate_contributions[0].dv01 == alone.rate_contributions[0].dv01
    np.testing.assert_array_equal(
        mixed.rate_contributions[0].dv01_by_day, alone.rate_contributions[0].dv01_by_day
    )
    np.testing.assert_array_equal(
        mixed.cross_contributions[0].cross_gamma, alone.cross_contributions[0].cross_gamma
    )
    assert given(mixed.payment_factor)[0] == given(alone.payment_factor)[0]


@pytest.mark.parametrize("order", ["as booked", "reversed", "A repeated"])
def test_the_mixed_batch_reports_what_its_parts_collected_together_report(order: str) -> None:
    # A and B as two single-key batches, each on its own curve, collected together: column for
    # column what the mixed batch alone reports, the Totals and every dated vector by day, month
    # and year, with the rows reversed and with A booked twice as well.
    a = keyed((TEN_LOTS,), ("SOFR",))
    b = keyed((FIVE_SHORT,), ("FFOIS",))
    parts: dict[str, tuple[tuple[ResolvedTrades, DiscountCurve], ...]] = {
        "as booked": ((a, SOFR), (b, FFOIS)),
        "reversed": ((b, FFOIS), (a, SOFR)),
        "A repeated": ((a, SOFR), (a, SOFR), (b, FFOIS)),
    }
    wholes = {
        "as booked": keyed(),
        "reversed": keyed((FIVE_SHORT, TEN_LOTS), ("FFOIS", "SOFR")),
        "A repeated": keyed((TEN_LOTS, TEN_LOTS, FIVE_SHORT), ("SOFR", "SOFR", "FFOIS")),
    }
    mixed = valued_on(prepared(wholes[order]), curve_set(SOFR, FFOIS))
    apart = collected(
        *[valued_on(prepared(terms), curve_set(curve)) for terms, curve in parts[order]]
    )
    alone = collected(mixed)
    for risk in Risk:
        for bucket in Bucket:
            same_view(aggregate_view(alone, risk, bucket), aggregate_view(apart, risk, bucket))
    for bucket in Bucket:
        same_view(risk_view(mixed, Risk.ALL, bucket), aggregate_view(apart, Risk.ALL, bucket))
    labels = risk_view(mixed, Risk.ALL, Bucket.DAY).labels
    first, second = ("SOFR", "FFOIS") if order != "reversed" else ("FFOIS", "SOFR")
    assert labels[2:] == (
        f"{first} USD dv01 [USD per basis point]",
        f"{second} USD dv01 [USD per basis point]",
        f"TENK {first} cross_gamma [TENK per basis point]",
        f"TENK {second} cross_gamma [TENK per basis point]",
    )


# --- the collection and the keys ------------------------------------------------------------------


def test_a_curve_nobody_selects_imposes_nothing_and_the_keys_order_the_curves() -> None:
    prep = prepared(keyed())
    mixed = valued_on(prep, curve_set(SOFR, FFOIS))
    with_spare = valued_on(prep, curve_set(SONIA, FFOIS, SOFR))  # another order, one more curve
    assert with_spare.curves == (SOFR, FFOIS)  # key order, never the collection's
    assert with_spare.mark == mixed.mark
    assert dv01s(with_spare) == dv01s(mixed) and cross_gammas(with_spare) == cross_gammas(mixed)
    assert len(with_spare.rate_contributions) == len(with_spare.cross_contributions) == 2
    # The spare curve starting on another day, or ending before every payment, is read for
    # nothing.
    late = curve_of(("2027-01-05", 1.0), (TWO_YEARS, 0.9), name="SONIA")
    short = curve_of((AS_OF, 1.0), ("2027-06-30", 0.99), name="SONIA")
    for spare in (late, short):
        assert valued_on(prep, curve_set(SOFR, FFOIS, spare)).curves == (SOFR, FFOIS)


def test_a_key_naming_no_curve_is_refused_first_in_key_order_with_its_first_row() -> None:
    both = prepared(keyed())
    with pytest.raises(ValueError, match=r"^discount_curve_key 'SOFR' of trade 1001 at row 1 "):
        valued_on(both, curve_set(FFOIS))
    with pytest.raises(ValueError) as refused:
        valued_on(both, curve_set(SONIA))
    assert str(refused.value) == (
        "discount_curve_key 'SOFR' of trade 1001 at row 1 names no curve of the collection, "
        "which holds SONIA; expected a curve of that name"
    )
    # Case and all, the first row booking the key, and the collection's names as it holds them.
    three = prepared(keyed((TEN_LOTS, FIVE_SHORT, TEN_LOTS), ("SOFR", "FFOIS", "Sonia")))
    with pytest.raises(ValueError) as refused:
        valued_on(three, curve_set(SOFR, FFOIS, SONIA))
    assert str(refused.value) == (
        "discount_curve_key 'Sonia' of trade 1003 at row 3 names no curve of the collection, "
        "which holds SOFR, FFOIS and SONIA; expected a curve of that name"
    )
    twice = prepared(keyed((TEN_LOTS, FIVE_SHORT, TEN_LOTS), ("SOFR", "FFOIS", "FFOIS")))
    with pytest.raises(ValueError, match=r"^discount_curve_key 'FFOIS' of trade 1002 at row 2 "):
        valued_on(twice, curve_set(SOFR))


def test_each_selected_curve_starts_on_the_valuation_day_and_covers_its_own_payments() -> None:
    late_ffois = curve_of(("2027-01-05", 1.0), (TWO_YEARS, 0.9), name="FFOIS")
    late_sofr = curve_of(("2027-01-05", 1.0), (TWO_YEARS, 0.9))
    prep = prepared(keyed())
    with pytest.raises(ValueError) as refused:
        valued_on(prep, curve_set(SOFR, late_ffois))
    assert str(refused.value) == (
        "discount curve 'FFOIS' starts on 2027-01-05, expected 2027-01-04, the valuation date; "
        "a curve is never rebased"
    )
    with pytest.raises(ValueError, match=r"^discount curve 'SOFR' starts on 2027-01-05"):
        valued_on(prep, curve_set(late_sofr, late_ffois))  # key order, not the collection's
    # A pays a year out on SOFR and B two years out on FFOIS: SOFR ending before B's day covers
    # every day of its own groups; FFOIS ending there does not.
    apart = prepared(keyed(pays=(A_YEAR, TWO_YEARS), lags=(261, 522)))
    short_sofr = curve_of((AS_OF, 1.0), ("2028-12-31", 0.9))
    short_ffois = curve_of((AS_OF, 1.0), ("2028-12-31", 0.8), name="FFOIS")
    covered = valued_on(apart, curve_set(short_sofr, FFOIS))
    assert covered.curves == (short_sofr, FFOIS)
    np.testing.assert_array_equal(given(covered.payment_factor)[1:], [0.80])
    with pytest.raises(ValueError) as refused:
        valued_on(apart, curve_set(SOFR, short_ffois))
    assert str(refused.value) == (
        "the payment of G27 on 2029-01-03 on FFOIS is past the discount curve 'FFOIS', which "
        "runs from 2027-01-04 to 2028-12-31; expected every unpaid payment day covered"
    )


# --- the groups, the slots and the unpaid payments by key -----------------------------------------


def test_two_keys_on_one_day_are_two_groups_and_one_key_is_one() -> None:
    two = prepared(keyed()).encoded
    assert two.keys == ("SOFR", "FFOIS")
    np.testing.assert_array_equal(keys_of_groups(two), [0, 1])
    assert two.group_contract.size == 2 and two.slot_group.size == 2
    np.testing.assert_array_equal(two.group_contract, [1, 1])
    assert two.curve_axes is not None and two.curve_axes.curves == 2
    one = prepared(keyed(keys=("SOFR", "SOFR"))).encoded
    assert one.keys == ("SOFR",)
    np.testing.assert_array_equal(keys_of_groups(one), [0])
    assert one.group_contract.size == 1 and one.slot_group.size == 1
    assert one.curve_axes is not None and one.curve_axes.curves == 1
    # The keys in the order the rows first name them, by key within a day: B's key first.
    reversed_rows = prepared(keyed((FIVE_SHORT, TEN_LOTS), ("FFOIS", "SOFR"))).encoded
    assert reversed_rows.keys == ("FFOIS", "SOFR")
    np.testing.assert_array_equal(keys_of_groups(reversed_rows), [0, 1])


def test_the_preparation_keeps_each_keys_unpaid_groups_and_distinct_days() -> None:
    # Three rows: A on SOFR a year out, B on FFOIS a year out, C on SOFR two years out.
    prep = prepared(
        keyed(
            (TEN_LOTS, FIVE_SHORT, TEN_LOTS),
            ("SOFR", "FFOIS", "SOFR"),
            (A_YEAR, A_YEAR, TWO_YEARS),
            (261, 261, 522),
        )
    )
    pays = prep.unpaid_payments
    assert pays is not None and len(pays.by_key) == 2
    sofr, ffois = pays.by_key
    np.testing.assert_array_equal(pays.groups, [0, 1, 2])
    np.testing.assert_array_equal(prep.encoded.key_of_group, [0, 1, 0])
    np.testing.assert_array_equal(sofr.groups, [0, 2])
    np.testing.assert_array_equal(sofr.days, dates(A_YEAR, TWO_YEARS))
    np.testing.assert_array_equal(sofr.day_of_group, [0, 1])
    np.testing.assert_array_equal(ffois.groups, [1])
    np.testing.assert_array_equal(ffois.days, dates(A_YEAR))
    np.testing.assert_array_equal(ffois.day_of_group, [0])
    counter = WorkCounter()
    result = valued_on(prep, curve_set(SOFR, FFOIS), counter=counter)
    assert counter.freeze().as_dict()["payment_factors_read"] == 3  # two days and one
    np.testing.assert_array_equal(given(result.payment_factor), [0.95, 0.90, 0.90])
    np.testing.assert_allclose(given(result.npv_by_group), [9_500.0, -4_500.0, 9_000.0], **TIGHT)
    assert dv01s(result) == (pytest.approx(-0.95 - 1.8, **CLOSE), pytest.approx(0.45, **CLOSE))
    # A batch on one key holds the unpaid groups themselves, by reference.
    single = prepared(keyed()).unpaid_payments
    alone = prepared(keyed(keys=("SOFR", "SOFR"))).unpaid_payments
    assert single is not None and alone is not None
    assert len(single.by_key) == 2 and len(alone.by_key) == 1
    assert alone.by_key[0].groups is alone.groups


def test_a_fixed_but_unpaid_group_keeps_its_curves_dv01_and_no_cross_gamma_until_paid() -> None:
    # Valued on 1 June 2027, G27 having fixed at 4.10 on 1 February: A's payment is set and
    # unpaid on SOFR, with DV01 on SOFR and no lots on it; B on F29, live, is FFOIS's alone,
    # paying 1 March 2029, after F29's last observation.
    terms = keyed((TEN_LOTS, FIVE_SHORT), ("SOFR", "FFOIS"), (A_YEAR, MARCH_29), (261, 560), (1, 2))
    june = "2027-06-01"
    sofr = curve_of((june, 1.0), (A_YEAR, 0.97))
    ffois = curve_of((june, 1.0), (MARCH_29, 0.90), name="FFOIS")
    history = history_on(TENK, june, {"G27": 4.10})
    prep = prepared(terms, history)
    counter = WorkCounter()
    result = valued_on(prep, curve_set(sofr, ffois), quoted(history, 4.10), counter)
    assert result.curves == (sofr, ffois) and result.cash == 0.0
    np.testing.assert_allclose(given(result.payment_amount), [10_000.0, -5_000.0], **TIGHT)
    np.testing.assert_allclose(given(result.npv_by_group), [9_700.0, -4_500.0], **TIGHT)
    tau_a = (np.datetime64(A_YEAR) - np.datetime64(june)).astype(np.int64) / 365.0
    tau_b = (np.datetime64(MARCH_29) - np.datetime64(june)).astype(np.int64) / 365.0
    assert dv01s(result) == (
        pytest.approx(-0.0001 * tau_a * 9_700.0, **CLOSE),
        pytest.approx(-0.0001 * tau_b * -4_500.0, **CLOSE),
    )
    # No live lot on SOFR: its cross-gamma is the known zero; FFOIS carries B's lots.
    assert cross_gammas(result)[0] == 0.0
    assert cross_gammas(result)[1] == pytest.approx(-0.0001 * tau_b * -4.5, **CLOSE)
    np.testing.assert_allclose(result.lot_delta, [0.0, -5.0], **TIGHT)
    np.testing.assert_allclose(result.discounted_lot_delta, [0.0, -4.5], **TIGHT)
    assert counter.freeze().as_dict()["payment_factors_read"] == 2
    # Paid, on 1 February 2028: A is cash, SOFR still bound and read for no day.
    february = "2028-02-01"
    paid_history = history_on(TENK, february, {"G27": 4.10})
    paid = prepared(terms, paid_history)
    later_sofr = curve_of((february, 1.0), (MARCH_29, 0.98))
    later_ffois = curve_of((february, 1.0), (MARCH_29, 0.93), name="FFOIS")
    counter = WorkCounter()
    settled = valued_on(
        paid, curve_set(later_sofr, later_ffois), quoted(paid_history, 4.10), counter
    )
    assert settled.curves == (later_sofr, later_ffois)
    assert settled.cash == pytest.approx(10_000.0, **CLOSE)
    assert settled.mark == pytest.approx(-4_650.0, **CLOSE)
    assert dv01s(settled)[0] == 0.0
    assert counter.freeze().as_dict()["curves_selected"] == 2
    assert counter.freeze().as_dict()["payment_factors_read"] == 1


# --- the bump check per curve ---------------------------------------------------------------------


def test_bumping_one_curve_moves_its_share_alone_and_agrees_with_its_analytic_risk() -> None:
    prep = prepared(keyed())
    base = valued_on(prep, curve_set(SOFR, FFOIS))
    up = valued_on(prep, curve_set(bump_discount_curve(SOFR, 1.0, WorkCounter()), FFOIS))
    down = valued_on(prep, curve_set(bump_discount_curve(SOFR, -1.0, WorkCounter()), FFOIS))
    # The centered differences of the mark and of the discounted delta are SOFR's analytic DV01
    # and cross-gamma, the third-order term of a basis point cubed over six within the tolerance.
    assert (up.mark - down.mark) / 2 == pytest.approx(dv01s(base)[0], rel=1e-8)
    assert (up.discounted_lot_delta_total - down.discounted_lot_delta_total) / 2 == pytest.approx(
        cross_gammas(base)[0], rel=1e-8
    )
    for moved in (up, down):
        assert moved.rate_contributions[1].dv01 == base.rate_contributions[1].dv01
        np.testing.assert_array_equal(
            moved.rate_contributions[1].dv01_by_day, base.rate_contributions[1].dv01_by_day
        )
        np.testing.assert_array_equal(
            moved.cross_contributions[1].cross_gamma, base.cross_contributions[1].cross_gamma
        )
        assert given(moved.payment_factor)[1] == given(base.payment_factor)[1]
        assert moved.curves[1] is FFOIS
