"""The work of a onetime period on a float_float, issue #279, measured against the same rows
booked by the month, at one row and at 500: a window from 20 January to 10 February 2027 on two
futures indexes, both legs asian, the second closed on the window's last day. A window is one
component a row where the months are two, one payment group where they are two, and the same
observations and slots, the days being the same days. Creation runs the monthly spread's
functions and, once a leg and never a row, the search for the contract pricing the window's
first day on that leg's own schedule; preparation and a tick run the monthly spread's functions
and numpy calls, name for name; and a window holds no more memory than the months do."""

from collections.abc import Callable

import numpy as np
import pytest
from holiday_fixtures import closed_on, index_on
from test_float_float_budgets import SPREAD_TEMPLATE, a_ticket
from test_seam_allocation import SLACK, least_peak
from test_two_index_budgets import (
    AS_OF,
    CALENDARS,
    ROWS,
    SOFR,
    A,
    curve_set,
    dates,
    numbers,
    quoted,
)

from catalyst.calendar.calendar import calendar
from catalyst.globals.unit_conversions import UNITS
from catalyst.globals.valuation_date import valuation_date
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import FuturesSchedule, futures_schedule
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market_history import MarketHistory, market_history
from catalyst.market_data.futures_fixings import futures_fixings
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades, trades
from catalyst.trades.template import trade_template

CallProfile = Callable[[Callable[[], object]], dict[str, int]]

# A second futures index on A's contracts and expiries, closed besides on 10 February 2027.
C = index_on(
    "C",
    "Index C",
    futures_schedule(
        ("X26", "Z26", "F27", "G27", "H27", "J27"),
        dates("2026-10-28", "2026-11-25", "2026-12-29", "2027-01-27", "2027-02-24", "2027-03-29"),
        None,
    ),
    index_conventions("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("LOT", "MMBTU"),
        numbers(10_000.0, 1.0),
        ("MMBTU", "MMBTU"),
        numbers(0.0, 0.0),
        numbers(0.0, 0.0),
        UNITS,
    ),
    closed_on(dates("2026-12-25", "2027-01-01", "2027-02-10")),
    "LOT",
    UNITS,
)
ASIAN: dict[str, object] = {
    **SPREAD_TEMPLATE,
    "schedule_method": "asian",
    "second_schedule_method": "asian",
}
ONETIME: dict[str, object] = {**ASIAN, "settlement_frequency": "onetime", "quantity_per": "period"}
WINDOW: dict[str, list[object]] = {
    "trade_id": [1],
    "trade_date": ["2026-12-15"],
    "start_date": ["2027-01-20"],
    "end_date": ["2027-02-10"],
    "quantity": [10_000],
    "spread_price": [0.10],
}


def spread(template: dict[str, object], n: int, counter: WorkCounter) -> Trades:
    """n rows of A less C over the window, each its own occurrence."""
    made = trade_template(a_ticket({k: [v] for k, v in template.items()}))
    ticket = a_ticket({name: list(values) * n for name, values in WINDOW.items()})
    return trades((A, C), ticket, made, UNITS, counter, CALENDARS)


def history_of(index: Index) -> MarketHistory:
    """The index's history on 4 January 2027: 3.00 on every fixed business day."""
    cal = calendar(valuation_date(np.datetime64(AS_OF, "D"), 0.5), index)
    assert isinstance(index.schedule, FuturesSchedule)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = np.full((priced.size, 1), 3.0)
    return market_history(cal, futures_fixings(priced[::-1].copy(), settles, index))


def more(mine: dict[str, int], theirs: dict[str, int]) -> dict[str, int]:
    """What one ledger holds over another, name by name, a name the other lacks from zero."""
    names = sorted(set(mine) | set(theirs))
    return {n: mine.get(n, 0) - theirs.get(n, 0) for n in names if mine.get(n) != theirs.get(n)}


@pytest.mark.parametrize("n", ROWS)
def test_a_window_is_one_component_and_one_payment_over_the_months_own_days(n: int) -> None:
    window, months = WorkCounter(), WorkCounter()
    one = spread(ONETIME, n, window)
    two = spread(ASIAN, n, months)
    assert one.resolved.occurrence.size == n and two.resolved.occurrence.size == 2 * n
    mine, theirs = window.freeze().as_dict(), months.freeze().as_dict()
    # Per leg: n components where the months are 2n, and the same observations, 16 days a row
    # on A and 15 on C, on the same slots.
    assert (mine["resolved_components"], theirs["resolved_components"]) == (n, 2 * n)
    assert (mine["encoded_components"], theirs["encoded_components"]) == (2 * n, 4 * n)
    assert (mine["encoded_groups"], theirs["encoded_groups"]) == (1, 2)
    assert mine["encoded_observations"] == theirs["encoded_observations"] == 31 * n
    assert mine["encoded_slots"] == theirs["encoded_slots"] == 31
    assert mine["encoded_payment_days"] == theirs["encoded_payment_days"] == 1


def test_a_window_costs_one_search_a_leg_and_nothing_a_row(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    few = call_profile(lambda: spread(ONETIME, 1, WorkCounter()))
    many = call_profile(lambda: spread(ONETIME, 500, WorkCounter()))
    assert few == many
    assert numpy_calls(lambda: spread(ONETIME, 1, WorkCounter())) == numpy_calls(
        lambda: spread(ONETIME, 500, WorkCounter())
    )
    # Over the same rows booked by the month: each leg's contract days made once and searched
    # once for the windows' rows, the method's look under onetime once a leg in each of the
    # rule's two runs, and the windows' last months' ends.
    months = call_profile(lambda: spread(ASIAN, 500, WorkCounter()))
    assert more(many, months) == WINDOW_FUNCTIONS


WINDOW_FUNCTIONS = {
    "contract_days": 2,  # each leg's own, made where a row is a window
    "window_rows": 2,  # and searched once for the contract pricing the windows' first day
    "_the_averaged": 4,  # the method asian, each leg, in the resolution and in the kernel
    "month_bounds": 1,  # the windows' last months' ends
}


@pytest.mark.parametrize("n", ROWS)
def test_preparing_and_valuing_a_window_run_the_months_functions(
    call_profile: CallProfile, numpy_calls: CallProfile, n: int
) -> None:
    histories = (history_of(A), history_of(C))
    markets = (quoted(histories[0], 3.50, 3.60), quoted(histories[1], 3.40, 3.45))
    curves = curve_set(SOFR)
    one, two = spread(ONETIME, n, WorkCounter()), spread(ASIAN, n, WorkCounter())
    for profile in (call_profile, numpy_calls):
        assert profile(lambda: prepared_trades(one.encoded, histories, WorkCounter())) == profile(
            lambda: prepared_trades(two.encoded, histories, WorkCounter())
        )
    ready_one = prepared_trades(one.encoded, histories, WorkCounter())
    ready_two = prepared_trades(two.encoded, histories, WorkCounter())
    for profile in (call_profile, numpy_calls):
        assert profile(lambda: trade_results(ready_one, markets, WorkCounter(), curves)) == profile(
            lambda: trade_results(ready_two, markets, WorkCounter(), curves)
        )
    # One payment where the months are two. The window's quantity is its total, one lot,
    # where a quantity by the month stands in each of the two months it touches.
    window = trade_results(ready_one, markets, WorkCounter(), curves)
    months = trade_results(ready_two, markets, WorkCounter(), curves)
    assert window.payment_amount is not None and months.payment_amount is not None
    assert (window.payment_amount.size, months.payment_amount.size) == (1, 2)
    for mine, theirs in zip(window.legs, months.legs, strict=True):
        assert 2 * mine.nominal_delta_total == pytest.approx(theirs.nominal_delta_total)


def test_a_window_holds_no_more_than_the_months_do() -> None:
    n = 500
    window = least_peak(lambda: spread(ONETIME, n, WorkCounter()))
    months = least_peak(lambda: spread(ASIAN, n, WorkCounter()))
    assert window <= months + SLACK
