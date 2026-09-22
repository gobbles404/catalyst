"""util_ReadHandle through the seam: each kind spilled as its creator's table, a spill fed back to a
creator, and the seam's words for a handle that does not resolve."""

from typing import cast

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray
from test_market import a_vector, any_history
from test_market_history import any_monthly_history

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
from goosedove.index_definitions.delivery_schedule import DeliverySchedule
from goosedove.index_definitions.expiry_schedule import ExpirySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index_conventions import IndexConventions
from goosedove.index_definitions.publication_schedule import PublicationSchedule
from goosedove.market.market import Market, market
from goosedove.market.market_history import MarketHistory
from goosedove.market_data.daily_fixings import DailyFixings
from goosedove.market_data.monthly_fixings import MonthlyFixings
from goosedove.market_data.price_vector import PriceVector

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


# Serials for 1 and 30 November and 1 and 31 December 2026, two months of delivery.
def test_a_delivery_schedule_spills_its_three_columns_under_two_heading_rows() -> None:
    codes = Cells.from_rows([["X26"], ["Z26"]])
    starts = Cells.from_rows([[46327.0], [46357.0]])
    ends = Cells.from_rows([[46356.0], [46387.0]])
    kinds, slots, joined = read(bridge.call("_CreateDeliverySchedule", [codes, starts, ends]))
    assert rows((kinds, slots, joined)) == [
        ["contract_code", "delivery_start", "delivery_end"],
        ["str", "datetime64[D]", "datetime64[D]"],
        ["X26", 46327.0, 46356.0],
        ["Z26", 46357.0, 46387.0],
    ]
    assert kinds.shape == (4, 3)
    assert kinds[2:].tolist() == [[TEXT_CODE, NUMBER_CODE, NUMBER_CODE]] * 2


# Serials for 2 November and 1 December 2026, the days two reference prices are published.
def test_a_publication_schedule_spills_its_two_columns_under_two_heading_rows() -> None:
    codes = Cells.from_rows([["X26"], ["Z26"]])
    published = Cells.from_rows([[46328.0], [46357.0]])
    kinds, slots, joined = read(bridge.call("_CreatePublicationSchedule", [codes, published]))
    assert rows((kinds, slots, joined)) == [
        ["contract_code", "publication_date"],
        ["str", "datetime64[D]"],
        ["X26", 46328.0],
        ["Z26", 46357.0],
    ]
    assert kinds.shape == (4, 2)
    assert kinds[2:].tolist() == [[TEXT_CODE, NUMBER_CODE]] * 2


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


# Serials for 19 and 20 May 2026 and 25 May, the valuation date: a calendar of one day spills
# its four columns, the day as a serial, the code as text and the two flags as booleans, whose
# kinds the boolean code marks and whose slots hold 1 and 0.
def test_a_calendar_spills_four_columns_with_the_flags_as_booleans() -> None:
    valuation = bridge.call("_CreateValuationDate", [46167.0, 0.5])
    schedule = bridge.call(
        "_CreateExpirySchedule",
        [
            Cells.from_rows([["m26"], ["n26"]]),
            Cells.from_rows([[46161.0], [46162.0]]),
            MISSING,
            MISSING,
        ],
    )
    holidays = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46167.0]])])
    handle = bridge.call("_CreateCalendar", [valuation, "daily", schedule, holidays])
    kinds, slots, joined = read(handle)
    assert rows((kinds, slots, joined)) == [
        ["date", "prompt_contract", "is_business_day", "is_past"],
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
        "_CreateExpirySchedule",
        [
            Cells.from_rows([["m26"], ["n26"]]),
            Cells.from_rows([[46161.0], [46162.0]]),
            MISSING,
            MISSING,
        ],
    )
    holidays = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46167.0]])])
    headers = Cells.from_rows([["date", "settle"]])
    fixed = bridge.call(
        "_CreateMarketHistory",
        [
            bridge.call(
                "_CreateCalendar",
                [bridge.call("_CreateValuationDate", [46163.0, 0.5]), "daily", schedule, holidays],
            ),
            bridge.call(
                "_CreateDailyFixings", [headers, Cells.from_rows([[46162.0, 70.85]]), holidays]
            ),
        ],
    )
    kinds, slots, joined = read(fixed)
    assert rows((kinds, slots, joined)) == [
        ["date", "prompt_contract", "is_business_day", "is_past", "fixing_price"],
        ["datetime64[D]", "str", "bool", "bool", "float64"],
        [46162.0, "n26", 1.0, 1.0, 70.85],
    ]
    assert kinds[2].tolist() == [NUMBER_CODE, TEXT_CODE, BOOLEAN_CODE, BOOLEAN_CODE, NUMBER_CODE]
    unfixed = bridge.call(
        "_CreateMarketHistory",
        [
            bridge.call(
                "_CreateCalendar",
                [bridge.call("_CreateValuationDate", [46162.0, 0.5]), "daily", schedule, holidays],
            ),
            bridge.call(
                "_CreateDailyFixings", [headers, Cells.from_rows([[46161.0, 70.0]]), holidays]
            ),
        ],
    )
    kinds, slots, joined = read(unfixed)
    assert rows((kinds, slots, joined))[2] == [46162.0, "n26", 1.0, 0.0, "unfixed"]
    assert kinds[2].tolist() == [NUMBER_CODE, TEXT_CODE, BOOLEAN_CODE, BOOLEAN_CODE, TEXT_CODE]


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


# Serials for 19 and 20 May 2026: a market over a one-day calendar valued on its day, with a
# fixing on the 19th, before it, and one quote, spills the calendar's four columns and price, the
# quote a number on the open day; with the day a holiday, the same market shows closed, text, and
# the one quote is still required.
def test_a_market_spills_the_calendar_and_a_price_by_kind() -> None:
    schedule = bridge.call(
        "_CreateExpirySchedule",
        [
            Cells.from_rows([["m26"], ["n26"]]),
            Cells.from_rows([[46161.0], [46162.0]]),
            MISSING,
            MISSING,
        ],
    )
    headers = Cells.from_rows([["date", "settle"]])
    valuation = bridge.call("_CreateValuationDate", [46162.0, 0.5])
    quote = bridge.call("_CreatePriceVector", [72.10])
    for holiday, flag, cell, kind in (
        (46167.0, 1.0, 72.10, NUMBER_CODE),
        (46162.0, 0.0, "closed", TEXT_CODE),
    ):
        holidays = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[holiday]])])
        calendar = bridge.call("_CreateCalendar", [valuation, "daily", schedule, holidays])
        fixings = bridge.call(
            "_CreateDailyFixings", [headers, Cells.from_rows([[46161.0, 70.0]]), holidays]
        )
        history = bridge.call("_CreateMarketHistory", [calendar, fixings])
        kinds, slots, joined = read(bridge.call("_CreateMarket", [history, quote]))
        assert rows((kinds, slots, joined)) == [
            ["date", "prompt_contract", "is_business_day", "is_past", "price"],
            ["datetime64[D]", "str", "bool", "bool", "float64"],
            [46162.0, "n26", flag, 0.0, cell],
        ]
        assert kinds[2].tolist() == [NUMBER_CODE, TEXT_CODE, BOOLEAN_CODE, BOOLEAN_CODE, kind]


# Serials for 18 to 23 May 2026: three contracts two days apart, each published the day after
# it expires, over a four-day calendar with the Thursday a holiday. Valued on that Thursday with
# n26's fixing supplied, n26 has expired: both of its days show the fixing in the history and
# the market alike, a number each; q26's two days show unfixed in the history and, with q26's one
# quote, the quote in the market, the holiday included. Valued on n26's expiry day instead, with
# only the anchor's fixing supplied, which is ignored, every day is unfixed in the history and
# the market shows each day its contract's quote, two quotes being required.
def test_a_monthly_history_and_market_spill_a_price_on_every_day_by_kind() -> None:
    schedule = bridge.call(
        "_CreateExpirySchedule",
        [
            Cells.from_rows([["m26"], ["n26"], ["q26"]]),
            Cells.from_rows([[46160.0], [46162.0], [46164.0]]),
            MISSING,
            Cells.from_rows([[46161.0], [46163.0], [46165.0]]),
        ],
    )
    holidays = bridge.call("_CreateHolidayCalendar", [Cells.from_rows([[46163.0]])])
    unfixed = ["unfixed"] * 4
    for as_of, published, price, quotes, past, in_history, in_market in (
        (
            46163.0,
            46163.0,
            2.95,
            [[3.10]],
            [1.0, 1.0, 0.0, 0.0],
            [2.95, 2.95, *unfixed[2:]],
            [2.95, 2.95, 3.10, 3.10],
        ),
        (
            46162.0,
            46161.0,
            1.0,
            [[2.9], [3.10]],
            [1.0, 0.0, 0.0, 0.0],
            unfixed,
            [2.9, 2.9, 3.10, 3.10],
        ),
    ):
        valuation = bridge.call("_CreateValuationDate", [as_of, 0.5])
        calendar = bridge.call("_CreateCalendar", [valuation, "monthly", schedule, holidays])
        fixings = bridge.call(
            "_CreateMonthlyFixings",
            [Cells.from_rows([[published]]), Cells.from_rows([[price]]), schedule],
        )
        history = bridge.call("_CreateMarketHistory", [calendar, fixings])
        kinds, slots, joined = read(history)
        body = rows((kinds, slots, joined))
        assert body[:2] == [
            ["date", "prompt_contract", "is_business_day", "is_past", "fixing_price"],
            ["datetime64[D]", "str", "bool", "bool", "float64"],
        ]
        assert body[2:] == [
            [46161.0, "n26", 1.0, past[0], in_history[0]],
            [46162.0, "n26", 1.0, past[1], in_history[1]],
            [46163.0, "q26", 0.0, past[2], in_history[2]],
            [46164.0, "q26", 1.0, past[3], in_history[3]],
        ]
        assert kinds[2:, 4].tolist() == [
            TEXT_CODE if cell == "unfixed" else NUMBER_CODE for cell in in_history
        ]
        quote = bridge.call("_CreatePriceVector", [Cells.from_rows(quotes)])
        kinds, slots, joined = read(bridge.call("_CreateMarket", [history, quote]))
        body = rows((kinds, slots, joined))
        assert body[1][4] == "float64"
        assert [row[:4] for row in body[2:]] == [
            [46161.0, "n26", 1.0, past[0]],
            [46162.0, "n26", 1.0, past[1]],
            [46163.0, "q26", 0.0, past[2]],
            [46164.0, "q26", 1.0, past[3]],
        ]
        assert [row[4] for row in body[2:]] == in_market
        assert kinds[2:, 4].tolist() == [NUMBER_CODE] * 4


# Four prices selected without a header, a zero and a negative among them and the first
# repeated: the spill puts the header and the type over them, each price a number in its place.
def test_a_price_vector_spills_one_column_of_prices_under_two_heading_rows() -> None:
    handle = bridge.call("_CreatePriceVector", [Cells.from_rows([[74.25], [0.0], [-0.5], [74.25]])])
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
        Calendar,
        ValuationDate,
        DiscountCurve,
        ExpirySchedule,
        HolidayCalendar,
        IndexConventions,
        ContractSpecifications,
        PublicationSchedule,
        DeliverySchedule,
        DailyFixings,
        MonthlyFixings,
        MarketHistory,
        PriceVector,
        Market,
    } <= set(shown.registry)


# --- the market's daily view, for any calendar -------------------------------------


# For any history of two to eight contracts, any holidays and any valuation day inside its
# calendar, with the quotes it requires: every row of the calendar's own spill stands, and the
# fifth cell is the day's fixing where the day is past and open, its prompt contract's quote
# where it is open and not past, and the word closed where the market is shut; no cell is
# unfixed, and no past day reads a quote.
@settings(deadline=None)
@given(data=st.data())
def test_every_day_of_a_market_shows_its_fixing_its_prompts_quote_or_closed(
    data: st.DataObject,
) -> None:
    history = any_history(data)
    calendar = history.calendar
    first = int(calendar.prompt[calendar.dates == calendar.valuation_date.as_of][0])
    quotes = a_vector(*(100.0 + i for i in range(len(calendar.expiry_schedule.codes) - first)))
    made = market(history, quotes)
    table = shown(made)
    body = rows((table.kinds, table.numeric_slots, "\0".join(table.texts)))[2:]
    days = shown(calendar)
    assert [row[:4] for row in body] == rows(
        (days.kinds, days.numeric_slots, "\0".join(days.texts))
    )[2:]
    fixed = dict(zip(history.fixed_rows.tolist(), history.fixing_prices.tolist(), strict=True))
    for row, (shown_row, open_, past, prompt) in enumerate(
        zip(body, calendar.is_business_day, calendar.is_past, calendar.prompt, strict=True)
    ):
        if not open_:
            assert shown_row[4] == "closed"
        elif past:
            assert shown_row[4] == fixed[row]
        else:
            assert shown_row[4] == float(quotes.prices[int(prompt) - first])
    assert "unfixed" not in table.texts


# For any monthly history valued inside its calendar, with the fixings its expired contracts
# require and the quotes the rest require: every day of an expired contract shows its fixing in
# the history and the market alike, every other day shows unfixed in the history and its
# contract's quote in the market, weekends and holidays the same as open days, and no day is
# closed in either.
@settings(deadline=None)
@given(data=st.data())
def test_every_day_of_a_monthly_market_shows_its_contracts_fixing_or_quote(
    data: st.DataObject,
) -> None:
    history = any_monthly_history(data)
    calendar = history.calendar
    assume(calendar.valuation_date.as_of <= calendar.dates[-1])
    first = int(calendar.prompt[calendar.dates == calendar.valuation_date.as_of][0])
    quotes = a_vector(*(100.0 + i for i in range(len(calendar.expiry_schedule.codes) - first)))
    made = market(history, quotes)
    fixed = dict(zip(history.fixed_rows.tolist(), history.fixing_prices.tolist(), strict=True))
    fixings, prices = shown(history), shown(made)
    history_rows = rows((fixings.kinds, fixings.numeric_slots, "\0".join(fixings.texts)))[2:]
    market_rows = rows((prices.kinds, prices.numeric_slots, "\0".join(prices.texts)))[2:]
    for row, (shown_fixing, shown_price, prompt) in enumerate(
        zip(history_rows, market_rows, calendar.prompt, strict=True)
    ):
        assert shown_fixing[:4] == shown_price[:4]
        if row in fixed:
            assert shown_fixing[4] == fixed[row] and shown_price[4] == fixed[row]
        else:
            assert shown_fixing[4] == "unfixed"
            assert shown_price[4] == float(quotes.prices[int(prompt) - first])
    assert "closed" not in fixings.texts and "closed" not in prices.texts
