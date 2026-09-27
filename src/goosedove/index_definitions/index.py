"""The index behind one reference price: its name, its schedule, the conventions its price is
quoted in, the contract specifications it trades as and, for a futures index, the holiday
calendar of its market, four objects the sheet already holds and a name, bound once.
docs/library/index-definitions/index.md is the page."""

from dataclasses import dataclass
from functools import singledispatch

from goosedove.globals.unit_conversions import UnitConversions
from goosedove.index_definitions.contract_specifications import ContractSpecifications
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.gas_daily_schedule import GasDailySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index_conventions import IndexConventions, a_unit_of
from goosedove.index_definitions.kind import (
    Kind,
    named,
    with_holiday_calendar,
    without_holiday_calendar,
)


@dataclass(frozen=True, slots=True)
class Index:
    """The name as the desk typed it, a label and nothing more; the kind, read off the schedule;
    and the four objects themselves, kept by reference and unchanged: the schedule, the holiday
    calendar, a futures index's own and None on the other two, the conventions and the
    specifications, whose lot units are units of the conventions' quantity type, the one fact
    read across two of them. Nothing else is read out of them here or checked again."""

    name: str
    kind: Kind
    schedule: FuturesSchedule | IfercSchedule | GasDailySchedule
    holiday_calendar: HolidayCalendar | None
    conventions: IndexConventions
    specifications: ContractSpecifications


def index(
    name: str,
    schedule: object,
    conventions: IndexConventions,
    specifications: ContractSpecifications,
    holiday_calendar: HolidayCalendar | None,
    units: UnitConversions,
) -> Index:
    """The one way to make an Index: the schedule's kind chooses which index is made, the
    holiday calendar is checked against it, the specifications' lot units against the
    conventions' quantity type, and the record is returned once all three hold, nothing else.

    The kind is read off the object the seam hands over, the one way the library tells kinds
    apart, as the market history reads its fixings'; an object of no schedule kind is refused
    here in the library's words, since the seam names no kind for it. A futures index brings
    its holiday calendar, and the other two leave it out, the calendar's rules of #104 in the
    calendar's words. Then each lot unit of the specifications is a unit of the conventions'
    quantity type, read from the tables passed in: a barrel row and a gallon row both stand
    under a volume index, and an MMBTU row does not, the one fact that lives across two of the
    definitions and so is checked where they meet. The name is a label, kept as typed, neither
    unique nor looked up; whether the four objects are one index's is otherwise the desk's to
    keep right, since nothing in any of them says which index it belongs to. Nothing is copied
    and nothing is built but the small record; the one pass is over the specifications' lot
    units, one lookup per row, and nothing of the schedule is looked at.
    """
    made = _of(schedule, name, conventions, specifications, holiday_calendar)
    measure = units.categories[conventions.quantity_type].sizes
    for row, unit in enumerate(specifications.lot_units, start=1):
        if unit not in measure:
            raise ValueError(
                f"specifications row {row} lot_unit is {unit!r}, "
                f"expected {a_unit_of(conventions.quantity_type, measure)}"
            )
    return made


@singledispatch
def _of(
    schedule: object,
    name: str,
    conventions: IndexConventions,
    specifications: ContractSpecifications,
    holiday_calendar: HolidayCalendar | None,
) -> Index:
    raise ValueError(
        f"schedule is {named(schedule)}, expected a futures, IFERC or Gas Daily schedule"
    )


@_of.register
def futures_index(
    schedule: FuturesSchedule,
    name: str,
    conventions: IndexConventions,
    specifications: ContractSpecifications,
    holiday_calendar: HolidayCalendar | None,
) -> Index:
    return Index(
        name,
        Kind.FUTURES,
        schedule,
        with_holiday_calendar(holiday_calendar),
        conventions,
        specifications,
    )


@_of.register
def iferc_index(
    schedule: IfercSchedule,
    name: str,
    conventions: IndexConventions,
    specifications: ContractSpecifications,
    holiday_calendar: HolidayCalendar | None,
) -> Index:
    without_holiday_calendar(holiday_calendar, Kind.IFERC)
    return Index(name, Kind.IFERC, schedule, None, conventions, specifications)


@_of.register
def gas_daily_index(
    schedule: GasDailySchedule,
    name: str,
    conventions: IndexConventions,
    specifications: ContractSpecifications,
    holiday_calendar: HolidayCalendar | None,
) -> Index:
    without_holiday_calendar(holiday_calendar, Kind.GAS_DAILY)
    return Index(name, Kind.GAS_DAILY, schedule, None, conventions, specifications)
