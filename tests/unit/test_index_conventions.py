"""The index conventions: five codes checked against the unit tables, in order, and kept as
typed."""

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.index_conventions import IndexConventions, index_conventions

# The page's samples: WTI quoted in dollars per barrel, settled in dollars, its quantity a volume
# stated in barrels; gasoline quoted in cents per gallon and settled in dollars per barrel; gas
# in dollars per MMBTU; a metal quoted per pound and stated in tonnes.
SAMPLE = ("USD", "BBL", "USD", "VOLUME", "BBL")
GASOLINE = ("CENT", "GAL", "USD", "VOLUME", "BBL")
GAS = ("USD", "MMBTU", "USD", "ENERGY", "MMBTU")
METAL = ("USD", "LB", "USD", "MASS", "MT")
MEASURES = ("VOLUME", "MASS", "ENERGY")
CURRENCY_UNITS = ("USD", "CENT")
VOLUME = "expected a VOLUME unit, GAL, BBL, L or M3"
MASS = "expected a MASS unit, KG, LB, MT, ST, LT, G, OZT or CWT_US"
ENERGY = "expected an ENERGY unit, MMBTU, BTU, THERM, GJ, MWH or KWH"


def conventions(
    quote_currency_unit: str,
    quote_quantity_unit: str,
    currency_unit: str,
    quantity_type: str,
    quantity_unit: str,
) -> IndexConventions:
    return index_conventions(
        quote_currency_unit, quote_quantity_unit, currency_unit, quantity_type, quantity_unit, UNITS
    )


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_code_in_its_own_field() -> None:
    made = conventions(*SAMPLE)
    assert made.quote_currency_unit == "USD"
    assert made.quote_quantity_unit == "BBL"
    assert made.currency_unit == "USD"
    assert made.quantity_type == "VOLUME"
    assert made.quantity_unit == "BBL"


# Two units of one category, in either pair: the codes are kept, and nothing is converted.
def test_different_units_of_one_category_are_accepted() -> None:
    for codes in (GASOLINE, GAS, METAL):
        assert dataclasses.astuple(conventions(*codes)) == codes


def test_every_unit_of_a_category_and_every_currency_unit_is_accepted_in_either_slot() -> None:
    for name in MEASURES:
        units = list(UNITS.categories[name].sizes)
        reference = units[0]
        for unit in units:
            assert conventions("USD", unit, "USD", name, reference).quote_quantity_unit == unit
            assert conventions("USD", reference, "USD", name, unit).quantity_unit == unit
    for quoted in CURRENCY_UNITS:
        for settled in CURRENCY_UNITS:
            made = conventions(quoted, "BBL", settled, "VOLUME", "BBL")
            assert (made.quote_currency_unit, made.currency_unit) == (quoted, settled)


# --- what is rejected, naming the argument and the codes that would have done ------------


@pytest.mark.parametrize(
    ("codes", "message"),
    [
        (
            ("usd", "BBL", "USD", "VOLUME", "BBL"),
            "quote_currency_unit is 'usd', expected USD or CENT",
        ),
        (
            ("EUR", "BBL", "USD", "VOLUME", "BBL"),
            "quote_currency_unit is 'EUR', expected USD or CENT",
        ),
        (
            ("USD ", "BBL", "USD", "VOLUME", "BBL"),
            "quote_currency_unit is 'USD ', expected USD or CENT",
        ),
        (
            ("BBL", "BBL", "USD", "VOLUME", "BBL"),
            "quote_currency_unit is 'BBL', expected USD or CENT",
        ),
        (("USD", "BBL", "cent", "VOLUME", "BBL"), "currency_unit is 'cent', expected USD or CENT"),
        (("USD", "BBL", "GBP", "VOLUME", "BBL"), "currency_unit is 'GBP', expected USD or CENT"),
        (("USD", "BBL", " USD", "VOLUME", "BBL"), "currency_unit is ' USD', expected USD or CENT"),
        (
            ("USD", "BBL", "MMBTU", "VOLUME", "BBL"),
            "currency_unit is 'MMBTU', expected USD or CENT",
        ),
        (
            ("USD", "BBL", "USD", "Volume", "BBL"),
            "quantity_type is 'Volume', expected VOLUME, MASS or ENERGY",
        ),
        (
            ("USD", "BBL", "USD", "volume", "BBL"),
            "quantity_type is 'volume', expected VOLUME, MASS or ENERGY",
        ),
        (
            ("USD", "BBL", "USD", "weight", "BBL"),
            "quantity_type is 'weight', expected VOLUME, MASS or ENERGY",
        ),
        (
            ("USD", "BBL", "USD", "VOLUME ", "BBL"),
            "quantity_type is 'VOLUME ', expected VOLUME, MASS or ENERGY",
        ),
        (
            ("USD", "BBL", "USD", "USD", "BBL"),
            "quantity_type is 'USD', expected VOLUME, MASS or ENERGY",
        ),
        (("USD", "MMBTU", "USD", "VOLUME", "BBL"), f"quote_quantity_unit is 'MMBTU', {VOLUME}"),
        (("USD", "bbl", "USD", "VOLUME", "BBL"), f"quote_quantity_unit is 'bbl', {VOLUME}"),
        (("USD", "BBL ", "USD", "VOLUME", "BBL"), f"quote_quantity_unit is 'BBL ', {VOLUME}"),
        (("USD", "BARREL", "USD", "VOLUME", "BBL"), f"quote_quantity_unit is 'BARREL', {VOLUME}"),
        (("USD", "BBL", "USD", "VOLUME", "MT"), f"quantity_unit is 'MT', {VOLUME}"),
        (("USD", "BBL", "USD", "VOLUME", "bbl"), f"quantity_unit is 'bbl', {VOLUME}"),
        (("USD", "BBL", "USD", "VOLUME", "GALLON"), f"quantity_unit is 'GALLON', {VOLUME}"),
        (("USD", "BBL", "USD", "MASS", "MT"), f"quote_quantity_unit is 'BBL', {MASS}"),
        (("USD", "MT", "USD", "MASS", "kg"), f"quantity_unit is 'kg', {MASS}"),
        (("USD", "M3", "USD", "ENERGY", "MMBTU"), f"quote_quantity_unit is 'M3', {ENERGY}"),
        (("USD", "MMBTU", "USD", "ENERGY", "GAL"), f"quantity_unit is 'GAL', {ENERGY}"),
    ],
    ids=[
        "a quoted currency unit in another case",
        "a quoted currency unit nobody defined",
        "a quoted currency unit with a space",
        "a quantity unit where the quoted currency unit should be",
        "a settlement currency unit in another case",
        "a settlement currency unit nobody defined",
        "a settlement currency unit with a space",
        "a quantity unit where the settlement currency unit should be",
        "a quantity type in another case",
        "a quantity type in small letters, as it was typed before the codes took capitals",
        "a quantity type nobody defined",
        "a quantity type with a space",
        "USD where the quantity type should be",
        "a quoted quantity unit of another category",
        "a quoted quantity unit in another case",
        "a quoted quantity unit with a space",
        "a quoted quantity unit nobody defined",
        "a stated quantity unit of another category",
        "a stated quantity unit in another case",
        "a stated quantity unit nobody defined",
        "a volume unit quoted for a mass",
        "a mass unit in another case",
        "a volume unit quoted for an energy",
        "a volume unit stated for an energy",
    ],
)
def test_conventions_that_cannot_be_made_say_why(
    codes: tuple[str, str, str, str, str], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        conventions(*codes)
    assert str(failure.value) == message


# The two currency units before the quantity type, and the type before the quantity units, which
# it judges: with several wrong, the earlier in that order is named.
def test_the_rules_run_in_order_and_the_earlier_failure_is_named() -> None:
    for codes, named in (
        (("usd", "MMBTU", "EUR", "Volume", "MT"), "quote_currency_unit is 'usd'"),
        (("USD", "MMBTU", "EUR", "Volume", "MT"), "currency_unit is 'EUR'"),
        (("USD", "MMBTU", "USD", "Volume", "MT"), "quantity_type is 'Volume'"),
        (("USD", "MMBTU", "USD", "VOLUME", "MT"), "quote_quantity_unit is 'MMBTU'"),
    ):
        with pytest.raises(ValueError) as failure:
            conventions(*codes)
        assert str(failure.value).startswith(named)


# --- the general rules ----------------------------------------------------------


@given(data=st.data())
def test_any_two_units_of_a_category_and_any_two_currency_units_are_kept_as_typed(
    data: st.DataObject,
) -> None:
    name = data.draw(st.sampled_from(MEASURES))
    units = list(UNITS.categories[name].sizes)
    codes = (
        data.draw(st.sampled_from(CURRENCY_UNITS)),
        data.draw(st.sampled_from(units)),
        data.draw(st.sampled_from(CURRENCY_UNITS)),
        name,
        data.draw(st.sampled_from(units)),
    )
    assert dataclasses.astuple(conventions(*codes)) == codes


CODES = frozenset(UNITS.categories) | frozenset(
    unit for found in UNITS.categories.values() for unit in found.sizes
)


@given(
    codes=st.tuples(
        *(st.text(min_size=1, max_size=12).filter(lambda text: text not in CODES) for _ in range(5))
    )
)
def test_five_texts_none_of_which_is_a_code_fail_at_the_quoted_currency_unit(
    codes: tuple[str, str, str, str, str],
) -> None:
    with pytest.raises(ValueError) as failure:
        conventions(*codes)
    assert str(failure.value) == (f"quote_currency_unit is {codes[0]!r}, expected USD or CENT")
