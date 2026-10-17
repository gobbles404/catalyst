"""What a bilateral batch costs, bilateral-calculation-kernel.md. The preparation maps the unpaid
payment days once, for a bilateral batch alone: the counter's days mapped, the one helper beside the
cleared preparation's functions, the unique's numpy over the cleared ledger, the mapping's bytes
retained and its peak by unpaid group. The tick: the counter's unpaid groups, slots weighted,
factors read and reductions; the same functions and numpy calls at five trades and at two thousand,
no day sorted or counted; and the peak following the groups, the slots, the live slots and the time
buckets, nothing per trade. The cleared preparation's and tick's ledgers are test_trade_budgets.py's
and did not move. The fixtures are that module's gas indexes and history, the batches bilateral and
financial with a counterparty, the curve anchored on the valuation day and running to the end of
2028, past every payment: lastday batches of one slot a contract and asian ones of a month of
pricing days each, valued on 10 March 2027, two thousand asian trades over twenty-four contracts
observing 519 days with 429 of them live; and the same asian trades over twenty-three contracts
valued on 10 October 2028, every one of their 497 days fixed and every group paid, the long strip
whose sums are over no live slot at all."""

from dataclasses import fields

import numpy as np
import pytest
from numpy.typing import NDArray
from test_seam_allocation import KEYWORD_CALL, SLACK, least_peak
from test_trade_budgets import (
    AS_OF,
    ASIAN_GAS,
    ASIAN_PAYS,
    GAS,
    HOLIDAYS,
    MONTH_DAYS,
    MONTHS,
    PAYMENT_CALENDAR,
    PAYS,
    PREPARATION_NUMPY,
    SCHEDULE_MONTHS,
    CallProfile,
    a_batch,
    a_history,
    a_market,
    observed_of,
)

from goosedove.globals.discount_curve import DiscountCurve, discount_curve
from goosedove.globals.unit_conversions import UNITS
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT
from goosedove.market.market import Market
from goosedove.trades.encoding import PaymentAxes, encoded
from goosedove.trades.evaluation import trade_results
from goosedove.trades.preparation import PreparedTrades, UnpaidPayments, prepared_trades
from goosedove.trades.resolution import month_bounds
from goosedove.trades.results import TradeResults, risk_view
from goosedove.trades.risk_report import Bucket, Risk
from goosedove.trades.schedule_methods import METHODS, ScheduleMethod
from goosedove.trades.terms import (
    BASES,
    PaymentTerms,
    QuantityPer,
    ResolvedTrades,
    Route,
    Settlement,
    one_choice,
    resolved_trades,
)

LATE = (
    "2028-10-10"  # every contract through September 2028 fixed and paid; October's is the market's
)


def curve_on(as_of: str) -> DiscountCurve:
    """A curve anchored on the valuation day, 1 there and 0.9 at the end of 2028."""
    return discount_curve(
        np.array([as_of, "2028-12-31"], dtype="datetime64[D]"), np.array([1.0, 0.9])
    )


def asian_live(contracts: int, as_of: str) -> int:
    """How many of an asian batch's slots are live on the valuation day, from the fixture's own
    dates: for each contract's month, the business days from the later of its first day and the
    valuation day, live on its own day, to its end, none for a month that ended before it."""
    months = MONTHS[1 : contracts + 1].astype("datetime64[D]")
    ends = (MONTHS[1 : contracts + 1] + np.timedelta64(1, "M")).astype("datetime64[D]")
    starts = np.maximum(months, np.datetime64(as_of))
    return int(np.busday_count(starts, ends, holidays=HOLIDAYS).clip(min=0).sum())


def slots_of(method: ScheduleMethod, contracts: int) -> int:
    """One slot a contract under lastday; a month of pricing days each under asian."""
    return int(MONTH_DAYS[1 : contracts + 1].sum()) if method is ScheduleMethod.ASIAN else contracts


# The method, components over contracts and the valuation day, then the live slots and the unpaid
# groups that day leaves, from the fixture's own dates: the five trades over November and December
# 2026 have all fixed and paid by 10 March 2027 under either method; two thousand lastday trades
# over twenty-four contracts leave twenty live slots and twenty unpaid groups, and two thousand
# asian ones 429 live days over the same twenty groups, one payment day a contract; two thousand
# asian trades over twenty-three contracts valued on 10 October 2028 leave nothing live and nothing
# unpaid, 497 days fixed and 23 groups paid.
CASES = [
    (ScheduleMethod.LASTDAY, 5, 2, AS_OF, 0, 0),
    (ScheduleMethod.LASTDAY, 2_000, 24, AS_OF, 20, 20),
    (ScheduleMethod.ASIAN, 5, 2, AS_OF, 0, 0),
    (ScheduleMethod.ASIAN, 2_000, 24, AS_OF, asian_live(24, AS_OF), 20),
    (ScheduleMethod.ASIAN, 2_000, 23, LATE, 0, 0),
]
IDS = [
    "five lastday trades, all paid",
    "two thousand lastday trades, twenty live",
    "five asian trades, all paid",
    "two thousand asian trades, 429 live days",
    "two thousand asian trades over 497 days, all paid",
]


def bilateral_terms(components: int, contracts: int, method: ScheduleMethod) -> ResolvedTrades:
    """test_trade_budgets' terms made bilateral: the route and a counterparty; under asian that
    module's asian index and its payment days, as its own asian_terms."""
    rows = 1 + np.arange(components, dtype=np.intp) % contracts
    asian = method is ScheduleMethod.ASIAN
    return resolved_trades(
        FIXED_FLOAT, ASIAN_GAS if asian else GAS, np.zeros(components, dtype=np.intp),
        Route.BILATERAL, Settlement.FINANCIAL, one_choice(METHODS, method, components),
        one_choice(BASES, QuantityPer.MONTH, components), None, None, None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        np.arange(components, dtype=np.intp), rows,
        np.where(np.arange(components) % 3 == 0, -3.0, 2.0), *month_bounds(SCHEDULE_MONTHS[rows]),
        3.0 + (np.arange(components) % 7) / 100,
        PaymentTerms(
            ("+2bd",) * components,
            (PAYMENT_CALENDAR,) * components,
            (ASIAN_PAYS if asian else PAYS)[rows],
        ),
        counterparty=("ACME Trading",) * components,
    )  # fmt: skip


def a_bilateral_batch(
    components: int, contracts: int, method: ScheduleMethod, as_of: str
) -> PreparedTrades:
    terms = bilateral_terms(components, contracts, method)
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    return prepared_trades(enc, a_history(as_of=as_of, ix=terms.index), WorkCounter())


def tick(prep: PreparedTrades, market: Market, curve: DiscountCurve) -> TradeResults:
    return trade_results(prep, market, WorkCounter(), curve)


def mapped(prep: PreparedTrades) -> UnpaidPayments:
    """The mapping a bilateral financial preparation always holds."""
    assert prep.unpaid_payments is not None
    return prep.unpaid_payments


# --- the preparation: the mapping once ----------------------------------------------------------


# The mapping's numpy over the cleared preparation's: the flatnonzero over the unsettled groups, the
# unique over their payment days with its sort, its inverse and the copies those take, the day
# counts' one conversion, and the four arrays frozen.
# The display axes' two more searches, since #186: the payment months and years placed from the
# valuation day's period beside the contract periods the cleared preparation places.
PAID_DISPLAY_NUMPY = {
    "ndarray.searchsorted": 2,
    "ndarray.astype": 4,  # the payment periods' keys and places, two a bucket
}
MAPPING_NUMPY = {
    "ndarray.argsort": 1,
    "ndarray.astype": 1,
    "ndarray.cumsum": 1,
    "ndarray.flatten": 1,
    "ndarray.nonzero": 1,
    "ndarray.ravel": 1,
    "ndarray.reshape": 1,
    "ndarray.setflags": 4,
    "numpy.asanyarray": 3,
    "numpy.empty": 2,
}


@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
def test_the_preparation_of_a_bilateral_batch_maps_its_unpaid_payment_days_once(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    method: ScheduleMethod,
    components: int,
    contracts: int,
    as_of: str,
    live: int,
    unpaid: int,
) -> None:
    terms = bilateral_terms(components, contracts, method)
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    history = a_history(as_of=as_of, ix=terms.index)
    counter = WorkCounter()
    prep = prepared_trades(enc, history, counter)
    slots = slots_of(method, contracts)
    assert counter.freeze().as_dict() == {
        "display_periods": prep.by_month.periods.size + prep.by_year.periods.size,  # since #186
        "fixings_read": slots - live,
        "payment_days_mapped": unpaid,  # one payment day a contract: a day an unpaid group
        "prepared_slots": slots,
    }
    # The unsettled groups in order, their one day each, and the time fractions ACT/365F from the
    # fixture's own dates; every array frozen and retained, eight bytes a day and twenty-four a
    # group.
    pays = mapped(prep)
    unsettled = np.flatnonzero(~prep.is_settled)
    assert unsettled.size == unpaid
    np.testing.assert_array_equal(pays.groups, unsettled)
    payment_date = enc.payment_date
    assert payment_date is not None
    np.testing.assert_array_equal(pays.days, np.sort(payment_date[unsettled]))
    np.testing.assert_array_equal(pays.days[pays.day_of_group], payment_date[unsettled])
    np.testing.assert_array_equal(
        pays.tau, (payment_date[unsettled] - np.datetime64(as_of)).astype(np.int64) / 365.0
    )
    arrays = (pays.days, pays.groups, pays.day_of_group, pays.tau)
    assert all(not array.flags.writeable for array in arrays)
    assert sum(array.nbytes for array in arrays) == 8 * (pays.days.size + 3 * unpaid)
    # The one helper beside the cleared preparation's functions, the unique's numpy over the
    # cleared ledger, and the peak within 192 bytes an unpaid group and two slacks of the cleared
    # preparation's, the unique's own arrays the slack when no group is unpaid.
    assert call_profile(lambda: prepared_trades(enc, history, WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_unsettled_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 4,
        "rows_through": 4,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "_unpaid_payments": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 4,
    }
    numpy = numpy_calls(lambda: prepared_trades(enc, history, WorkCounter()))
    assert numpy == {
        k: PREPARATION_NUMPY.get(k, 0) + MAPPING_NUMPY.get(k, 0) + PAID_DISPLAY_NUMPY.get(k, 0)
        for k in PREPARATION_NUMPY | MAPPING_NUMPY | PAID_DISPLAY_NUMPY
    }, numpy
    cleared = a_batch(components, contracts) if method is ScheduleMethod.LASTDAY else None
    if cleared is not None:
        plain = prepared_trades(cleared, history, WorkCounter())
        assert plain.unpaid_payments is None  # a cleared batch discounts nothing and maps nothing
        assert least_peak(lambda: prepared_trades(enc, history, WorkCounter())) <= (
            least_peak(lambda: prepared_trades(cleared, history, WorkCounter()))
            + 192 * unpaid
            + 2 * SLACK
        )


# --- the tick -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
def test_a_bilateral_tick_reports_its_factors_groups_slots_and_reductions(
    method: ScheduleMethod, components: int, contracts: int, as_of: str, live: int, unpaid: int
) -> None:
    prep = a_bilateral_batch(components, contracts, method, as_of)
    counter = WorkCounter()
    trade_results(prep, a_market(prep.history), counter, curve_on(as_of))
    assert counter.freeze().as_dict() == {
        "groups_valued": unpaid,
        "kernel": 1,
        "live_prices_read": prep.live_references.size,  # one quote a live contract
        "payment_factors_read": unpaid,  # one payment day a contract: a factor an unpaid group
        # The lots onto the references, the days, the months and the years; the DV01s onto the
        # payment days, their months and their years.
        "risk_reductions": 7,
        "slots_discounted": slots_of(method, contracts),  # every slot, a fixed one by nothing
    }


@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
def test_a_bilateral_tick_runs_the_same_functions_at_any_size(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    method: ScheduleMethod,
    components: int,
    contracts: int,
    as_of: str,
    live: int,
    unpaid: int,
) -> None:
    prep = a_bilateral_batch(components, contracts, method, as_of)
    quoted = a_market(prep.history)  # made before the ledger looks, as the market is on a sheet
    curve = curve_on(as_of)
    assert call_profile(lambda: tick(prep, quoted, curve)) == {
        "trade_results": 1,
        "_the_curve": 1,  # the four rules, before any quote is read
        "DiscountCurve.start_date": 2,  # the rule's look and the factors' positions
        "DiscountCurve.max_date": 1,  # the coverage rule
        "Market.live_prices": 1,
        "_discounted": 1,
        "early_risk": 2,  # the discounted lots and the DV01 before the start, since #186
        "early_fact": 4,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 6,
    }
    # No sort, no unique, no count: the days are the preparation's. The positions of the unpaid
    # days on the curve, the one conversion; the error state set once, the rules the judge; the
    # ones over the groups and the two zeros, the NPVs and the DV01s; the sums of the live
    # amount, the NPVs, the DV01s and the discounted lots; the looks that hold the coverage, the
    # amounts, the discounted lots by reference, the sensitivity, the three views of the lots and
    # the three of the DV01 finite, with the market's own; the bincounts' reductions among the
    # rest; and the new arrays frozen, thirteen of them. The same with no slot live: the sums are
    # over every slot and never over none.
    assert numpy_calls(lambda: tick(prep, quoted, curve)) == {
        "ndarray.any": 12,  # since #190 the live contributions finite before the groups sum them
        "ndarray.astype": 1,
        "ndarray.nonzero": 4,  # the discounted lots and the DV01 before the start, since #186
        "ndarray.ravel": 4,
        "ndarray.setflags": 13,
        "ndarray.sum": 3,  # the global live sum is the cleared route's alone since #190
        "numpy._make_extobj": 2,  # the contributions' flags and the discounting's, since #190
        "numpy.asanyarray": 4,  # the four looks' views
        "numpy.empty": 1,
        "numpy.zeros": 2,
        "ufunc.reduce": 15,
    }


# The peak follows the payment groups, the slots, the live slots and the time buckets: a dozen
# arrays over the groups; the factor gathered onto every slot and the slot's lots, 16 bytes a slot;
# the cleared tick's quote and contribution on a live slot and the bilateral path's live groups, 32
# a live slot; the three views over the days, the months and the years; and, since #178, the three
# DV01 views over the payment days, their months and their years; within four slacks.
# Measured 3,440 bytes for two groups and no live slot, 5,909 for twenty-four groups and twenty
# live slots, 4,105 for two asian groups over 43 days, 22,744 for twenty-four over 519 days with 429
# live and 15,139 for the fully paid strip of 497 days, on 2026-10-11 with the three DV01 views,
# against 2,992, 5,093, 3,648, 22,808 and 15,203 the day before and 1,210, 1,418, 1,210, 10,960
# and 1,210 for the cleared tick of the same batches. The retained arrays are exactly the new
# vectors' bytes, floats every one, the fully paid strip's as well.
@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
def test_a_bilateral_tick_allocates_by_group_slot_and_bucket_and_retains_its_vectors(
    method: ScheduleMethod, components: int, contracts: int, as_of: str, live: int, unpaid: int
) -> None:
    prep = a_bilateral_batch(components, contracts, method, as_of)
    encoding = prep.encoded
    groups = encoding.group_contract.size
    slots = encoding.slot_group.size
    buckets = encoding.days.size + encoding.contract_months.size + encoding.contract_years.size
    axes = encoding.payment_axes
    assert axes is not None
    paid = axes.days.size + axes.months.size + axes.years.size
    quoted = a_market(prep.history)
    curve = curve_on(as_of)
    assert least_peak(lambda: tick(prep, quoted, curve)) <= (
        128 * groups + 16 * slots + 32 * live + 8 * (buckets + paid) + KEYWORD_CALL + 4 * SLACK
    )
    result = tick(prep, quoted, curve)
    new: tuple[NDArray[np.float64] | None, ...] = (
        result.discounted_lot_delta,
        result.discounted_price_sensitivity,
        result.discounted_daily_lots,
        result.discounted_monthly_lots,
        result.discounted_yearly_lots,
        result.payment_amount,
        result.npv_by_group,
        result.dv01_by_group,
        result.payment_factor,
        result.dv01_by_day,
        result.dv01_by_month,
        result.dv01_by_year,
    )
    retained = sum(0 if array is None else array.nbytes for array in new)
    assert retained == 8 * (2 * encoding.references.size + buckets + paid + 4 * groups)
    assert all(array is None or array.dtype == np.float64 for array in new)
    # The nominal vectors are the preparation's, by reference, not copies.
    assert result.lot_delta is prep.lot_delta and result.price_sensitivity is prep.price_sensitivity


# --- the payment-time axes and the risk views, since #178 -----------------------------------------


def axes_of(prep: PreparedTrades) -> PaymentAxes:
    axes = prep.encoded.payment_axes
    assert axes is not None
    return axes


@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
def test_the_encoding_of_a_bilateral_batch_makes_its_payment_axes_once(
    call_profile: CallProfile,
    method: ScheduleMethod,
    components: int,
    contracts: int,
    as_of: str,
    live: int,
    unpaid: int,
) -> None:
    terms = bilateral_terms(components, contracts, method)
    counter = WorkCounter()
    enc = encoded(terms, observed_of(terms), UNITS, counter)
    axes = enc.payment_axes
    assert axes is not None
    payment_date = enc.payment_date
    assert payment_date is not None
    distinct = np.unique(payment_date)
    # One payment day a contract, counted; the three payment axes and the three unions as the
    # definitions say, every place saved, every array frozen.
    assert counter.freeze().as_dict()["encoded_payment_days"] == distinct.size
    assert distinct.size == contracts
    np.testing.assert_array_equal(axes.days, distinct)
    np.testing.assert_array_equal(axes.days[axes.day_of_group], payment_date)
    months = np.unique(distinct.astype("datetime64[M]")).astype("datetime64[D]")
    years = np.unique(distinct.astype("datetime64[Y]")).astype("datetime64[D]")
    np.testing.assert_array_equal(axes.months, months)
    np.testing.assert_array_equal(axes.months[axes.month_of_day], distinct.astype("datetime64[M]"))
    np.testing.assert_array_equal(axes.years, years)
    np.testing.assert_array_equal(axes.years[axes.year_of_month], months.astype("datetime64[Y]"))
    # The one union, the days': since #186 the month and year displays are the preparation's.
    np.testing.assert_array_equal(axes.union_days, np.union1d(enc.days, axes.days))
    np.testing.assert_array_equal(axes.union_days[axes.observed_in_days], enc.days)
    np.testing.assert_array_equal(axes.union_days[axes.paid_in_days], axes.days)
    arrays = [getattr(axes, field.name) for field in fields(axes)]
    assert all(not array.flags.writeable for array in arrays)
    # Retained: eight bytes an entry of every array, the three axes with their places and the day
    # union with both kinds' places.
    d, m, y = axes.days.size, axes.months.size, axes.years.size
    assert sum(array.nbytes for array in arrays) == 8 * (
        d + payment_date.size + m + d + y + m + axes.union_days.size + enc.days.size + d
    )
    # The cleared encoding's functions and, beside them, the axes once and the one union.
    cleared = call_profile(lambda: encoded(terms, observed_of(terms), UNITS, WorkCounter()))
    assert cleared["_the_payment_axes"] == 1 and cleared["_the_union"] == 1
    assert cleared["WorkCounter.hit"] == 6


@pytest.mark.parametrize(
    ("method", "components", "contracts", "as_of", "live", "unpaid"), CASES, ids=IDS
)
def test_a_risk_view_copies_through_saved_places_and_discovers_nothing(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    method: ScheduleMethod,
    components: int,
    contracts: int,
    as_of: str,
    live: int,
    unpaid: int,
) -> None:
    prep = a_bilateral_batch(components, contracts, method, as_of)
    result = tick(prep, a_market(prep.history), curve_on(as_of))
    for risk in (Risk.NOMINAL_DELTA, Risk.DELTA, Risk.DV01):
        # By day, by reference: no numpy call at all and nothing allocated beyond the record. By
        # month and by year, since #186, one zeros over the display axis filled through the saved
        # places, eight bytes a row.
        assert numpy_calls(lambda r=risk: risk_view(result, r, Bucket.DAY)) == {}
        assert least_peak(lambda r=risk: risk_view(result, r, Bucket.DAY)) <= SLACK
        for bucket in (Bucket.MONTH, Bucket.YEAR):
            view = risk_view(result, risk, bucket)
            assert numpy_calls(lambda r=risk, b=bucket: risk_view(result, r, b)) == {
                "numpy.zeros": 1
            }
            assert least_peak(lambda r=risk, b=bucket: risk_view(result, r, b)) <= (
                8 * view.dates.size + SLACK
            )
    for bucket in Bucket:
        # All three: three zeros over the axis, each filled through its saved places; nothing
        # sorted, nothing summed, nothing unique; by month and by year the saved refusals read.
        view = risk_view(result, Risk.ALL, bucket)
        assert numpy_calls(lambda b=bucket: risk_view(result, Risk.ALL, b)) == {"numpy.zeros": 3}
        selected = (
            {"_day_view": 1}
            if bucket is Bucket.DAY
            else {"_period_view": 1, "_saved": 1, "EarlyRisk.refuse": 3}
        )
        assert call_profile(lambda b=bucket: risk_view(result, Risk.ALL, b)) == {
            "risk_view": 1,
            "delta_labels": 1,  # the headings, spelled once in risk_report.py for both paths
            "dv01_label": 1,
            **selected,
            "placed": 3,
        }
        assert least_peak(lambda b=bucket: risk_view(result, Risk.ALL, b)) <= (
            24 * view.dates.size + SLACK
        )
