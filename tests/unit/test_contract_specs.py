"""The contract specs: each contract named once and each lot size whole, the rest kept as given, and
the columns aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.index_definitions.contract_specs import contract_specs


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
    specs = contract_specs(NAMES, LOTS, BROKERAGE, CLEARING)
    assert specs.names == NAMES
    assert specs.lot_sizes.tolist() == [10000, 2500]
    assert specs.lot_sizes.dtype == np.dtype("float64")
    assert specs.brokerage_rates_per_lot.tolist() == [3.0, 0.75]
    assert specs.clearing_rates_per_lot.tolist() == [2.0, 0.5]


def test_one_contract_is_a_set_of_specs() -> None:
    specs = contract_specs(NAMES[:1], LOTS[:1], BROKERAGE[:1], CLEARING[:1])
    assert specs.names == ("NYMEX NG",)
    assert specs.lot_sizes.tolist() == [10000]


# A lot size of zero, a negative fee, a fee with a fraction, a name with spaces in it: kept as
# given, because what must hold beyond each name once is a task for later, noted at the builder.
def test_nothing_else_is_checked_yet() -> None:
    specs = contract_specs(
        ("Brent, dated", "WTI"), wholes(0, -5), numbers(-0.5, 2.125), numbers(0.0, 1.0)
    )
    assert specs.names == ("Brent, dated", "WTI")
    assert specs.lot_sizes.tolist() == [0, -5]
    assert specs.brokerage_rates_per_lot.tolist() == [-0.5, 2.125]
    assert specs.clearing_rates_per_lot.tolist() == [0.0, 1.0]


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
        contract_specs(
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
        contract_specs(NAMES, lots, BROKERAGE, CLEARING)
    assert str(failure.value) == message


# A whole double beyond 2^53 is a lot size a cell holds: it is kept as it is, and goes back out
# as it came. The one-contract form's line at 2^53 belonged to a Python int, not to a double.
def test_a_whole_double_beyond_two_to_the_fifty_three_is_kept() -> None:
    specs = contract_specs(NAMES, wholes(1e16, 1e20), BROKERAGE, CLEARING)
    assert specs.lot_sizes.tolist() == [1e16, 1e20]


def test_the_names_are_checked_before_the_lot_sizes() -> None:
    with pytest.raises(ValueError, match=r"^name row 2 is 'NYMEX NG', already given at row 1$"):
        contract_specs(("NYMEX NG", "NYMEX NG"), wholes(2.5, 2.5), BROKERAGE, CLEARING)


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
        data.draw(st.lists(st.integers(-(2**53), 2**53), min_size=count, max_size=count)),
        dtype=np.float64,
    )
    brokerage = np.array(
        data.draw(st.lists(st.floats(allow_nan=False), min_size=count, max_size=count)),
        dtype=np.float64,
    )
    clearing = np.array(
        data.draw(st.lists(st.floats(allow_nan=False), min_size=count, max_size=count)),
        dtype=np.float64,
    )
    specs = contract_specs(names, lots, brokerage, clearing)
    assert specs.names == names
    assert np.array_equal(specs.lot_sizes, lots)
    assert np.array_equal(specs.brokerage_rates_per_lot, brokerage)
    assert np.array_equal(specs.clearing_rates_per_lot, clearing)


# --- ownership ----------------------------------------------------------------


def test_the_specs_own_their_columns() -> None:
    lots, brokerage, clearing = LOTS.copy(), BROKERAGE.copy(), CLEARING.copy()
    specs = contract_specs(NAMES, lots, brokerage, clearing)
    lots[0], brokerage[0], clearing[0] = 1, 0.0, 0.0
    assert specs.lot_sizes[0] == 10000
    assert specs.brokerage_rates_per_lot[0] == 3.0
    assert specs.clearing_rates_per_lot[0] == 2.0
    assert not specs.lot_sizes.flags.writeable
    with pytest.raises(ValueError):
        specs.clearing_rates_per_lot[0] = 0.0
