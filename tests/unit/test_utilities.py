"""ReadHandle through the seam: each kind spilled as its creator's table, a spill fed back to a
creator, and the seam's words for a handle that does not resolve."""

from typing import cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle
from goosedove.excel.probes import probe
from goosedove.excel.utilities import shown
from goosedove.globals.discount_curve import DiscountCurve
from goosedove.globals.valuation_date import ValuationDate
from goosedove.market_definitions.contract_spec import ContractSpec
from goosedove.market_definitions.expiry_schedule import ExpirySchedule
from goosedove.market_definitions.holiday_calendar import HolidayCalendar
from goosedove.market_definitions.market_conventions import MarketConventions

# Serials for 11, 12 and 13 September 2026.
SEP_11, SEP_12, SEP_13 = 46276.0, 46277.0, 46278.0
HEADERS = Cells.from_rows([["date", "discount_factor"]])
BODY = Cells.from_rows([[SEP_11, 1.0], [SEP_12, 0.9999], [SEP_13, 0.9998]])

Spill = tuple[NDArray[np.uint8], NDArray[np.float64], str]


def read(handle: object) -> Spill:
    """What the host is handed for a spill: the kinds, the numbers, the texts joined."""
    result = bridge.call("ReadHandle", [handle])
    assert isinstance(result, tuple), result
    return cast(Spill, result)


def rows(spill: Spill) -> list[list[object]]:
    """The spill as a sheet would show it: text where a cell holds text, the number otherwise."""
    kinds, slots, joined = spill
    texts = iter(joined.split("\0")) if joined else iter(())
    shown_rows: list[list[object]] = []
    for row_kinds, row_slots in zip(kinds.tolist(), slots.tolist(), strict=True):
        shown_rows.append(
            [
                next(texts) if kind == 1 else float(slot)
                for kind, slot in zip(row_kinds, row_slots, strict=True)
            ]
        )
    return shown_rows


# --- each kind, as its creator took it --------------------------------------


def test_a_valuation_date_spills_its_two_fields_under_two_heading_rows() -> None:
    handle = bridge.call("CreateValuationDate", [SEP_11, 0.5])
    assert rows(read(handle)) == [
        ["as_of", "day_fraction_elapsed"],
        ["datetime64[D]", "float"],
        [SEP_11, 0.5],
    ]


def test_a_curve_spills_its_table_with_dates_as_serials_and_factors_exactly() -> None:
    handle = bridge.call("CreateDiscountCurve", [HEADERS, BODY])
    assert rows(read(handle)) == [
        ["date", "discount_factor"],
        ["datetime64[D]", "float64"],
        [SEP_11, 1.0],
        [SEP_12, 0.9999],
        [SEP_13, 0.9998],
    ]


def test_a_schedule_spills_three_columns_with_options_and_two_without() -> None:
    codes = Cells.from_rows([["m26"], ["n26"]])
    futures = Cells.from_rows([[46161.0], [46195.0]])
    options = Cells.from_rows([[46156.0], [46189.0]])
    with_options = bridge.call("CreateExpirySchedule", [codes, futures, options])
    assert rows(read(with_options)) == [
        ["future_code", "future_expiry", "option_expiry"],
        ["str", "datetime64[D]", "datetime64[D]"],
        ["m26", 46161.0, 46156.0],
        ["n26", 46195.0, 46189.0],
    ]
    without = bridge.call("CreateExpirySchedule", [codes, futures, MISSING])
    assert rows(read(without)) == [
        ["future_code", "future_expiry"],
        ["str", "datetime64[D]"],
        ["m26", 46161.0],
        ["n26", 46195.0],
    ]


# Serials for 1 January, 19 January and 16 February 2026.
def test_a_calendar_spills_its_one_column_under_two_heading_rows() -> None:
    holidays = Cells.from_rows([[46023.0], [46041.0], [46069.0]])
    handle = bridge.call("CreateHolidayCalendar", [holidays])
    assert rows(read(handle)) == [
        ["holiday"],
        ["datetime64[D]"],
        [46023.0],
        [46041.0],
        [46069.0],
    ]


def test_market_conventions_spill_one_row_of_five_texts_under_two_heading_rows() -> None:
    handle = bridge.call("CreateMarketConventions", ["USD", "BBL", "USD", "volume", "BBL"])
    assert rows(read(handle)) == [
        [
            "quote_currency_unit",
            "quote_quantity_unit",
            "currency_unit",
            "quantity_type",
            "quantity_unit",
        ],
        ["str", "str", "str", "str", "str"],
        ["USD", "BBL", "USD", "volume", "BBL"],
    ]


# The lot size goes out as a number, as every whole number does on the sheet.
def test_a_contract_spec_spills_its_four_fields_under_two_heading_rows() -> None:
    handle = bridge.call("CreateContractSpec", ["WTI", 1000.0, 3.0, 2.0])
    assert rows(read(handle)) == [
        ["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"],
        ["str", "int", "float", "float"],
        ["WTI", 1000.0, 3.0, 2.0],
    ]


# Anchors three days apart spill four days, the anchors exact and the days between on the line.
def test_a_curve_from_anchors_spills_every_day_between_them() -> None:
    anchors = Cells.from_rows([[SEP_11, 1.0], [SEP_11 + 3, 0.9997]])
    kinds, slots, joined = read(bridge.call("CreateDiscountCurve", [HEADERS, anchors]))
    assert kinds.shape == (6, 2)
    assert joined == "date\0discount_factor\0datetime64[D]\0float64"
    assert slots[2:, 0].tolist() == [SEP_11, SEP_12, SEP_13, SEP_11 + 3]
    assert slots[2, 1] == 1.0 and slots[5, 1] == 0.9997
    assert np.allclose(slots[3:5, 1], [0.9999, 0.9998], rtol=0, atol=1e-15)


# --- a spill is the table its creator took ----------------------------------


def test_a_curves_spill_fed_back_to_its_creator_makes_an_equal_curve() -> None:
    first = bridge.call("CreateDiscountCurve", [HEADERS, BODY])
    spilled = rows(read(first))
    second = bridge.call(
        "CreateDiscountCurve", [Cells.from_rows([spilled[0]]), Cells.from_rows(spilled[2:])]
    )
    assert second != first  # a new creator call publishes anew
    assert rows(read(second)) == spilled


@given(count=st.integers(1, 400))
def test_any_curve_of_n_days_spills_n_plus_two_rows_by_two(count: int) -> None:
    body = Cells.from_rows([[SEP_11 + i, 1.0 - i * 1e-5] for i in range(count)])
    kinds, slots, joined = read(bridge.call("CreateDiscountCurve", [HEADERS, body]))
    assert kinds.shape == (count + 2, 2)
    assert joined == "date\0discount_factor\0datetime64[D]\0float64"
    assert slots[2:, 0].tolist() == [SEP_11 + i for i in range(count)]
    assert slots[2:, 1].tolist() == [1.0 - i * 1e-5 for i in range(count)]


# --- what does not resolve fails in the seam's words, and spills nothing -------


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (3.0, "#ERROR ReadHandle: handle is number 3.0, expected a handle"),
        (None, "#ERROR ReadHandle: handle is blank, expected a handle"),
        (
            "discount_curve:000000:000001",
            "#ERROR ReadHandle: handle is text 'discount_curve:000000:000001' naming no live "
            "object, expected a handle",
        ),
        (
            "#ERROR CreateDiscountCurve: ValueError: x",
            "#ERROR ReadHandle: handle is the creator's failure, expected a handle: "
            "#ERROR CreateDiscountCurve: ValueError: x",
        ),
    ],
    ids=["a number", "a blank", "text naming no live object", "a creator's failure, relayed"],
)
def test_a_handle_that_does_not_resolve_fails_in_the_seams_words(value: object, text: str) -> None:
    assert bridge.call("ReadHandle", [value]) == text


# --- every published kind has a table, and one without fails rather than guessing --------


class Unshown:
    """A kind no creator publishes and no table was written for."""


@probe
def MakeUnshown() -> Handle[Unshown]:
    return Unshown()


def test_a_kind_without_a_table_fails_rather_than_guessing_its_columns() -> None:
    handle = bridge.call("MakeUnshown", [])
    assert (
        bridge.call("ReadHandle", [handle])
        == "#ERROR ReadHandle: TypeError: no table for a Unshown"
    )


def test_every_kind_a_creator_publishes_has_a_table() -> None:
    assert {
        ValuationDate,
        DiscountCurve,
        ExpirySchedule,
        HolidayCalendar,
        MarketConventions,
        ContractSpec,
    } <= set(shown.registry)
