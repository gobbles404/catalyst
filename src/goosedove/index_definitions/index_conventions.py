"""The index conventions of one index: the units its price is quoted in and per, the currency
it settles in, and what its quantity measures and is stated in, five codes checked against the
library's unit tables. docs/library/index-definitions/index-conventions.md is the page."""

from collections.abc import Iterable
from dataclasses import dataclass

from goosedove.globals.unit_conversions import UnitConversions

# The tables' one currency category: its units are the currency units an index is quoted and
# settled in, and it is not a category a quantity measures. Another currency is another category
# there, when one arrives.
CURRENCY = "USD"


@dataclass(frozen=True, slots=True)
class IndexConventions:
    """Five codes, as the desk typed them and as the unit tables spell them: the currency unit and
    the quantity unit a price is quoted in, USD per BBL say; the currency unit the index settles
    in; and what a quantity measures, VOLUME say, with the unit it is stated in, BBL, the two
    quantity units both of that category."""

    quote_currency_unit: str
    quote_quantity_unit: str
    currency_unit: str
    quantity_type: str
    quantity_unit: str


def index_conventions(
    quote_currency_unit: str,
    quote_quantity_unit: str,
    currency_unit: str,
    quantity_type: str,
    quantity_unit: str,
    units: UnitConversions,
) -> IndexConventions:
    """The one way to make an IndexConventions: five rules of meaning against the unit tables,
    checked once, in this order, the first failure being the message.

    The two currency units first, which depend on nothing else: each is a unit of the tables'
    currency category, USD or CENT. Then the quantity type, a category a quantity can measure,
    VOLUME, MASS or ENERGY, in capitals like every other code, and not the currency category,
    which scales money. Then the two
    quantity units, judged by it: each a unit of that category, so that a price quoted per gallon
    and a quantity stated in barrels are two units of one measure, and the two may differ, as may
    the two currency units, so long as each pair is of one category. Each code is matched
    exactly, spelling and case as typed, never trimmed or re-cased, since a code is an identifier
    and not prose; a message names the argument, what arrived and the codes that would have done,
    in the tables' order. Nothing is converted or computed: the factor between two units is the
    instrument's to look up once when it is made, and the record holds the five codes and nothing
    derived. The tables are the collection passed in, read by key and never copied.
    """
    money = units.categories[CURRENCY].sizes
    if quote_currency_unit not in money:
        raise ValueError(
            f"quote_currency_unit is {quote_currency_unit!r}, expected {listed(money)}"
        )
    if currency_unit not in money:
        raise ValueError(f"currency_unit is {currency_unit!r}, expected {listed(money)}")
    measures = measures_of(units)
    if quantity_type not in measures:
        raise ValueError(f"quantity_type is {quantity_type!r}, expected {listed(measures)}")
    measure = units.categories[quantity_type].sizes
    for argument, code in (
        ("quote_quantity_unit", quote_quantity_unit),
        ("quantity_unit", quantity_unit),
    ):
        if code not in measure:
            raise ValueError(
                f"{argument} is {code!r}, expected {a_unit_of(quantity_type, measure)}"
            )
    return IndexConventions(
        quote_currency_unit, quote_quantity_unit, currency_unit, quantity_type, quantity_unit
    )


def listed(codes: Iterable[str]) -> str:
    """The codes a message offers, in the tables' order: USD or CENT; GAL, BBL, L or M3."""
    *head, last = codes
    return f"{', '.join(head)} or {last}" if head else last


def measures_of(units: UnitConversions) -> list[str]:
    """The categories a quantity can measure, VOLUME, MASS and ENERGY: every category but the
    currency's, in the tables' order."""
    return [name for name in units.categories if name != CURRENCY]


def a_unit_of(quantity_type: str, measure: Iterable[str]) -> str:
    """What a message wants of a unit of one category: `a VOLUME unit, GAL, BBL, L or M3`, or
    `an ENERGY unit, MMBTU, BTU, THERM, GJ, MWH or KWH`."""
    article = "an" if quantity_type[0] in "AEIOU" else "a"
    return f"{article} {quantity_type} unit, {listed(measure)}"
