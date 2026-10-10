"""What a bilateral tick costs, bilateral-calculation-kernel.md: the counter's unpaid groups, live
slots, factors read and reductions; the same functions and numpy calls at five trades and at two
thousand; and the peak following the groups and the live slots, nothing per trade. The cleared
tick's ledgers are test_trade_budgets.py's and did not move. The fixtures are that module's gas
index and history, valued on 10 March 2027, the batches bilateral and financial with a
counterparty, the curve anchored on the valuation day and running to the end of 2028, past every
payment."""

import numpy as np
import pytest
from numpy.typing import NDArray
from test_seam_allocation import SLACK, least_peak
from test_trade_budgets import (
    AS_OF,
    GAS,
    PAYMENT_CALENDAR,
    PAYS,
    SCHEDULE_MONTHS,
    CallProfile,
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
from goosedove.trades.preparation import PreparedTrades, prepared_trades
from goosedove.trades.resolution import month_bounds
from goosedove.trades.terms import (
    BASES,
    METHODS,
    PaymentTerms,
    QuantityPer,
    Route,
    ScheduleMethod,
    Settlement,
    one_choice,
    resolved_trades,
)

# Components over contracts, then the live references and the unpaid groups the valuation day
# leaves, from the fixture's own dates: the five trades over November and December 2026 have all
# paid by 10 March 2027, and two thousand over twenty-four contracts leave twenty of each.
SIZES = [(5, 2, 0, 0), (2_000, 24, 20, 20)]
IDS = ["five trades, all paid", "two thousand trades, twenty live"]
CURVE = discount_curve(np.array([AS_OF, "2028-12-31"], dtype="datetime64[D]"), np.array([1.0, 0.9]))


def bilateral_terms(components: int, contracts: int):
    rows = 1 + np.arange(components, dtype=np.intp) % contracts
    return resolved_trades(
        FIXED_FLOAT, GAS, np.zeros(components, dtype=np.intp), Route.BILATERAL,
        Settlement.FINANCIAL, one_choice(METHODS, ScheduleMethod.LASTDAY, components),
        one_choice(BASES, QuantityPer.MONTH, components), None, None, None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        np.arange(components, dtype=np.intp), rows,
        np.where(np.arange(components) % 3 == 0, -3.0, 2.0), *month_bounds(SCHEDULE_MONTHS[rows]),
        3.0 + (np.arange(components) % 7) / 100,
        PaymentTerms(np.full(components, 2), (PAYMENT_CALENDAR,) * components, PAYS[rows]),
        counterparty=("ACME Trading",) * components,
    )  # fmt: skip


def a_bilateral_batch(components: int, contracts: int) -> PreparedTrades:
    terms = bilateral_terms(components, contracts)
    enc = encoded(terms, observed_of(terms), UNITS, WorkCounter())
    return prepared_trades(enc, a_history(), WorkCounter())


def tick(prep: PreparedTrades, market: Market, curve: DiscountCurve = CURVE) -> TradeResults:
    return trade_results(prep, market, WorkCounter(), curve)


@pytest.mark.parametrize(("components", "contracts", "live", "unpaid"), SIZES, ids=IDS)
def test_a_bilateral_tick_reports_its_factors_groups_slots_and_reductions(
    components: int, contracts: int, live: int, unpaid: int
) -> None:
    prep = a_bilateral_batch(components, contracts)
    counter = WorkCounter()
    trade_results(prep, a_market(prep.history), counter, CURVE)
    assert counter.freeze().as_dict() == {
        "groups_valued": unpaid,
        "kernel": 1,
        "live_prices_read": live,
        "payment_factors_read": unpaid,  # one payment day a contract: a factor an unpaid group
        "risk_reductions": 4,  # the lots onto the references, the days, the months, the years
        "slots_discounted": live,
    }


@pytest.mark.parametrize(("components", "contracts", "live", "unpaid"), SIZES, ids=IDS)
def test_a_bilateral_tick_runs_the_same_functions_at_any_size(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    components: int,
    contracts: int,
    live: int,
    unpaid: int,
) -> None:
    prep = a_bilateral_batch(components, contracts)
    quoted = a_market(prep.history)  # made before the ledger looks, as the market is on a sheet
    assert call_profile(lambda: tick(prep, quoted)) == {
        "trade_results": 1,
        "_the_curve": 1,  # the four rules, before any quote is read
        "DiscountCurve.start_date": 2,  # the rule's look and the factors' positions
        "DiscountCurve.max_date": 1,  # the coverage rule
        "Market.live_prices": 1,
        "_discounted": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 6,
    }
    # The unique over the unpaid payment days, with its sort and its inverse; the positions of
    # those days on the curve and the day counts, two conversions; the sums of the live amount, the
    # NPVs, the DV01s and the discounted lots; the looks that hold the amounts, the two totals, the
    # discounted lots by reference and the three views finite; the unpaid groups counted; the
    # bincounts' reductions among the rest; and the new arrays frozen, ten of them.
    assert numpy_calls(lambda: tick(prep, quoted)) == {
        "ndarray.any": 7,
        "ndarray.argsort": 1,
        "ndarray.astype": 2,
        "ndarray.cumsum": 1,
        "ndarray.flatten": 1,
        "ndarray.reshape": 1,
        "ndarray.setflags": 10,
        "ndarray.sum": 4,
        "numpy.asanyarray": 2,
        "numpy.count_nonzero": 1,
        "numpy.empty": 3,
        "numpy.zeros": 1,
        "ufunc.reduce": 11,
    }


# The peak follows the payment groups and the live slots, the temporaries of the discounted path,
# a dozen arrays over the groups and three over the live slots, and the headers of those arrays,
# within four slacks: measured 3,608 bytes for two groups and no live slot and 7,600 for
# twenty-four groups and twenty live slots on 2026-10-10, against 1,210 and 1,418 for the cleared
# tick of the same batches. The retained arrays are exactly the new vectors' bytes.
@pytest.mark.parametrize(("components", "contracts", "live", "unpaid"), SIZES, ids=IDS)
def test_a_bilateral_tick_allocates_by_group_and_live_slot_and_retains_its_vectors(
    components: int, contracts: int, live: int, unpaid: int
) -> None:
    prep = a_bilateral_batch(components, contracts)
    groups = prep.encoded.group_contract.size
    quoted = a_market(prep.history)
    assert least_peak(lambda: tick(prep, quoted)) <= 128 * groups + 48 * live + 4 * SLACK
    result = tick(prep, quoted)
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
    encoding = prep.encoded
    assert retained == 8 * (
        2 * encoding.references.size
        + encoding.days.size
        + encoding.months.size
        + encoding.years.size
        + 4 * groups
    )
    # The nominal vectors are the preparation's, by reference, not copies.
    assert result.lot_delta is prep.lot_delta and result.price_sensitivity is prep.price_sensitivity
