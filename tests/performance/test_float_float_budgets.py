"""The work of a float_float, float-float-spread.md, measured against a fixed_float pair on the
same two indexes and rows at one row and at many: the spread is counted as the pair is at every
step, creation, preparation, a tick and the collection, since its second leg's sign is taken
once in the conversions the creation already makes and nothing later has a step for it. It runs
the pair's functions, its own rules and, since float-float-units.md, the handful that reads
its spread price's unit and makes that unit's coefficient at creation, the same at one row and
at many; after creation the pair's functions and numpy calls and none more; and it holds a
pair's memory at each step to the slack the seam allows. The indexes and the rows are the pair
budgets' own: A a futures index, B an IFERC one."""

from collections.abc import Callable, Mapping

import pytest
from test_seam_allocation import SLACK, least_peak
from test_two_index_budgets import (
    CALENDARS,
    ROWS,
    SOFR,
    TEMPLATE,
    TICKET,
    A,
    B,
    counts_of,
    curve_set,
    history_a,
    history_b,
    pair,
    quoted,
    typed,
)

from catalyst.globals.unit_conversions import UNITS
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FLOAT_FLOAT
from catalyst.instruments.fields import FieldValues
from catalyst.trades.aggregation import aggregate_results
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades, trades
from catalyst.trades.template import trade_template

CallProfile = Callable[[Callable[[], object]], dict[str, int]]

# The pair's row with a spread price where its outright stood: A at 3.50 less B at -0.40 is
# 3.90, a dime over 3.80.
SPREAD_TICKET: dict[str, list[object]] = {
    **{name: values for name, values in TICKET.items() if name != "fixed_price"},
    "spread_price": [3.80],
}


def a_ticket(columns: Mapping[str, list[object]]) -> FieldValues:
    rows = len(next(iter(columns.values())))
    return FieldValues(
        FLOAT_FLOAT,
        rows,
        tuple(columns),
        {name: typed(FLOAT_FLOAT, name, values) for name, values in columns.items()},
        {},
    )


# The pair's template with the spread price's unit, float-float-units.md, the unit both indexes
# quote in: dollars per MMBTU.
SPREAD_TEMPLATE: dict[str, object] = {
    **TEMPLATE,
    "spread_price_currency_unit": "DOLLAR",
    "spread_price_quantity_unit": "MMBTU",
}


def spread(n: int, counter: WorkCounter) -> Trades:
    """n rows of A less B, each its own occurrence of G27."""
    template = trade_template(a_ticket({k: [v] for k, v in SPREAD_TEMPLATE.items()}))
    ticket = a_ticket({name: list(values) * n for name, values in SPREAD_TICKET.items()})
    return trades((A, B), ticket, template, UNITS, counter, CALENDARS)


@pytest.mark.parametrize("n", ROWS)
def test_a_spread_is_counted_as_a_pair_is_at_every_step(n: int) -> None:
    hist_a, hist_b = history_a(), history_b()
    markets = (quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42))
    curves = curve_set(SOFR)
    mine: list[dict[str, int]] = []
    theirs: list[dict[str, int]] = []
    for make, counts in ((spread, mine), (pair, theirs)):
        counter = WorkCounter()
        batch = make(n, counter)
        counts.append(counts_of(counter).as_dict())
        counter = WorkCounter()
        prepared = prepared_trades(batch.encoded, (hist_a, hist_b), counter)
        counts.append(counts_of(counter).as_dict())
        counter = WorkCounter()
        results = trade_results(prepared, markets, counter, curves)
        counts.append(counts_of(counter).as_dict())
        counter = WorkCounter()
        aggregate_results((results,), counter)
        counts.append(counts_of(counter).as_dict())
    steps = ("creation", "preparation", "tick", "collection")
    for step, spread_counts, pair_counts in zip(steps, mine, theirs, strict=True):
        assert spread_counts == pair_counts, step
    # The tick, stated: each leg's quote read, one curve and one factor for the one payment,
    # each leg's slot discounted and weighted, eight reductions a leg and four for the trade,
    # whatever the rows.
    tick = mine[2]
    assert tick["kernel"] == 1
    assert tick["live_prices_read"] == 2
    assert tick["curves_selected"] == 1
    assert tick["payment_factors_read"] == 1
    assert tick["groups_valued"] == 1
    assert tick["slots_discounted"] == 2
    assert tick["slots_weighted"] == 2
    assert tick["risk_reductions"] == 20


@pytest.mark.parametrize("n", ROWS)
def test_a_spread_runs_a_pairs_functions_and_its_own_two_rules(
    call_profile: CallProfile, numpy_calls: CallProfile, n: int
) -> None:
    # Creation: the pair's calls, and the spread's rules once in the resolution and once in the
    # kernel, with the broker and the trade IDs the resolution reads for them a step early.
    mine = call_profile(lambda: spread(n, WorkCounter()))
    theirs = call_profile(lambda: pair(n, WorkCounter()))
    more = {
        name: mine[name] - theirs.get(name, 0) for name in mine if mine[name] != theirs.get(name)
    }
    assert more == {
        "spread_legs": 2,
        "spread_rules": 2,
        "_Fields.labels": 1,  # the brokers, asked for by the rule: none here, the field absent
        # Once for the brokers, and once each among the required fields for the second index's
        # method, always required of a spread, and the spread price's two units.
        "_Fields.has": 4,
        "FieldValues.has": 1,
        # float-float-units.md, the spread price's unit, whatever the rows: its two fields read
        # into the template and out of it as the batch's one each,
        "field_value": 2,
        "_holds": 2,
        "FieldValues.field": 2,
        "FieldValues.field.<locals>.<genexpr>": 4,
        "FieldValues.texts": 2,
        "_Fields.one_text": 2,
        # the pair's rules of a spread where the one-unit rule ran inline, once in the
        # resolution, before a quantity unit is read on the second index, and once in the kernel,
        "spread_pair": 2,
        # and the spread price's coefficient: each leg's selected specification restated in the
        # spread price's quantity unit, one factor each, and the currency factor.
        "_the_spread_coefficient": 1,
        "_the_sizes": 2,
        "UnitConversions.factor": 3,
        "UnitConversions.category": 3,
    }
    assert set(theirs) <= set(mine)
    # The pair's numpy calls and the coefficient's own: a row of sizes per leg, the flags down
    # round each conversion and the product, and one look that every coefficient is finite.
    # No sort, no unique and no pass over the rows but that product and that look.
    mine_numpy = numpy_calls(lambda: spread(n, WorkCounter()))
    theirs_numpy = numpy_calls(lambda: pair(n, WorkCounter()))
    assert {
        name: mine_numpy[name] - theirs_numpy.get(name, 0)
        for name in mine_numpy
        if mine_numpy[name] != theirs_numpy.get(name)
    } == {"numpy.zeros": 2, "numpy._make_extobj": 3, "ndarray.any": 1, "ufunc.reduce": 1}
    assert set(theirs_numpy) <= set(mine_numpy)
    # Preparation and a tick: the same functions and the same numpy calls, name for name.
    hist_a, hist_b = history_a(), history_b()
    markets = (quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42))
    curves = curve_set(SOFR)
    one, other = spread(n, WorkCounter()), pair(n, WorkCounter())
    for profile in (call_profile, numpy_calls):
        assert profile(
            lambda: prepared_trades(one.encoded, (hist_a, hist_b), WorkCounter())
        ) == profile(lambda: prepared_trades(other.encoded, (hist_a, hist_b), WorkCounter()))
    prepared_one = prepared_trades(one.encoded, (hist_a, hist_b), WorkCounter())
    prepared_other = prepared_trades(other.encoded, (hist_a, hist_b), WorkCounter())
    for profile in (call_profile, numpy_calls):
        assert profile(lambda: trade_results(prepared_one, markets, WorkCounter(), curves)) == (
            profile(lambda: trade_results(prepared_other, markets, WorkCounter(), curves))
        )


def test_a_spread_holds_a_pairs_memory_at_each_step() -> None:
    n = 500
    hist_a, hist_b = history_a(), history_b()
    markets = (quoted(hist_a, 3.50, 3.60), quoted(hist_b, -0.38, -0.40, -0.42))
    curves = curve_set(SOFR)
    one, other = spread(n, WorkCounter()), pair(n, WorkCounter())
    prepared_one = prepared_trades(one.encoded, (hist_a, hist_b), WorkCounter())
    prepared_other = prepared_trades(other.encoded, (hist_a, hist_b), WorkCounter())
    steps: tuple[tuple[str, Callable[[], object], Callable[[], object]], ...] = (
        ("creation", lambda: spread(n, WorkCounter()), lambda: pair(n, WorkCounter())),
        (
            "preparation",
            lambda: prepared_trades(one.encoded, (hist_a, hist_b), WorkCounter()),
            lambda: prepared_trades(other.encoded, (hist_a, hist_b), WorkCounter()),
        ),
        (
            "evaluation",
            lambda: trade_results(prepared_one, markets, WorkCounter(), curves),
            lambda: trade_results(prepared_other, markets, WorkCounter(), curves),
        ),
    )
    for name, mine, theirs in steps:
        assert least_peak(mine) <= least_peak(theirs) + SLACK, name
