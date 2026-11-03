"""Small, independently worked examples for the dense-matrix specimen."""

import dataclasses
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

# The specimen lives outside the installed package. pytest's executable does not
# add the repository root to sys.path as ``python -m`` does.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from catalyst.instrumentation.work_counts import WorkCounter
from tools.examples.linear_trade_matrices import (
    MarketPoint,
    ObservationKind,
    compact,
    compact_amounts,
    example,
    full_amounts,
    market_snapshot,
    prepare,
)


def test_hand_worked_rows_keep_daily_resolution_then_compress() -> None:
    trades, market = example()
    plan = prepare(trades, market.observations, WorkCounter())
    reduced = compact(plan, market, WorkCounter())
    assert reduced.source is plan
    assert reduced.source.trades is trades
    np.testing.assert_array_equal(
        plan.A,
        [
            [10000, 0, 0, 0, 0, 0],
            [0, -4000, 0, 0, 0, 0],
            [0, 0, 1500, 1500, 1500, 1500],
            [0, 0, -500, -500, -500, -500],
            [0, 0, 0, -3000, 0, 0],
        ],
    )
    np.testing.assert_array_equal(plan.c, [-700000, 284000, -423000, 142000, 212250])
    np.testing.assert_array_equal(
        reduced.W, [[10000, 0], [0, -4000], [1500, 3000], [-500, -1000], [-3000, 0]]
    )
    np.testing.assert_array_equal(reduced.b, [-700000, 284000, -318000, 107000, 212250])
    # Average (70 + 72 + 73 + 73) / 4 = 72; the fifth trade fixes at the second day.
    expected = np.array([20000, -8000, 9000, -2000, -3750])
    np.testing.assert_array_equal(full_amounts(plan, market, WorkCounter()), expected)
    np.testing.assert_array_equal(
        compact_amounts(reduced, market.point_keys, market.p, WorkCounter()), expected
    )


@given(st.tuples(st.floats(-1000, 1000), st.floats(-1000, 1000)))
def test_full_and_compressed_amounts_agree_after_arbitrary_price_changes(
    values: tuple[float, float],
) -> None:
    trades, original = example()
    plan = prepare(trades, original.observations, WorkCounter())
    reduced = compact(plan, original, WorkCounter())
    market = market_snapshot(
        original.point_keys,
        np.array(values),
        original.observations,
        original.B,
        original.k,
        original.is_fixed,
    )
    np.testing.assert_allclose(
        full_amounts(plan, market, WorkCounter()),
        compact_amounts(reduced, market.point_keys, market.p, WorkCounter()),
        rtol=1e-12,
        atol=1e-8,
    )


def test_each_trade_alone_keeps_the_same_shape_and_result_as_its_batch_row() -> None:
    trades, market = example()
    batch = prepare(trades, market.observations, WorkCounter())
    expected = full_amounts(batch, market, WorkCounter())
    for row, trade in enumerate(trades):
        one = prepare((trade,), market.observations, WorkCounter())
        reduced = compact(one, market, WorkCounter())
        assert one.A.shape == (1, 6)
        assert reduced.W.shape == (1, 2)
        np.testing.assert_array_equal(one.A, batch.A[row : row + 1])
        np.testing.assert_array_equal(
            compact_amounts(reduced, market.point_keys, market.p, WorkCounter()),
            expected[row : row + 1],
        )


def test_a_fixing_changes_market_binding_but_not_static_trades_or_current_marks() -> None:
    trades, original = example()
    plan = prepare(trades, original.observations, WorkCounter())
    A, c = plan.A.copy(), plan.c.copy()
    B, k, fixed = original.B.copy(), original.k.copy(), original.is_fixed.copy()
    B[3] = 0.0
    k[3], fixed[3] = 71.0, True
    market = market_snapshot(original.point_keys, original.p, original.observations, B, k, fixed)
    reduced = compact(plan, market, WorkCounter())
    # Asian average (70 + 71 + 73 + 73) / 4 = 71.75; pen amount now known.
    np.testing.assert_array_equal(
        full_amounts(plan, market, WorkCounter()), [20000, -8000, 7500, -1500, -750]
    )
    np.testing.assert_array_equal(reduced.W[:, 0], [10000, 0, 0, 0, 0])
    np.testing.assert_array_equal(reduced.W[4], [0, 0])
    assert plan.trades is trades
    np.testing.assert_array_equal(plan.A, A)
    np.testing.assert_array_equal(plan.c, c)
    assert not original.is_fixed[3] and original.k[3] == 0.0
    bumped = compact_amounts(
        reduced, market.point_keys, market.p + np.array([1.0, 0.0]), WorkCounter()
    )
    np.testing.assert_array_equal(bumped, [30000, -8000, 7500, -1500, -750])


def test_shared_schedules_and_identical_fixings_share_structure_not_trade_rows() -> None:
    trades, market = example()
    assert trades[2].schedule is trades[3].schedule
    assert trades[4].schedule.observations[0] is trades[2].schedule.observations[1]
    assert market.observations[0].kind is ObservationKind.CURRENT_MARK
    assert market.observations[3].kind is ObservationKind.SETTLEMENT
    plan = prepare((trades[2], trades[2]), market.observations, WorkCounter())
    assert plan.A.shape == (2, 6)
    np.testing.assert_array_equal(full_amounts(plan, market, WorkCounter()), [9000, 9000])
    assert trades[2].payment_date != trades[3].payment_date


def test_equal_market_values_do_not_merge_distinct_market_points() -> None:
    trades, market = example()
    plan = prepare(trades, market.observations, WorkCounter())
    reduced = compact(plan, market, WorkCounter())
    equal = np.array([72.0, 72.0])
    before = compact_amounts(reduced, market.point_keys, equal, WorkCounter())
    after = compact_amounts(reduced, market.point_keys, equal + np.array([1.0, 0.0]), WorkCounter())
    assert reduced.W.shape == (5, 2)
    np.testing.assert_array_equal(after - before, [10000, 0, 1500, -500, -3000])


def test_two_days_of_one_contract_can_use_distinct_projected_prices() -> None:
    trades, original = example()
    daily = (
        MarketPoint("NYMEX CL", "F27", date(2026, 12, 1)),
        MarketPoint("NYMEX CL", "F27", date(2026, 12, 2)),
    )
    B = np.zeros((6, 4))
    B[[0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 1, 1]] = 1.0
    market = market_snapshot(
        (*original.point_keys, *daily),
        np.array([72.0, 73.0, 69.0, 71.0]),
        original.observations,
        B,
        np.zeros(6),
        np.zeros(6, dtype=bool),
    )
    plan = prepare(trades, market.observations, WorkCounter())
    reduced = compact(plan, market, WorkCounter())
    expected = [20000, -8000, 6000, -1000, -750]  # average 71.5, pen fixing forecast 71
    np.testing.assert_array_equal(full_amounts(plan, market, WorkCounter()), expected)
    np.testing.assert_array_equal(
        compact_amounts(reduced, market.point_keys, market.p, WorkCounter()), expected
    )
    np.testing.assert_array_equal(reduced.W[2], [0, 3000, 1500, 1500])


def test_wrong_observation_and_price_axis_orders_fail_instead_of_mispricing() -> None:
    trades, market = example()
    plan = prepare(trades, market.observations, WorkCounter())
    wrong = market_snapshot(
        market.point_keys,
        market.p,
        market.observations[::-1],
        market.B[::-1],
        market.k[::-1],
        market.is_fixed[::-1],
    )
    with pytest.raises(ValueError, match="observation axis differs"):
        full_amounts(plan, wrong, WorkCounter())
    reduced = compact(plan, market, WorkCounter())
    with pytest.raises(ValueError, match="price axis differs"):
        compact_amounts(reduced, market.point_keys[::-1], market.p, WorkCounter())
    with pytest.raises(ValueError, match="unknown observation"):
        prepare(trades, market.observations[:-1], WorkCounter())


def test_a_zero_fixing_is_valid_but_an_unbound_observation_is_not() -> None:
    trades, market = example()
    known = market.k.copy()
    known[2] = 0.0
    zero = market_snapshot(
        market.point_keys, market.p, market.observations, market.B, known, market.is_fixed
    )
    plan = prepare(trades, zero.observations, WorkCounter())
    np.testing.assert_array_equal(
        full_amounts(plan, zero, WorkCounter()), [20000, -8000, -96000, 33000, -3750]
    )
    unbound = market.B.copy()
    unbound[3] = 0.0
    with pytest.raises(ValueError, match="no projection"):
        market_snapshot(
            market.point_keys, market.p, market.observations, unbound, market.k, market.is_fixed
        )


def test_static_and_derived_arrays_are_owned_and_read_only() -> None:
    trades, market = example()
    plan = prepare(trades, market.observations, WorkCounter())
    reduced = compact(plan, market, WorkCounter())
    for values in (
        plan.A,
        plan.c,
        market.p,
        market.B,
        market.k,
        market.is_fixed,
        reduced.W,
        reduced.b,
    ):
        assert values.flags.owndata and not values.flags.writeable
    with pytest.raises(dataclasses.FrozenInstanceError):
        field = "agreed_price"
        setattr(trades[0], field, 0.0)
