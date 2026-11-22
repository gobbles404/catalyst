"""Holiday calendars for tests, since holiday-keys.md: every calendar has a name and an index
names its calendar by key from a collection. A test that cares for a calendar's days alone, or
that holds the calendar it wants an index to price on, says so through here.
"""

from itertools import count

import numpy as np
from numpy.typing import NDArray

from catalyst.excel import bridge
from catalyst.globals.unit_conversions import UnitConversions
from catalyst.index_definitions.contract_specifications import ContractSpecifications
from catalyst.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from catalyst.index_definitions.holiday_calendars import (
    HolidayCalendars,
    collect_holiday_calendars,
)
from catalyst.index_definitions.index import Index, index
from catalyst.index_definitions.index_conventions import IndexConventions
from catalyst.instrumentation.work_counts import WorkCounter

_NAMES = count(1)


def a_name() -> str:
    """A calendar name no other test calendar has: CAL1, CAL2, in the order asked."""
    return f"CAL{next(_NAMES)}"


def closed_on(holiday: NDArray[np.datetime64]) -> HolidayCalendar:
    """A calendar closed on the days given, for a test that reads its days and not its name:
    made by the library's one way, under a name of its own."""
    return holiday_calendar(a_name(), holiday)


def key_in(handle: object) -> str:
    """The key of a calendar a test made through the seam, read off its handle, which shows the
    name between the kind and the count, `30512:holiday_calendar:CAL7:12`: for a test that made
    the calendar under a name of this module's, which holds no colon."""
    process, kind, name, count = str(handle).split(":")
    assert kind == "holiday_calendar" and process and count, handle
    return name


def key_and_collection(handle: object) -> tuple[object, object]:
    """What a seam call names its calendar by, for a test that holds the calendar's handle or
    left it out: the key the handle shows and a collection of that one calendar, published
    here, or the seam's MISSING twice where there is no calendar."""
    if handle is bridge.MISSING:
        return bridge.MISSING, bridge.MISSING
    return key_in(handle), bridge.entry("_CollectHolidayCalendars")(handle)


def holding(calendar: HolidayCalendar | None) -> HolidayCalendars | None:
    """The collection of that one calendar, or none for none."""
    return None if calendar is None else collect_holiday_calendars((calendar,), WorkCounter())


def index_on(
    name: str,
    display_name: str,
    schedule: object,
    conventions: IndexConventions,
    specifications: ContractSpecifications,
    calendar: HolidayCalendar | None,
    reporting_lot: str | None,
    units: UnitConversions,
) -> Index:
    """The index a test wants on a calendar it holds: made by the library's one way, the
    calendar's name its key and a collection of that one calendar what the key selects from;
    no key and no collection where the test holds no calendar."""
    return index(
        name,
        display_name,
        schedule,
        conventions,
        specifications,
        None if calendar is None else calendar.name,
        reporting_lot,
        units,
        holding(calendar),
        WorkCounter(),
    )
