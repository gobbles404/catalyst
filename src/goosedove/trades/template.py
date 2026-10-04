"""A trade template: shared field values under one instrument's definition, created once from a
template's row and taken, last and required, by every batch of trades whose ticket supplies the
rest. The template retains the definition and its own values and no index, so one template
serves every compatible index. It reads each value it holds for the rule intrinsic to its field,
a code from its list, a lag of positive business days, a contract code or strip the period
grammar reads, and leaves the rules that need the ticket or the index, which fields are required,
whether the two overlap, the schedule, to the resolution of a batch. Those readers live here,
since resolution reads the ticket's values by the same rules.
docs/library/trades/trade-template.md is the page."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, assert_never, cast

import numpy as np

from goosedove.index_definitions.periods import period_months
from goosedove.instruments.definitions import FieldType, Instrument
from goosedove.instruments.fields import FieldValues, selected
from goosedove.trades.terms import QuantityPer, Route, ScheduleMethod, Settlement, lot_unit


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
    for name, value in defaults.items():
        read = READERS.get(name)
        if read is not None:
            read(name, cast(str, value))
    return TradeTemplate(values.instrument, MappingProxyType(defaults))


@selected.register
def by_template(selector: TradeTemplate) -> Instrument:
    """The instrument a template holds, the form _CreateTrades takes."""
    return selector.instrument


def _value(values: FieldValues, name: str) -> object:
    """The one value of a field in a one-row record, as the scalar its type names."""
    match values.field(name).type:
        case FieldType.NUMBER:
            return float(values.numbers(name)[0])
        case FieldType.DATE:
            return values.dates(name)[0]
        case FieldType.TEXT | FieldType.CODE:
            return values.texts(name)[0]
        case FieldType.HOLIDAY_CALENDAR:
            return values.objects(name)[0]
        case _:
            assert_never(values.field(name).type)


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
    return choice(where, text, ScheduleMethod, "lastday, the one method built")


def quantity_per_of(where: str, text: str) -> QuantityPer:
    return choice(where, text, QuantityPer, "month, the one basis built")


_LAG: Final = re.compile(r"\+([1-9]\d*)bd")


def business_days_of(where: str, text: str) -> int:
    """The positive whole number of business days a payment lag states, `+1bd` or `+2bd`: counted
    strictly after the anchor by the resolution, so zero, which would need a rule for a closed
    anchor, is refused with every other spelling."""
    found = _LAG.fullmatch(text)
    if found is None:
        raise ValueError(
            f"{where} is {text!r}, expected a positive whole number of business days, such as +1bd"
        )
    return int(found.group(1))


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


# The readers by field name, for the fields whose text means something beyond being text; the
# others, the labels, the dates and the numbers, are read by the kernel's rules or by nobody.
READERS: Final[Mapping[str, Callable[[str, str], object]]] = MappingProxyType(
    {
        "contract_code": months_of,
        "schedule_method": schedule_method_of,
        "route": route_of,
        "settlement_method": settlement_of,
        "quantity_unit": lot_unit,
        "quantity_per": quantity_per_of,
        "payment_time_lag": business_days_of,
    }
)
