"""The index behind one reference price: its name, its schedule, the conventions its price is
quoted in, the contract specifications it trades as, for a futures index the holiday calendar of
its market, chosen by key from a collection, objects the sheet already holds and a name, bound
once, and, where the desk named one, the specification a batch's delta is reported in lots of,
resolved once here.
docs/library/index-definitions/index.md is the page."""

import math
from dataclasses import dataclass
from functools import singledispatch
from typing import assert_never, cast

from catalyst.globals.unit_conversions import UnitConversions
from catalyst.index_definitions.contract_specifications import ContractSpecifications
from catalyst.index_definitions.futures_schedule import FuturesSchedule
from catalyst.index_definitions.gas_daily_schedule import GasDailySchedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.holiday_calendars import HolidayCalendars, calendar_of
from catalyst.index_definitions.iferc_schedule import IfercSchedule
from catalyst.index_definitions.index_conventions import CURRENCY, IndexConventions, a_unit_of
from catalyst.index_definitions.kind import (
    Kind,
    named,
    with_holiday_calendar,
    without_holiday_key,
)
from catalyst.index_definitions.published_schedule import PublishedSchedule
from catalyst.instrumentation.work_counts import WorkCounter

type Schedule = FuturesSchedule | IfercSchedule | GasDailySchedule | PublishedSchedule


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
    """The name as the desk typed it, a label and nothing more, and since #169 the display name, a
    description a reader who does not know the desk's short names would understand, kept as
    typed and read for nothing but the readback; the kind, read off the schedule;
    the four objects themselves, kept by reference and unchanged: the schedule, the holiday
    calendar, a futures index's own and None on the other kinds, the conventions and the
    specifications, whose lot units are units of the conventions' quantity type, the one fact
    read across two of them; and the reporting lot, the specification a batch's delta is reported
    in lots of with its conversions resolved once, None when the index was made without one, as an
    index that only builds markets may be. Nothing else is read out of them here or checked
    again."""

    name: str
    display_name: str
    kind: Kind
    schedule: Schedule
    holiday_calendar: HolidayCalendar | None
    conventions: IndexConventions
    specifications: ContractSpecifications
    reporting_lot: ReportingLot | None


def index(
    name: str,
    display_name: str,
    schedule: object,
    conventions: IndexConventions,
    specifications: ContractSpecifications,
    holiday_key: str | None,
    reporting_lot: str | None,
    units: UnitConversions,
    holiday_calendars: HolidayCalendars | None,
    counter: WorkCounter,
) -> Index:
    """The one way to make an Index: the schedule's kind chooses which index is made, the
    holiday key is checked against it and bound to its calendar, the specifications' lot units
    are checked against the conventions' quantity type, the reporting lot, where one is named,
    against the specifications and the tables, and the record is returned once all four hold,
    nothing else.

    The kind is read off the object the seam hands over, the one way the library tells kinds
    apart, as the market history reads its fixings'; an object of no schedule kind is refused
    here in the library's words, since the seam names no kind for it. A futures index names
    its holiday calendar by key, one name of the collection or several joined by a plus sign,
    bound here once by the step every reader of a key shares, calendar_of, and held by
    reference, so nothing later looks a name up; the other kinds leave the key out, and one
    given is refused before it is looked up. Then each lot unit of the specifications is a
    unit of the conventions'
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
    neither unique nor looked up, and the display name, since #169, a description beside it, kept
    as typed too, nothing reading it but the readback, the two free to say the same thing; the
    handle and the price vector's match take the name alone. Whether the four objects are one
    index's is otherwise the desk's
    to keep right, since nothing in any of them says which index it belongs to. Nothing is copied
    and nothing is built but the small record, and the union a key of several names makes; the
    one pass is over the specifications' lot units, one lookup per row, and nothing of the
    schedule is looked at. Work: `holiday_keys_bound`, one for a futures index, and a union's
    own counts.
    """
    kind = _of(schedule)
    calendar = _the_calendar(kind, holiday_key, holiday_calendars, counter)
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
    typed = cast(Schedule, schedule)  # what the kind said
    return Index(name, display_name, kind, typed, calendar, conventions, specifications, lot)


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
def _of(schedule: object) -> Kind:
    raise ValueError(
        f"schedule is {named(schedule)}, expected a futures, IFERC, Gas Daily or published schedule"
    )


@_of.register
def futures_index(schedule: FuturesSchedule) -> Kind:
    return Kind.FUTURES


@_of.register
def iferc_index(schedule: IfercSchedule) -> Kind:
    return Kind.IFERC


@_of.register
def gas_daily_index(schedule: GasDailySchedule) -> Kind:
    return Kind.GAS_DAILY


@_of.register
def published_index(schedule: PublishedSchedule) -> Kind:
    return Kind.PUBLISHED


def _the_calendar(
    kind: Kind,
    holiday_key: str | None,
    holiday_calendars: HolidayCalendars | None,
    counter: WorkCounter,
) -> HolidayCalendar | None:
    """The holiday calendar the kind takes, holiday-keys.md: a futures index's, the one its key
    selects from the collection, the key required; none for the other kinds, a key given refused
    before anything is looked up."""
    match kind:
        case Kind.FUTURES:
            return with_holiday_calendar(
                calendar_of("holiday_key", holiday_key, holiday_calendars, counter)
            )
        case Kind.IFERC | Kind.GAS_DAILY | Kind.PUBLISHED:
            without_holiday_key(holiday_key, kind)
            return None
        case _:
            assert_never(kind)
