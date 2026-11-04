"""The kinds of index, and the words that name a kind or an object in a message: which market an
index is of, read off its schedule, a schedule, a calendar or an index of a kind named, and the
holiday calendar each kind takes. The index, the calendar, the fixings and the history read a
kind from here and nowhere else. docs/library/index-definitions/index.md and
docs/library/calendar/calendar.md are the pages."""

import re
from enum import Enum

from catalyst.index_definitions.holiday_calendar import HolidayCalendar


class Kind(Enum):
    """The market an index is of, read off the schedule it was defined by."""

    FUTURES = "futures"
    IFERC = "IFERC"
    GAS_DAILY = "Gas Daily"


def described(kind: Kind, what: str = "calendar") -> str:
    """A calendar, a schedule or an index of that kind named in a message: a futures calendar,
    an IFERC schedule, a Gas Daily index."""
    article = "an" if kind is Kind.IFERC else "a"
    return f"{article} {kind.value} {what}"


def named(obj: object) -> str:
    """An object of no expected kind named in a message by its class, in the words the seam gives
    a handle's kind: a holiday calendar, futures fixings, an iferc schedule, an index."""
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", type(obj).__name__).lower()
    if words.endswith("s"):
        return words
    return f"{'an' if words[0] in 'aeiou' else 'a'} {words}"


def with_holiday_calendar(holiday_calendar: HolidayCalendar | None) -> HolidayCalendar:
    """A futures index's holiday calendar, required: its market closes on days its schedule does
    not say, so a calendar left out is refused rather than guessed. Read through an index, it
    is the calendar the index was made with, never missing, and this is the one way to say so."""
    if holiday_calendar is None:
        raise ValueError(
            "holiday_calendar is missing, expected holiday calendar handle with a futures schedule"
        )
    return holiday_calendar


def without_holiday_calendar(holiday_calendar: HolidayCalendar | None, kind: Kind) -> None:
    """An IFERC or a Gas Daily index takes no holiday calendar, since every period of theirs
    prices; one given is refused, since nothing reads it: fail loudly rather than ignore."""
    if holiday_calendar is not None:
        raise ValueError(
            "holiday_calendar is a holiday calendar, "
            f"expected none with {described(kind, 'schedule')}"
        )
