"""The contract spec: four facts kept as given, each in its own field, and nothing checked yet."""

import dataclasses

from hypothesis import given
from hypothesis import strategies as st

from goosedove.market_definitions.contract_spec import contract_spec

# The page's sample: a contract of a thousand units a lot, with its two fees per lot.
SAMPLE = ("WTI", 1000, 3.0, 2.0)


def test_the_sample_keeps_every_fact_in_its_own_field() -> None:
    spec = contract_spec(*SAMPLE)
    assert spec.name == "WTI"
    assert spec.lot_size == 1000
    assert spec.brokerage_rate_per_lot == 3.0
    assert spec.clearing_rate_per_lot == 2.0


# A lot size of zero, a negative fee, a fee with a fraction, a name with spaces in it: kept as
# given, because what must hold is a task for later, noted at the builder.
def test_nothing_is_checked_yet() -> None:
    facts = ("Brent, dated", 0, -0.5, 2.125)
    assert dataclasses.astuple(contract_spec(*facts)) == facts


@given(
    name=st.text(min_size=1, max_size=12),
    lot_size=st.integers(-(2**53), 2**53),
    brokerage=st.floats(allow_nan=False),
    clearing=st.floats(allow_nan=False),
)
def test_any_four_facts_are_kept_in_order(
    name: str, lot_size: int, brokerage: float, clearing: float
) -> None:
    spec = contract_spec(name, lot_size, brokerage, clearing)
    assert dataclasses.astuple(spec) == (name, lot_size, brokerage, clearing)
