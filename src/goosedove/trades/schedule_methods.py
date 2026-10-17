"""The four schedule methods, lastday, penultimate, last3day and asian: the one place their
names and encoded positions live. A resolved batch holds each occurrence's method as its position
among METHODS, 0 lastday, 1 penultimate, 2 last3day, 3 asian, so that the kernel gathers and
compares positions and never texts, and a reader turns a position back into its name through
METHOD_NAMES. The template reads the entered text into the enum, the observations make each
method's days and weights, the encoding derives each observation's pricing contract; this module
names, and imports nothing of theirs. docs/library/trades/kernel.md is the page."""

from enum import Enum
from typing import Final

import numpy as np


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
