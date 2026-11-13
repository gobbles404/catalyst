"""observation-prices-readback.md, issue #228: the results readback shows each observation's
coefficient, price, unit and floating contribution, fixed or live, the preparation's settles and
the evaluation's quotes placed on their slots and nothing priced again; the issue's copper example
through its states, a tick, a corrected fixing, exposures of nothing, a contract crossed and the
bilateral path."""

from collections.abc import Mapping
from typing import cast

import numpy as np
import pytest
from test_bilateral_kernel import curve_of, curve_set
from test_create_trades import a_template, a_ticket
from test_quote import priced
from test_trades import an_index, quoted
from test_two_index import cell, grid

from catalyst.globals.discount_curve_set import DiscountCurveSet
from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.holiday_calendar import holiday_calendar
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades, trades
from catalyst.trades.results import TradeResults

# A copper-style index quoted in USD per LB: U26 bounding the calendar, V26 the October contract
# expiring Wednesday 28 October 2026, X26 and Z26 after it, a lot of one pound.
HG = an_index(
    "HG",
    (("U26", "2026-09-28"), ("V26", "2026-10-28"), ("X26", "2026-11-25"), ("Z26", "2026-12-29")),
    (),
    ("USD", "LB"),
    ("MASS", "LB"),
    ("LB", 1.0, "LB"),
)
PAYS = holiday_calendar(np.array(["2030-01-01"], dtype="datetime64[D]"))
CLEARED: dict[str, object] = {
    "quantity_unit": "LB",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "asian",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "CME Clearing",
    "payment_day": "+2bd",
    "payment_holiday_calendar": PAYS,
}
BILATERAL: dict[str, object] = {
    **{field: value for field, value in CLEARED.items() if field != "clearing_house"},
    "route": "bilateral",
    "counterparty": "ACME Trading",
    "discount_curve_key": "SOFR",
}
# The issue's row: 25,000 lb averaged over Monday 5 to Thursday 8 October 2026 at 4.00, four
# observations of 6,250 lb each, paying two business days after the last, Monday the 12th.
ROW: dict[str, list[object]] = {
    "trade_id": [1001],
    "trade_date": ["2026-09-30"],
    "start_date": ["2026-10-05"],
    "end_date": ["2026-10-08"],
    "quantity": [25_000.0],
    "fixed_price": [4.00],
}
SETTLES = {"2026-10-05": 4.10, "2026-10-06": 4.20, "2026-10-07": 4.22, "2026-10-08": 4.28}
COLUMNS = ("observation_coefficient", "observation_price", "price_unit", "floating_contribution")
# The issue's table: two days fixed at 4.10 and 4.20, two live at 4.30, 6,250 lb each.
MIXED = [
    [6_250.0, 4.10, "USD/LB", pytest.approx(25_625.0)],
    [6_250.0, 4.20, "USD/LB", pytest.approx(26_250.0)],
    [6_250.0, 4.30, "USD/LB", pytest.approx(26_875.0)],
    [6_250.0, 4.30, "USD/LB", pytest.approx(26_875.0)],
]


def settle(day: np.datetime64) -> float:
    return SETTLES.get(str(day), 4.00)


def booked(
    template: Mapping[str, object] = CLEARED, ticket: Mapping[str, list[object]] = ROW
) -> Trades:
    return trades((HG,), a_ticket(ticket), a_template(template), UNITS, WorkCounter())


def valued(
    as_of: str,
    *quotes: float,
    batch: Trades | None = None,
    curves: DiscountCurveSet | None = None,
) -> TradeResults:
    """The batch prepared against HG's history on that day, every fixed day settled as SETTLES
    says and at 4.00 elsewhere, and valued against the quotes from the prompt contract on."""
    market = priced(HG, as_of, settle, *quotes)
    batch = booked() if batch is None else batch
    prepared = prepared_trades(batch.encoded, (market.market_history,), WorkCounter())
    return trade_results(prepared, (market,), WorkCounter(), curves)


def facts(results: TradeResults) -> list[list[object]]:
    """The four columns' body rows, one per slot: coefficient, price, unit and contribution."""
    table = grid(results)
    return [[cell(table, r, name) for name in COLUMNS] for r in range(len(table) - 2)]


def test_the_issues_mixed_example_reads_each_observations_price_and_contribution() -> None:
    results = valued("2026-10-07", 4.30)
    table = grid(results)
    assert table[0][-4:] == list(COLUMNS)  # appended last: no column before them moves
    assert table[1][-4:] == ["float64", "float64", "str", "float64"]
    assert facts(results) == MIXED
    # The live columns as they were: zero on the fixed rows, the slot's own on the live ones.
    assert [cell(table, r, "is_fixed") for r in range(4)] == [1.0, 1.0, 0.0, 0.0]
    assert [cell(table, r, "live_coefficient") for r in range(4)] == [0.0, 0.0, 6_250.0, 6_250.0]
    assert [cell(table, r, "live_contribution") for r in range(4)] == [
        0.0,
        0.0,
        pytest.approx(26_875.0),
        pytest.approx(26_875.0),
    ]
    # The floating leg whole, 105,625, against the fixed leg of 100,000: the issue's 5,625 of
    # mark; nothing of the mark, the cash or the risk is moved by the columns.
    floating = sum(cast(float, line[3]) for line in facts(results))
    assert floating == pytest.approx(105_625.0)
    assert results.mark == pytest.approx(5_625.0) and results.cash == 0.0


@pytest.mark.parametrize(
    ("as_of", "prices", "mark", "cash"),
    [
        ("2026-10-02", [4.30, 4.30, 4.30, 4.30], 7_500.0, 0.0),
        ("2026-10-09", [4.10, 4.20, 4.22, 4.28], 5_000.0, 0.0),
        ("2026-10-13", [4.10, 4.20, 4.22, 4.28], 0.0, 5_000.0),
    ],
    ids=["2 Oct, all live", "9 Oct, all fixed and unpaid", "13 Oct, paid"],
)
def test_every_state_shows_each_slots_price_and_a_paid_group_keeps_its_history(
    as_of: str, prices: list[float], mark: float, cash: float
) -> None:
    results = valued(as_of, 4.30)
    assert facts(results) == [
        [6_250.0, price, "USD/LB", pytest.approx(6_250.0 * price)] for price in prices
    ]
    assert results.mark == pytest.approx(mark) and results.cash == pytest.approx(cash)
    table = grid(results)
    fixed = [cell(table, r, "is_fixed") == 1.0 for r in range(4)]
    assert [cell(table, r, "live_contribution") == 0.0 for r in range(4)] == fixed


def test_a_tick_moves_the_live_prices_and_contributions_alone_over_the_same_arrays() -> None:
    market = priced(HG, "2026-10-07", settle, 4.30)
    prepared = prepared_trades(booked().encoded, (market.market_history,), WorkCounter())
    first = trade_results(prepared, (market,), WorkCounter(), None)
    ticked = trade_results(prepared, (quoted(market.market_history, 4.40),), WorkCounter(), None)
    assert [line[1] for line in facts(ticked)] == [4.10, 4.20, 4.40, 4.40]
    assert [line[3] for line in facts(ticked)] == [
        pytest.approx(25_625.0),
        pytest.approx(26_250.0),
        pytest.approx(27_500.0),
        pytest.approx(27_500.0),
    ]
    assert facts(first) == MIXED  # the first result stands
    leg, again = first.legs[0], ticked.legs[0]
    assert again.prepared is leg.prepared  # the fixed facts are the preparation's, shared
    assert leg.prepared.settle.tolist() == [4.10, 4.20]  # one per fixed slot, in slot order
    assert leg.prepared.fixed_contribution.tolist() == pytest.approx([25_625.0, 26_250.0, 0, 0])
    assert leg.quote.tolist() == [4.30] and again.quote.tolist() == [4.40]  # V26, the one reference
    for array in (leg.prepared.settle, leg.prepared.fixed_contribution, leg.quote, again.quote):
        assert not array.flags.writeable


def test_a_corrected_fixing_reaches_the_readback_through_a_new_preparation() -> None:
    first = valued("2026-10-07", 4.30)
    corrected = priced(
        HG, "2026-10-07", lambda day: 4.25 if str(day) == "2026-10-06" else settle(day), 4.30
    )
    with pytest.raises(ValueError, match="another history"):
        trade_results(first.prepared, (corrected,), WorkCounter(), None)
    prepared = prepared_trades(first.prepared.encoded, (corrected.market_history,), WorkCounter())
    again = trade_results(prepared, (corrected,), WorkCounter(), None)
    assert [line[1] for line in facts(again)] == [4.10, 4.25, 4.30, 4.30]
    assert facts(again)[1][3] == pytest.approx(26_562.5)


def test_exposures_of_nothing_keep_their_prices() -> None:
    # Two rows of one group net to nothing on every slot, and a row of nothing is a slot of
    # nothing: the coefficient and the contribution zero, the price the slot was valued at shown
    # as on any other, no quotient of the two taken.
    nothing = [[0.0, price, "USD/LB", 0.0] for price in (4.10, 4.20, 4.30, 4.30)]
    netted = booked(
        ticket={
            "trade_id": [1001, 1002],
            "trade_date": ["2026-09-30"] * 2,
            "start_date": ["2026-10-05"] * 2,
            "end_date": ["2026-10-08"] * 2,
            "quantity": [25_000.0, -25_000.0],
            "fixed_price": [4.00, 4.00],
        }
    )
    assert facts(valued("2026-10-07", 4.30, batch=netted)) == nothing
    assert facts(valued("2026-10-07", 4.30, batch=booked(ticket={**ROW, "quantity": [0.0]}))) == (
        nothing
    )


def test_an_average_crossing_its_contracts_expiry_prices_each_day_at_its_own_contract() -> None:
    # Monday 26 to Friday 30 October 2026 valued on Tuesday the 27th: the 26th fixed at 4.00,
    # the days through V26's expiry on the 28th live at V26's quote and the days after at X26's,
    # each slot priced at the quote of the contract its row names,
    # calendar-driven-asian-references.md.
    crossing = booked(ticket={**ROW, "start_date": ["2026-10-26"], "end_date": ["2026-10-30"]})
    table = grid(valued("2026-10-27", 4.30, 4.40, 4.50, batch=crossing))
    quote_of = {"V26": 4.30, "X26": 4.40}
    contracts = [str(cell(table, r, "pricing_contract")) for r in range(5)]
    assert set(contracts) == {"V26", "X26"} and contracts == sorted(contracts)
    assert [cell(table, r, "observation_price") for r in range(5)] == [
        4.00,
        *[quote_of[contract] for contract in contracts[1:]],
    ]
    assert [cell(table, r, "observation_coefficient") for r in range(5)] == [5_000.0] * 5
    assert cell(table, 4, "floating_contribution") == pytest.approx(5_000.0 * 4.40)


def test_a_bilateral_result_shows_the_same_contributions_before_discounting() -> None:
    curves = curve_set(curve_of(("2026-10-07", 1.0), ("2026-10-12", 0.99)))
    results = valued("2026-10-07", 4.30, batch=booked(BILATERAL), curves=curves)
    assert facts(results) == MIXED  # the floating leg before the curve touches it
    table = grid(results)
    assert cell(table, 0, "discount_curve") == "SOFR" and cell(table, 0, "payment_factor") == 0.99
    assert results.mark == pytest.approx(5_625.0 * 0.99)
