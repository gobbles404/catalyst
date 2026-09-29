"""What the kernel costs, counted: the exact work counts of each call, which of the package's own
functions run, which numpy C calls, and the peak of the Python heap. A ledger is exact and a
ceiling is the peak measured plus slack, as in the seam files beside this one. The sizes are a
hundred components, ten thousand terms, two thousand observations and forty marks, a book of a
hundred year-long averages; every number is synthetic."""

from collections.abc import Callable
from functools import partial

import numpy as np
from test_seam_allocation import SLACK, peak_bytes

from goosedove.instrumentation.work_counts import CELL, KERNEL, OBSERVATION, TERM, WorkCounter
from goosedove.valuation.binding import binding
from goosedove.valuation.kernel import amounts, compressed, compressed_amounts, dense
from goosedove.valuation.terms import terms

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
NumpyCalls = Callable[[Callable[[], object]], dict[str, int]]

R, T, OBS, M = 100, 10_000, 2_000, 40
RNG = np.random.default_rng(1)
CONSTANT = RNG.normal(size=R)
COMPONENT = RNG.integers(0, R, size=T).astype(np.intp)
OBSERVATION_OF = RNG.integers(0, OBS, size=T).astype(np.intp)
COEFFICIENT = RNG.normal(size=T)
IS_FIXED = np.arange(OBS) < OBS // 3
PRINTS = np.where(IS_FIXED, RNG.normal(size=OBS) + 50, np.nan)
MARK_OF = (np.arange(OBS) * M // OBS).astype(np.intp)
MARKS = RNG.normal(size=M) + 50

TERMS = terms(CONSTANT, COMPONENT, OBSERVATION_OF, COEFFICIENT)
BOUND = binding(IS_FIXED, PRINTS, MARK_OF, MARKS, WorkCounter())
VIEW = compressed(TERMS, BOUND, WorkCounter())


# --- the work counts, exact -----------------------------------------------------------------------


def test_a_binding_counts_one_observation_per_row() -> None:
    counter = WorkCounter()
    binding(IS_FIXED, PRINTS, MARK_OF, MARKS, counter)
    assert counter.freeze().as_dict() == {OBSERVATION: OBS}


def test_the_amounts_count_one_term_per_term_and_one_kernel_call() -> None:
    counter = WorkCounter()
    amounts(TERMS, BOUND, counter)
    assert counter.freeze().as_dict() == {KERNEL: 1, TERM: T}


def test_the_fold_counts_one_term_per_term_and_one_cell_per_cell_of_the_view() -> None:
    counter = WorkCounter()
    compressed(TERMS, BOUND, counter)
    assert counter.freeze().as_dict() == {KERNEL: 1, TERM: T, CELL: R * M}


# The view is components times marks whatever the terms: a thousand components over a thousand
# terms make a thousand cells against one mark and two million against two thousand, sixteen
# megabytes, and the cell count is what shows it. Measured 43,065 and 16,035,097 bytes on
# 2026-09-29.
def test_the_folds_cells_grow_with_the_marks_while_the_terms_stay_fixed() -> None:
    components, count, observations = 1_000, 1_000, 500
    rng = np.random.default_rng(2)
    made = terms(
        rng.normal(size=components),
        rng.integers(0, components, size=count).astype(np.intp),
        rng.integers(0, observations, size=count).astype(np.intp),
        rng.normal(size=count),
    )
    for marks, ceiling in ((1, 43_065), (2_000, 16_035_097)):
        bound = binding(
            np.zeros(observations, dtype=np.bool_),
            np.full(observations, np.nan),
            (np.arange(observations) * marks // observations).astype(np.intp),
            np.full(marks, 50.0),
            WorkCounter(),
        )
        counter = WorkCounter()
        compressed(made, bound, counter)
        assert counter.freeze().as_dict() == {KERNEL: 1, TERM: count, CELL: components * marks}
        assert peak_bytes(partial(compressed, made, bound, WorkCounter())) <= ceiling + SLACK


def test_a_tick_through_the_compressed_view_counts_one_cell_per_cell_zeros_included() -> None:
    counter = WorkCounter()
    compressed_amounts(VIEW, MARKS, counter)
    assert counter.freeze().as_dict() == {KERNEL: 1, CELL: R * M}


def test_the_dense_view_counts_one_cell_per_cell_made() -> None:
    counter = WorkCounter()
    dense(TERMS, BOUND, counter)
    assert counter.freeze().as_dict() == {KERNEL: 1, CELL: R * OBS}


# --- which functions run, and which numpy calls ---------------------------------------------------


# The rule is one comparison through two properties; the arithmetic is a gather by index, a
# multiply by operator and an add by operator, none of which cProfile sees, and one zeros, one
# reduce for the runs mask and one reduceat over the runs, which it does.
def test_the_amounts_check_one_rule_and_sum_the_runs_once(
    call_profile: CallProfile, numpy_calls: NumpyCalls
) -> None:
    counter = WorkCounter()

    def call() -> object:
        return amounts(TERMS, BOUND, counter)

    assert call_profile(call) == {
        "amounts": 1,
        "_covers": 1,
        "Binding.observations": 1,
        "Terms.components": 1,
        "WorkCounter.hit": 2,
    }
    assert numpy_calls(call) == {
        "ndarray.any": 1,
        "numpy.zeros": 1,
        "ufunc.reduce": 1,
        "ufunc.reduceat": 1,
    }


# The fold is two grouped sums: the cells, zeros with each unfixed term added in by add.at, and the
# constants by bincount, which cProfile names as a plain built-in and does not list; then one
# reshape of the cells and the two freezes.
def test_the_fold_checks_one_rule_and_folds_every_term_once(
    call_profile: CallProfile, numpy_calls: NumpyCalls
) -> None:
    counter = WorkCounter()

    def call() -> object:
        return compressed(TERMS, BOUND, counter)

    assert call_profile(call) == {
        "compressed": 1,
        "_covers": 1,
        "Binding.observations": 1,
        "Terms.components": 4,
        "WorkCounter.hit": 3,
    }
    assert numpy_calls(call) == {
        "numpy.zeros": 1,
        "ufunc.at": 1,
        "ndarray.reshape": 1,
        "ndarray.setflags": 2,
    }


# A tick is one rule and one multiply of the rectangle by the vector, by operator.
def test_a_tick_through_the_compressed_view_is_one_rule_and_one_multiply(
    call_profile: CallProfile, numpy_calls: NumpyCalls
) -> None:
    counter = WorkCounter()

    def call() -> object:
        return compressed_amounts(VIEW, MARKS, counter)

    assert call_profile(call) == {
        "compressed_amounts": 1,
        "Compressed.marks": 1,
        "WorkCounter.hit": 2,
    }
    assert numpy_calls(call) == {}


# The binding's five rules cost three reductions, and pricing costs one nonzero for the unfixed
# rows and four copies, the price and the three columns kept.
def test_a_binding_checks_its_rules_and_prices_in_one_gather(
    call_profile: CallProfile, numpy_calls: NumpyCalls
) -> None:
    counter = WorkCounter()

    def call() -> object:
        return binding(IS_FIXED, PRINTS, MARK_OF, MARKS, counter)

    assert call_profile(call) == {"binding": 1, "finite": 1, "kept": 3, "WorkCounter.hit": 1}
    assert numpy_calls(call) == {
        "ndarray.any": 3,
        "ndarray.copy": 4,
        "ndarray.nonzero": 1,
        "ndarray.ravel": 1,
        "ndarray.setflags": 4,
        "numpy.asanyarray": 1,
        "ufunc.reduce": 3,
    }


# --- the peak of the heap ---------------------------------------------------------------------


# One array the length of the terms, the gather multiplied in place, and a few the length of the
# components: the runs mask, the run starts, the sums and the result. Measured 83,204 bytes on
# 2026-09-29, down from 161,240 when the grouped sum was bincount, which copies the read-only
# component column.
def test_the_amounts_allocate_one_array_the_length_of_the_terms() -> None:
    counter = WorkCounter()
    assert peak_bytes(lambda: amounts(TERMS, BOUND, counter)) <= 8 * T + 32 * R + SLACK


# The fold gathers the live and the fixed terms apart, so its temporaries add up to about twice
# the terms in eight-byte numbers, plus the cells. Measured 181,600 bytes on 2026-09-29.
def test_the_fold_allocates_about_twice_the_terms_and_the_cells() -> None:
    counter = WorkCounter()
    assert peak_bytes(lambda: compressed(TERMS, BOUND, counter)) <= 181_600 + SLACK


# A tick makes the result and one temporary of the components' length. Measured 1,944 bytes on
# 2026-09-29.
def test_a_tick_through_the_compressed_view_allocates_two_arrays_of_the_components() -> None:
    counter = WorkCounter()
    assert peak_bytes(lambda: compressed_amounts(VIEW, MARKS, counter)) <= 16 * R + SLACK


# The rectangle and the scatter's few small temporaries, nothing the size of the terms. Measured
# 1,605,792 bytes on 2026-09-29.
def test_the_dense_view_allocates_the_rectangle_and_little_else() -> None:
    counter = WorkCounter()
    assert peak_bytes(lambda: dense(TERMS, BOUND, counter)) <= 1_605_792 + SLACK


# The price and the three columns kept, and the rule masks. Measured 60,094 bytes on 2026-09-29.
def test_a_binding_allocates_its_four_columns_and_its_masks() -> None:
    counter = WorkCounter()
    assert peak_bytes(lambda: binding(IS_FIXED, PRINTS, MARK_OF, MARKS, counter)) <= 60_094 + SLACK


# The grouping: the sort's order and the three grouped columns, four arrays of the terms' length,
# beside the constants' copy and the rule masks, once per booking. Measured 342,800 bytes on
# 2026-09-29.
def test_making_terms_allocates_the_order_and_the_grouped_columns_once() -> None:
    assert (
        peak_bytes(lambda: terms(CONSTANT, COMPONENT, OBSERVATION_OF, COEFFICIENT))
        <= 342_800 + SLACK
    )
