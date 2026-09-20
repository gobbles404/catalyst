"""The utilities: worksheet functions that read what the library holds, or reshape what the sheet
supplies, and change nothing. docs/library/utilities/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from functools import singledispatch
from typing import Annotated, Any, assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar, FixingMode
from goosedove.excel.bridge import (
    NUMBER_CODE,
    TEXT_CODE,
    Handle,
    MixedArray,
    excel_function,
)
from goosedove.globals.discount_curve import DiscountCurve
from goosedove.globals.valuation_date import ValuationDate
from goosedove.index_definitions.contract_specifications import ContractSpecifications
from goosedove.index_definitions.expiry_schedule import ExpirySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index_conventions import IndexConventions
from goosedove.market.market import Market
from goosedove.market.market_history import MarketHistory
from goosedove.market_data.daily_fixings import DailyFixings
from goosedove.market_data.monthly_fixings import MonthlyFixings
from goosedove.market_data.price_vector import PriceVector


@singledispatch
def shown(obj: object) -> MixedArray:
    """The table a kind shows on the sheet: its headers in the creator's words, a row of types,
    then one row per element. Each kind registers its own below, and the pull request that
    builds a creator adds its kind here; a kind nobody registered fails rather than guessing."""
    raise TypeError(f"no table for a {type(obj).__name__}")


@shown.register
def valuation_date_table(obj: ValuationDate) -> MixedArray:
    return MixedArray.table(
        [("as_of", "day_fraction_elapsed"), ("datetime64[D]", "float")],
        np.array([obj.as_of]),
        np.array([obj.day_fraction_elapsed]),
    )


@shown.register
def discount_curve_table(obj: DiscountCurve) -> MixedArray:
    return MixedArray.table(
        [("date", "discount_factor"), ("datetime64[D]", "float64")], obj.dates, obj.factors
    )


@shown.register
def expiry_schedule_table(obj: ExpirySchedule) -> MixedArray:
    # The codes and the futures always, then the options and the publication dates when the
    # schedule holds them, in that order, so the publication dates are the last column.
    headers = ["future_code", "future_expiry"]
    columns: list[NDArray[np.datetime64] | tuple[str, ...]] = [obj.codes, obj.future_expiry]
    for header, dates in (
        ("option_expiry", obj.option_expiry),
        ("publication_date", obj.publication_date),
    ):
        if dates is not None:
            headers.append(header)
            columns.append(dates)
    types = ["str"] + ["datetime64[D]"] * (len(columns) - 1)
    return MixedArray.table([tuple(headers), tuple(types)], *columns)


@shown.register
def calendar_table(obj: Calendar) -> MixedArray:
    # The dates and the flags were made when the calendar was; the prompt contract's code is
    # read from the schedule the calendar keeps, one take over the rows, and nothing is rebuilt.
    codes = np.array(obj.expiry_schedule.codes, dtype=object)[obj.prompt]
    return MixedArray.table(
        [
            ("date", "prompt_contract", "is_business_day", "is_past"),
            ("datetime64[D]", "str", "bool", "bool"),
        ],
        obj.dates,
        tuple(codes),
        obj.is_business_day,
        obj.is_past,
    )


def _priced_column(
    base: MixedArray,
    header: str,
    words: NDArray[Any] | str,
    *priced: tuple[NDArray[np.intp], NDArray[np.float64]],
) -> MixedArray:
    """A calendar's table widened by one column that holds a number on some days and a word on
    the others: each priced pair names calendar rows and the prices on them, and the word, one
    for every day or one per day, shows on the rest. The words are display, not values, and a
    column holding numbers on some rows and words on others is not one the table builder takes,
    so the column is written by kind: its kinds, its slots, and its words into the texts. The
    calendar's own table stands as it is, nothing rebuilt.

    The texts in sheet order: each heading row's four then this column's, and each day's code
    then, on a day without a price, its word; the calendar's body texts are its codes alone, one
    per day, in the same order.
    """
    rows, width = base.shape
    kinds = np.empty((rows, width + 1), dtype=np.uint8)
    kinds[:, :width] = base.kinds
    kinds[:, width] = TEXT_CODE
    slots = np.full((rows, width + 1), np.nan)
    slots[:, :width] = base.numeric_slots
    pairs = np.empty((rows - 2, 2), dtype=object)
    pairs[:, 0] = base.texts[2 * width :]
    pairs[:, 1] = words
    worded = np.ones((rows - 2, 2), dtype=bool)
    for on, prices in priced:  # the pairs, not the prices: one or two of them
        kinds[on + 2, width] = NUMBER_CODE
        slots[on + 2, width] = prices
        worded[on, 1] = False
    headings = (*base.texts[:width], header, *base.texts[width : 2 * width], "float64")
    return MixedArray(kinds, slots, (*headings, *pairs[worded]))


@shown.register
def market_history_table(obj: MarketHistory) -> MixedArray:
    # The calendar's four columns, then fixing_price: the price on each fixed day, a number,
    # and a word on every other day. For a daily calendar, closed where the market is shut and
    # unfixed where it is open, the valuation day and the days after it; for a monthly one,
    # unfixed on every day of a contract still live, weekends and holidays alike, since a
    # monthly price falls on every day of its contract.
    calendar = obj.calendar
    words: NDArray[Any] | str
    match calendar.fixing_mode:
        case FixingMode.DAILY:
            words = np.empty(calendar.dates.size, dtype=object)
            words[:] = "closed"
            words[calendar.is_business_day] = "unfixed"
        case FixingMode.MONTHLY:
            words = "unfixed"
        case _:
            assert_never(calendar.fixing_mode)
    return _priced_column(
        calendar_table(calendar), "fixing_price", words, (obj.fixed_rows, obj.fixing_prices)
    )


@shown.register
def market_table(obj: Market) -> MixedArray:
    # The calendar's four columns, then price: the history's fixing on each day it has, the
    # quote of the prompt contract on each live day, and closed on the rest. For a daily
    # calendar the live days are the business days from the valuation day on; for a monthly one
    # every day of a contract not yet expired, weekends, holidays and past days alike, so no
    # day is closed. The quotes are gathered for the live rows alone, since a past day's prompt
    # may precede the first contract quoted and would index before the vector.
    history = obj.market_history
    calendar = history.calendar
    match calendar.fixing_mode:
        case FixingMode.DAILY:
            live = np.flatnonzero(calendar.is_business_day & ~calendar.is_past)
        case FixingMode.MONTHLY:
            live = np.flatnonzero(calendar.prompt >= obj.first_contract)
        case _:
            assert_never(calendar.fixing_mode)
    quotes = obj.price_vector.prices[calendar.prompt[live] - obj.first_contract]
    return _priced_column(
        calendar_table(calendar),
        "price",
        "closed",
        (history.fixed_rows, history.fixing_prices),
        (live, quotes),
    )


@shown.register
def daily_fixings_table(obj: DailyFixings) -> MixedArray:
    return MixedArray.table(
        [("date", "settle"), ("datetime64[D]", "float64")], obj.dates, obj.settles
    )


@shown.register
def monthly_fixings_table(obj: MonthlyFixings) -> MixedArray:
    return MixedArray.table(
        [("publication_date", "price"), ("datetime64[D]", "float64")],
        obj.publication_dates,
        obj.prices,
    )


@shown.register
def price_vector_table(obj: PriceVector) -> MixedArray:
    return MixedArray.table([("price",), ("float64",)], obj.prices)


@shown.register
def holiday_calendar_table(obj: HolidayCalendar) -> MixedArray:
    return MixedArray.table([("holiday",), ("datetime64[D]",)], obj.holiday)


@shown.register
def index_conventions_table(obj: IndexConventions) -> MixedArray:
    return MixedArray.table(
        [
            (
                "quote_currency_unit",
                "quote_quantity_unit",
                "currency_unit",
                "quantity_type",
                "quantity_unit",
            ),
            ("str", "str", "str", "str", "str"),
        ],
        (obj.quote_currency_unit,),
        (obj.quote_quantity_unit,),
        (obj.currency_unit,),
        (obj.quantity_type,),
        (obj.quantity_unit,),
    )


@shown.register
def contract_specifications_table(obj: ContractSpecifications) -> MixedArray:
    return MixedArray.table(
        [
            ("name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
            ("str", "float64", "float64", "float64"),
        ],
        obj.names,
        obj.lot_sizes,
        obj.brokerage_rates_per_lot,
        obj.clearing_rates_per_lot,
    )


@excel_function
def util_ReadHandle(
    handle: Annotated[
        Handle[object], "The cell showing any creator's result, such as B5, or a name for it."
    ],
) -> MixedArray:
    """Reads the object behind a handle and spills it as a table: its headers, a row of types,
    then one row per element."""
    return shown(handle)
