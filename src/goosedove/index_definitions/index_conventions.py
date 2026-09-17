"""The index conventions of one index: the units its price is quoted in and per, the currency
it settles in, and what its quantity measures and is stated in.
docs/library/index-definitions/index-conventions.md is the page."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndexConventions:
    """Five codes, as the desk typed them: the currency unit and the quantity unit a price is
    quoted in, USD per BBL say; the currency unit the index settles in; and what a quantity
    measures, volume say, with the unit it is stated in, BBL."""

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
) -> IndexConventions:
    """The one way to make a IndexConventions: the five codes kept as typed.

    Nothing is checked yet, and that is a task for later, noted here rather than on a backlog:
    which codes are allowed, the unit codes and the categories of
    docs/library/globals/unit-conversions.md, and that a quantity unit belongs to its quantity
    type, is built when the first consumer needs the codes to mean something. Until then a
    code is text as typed, never trimmed or re-cased.
    """
    return IndexConventions(
        quote_currency_unit, quote_quantity_unit, currency_unit, quantity_type, quantity_unit
    )
