"""The IFERC fixings: four rules of meaning, the codes and prices retained as typed, and the index
kept."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.gas_daily_schedule import gas_daily_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.market_data.iferc_fixings import iferc_fixings


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def prices(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


CONVENTIONS = index_conventions("USD", "MMBTU", "USD", "energy", "MMBTU", UNITS)
SPECIFICATIONS = contract_specifications(
    ("ICE",), np.array([2500.0]), np.array([0.0]), np.array([0.0])
)


def an_index(schedule: object, name: str = "Waha IFERC") -> Index:
    """The index of that schedule with one set of conventions and specifications throughout,
    since nothing here reads either, and no holiday calendar, as an IFERC or a Gas Daily index
    has none."""
    return index(name, schedule, CONVENTIONS, SPECIFICATIONS, None)


# The page's sample: Waha IFERC, the first four months of 2026, the codes as the desk typed them
# and an illustrative index beside each, over the index of those four months, ICE's last trading
# days and Platts' publication days, January's index having printed on the 5th.
CODES = ("F26", "G26", "H26", "J26")
PRICES = prices(1.85, 2.10, 1.95, 1.60)
SCHEDULE = iferc_schedule(
    CODES,
    dates("2025-12-31", "2026-01-30", "2026-02-27", "2026-03-31"),
    dates("2026-01-05", "2026-02-02", "2026-03-02", "2026-04-01"),
)
INDEX = an_index(SCHEDULE)
FUTURES_INDEX = index(
    "WTI NYMEX",
    futures_schedule(("m26", "n26"), dates("2026-05-19", "2026-06-22"), None),
    CONVENTIONS,
    SPECIFICATIONS,
    holiday_calendar(dates("2026-05-25")),
)
GAS_DAILY_INDEX = an_index(
    gas_daily_schedule(("U26",), dates("2026-09-01"), dates("2026-09-30")), "Henry Hub Gas Daily"
)


def months_of(*codes: str) -> Index:
    """An IFERC index whose schedule holds exactly those months, published a day apart."""
    published = np.datetime64("2027-01-04", "D") + np.arange(len(codes)).astype("timedelta64[D]")
    return an_index(iferc_schedule(codes, published - np.timedelta64(1, "D"), published))


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_code_and_every_price_aligned_as_typed_and_the_index() -> None:
    fixings = iferc_fixings(CODES, PRICES, INDEX)
    assert fixings.codes == CODES
    assert np.array_equal(fixings.prices, PRICES)
    assert fixings.prices.dtype == np.dtype(np.float64)
    assert fixings.prices.ndim == 1
    assert fixings.index is INDEX


def test_the_fixings_of_one_month_are_a_series() -> None:
    fixings = iferc_fixings(CODES[:1], PRICES[:1], INDEX)
    assert fixings.codes == ("F26",)
    assert np.array_equal(fixings.prices, prices(1.85))


def test_twelve_months_are_kept_in_their_order() -> None:
    codes = tuple(f"{letter}27" for letter in "FGHJKMNQUVXZ")
    given_prices = prices(*(2.0 + 0.1 * i for i in range(12)))
    fixings = iferc_fixings(codes, given_prices, months_of(*codes))
    assert fixings.codes == codes
    assert np.array_equal(fixings.prices, given_prices)


def test_a_price_below_zero_and_a_zero_are_kept_as_given() -> None:
    fixings = iferc_fixings(CODES[:3], prices(-1.25, 0.0, 1.95), INDEX)
    assert np.array_equal(fixings.prices, prices(-1.25, 0.0, 1.95))


# Months out of the schedule's order and a month left out: whether a month's index has printed
# by a given day and whether every published month has its index are the history's rules. The
# fixings keep them as given.
def test_nothing_else_is_checked() -> None:
    codes = ("J26", "F26", "H26")
    given_prices = prices(1.60, 1.85, 1.95)
    fixings = iferc_fixings(codes, given_prices, INDEX)
    assert fixings.codes == codes
    assert np.array_equal(fixings.prices, given_prices)


# --- what is rejected ---------------------------------------------------------


# The kind is the first rule: a count the columns would refuse is not reached.
def test_an_index_of_another_kind_is_refused_before_the_columns_are_looked_at() -> None:
    for other, what in ((FUTURES_INDEX, "a futures index"), (GAS_DAILY_INDEX, "a Gas Daily index")):
        with pytest.raises(ValueError) as failure:
            iferc_fixings(CODES, PRICES[:3], other)
        assert str(failure.value) == f"index is {what}, expected an IFERC index"


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
            ("K26", "G26"),
            PRICES[:2],
            "contract_code row 1 is 'K26', expected one of the index's months",
        ),
        (
            ("F26", "G26", "K26"),
            PRICES[:3],
            "contract_code row 3 is 'K26', expected one of the index's months",
        ),
        (
            ("F26", "K26", "H26"),
            PRICES[:3],
            "contract_code row 2 is 'K26', expected one of the index's months",
        ),
        (
            ("f26",),
            PRICES[:1],
            "contract_code row 1 is 'f26', expected one of the index's months",
        ),
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
            ("F26", "K26", "F26"),
            PRICES[:3],
            "contract_code row 2 is 'K26', expected one of the index's months",
        ),
        (
            ("F26", "F26", "K26"),
            PRICES[:3],
            "contract_code row 2 is 'F26', already given at row 1",
        ),
        (
            ("F26", "G26", "G26"),
            PRICES,
            "price has 4 prices, expected 3, one per contract_code",
        ),
        (
            ("K26", "G26"),
            PRICES,
            "price has 4 prices, expected 2, one per contract_code",
        ),
    ],
    ids=[
        "a price column one row short",
        "a price column one row long",
        "one price for four codes",
        "four prices for one code",
        "a code the index does not hold, first",
        "a code the index does not hold, last",
        "a code the index does not hold, between",
        "a code in another case than the schedule's",
        "a code given twice",
        "a code given three times, the second named",
        "an unknown code before a repeat, the unknown named",
        "a repeat before an unknown code, the repeat named",
        "a code twice and the count wrong, the count named first",
        "an unknown code and the count wrong, the count named first",
    ],
)
def test_fixings_that_cannot_be_made_say_why(
    codes: tuple[str, ...], given_prices: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        iferc_fixings(codes, given_prices, INDEX)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


@given(count=st.integers(1, 400), data=st.data())
def test_any_distinct_codes_of_the_indexs_months_with_one_price_each_are_kept_aligned(
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
    over = months_of(*codes)
    fixings = iferc_fixings(codes, given_prices, over)
    assert fixings.codes == codes
    assert fixings.prices.size == count
    assert np.array_equal(fixings.prices, given_prices)
    assert fixings.index is over


# --- ownership ----------------------------------------------------------------


def test_the_fixings_own_their_prices_and_keep_the_codes_and_the_index_that_arrived() -> None:
    given_prices = PRICES.copy()
    fixings = iferc_fixings(CODES, given_prices, INDEX)
    given_prices[0] = 9.99
    assert fixings.prices[0] == 1.85
    assert not fixings.prices.flags.writeable
    with pytest.raises(ValueError):
        fixings.prices[0] = 9.99
    assert fixings.codes is CODES
    assert fixings.index is INDEX
