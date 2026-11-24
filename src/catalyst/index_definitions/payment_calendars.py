"""A collection of named holiday calendars, payment-calendar-keys.md: the calendars a batch of
trades or a quote template will select its payment calendars from by name, gathered as they are
and held by reference, nothing of their days read or combined; every member named and each name
once, since a key must select one calendar. A calendar nobody selects costs nothing. And the
key: one calendar's name, or several joined by a plus sign, NYFED+LON, read by one rule and
bound by one step, which a batch of trades and a quote template share, to the collection's
calendar of that name or to the calendar closed on every day any of the named ones is closed.
docs/library/index-definitions/collect-payment-calendars.md is the page."""

from dataclasses import dataclass
from typing import Final, cast

from catalyst.index_definitions.holiday_calendar import (
    JOIN,
    HolidayCalendar,
    combine_holiday_calendars,
)
from catalyst.instrumentation.work_counts import WorkCounter

CALENDARS_COLLECTED: Final = "calendars_collected"  # one per calendar given, its name read once
# One per distinct key text a batch or a quote template binds, however many rows hold it; the
# calendars a key of several names combines are counted by the combination's own counts.
KEYS_BOUND: Final = "payment_keys_bound"
KEY_FORM: Final = "expected a calendar's name, or several joined by '+'"


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


def calendar_key(where: str, text: str) -> tuple[str, ...]:
    """The names a payment calendar key holds, sorted, so that NYFED+LON and LON+NYFED are one
    set of names: one name, or several joined by a plus sign with nothing else between them.
    A name missing, NYFED+ or NYFED++LON, a name with whitespace around it and a name given
    twice, which says nothing, are refused in the words of where the key stands, the field
    and, where a ticket supplied it, the row. Whether the names are calendars of a collection
    is the binding's to say, payment_calendar; a trade template reads its key by this alone."""
    names = text.split(JOIN)
    for name in names:
        if not name:
            raise ValueError(f"{where} is {text!r}, {KEY_FORM}; a name is missing")
        if name != name.strip():
            raise ValueError(f"{where} is {text!r}, {KEY_FORM}, each with no whitespace around it")
    if len(set(names)) != len(names):
        twice = next(name for i, name in enumerate(names) if name in names[:i])
        raise ValueError(f"{where} is {text!r}, {KEY_FORM}, each once; {twice!r} is given twice")
    return tuple(sorted(names))


def calendar_named(collection: PaymentCalendars, name: str) -> HolidayCalendar | None:
    """The collection's calendar of that exact name, or none: matched as it is, case and all,
    with no fallback to the first calendar, a collection of one included."""
    for calendar in collection.calendars:
        if calendar.name == name:
            return calendar
    return None


def payment_calendar(
    collection: PaymentCalendars,
    combined: dict[tuple[str, ...], HolidayCalendar],
    counter: WorkCounter,
    where: str,
    text: str,
) -> HolidayCalendar:
    """The calendar a key selects, the one step a key is bound by, whoever binds it, a batch of
    trades for each of its distinct keys or a quote template for its one: the key read by
    calendar_key; each name found in the collection exactly, the first that is not refused
    with the names the collection holds; one name the collection's calendar itself, by
    reference and nothing made; several the calendar closed on every day any of them is
    closed, combine_holiday_calendars, made once per set of names and kept in `combined`, the
    caller's for one batch, so that NYFED+LON on every row, or beside LON+NYFED, is one
    calendar and rows that share it are counted together."""
    names = calendar_key(where, text)
    made = combined.get(names)
    if made is not None:
        return made
    members: list[HolidayCalendar] = []
    for name in names:
        member = calendar_named(collection, name)
        if member is None:
            raise ValueError(
                f"{where} is {text!r}, expected names of the collection's calendars, "
                f"{_quoted(collection.names)}; it holds no {name!r}"
            )
        members.append(member)
    made = members[0] if len(members) == 1 else combine_holiday_calendars(members, counter)
    combined[names] = made
    return made


def no_collection(reader: str) -> ValueError:
    """The one refusal of a key with no collection to select from, for whoever needed one to
    raise: a financially settled batch, or a quote template that holds a key."""
    return ValueError(
        "payment_calendars is missing, expected a _CollectPaymentCalendars collection, which "
        f"{reader} selects its payment calendar from"
    )


def _quoted(names: tuple[str, ...]) -> str:
    """Names in a message: `'NYFED'`, `'NYFED' and 'LON'`, `'NYFED', 'LON' and 'TOK'`, and
    `none` for a collection of no calendars, which the library can make and the sheet cannot."""
    quoted = [repr(name) for name in names]
    if len(quoted) < 2:
        return quoted[0] if quoted else "none"
    return f"{', '.join(quoted[:-1])} and {quoted[-1]}"
