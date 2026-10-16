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
from goosedove.index_definitions.holiday_calendar import (
    HolidayCalendar,
    combine_holiday_calendars,
    holiday_calendar,
)
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT, NONE, FieldType, Instrument
from goosedove.instruments.fields import FieldValues
from goosedove.trades.resolution import CONDITIONS, PERIOD_FIELDS, Trades, resolved, trades
from goosedove.trades.template import TradeTemplate, trade_template
from goosedove.trades.terms import BASES, METHODS, QuantityPer, Route, ScheduleMethod, Settlement


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
    measure: tuple[str, str] = ("ENERGY", "MMBTU"),
    reporting_lot: str | None = "",
) -> Index:
    # The first lot given is the reporting lot unless another name is given; None makes an
    # index without one.
    codes = tuple(code for code, _ in contracts)
    schedule = futures_schedule(codes, dates(*(expiry for _, expiry in contracts)), None)
    names = tuple(name for name, _, _ in lots)
    return index(
        name,
        f"{name} index",
        schedule,
        index_conventions("USD", measure[1], "USD", measure[0], measure[1], UNITS),
        contract_specifications(
            names,
            np.array([size for _, size, _ in lots]),
            tuple(unit for _, _, unit in lots),
            np.zeros(len(lots)),
            np.zeros(len(lots)),
            UNITS,
        ),
        holiday_calendar(dates(*holidays)),
        names[0] if reporting_lot == "" else reporting_lot,
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
    "quantity_unit": "NYMEX NG",
    "quantity_per": "month",
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "physical",
    "clearing_house": "CME Clearing",
}
TOY_TEMPLATE: dict[str, object] = {
    **NG_TEMPLATE,
    "quantity_unit": "TOY",
    "settlement_method": "financial",
    "clearing_house": "TEST_CLEARER",
    "payment_time_lag": "+2bd",
    "payment_holiday_calendar": PAYMENT_CALENDAR,
}
NG_TICKET: dict[str, list[object]] = {
    "trade_id": [1001, 1002, 1003, 1004, 1001],
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


def a_ticket(
    columns: Mapping[str, list[object]], definition: Instrument = FIXED_FLOAT
) -> FieldValues:
    """A ticket as the seam hands it over: each column typed by its field and, since #172, a None
    among a column's values a cell the row left unsupplied, the column then holding the other
    rows' values with a mask saying which rows supplied one."""
    rows = len(next(iter(columns.values())))
    supplied: dict[str, NDArray[np.bool_]] = {}
    typed_columns: dict[str, object] = {}
    for name, values in columns.items():
        present = [value is not None for value in values]
        if not all(present):
            supplied[name] = np.array(present)
        typed_columns[name] = typed(definition, name, [v for v in values if v is not None])
    return FieldValues(definition, rows, tuple(columns), typed_columns, supplied)


def a_template(fields: Mapping[str, object], definition: Instrument = FIXED_FLOAT) -> TradeTemplate:
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
    assert terms.instrument is FIXED_FLOAT and terms.index is NG and terms.schedule is NG.schedule
    np.testing.assert_array_equal(terms.specification, [0] * 5)
    assert (terms.route, terms.settlement) == (Route.CLEARED, Settlement.PHYSICAL)
    np.testing.assert_array_equal(
        terms.schedule_method, [METHODS.index(ScheduleMethod.LASTDAY)] * 5
    )
    np.testing.assert_array_equal(terms.quantity_per, [BASES.index(QuantityPer.MONTH)] * 5)
    np.testing.assert_array_equal(terms.trade_ids, [1001, 1002, 1003, 1004, 1001])
    assert terms.clearing_house == ("CME Clearing",) * 5  # the template's, for every row
    assert terms.broker is None
    np.testing.assert_array_equal(
        terms.trade_dates,
        dates("2026-09-24", "2026-09-24", "2026-09-25", "2026-09-25", "2026-09-24"),
    )
    np.testing.assert_array_equal(terms.occurrence, [0, 1, 2, 3, 4])
    np.testing.assert_array_equal(terms.contract, [1, 1, 2, 2, 1])  # Z26 and F27 by row
    np.testing.assert_array_equal(terms.quantity, [10, -4, 7, -12, 10])
    np.testing.assert_array_equal(terms.covered_days, [31, 31, 31, 31, 31])  # December, January
    np.testing.assert_array_equal(terms.component_quantity, terms.quantity)  # month: as entered
    np.testing.assert_array_equal(  # each component covers its whole month
        terms.start_date,
        dates("2026-12-01", "2026-12-01", "2027-01-01", "2027-01-01", "2026-12-01"),
    )
    np.testing.assert_array_equal(
        terms.end_date,
        dates("2026-12-31", "2026-12-31", "2027-01-31", "2027-01-31", "2026-12-31"),
    )
    np.testing.assert_array_equal(terms.fixed_price, [3.1, 3.15, 3.4, 3.35, 3.1])
    assert terms.payment is None
    assert batch.encoded.terms is terms
    np.testing.assert_array_equal(
        batch.encoded.quote_quantity, [100_000, -40_000, 70_000, -120_000, 100_000]
    )
    np.testing.assert_array_equal(
        batch.encoded.offset, [-310_000, 126_000, -238_000, 402_000, -310_000]
    )
    np.testing.assert_array_equal(batch.encoded.group_contract, [1, 2])
    np.testing.assert_array_equal(batch.encoded.slot_exposure, [160_000, -50_000])
    np.testing.assert_array_equal(batch.encoded.slot_date, dates("2026-11-25", "2026-12-29"))
    assert counter.freeze().as_dict() == {
        "encoded_components": 5,
        "encoded_groups": 2,
        "encoded_observations": 5,
        "encoded_slots": 2,
        "reserved_fee_components": 5,
        "resolved_components": 5,
        "resolved_occurrences": 5,
        "schedule_codes_read": 3,
        "ticket_codes_read": 2,  # Z26 and F27, each distinct text once, since #172
    }
    # Since #172 the batch keeps what each row entered for its code, apart from the contracts.
    np.testing.assert_array_equal(batch.code_entered, [True] * 5)
    assert batch.entered_codes == ("Z26", "Z26", "F27", "F27", "Z26")
    assert not batch.code_entered.flags.writeable


def test_codes_resolve_in_either_case_against_a_schedule_in_either_case() -> None:
    mixed = an_index(
        contracts=(("x26", "2026-10-28"), ("Z26", "2026-11-25"), ("f27", "2026-12-29"))
    )
    batch, _ = created(mixed, {**NG_TICKET, "contract_code": ["z26", "Z26", "F27", "f27", "z26"]})
    np.testing.assert_array_equal(batch.resolved.contract, [1, 1, 2, 2, 1])


def test_a_strip_makes_one_component_per_month_on_its_one_occurrence() -> None:
    ticket: dict[str, list[object]] = {
        "trade_id": [1, 2],
        "trade_date": ["2026-09-24", "2026-09-24"],
        "contract_code": ["Z26-F27", "f27"],
        "quantity": [3, -1],
        "fixed_price": [3.2, 3.3],
    }
    batch, counter = created(TOY, ticket, TOY_TEMPLATE)
    terms = batch.resolved
    np.testing.assert_array_equal(terms.occurrence, [0, 0, 1])
    np.testing.assert_array_equal(terms.contract, [1, 2, 2])
    np.testing.assert_array_equal(terms.quantity, [3, 3, -1])  # the strip's quantity in every month
    np.testing.assert_array_equal(terms.fixed_price, [3.2, 3.2, 3.3])
    assert terms.payment is not None
    np.testing.assert_array_equal(
        terms.payment.date, dates("2026-11-30", "2026-12-31", "2026-12-31")
    )  # two business days after each expiry, the page's dates, 26 November closed
    assert terms.payment.lag == ("+2bd", "+2bd")  # the rule as written, per occurrence
    assert terms.payment.calendar == (PAYMENT_CALENDAR, PAYMENT_CALENDAR)
    assert terms.named(1) == "trade 1 at row 1"
    assert counter.freeze()["resolved_components"] == 3
    assert counter.freeze()["resolved_occurrences"] == 2


def test_a_whole_year_strip_resolves_twelve_months_against_a_long_schedule() -> None:
    months = np.arange("2026-10", "2028-01", dtype="datetime64[M]")
    letters = "FGHJKMNQUVXZ"
    # Each contract expires on the last business day on or before the 25th of its month, so that
    # every expiry is a day the market is open, which the encoding requires of an observation.
    contracts = tuple(
        (
            f"{letters[int(m.astype(int)) % 12]}{str(m)[2:4]}",
            str(np.busday_offset(np.datetime64(m, "D") + np.timedelta64(24, "D"), 0, "backward")),
        )
        for m in months
    )
    long = an_index(contracts=contracts)
    batch, _ = created(
        long,
        {
            "trade_id": [25],
            "trade_date": ["2026-09-24"],
            "contract_code": ["cal27"],
            "quantity": [2],
            "fixed_price": [3.0],
        },
    )
    assert long.schedule.codes[3] == "F27"
    np.testing.assert_array_equal(batch.resolved.contract, np.arange(3, 15))
    np.testing.assert_array_equal(batch.resolved.occurrence, np.zeros(12, dtype=np.intp))
    np.testing.assert_array_equal(batch.encoded.quote_quantity, np.full(12, 20_000.0))
    assert batch.encoded.slot_exposure.size == 12  # one slot per month, on its expiry


def test_a_templates_field_applies_to_every_row_and_a_tickets_varies() -> None:
    batch, _ = created(
        NG,
        {"trade_id": [1, 2, 3], "broker": ["ION", "TP", "ION"]},
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
    np.testing.assert_array_equal(terms.quantity, [2, 2, 2])
    assert terms.broker == ("ION", "TP", "ION")
    np.testing.assert_array_equal(terms.brokered, [True, True, True])
    np.testing.assert_array_equal(terms.trade_ids, [1, 2, 3])


def test_a_broker_of_none_in_any_case_is_a_screen_trade_and_the_text_stands() -> None:
    # Since #188, reserve-fee-applicability.md: the terms say which rows name a broker, the text
    # none in any case naming none, and keep every text as typed for the readback; a batch without
    # the field names none.
    template = {
        **NG_TEMPLATE,
        "trade_date": day("2026-09-24"),
        "contract_code": "z26",
        "quantity": 2.0,
        "fixed_price": 3.0,
    }
    batch, _ = created(NG, {"trade_id": [1, 2, 3], "broker": ["ION", "None", "none"]}, template)
    assert batch.resolved.broker == ("ION", "None", "none")
    np.testing.assert_array_equal(batch.resolved.brokered, [True, False, False])
    unbrokered, _ = created(NG, {"trade_id": [1, 2, 3]}, template)
    assert unbrokered.resolved.broker is None
    np.testing.assert_array_equal(unbrokered.resolved.brokered, [False, False, False])


def test_a_batch_field_in_the_ticket_is_taken_when_every_row_agrees() -> None:
    template = {name: value for name, value in NG_TEMPLATE.items() if name != "route"}
    batch, _ = created(NG, {**NG_TICKET, "route": ["cleared"] * 5}, template)
    assert batch.resolved.route is Route.CLEARED
    without_labels, _ = created(NG, {k: v for k, v in NG_TICKET.items() if k != "trade_id"})
    assert without_labels.resolved.trade_ids is None
    assert without_labels.resolved.named(4) == "trade at row 5"


# --- payment days ---------------------------------------------------------------------------


def one_payment_day(expiry: str, holidays: tuple[str, ...], lag: str) -> np.datetime64:
    """The payment day of one Z26 lot on an index whose Z26 expires that day, under a payment
    calendar of those holidays and that lag."""
    ix = an_index(
        "pay",
        (("X26", "2026-10-28"), ("Z26", expiry)),
        holidays=(),  # the market is open on the expiry; the payment calendar may not be
        lots=(("TOY", 10_000.0, "MMBTU"),),
    )
    batch, _ = created(
        ix,
        {
            "trade_id": [16],
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


def payment_refusal(lag: str, in_ticket: bool = False) -> str:
    """The refusal of one Z26 lot, its expiry 25 November 2026, under that lag on a payment calendar
    closing nothing, the lag in the template or, when asked, in the ticket's own column."""
    ix = an_index(
        "pay",
        (("X26", "2026-10-28"), ("Z26", "2026-11-25")),
        holidays=(),
        lots=(("TOY", 10_000.0, "MMBTU"),),
    )
    ticket: dict[str, list[object]] = {
        "trade_id": [16],
        "trade_date": ["2026-09-24"],
        "contract_code": ["Z26"],
        "quantity": [1],
        "fixed_price": [3.0],
    }
    template = {
        **TOY_TEMPLATE,
        "payment_time_lag": lag,
        "payment_holiday_calendar": holiday_calendar(dates()),
    }
    if in_ticket:
        return refused(
            ix,
            {**ticket, "payment_time_lag": [lag]},
            {k: v for k, v in template.items() if k != "payment_time_lag"},
        )
    return refused(ix, ticket, template)


def test_a_lag_is_held_to_the_sheets_calendar_and_its_day_to_the_sheets_last_day() -> None:
    # Representability and no term of business: a day outside the sheet's calendar could reach no
    # cell, so the rule that would pay there is refused naming the rule, the anchor and the day,
    # with the row when the ticket supplied it and the instruction when the rule has more than
    # one, since #181; the longest lag that still pays on the last day is taken: from Z26's 25
    # November 2026 that is 2,080,082 business days on an open calendar. A count of more than
    # seven significant digits is refused by its digits before any day is counted, so no number
    # overflows the arithmetic unnamed.
    assert payment_refusal("+2100000bd") == (
        "payment_time_lag is '+2100000bd', counted from 2026-11-25 to 10076-05-06, expected a "
        "payment day within the sheet's calendar, 1900-03-01 to 9999-12-31"
    )
    assert payment_refusal("+2100000bd", in_ticket=True) == (
        "payment_time_lag row 1 is '+2100000bd', counted from 2026-11-25 to 10076-05-06, expected "
        "a payment day within the sheet's calendar, 1900-03-01 to 9999-12-31"
    )
    assert payment_refusal("+99999999999999999999bd", in_ticket=True) == (
        "payment_time_lag row 1 has a count of 20 digits, expected at most 7; the sheet's "
        "calendar runs 1900-03-01 to 9999-12-31"
    )
    long_lag = "+" + "9" * 4301 + "bd"  # fits a cell, and would fail Python's own conversion
    bound = (
        "has a count of 4301 digits, expected at most 7; the sheet's calendar runs 1900-03-01 to "
        "9999-12-31"
    )
    assert payment_refusal(long_lag) == f"payment_time_lag {bound}"
    assert payment_refusal(long_lag, in_ticket=True) == f"payment_time_lag row 1 {bound}"
    longest = int(np.busday_count(day("2026-11-25"), day("9999-12-31")))
    assert longest == 2_080_082
    assert one_payment_day("2026-11-25", (), f"+{longest}bd") == day("9999-12-31")
    assert payment_refusal(f"+{longest + 1}bd") == (
        "payment_time_lag is '+2080083bd', counted from 2026-11-25 to 10000-01-03, expected a "
        "payment day within the sheet's calendar, 1900-03-01 to 9999-12-31"
    )
    assert payment_refusal("+9999999cd-9999999cd", in_ticket=True) == (
        "payment_time_lag row 1 is '+9999999cd-9999999cd', counted from 2026-11-25 to 29405-12-20 "
        "at instruction 1, '+9999999cd', expected a payment day within the sheet's calendar, "
        "1900-03-01 to 9999-12-31"
    )


def test_payment_calendars_and_lags_in_the_ticket_apply_row_by_row() -> None:
    # Each row's calendar closes a day that would move the other row's payment and not its
    # own: the first closes 26 November, the day after Z26 expires, the second 31 December,
    # two business days after F27 does. Row a, Z26 at +1bd on the first, pays 27 November;
    # row b, F27 at +3bd on the second, pays 4 January. Either calendar applied to both rows
    # would move one of them, row a to the 26th or row b to New Year's Day.
    after_z26 = holiday_calendar(dates("2026-11-26"))
    before_new_year = holiday_calendar(dates("2026-12-31"))
    template = {
        name: value
        for name, value in TOY_TEMPLATE.items()
        if name not in ("payment_time_lag", "payment_holiday_calendar")
    }
    batch, _ = created(
        TOY,
        {
            "trade_id": [1, 2],
            "trade_date": ["2026-09-24", "2026-09-24"],
            "contract_code": ["Z26", "F27"],
            "quantity": [1, 1],
            "fixed_price": [3.0, 3.0],
            "payment_time_lag": ["+1bd", "+3bd"],
            "payment_holiday_calendar": [after_z26, before_new_year],
        },
        template,
    )
    payment = batch.resolved.payment
    assert payment is not None
    np.testing.assert_array_equal(payment.date, dates("2026-11-27", "2027-01-04"))
    assert payment.lag == ("+1bd", "+3bd")
    assert payment.calendar == (after_z26, before_new_year)


# --- the penultimate method: the pen day observed, the payment counted from it ---------------
# penultimate-trades.md: the pen observes the business day before the underlying's expiry on the
# index's pricing calendar and pays its lag after that day on the payment calendar. The exchange
# cases are the page's, each checked against ICE's published expiry tables: PHH Z26, M27 and N27
# on the NG index, M27 the month Memorial Day closes the last business day before the contract
# month, and ICE WTI T F27 on a CL index in barrels.

CLEARING = holiday_calendar(dates("2026-12-25", "2026-12-28", "2027-01-01", "2027-05-31"))
PEN_TEMPLATE: dict[str, object] = {
    **NG_TEMPLATE,
    "quantity_unit": "ICE PHH",
    "schedule_method": "penultimate",
    "settlement_method": "financial",
    "clearing_house": "ICE Clear Europe",
    "payment_time_lag": "+1bd",
    "payment_holiday_calendar": CLEARING,
}
NG_2026 = an_index(
    contracts=(("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29")),
    lots=(("NYMEX NG", 10_000.0, "MMBTU"), ("ICE PHH", 2_500.0, "MMBTU")),
)
NG_2027 = an_index(
    contracts=(("M27", "2027-05-26"), ("N27", "2027-06-28"), ("Q27", "2027-07-28")),
    holidays=("2027-05-31", "2027-07-05"),
    lots=(("NYMEX NG", 10_000.0, "MMBTU"), ("ICE PHH", 2_500.0, "MMBTU")),
)
CL_2026 = an_index(
    "WTI NYMEX",
    (("Z26", "2026-11-20"), ("F27", "2026-12-21"), ("G27", "2027-01-20")),
    ("2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18"),
    (("NYMEX CL", 1_000.0, "BBL"), ("ICE WTI T", 1_000.0, "BBL")),
    ("VOLUME", "BBL"),
)


def pen_days(
    ix: Index, codes: list[str], template: Mapping[str, object] = PEN_TEMPLATE
) -> tuple[list[str], list[str]]:
    """One lot of each code under the template: each component's observation day and payment day
    as the batch retains them."""
    ticket: dict[str, list[object]] = {
        "trade_id": [i + 1 for i in range(len(codes))],
        "trade_date": ["2026-09-24"] * len(codes),
        "contract_code": list(codes),
        "quantity": [1] * len(codes),
        "fixed_price": [3.0] * len(codes),
    }
    batch, _ = created(ix, ticket, template)
    assert batch.resolved.payment is not None
    observed = [str(d) for d in batch.encoded.observations.date]
    return observed, [str(d) for d in batch.resolved.payment.date]


def test_the_exchange_cases_of_the_page_observe_and_pay_on_its_days() -> None:
    assert pen_days(NG_2026, ["Z26"]) == (["2026-11-24"], ["2026-11-25"])
    assert pen_days(NG_2027, ["M27", "N27"]) == (
        ["2027-05-25", "2027-06-25"],
        ["2027-05-26", "2027-06-28"],
    )
    wti = {**PEN_TEMPLATE, "quantity_unit": "ICE WTI T"}
    assert pen_days(CL_2026, ["F27"], wti) == (["2026-12-18"], ["2026-12-21"])


def test_a_strip_under_the_pen_observes_each_month_on_its_own_pen_day() -> None:
    assert pen_days(NG_2027, ["M27-N27"]) == (
        ["2027-05-25", "2027-06-25"],
        ["2027-05-26", "2027-06-28"],
    )


def test_each_calendar_serves_its_own_operation() -> None:
    # A Friday closed on the pricing calendar alone: the pen steps over it to Thursday, and the
    # payment calendar, open that Friday, pays on it.
    friday_closed = an_index(
        contracts=(("M27", "2027-05-26"), ("N27", "2027-06-28")),
        holidays=("2027-06-25",),
        lots=(("ICE PHH", 2_500.0, "MMBTU"),),
    )
    open_calendar = holiday_calendar(dates())
    assert pen_days(
        friday_closed, ["N27"], {**PEN_TEMPLATE, "payment_holiday_calendar": open_calendar}
    ) == (["2027-06-24"], ["2027-06-25"])
    # A Monday closed on the payment calendar alone: the pen day is the Friday as before, and
    # +1bd pays Tuesday.
    monday_closed = holiday_calendar(dates("2027-06-28"))
    assert pen_days(
        NG_2027, ["N27"], {**PEN_TEMPLATE, "payment_holiday_calendar": monday_closed}
    ) == (["2027-06-25"], ["2027-06-29"])
    # The pen day itself closed on the payment calendar: rolled back to Thursday first, then one
    # business day on, Monday, the first clearing day after the pen day and not the Tuesday a
    # second roll would give.
    friday_closed_for_payment = holiday_calendar(dates("2027-06-25"))
    assert pen_days(
        NG_2027, ["N27"], {**PEN_TEMPLATE, "payment_holiday_calendar": friday_closed_for_payment}
    ) == (["2027-06-25"], ["2027-06-28"])


def test_lastday_on_the_same_expiries_still_pays_from_the_expiry() -> None:
    lastday = {**PEN_TEMPLATE, "schedule_method": "lastday"}
    assert pen_days(NG_2027, ["M27", "N27"], lastday) == (
        ["2027-05-26", "2027-06-28"],
        ["2027-05-27", "2027-06-29"],
    )
    assert pen_days(NG_2026, ["Z26"], lastday) == (["2026-11-25"], ["2026-11-26"])


def test_an_expiry_the_market_closes_is_refused_by_its_contract_under_the_pen() -> None:
    thanksgiving = an_index(
        contracts=(("X26", "2026-10-28"), ("Z26", "2026-11-26")),
        holidays=("2026-11-26",),
        lots=(("ICE PHH", 2_500.0, "MMBTU"),),
    )
    assert refused(
        thanksgiving,
        {
            "trade_id": [16],
            "trade_date": ["2026-09-24"],
            "contract_code": ["Z26"],
            "quantity": [1],
            "fixed_price": [3.0],
        },
        PEN_TEMPLATE,
    ) == (
        "Z26 expires on 2026-11-26, a day the index's market is closed; the penultimate method "
        "takes the business day before an expiry the market prices"
    )


# --- the last3day method: three observations, one payment after the last ----------------------
# last3day-trades.md: each component observes its contract's expiry and the two business days
# before it, a third each, and pays its lag after the last of them. The synthetic index: X26
# expiring 30 November 2026, Z26 7 December, F27 7 January 2027, the market closed on 4 December,
# one specification UNIT of one MMBTU; the payment calendar open every weekday.

SYN = an_index(
    "SYN",
    contracts=(("X26", "2026-11-30"), ("Z26", "2026-12-07"), ("F27", "2027-01-07")),
    holidays=("2026-12-04",),
    lots=(("UNIT", 1.0, "MMBTU"),),
)
WEEKDAYS = holiday_calendar(dates("2026-01-01"))
L3D_TEMPLATE: dict[str, object] = {
    **NG_TEMPLATE,
    "quantity_unit": "UNIT",
    "schedule_method": "last3day",
    "settlement_method": "financial",
    "clearing_house": "Prototype Clearing",
    "payment_time_lag": "+2bd",
    "payment_holiday_calendar": WEEKDAYS,
}
L3D_TICKET: dict[str, list[object]] = {
    "trade_id": [1, 2],
    "trade_date": ["2026-11-20", "2026-11-20"],
    "contract_code": ["Z26", "Z26"],
    "quantity": [60, -30],
    "fixed_price": [70.0, 72.0],
}


def l3d_days(
    ticket: Mapping[str, list[object]] = L3D_TICKET,
    template: Mapping[str, object] = L3D_TEMPLATE,
    ix: Index = SYN,
) -> tuple[list[int], list[str], list[float], list[str]]:
    """The batch's observations as it retains them, the component and the day of each and its
    weight, and each component's payment day."""
    batch, _ = created(ix, ticket, template)
    assert batch.resolved.payment is not None
    obs = batch.encoded.observations
    return (
        [int(c) for c in obs.component],
        [str(d) for d in obs.date],
        [float(w) for w in obs.weight],
        [str(d) for d in batch.resolved.payment.date],
    )


def test_last3day_observes_the_expiry_and_the_two_days_before_and_pays_after_the_last() -> None:
    components, days, weights, pays = l3d_days()
    assert components == [0, 0, 0, 1, 1, 1]
    assert days == ["2026-12-02", "2026-12-03", "2026-12-07"] * 2
    assert weights == pytest.approx([1 / 3] * 6)
    assert pays == ["2026-12-09", "2026-12-09"]


def test_a_payment_calendar_closed_on_the_eighth_moves_the_payment_and_not_the_days() -> None:
    closed_eighth = {
        **L3D_TEMPLATE,
        "payment_holiday_calendar": holiday_calendar(dates("2026-12-08")),
    }
    components, days, weights, pays = l3d_days(template=closed_eighth)
    assert (components, days, weights) == l3d_days()[:3]
    assert pays == ["2026-12-10", "2026-12-10"]


def test_a_last3day_strip_observes_each_month_thrice_and_pays_once_per_month() -> None:
    strip: dict[str, list[object]] = {
        "trade_id": [19],
        "trade_date": ["2026-11-20"],
        "contract_code": ["Z26-F27"],
        "quantity": [3],
        "fixed_price": [70.0],
    }
    components, days, weights, pays = l3d_days(strip)
    assert components == [0, 0, 0, 1, 1, 1]
    assert days == [
        "2026-12-02",
        "2026-12-03",
        "2026-12-07",
        "2027-01-05",
        "2027-01-06",
        "2027-01-07",
    ]
    assert weights == pytest.approx([1 / 3] * 6)
    assert pays == ["2026-12-09", "2027-01-11"]
    twice = {name: values * 2 for name, values in strip.items()}
    assert l3d_days(twice)[3] == ["2026-12-09", "2027-01-11"] * 2
    batch, _ = created(SYN, twice, L3D_TEMPLATE)
    np.testing.assert_array_equal(batch.encoded.offset, [-210.0] * 4)
    np.testing.assert_allclose(batch.encoded.slot_exposure, [2.0] * 6)


def test_an_expiry_the_market_closes_is_refused_by_its_contract_under_last3day() -> None:
    closed = an_index(
        "x",
        contracts=(("X26", "2026-11-30"), ("Z26", "2026-12-04"), ("F27", "2027-01-07")),
        holidays=("2026-12-04",),
        lots=(("UNIT", 1.0, "MMBTU"),),
    )
    assert refused(closed, L3D_TICKET, L3D_TEMPLATE) == (
        "Z26 expires on 2026-12-04, a day the index's market is closed; the last3day method takes "
        "an expiry the market prices and the two business days before it"
    )


def test_an_observation_crossing_the_preceding_contract_is_refused_when_the_batch_is_made() -> None:
    crossing = an_index(
        "x",
        contracts=(("X26", "2026-12-03"), ("Z26", "2026-12-07"), ("F27", "2027-01-07")),
        holidays=("2026-12-04",),
        lots=(("UNIT", 1.0, "MMBTU"),),
    )
    assert refused(crossing, L3D_TICKET, L3D_TEMPLATE) == (
        "trade 1 at row 1 observes Z26 on 2026-12-02, a day X26 prices; the last3day method "
        "takes the contract's own days, and a futures history holds no settle of Z26 for a day "
        "X26 prices"
    )


def test_a_physical_last3day_future_is_refused_when_the_batch_is_made() -> None:
    physical = {
        name: value
        for name, value in L3D_TEMPLATE.items()
        if name not in ("payment_time_lag", "payment_holiday_calendar")
    }
    assert refused(SYN, L3D_TICKET, {**physical, "settlement_method": "physical"}) == (
        "settlement_method is 'physical', expected 'financial' with the last3day method of "
        "trade 1 at row 1; a last3day future is cash settled on the average of its last three "
        "pricing days"
    )


# --- the asian method: every pricing day of the month, one payment after the last -------------
# asian-trades.md: each component observes every Monday to Friday of its contract's calendar
# month the index's market is open on, an equal share each, and pays its lag after the last of
# them. The synthetic ethane index: X26 expiring 30 November 2026, Z26 31 December, F27 29
# January 2027 and G27 26 February, the market closed on 25 December and 1 January, one
# specification GAL of one gallon; the payment calendar closed on 1 January.

ETHANE_HOLIDAYS = ("2026-12-25", "2027-01-01")
ETHANE = an_index(
    "ETHANE",
    (("X26", "2026-11-30"), ("Z26", "2026-12-31"), ("F27", "2027-01-29"), ("G27", "2027-02-26")),
    ETHANE_HOLIDAYS,
    (("GAL", 1.0, "GAL"),),
    ("VOLUME", "GAL"),
)
PAY_JAN_1 = holiday_calendar(dates("2027-01-01"))
ASIAN_TEMPLATE: dict[str, object] = {
    **NG_TEMPLATE,
    "quantity_unit": "GAL",
    "schedule_method": "asian",
    "settlement_method": "financial",
    "clearing_house": "Prototype Clearing",
    "payment_time_lag": "+2bd",
    "payment_holiday_calendar": PAY_JAN_1,
}
ASIAN_TICKET: dict[str, list[object]] = {
    "trade_id": [1, 2],
    "trade_date": ["2026-11-20", "2026-11-20"],
    "contract_code": ["Z26", "Z26"],
    "quantity": [4_400, -2_200],
    "fixed_price": [0.25, 0.26],
}


def ethane_days(first: str, after: str) -> list[str]:
    """Every Monday to Friday from the first day to the day before the next, less the ethane
    market's holidays: the fixture's own arithmetic."""
    days = np.arange(np.datetime64(first), np.datetime64(after))
    return [str(d) for d in days[np.is_busday(days, holidays=dates(*ETHANE_HOLIDAYS))]]


DECEMBER_DAYS = ethane_days("2026-12-01", "2027-01-01")
JANUARY_DAYS = ethane_days("2027-01-01", "2027-02-01")


def asian_days(
    ticket: Mapping[str, list[object]] = ASIAN_TICKET,
    template: Mapping[str, object] = ASIAN_TEMPLATE,
    ix: Index = ETHANE,
) -> tuple[list[int], list[str], list[float], list[str]]:
    """The batch's observations as it retains them, the component and the day of each and its
    weight, and each component's payment day."""
    batch, _ = created(ix, ticket, template)
    assert batch.resolved.payment is not None
    obs = batch.encoded.observations
    return (
        [int(c) for c in obs.component],
        [str(d) for d in obs.date],
        [float(w) for w in obs.weight],
        [str(d) for d in batch.resolved.payment.date],
    )


def test_asian_observes_the_months_pricing_days_and_pays_after_the_last() -> None:
    components, days, weights, pays = asian_days()
    assert len(DECEMBER_DAYS) == 22
    assert components == [0] * 22 + [1] * 22
    assert days == DECEMBER_DAYS * 2
    assert weights == pytest.approx([1 / 22] * 44)
    assert pays == ["2027-01-05", "2027-01-05"]


def test_a_payment_calendar_closed_on_the_fourth_moves_the_payment_and_not_the_days() -> None:
    closed_fourth = {
        **ASIAN_TEMPLATE,
        "payment_holiday_calendar": holiday_calendar(dates("2027-01-01", "2027-01-04")),
    }
    components, days, weights, pays = asian_days(template=closed_fourth)
    assert (components, days, weights) == asian_days()[:3]
    assert pays == ["2027-01-06", "2027-01-06"]


def test_an_asian_strip_observes_each_month_on_its_own_days_and_pays_once_per_month() -> None:
    strip: dict[str, list[object]] = {
        "trade_id": [19],
        "trade_date": ["2026-11-20"],
        "contract_code": ["Z26-F27"],
        "quantity": [2_200],
        "fixed_price": [0.25],
    }
    components, days, weights, pays = asian_days(strip)
    assert len(JANUARY_DAYS) == 20
    assert components == [0] * 22 + [1] * 20
    assert days == DECEMBER_DAYS + JANUARY_DAYS
    assert weights == pytest.approx([1 / 22] * 22 + [1 / 20] * 20)
    assert pays == ["2027-01-05", "2027-02-02"]
    batch, _ = created(ETHANE, strip, ASIAN_TEMPLATE)
    np.testing.assert_allclose(batch.encoded.offset, [-550.0, -550.0])
    np.testing.assert_allclose(batch.encoded.slot_exposure, [100.0] * 22 + [110.0] * 20)
    twice = {name: values * 2 for name, values in strip.items()}
    assert asian_days(twice)[3] == ["2027-01-05", "2027-02-02"] * 2
    batch, _ = created(ETHANE, twice, ASIAN_TEMPLATE)
    np.testing.assert_allclose(batch.encoded.slot_exposure, [200.0] * 22 + [220.0] * 20)


def test_a_month_without_a_pricing_day_is_refused_by_its_contract_when_the_batch_is_made() -> None:
    closed = an_index(
        "x",
        (("F27", "2027-01-29"), ("G27", "2027-02-26"), ("H27", "2027-03-31")),
        tuple(ethane_days("2027-02-01", "2027-03-01")),
        (("GAL", 1.0, "GAL"),),
        ("VOLUME", "GAL"),
    )
    assert refused(closed, {**ASIAN_TICKET, "contract_code": ["G27", "G27"]}, ASIAN_TEMPLATE) == (
        "G27 of trade 1 at row 1 has no pricing day from 2027-02-01 to 2027-02-28, expected a "
        "Monday to Friday of the days it covers the index's market is open on; the asian method "
        "averages the pricing days a component covers"
    )


def test_an_asian_month_another_contract_prices_takes_the_days_contracts_when_made() -> None:
    # NYMEX NG's Z26 expires on 25 November: F27 prices December's days through its own expiry
    # on the 29th and G27 the last two, so the asian ticket on that schedule is made, its 22
    # days referencing F27 and then G27 while Z26 keeps the fixed leg and the payment;
    # calendar-driven-asian-references.md.
    ng_like = an_index(
        "x",
        (
            ("X26", "2026-10-28"),
            ("Z26", "2026-11-25"),
            ("F27", "2026-12-29"),
            ("G27", "2027-01-27"),
        ),
        ("2026-11-26", "2026-12-25"),
        (("GAL", 1.0, "GAL"),),
        ("VOLUME", "GAL"),
    )
    batch, _ = created(ng_like, ASIAN_TICKET, ASIAN_TEMPLATE)
    enc = batch.encoded
    codes = ng_like.schedule.codes
    assert [codes[int(r)] for r in enc.slot_reference] == ["F27"] * 20 + ["G27"] * 2
    assert [codes[int(g)] for g in enc.group_contract] == ["Z26"]
    assert batch.resolved.payment is not None
    assert [str(d) for d in batch.resolved.payment.date] == ["2027-01-05", "2027-01-05"]


def test_a_physical_asian_future_is_refused_when_the_batch_is_made() -> None:
    physical = {
        name: value
        for name, value in ASIAN_TEMPLATE.items()
        if name not in ("payment_time_lag", "payment_holiday_calendar")
    }
    assert refused(ETHANE, ASIAN_TICKET, {**physical, "settlement_method": "physical"}) == (
        "settlement_method is 'physical', expected 'financial' with the asian method of trade 1 "
        "at row 1; an asian future is cash settled on the average of its month's pricing days"
    )


# --- the calendar day basis: the entered quantity times the days each month covers -------------
# trade-periods-and-bal.md, slice A: `quantity_per = calday` beside `month`. The resolution counts
# the calendar days of each component's contract month, weekends and holidays included, and the
# kernel forms the component's quantity once, the entered quantity times those days; under month
# the entered quantity stands in every month, unprorated. The pricing and payment calendars move
# the observations and the payment day and never the days.

LEAP = an_index(
    "LEAP",
    (("X26", "2026-11-25"), ("Z26", "2026-12-29"), ("G27", "2027-02-24"), ("G28", "2028-02-25")),
)
CALDAY_TEMPLATE: dict[str, object] = {**NG_TEMPLATE, "quantity_per": "calday"}


def quantity_columns(
    ticket: Mapping[str, list[object]], template: Mapping[str, object], ix: Index = NG
) -> tuple[list[int], list[float], list[float], list[float]]:
    """A batch's quantity columns as it retains them: the covered days, the component
    quantities, the entered quantities and the encoding's quote quantities."""
    batch, _ = created(ix, ticket, template)
    terms = batch.resolved
    return (
        [int(d) for d in terms.covered_days],
        [float(q) for q in terms.component_quantity],
        [float(q) for q in terms.quantity],
        [float(q) for q in batch.encoded.quote_quantity],
    )


def test_100_a_day_is_3000_in_november_3100_in_december_and_2800_and_2900_in_february() -> None:
    ticket: dict[str, list[object]] = {
        "trade_id": [14, 4, 7, 8],
        "trade_date": ["2026-10-06"] * 4,
        "contract_code": ["X26", "Z26", "G27", "G28"],
        "quantity": [100, 100, 100, 100],
        "fixed_price": [3.0] * 4,
    }
    days, components, entered, quoted = quantity_columns(ticket, CALDAY_TEMPLATE, LEAP)
    assert days == [30, 31, 28, 29]
    assert components == [3_000, 3_100, 2_800, 2_900]
    assert entered == [100, 100, 100, 100]
    assert quoted == [30_000_000, 31_000_000, 28_000_000, 29_000_000]  # lots of 10,000 MMBtu
    batch, _ = created(LEAP, ticket, CALDAY_TEMPLATE)
    assert (batch.resolved.quantity_per == BASES.index(QuantityPer.CALDAY)).all()


def test_a_strip_at_100_a_day_covers_3000_and_3100_and_at_100_a_month_100_and_100() -> None:
    strip: dict[str, list[object]] = {
        "trade_id": [19],
        "trade_date": ["2026-10-06"],
        "contract_code": ["X26-Z26"],
        "quantity": [100],
        "fixed_price": [3.0],
    }
    assert quantity_columns(strip, CALDAY_TEMPLATE)[:2] == ([30, 31], [3_000, 3_100])
    assert quantity_columns(strip, NG_TEMPLATE)[:2] == ([30, 31], [100, 100])
    # Signed and duplicate rows, and a row kept ready at nothing, keep the arithmetic.
    signed: dict[str, list[object]] = {
        "trade_id": [19, 20, 19, 1000],
        "trade_date": ["2026-10-06"] * 4,
        "contract_code": ["X26-Z26"] * 4,
        "quantity": [-100, 100, -100, 0],
        "fixed_price": [3.0] * 4,
    }
    days, components, entered, _ = quantity_columns(signed, CALDAY_TEMPLATE)
    assert days == [30, 31] * 4
    assert components == [-3_000, -3_100, 3_000, 3_100, -3_000, -3_100, 0, 0]
    assert entered == [-100, -100, 100, 100, -100, -100, 0, 0]


def test_the_pricing_and_payment_calendars_move_no_covered_day() -> None:
    # The ethane batch under asian and calday, 100 and -50 gallons a day of Z26: closing
    # 2 December as well takes December's pricing days from 22 to 21 and each weight with them,
    # and moves no covered day and no component quantity; a payment calendar closed on 5 January
    # moves the payment day alone.
    template: dict[str, object] = {**ASIAN_TEMPLATE, "quantity_per": "calday"}
    ticket: dict[str, list[object]] = {**ASIAN_TICKET, "quantity": [100, -50]}
    open_market, _ = created(ETHANE, ticket, template)
    closed = an_index(
        "ETHANE",
        (
            ("X26", "2026-11-30"),
            ("Z26", "2026-12-31"),
            ("F27", "2027-01-29"),
            ("G27", "2027-02-26"),
        ),
        (*ETHANE_HOLIDAYS, "2026-12-02"),
        (("GAL", 1.0, "GAL"),),
        ("VOLUME", "GAL"),
    )
    closed_market, _ = created(closed, ticket, template)
    for batch in (open_market, closed_market):
        np.testing.assert_array_equal(batch.resolved.covered_days, [31, 31])
        np.testing.assert_array_equal(batch.resolved.component_quantity, [3_100, -1_550])
        np.testing.assert_array_equal(batch.encoded.quote_quantity, [3_100, -1_550])
    assert open_market.encoded.observations.component.size == 44
    assert closed_market.encoded.observations.component.size == 42
    np.testing.assert_allclose(closed_market.encoded.observations.weight, [1 / 21] * 42)
    paid_later, _ = created(
        ETHANE,
        ticket,
        {
            **template,
            "payment_holiday_calendar": holiday_calendar(dates("2027-01-01", "2027-01-05")),
        },
    )
    assert open_market.resolved.payment is not None and paid_later.resolved.payment is not None
    assert [str(d) for d in open_market.resolved.payment.date] == ["2027-01-05"] * 2
    assert [str(d) for d in paid_later.resolved.payment.date] == ["2027-01-06"] * 2
    np.testing.assert_array_equal(paid_later.resolved.component_quantity, [3_100, -1_550])


# --- explicit dates: the other period form -----------------------------------------------------
# trade-periods-and-bal.md, slice C: start_date and end_date in place of a contract_code, exactly
# one form in a batch; the period split at month ends into components, each covering its month's
# days but the first from the start date and the last to the end date; a part of a month priced
# under asian alone and refused under the expiry-based methods; the dates in the spill.

DATED_TICKET: dict[str, list[object]] = {
    "trade_id": [16],
    "trade_date": ["2026-11-20"],
    "start_date": ["2026-11-12"],
    "end_date": ["2026-12-31"],
    "quantity": [2_000],
    "fixed_price": [0.25],
}


def dated(
    start: str, end: str, quantity: float = 2_000, label: int = 16
) -> dict[str, list[object]]:
    return {
        **DATED_TICKET,
        "trade_id": [label],
        "start_date": [start],
        "end_date": [end],
        "quantity": [quantity],
    }


def components_of(batch: Trades) -> tuple[list[str], list[str], list[str], list[int], list[float]]:
    """A batch's components as it retains them: the contract codes, the days covered and the
    quantities the basis gave."""
    terms = batch.resolved
    return (
        [terms.schedule.codes[int(c)] for c in terms.contract],
        [str(d) for d in terms.start_date],
        [str(d) for d in terms.end_date],
        [int(d) for d in terms.covered_days],
        [float(q) for q in terms.component_quantity],
    )


def test_a_period_across_a_month_end_is_two_components_clipped_at_the_ends() -> None:
    # 12 November to 31 December: X26 over 12 to 30 November, 19 days, and Z26 over the whole of
    # December, 31; 2,000 a month in each, and 100 a day 1,900 and 3,100, the ticket's table.
    batch, counter = created(ETHANE, DATED_TICKET, ASIAN_TEMPLATE)
    assert components_of(batch) == (
        ["X26", "Z26"],
        ["2026-11-12", "2026-12-01"],
        ["2026-11-30", "2026-12-31"],
        [19, 31],
        [2_000.0, 2_000.0],
    )
    np.testing.assert_array_equal(batch.resolved.occurrence, [0, 0])
    assert counter.freeze()["resolved_components"] == 2
    by_day, _ = created(
        ETHANE, dated("2026-11-12", "2026-12-31", 100), {**ASIAN_TEMPLATE, "quantity_per": "calday"}
    )
    assert components_of(by_day)[3:] == ([19, 31], [1_900.0, 3_100.0])
    # Full-month dates are the code's own components, observations and encoding.
    by_dates, _ = created(ETHANE, dated("2026-12-01", "2026-12-31"), ASIAN_TEMPLATE)
    two: dict[str, list[object]] = {
        **ASIAN_TICKET,
        "trade_id": [16, 17],
        "quantity": [2_000, 2_000],
    }
    by_code, _ = created(ETHANE, two, ASIAN_TEMPLATE)
    assert components_of(by_dates) == tuple(column[:1] for column in components_of(by_code))
    np.testing.assert_array_equal(
        by_dates.encoded.observations.date, by_code.encoded.observations.date[:22]
    )
    np.testing.assert_array_equal(by_dates.encoded.slot_exposure, by_code.encoded.slot_exposure / 2)
    assert by_dates.resolved.payment is not None and by_code.resolved.payment is not None
    assert (
        str(by_dates.resolved.payment.date[0])
        == str(by_code.resolved.payment.date[0])
        == "2027-01-05"
    )


def test_a_part_of_a_month_observes_its_own_pricing_days_and_pays_after_the_last() -> None:
    batch, _ = created(ETHANE, dated("2026-12-15", "2026-12-31"), ASIAN_TEMPLATE)
    obs = batch.encoded.observations
    assert [str(d) for d in obs.date] == [
        "2026-12-15", "2026-12-16", "2026-12-17", "2026-12-18", "2026-12-21", "2026-12-22",
        "2026-12-23", "2026-12-24", "2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31",
    ]  # fmt: skip
    np.testing.assert_allclose(obs.weight, np.full(12, 1 / 12))
    assert components_of(batch) == (["Z26"], ["2026-12-15"], ["2026-12-31"], [17], [2_000.0])
    assert batch.resolved.payment is not None
    assert str(batch.resolved.payment.date[0]) == "2027-01-05"
    # Ending on the 30th, the payment counts from the 30th: 4 January, the 1st being closed.
    shorter, _ = created(ETHANE, dated("2026-12-15", "2026-12-30"), ASIAN_TEMPLATE)
    assert shorter.resolved.payment is not None
    assert str(shorter.resolved.payment.date[0]) == "2027-01-04"
    assert refused(ETHANE, dated("2026-12-26", "2026-12-27"), ASIAN_TEMPLATE) == (
        "Z26 of trade 16 at row 1 has no pricing day from 2026-12-26 to 2026-12-27, expected a "
        "Monday to Friday of the days it covers the index's market is open on; the asian method "
        "averages the pricing days a component covers"
    )


def test_the_expiry_based_methods_take_whole_months_from_dates_and_refuse_a_part() -> None:
    whole, _ = created(NG, dated("2026-12-01", "2026-12-31", 10), NG_TEMPLATE)
    assert components_of(whole) == (["Z26"], ["2026-12-01"], ["2026-12-31"], [31], [10.0])
    np.testing.assert_array_equal(whole.encoded.slot_date, dates("2026-11-25"))  # the expiry
    for method, template in (
        ("lastday", NG_TEMPLATE),
        ("penultimate", TOY_TEMPLATE),
        ("last3day", TOY_TEMPLATE),
    ):
        ix = NG if method == "lastday" else TOY
        assert refused(
            ix, dated("2026-12-15", "2026-12-31", 10), {**template, "schedule_method": method}
        ) == (
            "Z26 of trade 16 at row 1 is covered from 2026-12-15 to 2026-12-31, part of its "
            f"month, expected the whole month under {method}; the expiry-based methods take the "
            "contract's month entire, and a part of it prices under asian"
        )
    # Two rows, the second a part of its month: the refusal names the second, not the first.
    two_rows: dict[str, list[object]] = {
        "trade_id": [16, 17],
        "trade_date": ["2026-11-20", "2026-11-20"],
        "start_date": ["2026-12-01", "2026-12-15"],
        "end_date": ["2026-12-31", "2026-12-31"],
        "quantity": [10, 10],
        "fixed_price": [0.25, 0.25],
    }
    assert refused(NG, two_rows, NG_TEMPLATE) == (
        "Z26 of trade 17 at row 2 is covered from 2026-12-15 to 2026-12-31, part of its month, "
        "expected the whole month under lastday; the expiry-based methods take the contract's "
        "month entire, and a part of it prices under asian"
    )


# --- contract codes and dates on one ticket, contract-codes-and-dates.md, since #172 ------------
# Each row chooses its period: both dates supplied book the days between them, whatever code
# stands beside them, the code kept as entered text and read for nothing; neither supplied, the
# row books its code; one date without the other, or no code and no pair, is refused by the first
# such row. A blank or a formula's "" in the three fields is a cell that supplied nothing.

THREE_FORMS: dict[str, list[object]] = {
    "trade_id": [1, 2, 3, 4, 5, 6],
    "trade_date": ["2026-11-20"] * 6,
    "contract_code": ["Z26", "Z26", "Z26", None, "BALZ26", "F27"],
    "start_date": [None, "2026-12-12", "2026-12-12", "2026-12-12", "2026-12-12", "2026-12-12"],
    "end_date": [None, "2026-12-31", "2026-12-20", "2026-12-20", "2026-12-31", "2026-12-31"],
    "quantity": [100, 100, 10, 10, 100, 100],
    "fixed_price": [0.25] * 6,
}


def test_each_row_books_by_its_dates_when_both_stand_and_by_its_code_otherwise() -> None:
    # The ticket's table, Z26 for its V26: row 1 the code alone, the whole month; rows 2 and 3
    # the code beside both dates, the dates winning; row 4 the dates alone, the same window as
    # row 3; row 5 a BAL label the grammar refuses, standing beside dates as typed; row 6 a code
    # naming another month, moving nothing. The components come in row order whichever form.
    batch, counter = created(ETHANE, THREE_FORMS, ASIAN_TEMPLATE)
    assert components_of(batch) == (
        ["Z26"] * 6,
        ["2026-12-01", "2026-12-12", "2026-12-12", "2026-12-12", "2026-12-12", "2026-12-12"],
        ["2026-12-31", "2026-12-31", "2026-12-20", "2026-12-20", "2026-12-31", "2026-12-31"],
        [31, 20, 9, 9, 20, 20],
        [100.0, 100.0, 10.0, 10.0, 100.0, 100.0],
    )
    np.testing.assert_array_equal(batch.resolved.occurrence, [0, 1, 2, 3, 4, 5])
    np.testing.assert_array_equal(batch.code_entered, [True, True, True, False, True, True])
    assert batch.entered_codes == ("Z26", "Z26", "Z26", "BALZ26", "F27")
    assert counter.freeze()["ticket_codes_read"] == 1  # row 1's Z26; the labels beside dates, never
    # Rows 3 and 4 are one window: the same observation days and the same payment day.
    obs = batch.encoded.observations
    np.testing.assert_array_equal(obs.date[obs.component == 2], obs.date[obs.component == 3])
    assert batch.resolved.payment is not None
    assert batch.resolved.payment.date[2] == batch.resolved.payment.date[3]
    # Row 2 alone books as row 2 in the batch does, the code beside it unread either way.
    alone, _ = created(ETHANE, dated("2026-12-12", "2026-12-31", 100), ASIAN_TEMPLATE)
    assert components_of(alone) == tuple([column[1]] for column in components_of(batch))
    # A code the grammar refuses stands beside both dates and is refused alone, by its row.
    bad_alone: dict[str, list[object]] = {
        **THREE_FORMS,
        "contract_code": ["Z2026", *THREE_FORMS["contract_code"][1:]],
    }
    assert refused(ETHANE, bad_alone, ASIAN_TEMPLATE) == (
        "contract_code row 1 is 'Z2026', expected a contract or strip with two-digit years, such "
        "as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
    )


def test_half_a_pair_or_no_period_is_refused_by_the_earliest_such_row() -> None:
    def form(
        codes: list[object], starts: list[object], ends: list[object]
    ) -> dict[str, list[object]]:
        return {**THREE_FORMS, "contract_code": codes, "start_date": starts, "end_date": ends}

    codes, starts, ends = (
        THREE_FORMS["contract_code"],
        THREE_FORMS["start_date"],
        THREE_FORMS["end_date"],
    )
    # A start without its end, a valid code standing beside it: one date books nothing.
    assert refused(ETHANE, form(codes, starts, [*ends[:2], None, *ends[3:]]), ASIAN_TEMPLATE) == (
        "start_date row 3 is 2026-12-12 without end_date row 3, expected both dates, the period's "
        "first and last day, or neither and a contract_code"
    )
    assert refused(ETHANE, form(codes, [None, None, *starts[2:]], ends), ASIAN_TEMPLATE) == (
        "end_date row 2 is 2026-12-31 without start_date row 2, expected both dates, the period's "
        "first and last day, or neither and a contract_code"
    )
    # No code and no pair on row 4: nothing books it.
    nothing = form(codes, [*starts[:3], None, *starts[4:]], [*ends[:3], None, *ends[4:]])
    assert refused(ETHANE, nothing, ASIAN_TEMPLATE) == (
        "row 4 has no period, expected a contract_code or start_date with end_date on each row; "
        "contract_code, start_date and end_date are not supplied"
    )
    # Two faults, half a pair on row 2 and nothing on row 4: the earlier row is named.
    two = {**nothing, "start_date": [None, None, *starts[2:3], None, *starts[4:]]}
    assert refused(ETHANE, two, ASIAN_TEMPLATE) == (
        "end_date row 2 is 2026-12-31 without start_date row 2, expected both dates, the period's "
        "first and last day, or neither and a contract_code"
    )
    # Reversed dates, and a month the schedule lacks, each named by the row and its form.
    assert refused(ETHANE, dated("2026-12-31", "2026-12-15"), ASIAN_TEMPLATE) == (
        "end_date row 1 is 2026-12-15, expected a day on or after start_date row 1, 2026-12-31"
    )
    assert refused(ETHANE, dated("2026-11-12", "2027-03-15"), ASIAN_TEMPLATE) == (
        "start_date row 1 is 2026-11-12 and end_date row 1 2027-03-15, expected months the index's "
        "schedule has a contract for; it has none for 2027-03"
    )
    mixed_months = form(
        ["Z26", "CAL27", *codes[2:]], [None, None, *starts[2:]], [None, None, *ends[2:]]
    )
    assert refused(ETHANE, mixed_months, ASIAN_TEMPLATE) == (
        "contract_code row 2 is 'CAL27', expected months the index's schedule has a contract for; "
        "it has none for 2027-03"
    )
    # No period field anywhere, in the template or the ticket: refused by name before any row.
    neither = {name: values for name, values in THREE_FORMS.items() if name not in PERIOD_FIELDS}
    assert refused(ETHANE, neither, ASIAN_TEMPLATE) == (
        "contract_code is missing, expected a value in the template or a column in the ticket, or "
        "start_date and end_date in its place"
    )


def test_a_template_may_hold_a_code_or_a_date_beside_the_tickets_period_columns() -> None:
    # A template code with ticket dates: the dated rows book their dates and the rest the code,
    # which is read once; a template start with a ticket end column: a pair where the end stands
    # and half a pair where it does not; template dates with a ticket code column: the dates win
    # on every row and no code is read; a template whose period cell held nothing owns the header,
    # so the ticket's column of that name is still overlap, and supplies no row.
    two: dict[str, list[object]] = {
        "trade_id": [1, 2],
        "trade_date": ["2026-11-20"] * 2,
        "quantity": [100, 10],
        "fixed_price": [0.25] * 2,
    }
    coded_template = {**ASIAN_TEMPLATE, "contract_code": "Z26"}
    dated_rows: dict[str, list[object]] = {
        **two,
        "start_date": [None, "2026-12-12"],
        "end_date": [None, "2026-12-20"],
    }
    batch, counter = created(ETHANE, dated_rows, coded_template)
    assert components_of(batch)[1:4] == (
        ["2026-12-01", "2026-12-12"],
        ["2026-12-31", "2026-12-20"],
        [31, 9],
    )
    assert batch.entered_codes == ("Z26", "Z26")
    assert counter.freeze()["ticket_codes_read"] == 1
    started_template = {**ASIAN_TEMPLATE, "start_date": "2026-12-12"}
    ends_column: dict[str, list[object]] = {
        **two,
        "contract_code": ["Z26", None],
        "end_date": ["2026-12-20", None],
    }
    assert refused(ETHANE, ends_column, started_template) == (
        "start_date is 2026-12-12 without end_date row 2, expected both dates, the period's first "
        "and last day, or neither and a contract_code"
    )
    two_ends: dict[str, list[object]] = {**ends_column, "end_date": ["2026-12-20", "2026-12-31"]}
    both_ends, _ = created(ETHANE, two_ends, started_template)
    assert components_of(both_ends)[1:4] == (
        ["2026-12-12"] * 2,
        ["2026-12-20", "2026-12-31"],
        [9, 20],
    )
    np.testing.assert_array_equal(both_ends.code_entered, [True, False])
    dated_template = {**ASIAN_TEMPLATE, "start_date": "2026-12-12", "end_date": "2026-12-31"}
    codes_column: dict[str, list[object]] = {**two, "contract_code": ["F27", "Z2026"]}
    by_dates, counter = created(ETHANE, codes_column, dated_template)
    assert components_of(by_dates)[:4] == (
        ["Z26"] * 2,
        ["2026-12-12"] * 2,
        ["2026-12-31"] * 2,
        [20, 20],
    )
    assert by_dates.entered_codes == ("F27", "Z2026") and counter.freeze()["ticket_codes_read"] == 0
    blank_template = {**ASIAN_TEMPLATE, "start_date": None}
    assert refused(ETHANE, dated_rows, blank_template) == (
        "start_date is supplied by the template and by the ticket, expected by one of them"
    )
    coded_rows: dict[str, list[object]] = {**two, "contract_code": ["Z26", "Z26"]}
    by_code, _ = created(ETHANE, coded_rows, blank_template)
    assert components_of(by_code)[1:3] == (["2026-12-01"] * 2, ["2026-12-31"] * 2)
    # A template code the grammar refuses stands until a row books by it.
    bad_template = {**ASIAN_TEMPLATE, "contract_code": "Z2026"}
    dated_pair: dict[str, list[object]] = {
        **two,
        "start_date": ["2026-12-12"] * 2,
        "end_date": ["2026-12-31"] * 2,
    }
    standing, _ = created(ETHANE, dated_pair, bad_template)
    assert standing.entered_codes == ("Z2026", "Z2026")
    assert refused(ETHANE, two, bad_template) == (
        "contract_code is 'Z2026', expected a contract or strip with two-digit years, such as F26, "
        "1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
    )


# --- the quantity unit selects the specification ------------------------------------------------
# quantity-unit-selection.md: the unit is a name among the index's specifications, exactly as the
# index spells it, and the quantity counts the row it names. A template holds the name and asks
# nothing of it; the index asked at creation owns what it means.

TWO_LOTS = an_index(
    lots=(("NYMEX NG", 10_000.0, "MMBTU"), ("ICE PHH", 2_500.0, "MMBTU"), ("MMBTU", 1.0, "MMBTU"))
)


def one_row(
    quantity: float = 2.0, code: str = "Z26", unit: str | None = None
) -> dict[str, list[object]]:
    """One ticket row; given a unit, the ticket carries the quantity_unit column itself."""
    ticket: dict[str, list[object]] = {
        "trade_id": [17],
        "trade_date": ["2026-09-24"],
        "contract_code": [code],
        "quantity": [quantity],
        "fixed_price": [3.0],
    }
    return {**ticket, "quantity_unit": [unit]} if unit is not None else ticket


WITHOUT_UNIT = {name: value for name, value in NG_TEMPLATE.items() if name != "quantity_unit"}


def quote_quantity(ix: Index, unit: str, quantity: float = 2.0, code: str = "Z26") -> float:
    batch, _ = created(ix, one_row(quantity, code), {**NG_TEMPLATE, "quantity_unit": unit})
    assert batch.resolved.specification.tolist() == [ix.specifications.names.index(unit)]
    return float(batch.encoded.quote_quantity.sum())


def test_the_quantity_unit_names_a_specification_row_and_the_quantity_counts_it() -> None:
    # The page's table: the same two of each name, the first row's size never taken for the
    # second's, and a bare unit the index defines with a size of one.
    assert quote_quantity(TWO_LOTS, "NYMEX NG") == 20_000.0
    assert quote_quantity(TWO_LOTS, "ICE PHH") == 5_000.0
    assert quote_quantity(TWO_LOTS, "ICE PHH", -2.0) == -5_000.0
    assert quote_quantity(TWO_LOTS, "MMBTU", 5_000.0) == 5_000.0


def test_a_template_holds_the_name_and_the_index_asked_at_creation_owns_it() -> None:
    template = a_template({**NG_TEMPLATE, "quantity_unit": "ICE PHH"})
    assert template.defaults["quantity_unit"] == "ICE PHH"
    with_both = trades(TWO_LOTS, a_ticket(one_row()), template, UNITS, WorkCounter())
    assert with_both.resolved.specification.tolist() == [1]
    with pytest.raises(ValueError) as refused:
        trades(NG, a_ticket(one_row()), template, UNITS, WorkCounter())
    assert str(refused.value) == (
        "quantity_unit is 'ICE PHH', expected one of the index's specifications: 'NYMEX NG'"
    )


@pytest.mark.parametrize(
    "unit",
    ["ice phh", "ICE PHH ", " ICE PHH", "ICE  PHH", "LOT", "lot", "MWH"],
    ids=[
        "case",
        "trailing space",
        "leading space",
        "two spaces",
        "LOT",
        "lot",
        "a unit the tables know",
    ],
)
def test_a_name_the_index_does_not_spell_is_refused_whatever_the_tables_know(unit: str) -> None:
    assert refused(TWO_LOTS, one_row(), {**NG_TEMPLATE, "quantity_unit": unit}) == (
        f"quantity_unit is {unit!r}, expected one of the index's specifications: "
        "'NYMEX NG', 'ICE PHH', 'MMBTU'"
    )


@pytest.mark.parametrize(
    "unit",
    ["ice phh", "ICE PHH ", " ICE PHH", "ICE  PHH", "LOT", "MWH"],
    ids=["case", "trailing space", "leading space", "two spaces", "LOT", "a unit the tables know"],
)
def test_a_name_typed_in_the_ticket_is_held_to_the_same_spelling(unit: str) -> None:
    # The ticket's column is matched as exactly as the template's value, and named with its
    # row: no case folded, no space trimmed, no unit the tables know taken for a specification.
    assert refused(TWO_LOTS, one_row(unit=unit), WITHOUT_UNIT) == (
        f"quantity_unit row 1 is {unit!r}, expected one of the index's specifications: "
        "'NYMEX NG', 'ICE PHH', 'MMBTU'"
    )


def test_lot_is_a_name_like_any_other_accepted_only_where_the_index_defines_it() -> None:
    assert refused(NG, one_row(), {**NG_TEMPLATE, "quantity_unit": "LOT"}) == (
        "quantity_unit is 'LOT', expected one of the index's specifications: 'NYMEX NG'"
    )
    with_lot = an_index(lots=(("NYMEX NG", 10_000.0, "MMBTU"), ("LOT", 10_000.0, "MMBTU")))
    assert quote_quantity(with_lot, "LOT") == 20_000.0


def test_the_unit_in_the_ticket_names_its_row_and_each_row_counts_its_own() -> None:
    template = {name: value for name, value in NG_TEMPLATE.items() if name != "quantity_unit"}
    batch, _ = created(TWO_LOTS, {**NG_TICKET, "quantity_unit": ["ICE PHH"] * 5}, template)
    np.testing.assert_array_equal(batch.resolved.specification, [1] * 5)
    np.testing.assert_array_equal(
        batch.encoded.quote_quantity, [25_000, -10_000, 17_500, -30_000, 25_000]
    )
    assert refused(TWO_LOTS, {**NG_TICKET, "quantity_unit": ["ICE NG"] * 5}, template) == (
        "quantity_unit row 1 is 'ICE NG', expected one of the index's specifications: "
        "'NYMEX NG', 'ICE PHH', 'MMBTU'"
    )
    # Since #163 a row's unit is its own: NG-002 in ICE PHH lots of 2,500 beside the NYMEX rows.
    mixed: list[object] = ["NYMEX NG", "ICE PHH", "NYMEX NG", "NYMEX NG", "NYMEX NG"]
    two, _ = created(TWO_LOTS, {**NG_TICKET, "quantity_unit": mixed}, template)
    np.testing.assert_array_equal(two.resolved.specification, [0, 1, 0, 0, 0])
    np.testing.assert_array_equal(
        two.encoded.quote_quantity, [100_000, -10_000, 70_000, -120_000, 100_000]
    )


def test_two_specifications_of_two_units_are_read_each_by_its_own_row() -> None:
    # A megawatt hour beside the NYMEX lot on an index quoted per MMBTU: the second row's size and
    # unit, 1 MWH of 3.412 MMBTU, never the first's 10,000.
    two_units = an_index(lots=(("NYMEX NG", 10_000.0, "MMBTU"), ("MWH", 1.0, "MWH")))
    assert quote_quantity(two_units, "NYMEX NG", 1.0) == 10_000.0
    assert quote_quantity(two_units, "MWH", 1.0) == pytest.approx(3.4121416331279417)
    assert quote_quantity(two_units, "MWH", 1_000.0) == pytest.approx(3_412.1416331279417)


def test_a_strip_counts_the_selected_unit_in_every_month() -> None:
    batch, _ = created(
        TWO_LOTS, one_row(5_000.0, "Z26-F27"), {**NG_TEMPLATE, "quantity_unit": "MMBTU"}
    )
    np.testing.assert_array_equal(batch.encoded.quote_quantity, [5_000.0, 5_000.0])
    np.testing.assert_array_equal(batch.resolved.quantity, [5_000.0, 5_000.0])
    for quantity in (0.5, float("nan"), float("inf")):
        assert refused(
            TWO_LOTS, one_row(quantity), {**NG_TEMPLATE, "quantity_unit": "MMBTU"}
        ).startswith("quantity of trade 17 at row 1 is ")


def test_the_old_field_is_unknown_to_the_definition() -> None:
    assert "contract_specification" not in {field.name for field in FIXED_FLOAT.fields}
    with pytest.raises(StopIteration):
        typed(FIXED_FLOAT, "contract_specification", ["NYMEX NG"])


# --- a quantity of zero: a row kept ready --------------------------------------------------------
# zero-quantities.md: a numeric zero quantity, from the template or the ticket, is a count like
# any other, the row kept with its label, its code and its amounts of nothing.

ENTRY_TICKET: dict[str, list[object]] = {
    "trade_id": [1001, 1002],
    "trade_date": ["2026-10-06", "2026-10-06"],
    "contract_code": ["Z26", "F27"],
    "quantity": [2, 0],
    "fixed_price": [3.0, 3.3],
}


def test_a_zero_quantity_in_the_ticket_is_kept_with_its_row() -> None:
    batch, counter = created(NG, ENTRY_TICKET)
    terms = batch.resolved
    np.testing.assert_array_equal(terms.trade_ids, [1001, 1002])
    np.testing.assert_array_equal(terms.quantity, [2.0, 0.0])
    np.testing.assert_array_equal(terms.contract, [1, 2])
    np.testing.assert_array_equal(batch.encoded.quote_quantity, [20_000.0, 0.0])
    np.testing.assert_array_equal(batch.encoded.offset, [-60_000.0, 0.0])
    np.testing.assert_array_equal(batch.encoded.slot_exposure, [20_000.0, 0.0])
    assert counter.freeze()["resolved_occurrences"] == 2
    negative_zero, _ = created(NG, {**ENTRY_TICKET, "quantity": [2, -0.0]})
    assert negative_zero.resolved.quantity[1] == 0.0


def test_a_zero_quantity_in_the_template_puts_every_row_at_nothing() -> None:
    template = {**NG_TEMPLATE, "quantity": 0.0}
    ticket = {name: values for name, values in NG_TICKET.items() if name != "quantity"}
    batch, _ = created(NG, ticket, template)
    np.testing.assert_array_equal(batch.resolved.quantity, [0.0] * 5)
    np.testing.assert_array_equal(batch.encoded.quote_quantity, [0.0] * 5)
    assert batch.encoded.group_contract.tolist() == [1, 2]  # both contracts held, at nothing
    assert refused(NG, {**NG_TICKET, "quantity": [0, 0, 0, 0, 0]}, template) == (
        "quantity is supplied by the template and by the ticket, expected by one of them"
    )


def test_a_zero_row_bypasses_no_other_rule() -> None:
    assert refused(NG, {**ENTRY_TICKET, "contract_code": ["Z26", "G27"]}) == (
        "contract_code row 2 is 'G27', expected months the index's schedule has a contract for; "
        "it has none for 2027-02"
    )
    assert refused(NG, ENTRY_TICKET, {**NG_TEMPLATE, "quantity_unit": "ICE PHH"}) == (
        "quantity_unit is 'ICE PHH', expected one of the index's specifications: 'NYMEX NG'"
    )
    assert refused(NG, {**ENTRY_TICKET, "quantity": [2, 0.5]}) == (
        "quantity of trade 1002 at row 2 is 0.5, expected a whole number"
    )


def test_a_zero_row_counts_the_selected_unit_whatever_its_row_or_size() -> None:
    assert quote_quantity(TWO_LOTS, "ICE PHH", 0.0) == 0.0  # the second row's specification
    assert quote_quantity(TWO_LOTS, "MMBTU", 0.0) == 0.0  # the size-one unit
    strip, _ = created(TWO_LOTS, one_row(0.0, "Z26-F27"), {**NG_TEMPLATE, "quantity_unit": "MMBTU"})
    np.testing.assert_array_equal(strip.resolved.contract, [1, 2])  # both months kept
    np.testing.assert_array_equal(strip.encoded.quote_quantity, [0.0, 0.0])
    np.testing.assert_array_equal(strip.encoded.offset_of_group, [0.0, 0.0])


# --- what is refused, naming the field and the sheet's row ----------------------------------


@pytest.mark.parametrize(
    ("ticket", "template", "message"),
    [
        (
            {**NG_TICKET, "quantity_unit": ["NYMEX NG"] * 5},
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
            {**NG_TEMPLATE, "quantity_unit": "ICE NG"},
            "quantity_unit is 'ICE NG', expected one of the index's specifications: 'NYMEX NG'",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "schedule_method": "Asian"},
            "schedule_method is 'Asian', expected lastday, penultimate, last3day or asian",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "schedule_method": "penultimate"},
            "settlement_method is 'physical', expected 'financial' with the penultimate method of "
            "trade 1001 at row 1; a penultimate future is cash settled on the business day "
            "before its contract's expiry",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "quantity_unit": "MMBTU"},
            "quantity_unit is 'MMBTU', expected one of the index's specifications: 'NYMEX NG'",
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
        (  # since #175: a bilateral batch names its counterparty
            NG_TICKET,
            {
                **{k: v for k, v in NG_TEMPLATE.items() if k != "clearing_house"},
                "route": "bilateral",
            },
            "counterparty is missing, expected it when route = bilateral",
        ),
        (  # and a cleared one faces its clearing house, no counterparty
            NG_TICKET,
            {**NG_TEMPLATE, "counterparty": "ACME Trading"},
            "counterparty is 'ACME Trading', expected none unless route = bilateral",
        ),
        (  # a marketing reserve is a finite amount of zero or more, the first bad row named
            {**NG_TICKET, "marketing_reserve": [15.0, -5.0, 25.0, 5.0, 0.0]},
            NG_TEMPLATE,
            "marketing_reserve row 2 is -5.0, expected a finite amount of zero or more",
        ),
        (
            {**NG_TICKET, "contract_code": ["Z26", "Z2026", "F27", "F27", "Z26"]},
            NG_TEMPLATE,
            "contract_code row 2 is 'Z2026', expected a contract or strip with two-digit years, "
            "such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28",
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
            "quantity of trade 1003 at row 3 is 7.5, expected a whole number",
        ),
        (
            NG_TICKET,
            WITHOUT_UNIT,
            "quantity_unit is missing, expected a value in the template or a column in the ticket",
        ),
    ],
)
def test_a_batch_that_cannot_be_resolved_says_why(
    ticket: Mapping[str, list[object]], template: Mapping[str, object], message: str
) -> None:
    assert refused(NG, ticket, template) == message


def test_a_quantity_is_named_by_its_trades_row_though_a_strip_sits_before_it() -> None:
    message = refused(
        TOY,
        {
            "trade_id": [1, 2],
            "trade_date": ["2026-09-24", "2026-09-24"],
            "contract_code": ["Z26-F27", "F27"],
            "quantity": [3, 2.5],
            "fixed_price": [3.2, 3.3],
        },
        TOY_TEMPLATE,
    )
    assert message == "quantity of trade 2 at row 2 is 2.5, expected a whole number"


def test_two_lags_for_one_contract_make_two_payment_groups_by_their_days() -> None:
    # NG-002 at +3bd pays 1 December where the other Z26 rows pay 30 November: Z26 is two
    # groups, the earlier day first, and F27 one, each row in the group of its own day.
    template = {k: v for k, v in TOY_TEMPLATE.items() if k != "payment_time_lag"}
    batch, counter = created(
        TOY,
        {**NG_TICKET, "payment_time_lag": ["+2bd", "+3bd", "+2bd", "+2bd", "+2bd"]},
        template,
    )
    np.testing.assert_array_equal(batch.encoded.group_contract, [1, 1, 2])
    np.testing.assert_array_equal(
        batch.encoded.payment_date, dates("2026-11-30", "2026-12-01", "2026-12-31")
    )
    np.testing.assert_array_equal(batch.encoded.group_of_component, [0, 1, 2, 2, 0])
    assert counter.freeze()["encoded_groups"] == 3
    # The page's case: four rows of J27 at +2bd and one at +3bd, two groups of J27, the three
    # rows paying 31 March first and the one paying 1 April after.
    four, _ = created(
        an_index(
            "J27",
            (("X26", "2026-10-28"), ("J27", "2027-03-29")),
            lots=(("TOY", 10_000.0, "MMBTU"),),
        ),
        {
            "trade_id": [1, 2, 3, 4],
            "trade_date": ["2026-09-24"] * 4,
            "contract_code": ["J27"] * 4,
            "quantity": [1, 1, 1, 1],
            "fixed_price": [3.0] * 4,
            "payment_time_lag": ["+2bd", "+2bd", "+2bd", "+3bd"],
        },
        template,
    )
    np.testing.assert_array_equal(four.encoded.group_contract, [1, 1])
    np.testing.assert_array_equal(four.encoded.payment_date, dates("2027-03-31", "2027-04-01"))
    np.testing.assert_array_equal(four.encoded.group_of_component, [0, 0, 0, 1])
    # +1bd on a calendar closed on the 26th and the 27th reaches 30 November, as +2bd on the
    # toy's calendar does: one group of Z26, the grouping by the day and not by the lag or the
    # calendar that made it.
    friday_closed = holiday_calendar(dates("2026-11-26", "2026-11-27"))
    one, _ = created(
        TOY,
        {
            **NG_TICKET,
            "payment_time_lag": ["+1bd", "+2bd", "+2bd", "+2bd", "+1bd"],
            "payment_holiday_calendar": [
                friday_closed,
                PAYMENT_CALENDAR,
                PAYMENT_CALENDAR,
                PAYMENT_CALENDAR,
                friday_closed,
            ],
        },
        {k: v for k, v in template.items() if k != "payment_holiday_calendar"},
    )
    np.testing.assert_array_equal(one.encoded.group_contract, [1, 2])
    np.testing.assert_array_equal(one.encoded.payment_date, dates("2026-11-30", "2026-12-31"))
    np.testing.assert_array_equal(one.encoded.group_of_component, [0, 0, 1, 1, 0])


def test_a_code_or_a_lag_the_grammar_refuses_is_named_by_its_first_bad_row() -> None:
    # Whatever order the texts sort in: 'F2027' sorts before 'Z2026' and 'AAA' before 'ZZ26',
    # yet the row from the top is the one named, as the page says of every ticket field.
    two_bad: dict[str, list[object]] = {
        **NG_TICKET,
        "contract_code": ["Z2026", "F2027", "F27", "F27", "Z26"],
    }
    assert refused(NG, two_bad).startswith("contract_code row 1 is 'Z2026', expected a contract")
    later_bad: dict[str, list[object]] = {
        **NG_TICKET,
        "contract_code": ["Z26", "ZZ26", "AAA", "F27", "Z26"],
    }
    assert refused(NG, later_bad).startswith("contract_code row 2 is 'ZZ26', expected a contract")
    template = {k: v for k, v in TOY_TEMPLATE.items() if k != "payment_time_lag"}
    lags: dict[str, list[object]] = {
        **NG_TICKET,
        "payment_time_lag": ["+2BD", "+2bd+", "+2xd", "+2bd", "+2bd"],
    }
    assert refused(TOY, lags, template) == (  # row 1 reads since #181; row 2 is the first bad
        "payment_time_lag row 2 is '+2bd+', expected one or more of a sign, a whole count and bd, "
        "cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd; from character 5, '+' "
        "begins with no "
        "instruction"
    )


def test_a_batch_field_the_ticket_supplies_is_named_with_its_row() -> None:
    # The page's promise, kept for every batch field as it was for quantity_unit: the ticket's
    # agreed value is named with the row that supplied it, the template's alone.
    without = {k: v for k, v in NG_TEMPLATE.items() if k not in ("route", "schedule_method")}
    cleared: dict[str, list[object]] = {
        **NG_TICKET,
        "route": ["Cleared"] * 5,
        "schedule_method": ["lastday"] * 5,
    }
    assert refused(NG, cleared, without) == (
        "route row 1 is 'Cleared', expected cleared or bilateral"
    )
    asian: dict[str, list[object]] = {
        **NG_TICKET,
        "route": ["cleared"] * 5,
        "schedule_method": ["Asian"] * 5,
    }
    assert refused(NG, asian, without) == (
        "schedule_method row 1 is 'Asian', expected lastday, penultimate, last3day or asian"
    )
    assert refused(NG, NG_TICKET, {**NG_TEMPLATE, "route": "Cleared"}) == (
        "route is 'Cleared', expected cleared or bilateral"
    )


def test_the_batch_fields_are_read_in_the_pages_order_the_unit_first() -> None:
    # The page's order is the code's: the quantity unit, then the method, the route, the
    # settlement and the basis, each read for its meaning once the rows agree. The ticket
    # supplies every batch field wrong at once, every row agreeing, since a template reads its
    # own values when it is made and would name the first wrong one in its row's order. The
    # unit is named, and each field put right names the next, until the batch is made.
    template = {"clearing_house": "CME Clearing"}
    ticket: dict[str, list[object]] = {
        **NG_TICKET,
        "quantity_unit": ["ICE PHH"] * 5,
        "schedule_method": ["Asian"] * 5,
        "route": ["Cleared"] * 5,
        "settlement_method": ["Physical"] * 5,
        "quantity_per": ["day"] * 5,
    }
    in_order = (
        (
            "quantity_unit",
            "NYMEX NG",
            "quantity_unit row 1 is 'ICE PHH', expected one of the index's specifications: "
            "'NYMEX NG'",
        ),
        (
            "schedule_method",
            "lastday",
            "schedule_method row 1 is 'Asian', expected lastday, penultimate, last3day or asian",
        ),
        ("route", "cleared", "route row 1 is 'Cleared', expected cleared or bilateral"),
        (
            "settlement_method",
            "physical",
            "settlement_method row 1 is 'Physical', expected physical or financial",
        ),
        (
            "quantity_per",
            "month",
            "quantity_per row 1 is 'day', expected month or calday",
        ),
    )
    for name, right, message in in_order:
        assert refused(NG, ticket, template) == message
        ticket[name] = [right] * 5
    created(NG, ticket, template)


def test_the_index_must_be_a_futures_index_with_one_contract_per_month() -> None:
    daily = index(
        "daily",
        "Sample Gas Daily index",
        gas_daily_schedule(("c0",), dates("2026-01-01"), dates("2026-01-31")),
        NG.conventions,
        NG.specifications,
        None,
        None,
        UNITS,
    )
    assert (
        refused(daily)
        == "index is a Gas Daily index, expected a futures or an IFERC index for a fixed_float"
    )
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
    # The three conditional fields are CONDITIONS'; the period fields' three say their rule in
    # the definition's words and are the periods' to check row by row, not a condition on a fact.
    conditional = {
        field.name: field.required_when
        for field in FIXED_FLOAT.fields
        if field.required_when != NONE
    }
    period = {name: conditional.pop(name) for name in ("contract_code", "start_date", "end_date")}
    assert period == {
        "contract_code": "no start_date and end_date on the row",
        "start_date": "no contract_code on the row, or with end_date",
        "end_date": "no contract_code on the row, or with start_date",
    }
    assert conditional == {
        name: f"{fact} = {value.value}" for name, (fact, value) in CONDITIONS.items()
    }


def test_the_ticket_and_the_template_are_of_one_instrument_the_future() -> None:
    other = Instrument("swap", "Another instrument.", FIXED_FLOAT.fields)
    with pytest.raises(ValueError) as refusal:
        trades(NG, a_ticket(NG_TICKET, other), a_template(NG_TEMPLATE), UNITS, WorkCounter())
    assert (
        str(refusal.value)
        == "ticket is of instrument 'swap', expected the template's, 'fixed_float'"
    )
    with pytest.raises(ValueError) as refusal:
        resolved(NG, a_ticket(NG_TICKET), a_template({"route": "cleared"}, other), WorkCounter())
    assert str(refusal.value) == (
        "template is of instrument 'swap', expected fixed_float, the one instrument whose trades "
        "are built"
    )


# --- any ticket of single months ------------------------------------------------------------


@settings(max_examples=50, deadline=None)
@given(
    rows=st.lists(
        st.tuples(
            st.sampled_from(["Z26", "z26", "F27", "f27"]),
            st.integers(min_value=-20, max_value=20),  # zero included, a row kept ready
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
    np.testing.assert_array_equal(terms.quantity, [q for _, q, _ in rows])
    assert counter.freeze()["resolved_components"] == n
    assert batch.encoded.group_contract.size == len({code.upper() for code, _, _ in rows})


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
    """The NG example's cells: the index, the template over its six fields and the ticket's
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
    ng = ENTRY["_CreateIndex"](
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specs,
        holidays,
        "NYMEX NG",
    )
    template = ENTRY["_CreateTradeTemplate"](
        "fixed_float", row(*NG_TEMPLATE), row(*NG_TEMPLATE.values())
    )
    return {
        "index": ng,
        "holidays": holidays,
        "template": template,
        "headers": row("trade_id", "trade_date", "contract_code", "quantity", "fixed_price"),
        "rows": cells(
            [1001.0, 46289.0, "Z26", 10.0, 3.1],
            [1002.0, 46289.0, "z26", -4.0, 3.15],
            [1003.0, 46290.0, "F27", 7.0, 3.4],
            [1004.0, 46290.0, "F27", -12.0, 3.35],
            [1001.0, 46289.0, "Z26", 10.0, 3.1],
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
    np.testing.assert_array_equal(batch.encoded.slot_exposure, [160_000, -50_000])
    np.testing.assert_array_equal(batch.resolved.trade_ids, [1001, 1002, 1003, 1004, 1001])


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
        "#ERROR _CreateTrades: fields cell (1, 1) is text 'Trade_id', expected a field of "
        "fixed_float: "
    )
    assert create(ix, headers, cells([1001.0, 46289.0, "Z26", "ten", 3.1]), template) == (
        "#ERROR _CreateTrades: trade_rows cell (1, 4) is text 'ten', expected number"
    )
    # Then the library: the overlap, the completion, the codes, the kernel.
    assert create(
        ix, row(*NG_TICKET, "route"), cells([1.0, 46289.0, "Z26", 1.0, 3.0, "cleared"]), template
    ) == (
        "#ERROR _CreateTrades: ValueError: route is supplied by the template and by the ticket, "
        "expected by one of them"
    )
    assert create(ix, headers, cells([1.0, 46289.0, "G27", 1.0, 3.0]), template) == (
        "#ERROR _CreateTrades: ValueError: contract_code row 1 is 'G27', expected months the "
        "index's schedule has a contract for; it has none for 2027-02"
    )
    assert create(ix, headers, cells([1.0, 46289.0, "Z26", 2.5, 3.0]), template) == (
        "#ERROR _CreateTrades: ValueError: quantity of trade 1 at row 1 is 2.5, "
        "expected a whole number"
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
        "contract_code",
        "schedule_method",
        "route",
        "settlement_method",
        "clearing_house",
        "quantity",
        "quantity_unit",
        "quantity_per",
        "fixed_price",
        "entered_contract_code",
        "start_date",
        "end_date",
        "covered_days",
        "component_quantity",
        "quote_quantity",
        "coefficient",
        "offset",
    ]
    assert table[1] == [
        "int64",
        "int64",
        "datetime64[D]",
        "str",
        "str",
        "str",
        "str",
        "str",
        "float64",
        "str",
        "str",
        "float64",
        "str",
        "datetime64[D]",
        "datetime64[D]",
        "int64",
        "float64",
        "float64",
        "float64",
        "float64",
    ]
    first = [
        1.0,
        1001.0,
        46289.0,
        "Z26",
        "lastday",
        "cleared",
        "physical",
        "CME Clearing",
        10.0,
        "NYMEX NG",
        "month",
        3.1,
        "Z26",
        46357.0,
        46387.0,
        31.0,
        10.0,
        100_000.0,
        100_000.0,
        -310_000.0,
    ]
    assert table[2] == first
    assert table[3][3] == "Z26"  # the schedule's spelling, where the ticket typed z26
    assert table[3][12] == "z26"  # and the entered text as typed, since #172
    assert table[6] == [5.0, *first[1:]]  # the repeated row, a trade of its own
    assert len(table) == 7


def test_the_spill_shows_the_batchs_facts_wherever_they_came_from(sheet: dict[str, Any]) -> None:
    # The route and the settlement from the ticket's columns, the template holding neither, and
    # since #175 the counterparty the bilateral route requires: the spill is the one place all
    # three are read back, the counterparty between the clearing house's place and the broker's.
    template = ENTRY["_CreateTradeTemplate"](
        "fixed_float",
        row("quantity_unit", "quantity_per", "schedule_method"),
        row("NYMEX NG", "month", "lastday"),
    )
    handle = ENTRY["_CreateTrades"](
        sheet["index"],
        row(
            "trade_date",
            "contract_code",
            "quantity",
            "fixed_price",
            "route",
            "settlement_method",
            "counterparty",
        ),
        cells(
            [46289.0, "Z26", 1.0, 3.0, "bilateral", "physical", "ACME Trading"],
            [46289.0, "F27", 2.0, 3.0, "bilateral", "physical", "Beta Energy"],
        ),
        template,
    )
    table = spilled(handle)
    assert table[0][:3] == ["row", "trade_date", "contract_code"]
    assert "trade_id" not in table[0] and "clearing_house" not in table[0]
    assert [line[4] for line in table[2:]] == ["bilateral", "bilateral"]
    assert [line[5] for line in table[2:]] == ["physical", "physical"]
    assert table[0][6] == "counterparty"
    assert [line[6] for line in table[2:]] == ["ACME Trading", "Beta Energy"]  # each row its own
    assert [line[8] for line in table[2:]] == ["NYMEX NG", "NYMEX NG"]  # the unit, the template's


def test_a_financial_batchs_spill_carries_its_payment_terms(sheet: dict[str, Any]) -> None:
    template = ENTRY["_CreateTradeTemplate"](
        "fixed_float",
        row(*TOY_TEMPLATE),
        row(
            *[
                sheet["holidays"] if name == "payment_holiday_calendar" else value
                for name, value in {**TOY_TEMPLATE, "quantity_unit": "NYMEX NG"}.items()
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
        "entered_contract_code",
        "start_date",
        "end_date",
        "covered_days",
        "component_quantity",
        "quote_quantity",
        "coefficient",
        "offset",
    ]
    assert [line[0] for line in table[2:]] == [1.0, 1.0]
    assert [line[14] for line in table[2:]] == ["Z26-F27", "Z26-F27"]  # the strip as typed
    assert [line[2] for line in table[2:]] == ["Z26", "F27"]
    assert [line[7] for line in table[2:]] == ["ION", "ION"]
    assert [line[12] for line in table[2:]] == ["+2bd", "+2bd"]  # the lag beside the day it gave
    assert [line[13] for line in table[2:]] == [46356.0, 46387.0]  # 30 Nov and 31 Dec 2026


def test_a_row_kept_ready_crosses_the_seam_as_a_number_and_reads_back_at_nothing(
    sheet: dict[str, Any],
) -> None:
    handle = ENTRY["_CreateTrades"](
        sheet["index"],
        sheet["headers"],
        cells([1001.0, 46301.0, "Z26", 2.0, 3.0], [1002.0, 46301.0, "F27", 0.0, 3.3]),
        sheet["template"],
    )
    table = spilled(handle)
    assert len(table) == 4  # two heading rows and both components, the second kept at nothing
    assert table[3][:4] == [2.0, 1002.0, 46301.0, "F27"]
    assert table[3][8] == 0.0
    assert table[3][12:] == ["F27", 46388.0, 46418.0, 31.0, 0.0, 0.0, 0.0, 0.0]
    # Zero is a number: the seam's words for anything else stand, and text is never coerced.
    create = ENTRY["_CreateTrades"]
    for cell, words in (
        ("0", "text '0'"),
        (True, "boolean TRUE"),
        (None, "blank"),
        ("", "empty text"),
    ):
        message = str(
            create(
                sheet["index"],
                sheet["headers"],
                cells([1.0, 46301.0, "Z26", cell, 3.0]),
                sheet["template"],
            )
        )
        assert message.startswith(
            f"#ERROR _CreateTrades: trade_rows cell (1, 4) is {words}, expected number"
        ), message


def test_the_spill_keeps_the_entered_quantity_beside_the_days_and_the_months_quantity(
    sheet: dict[str, Any],
) -> None:
    # The NG rows at their lots a calendar day: the two columns the resolution derived sit after
    # the payment terms and before what the encoding made, so the entered quantity, the days and
    # the month's quantity read side by side and the month's total is never taken for the
    # entered daily quantity.
    template = ENTRY["_CreateTradeTemplate"](
        "fixed_float", row(*NG_TEMPLATE), row(*{**NG_TEMPLATE, "quantity_per": "calday"}.values())
    )
    table = spilled(
        ENTRY["_CreateTrades"](sheet["index"], sheet["headers"], sheet["rows"], template)
    )
    assert table[0][8:] == [
        "quantity",
        "quantity_unit",
        "quantity_per",
        "fixed_price",
        "entered_contract_code",
        "start_date",
        "end_date",
        "covered_days",
        "component_quantity",
        "quote_quantity",
        "coefficient",
        "offset",
    ]
    assert table[1][13:17] == ["datetime64[D]", "datetime64[D]", "int64", "float64"]
    assert [line[13] for line in table[2:]] == [46357.0, 46357.0, 46388.0, 46388.0, 46357.0]
    assert [line[14] for line in table[2:]] == [46387.0, 46387.0, 46418.0, 46418.0, 46387.0]
    assert [line[8] for line in table[2:]] == [10.0, -4.0, 7.0, -12.0, 10.0]  # as entered
    assert [line[10] for line in table[2:]] == ["calday"] * 5
    assert [line[15] for line in table[2:]] == [31.0] * 5  # December and January
    assert [line[16] for line in table[2:]] == [310.0, -124.0, 217.0, -372.0, 310.0]
    assert [line[17] for line in table[2:]] == [
        3_100_000.0,
        -1_240_000.0,
        2_170_000.0,
        -3_720_000.0,
        3_100_000.0,
    ]
    assert str(ENTRY["_CreateTradeTemplate"]("fixed_float", row("quantity_per"), row("day"))) == (
        "#ERROR _CreateTradeTemplate: ValueError: quantity_per is 'day', expected month or calday"
    )


def test_a_dated_ticket_crosses_the_seam_and_spills_the_days_each_component_covers(
    sheet: dict[str, Any],
) -> None:
    # The NG rows booked by dates, a whole December each: the spill shows the days under
    # start_date and end_date beside the code the resolution bound, `(not supplied)` under
    # entered_contract_code since the row entered none, and a part of a month under lastday is
    # refused in the kernel's words; since #172 a code beside the dates is kept as entered text
    # while the dates book the period, whatever the code says.
    headers = row("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price")
    table = spilled(
        ENTRY["_CreateTrades"](
            sheet["index"],
            headers,
            cells([1001.0, 46289.0, 46357.0, 46387.0, 10.0, 3.1]),
            sheet["template"],
        )
    )
    assert table[0][3] == "contract_code" and table[2][3] == "Z26"
    assert table[0][12:15] == ["entered_contract_code", "start_date", "end_date"]
    assert table[2][12:18] == ["(not supplied)", 46357.0, 46387.0, 31.0, 10.0, 100_000.0]
    assert str(
        ENTRY["_CreateTrades"](
            sheet["index"],
            headers,
            cells([1001.0, 46289.0, 46371.0, 46387.0, 10.0, 3.1]),
            sheet["template"],
        )
    ) == (
        "#ERROR _CreateTrades: ValueError: Z26 of trade 1001 at row 1 is covered from "
        "2026-12-15 to 2026-12-31, part of its month, expected the whole month under lastday; "
        "the expiry-based methods take the contract's month entire, and a part of it prices "
        "under asian"
    )
    three = row(
        "trade_id",
        "trade_date",
        "contract_code",
        "start_date",
        "end_date",
        "quantity",
        "fixed_price",
    )
    # A code beside both dates: the dates book December, the code is kept as typed and never
    # read, so F27, naming another month, and BALZ26, which the grammar refuses, stand alike.
    for label in ("Z26", "F27", "BALZ26"):
        table = spilled(
            ENTRY["_CreateTrades"](
                sheet["index"],
                three,
                cells([1001.0, 46289.0, label, 46357.0, 46387.0, 10.0, 3.1]),
                sheet["template"],
            )
        )
        assert table[2][3] == "Z26" and table[2][12:15] == [label, 46357.0, 46387.0]
    # Formula-empty text and a blank in the three columns supply nothing: a code alone books the
    # month and a pair alone books the days, in one ticket, the empty cells displacing no text.
    table = spilled(
        ENTRY["_CreateTrades"](
            sheet["index"],
            three,
            cells(
                [1001.0, 46289.0, "Z26", "", "", 10.0, 3.1],
                [1002.0, 46289.0, None, 46357.0, 46387.0, -4.0, 3.15],
                [1003.0, 46290.0, "", 46388.0, 46418.0, 7.0, 3.4],
            ),
            sheet["template"],
        )
    )
    assert [line[3] for line in table[2:]] == ["Z26", "Z26", "F27"]
    assert [line[12] for line in table[2:]] == ["Z26", "(not supplied)", "(not supplied)"]
    assert [line[13] for line in table[2:]] == [46357.0, 46357.0, 46388.0]
    # Half a pair with a valid code beside it, and a row with nothing: refused by their rows.
    for body, message in (
        (
            cells([1001.0, 46289.0, "Z26", 46357.0, "", 10.0, 3.1]),
            "start_date row 1 is 2026-12-01 without end_date row 1, expected both dates, the "
            "period's first and last day, or neither and a contract_code",
        ),
        (
            cells(
                [1001.0, 46289.0, "Z26", "", "", 10.0, 3.1],
                [1002.0, 46289.0, "", None, "", -4.0, 3.15],
            ),
            "row 2 has no period, expected a contract_code or start_date with end_date on each "
            "row; contract_code, start_date and end_date are not supplied",
        ),
    ):
        assert str(ENTRY["_CreateTrades"](sheet["index"], three, body, sheet["template"])) == (
            f"#ERROR _CreateTrades: ValueError: {message}"
        )
    # A blank anywhere else keeps the seam's words, now the field's own: a blank is no quantity.
    assert (
        str(
            ENTRY["_CreateTrades"](
                sheet["index"],
                three,
                cells([1001.0, 46289.0, "Z26", "", "", None, 3.1]),
                sheet["template"],
            )
        )
        == "#ERROR _CreateTrades: trade_rows cell (1, 6) is blank, expected number"
    )


# --- mixed fields in one batch, mixed-trade-fields.md ---------------------------------------------
# The ticket's four rows of Z26 at 10 on the MIXED index, USD per GAL, GAL and BBL specifications
# of one unit each, 42 gallons a barrel: A, 1 BBL a month under lastday; B, -2 GAL a day under
# penultimate; C, 3 BBL a month under last3day; D, 22 GAL a month under asian; each its own unit,
# basis, method and clearing house in the ticket, the template holding the rest. The kernel tests
# hold the same rows resolved by hand; here they come through the creator.
MIXED = an_index(
    "MIXED",
    (("X26", "2026-11-30"), ("Z26", "2026-12-31"), ("F27", "2027-01-29"), ("G27", "2027-02-26")),
    ("2026-12-25",),
    (("GAL", 1.0, "GAL"), ("BBL", 1.0, "BBL")),
    ("VOLUME", "GAL"),
)
MIXED_TEMPLATE: dict[str, object] = {
    "route": "cleared",
    "settlement_method": "financial",
    "trade_date": day("2026-11-30"),
    "fixed_price": 10.0,
    "payment_time_lag": "+1bd",
    "payment_holiday_calendar": holiday_calendar(dates("2027-01-01")),
}
MIXED_TICKET: dict[str, list[object]] = {
    "trade_id": [1, 2, 3, 4],
    "contract_code": ["Z26"] * 4,
    "quantity": [1, -2, 3, 22],
    "quantity_unit": ["BBL", "GAL", "BBL", "GAL"],
    "quantity_per": ["month", "calday", "month", "month"],
    "schedule_method": ["lastday", "penultimate", "last3day", "asian"],
    "clearing_house": ["Clearer A", "Clearer B", "Clearer A", "Clearer B"],
}


def test_a_mixed_ticket_resolves_each_row_to_its_own_choices_and_encodes_to_the_number() -> None:
    batch, counter = created(MIXED, MIXED_TICKET, MIXED_TEMPLATE)
    terms = batch.resolved
    np.testing.assert_array_equal(terms.specification, [1, 0, 1, 0])
    np.testing.assert_array_equal(
        terms.schedule_method,
        [METHODS.index(ScheduleMethod(str(m))) for m in MIXED_TICKET["schedule_method"]],
    )
    np.testing.assert_array_equal(
        terms.quantity_per,
        [BASES.index(QuantityPer(str(b))) for b in MIXED_TICKET["quantity_per"]],
    )
    np.testing.assert_array_equal(terms.component_quantity, [1.0, -62.0, 3.0, 22.0])
    assert terms.clearing_house == ("Clearer A", "Clearer B", "Clearer A", "Clearer B")
    assert terms.payment is not None
    np.testing.assert_array_equal(
        terms.payment.date, dates("2027-01-04", "2026-12-31", "2027-01-04", "2027-01-04")
    )
    enc = batch.encoded
    np.testing.assert_allclose(enc.quote_quantity, [42.0, -62.0, 126.0, 22.0])
    np.testing.assert_allclose(enc.offset, [-420.0, 620.0, -1_260.0, -220.0])
    np.testing.assert_array_equal(enc.group_contract, [1, 1])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-31", "2027-01-04"))
    np.testing.assert_allclose(enc.offset_of_group, [620.0, -1_900.0])
    np.testing.assert_allclose(enc.slot_exposure, [-62.0] + [1.0] * 19 + [43.0, 43.0, 85.0])
    assert counter.freeze().as_dict() == {
        "encoded_components": 4,
        "encoded_groups": 2,
        "encoded_observations": 27,
        "encoded_slots": 23,
        "payment_rules_read": 1,
        "payment_shifts": 1,
        "reserved_fee_components": 4,
        "resolved_components": 4,
        "resolved_occurrences": 4,
        "schedule_codes_read": 4,
        "ticket_codes_read": 1,
    }


def test_a_uniform_field_from_the_template_or_the_ticket_makes_the_same_batch() -> None:
    # Each of the three fields held by the template, or repeated down a ticket column, gives the
    # same encoding through the one path; held by both it is refused as any field is.
    for name, value in (
        ("schedule_method", "asian"),
        ("quantity_unit", "GAL"),
        ("quantity_per", "calday"),
    ):
        ticket = {k: v for k, v in MIXED_TICKET.items() if k != name}
        by_template, _ = created(MIXED, ticket, {**MIXED_TEMPLATE, name: value})
        by_ticket, _ = created(MIXED, {**ticket, name: [value] * 4}, MIXED_TEMPLATE)
        np.testing.assert_allclose(
            by_ticket.encoded.quote_quantity, by_template.encoded.quote_quantity
        )
        np.testing.assert_allclose(
            by_ticket.encoded.slot_exposure, by_template.encoded.slot_exposure
        )
        np.testing.assert_array_equal(
            by_ticket.encoded.payment_date, by_template.encoded.payment_date
        )
        assert refused(MIXED, MIXED_TICKET, {**MIXED_TEMPLATE, name: value}) == (
            f"{name} is supplied by the template and by the ticket, expected by one of them"
        )


def test_a_mixed_tickets_refusals_name_the_first_offending_row() -> None:
    assert refused(
        MIXED, {**MIXED_TICKET, "quantity_unit": ["GAL", "ICE", "BBL", "LOT"]}, MIXED_TEMPLATE
    ) == ("quantity_unit row 2 is 'ICE', expected one of the index's specifications: 'GAL', 'BBL'")
    assert (
        refused(
            MIXED,
            {**MIXED_TICKET, "schedule_method": ["lastday", "Asian", "x", "asian"]},
            MIXED_TEMPLATE,
        )
        == "schedule_method row 2 is 'Asian', expected lastday, penultimate, last3day or asian"
    )
    assert refused(
        MIXED, {**MIXED_TICKET, "quantity_per": ["month", "day", "calday", "x"]}, MIXED_TEMPLATE
    ) == ("quantity_per row 2 is 'day', expected month or calday")
    # A physical batch takes lastday rows alone: B is named with its method, the first row that
    # is not.
    physical = {
        "route": "cleared",
        "settlement_method": "physical",
        "trade_date": day("2026-11-30"),
        "fixed_price": 10.0,
    }
    assert refused(MIXED, MIXED_TICKET, physical) == (
        "settlement_method is 'physical', expected 'financial' with the penultimate method of "
        "trade 2 at row 2; a penultimate future is cash settled on the business day before its "
        "contract's expiry"
    )
    lastday_rows: dict[str, list[object]] = {
        **MIXED_TICKET,
        "schedule_method": ["lastday"] * 4,
        "quantity_per": ["month", "calday", "month", "calday"],
    }
    batch, _ = created(MIXED, lastday_rows, physical)
    np.testing.assert_array_equal(batch.resolved.component_quantity, [1.0, -62.0, 3.0, 682.0])


def test_an_index_without_a_reporting_lot_refuses_a_batch_before_any_row_is_read() -> None:
    lotless = an_index(reporting_lot=None)
    message = (
        "index 'Henry Hub NYMEX' has no reporting_lot, expected one of its specifications named "
        "when the index was made; a batch's delta is reported in lots of it"
    )
    assert refused(lotless) == message
    assert refused(lotless, {**NG_TICKET, "contract_code": ["Z2026"] * 5}) == message
    batch, _ = created(NG, NG_TICKET, NG_TEMPLATE)
    assert NG.reporting_lot is not None and batch.resolved.reporting_lot is NG.reporting_lot
    assert NG.reporting_lot.words == "lots of NYMEX NG (10000 MMBTU)"


# --- calendar-driven asian references, calendar-driven-asian-references.md ---------------------
# The ticket's WTI-like index: contracts expiring the month before their own, so that a December
# booking's days are F27's and then G27's; a barrel the unit entered and a thousand-barrel LOT the
# lot reported; the asian template in barrels paying +2bd on the same calendar.
WTI_HOLIDAYS = ("2026-12-25", "2027-01-01")
WTI = an_index(
    "WTI",
    (("Z26", "2026-11-20"), ("F27", "2026-12-21"), ("G27", "2027-01-20"), ("H27", "2027-02-22")),
    WTI_HOLIDAYS,
    (("BBL", 1.0, "BBL"), ("LOT", 1_000.0, "BBL")),
    ("VOLUME", "BBL"),
    "LOT",
)
WTI_TEMPLATE: dict[str, object] = {
    **ASIAN_TEMPLATE,
    "quantity_unit": "BBL",
    "payment_holiday_calendar": holiday_calendar(dates(*WTI_HOLIDAYS)),
}
WTI_TICKET: dict[str, list[object]] = {
    "trade_id": [23],
    "trade_date": ["2026-11-20"],
    "start_date": ["2026-12-18"],
    "end_date": ["2026-12-28"],
    "quantity": [1_200],
    "fixed_price": [70.0],
}
WTI_WINDOW = ["2026-12-18", "2026-12-21", "2026-12-22", "2026-12-23", "2026-12-24", "2026-12-28"]


def test_the_wti_booking_observes_six_days_off_f27_then_g27_and_pays_30_december() -> None:
    # The ticket's booking resolved: 18 to 28 December, eleven days covered and six pricing days,
    # F27 pricing the 18th and the 21st, its expiry, and G27 the four after, 200 barrels each;
    # booked as Z26, which keeps the fixed leg of -84,000 and pays 30 December, two business days
    # after the 28th on the payment calendar.
    batch, _ = created(WTI, WTI_TICKET, WTI_TEMPLATE)
    assert components_of(batch) == (["Z26"], ["2026-12-18"], ["2026-12-28"], [11], [1_200.0])
    enc = batch.encoded
    codes = WTI.schedule.codes
    assert [str(d) for d in enc.slot_date] == WTI_WINDOW
    assert [codes[int(r)] for r in enc.slot_reference] == ["F27", "F27", "G27", "G27", "G27", "G27"]
    assert [codes[int(g)] for g in enc.group_contract] == ["Z26"]
    np.testing.assert_allclose(enc.slot_exposure, [200.0] * 6)
    np.testing.assert_allclose(enc.offset_of_group, [-84_000.0])
    assert batch.resolved.payment is not None
    assert [str(d) for d in batch.resolved.payment.date] == ["2026-12-30"]


def test_a_code_and_the_whole_months_dates_book_the_same_december_on_the_wti_index() -> None:
    # Z26 typed as a code and 1 to 31 December typed as dates: 22 pricing days, 15 F27's and 7
    # G27's, 100 barrels a day of 2,200, paying 5 January, the slots the same either way.
    by_code, _ = created(
        WTI,
        {
            "trade_id": [26],
            "trade_date": ["2026-11-20"],
            "contract_code": ["Z26"],
            "quantity": [2_200],
            "fixed_price": [70.0],
        },
        WTI_TEMPLATE,
    )
    by_dates, _ = created(
        WTI,
        {
            **WTI_TICKET,
            "trade_id": [26],
            "start_date": ["2026-12-01"],
            "end_date": ["2026-12-31"],
            "quantity": [2_200],
        },
        WTI_TEMPLATE,
    )
    for batch in (by_code, by_dates):
        enc = batch.encoded
        assert [WTI.schedule.codes[int(r)] for r in enc.slot_reference] == ["F27"] * 15 + [
            "G27"
        ] * 7
        np.testing.assert_allclose(enc.slot_exposure, [100.0] * 22)
        assert batch.resolved.payment is not None
        assert [str(d) for d in batch.resolved.payment.date] == ["2027-01-05"]
    np.testing.assert_array_equal(by_code.encoded.slot_date, by_dates.encoded.slot_date)


# --- delta by day, month and year, daily-risk-vector.md ------------------------------------------
# The ticket's month-aligned index: X26 expiring 30 November bounds the calendar, Z26 expires
# 31 December and F27 29 January, closed on 25 December and New Year's Day, dollars a barrel, a
# barrel and a thousand-barrel LOT the specifications, the LOT reported; a template that leaves the
# method to the rows, cleared and financial at +1bd on the same calendar; 22 LOT of a December
# asian and 3 LOT of a Z26 penultimate, both at 70.
MONTHLY = an_index(
    "monthly",
    (("X26", "2026-11-30"), ("Z26", "2026-12-31"), ("F27", "2027-01-29")),
    WTI_HOLIDAYS,
    (("BBL", 1.0, "BBL"), ("LOT", 1_000.0, "BBL")),
    ("VOLUME", "BBL"),
    "LOT",
)
PEN_ASIAN_TEMPLATE: dict[str, object] = {
    key: value for key, value in WTI_TEMPLATE.items() if key != "schedule_method"
} | {"quantity_unit": "LOT", "payment_time_lag": "+1bd"}
ASIAN_AND_PEN: dict[str, list[object]] = {
    "trade_id": [1, 16],
    "trade_date": ["2026-11-20", "2026-11-20"],
    "contract_code": ["Z26", "Z26"],
    "quantity": [22, 3],
    "fixed_price": [70.0, 70.0],
    "schedule_method": ["asian", "penultimate"],
}
DECEMBER_PRICING_DAYS = ethane_days("2026-12-01", "2027-01-01")  # the same holidays


def test_the_asian_and_pen_share_one_december_axis_of_22_days_one_month_and_one_year() -> None:
    # Two groups, Z26 paying 4 January and Z26 paying 31 December, 23 slots: the asian's 22 days
    # and the pen's one, 30 December, which the asian observes too; the days axis is December's 22
    # pricing days once, every one priced by Z26, and since #186 the month axis Z26's own month,
    # 1 December, and the year axis 1 January 2026, the buckets that stand whatever fixes.
    batch, _ = created(MONTHLY, ASIAN_AND_PEN, PEN_ASIAN_TEMPLATE)
    enc = batch.encoded
    assert enc.slot_group.size == 23 and enc.group_contract.size == 2
    assert batch.resolved.payment is not None
    assert [str(d) for d in batch.resolved.payment.date] == ["2027-01-04", "2026-12-31"]
    assert len(DECEMBER_PRICING_DAYS) == 22
    assert [str(d) for d in enc.days] == DECEMBER_PRICING_DAYS
    assert [MONTHLY.schedule.codes[int(r)] for r in enc.day_reference] == ["Z26"] * 22
    assert [str(m) for m in enc.contract_months] == ["2026-12-01"]
    assert [str(y) for y in enc.contract_years] == ["2026-01-01"]
    np.testing.assert_array_equal(enc.contract_month_of_reference, [0])
    np.testing.assert_array_equal(enc.contract_year_of_month, [0])
    # The reversed rows give the same axes; with the pen at +2bd both pay 4 January, one group
    # and 22 slots, the axes the same.
    reversed_rows = {key: list(reversed(values)) for key, values in ASIAN_AND_PEN.items()}
    turned, _ = created(MONTHLY, reversed_rows, PEN_ASIAN_TEMPLATE)
    np.testing.assert_array_equal(turned.encoded.days, enc.days)
    np.testing.assert_array_equal(turned.encoded.day_of_slot, enc.day_of_slot)
    later, _ = created(
        MONTHLY,
        {**ASIAN_AND_PEN, "payment_time_lag": ["+1bd", "+2bd"]},
        {key: value for key, value in PEN_ASIAN_TEMPLATE.items() if key != "payment_time_lag"},
    )
    assert later.encoded.slot_group.size == 22 and later.encoded.group_contract.size == 1
    np.testing.assert_array_equal(later.encoded.days, enc.days)
    np.testing.assert_array_equal(later.encoded.contract_months, enc.contract_months)


# --- an IFERC basis future, iferc-basis-futures.md ------------------------------------------
# The ticket's Waha-like index as the kernel tests have it: X26, Z26 and F27 last trading on the
# last business day before their months and published on the first business day of them, a 2,500
# MMBtu LOT and a bare MMBTU, the LOT reported, no pricing calendar; the payment calendar closing
# New Year's Day; the template cleared, financial, lastday, LOT a month at +3bd; WAH001, 1 LOT of
# Z26 at -0.50 booked 30 November.

WAHA = index(
    "WAHA",
    "Waha basis - ICE",
    iferc_schedule(
        ("X26", "Z26", "F27"),
        dates("2026-10-30", "2026-11-30", "2026-12-31"),
        dates("2026-11-02", "2026-12-01", "2027-01-04"),
    ),
    index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("LOT", "MMBTU"),
        np.array([2_500.0, 1.0]),
        ("MMBTU", "MMBTU"),
        np.zeros(2),
        np.zeros(2),
        UNITS,
    ),
    None,
    "LOT",
    UNITS,
)
WAHA_PAYS = holiday_calendar(dates("2027-01-01"))
WAHA_TEMPLATE: dict[str, object] = {
    "quantity_unit": "LOT",
    "quantity_per": "month",
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "ICE Clear Europe",
    "payment_time_lag": "+3bd",
    "payment_holiday_calendar": WAHA_PAYS,
}
WAHA_TICKET: dict[str, list[object]] = {
    "trade_id": [1001],
    "trade_date": ["2026-11-30"],
    "contract_code": ["Z26"],
    "quantity": [1],
    "fixed_price": [-0.50],
}


def test_an_iferc_basis_future_observes_publication_day_and_pays_from_last_trading() -> None:
    # The terms hold the IFERC schedule; Z26 is row 1 covering the whole of December; the one
    # observation is 1 December, the publication day, and the payment 3 December, three business
    # days after the 30 November last trading day; the encoding a 2,500 MMBtu exposure with a
    # fixed leg of 1,250, one slot on 1 December referencing Z26; the counts one of each and the
    # schedule's three codes read.
    batch, counter = created(WAHA, WAHA_TICKET, WAHA_TEMPLATE)
    terms = batch.resolved
    assert terms.index is WAHA and terms.schedule is WAHA.schedule
    assert terms.settlement is Settlement.FINANCIAL
    np.testing.assert_array_equal(terms.schedule_method, [METHODS.index(ScheduleMethod.LASTDAY)])
    np.testing.assert_array_equal(terms.contract, [1])
    np.testing.assert_array_equal(terms.start_date, dates("2026-12-01"))
    np.testing.assert_array_equal(terms.end_date, dates("2026-12-31"))
    np.testing.assert_array_equal(terms.covered_days, [31])
    np.testing.assert_array_equal(terms.quantity, [1])
    np.testing.assert_array_equal(terms.fixed_price, [-0.5])
    assert terms.payment is not None
    assert terms.payment.lag == ("+3bd",)
    assert terms.payment.calendar == (WAHA_PAYS,)
    np.testing.assert_array_equal(terms.payment.date, dates("2026-12-03"))
    enc = batch.encoded
    np.testing.assert_array_equal(enc.observations.date, dates("2026-12-01"))
    np.testing.assert_array_equal(enc.observations.weight, [1.0])
    np.testing.assert_array_equal(enc.quote_quantity, [2_500.0])
    np.testing.assert_array_equal(enc.offset, [1_250.0])
    np.testing.assert_array_equal(enc.slot_date, dates("2026-12-01"))
    np.testing.assert_array_equal(enc.slot_reference, [1])
    np.testing.assert_array_equal(enc.group_contract, [1])
    np.testing.assert_array_equal(enc.payment_date, dates("2026-12-03"))
    assert counter.freeze().as_dict() == {
        "encoded_components": 1,
        "encoded_groups": 1,
        "encoded_observations": 1,
        "encoded_slots": 1,
        "payment_rules_read": 1,
        "payment_shifts": 1,
        "reserved_fee_components": 1,
        "resolved_components": 1,
        "resolved_occurrences": 1,
        "schedule_codes_read": 3,
        "ticket_codes_read": 1,
    }


def test_iferc_payment_counts_from_last_trading_on_the_payment_calendar_not_publication() -> None:
    # A Z26-F27 strip: one component a month on one occurrence, Z26 paying 3 December and F27
    # 6 January, 31 December plus three business days with New Year's Day closed, each observed
    # on its own publication day. X26, the schedule's first month, booked 15 October pays
    # 4 November. A calendar closing 2 December moves Z26's payment to the 4th and its observation
    # not at all. Two rows at +3bd and +4bd are two groups of one contract. +1bd lands on the
    # publication day and is refused by the existing rule.
    strip, _ = created(WAHA, {**WAHA_TICKET, "contract_code": ["Z26-F27"]}, WAHA_TEMPLATE)
    np.testing.assert_array_equal(strip.resolved.occurrence, [0, 0])
    np.testing.assert_array_equal(strip.resolved.contract, [1, 2])
    assert strip.resolved.payment is not None
    np.testing.assert_array_equal(strip.resolved.payment.date, dates("2026-12-03", "2027-01-06"))
    np.testing.assert_array_equal(strip.encoded.slot_date, dates("2026-12-01", "2027-01-04"))
    x26, _ = created(
        WAHA, {**WAHA_TICKET, "trade_date": ["2026-10-15"], "contract_code": ["X26"]}, WAHA_TEMPLATE
    )
    assert x26.resolved.payment is not None
    np.testing.assert_array_equal(x26.resolved.payment.date, dates("2026-11-04"))
    np.testing.assert_array_equal(x26.encoded.slot_date, dates("2026-11-02"))
    closed, _ = created(
        WAHA,
        WAHA_TICKET,
        {
            **WAHA_TEMPLATE,
            "payment_holiday_calendar": holiday_calendar(dates("2026-12-02", "2027-01-01")),
        },
    )
    assert closed.resolved.payment is not None
    np.testing.assert_array_equal(closed.resolved.payment.date, dates("2026-12-04"))
    np.testing.assert_array_equal(closed.encoded.slot_date, dates("2026-12-01"))
    pair, _ = created(
        WAHA,
        {
            "trade_id": [12, 19],
            "trade_date": ["2026-11-30", "2026-11-30"],
            "contract_code": ["Z26", "Z26"],
            "quantity": [1, -1],
            "fixed_price": [-0.50, -0.50],
            "payment_time_lag": ["+3bd", "+4bd"],
        },
        {key: value for key, value in WAHA_TEMPLATE.items() if key != "payment_time_lag"},
    )
    np.testing.assert_array_equal(pair.encoded.payment_date, dates("2026-12-03", "2026-12-04"))
    np.testing.assert_array_equal(pair.encoded.group_contract, [1, 1])
    assert pair.encoded.slot_group.size == 2
    assert refused(WAHA, WAHA_TICKET, {**WAHA_TEMPLATE, "payment_time_lag": "+1bd"}) == (
        "Z26 pays on 2026-12-01, expected a day after its last observation, 2026-12-01, when its "
        "final price exists"
    )


def test_an_iferc_batch_is_financial_lastday_whole_months_on_a_reporting_index_or_says_why() -> (
    None
):
    physical = {
        key: value
        for key, value in WAHA_TEMPLATE.items()
        if key not in ("payment_time_lag", "payment_holiday_calendar")
    }
    assert refused(WAHA, WAHA_TICKET, {**physical, "settlement_method": "physical"}) == (
        "settlement_method is 'physical', expected 'financial' on an IFERC index; an IFERC basis "
        "future is cash settled on its month's published index"
    )
    assert refused(WAHA, WAHA_TICKET, {**WAHA_TEMPLATE, "schedule_method": "asian"}) == (
        "schedule_method of trade 1001 at row 1 is 'asian', expected 'lastday' on an IFERC "
        "index; an IFERC month has one index, published once"
    )
    two: dict[str, list[object]] = {
        "trade_id": [1001, 1002],
        "trade_date": ["2026-11-30", "2026-11-30"],
        "contract_code": ["Z26", "F27"],
        "quantity": [1, 1],
        "fixed_price": [-0.5, -0.5],
        "schedule_method": ["lastday", "penultimate"],
    }
    by_row = {key: value for key, value in WAHA_TEMPLATE.items() if key != "schedule_method"}
    assert refused(WAHA, two, by_row) == (
        "schedule_method of trade 1002 at row 2 is 'penultimate', expected 'lastday' on an "
        "IFERC index; an IFERC month has one index, published once"
    )
    part: dict[str, list[object]] = {
        **{key: value for key, value in WAHA_TICKET.items() if key != "contract_code"},
        "start_date": ["2026-12-01"],
        "end_date": ["2026-12-15"],
    }
    assert refused(WAHA, part, WAHA_TEMPLATE) == (
        "Z26 of trade 1001 at row 1 is covered from 2026-12-01 to 2026-12-15, part of its "
        "month, expected the whole month under lastday; an IFERC month's index is one price for "
        "the whole month"
    )
    assert refused(WAHA, {**WAHA_TICKET, "contract_code": ["G27"]}, WAHA_TEMPLATE) == (
        "contract_code row 1 is 'G27', expected months the index's schedule has a contract for; "
        "it has none for 2027-02"
    )
    bare = index(
        "bare",
        "An index made without a reporting lot",
        WAHA.schedule,
        WAHA.conventions,
        WAHA.specifications,
        None,
        None,
        UNITS,
    )
    assert refused(bare, WAHA_TICKET, WAHA_TEMPLATE) == (
        "index 'bare' has no reporting_lot, expected one of its specifications named when the "
        "index was made; a batch's delta is reported in lots of it"
    )


# --- numeric trade IDs, numeric-trade-ids.md ------------------------------------------------
# The ticket's rows: 123456, 123457 and 123456 again, numbers typed as the source system keeps
# them, the repeat two occurrences; an ID is a whole number of at most 15 digits either side of
# zero, read once, the template's repeated and the ticket's by row, and changes no number.

ID_TICKET: dict[str, list[object]] = {
    "trade_id": [123456, 123457, 123456],
    "trade_date": ["2026-10-09", "2026-10-09", "2026-10-09"],
    "contract_code": ["Z26", "F27", "Z26"],
    "quantity": [1, -2, 1],
    "fixed_price": [3.0, 3.1, 3.0],
}


def test_the_tickets_numeric_ids_are_kept_whole_and_the_repeat_counts_twice() -> None:
    batch, counter = created(NG, ID_TICKET)
    terms = batch.resolved
    assert terms.trade_ids is not None and terms.trade_ids.dtype == np.int64
    np.testing.assert_array_equal(terms.trade_ids, [123456, 123457, 123456])
    assert not terms.trade_ids.flags.writeable
    np.testing.assert_array_equal(terms.occurrence, [0, 1, 2])
    np.testing.assert_array_equal(batch.encoded.quote_quantity, [10_000, -20_000, 10_000])
    assert terms.named(2) == "trade 123456 at row 3"
    assert counter.freeze().as_dict()["resolved_occurrences"] == 3
    # The IDs change no number: the same rows under other IDs encode the same arrays.
    other, _ = created(NG, {**ID_TICKET, "trade_id": [7, 8, 9]})
    np.testing.assert_array_equal(other.encoded.quote_quantity, batch.encoded.quote_quantity)
    np.testing.assert_array_equal(other.encoded.offset, batch.encoded.offset)
    np.testing.assert_array_equal(other.encoded.slot_exposure, batch.encoded.slot_exposure)
    np.testing.assert_array_equal(other.encoded.group_contract, batch.encoded.group_contract)


def test_a_whole_id_of_at_most_15_digits_either_side_of_zero_is_kept_exactly() -> None:
    edge, _ = created(NG, {**ID_TICKET, "trade_id": [999_999_999_999_999, -999_999_999_999_999, 0]})
    assert edge.resolved.trade_ids is not None
    assert edge.resolved.trade_ids.tolist() == [999_999_999_999_999, -999_999_999_999_999, 0]
    whole, _ = created(NG, {**ID_TICKET, "trade_id": [123456.0, 123457.0, 123456.0]})
    assert whole.resolved.trade_ids is not None
    assert whole.resolved.trade_ids.tolist() == [123456, 123457, 123456]


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (123456.5, "123456.5"),
        (1_000_000_000_000_000, "1000000000000000"),
        (-1_000_000_000_000_000, "-1000000000000000"),
        (float("nan"), "nan"),
        (float("inf"), "inf"),
        (-float("inf"), "-inf"),
    ],
    ids=["a fraction", "a sixteenth digit", "a sixteenth digit below zero", "nan", "inf", "-inf"],
)
def test_an_id_that_is_not_a_whole_number_of_at_most_15_digits_is_refused_by_its_row(
    value: float, shown: str
) -> None:
    assert refused(NG, {**ID_TICKET, "trade_id": [123456, value, 123456]}) == (
        f"trade_id row 2 is {shown}, expected a whole number of at most 15 digits"
    )


def test_a_templates_id_is_read_once_and_repeated_on_every_row() -> None:
    without = {key: value for key, value in ID_TICKET.items() if key != "trade_id"}
    batch, _ = created(NG, without, {**NG_TEMPLATE, "trade_id": 77})
    assert batch.resolved.trade_ids is not None
    assert batch.resolved.trade_ids.tolist() == [77, 77, 77]
    assert batch.resolved.named(1) == "trade 77 at row 2"
    with pytest.raises(ValueError) as fraction:
        a_template({**NG_TEMPLATE, "trade_id": 12.5})
    assert str(fraction.value) == "trade_id is 12.5, expected a whole number of at most 15 digits"
    with pytest.raises(ValueError) as long_id:
        a_template({**NG_TEMPLATE, "trade_id": 1_000_000_000_000_000})
    assert str(long_id.value) == (
        "trade_id is 1000000000000000, expected a whole number of at most 15 digits"
    )
    assert refused(NG, ID_TICKET, {**NG_TEMPLATE, "trade_id": 123456}) == (
        "trade_id is supplied by the template and by the ticket, expected by one of them"
    )


def test_a_strips_rows_carry_their_id_and_row_and_a_later_bad_row_is_named_by_its_own() -> None:
    strip, _ = created(NG, {**ID_TICKET, "contract_code": ["Z26-F27", "F27", "Z26"]})
    terms = strip.resolved
    np.testing.assert_array_equal(terms.occurrence, [0, 0, 1, 2])
    assert terms.trade_ids is not None and terms.trade_ids.tolist() == [123456, 123457, 123456]
    assert [terms.named(k) for k in range(4)] == [
        "trade 123456 at row 1",
        "trade 123456 at row 1",
        "trade 123457 at row 2",
        "trade 123456 at row 3",
    ]
    assert (
        refused(
            NG, {**ID_TICKET, "contract_code": ["Z26-F27", "F27", "Z26"], "quantity": [1, 2.5, 1]}
        )
        == "quantity of trade 123457 at row 2 is 2.5, expected a whole number"
    )


# --- compound payment rules, compound-date-offsets.md --------------------------------------------

# The ticket's fixture: a financial futures index whose V26 expires Friday 9 October 2026, the
# anchor under lastday, X26 a month on; a payment calendar of weekdays and no holiday.
CHAIN = an_index(
    "chain",
    (("U26", "2026-09-09"), ("V26", "2026-10-09"), ("X26", "2026-11-09")),
    holidays=(),
    lots=(("TOY", 10_000.0, "MMBTU"),),
)
WEEKDAYS_ONLY = holiday_calendar(dates())


def chained(
    rows: list[tuple[str, str]],
    template_rule: str | None = None,
    calendars: tuple[HolidayCalendar, ...] | None = None,
) -> tuple[Trades, WorkCounter]:
    """A batch on CHAIN of one lot per row, each row its code and, unless the template gives one
    rule for all, its own payment rule, on the weekday calendar unless each row's is given."""
    ticket: dict[str, list[object]] = {
        "trade_id": list(range(1, len(rows) + 1)),
        "trade_date": ["2026-09-24"] * len(rows),
        "contract_code": [code for code, _ in rows],
        "quantity": [1] * len(rows),
        "fixed_price": [3.0] * len(rows),
    }
    template: dict[str, object] = {**TOY_TEMPLATE, "payment_holiday_calendar": WEEKDAYS_ONLY}
    if template_rule is None:
        del template["payment_time_lag"]
        ticket["payment_time_lag"] = [rule for _, rule in rows]
    else:
        template["payment_time_lag"] = template_rule
    if calendars is not None:
        del template["payment_holiday_calendar"]
        ticket["payment_holiday_calendar"] = list(calendars)
    return created(CHAIN, ticket, template)


def paid_on(batch: Trades) -> NDArray[np.datetime64]:
    assert batch.resolved.payment is not None
    return batch.resolved.payment.date


def test_the_compound_tickets_payment_rules_on_the_chain_fixture() -> None:
    # +1bd and +3cd both pay Monday 12 October from Friday the 9th and are one group; +4cd pays
    # Tuesday the 13th, a group of its own; the rules are kept as written, and three rules over
    # one calendar are three instructions applied.
    batch, counter = chained([("V26", "+1bd"), ("V26", "+3cd"), ("V26", "+4cd")])
    assert batch.resolved.payment is not None
    assert batch.resolved.payment.lag == ("+1bd", "+3cd", "+4cd")
    np.testing.assert_array_equal(paid_on(batch), dates("2026-10-12", "2026-10-12", "2026-10-13"))
    np.testing.assert_array_equal(batch.encoded.payment_date, dates("2026-10-12", "2026-10-13"))
    np.testing.assert_array_equal(batch.encoded.group_contract, [1, 1])
    counts = counter.freeze().as_dict()
    assert counts["payment_rules_read"] == 3 and counts["payment_shifts"] == 3
    # The month's end, Saturday the 31st, back to Friday the 30th and on to Monday 2 November.
    np.testing.assert_array_equal(
        paid_on(chained([("V26", "+0em-1bd+1bd")])[0]), dates("2026-11-02")
    )
    # +1cd lands on Saturday the 10th and is kept there: no roll is added at the end of a rule.
    np.testing.assert_array_equal(paid_on(chained([("V26", "+1cd")])[0]), dates("2026-10-10"))
    # +1bd-1bd comes back to the anchor and pays on the last observation, which the kernel refuses
    # as it always has; the utility may make that day, a payment may not.
    with pytest.raises(ValueError) as early:
        chained([("V26", "+1bd-1bd")])
    assert str(early.value) == (
        "V26 pays on 2026-10-09, expected a day after its last observation, 2026-10-09, when its "
        "final price exists"
    )


def test_rules_and_calendars_vary_by_row_and_a_strip_applies_its_rule_per_component() -> None:
    # Row a's calendar closes the Monday, so its +1bd pays the Tuesday; rows b and c pay the
    # Monday by +3cd and by +1bd on the open calendar, one group; three groups of rule and
    # calendar, three instructions applied.
    closed_monday = holiday_calendar(dates("2026-10-12"))
    batch, counter = chained(
        [("V26", "+1bd"), ("V26", "+3cd"), ("V26", "+1bd")],
        calendars=(closed_monday, WEEKDAYS_ONLY, WEEKDAYS_ONLY),
    )
    np.testing.assert_array_equal(paid_on(batch), dates("2026-10-13", "2026-10-12", "2026-10-12"))
    np.testing.assert_array_equal(batch.encoded.payment_date, dates("2026-10-12", "2026-10-13"))
    counts = counter.freeze().as_dict()
    assert counts["payment_rules_read"] == 2 and counts["payment_shifts"] == 3
    # A strip applies the chain to each component's own anchor: V26's 9 October to the month's
    # end and the business day after, 2 November; X26's 9 November to 30 November and 1 December.
    strip, counter = chained([("V26-X26", "+0em+1bd")])
    np.testing.assert_array_equal(paid_on(strip), dates("2026-11-02", "2026-12-01"))
    counts = counter.freeze().as_dict()
    assert counts["payment_rules_read"] == 1 and counts["payment_shifts"] == 2
    # The rule in the template or in the ticket makes the same days; a row repeated is two
    # occurrences of one group; each row alone pays what it pays in the batch.
    rows = [
        ("V26", "+1bd"),
        ("V26", "+3cd"),
        ("V26", "+4cd"),
        ("V26", "+0em-1bd+1bd"),
        ("V26", "+1cd"),
    ]
    batch, _ = chained(rows)
    for k, (code, rule) in enumerate(rows):
        np.testing.assert_array_equal(
            paid_on(chained([(code, rule)])[0]), paid_on(batch)[k : k + 1]
        )
    templated, _ = chained([("V26", ""), ("X26", "")], template_rule="+0em-1bd+1bd")
    ticketed, _ = chained([("V26", "+0em-1bd+1bd"), ("X26", "+0em-1bd+1bd")])
    np.testing.assert_array_equal(paid_on(templated), paid_on(ticketed))
    np.testing.assert_array_equal(paid_on(templated), dates("2026-11-02", "2026-11-30"))
    twice, _ = chained([("V26", "+0EM-1bd+1BD"), ("V26", "+0EM-1bd+1BD")])
    assert twice.resolved.payment is not None
    assert twice.resolved.payment.lag == ("+0EM-1bd+1BD", "+0EM-1bd+1BD")  # as written, each
    np.testing.assert_array_equal(twice.encoded.payment_date, dates("2026-11-02"))
    assert twice.encoded.slot_group.size == 1


def test_a_rule_that_leaves_the_sheet_names_the_first_offending_row_in_ticket_order() -> None:
    # Row 1's rule reaches the sheet's last day exactly from V26's 9 October; row 3 shares that
    # rule on a calendar of its own and strays from X26's anchor a month on; row 2 strays by a
    # rule of its own. The groups are made rule by rule, so row 3's is made before row 2's, and
    # the refusal still names row 2, the first offending row of the ticket.
    cal_x, cal_y, cal_z = (
        holiday_calendar(dates(closed)) for closed in ("2026-10-12", "2026-10-13", "2026-10-14")
    )
    with pytest.raises(ValueError) as strayed:
        chained(
            [("V26", "+2912161cd"), ("V26", "+9999999cd"), ("X26", "+2912161cd")],
            calendars=(cal_x, cal_y, cal_z),
        )
    assert str(strayed.value) == (
        "payment_time_lag row 2 is '+9999999cd', counted from 2026-10-09 to 29405-11-03, expected "
        "a payment day within the sheet's calendar, 1900-03-01 to 9999-12-31"
    )
    exact, _ = chained([("V26", "+2912161cd")])
    np.testing.assert_array_equal(paid_on(exact), dates("9999-12-31"))


def test_an_iferc_chain_counts_from_last_trading_and_may_not_pay_on_publication_day() -> None:
    # Z26's last trading day is Monday 30 November and its index prints on 1 December: +0em+2bd
    # is the month's end, the 30th itself, and two business days on, 2 December; +3cd is 3
    # December, the day +3bd pays, so the two are one group; +1cd is the publication day, refused
    # by the existing rule, since the final price does not exist until that day is done.
    chain, _ = created(WAHA, WAHA_TICKET, {**WAHA_TEMPLATE, "payment_time_lag": "+0em+2bd"})
    np.testing.assert_array_equal(paid_on(chain), dates("2026-12-02"))
    np.testing.assert_array_equal(chain.encoded.slot_date, dates("2026-12-01"))
    pair, _ = created(
        WAHA,
        {
            "trade_id": [12, 19],
            "trade_date": ["2026-11-30", "2026-11-30"],
            "contract_code": ["Z26", "Z26"],
            "quantity": [1, -1],
            "fixed_price": [-0.50, -0.50],
            "payment_time_lag": ["+3bd", "+3cd"],
        },
        {key: value for key, value in WAHA_TEMPLATE.items() if key != "payment_time_lag"},
    )
    assert pair.resolved.payment is not None
    assert pair.resolved.payment.lag == ("+3bd", "+3cd")
    np.testing.assert_array_equal(pair.encoded.payment_date, dates("2026-12-03"))
    assert refused(WAHA, WAHA_TICKET, {**WAHA_TEMPLATE, "payment_time_lag": "+1cd"}) == (
        "Z26 pays on 2026-12-01, expected a day after its last observation, 2026-12-01, when its "
        "final price exists"
    )


# --- half-year strips, half-year-strips.md --------------------------------------------------------

# A financial one-unit index with every month from November 2026 to July 2028, X26 the boundary,
# each contract expiring on the last weekday on or before the 25th of its month, a payment calendar
# of weekdays and no holiday; a cleared lastday template a lot a month at +2bd.
HALF_LETTERS = "FGHJKMNQUVXZ"
HALF = an_index(
    "HALF",
    tuple(
        (
            f"{HALF_LETTERS[(month - 1) % 12]}{str(2026 + (month - 1) // 12)[2:]}",
            str(
                np.busday_offset(
                    f"{2026 + (month - 1) // 12}-{(month - 1) % 12 + 1:02d}-25", 0, roll="backward"
                )
            ),
        )
        for month in range(11, 32)
    ),
    holidays=(),
    lots=(("LOT", 1.0, "MMBTU"),),
)
HALF_TEMPLATE: dict[str, object] = {
    **TOY_TEMPLATE,
    "quantity_unit": "LOT",
    "payment_holiday_calendar": holiday_calendar(dates()),
}


def half_rows(*codes: str, quantity: float = 1.0) -> dict[str, list[object]]:
    return {
        "trade_id": [3001 + k for k in range(len(codes))],
        "trade_date": ["2026-12-01"] * len(codes),
        "contract_code": list(codes),
        "quantity": [quantity] * len(codes),
        "fixed_price": [3.0] * len(codes),
    }


def test_a_half_year_is_its_six_months_as_a_strip_of_them_is() -> None:
    # 1H27 in either case resolves to F27 through M27, one occurrence and six components with the
    # dates, payment days and exposures of the F27-M27 strip and of six monthly rows; the entered
    # code is kept as typed; H27 alone stays March, one component.
    half, counter = created(HALF, half_rows("1h27"), HALF_TEMPLATE)
    strip, _ = created(HALF, half_rows("F27-M27"), HALF_TEMPLATE)
    months, _ = created(HALF, half_rows("F27", "G27", "H27", "J27", "K27", "M27"), HALF_TEMPLATE)
    strip_payment = strip.resolved.payment
    assert strip_payment is not None
    for batch in (half, strip, months):
        terms = batch.resolved
        assert terms.payment is not None
        np.testing.assert_array_equal(
            terms.contract, HALF.schedule.codes.index("F27") + np.arange(6)
        )
        np.testing.assert_array_equal(
            terms.start_date, dates(*(f"2027-{m:02d}-01" for m in range(1, 7)))
        )
        np.testing.assert_array_equal(
            terms.end_date,
            dates(
                "2027-01-31", "2027-02-28", "2027-03-31", "2027-04-30", "2027-05-31", "2027-06-30"
            ),
        )
        np.testing.assert_array_equal(terms.payment.date, strip_payment.date)
        np.testing.assert_array_equal(batch.encoded.quote_quantity, half.encoded.quote_quantity)
        np.testing.assert_array_equal(batch.encoded.offset, half.encoded.offset)
        np.testing.assert_array_equal(batch.encoded.slot_date, half.encoded.slot_date)
        np.testing.assert_array_equal(batch.encoded.payment_date, half.encoded.payment_date)
    np.testing.assert_array_equal(half.resolved.occurrence, [0] * 6)
    np.testing.assert_array_equal(months.resolved.occurrence, np.arange(6))
    assert half.code_entered.tolist() == [True]
    assert counter.freeze()["resolved_components"] == 6
    assert counter.freeze()["resolved_occurrences"] == 1
    march, _ = created(HALF, half_rows("H27"), HALF_TEMPLATE)
    np.testing.assert_array_equal(march.resolved.start_date, dates("2027-03-01"))
    np.testing.assert_array_equal(march.resolved.end_date, dates("2027-03-31"))
    second, _ = created(HALF, half_rows("2H27"), HALF_TEMPLATE)
    np.testing.assert_array_equal(
        second.resolved.start_date, dates(*(f"2027-{m:02d}-01" for m in range(7, 13)))
    )
    twice, _ = created(HALF, half_rows("1H27", "1h27"), HALF_TEMPLATE)
    assert twice.resolved.occurrence.size == 12  # a repeat is counted again
    np.testing.assert_array_equal(twice.resolved.occurrence, [0] * 6 + [1] * 6)


def test_a_half_year_per_calendar_day_covers_its_days_and_a_missing_month_is_refused() -> None:
    # One lot a calendar day: 181 for the first half of 2027, 184 for the second, 182 for the leap
    # first half of 2028, each component its month's days.
    for code, total, days in (
        ("1H27", 181, [31, 28, 31, 30, 31, 30]),
        ("2H27", 184, [31, 31, 30, 31, 30, 31]),
        ("1H28", 182, [31, 29, 31, 30, 31, 30]),
    ):
        batch, _ = created(HALF, half_rows(code), {**HALF_TEMPLATE, "quantity_per": "calday"})
        np.testing.assert_array_equal(batch.resolved.covered_days, days)
        np.testing.assert_array_equal(batch.resolved.component_quantity, days)
        assert float(batch.resolved.component_quantity.sum()) == total
    # A half whose months the schedule lacks is refused as a strip is, naming the first missing:
    # the toy has X26 through G27, so March is the first month of 1H27 it has no contract for.
    assert refused(HALF, half_rows("2H28"), HALF_TEMPLATE) == (
        "contract_code row 1 is '2H28', expected months the index's schedule has a contract for; "
        "it has none for 2028-08"
    )
    assert refused(
        TOY, half_rows("1H27"), {**TOY_TEMPLATE, "payment_holiday_calendar": PAYMENT_CALENDAR}
    ) == (
        "contract_code row 1 is '1H27', expected months the index's schedule has a contract for; "
        "it has none for 2027-03"
    )
    assert refused(HALF, half_rows("3H27"), HALF_TEMPLATE) == (
        "contract_code row 1 is '3H27', expected a contract or strip with two-digit years, such as "
        "F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
    )


def test_an_asian_half_observes_each_month_on_its_own_days_as_the_strip_does() -> None:
    # The asian method averages each component's month on its own pricing days: a half is six
    # months of observations, not one averaging period, the same days and weights as F27-M27.
    template = {**HALF_TEMPLATE, "schedule_method": "asian"}
    half, _ = created(HALF, half_rows("1h27"), template)
    strip, _ = created(HALF, half_rows("F27-M27"), template)
    np.testing.assert_array_equal(half.encoded.observations.date, strip.encoded.observations.date)
    np.testing.assert_array_equal(
        half.encoded.observations.weight, strip.encoded.observations.weight
    )
    np.testing.assert_array_equal(half.encoded.slot_date, strip.encoded.slot_date)
    np.testing.assert_array_equal(half.encoded.payment_date, strip.encoded.payment_date)
    payment_dates = half.encoded.payment_date
    assert payment_dates is not None
    assert payment_dates.size == 6  # one payment per month, as the strip's


# --- a combined payment calendar, combine-holiday-calendars.md ------------------------------------


# A one-unit index whose X26 stops trading on Friday 9 October 2026, the ticket's anchor, behind a
# boundary contract; the ticket's synthetic calendars A and B, and their combination.
ANCHORED = an_index(
    "ANCHORED",
    (("U26", "2026-08-27"), ("V26", "2026-09-28"), ("X26", "2026-10-09")),
    holidays=(),
    lots=(("LOT", 1.0, "MMBTU"),),
)
CALENDAR_A = holiday_calendar(dates("2026-10-14", "2026-10-12", "2026-10-14"))
CALENDAR_B = holiday_calendar(dates("2026-10-13", "2026-10-14"))


def anchored_payment(calendar: HolidayCalendar, lag: str = "+1bd") -> str:
    batch, _ = created(
        ANCHORED,
        {
            "trade_id": [4001],
            "trade_date": ["2026-10-01"],
            "contract_code": ["X26"],
            "quantity": [1.0],
            "fixed_price": [3.0],
        },
        {
            **TOY_TEMPLATE,
            "quantity_unit": "LOT",
            "payment_time_lag": lag,
            "payment_holiday_calendar": calendar,
        },
    )
    assert batch.resolved.payment is not None
    assert batch.resolved.payment.date.size == 1
    return str(batch.resolved.payment.date[0])


def test_a_payment_steps_over_every_combined_calendars_holidays() -> None:
    # From the Friday anchor, the weekend and the three listed weekdays are closed on the combined
    # calendar, so +1bd pays Thursday 15 October, as a calendar listing the union pays; on A alone
    # the Tuesday, on B alone the Monday, and on no holidays at all the Monday.
    combined = combine_holiday_calendars((CALENDAR_A, CALENDAR_B), WorkCounter())
    assert anchored_payment(combined) == "2026-10-15"
    assert anchored_payment(holiday_calendar(dates("2026-10-12", "2026-10-13", "2026-10-14"))) == (
        "2026-10-15"
    )
    assert anchored_payment(combined, "+2bd") == "2026-10-16"
    assert anchored_payment(CALENDAR_A) == "2026-10-13"
    assert anchored_payment(CALENDAR_B) == "2026-10-12"
    assert anchored_payment(holiday_calendar(dates())) == "2026-10-12"
