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
    come from; its rule, what holds of its value beyond the type; and whether a cell of it may be
    left unsupplied, a blank or an empty text meaning the row supplies no value, which since #172
    the three period fields allow and no other does: the seam reads the flag off the field a
    header identified and never guesses it from a cell's position."""

    name: str
    description: str
    required: bool
    required_when: str
    type: FieldType
    options: str
    rule: str
    may_be_unsupplied: bool = False


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
            "External numeric identifier of the executed deal",
            False,
            NONE,
            FieldType.NUMBER,
            "a whole number of at most 15 digits",
            "The source system's deal number, whole, -999999999999999 to 999999999999999, "
            "never text; duplicates keep separate occurrences",
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
            "contract_code",
            "One monthly contract or a strip of monthly contracts, the row's period when it "
            "supplies no dates",
            False,
            "no start_date and end_date on the row",
            FieldType.TEXT,
            "a contract or strip, F26, 1Q27, CAL27, Z27-X28",
            "Typed in either case and resolved by month against the index's schedule when the "
            "row supplies no dates, every schedule code read; CAL27 is F27 through Z27, Z27-X28 "
            "December 2027 through November 2028; beside both dates it is kept as entered text "
            "and not read; a blank or empty cell is not supplied",
            may_be_unsupplied=True,
        ),
        Field(
            "start_date",
            "First day of a booked period; with end_date it takes precedence over a code",
            False,
            "no contract_code on the row, or with end_date",
            FieldType.DATE,
            "no fixed list",
            "With end_date the inclusive days the deal covers, split at month ends, whatever "
            "the row's code; one date without the other fails; a blank or empty cell is not "
            "supplied; util_StartDate gives it from a label",
            may_be_unsupplied=True,
        ),
        Field(
            "end_date",
            "Last day of a booked period, inclusive",
            False,
            "no contract_code on the row, or with start_date",
            FieldType.DATE,
            "no fixed list",
            "On or after start_date; the two dates book the row's period together, so one "
            "without the other fails; a blank or empty cell is not supplied; a part of a month "
            "prices under asian alone",
            may_be_unsupplied=True,
        ),
        Field(
            "schedule_method",
            "How observations determine the floating price",
            True,
            NONE,
            FieldType.CODE,
            "asian, lastday, penultimate, last3day",
            "A library rule selected by the trade; all four are built on a futures index, asian "
            "averaging the month's pricing days; lastday alone on an IFERC index, its published "
            "month",
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
            "Signed size of the position, a count of the quantity unit",
            True,
            NONE,
            FieldType.NUMBER,
            "a signed whole count, zero included",
            "A whole count of the selected quantity definition, positive, negative or zero; a "
            "zero row is kept, contributes nothing and can be filled in later",
        ),
        Field(
            "quantity_unit",
            "The desk's word for a quantity of the index, one of its contract specifications",
            True,
            NONE,
            FieldType.TEXT,
            "the index's specification names",
            "Selects the lot size and unit from the index given to _CreateTrades, exactly as "
            "named there; the template may supply it, and the index owns what it means",
        ),
        Field(
            "quantity_per",
            "Whether quantity is per month or per calendar day",
            True,
            NONE,
            FieldType.CODE,
            "month, calday",
            "The quantity per contract month, or per calendar day of it, weekends and holidays "
            "included",
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
            "Counted strictly after the component's anchor on the payment calendar: on a futures "
            "index its last observation day, the expiry under lastday; on an IFERC index the "
            "month's last_trading_date; +1bd for PHH, +3bd for Waha",
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
