"""A quote template: the static terms of a quote under the fixed_float's definition, created once
from a template's row and taken by every quote made under it beside the market and the contract
code the quote prices. It retains the definition, the fields its row named and their values, as
a trade template holds its defaults, and no index, market, period or quantity: a quote prices one
contract or strip on the market it is given, and nothing is booked. Which fields it may hold is
the definition's own metadata, the quote_allowed row of _ShowInstrument: the four codes, the
curve key and the two payment fields, so a booking fact, an identifier, a date, the quantity and
its unit, the price, a label or the reserve, is refused by name, and so is a period field, whose
cell may be blank for a trade template and here owns nothing, the quote's own argument being the
period. Each value is read once for the rule intrinsic to its field by the trade template's
reader, the same word meaning the same thing in a quote and in a booking. Nothing is required: a
template is a partial record, and what a completed quote needs is the quote's rule.
docs/library/quoting/quote-template.md is the page."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from goosedove.instruments.definitions import CATALOG, Instrument
from goosedove.instruments.fields import FieldValues
from goosedove.trades.template import field_value


@dataclass(frozen=True, slots=True)
class QuoteTemplate:
    """The instrument, the definition the fields were bound against; the names, the fields the
    template's row named, in the sheet's order, each one a quote template may hold; and the
    values by field name, in the same order: each the one value the row held, a code, the curve
    key and a payment rule as the text typed, a holiday calendar as the object its handle stood
    for; owned, and read for nothing until a quote is made."""

    instrument: Instrument
    names: tuple[str, ...]
    values: Mapping[str, object]


def quote_template(values: FieldValues) -> QuoteTemplate:
    """The one way to make a QuoteTemplate: one row of field values under an instrument a quote
    prices, every header a field a quote template may hold, in the sheet's order and before any
    value is read, then each value read once for the rule intrinsic to its field, the first
    failure being the message."""
    if values.rows != 1:
        raise ValueError(f"values has {values.rows} rows, expected one row of field values")
    instrument = values.instrument
    if not any(field.quote_allowed for field in instrument.fields):
        quoted = ", ".join(
            repr(each.name) for each in CATALOG if any(f.quote_allowed for f in each.fields)
        )
        raise ValueError(
            f"instrument is {instrument.name!r}, expected one a quote prices: {quoted}"
        )
    for name in values.names:
        if not values.field(name).quote_allowed:
            allowed = ", ".join(field.name for field in instrument.fields if field.quote_allowed)
            raise ValueError(
                f"{name} is a field of booking alone, expected one a quote template holds: "
                f"{allowed}"
            )
    read = {name: field_value(values, name) for name in values.names}
    return QuoteTemplate(instrument, values.names, MappingProxyType(read))
