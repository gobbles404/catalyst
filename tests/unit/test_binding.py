"""The binding: five rules on the market's answers, one price per observation, the print where
fixed and the mark where not, and the copies the record keeps frozen."""

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import OBSERVATION, WorkCounter
from goosedove.valuation.binding import binding


def floats(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def ints(*values: int) -> NDArray[np.intp]:
    return np.array(values, dtype=np.intp)


def flags(*values: bool) -> NDArray[np.bool_]:
    return np.array(values, dtype=np.bool_)


# The page's sample: four observations, the first two fixed with their prints, the last two not
# yet, priced by the first and the second of two marks.
IS_FIXED = flags(True, True, False, False)
PRINTS = floats(24.50, 25.00, np.nan, np.nan)
MARK_OF = ints(0, 0, 0, 1)
MARKS = floats(26.10, 25.80)


def test_the_sample_prices_the_fixed_by_their_prints_and_the_rest_by_their_marks() -> None:
    counter = WorkCounter()
    made = binding(IS_FIXED, PRINTS, MARK_OF, MARKS, counter)
    np.testing.assert_array_equal(made.price, floats(24.50, 25.00, 26.10, 25.80))
    np.testing.assert_array_equal(made.is_fixed, IS_FIXED)
    np.testing.assert_array_equal(made.mark_of, MARK_OF)
    np.testing.assert_array_equal(made.marks, MARKS)
    assert made.observations == 4
    assert counter.freeze().as_dict() == {OBSERVATION: 4}
    for column in (made.is_fixed, made.price, made.mark_of, made.marks):
        assert not column.flags.writeable


def test_the_columns_are_copies_so_the_caller_keeps_its_own() -> None:
    prints, marks = PRINTS.copy(), MARKS.copy()
    made = binding(IS_FIXED, prints, MARK_OF, marks, WorkCounter())
    prints[0] = 1.0
    marks[0] = 2.0
    assert made.price[0] == 24.50 and made.price[2] == 26.10 and made.marks[0] == 26.10
    assert prints.flags.writeable and marks.flags.writeable


def test_a_print_on_an_observation_not_yet_fixed_is_not_read() -> None:
    made = binding(IS_FIXED, floats(24.50, 25.00, 99.0, 99.0), MARK_OF, MARKS, WorkCounter())
    np.testing.assert_array_equal(made.price, floats(24.50, 25.00, 26.10, 25.80))


def test_a_fixed_observations_mapping_is_not_read_since_its_contract_may_have_expired() -> None:
    made = binding(IS_FIXED, PRINTS, ints(99, -1, 0, 1), MARKS, WorkCounter())
    np.testing.assert_array_equal(made.price, floats(24.50, 25.00, 26.10, 25.80))


def test_every_observation_fixed_needs_no_mark_at_all() -> None:
    made = binding(flags(True, True), floats(24.50, 25.00), ints(0, 0), floats(), WorkCounter())
    np.testing.assert_array_equal(made.price, floats(24.50, 25.00))
    assert made.marks.size == 0


def test_no_observation_at_all_is_a_binding_of_nothing() -> None:
    made = binding(flags(), floats(), ints(), MARKS, WorkCounter())
    assert made.observations == 0


@pytest.mark.parametrize(
    ("is_fixed", "prints", "mark_of", "marks", "message"),
    [
        (
            IS_FIXED,
            floats(24.50, 25.00, np.nan),
            MARK_OF,
            MARKS,
            "prints has 3 rows, expected 4, one per observation as is_fixed has",
        ),
        (
            IS_FIXED,
            PRINTS,
            ints(0, 0, 0, 1, 1),
            MARKS,
            "mark_of has 5 rows, expected 4, one per observation as is_fixed has",
        ),
        (
            IS_FIXED,
            PRINTS,
            MARK_OF,
            floats(26.10, np.nan),
            "marks row 2 is nan, expected a finite number",
        ),
        (
            IS_FIXED,
            floats(24.50, np.nan, np.nan, np.nan),
            MARK_OF,
            MARKS,
            "prints row 2 is nan, expected a finite number, since observation 2 has fixed",
        ),
        (
            IS_FIXED,
            PRINTS,
            ints(0, 0, 0, 2),
            MARKS,
            "mark_of row 4 is 2, expected 0 through 1, the marks counted from zero, "
            "since observation 4 has not fixed",
        ),
        (
            IS_FIXED,
            PRINTS,
            ints(0, 0, -1, 1),
            MARKS,
            "mark_of row 3 is -1, expected 0 through 1, the marks counted from zero, "
            "since observation 3 has not fixed",
        ),
        (
            IS_FIXED,
            PRINTS,
            MARK_OF,
            floats(),
            "mark_of row 3 is 0, expected a mark, and marks has 0 rows, "
            "since observation 3 has not fixed",
        ),
    ],
)
def test_a_rule_that_fails_names_the_row_and_what_was_wanted(
    is_fixed: NDArray[np.bool_],
    prints: NDArray[np.float64],
    mark_of: NDArray[np.intp],
    marks: NDArray[np.float64],
    message: str,
) -> None:
    counter = WorkCounter()
    with pytest.raises(ValueError) as caught:
        binding(is_fixed, prints, mark_of, marks, counter)
    assert str(caught.value) == message
    assert counter.freeze().as_dict() == {}
