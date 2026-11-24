"""The four schedule methods, lastday, penultimate, last3day and asian: the one place their
names and encoded positions live. A resolved batch holds each occurrence's method as its position
among METHODS, 0 lastday, 1 penultimate, 2 last3day, 3 asian, so that the kernel gathers and
compares positions and never texts, and a reader turns a position back into its name through
METHOD_NAMES. The template reads the entered text into the enum, the observations make each
method's days and weights, the encoding derives each observation's pricing contract; this module
names, and holds the five facts the stages share about the methods as rules over a batch's
method codes, each a mask the stage that applies it reads, the check and its refusal staying
with that stage; it imports nothing of theirs. docs/library/trades/kernel.md is the page."""

from enum import Enum
from typing import Final

import numpy as np
from numpy.typing import NDArray


class ScheduleMethod(Enum):
    """Which observations set a contract's final price. lastday, the settlement on the contract's
    last trading day, or on an IFERC index the month's index on its publication day, the one
    method an IFERC index takes since #167; penultimate, the settlement on the business day before
    the last trading day; last3day, the average of the settlements on the last trading day and the
    two business days before it, each a third; and asian, the average of the settles on every
    pricing day the component covers, its contract's calendar month or the booked part of it, each
    day's settle the contract the index's calendar prices that day with, which need not be the
    component's own, an equal share each: the four methods the definition lists, all built."""

    LASTDAY = "lastday"
    PENULTIMATE = "penultimate"
    LAST3DAY = "last3day"
    ASIAN = "asian"


METHODS: Final = tuple(ScheduleMethod)
METHOD_NAMES: Final = np.array([member.value for member in METHODS], dtype=object)
METHOD_NAMES.setflags(write=False)


def supported_on_iferc(method: NDArray[np.intp]) -> NDArray[np.bool_]:
    """lastday alone: an IFERC month has one index, published once, so the one observation is the
    month's index on its publication day. The terms refuse a batch with any other method on an
    IFERC index, and the observations read the same rule before making the month's day."""
    return method == METHODS.index(ScheduleMethod.LASTDAY)


def supported_on_published(method: NDArray[np.intp]) -> NDArray[np.bool_]:
    """asian alone: a published month is the average of the prints that count toward it, an
    equal share each. penultimate and last3day count business days back from an expiry, and a
    published index has neither; lastday is refused until the IFERC index, one print a month,
    moves onto the published kind. The terms refuse a batch with any other method on a published
    index, and the observations read the same rule before making a month's prints."""
    return method == METHODS.index(ScheduleMethod.ASIAN)


def permits_physical_settlement(method: NDArray[np.intp]) -> NDArray[np.bool_]:
    """lastday alone, on a futures index: a penultimate, last3day or asian future is cash settled
    on a price other than the expiry's settle, so a physical batch is lastday rows alone. The
    terms apply it; an IFERC index takes a financial settlement whatever the method."""
    return method == METHODS.index(ScheduleMethod.LASTDAY)


def requires_whole_month(method: NDArray[np.intp]) -> NDArray[np.bool_]:
    """The three expiry-based methods take a component that covers its contract's whole month;
    asian prices the booked part of one. The observations apply it before any day is made."""
    return method != METHODS.index(ScheduleMethod.ASIAN)


def counts_back_from_expiry(method: NDArray[np.intp]) -> NDArray[np.bool_]:
    """penultimate and last3day count business days back from the expiry, so the expiry must be
    a day the market prices; the observations apply it. lastday's closed expiry is the
    encoding's to refuse, as a day the market is closed."""
    return (method == METHODS.index(ScheduleMethod.PENULTIMATE)) | (
        method == METHODS.index(ScheduleMethod.LAST3DAY)
    )


def requires_booked_reference(method: NDArray[np.intp]) -> NDArray[np.bool_]:
    """All but asian price every observation off the component's own contract, the booked
    reference; under asian the calendar gives each day its pricing contract, which may roll.
    The encoding applies it when it derives the references. The whole-month and the
    booked-reference facts select the same methods today and are two facts all the same."""
    return method != METHODS.index(ScheduleMethod.ASIAN)
