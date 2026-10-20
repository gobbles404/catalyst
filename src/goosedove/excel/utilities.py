"""The utilities: worksheet functions that read what the library holds, or reshape what the sheet
supplies, and change nothing. docs/library/utilities/ holds a page per function.

The docstring is what Excel shows about the function, and the words beside each parameter are
what it shows about that argument as a person types the formula. How to write a line is
docs/library/conventions.md under Excel help; the pages quote the lines.
"""

from collections.abc import Mapping
from functools import singledispatch
from typing import Annotated, Any, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar
from goosedove.cashflows.booking import Cashflows
from goosedove.cashflows.valuation import CashflowResults
from goosedove.excel.bridge import (
    NUMBER_CODE,
    TEXT_CODE,
    Date,
    Handle,
    MixedArray,
    NumberColumn,
    TextColumn,
    excel_function,
)
from goosedove.globals.discount_curve import DiscountCurve, bump_discount_curve
from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.globals.valuation_date import ValuationDate
from goosedove.index_definitions.contract_codes import (
    cme_code,
    code_of_month,
    first_day_of,
    next_contract,
)
from goosedove.index_definitions.contract_specifications import ContractSpecifications
from goosedove.index_definitions.date_offsets import shift_date
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.gas_daily_schedule import GasDailySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.index_conventions import IndexConventions
from goosedove.index_definitions.kind import named
from goosedove.index_definitions.periods import end_date, start_date
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FieldType, Instrument
from goosedove.market.market import Market
from goosedove.market.market_history import MarketHistory
from goosedove.market_data.futures_fixings import FuturesFixings
from goosedove.market_data.gas_daily_fixings import GasDailyFixings
from goosedove.market_data.iferc_fixings import IfercFixings
from goosedove.market_data.interpolated_contracts import interpolate_contracts
from goosedove.market_data.price_vector import PriceVector
from goosedove.quoting.template import QuoteTemplate
from goosedove.trades.aggregation import AggregateResults
from goosedove.trades.encoding import Encoded
from goosedove.trades.preparation import PreparedTrades
from goosedove.trades.resolution import Trades
from goosedove.trades.results import TradeResults
from goosedove.trades.schedule_methods import METHOD_NAMES
from goosedove.trades.template import TradeTemplate
from goosedove.trades.terms import BASIS_NAMES


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


def _priced_column(
    base: MixedArray,
    header: str,
    words: NDArray[Any] | str,
    *priced: tuple[NDArray[np.intp], NDArray[np.float64]],
) -> MixedArray:
    """A calendar's table widened by one column that holds a number on some days and a word on
    the others: each priced pair names calendar rows and the prices on them, and the word, one
    for every day or one per day, shows on the rest. The words are display, not values, and a
    column holding numbers on some rows and words on others is not one the table builder takes,
    so the column is written by kind: its kinds, its slots, and its words into the texts. The
    calendar's own table stands as it is, nothing rebuilt.

    The texts in sheet order: each heading row's four then this column's, and each day's code
    then, on a day without a price, its word; the calendar's body texts are its codes alone, one
    per day, in the same order.
    """
    rows, width = base.shape
    kinds = np.empty((rows, width + 1), dtype=np.uint8)
    kinds[:, :width] = base.kinds
    kinds[:, width] = TEXT_CODE
    slots = np.full((rows, width + 1), np.nan)
    slots[:, :width] = base.numeric_slots
    pairs = np.empty((rows - 2, 2), dtype=object)
    pairs[:, 0] = base.texts[2 * width :]
    pairs[:, 1] = words
    worded = np.ones((rows - 2, 2), dtype=bool)
    for on, prices in priced:  # the pairs, not the prices: one or two of them
        kinds[on + 2, width] = NUMBER_CODE
        slots[on + 2, width] = prices
        worded[on, 1] = False
    headings = (*base.texts[:width], header, *base.texts[width : 2 * width], "float64")
    return MixedArray(kinds, slots, (*headings, *pairs[worded]))


@shown.register
def market_history_table(obj: MarketHistory) -> MixedArray:
    # The calendar's four columns, then fixing_price: the price fixed on each fixed and priced
    # period, a number, and a word on every other, closed where the calendar does not price the
    # day and unfixed where it prices but has not fixed, whatever the market.
    calendar = obj.calendar
    words = np.empty(calendar.dates.size, dtype=object)
    words[:] = "closed"
    words[calendar.is_priced] = "unfixed"
    return _priced_column(
        calendar_table(calendar), "fixing_price", words, (obj.fixed_rows, obj.fixing_prices)
    )


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
    return _priced_column(
        calendar_table(calendar, rows),
        "price",
        "closed",
        (history.fixed_rows, history.fixing_prices),
        (live, obj.live_prices(calendar.contract[live])),
    )


@shown.register
def futures_fixings_table(obj: FuturesFixings) -> MixedArray:
    # Newest first, as the creator takes them: the columns are kept oldest first, and each is
    # read here from its last row back, a view and no copy, date beside its own settle, so the
    # spill pasted back into the creator makes the same fixings.
    return MixedArray.table(
        [("date", "settle"), ("datetime64[D]", "float64")], obj.dates[::-1], obj.settles[::-1]
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
    # the specification's name as the index spells it; the payment lag and the day it gives for a
    # financial settlement; since #175 marketing_reserve where the batch has it, the amount the
    # row booked shown on each of its components, the one amount and no allocation among them,
    # so a reader never sums the column down a strip;
    # then what the resolution derived, since #172 entered_contract_code, the code text the row
    # entered as typed, kept apart from the contract its components resolved to under
    # contract_code, and the words `(not supplied)` where the row entered none and booked by
    # its dates, display and no value, then start_date and end_date, the days the component
    # covers, its whole month from a code and its share of a booked period from dates,
    # covered_days, the calendar days between them, and component_quantity, the quantity the
    # basis gives it, the entered quantity times those days under calday, so that a reader never
    # takes the month's total for the entered daily quantity;
    # then what the encoding made, quote_quantity the component quantity in the index's quote
    # quantity unit, coefficient and offset in the settlement currency.
    terms, encoding = obj.resolved, obj.encoded
    rows = terms.occurrence
    n = rows.size
    codes = np.array(terms.schedule.codes, dtype=object)[terms.contract]
    headers: list[str] = ["row"]
    types: list[str] = ["int64"]
    columns: list[NDArray[Any] | tuple[str, ...]] = [(rows + 1).astype(np.int64)]

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
    text("contract_code", tuple(codes))
    text("schedule_method", tuple(METHOD_NAMES[terms.schedule_method[rows]]))
    text("route", (terms.route.value,) * n)
    text("settlement_method", (terms.settlement.value,) * n)
    labels("clearing_house", terms.clearing_house)
    labels("counterparty", terms.counterparty)
    labels("discount_curve_key", terms.discount_curve_key)  # named-curves-slice-3.md
    labels("broker", terms.broker)
    numbers("quantity", "float64", terms.quantity)
    text(
        "quantity_unit",
        tuple(np.array(terms.index.specifications.names, dtype=object)[terms.specification[rows]]),
    )
    text("quantity_per", tuple(BASIS_NAMES[terms.quantity_per[rows]]))
    numbers("fixed_price", "float64", terms.fixed_price)
    if terms.payment is not None:
        lags = np.array(terms.payment.lag, dtype=object)  # as the ticket or the template wrote
        text("payment_time_lag", tuple(lags[rows]))
        numbers("payment_date", "datetime64[D]", terms.payment.date)
    if terms.marketing_reserve is not None:  # the row's one amount on each of its components
        numbers("marketing_reserve", "float64", terms.marketing_reserve[rows])
    entered = np.full(obj.code_entered.size, NOT_SUPPLIED, dtype=object)
    entered[obj.code_entered] = np.array(obj.entered_codes, dtype=object)
    text("entered_contract_code", tuple(entered[rows]))
    numbers("start_date", "datetime64[D]", terms.start_date)
    numbers("end_date", "datetime64[D]", terms.end_date)
    numbers("covered_days", "int64", terms.covered_days)
    numbers("component_quantity", "float64", terms.component_quantity)
    numbers("quote_quantity", "float64", encoding.quote_quantity)
    numbers("coefficient", "float64", encoding.coefficient)
    numbers("offset", "float64", encoding.offset)
    return MixedArray.table([tuple(headers), tuple(types)], *columns)


def _slot_names(
    encoding: Encoded,
) -> tuple[list[str], list[str], list[NDArray[Any] | tuple[str, ...]]]:
    # The columns that name a slot: the contract pricing the day, whose settle fixes the slot and
    # whose quote projects it; the contract the slot's group was booked on, which owns the fixed
    # leg and the payment and under asian may be another; the observation day; and, for a
    # financial settlement, the day the slot's payment group pays, so that two groups observing
    # one day read apart whatever contract prices it; a physical settlement pays on no day and
    # shows none.
    codes = np.array(encoding.terms.schedule.codes, dtype=object)
    names = ["pricing_contract", "booked_contract", "observation_date"]
    types = ["str", "str", "datetime64[D]"]
    columns: list[NDArray[Any] | tuple[str, ...]] = [
        tuple(codes[encoding.slot_reference]),
        tuple(codes[encoding.group_contract[encoding.slot_group]]),
        encoding.slot_date,
    ]
    if encoding.payment_date is not None:
        names.append("payment_date")
        types.append("datetime64[D]")
        columns.append(encoding.payment_date[encoding.slot_group])
    return names, types, columns


@shown.register
def prepared_trades_table(obj: PreparedTrades) -> MixedArray:
    # One row per slot, the dated axis as the preparation left it: the slot named, whether it has
    # fixed, whether its payment group has settled, its live coefficient, the settlement currency
    # its price moves the mark by, zero where it has fixed, and the same exposure in lots of the
    # index's reporting lot; nothing is made again, every column the record's own or a gather of
    # one.
    encoding = obj.encoded
    names, types, columns = _slot_names(encoding)
    return MixedArray.table(
        [
            (*names, "is_fixed", "is_settled", "live_coefficient", "live_lots"),
            (*types, "bool", "bool", "float64", "float64"),
        ],
        *columns,
        obj.is_fixed,
        obj.is_settled[encoding.slot_group],
        obj.dated_live_exposure,
        obj.dated_live_lots,
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
    its curve's word, its currency and its DV01. The collection's totals and vectors are
    _ReportRisk's to show; no handle text, since a source's cell may have been released while
    the collection holds the object."""
    sources = obj.sources
    n = len(sources)
    # The words of every curve a source used, in its own key order, since named-curves-slice-3.md,
    # joined with a comma and a space; a cleared source, with no contribution, a dash.
    word_of_curve = {id(group.curve): group.word for group in obj.rate_groups}
    curve = np.array(
        [
            ", ".join([word_of_curve[id(c.curve)] for c in source.rate_contributions]) or "-"
            for source in sources
        ],
        dtype=object,
    )
    index_names: list[str] = []
    lots: list[str] = []
    routes: list[str] = []
    trade = np.zeros(n, dtype=np.bool_)
    nominal = np.zeros(n)
    delta = np.zeros(n)
    cross = np.zeros(n)
    units = np.full(n, "-", dtype=object)
    for k, source in enumerate(sources):
        match source:
            case TradeResults():
                terms = source.prepared.encoded.terms
                index_names.append(terms.index.name)
                lots.append(terms.reporting_lot.name)
                routes.append(source.route.value)
                trade[k] = True
                nominal[k] = source.lot_delta_total
                delta[k] = source.discounted_lot_delta_total
                cross[k] = source.cross_gamma_total
                units[k] = f"{source.lot_unit} per basis point"
            case CashflowResults():
                index_names.append("-")
                lots.append("-")
                routes.append("cashflow")
            case _:
                assert_never(source)
    every = np.ones(n, dtype=np.bool_)
    return _assembled(
        [
            _numbers_on("position", np.arange(1, n + 1, dtype=np.float64), every, "int64"),
            _words_on("index", np.array(index_names, dtype=object)),
            _words_on("reporting_lot", np.array(lots, dtype=object)),
            _words_on("route", np.array(routes, dtype=object)),
            _words_on("curve", curve),
            _words_on("currency", np.array([source.currency for source in sources], dtype=object)),
            _numbers_on("nominal_delta", nominal[trade], trade),
            _numbers_on("delta", delta[trade], trade),
            _numbers_on("dv01", np.array([source.dv01 for source in sources]), every),
            _dates_on("as_of", np.full(n, obj.as_of, dtype="datetime64[D]")),
            _numbers_on("cross_gamma", cross[trade], trade),
            _words_on("cross_gamma_unit", units),
        ]
    )


@shown.register
def trade_results_table(obj: TradeResults) -> MixedArray:
    # One row per slot, the dated contents of the result: the slot named, whether it has fixed,
    # the slot's own live coefficient and the same exposure in lots, its live contribution,
    # coefficient times its contract's quote, all zero where it has fixed, and its contract's
    # risk, four retained vectors read by each slot's reference and so the same number on every
    # slot of one contract, whatever group holds it: the sensitivity and the lot delta, nominal,
    # and since #177 their discounted twins beside each, a cleared result's twins the nominal arrays
    # themselves, every one named contract_... so that none is read as the slot's and the
    # discounted apart from the nominal; then the two units those numbers are in, the batch's
    # facts on every row so that a row reads whole. The mark, the cash and the totals are the
    # reports' to show. Then, since #177, the payment groups' retained facts: payment_factor on
    # every slot, its group's, and payment_amount, group_npv and group_dv01 once per group, on the
    # first slot row the group holds and a dash on its other rows, since a group's amount repeated
    # on each of its slots would read as each slot's and sum twice; a cleared result retains none
    # of the four and shows a dash on every row. Then, since #170, the batch's reserves, once: the
    # three totals and their currency on the first slot row, as _ReportReserves spills them, and a
    # dash on every later row, since they are the batch's booked amounts and no slot's. Then,
    # since #197, the contract's cross-gamma on every slot, read by the slot's reference as the
    # contract's four risks are and so the same number on every slot of one contract, repeated
    # context and no slot's own risk, a cleared result's zero, and its unit, lots per basis
    # point, on every row; appended last so that no column before them moves. Then, since
    # named-curves-slice-3.md, the slot's group's key and the name of the curve the group was
    # discounted on, on every row, a cleared result a dash in both; appended last likewise.
    prepared = obj.prepared
    encoding = prepared.encoded
    names, types, columns = _slot_names(encoding)
    slots = encoding.slot_group.size
    contribution = np.zeros(slots)
    contribution[prepared.live_slot] = obj.dated_live_contribution
    reference = encoding.reference_of_slot
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
                "contract_lot_delta",
                "contract_delta",
                "sensitivity_unit",
                "lot_unit",
            ),
            (*types, "bool", *("float64",) * 7, "str", "str"),
        ],
        *columns,
        prepared.is_fixed,
        prepared.dated_live_exposure,
        prepared.dated_live_lots,
        contribution,
        obj.price_sensitivity[reference],
        obj.discounted_price_sensitivity[reference],
        obj.lot_delta[reference],
        obj.discounted_lot_delta[reference],
        (obj.price_sensitivity_unit,) * slots,
        (obj.lot_unit,) * slots,
    )
    group = encoding.slot_group
    first = np.zeros(slots, dtype=np.bool_)
    first[np.unique(group, return_index=True)[1]] = True  # each group's first slot row
    once = np.zeros(slots, dtype=np.bool_)
    once[0] = True  # the batch's own facts, on the first row
    every = np.ones(slots, dtype=np.bool_)
    if obj.payment_factor is None:
        # A cleared result: nothing retained for the four, a dash on every row.
        none, nothing = np.zeros(slots, dtype=np.bool_), np.empty(0)
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
    # The contract's cross-gamma with every used curve shifted together, the contributions' by
    # reference summed, one row per curve; a cleared result's zero.
    cross = np.zeros(slots)
    for contribution in obj.cross_contributions:
        cross += contribution.cross_gamma[reference]
    per_bp = np.full(slots, f"{obj.lot_unit} per basis point", dtype=object)
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
            _words_on("currency", currency),
            _numbers_on("contract_cross_gamma", cross, every),
            _words_on("cross_gamma_unit", per_bp),
            _words_on("discount_curve_key", keys),
            _words_on("discount_curve", curve_names),
        ],
    )


PAYMENT_COLUMNS = ("payment_factor", "payment_amount", "group_npv", "group_dv01")


@shown.register
def cashflows_table(obj: Cashflows) -> MixedArray:
    # One row per payment booked, in the ticket's order, since #200, under the definition's field
    # names in its order: trade_id where the batch has it, trade_date, amount, currency on every
    # row, payment_date, and counterparty and description where the batch has them, the
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
    numbers("payment_date", "datetime64[D]", obj.payment_date)
    if obj.counterparty is not None:
        text("counterparty", obj.counterparty)
    if obj.description is not None:
        text("description", obj.description)
    return MixedArray.table([tuple(headers), tuple(types)], *columns)


@shown.register
def cashflow_results_table(obj: CashflowResults) -> MixedArray:
    # One row per distinct payment day of the batch, increasing, paid or not, since #200: the
    # day, the amount the rows summed to on it, whether it has paid, its factor, 1 on a paid
    # day, its npv, its cash and its dv01, with the currency and the valuation day on every row so
    # that a row reads whole; then the batch's totals once, on the first row and a dash below,
    # cashflow_mark, cashflow_cash and cashflow_dv01, the numbers the reports show, since a total
    # repeated on every day would read as each day's and sum twice.
    days = obj.cashflows.payment_days
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
        obj.cashflows.payment_amounts,
        obj.is_paid,
        obj.payment_factor,
        obj.npv,
        obj.payment_cash,
        obj.rate_contributions[0].dv01_by_day,  # one curve values a batch of cashflows
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
        ],
    )


# A column a plain table cannot hold, written by kind: its name, its type word, and per body row
# its kind, its number and its word, a number on the rows that hold one and a dash on the rest,
# or a word on every row.
Added = tuple[str, str, NDArray[np.uint8], NDArray[np.float64], NDArray[np.object_]]


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
