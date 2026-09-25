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
    for name, description, arguments, hidden in bridge.function_specs()
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


def test_the_schedule_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateExpirySchedule"]
    assert not hidden
    assert description == (
        "Creates an expiry schedule from the contract codes of one index, their expiry dates and, "
        "where given, the dates their settles are published, and shows its handle, the text other "
        "formulas take as the schedule."
    )
    # The third and fourth arguments may be left out with nothing in their place: brackets, and
    # each line alone.
    assert arguments == [
        (
            "future_code",
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
        (
            "[publication_date]",
            "The column of dates each contract's settle is published, beside the codes, such as "
            "D2:D7, one per code.",
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
        "measured in, and shows its handle, the text other formulas take as the conventions."
    )
    assert arguments == [
        (
            "quote_currency_unit",
            "The currency unit a price of the index is quoted in, such as USD.",
        ),
        (
            "quote_quantity_unit",
            "The quantity unit a price of the index is quoted per, such as BBL for USD per barrel.",
        ),
        ("currency_unit", "The currency unit the index settles in, such as USD."),
        ("quantity_type", "What a quantity of the index measures, such as volume."),
        ("quantity_unit", "The unit a quantity of the index is stated in, such as BBL."),
    ]


def test_the_specifications_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateContractSpecifications"]
    assert not hidden
    assert description == (
        "Creates the contract specifications of one index, the name, lot size and fees per lot of "
        "each contract it trades as, and shows its handle, the text other formulas take as the "
        "specifications."
    )
    assert arguments == [
        (
            "header_row",
            "The header cells of your contract table, such as A1:D1, reading name, lot_size, "
            "brokerage_rate_per_lot and clearing_rate_per_lot in any order.",
        ),
        (
            "table",
            "The rows under the headers, such as A2:D3: one contract per row, its name, lot size "
            "and the two fees per lot, each name once.",
        ),
    ]


def test_the_daily_fixings_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateDailyFixings"]
    assert not hidden
    assert description == (
        "Creates the daily fixings of one index from the days it fixed and their settles, "
        "checked against its market's holiday calendar, and shows its handle, the text other "
        "formulas take as the fixings."
    )
    assert arguments == [
        (
            "header_row",
            "The header cells of your fixings table, such as A1:B1, reading date and settle in "
            "either order.",
        ),
        (
            "table",
            "The rows under the headers, such as A2:B5: one fixing per row, its date and settle, "
            "one for every business day from the first to the last.",
        ),
        (
            "holiday_calendar",
            "The market's holiday-calendar handle: the cell showing _CreateHolidayCalendar's "
            "result, such as D2, or a name for it.",
        ),
    ]


def test_the_iferc_fixings_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateIfercFixings"]
    assert not hidden
    assert description == (
        "Creates the IFERC fixings of one index from the contract months whose index has been "
        "published and the index printed for each, and shows its handle, the text other "
        "formulas take as the fixings."
    )
    assert arguments == [
        (
            "contract_code",
            "The column of contract codes, such as A2:A5 holding F26 to J26, one per month "
            "published.",
        ),
        (
            "price",
            "The column of published indices beside the codes, such as B2:B5, one per code.",
        ),
    ]


def test_the_price_vector_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreatePriceVector"]
    assert not hidden
    assert description == (
        "Creates a price vector from one column of prices and shows its handle, the text other "
        "formulas take as the price vector."
    )
    assert arguments == [
        ("prices", "The column of futures prices, such as B2:B101, without a header."),
    ]


def test_the_market_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateMarket"]
    assert not hidden
    assert description == (
        "Creates the daily market of one index from its history and current futures prices and "
        "shows its handle, the text other formulas take as the market."
    )
    assert arguments == [
        (
            "market_history",
            "The market-history handle: the cell showing _CreateMarketHistory's result, such as "
            "B10, or a name for it.",
        ),
        (
            "price_vector",
            "The price-vector handle from _CreatePriceVector, such as B12, with prices in "
            "schedule order from the valuation day's prompt through the last contract.",
        ),
    ]


def test_the_calendar_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateCalendar"]
    assert not hidden
    assert description == (
        "Creates the calendar of one index, every day after its first contract's expiry to its "
        "last, with the contract prompt on each, whether the market is open and whether the day "
        "is past, and shows its handle, the text other formulas take as the calendar."
    )
    assert arguments == [
        (
            "valuation_date",
            "The valuation-date handle: the cell showing _CreateValuationDate's result, such as "
            "B2, or a name for it.",
        ),
        (
            "expiry_schedule",
            "The index's expiry-schedule handle: the cell showing _CreateExpirySchedule's "
            "result, such as B8, or a name for it, two contracts or more.",
        ),
        (
            "holiday_calendar",
            "The market's holiday-calendar handle: the cell showing _CreateHolidayCalendar's "
            "result, such as B12, or a name for it.",
        ),
    ]


def test_the_market_history_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateMarketHistory"]
    assert not hidden
    assert description == (
        "Creates the market history of one index, its calendar with the settle fixed on each "
        "past business day, and shows its handle, the text other formulas take as the history."
    )
    assert arguments == [
        (
            "calendar",
            "The index's calendar handle: the cell showing _CreateCalendar's result, such as B7, "
            "or a name for it.",
        ),
        (
            "daily_fixings",
            "The index's daily-fixings handle: the cell showing the result of "
            "_CreateDailyFixings, such as B10, or a name for it, with a fixing on every past "
            "business day of the calendar.",
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
        for name, description, arguments, hidden in bridge.function_specs()
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
        for name, description, arguments, hidden in bridge.function_specs()
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
