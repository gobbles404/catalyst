"""The worksheet functions of the index definitions: the pieces one index is defined by, as
opposed to the globals every calculation starts from, each created once and reached by handle.
docs/library/index-definitions/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from typing import Annotated

from goosedove.excel.bridge import (
    DateColumn,
    Handle,
    NumberColumn,
    Table,
    TextColumn,
    TextRow,
    excel_function,
)
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import (
    ContractSpecifications,
    contract_specifications,
)
from goosedove.index_definitions.futures_schedule import FuturesSchedule, futures_schedule
from goosedove.index_definitions.gas_daily_schedule import GasDailySchedule, gas_daily_schedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule, iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import IndexConventions, index_conventions

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = [
    "_CreateContractSpecifications",
    "_CreateFuturesSchedule",
    "_CreateGasDailySchedule",
    "_CreateHolidayCalendar",
    "_CreateIfercSchedule",
    "_CreateIndex",
    "_CreateIndexConventions",
]


@excel_function
def _CreateFuturesSchedule(
    contract_code: Annotated[
        TextColumn,
        "The column of contract codes, such as A2:A7 holding m26 to X26, one per contract.",
    ],
    future_expiry: Annotated[
        DateColumn,
        "The column of future expiry dates beside the codes, such as B2:B7, one per code.",
    ],
    option_expiry: Annotated[
        DateColumn | None,
        "The column of option expiry dates beside the codes, such as C2:C7, one per code.",
    ] = None,
) -> Handle[FuturesSchedule]:
    """Creates the futures schedule of one index from its contract codes, the day each future
    expires and, where given, the day its option expires, and shows its handle, the text other
    formulas take as the schedule."""
    return futures_schedule(contract_code, future_expiry, option_expiry)


@excel_function
def _CreateHolidayCalendar(
    holiday: Annotated[
        DateColumn,
        "The column of dates the market is closed, such as A2:A11, one holiday per row.",
    ],
) -> Handle[HolidayCalendar]:
    """Creates a holiday calendar from the days one market is closed and shows its handle, the
    text other formulas take as the calendar."""
    return holiday_calendar(holiday)


@excel_function
def _CreateIfercSchedule(
    contract_code: Annotated[
        TextColumn,
        "The column of contract codes, such as A2:A4 holding V26 to Z26, one per contract month.",
    ],
    last_trading_date: Annotated[
        DateColumn,
        "The column of last trading dates beside the codes, such as B2:B4, one per code.",
    ],
    publication_date: Annotated[
        DateColumn,
        "The column of dates the index is published, beside the codes, such as C2:C4, one per "
        "code.",
    ],
) -> Handle[IfercSchedule]:
    """Creates an IFERC schedule from the contract months of one index, the day each month's
    future stops trading and the day its index is published, and shows its handle, the text
    other formulas take as the schedule."""
    return iferc_schedule(contract_code, last_trading_date, publication_date)


@excel_function
def _CreateGasDailySchedule(
    contract_code: Annotated[
        TextColumn,
        "The column of contract codes, such as A2:A4 holding U26 to X26, one per contract month.",
    ],
    first_date: Annotated[
        DateColumn,
        "The column of each month's first day of gas, beside the codes, such as B2:B4, one per "
        "code.",
    ],
    last_date: Annotated[
        DateColumn,
        "The column of each month's last day of gas, beside the codes, such as C2:C4, one per "
        "code.",
    ],
) -> Handle[GasDailySchedule]:
    """Creates a Gas Daily schedule from the contract months of one index and the first and
    last day of gas each month's price covers, and shows its handle, the text other formulas
    take as the schedule."""
    return gas_daily_schedule(contract_code, first_date, last_date)


@excel_function
def _CreateIndexConventions(
    quote_currency_unit: Annotated[
        str, "The currency unit a price of the index is quoted in: USD or CENT."
    ],
    quote_quantity_unit: Annotated[
        str,
        "The quantity unit a price of the index is quoted per, a unit of the quantity type: GAL, "
        "BBL, L or M3 for volume; KG, LB, MT, ST, LT, G, OZT or CWT_US for mass; MMBTU, BTU, "
        "THERM, GJ, MWH or KWH for energy.",
    ],
    currency_unit: Annotated[str, "The currency unit the index settles in: USD or CENT."],
    quantity_type: Annotated[str, "What a quantity of the index measures: volume, mass or energy."],
    quantity_unit: Annotated[
        str,
        "The unit a quantity of the index is stated in, a unit of the quantity type: GAL, BBL, L "
        "or M3 for volume; KG, LB, MT, ST, LT, G, OZT or CWT_US for mass; MMBTU, BTU, THERM, GJ, "
        "MWH or KWH for energy.",
    ],
) -> Handle[IndexConventions]:
    """Creates the index conventions of one index, the units it is quoted, settled and measured
    in, checked against the library's unit tables, and shows its handle, the text other formulas
    take as the conventions."""
    return index_conventions(
        quote_currency_unit,
        quote_quantity_unit,
        currency_unit,
        quantity_type,
        quantity_unit,
        UNITS,
    )


@excel_function
def _CreateIndex(
    name: Annotated[
        str, "The index's name as the desk calls it, such as Henry Hub NYMEX, kept as typed."
    ],
    schedule: Annotated[
        Handle[object],
        "The index's schedule handle, futures, IFERC or Gas Daily: the cell showing its creator's "
        "result, such as B2, or a name for it.",
    ],
    index_conventions: Annotated[
        Handle[IndexConventions],
        "The index-conventions handle: the cell showing _CreateIndexConventions's result, such "
        "as B4, or a name for it.",
    ],
    contract_specifications: Annotated[
        Handle[ContractSpecifications],
        "The contract-specifications handle: the cell showing _CreateContractSpecifications's "
        "result, such as B5, or a name for it.",
    ],
    holiday_calendar: Annotated[
        Handle[HolidayCalendar] | None,
        "The market's holiday-calendar handle with a futures schedule: the cell showing "
        "_CreateHolidayCalendar's result, such as B3, or a name for it; left out for an IFERC "
        "or Gas Daily schedule.",
    ] = None,
) -> Handle[Index]:
    """Creates the index behind one reference price, its name with its schedule, conventions,
    contract specifications and, for a futures index, holiday calendar, and shows its handle,
    the text other formulas take as the index."""
    return index(
        name, schedule, index_conventions, contract_specifications, holiday_calendar, UNITS
    )


class ContractSpecificationsTable(Table):
    """The specifications' table: one row per word the desk states a quantity of the index in, a
    contract or a bare unit, its name, lot size, the lot's unit and the two fees per lot."""

    name: TextColumn
    lot_size: NumberColumn
    lot_unit: TextColumn
    brokerage_rate_per_lot: NumberColumn
    clearing_rate_per_lot: NumberColumn


@excel_function
def _CreateContractSpecifications(
    header_row: Annotated[
        TextRow,
        "The header cells of your specifications table, such as A1:E1, reading name, lot_size, "
        "lot_unit, brokerage_rate_per_lot and clearing_rate_per_lot in any order.",
    ],
    table: Annotated[
        ContractSpecificationsTable,
        "The rows under the headers, such as A2:E4: one row per word for a quantity of the index, "
        "a contract or a bare unit, its name, a whole lot size of 1 or more, the unit that lot "
        "size is in and the two fees per lot, 0 or more, each name once.",
    ],
) -> Handle[ContractSpecifications]:
    """Creates the contract specifications of one index, the desk's words for a quantity of it,
    each with its lot size, the lot's unit and the fees per lot, and shows its handle, the text
    other formulas take as the specifications."""
    return contract_specifications(
        table.name,
        table.lot_size,
        table.lot_unit,
        table.brokerage_rate_per_lot,
        table.clearing_rate_per_lot,
        UNITS,
    )
