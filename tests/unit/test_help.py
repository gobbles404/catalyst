"""Function and argument help: the words beside each declaration, as Excel is told them."""

from typing import Annotated, cast

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import (
    Date,
    DateColumn,
    MixedArray,
    NumberColumn,
    excel_function,
    register,
)
from goosedove.excel.probes import probe

SPECS = {
    name: (description, arguments, hidden)
    for name, description, arguments, hidden, _ in bridge.function_specs()
}


# --- the listed functions, exactly: this is the text the desk reads ----------------------


def test_the_valuation_date_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateValuationDate"]
    assert not hidden
    # A docstring may wrap in the code; its lines are joined into one for the sheet.
    assert description == (
        "Creates a valuation date and shows its handle, the text other formulas take as the "
        "valuation date."
    )
    assert arguments == [
        ("as_of", "The valuation date, a date cell such as 11-Sep-2026, with no time of day."),
        (
            "day_fraction_elapsed",
            "How far through as_of: 0 at the start of the day, 0.5 at midday, 1 at the end.",
        ),
    ]


def test_the_curve_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateDiscountCurve"]
    assert not hidden
    assert description == (
        "Creates a discount curve from anchor dates and their discount factors, every day "
        "between filled in, and shows its handle, the text other formulas take as the curve."
    )
    assert arguments == [
        (
            "header_row",
            "The header cells of your curve table, such as A1:B1, reading date and "
            "discount_factor in either order.",
        ),
        (
            "table",
            "The rows under the headers, such as A2:B12: one anchor per row, its date and "
            "discount factor, dates increasing from the valuation date at 1, the factors never "
            "rising.",
        ),
    ]


def test_the_handle_reader_explains_itself() -> None:
    description, arguments, hidden = SPECS["util_ReadHandle"]
    assert not hidden
    assert description == (
        "Reads the object behind a handle and spills it as a table: its headers, a row of "
        "types, then one row per element."
    )
    assert arguments == [
        ("handle", "The cell showing any creator's result, such as B5, or a name for it."),
    ]


def test_the_prompt_reader_explains_itself() -> None:
    description, arguments, hidden = SPECS["util_ReadPrompt"]
    assert not hidden
    assert description == (
        "Reads the contract code for the first price expected in the calendar's market price "
        "vector."
    )
    assert arguments == [
        (
            "calendar",
            "The calendar handle: the cell showing _CreateCalendar's result, such as B5, or a "
            "name for it.",
        ),
    ]


def test_the_two_text_helpers_explain_themselves() -> None:
    line = (
        "One contract code, a month letter and a two-digit year such as F26, typed or in a cell "
        "such as A2."
    )
    description, arguments, hidden = SPECS["util_NextFut"]
    assert not hidden
    assert description == (
        "Gives the next contract in the monthly sequence, G26 after F26 and F27 after Z26, "
        "spelled as the code given."
    )
    assert arguments == [("contract", line)]
    description, arguments, hidden = SPECS["util_FutToCme"]
    assert not hidden
    assert description == (
        "Gives the contract month as CME's data feeds spell it, the year then the month, 202601 "
        "for F26."
    )
    assert arguments == [("contract", line)]


def test_the_two_date_helpers_explain_themselves() -> None:
    description, arguments, hidden = SPECS["util_DateToFut"]
    assert not hidden
    assert description == (
        "Gives the contract code of the month a day falls in, F26 for any day of January 2026."
    )
    assert arguments == [
        ("date", "One day, such as A2 or DATE(2026,1,15): any day of the contract's month."),
    ]
    description, arguments, hidden = SPECS["util_FutToDate"]
    assert not hidden
    assert description == "Gives the first day of a contract's month as a date, 1-Jan-2026 for F26."
    assert arguments == [
        (
            "contract",
            "One contract code, a month letter and a two-digit year such as F26, typed or in a "
            "cell such as A2.",
        ),
    ]


def test_the_two_period_functions_explain_themselves() -> None:
    line = (
        "One contract or strip label, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28, typed or in "
        "a cell such as A2."
    )
    description, arguments, hidden = SPECS["util_StartDate"]
    assert not hidden
    assert description == (
        "Gives the first calendar day of a contract or strip, 1-Jan-2026 for F26, 1-Nov-2029 for "
        "W29 and the first day of the left label of F26-Z28."
    )
    assert arguments == [("period", line)]
    description, arguments, hidden = SPECS["util_EndDate"]
    assert not hidden
    assert description == (
        "Gives the last calendar day of a contract or strip, 31-Jan-2026 for F26, 31-Mar-2030 for "
        "W29 and the last day of the right label of F26-Z28."
    )
    assert arguments == [("period", line)]


def test_the_futures_schedule_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateFuturesSchedule"]
    assert not hidden
    assert description == (
        "Creates the futures schedule of one index from its contract codes, the day each future "
        "expires and, where given, the day its option expires, and shows its handle, the text "
        "other formulas take as the schedule."
    )
    # The third argument may be left out with nothing in its place: brackets, and its line alone.
    assert arguments == [
        (
            "contract_code",
            "The column of contract codes, such as A2:A7 holding m26 to X26, one per contract.",
        ),
        (
            "future_expiry",
            "The column of future expiry dates beside the codes, such as B2:B7, one per code.",
        ),
        (
            "[option_expiry]",
            "The column of option expiry dates beside the codes, such as C2:C7, one per code.",
        ),
    ]


def test_the_holiday_calendar_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateHolidayCalendar"]
    assert not hidden
    assert description == (
        "Creates a holiday calendar from the days one market is closed and shows its handle, "
        "the text other formulas take as the calendar."
    )
    assert arguments == [
        (
            "holiday",
            "The column of dates the market is closed, such as A2:A11, one holiday per row.",
        ),
    ]


def test_the_iferc_schedule_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateIfercSchedule"]
    assert not hidden
    assert description == (
        "Creates an IFERC schedule from the contract months of one index, the day each month's "
        "future stops trading and the day its index is published, and shows its handle, the "
        "text other formulas take as the schedule."
    )
    assert arguments == [
        (
            "contract_code",
            "The column of contract codes, such as A2:A4 holding V26 to Z26, one per contract "
            "month.",
        ),
        (
            "last_trading_date",
            "The column of last trading dates beside the codes, such as B2:B4, one per code.",
        ),
        (
            "publication_date",
            "The column of dates the index is published, beside the codes, such as C2:C4, one "
            "per code.",
        ),
    ]


def test_the_gas_daily_schedule_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateGasDailySchedule"]
    assert not hidden
    assert description == (
        "Creates a Gas Daily schedule from the contract months of one index and the first and "
        "last day of gas each month's price covers, and shows its handle, the text other "
        "formulas take as the schedule."
    )
    assert arguments == [
        (
            "contract_code",
            "The column of contract codes, such as A2:A4 holding U26 to X26, one per contract "
            "month.",
        ),
        (
            "first_date",
            "The column of each month's first day of gas, beside the codes, such as B2:B4, one "
            "per code.",
        ),
        (
            "last_date",
            "The column of each month's last day of gas, beside the codes, such as C2:C4, one "
            "per code.",
        ),
    ]


def test_the_conventions_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateIndexConventions"]
    assert not hidden
    assert description == (
        "Creates the index conventions of one index, the units it is quoted, settled and "
        "measured in, checked against the library's unit tables, and shows its handle, the text "
        "other formulas take as the conventions."
    )
    units = (
        "GAL, BBL, L or M3 for VOLUME; KG, LB, MT, ST, LT, G, OZT or CWT_US for MASS; MMBTU, BTU, "
        "THERM, GJ, MWH or KWH for ENERGY."
    )
    assert arguments == [
        (
            "quote_currency_unit",
            "The currency unit a price of the index is quoted in: USD or CENT.",
        ),
        (
            "quote_quantity_unit",
            "The quantity unit a price of the index is quoted per, a unit of the quantity type: "
            + units,
        ),
        ("currency_unit", "The currency unit the index settles in: USD or CENT."),
        ("quantity_type", "What a quantity of the index measures: VOLUME, MASS or ENERGY."),
        (
            "quantity_unit",
            "The unit a quantity of the index is stated in, a unit of the quantity type: " + units,
        ),
    ]


def test_the_specifications_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateContractSpecifications"]
    assert not hidden
    assert description == (
        "Creates the contract specifications of one index, the desk's words for a quantity of it, "
        "each with its lot size, the lot's unit and the fees per lot, and shows its handle, the "
        "text other formulas take as the specifications."
    )
    assert arguments == [
        (
            "header_row",
            "The header cells of your specifications table, such as A1:E1, reading name, lot_size, "
            "lot_unit, brokerage_rate_per_lot and clearing_rate_per_lot in any order.",
        ),
        (
            "table",
            "The rows under the headers, such as A2:E4: one row per word for a quantity of the "
            "index, a contract or a bare unit, its name, a whole lot size of 1 or more, the unit "
            "that lot size is in and the two fees per lot, 0 or more, each name once.",
        ),
    ]


def test_the_futures_fixings_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateFuturesFixings"]
    assert not hidden
    assert description == (
        "Creates the futures fixings of one index from the days it fixed and their settles, "
        "checked against the holiday calendar of its index, and shows its handle, the text "
        "other formulas take as the fixings."
    )
    assert arguments == [
        (
            "date",
            "The column of days the index fixed, newest first, such as A2:A5 holding 6-May-2026 "
            "down to 1-May-2026, one for every business day between them.",
        ),
        ("settle", "The column of settles beside the days, such as B2:B5, one per day."),
        (
            "index",
            "The index handle: the cell showing _CreateIndex's result, such as D3, or a name for "
            "it; a futures index, whose holiday calendar the days are checked against.",
        ),
    ]


def test_the_iferc_fixings_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateIfercFixings"]
    assert not hidden
    assert description == (
        "Creates the IFERC fixings of one index from the contract months whose index has been "
        "published and the index printed for each, checked against the months of its index, and "
        "shows its handle, the text other formulas take as the fixings."
    )
    assert arguments == [
        (
            "contract_code",
            "The column of contract codes, such as A2:A5 holding J26 down to F26, one per month "
            "published.",
        ),
        (
            "price",
            "The column of published indices beside the codes, such as B2:B5, one per code.",
        ),
        (
            "index",
            "The index handle: the cell showing _CreateIndex's result, such as F3, or a name for "
            "it; an IFERC index, whose months the codes are checked against.",
        ),
    ]


def test_the_gas_daily_fixings_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateGasDailyFixings"]
    assert not hidden
    assert description == (
        "Creates the Gas Daily fixings of one index from the days gas flowed and the midpoint "
        "printed for each, one for every calendar day between the newest and the oldest, and shows "
        "its handle, the text other formulas take as the fixings."
    )
    assert arguments == [
        (
            "flow_date",
            "The column of flow days, newest first, such as A2:A7 holding 9-Sep-2026 down to "
            "4-Sep-2026, one for every calendar day between them.",
        ),
        (
            "price",
            "The column of midpoints beside the flow days, such as B2:B7, one per day.",
        ),
        (
            "index",
            "The index handle: the cell showing _CreateIndex's result, such as C4, or a name for "
            "it; a Gas Daily index, the one these fixings belong to.",
        ),
    ]


def test_the_price_vector_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreatePriceVector"]
    assert not hidden
    assert description == (
        "Creates a price vector of one index from the index's name and one column of prices, "
        "and shows its handle, the text other formulas take as the price vector."
    )
    assert arguments == [
        (
            "index_name",
            'The name the index was created with, such as A1 or "WTI NYMEX", typed as '
            "_CreateIndex was given it; the market checks it against its history's index.",
        ),
        ("prices", "The column of futures prices, such as B2:B101, without a header."),
    ]


def test_the_market_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateMarket"]
    assert not hidden
    assert description == (
        "Creates the market of one index from its history and the quotes of the periods still "
        "to come, and shows its handle, the text other formulas take as the market."
    )
    assert arguments == [
        (
            "market_history",
            "The market-history handle: the cell showing _CreateMarketHistory's result, such as "
            "B10, or a name for it.",
        ),
        (
            "price_vector",
            "The price-vector handle from _CreatePriceVector, such as B12, named for this "
            "index, with one quote per contract in schedule order, starting at the first period "
            "not yet fixed and stopping at or before the last contract.",
        ),
    ]


def test_the_index_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateIndex"]
    assert not hidden
    assert description == (
        "Creates the index behind one reference price, its name with its schedule, conventions, "
        "contract specifications and, for a futures index, holiday calendar, and shows its "
        "handle, the text other formulas take as the index."
    )
    assert arguments == [
        (
            "name",
            "The index's name as the desk calls it, such as Henry Hub NYMEX, kept as typed.",
        ),
        (
            "schedule",
            "The index's schedule handle, futures, IFERC or Gas Daily: the cell showing its "
            "creator's result, such as B2, or a name for it.",
        ),
        (
            "index_conventions",
            "The index-conventions handle: the cell showing _CreateIndexConventions's result, "
            "such as B4, or a name for it.",
        ),
        (
            "contract_specifications",
            "The contract-specifications handle: the cell showing "
            "_CreateContractSpecifications's result, such as B5, or a name for it.",
        ),
        (
            "[holiday_calendar]",
            "The market's holiday-calendar handle with a futures schedule: the cell showing "
            "_CreateHolidayCalendar's result, such as B3, or a name for it; left out for an "
            "IFERC or Gas Daily schedule.",
        ),
    ]


def test_the_calendar_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateCalendar"]
    assert not hidden
    assert description == (
        "Creates the calendar of one index, one row per day it prices, or per month for an "
        "index published monthly, each with its contract and whether it has fixed, and shows "
        "its handle, the text other formulas take as the calendar."
    )
    assert arguments == [
        (
            "valuation_date",
            "The valuation-date handle: the cell showing _CreateValuationDate's result, such as "
            "B2, or a name for it.",
        ),
        (
            "index",
            "The index handle: the cell showing _CreateIndex's result, such as B10, or a name "
            "for it; a futures index needs two contracts or more.",
        ),
    ]


def test_the_market_history_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateMarketHistory"]
    assert not hidden
    assert description == (
        "Creates the market history of one index, its calendar with the price fixed on each "
        "period that has fixed, from the fixings of the calendar's market, and shows its handle, "
        "the text other formulas take as the history."
    )
    assert arguments == [
        (
            "calendar",
            "The index's calendar handle: the cell showing _CreateCalendar's result, such as B7, "
            "or a name for it.",
        ),
        (
            "fixings",
            "The index's fixings handle, futures, IFERC or Gas Daily as the index is: the cell "
            "showing its creator's result, such as B10, or a name for it, made over the "
            "calendar's own index cell, with a price for every period of the calendar that has "
            "fixed.",
        ),
    ]


def test_the_catalog_list_explains_itself() -> None:
    description, arguments, hidden = SPECS["_ListInstruments"]
    assert not hidden
    assert description == "Lists the library-defined instruments and their descriptions."
    assert arguments == []


def test_the_catalog_show_explains_itself() -> None:
    description, arguments, hidden = SPECS["_ShowInstrument"]
    assert not hidden
    assert description == "Shows an instrument's fields, requirements, types and rules."
    assert arguments == [
        ("instrument", "One instrument name from _ListInstruments, such as future."),
    ]


def test_the_template_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateTradeTemplate"]
    assert not hidden
    assert description == (
        "Creates shared defaults for an instrument and shows their handle, the text other "
        "formulas take as the trade template."
    )
    assert arguments == [
        ("instrument", "One instrument name from _ListInstruments, such as future."),
        (
            "fields",
            "The field-name cells in one row, such as A1:B1, using names shown by _ShowInstrument.",
        ),
        ("values", "The values in one row beneath those fields, such as A2:B2."),
    ]


def test_the_trades_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateTrades"]
    assert not hidden
    assert description == (
        "Creates a batch of trades on one index from a template's shared fields and a ticket's "
        "rows, each contract code resolved against the index's schedule, and shows its handle, "
        "the text other formulas take as the trades."
    )
    assert arguments == [
        (
            "index",
            "The index handle: the cell showing _CreateIndex's result, such as B6, or a name for "
            "it, the one index every trade of the batch is on.",
        ),
        (
            "fields",
            "The ticket's header cells in one row, such as A4:E4, using names shown by "
            "_ShowInstrument and none the template supplies.",
        ),
        (
            "trade_rows",
            "The rows under the headers, such as A5:E9, one trade per row, a repeated row a "
            "second trade.",
        ),
        (
            "template",
            "The trade-template handle: the cell showing _CreateTradeTemplate's result, such as "
            "B2, or a name for it, which selects the instrument and supplies the shared fields.",
        ),
    ]


# --- what registration derives from the signature ---------------------------------------


def test_an_optional_argument_is_bracketed_and_says_what_omission_takes() -> None:
    _, arguments, hidden = SPECS["Times"]
    assert hidden
    assert arguments == [
        ("x", "One number to multiply."),
        ("[factor]", "One multiplier. 1 when omitted."),
    ]


def test_a_hidden_function_may_say_nothing() -> None:
    _, arguments, _ = SPECS["Add"]
    assert arguments == [("a", ""), ("b", "")]


# A date and a column default as the seam takes them: a serial, and one number for a one-cell range.
A_SERIAL = cast(Date, 46164.0)
ONE_WEIGHT = cast(NumberColumn, 2.0)
A_CELL = cast(MixedArray, 5.0)


@probe
def Defaults(
    number: Annotated[float, "A number."] = 1.0,
    fraction: Annotated[float, "A fraction."] = 0.05,
    whole: Annotated[int, "A whole number."] = 3,
    label: Annotated[str, "Text."] = "WTI",
    flag: Annotated[bool, "A flag."] = True,
    day: Annotated[Date, "A date."] = A_SERIAL,
    weights: Annotated[NumberColumn, "Weights."] = ONE_WEIGHT,
) -> float:
    return number


def test_a_default_is_shown_in_the_words_of_the_sheet() -> None:
    _, arguments, _ = {
        name: (description, arguments, hidden)
        for name, description, arguments, hidden, _ in bridge.function_specs()
    }["Defaults"]
    assert arguments == [
        ("[number]", "A number. 1 when omitted."),
        ("[fraction]", "A fraction. 0.05 when omitted."),
        ("[whole]", "A whole number. 3 when omitted."),
        ("[label]", 'Text. "WTI" when omitted.'),
        ("[flag]", "A flag. TRUE when omitted."),
        ("[day]", "A date. 2026-05-22 when omitted."),
        ("[weights]", "Weights. 2 when omitted."),
    ]


# An argument that may be left out with nothing in its place has nothing to name after its
# sentence: the sentence stands alone, and the brackets say it may be left out.
@probe
def LeftOut(
    x: Annotated[float, "A number."],
    dates: Annotated[DateColumn | None, "A column of dates."] = None,
) -> float:
    return x


def test_an_argument_that_may_be_left_out_shows_its_sentence_alone() -> None:
    _, arguments, _ = {
        name: (description, arguments, hidden)
        for name, description, arguments, hidden, _ in bridge.function_specs()
    }["LeftOut"]
    assert arguments == [("x", "A number."), ("[dates]", "A column of dates.")]


# --- what registration refuses, on a function Excel lists ----------------------------------


def test_a_listed_function_without_a_docstring_refuses_to_register() -> None:
    def Mute(x: Annotated[float, "A number."]) -> float:
        return x

    with pytest.raises(TypeError, match="Mute has no docstring; a function Excel lists says what"):
        excel_function(Mute)
    assert register(Mute, hidden=True) is Mute


def test_a_listed_argument_without_help_refuses_to_register() -> None:
    def Quiet(x: float) -> float:
        """Says nothing of x."""
        return x

    with pytest.raises(TypeError, match="Quiet: x has no help; a function Excel lists says what"):
        excel_function(Quiet)
    assert register(Quiet, hidden=True) is Quiet


# What registration adds for an optional argument follows the authored sentence, so the
# sentence ends with a period, listed or hidden.
def test_help_that_does_not_end_with_a_period_refuses_to_register() -> None:
    def Trailing(x: Annotated[float, "One number"]) -> float:
        """Says something of x, unfinished."""
        return x

    with pytest.raises(TypeError, match="Trailing: x's help does not end with a period"):
        excel_function(Trailing)
    with pytest.raises(TypeError, match="Trailing: x's help does not end with a period"):
        register(Trailing, hidden=True)


def test_anything_but_one_text_beside_the_type_refuses_to_register() -> None:
    def Loud(x: Annotated[float, "a", "b"]) -> float:
        """Two texts."""
        return x

    def Numbered(x: Annotated[float, 3]) -> float:
        """A number instead of a text."""
        return x

    with pytest.raises(TypeError, match=r"Loud: x declares .*, expected one text beside the type"):
        excel_function(Loud)
    with pytest.raises(TypeError, match=r"Numbered: x declares .*, expected one text beside the"):
        excel_function(Numbered)


def test_help_longer_than_excel_shows_refuses_to_register() -> None:
    def Long(x: Annotated[float, "a" * 253 + "."]) -> float:
        """Too much to say of x."""
        return x

    def Wordy(x: Annotated[float, "A number."]) -> float:
        return x

    Wordy.__doc__ = "w" * 254
    with pytest.raises(TypeError, match="Long: x's help is 254 characters, expected at most 253"):
        excel_function(Long)
    with pytest.raises(TypeError, match="Wordy's description is 254 characters, expected at most"):
        excel_function(Wordy)


def test_a_default_the_help_cannot_show_refuses_to_register() -> None:
    def Shown(values: Annotated[MixedArray, "Cells."] = A_CELL) -> float:
        return 1.0

    with pytest.raises(
        TypeError, match=r"Shown: values defaults to .*, which the help cannot show"
    ):
        register(Shown, hidden=True)
