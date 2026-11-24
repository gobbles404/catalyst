"""A collection of holiday calendars, holiday-keys.md: the calendars a batch of trades, a quote
template, an index or a date shift selects its calendar from by name, gathered as they are and
held by reference, nothing of their days read or combined; each name once, since a key must
select one calendar. A calendar nobody selects costs nothing. And the key: one calendar's name,
or several joined by a plus sign, NYFED+LON, read by one rule and bound by one step, which every
reader shares, to the collection's calendar of that name or to the calendar closed on every day
any of the named ones is closed.
docs/library/index-definitions/collect-holiday-calendars.md is the page."""

from dataclasses import dataclass
from typing import Final

from catalyst.index_definitions.holiday_calendar import (
    JOIN,
    HolidayCalendar,
    combine_holiday_calendars,
)
from catalyst.instrumentation.work_counts import WorkCounter

CALENDARS_COLLECTED: Final = "calendars_collected"  # one per calendar given, its name read once
# One per distinct key text a batch binds, however many rows hold it, and one for a quote
# template, an index or a date shift that holds a key; the calendars a key of several names
# combines are counted by the combination's own counts.
KEYS_BOUND: Final = "holiday_keys_bound"
KEY_FORM: Final = "expected a calendar's name, or several joined by '+'"


@dataclass(frozen=True, slots=True)
class HolidayCalendars:
    """The calendars in the order given, by reference, the names distinct."""

    calendars: tuple[HolidayCalendar, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple([calendar.name for calendar in self.calendars])


def collect_holiday_calendars(
    calendars: tuple[HolidayCalendar, ...], counter: WorkCounter
) -> HolidayCalendars:
    """The one way to make a HolidayCalendars: each name once, the first repeat refused with the
    cell it repeats, the same calendar given twice a repeat too, the cells counted from one in
    the order the sheet gave them. Nothing else is checked: no day is read or copied, and the
    calendars are kept as they are, so a collection is remade when one of its calendars is and
    a held one keeps its old members. Work: one calendar per calendar given, reported to the
    counter."""
    first_cell: dict[str, int] = {}
    for i, calendar in enumerate(calendars):
        first = first_cell.setdefault(calendar.name, i)
        if first != i:
            raise ValueError(
                f"calendar_handles cell {first + 1} and cell {i + 1} are both named "
                f"{calendar.name!r}, expected each name once"
            )
    counter.hit(CALENDARS_COLLECTED, len(calendars))
    return HolidayCalendars(calendars)


def calendar_key(where: str, text: str) -> tuple[str, ...]:
    """The names a holiday key holds, sorted, so that NYFED+LON and LON+NYFED are one set of
    names: one name, or several joined by a plus sign with nothing else between them. A name
    missing, NYFED+ or NYFED++LON, a name with whitespace around it and a name given twice,
    which says nothing, are refused in the words of where the key stands, the argument or the
    field and, where a ticket supplied it, the row. Whether the names are calendars of a
    collection is the binding's to say, keyed_calendar; a trade template reads its key by this
    alone."""
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


def calendar_named(collection: HolidayCalendars, name: str) -> HolidayCalendar | None:
    """The collection's calendar of that exact name, or none: matched as it is, case and all,
    with no fallback to the first calendar, a collection of one included."""
    for calendar in collection.calendars:
        if calendar.name == name:
            return calendar
    return None


def keyed_calendar(
    collection: HolidayCalendars,
    combined: dict[tuple[str, ...], HolidayCalendar],
    counter: WorkCounter,
    where: str,
    text: str,
) -> HolidayCalendar:
    """The calendar a key selects, the one step a key is bound by, whoever binds it: the key
    read by calendar_key; each name found in the collection exactly, the first that is not
    refused with the names the collection holds; one name the collection's calendar itself, by
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


def calendar_of(
    where: str, key: str | None, collection: HolidayCalendars | None, counter: WorkCounter
) -> HolidayCalendar | None:
    """The calendar the one key of a reader selects, for the readers that hold at most one, a
    quote template, an index and a date shift: none for no key, whatever came with it, since a
    collection nothing selects from is read for nothing; a key with no collection refused by
    the argument; otherwise the key bound by keyed_calendar. Work: `holiday_keys_bound`, one
    for a key bound; a key of several names adds the combination's own counts."""
    if key is None:
        return None
    if collection is None:
        raise no_collection(where)
    bound = keyed_calendar(collection, {}, counter, where, key)
    counter.hit(KEYS_BOUND, 1)
    return bound


def no_collection(reader: str) -> ValueError:
    """The one refusal of a key with no collection to select from, for whoever needed one to
    raise: a financially settled batch, or the key of a quote template, an index or a date
    shift."""
    return ValueError(
        "holiday_calendars is missing, expected a _CollectHolidayCalendars collection, which "
        f"{reader} selects a calendar from"
    )


def _quoted(names: tuple[str, ...]) -> str:
    """Names in a message: `'NYFED'`, `'NYFED' and 'LON'`, `'NYFED', 'LON' and 'TOK'`, and
    `none` for a collection of no calendars, which the library can make and the sheet cannot."""
    quoted = [repr(name) for name in names]
    if len(quoted) < 2:
        return quoted[0] if quoted else "none"
    return f"{', '.join(quoted[:-1])} and {quoted[-1]}"
