"""The market conventions: five codes kept as typed, and nothing checked yet."""

import dataclasses

from hypothesis import given
from hypothesis import strategies as st

from goosedove.market_definitions.market_conventions import market_conventions

# The page's sample: an index quoted in dollars per barrel, settled in dollars, its quantity a
# volume stated in barrels.
SAMPLE = ("USD", "BBL", "USD", "VOLUME", "BBL")


def test_the_sample_keeps_every_code_in_its_own_field() -> None:
    conventions = market_conventions(*SAMPLE)
    assert conventions.quote_currency_unit == "USD"
    assert conventions.quote_quantity_unit == "BBL"
    assert conventions.currency_unit == "USD"
    assert conventions.quantity_type == "VOLUME"
    assert conventions.quantity_unit == "BBL"


# Another case, a code nobody defined, a trailing space, words with a space in them: all kept
# as typed, because which codes are allowed is a task for later, noted at the builder.
def test_nothing_is_checked_yet() -> None:
    codes = ("usd", "bbl ", "GBP", "volume", "not a unit")
    assert dataclasses.astuple(market_conventions(*codes)) == codes


@given(codes=st.tuples(*(st.text(min_size=1, max_size=12) for _ in range(5))))
def test_any_five_texts_are_kept_in_order(codes: tuple[str, str, str, str, str]) -> None:
    assert dataclasses.astuple(market_conventions(*codes)) == codes
