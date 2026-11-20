"""What a physical batch costs, since expired-physical-cash.md: the one sum over its components
the encoding makes for its closed contracts, the preparation that settles them past their expiry,
and the tick that does nothing new, at five trades and at two thousand alike. The financial
batch's ledgers are test_trade_budgets.py's and stand; this file's are measured against them."""

from dataclasses import replace

import numpy as np
import pytest
from test_seam_allocation import SLACK, least_peak
from test_trade_budgets import (
    ENCODING_LEDGER,
    GAS,
    IDS,
    PREPARATION_NUMPY,
    SCHEDULE_MONTHS,
    SIZES,
    CallProfile,
    a_batch,
    a_history,
    a_market,
    display_periods,
    observed_of,
)

from catalyst.globals.unit_conversions import UNITS
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.trades.encoding import Encoded, encoded, position_counts
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.schedule_methods import METHODS, ScheduleMethod
from catalyst.trades.terms import (
    BASES,
    FREQUENCIES,
    QuantityPer,
    ResolvedTrades,
    Route,
    Settlement,
    SettlementFrequency,
    month_bounds,
    one_choice,
    resolved_trades,
)


def physical_terms(components: int, contracts: int) -> ResolvedTrades:
    """That many single-month trades spread over the first contracts after the boundary, as the
    financial fixture spreads them, settled physically under one clearing house, and every
    contract closed: one lot bought by each of a contract's trades but its last, which sells
    them all."""
    place = np.arange(components, dtype=np.intp)
    rows = 1 + place % contracts
    held = np.bincount(place % contracts, minlength=contracts)  # each contract's trades
    last = place // contracts == held[place % contracts] - 1
    return resolved_trades(
        FIXED_FLOAT,
        GAS,
        np.zeros(components, dtype=np.intp),
        Route.CLEARED,
        Settlement.PHYSICAL,
        one_choice(METHODS, ScheduleMethod.LASTDAY, components),
        one_choice(BASES, QuantityPer.MONTH, components),
        one_choice(FREQUENCIES, SettlementFrequency.MONTHLY, components),
        np.ones(components, dtype=np.intp),
        None,
        ("CME Clearing",) * components,
        None,
        np.repeat(np.datetime64("2026-09-24", "D"), components),
        place,
        rows,
        np.where(last, 1.0 - held[place % contracts], 1.0),
        *month_bounds(SCHEDULE_MONTHS[rows]),
        3.0 + (place % 7) / 100,
        None,
    )


def a_physical_batch(components: int, contracts: int) -> Encoded:
    terms = physical_terms(components, contracts)
    return encoded(terms, (observed_of(terms),), UNITS, WorkCounter())


# --- the encoding ---------------------------------------------------------------------------

# A physical batch pays on no day, so the payment rule's two functions do not run; the closed
# contracts are found by two, once each, whatever the rows.
PHYSICAL_ENCODING_LEDGER = {
    **{
        name: count
        for name, count in ENCODING_LEDGER.items()
        if name not in ("_payments_after_observations", "payments_after_observations")
    },
    "_the_closed_groups": 1,
    "position_counts": 1,
}
# The numpy of a physical batch's encoding. The closed contracts' part, measured against main on
# the same batch: two anys more with their reductions, whether any group and unit holds 2^53 or
# more and the flags reduced by group; two reshapes, the counts left and the counts held by group
# and unit; one setflags, the flags frozen; and one error state. The two bincounts are C
# functions no ledger sees.
PHYSICAL_ENCODING_NUMPY = {
    "ndarray.any": 14,  # 12 before
    "ndarray.argsort": 4,
    "ndarray.astype": 7,
    "ndarray.cumsum": 6,
    "ndarray.flatten": 5,
    "ndarray.reshape": 6,  # 4 before
    "ndarray.searchsorted": 1,
    "ndarray.setflags": 21,  # 20 before
    "ndarray.sort": 1,
    "ndarray.sum": 1,
    "numpy._make_extobj": 7,  # 6 before
    "numpy._unique_hash": 1,
    "numpy.asanyarray": 10,
    "numpy.empty": 12,
    "numpy.zeros": 1,
    "ufunc.reduce": 15,  # 13 before
}


@pytest.mark.parametrize(("components", "contracts"), SIZES, ids=IDS)
def test_a_physical_encoding_finds_its_closed_contracts_in_one_sum_at_any_size(
    call_profile: CallProfile, numpy_calls: CallProfile, components: int, contracts: int
) -> None:
    terms = physical_terms(components, contracts)
    obs = observed_of(terms)
    counter = WorkCounter()
    enc = encoded(terms, (obs,), UNITS, counter)
    # The work reported is a financial batch's: the sum is over components already counted.
    assert counter.freeze().as_dict() == {
        "encoded_components": components,
        "encoded_groups": contracts,
        "encoded_observations": components,
        "encoded_slots": contracts,
        "reserved_fee_components": components,
    }
    assert enc.closed is not None and enc.closed.all()
    assert enc.closed.nbytes == contracts  # one flag a contract, and nothing else kept
    profile = call_profile(lambda: encoded(terms, (obs,), UNITS, WorkCounter()))
    assert profile == PHYSICAL_ENCODING_LEDGER
    numpy = numpy_calls(lambda: encoded(terms, (obs,), UNITS, WorkCounter()))
    assert numpy == PHYSICAL_ENCODING_NUMPY, numpy
    # A financial batch makes none of it: the closed flags are a physical batch's alone.
    financial = a_batch(components, contracts)
    assert financial.closed is None


def test_the_counts_are_summed_in_three_temporaries_of_the_components_size() -> None:
    # The place of each component among the groups and units, its count's size and the two
    # sums, the counts left and the counts held: 24 bytes a component at the peak, freed on
    # return, at two thousand trades and at twenty thousand over the same contracts.
    for components in (2_000, 20_000):
        enc = a_physical_batch(components, 24)
        peak = least_peak(lambda e=enc: position_counts(e.terms, e.group_of_component, 24))
        assert peak <= 24 * components + SLACK


# --- the preparation ------------------------------------------------------------------------

# Valued on 10 March 2027 the contracts of rows 1 to 4 have expired: the five-trade batch over
# rows 1 and 2 is settled whole, and the batch of two thousand has four contracts settled and
# twenty live. A financial batch's functions less the compensated sum of the set amounts, which
# a closed contract's cash does not read.
PHYSICAL_PREPARATION_LEDGER = {
    "prepared_trades": 1,
    "_the_slot_rows": 1,
    "calendar_rows": 1,
    "_the_set_amounts": 1,
    "MarketHistory.fixed_prices": 1,
    "_the_histories": 1,
    "_the_prepared_leg": 1,
    "_the_sensitivity": 1,
    "_the_totals": 1,
    "period_axis": 2,
    "period_start": 2,
    "places_from": 2,
    "rows_through": 2,
    "display_periods": 2,
    "early_risk": 1,
    "early_fact": 2,
    "WorkCounter.__init__": 1,
    "WorkCounter.hit": 3,
}
# A financial batch's numpy and three calls more, the look at the expiries: the contracts'
# expiry rows, one astype, and whether any expired contract is open, one any with its reduction.
# Against main on a live physical batch the one change is the zeros: the settled flags are the
# expired ones, where an array of nothing settled was made.
PHYSICAL_PREPARATION_NUMPY = {
    **PREPARATION_NUMPY,
    "ndarray.any": PREPARATION_NUMPY["ndarray.any"] + 1,
    "ndarray.astype": PREPARATION_NUMPY["ndarray.astype"] + 1,
    "ufunc.reduce": PREPARATION_NUMPY["ufunc.reduce"] + 1,
}


@pytest.mark.parametrize(
    ("components", "contracts", "settled"), [(5, 2, 2), (2_000, 24, 4)], ids=IDS
)
def test_a_physical_preparation_settles_its_closed_contracts_with_a_financial_ones_functions(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    components: int,
    contracts: int,
    settled: int,
) -> None:
    enc = a_physical_batch(components, contracts)
    history = a_history()
    counter = WorkCounter()
    prep = prepared_trades(enc, (history,), counter)
    assert int(np.count_nonzero(prep.is_settled)) == settled
    assert counter.freeze().as_dict() == {
        "display_periods": display_periods(prep),
        "fixings_read": settled,  # one settle read per fixed slot, as ever
        "prepared_slots": contracts,
    }
    profile = call_profile(lambda: prepared_trades(enc, (history,), WorkCounter()))
    assert profile == PHYSICAL_PREPARATION_LEDGER
    numpy = numpy_calls(lambda: prepared_trades(enc, (history,), WorkCounter()))
    assert numpy == PHYSICAL_PREPARATION_NUMPY, numpy


def test_the_count_left_is_made_again_on_the_failing_path_alone(
    call_profile: CallProfile,
) -> None:
    # One lot more on the first contract leaves it open past its expiry: the refusal makes the
    # counts again for the count it names, two functions the passing path never runs.
    terms = physical_terms(2_000, 24)
    quantity = terms.component_quantity.copy()
    quantity[0] += 1.0
    quantity.setflags(write=False)
    opened = replace(terms, quantity=quantity, component_quantity=quantity)
    enc = encoded(opened, (observed_of(opened),), UNITS, WorkCounter())
    history = a_history()

    def refused() -> None:
        with pytest.raises(ValueError, match=r" with 1\.0 of 'lot' open, trade at row 1 among "):
            prepared_trades(enc, (history,), WorkCounter())

    assert call_profile(refused) == {
        "prepared_trades": 1,
        "_the_histories": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_open_past_expiry": 1,
        "position_counts": 1,
        "ResolvedTrades.named": 1,
        "named_trade": 1,
        "WorkCounter.__init__": 1,
    }


def test_a_physical_preparation_and_tick_allocate_by_slot_not_by_trade() -> None:
    # No more than a financial batch of the same shape, which makes the compensated sum besides,
    # and the same at ten times the trades over the same contracts.
    history = a_history()
    quoted = a_market(history)
    peaks: list[tuple[int, int]] = []
    for components in (2_000, 20_000):
        enc = a_physical_batch(components, 24)
        prep = prepared_trades(enc, (history,), WorkCounter())
        peaks.append(
            (
                least_peak(lambda e=enc: prepared_trades(e, (history,), WorkCounter())),
                least_peak(lambda p=prep: trade_results(p, (quoted,), WorkCounter())),
            )
        )
    financial = a_batch(2_000, 24)
    financial_prep = prepared_trades(financial, (history,), WorkCounter())
    assert peaks[0][0] <= SLACK + least_peak(
        lambda: prepared_trades(financial, (history,), WorkCounter())
    )
    assert peaks[0][1] <= SLACK + least_peak(
        lambda: trade_results(financial_prep, (quoted,), WorkCounter())
    )
    assert abs(peaks[1][0] - peaks[0][0]) <= SLACK and abs(peaks[1][1] - peaks[0][1]) <= SLACK


# --- the tick -------------------------------------------------------------------------------


@pytest.mark.parametrize(("components", "contracts", "live"), [(5, 2, 0), (2_000, 24, 20)], ids=IDS)
def test_a_tick_over_settled_contracts_runs_what_any_cleared_tick_runs(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    components: int,
    contracts: int,
    live: int,
) -> None:
    history = a_history()
    prep = prepared_trades(a_physical_batch(components, contracts), (history,), WorkCounter())
    quoted = a_market(history)
    counter = WorkCounter()
    trade_results(prep, (quoted,), counter)
    assert counter.freeze().as_dict() == {"kernel": 1, "live_prices_read": live}
    assert call_profile(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "trade_results": 1,
        "_the_markets": 1,
        "_the_contributions": 1,
        "compensated": 1,  # the mark's signed terms, as on any cleared tick
        "_cleared_leg": 1,
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
    }
    assert numpy_calls(lambda: trade_results(prep, (quoted,), WorkCounter())) == {
        "ndarray.any": 2,
        "ndarray.setflags": 2,
        "ndarray.sum": 1,
        "numpy._make_extobj": 1,
        "ufunc.reduce": 3,
    }
