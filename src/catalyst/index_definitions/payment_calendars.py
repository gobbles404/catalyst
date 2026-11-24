"""A collection of named holiday calendars, payment-calendar-keys.md: the calendars a batch of
trades or a quote template will select its payment calendars from by name, gathered as they are
and held by reference, nothing of their days read or combined; every member named and each name
once, since a key must select one calendar. A calendar nobody selects costs nothing.
docs/library/index-definitions/collect-payment-calendars.md is the page."""

from dataclasses import dataclass
from typing import Final, cast

from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.instrumentation.work_counts import WorkCounter

CALENDARS_COLLECTED: Final = "calendars_collected"  # one per calendar given, its name read once


@dataclass(frozen=True, slots=True)
class PaymentCalendars:
    """The calendars in the order given, by reference, every one named and the names distinct."""

    calendars: tuple[HolidayCalendar, ...]

    @property
    def names(self) -> tuple[str, ...]:
        # Every member has a name by the one way a collection is made; a member read here is
        # never asked again whether it has one.
        return tuple([cast(str, calendar.name) for calendar in self.calendars])


def collect_payment_calendars(
    calendars: tuple[HolidayCalendar, ...], counter: WorkCounter
) -> PaymentCalendars:
    """The one way to make a PaymentCalendars: every member has a name, the first without one
    refused by its cell, since a key could never select it; and each name once, the first repeat
    refused with the cell it repeats, the same calendar given twice a repeat too, the cells
    counted from one in the order the sheet gave them. Nothing else is checked: no day is read
    or copied, and the calendars are kept as they are, so a collection is remade when one of its
    calendars is and a held one keeps its old members. Work: one calendar per calendar given,
    reported to the counter."""
    first_cell: dict[str, int] = {}
    for i, calendar in enumerate(calendars):
        if calendar.name is None:
            raise ValueError(
                f"calendar_handles cell {i + 1} is a calendar with no name, expected one made "
                "with a name, the word a payment calendar key selects it by"
            )
        first = first_cell.setdefault(calendar.name, i)
        if first != i:
            raise ValueError(
                f"calendar_handles cell {first + 1} and cell {i + 1} are both named "
                f"{calendar.name!r}, expected each name once"
            )
    counter.hit(CALENDARS_COLLECTED, len(calendars))
    return PaymentCalendars(calendars)
