"""Two index legs on a fixed_float, two-index-fixed-float.md: a pair of synthetic indexes, A a
futures index with a 10,000 MMBTU reporting lot and B an IFERC index with a 2,500 MMBTU one,
each defining one MMBTU per entered unit, through resolution, encoding, preparation and
evaluation; the ticket's hand-priced acceptance table, its cleared version, its fixed-price
reallocation, the F27 lifecycle, the bump check of the analytic rate risk, and the rules of the
pair: the second leg's fields, distinct indexes of one quoting, one quantity on both legs, the
later observation anchoring one shared payment, histories and markets matched by identity
whatever their order, and the first leg's fees. Every expected number is the ticket's or hand
arithmetic here; the production code is never asked for an expected answer."""

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray
from test_bilateral_kernel import curve_of, curve_set
from test_create_trades import a_template, a_ticket
from test_trades import dates, day, history_on, numbers, quoted, waha_history

from goosedove.globals.discount_curve import DiscountCurve, bump_discount_curve
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market import Market
from goosedove.market.market_history import MarketHistory
from goosedove.quoting.template import quote_template
from goosedove.trades.evaluation import trade_results
from goosedove.trades.preparation import PreparedTrades, prepared_trades
from goosedove.trades.resolution import Trades, trades
from goosedove.trades.results import TradeResults

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
    quote_currency: str = "USD",
    extra: tuple[str, ...] = (),
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
    return index(
        name,
        f"Index {name}",
        futures_schedule(tuple(c for c, _ in contracts), dates(*(e for _, e in contracts)), None),
        index_conventions(quote_currency, "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
        contract_specifications(
            names,
            sizes,
            ("MMBTU",) * len(names),
            sizes * brokerage,
            sizes * clearing,
            UNITS,
        ),
        holiday_calendar(dates("2026-12-25", "2027-01-01")),
        "LOT",
        UNITS,
    )


def iferc(name: str, lot_size: float, quote_currency: str = "USD") -> Index:
    return index(
        name,
        f"Index {name}",
        iferc_schedule(
            ("Z26", "F27", "G27", "H27", "J27"),
            dates("2026-12-01", "2027-01-04", "2027-02-01", "2027-03-01", "2027-04-01"),
        ),
        index_conventions(quote_currency, "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
        contract_specifications(
            ("LOT", "MMBTU"),
            numbers(lot_size, 1.0),
            ("MMBTU", "MMBTU"),
            numbers(0.5 * lot_size, 0.5),
            numbers(0.5 * lot_size, 0.5),
            UNITS,
        ),
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
    "fixed_price": [3.30],
    "second_fixed_price": [-0.30],
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
    # 10,000 MMBTU at 3.30 and -0.30 against 3.50 and -0.40, one payment a year on at 0.95:
    # amounts 2,000 and -1,000, marks 1,900 and -950, nominal deltas 1 lot of A and 4 of B,
    # deltas 0.95 and 3.8, DV01s -0.19 and +0.095, cross-gammas -0.000095 and -0.00038; the
    # whole trade 1,000, 950 and -0.095, and no sum across the two indexes' lots.
    batch = booked()
    assert batch.resolved.descriptor == "A+B"
    assert [leg.index for leg in batch.resolved.legs] == [A, B]
    results = valued(batch)
    a, b = legs_of(results)
    assert (a.prepared.encoded.leg.index, b.prepared.encoded.leg.index) == (A, B)
    close(a.payment_amount, [2000.0])
    close(b.payment_amount, [-1000.0])
    close(results.payment_amount, [1000.0])
    close(results.payment_factor, [0.95])
    assert a.mark == pytest.approx(1900.0, **CLOSE)
    assert b.mark == pytest.approx(-950.0, **CLOSE)
    assert results.mark == pytest.approx(950.0, **CLOSE)
    assert a.dv01 == pytest.approx(-0.19, **CLOSE)
    assert b.dv01 == pytest.approx(0.095, **CLOSE)
    assert results.dv01 == pytest.approx(-0.095, **CLOSE)
    close(results.npv_by_group, [950.0])
    close(results.dv01_by_group, [-0.095])
    assert a.nominal_delta_total == pytest.approx(1.0, **CLOSE)
    assert b.nominal_delta_total == pytest.approx(4.0, **CLOSE)
    assert a.delta_total == pytest.approx(0.95, **CLOSE)
    assert b.delta_total == pytest.approx(3.8, **CLOSE)
    assert a.cross_gamma_total == pytest.approx(-0.000095, **CLOSE)
    assert b.cross_gamma_total == pytest.approx(-0.00038, **CLOSE)
    assert "LOT" in a.lot_unit and "LOT" in b.lot_unit and a.lot_unit != b.lot_unit
    # The sums are the whole trade's, exactly, and the trade's rate risk is one curve's.
    assert a.mark + b.mark == results.mark
    assert a.dv01 + b.dv01 == results.dv01
    np.testing.assert_array_equal(a.npv_by_group + b.npv_by_group, results.npv_by_group)
    np.testing.assert_array_equal(a.dv01_by_group + b.dv01_by_group, results.dv01_by_group)
    (rate,) = results.rate_contributions
    assert rate.curve is SOFR and rate.dv01 == pytest.approx(-0.095, **CLOSE)
    assert results.cash == 0.0 and a.cash == 0.0 and b.cash == 0.0
    assert [c.curve for c in a.cross_contributions] == [SOFR]
    assert a.cross_contributions[0].cross_gamma_total == pytest.approx(-0.000095, **CLOSE)


def test_the_cleared_version_is_undiscounted_with_no_rate_risk() -> None:
    results = valued(booked(CLEARED), curve=None)
    a, b = legs_of(results)
    assert (a.mark, b.mark, results.mark) == (2000.0, -1000.0, 1000.0)
    assert (a.dv01, b.dv01, results.dv01) == (0.0, 0.0, 0.0)
    assert (a.cross_gamma_total, b.cross_gamma_total) == (0.0, 0.0)
    assert a.delta is a.nominal_delta and b.delta is b.nominal_delta
    assert a.payment_amount is None and results.payment_amount is None
    assert results.curves == () and results.rate_contributions == ()


def test_moving_the_fixed_prices_moves_the_leg_values_and_not_the_whole() -> None:
    # 3.20 and -0.20 sum to the same 3.00: the legs' marks become 2,850 and -1,900 and their
    # DV01s -0.285 and 0.19; the whole mark, DV01, deltas and cross-gammas stand.
    moved: dict[str, list[object]] = {
        **TICKET,
        "fixed_price": [3.20],
        "second_fixed_price": [-0.20],
    }
    results = valued(booked(ticket=moved))
    a, b = legs_of(results)
    assert a.mark == pytest.approx(2850.0, **CLOSE)
    assert b.mark == pytest.approx(-1900.0, **CLOSE)
    assert a.dv01 == pytest.approx(-0.285, **CLOSE)
    assert b.dv01 == pytest.approx(0.19, **CLOSE)
    assert results.mark == pytest.approx(950.0, **CLOSE)
    assert results.dv01 == pytest.approx(-0.095, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (1.0, 4.0)
    assert (a.delta_total, b.delta_total) == pytest.approx((0.95, 3.8), **CLOSE)
    assert a.cross_gamma_total == pytest.approx(-0.000095, **CLOSE)
    assert b.cross_gamma_total == pytest.approx(-0.00038, **CLOSE)


def test_a_sold_pair_reverses_every_value_and_risk() -> None:
    bought = valued(booked())
    sold = valued(booked(ticket={**TICKET, "quantity": [-10_000]}))
    for mine, theirs in zip(sold.legs, bought.legs, strict=True):
        assert mine.mark == pytest.approx(-theirs.mark, **CLOSE)
        assert mine.dv01 == pytest.approx(-theirs.dv01, **CLOSE)
        assert mine.nominal_delta_total == pytest.approx(-theirs.nominal_delta_total, **CLOSE)
        assert mine.delta_total == pytest.approx(-theirs.delta_total, **CLOSE)
        assert mine.cross_gamma_total == pytest.approx(-theirs.cross_gamma_total, **CLOSE)
    assert sold.mark == pytest.approx(-bought.mark, **CLOSE)
    assert sold.dv01 == pytest.approx(-bought.dv01, **CLOSE)


def test_the_analytic_rate_risk_matches_a_bumped_curve() -> None:
    # One basis point up and down on the curve: the marks' half difference is the DV01, the
    # whole trade's and each leg's, and each leg's discounted lots' half difference its
    # cross-gamma, to the second order a bump of a basis point leaves.
    batch = booked()
    up = valued(batch, curve=bump_discount_curve(SOFR, 1.0, WorkCounter()))
    down = valued(batch, curve=bump_discount_curve(SOFR, -1.0, WorkCounter()))
    results = valued(batch)
    assert (up.mark - down.mark) / 2 == pytest.approx(results.dv01, rel=1e-6)
    for before, after, leg in zip(up.legs, down.legs, results.legs, strict=True):
        assert (before.mark - after.mark) / 2 == pytest.approx(leg.dv01, rel=1e-6)
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
    close(a.payment_amount, [2000.0])
    close(b.payment_amount, [-1000.0])
    assert results.mark == pytest.approx(1000.0 * 0.99, **CLOSE)
    assert a.dv01 == pytest.approx(-0.0001 * tau * 2000.0 * 0.99, **CLOSE)
    assert b.dv01 == pytest.approx(0.0001 * tau * 1000.0 * 0.99, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (1.0, 4.0)


def test_the_lifecycle_a_fixed_on_30_december_and_both_legs_still_carry_dv01() -> None:
    results = valued(
        booked(LIFECYCLE, F27),
        "2026-12-30",
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.40, -0.42, -0.44),
        curve=on("2026-12-30", 0.995),
    )
    a, b = legs_of(results)
    tau = 7 / 365
    close(a.payment_amount, [2500.0])  # 10,000 at 3.55 less 3.30
    close(b.payment_amount, [-1000.0])
    assert results.mark == pytest.approx(1500.0 * 0.995, **CLOSE)
    assert a.dv01 == pytest.approx(-0.0001 * tau * 2500.0 * 0.995, **CLOSE)
    assert b.dv01 == pytest.approx(0.0001 * tau * 1000.0 * 0.995, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (0.0, 4.0)
    assert a.cross_gamma_total == 0.0 and b.cross_gamma_total != 0.0
    # A's fixing corrected moves A's amount alone; B's quote moved moves B's alone.
    corrected = valued(
        booked(LIFECYCLE, F27),
        "2026-12-30",
        finals_a={"F27": 3.60},
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.40, -0.42, -0.44),
        curve=on("2026-12-30", 0.995),
    )
    close(corrected.legs[0].payment_amount, [3000.0])
    close(corrected.legs[1].payment_amount, [-1000.0])
    moved = valued(
        booked(LIFECYCLE, F27),
        "2026-12-30",
        quotes_a=(3.60, 3.70),
        quotes_b=(-0.45, -0.42, -0.44),
        curve=on("2026-12-30", 0.995),
    )
    close(moved.legs[0].payment_amount, [2500.0])
    close(moved.legs[1].payment_amount, [-1500.0])


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
    close(a.payment_amount, [2500.0])
    close(b.payment_amount, [-500.0])
    assert results.mark == pytest.approx(2000.0 * 0.9999, **CLOSE)
    assert results.dv01 == pytest.approx(-0.0001 * tau * 2000.0 * 0.9999, **CLOSE)
    assert a.dv01 == pytest.approx(-0.0001 * tau * 2500.0 * 0.9999, **CLOSE)
    assert (a.nominal_delta_total, b.nominal_delta_total) == (0.0, 0.0)
    assert results.cash == 0.0


def test_the_lifecycle_paid_on_6_january_is_cash_split_by_leg() -> None:
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
    assert (a.mark, b.mark, a.dv01, b.dv01) == (0.0, 0.0, 0.0, 0.0)
    assert results.cash == pytest.approx(2000.0, **CLOSE)
    assert a.cash == pytest.approx(2500.0, **CLOSE)
    assert b.cash == pytest.approx(-500.0, **CLOSE)
    assert results.prepared.is_settled.tolist() == [True]


# --- slots, offsets and payments of a pair -------------------------------------------------------


def test_two_futures_legs_observing_one_day_are_two_slots_with_their_own_fixings() -> None:
    # A and C expire alike; each leg's F27 slot is its own, fixed at its own settle, and the
    # offsets keep their legs after grouping: a pair whose NPV nets to nothing still has values.
    c = futures("C", 2_500.0, 0.0, 0.0)
    batch = booked(LIFECYCLE, F27, (A, c))
    a, other = batch.encoded.legs
    np.testing.assert_array_equal(a.slot_date, other.slot_date)
    assert a.slot_group.size == 1 and other.slot_group.size == 1
    close(a.offset_of_group, [-33_000.0])  # -10,000 at 3.30
    close(other.offset_of_group, [3_000.0])  # -10,000 at -0.30
    close(batch.encoded.offset_of_group, [-30_000.0])
    hist_a = history_on(A, "2026-12-30", {"F27": 3.55})
    hist_c = history_on(c, "2026-12-30", {"F27": 3.45})
    prep = prepared_trades(batch.encoded, (hist_c, hist_a), WorkCounter())  # any order
    assert prep.legs[0].history is hist_a and prep.legs[1].history is hist_c
    close(prep.legs[0].set_amount, [35_500.0])
    close(prep.legs[1].set_amount, [34_500.0])
    close(prep.set_amount, [70_000.0])
    # Cancelling legs: A at 3.50 against 3.30 and B at -0.50 against -0.30 net to nothing.
    nothing = valued(booked(), quotes_b=(-0.48, -0.50, -0.52))
    assert nothing.mark == 0.0 and nothing.dv01 == 0.0
    assert nothing.legs[0].mark == pytest.approx(1900.0, **CLOSE)
    assert nothing.legs[1].mark == pytest.approx(-1900.0, **CLOSE)
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
    close(results.legs[0].payment_amount, [2000.0, 3000.0, 4000.0])
    close(results.legs[1].payment_amount, [-1000.0, -1200.0, -1400.0])


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
        "fixed_price": [3.30, 3.40],
        "second_fixed_price": [-0.30, -0.35],
    }
    both = valued(booked(ticket=rows))
    first = valued(booked(ticket={k: [v[0]] for k, v in rows.items()}))
    second = valued(booked(ticket={k: [v[1]] for k, v in rows.items()}))
    assert both.mark == pytest.approx(first.mark + second.mark, **CLOSE)
    assert both.dv01 == pytest.approx(first.dv01 + second.dv01, **CLOSE)
    for k in range(2):
        assert both.legs[k].mark == pytest.approx(first.legs[k].mark + second.legs[k].mark, **CLOSE)
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
    # G27 covers February's 28 days: 280,000 MMBTU at 0.20 and -0.10, discounted at 0.95.
    close(daily.legs[0].payment_amount, [56_000.0])
    close(daily.legs[1].payment_amount, [-28_000.0])
    assert daily.mark == pytest.approx(28_000.0 * 0.95, **CLOSE)
    assert daily.legs[1].nominal_delta_total == pytest.approx(112.0, **CLOSE)
    zero = valued(booked(ticket={**TICKET, "quantity": [0]}))
    assert zero.mark == 0.0 and zero.dv01 == 0.0
    assert zero.legs[0].nominal_delta_total == 0.0 and zero.legs[1].nominal_delta_total == 0.0


# --- order, identity and fees --------------------------------------------------------------------


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
        assert mine.mark == theirs.mark and mine.dv01 == theirs.dv01
        assert mine.market is theirs.market and mine.prepared.history is theirs.prepared.history


def test_reversing_the_indexes_with_their_prices_keeps_the_values_and_moves_the_fees() -> None:
    brokered = {**BILATERAL, "broker": "ICAP"}
    forward = booked(brokered)
    backward = booked(
        brokered,
        {**TICKET, "fixed_price": [-0.30], "second_fixed_price": [3.30]},
        (B, A),
    )
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
    assert one.legs[0].mark == pytest.approx(other.legs[1].mark, **CLOSE)
    assert one.legs[1].delta_total == pytest.approx(other.legs[0].delta_total, **CLOSE)
    # The first leg's specification charges the brokerage: a cent a MMBTU on A, half a dollar
    # on B; the second index's rates are never read.
    assert forward.encoded.reserves.brokerage == pytest.approx(100.0, **CLOSE)
    assert backward.encoded.reserves.brokerage == pytest.approx(5000.0, **CLOSE)
    alone = booked(
        {k: v for k, v in brokered.items() if k != "second_schedule_method"},
        {k: v for k, v in TICKET.items() if k != "second_fixed_price"},
        (A,),
    )
    assert alone.encoded.reserves == forward.encoded.reserves


def test_a_single_index_batch_is_as_it_was() -> None:
    one = {k: v for k, v in BILATERAL.items() if k != "second_schedule_method"}
    ticket = {k: v for k, v in TICKET.items() if k != "second_fixed_price"}
    batch = booked(one, ticket, (A,))
    assert batch.resolved.descriptor == "A" and len(batch.encoded.legs) == 1
    hist_a = history_on(A, AS_OF, {"F27": 3.55})
    prep = prepared_trades(batch.encoded, (hist_a,), WorkCounter())
    results = trade_results(prep, (quoted(hist_a, 3.50, 3.60),), WorkCounter(), curve_set(SOFR))
    (leg,) = results.legs
    assert results.mark == pytest.approx(1900.0, **CLOSE) and leg.mark == results.mark
    assert leg.payment_amount is results.payment_amount
    assert leg.npv_by_group is results.npv_by_group and leg.dv01 == results.dv01


# --- the rules of the pair -----------------------------------------------------------------------


def test_the_second_legs_fields_are_present_exactly_with_two_indexes() -> None:
    without = {k: v for k, v in BILATERAL.items() if k != "second_schedule_method"}
    assert refused(without, {k: v for k, v in TICKET.items() if k != "second_fixed_price"}) == (
        "second_fixed_price is missing, expected it with two indexes"
    )
    assert refused(without) == "second_schedule_method is missing, expected it with two indexes"
    assert refused(without, TICKET, (A,)) == (
        "second_fixed_price is -0.3, expected none unless two indexes"
    )
    assert (
        refused(BILATERAL, {k: v for k, v in TICKET.items() if k != "second_fixed_price"}, (A,))
        == "second_schedule_method is 'lastday', expected none unless two indexes"
    )
    assert refused(indexes=(A, B, A)) == (
        "indexes are 3, expected one or two; a batch is on one index or, since "
        "two-index-fixed-float.md, on a pair"
    )
    with pytest.raises(ValueError) as refusal:
        quote_template(a_ticket({"route": ["bilateral"], "second_fixed_price": [1.0]}))
    assert str(refusal.value).startswith(
        "second_fixed_price is a field of booking alone, expected one a quote template holds: "
    )


def test_the_pair_is_two_distinct_indexes_of_one_quoting_on_a_financial_settlement() -> None:
    assert refused(indexes=(A, A)) == (
        "index 2 is index 1, 'A', again, expected two distinct indexes; a pair of one index is "
        "outside this version"
    )
    assert refused(indexes=(A, futures("A", 2_500.0, 0.0, 0.0))) == (
        "index 2 is another index named 'A', the name of index 1, expected one index for one name"
    )
    assert refused(indexes=(A, iferc("B", 2_500.0, "CENT"))) == (
        "index 2 'B' quotes in CENT per MMBTU and settles in USD, expected USD per MMBTU settled "
        "in USD as index 1 'A'; two legs' prices add in one unit"
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
    assert refused({**BILATERAL, "quantity_unit": "LOT"}, {**TICKET, "quantity": [1]}) == (
        "trade 1 at row 1 is 10000.0 MMBTU on index 'A' and 2500.0 MMBTU on index 'B', expected "
        "one quantity on both legs; quantity_unit 'LOT' is 10000.0 MMBTU a lot on 'A' and 'LOT' "
        "is 2500.0 MMBTU a lot on 'B'"
    )
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
