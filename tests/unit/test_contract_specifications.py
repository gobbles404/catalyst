"""The contract specifications: each word named once, each lot size whole and 1 or more, each lot
unit a quantity unit of the tables, each fee 0 or more, the rest kept as given, and the columns
aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import (
    ContractSpecifications,
    contract_specifications,
)


def wholes(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def numbers(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def specifications(
    names: tuple[str, ...],
    lots: NDArray[np.float64],
    units: tuple[str, ...],
    brokerage: NDArray[np.float64],
    clearing: NDArray[np.float64],
) -> ContractSpecifications:
    return contract_specifications(names, lots, units, brokerage, clearing, UNITS)


# The page's sample: gas dealt as NYMEX lots, as ICE lots and in MMBTU, the desk's three words for
# a quantity of it, with the fees per lot of each.
NAMES = ("lots", "ice_lots", "mmbtu")
LOTS = wholes(10000, 2500, 1)
LOT_UNITS = ("MMBTU", "MMBTU", "MMBTU")
BROKERAGE = numbers(3.0, 0.75, 0.0)
CLEARING = numbers(2.0, 0.5, 0.0)
QUANTITY_UNITS = tuple(
    unit for name, category in UNITS.categories.items() if name != "usd" for unit in category.sizes
)


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_word_aligned_in_its_own_columns() -> None:
    made = specifications(NAMES, LOTS, LOT_UNITS, BROKERAGE, CLEARING)
    assert made.names == NAMES
    assert made.lot_sizes.tolist() == [10000, 2500, 1]
    assert made.lot_sizes.dtype == np.dtype("float64")
    assert made.lot_units == LOT_UNITS
    assert made.brokerage_rates_per_lot.tolist() == [3.0, 0.75, 0.0]
    assert made.clearing_rates_per_lot.tolist() == [2.0, 0.5, 0.0]


def test_one_word_is_a_set_of_specifications() -> None:
    made = specifications(NAMES[:1], LOTS[:1], LOT_UNITS[:1], BROKERAGE[:1], CLEARING[:1])
    assert made.names == ("lots",)
    assert made.lot_sizes.tolist() == [10000]
    assert made.lot_units == ("MMBTU",)


# A lot size of one, a fee of zero, a fee with a fraction, a name with spaces in it, and units of
# two categories in one table: kept as given, since whether a unit is the index's measure is the
# index's rule and nothing else is checked.
def test_a_lot_of_one_a_zero_fee_a_fractional_fee_a_spaced_name_and_mixed_units_are_kept() -> None:
    made = specifications(
        ("Brent, dated", "WTI", "gas"),
        wholes(1, 5, 10000),
        ("BBL", "GAL", "MMBTU"),
        numbers(0.0, 2.125, 3.0),
        numbers(0.0, 1.0, 2.0),
    )
    assert made.names == ("Brent, dated", "WTI", "gas")
    assert made.lot_sizes.tolist() == [1, 5, 10000]
    assert made.lot_units == ("BBL", "GAL", "MMBTU")
    assert made.brokerage_rates_per_lot.tolist() == [0.0, 2.125, 3.0]
    assert made.clearing_rates_per_lot.tolist() == [0.0, 1.0, 2.0]


def test_every_quantity_unit_of_the_tables_is_a_lot_unit() -> None:
    count = len(QUANTITY_UNITS)
    made = specifications(
        tuple(f"word {i}" for i in range(count)),
        np.full(count, 1.0),
        QUANTITY_UNITS,
        np.zeros(count),
        np.zeros(count),
    )
    assert made.lot_units == QUANTITY_UNITS


# --- what is rejected, naming the row -----------------------------------------


@pytest.mark.parametrize(
    ("names", "message"),
    [
        (("lots", "lots"), "name row 2 is 'lots', already given at row 1"),
        (("ice_lots", "lots", "ice_lots"), "name row 3 is 'ice_lots', already given at row 1"),
        (("a", "b", "b", "a"), "name row 3 is 'b', already given at row 2"),
    ],
    ids=["twice in a row", "the first name again", "the earlier repeat named"],
)
def test_a_word_named_twice_is_rejected(names: tuple[str, ...], message: str) -> None:
    count = len(names)
    with pytest.raises(ValueError) as failure:
        specifications(
            names,
            wholes(*([1000] * count)),
            ("MMBTU",) * count,
            numbers(*([3.0] * count)),
            numbers(*([2.0] * count)),
        )
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("lots", "message"),
    [
        (wholes(10000, 2.5, 1), "lot_size row 2 is 2.5, expected a whole number"),
        (wholes(0.5, 2500, 1), "lot_size row 1 is 0.5, expected a whole number"),
        (wholes(10000, -2.25, 1), "lot_size row 2 is -2.25, expected a whole number"),
    ],
    ids=["a fraction in the second row", "a fraction in the first", "a negative fraction"],
)
def test_a_lot_size_with_a_fraction_is_rejected(lots: NDArray[np.float64], message: str) -> None:
    with pytest.raises(ValueError) as failure:
        specifications(NAMES, lots, LOT_UNITS, BROKERAGE, CLEARING)
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("lots", "message"),
    [
        (wholes(0, 2500, 1), "lot_size row 1 is 0.0, expected 1 or more"),
        (wholes(10000, 2500, 0), "lot_size row 3 is 0.0, expected 1 or more"),
        (wholes(10000, -0.0, 1), "lot_size row 2 is -0.0, expected 1 or more"),
        (wholes(10000, -5, 1), "lot_size row 2 is -5.0, expected 1 or more"),
        (wholes(0, -5, 1), "lot_size row 1 is 0.0, expected 1 or more"),
    ],
    ids=[
        "zero in the first row",
        "zero in the last row",
        "negative zero",
        "a negative whole",
        "two rows below one, the first named",
    ],
)
def test_a_lot_size_below_one_is_rejected(lots: NDArray[np.float64], message: str) -> None:
    with pytest.raises(ValueError) as failure:
        specifications(NAMES, lots, LOT_UNITS, BROKERAGE, CLEARING)
    assert str(failure.value) == message


# A negative lot size with a fraction is named as a fraction, a negative whole as below one: the
# fraction rule runs first, over the whole column.
def test_a_negative_fraction_is_a_fraction_and_a_negative_whole_is_below_one() -> None:
    with pytest.raises(ValueError, match=r"^lot_size row 1 is -2.25, expected a whole number$"):
        specifications(NAMES, wholes(-2.25, 2500, 1), LOT_UNITS, BROKERAGE, CLEARING)
    with pytest.raises(ValueError, match=r"^lot_size row 1 is -2.0, expected 1 or more$"):
        specifications(NAMES, wholes(-2, 2500, 1), LOT_UNITS, BROKERAGE, CLEARING)
    with pytest.raises(ValueError, match=r"^lot_size row 2 is 2.5, expected a whole number$"):
        specifications(NAMES, wholes(0, 2.5, 1), LOT_UNITS, BROKERAGE, CLEARING)


# A lot unit is a code of the tables' quantity categories, matched exactly: a currency unit, a
# code in another case, one with a space and one nobody defined are refused, naming the row.
@pytest.mark.parametrize(
    ("units", "message"),
    [
        (
            ("MMBTU", "USD", "MMBTU"),
            "lot_unit row 2 is 'USD', expected a volume, mass or energy unit",
        ),
        (
            ("mmbtu", "MMBTU", "MMBTU"),
            "lot_unit row 1 is 'mmbtu', expected a volume, mass or energy unit",
        ),
        (
            ("MMBTU", "MMBTU", "MMBTU "),
            "lot_unit row 3 is 'MMBTU ', expected a volume, mass or energy unit",
        ),
        (
            ("MMBTU", "MMBTU", "therms"),
            "lot_unit row 3 is 'therms', expected a volume, mass or energy unit",
        ),
        (
            ("CENT", "usd", "MMBTU"),
            "lot_unit row 1 is 'CENT', expected a volume, mass or energy unit",
        ),
    ],
    ids=[
        "a currency unit",
        "a unit in another case",
        "a unit with a space",
        "a unit nobody defined",
        "two bad units, the first named",
    ],
)
def test_a_lot_unit_that_is_no_quantity_unit_is_rejected(
    units: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        specifications(NAMES, LOTS, units, BROKERAGE, CLEARING)
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("brokerage", "clearing", "message"),
    [
        (
            numbers(-0.5, 0.75, 0.0),
            CLEARING,
            "brokerage_rate_per_lot row 1 is -0.5, expected 0 or more",
        ),
        (
            numbers(3.0, -0.75, 0.0),
            CLEARING,
            "brokerage_rate_per_lot row 2 is -0.75, expected 0 or more",
        ),
        (
            BROKERAGE,
            numbers(-2.0, 0.5, 0.0),
            "clearing_rate_per_lot row 1 is -2.0, expected 0 or more",
        ),
        (
            BROKERAGE,
            numbers(2.0, -0.25, 0.0),
            "clearing_rate_per_lot row 2 is -0.25, expected 0 or more",
        ),
        (
            numbers(-1.0, -1.0, -1.0),
            numbers(-1.0, -1.0, -1.0),
            "brokerage_rate_per_lot row 1 is -1.0, expected 0 or more",
        ),
        (
            BROKERAGE,
            numbers(-2.0, -0.25, 0.0),
            "clearing_rate_per_lot row 1 is -2.0, expected 0 or more",
        ),
    ],
    ids=[
        "a negative brokerage rate in the first row",
        "a negative brokerage rate in the second row",
        "a negative clearing rate in the first row",
        "a negative clearing rate in the second row",
        "every fee negative, brokerage named first",
        "two negative clearing rates, the first named",
    ],
)
def test_a_negative_fee_is_rejected_naming_the_column_and_the_row(
    brokerage: NDArray[np.float64], clearing: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        specifications(NAMES, LOTS, LOT_UNITS, brokerage, clearing)
    assert str(failure.value) == message


# The rules run in order: names, lot sizes, lot units, fees; with several wrong, the earlier is
# named.
def test_the_rules_run_in_order_and_the_earlier_failure_is_named() -> None:
    bad_fees = numbers(-1.0, -1.0, -1.0)
    with pytest.raises(ValueError, match=r"^name row 2 is 'lots', already given at row 1$"):
        specifications(
            ("lots", "lots", "mmbtu"), wholes(2.5, 0, 1), ("usd",) * 3, bad_fees, bad_fees
        )
    with pytest.raises(ValueError, match=r"^lot_size row 1 is 2.5, expected a whole number$"):
        specifications(NAMES, wholes(2.5, 0, 1), ("usd",) * 3, bad_fees, bad_fees)
    with pytest.raises(ValueError, match=r"^lot_size row 1 is 0.0, expected 1 or more$"):
        specifications(NAMES, wholes(0, 2500, 1), ("usd",) * 3, bad_fees, bad_fees)
    with pytest.raises(
        ValueError, match=r"^lot_unit row 1 is 'usd', expected a volume, mass or energy unit$"
    ):
        specifications(NAMES, LOTS, ("usd",) * 3, bad_fees, bad_fees)
    with pytest.raises(
        ValueError, match=r"^brokerage_rate_per_lot row 1 is -1.0, expected 0 or more$"
    ):
        specifications(NAMES, LOTS, LOT_UNITS, bad_fees, bad_fees)


# A whole double beyond 2^53 is a lot size a cell holds: it is kept as it is, and goes back out
# as it came. The one-contract form's line at 2^53 belonged to a Python int, not to a double.
def test_a_whole_double_beyond_two_to_the_fifty_three_is_kept() -> None:
    made = specifications(NAMES, wholes(1e16, 1e20, 1), LOT_UNITS, BROKERAGE, CLEARING)
    assert made.lot_sizes.tolist() == [1e16, 1e20, 1]


# --- the general rule ---------------------------------------------------------


@given(count=st.integers(1, 40), data=st.data())
def test_any_distinct_names_and_their_columns_are_kept_aligned(
    count: int, data: st.DataObject
) -> None:
    names = tuple(
        data.draw(
            st.lists(st.text(min_size=1, max_size=12), min_size=count, max_size=count, unique=True)
        )
    )
    lots = np.array(
        data.draw(st.lists(st.integers(1, 2**53), min_size=count, max_size=count)),
        dtype=np.float64,
    )
    units = tuple(
        data.draw(st.lists(st.sampled_from(QUANTITY_UNITS), min_size=count, max_size=count))
    )
    fees = st.floats(min_value=0.0, allow_nan=False, allow_infinity=False)
    brokerage = np.array(
        data.draw(st.lists(fees, min_size=count, max_size=count)), dtype=np.float64
    )
    clearing = np.array(data.draw(st.lists(fees, min_size=count, max_size=count)), dtype=np.float64)
    made = specifications(names, lots, units, brokerage, clearing)
    assert made.names == names
    assert np.array_equal(made.lot_sizes, lots)
    assert made.lot_units == units
    assert np.array_equal(made.brokerage_rates_per_lot, brokerage)
    assert np.array_equal(made.clearing_rates_per_lot, clearing)


# One bad row among good ones: the rule that fails names that row, wherever it is.
@given(count=st.integers(1, 40), data=st.data())
def test_one_row_below_the_line_is_named_wherever_it_is(count: int, data: st.DataObject) -> None:
    names = tuple(f"word {i}" for i in range(count))
    row = data.draw(st.integers(0, count - 1))
    lots = np.full(count, 1000.0)
    units = ["MMBTU"] * count
    brokerage = np.full(count, 3.0)
    clearing = np.full(count, 2.0)
    which = data.draw(
        st.sampled_from(("lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"))
    )
    if which == "lot_size":
        lots[row] = data.draw(st.integers(-(2**53), 0))
        bad, wanted = repr(float(lots[row])), "1 or more"
    elif which == "lot_unit":
        units[row] = data.draw(
            st.text(min_size=1, max_size=8).filter(lambda text: text not in QUANTITY_UNITS)
        )
        bad, wanted = repr(units[row]), "a volume, mass or energy unit"
    elif which == "brokerage_rate_per_lot":
        brokerage[row] = data.draw(
            st.floats(max_value=-1e-9, allow_nan=False, allow_infinity=False)
        )
        bad, wanted = repr(float(brokerage[row])), "0 or more"
    else:
        clearing[row] = data.draw(st.floats(max_value=-1e-9, allow_nan=False, allow_infinity=False))
        bad, wanted = repr(float(clearing[row])), "0 or more"
    with pytest.raises(ValueError) as failure:
        specifications(names, lots, tuple(units), brokerage, clearing)
    assert str(failure.value) == f"{which} row {row + 1} is {bad}, expected {wanted}"


# --- ownership ----------------------------------------------------------------


def test_the_specifications_own_their_columns() -> None:
    lots, brokerage, clearing = LOTS.copy(), BROKERAGE.copy(), CLEARING.copy()
    made = specifications(NAMES, lots, LOT_UNITS, brokerage, clearing)
    lots[0], brokerage[0], clearing[0] = 1, 0.0, 0.0
    assert made.lot_sizes[0] == 10000
    assert made.brokerage_rates_per_lot[0] == 3.0
    assert made.clearing_rates_per_lot[0] == 2.0
    assert not made.lot_sizes.flags.writeable
    with pytest.raises(ValueError):
        made.clearing_rates_per_lot[0] = 0.0
    assert made.lot_units is LOT_UNITS
