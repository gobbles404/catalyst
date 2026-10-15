"""The index behind one reference price: its name, its schedule, the conventions its price is
quoted in, the contract specifications it trades as, for a futures index the holiday calendar of
its market, four objects the sheet already holds and a name, bound once, and, where the desk
named one, the specification a batch's delta is reported in lots of, resolved once here.
docs/library/index-definitions/index.md is the page."""

import math
from dataclasses import dataclass
from functools import singledispatch
from typing import cast

from goosedove.globals.unit_conversions import UnitConversions
from goosedove.index_definitions.contract_specifications import ContractSpecifications
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.gas_daily_schedule import GasDailySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index_conventions import CURRENCY, IndexConventions, a_unit_of
from goosedove.index_definitions.kind import (
    Kind,
    named,
    with_holiday_calendar,
    without_holiday_calendar,
)


@dataclass(frozen=True, slots=True)
class ReportingLot:
    """The specification a batch's delta is reported in lots of, chosen by name when the index was
    made and resolved once: specification, its row of the index's specifications; name, lot_size
    and lot_unit as that row holds them; quote_quantity, one lot restated in the conventions' quote
    quantity unit, 42,000 gallons for a lot of a thousand barrels on an index quoted per gallon;
    coefficient, the settlement currency a fully live lot makes for a move of one unit of quote
    price, the quote quantity restated from the quote currency to the settlement currency, 420 for
    cents per gallon settled in dollars and 42,000 for dollars per gallon; and words, the unit the
    risk report names, `lots of LOT (1000 BBL)`. A count of lots is a count of this row, whatever
    word a trade's quantity was entered in."""

    specification: int
    name: str
    lot_size: float
    lot_unit: str
    quote_quantity: float
    coefficient: float
    words: str


@dataclass(frozen=True, slots=True)
class Index:
    """The name as the desk typed it, a label and nothing more; the kind, read off the schedule;
    the four objects themselves, kept by reference and unchanged: the schedule, the holiday
    calendar, a futures index's own and None on the other two, the conventions and the
    specifications, whose lot units are units of the conventions' quantity type, the one fact
    read across two of them; and the reporting lot, the specification a batch's delta is reported
    in lots of with its conversions resolved once, None when the index was made without one, as an
    index that only builds markets may be. Nothing else is read out of them here or checked
    again."""

    name: str
    kind: Kind
    schedule: FuturesSchedule | IfercSchedule | GasDailySchedule
    holiday_calendar: HolidayCalendar | None
    conventions: IndexConventions
    specifications: ContractSpecifications
    reporting_lot: ReportingLot | None


def index(
    name: str,
    schedule: object,
    conventions: IndexConventions,
    specifications: ContractSpecifications,
    holiday_calendar: HolidayCalendar | None,
    reporting_lot: str | None,
    units: UnitConversions,
) -> Index:
    """The one way to make an Index: the schedule's kind chooses which index is made, the
    holiday calendar is checked against it, the specifications' lot units against the
    conventions' quantity type, the reporting lot, where one is named, against the specifications
    and the tables, and the record is returned once all four hold, nothing else.

    The kind is read off the object the seam hands over, the one way the library tells kinds
    apart, as the market history reads its fixings'; an object of no schedule kind is refused
    here in the library's words, since the seam names no kind for it. A futures index brings
    its holiday calendar, and the other two leave it out, the calendar's rules of #104 in the
    calendar's words. Then each lot unit of the specifications is a unit of the conventions'
    quantity type, read from the tables passed in: a barrel row and a gallon row both stand
    under a volume index, and an MMBTU row does not, the one fact that lives across two of the
    definitions and so is checked where they meet. Then the reporting lot, when one is named: the
    name is one of the specifications' names, matched exactly, no trimming, no case folding, no
    alias and no first row taken for want of a match, since the delta of every batch on the index
    is a count of that row and a guess would count the wrong thing; its lot is restated in the
    quote quantity unit and then in the settlement currency through the tables, two factors
    looked up once, and the two numbers are finite, since a lot size that outruns the largest
    number would divide every delta into nothing; left out, the index has none, and a batch of
    trades on it is refused when it is made, never a market. The name is a label, kept as typed,
    neither unique nor looked up; whether the four objects are one index's is otherwise the desk's
    to keep right, since nothing in any of them says which index it belongs to. Nothing is copied
    and nothing is built but the small record; the one pass is over the specifications' lot
    units, one lookup per row, and nothing of the schedule is looked at.
    """
    kind, calendar = _of(schedule, holiday_calendar)
    measure = units.categories[conventions.quantity_type].sizes
    for row, unit in enumerate(specifications.lot_units, start=1):
        if unit not in measure:
            raise ValueError(
                f"specifications row {row} lot_unit is {unit!r}, "
                f"expected {a_unit_of(conventions.quantity_type, measure)}"
            )
    lot = (
        None
        if reporting_lot is None
        else _the_reporting_lot(reporting_lot, conventions, specifications, units)
    )
    typed = cast(FuturesSchedule | IfercSchedule | GasDailySchedule, schedule)  # what the kind said
    return Index(name, kind, typed, calendar, conventions, specifications, lot)


def _the_reporting_lot(
    name: str,
    conventions: IndexConventions,
    specifications: ContractSpecifications,
    units: UnitConversions,
) -> ReportingLot:
    """The named specification with its two conversions: one lot in the quote quantity unit, and
    the settlement currency a live lot makes per unit of quote price; both finite."""
    names = specifications.names
    if name not in names:
        choices = ", ".join(repr(each) for each in names)
        raise ValueError(
            f"reporting_lot is {name!r}, expected one of the specifications: {choices}"
        )
    row = names.index(name)
    size = float(specifications.lot_sizes[row])
    unit = specifications.lot_units[row]
    quote_quantity = size * units.factor(
        conventions.quantity_type, unit, conventions.quote_quantity_unit
    )
    coefficient = quote_quantity * units.factor(
        CURRENCY, conventions.quote_currency_unit, conventions.currency_unit
    )
    if not (math.isfinite(coefficient) and coefficient > 0.0):
        raise ValueError(
            f"reporting_lot {name!r} is {quote_quantity!r} {conventions.quote_quantity_unit} a "
            "lot, expected a finite quantity; the lot size outruns the largest number"
        )
    return ReportingLot(
        row, name, size, unit, quote_quantity, coefficient, f"lots of {name} ({int(size)} {unit})"
    )


@singledispatch
def _of(
    schedule: object, holiday_calendar: HolidayCalendar | None
) -> tuple[Kind, HolidayCalendar | None]:
    raise ValueError(
        f"schedule is {named(schedule)}, expected a futures, IFERC or Gas Daily schedule"
    )


@_of.register
def futures_index(
    schedule: FuturesSchedule, holiday_calendar: HolidayCalendar | None
) -> tuple[Kind, HolidayCalendar | None]:
    return Kind.FUTURES, with_holiday_calendar(holiday_calendar)


@_of.register
def iferc_index(
    schedule: IfercSchedule, holiday_calendar: HolidayCalendar | None
) -> tuple[Kind, HolidayCalendar | None]:
    without_holiday_calendar(holiday_calendar, Kind.IFERC)
    return Kind.IFERC, None


@_of.register
def gas_daily_index(
    schedule: GasDailySchedule, holiday_calendar: HolidayCalendar | None
) -> tuple[Kind, HolidayCalendar | None]:
    without_holiday_calendar(holiday_calendar, Kind.GAS_DAILY)
    return Kind.GAS_DAILY, None
