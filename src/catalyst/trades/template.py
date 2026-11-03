"""A trade template: shared field values under one instrument's definition, created once from a
template's row and taken, last and required, by every batch of trades whose ticket supplies the
rest. The template retains the definition, the fields its row named and its own values and no
index, so one template serves every compatible index. It reads each value it holds for the rule
intrinsic to its field, a code from its list, a payment day as the date it holds or as a rule
of one or more date instructions read whole, a whole quantity, zero included, a finite price,
and leaves the rules that need the ticket or the index, which fields are required, whether the
two overlap, the schedule, whether a
contract code is the period of any row, to the resolution of a batch: since #172 a template's
contract_code is text the seam typed and nothing more until a row without dates uses it, and a
period field's cell may hold nothing, the header then owning the field for every batch while no
row takes a value from it. Those readers live here, since resolution reads the ticket's values
by the same rules, and the two numeric ones are the kernel's own.
docs/library/trades/trade-template.md is the page."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, assert_never

import numpy as np

from catalyst.cashflows.rules import currency_of, finite_amounts
from catalyst.globals.discount_curve import curve_name
from catalyst.index_definitions.date_offsets import Instruction, read_offset
from catalyst.index_definitions.periods import period_months
from catalyst.instruments.definitions import FieldType, Instrument
from catalyst.instruments.fields import FieldValues, selected
from catalyst.trades.schedule_methods import ScheduleMethod
from catalyst.trades.terms import (
    QuantityPer,
    Route,
    Settlement,
    SettlementFrequency,
    finite_prices,
    marketing_reserves,
    whole_quantities,
    whole_trade_ids,
)


@dataclass(frozen=True, slots=True)
class TradeTemplate:
    """The instrument, the definition the fields were bound against; the names, the fields the
    template's row named, in the sheet's order, each one the template owns for every batch made
    under it, so that a ticket's column of the same name is refused whatever either holds; and
    the defaults by field name, in the same order: each the one value the row held, a number as
    a float, a date as a numpy day, text and a code as text, a holiday calendar as the object its
    handle stood for, and since payment-day-date-or-rule.md the payment day as a DayOrRule, the
    day or the rule text the row held; owned, each being a scalar or an object the library
    already holds, and read for nothing until a batch is resolved. Since #172 a name may stand
    with no default: a
    period field, contract_code, start_date or end_date, whose cell held nothing, which the
    template then supplies to no row, as its page says."""

    instrument: Instrument
    names: tuple[str, ...]
    defaults: Mapping[str, object]


def trade_template(values: FieldValues) -> TradeTemplate:
    """The one way to make a TradeTemplate: one row of field values, each value taken off its
    column and read once for the rule intrinsic to its field, in the sheet's order, the first
    failure being the message; a period field whose cell held nothing is a name without a value.
    Nothing is required, since a template is a partial record and the ticket supplies the rest,
    and no index is read, since the template retains none: a specification name waits for the
    index the batch is created on, and a contract code for the rows that book by it."""
    if values.rows != 1:
        raise ValueError(f"values has {values.rows} rows, expected one row of field values")
    defaults = {name: field_value(values, name) for name in values.names if _holds(values, name)}
    return TradeTemplate(values.instrument, values.names, MappingProxyType(defaults))


def _holds(values: FieldValues, name: str) -> bool:
    """Whether the one row supplied the field's value: every field but one whose cells may go
    unsupplied did, and that one did when its cell held a value."""
    mask = values.supplied.get(name)
    return mask is None or bool(mask[0])


@selected.register
def by_template(selector: TradeTemplate) -> Instrument:
    """The instrument a template holds, the form _CreateTrades takes."""
    return selector.instrument


@dataclass(frozen=True, slots=True)
class DayOrRule:
    """A payment day as a template holds it, since payment-day-date-or-rule.md: the one day the
    row entered, or the one rule text it entered, read whole for the grammar when the template
    was made, the other None; the seam told the two apart by type, so nothing here or after
    asks which a value is."""

    day: np.datetime64 | None
    rule: str | None


def field_value(values: FieldValues, name: str) -> object:
    """The one value of a field in a one-row record, as the scalar its type names, read for the
    field's own rule where it has one: a number for the kernel's, text for its list or grammar; a
    date, a holiday calendar and since #172 a contract code mean what they are, the code read for
    its months by the resolution, for the rows that book by it, and by nothing here; a payment
    day, since payment-day-date-or-rule.md, is the day it holds, or its rule text read for the
    grammar, as a DayOrRule. A quote template reads its values by the same rule, since
    template-based-quoting.md."""
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
        case FieldType.DATE_OR_TEXT:
            entered = values.dates_or_texts(name)
            if entered.is_date[0]:
                return DayOrRule(entered.dates[0], None)
            text = entered.texts[0]
            read = READERS.get(name)
            if read is not None:
                read(name, text)
            return DayOrRule(None, text)
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
    return choice(where, text, ScheduleMethod, "lastday, penultimate, last3day or asian")


def quantity_per_of(where: str, text: str) -> QuantityPer:
    return choice(where, text, QuantityPer, "month, calday or period")


def settlement_frequency_of(where: str, text: str) -> SettlementFrequency:
    """The frequency choice, since onetime-averaging.md: both words are read here, in a template
    as in a ticket, and whether a consumer prices onetime is that consumer's rule."""
    return choice(where, text, SettlementFrequency, "monthly or onetime")


def payment_rule_of(where: str, text: str) -> tuple[Instruction, ...]:
    """The instructions of a payment rule, `+1bd`, `+3cd`, `+0em` or a chain such as
    `+3em+25cd-1bd+1bd`, read whole before any is applied, as the date utility reads an offset and
    in its words, since #181: one or more of a sign, a whole count of at most seven significant
    digits and bd, cd or em in either case, nothing between or after. Zero and negative counts are
    steps like any other; the day the rule makes is held to the sheet's calendar where it is made
    and after each component's last observation by the kernel, so a rule that pays on or before
    the final price is refused there, not here."""
    return read_offset(where, text)


def quantity_of(where: str, number: float) -> float:
    """A quantity by the kernel's rule, whole, zero included, named by its field."""
    whole_quantities(np.array([number]), lambda _: where)
    return number


def price_of(where: str, number: float) -> float:
    """A price by the kernel's rule, finite, named by its field."""
    finite_prices(np.array([number]), lambda _: where)
    return number


def trade_id_of(where: str, number: float) -> int:
    """A trade ID by the kernel's rule, a whole number of at most 15 digits, named by its field,
    since #168: the one integer a template holds, read once here and repeated for every row."""
    return int(whole_trade_ids(np.array([number]), lambda _: where)[0])


def marketing_reserve_of(where: str, number: float) -> float:
    """A marketing reserve by the reserves' rule, finite and zero or more, named by its field,
    since #175: the one amount a template holds, read once here and booked once by every row of
    a batch made under it."""
    marketing_reserves(np.array([number]), lambda _: where)
    return number


def amount_of(where: str, number: float) -> float:
    """A cashflow's amount by the cashflows' rule, finite, zero and fractions included, named by
    its field, since #200: the one amount a template holds, every row of a batch made under it
    paying it."""
    finite_amounts(np.array([number]), lambda _: where)
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
# the four numbers the library has a rule for, the trade ID since #168 and the marketing
# reserve since #175; the three labels and the dates are read by nobody, and since #172 neither
# is a contract code, which the resolution reads for the rows that book by it, a row with both
# dates keeping it as entered text.
READERS: Final[Mapping[str, Callable[[str, str], object]]] = MappingProxyType(
    {
        "schedule_method": schedule_method_of,
        "second_schedule_method": schedule_method_of,  # two-index-fixed-float.md
        "route": route_of,
        "settlement_method": settlement_of,
        "quantity_per": quantity_per_of,
        "settlement_frequency": settlement_frequency_of,  # onetime-averaging.md
        "payment_day": payment_rule_of,  # the rule form; a date is read by nobody
        "discount_curve_key": curve_name,  # the curve's own name rule, named-curves-slice-3.md
        "currency": currency_of,  # the cashflow instrument's, since #200
    }
)
NUMBER_READERS: Final[Mapping[str, Callable[[str, float], float | int]]] = MappingProxyType(
    {
        "trade_id": trade_id_of,
        "quantity": quantity_of,
        "fixed_price": price_of,
        "second_fixed_price": price_of,  # two-index-fixed-float.md
        "marketing_reserve": marketing_reserve_of,
        "amount": amount_of,  # the cashflow instrument's, since #200
    }
)
