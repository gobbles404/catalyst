"""The utilities: worksheet functions that read what the library holds, or reshape what the sheet
supplies, and change nothing. docs/library/utilities/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from functools import singledispatch
from typing import Annotated

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar
from goosedove.excel.bridge import Handle, MixedArray, excel_function
from goosedove.globals.discount_curve import DiscountCurve
from goosedove.globals.valuation_date import ValuationDate
from goosedove.index_definitions.contract_specifications import ContractSpecifications
from goosedove.index_definitions.expiry_schedule import ExpirySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index_conventions import IndexConventions
from goosedove.market_data.daily_fixings import DailyFixings
from goosedove.market_data.futures_curve import FuturesCurve
from goosedove.market_data.monthly_fixings import MonthlyFixings


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
def futures_curve_table(obj: FuturesCurve) -> MixedArray:
    return MixedArray.table([("future_code", "price"), ("str", "float64")], obj.codes, obj.prices)


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
