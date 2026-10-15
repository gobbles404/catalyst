"""A trade template: shared field values under one instrument's definition, created once from a
template's row and taken, last and required, by every batch of trades whose ticket supplies the
rest. The template retains the definition and its own values and no index, so one template
serves every compatible index. It reads each value it holds for the rule intrinsic to its field,
a code from its list, a lag of positive business days within the sheet's calendar, a contract
code or strip the period grammar reads, a whole quantity, zero included, a finite price, and
leaves the rules that need the ticket or the index, which fields are required, whether the two
overlap, the schedule, to the resolution of a batch. Those readers live here, since resolution
reads the ticket's values by the same rules, and the two numeric ones are the kernel's own.
docs/library/trades/trade-template.md is the page."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, assert_never

import numpy as np

from goosedove.index_definitions.periods import period_months
from goosedove.instruments.definitions import FieldType, Instrument
from goosedove.instruments.fields import FieldValues, selected
from goosedove.trades.terms import (
    QuantityPer,
    Route,
    ScheduleMethod,
    Settlement,
    finite_prices,
    whole_quantities,
)


@dataclass(frozen=True, slots=True)
class TradeTemplate:
    """The instrument, the definition the fields were bound against, and the defaults by field
    name, in the sheet's order: each the one value the template's row held, a number as a
    float, a date as a numpy day, text and a code as text, a holiday calendar as the object its
    handle stood for; owned, each being a scalar or an object the library already holds, and
    read for nothing until a batch is resolved."""

    instrument: Instrument
    defaults: Mapping[str, object]


def trade_template(values: FieldValues) -> TradeTemplate:
    """The one way to make a TradeTemplate: one row of field values, each value taken off its
    column and read once for the rule intrinsic to its field, in the sheet's order, the first
    failure being the message. Nothing is required, since a template is a partial record and the
    ticket supplies the rest, and no index is read, since the template retains none: a
    specification name waits for the index the batch is created on."""
    if values.rows != 1:
        raise ValueError(f"values has {values.rows} rows, expected one row of field values")
    defaults = {name: _value(values, name) for name in values.names}
    return TradeTemplate(values.instrument, MappingProxyType(defaults))


@selected.register
def by_template(selector: TradeTemplate) -> Instrument:
    """The instrument a template holds, the form _CreateTrades takes."""
    return selector.instrument


def _value(values: FieldValues, name: str) -> object:
    """The one value of a field in a one-row record, as the scalar its type names, read for the
    field's own rule where it has one: a number for the kernel's, text for its list or grammar; a
    date and a holiday calendar mean what they are."""
    field_type = values.field(name).type
    match field_type:
        case FieldType.NUMBER:
            number = float(values.numbers(name)[0])
            read = NUMBER_READERS.get(name)
            return number if read is None else read(name, number)
        case FieldType.DATE:
            return values.dates(name)[0]
        case FieldType.TEXT | FieldType.CODE:
            text = values.texts(name)[0]
            read = READERS.get(name)
            if read is not None:
                read(name, text)
            return text
        case FieldType.HOLIDAY_CALENDAR:
            return values.objects(name)[0]
        case _:
            assert_never(field_type)


# --- what each field's text means, read the same way in a template and in a ticket ------------


def choice[E: Enum](where: str, text: str, kind: type[E], expected: str) -> E:
    """The member of an enum whose value is the text, exactly, case and all: the enums hold the
    choices built, so a choice the definition lists but the library has not built fails by name
    as an unknown one does."""
    try:
        return kind(text)
    except ValueError:
        raise ValueError(f"{where} is {text!r}, expected {expected}") from None


def route_of(where: str, text: str) -> Route:
    return choice(where, text, Route, "cleared or bilateral")


def settlement_of(where: str, text: str) -> Settlement:
    return choice(where, text, Settlement, "physical or financial")


def schedule_method_of(where: str, text: str) -> ScheduleMethod:
    return choice(
        where, text, ScheduleMethod, "lastday, penultimate or last3day, the three methods built"
    )


def quantity_per_of(where: str, text: str) -> QuantityPer:
    return choice(where, text, QuantityPer, "month, the one basis built")


_LAG: Final = re.compile(r"\+([1-9]\d*)bd")

# The sheet's calendar, as the seam holds it: serial 61, 1 March 1900, the first day Excel's
# serials and the real calendar agree on, to serial 2958465, 31 December 9999, the last day a
# cell can show. A payment day outside it could never reach a cell, so a lag is held to it
# here, where the lag is read, and the day it makes is held to it where the day is made.
SHEET_FIRST_DAY: Final = np.datetime64("1900-03-01", "D")
SHEET_LAST_DAY: Final = np.datetime64("9999-12-31", "D")
# The business days from the first day to the last, Monday to Friday: the most a lag can count
# between two days a sheet can show, since a holiday calendar only lowers the count.
MOST_BUSINESS_DAYS: Final = int(np.busday_count(SHEET_FIRST_DAY, SHEET_LAST_DAY))


def business_days_of(where: str, text: str) -> int:
    """The positive whole number of business days a payment lag states, `+1bd` or `+2bd`: counted
    strictly after the anchor by the resolution, so zero, which would need a rule for a closed
    anchor, is refused with every other spelling; and at most the business days of the sheet's
    calendar end to end, since a longer lag could pay on no day a cell can show, and a longer
    number still would fail unnamed, in the day arithmetic or, past 4,300 digits, in Python's
    own conversion. The day itself is checked where it is made, against the calendar it is
    counted on."""
    found = _LAG.fullmatch(text)
    if found is None:
        raise ValueError(
            f"{where} is {text!r}, expected a positive whole number of business days, such as +1bd"
        )
    digits = found.group(1)
    # Counted before any is converted: a cell holds up to 32,767 characters and Python refuses
    # to convert more than 4,300 digits with words of its own, so a lag with more digits than
    # the bound has is refused here by name, and only a shorter one is read as a number.
    if len(digits) > len(str(MOST_BUSINESS_DAYS)) or int(digits) > MOST_BUSINESS_DAYS:
        raise ValueError(
            f"{where} is {text!r}, expected at most {MOST_BUSINESS_DAYS:,} business days, "
            f"the sheet's calendar from {SHEET_FIRST_DAY} to {SHEET_LAST_DAY} end to end"
        )
    return int(digits)


def quantity_of(where: str, number: float) -> float:
    """A quantity by the kernel's rule, whole, zero included, named by its field."""
    whole_quantities(np.array([number]), lambda _: where)
    return number


def price_of(where: str, number: float) -> float:
    """A price by the kernel's rule, finite, named by its field."""
    finite_prices(np.array([number]), lambda _: where)
    return number


def months_of(where: str, text: str) -> tuple[int, int]:
    """The first month of a contract code or strip and the month after its last, as numpy counts
    months, through the period grammar, which reads `Z26`, `z26`, `CAL27` and `Z27-X28` alike;
    its refusal is given again naming the field and the text as the sheet has them."""
    try:
        first, after = period_months(text)
    except ValueError as refusal:
        reason = str(refusal).partition(", expected ")[2]
        raise ValueError(f"{where} is {text!r}, expected {reason}") from None
    return int(first.astype(np.int64)), int(after.astype(np.int64))


# The readers by field name: the text fields whose text means something beyond being text, and
# the two numbers the kernel has a rule for; the labels and the dates are read by nobody.
READERS: Final[Mapping[str, Callable[[str, str], object]]] = MappingProxyType(
    {
        "contract_code": months_of,
        "schedule_method": schedule_method_of,
        "route": route_of,
        "settlement_method": settlement_of,
        "quantity_per": quantity_per_of,
        "payment_time_lag": business_days_of,
    }
)
NUMBER_READERS: Final[Mapping[str, Callable[[str, float], float]]] = MappingProxyType(
    {"quantity": quantity_of, "fixed_price": price_of}
)
