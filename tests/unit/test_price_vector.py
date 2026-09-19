"""The price vector: the column retained as given, owned and frozen, and nothing checked."""

import dataclasses

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.market_data.price_vector import price_vector

# The page's sample: four prices, a zero and a negative among them and the first repeated.
PRICES = np.array([74.25, 0.0, -0.5, 74.25])


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_price_in_its_place() -> None:
    made = price_vector(PRICES)
    assert made.prices.tolist() == [74.25, 0.0, -0.5, 74.25]
    assert made.prices.dtype == np.dtype(np.float64)
    assert made.prices.ndim == 1
    assert made.prices.shape == (4,)


def test_one_price_is_a_vector_of_one() -> None:
    made = price_vector(PRICES[:1])
    assert made.prices.tolist() == [74.25]
    assert made.prices.shape == (1,)


# Nothing is sorted, rounded, deduplicated, padded, cut or bounded: a zero, a negative price and
# a repeat are prices, and the order is the column's.
def test_nothing_else_is_checked() -> None:
    given_ = np.array([-37.63, 0.0, 0.0, 1e6, 74.251, -37.63])
    made = price_vector(given_)
    assert made.prices.tolist() == given_.tolist()


# A caller in Python may hand whole numbers or narrower floats; the vector holds float64 and the
# values as given, never a smaller dtype.
@pytest.mark.parametrize(
    "given_",
    [np.array([74, 0, -1]), np.array([74.25, 0.0, -0.5], dtype=np.float32)],
    ids=["whole numbers", "narrower floats"],
)
def test_the_vector_holds_float64_whatever_arrived(given_: np.ndarray) -> None:
    made = price_vector(given_)
    assert made.prices.dtype == np.dtype(np.float64)
    assert made.prices.tolist() == [float(x) for x in given_.tolist()]


# --- the general rule ---------------------------------------------------------


@given(
    values=st.lists(
        st.floats(allow_nan=False, allow_infinity=False, width=64), min_size=1, max_size=400
    )
)
def test_any_column_of_prices_is_kept_as_given(values: list[float]) -> None:
    given_ = np.array(values, dtype=np.float64)
    made = price_vector(given_)
    assert made.prices.shape == (len(values),)
    assert np.array_equal(made.prices, given_)
    assert made.prices.dtype == np.dtype(np.float64)


# --- ownership ----------------------------------------------------------------


def test_the_vector_owns_a_copy_and_a_change_to_the_input_leaves_it() -> None:
    given_ = PRICES.copy()
    made = price_vector(given_)
    assert not np.shares_memory(made.prices, given_)
    given_[0] = 99.0
    assert made.prices.tolist() == [74.25, 0.0, -0.5, 74.25]
    assert given_.tolist() == [99.0, 0.0, -0.5, 74.25]


def test_the_record_and_its_prices_refuse_writes() -> None:
    made = price_vector(PRICES)
    assert not made.prices.flags.writeable
    with pytest.raises(ValueError):
        made.prices[0] = 0.0
    field = "prices"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(made, field, PRICES)


# A later vector, over the same prices or a different number of them, is its own object with
# its own storage, and the earlier one reads as it did.
def test_a_later_vector_leaves_the_earlier_one() -> None:
    first = price_vector(PRICES)
    same = price_vector(PRICES)
    longer = price_vector(np.array([74.25, 0.0, -0.5, 74.25, 75.0]))
    assert same is not first
    assert not np.shares_memory(same.prices, first.prices)
    assert same.prices.tolist() == first.prices.tolist() == [74.25, 0.0, -0.5, 74.25]
    assert longer.prices.shape == (5,)
    assert first.prices.shape == (4,)
