"""Function and argument help: the words beside each declaration, as Excel is told them."""

from typing import Annotated, cast

import pytest

from catalyst.excel import bridge
from catalyst.excel.bridge import (
    Date,
    DateColumn,
    MixedArray,
    NumberColumn,
    excel_function,
    register,
)
from catalyst_probes import probe

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
        "Creates a discount curve under its name from anchor dates and their discount factors, "
        "every day between filled in, and shows its handle, the text other formulas take as "
        "the curve."
    )
    assert arguments == [
        (
            "name",
            "The curve's name, text such as SOFR, exact and case-sensitive with no whitespace "
            "around it: what a trade's discount_curve_key will select and the reports will show.",
        ),
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


def test_the_curve_collector_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CollectDiscountCurves"]
    assert not hidden
    assert description == (
        "Collects named discount curves into one collection, each name once, the curves as "
        "they are and nothing of their factors combined, and shows its handle, the text other "
        "formulas take as the collection."
    )
    assert arguments == [
        (
            "curve_handles",
            "The curves to collect: a cell, a row or a column of cells showing "
            "_CreateDiscountCurve's or util_BumpDiscountCurve's results, such as B2:B3, each "
            "name once.",
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
        "One contract or strip label, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28, or "
        "its balance, BALZ26, typed or in a cell such as A2."
    )
    valuation = (
        "For a BAL label, the valuation-date handle whose day the balance starts on, such as B1 "
        "showing _CreateValuationDate's result; left out for any other label."
    )
    description, arguments, hidden = SPECS["util_StartDate"]
    assert not hidden
    assert description == (
        "Gives the first calendar day of a contract or strip, 1-Jan-2026 for F26, 1-Nov-2029 for "
        "W29 and the first day of the left label of F26-Z28; of its balance, the later of the "
        "valuation day and that first day."
    )
    assert arguments == [("period", line), ("[valuation_date]", valuation)]
    description, arguments, hidden = SPECS["util_EndDate"]
    assert not hidden
    assert description == (
        "Gives the last calendar day of a contract or strip, 31-Jan-2026 for F26, 31-Mar-2030 for "
        "W29 and the last day of the right label of F26-Z28; of its balance, the same last day, a "
        "period ended before the valuation day refused."
    )
    assert arguments == [("period", line), ("[valuation_date]", valuation)]


def test_the_date_shift_explains_itself() -> None:
    description, arguments, hidden = SPECS["util_ShiftDate"]
    assert not hidden
    assert description == (
        "Shifts a date by business days, calendar days or month ends, +1bd the next business day, "
        "-1bd the one before, +7cd a week on, +0em the month's last day, a chain such as "
        "+3em+25cd-1bd+1bd applied left to right, and shows the date."
    )
    assert arguments == [
        ("date", "The day to shift, such as A2 or DATE(2026,10,9)."),
        (
            "offset",
            "The shift as text: one or more of a sign, a whole count and bd, cd or em, such as "
            "+1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd, applied left to right, typed or in a "
            "cell such as B2.",
        ),
        (
            "[holiday_calendar]",
            "The holiday-calendar handle whose holidays business days skip, such as C2; left out "
            "for Monday to Friday with no holidays.",
        ),
    ]


def test_the_bump_explains_itself() -> None:
    description, arguments, hidden = SPECS["util_BumpDiscountCurve"]
    assert not hidden
    assert description == (
        "Bumps a discount curve by a parallel shift of its continuously compounded zero rates in "
        "basis points, every day's factor moved from its start, ACT/365F, under the curve's "
        "rules, and shows the new curve's handle, an ordinary curve for _EvaluateTrades."
    )
    assert arguments == [
        (
            "curve",
            "The curve handle: the cell showing _CreateDiscountCurve's or this function's result, "
            "such as B2, or a name for it.",
        ),
        (
            "bump_bps",
            "The parallel shift of the curve's zero rates in basis points, a signed number: 1 for "
            "one basis point up, -25 for twenty-five down, 0.5 for half a point; a number, not "
            "text.",
        ),
    ]


def test_the_interpolation_explains_itself() -> None:
    description, arguments, hidden = SPECS["util_InterpolateContracts"]
    assert not hidden
    assert description == (
        "Infers every monthly contract from the first anchor's month through the last's, each "
        "with the index's futures expiry and the price on the straight line between its anchors "
        "weighted by calendar days, and spills contract_code, future_expiry and price."
    )
    assert arguments == [
        (
            "index",
            "The index handle: the cell showing _CreateIndex's result, such as B9, or a name for "
            "it; a futures index, whose schedule has a futures expiry per contract.",
        ),
        (
            "anchor_contracts",
            "A column of at least two contract months in increasing order, each a code such as "
            "F26 or the month as CME spells it, 202601, as text, without a header, such as A2:A3.",
        ),
        (
            "anchor_prices",
            "A column of one price per anchor, in the same rows and the index's quote convention, "
            "without a header, such as B2:B3.",
        ),
    ]


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
    description, arguments, hidden = SPECS["_CombineHolidayCalendars"]
    assert not hidden
    assert description == (
        "Combines holiday calendars into one closed on every day any of them is closed, the days "
        "in order, once each, and shows its handle, an ordinary calendar for "
        "payment_holiday_calendar, util_ShiftDate or another combination."
    )
    assert arguments == [
        (
            "calendar_handles",
            "The calendars to combine: a cell, a row or a column of cells showing "
            "_CreateHolidayCalendar's or this function's results, such as B2:B3, every one read "
            "and a repeat read again.",
        )
    ]
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
        "Creates an IFERC schedule from the contract months of one index and the day each "
        "month's index is published, and shows its handle, the text other formulas take as the "
        "schedule."
    )
    assert arguments == [
        (
            "contract_code",
            "The column of contract codes, such as A2:A4 holding V26 to Z26, one per contract "
            "month.",
        ),
        (
            "publication_date",
            "The column of dates the index is published, beside the codes, such as B2:B4, one "
            "per code, the day each month is observed and the day its payment counts from.",
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
        "Creates the futures fixings of one index from the days it fixed and their settles, a "
        "column for each nearby contract, checked against the holiday calendar of its index, "
        "and shows its handle, the text other formulas take as the fixings."
    )
    assert arguments == [
        (
            "date",
            "The column of days the index fixed, newest first, such as A2:A5 holding 6-May-2026 "
            "down to 1-May-2026, one for every business day between them.",
        ),
        (
            "settle",
            "The settles beside the days, such as B2:B5, one row per day; a wider range, such "
            "as B2:C5, holds a column for each nearby contract, the prompt's first.",
        ),
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
        "published, newest first, and the index printed for each, checked against the months of "
        "its index, and shows its handle, the text other formulas take as the fixings."
    )
    assert arguments == [
        (
            "contract_code",
            "The column of contract codes, newest first, such as A2:A5 holding J26 down to F26, "
            "one per month published.",
        ),
        (
            "price",
            "The column of published indices beside the codes, such as B2:B5, one per code.",
        ),
        (
            "index",
            "The index handle: the cell showing _CreateIndex's result, such as F3, or a name for "
            "it; an IFERC index, whose months the codes are checked against and whose schedule "
            "says the day each printed.",
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
        "Creates the index behind one reference price from its name, a description, "
        "schedule, conventions, specifications, a futures index's holiday calendar and the lot "
        "its delta is reported in, and shows its handle, the text other formulas take as the "
        "index."
    )
    assert arguments == [
        (
            "name",
            "The index's name as the desk calls it, such as Henry Hub NYMEX, kept as typed.",
        ),
        (
            "display_name",
            "A description a reader who does not know the desk's short names would understand, "
            "such as Henry Hub natural gas - NYMEX, kept as typed and read for nothing else.",
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
        (
            "[reporting_lot]",
            "The name of the specification a batch's delta is reported in lots of, such as "
            "NYMEX NG, exactly as the specifications spell it; left out for an index that only "
            "builds markets and prices no trades.",
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
    assert description == (
        "Shows an instrument's fields, requirements, types and rules, for booking and quoting."
    )
    assert arguments == [
        ("instrument", "One instrument name from _ListInstruments, such as fixed_float."),
    ]


def test_the_template_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateTradeTemplate"]
    assert not hidden
    assert description == (
        "Creates shared defaults for an instrument and shows their handle, the text other "
        "formulas take as the trade template."
    )
    assert arguments == [
        ("instrument", "One instrument name from _ListInstruments, such as fixed_float."),
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
        "Creates a batch of trades on one index, or on a pair as two legs, from a template's "
        "shared fields and a ticket's rows, each contract code resolved against each index's "
        "schedule, and shows its handle, the text other formulas take as the trades."
    )
    assert arguments == [
        (
            "indexes",
            "The index handle, or a row or column of two for a pair: the cells showing "
            "_CreateIndex's results, such as I3 or I3:I4, or names for them, the first leg's "
            "index first.",
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
            "B3, or a name for it, which selects the instrument and supplies the shared fields.",
        ),
    ]


def test_the_preparation_explains_itself() -> None:
    description, arguments, hidden = SPECS["_PrepareTrades"]
    assert not hidden
    assert description == (
        "Prepares a batch of trades against its market histories, one per index, each observation "
        "whose day has passed fixed at that day's settle and each payment fallen due settled, and "
        "shows its handle, the text _EvaluateTrades takes as the prepared trades."
    )
    assert arguments == [
        (
            "trades",
            "The trades handle: the cell showing _CreateTrades's result, such as A10, or a name "
            "for it.",
        ),
        (
            "histories",
            "The market-history handle of the trades' index, or a row or column of one per index "
            "of a pair, such as I11 or I11:I12, each valued on the day the trades are prepared "
            "for.",
        ),
    ]


def test_the_evaluation_explains_itself() -> None:
    description, arguments, hidden = SPECS["_EvaluateTrades"]
    assert not hidden
    assert description == (
        "Evaluates prepared trades against their markets, one per index, live observations at "
        "quotes and fixed at settles, each bilateral payment discounted on its curve, into mark, "
        "cash, delta and DV01, and shows the results' handle, which the reports take."
    )
    assert arguments == [
        (
            "prepared",
            "The prepared-trades handle: the cell showing _PrepareTrades's result, such as A11, "
            "or a name for it.",
        ),
        (
            "markets",
            "The market handle over the history the trades were prepared against, or a row or "
            "column of one per index of a pair, such as I12 or I12:I13, each with the day's "
            "quotes.",
        ),
        (
            "[discount_curve_set]",
            "The collection handle for a bilateral batch: the cell showing "
            "_CollectDiscountCurves's result, such as I13, or a name for it, holding every curve "
            "the rows name by discount_curve_key, each starting on the valuation day; left out for "
            "a cleared batch.",
        ),
    ]


def test_the_quote_template_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateQuoteTemplate"]
    assert not hidden
    assert description == (
        "Creates the static terms of a quote under an instrument and shows their handle, the "
        "text _Quote takes as the quote template."
    )
    assert arguments == [
        (
            "instrument",
            "One instrument name from _ListInstruments; fixed_float, the one a quote prices.",
        ),
        (
            "fields",
            "The field-name cells in one row, such as A1:G1, using names _ShowInstrument marks "
            "quote_allowed.",
        ),
        ("values", "The values in one row beneath those fields, such as A2:G2."),
    ]


def test_the_quote_explains_itself() -> None:
    description, arguments, hidden = SPECS["_Quote"]
    assert not hidden
    assert description == (
        "Quotes one fixed price, flat or fit to curve, for a contract or strip on a market from "
        "a quote template's terms, fixings for the observations that have passed and the day's "
        "quotes for the rest, a flat bilateral price discounted on the template's curve."
    )
    assert arguments == [
        (
            "market",
            "The market handle: the cell showing _CreateMarket's result, such as I12, or a name "
            "for it, with the day's quotes over the history they follow.",
        ),
        (
            "contract_code",
            "The contract, strip or balance to quote, such as Z26, F27-G27, CAL27 or BALZ26, the "
            "balance from the market's valuation day, every month of it a contract of the "
            "market's schedule.",
        ),
        (
            "template",
            "The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as "
            "B3, or a name for it, which supplies the quote's terms.",
        ),
        (
            "pricing",
            "The price to quote, flat or ftc: flat is one fixed price for the whole period, each "
            "month weighed by its quantity and its payment's discount factor; ftc, fit to curve, "
            "is the months' own prices averaged by quantity alone.",
        ),
        (
            "[discount_curve_set]",
            "The collection handle for a bilateral quote, under either pricing: the cell showing "
            "_CollectDiscountCurves's result, such as I13, or a name for it, holding the curve "
            "the template names; left out for a cleared quote.",
        ),
    ]


def test_the_quote_by_dates_explains_itself() -> None:
    description, arguments, hidden = SPECS["_QuoteByDates"]
    assert not hidden
    assert description == (
        "Quotes one fixed price, flat or fit to curve, from start_date to end_date on a market "
        "under a quote template, one average over the window under onetime and a strip by the "
        "month under monthly, fixings for days passed and the day's quotes for the rest."
    )
    assert arguments == [
        (
            "market",
            "The market handle: the cell showing _CreateMarket's result, such as I12, or a name "
            "for it, with the day's quotes over the history they follow.",
        ),
        ("start_date", "The first day the quote covers, such as A2 or DATE(2026,5,26)."),
        (
            "end_date",
            "The last day it covers, inclusive, such as B2 or DATE(2026,6,25), on or after "
            "start_date.",
        ),
        (
            "template",
            "The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as "
            "B3, or a name for it, whose settlement_frequency makes the days one average or a "
            "strip by the month.",
        ),
        (
            "pricing",
            "The price to quote, flat or ftc: flat is one fixed price for the days, each "
            "component weighed by its quantity and its payment's discount factor; ftc, fit to "
            "curve, is the components' own prices averaged by quantity alone.",
        ),
        (
            "[discount_curve_set]",
            "The collection handle for a bilateral quote, under either pricing: the cell showing "
            "_CollectDiscountCurves's result, such as I13, or a name for it, holding the curve "
            "the template names; left out for a cleared quote.",
        ),
    ]


def test_the_cashflow_functions_explain_themselves() -> None:
    description, arguments, hidden = SPECS["_CreateCashflows"]
    assert not hidden
    assert description == (
        "Creates a batch of cashflows, known signed amounts in one currency each on its own "
        "payment date, from a template's shared fields and a ticket's rows, and shows its "
        "handle, the text _EvaluateCashflows takes as the cashflows."
    )
    assert arguments == [
        (
            "fields",
            "The ticket's header cells in one row, such as A4:E4, using names shown by "
            "_ShowInstrument for cashflow and none the template supplies.",
        ),
        (
            "cashflow_rows",
            "The rows under the headers, such as A5:E9, one payment per row, a repeated row a "
            "second payment.",
        ),
        (
            "template",
            "The trade-template handle: the cell showing _CreateTradeTemplate's result for the "
            "cashflow instrument, such as B3, or a name for it, which supplies the shared "
            "fields.",
        ),
    ]
    description, arguments, hidden = SPECS["_EvaluateCashflows"]
    assert not hidden
    assert description == (
        "Values a batch of cashflows on the valuation day: each unpaid payment discounted on "
        "the curve's factor for its day with its DV01, each paid one cash, and shows the "
        "results' handle, the text the reports and util_ReadHandle take."
    )
    assert arguments == [
        (
            "cashflows",
            "The cashflows handle: the cell showing _CreateCashflows's result, such as A10, or "
            "a name for it.",
        ),
        (
            "valuation_date",
            "The valuation-date handle: the cell showing _CreateValuationDate's result, such "
            "as B2, or a name for it; the day the unpaid payments are discounted to.",
        ),
        (
            "discount_curve",
            "The discount-curve handle: the cell showing _CreateDiscountCurve's result, such "
            "as B5, or a name for it, starting on the valuation day and covering every unpaid "
            "payment day.",
        ),
    ]


def test_the_two_reports_explain_themselves() -> None:
    results = (
        "results",
        "The results handle: the cell showing _EvaluateTrades's or _EvaluateCashflows's result, "
        "such as A12, or a name for it.",
    )
    description, arguments, hidden = SPECS["_ReportValues"]
    assert not hidden and arguments == [results]
    assert description == (
        "Reports the batch's values from its results: the mark and the cash under the route's "
        "labels, or under cashflow for a batch of cashflows, the currency and the valuation "
        "day, as evaluation stored them."
    )
    description, arguments, hidden = SPECS["_ReportRisk"]
    either = (
        "results",
        "The results handle, one evaluated batch's, a collection's or a batch of cashflows': "
        "the cell showing _EvaluateTrades's, _AggregateResults's or _EvaluateCashflows's "
        "result, such as A12, or a name for it.",
    )
    assert not hidden and arguments == [
        either,
        (
            "risk",
            "Which risk: nominal_delta, delta, dv01, cross_gamma or all, exactly so; the deltas "
            "and the cross_gamma in lots of the reporting specification by observation day or "
            "contract month or year, the DV01 in the currency per basis point by payment "
            "period.",
        ),
        (
            "bucket",
            "What to sum by: day, month or year, exactly so; a month or a year is the pricing "
            "contract's for the deltas and the payment's for the DV01, labelled by its first "
            "day, and the Total is the saved number.",
        ),
    ]
    assert description == (
        "Reports one risk of a batch or a collection, or all four, by day, month or year: the "
        "saved Total first, then a row per period, the deltas and the cross-gamma by observation "
        "day or contract period, the DV01 by payment period, as evaluation stored them."
    )
    description, arguments, hidden = SPECS["_AggregateResults"]
    assert not hidden and arguments == [
        (
            "result_handles",
            "The results handles to collect: a cell, a row or a column of cells showing "
            "_EvaluateTrades's or _EvaluateCashflows's results, in any mix, such as B2:B5, in the "
            "order given, a repeat counted again.",
        )
    ]
    assert description == (
        "Collects evaluated batches' saved risk, trades' and cashflows', into one collection, the "
        "lots by index, the DV01 by curve and currency and the cross-gamma by index and curve, "
        "nothing valued again, and shows its handle, which _ReportRisk takes."
    )
    description, arguments, hidden = SPECS["_ReportReserves"]
    assert not hidden and arguments == [
        (
            "results",
            "The results handle: the cell showing _EvaluateTrades's result, such as A12, or a name "
            "for it.",
        )
    ]
    assert description == (
        "Reports the batch's booked reserves: brokerage on the trades naming a broker and "
        "clearing on a cleared route, each trade's unsigned quantity times its specification's "
        "rate per lot, summed; marketing and the signed CVA, once a row; and the currency."
    )


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


def test_the_request_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["_CreateRFQ"]
    assert not hidden
    assert description == (
        "Creates a request for quote on one index from a ticket's rows under a quote template's "
        "terms, a month or two dates and a quantity per row, paying on the template's days or "
        "the dates given, and shows its handle, the text _QuoteRFQ takes as the request."
    )
    assert arguments == [
        (
            "index",
            "The index handle: the cell showing _CreateIndex's result, such as I3, or a name for "
            "it, the one index every row of the request is on.",
        ),
        (
            "fields",
            "The request's header cells in one row, such as A1:D1, from contract_code, "
            "start_date, end_date, quantity and payment_day, in any order.",
        ),
        (
            "rows",
            "The rows under the headers, such as A2:D4, each a contract month or two dates with "
            "its quantity, and a payment date where that column is given.",
        ),
        (
            "template",
            "The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as "
            "B3, or a name for it, which supplies the request's terms and its frequency.",
        ),
    ]


def test_the_request_quote_explains_itself() -> None:
    description, arguments, hidden = SPECS["_QuoteRFQ"]
    assert not hidden
    assert description == (
        "Quotes one fixed price, flat or fit to curve, for a saved request on one market, each "
        "month at its quantity, fixings for the observations that have passed and the day's "
        "quotes for the rest, a flat bilateral price discounted on each month's own day."
    )
    assert arguments == [
        (
            "market",
            "The market handle over the request's index: the cell showing _CreateMarket's result, "
            "such as I12, or a name for it, with the day's quotes over the history they follow.",
        ),
        (
            "rfq",
            "The request handle: the cell showing _CreateRFQ's result, such as B5, or a name for "
            "it.",
        ),
        (
            "pricing",
            "The price to quote, flat or ftc: flat is one fixed price for the request, each "
            "component weighed by its quantity and its payment's discount factor; ftc, fit to "
            "curve, is the components' own prices averaged by quantity alone.",
        ),
        (
            "[discount_curve_set]",
            "The collection handle for a bilateral request, under either pricing: the cell "
            "showing _CollectDiscountCurves's result, such as I13, or a name for it, holding the "
            "curve the template names; left out for a cleared request.",
        ),
    ]


def test_the_fit_to_curve_prices_explain_themselves() -> None:
    description, arguments, hidden = SPECS["_QuoteFTCPrices"]
    assert not hidden
    assert description == (
        "Quotes the fixed price of each month of a saved request from one agreed fit-to-curve "
        "price, each month's own price moved by the same amount and rounded, and above them the "
        "agreed price, the average the fixed prices come back to and the difference."
    )
    assert arguments == [
        (
            "market",
            "The market handle over the request's index: the cell showing _CreateMarket's result, "
            "such as I12, or a name for it, with the day's quotes over the history they follow.",
        ),
        (
            "rfq",
            "The request handle: the cell showing _CreateRFQ's result, such as B5, or a name for "
            "it.",
        ),
        (
            "price",
            "The one price agreed for the request, a fit-to-curve price, such as B7 or 3.95; "
            "every month's own price is moved by the same amount, this price less the request's "
            "fit-to-curve quote.",
        ),
        (
            "decimals",
            "The decimals a fixed price may hold, a whole number from 0 to 15, such as 2; each "
            "fixed price is rounded alone, as ROUND rounds.",
        ),
    ]


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
