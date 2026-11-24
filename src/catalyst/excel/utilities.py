"""The utilities: worksheet functions that read what the library holds, or reshape what the sheet
supplies, and change nothing. docs/library/utilities/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from collections.abc import Mapping, Sequence
from functools import singledispatch
from typing import Annotated, Any, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from catalyst.calendar.calendar import Calendar
from catalyst.cashflows.booking import Cashflows
from catalyst.cashflows.valuation import CashflowResults
from catalyst.excel.bridge import (
    NUMBER_CODE,
    TEXT_CODE,
    Date,
    Handle,
    MixedArray,
    NumberColumn,
    TextColumn,
    excel_function,
)
from catalyst.globals.discount_curve import DiscountCurve, bump_discount_curve
from catalyst.globals.discount_curve_set import DiscountCurveSet
from catalyst.globals.valuation_date import ValuationDate
from catalyst.index_definitions.contract_codes import (
    cme_code,
    code_of_month,
    first_day_of,
    next_contract,
)
from catalyst.index_definitions.contract_specifications import ContractSpecifications
from catalyst.index_definitions.date_offsets import shift_date
from catalyst.index_definitions.futures_schedule import FuturesSchedule
from catalyst.index_definitions.gas_daily_schedule import GasDailySchedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.iferc_schedule import IfercSchedule
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.index_conventions import IndexConventions
from catalyst.index_definitions.kind import named
from catalyst.index_definitions.periods import end_date, start_date
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FieldType, Instrument
from catalyst.instruments.fields import DatesOrTexts
from catalyst.market.market import Market
from catalyst.market.market_history import MarketHistory
from catalyst.market_data.futures_fixings import FuturesFixings
from catalyst.market_data.gas_daily_fixings import GasDailyFixings
from catalyst.market_data.iferc_fixings import IfercFixings
from catalyst.market_data.interpolated_contracts import interpolate_contracts
from catalyst.market_data.price_vector import PriceVector
from catalyst.quoting.rfq import Rfq
from catalyst.quoting.template import QuoteTemplate
from catalyst.trades.aggregation import AggregateResults
from catalyst.trades.encoding import Encoded, EncodedLeg
from catalyst.trades.preparation import PreparedTrades
from catalyst.trades.resolution import Trades
from catalyst.trades.results import LegResults, TradeResults
from catalyst.trades.schedule_methods import METHOD_NAMES
from catalyst.trades.template import DayOrRule, TradeTemplate
from catalyst.trades.terms import (
    BASIS_NAMES,
    FREQUENCY_NAMES,
    booked_words,
    period_words,
    price_words,
)


@singledispatch
def shown(obj: object) -> MixedArray:
    """The table a kind shows on the sheet: its headers in the creator's words, a row of types,
    then one row per element. Each kind registers its own below, and the pull request that
    builds a creator adds its kind here; a kind nobody registered fails rather than guessing."""
    raise TypeError(f"no table for a {type(obj).__name__}")


@shown.register
def valuation_date_table(obj: ValuationDate) -> MixedArray:
    return MixedArray.table(
        [("as_of", "day_fraction_elapsed"), ("datetime64[D]", "float")],
        np.array([obj.as_of]),
        np.array([obj.day_fraction_elapsed]),
    )


@shown.register
def discount_curve_table(obj: DiscountCurve) -> MixedArray:
    # The days and their factors, and since #201 the curve's name on every row, last, so that
    # every positional read of the two columns stands.
    return MixedArray.table(
        [("date", "discount_factor", "name"), ("datetime64[D]", "float64", "str")],
        obj.dates,
        obj.factors,
        (obj.name,) * obj.dates.size,
    )


@shown.register
def discount_curve_set_table(obj: DiscountCurveSet) -> MixedArray:
    # One row per curve in the order given, since #201: its name, its first and its last day
    # and the days between, inclusive; the daily factors are each curve's own handle's to spill.
    curves = obj.curves
    return MixedArray.table(
        [
            ("name", "start_date", "end_date", "days"),
            ("str", "datetime64[D]", "datetime64[D]", "int64"),
        ],
        obj.names,
        np.array([c.start_date for c in curves], dtype="datetime64[D]"),
        np.array([c.max_date for c in curves], dtype="datetime64[D]"),
        np.array([c.dates.size for c in curves], dtype=np.int64),
    )


@shown.register
def futures_schedule_table(obj: FuturesSchedule) -> MixedArray:
    # The codes and the futures always, then the options when the index has them.
    if obj.option_expiry is None:
        return MixedArray.table(
            [("contract_code", "future_expiry"), ("str", "datetime64[D]")],
            obj.codes,
            obj.future_expiry,
        )
    return MixedArray.table(
        [
            ("contract_code", "future_expiry", "option_expiry"),
            ("str", "datetime64[D]", "datetime64[D]"),
        ],
        obj.codes,
        obj.future_expiry,
        obj.option_expiry,
    )


@shown.register
def iferc_schedule_table(obj: IfercSchedule) -> MixedArray:
    return MixedArray.table(
        [
            ("contract_code", "publication_date"),
            ("str", "datetime64[D]"),
        ],
        obj.codes,
        obj.publication_date,
    )


@shown.register
def gas_daily_schedule_table(obj: GasDailySchedule) -> MixedArray:
    return MixedArray.table(
        [("contract_code", "first_date", "last_date"), ("str", "datetime64[D]", "datetime64[D]")],
        obj.codes,
        obj.first_date,
        obj.last_date,
    )


@shown.register
def calendar_table(obj: Calendar, rows: int | None = None) -> MixedArray:
    # The dates and the flags were made when the calendar was; the prompt contract's code is
    # read from the schedule of the index the calendar keeps, one take over the rows, and
    # nothing is rebuilt. A market asks for the first rows alone, those its quotes cover: each
    # column is cut there before anything is made of it, a view of the calendar's own column,
    # and the codes are taken no further than the last contract those rows reach, so the table
    # costs its own rows and no others, however long the schedule and the calendar run on.
    # Given no count, each cut is the whole column and the codes are the whole schedule's.
    prompt = obj.contract[:rows]
    codes = np.array(obj.index.schedule.codes[: int(prompt[-1]) + 1], dtype=object)[prompt]
    return MixedArray.table(
        [
            ("date", "contract", "is_priced", "is_fixed"),
            ("datetime64[D]", "str", "bool", "bool"),
        ],
        obj.dates[:rows],
        tuple(codes),
        obj.is_priced[:rows],
        obj.is_fixed[:rows],
    )


type _Priced = tuple[NDArray[np.intp], NDArray[np.float64]]
type _PricedColumn = tuple[str, str, NDArray[Any] | str, tuple[_Priced, ...]]


def _priced_columns(base: MixedArray, columns: Sequence[_PricedColumn]) -> MixedArray:
    """A calendar's table widened by columns that hold a number on some days and a word on the
    others, or a word on every day: each column is its header, the word for its type, its
    words, one for every day or one per day, and its priced pairs, each naming calendar rows
    and the prices on them, the words showing on the rest; a column with no pair is text
    throughout. The words are display, not values, and a column holding numbers on some rows
    and words on others is not one the table builder takes, so each column is written by kind:
    its kinds, its slots, and its words into the texts. The calendar's own table stands as it
    is, nothing rebuilt.

    The texts in sheet order: each heading row's four then the columns', and each day's code
    then, for each column in order, its word on a day it holds no price; the calendar's body
    texts are its codes alone, one per day, in the same order.
    """
    rows, width = base.shape
    added = len(columns)
    kinds = np.empty((rows, width + added), dtype=np.uint8)
    kinds[:, :width] = base.kinds
    kinds[:, width:] = TEXT_CODE
    slots = np.full((rows, width + added), np.nan)
    slots[:, :width] = base.numeric_slots
    cells = np.empty((rows - 2, 1 + added), dtype=object)
    cells[:, 0] = base.texts[2 * width :]
    worded = np.ones((rows - 2, 1 + added), dtype=bool)
    for c, (_, _, words, priced) in enumerate(columns):  # the columns, not the days
        cells[:, c + 1] = words
        for on, prices in priced:  # the pairs, not the prices: none, one or two of them
            kinds[on + 2, width + c] = NUMBER_CODE
            slots[on + 2, width + c] = prices
            worded[on, c + 1] = False
    headings = (
        *base.texts[:width],
        *[header for header, _, _, _ in columns],
        *base.texts[width : 2 * width],
        *[kind for _, kind, _, _ in columns],
    )
    return MixedArray(kinds, slots, (*headings, *cells[worded]))


@shown.register
def market_history_table(obj: MarketHistory) -> MixedArray:
    # The calendar's four columns, then fixing_price: the price fixed on each fixed and priced
    # period for the calendar's own contract, a number, and a word on every other, closed where
    # the calendar does not price the day and unfixed where it prices but has not fixed,
    # whatever the market. Then, since nearby-selection.md, two columns for each further nearby
    # a futures history holds a settle of: nearby_N_contract, the code of the contract N less
    # one places after the day's prompt, the contract that settle is of, on every day, a dash
    # where the schedule lists none; and nearby_N_fixing_price, its settle where the day is
    # fixed and priced and the same words elsewhere. A history of the prompt alone, and an
    # IFERC or a Gas Daily one, spills the five columns it always did.
    calendar = obj.calendar
    words = np.empty(calendar.dates.size, dtype=object)
    words[:] = "closed"
    words[calendar.is_priced] = "unfixed"
    prices = obj.fixing_prices
    columns: list[_PricedColumn] = [
        ("fixing_price", "float64", words, ((obj.fixed_rows, prices[:, 0]),))
    ]
    codes = calendar.index.schedule.codes
    for n in range(1, prices.shape[1]):  # the further nearbys, not the days
        contract = calendar.contract + n
        listed = contract < len(codes)
        names = np.full(calendar.dates.size, "-", dtype=object)
        names[listed] = np.array(codes, dtype=object)[contract[listed]]
        columns.append((f"nearby_{n + 1}_contract", "str", names, ()))
        columns.append(
            (f"nearby_{n + 1}_fixing_price", "float64", words, ((obj.fixed_rows, prices[:, n]),))
        )
    return _priced_columns(calendar_table(calendar), columns)


@shown.register
def market_table(obj: Market) -> MixedArray:
    # The calendar's four columns, then price, over the rows the market's prices cover: every
    # row through the last period of the last contract quoted, open or closed, the history
    # before it included. That row is found by one search down the calendar's contract column,
    # which never decreases, and the columns are cut there before the table is made, so a
    # vector that stops before the schedule costs its own rows; a vector that reaches the
    # schedule's end takes the same path and every row. The fixing on each fixed and priced
    # period, the quote of its contract on each unfixed period, and closed on every other. The
    # quotes are asked for the live rows alone, since a fixed period's contract may precede the
    # first contract quoted, and through the market's own reader, which holds the coverage rule.
    history = obj.market_history
    calendar = history.calendar
    rows = int(calendar.contract.searchsorted(obj.last_contract, side="right"))
    live = np.flatnonzero(calendar.is_priced[:rows] & ~calendar.is_fixed[:rows])
    # The price of each day's own contract: the history's first column on the fixed side,
    # whatever further nearbys it holds, since nearby-selection.md.
    fixed = (history.fixed_rows, history.fixing_prices[:, 0])
    quoted = (live, obj.live_prices(calendar.contract[live]))
    return _priced_columns(
        calendar_table(calendar, rows), [("price", "float64", "closed", (fixed, quoted))]
    )


@shown.register
def futures_fixings_table(obj: FuturesFixings) -> MixedArray:
    # Newest first, as the creator takes them: the dates and the settles are kept oldest first,
    # and each column is read here from its last row back, a view and no copy, a date beside
    # its own settles, so the spill pasted back into the creator makes the same fixings. One
    # column per nearby the series carries, since nearby-selection.md, headed by the word a
    # trade's nearby field reads it by: nearby_1 the prompt contract's settle, nearby_2 the
    # next listed contract's.
    nearbys = obj.settles.shape[1]
    return MixedArray.table(
        [
            ("date", *[f"nearby_{n + 1}" for n in range(nearbys)]),
            ("datetime64[D]", *["float64"] * nearbys),
        ],
        obj.dates[::-1],
        *[obj.settles[::-1, n] for n in range(nearbys)],
    )


@shown.register
def gas_daily_fixings_table(obj: GasDailyFixings) -> MixedArray:
    # Newest first, as the creator takes them, each kept column read from its last row back.
    return MixedArray.table(
        [("flow_date", "price"), ("datetime64[D]", "float64")],
        obj.dates[::-1],
        obj.prices[::-1],
    )


@shown.register
def iferc_fixings_table(obj: IfercFixings) -> MixedArray:
    # Newest first, as the creator takes them: the columns are kept oldest first, and each is
    # read here from its last row back, the codes as a tuple the other way up and the prices
    # through a view, each price beside its own code, so the spill pasted back into the creator
    # makes the same fixings. No code is resolved and no day is read: the order was settled when
    # the fixings were made.
    return MixedArray.table(
        [("contract_code", "price"), ("str", "float64")], obj.codes[::-1], obj.prices[::-1]
    )


@shown.register
def price_vector_table(obj: PriceVector) -> MixedArray:
    return MixedArray.table([("price",), ("float64",)], obj.prices)


@shown.register
def holiday_calendar_table(obj: HolidayCalendar) -> MixedArray:
    return MixedArray.table([("holiday",), ("datetime64[D]",)], obj.holiday)


@shown.register
def index_conventions_table(obj: IndexConventions) -> MixedArray:
    return MixedArray.table(
        [
            (
                "quote_currency_unit",
                "quote_quantity_unit",
                "currency_unit",
                "quantity_type",
                "quantity_unit",
            ),
            ("str", "str", "str", "str", "str"),
        ],
        (obj.quote_currency_unit,),
        (obj.quote_quantity_unit,),
        (obj.currency_unit,),
        (obj.quantity_type,),
        (obj.quantity_unit,),
    )


@shown.register
def index_table(obj: Index) -> MixedArray:
    # What the index holds, one row: its name and, since #169, the display name beside it, its
    # kind, how many contracts its schedule has,
    # how many the specifications name, whether a holiday calendar was given, and the reporting
    # lot, its name with its size, its unit and the two conversions the index resolved, or the
    # word unset and nothing after it for an index made without one. The parts spill through
    # their own handles; nothing of them is read here but two lengths.
    headers = [
        "name",
        "display_name",
        "kind",
        "contracts",
        "specifications",
        "has_holiday_calendar",
        "reporting_lot",
    ]
    types = ["str", "str", "str", "int64", "int64", "bool", "str"]
    lot = obj.reporting_lot
    columns: list[NDArray[Any] | tuple[str, ...]] = [
        (obj.name,),
        (obj.display_name,),
        (obj.kind.value,),
        np.array([len(obj.schedule.codes)], dtype=np.int64),
        np.array([len(obj.specifications.names)], dtype=np.int64),
        np.array([obj.holiday_calendar is not None], dtype=bool),
        ("unset" if lot is None else lot.name,),
    ]
    if lot is not None:
        headers += ["lot_size", "lot_unit", "lot_quote_quantity", "lot_coefficient"]
        types += ["float64", "str", "float64", "float64"]
        columns += [
            np.array([lot.lot_size]),
            (lot.lot_unit,),
            np.array([lot.quote_quantity]),
            np.array([lot.coefficient]),
        ]
    return MixedArray.table([tuple(headers), tuple(types)], *columns)


@shown.register
def contract_specifications_table(obj: ContractSpecifications) -> MixedArray:
    return MixedArray.table(
        [
            ("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
            ("str", "float64", "str", "float64", "float64"),
        ],
        obj.names,
        obj.lot_sizes,
        obj.lot_units,
        obj.brokerage_rates_per_lot,
        obj.clearing_rates_per_lot,
    )


# The words a readback shows where a row supplied no value, since #172: display alone, never a
# value the library holds, takes or defaults to; a reader who pastes a spill back types nothing.
NOT_SUPPLIED = "(not supplied)"


@shown.register
def trade_template_table(obj: TradeTemplate) -> MixedArray:
    # The instrument, then each field the template's row named, in the sheet's order, one row:
    # its default, a number, a day and text as they are, a holiday calendar as the words of its
    # kind, since the spill shows what the template holds and is no round trip of a handle; and
    # since #172 the words `(not supplied)`, text, under a period field whose cell held nothing,
    # the header the template owns and the value it supplies to no row.
    return template_table(obj.instrument, obj.names, obj.defaults)


@shown.register
def quote_template_table(obj: QuoteTemplate) -> MixedArray:
    # The same spill for a quote template, since template-based-quoting.md: the instrument, then
    # each field its row named under its name, every one holding a value, since no period field
    # may stand in a quote template.
    return template_table(obj.instrument, obj.names, obj.values)


@shown.register
def rfq_table(obj: Rfq) -> MixedArray:
    """A request's spill, since rfq-quoting.md and dated-quotes.md: one row per component in row
    order, `row`, the entered row it came from, `period`, its contract code in the schedule's
    spelling or a window's two dates, `quantity` as its row entered it, `quantity_per`,
    `component_quantity`, the component's quantity by the basis, `payment_source`, template or
    request, and `payment_date`, the component's effective day, a dash for both on a physical
    request; then the request's facts on every row so that a row reads whole, `index`,
    `schedule_method`, `route`, `settlement_method`, `quote_unit`, `discount_curve_key`, a dash
    on the cleared route, `settlement_frequency` and, since nearby-selection.md, `nearby`. Saved
    facts alone: nothing is priced and no
    factor is shown."""
    request = obj.request
    terms = request.terms
    period = request.period
    occurrence = obj.occurrence
    n = occurrence.size
    every = np.ones(n, dtype=np.bool_)
    conventions = request.index.conventions

    def on_every(word: str) -> NDArray[np.object_]:
        return np.full(n, word, dtype=object)

    source = "-" if obj.payment_source is None else obj.payment_source.value
    pays = request.payment_date
    return _assembled(
        [
            _numbers_on("row", (occurrence + 1).astype(np.float64), every, "int64"),
            _words_on(
                "period",
                period_words(
                    request.schedule.codes,
                    period.contract,
                    period.window,
                    period.first,
                    period.last,
                ),
            ),
            _numbers_on("quantity", obj.quantity[occurrence], every),
            _words_on("quantity_per", on_every(terms.quantity_per.value)),
            _numbers_on("component_quantity", obj.component_quantity, every),
            _words_on("payment_source", on_every(source)),
            _words_on("payment_date", on_every("-"))
            if pays is None
            else _dates_on("payment_date", pays),
            _words_on("index", on_every(request.index.name)),
            _words_on("schedule_method", on_every(terms.method.value)),
            _words_on("route", on_every(terms.route.value)),
            _words_on("settlement_method", on_every(terms.settlement.value)),
            _words_on(
                "quote_unit",
                on_every(
                    f"{conventions.quote_currency_unit} per {conventions.quote_quantity_unit}"
                ),
            ),
            _words_on("discount_curve_key", on_every("-" if terms.key is None else terms.key)),
            _words_on("settlement_frequency", on_every(terms.frequency.value)),
            _numbers_on("nearby", np.full(n, float(terms.nearby)), every, "int64"),
        ]
    )


def template_table(
    instrument: Instrument, names: tuple[str, ...], values: Mapping[str, object]
) -> MixedArray:
    """A template's spill, a trade template's and a quote template's alike: the instrument, then
    each field named under its name in the order given, one row, a number, a day and text as
    they are, a holiday calendar as the words of its kind, and `(not supplied)` under a field
    named with no value."""
    headers: list[str] = ["instrument"]
    types: list[str] = ["str"]
    columns: list[NDArray[Any] | tuple[str, ...]] = [(instrument.name,)]
    for name in names:
        headers.append(name)
        if name not in values:
            types.append("str")
            columns.append((NOT_SUPPLIED,))
            continue
        value = values[name]
        field_type = next(field for field in instrument.fields if field.name == name).type
        match field_type:
            case FieldType.NUMBER:
                types.append("float64")
                columns.append(np.array([value], dtype=np.float64))
            case FieldType.DATE:
                types.append("datetime64[D]")
                columns.append(np.array([value], dtype="datetime64[D]"))
            case FieldType.TEXT | FieldType.CODE:
                types.append("str")
                columns.append((str(value),))
            case FieldType.HOLIDAY_CALENDAR:
                types.append("str")
                columns.append((named(value),))
            case FieldType.DATE_OR_TEXT:  # the day or the rule, payment-day-date-or-rule.md
                entered = cast(DayOrRule, value)
                if entered.day is not None:
                    types.append("datetime64[D]")
                    columns.append(np.array([entered.day], dtype="datetime64[D]"))
                else:
                    types.append("str")
                    columns.append((cast(str, entered.rule),))
            case _:
                assert_never(field_type)
    return MixedArray.table([tuple(headers), tuple(types)], *columns)


@shown.register
def trades_table(obj: Trades) -> MixedArray:
    # One row per component: the ticket row it belongs to, as the sheet counts rows, then the
    # resolved terms under the definition's own field names in the definition's order, the row's
    # own method, unit and basis and the batch's route and settlement on every row, since a
    # reader of one row should see the whole deal and the template need not have supplied them,
    # then what the encoding made of the terms. trade_id, a number since #168,
    # clearing_house, since #175 counterparty, and broker where the batch has them; quantity_unit
    # the specification's name as the index spells it; the payment day as entered, a date a date
    # and a rule its text since payment-day-date-or-rule.md, and the day it gives for a
    # financial settlement; since #175 marketing_reserve where the batch has it, the amount the
    # row booked shown on each of its components, the one amount and no allocation among them,
    # so a reader never sums the column down a strip, and since cva-reserve.md cva_reserve where
    # it has that, the row's signed amount, likewise;
    # then what the resolution derived, since #172 entered_contract_code, the code text the row
    # entered as typed, kept apart from the period its components resolved to under
    # booked_period, and the words `(not supplied)` where the row entered none and booked by
    # its dates, display and no value, then start_date and end_date, the days the component
    # covers, its whole month from a code, its share of a booked period from dates and a onetime
    # row's whole window,
    # covered_days, the calendar days between them, and component_quantity, the quantity the
    # basis gives it, the entered quantity times those days under calday, so that a reader never
    # takes the month's total for the entered daily quantity;
    # then what the encoding made, quote_quantity the component quantity in the index's quote
    # quantity unit, coefficient and offset in the settlement currency. A pair, since
    # two-index-fixed-float.md, shows the second leg's second_schedule_method after the first's
    # method, one row per component still, and a single index shows no such column; since
    # two-index-one-price.md fixed_price and offset are the trade's, one price and one fixed
    # leg whatever the legs, and no column is a leg's price; a float_float, since
    # float-float-spread.md, shows its one price under its own name, spread_price, in the same
    # place, and offset is its spread leg; since float-float-units.md the spread price's two
    # units follow it, as the batch typed them, on every row.
    terms, encoding = obj.resolved, obj.encoded
    leg, leg_encoding = terms.legs[0], encoding.legs[0]  # the first leg's, the batch's own
    paired = len(terms.legs) > 1
    rows = terms.occurrence
    n = rows.size
    # Each component's booked period in words, since onetime-averaging.md: the contract's code of
    # a month, the two dates of a window; the column was contract_code until a window could be
    # booked, which no one contract names.
    booked = tuple(booked_words(terms, leg, np.arange(n, dtype=np.intp)))
    headers: list[str] = ["row"]
    types: list[str] = ["int64"]
    columns: list[NDArray[Any] | tuple[str, ...] | DatesOrTexts] = [(rows + 1).astype(np.int64)]

    def text(name: str, column: tuple[str, ...]) -> None:
        headers.append(name)
        types.append("str")
        columns.append(column)

    def numbers(name: str, kind: str, column: NDArray[Any]) -> None:
        headers.append(name)
        types.append(kind)
        columns.append(column)

    def labels(name: str, given: tuple[str, ...] | None) -> None:
        if given is not None:
            text(name, tuple(np.array(given, dtype=object)[rows]))

    if terms.trade_ids is not None:  # the source system's whole numbers, since #168
        numbers("trade_id", "int64", terms.trade_ids[rows])
    numbers("trade_date", "datetime64[D]", terms.trade_dates[rows])
    text("booked_period", booked)
    text("schedule_method", tuple(METHOD_NAMES[leg.schedule_method[rows]]))
    if paired:
        text("second_schedule_method", tuple(METHOD_NAMES[terms.legs[1].schedule_method[rows]]))
    text("route", (terms.route.value,) * n)
    text("settlement_method", (terms.settlement.value,) * n)
    labels("clearing_house", terms.clearing_house)
    labels("counterparty", terms.counterparty)
    labels("discount_curve_key", terms.discount_curve_key)  # named-curves-slice-3.md
    labels("broker", terms.broker)
    numbers("quantity", "float64", terms.quantity)
    text(
        "quantity_unit",
        tuple(np.array(leg.index.specifications.names, dtype=object)[leg.specification[rows]]),
    )
    text("quantity_per", tuple(BASIS_NAMES[terms.quantity_per[rows]]))
    numbers(price_words(terms.instrument)[0], "float64", terms.price)
    if terms.price_unit is not None:  # a float_float's spread price's unit, as typed
        text("spread_price_currency_unit", (terms.price_unit.currency_unit,) * n)
        text("spread_price_quantity_unit", (terms.price_unit.quantity_unit,) * n)
    if terms.payment is not None:
        headers.append("payment_day")  # as the ticket or the template wrote, each kind its own
        types.append("date or text")
        columns.append(_entered_by_component(terms.payment.entered, rows))
        numbers("payment_date", "datetime64[D]", terms.payment.date)
    if terms.marketing_reserve is not None:  # the row's one amount on each of its components
        numbers("marketing_reserve", "float64", terms.marketing_reserve[rows])
    if terms.cva_reserve is not None:  # likewise the row's signed amount, since cva-reserve.md
        numbers("cva_reserve", "float64", terms.cva_reserve[rows])
    entered = np.full(obj.code_entered.size, NOT_SUPPLIED, dtype=object)
    entered[obj.code_entered] = np.array(obj.entered_codes, dtype=object)
    text("entered_contract_code", tuple(entered[rows]))
    numbers("start_date", "datetime64[D]", terms.start_date)
    numbers("end_date", "datetime64[D]", terms.end_date)
    numbers("covered_days", "int64", terms.covered_days)
    numbers("component_quantity", "float64", terms.component_quantity)
    numbers("quote_quantity", "float64", leg_encoding.quote_quantity)
    numbers("coefficient", "float64", leg_encoding.coefficient)
    numbers("offset", "float64", encoding.offset)
    # settlement_frequency last, since onetime-averaging.md, a term of the row shown after the
    # encoding's columns so that no column before it moves, as the observation columns of #229
    # were appended: each row's own word, monthly or onetime.
    text("settlement_frequency", tuple(FREQUENCY_NAMES[terms.settlement_frequency[rows]]))
    # nearby after it, since nearby-selection.md, appended the same way: each row's own number,
    # the contract its days are priced by counted from the prompt.
    numbers("nearby", "int64", terms.nearby[rows])
    return MixedArray.table([tuple(headers), tuple(types)], *columns)


def _entered_by_component(entered: DatesOrTexts, rows: NDArray[np.intp]) -> DatesOrTexts:
    """The entered payment day of each component's row, a date or a rule text, since
    payment-day-date-or-rule.md: the rows' mask taken by the components' rows, and each kind's
    values found at their rows' positions among the rows of that kind, one search each."""
    is_date = entered.is_date[rows]
    dated_rows = np.flatnonzero(entered.is_date)
    ruled_rows = np.flatnonzero(~entered.is_date)
    texts = np.array(entered.texts, dtype=object)
    return DatesOrTexts(
        is_date,
        entered.dates[np.searchsorted(dated_rows, rows[is_date])],
        tuple(texts[np.searchsorted(ruled_rows, rows[~is_date])]),
    )


def _slot_names(
    encoding: Encoded, leg: EncodedLeg
) -> tuple[list[str], list[str], list[NDArray[Any] | tuple[str, ...]]]:
    # The columns that name a slot: the contract pricing the day, whose settle fixes the slot and
    # whose quote projects it; the period the slot's group was booked on, since
    # onetime-averaging.md the group's label, a month's contract code or a window's two dates,
    # which owns the fixed leg and the payment and under asian may be another than the pricing
    # contract; the observation day; and, for a financial settlement, the day the slot's payment
    # group pays, so that two groups observing one day read apart whatever contract prices it; a
    # physical settlement pays on no day and shows none. The slots are the leg's, the payment
    # days the trade's.
    codes = np.array(leg.leg.schedule.codes, dtype=object)
    labels = booked_words(encoding.terms, leg.leg, encoding.group_head)  # one per group
    names = ["pricing_contract", "booked_period", "observation_date"]
    types = ["str", "str", "datetime64[D]"]
    columns: list[NDArray[Any] | tuple[str, ...]] = [
        tuple(codes[leg.slot_reference]),
        tuple(labels[leg.slot_group]),
        leg.slot_date,
    ]
    if encoding.payment_date is not None:
        names.append("payment_date")
        types.append("datetime64[D]")
        columns.append(encoding.payment_date[leg.slot_group])
    return names, types, columns


# A readback column written by kind: its name, its type, its kinds, its slots and its words.
Added = tuple[str, str, NDArray[np.uint8], NDArray[np.float64], NDArray[np.object_]]


def _slot_rows(
    encoding: Encoded,
) -> tuple[list[str], list[str], list[NDArray[Any] | tuple[str, ...]]]:
    """The rows of a slot readback, one per slot of every leg in leg order: one leg's slots named
    by _slot_names; a pair's, since two-index-fixed-float.md, each leg's slots after the other's,
    every row naming its leg, counted from one, and its index first, so that a slot is never
    read as the other leg's, then the slot's columns, each leg's after the other's."""
    legs = encoding.legs
    if len(legs) == 1:
        return _slot_names(encoding, legs[0])
    named = [_slot_names(encoding, leg) for leg in legs]
    sizes = [leg.slot_group.size for leg in legs]
    numbers = np.concatenate([np.full(size, k + 1, dtype=np.int64) for k, size in enumerate(sizes)])
    index_names = tuple(
        [leg.leg.index.name for leg, size in zip(legs, sizes, strict=True) for _ in range(size)]
    )
    columns: list[NDArray[Any] | tuple[str, ...]] = [numbers, index_names]
    for j, kind in enumerate(named[0][1]):  # a text column joined, any other stacked
        parts = [each[2][j] for each in named]
        columns.append(
            _joined(cast(list[tuple[str, ...]], parts))
            if kind == "str"
            else _stacked(cast(list[NDArray[Any]], parts))
        )
    return ["leg", "index", *named[0][0]], ["int64", "str", *named[0][1]], columns


def _stacked(parts: list[NDArray[Any]]) -> NDArray[Any]:
    """The legs' arrays one after the other: the one leg's by reference, a pair's concatenated."""
    return parts[0] if len(parts) == 1 else np.concatenate(parts)


def _joined(parts: list[tuple[str, ...]]) -> tuple[str, ...]:
    """The legs' text columns one after the other: the one leg's by reference, a pair's joined."""
    return parts[0] if len(parts) == 1 else tuple([text for part in parts for text in part])


@shown.register
def prepared_trades_table(obj: PreparedTrades) -> MixedArray:
    # One row per slot, the dated axis as the preparation left it: the slot named, whether it has
    # fixed, whether its payment group has settled, its live coefficient, the settlement currency
    # its price moves the mark by, zero where it has fixed, and the same exposure in lots of the
    # index's reporting lot; nothing is made again, every column the record's own or a gather of
    # one. A pair's rows are each leg's slots after the other's, each naming its leg and its
    # index, since two-index-fixed-float.md.
    encoding = obj.encoded
    legs = obj.legs
    names, types, columns = _slot_rows(encoding)
    return MixedArray.table(
        [
            (*names, "is_fixed", "is_settled", "live_coefficient", "live_lots"),
            (*types, "bool", "bool", "float64", "float64"),
        ],
        *columns,
        _stacked([leg.is_fixed for leg in legs]),
        _stacked([obj.is_settled[leg.encoded.slot_group] for leg in legs]),
        _stacked([leg.dated_live_exposure for leg in legs]),
        _stacked([leg.dated_live_lots for leg in legs]),
    )


@shown.register
def aggregate_results_table(obj: AggregateResults) -> MixedArray:
    """The collection's membership, since #180, one row per occurrence in the order given, a
    repeat a row again: its position counted from one as the sheet counts, its index's name and
    reporting lot, its route, its curve's word, the heading's, or a dash for a cleared source,
    its currency, its own saved nominal delta, delta and DV01, the day every source shares and,
    since #197, its own saved cross-gamma total with its unit, lots per basis point. Since
    named-curves-slice-2.md a batch of cashflows is a row too: a dash under the index, the lot,
    the two deltas, the cross-gamma and its unit, numbers it has not, `cashflow` under the route,
    its curve's word, its currency and its DV01. Since two-index-fixed-float.md a pair is a row
    per leg under its one position, each leg's index, lot, deltas and cross-gamma its own, and
    since two-index-one-price.md a row of its own before them, named by the handle's
    descriptor, `A+B`, carrying the swap's DV01 and a dash under every commodity column, the
    DV01 being the swap's against its one price and no leg's; the leg rows show a dash under
    the DV01, and a one-index source keeps its one row, its descriptor its index's name. The
    source's route, curve, currency and day stand on every row of it, and since
    currency-and-currency-unit.md its currency unit, the unit of the currency its DV01 is in,
    appended last so that no column before it moves. The collection's totals
    and vectors are _ReportRisk's to show; no handle text, since a source's cell may have been
    released while the collection holds the object."""
    sources = obj.sources
    # The words of every curve a source used, in its own key order, since named-curves-slice-3.md,
    # joined with a comma and a space; a cleared source, with no contribution, a dash.
    word_of_curve = {id(group.curve): group.word for group in obj.rate_groups}
    positions: list[float] = []
    index_names: list[str] = []
    lots: list[str] = []
    routes: list[str] = []
    curves: list[str] = []
    currencies: list[str] = []
    currency_units: list[str] = []
    trade: list[bool] = []
    nominal: list[float] = []
    delta: list[float] = []
    cross: list[float] = []
    units: list[str] = []
    dv01_on: list[bool] = []
    dv01: list[float] = []
    for k, source in enumerate(sources):
        word = ", ".join([word_of_curve[id(c.curve)] for c in source.rate_contributions]) or "-"
        match source:
            case TradeResults():
                paired = len(source.legs) > 1
                if paired:
                    # The swap's own row: its descriptor, its DV01 and nothing of a leg's.
                    positions.append(k + 1)
                    index_names.append(source.prepared.encoded.terms.descriptor)
                    lots.append("-")
                    routes.append(source.route.value)
                    curves.append(word)
                    currencies.append(source.currency)
                    currency_units.append(source.currency_unit)
                    trade.append(False)
                    units.append("-")
                    dv01_on.append(True)
                    dv01.append(source.dv01)
                for leg in source.legs:
                    leg_terms = leg.prepared.encoded.leg
                    positions.append(k + 1)
                    index_names.append(leg_terms.index.name)
                    lots.append(leg_terms.reporting_lot.name)
                    routes.append(source.route.value)
                    curves.append(word)
                    currencies.append(source.currency)
                    currency_units.append(source.currency_unit)
                    trade.append(True)
                    nominal.append(leg.nominal_delta_total)
                    delta.append(leg.delta_total)
                    cross.append(leg.cross_gamma_total)
                    units.append(f"{leg.lot_unit} per basis point")
                    dv01_on.append(not paired)
                    if not paired:
                        dv01.append(source.dv01)
            case CashflowResults():
                positions.append(k + 1)
                index_names.append("-")
                lots.append("-")
                routes.append("cashflow")
                curves.append(word)
                currencies.append(source.currency)
                currency_units.append(source.currency_unit)
                trade.append(False)
                units.append("-")
                dv01_on.append(True)
                dv01.append(source.dv01)
            case _:
                assert_never(source)
    n = len(positions)
    every = np.ones(n, dtype=np.bool_)
    on_trades = np.array(trade, dtype=np.bool_)
    on_first = np.array(dv01_on, dtype=np.bool_)
    return _assembled(
        [
            _numbers_on("position", np.array(positions), every, "int64"),
            _words_on("index", np.array(index_names, dtype=object)),
            _words_on("reporting_lot", np.array(lots, dtype=object)),
            _words_on("route", np.array(routes, dtype=object)),
            _words_on("curve", np.array(curves, dtype=object)),
            _words_on("currency", np.array(currencies, dtype=object)),
            _numbers_on("nominal_delta", np.array(nominal), on_trades),
            _numbers_on("delta", np.array(delta), on_trades),
            _numbers_on("dv01", np.array(dv01), on_first),
            _dates_on("as_of", np.full(n, obj.as_of, dtype="datetime64[D]")),
            _numbers_on("cross_gamma", np.array(cross), on_trades),
            _words_on("cross_gamma_unit", np.array(units, dtype=object)),
            _words_on("currency_unit", np.array(currency_units, dtype=object)),
        ]
    )


@shown.register
def trade_results_table(obj: TradeResults) -> MixedArray:
    # One row per slot, the dated contents of the result: the slot named, whether it has fixed,
    # the slot's own live coefficient and the same exposure in lots, its live contribution,
    # coefficient times its contract's quote, all zero where it has fixed, and its contract's
    # risk, four retained vectors read by each slot's reference and so the same number on every
    # slot of one contract, whatever group holds it: the sensitivity and the nominal delta, nominal,
    # and since #177 their discounted twins beside each, a cleared result's twins the nominal arrays
    # themselves, every one named contract_... so that none is read as the slot's and the
    # discounted apart from the nominal; then the two units those numbers are in, the batch's
    # facts on every row so that a row reads whole. The mark, the cash and the totals are the
    # reports' to show. Then, since #177, the payment groups' retained facts: payment_factor on
    # every slot, its group's, and payment_amount, group_npv and group_dv01 once per group, on the
    # first slot row the group holds and a dash on its other rows, since a group's amount repeated
    # on each of its slots would read as each slot's and sum twice; a cleared result retains none
    # of the four and shows a dash on every row. A pair, since two-index-fixed-float.md, shows
    # each leg's slots after the other's, each row naming its leg and its index, the group facts
    # once per group on the group's first row of all, the trade's and no leg's, since
    # two-index-one-price.md the payment being one amount against one price; a leg's floating
    # side is the observation columns' last. Then, since #170, the batch's reserves, once: the
    # three totals, since cva-reserve.md the signed CVA's fourth, and their currency on
    # the first slot row, as _ReportReserves spills them, and a dash on every later row, since
    # they are the batch's booked amounts and no slot's. Then, since #197, the contract's
    # cross-gamma on every slot, read by the slot's reference as the contract's four risks are
    # and so the same number on every slot of one contract, repeated context and no slot's own
    # risk, a cleared result's zero, and its unit, lots per basis point, on every row, each
    # leg's own; appended last so that no column before them moves. Then, since
    # named-curves-slice-3.md, the slot's group's key and the name of the curve the group was
    # discounted on, on every row, a cleared result a dash in both; appended last likewise.
    # Then, since observation-prices-readback.md, the slot's own price facts on every row, fixed
    # or live, _observation_facts, appended last so that no column before them moves. Then,
    # since currency-and-currency-unit.md, the unit of the currency the batch's amounts are
    # in, once on the first row as the reserves' currency is and a dash below, the last column.
    encoding = obj.prepared.encoded
    legs = obj.legs
    names, types, columns = _slot_rows(encoding)
    sizes = [leg.prepared.encoded.slot_group.size for leg in legs]
    slots = sum(sizes)
    offsets = [sum(sizes[:k]) for k in range(len(sizes))]  # each leg's first row
    contribution = np.zeros(slots)
    for leg, offset in zip(legs, offsets, strict=True):
        contribution[offset + leg.prepared.live_slot] = leg.dated_live_contribution
    references = [leg.prepared.encoded.reference_of_slot for leg in legs]
    by_reference = zip(legs, references, strict=True)
    table = MixedArray.table(
        [
            (
                *names,
                "is_fixed",
                "live_coefficient",
                "live_lots",
                "live_contribution",
                "contract_sensitivity",
                "contract_discounted_sensitivity",
                "contract_nominal_delta",
                "contract_delta",
                "sensitivity_unit",
                "lot_unit",
            ),
            (*types, "bool", *("float64",) * 7, "str", "str"),
        ],
        *columns,
        _stacked([leg.prepared.is_fixed for leg in legs]),
        _stacked([leg.prepared.dated_live_exposure for leg in legs]),
        _stacked([leg.prepared.dated_live_lots for leg in legs]),
        contribution,
        _stacked([leg.price_sensitivity[r] for leg, r in zip(legs, references, strict=True)]),
        _stacked(
            [leg.discounted_price_sensitivity[r] for leg, r in zip(legs, references, strict=True)]
        ),
        _stacked([leg.nominal_delta[r] for leg, r in zip(legs, references, strict=True)]),
        _stacked([leg.delta[r] for leg, r in by_reference]),
        _joined(
            [(leg.price_sensitivity_unit,) * size for leg, size in zip(legs, sizes, strict=True)]
        ),
        _joined([(leg.lot_unit,) * size for leg, size in zip(legs, sizes, strict=True)]),
    )
    group = _stacked([leg.prepared.encoded.slot_group for leg in legs])
    first = np.zeros(slots, dtype=np.bool_)
    first[np.unique(group, return_index=True)[1]] = True  # each group's first slot row
    once = np.zeros(slots, dtype=np.bool_)
    once[0] = True  # the batch's own facts, on the first row
    every = np.ones(slots, dtype=np.bool_)
    none, nothing = np.zeros(slots, dtype=np.bool_), np.empty(0)
    if obj.payment_factor is None:
        # A cleared result: nothing retained for the four, a dash on every row.
        payments = [_numbers_on(name, nothing, none) for name in PAYMENT_COLUMNS]
    else:
        held = (obj.payment_amount, obj.npv_by_group, obj.dv01_by_group)
        payments = [
            _numbers_on(PAYMENT_COLUMNS[0], obj.payment_factor[group], every),
            *(
                _numbers_on(name, cast(NDArray[np.float64], vector)[group[first]], first)
                for name, vector in zip(PAYMENT_COLUMNS[1:], held, strict=True)
            ),  # the three are retained together with the factors
        ]
    reserves = obj.reserves
    currency = np.full(slots, "-", dtype=object)
    currency[0] = reserves.currency
    currency_unit = np.full(slots, "-", dtype=object)
    currency_unit[0] = reserves.currency_unit
    # The contract's cross-gamma with every used curve shifted together, the contributions' by
    # reference summed, one row per curve, each leg's own; a cleared result's zero.
    cross = np.zeros(slots)
    for leg, offset, size, reference in zip(legs, offsets, sizes, references, strict=True):
        for contribution_of in leg.cross_contributions:
            cross[offset : offset + size] += contribution_of.cross_gamma[reference]
    per_bp = np.array(
        [
            f"{leg.lot_unit} per basis point"
            for leg, size in zip(legs, sizes, strict=True)
            for _ in range(size)
        ],
        dtype=object,
    )
    key_of_group = encoding.key_of_group
    if key_of_group is None or not obj.curves:
        keys = np.full(slots, "-", dtype=object)
        curve_names = np.full(slots, "-", dtype=object)
    else:
        key_of_slot = key_of_group[group]
        keys = np.array(encoding.keys, dtype=object)[key_of_slot]
        curve_names = np.array([curve.name for curve in obj.curves], dtype=object)[key_of_slot]
    return _widened(
        table,
        [
            *payments,
            _numbers_on("brokerage_reserve", np.array([reserves.brokerage]), once),
            _numbers_on("clearing_reserve", np.array([reserves.clearing]), once),
            _numbers_on("marketing_reserve", np.array([reserves.marketing]), once),
            _numbers_on("cva_reserve", np.array([reserves.cva]), once),
            _words_on("currency", currency),
            _numbers_on("contract_cross_gamma", cross, every),
            _words_on("cross_gamma_unit", per_bp),
            _words_on("discount_curve_key", keys),
            _words_on("discount_curve", curve_names),
            *_observation_facts(legs, slots, offsets, sizes, every),
            _words_on("currency_unit", currency_unit),
        ],
    )


def _observation_facts(
    legs: tuple[LegResults, ...],
    slots: int,
    offsets: list[int],
    sizes: list[int],
    every: NDArray[np.bool_],
) -> list[Added]:
    """The four columns of observation-prices-readback.md, one row per slot, fixed or live:
    observation_coefficient, the slot's exposure, what every price of it multiplies;
    observation_price, the settle the preparation kept where the slot has fixed and the quote
    the evaluation kept where it is live, each the retained number placed on its slot;
    price_unit, the index's quote currency over its quote quantity unit, USD/LB, on every row
    of the leg; and floating_contribution, the exposure times that price, the preparation's
    amount of a fixed slot and the evaluation's of a live one, before the fixed leg and before
    any discounting. Selected and placed: no fixing or quote is read again, no product is made
    and no amount is divided by its coefficient."""
    price = np.empty(slots)
    contribution = np.empty(slots)
    for leg, offset, size in zip(legs, offsets, sizes, strict=True):
        prepared = leg.prepared
        leg_price = price[offset : offset + size]
        leg_price[prepared.is_fixed] = prepared.settle
        leg_price[prepared.live_slot] = leg.quote[prepared.reference_of_live_slot]
        leg_contribution = contribution[offset : offset + size]
        leg_contribution[:] = prepared.fixed_contribution
        leg_contribution[prepared.live_slot] = leg.dated_live_contribution
    units = np.array(
        [
            unit
            for leg, size in zip(legs, sizes, strict=True)
            for unit in (_quote_unit(leg),) * size  # the leg's words once, on each of its rows
        ],
        dtype=object,
    )
    return [
        _numbers_on(
            "observation_coefficient",
            _stacked([leg.prepared.encoded.slot_exposure for leg in legs]),
            every,
        ),
        _numbers_on("observation_price", price, every),
        _words_on("price_unit", units),
        _numbers_on("floating_contribution", contribution, every),
    ]


def _quote_unit(leg: LegResults) -> str:
    """The leg's index's quote unit as price_unit spells it, the currency over the quantity
    unit, USD/LB or CENT/GAL, the unit every observation_price of the leg is in."""
    conventions = leg.prepared.encoded.leg.index.conventions
    return f"{conventions.quote_currency_unit}/{conventions.quote_quantity_unit}"


PAYMENT_COLUMNS = ("payment_factor", "payment_amount", "group_npv", "group_dv01")


@shown.register
def cashflows_table(obj: Cashflows) -> MixedArray:
    # One row per payment booked, in the ticket's order, since #200, under the definition's field
    # names in its order: trade_id where the batch has it, trade_date, amount, currency on every
    # row, payment_day, the field's name since cashflow-payment-day.md and in the place it
    # had as payment_date, and counterparty and description where the batch has them, the
    # template's value on every row as a ticket's column is on its own, so that a payment reads
    # whole from its row; nothing of the valuation, which the results show.
    n = obj.rows
    headers: list[str] = []
    types: list[str] = []
    columns: list[NDArray[Any] | tuple[str, ...]] = []

    def text(name: str, column: tuple[str, ...]) -> None:
        headers.append(name)
        types.append("str")
        columns.append(column)

    def numbers(name: str, kind: str, column: NDArray[Any]) -> None:
        headers.append(name)
        types.append(kind)
        columns.append(column)

    if obj.trade_id is not None:
        numbers("trade_id", "int64", obj.trade_id)
    numbers("trade_date", "datetime64[D]", obj.trade_date)
    numbers("amount", "float64", obj.amount)
    text("currency", (obj.currency,) * n)
    numbers("payment_day", "datetime64[D]", obj.payment_date)
    if obj.counterparty is not None:
        text("counterparty", obj.counterparty)
    if obj.description is not None:
        text("description", obj.description)
    text("discount_curve_key", obj.discount_curve_key)  # last, cashflow-curve-keys.md
    return MixedArray.table([tuple(headers), tuple(types)], *columns)


@shown.register
def cashflow_results_table(obj: CashflowResults) -> MixedArray:
    # One row per payment group of the batch, a payment day and a key since
    # cashflow-curve-keys.md, in day order and paid or not, where it was one per payment day,
    # a batch on one key reading row for row as it did: the day, the amount the group's rows
    # summed to, whether it has paid, its factor, 1 on a paid group, its npv, its cash and its
    # dv01, with the currency and the valuation day on every row so that a row reads whole;
    # then the batch's totals once, on the first row and a dash below, cashflow_mark,
    # cashflow_cash and cashflow_dv01, the numbers the reports show, since a total repeated on
    # every row would read as each row's and sum twice; then the group's key, the name of
    # the curve it is valued on, after every column a sheet already reads; and last, since
    # currency-and-currency-unit.md, the unit of the currency the amounts are in, on every
    # row as the currency is.
    booked = obj.cashflows
    days = booked.payment_days[booked.group_day]
    n = days.size
    table = MixedArray.table(
        [
            (
                "payment_date",
                "amount",
                "is_paid",
                "payment_factor",
                "npv",
                "cash",
                "dv01",
                "currency",
                "as_of",
            ),
            (
                "datetime64[D]",
                "float64",
                "bool",
                "float64",
                "float64",
                "float64",
                "float64",
                "str",
                "datetime64[D]",
            ),
        ],
        days,
        booked.group_amounts,
        obj.is_paid,
        obj.payment_factor,
        obj.npv,
        obj.payment_cash,
        obj.group_dv01,
        (obj.currency,) * n,
        np.full(n, obj.as_of, dtype="datetime64[D]"),
    )
    once = np.zeros(n, dtype=np.bool_)
    once[0] = True  # the batch's own facts, on the first row
    return _widened(
        table,
        [
            _numbers_on("cashflow_mark", np.array([obj.mark]), once),
            _numbers_on("cashflow_cash", np.array([obj.cash]), once),
            _numbers_on("cashflow_dv01", np.array([obj.dv01]), once),
            _words_on("discount_curve_key", np.array(booked.keys, dtype=object)[booked.group_key]),
            _words_on("currency_unit", np.full(n, obj.currency_unit, dtype=object)),
        ],
    )


# A column a plain table cannot hold, written by kind: its name, its type word, and per body row
# its kind, its number and its word, a number on the rows that hold one and a dash on the rest,
# or a word on every row.


def _numbers_on(
    name: str, held: NDArray[np.float64], holds: NDArray[np.bool_], kind: str = "float64"
) -> Added:
    """A numeric column, float64 unless the caller says int64, holding a number on the rows that
    hold one, in row order, and a dash on the rest: every row, no row or the first row of each
    group, as the caller's mask says."""
    kinds = np.where(holds, NUMBER_CODE, TEXT_CODE).astype(np.uint8)
    slots = np.full(holds.size, np.nan)
    slots[holds] = held
    return name, kind, kinds, slots, np.full(holds.size, "-", dtype=object)


def _dates_on(name: str, days: NDArray[np.datetime64]) -> Added:
    """A datetime64[D] column holding a day on every row, as the serials the sheet formats, the
    check a date result gets."""
    serials = MixedArray.table([], days).numeric_slots[:, 0]
    kinds = np.full(days.size, NUMBER_CODE, dtype=np.uint8)
    return name, "datetime64[D]", kinds, serials, np.full(days.size, "-", dtype=object)


def _words_on(name: str, words: NDArray[np.object_]) -> Added:
    """A str column holding the caller's word on every row, a dash where it gives none."""
    kinds = np.full(words.size, TEXT_CODE, dtype=np.uint8)
    return name, "str", kinds, np.full(words.size, np.nan), words


def _assembled(added: list[Added]) -> MixedArray:
    """A table written by kind from columns alone, in the order given, for a readback whose
    dashed columns stand among columns every row holds, where _widened would put them last: the
    headings and the types first, then each body row's texts left to right, one per text cell,
    as _widened writes them."""
    body = added[0][2].size
    width = len(added)
    kinds = np.full((body + 2, width), TEXT_CODE, dtype=np.uint8)
    slots = np.full((body + 2, width), np.nan)
    words = np.full((body, width), "-", dtype=object)
    placed = np.zeros((body, width), dtype=np.bool_)
    for j, (_, _, column_kinds, column_slots, column_words) in enumerate(added):
        kinds[2:, j] = column_kinds
        slots[2:, j] = column_slots
        words[:, j] = column_words
        placed[:, j] = column_kinds == TEXT_CODE
    headings = (*(name for name, *_ in added), *(kind for _, kind, *_ in added))
    return MixedArray(kinds, slots, (*headings, *words[placed]))


def _widened(base: MixedArray, added: list[Added]) -> MixedArray:
    """A results table widened by columns a plain table cannot hold: a number on some rows and a
    dash on the rest, the batch's reserves on the first row as _ReportReserves spills them and a
    payment group's amount on the first row of its slots, since a column holding a number on one
    row and a word on the others is not one the table builder takes; or a word on every row, the
    currency once and a dash below it, a unit on every row. Each is written by kind, as the
    market's price column is: its kinds, its slots and its texts placed among the base's in sheet
    order, every body row of the base holding the same number of texts, one per text column, and
    the type row saying what each column is whatever its rows hold. Nothing is summed or looked
    up; every result has a first row, a batch observing at least once."""
    rows, width = base.shape
    body = rows - 2
    extra = len(added)
    kinds = np.full((rows, width + extra), TEXT_CODE, dtype=np.uint8)
    kinds[:, :width] = base.kinds
    slots = np.full((rows, width + extra), np.nan)
    slots[:, :width] = base.numeric_slots
    per_row = (len(base.texts) - 2 * width) // body
    words = np.full((body, per_row + extra), "-", dtype=object)
    words[:, :per_row] = np.array(base.texts[2 * width :], dtype=object).reshape(body, per_row)
    placed = np.ones((body, per_row + extra), dtype=np.bool_)
    for j, (_, _, column_kinds, column_slots, column_words) in enumerate(added):
        kinds[2:, width + j] = column_kinds
        slots[2:, width + j] = column_slots
        words[:, per_row + j] = column_words
        placed[:, per_row + j] = column_kinds == TEXT_CODE
    headings = (
        *base.texts[:width],
        *(name for name, *_ in added),
        *base.texts[width : 2 * width],
        *(kind for _, kind, *_ in added),
    )
    return MixedArray(kinds, slots, (*headings, *words[placed]))


@excel_function
def util_ReadHandle(
    handle: Annotated[
        Handle[object], "The cell showing any creator's result, such as B5, or a name for it."
    ],
) -> MixedArray:
    """Reads the object behind a handle and spills it as a table: its headers, a row of types,
    then one row per element."""
    return shown(handle)


@excel_function
def util_ReadPrompt(
    calendar: Annotated[
        Handle[Calendar],
        "The calendar handle: the cell showing _CreateCalendar's result, such as B5, or a name "
        "for it.",
    ],
) -> str:
    """Reads the contract code for the first price expected in the calendar's market price
    vector."""
    # The calendar's own reading of its first unfixed period: text in the cell, no object kept.
    return calendar.prompt_code()


@excel_function
def util_NextFut(
    contract: Annotated[
        str,
        "One contract code, a month letter and a two-digit year such as F26, typed or in a cell "
        "such as A2.",
    ],
) -> str:
    """Gives the next contract in the monthly sequence, G26 after F26 and F27 after Z26, spelled
    as the code given."""
    return next_contract(contract)


@excel_function
def util_FutToCme(
    contract: Annotated[
        str,
        "One contract code, a month letter and a two-digit year such as F26, typed or in a cell "
        "such as A2.",
    ],
) -> str:
    """Gives the contract month as CME's data feeds spell it, the year then the month, 202601 for
    F26."""
    return cme_code(contract)


@excel_function
def util_DateToFut(
    date: Annotated[
        Date, "One day, such as A2 or DATE(2026,1,15): any day of the contract's month."
    ],
) -> str:
    """Gives the contract code of the month a day falls in, F26 for any day of January 2026."""
    return code_of_month(date)


@excel_function
def util_FutToDate(
    contract: Annotated[
        str,
        "One contract code, a month letter and a two-digit year such as F26, typed or in a cell "
        "such as A2.",
    ],
) -> Date:
    """Gives the first day of a contract's month as a date, 1-Jan-2026 for F26."""
    return Date(first_day_of(contract))


@excel_function
def util_StartDate(
    period: Annotated[
        str,
        "One contract or strip label, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28, or "
        "its balance, BALZ26, typed or in a cell such as A2.",
    ],
    valuation_date: Annotated[
        Handle[ValuationDate] | None,
        "For a BAL label, the valuation-date handle whose day the balance starts on, such as B1 "
        "showing _CreateValuationDate's result; left out for any other label.",
    ] = None,
) -> Date:
    """Gives the first calendar day of a contract or strip, 1-Jan-2026 for F26, 1-Nov-2029 for
    W29 and the first day of the left label of F26-Z28; of its balance, the later of the
    valuation day and that first day."""
    return Date(start_date(period, None if valuation_date is None else valuation_date.as_of))


@excel_function
def util_EndDate(
    period: Annotated[
        str,
        "One contract or strip label, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28, or "
        "its balance, BALZ26, typed or in a cell such as A2.",
    ],
    valuation_date: Annotated[
        Handle[ValuationDate] | None,
        "For a BAL label, the valuation-date handle whose day the balance starts on, such as B1 "
        "showing _CreateValuationDate's result; left out for any other label.",
    ] = None,
) -> Date:
    """Gives the last calendar day of a contract or strip, 31-Jan-2026 for F26, 31-Mar-2030 for
    W29 and the last day of the right label of F26-Z28; of its balance, the same last day, a
    period ended before the valuation day refused."""
    return Date(end_date(period, None if valuation_date is None else valuation_date.as_of))


@excel_function
def util_ShiftDate(
    date: Annotated[Date, "The day to shift, such as A2 or DATE(2026,10,9)."],
    offset: Annotated[
        str,
        "The shift as text: one or more of a sign, a whole count and bd, cd or em, such as +1bd, "
        "-1bd, +7cd, +0em or +3em+25cd-1bd+1bd, applied left to right, typed or in a cell such "
        "as B2.",
    ],
    holiday_calendar: Annotated[
        Handle[HolidayCalendar] | None,
        "The holiday-calendar handle whose holidays business days skip, such as C2; left out for "
        "Monday to Friday with no holidays.",
    ] = None,
) -> Date:
    """Shifts a date by business days, calendar days or month ends, +1bd the next business day,
    -1bd the one before, +7cd a week on, +0em the month's last day, a chain such as
    +3em+25cd-1bd+1bd applied left to right, and shows the date."""
    return Date(shift_date(date, offset, holiday_calendar))


@excel_function
def util_InterpolateContracts(
    index: Annotated[
        Handle[Index],
        "The index handle: the cell showing _CreateIndex's result, such as B9, or a name for it; a "
        "futures index, whose schedule has a futures expiry per contract.",
    ],
    anchor_contracts: Annotated[
        TextColumn,
        "A column of at least two contract months in increasing order, each a code such as F26 or "
        "the month as CME spells it, 202601, as text, without a header, such as A2:A3.",
    ],
    anchor_prices: Annotated[
        NumberColumn,
        "A column of one price per anchor, in the same rows and the index's quote convention, "
        "without a header, such as B2:B3.",
    ],
) -> MixedArray:
    """Infers every monthly contract from the first anchor's month through the last's, each with
    the index's futures expiry and the price on the straight line between its anchors weighted
    by calendar days, and spills contract_code, future_expiry and price."""
    made = interpolate_contracts(index, anchor_contracts, anchor_prices, WorkCounter())
    return MixedArray.table(
        [("contract_code", "future_expiry", "price"), ("str", "datetime64[D]", "float64")],
        made.codes,
        made.expiries,
        made.prices,
    )


@excel_function
def util_BumpDiscountCurve(
    curve: Annotated[
        Handle[DiscountCurve],
        "The curve handle: the cell showing _CreateDiscountCurve's or this function's result, "
        "such as B2, or a name for it.",
    ],
    bump_bps: Annotated[
        float,
        "The parallel shift of the curve's zero rates in basis points, a signed number: 1 for one "
        "basis point up, -25 for twenty-five down, 0.5 for half a point; a number, not text.",
    ],
) -> Handle[DiscountCurve]:
    """Bumps a discount curve by a parallel shift of its continuously compounded zero rates in
    basis points, every day's factor moved from its start, ACT/365F, under the
    curve's rules, and shows the new curve's handle, an ordinary curve for _EvaluateTrades."""
    return bump_discount_curve(curve, bump_bps, WorkCounter())
