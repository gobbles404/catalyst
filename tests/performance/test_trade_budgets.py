"""What the trade kernel costs, called directly: the work each step reports to its counter,
which of the package's functions run and how many times, and which numpy C calls cProfile sees,
at five components and at two thousand alike. The pins are the pipeline's work rules: a tick
reads one quote per live reference, gathers them onto the live slots and makes one kernel call,
and does nothing of the encoding or the preparation again; a preparation reads one settle per
fixed slot and nothing per component, per observation or per day of the calendar; an encoding
does one pass over the components, one over the observations and one over the slots. Every
ledger here is the same at any batch size, which is what makes it a ledger and not a count of
trades."""

from collections.abc import Callable

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.calendar.calendar import calendar
from goosedove.globals.unit_conversions import UNITS
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.index import index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FUTURE
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.futures_fixings import futures_fixings
from goosedove.market_data.price_vector import price_vector
from goosedove.trades.encoding import Encoded, encoded
from goosedove.trades.evaluation import results
from goosedove.trades.observations import observed
from goosedove.trades.preparation import prepared
from goosedove.trades.terms import (
    PaymentTerms,
    QuantityPer,
    Route,
    ScheduleMethod,
    Settlement,
    resolved_trades,
)

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
SIZES = [(5, 2), (2_000, 24)]  # components over contracts: the page's five, and two thousand
IDS = ["five trades", "two thousand trades"]


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


# A financial index of 25 monthly contracts from October 2026, each expiring on the last
# business day on or before the 25th of its month and paying on the month's last day, so that a
# batch may hold contracts that have fixed, contracts that have paid and contracts still live
# under one history.
MONTHS = np.arange("2026-10", "2028-11", dtype="datetime64[M]")
HOLIDAYS = dates("2026-12-25", "2027-01-01", "2027-12-24")
EXPIRIES = np.busday_offset(
    MONTHS.astype("datetime64[D]") + np.timedelta64(24, "D"), 0, roll="backward", holidays=HOLIDAYS
)
CODES = tuple(f"c{i}" for i in range(EXPIRIES.size))
PAYS: NDArray[np.datetime64] = np.array(
    (MONTHS + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D"),
    dtype="datetime64[D]",
)
PAYMENT_CALENDAR = holiday_calendar(HOLIDAYS)
GAS = index(
    "gas",
    futures_schedule(CODES, EXPIRIES, None),
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot",), np.array([10_000.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    holiday_calendar(HOLIDAYS),
    UNITS,
)
# Valued on 10 March 2027: the contracts of October 2026 to February 2027, rows 0 to 4, have
# fixed and paid; a batch over rows 1 to 24 then has four fixed inputs and twenty live ones, and
# one over rows 1 and 2 has two fixed and none live.
AS_OF = "2027-03-10"


def a_batch(components: int, contracts: int) -> Encoded:
    """That many single-month trades spread over the first contracts after the boundary, lots
    and prices varying, encoded on a counter of its own."""
    rows = 1 + np.arange(components, dtype=np.intp) % contracts
    terms = resolved_trades(
        FUTURE,
        GAS,
        0,
        Route.CLEARED,
        Settlement.FINANCIAL,
        ScheduleMethod.LASTDAY,
        "LOT",
        QuantityPer.MONTH,
        None,
        None,
        None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        np.arange(components, dtype=np.intp),
        rows,
        np.where(np.arange(components) % 3 == 0, -3.0, 2.0),
        3.0 + (np.arange(components) % 7) / 100,
        PaymentTerms(np.full(components, 2), (PAYMENT_CALENDAR,) * components, PAYS[rows]),
    )
    return encoded(terms, observed(terms), UNITS, WorkCounter())


def a_history(as_of: str = AS_OF) -> MarketHistory:
    cal = calendar(valuation_date(np.datetime64(as_of, "D"), 0.5), GAS)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = 3.0 + (np.arange(priced.size) % 11) / 100
    return market_history(cal, futures_fixings(priced[::-1].copy(), settles[::-1].copy(), GAS))


def a_market(history: MarketHistory) -> Market:
    """A quote for every contract from the first unfixed period's through the last."""
    cal = history.calendar
    remaining = len(CODES) - int(cal.contract[cal.first_unfixed])
    return market(history, price_vector("gas", 3.5 + np.arange(remaining) / 100))


# --- the work each step reports -------------------------------------------------------------


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_the_encoding_reports_its_components_its_observations_and_its_slots(
    components: int, contracts: int
) -> None:
    counter = WorkCounter()
    terms = a_batch(components, contracts).terms
    encoded(terms, observed(terms), UNITS, counter)
    assert counter.freeze().as_dict() == {
        "encoded_components": components,
        "encoded_observations": components,  # lastday: one per component
        "encoded_slots": contracts,  # one per contract, on its expiry day
    }


@pytest.mark.parametrize(("components", "contracts", "fixed"), [(5, 2, 2), (2_000, 24, 4)], ids=IDS)
def test_the_preparation_reports_its_slots_and_one_settle_read_per_fixed_slot(
    components: int, contracts: int, fixed: int
) -> None:
    counter = WorkCounter()
    prepared(a_batch(components, contracts), a_history(), counter)
    assert counter.freeze().as_dict() == {"fixings_read": fixed, "prepared_slots": contracts}


@pytest.mark.parametrize(("components", "contracts", "live"), [(5, 2, 0), (2_000, 24, 20)], ids=IDS)
def test_a_tick_reports_one_kernel_call_and_one_quote_per_live_reference(
    components: int, contracts: int, live: int
) -> None:
    history = a_history()
    prep = prepared(a_batch(components, contracts), history, WorkCounter())
    counter = WorkCounter()
    results(prep, a_market(history), counter)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": live}


# --- which functions run, and how many times, whatever the size -----------------------------

# The preparation's numpy, the same at any size: the two looks that refuse a slot before the
# calendar or on a closed day, the unique over the live references with its sort, the searches
# of the history's fixed rows and the live references, the bincounts' reductions and the sums,
# the frozen arrays.
PREPARATION_NUMPY = {
    "ndarray.any": 2,
    "ndarray.argsort": 1,
    "ndarray.astype": 1,
    "ndarray.cumsum": 1,
    "ndarray.flatten": 1,
    "ndarray.nonzero": 1,
    "ndarray.ravel": 1,
    "ndarray.reshape": 1,
    "ndarray.searchsorted": 1,
    "ndarray.setflags": 8,
    "ndarray.sum": 4,
    "numpy.asanyarray": 3,
    "numpy.zeros": 1,
    "numpy.empty": 2,
    "ufunc.reduce": 6,
}


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_a_tick_runs_evaluation_alone_and_nothing_of_the_steps_before(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int
) -> None:
    history = a_history()
    prep = prepared(a_batch(components, contracts), history, WorkCounter())
    quoted = a_market(history)
    assert call_profile(lambda: results(prep, quoted, WorkCounter())) == {
        "results": 1,
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }
    # The gather and the multiplication are dispatched in C and unseen; delta and its total are
    # the preparation's, shared and not made again. What is seen is the market's one look at the
    # references asked for, with its reduction, the sum of the dated contributions, and the
    # contributions frozen.
    assert numpy_calls(lambda: results(prep, quoted, WorkCounter())) == {
        "ndarray.any": 1,
        "ndarray.setflags": 1,
        "ndarray.sum": 1,
        "ufunc.reduce": 2,
    }


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_the_encoding_runs_the_same_functions_at_any_size(
    call_profile: CallProfile, components: int, contracts: int
) -> None:
    terms = a_batch(components, contracts).terms
    obs = observed(terms)
    assert call_profile(lambda: encoded(terms, obs, UNITS, WorkCounter())) == {
        "encoded": 1,
        "_the_references": 1,
        "contract_on": 1,  # the calendar's rule, one search over the schedule
        "_the_slots": 1,
        "_one_payment_day_per_group": 1,
        "UnitConversions.factor": 2,
        "UnitConversions.category": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    assert call_profile(lambda: observed(terms)) == {
        "observed": 1,
        "observations": 1,
    }


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_the_preparation_runs_the_same_functions_at_any_size(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int
) -> None:
    enc = a_batch(components, contracts)
    history = a_history()
    assert call_profile(lambda: prepared(enc, history, WorkCounter())) == {
        "prepared": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }
    numpy = numpy_calls(lambda: prepared(enc, history, WorkCounter()))
    assert numpy == PREPARATION_NUMPY, numpy
