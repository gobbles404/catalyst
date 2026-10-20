"""The contributions a result keeps per curve, named-curves-slice-2.md: one rate and one cross
contribution from a bilateral evaluation, by reference to the arrays the evaluation made, none
from a cleared batch, one rate contribution from a batch of cashflows; and the words a report
names a curve by, the name bare or, where two objects share one, both qualified."""

from hypothesis import given, settings
from hypothesis import strategies as st
from test_aggregate_risk import HNG_HISTORY, HNG_MARKET, hng, valued_on
from test_bilateral_kernel import A_YEAR, AS_OF, TWO_YEARS, cross, curve_of, prepared_on, rate
from test_bilateral_kernel import terms_of as bilateral_terms
from test_bilateral_kernel import valued as trades_valued
from test_cashflows import booked
from test_cashflows import valued as cashflows_valued

from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.aggregation import aggregate_results, aggregate_view
from goosedove.trades.contributions import (
    CLEARED,
    CrossContribution,
    RateContribution,
    curve_words,
)
from goosedove.trades.results import risk_view
from goosedove.trades.risk_report import Bucket, Risk
from goosedove.trades.terms import Route

SOFR = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90))
FFOIS = curve_of((AS_OF, 1.0), (A_YEAR, 0.96), (TWO_YEARS, 0.92), name="FFOIS")


# --- the words ------------------------------------------------------------------------------------


def test_a_name_one_object_carries_is_its_bare_word() -> None:
    assert curve_words([SOFR]) == {id(SOFR): "SOFR"}
    assert curve_words([SOFR, FFOIS, SOFR]) == {id(SOFR): "SOFR", id(FFOIS): "FFOIS"}
    assert curve_words([]) == {}


def test_two_objects_of_one_name_are_both_qualified_by_first_appearance() -> None:
    again = curve_of((AS_OF, 1.0), (A_YEAR, 0.94), name="SOFR")
    assert curve_words([SOFR, FFOIS, again]) == {
        id(SOFR): "SOFR (curve_1)",
        id(FFOIS): "FFOIS",
        id(again): "SOFR (curve_2)",
    }
    # The place follows the first appearance among that name's objects, whatever comes between.
    assert curve_words([again, SOFR, again, SOFR]) == {
        id(again): "SOFR (curve_1)",
        id(SOFR): "SOFR (curve_2)",
    }
    # Display, not identity: the same values under one name are two objects and two words, and
    # the number says nothing of the object beyond its place in this listing.
    twin = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90))
    assert curve_words([SOFR, twin])[id(twin)] == "SOFR (curve_2)"
    assert curve_words([twin])[id(twin)] == "SOFR"


def test_a_qualifier_never_repeats_a_name_or_the_cleared_word() -> None:
    # The review of 2bb4574: a name in the qualifier's own form beside two objects of the name
    # it qualifies, and a curve named for a batch on no curve. Every word is distinct, the place
    # counting on past a word the report already uses, and `cleared` is kept for no curve.
    again = curve_of((AS_OF, 1.0), (A_YEAR, 0.94), name="SOFR")
    literal = curve_of((AS_OF, 1.0), (A_YEAR, 0.93), name="SOFR (curve_1)")
    assert curve_words([SOFR, again, literal]) == {
        id(SOFR): "SOFR (curve_2)",
        id(again): "SOFR (curve_3)",
        id(literal): "SOFR (curve_1)",
    }
    later = curve_of((AS_OF, 1.0), (A_YEAR, 0.93), name="SOFR (curve_2)")
    assert curve_words([SOFR, again, later]) == {
        id(SOFR): "SOFR (curve_1)",
        id(again): "SOFR (curve_3)",
        id(later): "SOFR (curve_2)",
    }
    cleared = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), name=CLEARED)
    assert curve_words([cleared]) == {id(cleared): "cleared (curve_1)"}
    assert curve_words([SOFR, cleared]) == {id(SOFR): "SOFR", id(cleared): "cleared (curve_1)"}
    taken = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), name="cleared (curve_1)")
    assert curve_words([cleared, taken]) == {
        id(cleared): "cleared (curve_2)",
        id(taken): "cleared (curve_1)",
    }


@settings(deadline=None)
@given(
    names=st.lists(
        st.sampled_from(
            ["SOFR", "FFOIS", CLEARED, "SOFR (curve_1)", "SOFR (curve_2)", "cleared (curve_1)"]
        ),
        max_size=8,
    )
)
def test_every_word_is_distinct_whatever_the_names(names: list[str]) -> None:
    curves = [curve_of((AS_OF, 1.0), (A_YEAR, 0.95), name=name) for name in names]
    words = curve_words(curves)
    assert len(words) == len(curves) and len(set(words.values())) == len(curves)
    assert CLEARED not in words.values()
    for curve in curves:
        if names.count(curve.name) == 1 and curve.name != CLEARED:
            assert words[id(curve)] == curve.name


def test_a_curve_named_cleared_keeps_its_columns_apart_from_a_cleared_batch() -> None:
    named = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90), name=CLEARED)
    on_named = valued_on(hng((10.0,), (A_YEAR,), Route.BILATERAL), HNG_HISTORY, HNG_MARKET, named)
    assert risk_view(on_named, Risk.ALL, Bucket.DAY).labels[2:] == (
        "cleared (curve_1) USD dv01 [USD per basis point]",
        "HNG cleared (curve_1) cross_gamma [LOT per basis point]",
    )
    cleared = valued_on(hng((10.0,), (A_YEAR,), Route.CLEARED), HNG_HISTORY, HNG_MARKET, None)
    both = aggregate_results([cleared, on_named], WorkCounter())
    assert aggregate_view(both, Risk.CROSS_GAMMA, Bucket.DAY).labels == (
        "HNG cleared cross_gamma [LOT per basis point]",
        "HNG cleared (curve_1) cross_gamma [LOT per basis point]",
    )
    assert aggregate_view(both, Risk.DV01, Bucket.DAY).labels == (
        "cleared (curve_1) USD dv01 [USD per basis point]",
    )


# --- the contributions on the records -------------------------------------------------------------


def test_a_bilateral_result_keeps_one_contribution_of_each_kind_by_reference() -> None:
    prep = prepared_on(bilateral_terms())
    result = trades_valued(prep, (80.0, 50.0), SOFR)
    (contribution,) = result.rate_contributions
    assert isinstance(contribution, RateContribution)
    assert contribution.curve is SOFR and contribution.currency == result.currency
    assert contribution.dv01 == result.dv01  # the one curve's share is the whole of it
    axes = prep.encoded.payment_axes
    assert axes is not None
    assert contribution.days is axes.days and contribution.months is axes.months
    assert contribution.years is axes.years
    assert contribution.dv01_by_day.sum() == contribution.dv01
    assert not contribution.dv01_by_day.flags.writeable
    (cross_contribution,) = result.cross_contributions
    assert isinstance(cross_contribution, CrossContribution)
    assert cross_contribution.curve is SOFR
    assert cross_contribution.cross_gamma_total == result.cross_gamma_total
    assert cross_contribution.references is prep.encoded.references
    assert cross_contribution.days is prep.encoded.days
    assert cross_contribution.months is prep.encoded.contract_months
    assert cross_contribution.years is prep.encoded.contract_years
    assert not cross_contribution.cross_gamma.flags.writeable
    assert rate(result) is contribution and cross(result) is cross_contribution


def test_a_cleared_result_keeps_no_contribution_and_the_known_zeros() -> None:
    result = trades_valued(prepared_on(bilateral_terms(route=Route.CLEARED)), (80.0, 50.0), None)
    assert result.rate_contributions == () and result.cross_contributions == ()
    assert result.dv01 == 0.0 and result.cross_gamma_total == 0.0


def test_a_batch_of_cashflows_keeps_one_rate_contribution_on_its_curve() -> None:
    result = cashflows_valued(booked(), curve=FFOIS)
    (contribution,) = result.rate_contributions
    assert contribution.curve is FFOIS and contribution.currency == "USD"
    assert contribution.dv01 == result.dv01
    assert contribution.days is result.cashflows.payment_days
    assert contribution.months is result.cashflows.months
    assert contribution.years is result.cashflows.years
    assert not contribution.dv01_by_month.flags.writeable


def test_a_batch_of_cashflows_reports_under_the_word_its_collection_shows() -> None:
    # The review of 5b14c61: the result's own report names its curve by the word a
    # collection of the batch alone shows, a curve named cleared qualified in both.
    for name, word in (("SOFR", "SOFR"), (CLEARED, "cleared (curve_1)")):
        curve = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90), name=name)
        result = cashflows_valued(booked(), curve=curve)
        alone = aggregate_results([result], WorkCounter())
        for bucket in Bucket:
            direct = result.report(Risk.DV01, bucket)
            collected = aggregate_view(alone, Risk.DV01, bucket)
            assert direct.labels == collected.labels == (f"{word} USD dv01 [USD per basis point]",)
            assert direct.totals == collected.totals == (result.dv01,)
