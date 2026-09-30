"""The binding: three rules on the market's answers for one fixing state, each observation bound
to its print or to the contract whose mark prices it, no mark held, and the copies the record
keeps frozen; and the prices, one per observation for one vector of marks, with two rules of
their own."""

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import OBSERVATION, WorkCounter
from goosedove.valuation.binding import binding, prices


def floats(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def ints(*values: int) -> NDArray[np.intp]:
    return np.array(values, dtype=np.intp)


def flags(*values: bool) -> NDArray[np.bool_]:
    return np.array(values, dtype=np.bool_)


# The page's sample: four observations, the first two fixed with their prints, the last two not
# yet, bound to the first and the second of two marks.
IS_FIXED = flags(True, True, False, False)
PRINTS = floats(24.50, 25.00, np.nan, np.nan)
MARK_OF = ints(0, 0, 0, 1)
MARKS = floats(26.10, 25.80)


def test_the_sample_binds_the_fixed_to_their_prints_and_the_rest_to_their_contracts() -> None:
    made = binding(IS_FIXED, PRINTS, MARK_OF, 2)
    np.testing.assert_array_equal(made.is_fixed, IS_FIXED)
    np.testing.assert_array_equal(made.prints, PRINTS)
    np.testing.assert_array_equal(made.mark_of, MARK_OF)
    assert made.marks == 2 and made.observations == 4
    for column in (made.is_fixed, made.prints, made.mark_of):
        assert not column.flags.writeable


def test_the_prices_are_the_prints_where_fixed_and_the_marks_where_not() -> None:
    counter = WorkCounter()
    made = prices(binding(IS_FIXED, PRINTS, MARK_OF, 2), MARKS, counter)
    np.testing.assert_array_equal(made, floats(24.50, 25.00, 26.10, 25.80))
    assert counter.freeze().as_dict() == {OBSERVATION: 4}


def test_one_binding_prices_any_vector_of_marks_and_each_result_is_a_new_array() -> None:
    bound = binding(IS_FIXED, PRINTS, MARK_OF, 2)
    first = prices(bound, MARKS, WorkCounter())
    second = prices(bound, floats(26.20, 25.70), WorkCounter())
    np.testing.assert_array_equal(second, floats(24.50, 25.00, 26.20, 25.70))
    assert first is not second and first.flags.writeable
    np.testing.assert_array_equal(first, floats(24.50, 25.00, 26.10, 25.80))


def test_the_columns_are_copies_so_the_caller_keeps_its_own() -> None:
    prints = PRINTS.copy()
    made = binding(IS_FIXED, prints, MARK_OF, 2)
    prints[0] = 1.0
    assert made.prints[0] == 24.50
    assert prices(made, MARKS, WorkCounter())[0] == 24.50
    assert prints.flags.writeable


def test_a_print_on_an_observation_not_yet_fixed_is_not_read() -> None:
    made = binding(IS_FIXED, floats(24.50, 25.00, 99.0, 99.0), MARK_OF, 2)
    np.testing.assert_array_equal(
        prices(made, MARKS, WorkCounter()), floats(24.50, 25.00, 26.10, 25.80)
    )


def test_a_fixed_observations_mapping_is_not_read_since_its_contract_may_have_expired() -> None:
    made = binding(IS_FIXED, PRINTS, ints(99, -1, 0, 1), 2)
    np.testing.assert_array_equal(
        prices(made, MARKS, WorkCounter()), floats(24.50, 25.00, 26.10, 25.80)
    )


def test_every_observation_fixed_needs_no_mark_at_all() -> None:
    made = binding(flags(True, True), floats(24.50, 25.00), ints(0, 0), 0)
    np.testing.assert_array_equal(prices(made, floats(), WorkCounter()), floats(24.50, 25.00))
    assert made.marks == 0


def test_no_observation_at_all_is_a_binding_of_nothing() -> None:
    made = binding(flags(), floats(), ints(), 2)
    assert made.observations == 0
    assert prices(made, MARKS, WorkCounter()).size == 0


@pytest.mark.parametrize(
    ("is_fixed", "prints", "mark_of", "marks", "message"),
    [
        (
            IS_FIXED,
            floats(24.50, 25.00, np.nan),
            MARK_OF,
            2,
            "prints has 3 rows, expected 4, one per observation as is_fixed has",
        ),
        (
            IS_FIXED,
            PRINTS,
            ints(0, 0, 0, 1, 1),
            2,
            "mark_of has 5 rows, expected 4, one per observation as is_fixed has",
        ),
        (
            IS_FIXED,
            floats(24.50, np.nan, np.nan, np.nan),
            MARK_OF,
            2,
            "prints row 2 is nan, expected a finite number, since observation 2 has fixed",
        ),
        (
            IS_FIXED,
            PRINTS,
            ints(0, 0, 0, 2),
            2,
            "mark_of row 4 is 2, expected 0 through 1, the marks counted from zero, "
            "since observation 4 has not fixed",
        ),
        (
            IS_FIXED,
            PRINTS,
            ints(0, 0, -1, 1),
            2,
            "mark_of row 3 is -1, expected 0 through 1, the marks counted from zero, "
            "since observation 3 has not fixed",
        ),
        (
            IS_FIXED,
            PRINTS,
            MARK_OF,
            0,
            "mark_of row 3 is 0, expected a mark, and marks is 0, "
            "since observation 3 has not fixed",
        ),
    ],
)
def test_a_binding_rule_that_fails_names_the_row_and_what_was_wanted(
    is_fixed: NDArray[np.bool_],
    prints: NDArray[np.float64],
    mark_of: NDArray[np.intp],
    marks: int,
    message: str,
) -> None:
    with pytest.raises(ValueError) as caught:
        binding(is_fixed, prints, mark_of, marks)
    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("marks", "message"),
    [
        (floats(26.10), "marks has 1 row, expected 2, one per mark as the binding has"),
        (
            floats(26.10, 25.80, 25.40),
            "marks has 3 rows, expected 2, one per mark as the binding has",
        ),
        (floats(26.10, np.nan), "marks row 2 is nan, expected a finite number"),
        (floats(np.inf, 25.80), "marks row 1 is inf, expected a finite number"),
    ],
)
def test_a_prices_rule_that_fails_names_the_row_and_counts_nothing(
    marks: NDArray[np.float64], message: str
) -> None:
    counter = WorkCounter()
    with pytest.raises(ValueError) as caught:
        prices(binding(IS_FIXED, PRINTS, MARK_OF, 2), marks, counter)
    assert str(caught.value) == message
    assert counter.freeze().as_dict() == {}
