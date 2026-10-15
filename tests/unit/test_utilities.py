"""util_ReadHandle through the seam: each kind spilled as its creator's table, a spill fed back to a
creator, and the seam's words for a handle that does not resolve."""

import functools
import os
from typing import cast

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray
from test_market import a_vector, any_gas_daily_history, any_history, any_iferc_history

from goosedove.calendar.calendar import Calendar
from goosedove.excel import bridge
from goosedove.excel.bridge import (
    BOOLEAN_CODE,
    MISSING,
    NUMBER_CODE,
    TEXT_CODE,
    Cells,
    Handle,
)
from goosedove.excel.probes import probe
from goosedove.excel.utilities import shown
from goosedove.globals.discount_curve import DiscountCurve
from goosedove.globals.valuation_date import ValuationDate
from goosedove.index_definitions.contract_specifications import ContractSpecifications
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.gas_daily_schedule import GasDailySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.index_conventions import IndexConventions
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory
from goosedove.market_data.futures_fixings import FuturesFixings
from goosedove.market_data.gas_daily_fixings import GasDailyFixings
from goosedove.market_data.iferc_fixings import IfercFixings
from goosedove.market_data.price_vector import PriceVector

PID = os.getpid()  # leads every handle this Python publishes

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


def test_a_schedule_spills_its_columns_with_the_options_last() -> None:
    codes = Cells.from_rows([["m26"], ["n26"]])
    futures = Cells.from_rows([[46161.0], [46195.0]])
    options = Cells.from_rows([[46156.0], [46189.0]])
    with_options = bridge.call("_CreateFuturesSchedule", [codes, futures, options])
    assert rows(read(with_options)) == [
        ["contract_code", "future_expiry", "option_expiry"],
        ["str", "datetime64[D]", "datetime64[D]"],
        ["m26", 46161.0, 46156.0],
        ["n26", 46195.0, 46189.0],
    ]
    without = bridge.call("_CreateFuturesSchedule", [codes, futures, MISSING])
    assert rows(read(without)) == [
        ["contract_code", "future_expiry"],
        ["str", "datetime64[D]"],
        ["m26", 46161.0],
        ["n26", 46195.0],
    ]


# Serials for 30 September, 30 October and 30 November 2026, the days three IFERC contract
# months stop trading, and 1 October, 2 November and 1 December, the days their indices print.
def test_an_iferc_schedule_spills_its_three_columns_under_two_heading_rows() -> None:
    codes = Cells.from_rows([["V26"], ["X26"], ["Z26"]])
    last_trading = Cells.from_rows([[46295.0], [46325.0], [46356.0]])
    published = Cells.from_rows([[46296.0], [46328.0], [46357.0]])
    kinds, slots, joined = read(
        bridge.call("_CreateIfercSchedule", [codes, last_trading, published])
    )
    assert rows((kinds, slots, joined)) == [
        ["contract_code", "last_trading_date", "publication_date"],
        ["str", "datetime64[D]", "datetime64[D]"],
        ["V26", 46295.0, 46296.0],
        ["X26", 46325.0, 46328.0],
        ["Z26", 46356.0, 46357.0],
    ]
    assert kinds.shape == (5, 3)
    assert kinds[2:].tolist() == [[TEXT_CODE, NUMBER_CODE, NUMBER_CODE]] * 3


# Serials for the first and last days of September, October and November 2026, three contract
# months of Gas Daily.
def test_a_gas_daily_schedule_spills_its_three_columns_under_two_heading_rows() -> None:
    codes = Cells.from_rows([["U26"], ["V26"], ["X26"]])
    first = Cells.from_rows([[46266.0], [46296.0], [46327.0]])
    last = Cells.from_rows([[46295.0], [46326.0], [46356.0]])
    kinds, slots, joined = read(bridge.call("_CreateGasDailySchedule", [codes, first, last]))
    assert rows((kinds, slots, joined)) == [
        ["contract_code", "first_date", "last_date"],
        ["str", "datetime64[D]", "datetime64[D]"],
        ["U26", 46266.0, 46295.0],
        ["V26", 46296.0, 46326.0],
        ["X26", 46327.0, 46356.0],
    ]
    assert kinds.shape == (5, 3)
    assert kinds[2:].tolist() == [[TEXT_CODE, NUMBER_CODE, NUMBER_CODE]] * 3


def an_index(schedule: object, holidays: object = MISSING) -> str:
    """The index handle of that schedule handle and holiday calendar handle, with one set of
    conventions and specifications, since nothing here reads either."""
    conventions = bridge.call("_CreateIndexConventions", ["USD", "BBL", "USD", "VOLUME", "BBL"])
    specifications = bridge.call(
        "_CreateContractSpecifications",
        [
            Cells.from_rows(
                [
                    [
                        "name",
                        "lot_size",
                        "lot_unit",
                        "brokerage_rate_per_lot",
                        "clearing_rate_per_lot",
                    ]
                ]
            ),
            Cells.from_rows([["NYMEX", 1000.0, "BBL", 0.0, 0.0]]),
        ],
    )
    text = bridge.call(
        "_CreateIndex",
        [
            "sample",
            "Sample futures index",
            schedule,
            conventions,
            specifications,
            holidays,
            MISSING,
        ],
    )
    assert isinstance(text, str) and text.startswith(f"{PID}:index:"), text
    return text


def a_two_contract_schedule() -> object:
    return bridge.call(
        "_CreateFuturesSchedule",
        [Cells.from_rows([["m26"], ["n26"]]), Cells.from_rows([[46161.0], [46162.0]]), MISSING],
    )


# Serials for 4 and 1 May 2026, a Monday and the Friday before it, the newer day in the first
# row as the creator takes them, checked against a calendar of one day, 1 January: the spill
# shows the rows as they were given, newest first, each settle beside its own day.
def test_futures_fixings_spill_their_columns_with_dates_as_serials_and_settles_exactly() -> None:
    days = Cells.from_rows([[46146.0], [46143.0]])
    settles = Cells.from_rows([[106.42], [101.94]])
    calendar = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46023.0]])])
    handle = bridge.call(
        "_CreateFuturesFixings", [days, settles, an_index(a_two_contract_schedule(), calendar)]
    )
    assert rows(read(handle)) == [
        ["date", "settle"],
        ["datetime64[D]", "float64"],
        [46146.0, 106.42],
        [46143.0, 101.94],
    ]


# Serials for 19 and 20 May 2026 and 25 May, the valuation date: a calendar of one day spills
# its four columns, the day as a serial, the code as text and the two flags as booleans, whose
# kinds the boolean code marks and whose slots hold 1 and 0.
def test_a_calendar_spills_four_columns_with_the_flags_as_booleans() -> None:
    valuation = bridge.call("_CreateValuationDate", [46167.0, 0.5])
    schedule = bridge.call(
        "_CreateFuturesSchedule",
        [Cells.from_rows([["m26"], ["n26"]]), Cells.from_rows([[46161.0], [46162.0]]), MISSING],
    )
    holidays = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46167.0]])])
    handle = bridge.call("_CreateCalendar", [valuation, an_index(schedule, holidays)])
    kinds, slots, joined = read(handle)
    assert rows((kinds, slots, joined)) == [
        ["date", "contract", "is_priced", "is_fixed"],
        ["datetime64[D]", "str", "bool", "bool"],
        [46162.0, "n26", 1.0, 1.0],
    ]
    assert kinds[2].tolist() == [NUMBER_CODE, TEXT_CODE, BOOLEAN_CODE, BOOLEAN_CODE]


# Serials for 19 and 20 May 2026 and the valuation date 21 May, with a settle fixed on the 20th:
# a history of a one-day calendar spills the calendar's four columns and the fixing price, a
# number on the fixed day, whose kind is the number code. Valued on the 20th instead, the day is
# not past, and with a fixing on the 19th, before the valuation date and unused, the fifth cell
# is the word unfixed, whose kind is the text code.
def test_a_market_history_spills_the_calendar_and_a_fixing_price_by_kind() -> None:
    schedule = bridge.call(
        "_CreateFuturesSchedule",
        [Cells.from_rows([["m26"], ["n26"]]), Cells.from_rows([[46161.0], [46162.0]]), MISSING],
    )
    holidays = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46167.0]])])
    over = an_index(schedule, holidays)
    fixed = bridge.call(
        "_CreateMarketHistory",
        [
            bridge.call(
                "_CreateCalendar",
                [bridge.call("_CreateValuationDate", [46163.0, 0.5]), over],
            ),
            bridge.call(
                "_CreateFuturesFixings",
                [46162.0, 70.85, over],
            ),
        ],
    )
    kinds, slots, joined = read(fixed)
    assert rows((kinds, slots, joined)) == [
        ["date", "contract", "is_priced", "is_fixed", "fixing_price"],
        ["datetime64[D]", "str", "bool", "bool", "float64"],
        [46162.0, "n26", 1.0, 1.0, 70.85],
    ]
    assert kinds[2].tolist() == [NUMBER_CODE, TEXT_CODE, BOOLEAN_CODE, BOOLEAN_CODE, NUMBER_CODE]
    unfixed = bridge.call(
        "_CreateMarketHistory",
        [
            bridge.call(
                "_CreateCalendar",
                [bridge.call("_CreateValuationDate", [46162.0, 0.5]), over],
            ),
            bridge.call(
                "_CreateFuturesFixings",
                [46161.0, 70.0, over],
            ),
        ],
    )
    kinds, slots, joined = read(unfixed)
    assert rows((kinds, slots, joined))[2] == [46162.0, "n26", 1.0, 0.0, "unfixed"]
    assert kinds[2].tolist() == [NUMBER_CODE, TEXT_CODE, BOOLEAN_CODE, BOOLEAN_CODE, TEXT_CODE]


# A Gas Daily calendar of one month, September 2026, valued on the 2nd with a print on the 2nd
# and the 1st, given newest first, and an IFERC calendar of two months valued on 15 October with
# October's index: the same five columns in the calendar's order, the oldest period first, a
# number on each fixed period and the word unfixed on the rest, no period being closed.
def test_the_other_two_histories_spill_the_same_five_columns() -> None:
    month = bridge.call(
        "_CreateGasDailySchedule",
        [Cells.from_rows([["U26"]]), Cells.from_rows([[46266.0]]), Cells.from_rows([[46295.0]])],
    )
    gas = an_index(month, MISSING)
    gas_daily = bridge.call(
        "_CreateCalendar", [bridge.call("_CreateValuationDate", [46267.0, 0.5]), gas]
    )
    prints = bridge.call(
        "_CreateGasDailyFixings",
        [Cells.from_rows([[46267.0], [46266.0]]), Cells.from_rows([[2.92], [2.91]]), gas],
    )
    kinds, slots, joined = read(bridge.call("_CreateMarketHistory", [gas_daily, prints]))
    shown = rows((kinds, slots, joined))
    assert len(shown) == 32
    assert shown[:5] == [
        ["date", "contract", "is_priced", "is_fixed", "fixing_price"],
        ["datetime64[D]", "str", "bool", "bool", "float64"],
        [46266.0, "U26", 1.0, 1.0, 2.91],
        [46267.0, "U26", 1.0, 1.0, 2.92],
        [46268.0, "U26", 1.0, 0.0, "unfixed"],
    ]
    assert {row[4] for row in shown[4:]} == {"unfixed"}
    assert kinds[2].tolist() == [NUMBER_CODE, TEXT_CODE, BOOLEAN_CODE, BOOLEAN_CODE, NUMBER_CODE]
    assert kinds[4].tolist() == [NUMBER_CODE, TEXT_CODE, BOOLEAN_CODE, BOOLEAN_CODE, TEXT_CODE]
    months = bridge.call(
        "_CreateIfercSchedule",
        [
            Cells.from_rows([["V26"], ["X26"]]),
            Cells.from_rows([[46295.0], [46325.0]]),
            Cells.from_rows([[46296.0], [46328.0]]),
        ],
    )
    henry = an_index(months, MISSING)
    iferc = bridge.call(
        "_CreateCalendar", [bridge.call("_CreateValuationDate", [46310.0, 0.5]), henry]
    )
    indices = bridge.call(
        "_CreateIfercFixings", [Cells.from_rows([["V26"]]), Cells.from_rows([[1.85]]), henry]
    )
    kinds, slots, joined = read(bridge.call("_CreateMarketHistory", [iferc, indices]))
    assert rows((kinds, slots, joined)) == [
        ["date", "contract", "is_priced", "is_fixed", "fixing_price"],
        ["datetime64[D]", "str", "bool", "bool", "float64"],
        [46296.0, "V26", 1.0, 1.0, 1.85],
        [46328.0, "X26", 1.0, 0.0, "unfixed"],
    ]
    assert kinds[2:, 4].tolist() == [NUMBER_CODE, TEXT_CODE]


# Serials for 7 back to 4 September 2026, Labor Day Monday back to the Friday, the newest flow
# day in the first row as the creator takes them, the three rows above the Friday carrying one
# print: the spill shows the rows as they were given.
def test_gas_daily_fixings_spill_flow_days_as_serials_and_prices_exactly() -> None:
    flow_days = Cells.from_rows([[46272.0], [46271.0], [46270.0], [46269.0]])
    prices = Cells.from_rows([[2.875], [2.875], [2.875], [2.930]])
    month = bridge.call(
        "_CreateGasDailySchedule",
        [Cells.from_rows([["U26"]]), Cells.from_rows([[46266.0]]), Cells.from_rows([[46295.0]])],
    )
    made = bridge.call("_CreateGasDailyFixings", [flow_days, prices, an_index(month, MISSING)])
    kinds, slots, joined = read(made)
    assert rows((kinds, slots, joined)) == [
        ["flow_date", "price"],
        ["datetime64[D]", "float64"],
        [46272.0, 2.875],
        [46271.0, 2.875],
        [46270.0, 2.875],
        [46269.0, 2.930],
    ]
    assert kinds.shape == (6, 2)
    assert kinds[2:].tolist() == [[NUMBER_CODE, NUMBER_CODE]] * 4


# Four months of Waha IFERC, the codes as typed, the newest month in the first row as the desk
# keeps them, and an index beside each, a zero and a negative among four kept in their places:
# the spill shows the codes in the order typed, over a schedule that lists them the other way.
def test_iferc_fixings_spill_codes_as_text_and_prices_exactly() -> None:
    codes = Cells.from_rows([["J26"], ["H26"], ["G26"], ["F26"]])
    prices = Cells.from_rows([[1.60], [-0.5], [0.0], [1.85]])
    months = bridge.call(
        "_CreateIfercSchedule",
        [
            Cells.from_rows([["F26"], ["G26"], ["H26"], ["J26"]]),
            Cells.from_rows([[46022.0], [46052.0], [46080.0], [46112.0]]),
            Cells.from_rows([[46027.0], [46055.0], [46083.0], [46113.0]]),
        ],
    )
    made = bridge.call("_CreateIfercFixings", [codes, prices, an_index(months, MISSING)])
    kinds, slots, joined = read(made)
    assert rows((kinds, slots, joined)) == [
        ["contract_code", "price"],
        ["str", "float64"],
        ["J26", 1.60],
        ["H26", -0.5],
        ["G26", 0.0],
        ["F26", 1.85],
    ]
    assert kinds.shape == (6, 2)
    assert kinds[2:].tolist() == [[TEXT_CODE, NUMBER_CODE]] * 4


# A Gas Daily market over one month, September 2026, valued on the 2nd with two prints, given
# newest first, and the balance-of-month quote: the market's rows run in the calendar's order,
# the prints on the 1st and 2nd, the quote on every later day, every cell a number. An IFERC
# market over two months valued on 15 October with October's index and November's quote: the
# index on the published row and the quote on the other.
def test_the_other_two_markets_spill_the_same_five_columns() -> None:
    month = bridge.call(
        "_CreateGasDailySchedule",
        [Cells.from_rows([["U26"]]), Cells.from_rows([[46266.0]]), Cells.from_rows([[46295.0]])],
    )
    gas = an_index(month, MISSING)
    gas_daily = bridge.call(
        "_CreateCalendar", [bridge.call("_CreateValuationDate", [46267.0, 0.5]), gas]
    )
    prints = bridge.call(
        "_CreateGasDailyFixings",
        [Cells.from_rows([[46267.0], [46266.0]]), Cells.from_rows([[2.92], [2.91]]), gas],
    )
    history = bridge.call("_CreateMarketHistory", [gas_daily, prints])
    balance = bridge.call("_CreatePriceVector", ["sample", 2.95])
    kinds, slots, joined = read(bridge.call("_CreateMarket", [history, balance]))
    shown_rows = rows((kinds, slots, joined))
    assert len(shown_rows) == 32
    assert shown_rows[:5] == [
        ["date", "contract", "is_priced", "is_fixed", "price"],
        ["datetime64[D]", "str", "bool", "bool", "float64"],
        [46266.0, "U26", 1.0, 1.0, 2.91],
        [46267.0, "U26", 1.0, 1.0, 2.92],
        [46268.0, "U26", 1.0, 0.0, 2.95],
    ]
    assert {row[4] for row in shown_rows[4:]} == {2.95}
    assert (kinds[2:, 4] == NUMBER_CODE).all()
    months = bridge.call(
        "_CreateIfercSchedule",
        [
            Cells.from_rows([["V26"], ["X26"]]),
            Cells.from_rows([[46295.0], [46325.0]]),
            Cells.from_rows([[46296.0], [46328.0]]),
        ],
    )
    henry = an_index(months, MISSING)
    iferc = bridge.call(
        "_CreateCalendar", [bridge.call("_CreateValuationDate", [46310.0, 0.5]), henry]
    )
    indices = bridge.call(
        "_CreateIfercFixings", [Cells.from_rows([["V26"]]), Cells.from_rows([[1.85]]), henry]
    )
    history = bridge.call("_CreateMarketHistory", [iferc, indices])
    quote = bridge.call("_CreatePriceVector", ["sample", 2.20])
    kinds, slots, joined = read(bridge.call("_CreateMarket", [history, quote]))
    assert rows((kinds, slots, joined)) == [
        ["date", "contract", "is_priced", "is_fixed", "price"],
        ["datetime64[D]", "str", "bool", "bool", "float64"],
        [46296.0, "V26", 1.0, 1.0, 1.85],
        [46328.0, "X26", 1.0, 0.0, 2.20],
    ]
    assert kinds[2:, 4].tolist() == [NUMBER_CODE, NUMBER_CODE]


# Serials for 19 and 20 May 2026: a market over a one-day calendar valued on its day, with a
# fixing on the 19th, before it, and one quote, spills the calendar's four columns and price, the
# quote a number on the open day; with the day a holiday, the same market shows closed, text, and
# the one quote is still required.
def test_a_market_spills_the_calendar_and_a_price_by_kind() -> None:
    schedule = bridge.call(
        "_CreateFuturesSchedule",
        [Cells.from_rows([["m26"], ["n26"]]), Cells.from_rows([[46161.0], [46162.0]]), MISSING],
    )
    valuation = bridge.call("_CreateValuationDate", [46162.0, 0.5])
    quote = bridge.call("_CreatePriceVector", ["sample", 72.10])
    for holiday, flag, cell, kind in (
        (46167.0, 1.0, 72.10, NUMBER_CODE),
        (46162.0, 0.0, "closed", TEXT_CODE),
    ):
        holidays = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[holiday]])])
        over = an_index(schedule, holidays)
        calendar = bridge.call("_CreateCalendar", [valuation, over])
        fixings = bridge.call("_CreateFuturesFixings", [46161.0, 70.0, over])
        history = bridge.call("_CreateMarketHistory", [calendar, fixings])
        kinds, slots, joined = read(bridge.call("_CreateMarket", [history, quote]))
        assert rows((kinds, slots, joined)) == [
            ["date", "contract", "is_priced", "is_fixed", "price"],
            ["datetime64[D]", "str", "bool", "bool", "float64"],
            [46162.0, "n26", flag, 0.0, cell],
        ]
        assert kinds[2].tolist() == [NUMBER_CODE, TEXT_CODE, BOOLEAN_CODE, BOOLEAN_CODE, kind]


# Four prices selected without a header, a zero and a negative among them and the first
# repeated, under the index's name: the spill puts the header and the type over the prices,
# each a number in its place, and shows no name, which the sheet holds beside the creator.
def test_a_price_vector_spills_one_column_of_prices_under_two_heading_rows() -> None:
    handle = bridge.call(
        "_CreatePriceVector", ["WTI NYMEX", Cells.from_rows([[74.25], [0.0], [-0.5], [74.25]])]
    )
    kinds, slots, joined = read(handle)
    assert rows((kinds, slots, joined)) == [
        ["price"],
        ["float64"],
        [74.25],
        [0.0],
        [-0.5],
        [74.25],
    ]
    assert kinds[2:, 0].tolist() == [NUMBER_CODE] * 4


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
    handle = bridge.call("_CreateIndexConventions", ["USD", "BBL", "USD", "VOLUME", "BBL"])
    assert rows(read(handle)) == [
        [
            "quote_currency_unit",
            "quote_quantity_unit",
            "currency_unit",
            "quantity_type",
            "quantity_unit",
        ],
        ["str", "str", "str", "str", "str"],
        ["USD", "BBL", "USD", "VOLUME", "BBL"],
    ]


# The lot sizes go out as numbers, as every whole number does on the sheet, the lot units as text,
# one row per word.
def test_contract_specifications_spill_one_row_per_contract_under_two_heading_rows() -> None:
    headers = Cells.from_rows(
        [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
    )
    body = Cells.from_rows(
        [["lots", 10000.0, "MMBTU", 3.0, 2.0], ["ice_lots", 2500.0, "MMBTU", 0.75, 0.5]]
    )
    handle = bridge.call("_CreateContractSpecifications", [headers, body])
    assert rows(read(handle)) == [
        ["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"],
        ["str", "float64", "str", "float64", "float64"],
        ["lots", 10000.0, "MMBTU", 3.0, 2.0],
        ["ice_lots", 2500.0, "MMBTU", 0.75, 0.5],
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


# --- the prompt code: one calendar handle in, one code out ---------------------


@functools.cache
def the_futures_index() -> str:
    """A three-contract index, m26, n26 and q26 expiring 19 May, 22 June and 21 July 2026, with
    the 25th of May a holiday, made once so that its calendars and fixings share it."""
    schedule = bridge.call(
        "_CreateFuturesSchedule",
        [
            Cells.from_rows([["m26"], ["n26"], ["q26"]]),
            Cells.from_rows([[46161.0], [46195.0], [46224.0]]),
            MISSING,
        ],
    )
    holidays = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46167.0]])])
    return an_index(schedule, holidays)


def a_futures_calendar(serial: float) -> str:
    """That index's calendar, valued on the serial at midday."""
    valuation = bridge.call("_CreateValuationDate", [serial, 0.5])
    return cast(str, bridge.call("_CreateCalendar", [valuation, the_futures_index()]))


# The prompt code, through the seam, on each kind: the contract prompt on the valuation day on
# a futures calendar, the expiring contract on its expiry day and the next from the day after,
# the first contract before the calendar begins; the month of the day after the valuation day
# on a Gas Daily calendar; the first month not yet published on an IFERC one, the month itself on
# its publication day. Text in the cell, the schedule's own spelling.
def test_the_prompt_code_reads_the_first_contract_quoted_on_each_kind() -> None:
    for serial, code in ((46168.0, "n26"), (46195.0, "n26"), (46196.0, "q26"), (46150.0, "n26")):
        assert bridge.call("util_ReadPrompt", [a_futures_calendar(serial)]) == code
    month = bridge.call(
        "_CreateGasDailySchedule",
        [Cells.from_rows([["U26"]]), Cells.from_rows([[46266.0]]), Cells.from_rows([[46295.0]])],
    )
    gas = an_index(month, MISSING)
    september = bridge.call(
        "_CreateCalendar", [bridge.call("_CreateValuationDate", [46267.0, 0.5]), gas]
    )
    assert bridge.call("util_ReadPrompt", [september]) == "U26"
    months = bridge.call(
        "_CreateIfercSchedule",
        [
            Cells.from_rows([["V26"], ["X26"]]),
            Cells.from_rows([[46295.0], [46325.0]]),
            Cells.from_rows([[46296.0], [46328.0]]),
        ],
    )
    henry = an_index(months, MISSING)
    for serial, code in ((46296.0, "V26"), (46297.0, "X26"), (46328.0, "X26")):
        iferc = bridge.call(
            "_CreateCalendar", [bridge.call("_CreateValuationDate", [serial, 0.5]), henry]
        )
        assert bridge.call("util_ReadPrompt", [iferc]) == code


# A calendar whose every period has fixed: the library's words, through the seam, for each kind.
def test_a_calendar_with_no_unfixed_period_has_no_prompt_code_through_the_seam() -> None:
    message = (
        "#ERROR util_ReadPrompt: ValueError: calendar has no unfixed period, "
        "expected at least one to quote"
    )
    assert bridge.call("util_ReadPrompt", [a_futures_calendar(46225.0)]) == message
    month = bridge.call(
        "_CreateGasDailySchedule",
        [Cells.from_rows([["U26"]]), Cells.from_rows([[46266.0]]), Cells.from_rows([[46295.0]])],
    )
    ended = bridge.call(
        "_CreateCalendar",
        [bridge.call("_CreateValuationDate", [46295.0, 0.5]), an_index(month, MISSING)],
    )
    assert bridge.call("util_ReadPrompt", [ended]) == message
    published = bridge.call(
        "_CreateIfercSchedule",
        [Cells.from_rows([["V26"]]), Cells.from_rows([[46295.0]]), Cells.from_rows([[46296.0]])],
    )
    after = bridge.call(
        "_CreateCalendar",
        [bridge.call("_CreateValuationDate", [46297.0, 0.5]), an_index(published, MISSING)],
    )
    assert bridge.call("util_ReadPrompt", [after]) == message


# The one argument is a calendar's handle, and the seam says so for anything else: left out,
# blank, a number, text naming no live object, and a handle of another kind, the index's and the
# market history's included.
def test_the_prompt_code_takes_a_calendar_handle_and_nothing_else() -> None:
    made = a_futures_calendar(46168.0)
    for wrong, what in (
        (MISSING, "is missing"),
        (None, "is blank"),
        (46168.0, "is number 46168.0"),
        ("calendar:9999999", "is text 'calendar:9999999' naming no live object"),
    ):
        assert bridge.call("util_ReadPrompt", [wrong]) == (
            f"#ERROR util_ReadPrompt: calendar {what}, expected calendar handle"
        )
    index = the_futures_index()
    fixings = bridge.call(
        "_CreateFuturesFixings",
        [
            Cells.from_rows([[46164.0], [46163.0], [46162.0]]),
            Cells.from_rows([[71.25], [71.1], [70.85]]),
            index,
        ],
    )
    history = bridge.call("_CreateMarketHistory", [made, fixings])
    for other, kind in (
        (history, "market history"),
        (index, "index"),
        (fixings, "futures fixings"),
    ):
        assert bridge.call("util_ReadPrompt", [other]) == (
            f"#ERROR util_ReadPrompt: calendar is {kind} handle {other!r}, expected calendar handle"
        )


# Reading the prompt publishes nothing: the store holds what it held, and the cell gets text.
def test_reading_the_prompt_publishes_no_object() -> None:
    made = a_futures_calendar(46168.0)
    before = bridge.live_handles()
    assert bridge.call("util_ReadPrompt", [made]) == "n26"
    assert bridge.call("util_ReadPrompt", [made]) == "n26"
    assert bridge.live_handles() == before


# --- two text helpers: the next contract, and the month as CME spells it --------------


# Text in and text out through the seam: the next contract in the monthly sequence, spelled as
# the code given, and the month as CME's feeds spell it, year then month, text and no number.
def test_the_next_contract_and_the_cme_month_read_a_code_as_the_desk_types_it() -> None:
    assert bridge.call("util_NextFut", ["F26"]) == "G26"
    assert bridge.call("util_NextFut", ["Z26"]) == "F27"
    assert bridge.call("util_NextFut", ["m26"]) == "n26"
    assert bridge.call("util_FutToCme", ["F26"]) == "202601"
    assert bridge.call("util_FutToCme", ["Z26"]) == "202612"
    assert bridge.call("util_FutToCme", ["u26"]) == "202609"
    assert isinstance(bridge.call("util_FutToCme", ["F26"]), str)


# A strip, a season, a four-digit year and December 2099: the library's words through the seam.
def test_a_code_that_is_no_single_contract_is_refused_through_the_seam() -> None:
    for name in ("util_NextFut", "util_FutToCme"):
        for contract in ("Cal27", "W29", "F2026", "F-26"):
            assert bridge.call(name, [contract]) == (
                f"#ERROR {name}: ValueError: contract is {contract!r}, "
                "expected a month letter and a two-digit year, such as F26"
            )
    assert bridge.call("util_NextFut", ["Z99"]) == (
        "#ERROR util_NextFut: ValueError: contract is 'Z99', expected a month before "
        "December 2099, the last a two-digit year can name"
    )
    assert bridge.call("util_FutToCme", ["Z99"]) == "209912"


# The one argument is text, and the seam says so for anything else: left out, blank, empty text,
# a number, a boolean and a range.
def test_the_text_helpers_take_one_text_and_nothing_else() -> None:
    for name in ("util_NextFut", "util_FutToCme"):
        for wrong, what in (
            (MISSING, "is missing"),
            (None, "is blank"),
            ("", "is empty text"),
            (26.0, "is number 26.0"),
            (True, "is boolean TRUE"),
            (Cells.from_rows([["F26"], ["G26"]]), "is 2x1 array"),
        ):
            assert bridge.call(name, [wrong]) == f"#ERROR {name}: contract {what}, expected text"


# --- two more: the month a day falls in, and the first day of a code's month -------------


# A day in and a code out, a code in and a day out, through the seam: the day's own month in
# capitals, and the first of the code's month as a serial, the sheet's date.
def test_the_code_of_a_day_and_the_first_day_of_a_code_through_the_seam() -> None:
    assert bridge.call("util_DateToFut", [46161.0]) == "K26"  # 19 May 2026, a WTI June expiry
    assert bridge.call("util_DateToFut", [46023.0]) == "F26"
    assert bridge.call("util_DateToFut", [46387.0]) == "Z26"
    assert bridge.call("util_FutToDate", ["F26"]) == 46023.0  # 1 January 2026
    assert bridge.call("util_FutToDate", ["n26"]) == 46204.0  # 1 July 2026
    assert bridge.call("util_FutToDate", ["Z99"]) == 73020.0
    assert isinstance(bridge.call("util_FutToDate", ["F26"]), float)


# A day outside the years two digits name, and a code that is no single contract: the library's
# words through the seam.
def test_a_day_outside_the_century_and_a_strip_are_refused_through_the_seam() -> None:
    for serial, named in ((36525.0, "1999-12-31"), (73051.0, "2100-01-01")):
        assert bridge.call("util_DateToFut", [serial]) == (
            f"#ERROR util_DateToFut: ValueError: date is {named}, expected a day from 2000 to "
            "2099, the years a two-digit code can name"
        )
    for contract in ("Cal27", "F2026"):
        assert bridge.call("util_FutToDate", [contract]) == (
            f"#ERROR util_FutToDate: ValueError: contract is {contract!r}, "
            "expected a month letter and a two-digit year, such as F26"
        )


# The day is one date and the code one text, and the seam says so for anything else.
def test_the_date_helpers_take_one_date_or_one_text_and_nothing_else() -> None:
    for wrong, what in (
        (MISSING, "is missing"),
        (None, "is blank"),
        (1.5, "is number 1.5"),
        ("x", "is text 'x'"),
        (True, "is boolean TRUE"),
        (Cells.from_rows([[46023.0], [46024.0]]), "is 2x1 array"),
    ):
        assert bridge.call("util_DateToFut", [wrong]) == (
            f"#ERROR util_DateToFut: date {what}, expected date"
        )
    for wrong, what in ((MISSING, "is missing"), (None, "is blank"), ("", "is empty text")):
        assert bridge.call("util_FutToDate", [wrong]) == (
            f"#ERROR util_FutToDate: contract {what}, expected text"
        )


# --- the first and the last day of a contract or strip --------------------------------


def serial(text: str) -> float:
    return float((np.datetime64(text, "D") - np.datetime64("1899-12-30", "D")).astype(np.int64))


# A label in and a date out, each the sheet's serial: a month, a quarter, a year, a winter across
# the year end, a summer and a range, in any case.
def test_the_first_and_last_days_of_a_period_come_out_as_dates() -> None:
    for period, first, last in (
        ("f26", "2026-01-01", "2026-01-31"),
        ("1Q27", "2027-01-01", "2027-03-31"),
        ("cal28", "2028-01-01", "2028-12-31"),
        ("W29", "2029-11-01", "2030-03-31"),
        ("s28", "2028-04-01", "2028-10-31"),
        ("F26-Z28", "2026-01-01", "2028-12-31"),
        ("w28-w29", "2028-11-01", "2030-03-31"),
        ("W99", "2099-11-01", "2100-03-31"),
    ):
        assert bridge.call("util_StartDate", [period, MISSING]) == serial(first)
        assert bridge.call("util_EndDate", [period, MISSING]) == serial(last)
    assert isinstance(bridge.call("util_EndDate", ["G28", MISSING]), float)


# A label that is no form, and a range the wrong way round: the library's words through the seam,
# the same from either reader, which both read the whole expression.
def test_a_malformed_or_reversed_period_is_refused_by_both_readers_through_the_seam() -> None:
    forms = (
        "a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28"
    )
    for name in ("util_StartDate", "util_EndDate"):
        for period in ("W8-W9", "Q1 27", "F26-", "F2026"):
            assert bridge.call(name, [period, MISSING]) == (
                f"#ERROR {name}: ValueError: period is {period!r}, expected {forms}"
            )
        for period in ("Z28-F26", "CAL28-F28"):
            assert bridge.call(name, [period, MISSING]) == (
                f"#ERROR {name}: ValueError: period is {period!r}, "
                "expected range endpoints in chronological order"
            )
        for wrong, what in (
            (MISSING, "is missing"),
            (None, "is blank"),
            ("", "is empty text"),
            (46023.0, "is number 46023.0"),
            (Cells.from_rows([["F26"], ["G26"]]), "is 2x1 array"),
        ):
            assert bridge.call(name, [wrong, MISSING]) == (
                f"#ERROR {name}: period {what}, expected text"
            )


# The balance of a period, since #173 from a valuation-date handle beside the label: the ticket's
# table as serials, the first day the later of the handle's day and the label's first, the last
# day the label's, the fraction of the day read for nothing; an ordinary label with a handle
# reads as before, with either handle. Left out with a BAL label, and a period that has ended,
# the library's words; a blank, a raw date, a text naming no object, a handle of another kind and
# a range, the seam's, the same whichever label stands beside them, since a supplied handle is
# checked whatever the label. Nothing is published for a result.
def test_the_balance_of_a_period_takes_its_valuation_date_handle_through_the_seam() -> None:
    def at(text: str, fraction: float = 0.5) -> object:
        return bridge.call("_CreateValuationDate", [serial(text), fraction])

    live = bridge.live_handles()
    for period, as_of, first, last in (
        ("balv26", "2026-09-20", "2026-10-01", "2026-10-31"),
        ("BALV26", "2026-10-12", "2026-10-12", "2026-10-31"),
        ("BalV26", "2026-10-31", "2026-10-31", "2026-10-31"),
        ("balf26", "2025-12-20", "2026-01-01", "2026-01-31"),
        ("balf26", "2026-01-15", "2026-01-15", "2026-01-31"),
        ("balf26", "2026-01-31", "2026-01-31", "2026-01-31"),
        ("balx26-z26", "2026-11-12", "2026-11-12", "2026-12-31"),
        ("balcal27", "2026-10-12", "2027-01-01", "2027-12-31"),
        ("BALZ26", "2026-12-15", "2026-12-15", "2026-12-31"),
        ("BALG28", "2028-02-29", "2028-02-29", "2028-02-29"),
        ("Z26", "2026-12-15", "2026-12-01", "2026-12-31"),
        ("V26", "2027-06-01", "2026-10-01", "2026-10-31"),
    ):
        handle = at(as_of)
        assert bridge.call("util_StartDate", [period, handle]) == serial(first)
        assert bridge.call("util_EndDate", [period, handle]) == serial(last)
        assert bridge.call("util_StartDate", [period, at(as_of, 1.0)]) == serial(first)
    # Two handles, each its own start, no ambient day between them.
    september, mid = at("2026-09-20"), at("2026-10-12")
    assert bridge.call("util_StartDate", ["balv26", september]) == serial("2026-10-01")
    assert bridge.call("util_StartDate", ["balv26", mid]) == serial("2026-10-12")
    assert bridge.call("util_StartDate", ["V26", september]) == serial("2026-10-01")
    assert bridge.call("util_StartDate", ["V26", mid]) == serial("2026-10-01")
    published = bridge.live_handles()[0] - live[0]  # the handles made above, nothing of the days
    for name in ("util_StartDate", "util_EndDate"):
        assert bridge.call(name, ["BALZ26", MISSING]) == (
            f"#ERROR {name}: ValueError: valuation_date is missing, expected a valuation-date "
            "handle with 'BALZ26', whose day starts the balance of a period"
        )
        assert bridge.call(name, ["balv26", at("2026-11-01")]) == (
            f"#ERROR {name}: ValueError: valuation_date is 2026-11-01, after 'balv26' ended on "
            "2026-10-31, expected a valuation day on or before the period's last day"
        )
        calendar = bridge.call(
            "_CreateHolidayCalendar", [Cells.from_rows([[serial("2026-12-25")]])]
        )
        for wrong, what in (
            (None, "is blank"),
            (serial("2026-12-15"), "is number 46371.0"),
            (46371.5, "is number 46371.5"),
            ("x", "is text 'x' naming no live object"),
            ("15-Dec-2026", "is text '15-Dec-2026' naming no live object"),
            (calendar, f"is holiday calendar handle {calendar!r}"),
            (Cells.from_rows([[46371.0], [46372.0]]), "is 2x1 array"),
        ):
            for period in ("BALZ26", "Z26"):
                assert bridge.call(name, [period, wrong]) == (
                    f"#ERROR {name}: valuation_date {what}, expected valuation date handle"
                )
    assert (
        bridge.live_handles()[0] == live[0] + published + 4
    )  # two calendars and two days, nothing else


# --- a date shifted by a text offset ------------------------------------------------------------


# The ticket's table through the seam: a serial and an instruction in, a serial out; the synthetic
# calendar, Monday 12 October 2026 closed, where a row names it, and the seam's MISSING where the
# calendar is left out. Nothing is published for a result.
def test_a_date_shifted_by_an_offset_comes_out_as_a_date() -> None:
    live = bridge.live_handles()
    synthetic = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[serial("2026-10-12")]])])
    for date, offset, calendar, expected in (
        ("2026-10-09", "+1bd", MISSING, "2026-10-12"),
        ("2026-10-09", "+1BD", synthetic, "2026-10-13"),
        ("2026-10-10", "+1bd", MISSING, "2026-10-12"),
        ("2026-10-11", "-1bd", MISSING, "2026-10-09"),
        ("2026-10-12", "+1bd", synthetic, "2026-10-13"),
        ("2026-10-12", "-1bd", synthetic, "2026-10-09"),
        ("2026-10-10", "+0bd", synthetic, "2026-10-10"),
        ("2026-10-09", "+7cd", synthetic, "2026-10-16"),
        ("2026-10-09", "-7cd", MISSING, "2026-10-02"),
        ("2026-10-10", "-0cd", MISSING, "2026-10-10"),
        ("2026-10-09", "+0em", synthetic, "2026-10-31"),
        ("2026-10-09", "+1em", MISSING, "2026-11-30"),
        ("2026-10-09", "-1em", MISSING, "2026-09-30"),
        ("2028-01-31", "+1em", MISSING, "2028-02-29"),
        ("2026-12-15", "+1em", MISSING, "2027-01-31"),
        ("2026-10-09", "+001cD", MISSING, "2026-10-10"),
        ("9999-12-31", "+0em", MISSING, "9999-12-31"),
    ):
        assert bridge.call("util_ShiftDate", [serial(date), offset, calendar]) == serial(expected)
    # Since #181 a chain, compound-date-offsets.md: the requested chain from 12 August 2026 on a
    # calendar closing Christmas Day, 28 December, and 25 December without it; the order the rule.
    christmas = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[serial("2026-12-25")]])])
    for date, offset, calendar, expected in (
        ("2026-08-12", "+3em+25cd-1bd+1bd", christmas, "2026-12-28"),
        ("2026-08-12", "+003EM+025cD-01BD+001bd", christmas, "2026-12-28"),
        ("2026-08-12", "+3em+25cd-1bd+1bd", MISSING, "2026-12-25"),
        ("2026-10-10", "-1bd+1bd", MISSING, "2026-10-12"),
        ("2026-01-30", "+1cd+0em", MISSING, "2026-01-31"),
        ("2026-01-30", "+0em+1cd", MISSING, "2026-02-01"),
    ):
        assert bridge.call("util_ShiftDate", [serial(date), offset, calendar]) == serial(expected)
    shifted = bridge.call("util_ShiftDate", [serial("2026-10-09"), "+1bd", MISSING])
    assert isinstance(shifted, float)
    assert bridge.live_handles()[0] == live[0] + 2  # the calendars, and nothing of the shifts


# The library's words through the seam: an instruction that is no offset, a result past the
# sheet's calendar, and a count of too many digits, named by its digits and not echoed.
def test_a_shift_the_library_refuses_is_refused_in_its_words_through_the_seam() -> None:
    for offset in ("1bd", "+1.5bd", "+1wd", " +1bd"):
        assert bridge.call("util_ShiftDate", [serial("2026-10-09"), offset, MISSING]) == (
            f"#ERROR util_ShiftDate: ValueError: offset is {offset!r}, expected one or more of a "
            "sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or "
            "+3em+25cd-1bd+1bd"
        )
    assert bridge.call("util_ShiftDate", [serial("2026-10-09"), "+1bd+2xd", MISSING]) == (
        "#ERROR util_ShiftDate: ValueError: offset is '+1bd+2xd', expected one or more of a "
        "sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or "
        "+3em+25cd-1bd+1bd; from character 5, '+2xd' begins with no instruction"
    )
    assert bridge.call("util_ShiftDate", [serial("9999-12-31"), "+1cd-1cd", MISSING]) == (
        "#ERROR util_ShiftDate: ValueError: date 9999-12-31 shifted by '+1cd-1cd' is 10000-01-01 "
        "at instruction 1, '+1cd', outside the sheet's calendar, 1900-03-01 to 9999-12-31"
    )
    assert bridge.call("util_ShiftDate", [serial("9999-12-31"), "+1cd", MISSING]) == (
        "#ERROR util_ShiftDate: ValueError: date 9999-12-31 shifted by '+1cd' is 10000-01-01, "
        "outside the sheet's calendar, 1900-03-01 to 9999-12-31"
    )
    assert bridge.call("util_ShiftDate", [serial("1900-03-01"), "-1bd", MISSING]) == (
        "#ERROR util_ShiftDate: ValueError: date 1900-03-01 shifted by '-1bd' is 1900-02-28, "
        "outside the sheet's calendar, 1900-03-01 to 9999-12-31"
    )
    assert bridge.call(
        "util_ShiftDate", [serial("2026-10-09"), "+" + "9" * 5000 + "cd", MISSING]
    ) == (
        "#ERROR util_ShiftDate: ValueError: offset has a count of 5000 digits, expected at most 7; "
        "the sheet's calendar runs 1900-03-01 to 9999-12-31"
    )


# The seam's words: the date one date, the offset one text, the calendar left out or a holiday
# calendar handle, a blank being no omission; checked whatever the offset, a zero or a calendar-day
# one that reads no holiday included.
def test_the_shifts_arguments_are_checked_by_the_seam_whatever_the_offset() -> None:
    for wrong, what in (
        (MISSING, "is missing"),
        (None, "is blank"),
        (46304.5, "is number 46304.5"),
        ("x", "is text 'x'"),
        (Cells.from_rows([[46304.0], [46305.0]]), "is 2x1 array"),
    ):
        assert bridge.call("util_ShiftDate", [wrong, "+1bd", MISSING]) == (
            f"#ERROR util_ShiftDate: date {what}, expected date"
        )
    for wrong, what in (
        (MISSING, "is missing"),
        (None, "is blank"),
        ("", "is empty text"),
        (1.0, "is number 1.0"),
    ):
        assert bridge.call("util_ShiftDate", [serial("2026-10-09"), wrong, MISSING]) == (
            f"#ERROR util_ShiftDate: offset {what}, expected text"
        )
    valuation = bridge.call("_CreateValuationDate", [serial("2026-10-09"), 0.5])
    for offset in ("+1bd", "+0bd", "+7cd", "+0em"):
        assert bridge.call("util_ShiftDate", [serial("2026-10-09"), offset, None]) == (
            "#ERROR util_ShiftDate: holiday_calendar is blank, expected holiday calendar handle"
        )
        assert bridge.call(
            "util_ShiftDate", [serial("2026-10-09"), offset, "x:holiday_calendar:9"]
        ) == (
            "#ERROR util_ShiftDate: holiday_calendar is text 'x:holiday_calendar:9' naming no "
            "live object, expected holiday calendar handle"
        )
        assert bridge.call("util_ShiftDate", [serial("2026-10-09"), offset, valuation]) == (
            f"#ERROR util_ShiftDate: holiday_calendar is valuation date handle {valuation!r}, "
            "expected holiday calendar handle"
        )


# --- what does not resolve fails in the seam's words, and spills nothing -------


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (3.0, "#ERROR util_ReadHandle: handle is number 3.0, expected a handle"),
        (None, "#ERROR util_ReadHandle: handle is blank, expected a handle"),
        (
            "discount_curve:9999999",
            "#ERROR util_ReadHandle: handle is text 'discount_curve:9999999' naming no live "
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


# One row of what an index holds: the name and the kind as text, the two counts as numbers and
# the holiday flag a boolean, for a futures index with its calendar and an IFERC one without.
def test_an_index_spills_one_row_of_what_it_holds() -> None:
    schedule = bridge.call(
        "_CreateFuturesSchedule",
        [Cells.from_rows([["m26"], ["n26"]]), Cells.from_rows([[46161.0], [46162.0]]), MISSING],
    )
    holidays = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46167.0]])])
    conventions = bridge.call("_CreateIndexConventions", ["USD", "MMBTU", "USD", "ENERGY", "MMBTU"])
    specifications = bridge.call(
        "_CreateContractSpecifications",
        [
            Cells.from_rows(
                [
                    [
                        "name",
                        "lot_size",
                        "lot_unit",
                        "brokerage_rate_per_lot",
                        "clearing_rate_per_lot",
                    ]
                ]
            ),
            Cells.from_rows([["NYMEX NG", 10000.0, "MMBTU", 3.0, 2.0]]),
        ],
    )
    made = bridge.call(
        "_CreateIndex",
        [
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            schedule,
            conventions,
            specifications,
            holidays,
            MISSING,
        ],
    )
    kinds, slots, joined = read(made)
    assert rows((kinds, slots, joined)) == [
        [
            "name",
            "display_name",
            "kind",
            "contracts",
            "specifications",
            "has_holiday_calendar",
            "reporting_lot",
        ],
        ["str", "str", "str", "int64", "int64", "bool", "str"],
        ["Henry Hub NYMEX", "Henry Hub natural gas - NYMEX", "futures", 2.0, 1.0, 1.0, "unset"],
    ]
    assert kinds[2].tolist() == [
        TEXT_CODE,
        TEXT_CODE,
        TEXT_CODE,
        NUMBER_CODE,
        NUMBER_CODE,
        BOOLEAN_CODE,
        TEXT_CODE,
    ]
    month = bridge.call(
        "_CreateIfercSchedule",
        [Cells.from_rows([["V26"]]), Cells.from_rows([[46295.0]]), Cells.from_rows([[46296.0]])],
    )
    kinds, slots, joined = read(
        bridge.call(
            "_CreateIndex",
            [
                "Henry Hub IFERC",
                "Henry Hub natural gas - Inside FERC monthly index",
                month,
                conventions,
                specifications,
                MISSING,
                MISSING,
            ],
        )
    )
    assert rows((kinds, slots, joined))[2] == [
        "Henry Hub IFERC",
        "Henry Hub natural gas - Inside FERC monthly index",
        "IFERC",
        1.0,
        1.0,
        0.0,
        "unset",
    ]
    assert kinds[2, 5] == BOOLEAN_CODE


def test_every_kind_a_creator_publishes_has_a_table() -> None:
    assert {
        Calendar,
        ValuationDate,
        DiscountCurve,
        FuturesSchedule,
        GasDailySchedule,
        HolidayCalendar,
        IfercSchedule,
        IndexConventions,
        ContractSpecifications,
        Index,
        FuturesFixings,
        GasDailyFixings,
        IfercFixings,
        MarketHistory,
        PriceVector,
        Market,
    } <= set(shown.registry)


# --- the market's daily view, for any calendar -------------------------------------


# For any history of any of the three kinds, a futures one of two to eight contracts with any
# holidays or a Gas Daily or an IFERC one of one to eight months, valued on any day from before
# its calendar to its last period, with any number of quotes from the first unfixed period's
# contract's alone to one per remaining contract: the rows are the calendar's own spill through
# the last period of the last contract quoted, every one and no other, and the fifth cell is
# the period's fixing where it is fixed and priced, its contract's quote where it is priced and
# not fixed, and the word closed where the market is shut; no cell is unfixed, and no fixed
# period reads a quote.
@settings(deadline=None)
@given(data=st.data())
def test_every_day_of_a_market_shows_its_fixing_its_prompts_quote_or_closed(
    data: st.DataObject,
) -> None:
    history = data.draw(st.sampled_from((any_history, any_gas_daily_history, any_iferc_history)))(
        data
    )
    calendar = history.calendar
    first = int(calendar.contract[int(np.count_nonzero(calendar.is_fixed))])
    count = data.draw(st.integers(1, len(calendar.index.schedule.codes) - first))
    quotes = a_vector(*(100.0 + i for i in range(count)))
    made = market(history, quotes)
    table = shown(made)
    body = rows((table.kinds, table.numeric_slots, "\0".join(table.texts)))[2:]
    covered = int(np.count_nonzero(calendar.contract <= first + count - 1))
    assert len(body) == covered > int(np.count_nonzero(calendar.is_fixed))
    days = shown(calendar)
    assert [row[:4] for row in body] == rows(
        (days.kinds, days.numeric_slots, "\0".join(days.texts))
    )[2 : 2 + covered]
    fixed = dict(zip(history.fixed_rows.tolist(), history.fixing_prices.tolist(), strict=True))
    for row, (shown_row, open_, past, prompt) in enumerate(
        zip(
            body,
            calendar.is_priced[:covered],
            calendar.is_fixed[:covered],
            calendar.contract[:covered],
            strict=True,
        )
    ):
        if not open_:
            assert shown_row[4] == "closed"
        elif past:
            assert shown_row[4] == fixed[row]
        else:
            assert shown_row[4] == float(quotes.prices[int(prompt) - first])
    assert "unfixed" not in table.texts
