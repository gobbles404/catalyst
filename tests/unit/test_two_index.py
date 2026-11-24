"""Two index legs on a fixed_float at one outright price, two-index-fixed-float.md and
two-index-one-price.md: a pair of synthetic indexes, A a futures index with a 10,000 MMBTU
reporting lot and B an IFERC index with a 2,500 MMBTU one, each defining one MMBTU per entered
unit, through resolution, encoding, preparation and evaluation; the hand-priced acceptance
table at the outright price, its cleared version, the outright price moved, the F27 lifecycle,
the bump check of the analytic rate risk, and the rules of the pair: the second leg's method
and no second price, distinct indexes of one quoting, one quantity on both legs, the later
observation anchoring one shared payment, histories and markets matched by identity whatever
their order, and the first leg's fees. Every expected number is the ticket's or hand arithmetic
here; the production code is never asked for an expected answer."""

import os
import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray
from test_aggregate_risk import column, same_view
from test_bilateral_kernel import curve_of, curve_set
from test_create_trades import a_template, a_ticket
from test_trades import dates, day, history_on, numbers, quoted, waha_history
from test_utilities import rows

from catalyst.cashflows.booking import cashflows
from catalyst.cashflows.valuation import cashflow_results
from catalyst.excel import bridge
from catalyst.excel.bridge import Cells
from catalyst.excel.utilities import shown
from catalyst.globals.discount_curve import DiscountCurve, bump_discount_curve
from catalyst.globals.discount_curve_set import collect_discount_curves
from catalyst.globals.unit_conversions import UNITS
from catalyst.globals.valuation_date import valuation_date
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.holiday_calendar import holiday_calendar
from catalyst.index_definitions.iferc_schedule import iferc_schedule
from catalyst.index_definitions.index import Index, index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import CASHFLOW, FIXED_FLOAT
from catalyst.market.market import Market
from catalyst.market.market_history import MarketHistory
from catalyst.trades.aggregation import aggregate_results
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import PreparedTrades, prepared_trades
from catalyst.trades.resolution import Trades, trades
from catalyst.trades.results import TradeResults
from catalyst.trades.risk_report import Bucket, Risk

CLOSE: dict[str, Any] = {"rel": 1e-12, "abs": 1e-12}


def close(actual: NDArray[np.float64] | None, expected: list[float]) -> None:
    """A retained vector, never None here, as expected to within 1e-12, absolute and relative."""
    assert actual is not None
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)


# --- the pair -------------------------------------------------------------------------------------
# A: a futures index, X26 to J27, F27 expiring 29 December 2026 and G27 27 January 2027, the
# pricing holidays Christmas and New Year's Day; LOT 10,000 MMBTU reported, MMBTU one each, the
# fees a cent of brokerage and half a cent of clearing per MMBTU. B: an IFERC index, Z26 to H27,
# F27 publishing 4 January 2027 and G27 1 February, J27 unused; LOT 2,500 MMBTU reported;
# fees of half a
# dollar per MMBTU, which the pair never charges, the first leg's being the deal's.


def futures(
    name: str,
    lot_size: float,
    brokerage: float,
    clearing: float,
    quote_currency: str = "DOLLAR",
    extra: tuple[str, ...] = (),
    spec: tuple[str, float, str] | None = None,
) -> Index:
    contracts = (
        ("X26", "2026-10-28"),
        ("Z26", "2026-11-25"),
        ("F27", "2026-12-29"),
        ("G27", "2027-01-27"),
        ("H27", "2027-02-24"),
        ("J27", "2027-03-29"),
    )
    names = ("LOT", "MMBTU", *extra)
    sizes = numbers(lot_size, 1.0, *([1.0] * len(extra)))
    units = ("MMBTU",) * len(names)
    if spec is not None:  # one more specification, in a unit of its own
        names, sizes, units = (*names, spec[0]), np.append(sizes, spec[1]), (*units, spec[2])
    return index(
        name,
        f"Index {name}",
        futures_schedule(tuple(c for c, _ in contracts), dates(*(e for _, e in contracts)), None),
        index_conventions(quote_currency, "MMBTU", "DOLLAR", "ENERGY", "MMBTU", UNITS),
        contract_specifications(
            names,
            sizes,
            units,
            sizes * brokerage,
            sizes * clearing,
            UNITS,
        ),
        holiday_calendar(dates("2026-12-25", "2027-01-01")),
        "LOT",
        UNITS,
    )


def iferc(
    name: str,
    lot_size: float,
    quote_currency: str = "DOLLAR",
    spec: tuple[str, float, str] | None = None,
) -> Index:
    names: tuple[str, ...] = ("LOT", "MMBTU")
    sizes = numbers(lot_size, 1.0)
    units: tuple[str, ...] = ("MMBTU", "MMBTU")
    if spec is not None:
        names, sizes, units = (*names, spec[0]), np.append(sizes, spec[1]), (*units, spec[2])
    return index(
        name,
        f"Index {name}",
        iferc_schedule(
            ("Z26", "F27", "G27", "H27", "J27"),
            dates("2026-12-01", "2027-01-04", "2027-02-01", "2027-03-01", "2027-04-01"),
        ),
        index_conventions(quote_currency, "MMBTU", "DOLLAR", "ENERGY", "MMBTU", UNITS),
        contract_specifications(names, sizes, units, sizes * 0.5, sizes * 0.5, UNITS),
        None,
        "LOT",
        UNITS,
    )


A = futures("A", 10_000.0, 0.01, 0.005, extra=("THERM10",))
B = iferc("B", 2_500.0)
PAYS = holiday_calendar(dates())  # weekends alone
AS_OF = "2027-01-04"
PAY = "2028-01-04"  # exactly 365 days on, tau 1
SOFR = curve_of((AS_OF, 1.0), (PAY, 0.95))
SHARED: dict[str, object] = {
    "quantity_unit": "MMBTU",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "lastday",
    "second_schedule_method": "lastday",
    "settlement_method": "financial",
    "payment_holiday_calendar": PAYS,
}
BILATERAL: dict[str, object] = {
    **SHARED,
    "route": "bilateral",
    "counterparty": "ACME Trading",
    "discount_curve_key": "SOFR",
    "payment_day": day(PAY),
}
CLEARED: dict[str, object] = {
    **SHARED,
    "route": "cleared",
    "clearing_house": "ICE Clear Europe",
    "payment_day": day(PAY),
}
TICKET: dict[str, list[object]] = {
    "trade_id": [1],
    "trade_date": ["2026-12-15"],
    "contract_code": ["G27"],
    "quantity": [10_000],
    "fixed_price": [3.00],  # the outright, the one price of the deal
}


def booked(
    template: Mapping[str, object] = BILATERAL,
    ticket: Mapping[str, list[object]] = TICKET,
    indexes: Sequence[Index] = (A, B),
) -> Trades:
    return trades(indexes, a_ticket(ticket), a_template(template), UNITS, WorkCounter())


def refused(
    template: Mapping[str, object] = BILATERAL,
    ticket: Mapping[str, list[object]] = TICKET,
    indexes: Sequence[Index] = (A, B),
) -> str:
    with pytest.raises(ValueError) as refusal:
        booked(template, ticket, indexes)
    return str(refusal.value)


def histories(
    as_of: str = AS_OF,
    finals_a: Mapping[str, float] | None = None,
    indices_b: Mapping[str, float] | None = None,
) -> tuple[MarketHistory, MarketHistory]:
    """A's and B's histories on the day: A's settles 3.00 on every fixed day but the finals given,
    B's the months published before the day."""
    return (
        history_on(A, as_of, dict(finals_a or {"F27": 3.55})),
        waha_history(as_of, dict(indices_b or {"Z26": -0.30}), B),
    )


def valued(
    batch: Trades,
    as_of: str = AS_OF,
    finals_a: Mapping[str, float] | None = None,
    indices_b: Mapping[str, float] | None = None,
    quotes_a: tuple[float, ...] = (3.50, 3.60),
    quotes_b: tuple[float, ...] = (-0.38, -0.40, -0.42),
    curve: DiscountCurve | None = SOFR,
    counter: WorkCounter | None = None,
) -> TradeResults:
    """The batch prepared against both histories and valued against both markets, A's quotes
    from its first live contract on, G27 on the hand table's day, and B's from F27, so that G27
    quotes -0.40 there."""
    hist_a, hist_b = histories(as_of, finals_a, indices_b)
    prep = prepared_trades(batch.encoded, (hist_a, hist_b), WorkCounter())
    return trade_results(
        prep,
        (quoted(hist_a, *quotes_a), quoted(hist_b, *quotes_b)),
        counter or WorkCounter(),
        None if curve is None else curve_set(curve),
    )


def legs_of(results: TradeResults) -> tuple[Any, Any]:
    a, b = results.legs
    return a, b


# --- the hand-priced acceptance table ------------------------------------------------------------


def test_the_hand_table_both_legs_live_on_4_january_2027() -> None:
    # 10,000 MMBTU at the outright 3.00 against 3.50 and -0.40, 3.10 together, one payment a
    # year on at 0.95: payment 1,000, mark 950, DV01 -0.095; nominal deltas 1 lot of A and 4 of
    # B, deltas 0.95 and 3.8, cross-gammas -0.000095 and -0.00038; no leg has a value and no
    # sum crosses the two indexes' lots.
    batch = booked()
    assert batch.resolved.descriptor == "A+B"
    assert [leg.index for leg in batch.resolved.legs] == [A, B]
    close(batch.resolved.price, [3.0])
    close(batch.encoded.offset, [-30_000.0])  # -10,000 MMBTU at 3.00, the trade's once
    close(batch.encoded.offset_of_group, [-30_000.0])
    results = valued(batch)
    a, b = legs_of(results)
    assert (a.prepared.encoded.leg.index, b.prepared.encoded.leg.index) == (A, B)
    close(results.payment_amount, [1000.0])
    close(results.payment_factor, [0.95])
    assert results.mark == pytest.approx(950.0, **CLOSE)
    assert results.dv01 == pytest.approx(-0.095, **CLOSE)
    close(results.npv_by_group, [950.0])
    close(results.dv01_by_group, [-0.095])
    # Each leg's floating side, its one slot's live contribution: 35,000 of A and -4,000 of B,
    # which with the fixed leg make the payment.
    close(a.dated_live_contribution, [35_000.0])
    close(b.dated_live_contribution, [-4_000.0])
    assert a.nominal_delta_total == pytest.approx(1.0, **CLOSE)
    assert b.nominal_delta_total == pytest.approx(4.0, **CLOSE)
    assert a.delta_total == pytest.approx(0.95, **CLOSE)
    assert b.delta_total == pytest.approx(3.8, **CLOSE)
    assert a.cross_gamma_total == pytest.approx(-0.000095, **CLOSE)
    assert b.cross_gamma_total == pytest.approx(-0.00038, **CLOSE)
    assert "LOT" in a.lot_unit and "LOT" in b.lot_unit and a.lot_unit != b.lot_unit
    # No value is a leg's, the records holding none, and the trade's rate risk is one curve's.
    for name in ("mark", "cash", "dv01", "payment_amount", "npv_by_group", "dv01_by_group"):
        assert not hasattr(a, name), name
    (rate,) = results.rate_contributions
    assert rate.curve is SOFR and rate.dv01 == pytest.approx(-0.095, **CLOSE)
    assert results.cash == 0.0
    assert [c.curve for c in a.cross_contributions] == [SOFR]
    assert a.cross_contributions[0].cross_gamma_total == pytest.approx(-0.000095, **CLOSE)


def test_the_cleared_version_is_undiscounted_with_no_rate_risk() -> None:
    results = valued(booked(CLEARED), curve=None)
    a, b = legs_of(results)
    assert (results.mark, results.dv01) == (1000.0, 0.0)
    assert (a.cross_gamma_total, b.cross_gamma_total) == (0.0, 0.0)
    assert a.delta is a.nominal_delta and b.delta is b.nominal_delta
    assert results.payment_amount is None and results.npv_by_group is None
    assert results.curves == () and results.rate_contributions == ()


def test_moving_the_outright_price_moves_the_value_and_the_rate_risk_and_not_the_deltas() -> None:
    # 2.90 in place of 3.00: the payment 2,000, the mark 1,900 and the DV01 -0.19; every delta
    # and cross-gamma stands, the fixed price entering none of them.
    results = valued(booked(ticket={**TICKET, "fixed_price": [2.90]}))
    a, b = legs_of(results)
    close(results.payment_amount, [2000.0])
    assert results.mark == pytest.approx(1900.0, **CLOSE)
    assert results.dv01 == pytest.approx(-0.19, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (1.0, 4.0)
    assert (a.delta_total, b.delta_total) == pytest.approx((0.95, 3.8), **CLOSE)
    assert a.cross_gamma_total == pytest.approx(-0.000095, **CLOSE)
    assert b.cross_gamma_total == pytest.approx(-0.00038, **CLOSE)


def test_a_sold_pair_reverses_every_value_and_risk() -> None:
    bought = valued(booked())
    sold = valued(booked(ticket={**TICKET, "quantity": [-10_000]}))
    for mine, theirs in zip(sold.legs, bought.legs, strict=True):
        assert mine.nominal_delta_total == pytest.approx(-theirs.nominal_delta_total, **CLOSE)
        assert mine.delta_total == pytest.approx(-theirs.delta_total, **CLOSE)
        assert mine.cross_gamma_total == pytest.approx(-theirs.cross_gamma_total, **CLOSE)
    assert sold.mark == pytest.approx(-bought.mark, **CLOSE)
    assert sold.dv01 == pytest.approx(-bought.dv01, **CLOSE)


def test_the_analytic_rate_risk_matches_a_bumped_curve() -> None:
    # One basis point up and down on the curve: the marks' half difference is the trade's DV01,
    # and each leg's discounted lots' half difference its cross-gamma, to the second order a
    # bump of a basis point leaves.
    batch = booked()
    up = valued(batch, curve=bump_discount_curve(SOFR, 1.0, WorkCounter()))
    down = valued(batch, curve=bump_discount_curve(SOFR, -1.0, WorkCounter()))
    results = valued(batch)
    assert (up.mark - down.mark) / 2 == pytest.approx(results.dv01, rel=1e-6)
    for before, after, leg in zip(up.legs, down.legs, results.legs, strict=True):
        assert (before.delta_total - after.delta_total) / 2 == pytest.approx(
            leg.cross_gamma_total, rel=1e-6
        )


# --- the F27 lifecycle ---------------------------------------------------------------------------
# A observes 29 December 2026 at 3.55, B publishes 4 January 2027 at -0.35; +2bd from the later
# observation pays 6 January; the same quantity and prices as the table.

LIFECYCLE: dict[str, object] = {**BILATERAL, "payment_day": "+2bd"}
F27: dict[str, list[object]] = {**TICKET, "contract_code": ["F27"]}


def on(as_of: str, factor: float) -> DiscountCurve:
    """A curve anchored on the valuation day with the given factor on the payment day."""
    return curve_of((as_of, 1.0), ("2027-01-06", factor), ("2027-06-30", factor - 0.02))


def test_the_pair_pays_two_business_days_after_the_later_observation() -> None:
    batch = booked(LIFECYCLE, F27)
    terms = batch.resolved
    assert terms.payment is not None
    np.testing.assert_array_equal(terms.payment.date, dates("2027-01-06"))
    a, b = batch.encoded.legs
    np.testing.assert_array_equal(a.slot_date, dates("2026-12-29"))
    np.testing.assert_array_equal(b.slot_date, dates("2027-01-04"))
    assert a.group_contract.tolist() == [2] and b.group_contract.tolist() == [1]  # F27 on each


def test_the_lifecycle_both_live_on_28_december() -> None:
    results = valued(
        booked(LIFECYCLE, F27),
        "2026-12-28",
        finals_a={},
        quotes_a=(3.50, 3.60, 3.70),
        quotes_b=(-0.40, -0.42, -0.44),
        curve=on("2026-12-28", 0.99),
    )
    a, b = legs_of(results)
    tau = 9 / 365
    close(results.payment_amount, [1000.0])
    assert results.mark == pytest.approx(1000.0 * 0.99, **CLOSE)
    assert results.dv01 == pytest.approx(-0.0001 * tau * 1000.0 * 0.99, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (1.0, 4.0)


def test_the_lifecycle_a_fixed_on_30_december_and_the_unpaid_payment_still_carries_dv01() -> None:
    results = valued(
        booked(LIFECYCLE, F27),
        "2026-12-30",
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.40, -0.42, -0.44),
        curve=on("2026-12-30", 0.995),
    )
    a, b = legs_of(results)
    tau = 7 / 365
    close(results.payment_amount, [1500.0])  # 10,000 at 3.55 less 0.40 less the outright 3.00
    close(a.prepared.fixed_contribution, [35_500.0])  # A's side, fixed at 3.55
    close(b.dated_live_contribution, [-4_000.0])  # B's side, live at -0.40
    assert results.mark == pytest.approx(1500.0 * 0.995, **CLOSE)
    assert results.dv01 == pytest.approx(-0.0001 * tau * 1500.0 * 0.995, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (0.0, 4.0)
    assert a.cross_gamma_total == 0.0 and b.cross_gamma_total != 0.0
    # A's fixing corrected moves A's side alone, and the one payment with it; B's quote moved
    # moves B's side alone.
    corrected = valued(
        booked(LIFECYCLE, F27),
        "2026-12-30",
        finals_a={"F27": 3.60},
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.40, -0.42, -0.44),
        curve=on("2026-12-30", 0.995),
    )
    close(corrected.payment_amount, [2000.0])  # 3.60 less 0.40 less 3.00
    close(corrected.legs[0].prepared.fixed_contribution, [36_000.0])
    close(corrected.legs[1].dated_live_contribution, [-4_000.0])
    moved = valued(
        booked(LIFECYCLE, F27),
        "2026-12-30",
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.45, -0.42, -0.44),
        curve=on("2026-12-30", 0.995),
    )
    close(moved.payment_amount, [1000.0])  # 3.55 less 0.45 less 3.00
    close(moved.legs[0].prepared.fixed_contribution, [35_500.0])
    close(moved.legs[1].dated_live_contribution, [-4_500.0])


def test_the_lifecycle_both_fixed_on_5_january_with_dv01_remaining() -> None:
    results = valued(
        booked(LIFECYCLE, F27),
        "2027-01-05",
        indices_b={"Z26": -0.30, "F27": -0.35},
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.42, -0.44),
        curve=on("2027-01-05", 0.9999),
    )
    a, b = legs_of(results)
    tau = 1 / 365
    close(results.payment_amount, [2000.0])  # 3.55 less 0.35 less 3.00, both sides fixed
    close(a.prepared.fixed_contribution, [35_500.0])
    close(b.prepared.fixed_contribution, [-3_500.0])
    assert results.mark == pytest.approx(2000.0 * 0.9999, **CLOSE)
    assert results.dv01 == pytest.approx(-0.0001 * tau * 2000.0 * 0.9999, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (0.0, 0.0)
    assert results.cash == 0.0


def test_the_lifecycle_paid_on_6_january_is_one_cash_amount() -> None:
    results = valued(
        booked(LIFECYCLE, F27),
        "2027-01-06",
        indices_b={"Z26": -0.30, "F27": -0.35},
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.42, -0.44),
        curve=curve_of(("2027-01-06", 1.0), ("2027-06-30", 0.98)),
    )
    a, b = legs_of(results)
    assert (results.mark, results.dv01) == (0.0, 0.0)
    assert results.cash == pytest.approx(2000.0, **CLOSE)  # one amount, split by nothing
    assert (a.nominal_delta_total, b.nominal_delta_total) == (0.0, 0.0)
    assert results.prepared.is_settled.tolist() == [True]


def test_a_small_legs_dollar_survives_a_strike_that_cancels_the_large_leg() -> None:
    # The review's case on #242: one MMBTU, A quoted and struck at ten thousand trillion, B
    # quoted at one dollar. Adding the two sides before the strike rounds the dollar away; the
    # payment is its signed terms summed with compensation, so it reads one dollar with both
    # legs live, with A fixed, with both fixed and, paid, as cash, on either route.
    extreme: dict[str, list[object]] = {**F27, "quantity": [1], "fixed_price": [1e16]}
    big, one = (1e16, 1e16, 1e16), (1.0, 1.0, 1.0)
    live = valued(
        booked(LIFECYCLE, extreme),
        "2026-12-28",
        finals_a={},
        quotes_a=big,
        quotes_b=one,
        curve=on("2026-12-28", 0.99),
    )
    close(live.payment_amount, [1.0])
    assert live.mark == pytest.approx(0.99, **CLOSE)
    a_fixed = valued(
        booked(LIFECYCLE, extreme),
        "2026-12-30",
        finals_a={"F27": 1e16},
        quotes_a=big,
        quotes_b=one,
        curve=on("2026-12-30", 0.995),
    )
    close(a_fixed.payment_amount, [1.0])
    both_fixed = valued(
        booked(LIFECYCLE, extreme),
        "2027-01-05",
        finals_a={"F27": 1e16},
        indices_b={"Z26": -0.30, "F27": 1.0},
        quotes_a=big,
        quotes_b=one,
        curve=on("2027-01-05", 0.9999),
    )
    close(both_fixed.payment_amount, [1.0])
    paid = valued(
        booked(LIFECYCLE, extreme),
        "2027-01-06",
        finals_a={"F27": 1e16},
        indices_b={"Z26": -0.30, "F27": 1.0},
        quotes_a=big,
        quotes_b=one,
        curve=curve_of(("2027-01-06", 1.0), ("2027-06-30", 0.98)),
    )
    assert (paid.cash, paid.mark) == (1.0, 0.0)
    cleared = {**CLEARED, "payment_day": "+2bd"}
    both_live = valued(
        booked(cleared, extreme), "2026-12-28", finals_a={}, quotes_a=big, quotes_b=one, curve=None
    )
    assert both_live.mark == 1.0
    fixed = valued(
        booked(cleared, extreme),
        "2027-01-05",
        finals_a={"F27": 1e16},
        indices_b={"Z26": -0.30, "F27": 1.0},
        quotes_a=big,
        quotes_b=one,
        curve=None,
    )
    assert fixed.mark == 1.0 and fixed.prepared.set_unsettled == (1e16, 1.0)


# --- slots, offsets and payments of a pair -------------------------------------------------------


def test_two_futures_legs_observing_one_day_are_two_slots_with_their_own_fixings() -> None:
    # A and C expire alike; each leg's F27 slot is its own, fixed at its own settle, and the
    # fixed leg is the trade's once: a pair whose NPV nets to nothing still has its two sides.
    c = futures("C", 2_500.0, 0.0, 0.0)
    batch = booked(LIFECYCLE, F27, (A, c))
    a, other = batch.encoded.legs
    np.testing.assert_array_equal(a.slot_date, other.slot_date)
    assert a.slot_group.size == 1 and other.slot_group.size == 1
    close(batch.encoded.offset, [-30_000.0])  # -10,000 at the outright 3.00, the trade's
    close(batch.encoded.offset_of_group, [-30_000.0])
    hist_a = history_on(A, "2026-12-30", {"F27": 3.55})
    hist_c = history_on(c, "2026-12-30", {"F27": 3.45})
    prep = prepared_trades(batch.encoded, (hist_c, hist_a), WorkCounter())  # any order
    assert prep.legs[0].history is hist_a and prep.legs[1].history is hist_c
    close(prep.legs[0].set_amount, [35_500.0])
    close(
        prep.legs[1].set_amount, [34_500.0]
    )  # each leg's own, never summed apart from the payment
    # A payment of nothing: A at 3.50 and B at -0.50 make the outright 3.00 exactly; the two
    # sides and the deltas stand while the value is zero.
    nothing = valued(booked(), quotes_b=(-0.48, -0.50, -0.52))
    assert nothing.mark == 0.0 and nothing.dv01 == 0.0
    close(nothing.legs[0].dated_live_contribution, [35_000.0])
    close(nothing.legs[1].dated_live_contribution, [-5_000.0])
    assert nothing.legs[0].delta_total == pytest.approx(0.95, **CLOSE)
    assert nothing.legs[1].delta_total == pytest.approx(3.8, **CLOSE)


def test_a_strip_pays_each_month_from_its_later_observation_or_all_on_one_date() -> None:
    strip: dict[str, list[object]] = {**TICKET, "contract_code": ["F27-H27"]}
    ruled = booked(LIFECYCLE, strip).resolved
    assert ruled.payment is not None
    # F27: 4 January 2027 is the later, paying the 6th; G27: 1 February, the 3rd; H27: 1 March,
    # the 3rd; three groups, one a month.
    np.testing.assert_array_equal(
        ruled.payment.date, dates("2027-01-06", "2027-02-03", "2027-03-03")
    )
    dated = booked({**BILATERAL, "payment_day": day("2027-06-01")}, strip)
    assert dated.resolved.payment is not None
    np.testing.assert_array_equal(dated.resolved.payment.date, [day("2027-06-01")] * 3)
    assert dated.encoded.offset_of_group.size == 3
    results = valued(
        dated,
        "2026-12-28",
        finals_a={},
        quotes_a=(3.50, 3.60, 3.70),
        quotes_b=(-0.40, -0.42, -0.44),
        curve=curve_of(("2026-12-28", 1.0), ("2027-06-01", 0.97), ("2027-12-31", 0.95)),
    )
    close(results.payment_factor, [0.97] * 3)
    # 3.50 less 0.40, 3.60 less 0.42 and 3.70 less 0.44, each less the outright 3.00.
    close(results.payment_amount, [1000.0, 1800.0, 2600.0])


def test_different_methods_on_the_two_legs_each_observe_their_own_days() -> None:
    # A averages February's pricing days, 20 of them; B publishes on 1 February; the later
    # observation is A's 26 February, and the pair pays two business days after it, 2 March.
    batch = booked({**LIFECYCLE, "schedule_method": "asian"})
    a, b = batch.encoded.legs
    pricing_days = int(np.busday_count("2027-02-01", "2027-03-01"))
    assert pricing_days == 20
    assert a.slot_date.size == pricing_days and b.slot_date.size == 1
    assert batch.resolved.payment is not None
    np.testing.assert_array_equal(batch.resolved.payment.date, dates("2027-03-02"))


def test_a_batch_equals_its_singleton_rows_and_a_duplicate_counts_twice() -> None:
    rows: dict[str, list[object]] = {
        "trade_id": [1, 2],
        "trade_date": ["2026-12-15", "2026-12-16"],
        "contract_code": ["G27", "H27"],
        "quantity": [10_000, -5_000],
        "fixed_price": [3.00, 3.05],
    }
    both = valued(booked(ticket=rows))
    first = valued(booked(ticket={k: [v[0]] for k, v in rows.items()}))
    second = valued(booked(ticket={k: [v[1]] for k, v in rows.items()}))
    assert both.mark == pytest.approx(first.mark + second.mark, **CLOSE)
    assert both.dv01 == pytest.approx(first.dv01 + second.dv01, **CLOSE)
    for k in range(2):
        assert both.legs[k].nominal_delta_total == pytest.approx(
            first.legs[k].nominal_delta_total + second.legs[k].nominal_delta_total, **CLOSE
        )
    twice = valued(booked(ticket={k: [v[0], v[0]] for k, v in rows.items()}))
    assert twice.mark == pytest.approx(2 * first.mark, **CLOSE)
    assert twice.legs[1].nominal_delta_total == pytest.approx(
        2 * first.legs[1].nominal_delta_total, **CLOSE
    )


def test_calday_and_zero_quantities_hold_on_both_legs() -> None:
    daily = valued(booked({**BILATERAL, "quantity_per": "calday"}))
    # G27 covers February's 28 days: 280,000 MMBTU at 3.10 less 3.00, discounted at 0.95.
    close(daily.payment_amount, [28_000.0])
    assert daily.mark == pytest.approx(28_000.0 * 0.95, **CLOSE)
    assert daily.legs[1].nominal_delta_total == pytest.approx(112.0, **CLOSE)
    zero = valued(booked(ticket={**TICKET, "quantity": [0]}))
    assert zero.mark == 0.0 and zero.dv01 == 0.0
    assert zero.legs[0].nominal_delta_total == 0.0 and zero.legs[1].nominal_delta_total == 0.0


# --- order, identity and fees --------------------------------------------------------------------


def test_the_pair_books_a_cva_reserve_once_per_row_though_it_has_two_legs() -> None:
    # cva-reserve.md: the row's signed amount once, the legs apart; a reserve enters no number.
    batch = booked(ticket={**TICKET, "cva_reserve": [-40.0]})
    assert (batch.encoded.reserves.marketing, batch.encoded.reserves.cva) == (0.0, -40.0)
    results = valued(batch)
    assert results.reserves is batch.encoded.reserves
    assert results.mark == valued(booked()).mark
    both = booked(ticket={**TICKET, "marketing_reserve": [15.0], "cva_reserve": [-40.0]})
    assert (both.encoded.reserves.marketing, both.encoded.reserves.cva) == (15.0, -40.0)


def test_histories_and_markets_match_the_legs_by_identity_whatever_their_order() -> None:
    batch = booked()
    hist_a, hist_b = histories()
    forward = prepared_trades(batch.encoded, (hist_a, hist_b), WorkCounter())
    backward = prepared_trades(batch.encoded, (hist_b, hist_a), WorkCounter())
    assert backward.legs[0].history is hist_a and backward.legs[1].history is hist_b
    market_a, market_b = quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42)
    one = trade_results(forward, (market_a, market_b), WorkCounter(), curve_set(SOFR))
    other = trade_results(backward, (market_b, market_a), WorkCounter(), curve_set(SOFR))
    assert one.mark == other.mark and one.dv01 == other.dv01
    for mine, theirs in zip(one.legs, other.legs, strict=True):
        assert mine.delta_total == theirs.delta_total
        assert mine.market is theirs.market and mine.prepared.history is theirs.prepared.history


def test_reversing_the_indexes_with_their_prices_keeps_the_values_and_moves_the_fees() -> None:
    brokered = {**BILATERAL, "broker": "ICAP"}
    forward = booked(brokered)
    backward = booked(brokered, TICKET, (B, A))  # the one price is the deal's, whatever the order
    assert backward.resolved.descriptor == "B+A"
    hist_a, hist_b = histories()
    one = trade_results(
        prepared_trades(forward.encoded, (hist_a, hist_b), WorkCounter()),
        (quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42)),
        WorkCounter(),
        curve_set(SOFR),
    )
    other = trade_results(
        prepared_trades(backward.encoded, (hist_a, hist_b), WorkCounter()),
        (quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42)),
        WorkCounter(),
        curve_set(SOFR),
    )
    assert one.mark == pytest.approx(other.mark, **CLOSE)
    assert one.dv01 == pytest.approx(other.dv01, **CLOSE)
    assert one.legs[0].delta_total == pytest.approx(other.legs[1].delta_total, **CLOSE)
    assert one.legs[1].delta_total == pytest.approx(other.legs[0].delta_total, **CLOSE)
    # The first leg's specification charges the brokerage: a cent a MMBTU on A, half a dollar
    # on B; the second index's rates are never read.
    assert forward.encoded.reserves.brokerage == pytest.approx(100.0, **CLOSE)
    assert backward.encoded.reserves.brokerage == pytest.approx(5000.0, **CLOSE)
    alone = booked(
        {k: v for k, v in brokered.items() if k != "second_schedule_method"}, TICKET, (A,)
    )
    assert alone.encoded.reserves == forward.encoded.reserves


def test_a_single_index_batch_is_as_it_was() -> None:
    one = {k: v for k, v in BILATERAL.items() if k != "second_schedule_method"}
    batch = booked(one, {**TICKET, "fixed_price": [3.30]}, (A,))
    assert batch.resolved.descriptor == "A" and len(batch.encoded.legs) == 1
    close(batch.resolved.price, [3.3])
    close(batch.encoded.offset, [-33_000.0])
    hist_a = history_on(A, AS_OF, {"F27": 3.55})
    prep = prepared_trades(batch.encoded, (hist_a,), WorkCounter())
    results = trade_results(prep, (quoted(hist_a, 3.50, 3.60),), WorkCounter(), curve_set(SOFR))
    (leg,) = results.legs
    assert results.mark == pytest.approx(1900.0, **CLOSE)
    close(results.payment_amount, [2000.0])
    assert leg.nominal_delta_total == pytest.approx(1.0, **CLOSE)


# --- the rules of the pair -----------------------------------------------------------------------


def test_the_second_legs_method_is_present_exactly_with_two_indexes_and_no_second_price() -> None:
    without = {k: v for k, v in BILATERAL.items() if k != "second_schedule_method"}
    assert refused(without) == "second_schedule_method is missing, expected it with two indexes"
    assert refused(BILATERAL, TICKET, (A,)) == (
        "second_schedule_method is 'lastday', expected none unless two indexes"
    )
    assert refused(indexes=(A, B, A)) == (
        "indexes are 3, expected one or two; a batch is on one index or, since "
        "two-index-fixed-float.md, on a pair"
    )
    # Since two-index-one-price.md the fixed_float has no second price: not a field of the
    # definition, so the sheet refuses it at the header as any unknown name, below.
    assert "second_fixed_price" not in {field.name for field in FIXED_FLOAT.fields}


def test_the_pair_is_two_distinct_indexes_of_one_quoting_on_a_financial_settlement() -> None:
    assert refused(indexes=(A, A)) == (
        "index 2 is index 1, 'A', again, expected two distinct indexes; a pair of one index is "
        "outside this version"
    )
    assert refused(indexes=(A, futures("A", 2_500.0, 0.0, 0.0))) == (
        "index 2 is another index named 'A', the name of index 1, expected one index for one name"
    )
    assert refused(indexes=(A, iferc("B", 2_500.0, "CENT"))) == (
        "index 2 'B' quotes in CENT per MMBTU and settles in DOLLAR, expected DOLLAR per MMBTU "
        "settled in DOLLAR as index 1 'A'; two legs' prices add in one unit"
    )
    physical = {
        k: v for k, v in CLEARED.items() if k not in ("payment_day", "payment_holiday_calendar")
    } | {"settlement_method": "physical"}
    assert refused(physical) == (
        "settlement_method is 'physical', expected 'financial' with two indexes; a two-index "
        "physical settlement is outside this version"
    )
    assert refused({**BILATERAL, "second_schedule_method": "asian"}) == (
        "second_schedule_method of trade 1 at row 1 is 'asian', expected 'lastday' on an IFERC "
        "index; an IFERC month has one index, published once"
    )


def test_the_quantity_unit_names_one_quantity_on_both_indexes() -> None:
    # A LOT of 10,000 MMBTU on A against one of 2,500 on B is refused whatever the row's
    # quantity, zero included; a THERM on one index and 100,000 BTU on the other are one
    # quantity to the roundoff of their conversions, 0.1 against 0.09999999999999999 MMBTU.
    ambiguous = (
        "quantity_unit 'LOT' of trade 1 at row 1 is 10000.0 MMBTU on index 'A' and 2500.0 MMBTU "
        "on index 'B', expected one quantity per entered unit on both legs"
    )
    assert refused({**BILATERAL, "quantity_unit": "LOT"}) == ambiguous
    assert refused({**BILATERAL, "quantity_unit": "LOT"}, {**TICKET, "quantity": [0]}) == ambiguous
    heated = {**BILATERAL, "quantity_unit": "HEAT"}
    by_therm = futures("A", 10_000.0, 0.01, 0.005, spec=("HEAT", 1.0, "THERM"))
    by_btu = iferc("B", 2_500.0, spec=("HEAT", 100_000.0, "BTU"))
    batch = booked(heated, {**TICKET, "quantity": [1]}, (by_therm, by_btu))
    a, b = batch.encoded.legs
    assert a.quote_quantity[0] == pytest.approx(0.1, rel=1e-12)
    assert b.quote_quantity[0] == pytest.approx(0.1, rel=1e-12)
    assert a.quote_quantity[0] != b.quote_quantity[0]  # the roundoff the rule allows for
    # A zero row with one quantity on both legs is kept, ready for a deal, as a one-index zero is.
    kept = booked(ticket={**TICKET, "quantity": [0]})
    assert kept.encoded.legs[0].quote_quantity.tolist() == [0.0]
    assert kept.encoded.legs[1].quote_quantity.tolist() == [0.0]
    assert refused({**BILATERAL, "quantity_unit": "THERM10"}) == (
        "quantity_unit is 'THERM10', expected one of the specifications of index 'B': 'LOT', "
        "'MMBTU'"
    )
    assert refused(ticket={**TICKET, "contract_code": ["X26"]}) == (
        "contract_code row 1 is 'X26', expected months the schedule of index 'B' has a contract "
        "for; it has none for 2026-11"
    )


def test_the_histories_and_the_markets_are_one_per_leg_of_the_pair() -> None:
    batch = booked()
    hist_a, hist_b = histories()
    c = futures("C", 2_500.0, 0.0, 0.0)
    with pytest.raises(ValueError) as refusal:
        prepared_trades(batch.encoded, (hist_a,), WorkCounter())
    assert str(refusal.value) == "histories are 1, expected 2, one per leg of the trades"
    with pytest.raises(ValueError) as refusal:
        prepared_trades(batch.encoded, (hist_a, history_on(c, AS_OF, {"F27": 3.55})), WorkCounter())
    assert str(refusal.value) == (
        "history 2 is over another index, 'C', expected the trades', 'A' and 'B'"
    )
    with pytest.raises(ValueError) as refusal:
        prepared_trades(batch.encoded, (hist_a, history_on(A, AS_OF, {})), WorkCounter())
    assert str(refusal.value) == (
        "history 2 is over index 'A' as history 1 is, expected one history per index of the trades"
    )
    with pytest.raises(ValueError) as refusal:
        prepared_trades(
            batch.encoded, (hist_a, waha_history("2027-01-05", {"Z26": -0.30, "F27": -0.35}, B)),
            WorkCounter(),
        )  # fmt: skip
    assert str(refusal.value) == (
        "the history of index 'B' is valued on 2027-01-05, expected 2027-01-04, the valuation "
        "day of the history of index 'A'; the trades are prepared on one day"
    )
    prep = prepared_trades(batch.encoded, (hist_a, hist_b), WorkCounter())
    market_a = quoted(hist_a, 3.50, 3.60)
    with pytest.raises(ValueError) as refusal:
        trade_results(prep, (market_a,), WorkCounter(), curve_set(SOFR))
    assert str(refusal.value) == "markets are 1, expected 2, one per leg of the trades"
    with pytest.raises(ValueError) as refusal:
        trade_results(
            prep,
            (market_a, quoted(waha_history(AS_OF, {"Z26": -0.30}, B), -0.38, -0.40, -0.42)),
            WorkCounter(),
            curve_set(SOFR),
        )
    assert str(refusal.value) == (
        "market 2 is over another history of index 'B', expected the ones the trades were "
        "prepared against, of 'A' and 'B'"
    )
    with pytest.raises(ValueError) as refusal:
        trade_results(prep, (market_a, market_a), WorkCounter(), curve_set(SOFR))
    assert str(refusal.value) == (
        "market 2 is over the history of index 'A' as market 1 is, expected one market per "
        "history of the trades"
    )


def test_the_pairs_counts_are_each_legs_observations_and_slots_and_the_trades_groups() -> None:
    counter = WorkCounter()
    trades((A, B), a_ticket(TICKET), a_template(BILATERAL), UNITS, counter)
    counts = counter.freeze()
    assert counts["resolved_occurrences"] == 1 and counts["resolved_components"] == 1
    assert counts["schedule_codes_read"] == 11  # A's six and B's five
    assert counts["encoded_components"] == 2
    assert counts["encoded_groups"] == 1
    assert counts["encoded_observations"] == 2 and counts["encoded_slots"] == 2
    tick = WorkCounter()
    results = valued(booked(), counter=tick)
    ticked = tick.freeze()
    assert ticked["live_prices_read"] == 2
    assert ticked["groups_valued"] == 1
    assert ticked["slots_discounted"] == 2 and ticked["slots_weighted"] == 2
    assert ticked["risk_reductions"] == 20  # eight a leg and four for the trade
    assert ticked["payment_factors_read"] == 1  # one factor serves both legs
    assert isinstance(results, TradeResults)


def test_a_prepared_pair_settles_a_group_only_when_both_legs_have_fixed() -> None:
    batch = booked(LIFECYCLE, F27)
    prep: PreparedTrades = prepared_trades(
        batch.encoded,
        histories("2027-01-04", {"F27": 3.55}, {"Z26": -0.30}),
        WorkCounter(),
    )
    # 4 January: A has fixed, B publishes today and is live; the common payment is unpaid.
    assert prep.legs[0].is_fixed.tolist() == [True]
    assert prep.legs[1].is_fixed.tolist() == [False]
    assert prep.is_settled.tolist() == [False]
    assert isinstance(prep.legs[1].history, MarketHistory)
    market: Market = quoted(prep.legs[0].history, 3.60, 3.70)
    assert market.market_history is prep.legs[0].history


# --- the pair's report and its collection --------------------------------------------------------


def one_index(
    ix: Index,
    fixed_price: float,
    template: Mapping[str, object] = BILATERAL,
    quantity: float = 10_000,
) -> Trades:
    """A single-index batch of the hand table's row on one index at its own fixed price."""
    shared = {k: v for k, v in template.items() if k != "second_schedule_method"}
    rows: dict[str, list[object]] = dict(TICKET)
    rows["fixed_price"] = [fixed_price]
    rows["quantity"] = [quantity]
    return booked(shared, rows, (ix,))


def valued_one(
    batch: Trades, quotes: tuple[float, ...], curve: DiscountCurve | None = SOFR
) -> TradeResults:
    """A single-index batch valued against its own history and market on the hand table's day."""
    ix = batch.resolved.legs[0].index
    history = (
        history_on(A, AS_OF, {"F27": 3.55}) if ix is A else waha_history(AS_OF, {"Z26": -0.30}, B)
    )
    prep = prepared_trades(batch.encoded, (history,), WorkCounter())
    return trade_results(
        prep,
        (quoted(history, *quotes),),
        WorkCounter(),
        None if curve is None else curve_set(curve),
    )


@pytest.mark.parametrize("cleared", [False, True], ids=["bilateral", "cleared"])
def test_a_pairs_report_reads_as_the_collection_of_its_legs(cleared: bool) -> None:
    # Every risk by every bucket: the pair's report and the collection of the two legs booked
    # and valued apart have the same labels, dates, Totals and columns, two commodity groups and
    # one DV01 column, never a combined-index column. The singles book A at 3.30 and B at -0.30,
    # one split of the outright 3.00: no column depends on the split, so any split reads alike.
    template, curve = (CLEARED, None) if cleared else (BILATERAL, SOFR)
    pair = valued(booked(template), curve=curve)
    legs = aggregate_results(
        (
            valued_one(one_index(A, 3.30, template), (3.50, 3.60), curve),
            valued_one(one_index(B, -0.30, template), (-0.38, -0.40, -0.42), curve),
        ),
        WorkCounter(),
    )
    for risk in Risk:
        for bucket in Bucket:
            same_view(pair.report(risk, bucket), legs.report(risk, bucket))
    everything = pair.report(Risk.ALL, Bucket.DAY)
    assert everything.labels[:4] == (
        "A nominal_delta [LOT]",
        "A delta [LOT]",
        "B nominal_delta [LOT]",
        "B delta [LOT]",
    )
    assert everything.labels[4] == ("cleared USD dv01" if cleared else "SOFR USD dv01") + (
        " [DOLLAR per basis point]"
    )
    assert len(everything.labels) == 7  # the two pairs, one DV01 column and a cross-gamma a leg


def pair_beside_alone() -> tuple[TradeResults, TradeResults]:
    """The ticket's pair beside an A-alone batch of 5,000 MMBTU at 3.40, the two valued on one
    history, one market and one curve set of A, as a collection takes them."""
    hist_a, hist_b = histories()
    market_a, market_b = quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42)
    curves = curve_set(SOFR)
    pair = trade_results(
        prepared_trades(booked().encoded, (hist_a, hist_b), WorkCounter()),
        (market_a, market_b),
        WorkCounter(),
        curves,
    )
    alone = trade_results(
        prepared_trades(one_index(A, 3.40, quantity=5_000).encoded, (hist_a,), WorkCounter()),
        (market_a,),
        WorkCounter(),
        curves,
    )
    return pair, alone


def test_the_pair_collects_with_a_single_index_source_and_a_cashflow() -> None:
    # The ticket's case: the pair beside an A-alone result of 5,000 MMBTU at 3.40 against 3.50,
    # amount 500, mark 475, nominal delta 0.5 A lots, delta 0.475 and DV01 -0.0475 on the same
    # payment day, market and curve objects: A totals 1.5 and 1.425, B stays 4 and 3.8, SOFR's
    # DV01 is -0.1425; a cashflow on SOFR moves that rate column alone; no combined total is
    # added on top of the legs.
    pair, alone = pair_beside_alone()
    assert alone.mark == pytest.approx(475.0, **CLOSE)
    assert alone.legs[0].nominal_delta_total == pytest.approx(0.5, **CLOSE)
    assert alone.dv01 == pytest.approx(-0.0475, **CLOSE)
    together = aggregate_results((pair, alone), WorkCounter())
    a_group, b_group = together.index_groups
    assert a_group.index is A and b_group.index is B
    assert a_group.occurrences.tolist() == [0, 1] and b_group.occurrences.tolist() == [0]
    assert a_group.nominal_delta_total == pytest.approx(1.5, **CLOSE)
    assert a_group.delta_total == pytest.approx(1.425, **CLOSE)
    assert b_group.nominal_delta_total == pytest.approx(4.0, **CLOSE)
    assert b_group.delta_total == pytest.approx(3.8, **CLOSE)
    (sofr,) = together.rate_groups
    assert sofr.curve is SOFR and sofr.dv01 == pytest.approx(-0.1425, **CLOSE)
    assert sofr.occurrences.tolist() == [0, 1]
    assert [(c.index.name, c.word) for c in together.cross_groups] == [("A", "SOFR"), ("B", "SOFR")]
    assert together.cross_groups[0].cross_gamma_total == pytest.approx(-0.0001425, **CLOSE)
    assert together.cross_groups[1].cross_gamma_total == pytest.approx(-0.00038, **CLOSE)
    view = together.report(Risk.ALL, Bucket.DAY)
    assert len(view.labels) == 7
    assert column(view, "SOFR USD dv01 [DOLLAR per basis point]")[0] == pytest.approx(
        -0.1425, **CLOSE
    )
    # A cashflow of 1,000 USD on the payment day, valued on SOFR: -0.095 of DV01 more on the
    # SOFR column and nothing else moved.
    cash = cashflow_results(
        cashflows(
            a_ticket(
                {"trade_date": ["2026-12-15"], "amount": [1_000.0], "payment_day": [PAY]},
                CASHFLOW,
            ),
            a_template({"currency": "USD", "discount_curve_key": "SOFR"}, CASHFLOW),
            UNITS,
            WorkCounter(),
        ),
        valuation_date(day(AS_OF), 0.5),
        collect_discount_curves((SOFR,), WorkCounter()),
        WorkCounter(),
    )
    with_cash = aggregate_results((pair, alone, cash), WorkCounter())
    assert [g.nominal_delta_total for g in with_cash.index_groups] == pytest.approx(
        [1.5, 4.0], **CLOSE
    )
    assert with_cash.rate_groups[0].dv01 == pytest.approx(-0.1425 - 0.095, **CLOSE)
    assert with_cash.rate_groups[0].occurrences.tolist() == [0, 1, 2]
    assert len(with_cash.cross_groups) == 2


def test_a_repeated_pair_counts_twice_in_a_collection() -> None:
    pair = valued(booked())
    twice = aggregate_results((pair, pair), WorkCounter())
    a_group, b_group = twice.index_groups
    assert a_group.occurrences.tolist() == [0, 1] and b_group.occurrences.tolist() == [0, 1]
    assert a_group.nominal_delta_total == pytest.approx(2.0, **CLOSE)
    assert b_group.nominal_delta_total == pytest.approx(8.0, **CLOSE)
    assert twice.rate_groups[0].dv01 == pytest.approx(-0.19, **CLOSE)


def test_the_pairs_day_axes_unite_the_legs_observation_days() -> None:
    # A's G27 expires 27 January and B's G27 publishes 1 February: two days, each leg on its
    # own, and with the payment day a union of three for the report of every risk by day.
    batch = booked()
    pair = batch.encoded.pair
    assert pair is not None
    np.testing.assert_array_equal(pair.days, dates("2027-01-27", "2027-02-01"))
    assert [places.tolist() for places in pair.day_in] == [[0], [1]]
    axes = batch.encoded.payment_axes
    assert axes is not None
    np.testing.assert_array_equal(axes.union_days, dates("2027-01-27", "2027-02-01", PAY))
    assert [leg.day_in_union.tolist() for leg in batch.encoded.legs] == [[0], [1]]  # type: ignore[union-attr]
    assert axes.paid_in_days.tolist() == [2]
    assert booked(CLEARED).encoded.legs[0].day_in_union is None
    assert one_index(A, 3.30).encoded.pair is None


# --- the readbacks of a pair ----------------------------------------------------------------------


def grid(obj: object) -> list[list[object]]:
    """A readback as the sheet shows it: the headings, the types and the body rows."""
    table = shown(obj)
    return rows((table.kinds, table.numeric_slots, "\0".join(table.texts)))


def cell(table: list[list[object]], row: int, name: str) -> object:
    """A body row's cell under a heading, the body counted from zero."""
    return table[2 + row][table[0].index(name)]


def test_the_created_pair_reads_back_one_price_and_one_fixed_leg() -> None:
    table = grid(booked())
    assert len(table) == 3
    headings = table[0]
    assert headings.index("second_schedule_method") == headings.index("schedule_method") + 1
    for name in ("second_fixed_price", "combined_fixed_price", "second_offset"):
        assert name not in headings, name  # since two-index-one-price.md no column is a leg's price
    assert cell(table, 0, "schedule_method") == "lastday"
    assert cell(table, 0, "second_schedule_method") == "lastday"
    assert cell(table, 0, "fixed_price") == 3.0
    assert cell(table, 0, "offset") == pytest.approx(-30_000.0, **CLOSE)
    one = grid(one_index(A, 3.30))
    assert "second_schedule_method" not in one[0]
    assert len(one[0]) == len(headings) - 1


def test_the_prepared_and_valued_pair_read_back_one_row_per_slot_naming_its_leg() -> None:
    batch = booked()
    hist_a, hist_b = histories()
    prep = prepared_trades(batch.encoded, (hist_a, hist_b), WorkCounter())
    slots = grid(prep)
    assert slots[0][:5] == [
        "leg",
        "index",
        "pricing_contract",
        "booked_period",
        "observation_date",
    ]
    assert slots[1][:2] == ["int64", "str"]
    assert [row[:2] for row in slots[2:]] == [[1.0, "A"], [2.0, "B"]]
    assert (
        cell(slots, 0, "pricing_contract") == "G27" and cell(slots, 1, "pricing_contract") == "G27"
    )
    assert cell(slots, 0, "is_fixed") == 0.0 and cell(slots, 1, "is_settled") == 0.0
    assert cell(slots, 0, "live_lots") == pytest.approx(1.0, **CLOSE)  # 10,000 MMBTU in A lots
    assert cell(slots, 1, "live_lots") == pytest.approx(4.0, **CLOSE)  # and in B's
    results = trade_results(
        prep,
        (quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42)),
        WorkCounter(),
        curve_set(SOFR),
    )
    table = grid(results)
    assert len(table) == 4 and [row[:2] for row in table[2:]] == [[1.0, "A"], [2.0, "B"]]
    # The group's facts once, on its first row of all, the swap's and under no index; the
    # payment factor on every row; no column a leg's value since two-index-one-price.md.
    assert cell(table, 0, "payment_amount") == pytest.approx(1000.0, **CLOSE)
    assert cell(table, 1, "payment_amount") == "-"
    assert cell(table, 0, "group_npv") == pytest.approx(950.0, **CLOSE)
    assert cell(table, 0, "group_dv01") == pytest.approx(-0.095, **CLOSE)
    assert cell(table, 0, "payment_factor") == 0.95 and cell(table, 1, "payment_factor") == 0.95
    for name in ("leg_amount", "leg_npv", "leg_group_dv01", "leg_mark", "leg_cash", "leg_dv01"):
        assert name not in table[0], name
    assert cell(table, 0, "brokerage_reserve") == 0.0 and cell(table, 1, "brokerage_reserve") == "-"
    assert cell(table, 0, "contract_cross_gamma") == pytest.approx(-0.000095, **CLOSE)
    assert cell(table, 1, "contract_cross_gamma") == pytest.approx(-0.00038, **CLOSE)
    assert cell(table, 1, "cross_gamma_unit") != cell(table, 0, "cross_gamma_unit")
    assert cell(table, 0, "discount_curve") == "SOFR" and cell(table, 1, "discount_curve") == "SOFR"
    # Since observation-prices-readback.md each leg's slot shows its own price facts, last:
    # A's 10,000 of coefficient at G27's 3.50, 35,000 of contribution, and B's at -0.40,
    # -4,000, each in its index's quote unit.
    assert cell(table, 0, "observation_coefficient") == 10_000.0
    assert cell(table, 1, "observation_coefficient") == 10_000.0
    assert cell(table, 0, "observation_price") == 3.50
    assert cell(table, 1, "observation_price") == -0.40
    assert cell(table, 0, "price_unit") == "DOLLAR/MMBTU"
    assert cell(table, 1, "price_unit") == "DOLLAR/MMBTU"
    assert cell(table, 0, "floating_contribution") == pytest.approx(35_000.0, **CLOSE)
    assert cell(table, 1, "floating_contribution") == pytest.approx(-4_000.0, **CLOSE)
    headings = table[0]
    assert headings[-5:] == [
        "observation_coefficient",
        "observation_price",
        "price_unit",
        "floating_contribution",
        "currency_unit",  # the batch's, once, since currency-and-currency-unit.md
    ]
    assert [cell(table, r, "currency_unit") for r in range(2)] == ["DOLLAR", "-"]
    assert headings.index("brokerage_reserve") == headings.index("group_dv01") + 1
    # A cleared pair: the group facts are none, a dash on every row.
    cleared = grid(valued(booked(CLEARED), curve=None))
    assert cell(cleared, 0, "payment_amount") == "-" and cell(cleared, 1, "group_dv01") == "-"
    # A single index reads back as it did: no leg column.
    one = grid(valued_one(one_index(A, 3.30), (3.50, 3.60)))
    assert one[0][0] == "pricing_contract" and "leg" not in one[0] and len(one) == 3


def test_a_collections_readback_has_a_row_for_the_swap_and_a_row_per_leg() -> None:
    # Since two-index-one-price.md the pair's DV01 sits on a row of its own, named by the
    # handle's descriptor, and each leg's row carries its index's commodity risk alone; the
    # A-alone source keeps its one row with everything on it.
    pair, alone = pair_beside_alone()
    table = grid(aggregate_results((pair, alone), WorkCounter()))
    assert len(table) == 6
    assert [cell(table, r, "position") for r in range(4)] == [1.0, 1.0, 1.0, 2.0]
    assert [cell(table, r, "index") for r in range(4)] == ["A+B", "A", "B", "A"]
    assert [cell(table, r, "reporting_lot") for r in range(4)] == ["-", "LOT", "LOT", "LOT"]
    assert cell(table, 0, "nominal_delta") == "-" and cell(table, 0, "delta") == "-"
    assert [cell(table, r, "nominal_delta") for r in (1, 2, 3)] == pytest.approx([1.0, 4.0, 0.5])
    assert cell(table, 0, "dv01") == pytest.approx(-0.095, **CLOSE)
    assert cell(table, 1, "dv01") == "-" and cell(table, 2, "dv01") == "-"
    assert cell(table, 3, "dv01") == pytest.approx(-0.0475, **CLOSE)
    assert [cell(table, r, "route") for r in range(4)] == ["bilateral"] * 4
    assert [cell(table, r, "curve") for r in range(4)] == ["SOFR"] * 4
    assert cell(table, 0, "cross_gamma") == "-" and cell(table, 0, "cross_gamma_unit") == "-"
    assert cell(table, 2, "cross_gamma") == pytest.approx(-0.00038, **CLOSE)
    assert cell(table, 3, "cross_gamma") == pytest.approx(-0.0000475, **CLOSE)


# --- the pair on the sheet -----------------------------------------------------------------


SEAM = {
    name: bridge.entry(name)
    for name in (
        "_CreateFuturesSchedule",
        "_CreateIfercSchedule",
        "_CreateHolidayCalendar",
        "_CreateIndexConventions",
        "_CreateContractSpecifications",
        "_CreateIndex",
        "_CreateValuationDate",
        "_CreateCalendar",
        "_CreateFuturesFixings",
        "_CreateIfercFixings",
        "_CreateMarketHistory",
        "_CreatePriceVector",
        "_CreateMarket",
        "_CreateDiscountCurve",
        "_CollectDiscountCurves",
        "_CreateTradeTemplate",
        "_CreateTrades",
        "_PrepareTrades",
        "_EvaluateTrades",
        "_ReportValues",
        "_ReportRisk",
        "util_ReadHandle",
    )
}
PID = os.getpid()


def serial(text: str) -> float:
    """A day as the sheet counts it, days since 30 December 1899."""
    return float((np.datetime64(text, "D") - np.datetime64("1899-12-30", "D")).astype(np.int64))


def down(*values: object) -> Cells:
    """A column of cells, as the host sends one."""
    return Cells.from_rows([[value] for value in values])


def across(*values: object) -> Cells:
    """A row of cells, as the host sends one."""
    return Cells.from_rows([list(values)])


def spilled(result: object) -> list[list[object]]:
    """A spill as the sheet shows it, every text and number in its cell."""
    kinds, slots, text = cast(tuple[NDArray[np.uint8], NDArray[np.float64], str], result)
    texts = iter(text.split("\0"))
    return [
        [
            next(texts) if kinds[r, c] == bridge.TEXT_CODE else slots[r, c]
            for c in range(kinds.shape[1])
        ]
        for r in range(kinds.shape[0])
    ]


def read(handle: object) -> list[list[object]]:
    return spilled(SEAM["util_ReadHandle"](handle))


def under(table: list[list[object]], heading: str) -> list[object]:
    """A readback's body cells under a heading."""
    at = table[0].index(heading)
    return [line[at] for line in table[2:]]


def the_sheet() -> dict[str, Any]:
    """The ticket's pair on a sheet, the host test's cells: A a futures index over F27, G27 and
    H27, 1 January 2027 closed, and B an IFERC index over Z26 to J27, both defining the NYMEX NG
    lot of 10,000 MMBTU; valued on 4 January 2027, A's two December settles and B's Z26 index
    behind the histories, A quoted 3.50 and 3.60 and B -0.38, -0.40 and -0.42, SOFR at 0.95 a
    year on; a bilateral template carrying the second leg's method and the ticket's one row,
    G27 for one lot at the outright 3.00."""
    conventions = SEAM["_CreateIndexConventions"]("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU")
    specs = SEAM["_CreateContractSpecifications"](
        across("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        across("NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0),
    )
    holidays = SEAM["_CreateHolidayCalendar"](serial("2027-01-01"), bridge.MISSING)
    a_schedule = SEAM["_CreateFuturesSchedule"](
        down("F27", "G27", "H27"),
        down(serial("2026-12-29"), serial("2027-01-27"), serial("2027-02-24")),
        bridge.MISSING,
    )
    a = SEAM["_CreateIndex"](
        "A", "Pair leg A, a futures index", a_schedule, conventions, specs, holidays, "NYMEX NG"
    )
    b_schedule = SEAM["_CreateIfercSchedule"](
        down("Z26", "F27", "G27", "H27", "J27"),
        down(
            *(
                serial(d)
                for d in ("2026-12-01", "2027-01-04", "2027-02-01", "2027-03-01", "2027-04-01")
            )
        ),
    )
    b = SEAM["_CreateIndex"](
        "B",
        "Pair leg B, an IFERC index",
        b_schedule,
        conventions,
        specs,
        bridge.MISSING,
        "NYMEX NG",
    )
    date = SEAM["_CreateValuationDate"](serial(AS_OF), 0.5)
    hist_a = SEAM["_CreateMarketHistory"](
        SEAM["_CreateCalendar"](date, a),
        SEAM["_CreateFuturesFixings"](
            down(serial("2026-12-31"), serial("2026-12-30")), down(3.60, 3.58), a
        ),
    )
    hist_b = SEAM["_CreateMarketHistory"](
        SEAM["_CreateCalendar"](date, b), SEAM["_CreateIfercFixings"](down("Z26"), down(-0.30), b)
    )
    market_a = SEAM["_CreateMarket"](hist_a, SEAM["_CreatePriceVector"]("A", down(3.50, 3.60)))
    market_b = SEAM["_CreateMarket"](
        hist_b, SEAM["_CreatePriceVector"]("B", down(-0.38, -0.40, -0.42))
    )
    curves = SEAM["_CollectDiscountCurves"](
        SEAM["_CreateDiscountCurve"](
            "SOFR",
            across("date", "discount_factor"),
            Cells.from_rows([[serial(AS_OF), 1.0], [serial(PAY), 0.95]]),
        )
    )
    template = SEAM["_CreateTradeTemplate"](
        "fixed_float",
        across(
            "quantity_unit",
            "quantity_per",
            "settlement_frequency",
            "nearby",
            "schedule_method",
            "second_schedule_method",
            "route",
            "settlement_method",
            "counterparty",
            "discount_curve_key",
            "payment_day",
            "payment_holiday_calendar",
        ),
        across(
            "NYMEX NG",
            "month",
            "monthly",
            1.0,
            "lastday",
            "lastday",
            "bilateral",
            "financial",
            "ACME Trading",
            "SOFR",
            serial(PAY),
            holidays,
        ),
    )
    return {
        "a": a,
        "b": b,
        "hist_a": hist_a,
        "hist_b": hist_b,
        "market_a": market_a,
        "market_b": market_b,
        "curves": curves,
        "template": template,
        "headers": across("trade_id", "trade_date", "contract_code", "quantity", "fixed_price"),
        "row": across(1.0, serial("2026-12-15"), "G27", 1.0, 3.00),
        "holidays": holidays,
    }


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """The pair's sheet, made once for the module; the_sheet is the plain maker another test
    file books its own instrument over."""
    return the_sheet()


def test_the_sheet_books_a_pair_from_a_column_of_two_index_handles(sheet: dict[str, Any]) -> None:
    create = SEAM["_CreateTrades"]
    trades = create(down(sheet["a"], sheet["b"]), sheet["headers"], sheet["row"], sheet["template"])
    assert re.fullmatch(rf"{PID}:trades:A\+B:\d+", str(trades))
    table = read(trades)
    assert len(table) == 3
    assert under(table, "fixed_price") == [3.0]
    assert under(table, "second_schedule_method") == ["lastday"]
    assert under(table, "offset") == pytest.approx([-30_000.0], **CLOSE)
    assert "second_fixed_price" not in table[0] and "second_offset" not in table[0]
    # cva-reserve.md: a CVA column books the row's signed amount once, the row's two legs apart.
    marked = create(
        down(sheet["a"], sheet["b"]),
        across("trade_id", "trade_date", "contract_code", "quantity", "fixed_price", "cva_reserve"),
        across(1.0, serial("2026-12-15"), "G27", 1.0, 3.00, -40.0),
        sheet["template"],
    )
    assert under(read(marked), "cva_reserve") == [-40.0]
    # A row of two reads the same pair; the order entered is the legs' order and the handle's.
    assert re.fullmatch(
        rf"{PID}:trades:A\+B:\d+",
        str(
            create(
                across(sheet["a"], sheet["b"]), sheet["headers"], sheet["row"], sheet["template"]
            )
        ),
    )
    assert re.fullmatch(
        rf"{PID}:trades:B\+A:\d+",
        str(
            create(down(sheet["b"], sheet["a"]), sheet["headers"], sheet["row"], sheet["template"])
        ),
    )


def test_the_sheet_prepares_and_values_a_pair_from_ranges_in_either_order(
    sheet: dict[str, Any],
) -> None:
    trades = SEAM["_CreateTrades"](
        down(sheet["a"], sheet["b"]), sheet["headers"], sheet["row"], sheet["template"]
    )
    # The histories as a column with B first: matched to the legs by index, not by place.
    prepared = SEAM["_PrepareTrades"](trades, down(sheet["hist_b"], sheet["hist_a"]))
    assert re.fullmatch(rf"{PID}:prepared_trades:A\+B:\d+", str(prepared))
    slots = read(prepared)
    assert slots[0][:2] == ["leg", "index"] and slots[1][:2] == ["int64", "str"]
    assert under(slots, "leg") == [1.0, 2.0] and under(slots, "index") == ["A", "B"]
    assert under(slots, "live_lots") == pytest.approx([1.0, 1.0], **CLOSE)  # both lots 10,000
    # The markets as a row, A then B.
    results = SEAM["_EvaluateTrades"](
        prepared, across(sheet["market_a"], sheet["market_b"]), sheet["curves"]
    )
    assert re.fullmatch(rf"{PID}:trade_results:A\+B:\d+", str(results))
    values = spilled(SEAM["_ReportValues"](results))
    assert values[0][0] == "bilateral_mark"
    assert values[2][0] == pytest.approx(950.0, **CLOSE) and values[2][1] == 0.0
    risk = spilled(SEAM["_ReportRisk"](results, "all", "day"))
    assert risk[1][1:] == [
        "A nominal_delta [NYMEX NG]",
        "A delta [NYMEX NG]",
        "B nominal_delta [NYMEX NG]",
        "B delta [NYMEX NG]",
        "SOFR USD dv01 [DOLLAR per basis point]",
        "A SOFR cross_gamma [NYMEX NG per basis point]",
        "B SOFR cross_gamma [NYMEX NG per basis point]",
    ]
    assert risk[3][0] == "Total"
    assert risk[3][1:6] == pytest.approx([1.0, 0.95, 1.0, 0.95, -0.095], **CLOSE)
    table = read(results)
    assert under(table, "leg") == [1.0, 2.0] and under(table, "index") == ["A", "B"]
    assert under(table, "payment_amount")[0] == pytest.approx(1000.0, **CLOSE)
    assert under(table, "payment_amount")[1] == "-"
    assert under(table, "group_dv01")[0] == pytest.approx(-0.095, **CLOSE)
    assert "leg_dv01" not in table[0] and "leg_amount" not in table[0]
    # A single history and a single market in a cell, as every one-index sheet types them.
    alone = SEAM["_CreateTrades"](
        sheet["a"],
        across("trade_id", "trade_date", "contract_code", "quantity", "fixed_price"),
        across(2.0, serial("2026-12-15"), "G27", 1.0, 3.30),
        SEAM["_CreateTradeTemplate"](
            "fixed_float",
            across(
                "quantity_unit",
                "quantity_per",
                "settlement_frequency",
                "nearby",
                "schedule_method",
                "route",
                "settlement_method",
                "counterparty",
                "discount_curve_key",
                "payment_day",
                "payment_holiday_calendar",
            ),
            across(
                "NYMEX NG",
                "month",
                "monthly",
                1.0,
                "lastday",
                "bilateral",
                "financial",
                "ACME Trading",
                "SOFR",
                serial(PAY),
                SEAM["_CreateHolidayCalendar"](serial("2027-01-01"), bridge.MISSING),
            ),
        ),
    )
    assert re.fullmatch(rf"{PID}:trades:A:\d+", str(alone))
    one = SEAM["_EvaluateTrades"](
        SEAM["_PrepareTrades"](alone, sheet["hist_a"]), sheet["market_a"], sheet["curves"]
    )
    assert spilled(SEAM["_ReportValues"](one))[2][0] == pytest.approx(1900.0, **CLOSE)
    assert read(one)[0][0] == "pricing_contract"


def test_the_sheet_refuses_a_pairs_ranges_in_the_seams_words_and_the_kernels(
    sheet: dict[str, Any],
) -> None:
    create, prepare, evaluate = (
        SEAM["_CreateTrades"],
        SEAM["_PrepareTrades"],
        SEAM["_EvaluateTrades"],
    )
    a, b, headers, row, template = (
        sheet["a"],
        sheet["b"],
        sheet["headers"],
        sheet["row"],
        sheet["template"],
    )
    assert create(Cells.from_rows([[a, b], [a, b]]), headers, row, template) == (
        "#ERROR _CreateTrades: indexes is 2x2 array, expected one cell, one row or one column of "
        "index handles"
    )
    assert create(down(a, None), headers, row, template) == (
        "#ERROR _CreateTrades: indexes cell (2, 1) is blank, expected index handle"
    )
    assert create(across(a, sheet["hist_a"]), headers, row, template) == (
        f"#ERROR _CreateTrades: indexes cell (1, 2) is market history handle {sheet['hist_a']!r}, "
        "expected index handle"
    )
    assert create(bridge.MISSING, headers, row, template) == (
        "#ERROR _CreateTrades: indexes is missing, expected index handles in a cell, a row or a "
        "column"
    )
    assert create(a, headers, row, template) == (
        "#ERROR _CreateTrades: ValueError: second_schedule_method is 'lastday', expected none "
        "unless two indexes"
    )
    assert create(down(a, a), headers, row, template) == (
        "#ERROR _CreateTrades: ValueError: index 2 is index 1, 'A', again, expected two distinct "
        "indexes; a pair of one index is outside this version"
    )
    trades = create(down(a, b), headers, row, template)
    assert prepare(trades, sheet["hist_a"]) == (
        "#ERROR _PrepareTrades: ValueError: histories are 1, expected 2, one per leg of the trades"
    )
    assert prepare(trades, down(sheet["hist_a"], sheet["hist_a"])) == (
        "#ERROR _PrepareTrades: ValueError: history 2 is over index 'A' as history 1 is, expected "
        "one history per index of the trades"
    )
    assert prepare(trades, down(sheet["hist_a"], sheet["market_b"])) == (
        f"#ERROR _PrepareTrades: histories cell (2, 1) is market handle {sheet['market_b']!r}, "
        "expected market history handle"
    )
    prepared = prepare(trades, down(sheet["hist_a"], sheet["hist_b"]))
    assert evaluate(prepared, sheet["market_a"], sheet["curves"]) == (
        "#ERROR _EvaluateTrades: ValueError: markets are 1, expected 2, one per leg of the trades"
    )
    assert evaluate(prepared, down(sheet["market_a"], sheet["market_a"]), sheet["curves"]) == (
        "#ERROR _EvaluateTrades: ValueError: market 2 is over the history of index 'A' as market 1 "
        "is, expected one market per history of the trades"
    )
    assert evaluate(prepared, bridge.MISSING, sheet["curves"]) == (
        "#ERROR _EvaluateTrades: markets is missing, expected market handles in a cell, a row or a "
        "column"
    )


# --- the second price, no field since two-index-one-price.md -----------------------------------


FIELDS = (
    "trade_id, trade_date, contract_code, start_date, end_date, schedule_method, route, "
    "settlement_method, clearing_house, counterparty, discount_curve_key, broker, quantity, "
    "quantity_unit, quantity_per, fixed_price, second_schedule_method, payment_day, "
    "payment_holiday_calendar, marketing_reserve, cva_reserve, settlement_frequency, nearby"
)


def test_the_sheet_refuses_a_second_price_as_a_field_the_instrument_has_not(
    sheet: dict[str, Any],
) -> None:
    # A ticket or a template still typing second_fixed_price is refused at the header, in the
    # seam's words for any unknown field, the list no longer carrying it: no alias, no default
    # and no silent zero.
    headers = across(
        "trade_id", "trade_date", "contract_code", "quantity", "fixed_price", "second_fixed_price"
    )
    row = across(1.0, serial("2026-12-15"), "G27", 1.0, 3.30, -0.30)
    assert SEAM["_CreateTrades"](down(sheet["a"], sheet["b"]), headers, row, sheet["template"]) == (
        "#ERROR _CreateTrades: fields cell (1, 6) is text 'second_fixed_price', expected a field "
        f"of fixed_float: {FIELDS}"
    )
    assert SEAM["_CreateTradeTemplate"](
        "fixed_float", across("route", "second_fixed_price"), across("bilateral", -0.30)
    ) == (
        "#ERROR _CreateTradeTemplate: fields cell (1, 2) is text 'second_fixed_price', expected a "
        f"field of fixed_float: {FIELDS}"
    )
    # The one price's fixed leg is the trade's, once, whatever the row's quantity: a row of
    # nothing books a fixed leg of nothing and is kept, ready for a deal.
    kept = SEAM["_CreateTrades"](
        down(sheet["a"], sheet["b"]),
        sheet["headers"],
        across(1.0, serial("2026-12-15"), "G27", 0.0, 3.00),
        sheet["template"],
    )
    assert re.fullmatch(rf"{PID}:trades:A\+B:\d+", str(kept))
    assert under(read(kept), "offset") == [0.0]
