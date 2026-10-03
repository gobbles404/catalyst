"""Static futures trades: one and many rows keep the same meaning and representation."""

import dataclasses

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.index import index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.index_definitions.kind import Kind
from goosedove.trades.futures_trades import futures_trades

NG = index(
    "Henry Hub NYMEX",
    futures_schedule(
        ("Z26", "F27"), np.array(["2026-11-25", "2026-12-29"], dtype="datetime64[D]"), None
    ),
    index_conventions("USD", "MMBTU", "USD", "energy", "MMBTU", UNITS),
    contract_specifications(("NYMEX NG",), np.array([10000.0]), np.array([0.0]), np.array([0.0])),
    holiday_calendar(np.array(["2026-11-26", "2026-12-25"], dtype="datetime64[D]")),
)
IDS = ("NG-001", "NG-002", "NG-003", "NG-004")
DATES = np.array(["2026-09-24", "2026-09-24", "2026-09-25", "2026-09-25"], dtype="datetime64[D]")
CODES = ("Z26", "Z26", "F27", "F27")
LOTS = np.array([10.0, -4.0, 7.0, -12.0])
PRICES = np.array([3.100, 3.150, 3.400, 3.350])


def test_the_sample_keeps_each_deal_and_binds_shared_facts_once() -> None:
    made = futures_trades(NG, "NYMEX NG", IDS, DATES, CODES, LOTS, PRICES)
    assert made.index is NG
    assert made.specification_position == 0
    assert made.index.specifications.lot_sizes[made.specification_position] == 10000.0
    assert made.trade_ids is IDS
    assert made.contract_codes is CODES
    assert made.trade_dates.tolist() == DATES.tolist()
    assert made.signed_lots.tolist() == [10.0, -4.0, 7.0, -12.0]
    assert made.trade_prices.tolist() == [3.100, 3.150, 3.400, 3.350]
    assert made.contract_positions.tolist() == [0, 0, 1, 1]


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["Z26", "F27"]),
            st.integers(-10000, 10000).filter(lambda n: n != 0),
            st.floats(allow_nan=False, allow_infinity=False),
        ),
        min_size=1,
        max_size=40,
    )
)
def test_each_trade_alone_is_the_same_row_as_in_the_batch(
    rows: list[tuple[str, int, float]],
) -> None:
    count = len(rows)
    ids = ("repeated label",) * count
    dates = np.full(count, np.datetime64("2026-09-25", "D"))
    codes = tuple(row[0] for row in rows)
    lots = np.array([row[1] for row in rows], dtype=np.float64)
    prices = np.array([row[2] for row in rows], dtype=np.float64)
    batch = futures_trades(NG, "NYMEX NG", ids, dates, codes, lots, prices)
    for i in range(count):
        one = futures_trades(
            NG,
            "NYMEX NG",
            ids[i : i + 1],
            dates[i : i + 1],
            codes[i : i + 1],
            lots[i : i + 1],
            prices[i : i + 1],
        )
        assert one.index is batch.index
        assert one.specification_position == batch.specification_position
        assert one.trade_ids == batch.trade_ids[i : i + 1]
        assert one.contract_codes == batch.contract_codes[i : i + 1]
        for single, grouped in (
            (one.trade_dates, batch.trade_dates),
            (one.signed_lots, batch.signed_lots),
            (one.trade_prices, batch.trade_prices),
            (one.contract_positions, batch.contract_positions),
        ):
            assert single.shape == (1,)
            assert grouped.shape == (count,)
            assert single.dtype == grouped.dtype
            np.testing.assert_array_equal(single, grouped[i : i + 1])


def test_owned_columns_cannot_be_changed_by_reused_input_buffers() -> None:
    dates, lots, prices = DATES.copy(), LOTS.copy(), PRICES.copy()
    made = futures_trades(NG, "NYMEX NG", IDS, dates, CODES, lots, prices)
    for stored, supplied, dtype in (
        (made.trade_dates, dates, "datetime64[D]"),
        (made.signed_lots, lots, "float64"),
        (made.trade_prices, prices, "float64"),
    ):
        assert stored.dtype == np.dtype(dtype)
        assert stored.ndim == 1
        assert not np.shares_memory(stored, supplied)
        assert not stored.flags.writeable
        supplied[:] = supplied[-1]
        with pytest.raises(ValueError):
            stored[0] = supplied[-1]
    assert made.signed_lots.tolist() == [10.0, -4.0, 7.0, -12.0]
    assert made.trade_prices.tolist() == [3.100, 3.150, 3.400, 3.350]
    np.testing.assert_array_equal(made.trade_dates, DATES)
    assert made.contract_positions.dtype == np.dtype(np.intp)
    assert not made.contract_positions.flags.writeable
    for field in ("trade_ids", "index"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(made, field, None)


def test_duplicate_deal_occurrences_are_preserved_without_netting() -> None:
    made = futures_trades(
        NG,
        "NYMEX NG",
        ("same",) * 3,
        DATES[:3],
        ("Z26",) * 3,
        np.array([10.0, 10.0, -10.0]),
        np.array([3.1, 3.1, 3.1]),
    )
    assert made.trade_ids == ("same", "same", "same")
    assert made.signed_lots.tolist() == [10.0, 10.0, -10.0]
    assert made.contract_positions.tolist() == [0, 0, 0]


def test_agreed_prices_are_not_rounded_or_restricted_to_positive_values() -> None:
    prices = np.array([0.0, -0.05, 3.12345, 1000.0])
    made = futures_trades(NG, "NYMEX NG", IDS, DATES, CODES, LOTS, prices)
    np.testing.assert_array_equal(made.trade_prices, prices)


@pytest.mark.parametrize(
    ("lots", "message"),
    [
        ([1.0, 0.0, 2.0, 3.0], "signed_lots row 2 is 0.0, expected nonzero lots"),
        ([1.0, -0.5, 2.0, 3.0], "signed_lots row 2 is -0.5, expected a whole number"),
    ],
)
def test_lots_describe_whole_nonzero_contract_positions(lots: list[float], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        futures_trades(NG, "NYMEX NG", IDS, DATES, CODES, np.array(lots), PRICES)


@pytest.mark.parametrize("code", ["z26", "Z26 ", "CAL27", "G27"])
def test_codes_must_match_the_schedule_exactly(code: str) -> None:
    with pytest.raises(ValueError, match=r"contract_code row 2.*expected a code"):
        futures_trades(NG, "NYMEX NG", IDS, DATES, ("Z26", code, "F27", "F27"), LOTS, PRICES)


def test_an_ambiguous_schedule_cannot_silently_bind_a_trade_to_a_month() -> None:
    ambiguous = dataclasses.replace(NG, schedule=futures_schedule(("Z26", "Z26"), DATES[:2], None))
    with pytest.raises(ValueError, match="index schedule has duplicate contract codes"):
        futures_trades(ambiguous, "NYMEX NG", IDS, DATES, CODES, LOTS, PRICES)


def test_the_shared_specification_is_required_and_resolved_by_name() -> None:
    with pytest.raises(ValueError, match="contract_specification is 'ICE NG'"):
        futures_trades(NG, "ICE NG", IDS, DATES, CODES, LOTS, PRICES)
    specs = contract_specifications(
        ("other", "NYMEX NG"), np.array([2500.0, 10000.0]), np.zeros(2), np.zeros(2)
    )
    other = dataclasses.replace(NG, specifications=specs)
    assert (
        futures_trades(other, "NYMEX NG", IDS, DATES, CODES, LOTS, PRICES).specification_position
        == 1
    )


@pytest.mark.parametrize("kind", [Kind.IFERC, Kind.GAS_DAILY])
def test_this_iteration_accepts_only_a_futures_index(kind: Kind) -> None:
    other = dataclasses.replace(NG, kind=kind)
    with pytest.raises(ValueError, match="expected a futures index"):
        futures_trades(other, "NYMEX NG", IDS, DATES, CODES, LOTS, PRICES)
