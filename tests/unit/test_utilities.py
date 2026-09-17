"""util_ReadHandle through the seam: each kind spilled as its creator's table, a spill fed back to a
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
from goosedove.index_definitions.contract_specifications import ContractSpecifications
from goosedove.index_definitions.expiry_schedule import ExpirySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index_conventions import IndexConventions
from goosedove.market_data.daily_fixings import DailyFixings
from goosedove.market_data.futures_curve import FuturesCurve
from goosedove.market_data.monthly_fixings import MonthlyFixings

# Serials for 11, 12 and 13 September 2026.
SEP_11, SEP_12, SEP_13 = 46276.0, 46277.0, 46278.0
HEADERS = Cells.from_rows([["date", "discount_factor"]])
BODY = Cells.from_rows([[SEP_11, 1.0], [SEP_12, 0.9999], [SEP_13, 0.9998]])

Spill = tuple[NDArray[np.uint8], NDArray[np.float64], str]


def read(handle: object) -> Spill:
    """What the host is handed for a spill: the kinds, the numbers, the texts joined."""
    result = bridge.call("util_ReadHandle", [handle])
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
    handle = bridge.call("_CreateValuationDate", [SEP_11, 0.5])
    assert rows(read(handle)) == [
        ["as_of", "day_fraction_elapsed"],
        ["datetime64[D]", "float"],
        [SEP_11, 0.5],
    ]


def test_a_curve_spills_its_table_with_dates_as_serials_and_factors_exactly() -> None:
    handle = bridge.call("_CreateDiscountCurve", [HEADERS, BODY])
    assert rows(read(handle)) == [
        ["date", "discount_factor"],
        ["datetime64[D]", "float64"],
        [SEP_11, 1.0],
        [SEP_12, 0.9999],
        [SEP_13, 0.9998],
    ]


def test_a_schedule_spills_its_columns_with_the_publication_dates_last() -> None:
    codes = Cells.from_rows([["m26"], ["n26"]])
    futures = Cells.from_rows([[46161.0], [46195.0]])
    options = Cells.from_rows([[46156.0], [46189.0]])
    publications = Cells.from_rows([[46162.0], [46196.0]])
    with_options = bridge.call("_CreateExpirySchedule", [codes, futures, options, MISSING])
    assert rows(read(with_options)) == [
        ["future_code", "future_expiry", "option_expiry"],
        ["str", "datetime64[D]", "datetime64[D]"],
        ["m26", 46161.0, 46156.0],
        ["n26", 46195.0, 46189.0],
    ]
    without = bridge.call("_CreateExpirySchedule", [codes, futures, MISSING, MISSING])
    assert rows(read(without)) == [
        ["future_code", "future_expiry"],
        ["str", "datetime64[D]"],
        ["m26", 46161.0],
        ["n26", 46195.0],
    ]
    every = bridge.call("_CreateExpirySchedule", [codes, futures, options, publications])
    assert rows(read(every)) == [
        ["future_code", "future_expiry", "option_expiry", "publication_date"],
        ["str", "datetime64[D]", "datetime64[D]", "datetime64[D]"],
        ["m26", 46161.0, 46156.0, 46162.0],
        ["n26", 46195.0, 46189.0, 46196.0],
    ]
    published = bridge.call("_CreateExpirySchedule", [codes, futures, MISSING, publications])
    assert rows(read(published)) == [
        ["future_code", "future_expiry", "publication_date"],
        ["str", "datetime64[D]", "datetime64[D]"],
        ["m26", 46161.0, 46162.0],
        ["n26", 46195.0, 46196.0],
    ]


def test_a_futures_curve_spills_its_two_columns_with_prices_exactly() -> None:
    codes = Cells.from_rows([["M26"], ["N26"]])
    prices = Cells.from_rows([[71.25], [71.4]])
    handle = bridge.call("_CreateFuturesCurve", [codes, prices])
    assert rows(read(handle)) == [
        ["future_code", "price"],
        ["str", "float64"],
        ["M26", 71.25],
        ["N26", 71.4],
    ]


# Serials for 1 and 4 May 2026, a Friday and the Monday after it, checked against a calendar of
# one day, 1 January.
def test_daily_fixings_spill_their_table_with_dates_as_serials_and_settles_exactly() -> None:
    headers = Cells.from_rows([["date", "settle"]])
    body = Cells.from_rows([[46143.0, 101.94], [46146.0, 106.42]])
    calendar = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46023.0]])])
    handle = bridge.call("_CreateDailyFixings", [headers, body, calendar])
    assert rows(read(handle)) == [
        ["date", "settle"],
        ["datetime64[D]", "float64"],
        [46143.0, 101.94],
        [46146.0, 106.42],
    ]


# Serials for 5 January and 2 February 2026, the days two monthly indices were published, checked
# against a schedule of those two contract months.
def test_monthly_fixings_spill_publication_dates_as_serials_and_prices_exactly() -> None:
    publications = Cells.from_rows([[46027.0], [46055.0]])
    prices = Cells.from_rows([[1.85], [2.10]])
    schedule = bridge.call(
        "_CreateExpirySchedule",
        [
            Cells.from_rows([["F26"], ["G26"]]),
            Cells.from_rows([[46022.0], [46052.0]]),
            MISSING,
            publications,
        ],
    )
    handle = bridge.call("_CreateMonthlyFixings", [publications, prices, schedule])
    assert rows(read(handle)) == [
        ["publication_date", "price"],
        ["datetime64[D]", "float64"],
        [46027.0, 1.85],
        [46055.0, 2.10],
    ]


# Serials for 1 January, 19 January and 16 February 2026.
def test_a_calendar_spills_its_one_column_under_two_heading_rows() -> None:
    holidays = Cells.from_rows([[46023.0], [46041.0], [46069.0]])
    handle = bridge.call("_CreateHolidayCalendar", [holidays])
    assert rows(read(handle)) == [
        ["holiday"],
        ["datetime64[D]"],
        [46023.0],
        [46041.0],
        [46069.0],
    ]


def test_index_conventions_spill_one_row_of_five_texts_under_two_heading_rows() -> None:
    handle = bridge.call("_CreateIndexConventions", ["USD", "BBL", "USD", "volume", "BBL"])
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


# The lot sizes go out as numbers, as every whole number does on the sheet, one row per contract.
def test_contract_specifications_spill_one_row_per_contract_under_two_heading_rows() -> None:
    headers = Cells.from_rows(
        [["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
    )
    body = Cells.from_rows([["NYMEX NG", 10000.0, 3.0, 2.0], ["ICE NG", 2500.0, 0.75, 0.5]])
    handle = bridge.call("_CreateContractSpecifications", [headers, body])
    assert rows(read(handle)) == [
        ["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"],
        ["str", "float64", "float64", "float64"],
        ["NYMEX NG", 10000.0, 3.0, 2.0],
        ["ICE NG", 2500.0, 0.75, 0.5],
    ]


# Anchors three days apart spill four days, the anchors exact and the days between on the line.
def test_a_curve_from_anchors_spills_every_day_between_them() -> None:
    anchors = Cells.from_rows([[SEP_11, 1.0], [SEP_11 + 3, 0.9997]])
    kinds, slots, joined = read(bridge.call("_CreateDiscountCurve", [HEADERS, anchors]))
    assert kinds.shape == (6, 2)
    assert joined == "date\0discount_factor\0datetime64[D]\0float64"
    assert slots[2:, 0].tolist() == [SEP_11, SEP_12, SEP_13, SEP_11 + 3]
    assert slots[2, 1] == 1.0 and slots[5, 1] == 0.9997
    assert np.allclose(slots[3:5, 1], [0.9999, 0.9998], rtol=0, atol=1e-15)


# --- a spill is the table its creator took ----------------------------------


def test_a_curves_spill_fed_back_to_its_creator_makes_an_equal_curve() -> None:
    first = bridge.call("_CreateDiscountCurve", [HEADERS, BODY])
    spilled = rows(read(first))
    second = bridge.call(
        "_CreateDiscountCurve", [Cells.from_rows([spilled[0]]), Cells.from_rows(spilled[2:])]
    )
    assert second != first  # a new creator call publishes anew
    assert rows(read(second)) == spilled


@given(count=st.integers(1, 400))
def test_any_curve_of_n_days_spills_n_plus_two_rows_by_two(count: int) -> None:
    body = Cells.from_rows([[SEP_11 + i, 1.0 - i * 1e-5] for i in range(count)])
    kinds, slots, joined = read(bridge.call("_CreateDiscountCurve", [HEADERS, body]))
    assert kinds.shape == (count + 2, 2)
    assert joined == "date\0discount_factor\0datetime64[D]\0float64"
    assert slots[2:, 0].tolist() == [SEP_11 + i for i in range(count)]
    assert slots[2:, 1].tolist() == [1.0 - i * 1e-5 for i in range(count)]


# --- what does not resolve fails in the seam's words, and spills nothing -------


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (3.0, "#ERROR util_ReadHandle: handle is number 3.0, expected a handle"),
        (None, "#ERROR util_ReadHandle: handle is blank, expected a handle"),
        (
            "discount_curve:000000:000001",
            "#ERROR util_ReadHandle: handle is text 'discount_curve:000000:000001' naming no live "
            "object, expected a handle",
        ),
        (
            "#ERROR _CreateDiscountCurve: ValueError: x",
            "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: "
            "#ERROR _CreateDiscountCurve: ValueError: x",
        ),
    ],
    ids=["a number", "a blank", "text naming no live object", "a creator's failure, relayed"],
)
def test_a_handle_that_does_not_resolve_fails_in_the_seams_words(value: object, text: str) -> None:
    assert bridge.call("util_ReadHandle", [value]) == text


# --- every published kind has a table, and one without fails rather than guessing --------


class Unshown:
    """A kind no creator publishes and no table was written for."""


@probe
def MakeUnshown() -> Handle[Unshown]:
    return Unshown()


def test_a_kind_without_a_table_fails_rather_than_guessing_its_columns() -> None:
    handle = bridge.call("MakeUnshown", [])
    assert (
        bridge.call("util_ReadHandle", [handle])
        == "#ERROR util_ReadHandle: TypeError: no table for a Unshown"
    )


def test_every_kind_a_creator_publishes_has_a_table() -> None:
    assert {
        ValuationDate,
        DiscountCurve,
        ExpirySchedule,
        HolidayCalendar,
        IndexConventions,
        ContractSpecifications,
        FuturesCurve,
        DailyFixings,
        MonthlyFixings,
    } <= set(shown.registry)
