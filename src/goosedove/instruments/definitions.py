"""The definitions themselves: a field is seven facts, an instrument is a name, a description and
its fields, and the catalog is the instruments in the order the library declares them. The
records are frozen library data, changed by a reviewed change to this file and by nothing a
workbook does. docs/library/instruments/show-instrument.md shows them as the sheet sees them."""

from dataclasses import dataclass
from enum import Enum

# The metadata rows of a shown instrument, down its first column, in this order.
ROWS = ("field", "description", "required", "required_when", "type", "options", "rule")
NONE = "none"  # a field with no condition says so, in a cell that is never blank


class FieldType(Enum):
    """What a field's value is, in the seam's words: the type the seam checks a cell against
    when a template or a ticket is bound, and the word the sheet reads in the type row."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CODE = "code"  # text from a fixed list, the list in the options
    HOLIDAY_CALENDAR = "holiday calendar handle"


@dataclass(frozen=True, slots=True)
class Field:
    """One field of an instrument: its name, the exact header a template or a ticket must use;
    what it means; whether it must always be present once the trade is resolved; the condition
    that makes it required when it is not always, or none; its type; its choices, or where they
    come from; and its rule, what holds of its value beyond the type."""

    name: str
    description: str
    required: bool
    required_when: str
    type: FieldType
    options: str
    rule: str


@dataclass(frozen=True, slots=True)
class Instrument:
    """One definition: its name, the exact identifier the sheet types; a description of the
    economic record it is; and its fields, in the order they are shown."""

    name: str
    description: str
    fields: tuple[Field, ...]


FUTURE = Instrument(
    "future",
    "A position tied to a specified reference contract, with explicit settlement terms.",
    (
        Field(
            "trade_id",
            "External label identifying the deal",
            False,
            NONE,
            FieldType.TEXT,
            "no fixed list",
            "Duplicate labels keep separate occurrences",
        ),
        Field(
            "trade_date",
            "Date the deal was executed",
            True,
            NONE,
            FieldType.DATE,
            "no fixed list",
            "The day the deal was struck, never inferred from the valuation date or today",
        ),
        Field(
            "contract_specification",
            "Name selecting the lot and quantity specification from the index",
            True,
            NONE,
            FieldType.TEXT,
            "the index's specification names",
            "Selects the lot size and unit from the index given to _CreateTrades; "
            "the template may supply it",
        ),
        Field(
            "contract_code",
            "One monthly contract or a strip of monthly contracts",
            True,
            NONE,
            FieldType.TEXT,
            "a contract or strip, F26, 1Q27, CAL27, Z27-X28",
            "Typed in either case and resolved by month against the index's schedule, every "
            "schedule code read; CAL27 is F27 through Z27, Z27-X28 December 2027 through "
            "November 2028",
        ),
        Field(
            "schedule_method",
            "How observations determine the floating price",
            True,
            NONE,
            FieldType.CODE,
            "asian, lastday, penultimate, last3day",
            "A library rule selected by the trade; lastday is built, the others fail by name "
            "until they are",
        ),
        Field(
            "route",
            "The actual trade's clearing arrangement",
            True,
            NONE,
            FieldType.CODE,
            "cleared, bilateral",
            "Must be supported for the traded product; bilateral valuation waits on rates",
        ),
        Field(
            "settlement_method",
            "Descriptive final-settlement form of the actual trade",
            True,
            NONE,
            FieldType.CODE,
            "physical, financial",
            "A fact of the trade; a physical future past its expiry is refused, a financial one "
            "pays on its payment day",
        ),
        Field(
            "clearing_house",
            "The clearing organization for this trade",
            False,
            "route = cleared",
            FieldType.TEXT,
            "no fixed list",
            "A label kept as typed; nothing is inferred from it",
        ),
        Field(
            "broker",
            "The broker recorded for the deal",
            False,
            NONE,
            FieldType.TEXT,
            "no fixed list",
            "Attribution; no fee or clearing role inferred from the label",
        ),
        Field(
            "quantity",
            "Signed size of the position",
            True,
            NONE,
            FieldType.NUMBER,
            "whole nonzero lots",
            "Signed; whole nonzero lots for the first future profile",
        ),
        Field(
            "quantity_unit",
            "How the supplied quantity is measured",
            True,
            NONE,
            FieldType.CODE,
            "LOT",
            "LOT is the one unit built; the specification gives the quantity per lot",
        ),
        Field(
            "quantity_per",
            "Whether quantity applies per month or per day",
            True,
            NONE,
            FieldType.CODE,
            "month, day",
            "The quantity for each contract month, or for each calendar day of it; month is "
            "built first",
        ),
        Field(
            "fixed_price",
            "The fixed price agreed when the deal was executed",
            True,
            NONE,
            FieldType.NUMBER,
            "no fixed list",
            "A finite number in the index's quote units; the same for every month of a strip",
        ),
        Field(
            "payment_time_lag",
            "Business-day offset from the payment anchor defined by the supported product",
            False,
            "settlement_method = financial",
            FieldType.TEXT,
            "+1bd, +2bd and other positive whole business days",
            "Counted strictly after the traded contract's last trading day on the payment "
            "calendar; +1bd for PHH, +2bd for ETE",
        ),
        Field(
            "payment_holiday_calendar",
            "Calendar supplying holidays for payment-day counting",
            False,
            "settlement_method = financial",
            FieldType.HOLIDAY_CALENDAR,
            "a _CreateHolidayCalendar handle",
            "Monday to Friday less its holidays; separate from the pricing calendar",
        ),
    ),
)


def catalog(*instruments: Instrument) -> tuple[Instrument, ...]:
    """The one way to make a catalog: each name once and nonempty, each description nonempty,
    and within each instrument each field name once and nonempty, with a condition or `none` and
    nonempty options and rule, so that no cell the sheet reads is ever blank. Checked here, where
    the definitions are authored, and never on a reader's call."""
    names: set[str] = set()
    for each in instruments:
        if not each.name or not each.description:
            raise ValueError(f"instrument {each.name!r} needs a nonempty name and description")
        if each.name in names:
            raise ValueError(f"instrument {each.name!r} is defined twice")
        names.add(each.name)
        fields: set[str] = set()
        for field in each.fields:
            if field.name in fields:
                raise ValueError(f"{each.name} defines field {field.name!r} twice")
            fields.add(field.name)
            texts = (field.name, field.description, field.required_when, field.options, field.rule)
            if not all(texts):
                raise ValueError(f"{each.name} field {field.name!r} has an empty cell")
    return instruments


CATALOG = catalog(FUTURE)


def instrument(name: str, instruments: tuple[Instrument, ...] = CATALOG) -> Instrument:
    """The instrument of that name, matched exactly, case and all; an unknown name is refused
    with the names there are, in the catalog's order, and an empty catalog says it is empty."""
    for each in instruments:
        if each.name == name:
            return each
    if not instruments:
        raise ValueError(f"instrument is {name!r}, expected a listed instrument; none are defined")
    choices = ", ".join(repr(each.name) for each in instruments)
    raise ValueError(f"instrument is {name!r}, expected one of: {choices}")
