"""The contract specifications: each contract named once, each lot size whole and 1 or more, each
fee 0 or more, the rest kept as given, and the columns aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.index_definitions.contract_specifications import contract_specifications


def wholes(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


def numbers(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# The page's sample: gas traded as NYMEX lots and as ICE lots, with the fees per lot of each.
NAMES = ("NYMEX NG", "ICE NG")
LOTS = wholes(10000, 2500)
BROKERAGE = numbers(3.0, 0.75)
CLEARING = numbers(2.0, 0.5)


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_contract_aligned_in_its_own_columns() -> None:
    specifications = contract_specifications(NAMES, LOTS, BROKERAGE, CLEARING)
    assert specifications.names == NAMES
    assert specifications.lot_sizes.tolist() == [10000, 2500]
    assert specifications.lot_sizes.dtype == np.dtype("float64")
    assert specifications.brokerage_rates_per_lot.tolist() == [3.0, 0.75]
    assert specifications.clearing_rates_per_lot.tolist() == [2.0, 0.5]


def test_one_contract_is_a_set_of_specifications() -> None:
    specifications = contract_specifications(NAMES[:1], LOTS[:1], BROKERAGE[:1], CLEARING[:1])
    assert specifications.names == ("NYMEX NG",)
    assert specifications.lot_sizes.tolist() == [10000]


# A lot size of one, a fee of zero, a fee with a fraction, a name with spaces in it: kept as
# given, since nothing else is checked.
def test_a_lot_of_one_a_fee_of_zero_a_fee_with_a_fraction_and_a_name_with_spaces_are_kept() -> None:
    specifications = contract_specifications(
        ("Brent, dated", "WTI"), wholes(1, 5), numbers(0.0, 2.125), numbers(0.0, 1.0)
    )
    assert specifications.names == ("Brent, dated", "WTI")
    assert specifications.lot_sizes.tolist() == [1, 5]
    assert specifications.brokerage_rates_per_lot.tolist() == [0.0, 2.125]
    assert specifications.clearing_rates_per_lot.tolist() == [0.0, 1.0]


# --- what is rejected, naming the row -----------------------------------------


@pytest.mark.parametrize(
    ("names", "message"),
    [
        (("NYMEX NG", "NYMEX NG"), "name row 2 is 'NYMEX NG', already given at row 1"),
        (("ICE NG", "NYMEX NG", "ICE NG"), "name row 3 is 'ICE NG', already given at row 1"),
        (("a", "b", "b", "a"), "name row 3 is 'b', already given at row 2"),
    ],
    ids=["twice in a row", "the first name again", "the earlier repeat named"],
)
def test_a_contract_named_twice_is_rejected(names: tuple[str, ...], message: str) -> None:
    count = len(names)
    with pytest.raises(ValueError) as failure:
        contract_specifications(
            names, wholes(*([1000] * count)), numbers(*([3.0] * count)), numbers(*([2.0] * count))
        )
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("lots", "message"),
    [
        (wholes(10000, 2.5), "lot_size row 2 is 2.5, expected a whole number"),
        (wholes(0.5, 2500), "lot_size row 1 is 0.5, expected a whole number"),
        (wholes(10000, -2.25), "lot_size row 2 is -2.25, expected a whole number"),
    ],
    ids=["a fraction in the second row", "a fraction in the first", "a negative fraction"],
)
def test_a_lot_size_with_a_fraction_is_rejected(lots: NDArray[np.float64], message: str) -> None:
    with pytest.raises(ValueError) as failure:
        contract_specifications(NAMES, lots, BROKERAGE, CLEARING)
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("lots", "message"),
    [
        (wholes(0, 2500), "lot_size row 1 is 0.0, expected 1 or more"),
        (wholes(10000, 0), "lot_size row 2 is 0.0, expected 1 or more"),
        (wholes(10000, -0.0), "lot_size row 2 is -0.0, expected 1 or more"),
        (wholes(10000, -5), "lot_size row 2 is -5.0, expected 1 or more"),
        (wholes(0, -5), "lot_size row 1 is 0.0, expected 1 or more"),
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
        contract_specifications(NAMES, lots, BROKERAGE, CLEARING)
    assert str(failure.value) == message


# A negative lot size with a fraction is named as a fraction, a negative whole as below one: the
# fraction rule runs first, over the whole column.
def test_a_negative_fraction_is_a_fraction_and_a_negative_whole_is_below_one() -> None:
    with pytest.raises(ValueError, match=r"^lot_size row 1 is -2.25, expected a whole number$"):
        contract_specifications(NAMES, wholes(-2.25, 2500), BROKERAGE, CLEARING)
    with pytest.raises(ValueError, match=r"^lot_size row 1 is -2.0, expected 1 or more$"):
        contract_specifications(NAMES, wholes(-2, 2500), BROKERAGE, CLEARING)
    with pytest.raises(ValueError, match=r"^lot_size row 2 is 2.5, expected a whole number$"):
        contract_specifications(NAMES, wholes(0, 2.5), BROKERAGE, CLEARING)


@pytest.mark.parametrize(
    ("brokerage", "clearing", "message"),
    [
        (numbers(-0.5, 0.75), CLEARING, "brokerage_rate_per_lot row 1 is -0.5, expected 0 or more"),
        (
            numbers(3.0, -0.75),
            CLEARING,
            "brokerage_rate_per_lot row 2 is -0.75, expected 0 or more",
        ),
        (BROKERAGE, numbers(-2.0, 0.5), "clearing_rate_per_lot row 1 is -2.0, expected 0 or more"),
        (
            BROKERAGE,
            numbers(2.0, -0.25),
            "clearing_rate_per_lot row 2 is -0.25, expected 0 or more",
        ),
        (
            numbers(-1.0, -1.0),
            numbers(-1.0, -1.0),
            "brokerage_rate_per_lot row 1 is -1.0, expected 0 or more",
        ),
        (
            BROKERAGE,
            numbers(-2.0, -0.25),
            "clearing_rate_per_lot row 1 is -2.0, expected 0 or more",
        ),
    ],
    ids=[
        "a negative brokerage rate in the first row",
        "a negative brokerage rate in the last row",
        "a negative clearing rate in the first row",
        "a negative clearing rate in the last row",
        "every fee negative, brokerage named first",
        "two negative clearing rates, the first named",
    ],
)
def test_a_negative_fee_is_rejected_naming_the_column_and_the_row(
    brokerage: NDArray[np.float64], clearing: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        contract_specifications(NAMES, LOTS, brokerage, clearing)
    assert str(failure.value) == message


def test_the_lot_sizes_are_checked_before_the_fees() -> None:
    with pytest.raises(ValueError, match=r"^lot_size row 1 is 0.0, expected 1 or more$"):
        contract_specifications(NAMES, wholes(0, 2500), numbers(-1.0, -1.0), numbers(-1.0, -1.0))


# A whole double beyond 2^53 is a lot size a cell holds: it is kept as it is, and goes back out
# as it came. The one-contract form's line at 2^53 belonged to a Python int, not to a double.
def test_a_whole_double_beyond_two_to_the_fifty_three_is_kept() -> None:
    specifications = contract_specifications(NAMES, wholes(1e16, 1e20), BROKERAGE, CLEARING)
    assert specifications.lot_sizes.tolist() == [1e16, 1e20]


def test_the_names_are_checked_before_the_lot_sizes() -> None:
    with pytest.raises(ValueError, match=r"^name row 2 is 'NYMEX NG', already given at row 1$"):
        contract_specifications(("NYMEX NG", "NYMEX NG"), wholes(2.5, 2.5), BROKERAGE, CLEARING)


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
    fees = st.floats(min_value=0.0, allow_nan=False, allow_infinity=False)
    brokerage = np.array(
        data.draw(st.lists(fees, min_size=count, max_size=count)), dtype=np.float64
    )
    clearing = np.array(data.draw(st.lists(fees, min_size=count, max_size=count)), dtype=np.float64)
    specifications = contract_specifications(names, lots, brokerage, clearing)
    assert specifications.names == names
    assert np.array_equal(specifications.lot_sizes, lots)
    assert np.array_equal(specifications.brokerage_rates_per_lot, brokerage)
    assert np.array_equal(specifications.clearing_rates_per_lot, clearing)


# One bad row among good ones: the rule that fails names that row, wherever it is.
@given(count=st.integers(1, 40), data=st.data())
def test_one_row_below_the_line_is_named_wherever_it_is(count: int, data: st.DataObject) -> None:
    names = tuple(f"contract {i}" for i in range(count))
    row = data.draw(st.integers(0, count - 1))
    lots = np.full(count, 1000.0)
    brokerage = np.full(count, 3.0)
    clearing = np.full(count, 2.0)
    which = data.draw(
        st.sampled_from(("lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"))
    )
    if which == "lot_size":
        lots[row] = data.draw(st.integers(-(2**53), 0))
        bad, wanted = lots[row], "1 or more"
    elif which == "brokerage_rate_per_lot":
        brokerage[row] = data.draw(
            st.floats(max_value=-1e-9, allow_nan=False, allow_infinity=False)
        )
        bad, wanted = brokerage[row], "0 or more"
    else:
        clearing[row] = data.draw(st.floats(max_value=-1e-9, allow_nan=False, allow_infinity=False))
        bad, wanted = clearing[row], "0 or more"
    with pytest.raises(ValueError) as failure:
        contract_specifications(names, lots, brokerage, clearing)
    assert str(failure.value) == f"{which} row {row + 1} is {float(bad)!r}, expected {wanted}"


# --- ownership ----------------------------------------------------------------


def test_the_specifications_own_their_columns() -> None:
    lots, brokerage, clearing = LOTS.copy(), BROKERAGE.copy(), CLEARING.copy()
    specifications = contract_specifications(NAMES, lots, brokerage, clearing)
    lots[0], brokerage[0], clearing[0] = 1, 0.0, 0.0
    assert specifications.lot_sizes[0] == 10000
    assert specifications.brokerage_rates_per_lot[0] == 3.0
    assert specifications.clearing_rates_per_lot[0] == 2.0
    assert not specifications.lot_sizes.flags.writeable
    with pytest.raises(ValueError):
        specifications.clearing_rates_per_lot[0] = 0.0
