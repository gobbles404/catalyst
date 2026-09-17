"""The unit conversions: the shipped definitions, the rules on them, checked once where they are
authored, and the conversion between two units of one category."""

import math
from collections.abc import MutableMapping
from dataclasses import FrozenInstanceError
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.globals.unit_conversions import (
    UNITS,
    Category,
    UnitDefinition,
    category,
    unit_conversions,
)

# Relative: the page's relations are exact in decimal and not in binary, and a conversion is
# within a few units in the last place of its target, measured at about one.
TOLERANCE = 1e-15

Conversion = tuple[str, str, str]


def converted(quantity: float, which: str, from_unit: str, to_unit: str) -> float:
    """One quantity through convert, as a float."""
    return float(UNITS.convert(np.array([quantity]), which, from_unit, to_unit)[0])


def close(actual: float, target: float) -> bool:
    return math.isclose(actual, target, rel_tol=TOLERANCE, abs_tol=0.0)


# --- the collection ---------------------------------------------------------


def test_the_four_categories_each_with_their_own_reference_unit() -> None:
    assert [(c.name, c.reference_unit) for c in UNITS.categories.values()] == [
        ("volume", "GAL"),
        ("mass", "KG"),
        ("energy", "MMBTU"),
        ("usd", "USD"),
    ]
    assert all(c.sizes[c.reference_unit] == 1.0 for c in UNITS.categories.values())
    assert all(UNITS.category(name) is c for name, c in UNITS.categories.items())


def test_the_units_of_each_category_as_the_page_lists_them() -> None:
    assert list(UNITS.category("volume").sizes) == ["GAL", "BBL", "L", "M3"]
    assert list(UNITS.category("mass").sizes) == [
        "KG",
        "LB",
        "MT",
        "ST",
        "LT",
        "G",
        "OZT",
        "CWT_US",
    ]
    assert list(UNITS.category("energy").sizes) == ["MMBTU", "BTU", "THERM", "GJ", "MWH", "KWH"]
    assert list(UNITS.category("usd").sizes) == ["USD", "CENT"]


# --- the page's conversions -------------------------------------------------


def test_barrels_and_gallons_both_ways_and_a_unit_to_itself() -> None:
    assert converted(2.0, "volume", "BBL", "GAL") == 84.0
    assert converted(84.0, "volume", "GAL", "BBL") == 2.0
    assert converted(3.5, "volume", "GAL", "GAL") == 3.5
    assert UNITS.factor("volume", "BBL", "GAL") == 42.0
    assert UNITS.factor("volume", "GAL", "GAL") == 1.0


@pytest.mark.parametrize(
    ("quantity", "which", "from_unit", "to_unit", "target"),
    [
        (1.0, "volume", "GAL", "L", 3.785411784),
        (1.0, "volume", "M3", "L", 1000.0),
        (1.0, "mass", "MT", "KG", 1000.0),
        (1.0, "mass", "ST", "LB", 2000.0),
        (1.0, "mass", "LT", "LB", 2240.0),
        (1.0, "mass", "OZT", "G", 31.1034768),
        (1.0, "mass", "CWT_US", "LB", 100.0),
        (1.0, "energy", "MWH", "GJ", 3.6),
        (1.0, "energy", "MMBTU", "BTU", 1_000_000.0),
        (1.0, "energy", "MMBTU", "THERM", 10.0),
        (1.0, "energy", "MWH", "KWH", 1000.0),
        (1.0, "usd", "USD", "CENT", 100.0),
        (100.0, "usd", "CENT", "USD", 1.0),
        (250.0, "usd", "CENT", "USD", 2.5),
    ],
)
def test_the_pages_relations_hold_within_tolerance(
    quantity: float, which: str, from_unit: str, to_unit: str, target: float
) -> None:
    assert close(converted(quantity, which, from_unit, to_unit), target)


def test_zero_stays_zero_and_a_negative_quantity_keeps_its_sign() -> None:
    quantities = np.array([0.0, -2.0, -0.5])
    result = UNITS.convert(quantities, "volume", "BBL", "GAL")
    assert result.tolist() == [0.0, -84.0, -21.0]
    assert result.dtype == np.float64


def test_a_column_converts_in_one_go_and_the_column_is_left_as_it_was() -> None:
    quantities = np.array([1.0, 2.0, 3.0])
    result = UNITS.convert(quantities, "usd", "USD", "CENT")
    assert result.tolist() == [100.0, 200.0, 300.0]
    assert quantities.tolist() == [1.0, 2.0, 3.0]
    assert result is not quantities


# --- there and back, for every pair of every category -----------------------


@st.composite
def conversions(draw: st.DrawFn) -> Conversion:
    """A category and any two of its units, the same unit twice included."""
    found = draw(st.sampled_from(list(UNITS.categories.values())))
    units = list(found.sizes)
    return found.name, draw(st.sampled_from(units)), draw(st.sampled_from(units))


# Zero, and either sign of a quantity from 1e-15 to 1e15: with every factor between a millionth
# and a thousand, that keeps the arithmetic away from underflow, where a double loses digits.
quantities = st.one_of(
    st.just(0.0),
    st.tuples(st.sampled_from([-1.0, 1.0]), st.floats(1e-15, 1e15)).map(lambda p: p[0] * p[1]),
)


@given(conversions(), quantities)
def test_there_and_back_returns_the_quantity_within_tolerance(
    conversion: Conversion, quantity: float
) -> None:
    which, from_unit, to_unit = conversion
    there = converted(quantity, which, from_unit, to_unit)
    back = converted(there, which, to_unit, from_unit)
    assert math.isclose(back, quantity, rel_tol=1e-14, abs_tol=0.0)
    assert math.copysign(1.0, there) == math.copysign(1.0, quantity)


@given(conversions())
def test_the_factor_one_way_is_the_reciprocal_of_the_other(conversion: Conversion) -> None:
    which, from_unit, to_unit = conversion
    assert close(
        UNITS.factor(which, from_unit, to_unit) * UNITS.factor(which, to_unit, from_unit), 1
    )


# --- the rules on definitions, checked where they are authored ----------------


def rows(*triples: tuple[str, str, float]) -> tuple[UnitDefinition, ...]:
    return tuple(UnitDefinition(*triple) for triple in triples)


def test_a_unit_defined_twice_in_a_category_fails() -> None:
    with pytest.raises(ValueError, match=r"^energy defines BTU twice$"):
        category(
            "energy",
            "MMBTU",
            *rows(("MMBTU", "MMBTU", 1.0), ("BTU", "MMBTU", 1e-06), ("BTU", "MMBTU", 1e-06)),
        )


def test_a_category_without_its_reference_units_row_fails() -> None:
    with pytest.raises(
        ValueError, match=r"^volume reference GAL has no row, expected one with size 1$"
    ):
        category("volume", "GAL", *rows(("BBL", "GAL", 42.0)))


def test_a_row_referencing_another_unit_than_the_categorys_fails() -> None:
    with pytest.raises(ValueError, match=r"^mass row LB references GAL, expected KG$"):
        category("mass", "KG", *rows(("KG", "KG", 1.0), ("LB", "GAL", 0.45359237)))


def test_a_reference_row_whose_size_is_not_one_fails() -> None:
    with pytest.raises(ValueError, match=r"^volume reference GAL has size 42, expected 1$"):
        category("volume", "GAL", *rows(("GAL", "GAL", 42.0), ("BBL", "GAL", 1.0)))


@pytest.mark.parametrize(
    ("size", "shown"),
    [(0.0, "0"), (-1.5, "-1.5"), (math.nan, "nan"), (math.inf, "inf"), (-math.inf, "-inf")],
)
def test_a_size_that_is_not_finite_and_greater_than_zero_fails(size: float, shown: str) -> None:
    with pytest.raises(
        ValueError, match=rf"^volume row L has size {shown}, expected greater than 0$"
    ):
        category("volume", "GAL", *rows(("GAL", "GAL", 1.0), ("L", "GAL", size)))


def test_a_category_defined_twice_in_a_collection_fails() -> None:
    volume = category("volume", "GAL", *rows(("GAL", "GAL", 1.0)))
    with pytest.raises(ValueError, match=r"^volume is defined twice$"):
        unit_conversions(volume, volume)


# --- the rules on a request ---------------------------------------------------


@pytest.mark.parametrize("name", ["Volume", "VOLUME", "volume ", " volume", "weight", ""])
def test_a_category_is_matched_exactly_or_is_unknown(name: str) -> None:
    with pytest.raises(
        ValueError, match=rf"^unknown category {name!r}; categories are volume, mass, energy, usd$"
    ):
        UNITS.category(name)
    with pytest.raises(ValueError, match=rf"^unknown category {name!r};"):
        UNITS.factor(name, "BBL", "GAL")


@pytest.mark.parametrize("unit", ["GALLON", "gal", "Bbl", "BBL ", ""])
def test_a_unit_is_matched_exactly_within_its_category_or_is_unknown(unit: str) -> None:
    message = rf"^unknown unit {unit!r} in volume; units are GAL, BBL, L, M3$"
    with pytest.raises(ValueError, match=message):
        UNITS.category("volume").size_of(unit)
    with pytest.raises(ValueError, match=message):
        UNITS.factor("volume", unit, "BBL")
    with pytest.raises(ValueError, match=message):
        UNITS.factor("volume", "BBL", unit)


def test_the_first_unknown_unit_is_named() -> None:
    with pytest.raises(ValueError, match=r"^unknown unit 'GALLON' in volume;"):
        UNITS.factor("volume", "GALLON", "BARREL")
    with pytest.raises(ValueError, match=r"^unknown unit 'GALLON' in volume;"):
        UNITS.factor("volume", "GALLON", "MWH")


@pytest.mark.parametrize(
    ("which", "from_unit", "to_unit", "message"),
    [
        (
            "energy",
            "MWH",
            "BBL",
            "cannot convert MWH to BBL; energy and volume are different categories",
        ),
        (
            "volume",
            "MWH",
            "BBL",
            "cannot convert MWH to BBL; energy and volume are different categories",
        ),
        (
            "volume",
            "BBL",
            "MWH",
            "cannot convert BBL to MWH; volume and energy are different categories",
        ),
        (
            "mass",
            "USD",
            "GAL",
            "cannot convert USD to GAL; usd and volume are different categories",
        ),
    ],
)
def test_units_of_different_categories_are_refused(
    which: str, from_unit: str, to_unit: str, message: str
) -> None:
    with pytest.raises(ValueError, match=rf"^{message}$"):
        UNITS.factor(which, from_unit, to_unit)
    with pytest.raises(ValueError, match=rf"^{message}$"):
        UNITS.convert(np.array([1.0]), which, from_unit, to_unit)


# Two units of one category, asked for in another: not a conversion across categories but two
# units the category asked for does not have.
def test_two_units_of_one_other_category_are_unknown_in_the_one_asked_for() -> None:
    with pytest.raises(
        ValueError, match=r"^unknown unit 'MWH' in volume; units are GAL, BBL, L, M3$"
    ):
        UNITS.factor("volume", "MWH", "KWH")


# --- nothing changes ------------------------------------------------------------


def test_a_conversion_leaves_the_collection_and_every_definition_unchanged() -> None:
    before = {name: dict(c.sizes) for name, c in UNITS.categories.items()}
    UNITS.convert(np.array([1.0, 2.0]), "mass", "LB", "KG")
    UNITS.convert(np.array([1.0, 2.0]), "energy", "KWH", "MMBTU")
    assert {name: dict(c.sizes) for name, c in UNITS.categories.items()} == before
    assert before["volume"] == {
        "GAL": 1.0,
        "BBL": 42.0,
        "L": 0.26417205235814845,
        "M3": 264.17205235814845,
    }


def test_the_collection_and_its_categories_are_read_only() -> None:
    volume = UNITS.category("volume")
    with pytest.raises(TypeError):
        cast(MutableMapping[str, float], volume.sizes)["GAL"] = 2.0
    with pytest.raises(TypeError):
        cast(MutableMapping[str, Category], UNITS.categories)["weight"] = volume
    with pytest.raises(FrozenInstanceError):
        cast(Any, volume).reference_unit = "L"
