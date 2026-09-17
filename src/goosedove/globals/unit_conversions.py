"""The library's fixed unit definitions and the conversion between them: four categories,
volume, mass, energy and usd, each a reference unit and the size of every unit of it in that
reference unit. docs/library/globals/unit-conversions.md is the page.

Nothing here crosses the seam: no worksheet function, no handle, no workbook table. The
definitions are authored at the foot of this module, checked once when it is imported, and shared
by reference as UNITS, which a calculation takes as a parameter and never reads for itself."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Final

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    """One row of the page's tables: 1 unit = size_in_reference_unit reference_unit, so BBL, GAL,
    42 says a barrel is 42 gallons."""

    unit: str
    reference_unit: str
    size_in_reference_unit: float


@dataclass(frozen=True, slots=True)
class Category:
    """One category as checked: its name, its reference unit, and the size of each of its units
    in that reference unit, in the order they were authored, read-only."""

    name: str
    reference_unit: str
    sizes: Mapping[str, float]

    def size_of(self, unit: str) -> float:
        """How many reference units one unit is, the unit being one of this category's, matched
        exactly: a code is an identifier, never trimmed or re-cased."""
        size = self.sizes.get(unit)
        if size is None:
            raise _unknown_unit(self, unit)
        return size


@dataclass(frozen=True, slots=True)
class UnitConversions:
    """The collection: every category by name, in the order authored, read-only. Internal code
    that converts takes one reference to it and shares the definitions; nothing copies them."""

    categories: Mapping[str, Category]

    def category(self, name: str) -> Category:
        """The category of that name, matched exactly and case-sensitively."""
        found = self.categories.get(name)
        if found is None:
            raise ValueError(
                f"unknown category {name!r}; categories are {', '.join(self.categories)}"
            )
        return found

    def factor(self, category: str, from_unit: str, to_unit: str) -> float:
        """The multiplier that restates a quantity in from_unit as one in to_unit, both units of
        the category: size_from / size_to, so BBL to GAL in volume is 42 and GAL to BBL is 1 / 42.

        A unit of another category is refused as a conversion across categories, which needs a
        density or heat content the tables do not carry; a unit of no category is unknown in
        the one asked for, the first such unit named.
        """
        found = self.category(category)
        from_size, to_size = found.sizes.get(from_unit), found.sizes.get(to_unit)
        if from_size is None or to_size is None:
            from_home, to_home = self._home_of(from_unit), self._home_of(to_unit)
            if from_home is not None and to_home is not None and from_home is not to_home:
                raise ValueError(
                    f"cannot convert {from_unit} to {to_unit}; "
                    f"{from_home.name} and {to_home.name} are different categories"
                )
            raise _unknown_unit(found, from_unit if from_size is None else to_unit)
        return from_size / to_size

    def convert(
        self, quantities: NDArray[np.float64], category: str, from_unit: str, to_unit: str
    ) -> NDArray[np.float64]:
        """Every quantity, stated in from_unit, restated in to_unit: quantity * size_from /
        size_to, the page's formula, the factor formed once and one multiplication over the
        array. The factor is positive, so zero stays zero and a negative quantity keeps its sign.
        """
        return quantities * self.factor(category, from_unit, to_unit)

    def _home_of(self, unit: str) -> Category | None:
        """The category that defines the unit, if one does: four lookups on the failing path,
        to say which two categories a refused conversion was between."""
        for found in self.categories.values():
            if unit in found.sizes:
                return found
        return None


def _unknown_unit(category: Category, unit: str) -> ValueError:
    """The one message for a unit the category does not have, raised by whoever looked."""
    return ValueError(
        f"unknown unit {unit!r} in {category.name}; units are {', '.join(category.sizes)}"
    )


def _size(value: float) -> str:
    """A size in the page's words: 42, not 42.0, and 0.5, nan or inf as they are."""
    return repr(int(value)) if value.is_integer() else repr(value)


def category(name: str, reference_unit: str, *definitions: UnitDefinition) -> Category:
    """The one way to make a Category: the page's rules on the definitions, checked once, here,
    where the definitions are authored, and never on a conversion.

    Each unit is defined once; every row's reference unit is the category's; every size is
    finite and greater than zero; and the reference unit has a row of its own, of size exactly
    1. Rows are named by their unit, as the page's tables show them.
    """
    sizes: dict[str, float] = {}
    for row in definitions:
        if row.unit in sizes:
            raise ValueError(f"{name} defines {row.unit} twice")
        if row.reference_unit != reference_unit:
            raise ValueError(
                f"{name} row {row.unit} references {row.reference_unit}, expected {reference_unit}"
            )
        size = row.size_in_reference_unit
        if not (isfinite(size) and size > 0.0):
            raise ValueError(
                f"{name} row {row.unit} has size {_size(size)}, expected greater than 0"
            )
        sizes[row.unit] = size
    reference_size = sizes.get(reference_unit)
    if reference_size is None:
        raise ValueError(f"{name} reference {reference_unit} has no row, expected one with size 1")
    if reference_size != 1.0:
        raise ValueError(
            f"{name} reference {reference_unit} has size {_size(reference_size)}, expected 1"
        )
    return Category(name, reference_unit, MappingProxyType(sizes))


def unit_conversions(*categories: Category) -> UnitConversions:
    """The one way to make a UnitConversions: the categories by name, each checked as it was
    built, and no name twice, since the collection is keyed by it."""
    by_name: dict[str, Category] = {}
    for found in categories:
        if found.name in by_name:
            raise ValueError(f"{found.name} is defined twice")
        by_name[found.name] = found
    return UnitConversions(MappingProxyType(by_name))


# The shipped definitions, the page's tables row for row, with the full names beside the codes,
# which the page says must accompany them. Sources are cited on the page.
UNITS: Final = unit_conversions(
    # GAL the U.S. liquid gallon; BBL the petroleum barrel, 42 U.S. gallons; L the litre and M3
    # the cubic metre, at 3.785411784 litres per U.S. gallon.
    category(
        "volume",
        "GAL",
        UnitDefinition("GAL", "GAL", 1.0),
        UnitDefinition("BBL", "GAL", 42.0),
        UnitDefinition("L", "GAL", 0.26417205235814845),
        UnitDefinition("M3", "GAL", 264.17205235814845),
    ),
    # KG the kilogram; LB the international avoirdupois pound; MT the metric tonne; ST the short
    # ton, 2000 lb; LT the long ton, 2240 lb; G the gram, for precious metals quoted in grams;
    # OZT the troy ounce, 31.1034768 g, for gold, silver, platinum and palladium, and not the
    # avoirdupois ounce; CWT_US the U.S. hundredweight, 100 lb, for rice and dairy, and not the
    # 112 lb imperial hundredweight.
    category(
        "mass",
        "KG",
        UnitDefinition("KG", "KG", 1.0),
        UnitDefinition("LB", "KG", 0.45359237),
        UnitDefinition("MT", "KG", 1000.0),
        UnitDefinition("ST", "KG", 907.18474),
        UnitDefinition("LT", "KG", 1016.0469088),
        UnitDefinition("G", "KG", 0.001),
        UnitDefinition("OZT", "KG", 0.0311034768),
        UnitDefinition("CWT_US", "KG", 45.359237),
    ),
    # MMBTU one million International Table Btu, the Btu being exactly 1055.05585262 joules; BTU
    # that Btu; THERM exactly 100,000 Btu; GJ the gigajoule, 1e9 joules; MWH the megawatt hour,
    # 3.6e9 joules; KWH the kilowatt hour, 3.6e6 joules.
    category(
        "energy",
        "MMBTU",
        UnitDefinition("MMBTU", "MMBTU", 1.0),
        UnitDefinition("BTU", "MMBTU", 1e-06),
        UnitDefinition("THERM", "MMBTU", 0.1),
        UnitDefinition("GJ", "MMBTU", 0.9478171203133172),
        UnitDefinition("MWH", "MMBTU", 3.4121416331279417),
        UnitDefinition("KWH", "MMBTU", 0.0034121416331279417),
    ),
    # USD the U.S. dollar and CENT its cent: a scale of dollar amounts, never a currency
    # conversion.
    category(
        "usd",
        "USD",
        UnitDefinition("USD", "USD", 1.0),
        UnitDefinition("CENT", "USD", 0.01),
    ),
)
