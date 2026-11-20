"""The definitions themselves: a field is seven facts of booking and since
template-based-quoting.md three of quoting, an instrument is a name, a description and its
fields, and the catalog is the instruments in the order the library declares them. The records
are frozen library data, changed by a reviewed change to this file and by nothing a workbook
does. docs/library/instruments/show-instrument.md shows them as the sheet sees them."""

from dataclasses import dataclass, replace
from enum import Enum

# The metadata rows of a shown instrument, down its first column, in this order: the seven of
# booking, then the three of quoting.
ROWS = (
    "field",
    "description",
    "required",
    "required_when",
    "type",
    "options",
    "rule",
    "quote_allowed",
    "quote_required",
    "quote_required_when",
)
NONE = "none"  # a field with no condition says so, in a cell that is never blank


class FieldType(Enum):
    """What a field's value is, in the seam's words: the type the seam checks a cell against
    when a template or a ticket is bound, and the word the sheet reads in the type row."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CODE = "code"  # text from a fixed list, the list in the options
    HOLIDAY_CALENDAR = "holiday calendar handle"
    # A date or a text, told apart by type once at the seam and never by reading, since
    # payment-day-date-or-rule.md: the payment day, a day as entered or the rule that finds it.
    DATE_OR_TEXT = "date or text"


@dataclass(frozen=True, slots=True)
class Field:
    """One field of an instrument: its name, the exact header a template or a ticket must use;
    what it means; whether it must always be present once the trade is resolved; the condition
    that makes it required when it is not always, or none; its type; its choices, or where they
    come from; its rule, what holds of its value beyond the type; and whether a cell of it may be
    left unsupplied, a blank or an empty text meaning the row supplies no value, which since #172
    the three period fields allow and no other does: the seam reads the flag off the field a
    header identified and never guesses it from a cell's position. And since
    template-based-quoting.md the field's part in a quote, three facts beside the booking facts
    and no second definition: whether a quote template may hold it at all, whether a completed
    quote always requires it, and the condition that otherwise requires it, or none; a field a
    quote refuses is never one it requires, the catalog's rule."""

    name: str
    description: str
    required: bool
    required_when: str
    type: FieldType
    options: str
    rule: str
    may_be_unsupplied: bool = False
    quote_allowed: bool = False
    quote_required: bool = False
    quote_required_when: str = NONE


@dataclass(frozen=True, slots=True)
class Instrument:
    """One definition: its name, the exact identifier the sheet types; a description of the
    economic record it is; and its fields, in the order they are shown."""

    name: str
    description: str
    fields: tuple[Field, ...]


# The two booking fields every instrument shares, one definition each: the identifier and the
# day the deal was struck.
TRADE_ID = Field(
    "trade_id",
    "External numeric identifier of the executed deal",
    False,
    NONE,
    FieldType.NUMBER,
    "a whole number of at most 15 digits",
    "The source system's deal number, whole, -999999999999999 to 999999999999999, "
    "never text; duplicates keep separate occurrences",
)
TRADE_DATE = Field(
    "trade_date",
    "Date the deal was executed",
    True,
    NONE,
    FieldType.DATE,
    "no fixed list",
    "The day the deal was struck, never inferred from the valuation date or today",
)

FIXED_FLOAT = Instrument(
    "fixed_float",
    "A fixed-for-floating position on a specified reference contract, with explicit observation "
    "and settlement terms.",
    (
        TRADE_ID,
        TRADE_DATE,
        Field(
            "contract_code",
            "One monthly contract or a strip of monthly contracts, the row's period when it "
            "supplies no dates",
            False,
            "no start_date and end_date on the row",
            FieldType.TEXT,
            "a contract or strip, F26, 1Q27, 1H27, CAL27, Z27-X28",
            "Typed in either case and resolved by month against the index's schedule when the "
            "row supplies no dates, every schedule code read; CAL27 is F27 through Z27, 1H27 F27 "
            "through M27, Z27-X28 December 2027 through November 2028; beside both dates it is "
            "kept as entered text and not read; a blank or empty cell is not supplied",
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
            quote_allowed=True,
            quote_required=True,
        ),
        Field(
            "route",
            "The route the trade clears or settles by, cleared or bilateral",
            True,
            NONE,
            FieldType.CODE,
            "cleared, bilateral",
            "Decides the clearing reserve: a cleared trade incurs the selected specification's "
            "clearing rate and a bilateral one none; a cleared batch values undiscounted and takes "
            "no discount curve, a bilateral one is valued on the curve _EvaluateTrades requires",
            quote_allowed=True,
            quote_required=True,
        ),
        Field(
            "settlement_method",
            "How the trade finally settles, by physical delivery or a financial payment",
            True,
            NONE,
            FieldType.CODE,
            "physical, financial",
            "Selects behavior, validation and payment terms, not a label: a financial batch "
            "requires payment_day and payment_holiday_calendar and pays on its payment day, the "
            "row's date or the day its rule finds; a physical one pays on no day, takes lastday "
            "rows alone, is refused past its expiry and refused on the bilateral route; the "
            "delivery itself is outside the model",
            quote_allowed=True,
            quote_required=True,
        ),
        Field(
            "clearing_house",
            "The clearing organization a cleared trade clears through",
            False,
            "route = cleared",
            FieldType.TEXT,
            "no fixed list",
            "Identifies the organization, kept as typed: required with route = cleared and refused "
            "with bilateral; it selects no rate and exempts no fee, the route alone deciding the "
            "clearing reserve",
        ),
        Field(
            "counterparty",
            "The counterparty to a bilateral trade",
            False,
            "route = bilateral",
            FieldType.TEXT,
            "no fixed list",
            "A label kept as typed, each row its own; nothing is inferred from it, no netting, "
            "credit treatment or curve",
        ),
        Field(
            "discount_curve_key",
            "The name of the curve a bilateral trade's payments discount on",
            False,
            "route = bilateral",
            FieldType.TEXT,
            "the name of a curve in the collection given to _EvaluateTrades",
            "Exact and case-sensitive, no whitespace around it: required with route = bilateral "
            "and refused with cleared; rows may name different curves; the curve is selected "
            "when the batch is evaluated, from the collection supplied then, and a key naming "
            "none of its curves fails the evaluation, never silently the first curve",
            quote_allowed=True,
            quote_required_when="route = bilateral",
        ),
        Field(
            "broker",
            "The broker named for the deal, or none for a screen trade",
            False,
            NONE,
            FieldType.TEXT,
            "no fixed list",
            "A named broker enables the brokerage reserve for that trade at the selected "
            "specification's rate; omit the field, or enter none in any case, for no brokerage; a "
            "ticket column may mix names and none; the name selects no rate",
        ),
        Field(
            "quantity",
            "Signed size of the position, a count of the quantity unit",
            True,
            NONE,
            FieldType.NUMBER,
            "a signed whole count, zero included",
            "A whole count of the selected quantity definition, positive, negative or zero; a "
            "zero row is kept, has no exposure and no quantity-based reserve, keeps a marketing "
            "or CVA reserve it entered and can be filled in later",
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
            "Whether quantity is per month, per calendar day or the whole period's",
            True,
            NONE,
            FieldType.CODE,
            "month, calday, period",
            "The quantity per contract month, or per calendar day of it, weekends and holidays "
            "included, under settlement_frequency = monthly; period, the total of the one period "
            "a onetime row is, or calday, per calendar day of its window, under onetime; period "
            "is refused under monthly and month under onetime",
            quote_allowed=True,
            quote_required=True,
        ),
        Field(
            "fixed_price",
            "The fixed price agreed when the deal was executed",
            True,
            NONE,
            FieldType.NUMBER,
            "no fixed list",
            "A finite number in the index's quote units, the same for every month of a strip; "
            "with two indexes given to _CreateTrades the one outright price of the deal, the "
            "price of the sum of the two indexes in the quote unit they share, never a price "
            "per index",
        ),
        Field(
            "second_schedule_method",
            "How the second leg's observations determine its floating price, with two indexes",
            False,
            "two indexes",
            FieldType.CODE,
            "asian, lastday, penultimate, last3day",
            "The second index's method, the same choices as schedule_method under the second "
            "index's kind, lastday alone on an IFERC index; required with two indexes and "
            "refused with one",
        ),
        Field(
            "payment_day",
            "The day a component pays, as a date, or the rule that finds it from the component's "
            "last observation day",
            False,
            "settlement_method = financial",
            FieldType.DATE_OR_TEXT,
            "a date, or +1bd, +3cd, +0em or a chain such as +3em+25cd-1bd+1bd, each a sign, a "
            "whole count and bd, cd or em",
            "A date is the row's one payment day, every component of the row paying on it as "
            "entered, never rolled, after the row's last observation; a rule is applied in order "
            "from each component's last observation day, business days on the payment calendar: "
            "the expiry under lastday on a futures index, the publication day on an IFERC one; "
            "the payment must be after it; +1bd for PHH, +2bd for Waha",
            quote_allowed=True,
            quote_required_when="settlement_method = financial",
        ),
        Field(
            "payment_holiday_calendar",
            "Calendar supplying holidays for payment-day counting",
            False,
            "settlement_method = financial",
            FieldType.HOLIDAY_CALENDAR,
            "a _CreateHolidayCalendar handle",
            "Monday to Friday less its holidays, counted by a rule's business days; separate from "
            "the pricing calendar; read for nothing by a row paying on a date",
            quote_allowed=True,
            quote_required_when="settlement_method = financial",
        ),
        Field(
            "marketing_reserve",
            "A marketing cost booked once with the trade",
            False,
            NONE,
            FieldType.NUMBER,
            "a finite amount of zero or more",
            "In the index's settlement currency, counted once per ticket row whatever its months, "
            "quantity or days; left out of the template and the ticket, zero; static, never a "
            "contribution to value",
        ),
        Field(
            "cva_reserve",
            "A credit valuation adjustment reserve booked once with the trade, signed",
            False,
            NONE,
            FieldType.NUMBER,
            "a finite amount of either sign",
            "In the index's settlement currency, counted once per ticket row whatever its months, "
            "quantity or days, its sign as entered, positive, zero or negative, whatever the "
            "quantity's; left out of the template and the ticket, zero; static, never a "
            "contribution to value",
        ),
        Field(
            "settlement_frequency",
            "How many calculation periods the row's days make, one per calendar month or one "
            "in all",
            True,
            NONE,
            FieldType.CODE,
            "monthly, onetime",
            "Selects independently calculated payoff periods, never the cash day, which "
            "payment_day decides: monthly makes one period per calendar month the row covers, "
            "each with its own observations, weights and quantity; onetime makes one period "
            "across the row's start_date and end_date, every pricing day it covers averaged "
            "together on the window's one quantity, booked under asian on one futures index, "
            "financially settled, with quantity_per = period or calday; a quote, a request for "
            "quote, two indexes, a physical settlement, an IFERC index or another method refuse "
            "onetime by name",
            quote_allowed=True,
            quote_required=True,
        ),
        Field(
            "nearby",
            "Which listed contract prices each observation day, counted from the prompt contract",
            True,
            NONE,
            FieldType.NUMBER,
            "a whole number of 1 or more",
            "1 is the prompt contract on each observation day, the listed contract nearest its "
            "expiry, 2 the next the schedule lists and so on, found afresh for every day by the "
            "calendar's own roll, the expiry day the expiring contract's; a number above 1 is "
            "booked and quoted under asian on one futures index, financially settled, and refused "
            "by name under another method, on an IFERC index, with two indexes and under a "
            "physical settlement",
            quote_allowed=True,
            quote_required=True,
        ),
    ),
)

_BOOKED = {field.name: field for field in FIXED_FLOAT.fields}


def _as_booked(name: str) -> Field:
    """A fixed_float's field as a float_float books it, since float-float-spread.md: the same
    seven facts of booking, one definition of each, and no part in a quote, since no quote
    prices a spread."""
    return replace(
        _BOOKED[name], quote_allowed=False, quote_required=False, quote_required_when=NONE
    )


# The fields of a fixed_float, with spread_price where fixed_price stood and the second index's
# method always required; a field whose choices this instrument narrows says so in its own words,
# and what it does not build is refused by name, float-float-spread.md.
FLOAT_FLOAT = Instrument(
    "float_float",
    "A floating-for-floating position on two reference contracts, the first index's price less "
    "the second's against one agreed spread price, with explicit observation and settlement "
    "terms.",
    (
        TRADE_ID,
        TRADE_DATE,
        _as_booked("contract_code"),
        _as_booked("start_date"),
        _as_booked("end_date"),
        Field(
            "schedule_method",
            "How observations determine the first index's floating price",
            True,
            NONE,
            FieldType.CODE,
            "asian, lastday, penultimate, last3day",
            "The first index's method, a library rule selected by the trade; all four are built "
            "on a futures index, asian averaging the month's pricing days; lastday alone on an "
            "IFERC index, its published month",
        ),
        Field(
            "route",
            "The route the trade settles by, bilateral",
            True,
            NONE,
            FieldType.CODE,
            "bilateral",
            "bilateral exactly, the one route a spread is built on: valued on the curve "
            "_EvaluateTrades requires, with no clearing reserve; cleared is refused by name",
        ),
        Field(
            "settlement_method",
            "How the trade finally settles, a financial payment",
            True,
            NONE,
            FieldType.CODE,
            "financial",
            "financial exactly: the batch requires payment_day and payment_holiday_calendar and "
            "each month pays one net amount on its payment day, the row's date or the day its "
            "rule finds; physical is refused by name",
        ),
        Field(
            "clearing_house",
            "The clearing organization a cleared trade clears through; none for a float_float",
            False,
            "route = cleared",
            FieldType.TEXT,
            "no fixed list",
            "Refused with any value: a float_float is on the bilateral route alone, where no "
            "clearing house stands",
        ),
        _as_booked("counterparty"),
        _as_booked("discount_curve_key"),
        Field(
            "broker",
            "The broker named for the deal; none for a float_float",
            False,
            NONE,
            FieldType.TEXT,
            "none, in any case",
            "Omit the field, or enter none in any case; a named broker is refused by name, a "
            "brokered spread not being built, so no brokerage is reserved",
        ),
        Field(
            "quantity",
            "Signed size of the position, a count of the quantity unit",
            True,
            NONE,
            FieldType.NUMBER,
            "a signed whole count, zero included",
            "A whole count of the selected quantity definition: a positive quantity buys the "
            "spread, receiving the first index and paying the second and the spread price, a "
            "negative one sells it; a zero row is kept, has no exposure, keeps a marketing or "
            "CVA reserve it entered and can be filled in later",
        ),
        Field(
            "quantity_unit",
            "The desk's word for a quantity of both indexes, a contract specification each defines",
            True,
            NONE,
            FieldType.TEXT,
            "a specification name both indexes define",
            "Selects the lot size and unit on each index given to _CreateTrades, exactly as named "
            "there, the two one quantity per entered unit; the template may supply it, and the "
            "indexes own what it means",
        ),
        _as_booked("quantity_per"),
        Field(
            "spread_price",
            "The spread price agreed when the deal was executed",
            True,
            NONE,
            FieldType.NUMBER,
            "no fixed list",
            "A finite number of either sign or zero in the quote unit the two indexes share, the "
            "same for every month of a strip: the first index's price less the second's is paid "
            "against it; a constant of the contract, never a market price",
        ),
        Field(
            "second_schedule_method",
            "How observations determine the second index's floating price",
            True,
            NONE,
            FieldType.CODE,
            "asian, lastday, penultimate, last3day",
            "The second index's method, the same choices as schedule_method under the second "
            "index's kind, lastday alone on an IFERC index",
        ),
        _as_booked("payment_day"),
        _as_booked("payment_holiday_calendar"),
        _as_booked("marketing_reserve"),
        _as_booked("cva_reserve"),
        Field(
            "settlement_frequency",
            "How many calculation periods the row's days make, one per calendar month",
            True,
            NONE,
            FieldType.CODE,
            "monthly",
            "monthly exactly: one period per calendar month the row covers, each with its own "
            "observations, weights and quantity and one net payment; onetime is refused by name",
        ),
        Field(
            "nearby",
            "Which listed contract prices each observation day, counted from the prompt contract",
            True,
            NONE,
            FieldType.NUMBER,
            "1",
            "1 exactly, the prompt contract on each observation day; a later nearby is refused "
            "by name",
        ),
    ),
)

CASHFLOW = Instrument(
    "cashflow",
    "A known signed amount in one currency, payable on one explicit date.",
    (
        TRADE_ID,
        TRADE_DATE,
        Field(
            "amount",
            "Signed amount of the payment in the stated currency, positive received and "
            "negative paid",
            True,
            NONE,
            FieldType.NUMBER,
            "a finite signed amount, fractions and zero included",
            "The whole payment in whole units of the currency, 100 USD a hundred dollars, not a "
            "price or a quantity; a zero row is kept; nothing is read from it beyond its sign",
        ),
        Field(
            "currency",
            "Settlement currency of the payment",
            True,
            NONE,
            FieldType.CODE,
            "USD",
            "USD exactly, the one currency this version books, one per batch; CENT is a scale of "
            "the dollar and no currency, and an amount is never read as cents; no conversion",
        ),
        Field(
            "payment_date",
            "The scheduled payment date, past, present or future",
            True,
            NONE,
            FieldType.DATE,
            "no fixed list",
            "Used as entered, never rolled, never inferred from a schedule; on or before the "
            "valuation day the amount is cash, after it the amount is discounted on the curve",
        ),
        Field(
            "counterparty",
            "The payer or payee: a trading counterparty, a broker or an exchange",
            False,
            NONE,
            FieldType.TEXT,
            "no fixed list",
            "A label kept as typed, each row its own; attribution and nothing more, no curve, no "
            "fee and no netting",
        ),
        Field(
            "description",
            "What the payment is for, such as Swap termination or Clearing rebate",
            False,
            NONE,
            FieldType.TEXT,
            "no fixed list",
            "A label kept as typed; nothing is read from the words",
        ),
    ),
)


def catalog(*instruments: Instrument) -> tuple[Instrument, ...]:
    """The one way to make a catalog: each name once and nonempty, each description nonempty,
    and within each instrument each field name once and nonempty, with a condition or `none` and
    nonempty options and rule, so that no cell the sheet reads is ever blank; and since
    template-based-quoting.md no field a quote refuses required by one, always or on a
    condition. Checked here, where the definitions are authored, and never on a reader's
    call."""
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
            texts = (
                field.name,
                field.description,
                field.required_when,
                field.options,
                field.rule,
                field.quote_required_when,
            )
            if not all(texts):
                raise ValueError(f"{each.name} field {field.name!r} has an empty cell")
            if not field.quote_allowed and (
                field.quote_required or field.quote_required_when != NONE
            ):
                raise ValueError(
                    f"{each.name} field {field.name!r} is required by a quote but not allowed in "
                    "one"
                )
    return instruments


CATALOG = catalog(FIXED_FLOAT, FLOAT_FLOAT, CASHFLOW)


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
