"""The kinds of index, and the words that name a kind or an object in a message: which market an
index is of, read off its schedule, the schedule and the calendar of each kind named, and the
holiday calendar each kind takes. The index, the calendar and the history read a kind from here
and nowhere else. docs/library/index-definitions/index.md and docs/library/calendar/calendar.md
are the pages."""

import re
from enum import Enum
from typing import assert_never

from goosedove.index_definitions.holiday_calendar import HolidayCalendar


class Kind(Enum):
    """The market an index is of, read off the schedule it was defined by."""

    FUTURES = "futures"
    IFERC = "IFERC"
    GAS_DAILY = "Gas Daily"


def described(kind: Kind) -> str:
    """A calendar of that kind named in a message: a futures calendar, an IFERC calendar."""
    match kind:
        case Kind.FUTURES:
            return "a futures calendar"
        case Kind.IFERC:
            return "an IFERC calendar"
        case Kind.GAS_DAILY:
            return "a Gas Daily calendar"
        case _:
            assert_never(kind)


def schedule_of(kind: Kind) -> str:
    """A schedule of that kind named in a message: a futures schedule, an IFERC schedule."""
    match kind:
        case Kind.FUTURES:
            return "a futures schedule"
        case Kind.IFERC:
            return "an IFERC schedule"
        case Kind.GAS_DAILY:
            return "a Gas Daily schedule"
        case _:
            assert_never(kind)


def named(obj: object) -> str:
    """An object of no expected kind named in a message by its class, in the words the seam gives
    a handle's kind: a holiday calendar, futures fixings, an iferc schedule, an index."""
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", type(obj).__name__).lower()
    if words.endswith("s"):
        return words
    return f"{'an' if words[0] in 'aeiou' else 'a'} {words}"


def with_holiday_calendar(holiday_calendar: HolidayCalendar | None) -> HolidayCalendar:
    """A futures index's holiday calendar, required: its market closes on days its schedule does
    not say, so a calendar left out is refused rather than guessed."""
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
            f"holiday_calendar is a holiday calendar, expected none with {schedule_of(kind)}"
        )
