"""The futures curve: the one rule of meaning, and the columns retained as typed and aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.market_data.futures_curve import futures_curve


def prices(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# The page's sample: six contracts of one index, the codes as the desk typed them, the prices in
# dollars per barrel.
CODES = ("M26", "N26", "Q26", "U26", "V26", "X26")
PRICES = prices(71.25, 71.4, 71.1, 70.85, 70.6, 70.4)


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_code_and_price_aligned_as_typed() -> None:
    curve = futures_curve(CODES, PRICES)
    assert curve.codes == CODES
    assert np.array_equal(curve.prices, PRICES)
    assert curve.prices.dtype == np.dtype("float64")


def test_a_one_contract_curve_is_a_curve() -> None:
    curve = futures_curve(CODES[:1], PRICES[:1])
    assert curve.codes == ("M26",)
    assert curve.prices.tolist() == [71.25]


# A price at or below zero, repeated codes and codes out of order: a reader's rules, written when
# the reader is. WTI's May 2020 contract settled at minus 37.63, so no sign is assumed.
def test_nothing_else_is_checked() -> None:
    codes = ("K20", "K20", "F20")
    curve = futures_curve(codes, prices(-37.63, 0.0, 20.0))
    assert curve.codes == codes
    assert curve.prices.tolist() == [-37.63, 0.0, 20.0]


# --- what is rejected, naming the count ---------------------------------------


@pytest.mark.parametrize(
    ("given", "message"),
    [
        (PRICES[:5], "price has 5 prices, expected 6, one per future_code"),
        (np.append(PRICES, 70.2), "price has 7 prices, expected 6, one per future_code"),
        (PRICES[:1], "price has 1 price, expected 6, one per future_code"),
    ],
    ids=["a price column one row short", "a price column one row long", "one price for six codes"],
)
def test_a_price_column_without_one_row_per_code_is_rejected(
    given: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        futures_curve(CODES, given)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


@given(count=st.integers(1, 400), data=st.data())
def test_any_columns_with_one_price_per_code_are_kept_aligned(
    count: int, data: st.DataObject
) -> None:
    codes = tuple(
        data.draw(st.lists(st.text(min_size=1, max_size=8), min_size=count, max_size=count))
    )
    given = np.array(
        data.draw(st.lists(st.floats(-1e6, 1e6), min_size=count, max_size=count)), dtype=np.float64
    )
    curve = futures_curve(codes, given)
    assert curve.codes == codes
    assert curve.prices.size == count
    assert np.array_equal(curve.prices, given)


# --- ownership ----------------------------------------------------------------


def test_the_curve_owns_its_prices() -> None:
    given = PRICES.copy()
    curve = futures_curve(CODES, given)
    given[0] = 0.0
    assert curve.prices[0] == 71.25
    assert not curve.prices.flags.writeable
    with pytest.raises(ValueError):
        curve.prices[0] = 0.0
