"""Work budgets for the isolated dense-matrix specimen, not a production pricer."""

import sys
from pathlib import Path

import pytest

# The specimen is deliberately outside the installed production package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from catalyst.instrumentation.work_counts import WorkCounter
from tools.examples.linear_trade_matrices import (
    compact,
    compact_amounts,
    example,
    full_amounts,
    prepare,
)


@pytest.mark.parametrize("repetitions", [1, 100])
def test_repeated_trade_occurrences_share_schedule_preparation(repetitions: int) -> None:
    trades, market = example()
    counter = WorkCounter()
    plan = prepare(trades * repetitions, market.observations, counter)
    assert plan.A.shape == (5 * repetitions, 6)
    assert counter.freeze().as_dict() == {
        "plan_build": 1,
        "trade_row": 5 * repetitions,
        "schedule_build": 4,
        "observation_binding": 7,
        "dense_exposure_cell": 30 * repetitions,
        "weighted_observation": 11 * repetitions,
    }


@pytest.mark.parametrize("count", [1, 5])
def test_one_or_many_components_use_the_same_dense_operation_counts(count: int) -> None:
    trades, market = example()
    plan = prepare(trades[:count], market.observations, WorkCounter())
    full_counter = WorkCounter()
    full_amounts(plan, market, full_counter)
    assert full_counter.freeze().as_dict() == {
        "matrix_vector": 2,
        "dense_product_term": 12 + 6 * count,
    }
    compact_counter = WorkCounter()
    reduced = compact(plan, market, compact_counter)
    assert compact_counter.freeze().as_dict() == {
        "matrix_matrix": 1,
        "matrix_vector": 1,
        "dense_product_term": 18 * count,
    }
    update_counter = WorkCounter()
    compact_amounts(reduced, market.point_keys, market.p, update_counter)
    assert update_counter.freeze().as_dict() == {
        "matrix_vector": 1,
        "dense_product_term": 2 * count,
    }
