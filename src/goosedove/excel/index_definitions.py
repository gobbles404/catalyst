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
from goosedove.index_definitions.contract_specifications import (
    ContractSpecifications,
    contract_specifications,
)
from goosedove.index_definitions.expiry_schedule import ExpirySchedule, expiry_schedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from goosedove.index_definitions.index_conventions import IndexConventions, index_conventions

# The worksheet functions this module registers, named here so that their leading underscore
# reads as Excel's filter, docs/library/conventions.md under Names, and not as Python's privacy.
__all__ = [
    "_CreateContractSpecifications",
    "_CreateExpirySchedule",
    "_CreateHolidayCalendar",
    "_CreateIndexConventions",
]


@excel_function
def _CreateExpirySchedule(
    future_code: Annotated[
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
) -> Handle[ExpirySchedule]:
    """Creates an expiry schedule from the contract codes of one index and their expiry dates,
    and shows its handle, the text other formulas take as the schedule."""
    return expiry_schedule(future_code, future_expiry, option_expiry)


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
def _CreateIndexConventions(
    quote_currency_unit: Annotated[
        str, "The currency unit a price of the index is quoted in, such as USD."
    ],
    quote_quantity_unit: Annotated[
        str, "The quantity unit a price of the index is quoted per, such as BBL for USD per barrel."
    ],
    currency_unit: Annotated[str, "The currency unit the index settles in, such as USD."],
    quantity_type: Annotated[str, "What a quantity of the index measures, such as volume."],
    quantity_unit: Annotated[str, "The unit a quantity of the index is stated in, such as BBL."],
) -> Handle[IndexConventions]:
    """Creates the index conventions of one index, the units it is quoted, settled and measured
    in, and shows its handle, the text other formulas take as the conventions."""
    # The five codes are not checked yet: which are allowed is a later task, noted in the builder.
    return index_conventions(
        quote_currency_unit, quote_quantity_unit, currency_unit, quantity_type, quantity_unit
    )


class ContractSpecificationsTable(Table):
    """The contracts' table: one row per contract an index trades as, its name, lot size and the
    two fees per lot."""

    name: TextColumn
    lot_size: NumberColumn
    brokerage_rate_per_lot: NumberColumn
    clearing_rate_per_lot: NumberColumn


@excel_function
def _CreateContractSpecifications(
    header_row: Annotated[
        TextRow,
        "The header cells of your contract table, such as A1:D1, reading name, lot_size, "
        "brokerage_rate_per_lot and clearing_rate_per_lot in any order.",
    ],
    table: Annotated[
        ContractSpecificationsTable,
        "The rows under the headers, such as A2:D3: one contract per row, its name, lot size and "
        "the two fees per lot, each name once.",
    ],
) -> Handle[ContractSpecifications]:
    """Creates the contract specifications of one index, the name, lot size and fees per lot of
    each contract it trades as, and shows its handle, the text other formulas take as the
    specifications."""
    # Beyond each name once and each lot size whole, the facts are not checked yet: a later task,
    # noted in the builder.
    return contract_specifications(
        table.name, table.lot_size, table.brokerage_rate_per_lot, table.clearing_rate_per_lot
    )
