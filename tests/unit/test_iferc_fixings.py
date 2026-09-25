"""The IFERC fixings: two rules of meaning, and the codes and prices retained as typed."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.market_data.iferc_fixings import iferc_fixings


def prices(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# The page's sample: Waha IFERC, the first four months of 2026, the codes as the desk typed them
# and an illustrative index beside each.
CODES = ("F26", "G26", "H26", "J26")
PRICES = prices(1.85, 2.10, 1.95, 1.60)


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_code_and_every_price_aligned_as_typed() -> None:
    fixings = iferc_fixings(CODES, PRICES)
    assert fixings.codes == CODES
    assert np.array_equal(fixings.prices, PRICES)
    assert fixings.prices.dtype == np.dtype(np.float64)
    assert fixings.prices.ndim == 1


def test_the_fixings_of_one_month_are_a_series() -> None:
    fixings = iferc_fixings(CODES[:1], PRICES[:1])
    assert fixings.codes == ("F26",)
    assert np.array_equal(fixings.prices, prices(1.85))


def test_twelve_months_are_kept_in_their_order() -> None:
    codes = tuple(f"{letter}27" for letter in "FGHJKMNQUVXZ")
    given_prices = prices(*(2.0 + 0.1 * i for i in range(12)))
    fixings = iferc_fixings(codes, given_prices)
    assert fixings.codes == codes
    assert np.array_equal(fixings.prices, given_prices)


def test_a_price_below_zero_and_a_zero_are_kept_as_given() -> None:
    fixings = iferc_fixings(CODES[:3], prices(-1.25, 0.0, 1.95))
    assert np.array_equal(fixings.prices, prices(-1.25, 0.0, 1.95))


# Codes in either case, months out of a schedule's order, a month left out and a code no schedule
# lists: the history's rules, written when the history is. The fixings keep them as given.
def test_nothing_else_is_checked() -> None:
    codes = ("j26", "J26", "F26", "ZZZ")
    given_prices = prices(1.60, 1.61, 1.85, 9.99)
    fixings = iferc_fixings(codes, given_prices)
    assert fixings.codes == codes
    assert np.array_equal(fixings.prices, given_prices)


# --- what is rejected ---------------------------------------------------------


@pytest.mark.parametrize(
    ("codes", "given_prices", "message"),
    [
        (CODES, PRICES[:3], "price has 3 prices, expected 4, one per contract_code"),
        (
            CODES,
            np.append(PRICES, 1.5),
            "price has 5 prices, expected 4, one per contract_code",
        ),
        (CODES, PRICES[:1], "price has 1 price, expected 4, one per contract_code"),
        (CODES[:1], PRICES, "price has 4 prices, expected 1, one per contract_code"),
        (
            ("F26", "G26", "G26", "J26"),
            PRICES,
            "contract_code row 3 is 'G26', already given at row 2",
        ),
        (
            ("F26", "F26", "F26"),
            PRICES[:3],
            "contract_code row 2 is 'F26', already given at row 1",
        ),
        (
            ("F26", "G26", "G26"),
            PRICES,
            "price has 4 prices, expected 3, one per contract_code",
        ),
    ],
    ids=[
        "a price column one row short",
        "a price column one row long",
        "one price for four codes",
        "four prices for one code",
        "a code given twice",
        "a code given three times, the second named",
        "a code twice and the count wrong, the count named first",
    ],
)
def test_fixings_that_cannot_be_made_say_why(
    codes: tuple[str, ...], given_prices: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        iferc_fixings(codes, given_prices)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


@given(count=st.integers(1, 400), data=st.data())
def test_any_distinct_codes_with_one_price_each_are_kept_aligned(
    count: int, data: st.DataObject
) -> None:
    codes = tuple(
        data.draw(
            st.lists(st.text(min_size=1, max_size=8), min_size=count, max_size=count, unique=True)
        )
    )
    given_prices = np.array(
        data.draw(
            st.lists(
                st.floats(-100, 100, allow_nan=False, allow_infinity=False),
                min_size=count,
                max_size=count,
            )
        ),
        dtype=np.float64,
    )
    fixings = iferc_fixings(codes, given_prices)
    assert fixings.codes == codes
    assert fixings.prices.size == count
    assert np.array_equal(fixings.prices, given_prices)


# --- ownership ----------------------------------------------------------------


def test_the_fixings_own_their_prices_and_keep_the_codes_that_arrived() -> None:
    given_prices = PRICES.copy()
    fixings = iferc_fixings(CODES, given_prices)
    given_prices[0] = 9.99
    assert fixings.prices[0] == 1.85
    assert not fixings.prices.flags.writeable
    with pytest.raises(ValueError):
        fixings.prices[0] = 9.99
    assert fixings.codes is CODES
