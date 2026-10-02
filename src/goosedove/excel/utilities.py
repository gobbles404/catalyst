"""The utilities: worksheet functions that read what the library holds, or reshape what the sheet
supplies, and change nothing. docs/library/utilities/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from functools import singledispatch
from typing import Annotated, Any

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar
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
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.gas_daily_schedule import GasDailySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.index_conventions import IndexConventions
from goosedove.market.market import Market
from goosedove.market.market_history import MarketHistory
from goosedove.market_data.futures_fixings import FuturesFixings
from goosedove.market_data.gas_daily_fixings import GasDailyFixings
from goosedove.market_data.iferc_fixings import IfercFixings
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
def futures_schedule_table(obj: FuturesSchedule) -> MixedArray:
    # The codes and the futures always, then the options when the index has them.
    if obj.option_expiry is None:
        return MixedArray.table(
            [("contract_code", "future_expiry"), ("str", "datetime64[D]")],
            obj.codes,
            obj.future_expiry,
        )
    return MixedArray.table(
        [
            ("contract_code", "future_expiry", "option_expiry"),
            ("str", "datetime64[D]", "datetime64[D]"),
        ],
        obj.codes,
        obj.future_expiry,
        obj.option_expiry,
    )


@shown.register
def iferc_schedule_table(obj: IfercSchedule) -> MixedArray:
    return MixedArray.table(
        [
            ("contract_code", "last_trading_date", "publication_date"),
            ("str", "datetime64[D]", "datetime64[D]"),
        ],
        obj.codes,
        obj.last_trading_date,
        obj.publication_date,
    )


@shown.register
def gas_daily_schedule_table(obj: GasDailySchedule) -> MixedArray:
    return MixedArray.table(
        [("contract_code", "first_date", "last_date"), ("str", "datetime64[D]", "datetime64[D]")],
        obj.codes,
        obj.first_date,
        obj.last_date,
    )


@shown.register
def calendar_table(obj: Calendar, rows: int | None = None) -> MixedArray:
    # The dates and the flags were made when the calendar was; the prompt contract's code is
    # read from the schedule of the index the calendar keeps, one take over the rows, and
    # nothing is rebuilt. A market asks for the first rows alone, those its quotes cover: each
    # column is cut there before anything is made of it, a view of the calendar's own column,
    # and the codes are taken no further than the last contract those rows reach, so the table
    # costs its own rows and no others, however long the schedule and the calendar run on.
    # Given no count, each cut is the whole column and the codes are the whole schedule's.
    prompt = obj.contract[:rows]
    codes = np.array(obj.index.schedule.codes[: int(prompt[-1]) + 1], dtype=object)[prompt]
    return MixedArray.table(
        [
            ("date", "contract", "is_priced", "is_fixed"),
            ("datetime64[D]", "str", "bool", "bool"),
        ],
        obj.dates[:rows],
        tuple(codes),
        obj.is_priced[:rows],
        obj.is_fixed[:rows],
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
    # The calendar's four columns, then fixing_price: the price fixed on each fixed and priced
    # period, a number, and a word on every other, closed where the calendar does not price the
    # day and unfixed where it prices but has not fixed, whatever the market.
    calendar = obj.calendar
    words = np.empty(calendar.dates.size, dtype=object)
    words[:] = "closed"
    words[calendar.is_priced] = "unfixed"
    return _priced_column(
        calendar_table(calendar), "fixing_price", words, (obj.fixed_rows, obj.fixing_prices)
    )


@shown.register
def market_table(obj: Market) -> MixedArray:
    # The calendar's four columns, then price, over the rows the market's prices cover: every
    # row through the last period of the last contract quoted, open or closed, the history
    # before it included. That row is found by one search down the calendar's contract column,
    # which never decreases, and the columns are cut there before the table is made, so a
    # vector that stops before the schedule costs its own rows; a vector that reaches the
    # schedule's end takes the same path and every row. The fixing on each fixed and priced
    # period, the quote of its contract on each unfixed period, and closed on every other. The
    # quotes are asked for the live rows alone, since a fixed period's contract may precede the
    # first contract quoted, and through the market's own reader, which holds the coverage rule.
    history = obj.market_history
    calendar = history.calendar
    rows = int(calendar.contract.searchsorted(obj.last_contract, side="right"))
    live = np.flatnonzero(calendar.is_priced[:rows] & ~calendar.is_fixed[:rows])
    return _priced_column(
        calendar_table(calendar, rows),
        "price",
        "closed",
        (history.fixed_rows, history.fixing_prices),
        (live, obj.live_prices(calendar.contract[live])),
    )


@shown.register
def futures_fixings_table(obj: FuturesFixings) -> MixedArray:
    # Newest first, as the creator takes them: the columns are kept oldest first, and each is
    # read here from its last row back, a view and no copy, date beside its own settle, so the
    # spill pasted back into the creator makes the same fixings.
    return MixedArray.table(
        [("date", "settle"), ("datetime64[D]", "float64")], obj.dates[::-1], obj.settles[::-1]
    )


@shown.register
def gas_daily_fixings_table(obj: GasDailyFixings) -> MixedArray:
    # Newest first, as the creator takes them, each kept column read from its last row back.
    return MixedArray.table(
        [("flow_date", "price"), ("datetime64[D]", "float64")],
        obj.dates[::-1],
        obj.prices[::-1],
    )


@shown.register
def iferc_fixings_table(obj: IfercFixings) -> MixedArray:
    # In the order the desk gave the codes, whichever it was: nothing here is dated.
    return MixedArray.table([("contract_code", "price"), ("str", "float64")], obj.codes, obj.prices)


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
def index_table(obj: Index) -> MixedArray:
    # What the index holds, one row: its name, its kind, how many contracts its schedule has,
    # how many the specifications name, and whether a holiday calendar was given. The parts
    # spill through their own handles; nothing of them is read here but two lengths.
    return MixedArray.table(
        [
            ("name", "kind", "contracts", "specifications", "has_holiday_calendar"),
            ("str", "str", "int64", "int64", "bool"),
        ],
        (obj.name,),
        (obj.kind.value,),
        np.array([len(obj.schedule.codes)], dtype=np.int64),
        np.array([len(obj.specifications.names)], dtype=np.int64),
        np.array([obj.holiday_calendar is not None], dtype=bool),
    )


@shown.register
def contract_specifications_table(obj: ContractSpecifications) -> MixedArray:
    return MixedArray.table(
        [
            ("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
            ("str", "float64", "str", "float64", "float64"),
        ],
        obj.names,
        obj.lot_sizes,
        obj.lot_units,
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
