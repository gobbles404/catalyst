"""The utilities: worksheet functions that read what the library holds, or reshape what the sheet
supplies, and change nothing. docs/library/utilities/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from functools import singledispatch
from typing import Annotated

import numpy as np

from goosedove.excel.bridge import Handle, MixedArray, excel_function
from goosedove.globals.discount_curve import DiscountCurve
from goosedove.globals.valuation_date import ValuationDate
from goosedove.market_definitions.expiry_schedule import ExpirySchedule
from goosedove.market_definitions.holiday_calendar import HolidayCalendar


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
    if obj.option_expiry is None:
        return MixedArray.table(
            [("future_code", "future_expiry"), ("str", "datetime64[D]")],
            obj.codes,
            obj.future_expiry,
        )
    return MixedArray.table(
        [
            ("future_code", "future_expiry", "option_expiry"),
            ("str", "datetime64[D]", "datetime64[D]"),
        ],
        obj.codes,
        obj.future_expiry,
        obj.option_expiry,
    )


@shown.register
def holiday_calendar_table(obj: HolidayCalendar) -> MixedArray:
    return MixedArray.table([("holiday",), ("datetime64[D]",)], obj.holiday)


@excel_function
def ReadHandle(
    handle: Annotated[
        Handle[object], "The cell showing any creator's result, such as B5, or a name for it."
    ],
) -> MixedArray:
    """Reads the object behind a handle and spills it as a table: its headers, a row of types,
    then one row per element."""
    return shown(handle)
