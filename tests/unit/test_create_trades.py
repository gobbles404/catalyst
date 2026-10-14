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
    measure: tuple[str, str] = ("ENERGY", "MMBTU"),
) -> Index:
    codes = tuple(code for code, _ in contracts)
    schedule = futures_schedule(codes, dates(*(expiry for _, expiry in contracts)), None)
    names = tuple(name for name, _, _ in lots)
    return index(
        name,
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
    assert terms.labels == ("NG-001", "NG-002", "NG-003", "NG-004", "NG-001")
    assert terms.clearing_house == ("CME Clearing",) * 5  # the template's, for every row
    assert terms.broker is None
    np.testing.assert_array_equal(
        terms.trade_dates,
        dates("2026-09-24", "2026-09-24", "2026-09-25", "2026-09-25", "2026-09-24"),
    )
    np.testing.assert_array_equal(terms.occurrence, [0, 1, 2, 3, 4])
    np.testing.assert_array_equal(terms.contract, [1, 1, 2, 2, 1])  # Z26 and F27 by row
    np.testing.assert_array_equal(terms.quantity, [10, -4, 7, -12, 10])
    np.testing.assert_array_equal(terms.fixed_price, [3.1, 3.15, 3.4, 3.35, 3.1])
    assert terms.payment is None
    assert batch.encoded.terms is terms
    np.testing.assert_array_equal(
        batch.encoded.quote_quantity, [100_000, -40_000, 70_000, -120_000, 100_000]
    )
    np.testing.assert_array_equal(
        batch.encoded.offset, [-310_000, 126_000, -238_000, 402_000, -310_000]
    )
    np.testing.assert_array_equal(batch.encoded.groups, [1, 2])
    np.testing.assert_array_equal(batch.encoded.slot_exposure, [160_000, -50_000])
    np.testing.assert_array_equal(batch.encoded.slot_date, dates("2026-11-25", "2026-12-29"))
    assert counter.freeze().as_dict() == {
        "encoded_components": 5,
        "encoded_observations": 5,
        "encoded_slots": 2,
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
    np.testing.assert_array_equal(terms.quantity, [3, 3, -1])  # the strip's lots in every month
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
    # Each contract expires on the last business day on or before the 25th of its month, so that
    # every expiry is a day the market is open, which the encoding requires of an observation.
    contracts = tuple(
        (
            f"{letters[int(m.astype(int)) % 12]}{str(m)[2:4]}",
            str(
                np.busday_offset(m.astype("datetime64[D]") + np.timedelta64(24, "D"), 0, "backward")
            ),
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
    np.testing.assert_array_equal(batch.encoded.quote_quantity, np.full(12, 20_000.0))
    assert batch.encoded.slot_exposure.size == 12  # one slot per month, on its expiry


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
    np.testing.assert_array_equal(terms.quantity, [2, 2, 2])
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
        "pay",
        (("X26", "2026-10-28"), ("Z26", expiry)),
        holidays=(),  # the market is open on the expiry; the payment calendar may not be
        lots=(("TOY", 10_000.0, "MMBTU"),),
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
        "trade_id": ["p"],
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
    # Representability and no term of business: a day past 31 December 9999 could reach no cell,
    # so the lag that would pay there is refused naming the lag, the anchor and the day, with
    # the row when the ticket supplied it, and the longest lag that still pays on the last day
    # is taken: from Z26's 25 November 2026 that is 2,080,082 business days on an open calendar.
    # A lag beyond the sheet's whole calendar, 2,113,146 business days, is refused by the grammar
    # before any day is counted, so no number overflows the arithmetic unnamed.
    assert payment_refusal("+2100000bd") == (
        "payment_time_lag is '+2100000bd', counted from 2026-11-25 to 10076-05-06, "
        "expected a payment day on or before 9999-12-31, the last a sheet can show"
    )
    assert payment_refusal("+2100000bd", in_ticket=True) == (
        "payment_time_lag row 1 is '+2100000bd', counted from 2026-11-25 to 10076-05-06, "
        "expected a payment day on or before 9999-12-31, the last a sheet can show"
    )
    assert payment_refusal("+99999999999999999999bd", in_ticket=True) == (
        "payment_time_lag row 1 is '+99999999999999999999bd', expected at most 2,113,146 business "
        "days, the sheet's calendar from 1900-03-01 to 9999-12-31 end to end"
    )
    long_lag = "+" + "9" * 4301 + "bd"  # fits a cell, and would fail Python's own conversion
    bound = (
        "expected at most 2,113,146 business days, the sheet's calendar from 1900-03-01 to "
        "9999-12-31 end to end"
    )
    assert payment_refusal(long_lag) == f"payment_time_lag is {long_lag!r}, {bound}"
    assert (
        payment_refusal(long_lag, in_ticket=True)
        == f"payment_time_lag row 1 is {long_lag!r}, {bound}"
    )
    longest = int(np.busday_count(day("2026-11-25"), day("9999-12-31")))
    assert longest == 2_080_082
    assert one_payment_day("2026-11-25", (), f"+{longest}bd") == day("9999-12-31")
    assert payment_refusal(f"+{longest + 1}bd") == (
        "payment_time_lag is '+2080083bd', counted from 2026-11-25 to 10000-01-03, "
        "expected a payment day on or before 9999-12-31, the last a sheet can show"
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
            "trade_id": ["a", "b"],
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
    np.testing.assert_array_equal(payment.lag_days, [1, 3])
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
        "trade_id": [f"p{i}" for i in range(len(codes))],
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
            "trade_id": ["p"],
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
        "trade_id": ["q"],
        "trade_date": ["2026-09-24"],
        "contract_code": [code],
        "quantity": [quantity],
        "fixed_price": [3.0],
    }
    return {**ticket, "quantity_unit": [unit]} if unit is not None else ticket


WITHOUT_UNIT = {name: value for name, value in NG_TEMPLATE.items() if name != "quantity_unit"}


def quote_quantity(ix: Index, unit: str, quantity: float = 2.0, code: str = "Z26") -> float:
    batch, _ = created(ix, one_row(quantity, code), {**NG_TEMPLATE, "quantity_unit": unit})
    assert batch.resolved.specification == ix.specifications.names.index(unit)
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
    assert with_both.resolved.specification == 1
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


def test_the_unit_in_the_ticket_names_its_row_and_must_agree_on_every_row() -> None:
    template = {name: value for name, value in NG_TEMPLATE.items() if name != "quantity_unit"}
    batch, _ = created(TWO_LOTS, {**NG_TICKET, "quantity_unit": ["ICE PHH"] * 5}, template)
    assert batch.resolved.specification == 1
    np.testing.assert_array_equal(
        batch.encoded.quote_quantity, [25_000, -10_000, 17_500, -30_000, 25_000]
    )
    assert refused(TWO_LOTS, {**NG_TICKET, "quantity_unit": ["ICE NG"] * 5}, template) == (
        "quantity_unit row 1 is 'ICE NG', expected one of the index's specifications: "
        "'NYMEX NG', 'ICE PHH', 'MMBTU'"
    )
    mixed: list[object] = ["NYMEX NG", "ICE PHH", "NYMEX NG", "NYMEX NG", "NYMEX NG"]
    assert refused(TWO_LOTS, {**NG_TICKET, "quantity_unit": mixed}, template) == (
        "quantity_unit row 2 is 'ICE PHH', expected 'NYMEX NG' as at row 1; "
        "a batch has one quantity_unit"
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
        ).startswith("quantity of trade 'q' at row 1 is ")


def test_the_old_field_is_unknown_to_the_definition() -> None:
    assert "contract_specification" not in {field.name for field in FUTURE.fields}
    with pytest.raises(StopIteration):
        typed(FUTURE, "contract_specification", ["NYMEX NG"])


# --- a quantity of zero: a row kept ready --------------------------------------------------------
# zero-quantities.md: a numeric zero quantity, from the template or the ticket, is a count like
# any other, the row kept with its label, its code and its amounts of nothing.

ENTRY_TICKET: dict[str, list[object]] = {
    "trade_id": ["NG-001", "ENTRY-002"],
    "trade_date": ["2026-10-06", "2026-10-06"],
    "contract_code": ["Z26", "F27"],
    "quantity": [2, 0],
    "fixed_price": [3.0, 3.3],
}


def test_a_zero_quantity_in_the_ticket_is_kept_with_its_row() -> None:
    batch, counter = created(NG, ENTRY_TICKET)
    terms = batch.resolved
    assert terms.labels == ("NG-001", "ENTRY-002")
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
    assert batch.encoded.groups.tolist() == [1, 2]  # both contracts held, at nothing
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
        "quantity of trade 'ENTRY-002' at row 2 is 0.5, expected a whole number"
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
            {**NG_TEMPLATE, "schedule_method": "asian"},
            "schedule_method is 'asian', expected lastday or penultimate, the two methods built",
        ),
        (
            NG_TICKET,
            {**NG_TEMPLATE, "schedule_method": "penultimate"},
            "settlement_method is 'physical', expected 'financial' with the penultimate method; a"
            " penultimate future is cash settled on the business day before its contract's expiry",
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
            "quantity of trade 'NG-003' at row 3 is 7.5, expected a whole number",
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
    assert message == "quantity of trade 'S2' at row 2 is 2.5, expected a whole number"


def test_two_lags_for_one_contract_are_refused_by_the_trade_and_the_contract() -> None:
    template = {k: v for k, v in TOY_TEMPLATE.items() if k != "payment_time_lag"}
    message = refused(
        TOY,
        {**NG_TICKET, "payment_time_lag": ["+2bd", "+3bd", "+2bd", "+2bd", "+2bd"]},
        template,
    )
    assert message == (
        "Z26 pays on 2026-11-30 for trade 'NG-001' at row 1 and on 2026-12-01 for trade 'NG-002"
        "' at row 2, expected one payment day per contract"
    )
    # The page's case: four rows of J27 at +2bd and one at +3bd. Both days are named with their
    # rows and neither is held to be the right one; the desk decides which terms to change.
    four = refused(
        an_index(
            "J27",
            (("X26", "2026-10-28"), ("J27", "2027-03-29")),
            lots=(("TOY", 10_000.0, "MMBTU"),),
        ),
        {
            "trade_id": ["R1", "R2", "R3", "R4"],
            "trade_date": ["2026-09-24"] * 4,
            "contract_code": ["J27"] * 4,
            "quantity": [1, 1, 1, 1],
            "fixed_price": [3.0] * 4,
            "payment_time_lag": ["+2bd", "+2bd", "+2bd", "+3bd"],
        },
        template,
    )
    assert four == (
        "J27 pays on 2027-03-31 for trade 'R1' at row 1 and on 2027-04-01 for trade 'R4' at row 4, "
        "expected one payment day per contract"
    )


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
        "payment_time_lag": ["+2BD", "+0bd", "+2bd", "+2bd", "+2bd"],
    }
    assert refused(TOY, lags, template) == (
        "payment_time_lag row 1 is '+2BD', expected a positive whole number of business days, "
        "such as +1bd"
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
        "schedule_method": ["asian"] * 5,
    }
    assert refused(NG, asian, without) == (
        "schedule_method row 1 is 'asian', expected lastday or penultimate, the two methods built"
    )
    assert refused(NG, NG_TICKET, {**NG_TEMPLATE, "route": "Cleared"}) == (
        "route is 'Cleared', expected cleared or bilateral"
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
    assert batch.encoded.groups.size == len({code.upper() for code, _, _ in rows})


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
    np.testing.assert_array_equal(batch.encoded.slot_exposure, [160_000, -50_000])
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
        "#ERROR _CreateTrades: ValueError: quantity of trade 'a' at row 1 is 2.5, "
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
        "Z26",
        "lastday",
        "cleared",
        "physical",
        "CME Clearing",
        10.0,
        "NYMEX NG",
        "month",
        3.1,
        100_000.0,
        100_000.0,
        -310_000.0,
    ]
    assert table[2] == first
    assert table[3][3] == "Z26"  # the schedule's spelling, where the ticket typed z26
    assert table[6] == [5.0, *first[1:]]  # the repeated row, a trade of its own
    assert len(table) == 7


def test_the_spill_shows_the_batchs_facts_wherever_they_came_from(sheet: dict[str, Any]) -> None:
    # The route and the settlement from the ticket's columns, the template holding neither: the
    # spill is the one place both are read back.
    template = ENTRY["_CreateTradeTemplate"](
        "future",
        row("quantity_unit", "quantity_per", "schedule_method"),
        row("NYMEX NG", "month", "lastday"),
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
    assert table[0][:3] == ["row", "trade_date", "contract_code"]
    assert "trade_id" not in table[0] and "clearing_house" not in table[0]
    assert [line[4] for line in table[2:]] == ["bilateral", "bilateral"]
    assert [line[5] for line in table[2:]] == ["physical", "physical"]
    assert [line[7] for line in table[2:]] == ["NYMEX NG", "NYMEX NG"]  # the unit, the template's


def test_a_financial_batchs_spill_carries_its_payment_terms(sheet: dict[str, Any]) -> None:
    template = ENTRY["_CreateTradeTemplate"](
        "future",
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
        "quote_quantity",
        "coefficient",
        "offset",
    ]
    assert [line[0] for line in table[2:]] == [1.0, 1.0]
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
        cells(["NG-001", 46301.0, "Z26", 2.0, 3.0], ["ENTRY-002", 46301.0, "F27", 0.0, 3.3]),
        sheet["template"],
    )
    table = spilled(handle)
    assert len(table) == 4  # two heading rows and both components, the second kept at nothing
    assert table[3][:4] == [2.0, "ENTRY-002", 46301.0, "F27"]
    assert table[3][8] == 0.0 and table[3][12:] == [0.0, 0.0, 0.0]
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
                cells(["a", 46301.0, "Z26", cell, 3.0]),
                sheet["template"],
            )
        )
        assert message.startswith(
            f"#ERROR _CreateTrades: trade_rows cell (1, 4) is {words}, expected number"
        ), message
