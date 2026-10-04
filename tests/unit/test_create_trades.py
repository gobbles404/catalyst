"""_CreateTrades and its resolution child on the NG example of
docs/engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md: a template
and a ticket completed into the kernel's resolved terms, every field from one of the two, codes
in either case and strips resolved by month against every code of the schedule, payment days
counted strictly after the expiry on the payment calendar, each refusal in the decided order and
naming the sheet's row, the batch's handle and its spill. docs/library/trades/create-trades.md
is the page."""

import os
import re
from collections.abc import Mapping
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells, Handle, register
from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.gas_daily_schedule import gas_daily_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FUTURE, NONE, FieldType, Instrument
from goosedove.instruments.fields import FieldValues
from goosedove.trades.resolution import CONDITIONS, Trades, resolved, trades
from goosedove.trades.template import TradeTemplate, trade_template
from goosedove.trades.terms import QuantityPer, Route, ScheduleMethod, Settlement


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


# --- the page's static facts, as the kernel tests have them ---------------------------------


def an_index(
    name: str = "Henry Hub NYMEX",
    contracts: tuple[tuple[str, str], ...] = (
        ("X26", "2026-10-28"),
        ("Z26", "2026-11-25"),
        ("F27", "2026-12-29"),
    ),
    holidays: tuple[str, ...] = ("2026-11-26", "2026-12-25"),
    lots: tuple[tuple[str, float, str], ...] = (("NYMEX NG", 10_000.0, "MMBTU"),),
) -> Index:
    codes = tuple(code for code, _ in contracts)
    schedule = futures_schedule(codes, dates(*(expiry for _, expiry in contracts)), None)
    names = tuple(name for name, _, _ in lots)
    return index(
        name,
        schedule,
        index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
        contract_specifications(
            names,
            np.array([size for _, size, _ in lots]),
            tuple(unit for _, _, unit in lots),
            np.zeros(len(lots)),
            np.zeros(len(lots)),
            UNITS,
        ),
        holiday_calendar(dates(*holidays)),
        UNITS,
    )


NG = an_index()
TOY = an_index(
    "TOY_GAS",
    (("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29"), ("G27", "2027-01-27")),
    ("2026-11-26", "2026-12-25", "2027-01-01"),
    (("TOY", 10_000.0, "MMBTU"),),
)
# The toy's payment calendar: Monday to Friday less 26 November, 25 December and New Year's Day.
PAYMENT_CALENDAR = holiday_calendar(dates("2026-11-26", "2026-12-25", "2027-01-01"))

NG_TEMPLATE: dict[str, object] = {
    "contract_specification": "NYMEX NG",
    "quantity_unit": "LOT",
    "quantity_per": "month",
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "physical",
    "clearing_house": "CME Clearing",
}
TOY_TEMPLATE: dict[str, object] = {
    **NG_TEMPLATE,
    "contract_specification": "TOY",
    "settlement_method": "financial",
    "clearing_house": "TEST_CLEARER",
    "payment_time_lag": "+2bd",
    "payment_holiday_calendar": PAYMENT_CALENDAR,
}
NG_TICKET: dict[str, list[object]] = {
    "trade_id": ["NG-001", "NG-002", "NG-003", "NG-004", "NG-001"],
    "trade_date": ["2026-09-24", "2026-09-24", "2026-09-25", "2026-09-25", "2026-09-24"],
    "contract_code": ["Z26", "Z26", "F27", "F27", "Z26"],
    "quantity": [10, -4, 7, -12, 10],
    "fixed_price": [3.100, 3.150, 3.400, 3.350, 3.100],
}


def typed(definition: Instrument, name: str, values: list[object]) -> object:
    """A column as the seam hands it over, typed by its field."""
    match next(field for field in definition.fields if field.name == name).type:
        case FieldType.NUMBER:
            return np.array(values, dtype=np.float64)
        case FieldType.DATE:
            return np.array(values, dtype="datetime64[D]")
        case FieldType.TEXT | FieldType.CODE:
            return tuple(str(value) for value in values)
        case FieldType.HOLIDAY_CALENDAR:
            return tuple(values)


def a_ticket(columns: Mapping[str, list[object]], definition: Instrument = FUTURE) -> FieldValues:
    rows = len(next(iter(columns.values())))
    return FieldValues(
        definition,
        rows,
        tuple(columns),
        {name: typed(definition, name, values) for name, values in columns.items()},
    )


def a_template(fields: Mapping[str, object], definition: Instrument = FUTURE) -> TradeTemplate:
    return trade_template(a_ticket({name: [value] for name, value in fields.items()}, definition))


def created(
    ix: Index = NG,
    ticket: Mapping[str, list[object]] = NG_TICKET,
    template: Mapping[str, object] = NG_TEMPLATE,
) -> tuple[Trades, WorkCounter]:
    counter = WorkCounter()
    return trades(ix, a_ticket(ticket), a_template(template), UNITS, counter), counter


def refused(
    ix: Index = NG,
    ticket: Mapping[str, list[object]] = NG_TICKET,
    template: Mapping[str, object] = NG_TEMPLATE,
) -> str:
    with pytest.raises(ValueError) as refusal:
        created(ix, ticket, template)
    return str(refusal.value)


# --- the NG example ---------------------------------------------------------------------------


def test_the_ng_rows_resolve_to_the_terms_the_kernel_tests_supply() -> None:
    batch, counter = created()
    terms = batch.resolved
    assert terms.instrument is FUTURE and terms.index is NG and terms.schedule is NG.schedule
    assert terms.specification == 0
    assert (terms.route, terms.settlement) == (Route.CLEARED, Settlement.PHYSICAL)
    assert (terms.schedule_method, terms.quantity_per) == (
        ScheduleMethod.LASTDAY,
        QuantityPer.MONTH,
    )
    assert terms.quantity_unit == "LOT"
    assert terms.labels == ("NG-001", "NG-002", "NG-003", "NG-004", "NG-001")
    assert terms.clearing_house == ("CME Clearing",) * 5  # the template's, for every row
    assert terms.broker is None
    np.testing.assert_array_equal(
        terms.trade_dates,
        dates("2026-09-24", "2026-09-24", "2026-09-25", "2026-09-25", "2026-09-24"),
    )
    np.testing.assert_array_equal(terms.occurrence, [0, 1, 2, 3, 4])
    np.testing.assert_array_equal(terms.contract, [1, 1, 2, 2, 1])  # Z26 and F27 by row
    np.testing.assert_array_equal(terms.lots, [10, -4, 7, -12, 10])
    np.testing.assert_array_equal(terms.fixed_price, [3.1, 3.15, 3.4, 3.35, 3.1])
    assert terms.payment is None
    assert batch.encoded.terms is terms
    np.testing.assert_array_equal(
        batch.encoded.quantity, [100_000, -40_000, 70_000, -120_000, 100_000]
    )
    np.testing.assert_array_equal(
        batch.encoded.offset, [-310_000, 126_000, -238_000, 402_000, -310_000]
    )
    np.testing.assert_array_equal(batch.encoded.inputs, [1, 2])
    np.testing.assert_array_equal(batch.encoded.exposure, [160_000, -50_000])
    assert counter.freeze().as_dict() == {
        "encoded_components": 5,
        "encoded_inputs": 2,
        "resolved_components": 5,
        "resolved_occurrences": 5,
        "schedule_codes_read": 3,
    }


def test_codes_resolve_in_either_case_against_a_schedule_in_either_case() -> None:
    mixed = an_index(
        contracts=(("x26", "2026-10-28"), ("Z26", "2026-11-25"), ("f27", "2026-12-29"))
    )
    batch, _ = created(mixed, {**NG_TICKET, "contract_code": ["z26", "Z26", "F27", "f27", "z26"]})
    np.testing.assert_array_equal(batch.resolved.contract, [1, 1, 2, 2, 1])


def test_a_strip_makes_one_component_per_month_on_its_one_occurrence() -> None:
    ticket: dict[str, list[object]] = {
        "trade_id": ["S1", "S2"],
        "trade_date": ["2026-09-24", "2026-09-24"],
        "contract_code": ["Z26-F27", "f27"],
        "quantity": [3, -1],
        "fixed_price": [3.2, 3.3],
    }
    batch, counter = created(TOY, ticket, TOY_TEMPLATE)
    terms = batch.resolved
    np.testing.assert_array_equal(terms.occurrence, [0, 0, 1])
    np.testing.assert_array_equal(terms.contract, [1, 2, 2])
    np.testing.assert_array_equal(terms.lots, [3, 3, -1])  # the strip's lots in every month
    np.testing.assert_array_equal(terms.fixed_price, [3.2, 3.2, 3.3])
    assert terms.payment is not None
    np.testing.assert_array_equal(
        terms.payment.date, dates("2026-11-30", "2026-12-31", "2026-12-31")
    )  # two business days after each expiry, the page's dates, 26 November closed
    np.testing.assert_array_equal(terms.payment.lag_days, [2, 2])  # the terms, per occurrence
    assert terms.payment.calendar == (PAYMENT_CALENDAR, PAYMENT_CALENDAR)
    assert terms.named(1) == "trade 'S1' at row 1"
    assert counter.freeze()["resolved_components"] == 3
    assert counter.freeze()["resolved_occurrences"] == 2


def test_a_whole_year_strip_resolves_twelve_months_against_a_long_schedule() -> None:
    months = np.arange("2026-10", "2028-01", dtype="datetime64[M]")
    letters = "FGHJKMNQUVXZ"
    contracts = tuple(
        (
            f"{letters[int(m.astype(int)) % 12]}{str(m)[2:4]}",
            str(m.astype("datetime64[D]") + np.timedelta64(24, "D")),
        )
        for m in months
    )
    long = an_index(contracts=contracts)
    batch, _ = created(
        long,
        {
            "trade_id": ["Y"],
            "trade_date": ["2026-09-24"],
            "contract_code": ["cal27"],
            "quantity": [2],
            "fixed_price": [3.0],
        },
    )
    assert long.schedule.codes[3] == "F27"
    np.testing.assert_array_equal(batch.resolved.contract, np.arange(3, 15))
    np.testing.assert_array_equal(batch.resolved.occurrence, np.zeros(12, dtype=np.intp))
    np.testing.assert_array_equal(batch.encoded.quantity_of_input, np.full(12, 20_000.0))


def test_a_templates_field_applies_to_every_row_and_a_tickets_varies() -> None:
    batch, _ = created(
        NG,
        {"trade_id": ["a", "b", "c"], "broker": ["ION", "TP", "ION"]},
        {
            **NG_TEMPLATE,
            "trade_date": day("2026-09-24"),
            "contract_code": "z26",
            "quantity": 2.0,
            "fixed_price": 3.0,
        },
    )
    terms = batch.resolved
    np.testing.assert_array_equal(terms.trade_dates, dates(*["2026-09-24"] * 3))
    np.testing.assert_array_equal(terms.contract, [1, 1, 1])
    np.testing.assert_array_equal(terms.lots, [2, 2, 2])
    assert terms.broker == ("ION", "TP", "ION")
    assert terms.labels == ("a", "b", "c")


def test_a_batch_field_in_the_ticket_is_taken_when_every_row_agrees() -> None:
    template = {name: value for name, value in NG_TEMPLATE.items() if name != "route"}
    batch, _ = created(NG, {**NG_TICKET, "route": ["cleared"] * 5}, template)
    assert batch.resolved.route is Route.CLEARED
    without_labels, _ = created(NG, {k: v for k, v in NG_TICKET.items() if k != "trade_id"})
    assert without_labels.resolved.labels is None
    assert without_labels.resolved.named(4) == "trade at row 5"


# --- payment days ---------------------------------------------------------------------------


def one_payment_day(expiry: str, holidays: tuple[str, ...], lag: str) -> np.datetime64:
    """The payment day of one Z26 lot on an index whose Z26 expires that day, under a payment
    calendar of those holidays and that lag."""
    ix = an_index(
        "pay", (("X26", "2026-10-28"), ("Z26", expiry)), lots=(("TOY", 10_000.0, "MMBTU"),)
    )
    batch, _ = created(
        ix,
        {
            "trade_id": ["p"],
            "trade_date": ["2026-09-24"],
            "contract_code": ["Z26"],
            "quantity": [1],
            "fixed_price": [3.0],
        },
        {
            **TOY_TEMPLATE,
            "payment_time_lag": lag,
            "payment_holiday_calendar": holiday_calendar(dates(*holidays)),
        },
    )
    assert batch.resolved.payment is not None
    return batch.resolved.payment.date[0]


def test_payment_days_are_counted_strictly_after_the_expiry() -> None:
    # The page's illustration: a Friday expiry with the Monday closed pays Tuesday at +1bd and
    # Wednesday at +2bd; an expiry the payment calendar closes is rolled back first, so the
    # Thursday of Thanksgiving pays Friday at +1bd, the closed day itself never counted.
    assert one_payment_day("2026-12-04", ("2026-12-07",), "+1bd") == day("2026-12-08")
    assert one_payment_day("2026-12-04", ("2026-12-07",), "+2bd") == day("2026-12-09")
    assert one_payment_day("2026-11-26", ("2026-11-26",), "+1bd") == day("2026-11-27")
    assert one_payment_day("2026-11-26", ("2026-11-26",), "+2bd") == day("2026-11-30")
    assert one_payment_day("2026-11-25", (), "+1bd") == day("2026-11-26")  # no holiday given


def test_payment_calendars_and_lags_in_the_ticket_apply_row_by_row() -> None:
    closes_two_days = holiday_calendar(dates("2026-11-26", "2026-11-27"))
    open_calendar = holiday_calendar(dates())
    template = {
        name: value
        for name, value in TOY_TEMPLATE.items()
        if name not in ("payment_time_lag", "payment_holiday_calendar")
    }
    batch, _ = created(
        TOY,
        {
            "trade_id": ["a", "b"],
            "trade_date": ["2026-09-24", "2026-09-24"],
            "contract_code": ["Z26", "F27"],
            "quantity": [1, 1],
            "fixed_price": [3.0, 3.0],
            "payment_time_lag": ["+1bd", "+3bd"],
            "payment_holiday_calendar": [closes_two_days, open_calendar],
        },
        template,
    )
    payment = batch.resolved.payment
    assert payment is not None
    np.testing.assert_array_equal(payment.date, dates("2026-11-30", "2027-01-01"))
    np.testing.assert_array_equal(payment.lag_days, [1, 3])
    assert payment.calendar == (closes_two_days, open_calendar)


# --- what is refused, naming the field and the sheet's row ----------------------------------


@pytest.mark.parametrize(
    ("ticket", "template", "message"),
    [
        (
            {**NG_TICKET, "quantity_unit": ["LOT"] * 5},
            NG_TEMPLATE,
            "quantity_unit is supplied by the template and by the ticket, expected by one of them",
        ),
        (
            {name: values for name, values in NG_TICKET.items() if name != "fixed_price"},
            NG_TEMPLATE,
            "fixed_price is missing, expected a value in the template or a column in the ticket",
        ),
        (
            NG_TICKET,
            {name: value for name, value in NG_TEMPLATE.items() if name != "settlement_method"},
            "settlement_method is missing, expected a value in the template or a column in the "
            "ticket",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "contract_specification": "ICE NG"},
            "contract_specification is 'ICE NG', expected one of the index's specifications: "
            "'NYMEX NG'",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "schedule_method": "penultimate"},
            "schedule_method is 'penultimate', expected lastday, the one method built",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "quantity_unit": "MMBTU"},
            "quantity_unit is 'MMBTU', expected LOT, the one quantity unit built",
        ),
        (
            {**NG_TICKET, "route": ["cleared", "cleared", "bilateral", "cleared", "cleared"]},
            {name: value for name, value in NG_TEMPLATE.items() if name != "route"},
            "route row 3 is 'bilateral', expected 'cleared' as at row 1; a batch has one route",
        ),
        (
            NG_TICKET,
            {name: value for name, value in NG_TEMPLATE.items() if name != "clearing_house"},
            "clearing_house is missing, expected it when route = cleared",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "route": "bilateral"},
            "clearing_house is 'CME Clearing', expected none unless route = cleared",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "payment_time_lag": "+1bd"},
            "payment_time_lag is '+1bd', expected none unless settlement_method = financial",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "payment_holiday_calendar": PAYMENT_CALENDAR},
            "payment_holiday_calendar is a holiday calendar, expected none unless "
            "settlement_method = financial",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "settlement_method": "financial"},
            "payment_time_lag is missing, expected it when settlement_method = financial",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "settlement_method": "financial", "payment_time_lag": "+1bd"},
            "payment_holiday_calendar is missing, expected it when settlement_method = financial",
        ),
        (
            {**NG_TICKET, "contract_code": ["Z26", "Z2026", "F27", "F27", "Z26"]},
            NG_TEMPLATE,
            "contract_code row 2 is 'Z2026', expected a contract or strip with two-digit years, "
            "such as F26, 1Q27, CAL28, W29, S28 or F26-Z28",
        ),
        (
            {**NG_TICKET, "contract_code": ["Z26", "Z26", "F27", "CAL27", "Z26"]},
            NG_TEMPLATE,
            "contract_code row 4 is 'CAL27', expected months the index's schedule has a contract "
            "for; it has none for 2027-02",
        ),
        (
            {**NG_TICKET, "contract_code": ["Z26", "V26", "F27", "F27", "Z26"]},
            NG_TEMPLATE,
            "contract_code row 2 is 'V26', expected months the index's schedule has a contract "
            "for; it has none for 2026-10",
        ),
        (
            {name: values for name, values in NG_TICKET.items() if name != "contract_code"},
            {**NG_TEMPLATE, "contract_code": "G27"},
            "contract_code is 'G27', expected months the index's schedule has a contract for; "
            "it has none for 2027-02",
        ),
        (
            {**NG_TICKET, "quantity": [10, -4, 7.5, -12, 10]},
            NG_TEMPLATE,
            "lots of trade 'NG-003' at row 3 is 7.5, expected a whole number of lots",
        ),
        (
            {**NG_TICKET, "quantity": [10, 0, 7, -12, 10]},
            NG_TEMPLATE,
            "lots of trade 'NG-002' at row 2 is 0.0, expected a nonzero quantity",
        ),
    ],
)
def test_a_batch_that_cannot_be_resolved_says_why(
    ticket: Mapping[str, list[object]], template: Mapping[str, object], message: str
) -> None:
    assert refused(NG, ticket, template) == message


def test_a_lot_count_is_named_by_its_trades_row_though_a_strip_sits_before_it() -> None:
    message = refused(
        TOY,
        {
            "trade_id": ["S1", "S2"],
            "trade_date": ["2026-09-24", "2026-09-24"],
            "contract_code": ["Z26-F27", "F27"],
            "quantity": [3, 2.5],
            "fixed_price": [3.2, 3.3],
        },
        TOY_TEMPLATE,
    )
    assert message == "lots of trade 'S2' at row 2 is 2.5, expected a whole number of lots"


def test_two_lags_for_one_contract_are_refused_by_the_trade_and_the_contract() -> None:
    template = {k: v for k, v in TOY_TEMPLATE.items() if k != "payment_time_lag"}
    message = refused(
        TOY,
        {**NG_TICKET, "payment_time_lag": ["+2bd", "+3bd", "+2bd", "+2bd", "+2bd"]},
        template,
    )
    assert message == (
        "payment_date of trade 'NG-002' at row 2 is 2026-12-01, expected 2026-11-30, "
        "the one day Z26 pays"
    )


def test_the_index_must_be_a_futures_index_with_one_contract_per_month() -> None:
    daily = index(
        "daily",
        gas_daily_schedule(("c0",), dates("2026-01-01"), dates("2026-01-31")),
        NG.conventions,
        NG.specifications,
        None,
        UNITS,
    )
    assert refused(daily) == "index is a Gas Daily index, expected a futures index for a future"
    labelled = an_index(contracts=(("X26", "2026-10-28"), ("c1", "2026-11-25")))
    assert refused(labelled) == (
        "index schedule row 2 is 'c1', expected a contract code, a month letter and a two-digit "
        "year such as F26"
    )
    twice = an_index(
        contracts=(("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("z26", "2026-11-25"))
    )
    assert refused(twice) == (
        "index schedule rows 2 and 3 are 'Z26' and 'z26', both 2026-12, "
        "expected one contract per month"
    )


def test_the_conditions_are_the_definitions_own() -> None:
    conditional = {
        field.name: field.required_when for field in FUTURE.fields if field.required_when != NONE
    }
    assert conditional == {
        name: f"{fact} = {value.value}" for name, (fact, value) in CONDITIONS.items()
    }


def test_the_ticket_and_the_template_are_of_one_instrument_the_future() -> None:
    other = Instrument("swap", "Another instrument.", FUTURE.fields)
    with pytest.raises(ValueError) as refusal:
        trades(NG, a_ticket(NG_TICKET, other), a_template(NG_TEMPLATE), UNITS, WorkCounter())
    assert str(refusal.value) == "ticket is of instrument 'swap', expected the template's, 'future'"
    with pytest.raises(ValueError) as refusal:
        resolved(NG, a_ticket(NG_TICKET), a_template({"route": "cleared"}, other), WorkCounter())
    assert str(refusal.value) == (
        "template is of instrument 'swap', expected future, the one instrument whose trades are "
        "built"
    )


# --- any ticket of single months ------------------------------------------------------------


@settings(max_examples=50, deadline=None)
@given(
    rows=st.lists(
        st.tuples(
            st.sampled_from(["Z26", "z26", "F27", "f27"]),
            st.integers(min_value=-20, max_value=20).filter(lambda q: q != 0),
            st.floats(min_value=1.0, max_value=5.0, allow_nan=False),
        ),
        min_size=1,
        max_size=12,
    )
)
def test_any_ticket_of_single_months_resolves_row_by_row(
    rows: list[tuple[str, int, float]],
) -> None:
    n = len(rows)
    batch, counter = created(
        NG,
        {
            "trade_date": ["2026-09-24"] * n,
            "contract_code": [code for code, _, _ in rows],
            "quantity": [q for _, q, _ in rows],
            "fixed_price": [p for _, _, p in rows],
        },
    )
    terms = batch.resolved
    np.testing.assert_array_equal(terms.occurrence, np.arange(n))
    np.testing.assert_array_equal(
        terms.contract, [1 if code.upper() == "Z26" else 2 for code, _, _ in rows]
    )
    np.testing.assert_array_equal(terms.lots, [q for _, q, _ in rows])
    assert counter.freeze()["resolved_components"] == n
    assert batch.encoded.inputs.size == len({code.upper() for code, _, _ in rows})


# --- the creator on the sheet ---------------------------------------------------------------

ENTRY = {
    name: bridge.entry(name)
    for name in (
        "_CreateTrades",
        "_CreateTradeTemplate",
        "_CreateFuturesSchedule",
        "_CreateHolidayCalendar",
        "_CreateIndexConventions",
        "_CreateContractSpecifications",
        "_CreateIndex",
        "util_ReadHandle",
    )
}
CAUGHT: list[Trades] = []


def CatchTrades(trades: Handle[Trades]) -> float:
    CAUGHT.append(trades)
    return 0.0


register(CatchTrades, hidden=True)


def cells(*lines: list[object]) -> Cells:
    return Cells.from_rows(list(lines))


def row(*values: object) -> Cells:
    return cells(list(values))


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """The NG example's cells: the index, the template over its seven fields and the ticket's
    headers and five rows, with 24 September 2026 as 46289 and 25 September as 46290."""
    schedule = ENTRY["_CreateFuturesSchedule"](
        cells(["X26"], ["Z26"], ["F27"]), cells([46323.0], [46351.0], [46385.0]), bridge.MISSING
    )
    holidays = ENTRY["_CreateHolidayCalendar"](cells([46352.0], [46381.0]))
    conventions = ENTRY["_CreateIndexConventions"]("USD", "MMBTU", "USD", "ENERGY", "MMBTU")
    specs = ENTRY["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        row("NYMEX NG", 10000.0, "MMBTU", 0.0, 0.0),
    )
    ng = ENTRY["_CreateIndex"]("Henry Hub NYMEX", schedule, conventions, specs, holidays)
    template = ENTRY["_CreateTradeTemplate"](
        "future", row(*NG_TEMPLATE), row(*NG_TEMPLATE.values())
    )
    return {
        "index": ng,
        "holidays": holidays,
        "template": template,
        "headers": row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price"),
        "rows": cells(
            ["NG-001", 46289.0, "Z26", 10.0, 3.1],
            ["NG-002", 46289.0, "z26", -4.0, 3.15],
            ["NG-003", 46290.0, "F27", 7.0, 3.4],
            ["NG-004", 46290.0, "F27", -12.0, 3.35],
            ["NG-001", 46289.0, "Z26", 10.0, 3.1],
        ),
    }


def test_the_creator_publishes_the_batch_named_for_its_index(sheet: dict[str, Any]) -> None:
    handle = ENTRY["_CreateTrades"](
        sheet["index"], sheet["headers"], sheet["rows"], sheet["template"]
    )
    assert re.fullmatch(rf"{os.getpid()}:trades:Henry Hub NYMEX:\d+", str(handle))
    assert bridge.call("CatchTrades", [handle]) == 0.0
    batch = CAUGHT.pop()
    np.testing.assert_array_equal(batch.resolved.contract, [1, 1, 2, 2, 1])
    np.testing.assert_array_equal(batch.encoded.exposure, [160_000, -50_000])
    assert batch.resolved.labels == ("NG-001", "NG-002", "NG-003", "NG-004", "NG-001")


def test_the_creators_refusals_come_in_the_decided_order(sheet: dict[str, Any]) -> None:
    create = ENTRY["_CreateTrades"]
    ix, headers, rows, template = (
        sheet["index"],
        sheet["headers"],
        sheet["rows"],
        sheet["template"],
    )
    # The arguments alone, in signature order: the index, then the template, before any binding.
    assert create(sheet["holidays"], row("Quantity"), rows, "x:trade_template:9") == (
        f"#ERROR _CreateTrades: index is holiday calendar handle {sheet['holidays']!r}, "
        "expected index handle"
    )
    assert create(ix, row("Quantity"), rows, "x:trade_template:9") == (
        "#ERROR _CreateTrades: template is text 'x:trade_template:9' naming no live object, "
        "expected trade template handle"
    )
    assert create(ix, row("Quantity"), rows, sheet["holidays"]) == (
        f"#ERROR _CreateTrades: template is holiday calendar handle {sheet['holidays']!r}, "
        "expected trade template handle"
    )
    # Then the binding against the template's instrument: the width, the headers, the cells.
    assert create(ix, row("quantity"), rows, template) == (
        "#ERROR _CreateTrades: fields has 1 headers, expected 5, one per column of trade_rows"
    )
    assert str(
        create(
            ix,
            row("Trade_id", "trade_date", "contract_code", "quantity", "fixed_price"),
            rows,
            template,
        )
    ).startswith(
        "#ERROR _CreateTrades: fields cell (1, 1) is text 'Trade_id', expected a field of future: "
    )
    assert create(ix, headers, cells(["NG-001", 46289.0, "Z26", "ten", 3.1]), template) == (
        "#ERROR _CreateTrades: trade_rows cell (1, 4) is text 'ten', expected number"
    )
    # Then the library: the overlap, the completion, the codes, the kernel.
    assert create(
        ix, row(*NG_TICKET, "route"), cells(["a", 46289.0, "Z26", 1.0, 3.0, "cleared"]), template
    ) == (
        "#ERROR _CreateTrades: ValueError: route is supplied by the template and by the ticket, "
        "expected by one of them"
    )
    assert create(ix, headers, cells(["a", 46289.0, "G27", 1.0, 3.0]), template) == (
        "#ERROR _CreateTrades: ValueError: contract_code row 1 is 'G27', expected months the "
        "index's schedule has a contract for; it has none for 2027-02"
    )
    assert create(ix, headers, cells(["a", 46289.0, "Z26", 2.5, 3.0]), template) == (
        "#ERROR _CreateTrades: ValueError: lots of trade 'a' at row 1 is 2.5, "
        "expected a whole number of lots"
    )


def spilled(handle: object) -> list[list[object]]:
    kinds, slots, text = cast(
        tuple[NDArray[np.uint8], NDArray[np.float64], str], ENTRY["util_ReadHandle"](handle)
    )
    texts = iter(text.split("\0"))
    return [
        [
            next(texts) if kinds[r, c] == bridge.TEXT_CODE else slots[r, c]
            for c in range(kinds.shape[1])
        ]
        for r in range(kinds.shape[0])
    ]


def test_the_reader_spills_one_row_per_component_with_the_terms_and_the_encoding(
    sheet: dict[str, Any],
) -> None:
    handle = ENTRY["_CreateTrades"](
        sheet["index"], sheet["headers"], sheet["rows"], sheet["template"]
    )
    table = spilled(handle)
    assert table[0] == [
        "row",
        "trade_id",
        "trade_date",
        "contract_specification",
        "contract_code",
        "schedule_method",
        "route",
        "settlement_method",
        "clearing_house",
        "quantity",
        "quantity_unit",
        "quantity_per",
        "fixed_price",
        "quote_quantity",
        "coefficient",
        "offset",
    ]
    assert table[1] == [
        "int64",
        "str",
        "datetime64[D]",
        "str",
        "str",
        "str",
        "str",
        "str",
        "str",
        "float64",
        "str",
        "str",
        "float64",
        "float64",
        "float64",
        "float64",
    ]
    first = [
        1.0,
        "NG-001",
        46289.0,
        "NYMEX NG",
        "Z26",
        "lastday",
        "cleared",
        "physical",
        "CME Clearing",
        10.0,
        "LOT",
        "month",
        3.1,
        100_000.0,
        100_000.0,
        -310_000.0,
    ]
    assert table[2] == first
    assert table[3][4] == "Z26"  # the schedule's spelling, where the ticket typed z26
    assert table[6] == [5.0, *first[1:]]  # the repeated row, a trade of its own
    assert len(table) == 7


def test_the_spill_shows_the_batchs_facts_wherever_they_came_from(sheet: dict[str, Any]) -> None:
    # The route and the settlement from the ticket's columns, the template holding neither: the
    # spill is the one place both are read back.
    template = ENTRY["_CreateTradeTemplate"](
        "future",
        row("contract_specification", "quantity_unit", "quantity_per", "schedule_method"),
        row("NYMEX NG", "LOT", "month", "lastday"),
    )
    handle = ENTRY["_CreateTrades"](
        sheet["index"],
        row("trade_date", "contract_code", "quantity", "fixed_price", "route", "settlement_method"),
        cells(
            [46289.0, "Z26", 1.0, 3.0, "bilateral", "physical"],
            [46289.0, "F27", 2.0, 3.0, "bilateral", "physical"],
        ),
        template,
    )
    table = spilled(handle)
    assert table[0][:3] == ["row", "trade_date", "contract_specification"]
    assert "trade_id" not in table[0] and "clearing_house" not in table[0]
    assert [line[5] for line in table[2:]] == ["bilateral", "bilateral"]
    assert [line[6] for line in table[2:]] == ["physical", "physical"]
    assert [line[2] for line in table[2:]] == ["NYMEX NG", "NYMEX NG"]


def test_a_financial_batchs_spill_carries_its_payment_terms(sheet: dict[str, Any]) -> None:
    template = ENTRY["_CreateTradeTemplate"](
        "future",
        row(*TOY_TEMPLATE),
        row(
            *[
                sheet["holidays"] if name == "payment_holiday_calendar" else value
                for name, value in {**TOY_TEMPLATE, "contract_specification": "NYMEX NG"}.items()
            ]
        ),
    )
    handle = ENTRY["_CreateTrades"](
        sheet["index"],
        row("trade_date", "contract_code", "quantity", "fixed_price", "broker"),
        cells([46289.0, "Z26-F27", 3.0, 3.2, "ION"]),
        template,
    )
    table = spilled(handle)
    assert table[0] == [
        "row",
        "trade_date",
        "contract_specification",
        "contract_code",
        "schedule_method",
        "route",
        "settlement_method",
        "clearing_house",
        "broker",
        "quantity",
        "quantity_unit",
        "quantity_per",
        "fixed_price",
        "payment_time_lag",
        "payment_date",
        "quote_quantity",
        "coefficient",
        "offset",
    ]
    assert [line[0] for line in table[2:]] == [1.0, 1.0]
    assert [line[3] for line in table[2:]] == ["Z26", "F27"]
    assert [line[8] for line in table[2:]] == ["ION", "ION"]
    assert [line[13] for line in table[2:]] == ["+2bd", "+2bd"]  # the lag beside the day it gave
    assert [line[14] for line in table[2:]] == [46356.0, 46387.0]  # 30 Nov and 31 Dec 2026
