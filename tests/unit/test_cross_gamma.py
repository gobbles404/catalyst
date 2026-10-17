"""The cross-gamma of a bilateral batch, single-curve-cross-gamma.md: the sensitivity of the
discounted lot delta to a rise of one basis point in the discount curve's continuously compounded
zero rates, -0.0001 times each live slot's discounted lots times its payment's time fraction,
ACT/365F, the convention the DV01 moves by, each payment's own time applied before any sum. The
figures are the ticket's, priced by hand here on its synthetic index, a one-barrel lot settled in
dollars so that a quote move of one on a lot is one dollar: valued on 4 January 2027, A buys 10
and B sells 5 of G27 at 70 and 74, both observed on 1 February 2027 and quoted 72, A paid on 4
January 2028 at 0.95, a year out, and B on 3 January 2029 at 0.90, two years out. The production
code is never asked for an expected answer; the numerical check bumps every daily factor of the
built curve through the ordinary constructor and compares a centered difference of the
discounted lots with the analytic number.

Tolerances: the hand figures to the bilateral kernel's, 1e-12 absolute and relative; the centered
difference by its own truncation and roundoff, said where it is taken. docs/library/trades/kernel.md
is the page."""

import numpy as np
import pytest
from test_bilateral_kernel import (
    A_YEAR,
    AS_OF,
    CLOSE,
    LARGEST,
    PAY_DAYS,
    TIGHT,
    curve_of,
    given,
    prepared_on,
    terms_of,
    valued,
)
from test_trades import an_index, bounds_of, dates, ids, numbers, picks, rows, spec

from goosedove.globals.discount_curve import DiscountCurve, discount_curve
from goosedove.index_definitions.index import Index
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT
from goosedove.trades.preparation import PreparedTrades
from goosedove.trades.results import TradeResults
from goosedove.trades.schedule_methods import ScheduleMethod
from goosedove.trades.terms import (
    PaymentTerms,
    QuantityPer,
    ResolvedTrades,
    Route,
    Settlement,
    resolved_trades,
)

# The ticket's index: Z26 the boundary the calendar needs, G27 the one contract traded, expiring
# on 1 February 2027, and F29 after it keeping a quote in every market.
HNG = an_index(
    "HNG",
    (("Z26", "2026-12-31"), ("G27", "2027-02-01"), ("F29", "2029-01-05")),
    ("2027-12-27",),
    ("USD", "BBL"),
    ("VOLUME", "BBL"),
    ("LOT", 1.0, "BBL"),
)
PAYS = ("2028-01-04", "2029-01-03")  # 365 and 730 days after the valuation day
LAGS = ("+337cd", "+702cd")  # from the observation day, 1 February 2027, in calendar days
CURVE = curve_of((AS_OF, 1.0), (PAYS[0], 0.95), (PAYS[1], 0.90))
QUOTES = (72.0, 50.0)  # G27 and F29
PER_BP = "lots of LOT (1 BBL) per basis point"


def trades_on(
    ix: Index,
    quantities: tuple[float, ...],
    fixed: tuple[float, ...],
    pays: tuple[str, ...],
    lags: tuple[str, ...],
    method: ScheduleMethod = ScheduleMethod.LASTDAY,
    contracts: tuple[int, ...] | None = None,
    route: Route = Route.BILATERAL,
    settlement: Settlement = Settlement.FINANCIAL,
    as_of: str = AS_OF,
) -> ResolvedTrades:
    """One trade per quantity, each its own payment group, on row 1 of the index's schedule
    unless other rows are given, by the month under the method; bilateral and financial unless
    told otherwise, the payment lags carried as the sheet spelled them."""
    n = len(quantities)
    contract = rows(*(contracts or (1,) * n))
    payment = (
        None
        if settlement is Settlement.PHYSICAL
        else PaymentTerms(tuple(lags), (PAY_DAYS,) * n, dates(*pays))
    )
    return resolved_trades(
        FIXED_FLOAT, ix, spec(n), route, settlement,
        *picks(method, QuantityPer.MONTH, n), ids(*range(1001, 1001 + n)),
        None, None,
        dates(*[as_of] * n), np.arange(n, dtype=np.intp), contract, numbers(*quantities),
        *bounds_of(ix, contract), numbers(*fixed), payment,
        counterparty=None if route is Route.CLEARED else ("ACME Trading",) * n,
    )  # fmt: skip


def ticket_batch(
    quantities: tuple[float, ...] = (10.0, -5.0), fixed: tuple[float, ...] = (70.0, 74.0)
) -> PreparedTrades:
    """A and B, or other quantities and prices on their dates, prepared on the valuation day."""
    return prepared_on(trades_on(HNG, quantities, fixed, PAYS, LAGS))


def cross_of(result: TradeResults) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The four saved vectors a bilateral result always holds."""
    return (
        given(result.cross_gamma),
        given(result.cross_gamma_by_day),
        given(result.cross_gamma_by_month),
        given(result.cross_gamma_by_year),
    )


# --- the worked example ---------------------------------------------------------------------------


def test_the_worked_example_prices_by_hand() -> None:
    # Nominal 5 and discounted 9.5 - 4.5 = 5 lots; 20 and 10 of payment, 19 + 9 = 28 of NPV;
    # DV01 -0.0019 - 0.0018; cross-gamma -0.0001 times 9.5 a year out and times 2 times -4.5 two
    # years out, -0.00095 + 0.0009 = -0.00005, each payment's time on its own lots, on the one
    # contract, the one observation day, the contract's month and its year.
    prep = ticket_batch()
    counter = WorkCounter()
    result = valued(prep, QUOTES, CURVE, counter)
    assert result.lot_delta_total == 5.0
    assert result.discounted_lot_delta_total == pytest.approx(5.0, **CLOSE)
    np.testing.assert_allclose(given(result.payment_amount), [20.0, 10.0], **TIGHT)
    np.testing.assert_allclose(given(result.npv_by_group), [19.0, 9.0], **TIGHT)
    assert result.mark == pytest.approx(28.0, **CLOSE)
    np.testing.assert_allclose(given(result.dv01_by_group), [-0.0019, -0.0018], **TIGHT)
    assert result.dv01 == pytest.approx(-0.0037, **CLOSE)
    by_reference, by_day, by_month, by_year = cross_of(result)
    assert result.codes() == ("G27",)
    np.testing.assert_allclose(by_reference, [-0.00005], **TIGHT)
    assert result.cross_gamma_total == pytest.approx(-0.00005, **CLOSE)
    np.testing.assert_array_equal(prep.encoded.days, dates("2027-02-01"))
    np.testing.assert_allclose(by_day, [-0.00005], **TIGHT)
    np.testing.assert_array_equal(prep.encoded.contract_months, dates("2027-02-01"))
    np.testing.assert_allclose(by_month, [-0.00005], **TIGHT)
    np.testing.assert_array_equal(prep.encoded.contract_years, dates("2027-01-01"))
    np.testing.assert_allclose(by_year, [-0.00005], **TIGHT)
    assert all(
        not array.flags.writeable and array.dtype == np.float64 for array in cross_of(result)
    )
    assert result.early_cross_gamma.month is None and result.early_cross_gamma.year is None
    assert counter.freeze().as_dict() == {
        "groups_valued": 2,
        "kernel": 1,
        "live_prices_read": 1,
        "payment_factors_read": 2,
        "risk_reductions": 11,  # the lots and the cross-gamma onto four axes each, the DV01 three
        "slots_discounted": 2,
    }
    # Each trade alone, the contribution rows: A -0.00095, B +0.0009, the batch their sum.
    a = valued(prepared_on(trades_on(HNG, (10.0,), (70.0,), PAYS[:1], LAGS[:1])), QUOTES, CURVE)
    b = valued(prepared_on(trades_on(HNG, (-5.0,), (74.0,), PAYS[1:], LAGS[1:])), QUOTES, CURVE)
    assert (a.mark, a.dv01) == (pytest.approx(19.0, **CLOSE), pytest.approx(-0.0019, **CLOSE))
    assert (b.mark, b.dv01) == (pytest.approx(9.0, **CLOSE), pytest.approx(-0.0018, **CLOSE))
    assert a.discounted_lot_delta_total == pytest.approx(9.5, **CLOSE)
    assert b.discounted_lot_delta_total == pytest.approx(-4.5, **CLOSE)
    assert a.cross_gamma_total == pytest.approx(-0.00095, **CLOSE)
    assert b.cross_gamma_total == pytest.approx(0.0009, **CLOSE)
    assert a.cross_gamma_total + b.cross_gamma_total == pytest.approx(
        result.cross_gamma_total, **CLOSE
    )


def test_a_quote_tick_moves_the_mark_and_the_dv01_and_a_curve_move_moves_the_cross_gamma() -> None:
    # Quoted 73: 30 and 5 of payment, 33 of NPV, -0.00375 of DV01, the deltas and the
    # cross-gamma as they were, bit for bit, since the lots, the factors and the times are the
    # same; the cross-gamma is no function of the mark. At 0.96 and 0.92: 9.6 - 4.6 = 5 of delta
    # again, 28.4 of NPV, -0.00376 of DV01 and -0.0001 times 9.6 - 2 times 4.6, -0.00004: equal
    # deltas on other factors are other cross-gammas.
    prep = ticket_batch()
    base = valued(prep, QUOTES, CURVE)
    ticked = valued(prep, (73.0, 50.0), CURVE)
    assert ticked.mark == pytest.approx(33.0, **CLOSE)
    assert ticked.dv01 == pytest.approx(-0.00375, **CLOSE)
    assert ticked.lot_delta_total == 5.0
    assert ticked.discounted_lot_delta_total == pytest.approx(5.0, **CLOSE)
    assert ticked.cross_gamma_total == base.cross_gamma_total == pytest.approx(-0.00005, **CLOSE)
    for before, after in zip(cross_of(base), cross_of(ticked), strict=True):
        np.testing.assert_array_equal(before, after)
    moved = valued(prep, QUOTES, curve_of((AS_OF, 1.0), (PAYS[0], 0.96), (PAYS[1], 0.92)))
    assert moved.discounted_lot_delta_total == pytest.approx(5.0, **CLOSE)
    assert moved.mark == pytest.approx(28.4, **CLOSE)
    assert moved.dv01 == pytest.approx(-0.00376, **CLOSE)
    assert moved.cross_gamma_total == pytest.approx(-0.00004, **CLOSE)


def test_the_cross_gamma_stands_where_the_npv_or_the_discounted_delta_is_nothing() -> None:
    # Both at the live quote: no payment, no NPV, no DV01, and 5 of delta with -0.00005 of
    # cross-gamma, the lots and their times untouched by the prices. Then +18 and -19 at 70,
    # quoted 80: 180 a year out at 0.95 and -190 two years out at 0.90 are 171 and -171 of NPV,
    # nothing in all, and 0.0171 of DV01; -1 of nominal lots and 17.1 - 17.1 of discounted lots,
    # nothing; and -0.0001 times 17.1 - 2 times 17.1, +0.00171 of cross-gamma, since each
    # payment's time weights its own lots before they net.
    at_the_money = valued(ticket_batch((10.0, -5.0), (72.0, 72.0)), QUOTES, CURVE)
    assert at_the_money.mark == 0.0 and at_the_money.dv01 == 0.0
    assert at_the_money.lot_delta_total == 5.0
    assert at_the_money.discounted_lot_delta_total == pytest.approx(5.0, **CLOSE)
    assert at_the_money.cross_gamma_total == pytest.approx(-0.00005, **CLOSE)
    netted = valued(ticket_batch((18.0, -19.0), (70.0, 70.0)), (80.0, 50.0), CURVE)
    np.testing.assert_allclose(given(netted.npv_by_group), [171.0, -171.0], **TIGHT)
    assert netted.mark == pytest.approx(0.0, **CLOSE)
    assert netted.dv01 == pytest.approx(0.0171, **CLOSE)
    assert netted.lot_delta_total == -1.0
    assert netted.discounted_lot_delta_total == pytest.approx(0.0, **CLOSE)
    np.testing.assert_allclose(given(netted.cross_gamma), [0.00171], **TIGHT)
    assert netted.cross_gamma_total == pytest.approx(0.00171, **CLOSE)


# --- the numerical derivative ---------------------------------------------------------------------


def bumped(curve: DiscountCurve, h: float) -> DiscountCurve:
    """The curve with every daily factor times exp(-h tau), tau the day's ACT/365F time from the
    start, the first factor still 1, through the ordinary constructor over the daily table: a
    parallel shift of h in the continuously compounded zero rates, the convention itself and not
    an interpolation of bumped anchors."""
    tau = (curve.dates - curve.start_date).astype(np.int64) / 365.0
    return discount_curve(curve.dates, curve.factors * np.exp(-h * tau))


def test_the_analytic_cross_gamma_agrees_with_a_centered_difference_of_the_discounted_lots() -> (
    None
):
    # The discounted lots on the curve shifted up and down by h, 0.0001 times their difference
    # over 2h, against the analytic vectors and total. At h = 1e-5 the centered difference is off
    # by its truncation, h squared over 6 times the third derivative of 9.5 exp(-b) - 4.5
    # exp(-2b) at nought, 26.5, times 0.0001, some 4e-14, and by roundoff, the lots near 5 known
    # to 1e-15 and divided by 2e-5, some 1e-14: within 1e-12. At h = 1e-4 the truncation is a
    # hundred times larger, 4e-12, within 1e-10. Both bumped curves fall day by day, the straight
    # line between the anchors dropping 1.4e-4 a day where the shift moves 3e-8.
    prep = ticket_batch()
    analytic = valued(prep, QUOTES, CURVE)
    centered_total = 0.0
    for h, tolerance in ((1e-5, 1e-12), (1e-4, 1e-10)):
        up = valued(prep, QUOTES, bumped(CURVE, h))
        down = valued(prep, QUOTES, bumped(CURVE, -h))
        pairs = (
            (up.discounted_lot_delta, down.discounted_lot_delta),
            (up.discounted_daily_lots, down.discounted_daily_lots),
            (up.discounted_monthly_lots, down.discounted_monthly_lots),
            (up.discounted_yearly_lots, down.discounted_yearly_lots),
        )
        for (plus, minus), exact in zip(pairs, cross_of(analytic), strict=True):
            np.testing.assert_allclose(
                0.0001 * (plus - minus) / (2 * h), exact, rtol=0, atol=tolerance
            )
        centered_total = (
            0.0001 * (up.discounted_lot_delta_total - down.discounted_lot_delta_total) / (2 * h)
        )
        assert centered_total == pytest.approx(analytic.cross_gamma_total, rel=0, abs=tolerance)
        if h == 1e-5:
            # The ticket's own figure for the primary example at this bump, to its roundoff.
            assert centered_total == pytest.approx(-0.0000499999999581, rel=0, abs=2e-14)


# --- the lifecycle --------------------------------------------------------------------------------


def test_fixed_lots_carry_no_cross_gamma_and_a_paid_group_none_at_all() -> None:
    # The bilateral kernel's one trade, +10 of UNIT's F27 at 70 paying a year out: on the
    # observation day, quoted 80 on a curve of ones, 10 of discounted lots and -0.001 of
    # cross-gamma. The next day, fixed at 82: 120 of NPV and a DV01 364 days out, no lots and no
    # cross-gamma, the vectors zeros of floats and frozen. The payment day: cash, no factor read,
    # and the cross-gamma zeros again over the one slot.
    terms = terms_of((10.0,), (A_YEAR,), (261,))
    ones = curve_of((AS_OF, 1.0), (A_YEAR, 1.0))
    on_the_day = valued(prepared_on(terms), (80.0, 50.0), ones)
    assert on_the_day.discounted_lot_delta_total == pytest.approx(10.0, **CLOSE)
    assert on_the_day.cross_gamma_total == pytest.approx(-0.001, **CLOSE)
    fixed = prepared_on(terms, "2027-01-05", {"F27": 82.0})
    unpaid = valued(fixed, (50.0,), curve_of(("2027-01-05", 1.0), (A_YEAR, 1.0)))
    assert unpaid.mark == pytest.approx(120.0, **CLOSE)
    assert unpaid.dv01 == pytest.approx(-0.0001 * 364 / 365 * 120.0, **CLOSE)
    assert unpaid.discounted_lot_delta_total == 0.0 and unpaid.cross_gamma_total == 0.0
    for array in cross_of(unpaid):
        assert array.dtype == np.float64 and not array.flags.writeable
        np.testing.assert_array_equal(array, [0.0])
    paid = prepared_on(terms, A_YEAR, {"F27": 82.0})
    counter = WorkCounter()
    settled = valued(paid, (50.0,), curve_of((A_YEAR, 1.0)), counter)
    assert settled.cash == pytest.approx(120.0, **CLOSE) and settled.mark == 0.0
    assert settled.cross_gamma_total == 0.0
    for array in cross_of(settled):
        np.testing.assert_array_equal(array, [0.0])
    assert counter.freeze().as_dict()["payment_factors_read"] == 0


def test_a_partly_fixed_asian_keeps_the_cross_gamma_of_its_live_days_alone() -> None:
    # An index whose contracts expire on their own month's last weekday, so that October prices
    # on V26 through the 30th: 22 lots of V26 by the month, one a pricing day, valued on 15
    # October 2026 with the ten days before fixed at the settle and the twelve from the 15th live,
    # paying a year out at 0.95: 12 of nominal lots, 11.4 discounted and -0.0001 times 11.4,
    # -0.00114 of cross-gamma, -0.000095 on each live day and nothing on a fixed one, on the one
    # contract, its month and its year.
    eth = an_index(
        "ETH",
        (("U26", "2026-09-30"), ("V26", "2026-10-30"), ("X26", "2026-11-30")),
        ("2027-12-27",),
        ("USD", "BBL"),
        ("VOLUME", "BBL"),
        ("LOT", 1.0, "BBL"),
    )
    as_of = "2026-10-15"
    prep = prepared_on(
        trades_on(
            eth, (22.0,), (3.0,), ("2027-10-15",), ("+365cd",), ScheduleMethod.ASIAN, as_of=as_of
        ),
        as_of,
    )
    assert prep.encoded.days.size == 22 and int(prep.is_fixed.sum()) == 10
    result = valued(prep, (3.1, 3.2), curve_of((as_of, 1.0), ("2027-10-15", 0.95)))
    assert result.lot_delta_total == pytest.approx(12.0, **CLOSE)
    assert result.discounted_lot_delta_total == pytest.approx(11.4, **CLOSE)
    by_reference, by_day, by_month, by_year = cross_of(result)
    np.testing.assert_allclose(by_reference, [-0.00114], **TIGHT)
    np.testing.assert_allclose(by_day, [0.0] * 10 + [-0.000095] * 12, **TIGHT)
    np.testing.assert_array_equal(prep.encoded.contract_months, dates("2026-10-01"))
    np.testing.assert_allclose(by_month, [-0.00114], **TIGHT)
    np.testing.assert_allclose(by_year, [-0.00114], **TIGHT)
    assert result.cross_gamma_total == pytest.approx(-0.00114, **CLOSE)


def test_a_cleared_batch_holds_the_known_zero_and_asks_for_no_curve() -> None:
    for settlement in (Settlement.FINANCIAL, Settlement.PHYSICAL):
        prep = prepared_on(terms_of(route=Route.CLEARED, settlement=settlement))
        result = valued(prep, (80.0, 50.0), None)
        assert result.curve is None and result.cross_gamma_total == 0.0
        assert result.cross_gamma is None and result.cross_gamma_by_day is None
        assert result.cross_gamma_by_month is None and result.cross_gamma_by_year is None
        assert result.early_cross_gamma.month is None and result.early_cross_gamma.year is None


# --- the axes -------------------------------------------------------------------------------------

# An NG-like index: V26 the boundary, X26 expiring 28 October, Z26 25 November and F27 29 December
# 2026, each the month before its contract's; the pricing calendar closed on nothing before 2030.
NG = an_index(
    "NG",
    (("V26", "2026-09-28"), ("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29")),
    ("2030-01-01",),
    ("USD", "BBL"),
    ("VOLUME", "BBL"),
    ("LOT", 1.0, "BBL"),
)
OCTOBER = "2026-10-14"
NG_CURVE = curve_of((OCTOBER, 1.0), ("2027-10-14", 0.95), ("2028-10-13", 0.90))


def test_the_month_and_the_year_follow_the_pricing_contract_and_the_day_the_observation() -> None:
    # +10 of Z26 observed 25 November 2026 paying a year out at 0.95 and +4 of F27 observed 29
    # December paying two years out at 0.90: -0.00095 and -0.0001 times 2 times 3.6, -0.00072;
    # by day on the two observation days, by month under December 2026 and January 2027, the
    # contracts' months, and by year under 2026 and 2027, the second observed in 2026 and
    # counted in 2027; the three views and the vector by contract each sum to the total.
    prep = prepared_on(
        trades_on(
            NG,
            (10.0, 4.0),
            (3.0, 3.0),
            ("2027-10-14", "2028-10-13"),
            ("+323cd", "+654cd"),
            contracts=(2, 3),
            as_of=OCTOBER,
        ),
        OCTOBER,
    )
    result = valued(prep, (3.2, 3.3, 3.4), NG_CURVE)
    by_reference, by_day, by_month, by_year = cross_of(result)
    assert result.codes() == ("Z26", "F27")
    np.testing.assert_allclose(by_reference, [-0.00095, -0.00072], **TIGHT)
    np.testing.assert_array_equal(prep.encoded.days, dates("2026-11-25", "2026-12-29"))
    np.testing.assert_allclose(by_day, [-0.00095, -0.00072], **TIGHT)
    np.testing.assert_array_equal(prep.encoded.contract_months, dates("2026-12-01", "2027-01-01"))
    np.testing.assert_allclose(by_month, [-0.00095, -0.00072], **TIGHT)
    np.testing.assert_array_equal(prep.encoded.contract_years, dates("2026-01-01", "2027-01-01"))
    np.testing.assert_allclose(by_year, [-0.00095, -0.00072], **TIGHT)
    for vector in cross_of(result):
        assert float(vector.sum()) == pytest.approx(result.cross_gamma_total, **CLOSE)
    assert result.cross_gamma_total == pytest.approx(-0.00167, **CLOSE)


def test_a_rolling_asian_splits_its_cross_gamma_by_the_contract_pricing_each_day() -> None:
    # 21 lots of X26 by the month, November 2026, one a pricing day: the 2nd through the 25th,
    # eighteen days, price on Z26 and the 26th, 27th and 30th on F27, paying a year out at 0.95:
    # -0.0001 times 18 times 0.95 on Z26 and times 3 times 0.95 on F27, -0.00171 and -0.000285;
    # by day -0.000095 on each of the 21; by month and by year under the pricing contracts'
    # periods, December 2026 and January 2027, not under November.
    prep = prepared_on(
        trades_on(
            NG,
            (21.0,),
            (3.0,),
            ("2027-10-14",),
            ("+365cd",),
            ScheduleMethod.ASIAN,
            contracts=(1,),
            as_of=OCTOBER,
        ),
        OCTOBER,
    )
    result = valued(prep, (3.2, 3.3, 3.4), NG_CURVE)
    by_reference, by_day, by_month, by_year = cross_of(result)
    assert result.codes() == ("Z26", "F27")
    np.testing.assert_allclose(by_reference, [-0.00171, -0.000285], **TIGHT)
    assert prep.encoded.days.size == 21
    np.testing.assert_allclose(by_day, [-0.000095] * 21, **TIGHT)
    np.testing.assert_array_equal(prep.encoded.contract_months, dates("2026-12-01", "2027-01-01"))
    np.testing.assert_allclose(by_month, [-0.00171, -0.000285], **TIGHT)
    np.testing.assert_allclose(by_year, [-0.00171, -0.000285], **TIGHT)
    assert result.cross_gamma_total == pytest.approx(-0.001995, **CLOSE)


def test_a_contract_month_before_the_valuation_month_is_a_saved_fact() -> None:
    # U26, a September contract still trading on 14 October 2026: 3 lots paying a year out at
    # 0.95 are -0.000285 of cross-gamma in a contract month before the report's first, the fact
    # saved with the vector for a month report to word; the year is 2026, the valuation year, so
    # no fact by year.
    ng3 = an_index(
        "NG3",
        (("Q26", "2026-08-27"), ("U26", "2026-10-15"), ("X26", "2026-10-28")),
        ("2030-01-01",),
        ("USD", "BBL"),
        ("VOLUME", "BBL"),
        ("LOT", 1.0, "BBL"),
    )
    prep = prepared_on(
        trades_on(ng3, (3.0,), (3.0,), ("2027-10-14",), ("+364cd",), as_of=OCTOBER), OCTOBER
    )
    result = valued(prep, (3.2, 3.3), curve_of((OCTOBER, 1.0), ("2027-10-14", 0.95)))
    early = result.early_cross_gamma
    assert early.month is not None and early.year is None
    assert early.month.period == np.datetime64("2026-09-01")
    assert early.month.value == pytest.approx(-0.000285, **CLOSE)
    assert early.month.what == PER_BP
    assert early.month.words("cross-gamma").startswith(
        "the cross-gamma of index 'NG3' in the contract month from 2026-09-01 is "
    )


# --- cardinality ----------------------------------------------------------------------------------


def test_the_batch_is_its_rows_in_any_order_a_repeat_counts_and_a_zero_row_adds_nothing() -> None:
    result = valued(ticket_batch(), QUOTES, CURVE)
    reversed_rows = valued(
        prepared_on(trades_on(HNG, (-5.0, 10.0), (74.0, 70.0), PAYS[::-1], LAGS[::-1])),
        QUOTES,
        CURVE,
    )
    assert reversed_rows.cross_gamma_total == pytest.approx(result.cross_gamma_total, **CLOSE)
    for mine, theirs in zip(cross_of(result), cross_of(reversed_rows), strict=True):
        np.testing.assert_allclose(mine, theirs, **TIGHT)
    twice = valued(
        prepared_on(trades_on(HNG, (10.0, 10.0), (70.0, 70.0), PAYS[:1] * 2, LAGS[:1] * 2)),
        QUOTES,
        CURVE,
    )
    assert given(twice.payment_amount).size == 1  # one group, both trades
    assert twice.cross_gamma_total == pytest.approx(-0.0019, **CLOSE)
    with_zero = valued(
        prepared_on(
            trades_on(
                HNG,
                (10.0, 0.0, -5.0),
                (70.0, 70.0, 74.0),
                (PAYS[0], PAYS[0], PAYS[1]),
                (LAGS[0], LAGS[0], LAGS[1]),
            )
        ),
        QUOTES,
        CURVE,
    )
    assert with_zero.cross_gamma_total == pytest.approx(-0.00005, **CLOSE)
    # A third payment day for the one contract and observation, 2 lots three years out at 0.85:
    # -0.0001 times 3 times 1.7, -0.00051, beside the pair's -0.00005, each slot its own time.
    three = valued(
        prepared_on(
            trades_on(
                HNG,
                (10.0, -5.0, 2.0),
                (70.0, 74.0, 70.0),
                (*PAYS, "2030-01-03"),
                (*LAGS, "+1067cd"),
            )
        ),
        QUOTES,
        curve_of((AS_OF, 1.0), (PAYS[0], 0.95), (PAYS[1], 0.90), ("2030-01-03", 0.85)),
    )
    assert given(three.payment_amount).size == 3
    np.testing.assert_allclose(given(three.cross_gamma), [-0.00056], **TIGHT)
    assert three.cross_gamma_total == pytest.approx(-0.00056, **CLOSE)


# --- the rules ------------------------------------------------------------------------------------


def test_a_cross_gamma_bucket_past_the_largest_number_is_refused_by_its_contract_year() -> None:
    # Eight contracts of 2027 on a one-barrel index, bought and sold by turns at 0.9 of the largest
    # number, every price 1, so that each payment is nothing and each contract's lots are finite:
    # the bought lots pay in the year 4890, 2,863 years out at 0.999, and the sold ones the day
    # after their own observation. The discounted lots by contract, by day and by month are
    # finite, and by year their
    # sum alternates and stays finite; the cross-gamma of a bought contract, -0.0001 times 2,865
    # times 0.9 of the largest number, is a quarter of the largest number, and the four of them
    # in the one contract year sum past it, refused by that year before any result is made.
    eight = an_index(
        "EIGHT",
        (
            ("Z26", "2026-12-31"),
            ("F27", "2027-01-04"),
            ("G27", "2027-02-01"),
            ("H27", "2027-03-01"),
            ("J27", "2027-04-01"),
            ("K27", "2027-05-03"),
            ("M27", "2027-06-01"),
            ("N27", "2027-07-01"),
            ("Q27", "2027-08-02"),
            ("F29", "2029-01-05"),
        ),
        ("2027-12-27",),
        ("USD", "BBL"),
        ("VOLUME", "BBL"),
        ("EIGHT", 1.0, "BBL"),
    )
    far = "4890-01-04"
    next_days = ("2027-02-02", "2027-04-02", "2027-06-02", "2027-08-03")
    pays = tuple(day for next_day in next_days for day in (far, next_day))
    big = 0.9 * LARGEST
    prep = prepared_on(
        trades_on(
            eight,
            (big, -big) * 4,
            (1.0,) * 8,
            pays,
            ("+1cd",) * 8,
            contracts=tuple(range(1, 9)),
        )
    )
    with pytest.raises(ValueError) as refused:
        valued(prep, (1.0,) * 9, curve_of((AS_OF, 1.0), (far, 0.999)))
    assert str(refused.value) == (
        "the contract year from 2027-01-01 has -inf of cross-gamma in all, expected a finite "
        "number of lots of EIGHT (1 BBL) per basis point; its slots' cross-gammas sum past the "
        "largest number"
    )
