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
from dataclasses import replace

import numpy as np
import pytest
from numpy.typing import NDArray
from test_seam_allocation import KEYWORD_CALL, SLACK, least_peak

from goosedove.calendar.calendar import calendar
from goosedove.excel.utilities import shown
from goosedove.globals.unit_conversions import UNITS
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.contract_codes import schedule_months
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT
from goosedove.instruments.fields import DatesOrTexts
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory, market_history
from goosedove.market_data.futures_fixings import futures_fixings
from goosedove.market_data.iferc_fixings import iferc_fixings
from goosedove.market_data.price_vector import price_vector
from goosedove.trades.encoding import Encoded, encoded
from goosedove.trades.evaluation import trade_results
from goosedove.trades.observations import Observations, observations, observed
from goosedove.trades.preparation import PreparedTrades, prepared_trades
from goosedove.trades.schedule_methods import METHODS, ScheduleMethod
from goosedove.trades.terms import (
    BASES,
    FREQUENCIES,
    PaymentTerms,
    QuantityPer,
    ResolvedTrades,
    Route,
    Settlement,
    SettlementFrequency,
    month_bounds,
    one_choice,
    resolved_trades,
)

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
SIZES = [(5, 2), (2_000, 24)]  # components over contracts: the page's five, and two thousand
IDS = ["five trades", "two thousand trades"]


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def observed_of(terms: ResolvedTrades) -> Observations:
    """The observations the terms' schedule method gives them over the days each component
    covers, as resolution makes them."""
    return observed(
        terms.legs[0].schedule_method[terms.occurrence],
        terms.legs[0].index,
        terms.legs[0].contract,
        terms.start_date,
        terms.end_date,
        terms.named,
    )


# A financial index of 25 monthly contracts from October 2026, each expiring on the last
# business day on or before the 25th of its month and paying on the month's last day, so that a
# batch may hold contracts that have fixed, contracts that have paid and contracts still live
# under one history.
MONTHS = np.arange("2026-10", "2028-11", dtype="datetime64[M]")
HOLIDAYS = dates("2026-12-25", "2027-01-01", "2027-12-24")
EXPIRIES = np.busday_offset(
    MONTHS.astype("datetime64[D]") + np.timedelta64(24, "D"), 0, roll="backward", holidays=HOLIDAYS
)
LETTERS = "FGHJKMNQUVXZ"
CODES = tuple(f"{LETTERS[int(m.astype(int)) % 12]}{str(m)[2:4]}" for m in MONTHS)
# The schedule's months as the resolution reads them, the same under both indexes below, read
# once here so that no ledger counts the reading.
SCHEDULE_MONTHS = schedule_months(futures_schedule(CODES, EXPIRIES, None))
PAYS: NDArray[np.datetime64] = np.array(
    (MONTHS + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D"),
    dtype="datetime64[D]",
)
PAYMENT_CALENDAR = holiday_calendar(HOLIDAYS)
GAS = index(
    "gas",
    "Sample gas index",
    futures_schedule(CODES, EXPIRIES, None),
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot",), np.array([10_000.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    holiday_calendar(HOLIDAYS),
    "lot",
    UNITS,
)
# Valued on 10 March 2027: the contracts of October 2026 to February 2027, rows 0 to 4, have
# fixed and paid; a batch over rows 1 to 24 then has four fixed inputs and twenty live ones, and
# one over rows 1 and 2 has two fixed and none live.
AS_OF = "2027-03-10"


def a_batch(components: int, contracts: int) -> Encoded:
    """That many single-month trades spread over the first contracts after the boundary, lots
    and prices varying, encoded on a counter of its own."""
    terms = some_terms(components, contracts)
    return encoded(terms, (observed_of(terms),), UNITS, WorkCounter())


def some_terms(
    components: int,
    contracts: int,
    method: ScheduleMethod = ScheduleMethod.LASTDAY,
    basis: QuantityPer = QuantityPer.MONTH,
) -> ResolvedTrades:
    rows = 1 + np.arange(components, dtype=np.intp) % contracts
    return resolved_trades(
        FIXED_FLOAT,
        GAS,
        np.zeros(components, dtype=np.intp),
        Route.CLEARED,
        Settlement.FINANCIAL,
        one_choice(METHODS, method, components),
        one_choice(BASES, basis, components),
        one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, components),
        None,
        None,
        None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        np.arange(components, dtype=np.intp),
        rows,
        np.where(np.arange(components) % 3 == 0, -3.0, 2.0),
        *month_bounds(SCHEDULE_MONTHS[rows]),
        3.0 + (np.arange(components) % 7) / 100,
        PaymentTerms(
            DatesOrTexts.of_texts(("+2bd",) * components),
            (PAYMENT_CALENDAR,) * components,
            PAYS[rows],
        ),
    )


# The daily batch: the same trades, each observing the last `days` business days of its contract,
# the expiry among them, with a share each, as a daily average would; the days are the fixture's
# own arithmetic, business days counted back from the expiry on the index's holidays, and never
# the kernel's. Two thousand trades over twenty-four contracts and fifteen days make thirty
# thousand observations and 360 slots, fifteen a contract.
DAILY = [(5, 2, 3), (2_000, 24, 15)]
DAILY_IDS = ["five trades, three days", "two thousand trades, fifteen days"]


def daily_days(components: int, contracts: int, days: int) -> NDArray[np.datetime64]:
    rows = 1 + np.arange(components, dtype=np.intp) % contracts
    back = np.tile(-np.arange(days)[::-1], components)
    return np.busday_offset(
        np.repeat(EXPIRIES[rows], days), back, roll="backward", holidays=HOLIDAYS
    )


def a_daily_batch(components: int, contracts: int, days: int) -> Encoded:
    terms = some_terms(components, contracts)
    obs = observations(
        np.repeat(np.arange(components, dtype=np.intp), days),
        daily_days(components, contracts, days),
        np.full(components * days, 1 / days),
        components,
    )
    return encoded(terms, (obs,), UNITS, WorkCounter())


def daily_fixed_slots(components: int, contracts: int, days: int, as_of: str = AS_OF) -> int:
    """How many of the batch's slots have fixed by the valuation day, from the fixture's own
    dates: the distinct days before it."""
    return int((np.unique(daily_days(components, contracts, days)) < np.datetime64(as_of)).sum())


def a_history(as_of: str = AS_OF, ix: Index = GAS) -> MarketHistory:
    cal = calendar(valuation_date(np.datetime64(as_of, "D"), 0.5), ix)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = 3.0 + (np.arange(priced.size) % 11) / 100
    return market_history(cal, futures_fixings(priced[::-1].copy(), settles[::-1].copy(), ix))


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
    encoded(terms, (observed_of(terms),), UNITS, counter)
    assert counter.freeze().as_dict() == {
        "encoded_components": components,
        "encoded_groups": contracts,  # one payment day per contract: one group each
        "encoded_observations": components,  # lastday: one per component
        "encoded_slots": contracts,  # one per contract, on its expiry day
        "reserved_fee_components": components,  # clearing alone: cleared, no broker, since #188
    }


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_each_fee_charged_is_one_pass_over_its_components_and_an_uncharged_one_is_nothing(
    call_profile: CallProfile, components: int, contracts: int
) -> None:
    # Since #188, reserve-fee-applicability.md: the cleared, unbrokered batch charges clearing
    # alone, one pass and one count per component; brokered throughout it charges both fees, two
    # passes and two counts; bilateral without a broker it charges nothing, no pass and a count of
    # zero. The same functions at five components and at two thousand.
    terms = some_terms(components, contracts)
    every_row = np.ones(components, dtype=np.bool_)
    every_row.setflags(write=False)
    brokered = replace(terms, broker=("ION",) * components, brokered=every_row)
    bilateral = replace(terms, route=Route.BILATERAL, discount_curve_key=("SOFR",) * components)
    for batch, passes, charged in (
        (terms, 1, components),
        (brokered, 2, 2 * components),
        (bilateral, 0, 0),
    ):
        counter = WorkCounter()
        encoded(batch, (observed_of(batch),), UNITS, counter)
        assert counter.freeze()["reserved_fee_components"] == charged
        profile = call_profile(lambda b=batch: encoded(b, (observed_of(b),), UNITS, WorkCounter()))
        assert profile.get("_charged", 0) == passes and profile["reserves"] == 1


@pytest.mark.parametrize(("components", "contracts", "fixed"), [(5, 2, 2), (2_000, 24, 4)], ids=IDS)
def test_the_preparation_reports_its_slots_and_one_settle_read_per_fixed_slot(
    components: int, contracts: int, fixed: int
) -> None:
    counter = WorkCounter()
    prep = prepared_trades(a_batch(components, contracts), (a_history(),), counter)
    assert counter.freeze().as_dict() == {
        "display_periods": display_periods(prep),
        "fixings_read": fixed,
        "prepared_slots": contracts,
    }


@pytest.mark.parametrize(("components", "contracts", "live"), [(5, 2, 0), (2_000, 24, 20)], ids=IDS)
def test_a_tick_reports_one_kernel_call_and_one_quote_per_live_reference(
    components: int, contracts: int, live: int
) -> None:
    history = a_history()
    prep = prepared_trades(a_batch(components, contracts), (history,), WorkCounter())
    counter = WorkCounter()
    trade_results(prep, (a_market(history),), counter)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": live}


# --- which functions run, and how many times, whatever the size -----------------------------

# The preparation's numpy, the same at any size: the one look that refuses a slot before the
# calendar begins, the unique over the live references with its sort, the search of the history's
# fixed rows, the bincounts' reductions and the sums, the frozen arrays; a closed day is the
# encoding's to refuse, so no look here.


def display_periods(prep: PreparedTrades) -> int:
    """The periods of the two display axes the preparation made, since #186: the valuation day's
    month and year through the last contract's, two for the five-trade fixtures and twenty-two
    for two thousand trades over two years."""
    return prep.legs[0].by_month.periods.size + prep.legs[0].by_year.periods.size


PREPARATION_NUMPY = {
    "generic.astype": 2,  # the valuation day to its month and its year, since #186
    "ndarray.any": 9,  # the boundary slot; since #190 the set amounts by slot and by group and the
    # sensitivity by contract finite; the lots, the nominal delta and the three views finite
    "ndarray.argsort": 1,
    "ndarray.astype": 7,  # the slot rows, and since #186 the two display axes' keys, periods and
    # first days, three a bucket
    "ndarray.cumsum": 1,
    "ndarray.flatten": 1,
    "ndarray.nonzero": 3,  # the live slots, and since #186 the two looks for lots before the start
    "ndarray.ravel": 3,
    "ndarray.reshape": 1,
    "ndarray.searchsorted": 3,  # the fixed rows, and since #186 the contract periods' places, one
    # a bucket
    "ndarray.setflags": 21,  # the eight, the two lot arrays of the nominal delta, the three views,
    # since #186 the two display axes' three arrays each, and since
    # observation-prices-readback.md the settles and the fixed contributions kept for the readback
    "ndarray.sum": 4,
    "numpy._make_extobj": 4,  # the error state set for the set amounts, the sensitivity, the lots
    # and the unsettled totals, since #190, the overflow the fourth rule's to catch
    "numpy.arange": 2,  # the display periods, since #186
    "numpy.asanyarray": 5,
    "numpy.zeros": 1,
    "numpy.empty": 2,
    "ufunc.reduce": 13,  # the nine looks among them
}


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_a_tick_runs_evaluation_alone_and_nothing_of_the_steps_before(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int
) -> None:
    history = a_history()
    prep = prepared_trades(a_batch(components, contracts), (history,), WorkCounter())
    quoted = a_market(history)
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }
    # The gather and the multiplication are dispatched in C and unseen; delta and its total are
    # the preparation's, shared and not made again. What is seen is the market's one look at the
    # references asked for, with its reduction, the sum of the dated contributions, and the
    # contributions frozen, and since observation-prices-readback.md the quotes frozen too, kept
    # for the readback.
    assert numpy_calls(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "ndarray.any": 2,  # the market's coverage, and since #190 the live contributions finite
        "ndarray.setflags": 2,  # the contributions and, since #229, the quotes for the readback
        "ndarray.sum": 1,
        "numpy._make_extobj": 1,  # the error state set for the live contributions and their sum
        "ufunc.reduce": 3,
    }


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_the_encoding_runs_the_same_functions_at_any_size(
    call_profile: CallProfile, components: int, contracts: int
) -> None:
    terms = a_batch(components, contracts).terms
    obs = observed_of(terms)
    assert call_profile(lambda: encoded(terms, (obs,), UNITS, WorkCounter())) == ENCODING_LEDGER
    assert call_profile(lambda: observed_of(terms)) == {
        "observed": 1,
        "trade_schedule_of": 1,
        "with_holiday_calendar": 1,  # the index's calendar typed once for the methods that read it
        "requires_whole_month": 1,  # the methods' two facts the observations read, once each
        "counts_back_from_expiry": 1,
        "_whole_months": 1,  # each component covers its whole month, the expiry-based rule
        "_the_days": 1,  # one method present, its observations once
        "observations": 1,
    }
    # The penultimate method reads the holiday calendar and looks once at the expiries; the
    # encoding over its observations runs the same functions as over lastday's.
    pen = some_terms(components, contracts, ScheduleMethod.PENULTIMATE)
    with_expiries = {
        "observed": 1,
        "trade_schedule_of": 1,
        "requires_whole_month": 1,  # the methods' two facts the observations read, once each
        "counts_back_from_expiry": 1,
        "_whole_months": 1,
        "_with_expiries_priced": 1,
        "with_holiday_calendar": 1,
        "open_days": 1,
        "_the_days": 1,
        "observations": 1,
    }
    assert call_profile(lambda: observed_of(pen)) == with_expiries
    pen_obs = observed_of(pen)
    assert call_profile(lambda: encoded(pen, (pen_obs,), UNITS, WorkCounter())) == ENCODING_LEDGER
    # last3day makes three observations per component with the same functions as the pen, one
    # offset over the components and the three offsets at once; the encoding over them runs the
    # same functions again, three times the observations and slots through the same calls.
    three = some_terms(components, contracts, ScheduleMethod.LAST3DAY)
    assert call_profile(lambda: observed_of(three)) == with_expiries
    three_obs = observed_of(three)
    assert three_obs.component.size == 3 * components
    assert (
        call_profile(lambda: encoded(three, (three_obs,), UNITS, WorkCounter())) == ENCODING_LEDGER
    )


# The encoding's functions, each once: the groups found in one sort over the components and
# the slots in one over the observations, the distinct pairs of contract and day and of group
# and day through the one helper, the two calendar rules read once over every observation,
# the open days and the pricing contract, and the payment rule once over the groups.
ENCODING_LEDGER = {
    "encoded": 1,
    "_the_groups": 1,
    "_the_amounts": 1,  # two-index-fixed-float.md: the leg's three amounts per component
    "_the_group_offsets": 1,  # the leg's offsets by group
    "_the_exposures": 1,  # the leg's slots' exposures
    "_distinct": 2,
    "_the_references": 1,
    "observation_references": 1,  # the reader shared with a quote, template-based-quoting.md
    "requires_booked_reference": 1,  # the methods' fact the references read, once
    "with_holiday_calendar": 1,
    "open_days": 1,
    "contract_on": 1,
    "_the_slots": 1,
    "_the_day_axis": 1,  # the day axis, since #166
    "_the_contract_periods": 1,  # the contract month and year axes, since #186
    "_payments_after_observations": 1,
    "payments_after_observations": 1,  # the kernel's rule, one owner since
    # payment-day-date-or-rule.md
    "reserves": 1,  # the booked brokerage and clearing, once over the components, since #170
    "_charged": 1,  # clearing, the one fee a cleared, unbrokered batch charges, since #188
    "UnitConversions.factor": 2,
    "UnitConversions.category": 2,
    "WorkCounter.__init__": 1,
    "WorkCounter.hit": 5,
}


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_the_preparation_runs_the_same_functions_at_any_size(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int
) -> None:
    enc = a_batch(components, contracts)
    history = a_history()
    assert call_profile(lambda: prepared_trades(enc, (history,), WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    numpy = numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter()))
    assert numpy == PREPARATION_NUMPY, numpy


# The asian method's index: the same months, each contract expiring on its month's last business
# day, so that every pricing day of a month prices its own contract, and paying two business
# days after the month's end; the days of each month are the fixture's own arithmetic.
MONTH_ENDS = np.busday_offset(
    (MONTHS + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D"),
    0,
    roll="backward",
    holidays=HOLIDAYS,
)
ASIAN_PAYS = np.busday_offset(MONTH_ENDS, 2, holidays=HOLIDAYS)
ASIAN_GAS = index(
    "gas",
    "Sample gas index",
    futures_schedule(CODES, MONTH_ENDS, None),
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot",), np.array([10_000.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    holiday_calendar(HOLIDAYS),
    "lot",
    UNITS,
)
MONTH_DAYS = np.busday_count(
    MONTHS.astype("datetime64[D]"),
    (MONTHS + np.timedelta64(1, "M")).astype("datetime64[D]"),
    holidays=HOLIDAYS,
)


def asian_terms(components: int, contracts: int) -> ResolvedTrades:
    rows = 1 + np.arange(components, dtype=np.intp) % contracts
    return resolved_trades(
        FIXED_FLOAT,
        ASIAN_GAS,
        np.zeros(components, dtype=np.intp),
        Route.CLEARED,
        Settlement.FINANCIAL,
        one_choice(METHODS, ScheduleMethod.ASIAN, components),
        one_choice(BASES, QuantityPer.MONTH, components),
        one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, components),
        None,
        None,
        None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        np.arange(components, dtype=np.intp),
        rows,
        np.where(np.arange(components) % 3 == 0, -3.0, 2.0),
        *month_bounds(SCHEDULE_MONTHS[rows]),
        3.0 + (np.arange(components) % 7) / 100,
        PaymentTerms(
            DatesOrTexts.of_texts(("+2bd",) * components),
            (PAYMENT_CALENDAR,) * components,
            ASIAN_PAYS[rows],
        ),
    )


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_an_asian_batch_observes_a_month_per_component_and_ticks_like_a_lastday_one(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int
) -> None:
    # A month of pricing days per component, 21 to 23, into one slot per contract and day: the
    # observations through the same functions as the pen's but the look at the expiries, the
    # encoding, the preparation and a tick over them the same functions as a lastday batch's,
    # and the counts by component, observation, slot and live reference.
    terms = asian_terms(components, contracts)
    assert call_profile(lambda: observed_of(terms)) == {
        "observed": 1,
        "trade_schedule_of": 1,
        "with_holiday_calendar": 1,
        "requires_whole_month": 1,  # the methods' two facts the observations read, once each
        "counts_back_from_expiry": 1,
        "_the_days": 1,
        "observations": 1,
    }
    counter = WorkCounter()
    enc = encoded(terms, (observed_of(terms),), UNITS, counter)
    history = a_history(ix=ASIAN_GAS)
    prep = prepared_trades(enc, (history,), counter)
    quoted = a_market(history)
    trade_results(prep, (quoted,), counter)
    counts = counter.freeze().as_dict()
    rows = 1 + np.arange(components) % contracts
    assert counts["encoded_components"] == components
    assert counts["encoded_observations"] == int(MONTH_DAYS[rows].sum())
    assert (
        counts["encoded_slots"]
        == counts["prepared_slots"]
        == int(MONTH_DAYS[1 : contracts + 1].sum())
    )
    assert counts["live_prices_read"] == prep.legs[0].live_references.size
    obs = observed_of(terms)
    assert call_profile(lambda: encoded(terms, (obs,), UNITS, WorkCounter())) == ENCODING_LEDGER
    assert call_profile(lambda: prepared_trades(enc, (history,), WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    numpy = numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter()))
    assert numpy == PREPARATION_NUMPY, numpy
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_a_last3day_batch_prepares_and_ticks_with_the_same_functions_as_a_lastday_one(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int
) -> None:
    # Three slots per contract where lastday has one: the preparation runs the same functions
    # and numpy calls over them, and a tick reads one quote per live reference and runs nothing
    # of the steps before, no schedule generated, no fixed leg made, no fixing folded again.
    terms = some_terms(components, contracts, ScheduleMethod.LAST3DAY)
    counter = WorkCounter()
    enc = encoded(terms, (observed_of(terms),), UNITS, counter)
    history = a_history()
    prep = prepared_trades(enc, (history,), counter)
    quoted = a_market(history)
    trade_results(prep, (quoted,), counter)
    counts = counter.freeze().as_dict()
    assert (counts["encoded_components"], counts["encoded_observations"]) == (
        components,
        3 * components,
    )
    assert counts["encoded_slots"] == counts["prepared_slots"] == 3 * contracts
    assert counts["live_prices_read"] == prep.legs[0].live_references.size  # one a live reference
    assert call_profile(lambda: prepared_trades(enc, (history,), WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    numpy = numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter()))
    assert numpy == PREPARATION_NUMPY, numpy
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }


# --- many observations on one contract: the daily batch -----------------------------------
# The dated axis is sized by slots, the distinct days of each contract, and never by trades or
# observations: two thousand trades over fifteen days are thirty thousand observations into 360
# slots, and the tick, the preparation and the result know only the slots and the references.


@pytest.mark.parametrize(("components", "contracts", "days"), DAILY, ids=DAILY_IDS)
def test_a_daily_batch_is_summed_into_one_slot_per_contract_and_day(
    components: int, contracts: int, days: int
) -> None:
    counter = WorkCounter()
    terms = some_terms(components, contracts)
    obs = observations(
        np.repeat(np.arange(components, dtype=np.intp), days),
        daily_days(components, contracts, days),
        np.full(components * days, 1 / days),
        components,
    )
    enc = encoded(terms, (obs,), UNITS, counter)
    slots = contracts * days
    assert counter.freeze().as_dict() == {
        "encoded_components": components,
        "encoded_groups": contracts,
        "encoded_observations": components * days,
        "encoded_slots": slots,
        "reserved_fee_components": components,  # clearing alone: cleared, no broker, since #188
    }
    assert enc.legs[0].slot_group.size == slots and enc.legs[0].references.size == contracts
    np.testing.assert_array_equal(
        enc.legs[0].slot_reference, enc.legs[0].group_contract[enc.legs[0].slot_group]
    )
    # Every component's exposure is shared out over its days and nothing is lost in the sum.
    assert enc.legs[0].slot_exposure.sum() == pytest.approx(enc.legs[0].coefficient.sum(), abs=1e-6)
    # What is retained per slot and per observation, in bytes: eight a slot for each of the
    # four slot columns, eight an observation for each of the observations' three and its slot.
    assert enc.legs[0].slot_exposure.nbytes == 8 * slots and enc.legs[
        0
    ].slot_of_observation.nbytes == (8 * components * days)


@pytest.mark.parametrize(("components", "contracts", "days"), DAILY, ids=DAILY_IDS)
def test_a_daily_batch_prepares_per_slot_and_ticks_per_live_reference(
    components: int, contracts: int, days: int
) -> None:
    enc = a_daily_batch(components, contracts, days)
    history = a_history()
    counter = WorkCounter()
    prep = prepared_trades(enc, (history,), counter)
    slots, fixed = contracts * days, daily_fixed_slots(components, contracts, days)
    assert counter.freeze().as_dict() == {
        "display_periods": display_periods(prep),
        "fixings_read": fixed,
        "prepared_slots": slots,
    }
    assert prep.legs[0].live_slot.size == slots - fixed
    assert (
        prep.legs[0].dated_live_exposure.nbytes == 8 * slots
        and prep.legs[0].dated_live_lots.nbytes == 8 * slots  # the lot view per slot
        and prep.legs[0].price_sensitivity.nbytes == 8 * contracts
        and prep.legs[0].nominal_delta.nbytes == 8 * contracts
        # since observation-prices-readback.md the settles, one per fixed slot, and the fixed
        # contributions, one per slot, kept for the readback
        and prep.legs[0].settle.nbytes == 8 * fixed
        and prep.legs[0].fixed_contribution.nbytes == 8 * slots
    )
    counter = WorkCounter()
    result = trade_results(prep, (a_market(history),), counter)
    live_references = int(np.unique(enc.legs[0].slot_reference[prep.legs[0].live_slot]).size)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": live_references}
    assert result.legs[0].dated_live_contribution.nbytes == 8 * (slots - fixed)  # one per live slot
    assert result.legs[0].quote.nbytes == 8 * live_references  # one per live reference, kept
    assert result.legs[0].dated_live_contribution.sum() == pytest.approx(
        result.mark - prep.offset_unsettled - prep.set_unsettled
    )
    np.testing.assert_allclose(
        np.bincount(
            enc.legs[0].reference_of_slot,
            weights=prep.legs[0].dated_live_exposure,
            minlength=contracts,
        ),
        prep.legs[0].price_sensitivity,
    )


def test_the_results_readback_reads_no_fixing_and_no_quote(call_profile: CallProfile) -> None:
    """observation-prices-readback.md: the four price columns are the retained settles, quotes
    and contributions placed on their slots; the readback asks the history and the market for
    nothing, prepares nothing and multiplies nothing."""
    enc = a_daily_batch(*DAILY[1])
    history = a_history()
    prep = prepared_trades(enc, (history,), WorkCounter())
    result = trade_results(prep, (a_market(history),), WorkCounter())
    profile = call_profile(lambda: shown(result))
    assert profile["trade_results_table"] == 1 and profile["_observation_facts"] == 1
    assert profile["_quote_unit"] == 1  # the leg's unit once, repeated on its rows
    assert (
        not {
            "Market.live_prices",
            "_the_contributions",
            "_the_set_amounts",
            "_the_prepared_leg",
            "prepared_trades",
            "trade_results",
        }
        & profile.keys()
    )


@pytest.mark.parametrize(("components", "contracts", "days"), DAILY, ids=DAILY_IDS)
def test_a_daily_batch_runs_the_same_functions_as_a_lastday_one(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int, days: int
) -> None:
    terms = some_terms(components, contracts)
    obs = observations(
        np.repeat(np.arange(components, dtype=np.intp), days),
        daily_days(components, contracts, days),
        np.full(components * days, 1 / days),
        components,
    )
    assert call_profile(lambda: encoded(terms, (obs,), UNITS, WorkCounter())) == ENCODING_LEDGER
    enc = encoded(terms, (obs,), UNITS, WorkCounter())
    history = a_history()
    assert call_profile(lambda: prepared_trades(enc, (history,), WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    assert numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter())) == PREPARATION_NUMPY
    prep = prepared_trades(enc, (history,), WorkCounter())
    quoted = a_market(history)
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }


# Memory: the preparation and the tick allocate by slots and references, never by trades or
# observations. Measured on 2026-10-04 for two thousand trades over twenty-four contracts and
# fifteen days, 360 slots: the preparation 30,972 bytes, about 86 a slot, its masks, the sort
# behind the unique live references, its set amounts and its delta, and 33,964 on 2026-10-08,
# about 94 a slot, with the lot view per slot and per contract beside them, the pin 98; the
# tick 7,792 bytes, about
# 22 a slot, the quotes, their gather onto the live slots and the contributions; the five-trade
# batch of six slots 1,210, its records and a few small arrays, under twice the slack.
def test_a_daily_batchs_preparation_and_tick_allocate_by_slot_not_by_trade() -> None:
    components, contracts, days = DAILY[1]
    enc = a_daily_batch(components, contracts, days)
    history = a_history()
    slots = contracts * days
    assert least_peak(lambda: prepared_trades(enc, (history,), WorkCounter())) <= 98 * slots + SLACK
    prep = prepared_trades(enc, (history,), WorkCounter())
    quoted = a_market(history)
    assert least_peak(lambda: trade_results(prep, (quoted,), WorkCounter())) <= 24 * slots + SLACK
    small = a_daily_batch(*DAILY[0])
    small_prep = prepared_trades(small, (history,), WorkCounter())
    assert least_peak(lambda: trade_results(small_prep, (quoted,), WorkCounter())) <= (
        KEYWORD_CALL + 2 * SLACK
    )


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_a_calday_batch_encodes_prepares_and_ticks_like_a_month_one(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int
) -> None:
    # The basis is the terms' business: the encoding converts the component quantity the kernel
    # formed, the preparation and a tick take the coefficients as they are, and none of the three
    # counts a day or scales a quantity, so each runs the same functions and numpy as over a month
    # batch; the quote quantities are the month batch's times the days each month covers.
    terms = some_terms(components, contracts, basis=QuantityPer.CALDAY)
    obs = observed_of(terms)
    assert call_profile(lambda: encoded(terms, (obs,), UNITS, WorkCounter())) == ENCODING_LEDGER
    enc = encoded(terms, (obs,), UNITS, WorkCounter())
    np.testing.assert_array_equal(
        enc.legs[0].quote_quantity,
        a_batch(components, contracts).legs[0].quote_quantity * terms.covered_days,
    )
    history = a_history()
    assert call_profile(lambda: prepared_trades(enc, (history,), WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    assert numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter())) == PREPARATION_NUMPY
    prep = prepared_trades(enc, (history,), WorkCounter())
    quoted = a_market(history)
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }
    assert numpy_calls(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "ndarray.any": 2,  # the market's coverage, and since #190 the live contributions finite
        "ndarray.setflags": 2,  # the contributions and, since #229, the quotes for the readback
        "ndarray.sum": 1,
        "numpy._make_extobj": 1,  # the error state set for the live contributions and their sum
        "ufunc.reduce": 3,
    }


# --- two payment days per contract: the groups and the slots double, the quotes do not ---------
# multiple-payment-groups.md: a payment group is a contract and a payment day, so the same trades
# with the second lap of components over the contracts paying a day after the first make two
# groups of every contract and two slots on its one expiry day, while the delta axis, the quotes
# a tick reads and the functions and numpy calls every step runs are the one-group batch's.


def two_day_terms(components: int, contracts: int) -> ResolvedTrades:
    """The budgets' trades, the second lap over the contracts at +3bd paying a day after the
    first lap's +2bd, so that every contract has two payment groups."""
    rows = 1 + np.arange(components, dtype=np.intp) % contracts
    later = (np.arange(components) // contracts) % 2
    return resolved_trades(
        FIXED_FLOAT,
        GAS,
        np.zeros(components, dtype=np.intp),
        Route.CLEARED,
        Settlement.FINANCIAL,
        one_choice(METHODS, ScheduleMethod.LASTDAY, components),
        one_choice(BASES, QuantityPer.MONTH, components),
        one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, components),
        None,
        None,
        None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        np.arange(components, dtype=np.intp),
        rows,
        np.where(np.arange(components) % 3 == 0, -3.0, 2.0),
        *month_bounds(SCHEDULE_MONTHS[rows]),
        3.0 + (np.arange(components) % 7) / 100,
        PaymentTerms(
            DatesOrTexts.of_texts(tuple(f"+{n}bd" for n in (2 + later).tolist())),
            (PAYMENT_CALENDAR,) * components,
            PAYS[rows] + later.astype("timedelta64[D]"),
        ),
    )


@pytest.mark.parametrize(
    ("components", "contracts", "fixed", "live"), [(5, 2, 2, 0), (2_000, 24, 4, 20)], ids=IDS
)
def test_two_payment_days_per_contract_double_the_groups_and_slots_and_not_the_quotes(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    components: int,
    contracts: int,
    fixed: int,
    live: int,
) -> None:
    terms = two_day_terms(components, contracts)
    obs = observed_of(terms)
    assert call_profile(lambda: encoded(terms, (obs,), UNITS, WorkCounter())) == ENCODING_LEDGER
    counter = WorkCounter()
    enc = encoded(terms, (obs,), UNITS, counter)
    history = a_history()
    prep = prepared_trades(enc, (history,), counter)
    quoted = a_market(history)
    trade_results(prep, (quoted,), counter)
    assert counter.freeze().as_dict() == {
        "display_periods": display_periods(prep),
        "encoded_components": components,
        "encoded_groups": 2 * contracts,
        "encoded_observations": components,
        "encoded_slots": 2 * contracts,  # each contract's expiry day once per group
        "reserved_fee_components": components,  # clearing alone: cleared, no broker, since #188
        "prepared_slots": 2 * contracts,
        "fixings_read": 2 * fixed,  # one settle read per fixed slot, two slots a fixed day
        "kernel": 1,
        "live_prices_read": live,  # one quote per live contract, not per live group
    }
    assert enc.legs[0].references.size == contracts and prep.legs[0].live_references.size == live
    assert prep.legs[0].live_slot.size == 2 * live
    np.testing.assert_array_equal(enc.legs[0].group_contract, np.repeat(enc.legs[0].references, 2))
    assert call_profile(lambda: prepared_trades(enc, (history,), WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    assert numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter())) == PREPARATION_NUMPY
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }
    # The same trades, the same exposure per contract: the delta is the one-group batch's.
    one_group = prepared_trades(a_batch(components, contracts), (history,), WorkCounter())
    np.testing.assert_allclose(prep.legs[0].price_sensitivity, one_group.legs[0].price_sensitivity)


def test_a_two_day_daily_batch_prepares_and_ticks_by_its_doubled_slots() -> None:
    # The daily batch with two payment days per contract: 720 slots for 360, thirty thousand
    # observations still, the tick reading one quote per live contract, and the preparation's and
    # the tick's peaks within the one-day batch's ceilings per slot over the slots they have.
    components, contracts, days = DAILY[1]
    terms = two_day_terms(components, contracts)
    obs = observations(
        np.repeat(np.arange(components, dtype=np.intp), days),
        daily_days(components, contracts, days),
        np.full(components * days, 1 / days),
        components,
    )
    enc = encoded(terms, (obs,), UNITS, WorkCounter())
    slots = 2 * contracts * days
    assert enc.legs[0].slot_group.size == slots and enc.legs[0].references.size == contracts
    assert enc.legs[0].slot_of_observation.size == components * days
    history = a_history()
    assert least_peak(lambda: prepared_trades(enc, (history,), WorkCounter())) <= 98 * slots + SLACK
    prep = prepared_trades(enc, (history,), WorkCounter())
    quoted = a_market(history)
    assert least_peak(lambda: trade_results(prep, (quoted,), WorkCounter())) <= 24 * slots + SLACK
    counter = WorkCounter()
    trade_results(prep, (quoted,), counter)
    live_references = int(np.unique(enc.legs[0].slot_reference[prep.legs[0].live_slot]).size)
    assert counter.freeze()["live_prices_read"] == live_references


# --- mixed fields in one batch: units, bases and methods row by row ------------------------------
# mixed-trade-fields.md: the asian index with a second specification, MMBTU of one, and trades
# whose every lap over the contracts takes the next method, the unit and the basis turning row by
# row, so that every contract carries all four methods, two units and both bases; the penultimate
# rows pay a business day after the expiry and the rest two, so every contract is two payment
# groups. Eight components over two contracts hold every method once per contract; two thousand
# over twenty-four hold each many times.
MIXED_SIZES = [(8, 2), (2_000, 24)]
MIXED_IDS = ["eight trades", "two thousand trades"]
MIXED_GAS = index(
    "gas",
    "Sample gas index",
    futures_schedule(CODES, MONTH_ENDS, None),
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot", "MMBTU"),
        np.array([10_000.0, 1.0]),
        ("MMBTU", "MMBTU"),
        np.array([0.0, 0.0]),
        np.array([0.0, 0.0]),
        UNITS,
    ),
    holiday_calendar(HOLIDAYS),
    "lot",
    UNITS,
)
METHOD_LAPS = np.array(
    [
        METHODS.index(m)
        for m in (
            ScheduleMethod.LASTDAY,
            ScheduleMethod.PENULTIMATE,
            ScheduleMethod.LAST3DAY,
            ScheduleMethod.ASIAN,
        )
    ],
    dtype=np.intp,
)


def mixed_terms(components: int, contracts: int) -> ResolvedTrades:
    """The budgets' trades on MIXED_GAS, each lap over the contracts the next method, the unit
    turning every row and the basis every two, the payment days the fixture's own arithmetic."""
    rows = 1 + np.arange(components, dtype=np.intp) % contracts
    method = METHOD_LAPS[(np.arange(components) // contracts) % 4]
    pen = method == METHODS.index(ScheduleMethod.PENULTIMATE)
    pays = np.where(pen, np.busday_offset(MONTH_ENDS[rows], 1, holidays=HOLIDAYS), ASIAN_PAYS[rows])
    return resolved_trades(
        FIXED_FLOAT,
        MIXED_GAS,
        (np.arange(components) % 2).astype(np.intp),
        Route.CLEARED,
        Settlement.FINANCIAL,
        method,
        ((np.arange(components) // 2) % 2).astype(np.intp),
        one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, components),
        None,
        None,
        None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        np.arange(components, dtype=np.intp),
        rows,
        np.where(np.arange(components) % 3 == 0, -3.0, 2.0),
        *month_bounds(SCHEDULE_MONTHS[rows]),
        3.0 + (np.arange(components) % 7) / 100,
        PaymentTerms(
            DatesOrTexts.of_texts(("+2bd",) * components), (PAYMENT_CALENDAR,) * components, pays
        ),
    )


def mixed_slots(contracts: int) -> int:
    """The slots a mixed batch over the first contracts has, by the fixture's own arithmetic: per
    contract the penultimate group's one day and the other group's pricing days of the month, the
    expiry and the last3day days among them."""
    return contracts + int(MONTH_DAYS[1 : contracts + 1].sum())


@pytest.mark.parametrize(
    ("components", "contracts", "fixings", "live"),
    [(8, 2, 45, 0), (2_000, 24, 94, 20)],
    ids=MIXED_IDS,
)
def test_a_mixed_batch_dispatches_over_its_methods_once_and_values_through_the_one_path(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    components: int,
    contracts: int,
    fixings: int,
    live: int,
) -> None:
    # The observations: the four methods present made once each, the whole-month and the open-
    # expiry rules looked at once over the components and the index's calendar typed once; the
    # encoding the one-method batch's functions but one conversion more, the second
    # specification's; the preparation and a tick the same functions and numpy calls as any
    # batch's. The counts: two groups per contract, the penultimate rows paying a day before the
    # rest; a slot per contract for the penultimate day and one per pricing day of the month for
    # the rest, the expiry and the last3day days among them; the fixings read per slot, every slot
    # of the expired contracts and the March pricing days before the 10th; one quote per live
    # contract, whatever methods and groups hold it.
    terms = mixed_terms(components, contracts)
    assert call_profile(lambda: observed_of(terms)) == {
        "observed": 1,
        "trade_schedule_of": 1,
        "with_holiday_calendar": 1,
        "requires_whole_month": 1,  # the methods' two facts the observations read, once each
        "counts_back_from_expiry": 1,
        "_whole_months": 1,
        "_with_expiries_priced": 1,
        "open_days": 1,
        "_the_days": 4,
        "observations": 1,
    }
    obs = observed_of(terms)
    assert call_profile(lambda: encoded(terms, (obs,), UNITS, WorkCounter())) == {
        **ENCODING_LEDGER,
        "UnitConversions.factor": 3,
        "UnitConversions.category": 3,
    }
    counter = WorkCounter()
    enc = encoded(terms, (obs,), UNITS, counter)
    history = a_history(ix=MIXED_GAS)
    prep = prepared_trades(enc, (history,), counter)
    quoted = a_market(history)
    trade_results(prep, (quoted,), counter)
    rows = 1 + np.arange(components) % contracts
    lap = (np.arange(components) // contracts) % 4
    observations_by_method = np.array([1, 1, 3, 0])[lap] + np.where(lap == 3, MONTH_DAYS[rows], 0)
    assert counter.freeze().as_dict() == {
        "display_periods": display_periods(prep),
        "encoded_components": components,
        "encoded_groups": 2 * contracts,
        "encoded_observations": int(observations_by_method.sum()),
        "encoded_slots": mixed_slots(contracts),
        "reserved_fee_components": components,  # clearing alone: cleared, no broker, since #188
        "prepared_slots": mixed_slots(contracts),
        "fixings_read": fixings,
        "kernel": 1,
        "live_prices_read": live,
    }
    assert enc.legs[0].references.size == contracts and prep.legs[0].live_references.size == live
    assert call_profile(lambda: prepared_trades(enc, (history,), WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    assert numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter())) == PREPARATION_NUMPY
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }


# Memory: the mixed batch of two thousand trades over twenty-four contracts, 543 slots, measured
# on 2026-10-08: the preparation 45,298 bytes, about 83 a slot, the tick 11,440, about 21, within
# the one-method ceilings per slot; the eight-trade batch's tick 1,210, under twice the slack.
def test_a_mixed_batchs_preparation_and_tick_allocate_by_slot_not_by_trade() -> None:
    components, contracts = MIXED_SIZES[1]
    terms = mixed_terms(components, contracts)
    enc = encoded(terms, (observed_of(terms),), UNITS, WorkCounter())
    history = a_history(ix=MIXED_GAS)
    slots = mixed_slots(contracts)
    assert enc.legs[0].slot_group.size == slots
    assert least_peak(lambda: prepared_trades(enc, (history,), WorkCounter())) <= 98 * slots + SLACK
    prep = prepared_trades(enc, (history,), WorkCounter())
    quoted = a_market(history)
    assert least_peak(lambda: trade_results(prep, (quoted,), WorkCounter())) <= 24 * slots + SLACK
    small = mixed_terms(*MIXED_SIZES[0])
    small_enc = encoded(small, (observed_of(small),), UNITS, WorkCounter())
    small_prep = prepared_trades(small_enc, (history,), WorkCounter())
    assert least_peak(lambda: trade_results(small_prep, (quoted,), WorkCounter())) <= (
        KEYWORD_CALL + 2 * SLACK
    )


# --- the rolling asian batch, calendar-driven-asian-references.md -------------------------------
# The same months on a schedule whose contracts expire on the 20th of the month before their own,
# as crude's do, so that each month's pricing days are two contracts', the one expiring in it and
# the next, and an asian batch references one contract more than it books: the same functions as
# the month-aligned asian batch runs, every count by component, observation, slot and live
# reference, and a tick that reads each distinct live reference once. Two months more than the
# other schedules, so that the last booked month's later days have a contract to price them.
ROLLING_MONTHS = np.arange("2026-10", "2029-01", dtype="datetime64[M]")
ROLLING_CODES = tuple(f"{LETTERS[int(m.astype(int)) % 12]}{str(m)[2:4]}" for m in ROLLING_MONTHS)
ROLLING_EXPIRIES = np.busday_offset(
    (ROLLING_MONTHS - np.timedelta64(1, "M")).astype("datetime64[D]") + np.timedelta64(19, "D"),
    0,
    roll="backward",
    holidays=HOLIDAYS,
)
ROLLING_GAS = index(
    "rolling",
    "Sample gas index with rolling contracts",
    futures_schedule(ROLLING_CODES, ROLLING_EXPIRIES, None),
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot",), np.array([10_000.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    holiday_calendar(HOLIDAYS),
    "lot",
    UNITS,
)


def rolling_terms(components: int, contracts: int) -> ResolvedTrades:
    rows = 1 + np.arange(components, dtype=np.intp) % contracts
    return resolved_trades(
        FIXED_FLOAT,
        ROLLING_GAS,
        np.zeros(components, dtype=np.intp),
        Route.CLEARED,
        Settlement.FINANCIAL,
        one_choice(METHODS, ScheduleMethod.ASIAN, components),
        one_choice(BASES, QuantityPer.MONTH, components),
        one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, components),
        None,
        None,
        None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        np.arange(components, dtype=np.intp),
        rows,
        np.where(np.arange(components) % 3 == 0, -3.0, 2.0),
        *month_bounds(SCHEDULE_MONTHS[rows]),
        3.0 + (np.arange(components) % 7) / 100,
        PaymentTerms(
            DatesOrTexts.of_texts(("+2bd",) * components),
            (PAYMENT_CALENDAR,) * components,
            ASIAN_PAYS[rows],
        ),
    )


def rolling_market(history: MarketHistory) -> Market:
    """A quote for every contract of the rolling schedule from the first unfixed period's on."""
    cal = history.calendar
    remaining = len(ROLLING_CODES) - int(cal.contract[cal.first_unfixed])
    return market(history, price_vector("rolling", 3.5 + np.arange(remaining) / 100))


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_a_rolling_asian_batch_references_the_calendars_contracts_and_ticks_like_the_month_one(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int
) -> None:
    terms = rolling_terms(components, contracts)
    counter = WorkCounter()
    obs = observed_of(terms)
    enc = encoded(terms, (obs,), UNITS, counter)
    history = a_history(ix=ROLLING_GAS)
    prep = prepared_trades(enc, (history,), counter)
    quoted = rolling_market(history)
    trade_results(prep, (quoted,), counter)
    counts = counter.freeze().as_dict()
    rows = 1 + np.arange(components) % contracts
    assert counts["encoded_components"] == components
    assert counts["encoded_groups"] == contracts  # one payment day a month: the booked contracts
    assert counts["encoded_observations"] == int(MONTH_DAYS[rows].sum())
    assert (
        counts["encoded_slots"]
        == counts["prepared_slots"]
        == int(MONTH_DAYS[1 : contracts + 1].sum())
    )
    # Each booked month's days are two contracts', the one expiring in it and the next: the groups
    # are rows 1 to `contracts`, the references rows 2 to `contracts` + 2, every slot's a row or
    # two after its group's.
    np.testing.assert_array_equal(
        np.unique(enc.legs[0].group_contract), np.arange(1, contracts + 1)
    )
    np.testing.assert_array_equal(enc.legs[0].references, np.arange(2, contracts + 3))
    assert (
        enc.legs[0].slot_reference >= enc.legs[0].group_contract[enc.legs[0].slot_group] + 1
    ).all()
    assert counts["live_prices_read"] == prep.legs[0].live_references.size
    assert call_profile(lambda: encoded(terms, (obs,), UNITS, WorkCounter())) == ENCODING_LEDGER
    assert call_profile(lambda: prepared_trades(enc, (history,), WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    numpy = numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter()))
    assert numpy == PREPARATION_NUMPY, numpy
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }


# --- an IFERC basis batch, iferc-basis-futures.md -------------------------------------------
# The same 25 months on an IFERC index: each month's index published on the first business day
# of it, 2,500 MMBtu a lot, no pricing calendar; the payment two business days after publication
# on the payment calendar, since iferc-publication-payment-anchor.md. The
# first month is a month like any other, so the rows begin at 0. Valued on 10 March 2027 the
# months of October 2026 to March 2027, rows 0 to 5, have published: a batch over 24 contracts has
# six fixed and eighteen live, and one over two contracts two fixed and none live.
IFERC_PUBLICATION = np.busday_offset(
    MONTHS.astype("datetime64[D]"), 0, roll="forward", holidays=HOLIDAYS
)
IFERC_PAYS = np.busday_offset(IFERC_PUBLICATION, 2, roll="backward", holidays=HOLIDAYS)
BASIS = index(
    "basis",
    "Sample basis index",
    iferc_schedule(CODES, IFERC_PUBLICATION),
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot",), np.array([2_500.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    None,
    "lot",
    UNITS,
)


def iferc_terms(components: int, contracts: int) -> ResolvedTrades:
    """That many single-month lastday trades spread over the first contracts, lots and prices
    varying, cleared and financial, each paying its month's day."""
    rows = np.arange(components, dtype=np.intp) % contracts
    return resolved_trades(
        FIXED_FLOAT,
        BASIS,
        np.zeros(components, dtype=np.intp),
        Route.CLEARED,
        Settlement.FINANCIAL,
        one_choice(METHODS, ScheduleMethod.LASTDAY, components),
        one_choice(BASES, QuantityPer.MONTH, components),
        one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, components),
        None,
        None,
        None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        np.arange(components, dtype=np.intp),
        rows,
        np.where(np.arange(components) % 3 == 0, -3.0, 2.0),
        *month_bounds(SCHEDULE_MONTHS[rows]),
        3.0 + (np.arange(components) % 7) / 100,
        PaymentTerms(
            DatesOrTexts.of_texts(("+3bd",) * components),
            (PAYMENT_CALENDAR,) * components,
            IFERC_PAYS[rows],
        ),
    )


def iferc_history(as_of: str = AS_OF) -> MarketHistory:
    """The IFERC index's history valued on that day, an index for every published month, newest
    first as the desk keeps them."""
    cal = calendar(valuation_date(np.datetime64(as_of, "D"), 0.5), BASIS)
    published = np.flatnonzero(cal.is_fixed)[::-1]
    return market_history(
        cal,
        iferc_fixings(tuple(CODES[int(i)] for i in published), 3.0 + published / 100, BASIS),
    )


def iferc_market(history: MarketHistory) -> Market:
    """A quote for every month from the first unpublished through the last."""
    cal = history.calendar
    remaining = len(CODES) - int(cal.contract[cal.first_unfixed])
    return market(history, price_vector("basis", 3.5 + np.arange(remaining) / 100))


# The IFERC encoding runs the futures encoding's functions but the three that read a pricing
# calendar and a day's contract, which an IFERC index has none of: the reference is the component's
# own month, checked against its publication day in one comparison.
IFERC_ENCODING_LEDGER = {
    name: count
    for name, count in ENCODING_LEDGER.items()
    if name
    not in ("with_holiday_calendar", "open_days", "contract_on", "requires_booked_reference")
}
# The IFERC preparation's numpy beside the futures': one look fewer, no slot before the calendar
# to refuse since the first month is a month, and one search more, each slot's row found among
# the publication days instead of counted off the calendar's first day.
IFERC_PREPARATION_NUMPY = {
    **PREPARATION_NUMPY,
    "ndarray.any": 8,
    "ndarray.searchsorted": 4,
    "ufunc.reduce": 12,
}


@pytest.mark.parametrize(("components", "contracts", "fixed"), [(5, 2, 2), (2_000, 24, 6)], ids=IDS)
def test_an_iferc_batch_observes_once_a_component_and_runs_the_kernel_on_monthly_rows(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int, fixed: int
) -> None:
    # One observation per component on its month's publication day: the observations through the
    # schedule's kind and the whole-month look alone, no pricing calendar and no days; one slot a
    # contract on that day referencing the contract itself, one group a contract; the preparation
    # one fixing read per published month and the tick one quote per month still to publish,
    # through the same functions as a futures batch's but the calendar's, and the same numpy but
    # the boundary look and the row search.
    terms = iferc_terms(components, contracts)
    assert call_profile(lambda: observed_of(terms)) == {
        "observed": 1,
        "trade_schedule_of": 1,
        "supported_on_iferc": 1,  # the methods' fact the observations read on an IFERC index
        "_whole_months": 1,
        "observations": 1,
    }
    counter = WorkCounter()
    obs = observed_of(terms)
    enc = encoded(terms, (obs,), UNITS, counter)
    history = iferc_history()
    prep = prepared_trades(enc, (history,), counter)
    quoted = iferc_market(history)
    trade_results(prep, (quoted,), counter)
    assert counter.freeze().as_dict() == {
        "display_periods": display_periods(prep),
        "encoded_components": components,
        "encoded_groups": contracts,
        "encoded_observations": components,
        "encoded_slots": contracts,
        "reserved_fee_components": components,  # clearing alone: cleared, no broker, since #188
        "prepared_slots": contracts,
        "fixings_read": fixed,
        "kernel": 1,
        "live_prices_read": contracts - fixed,
    }
    np.testing.assert_array_equal(enc.legs[0].slot_date, IFERC_PUBLICATION[:contracts])
    np.testing.assert_array_equal(enc.legs[0].slot_reference, np.arange(contracts))
    np.testing.assert_array_equal(enc.payment_date, IFERC_PAYS[:contracts])
    assert (
        call_profile(lambda: encoded(terms, (obs,), UNITS, WorkCounter())) == IFERC_ENCODING_LEDGER
    )
    assert call_profile(lambda: prepared_trades(enc, (history,), WorkCounter())) == {
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
    }
    numpy = numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter()))
    assert numpy == IFERC_PREPARATION_NUMPY, numpy
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }
    assert numpy_calls(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "ndarray.any": 2,  # the market's coverage, and since #190 the live contributions finite
        "ndarray.setflags": 2,  # the contributions and, since #229, the quotes for the readback
        "ndarray.sum": 1,
        "numpy._make_extobj": 1,  # the error state set for the live contributions and their sum
        "ufunc.reduce": 3,
    }


# Memory: an IFERC batch's slots, groups, references, days and months are all its contracts, so
# its preparation allocates by contract and not by trade. Measured on 2026-10-09: five trades over
# two months 4,416 bytes and two thousand over twenty-four 8,880, about 203 a month more for 400
# times the trades; the tick 1,210 and 1,080, the quotes and their gather.
def test_an_iferc_batchs_preparation_and_tick_allocate_by_month_not_by_trade() -> None:
    history = iferc_history()
    small = encoded(iferc_terms(5, 2), (observed_of(iferc_terms(5, 2)),), UNITS, WorkCounter())
    big = encoded(
        iferc_terms(2_000, 24), (observed_of(iferc_terms(2_000, 24)),), UNITS, WorkCounter()
    )
    small_peak = least_peak(lambda: prepared_trades(small, (history,), WorkCounter()))
    big_peak = least_peak(lambda: prepared_trades(big, (history,), WorkCounter()))
    assert big_peak <= small_peak + 230 * 22 + SLACK
    quoted = iferc_market(history)
    big_prep = prepared_trades(big, (history,), WorkCounter())
    # Since #190 the finite check keeps two boolean temporaries over the live slots for a moment;
    # since #197 the record holds the cross-gamma's six fields, 48 bytes, None and 0.0 here.
    assert (
        least_peak(lambda: trade_results(big_prep, (quoted,), WorkCounter()))
        <= 24 * 24 + KEYWORD_CALL + SLACK + 304
    )
    small_prep = prepared_trades(small, (history,), WorkCounter())
    assert least_peak(lambda: trade_results(small_prep, (quoted,), WorkCounter())) <= (
        KEYWORD_CALL + 2 * SLACK
    )
