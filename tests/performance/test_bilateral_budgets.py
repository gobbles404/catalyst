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

import numpy as np
import pytest
from numpy.typing import NDArray
from test_seam_allocation import SLACK, least_peak
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
from goosedove.trades.encoding import encoded
from goosedove.trades.evaluation import TradeResults, trade_results
from goosedove.trades.preparation import PreparedTrades, UnpaidPayments, prepared_trades
from goosedove.trades.resolution import month_bounds
from goosedove.trades.terms import (
    BASES,
    METHODS,
    PaymentTerms,
    QuantityPer,
    ResolvedTrades,
    Route,
    ScheduleMethod,
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
            np.full(components, 2),
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
        "_unpaid_payments": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    numpy = numpy_calls(lambda: prepared_trades(enc, history, WorkCounter()))
    assert numpy == {
        k: PREPARATION_NUMPY.get(k, 0) + MAPPING_NUMPY.get(k, 0)
        for k in PREPARATION_NUMPY | MAPPING_NUMPY
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
        "risk_reductions": 4,  # the lots onto the references, the days, the months, the years
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
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 6,
    }
    # No sort, no unique, no count: the days are the preparation's. The positions of the unpaid
    # days on the curve, the one conversion; the error state set once, the rules the judge; the
    # ones over the groups and the two zeros, the NPVs and the DV01s; the sums of the live
    # amount, the NPVs, the DV01s and the discounted lots; the looks that hold the coverage, the
    # amounts, the discounted lots by reference, the sensitivity and the three views finite, with
    # the market's own; the bincounts' reductions among the rest; and the new arrays frozen, ten
    # of them. The same with no slot live: the sums are over every slot and never over none.
    assert numpy_calls(lambda: tick(prep, quoted, curve)) == {
        "ndarray.any": 8,
        "ndarray.astype": 1,
        "ndarray.setflags": 10,
        "ndarray.sum": 4,
        "numpy._make_extobj": 1,
        "numpy.empty": 1,
        "numpy.zeros": 2,
        "ufunc.reduce": 12,
    }


# The peak follows the payment groups, the slots, the live slots and the time buckets: a dozen
# arrays over the groups; the factor gathered onto every slot and the slot's lots, 16 bytes a slot;
# the cleared tick's quote and contribution on a live slot and the bilateral path's live groups, 32
# a live slot; and the three views over the days, the months and the years; within four slacks.
# Measured 2,992 bytes for two groups and no live slot, 5,093 for twenty-four groups and twenty
# live slots, 3,648 for two asian groups over 43 days, 22,808 for twenty-four over 519 days with 429
# live and 15,203 for the fully paid strip of 497 days, on 2026-10-10, against 1,210, 1,418, 1,210,
# 10,960 and 1,210 for the cleared tick of the same batches. The retained arrays are exactly the new
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
    buckets = encoding.days.size + encoding.months.size + encoding.years.size
    quoted = a_market(prep.history)
    curve = curve_on(as_of)
    assert least_peak(lambda: tick(prep, quoted, curve)) <= (
        128 * groups + 16 * slots + 32 * live + 8 * buckets + 4 * SLACK
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
    )
    retained = sum(0 if array is None else array.nbytes for array in new)
    assert retained == 8 * (2 * encoding.references.size + buckets + 4 * groups)
    assert all(array is None or array.dtype == np.float64 for array in new)
    # The nominal vectors are the preparation's, by reference, not copies.
    assert result.lot_delta is prep.lot_delta and result.price_sensitivity is prep.price_sensitivity
