"""The bilateral path of the one evaluator, bilateral-calculation-kernel.md: a discount curve, each
unpaid payment group's amount discounted on the curve's factor for its payment day, DV01 the
analytic sensitivity of the mark to a rise of one basis point, and the lots each live slot holds
weighted by its group's factor before any sum; the cleared path as it was, sharing its arrays. The
figures are the ticket's, priced by hand here, and the production code is never asked for an
expected answer.

Tolerances, by measure: amounts near 100, lots near 10 and their sums to within 1e-12 absolute and
1e-12 relative, 1e-14 relative to the legs they come from and far below what a handful of products
of doubles can drift; DV01s near 1e-2 to the same bounds, the absolute one mattering since a batch
that cancels to nothing has a mark of 0 exactly here, the legs being equal and opposite in binary.
The review of the kernel added the mapping of the unpaid payment days, made once at preparation,
and the rules over every stored vector: the discounted sensitivity on a three-barrel lot and the
amounts past the largest number, by group or as cash. docs/library/trades/kernel.md is the
page."""

from dataclasses import fields
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray
from test_trades import (
    an_index,
    bounds_of,
    dates,
    history_on,
    ids,
    numbers,
    observed_of,
    picks,
    quoted,
    rows,
    spec,
)

from goosedove.globals.discount_curve import DiscountCurve, discount_curve
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT
from goosedove.instruments.fields import FieldValues
from goosedove.trades.encoding import PaymentAxes, encoded
from goosedove.trades.evaluation import Bucket, Risk, TradeResults, risk_view, trade_results
from goosedove.trades.preparation import PreparedTrades, prepared_trades
from goosedove.trades.resolution import trades
from goosedove.trades.template import trade_template
from goosedove.trades.terms import (
    PaymentTerms,
    QuantityPer,
    ResolvedTrades,
    Route,
    ScheduleMethod,
    Settlement,
    resolved_trades,
)

CLOSE: dict[str, Any] = {"rel": 1e-12, "abs": 1e-12}  # pytest.approx
TIGHT: dict[str, Any] = {"rtol": 1e-12, "atol": 1e-12}  # np.testing.assert_allclose

# A one-unit reporting lot, UNIT, one barrel, dollars a barrel settled in dollars: a quantity of 10
# is an exposure of 10, the coefficient is one, and 10 at 70 against 80 pays 100. The boundary Z26
# expires 2026-12-31; the traded F27 on 2027-01-04, the valuation day, so its observation is live on
# its own day; and F29 on 2029-01-05 keeps a quote in every market. The pricing calendar closes on
# one day that matters to nothing, and the payment calendar on one past every payment.
UNIT = an_index(
    "UNIT",
    (("Z26", "2026-12-31"), ("F27", "2027-01-04"), ("F29", "2029-01-05")),
    ("2027-12-27",),
    ("USD", "BBL"),
    ("VOLUME", "BBL"),
    ("UNIT", 1.0, "BBL"),
)
PAY_DAYS = holiday_calendar(dates("2030-01-01"))
AS_OF = "2027-01-04"
A_YEAR, TWO_YEARS = "2028-01-04", "2029-01-03"  # 365 and 730 days after the valuation day
# The review's index: the same contracts and calendars, trades entered in barrels, a bare unit of
# one, and a reporting lot of three barrels, so that a lot is a third of an exposure and the
# discounted sensitivity is the lots multiplied back by three.
TRIO = index(
    "TRIO",
    "TRIO index",
    futures_schedule(("Z26", "F27", "F29"), dates("2026-12-31", "2027-01-04", "2029-01-05"), None),
    index_conventions("USD", "BBL", "USD", "VOLUME", "BBL", UNITS),
    contract_specifications(
        ("BBL", "TRIO"),
        numbers(1.0, 3.0),
        ("BBL", "BBL"),
        numbers(0.0, 0.0),
        numbers(0.0, 0.0),
        UNITS,
    ),
    holiday_calendar(dates("2027-12-27")),
    "TRIO",
    UNITS,
)
LARGEST = float(np.finfo(np.float64).max)


def given(array: NDArray[np.float64] | None) -> NDArray[np.float64]:
    """A bilateral field, which a bilateral result always holds."""
    assert array is not None
    return array


def curve_of(*anchors: tuple[str, float]) -> DiscountCurve:
    return discount_curve(dates(*[d for d, _ in anchors]), numbers(*[f for _, f in anchors]))


FLAT = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90))


def terms_of(
    quantities: tuple[float, ...] = (10.0, -10.0),
    pays: tuple[str, ...] = (A_YEAR, TWO_YEARS),
    lags: tuple[int, ...] = (261, 522),
    route: Route = Route.BILATERAL,
    settlement: Settlement = Settlement.FINANCIAL,
    contracts: tuple[int, ...] | None = None,
    fixed: float = 70.0,
    ix: Index = UNIT,
) -> ResolvedTrades:
    """One lastday trade per quantity, each its own payment group, at 70 on F27 of UNIT unless
    another schedule row, fixed price or index is given; bilateral and financial unless told
    otherwise."""
    n = len(quantities)
    contract = rows(*(contracts or (1,) * n))
    payment = (
        None
        if settlement is Settlement.PHYSICAL
        else PaymentTerms(tuple(f"+{lag}bd" for lag in lags[:n]), (PAY_DAYS,) * n, dates(*pays[:n]))
    )
    return resolved_trades(
        FIXED_FLOAT, ix, spec(n), route, settlement,
        *picks(ScheduleMethod.LASTDAY, QuantityPer.MONTH, n), ids(*range(1001, 1001 + n)),
        None, None,
        dates(*[AS_OF] * n), np.arange(n, dtype=np.intp), contract, numbers(*quantities),
        *bounds_of(ix, contract), numbers(*[fixed] * n), payment,
        counterparty=None if route is Route.CLEARED else ("ACME Trading",) * n,
    )  # fmt: skip


def prepared_on(
    terms: ResolvedTrades, as_of: str = AS_OF, finals: dict[str, float] | None = None
) -> PreparedTrades:
    return prepared_trades(
        encoded(terms, observed_of(terms), UNITS, WorkCounter()),
        history_on(terms.index, as_of, finals or {}),
        WorkCounter(),
    )


def valued(
    prep: PreparedTrades,
    quotes: tuple[float, ...],
    curve: DiscountCurve | None,
    counter: WorkCounter | None = None,
) -> TradeResults:
    return trade_results(prep, quoted(prep.history, *quotes), counter or WorkCounter(), curve)


def test_the_unit_lot_makes_the_hand_figures_the_libraries() -> None:
    lot = UNIT.reporting_lot
    assert lot is not None and lot.coefficient == 1.0


# --- opposite trades paying a year apart ----------------------------------------------------------


def test_two_groups_paying_a_year_apart_discount_before_they_net() -> None:
    # +10 and -10 of F27 at 70, quoted 80: payments of +100 a year out and -100 two years out, net
    # nothing, and still 5 of NPV, 0.5 of discounted lots and 0.0085 of DV01 at 0.95 and 0.90.
    prep = prepared_on(terms_of())
    counter = WorkCounter()
    result = valued(prep, (80.0, 50.0), FLAT, counter)
    assert result.route is Route.BILATERAL and result.curve is FLAT and result.cash == 0.0
    assert result.mark == pytest.approx(5.0, **CLOSE)
    assert result.dv01 == pytest.approx(0.0085, **CLOSE)
    np.testing.assert_allclose(given(result.payment_amount), [100.0, -100.0], **TIGHT)
    np.testing.assert_allclose(given(result.npv_by_group), [95.0, -90.0], **TIGHT)
    np.testing.assert_allclose(given(result.dv01_by_group), [-0.0095, 0.018], **TIGHT)
    np.testing.assert_array_equal(given(result.payment_factor), [0.95, 0.90])
    # The nominal risk is the preparation's, shared and nought; the discounted lots are 9.5 less 9.
    assert result.lot_delta is prep.lot_delta and result.lot_delta_total == 0.0
    assert result.price_sensitivity is prep.price_sensitivity
    np.testing.assert_allclose(result.discounted_lot_delta, [0.5], **TIGHT)
    assert result.discounted_lot_delta_total == pytest.approx(0.5, **CLOSE)
    np.testing.assert_allclose(result.discounted_price_sensitivity, [0.5], **TIGHT)
    np.testing.assert_array_equal(prep.encoded.days, dates(AS_OF))
    np.testing.assert_allclose(result.discounted_daily_lots, [0.5], **TIGHT)
    np.testing.assert_allclose(result.discounted_monthly_lots, [0.5], **TIGHT)
    np.testing.assert_allclose(result.discounted_yearly_lots, [0.5], **TIGHT)
    assert counter.freeze().as_dict() == {
        "groups_valued": 2,
        "kernel": 1,
        "live_prices_read": 1,
        "payment_factors_read": 2,
        "risk_reductions": 7,
        "slots_discounted": 2,
    }
    # The same preparation under a tick to 81: 110 and -110, 5.5 of NPV, 0.00935 of DV01, the lots
    # as they were; and under another curve, 0.96 and 0.92 at 80: 4 of NPV, 0.4 of lots, 0.0088.
    ticked = valued(prep, (81.0, 50.0), FLAT)
    assert ticked.mark == pytest.approx(5.5, **CLOSE)
    assert ticked.dv01 == pytest.approx(0.00935, **CLOSE)
    assert ticked.discounted_lot_delta_total == pytest.approx(0.5, **CLOSE)
    assert ticked.lot_delta_total == 0.0
    other = valued(prep, (80.0, 50.0), curve_of((AS_OF, 1.0), (A_YEAR, 0.96), (TWO_YEARS, 0.92)))
    assert other.mark == pytest.approx(4.0, **CLOSE)
    assert other.discounted_lot_delta_total == pytest.approx(0.4, **CLOSE)
    assert other.dv01 == pytest.approx(0.0088, **CLOSE)
    assert other.lot_delta_total == 0.0
    for array in (result.payment_amount, result.npv_by_group, result.discounted_daily_lots):
        assert array is not None and not array.flags.writeable


def test_a_mark_of_nothing_still_carries_lots_and_dv01() -> None:
    # One +10 at the money, 70 against 70: no NPV and no DV01, 10 nominal lots and 9.5 discounted;
    # a quote move of one makes 9.5 of NPV and -0.00095 of DV01. And +100 and -100 both at 0.90,
    # one and two years out: a mark of nothing with 0.009 of DV01, each group's own time to payment.
    prep = prepared_on(terms_of((10.0,), (A_YEAR,), (261,)))
    flat = valued(prep, (70.0, 50.0), FLAT)
    assert flat.mark == 0.0 and flat.dv01 == 0.0
    assert flat.lot_delta_total == 10.0
    assert flat.discounted_lot_delta_total == pytest.approx(9.5, **CLOSE)
    moved = valued(prep, (71.0, 50.0), FLAT)
    assert moved.mark == pytest.approx(9.5, **CLOSE)
    assert moved.dv01 == pytest.approx(-0.00095, **CLOSE)
    both = valued(
        prepared_on(terms_of()),
        (80.0, 50.0),
        curve_of((AS_OF, 1.0), ("2027-01-05", 0.90), (TWO_YEARS, 0.90)),
    )
    assert both.mark == pytest.approx(0.0, **CLOSE)
    assert both.dv01 == pytest.approx(0.009, **CLOSE)


def test_batch_equals_its_singletons_and_order_and_duplicates_count() -> None:
    prep = prepared_on(terms_of())
    batch = valued(prep, (80.0, 50.0), FLAT)
    a = valued(prepared_on(terms_of((10.0,), (A_YEAR,), (261,))), (80.0, 50.0), FLAT)
    b = valued(prepared_on(terms_of((-10.0,), (TWO_YEARS,), (522,))), (80.0, 50.0), FLAT)
    assert a.mark + b.mark == pytest.approx(batch.mark, **CLOSE)
    assert a.dv01 + b.dv01 == pytest.approx(batch.dv01, **CLOSE)
    assert a.discounted_lot_delta_total + b.discounted_lot_delta_total == pytest.approx(
        batch.discounted_lot_delta_total, **CLOSE
    )
    reversed_rows = valued(
        prepared_on(terms_of((-10.0, 10.0), (TWO_YEARS, A_YEAR), (522, 261))), (80.0, 50.0), FLAT
    )
    assert reversed_rows.mark == pytest.approx(batch.mark, **CLOSE)
    assert reversed_rows.dv01 == pytest.approx(batch.dv01, **CLOSE)
    twice = valued(
        prepared_on(terms_of((10.0, 10.0), (A_YEAR, A_YEAR), (261, 261))), (80.0, 50.0), FLAT
    )
    np.testing.assert_allclose(
        given(twice.npv_by_group), [190.0], **TIGHT
    )  # one group, both trades
    assert twice.dv01 == pytest.approx(-0.019, **CLOSE)
    assert twice.discounted_lot_delta_total == pytest.approx(19.0, **CLOSE)


# --- fixed is not paid ----------------------------------------------------------------------------


def test_a_fixed_payment_is_discounted_until_it_is_paid_and_then_is_cash() -> None:
    terms = terms_of((10.0,), (A_YEAR,), (261,))
    # The observation day, 80 quoted, a curve of ones: 100 of NPV a year out, -0.01 of DV01.
    on_the_day = valued(prepared_on(terms), (80.0, 50.0), curve_of((AS_OF, 1.0), (A_YEAR, 1.0)))
    assert on_the_day.mark == pytest.approx(100.0, **CLOSE)
    assert on_the_day.dv01 == pytest.approx(-0.01, **CLOSE)
    assert on_the_day.lot_delta_total == 10.0
    assert on_the_day.discounted_lot_delta_total == pytest.approx(10.0, **CLOSE)
    # The next day, fixed at 82: 120 of NPV, 364 days out, no lots, and -0.0119671232876712 of DV01.
    fixed = prepared_on(terms, "2027-01-05", {"F27": 82.0})
    unpaid = valued(fixed, (50.0,), curve_of(("2027-01-05", 1.0), (A_YEAR, 1.0)))
    assert unpaid.mark == pytest.approx(120.0, **CLOSE)
    assert unpaid.cash == 0.0
    assert unpaid.dv01 == pytest.approx(-0.0001 * 364 / 365 * 120.0, **CLOSE)
    assert unpaid.lot_delta_total == 0.0 and unpaid.discounted_lot_delta_total == 0.0
    np.testing.assert_array_equal(given(unpaid.payment_factor), [1.0])
    # At 0.99 the same payment is worth 118.8.
    at_99 = valued(fixed, (50.0,), curve_of(("2027-01-05", 1.0), (A_YEAR, 0.99)))
    assert at_99.mark == pytest.approx(118.8, **CLOSE)
    # The payment day: cash 120, nothing left to value, a curve of that one day enough and no
    # factor read; and the day after, the payment before the curve begins, the same.
    for as_of in (A_YEAR, "2028-01-05"):
        paid = prepared_on(terms, as_of, {"F27": 82.0})
        counter = WorkCounter()
        settled = valued(paid, (50.0,), curve_of((as_of, 1.0)), counter)
        assert settled.mark == 0.0 and settled.cash == pytest.approx(120.0, **CLOSE)
        assert settled.dv01 == 0.0 and settled.discounted_lot_delta_total == 0.0
        np.testing.assert_array_equal(
            given(settled.payment_factor), [1.0]
        )  # the policy, read for nothing
        np.testing.assert_array_equal(given(settled.npv_by_group), [0.0])
        # The one slot, fixed, is weighted like any other, its lots nothing; the discounted
        # vectors are floats of nothing, a sum over every slot and never numpy's integer zeros
        # for a sum over none.
        for array in (
            settled.discounted_lot_delta,
            settled.discounted_price_sensitivity,
            settled.discounted_daily_lots,
            settled.discounted_monthly_lots,
            settled.discounted_yearly_lots,
        ):
            assert array.dtype == np.float64
            np.testing.assert_array_equal(array, [0.0])
        assert counter.freeze().as_dict() == {
            "groups_valued": 0,
            "kernel": 1,
            "live_prices_read": 0,
            "payment_factors_read": 0,
            "risk_reductions": 7,
            "slots_discounted": 1,
        }


# --- the rules ------------------------------------------------------------------------------------


def test_the_rules_refuse_a_curve_with_a_cleared_batch_and_want_one_with_a_bilateral() -> None:
    cleared = prepared_on(terms_of(route=Route.CLEARED))
    with pytest.raises(ValueError) as refused:
        valued(cleared, (80.0, 50.0), FLAT)
    assert str(refused.value) == (
        "discount_curve is supplied, expected none unless route = bilateral; a cleared batch is "
        "undiscounted"
    )
    bilateral = prepared_on(terms_of())
    with pytest.raises(ValueError) as refused:
        valued(bilateral, (80.0, 50.0), None)
    assert str(refused.value) == (
        "discount_curve is missing, expected a discount curve with a bilateral batch, whose "
        "payments it discounts"
    )
    physical = prepared_on(terms_of(settlement=Settlement.PHYSICAL))
    with pytest.raises(ValueError) as refused:
        valued(physical, (80.0, 50.0), FLAT)
    assert str(refused.value) == (
        "settlement_method is 'physical', expected 'financial' with a bilateral batch; a physical "
        "delivery has no payment to discount"
    )
    with pytest.raises(ValueError) as refused:
        valued(bilateral, (80.0, 50.0), curve_of(("2027-01-05", 1.0), (TWO_YEARS, 0.9)))
    assert str(refused.value) == (
        "discount_curve starts on 2027-01-05, expected 2027-01-04, the valuation date; a curve is "
        "never rebased"
    )
    with pytest.raises(ValueError) as refused:
        valued(bilateral, (80.0, 50.0), curve_of((AS_OF, 1.0), ("2028-12-31", 0.9)))
    assert str(refused.value) == (
        "the payment of F27 on 2029-01-03 is past the discount curve, which runs from 2027-01-04 "
        "to 2028-12-31; expected every unpaid payment day covered"
    )
    # A curve ending on the last payment day covers it; a fixed, unpaid group needs its day too.
    assert valued(bilateral, (80.0, 50.0), FLAT).curve is FLAT
    fixed = prepared_on(terms_of((10.0,), (A_YEAR,), (261,)), "2027-01-05", {"F27": 82.0})
    with pytest.raises(
        ValueError, match=r"^the payment of F27 on 2028-01-04 is past the discount curve"
    ):
        valued(fixed, (50.0,), curve_of(("2027-01-05", 1.0), ("2028-01-03", 1.0)))


# --- the axes -------------------------------------------------------------------------------------


def test_discounted_lots_are_weighted_by_slot_before_the_reference_and_time_sums() -> None:
    # Three groups: +10 and -10 of F27 observed on the valuation day, paying a year and two years
    # out, and +5 of F29 observed on its expiry, 2029-01-05, paying one business day after, on
    # Monday 2029-01-08; the curve runs from the valuation day to that day, 1 to 0.90 over 735
    # days, so every factor is interpolated and no two of the three agree. Two slots of one day and
    # one contract pay on different days, so the weighting comes before the day's sum.
    curve = curve_of((AS_OF, 1.0), ("2029-01-08", 0.90))

    def factor(days: int) -> float:
        return 1.0 - 0.1 * days / 735

    terms = terms_of(
        (10.0, -10.0, 5.0), (A_YEAR, TWO_YEARS, "2029-01-08"), (261, 522, 1), contracts=(1, 1, 2)
    )
    prep = prepared_on(terms)
    counter = WorkCounter()
    result = valued(prep, (80.0, 50.0), curve, counter)
    d365, d730, d735 = factor(365), factor(730), factor(735)
    np.testing.assert_allclose(given(result.payment_factor), [d365, d730, d735], **TIGHT)
    np.testing.assert_allclose(given(result.payment_amount), [100.0, -100.0, -100.0], **TIGHT)
    np.testing.assert_allclose(
        given(result.npv_by_group), [100 * d365, -100 * d730, -100 * d735], **TIGHT
    )
    np.testing.assert_allclose(
        given(result.dv01_by_group),
        [-0.0001 * 1 * 100 * d365, -0.0001 * 2 * -100 * d730, -0.0001 * 735 / 365 * -100 * d735],
        **TIGHT,
    )
    assert result.mark == pytest.approx(100 * d365 - 100 * d730 - 100 * d735, **CLOSE)
    # By reference, F27 then F29; by day, the two observation days; by month and year likewise.
    np.testing.assert_array_equal(prep.encoded.references, [1, 2])
    np.testing.assert_allclose(
        result.discounted_lot_delta, [10 * d365 - 10 * d730, 5 * d735], **TIGHT
    )
    np.testing.assert_allclose(result.lot_delta, [0.0, 5.0])
    np.testing.assert_array_equal(prep.encoded.days, dates(AS_OF, "2029-01-05"))
    np.testing.assert_allclose(
        result.discounted_daily_lots, [10 * d365 - 10 * d730, 5 * d735], **TIGHT
    )
    np.testing.assert_array_equal(prep.encoded.months, dates("2027-01-01", "2029-01-01"))
    np.testing.assert_allclose(
        result.discounted_monthly_lots, [10 * d365 - 10 * d730, 5 * d735], **TIGHT
    )
    np.testing.assert_array_equal(prep.encoded.years, dates("2027-01-01", "2029-01-01"))
    np.testing.assert_allclose(
        result.discounted_yearly_lots, [10 * d365 - 10 * d730, 5 * d735], **TIGHT
    )
    assert result.discounted_lot_delta_total == pytest.approx(
        10 * d365 - 10 * d730 + 5 * d735, **CLOSE
    )
    assert counter.freeze().as_dict() == {
        "groups_valued": 3,
        "kernel": 1,
        "live_prices_read": 2,
        "payment_factors_read": 3,
        "risk_reductions": 7,
        "slots_discounted": 3,
    }


# --- the cleared path, as it was ------------------------------------------------------------------


def test_a_cleared_batch_shares_its_nominal_arrays_and_keeps_no_group_vector() -> None:
    prep = prepared_on(terms_of(route=Route.CLEARED))
    counter = WorkCounter()
    result = valued(prep, (80.0, 50.0), None, counter)
    assert result.curve is None and result.dv01 == 0.0
    assert result.mark == pytest.approx(0.0, **CLOSE)  # +100 and -100, undiscounted, net
    assert result.discounted_lot_delta is prep.lot_delta
    assert result.discounted_price_sensitivity is prep.price_sensitivity
    assert result.discounted_daily_lots is prep.daily_lots
    assert result.discounted_monthly_lots is prep.monthly_lots
    assert result.discounted_yearly_lots is prep.yearly_lots
    assert result.discounted_lot_delta_total == prep.lot_delta_total
    assert result.payment_amount is None and result.npv_by_group is None
    assert result.dv01_by_group is None and result.payment_factor is None
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": 1}


# --- the same figures through creation ------------------------------------------------------------


def test_the_two_trades_made_through_the_creators_value_the_same() -> None:
    # The ticket's rows made as a sheet makes them, the lags +261bd and +522bd counted on the
    # payment calendar from the expiry, 2027-01-04, to 2028-01-04 and 2029-01-03.
    fields = {
        "quantity_unit": "UNIT",
        "quantity_per": "month",
        "schedule_method": "lastday",
        "route": "bilateral",
        "settlement_method": "financial",
        "counterparty": "ACME Trading",
        "payment_holiday_calendar": PAY_DAYS,
    }
    template = trade_template(
        FieldValues(FIXED_FLOAT, 1, tuple(fields), {k: (v,) for k, v in fields.items()})
    )
    columns: dict[str, Any] = {
        "trade_id": numbers(1001.0, 1002.0),
        "trade_date": dates(AS_OF, AS_OF),
        "contract_code": ("F27", "F27"),
        "quantity": numbers(10.0, -10.0),
        "fixed_price": numbers(70.0, 70.0),
        "payment_time_lag": ("+261bd", "+522bd"),
    }
    ticket = FieldValues(FIXED_FLOAT, 2, tuple(columns), columns)
    batch = trades(UNIT, ticket, template, UNITS, WorkCounter())
    assert batch.encoded.payment_date is not None
    np.testing.assert_array_equal(batch.encoded.payment_date, dates(A_YEAR, TWO_YEARS))
    assert batch.resolved.counterparty == ("ACME Trading", "ACME Trading")
    prep = prepared_trades(batch.encoded, history_on(UNIT, AS_OF, {}), WorkCounter())
    result = valued(prep, (80.0, 50.0), FLAT)
    assert result.mark == pytest.approx(5.0, **CLOSE)
    assert result.dv01 == pytest.approx(0.0085, **CLOSE)
    assert result.discounted_lot_delta_total == pytest.approx(0.5, **CLOSE)
    assert result.lot_delta_total == 0.0


# --- the review of #176: the mapping once, every stored vector finite -----------------------------


def test_the_preparation_maps_the_unpaid_payment_days_once_for_the_ticks() -> None:
    # The two groups, a year and two years out: two days, each group's place among them and the
    # time fractions 1 and 2, frozen, two days mapped. Once the first has paid, one group is left,
    # a year from the new valuation day. Two contracts paying on one day map one day for the two,
    # and a tick reads one factor for both. A cleared batch and a physical one map nothing.
    terms = terms_of()
    counter = WorkCounter()
    prep = prepared_trades(
        encoded(terms, observed_of(terms), UNITS, WorkCounter()),
        history_on(UNIT, AS_OF, {}),
        counter,
    )
    assert counter.freeze().as_dict() == {
        "fixings_read": 0,
        "payment_days_mapped": 2,
        "prepared_slots": 2,
    }
    pays = prep.unpaid_payments
    assert pays is not None
    np.testing.assert_array_equal(pays.days, dates(A_YEAR, TWO_YEARS))
    np.testing.assert_array_equal(pays.groups, [0, 1])
    np.testing.assert_array_equal(pays.day_of_group, [0, 1])
    np.testing.assert_array_equal(pays.tau, [1.0, 2.0])
    for array in (pays.days, pays.groups, pays.day_of_group, pays.tau):
        assert not array.flags.writeable
    later = prepared_on(terms, A_YEAR, {"F27": 82.0}).unpaid_payments
    assert later is not None
    np.testing.assert_array_equal(later.days, dates(TWO_YEARS))
    np.testing.assert_array_equal(later.groups, [1])
    np.testing.assert_array_equal(later.day_of_group, [0])
    np.testing.assert_array_equal(later.tau, [1.0])
    one_day = prepared_on(
        terms_of((10.0, 5.0), ("2029-01-08", "2029-01-08"), (522, 1), contracts=(1, 2))
    )
    shared = one_day.unpaid_payments
    assert shared is not None
    np.testing.assert_array_equal(shared.days, dates("2029-01-08"))
    np.testing.assert_array_equal(shared.groups, [0, 1])
    np.testing.assert_array_equal(shared.day_of_group, [0, 0])
    np.testing.assert_allclose(shared.tau, [735 / 365, 735 / 365], **TIGHT)
    counter = WorkCounter()
    result = valued(one_day, (80.0, 50.0), curve_of((AS_OF, 1.0), ("2029-01-08", 0.90)), counter)
    np.testing.assert_array_equal(given(result.payment_factor), [0.9, 0.9])
    counts = counter.freeze().as_dict()
    assert counts["payment_factors_read"] == 1 and counts["groups_valued"] == 2
    assert prepared_on(terms_of(route=Route.CLEARED)).unpaid_payments is None
    assert prepared_on(terms_of(settlement=Settlement.PHYSICAL)).unpaid_payments is None


def test_an_amount_past_the_largest_number_is_refused_by_its_group_or_as_cash() -> None:
    # One barrel bought at -1e308 is an entry offset of 1e308. Quoted 1e308, the live leg is
    # another 1e308 and the group's amount is past the largest number, refused by its contract
    # and payment day with no mark or DV01 made; fixed at 1e308 the next day, the set leg is, the
    # same words; and on its payment day, when the group is cash, the preparation refuses the
    # batch's cash, bilateral or cleared alike, before any curve is asked for.
    terms = terms_of((1.0,), (A_YEAR,), (261,), fixed=-1e308)
    with pytest.raises(ValueError) as refused:
        valued(prepared_on(terms), (1e308, 50.0), curve_of((AS_OF, 1.0), (A_YEAR, 1.0)))
    assert str(refused.value) == (
        "the payment of F27 on 2028-01-04 is inf, expected a finite amount of USD; its fixed, set "
        "and live legs sum past the largest number"
    )
    fixed = prepared_on(terms, "2027-01-05", {"F27": 1e308})
    with pytest.raises(ValueError, match=r"^the payment of F27 on 2028-01-04 is inf, "):
        valued(fixed, (50.0,), curve_of(("2027-01-05", 1.0), (A_YEAR, 1.0)))
    for route in (Route.BILATERAL, Route.CLEARED):
        with pytest.raises(ValueError) as refused:
            prepared_on(
                terms_of((1.0,), (A_YEAR,), (261,), route=route, fixed=-1e308),
                A_YEAR,
                {"F27": 1e308},
            )
        assert str(refused.value) == (
            "the batch has inf of cash in all, expected a finite amount of USD; the settled "
            "groups' offsets and set amounts sum past the largest number"
        )


def test_a_discounted_sensitivity_past_the_largest_number_is_refused_by_its_contract() -> None:
    # The review's case: half the largest number of barrels in each of two groups of F27, bought
    # at nothing and quoted nothing on a curve of ones, the reporting lot three barrels. The
    # nominal sensitivity is their sum, the largest number exactly, the lot delta a third of it,
    # and the cleared batch publishes both with a mark of nothing. The discounted lots are a third
    # of each half, summed, and multiplied back by three they round past the largest number: the
    # bilateral tick refuses the sensitivity by its contract rather than publish inf beside a mark
    # and a DV01 of nothing.
    halves = (LARGEST / 2, LARGEST / 2)
    cleared = valued(
        prepared_on(terms_of(halves, route=Route.CLEARED, fixed=0.0, ix=TRIO)), (0.0, 50.0), None
    )
    assert cleared.mark == 0.0 and cleared.dv01 == 0.0
    np.testing.assert_array_equal(cleared.price_sensitivity, [LARGEST])
    assert cleared.lot_delta_total == LARGEST / 3
    prep = prepared_on(terms_of(halves, fixed=0.0, ix=TRIO))
    assert prep.lot_delta_total == LARGEST / 3
    with pytest.raises(ValueError) as refused:
        valued(prep, (0.0, 50.0), curve_of((AS_OF, 1.0), (TWO_YEARS, 1.0)))
    assert str(refused.value) == (
        "F27 has inf of discounted price sensitivity, expected a finite amount of USD per USD/BBL; "
        "its discounted lots times the lot's coefficient outrun the largest number"
    )


# --- the payment-time axes and the risk views, unified-risk-reporting.md --------------------------
# The DV01 by payment day, month and year, summed onto axes the encoding makes once for a bilateral
# batch, and the one way a report reads a risk: by reference where the axis is the risk's own and
# through saved places onto the union where all three share one axis.

ALL_LABELS = (
    "UNIT nominal_delta [UNIT]",
    "UNIT delta [UNIT]",
    "curve_1 USD dv01 [USD per basis point]",
)


def axes_of(prep: PreparedTrades) -> PaymentAxes:
    """The payment-time axes a bilateral batch always holds."""
    axes = prep.encoded.payment_axes
    assert axes is not None
    return axes


def test_the_encoding_makes_the_payment_axes_once_for_a_bilateral_batch() -> None:
    # Two groups paying a year apart: two payment days in two months of two years, and on the
    # unions the observation day, its month and its year a third entry before them, every place
    # saved and every array frozen; the encoding counts the distinct payment days; the cleared
    # twin and the physical one make no axes at all.
    counter = WorkCounter()
    terms = terms_of()
    axes = encoded(terms, observed_of(terms), UNITS, counter).payment_axes
    assert axes is not None
    assert counter.freeze().as_dict()["encoded_payment_days"] == 2
    np.testing.assert_array_equal(axes.days, dates(A_YEAR, TWO_YEARS))
    np.testing.assert_array_equal(axes.day_of_group, [0, 1])
    np.testing.assert_array_equal(axes.months, dates("2028-01-01", "2029-01-01"))
    np.testing.assert_array_equal(axes.month_of_day, [0, 1])
    np.testing.assert_array_equal(axes.years, dates("2028-01-01", "2029-01-01"))
    np.testing.assert_array_equal(axes.year_of_month, [0, 1])
    np.testing.assert_array_equal(axes.union_days, dates(AS_OF, A_YEAR, TWO_YEARS))
    np.testing.assert_array_equal(axes.observed_in_days, [0])
    np.testing.assert_array_equal(axes.paid_in_days, [1, 2])
    firsts = dates("2027-01-01", "2028-01-01", "2029-01-01")
    np.testing.assert_array_equal(axes.union_months, firsts)
    np.testing.assert_array_equal(axes.observed_in_months, [0])
    np.testing.assert_array_equal(axes.paid_in_months, [1, 2])
    np.testing.assert_array_equal(axes.union_years, firsts)
    np.testing.assert_array_equal(axes.observed_in_years, [0])
    np.testing.assert_array_equal(axes.paid_in_years, [1, 2])
    assert all(not getattr(axes, field.name).flags.writeable for field in fields(axes))
    for other in (terms_of(route=Route.CLEARED), terms_of(settlement=Settlement.PHYSICAL)):
        counter = WorkCounter()
        assert encoded(other, observed_of(other), UNITS, counter).payment_axes is None
        assert "encoded_payment_days" not in counter.freeze().as_dict()


def test_groups_paying_on_one_day_share_it_and_days_in_one_month_share_the_month() -> None:
    # A group is a contract and a payment day, so three groups on two days take two contracts, on
    # an index with a G27 beside UNIT's months: +10 of F27 and +4 of G27 paying on the same January
    # day and six more of F27 paying six days later are three groups, two days, one month and one
    # year; the DV01 by day sums the two groups on the one day, by month and by year the three,
    # each the saved DV01. Then a December payment against a January one: two months in two
    # years, the valuation day's year the first of them on the union.
    pair = an_index(
        "PAIR",
        (
            ("Z26", "2026-12-31"),
            ("F27", "2027-01-04"),
            ("G27", "2027-02-04"),
            ("F29", "2029-01-05"),
        ),
        ("2027-12-27",),
        ("USD", "BBL"),
        ("VOLUME", "BBL"),
        ("PAIR", 1.0, "BBL"),
    )
    prep = prepared_on(
        terms_of(
            (10.0, 4.0, 6.0),
            (A_YEAR, A_YEAR, "2028-01-10"),
            (261, 261, 265),
            contracts=(1, 2, 1),
            ix=pair,
        )
    )
    axes = axes_of(prep)
    np.testing.assert_array_equal(axes.days, dates(A_YEAR, "2028-01-10"))
    paid_on = prep.encoded.payment_date
    assert paid_on is not None
    np.testing.assert_array_equal(axes.days[axes.day_of_group], paid_on)
    assert axes.day_of_group.size == 3 and np.count_nonzero(axes.day_of_group == 0) == 2
    np.testing.assert_array_equal(axes.months, dates("2028-01-01"))
    np.testing.assert_array_equal(axes.month_of_day, [0, 0])
    np.testing.assert_array_equal(axes.years, dates("2028-01-01"))
    result = valued(prep, (80.0, 60.0, 50.0), FLAT)
    by_group = given(result.dv01_by_group)
    assert np.all(by_group != 0.0)
    np.testing.assert_allclose(
        given(result.dv01_by_day),
        [by_group[axes.day_of_group == 0].sum(), by_group[axes.day_of_group == 1].sum()],
        **TIGHT,
    )
    np.testing.assert_allclose(given(result.dv01_by_month), [by_group.sum()], **TIGHT)
    np.testing.assert_allclose(given(result.dv01_by_year), [by_group.sum()], **TIGHT)
    assert result.dv01 == pytest.approx(float(by_group.sum()), **CLOSE)
    straddle = prepared_on(terms_of((10.0, -10.0), ("2027-12-31", "2028-01-03"), (258, 259)))
    axes = axes_of(straddle)
    np.testing.assert_array_equal(axes.months, dates("2027-12-01", "2028-01-01"))
    np.testing.assert_array_equal(axes.years, dates("2027-01-01", "2028-01-01"))
    np.testing.assert_array_equal(axes.year_of_month, [0, 1])
    np.testing.assert_array_equal(axes.union_years, dates("2027-01-01", "2028-01-01"))
    np.testing.assert_array_equal(axes.observed_in_years, [0])
    np.testing.assert_array_equal(axes.paid_in_years, [0, 1])
    np.testing.assert_array_equal(
        axes.union_months, dates("2027-01-01", "2027-12-01", "2028-01-01")
    )
    np.testing.assert_array_equal(axes.paid_in_months, [1, 2])


def test_the_views_select_by_reference_and_all_places_both_kinds_on_one_axis() -> None:
    # +10 of F27 paying on 5 January 2029, the day F29 is observed, and +5 of F29 paying five days
    # later, on a curve flat at 0.9 from a year out: the observation days 4 January 2027 and 5
    # January 2029, the payment days 5 and 10 January 2029, the union three days with the shared
    # one in the middle. The nominal view is the preparation's vector on the encoding's axis, the
    # delta view the result's, the DV01 view the result's on the payment axis; all three put the
    # lots and the DV01 side by side on the shared day and nothing where only the other kind has
    # a date. The lots by hand: 10 and 5, discounted 9 and 4.5; the DV01s -0.0001 times 732/365
    # of 90 and -0.0001 times 737/365 of -90, 2028 a leap year.
    prep = prepared_on(
        terms_of((10.0, 5.0), ("2029-01-05", "2029-01-10"), (522, 525), contracts=(1, 2))
    )
    axes = axes_of(prep)
    np.testing.assert_array_equal(prep.encoded.days, dates(AS_OF, "2029-01-05"))
    np.testing.assert_array_equal(axes.days, dates("2029-01-05", "2029-01-10"))
    np.testing.assert_array_equal(axes.union_days, dates(AS_OF, "2029-01-05", "2029-01-10"))
    np.testing.assert_array_equal(axes.observed_in_days, [0, 1])
    np.testing.assert_array_equal(axes.paid_in_days, [1, 2])
    flat_from_a_year = curve_of((AS_OF, 1.0), (A_YEAR, 0.9), ("2029-01-10", 0.9))
    result = valued(prep, (80.0, 50.0), flat_from_a_year)
    first, second = -0.0001 * 732 / 365 * 90.0, -0.0001 * 737 / 365 * -90.0
    np.testing.assert_allclose(given(result.dv01_by_day), [first, second], **TIGHT)
    np.testing.assert_allclose(given(result.dv01_by_month), [first + second], **TIGHT)
    np.testing.assert_allclose(given(result.dv01_by_year), [first + second], **TIGHT)
    nominal = risk_view(result, Risk.NOMINAL_DELTA, Bucket.DAY)
    assert nominal.dates is prep.encoded.days and nominal.columns[0] is prep.daily_lots
    assert nominal.labels == ALL_LABELS[:1] and nominal.totals == (15.0,)
    delta = risk_view(result, Risk.DELTA, Bucket.MONTH)
    assert delta.dates is prep.encoded.months
    assert delta.columns[0] is result.discounted_monthly_lots
    assert delta.labels == ALL_LABELS[1:2]
    assert delta.totals == (pytest.approx(13.5, **CLOSE),)
    dv01 = risk_view(result, Risk.DV01, Bucket.DAY)
    assert dv01.dates is axes.days and dv01.columns[0] is result.dv01_by_day
    assert dv01.labels == ALL_LABELS[2:] and dv01.totals == (
        pytest.approx(first + second, **CLOSE),
    )
    everything = risk_view(result, Risk.ALL, Bucket.DAY)
    assert everything.dates is axes.union_days and everything.labels == ALL_LABELS
    assert everything.totals == (
        15.0,
        pytest.approx(13.5, **CLOSE),
        pytest.approx(first + second, **CLOSE),
    )
    np.testing.assert_allclose(everything.columns[0], [10.0, 5.0, 0.0], **TIGHT)
    np.testing.assert_allclose(everything.columns[1], [9.0, 4.5, 0.0], **TIGHT)
    np.testing.assert_allclose(everything.columns[2], [0.0, first, second], **TIGHT)
    by_year = risk_view(result, Risk.ALL, Bucket.YEAR)
    np.testing.assert_array_equal(by_year.dates, dates("2027-01-01", "2029-01-01"))
    np.testing.assert_allclose(by_year.columns[0], [10.0, 5.0], **TIGHT)
    np.testing.assert_allclose(by_year.columns[2], [0.0, first + second], **TIGHT)


def test_a_cleared_result_has_no_rate_axis_and_its_views_share_the_nominal_arrays() -> None:
    prep = prepared_on(terms_of(route=Route.CLEARED))
    result = valued(prep, (80.0, 50.0), None)
    assert (result.dv01_by_day, result.dv01_by_month, result.dv01_by_year) == (None, None, None)
    nominal = risk_view(result, Risk.NOMINAL_DELTA, Bucket.DAY)
    assert nominal.dates is prep.encoded.days and nominal.columns[0] is prep.daily_lots
    assert nominal.labels == ALL_LABELS[:1] and nominal.totals == (0.0,)
    delta = risk_view(result, Risk.DELTA, Bucket.MONTH)
    assert delta.dates is prep.encoded.months and delta.columns[0] is prep.monthly_lots
    dv01 = risk_view(result, Risk.DV01, Bucket.YEAR)
    assert dv01.dates.size == 0 and dv01.columns[0].size == 0 and dv01.totals == (0.0,)
    assert dv01.labels == ("cleared USD dv01 [USD per basis point]",)
    everything = risk_view(result, Risk.ALL, Bucket.DAY)
    assert everything.dates is prep.encoded.days
    assert everything.columns[0] is prep.daily_lots and everything.columns[1] is prep.daily_lots
    np.testing.assert_array_equal(everything.columns[2], [0.0])
    assert everything.labels == (*ALL_LABELS[:2], "cleared USD dv01 [USD per basis point]")


def test_a_dv01_bucket_past_the_largest_number_is_refused_by_its_payment_day() -> None:
    # A group is a contract and a payment day, so hundreds of them on one day take hundreds of
    # contracts: a one-barrel index of 512 monthly contracts from February 2027, a lot bought on
    # each of the first eight, sold on the next eight and so on, the bought lots paying on 4
    # January 2100 and the sold ones the day after, quoted at the largest number on a curve flat at
    # 0.9 from a year out. Every group's amount, NPV and DV01 is finite, and so are the mark and
    # the DV01 in all, since runs of eight keep every partial sum of the pairwise reductions in
    # bounds; the DV01 of the bought lots' payment day, 256 groups' at 73 years each, is past the
    # largest number, refused by that day before any result is made. Z26 stands first as the
    # schedule's boundary, which bounds the calendar and prices nothing.
    months = [(year, month) for year in range(2027, 2070) for month in range(1, 13)][1:513]
    contracts = (
        ("Z26", "2026-12-31"),
        *(
            (
                f"{'FGHJKMNQUVXZ'[month - 1]}{year % 100:02d}",
                str(np.busday_offset(np.datetime64(f"{year}-{month:02d}-15"), 0, roll="forward")),
            )
            for year, month in months
        ),
    )
    big = an_index(
        "BIG", contracts, ("2027-12-27",), ("USD", "BBL"), ("VOLUME", "BBL"), ("BIG", 1.0, "BBL")
    )
    runs = 32
    prep = prepared_on(
        terms_of(
            tuple(([1.0] * 8 + [-1.0] * 8) * runs),
            tuple((["2100-01-04"] * 8 + ["2100-01-05"] * 8) * runs),
            tuple([19_000] * 16 * runs),
            contracts=tuple(range(1, 513)),
            ix=big,
        )
    )
    flat_from_a_year = curve_of((AS_OF, 1.0), (A_YEAR, 0.9), ("2100-01-05", 0.9))
    with pytest.raises(ValueError) as refused:
        valued(prep, (LARGEST,) * 512, flat_from_a_year)
    assert str(refused.value) == (
        "the payment day 2100-01-04 has -inf of DV01 in all, expected a finite amount of USD per "
        "basis point; its groups' DV01s sum past the largest number"
    )
