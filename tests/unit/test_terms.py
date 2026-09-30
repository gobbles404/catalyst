"""The terms: six rules on the four columns, the terms grouped by component with their runs
found, the columns the record keeps frozen, and the one number found."""

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.valuation.terms import terms


def floats(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def ints(*values: int) -> NDArray[np.intp]:
    return np.array(values, dtype=np.intp)


# The page's sample: two components, an NG outright of 100,000 MMBtu bought at 3.10, reading
# observation 0, and a three-day ethane average of three lots at 25.10, 63 USD per cent per gallon
# on each day, reading observations 1 to 3.
FIXED_LEG = floats(-310_000.0, -1_260.0 * 25.10)
COMPONENT = ints(0, 1, 1, 1)
OBSERVATION = ints(0, 1, 2, 3)
COEFFICIENT = floats(100_000.0, 63.0, 63.0, 63.0)


def test_the_sample_keeps_its_columns_and_finds_the_observations_read() -> None:
    made = terms(FIXED_LEG, COMPONENT, OBSERVATION, COEFFICIENT)
    assert made.components == 2
    assert made.observations == 4
    np.testing.assert_array_equal(made.fixed_leg, FIXED_LEG)
    np.testing.assert_array_equal(made.component, COMPONENT)
    np.testing.assert_array_equal(made.observation, OBSERVATION)
    np.testing.assert_array_equal(made.coefficient, COEFFICIENT)
    np.testing.assert_array_equal(made.first, ints(0, 1, 4))
    for column in (made.fixed_leg, made.component, made.observation, made.coefficient, made.first):
        assert not column.flags.writeable


def test_the_terms_are_grouped_by_component_in_the_order_given_and_the_runs_found() -> None:
    made = terms(
        floats(1.0, 2.0, 3.0), ints(2, 0, 2, 0), ints(10, 11, 12, 13), floats(0.1, 0.2, 0.3, 0.4)
    )
    np.testing.assert_array_equal(made.component, ints(0, 0, 2, 2))
    np.testing.assert_array_equal(made.observation, ints(11, 13, 10, 12))
    np.testing.assert_array_equal(made.coefficient, floats(0.2, 0.4, 0.1, 0.3))
    np.testing.assert_array_equal(made.first, ints(0, 2, 2, 4))  # component 1's run is empty
    assert made.observations == 14


def test_the_columns_are_copies_so_the_caller_keeps_its_own() -> None:
    fixed_leg, coefficient = FIXED_LEG.copy(), COEFFICIENT.copy()
    made = terms(fixed_leg, COMPONENT, OBSERVATION, coefficient)
    fixed_leg[0] = 1.0
    coefficient[0] = 2.0
    assert made.fixed_leg[0] == -310_000.0
    assert made.coefficient[0] == 100_000.0
    assert fixed_leg.flags.writeable and coefficient.flags.writeable


def test_a_component_with_no_term_is_allowed_and_so_are_no_terms_at_all() -> None:
    quiet = terms(floats(5.0, 6.0), ints(1), ints(0), floats(2.0))
    assert quiet.components == 2 and quiet.observations == 1
    np.testing.assert_array_equal(quiet.first, ints(0, 0, 1))
    none = terms(floats(5.0), ints(), ints(), floats())
    assert none.components == 1 and none.observations == 0 and none.coefficient.size == 0
    np.testing.assert_array_equal(none.first, ints(0, 0))


def test_a_coefficient_of_zero_is_allowed() -> None:
    made = terms(floats(0.0), ints(0), ints(7), floats(0.0))
    assert made.observations == 8


@pytest.mark.parametrize(
    ("fixed_leg", "component", "observation", "coefficient", "message"),
    [
        (
            floats(),
            ints(),
            ints(),
            floats(),
            "fixed_leg has 0 rows, expected 1 or more, one per component",
        ),
        (
            FIXED_LEG,
            ints(0, 1, 1),
            OBSERVATION,
            COEFFICIENT,
            "component has 3 rows, expected 4, one per term as coefficient has",
        ),
        (
            FIXED_LEG,
            COMPONENT,
            ints(0),
            COEFFICIENT,
            "observation has 1 row, expected 4, one per term as coefficient has",
        ),
        (
            floats(-310_000.0, np.nan),
            COMPONENT,
            OBSERVATION,
            COEFFICIENT,
            "fixed_leg row 2 is nan, expected a finite number",
        ),
        (
            FIXED_LEG,
            COMPONENT,
            OBSERVATION,
            floats(100_000.0, 63.0, np.inf, 63.0),
            "coefficient row 3 is inf, expected a finite number",
        ),
        (
            FIXED_LEG,
            ints(0, 2, 1, 1),
            OBSERVATION,
            COEFFICIENT,
            "component row 2 is 2, expected 0 through 1, the components counted from zero",
        ),
        (
            FIXED_LEG,
            ints(-1, 1, 1, 1),
            OBSERVATION,
            COEFFICIENT,
            "component row 1 is -1, expected 0 through 1, the components counted from zero",
        ),
        (
            FIXED_LEG,
            COMPONENT,
            ints(0, 1, 2, -1),
            COEFFICIENT,
            "observation row 4 is -1, expected 0 or more",
        ),
    ],
)
def test_a_rule_that_fails_names_the_row_and_what_was_wanted(
    fixed_leg: NDArray[np.float64],
    component: NDArray[np.intp],
    observation: NDArray[np.intp],
    coefficient: NDArray[np.float64],
    message: str,
) -> None:
    with pytest.raises(ValueError) as caught:
        terms(fixed_leg, component, observation, coefficient)
    assert str(caught.value) == message
