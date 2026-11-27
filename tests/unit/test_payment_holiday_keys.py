"""A payment calendar chosen by key, payment-calendar-keys.md: the ticket's worked dates by hand,
a key of one name and of two joined by a plus sign, from the ticket and from the template; the
key's form and the names the collection lacks, refused naming the field and the first row that
holds them; a key required on every financially settled row, a row paying on a stated date
included, and refused on a physical one; the pair and the spread; the quote template's bound
calendar through direct quotes, dated quotes and a request; and the creators on the sheet. Each
test gives its own collection; every expected day and price is hand arithmetic here.
docs/library/trades/create-trades.md is the page."""

import re
from collections.abc import Mapping
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray
from test_bilateral_kernel import CLOSE
from test_create_trades import TOY, a_template, a_ticket
from test_float_float import F27 as SPREAD_F27
from test_float_float import LIFECYCLE as SPREAD_LIFECYCLE
from test_float_float import NTO, PAN
from test_rfq import DEFAULT_PRICE, EXPLICIT_PRICE, MARKET, RATES, price, request
from test_trades import dates, day
from test_two_index import F27 as PAIR_F27
from test_two_index import LIFECYCLE as PAIR_LIFECYCLE
from test_two_index import PID, A, B, across, down, grid, serial, the_sheet, under

from catalyst.excel import bridge
from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.holiday_calendar import combine_holiday_calendars, holiday_calendar
from catalyst.index_definitions.holiday_calendars import (
    HolidayCalendars,
    calendar_key,
    collect_holiday_calendars,
)
from catalyst.index_definitions.index import Index
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT, FLOAT_FLOAT, Instrument
from catalyst.quoting.quote import quote, quote_by_dates
from catalyst.quoting.template import QuoteTemplate, quote_template
from catalyst.trades.resolution import Trades, trades

# --- the ticket's example ------------------------------------------------------------------------
# Synthetic calendars, claiming no market's convention. TOY's Z26 expires on Wednesday 25 November
# 2026, its one lastday observation, and each trade pays +2bd from it.
#   PAY_A, closed Thursday 26:            Friday 27, Monday 30        -> 30 November
#   PAY_B, closed Friday 27 and Monday 30: Thursday 26, Tuesday 1     -> 1 December
#   both, closed 26, 27 and 30:            Tuesday 1, Wednesday 2     -> 2 December
#   PAY_D, closed Friday 27:               Thursday 26, Monday 30     -> 30 November, as PAY_A

PAY_A = holiday_calendar("PAY_A", dates("2026-11-26"))
PAY_B = holiday_calendar("PAY_B", dates("2026-11-27", "2026-11-30"))
PAY_D = holiday_calendar("PAY_D", dates("2026-11-27"))
CALENDARS = collect_holiday_calendars((PAY_A, PAY_B, PAY_D), WorkCounter())
TEMPLATE: dict[str, object] = {
    "quantity_unit": "TOY",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "TEST_CLEARER",
    "payment_day": "+2bd",
}


def rows_of(*keys: str | None, code: str = "Z26") -> dict[str, list[object]]:
    """One row of Z26 per key, a lot bought at 3.00; no key column where the keys are None."""
    n = len(keys)
    ticket: dict[str, list[object]] = {
        "trade_id": list(range(1, n + 1)),
        "trade_date": ["2026-09-24"] * n,
        "contract_code": [code] * n,
        "quantity": [1] * n,
        "fixed_price": [3.0] * n,
    }
    if keys[0] is not None:
        ticket["payment_holiday_key"] = list(keys)
    return ticket


def booked(
    ticket: Mapping[str, list[object]],
    template: Mapping[str, object] = TEMPLATE,
    calendars: HolidayCalendars | None = CALENDARS,
    counter: WorkCounter | None = None,
    indexes: tuple[Index, ...] = (TOY,),
    definition: Instrument = FIXED_FLOAT,
) -> Trades:
    return trades(
        indexes,
        a_ticket(ticket, definition),
        a_template(template, definition),
        UNITS,
        counter or WorkCounter(),
        calendars,
    )


def refused(
    ticket: Mapping[str, list[object]],
    template: Mapping[str, object] = TEMPLATE,
    calendars: HolidayCalendars | None = CALENDARS,
) -> str:
    with pytest.raises(ValueError) as refusal:
        booked(ticket, template, calendars)
    return str(refusal.value)


def paid(batch: Trades) -> list[str]:
    assert batch.resolved.payment is not None
    return [str(each) for each in batch.resolved.payment.date]


def keys_read_back(batch: Trades) -> list[str]:
    """Each row's key as entered, read off the trades readback: its last column, but for a
    fixed_float's fixed price's two units, which stand after it since #273."""
    table = grid(batch)
    at = table[0].index("payment_holiday_key")
    fixed_units = ["fixed_price_currency_unit", "fixed_price_quantity_unit"]
    assert table[0][at + 1 :] in ([], fixed_units) and table[1][at] == "str"
    return [str(key) for key in under(table, "payment_holiday_key")]


def test_the_tickets_four_keys_pay_on_the_days_worked_by_hand() -> None:
    counter = WorkCounter()
    keys = ("PAY_A", "PAY_B", "PAY_A+PAY_B", "PAY_B+PAY_A")
    batch = booked(rows_of(*keys), counter=counter)
    assert paid(batch) == ["2026-11-30", "2026-12-01", "2026-12-02", "2026-12-02"]
    payment = batch.resolved.payment
    assert payment is not None
    one, other, both, again = payment.calendar
    # One name is the collection's calendar itself; two are one combination, whichever order.
    assert one is PAY_A and other is PAY_B and both is again
    assert both.name == "PAY_A+PAY_B"
    np.testing.assert_array_equal(
        both.holiday, combine_holiday_calendars((PAY_A, PAY_B), WorkCounter()).holiday
    )
    assert batch.resolved.payment_holiday_key == keys
    assert keys_read_back(batch) == list(keys)  # as entered, the order of the names kept
    counts = counter.freeze().as_dict()
    # Four distinct key texts bound; one combination of two calendars, their three listed days
    # read and kept; one rule read and applied once on each of the three calendars.
    assert counts["holiday_keys_bound"] == 4
    assert (counts["calendars_combined"], counts["holidays_read"], counts["holidays_kept"]) == (
        2,
        3,
        3,
    )
    assert (counts["payment_rules_read"], counts["payment_shifts"]) == (1, 3)


def test_a_key_from_the_template_pays_as_the_same_key_on_every_row() -> None:
    counter = WorkCounter()
    from_template = booked(
        rows_of(None, None, None),
        {**TEMPLATE, "payment_holiday_key": "PAY_A+PAY_B"},
        counter=counter,
    )
    from_rows = booked(rows_of("PAY_A+PAY_B", "PAY_A+PAY_B", "PAY_A+PAY_B"))
    assert paid(from_template) == paid(from_rows) == ["2026-12-02"] * 3
    assert keys_read_back(from_template) == ["PAY_A+PAY_B"] * 3
    counts = counter.freeze().as_dict()
    assert counts["holiday_keys_bound"] == 1 and counts["calendars_combined"] == 2
    # A thousand rows of one key bind once and combine once: nothing per row.
    many = WorkCounter()
    booked(rows_of(*["PAY_B+PAY_A"] * 1_000), counter=many)
    assert many.freeze().as_dict()["holiday_keys_bound"] == 1
    assert many.freeze().as_dict()["calendars_combined"] == 2
    # The collection's order changes nothing, nor a member no key names.
    reordered = collect_holiday_calendars((PAY_D, PAY_B, PAY_A), WorkCounter())
    assert paid(booked(rows_of("PAY_A", "PAY_B", "PAY_A+PAY_B"), calendars=reordered)) == [
        "2026-11-30",
        "2026-12-01",
        "2026-12-02",
    ]


def test_a_stated_date_is_paid_as_entered_and_still_needs_a_key_the_collection_holds() -> None:
    # 5 December 2026 is a Saturday: a stated date is never rolled, whatever its row's calendar,
    # which is read for nothing. The key is required all the same and must name calendars the
    # collection holds, the owner's rule of 21 November 2026.
    dated = {**TEMPLATE, "payment_day": day("2026-12-05")}
    batch = booked(rows_of("PAY_A", "PAY_B", "PAY_A+PAY_B"), dated)
    assert paid(batch) == ["2026-12-05"] * 3
    assert keys_read_back(batch) == ["PAY_A", "PAY_B", "PAY_A+PAY_B"]
    # A holiday of the row's own calendar is a payment day like any other when it is stated.
    assert paid(booked(rows_of("PAY_A"), {**TEMPLATE, "payment_day": day("2026-11-26")})) == [
        "2026-11-26"
    ]
    assert refused(rows_of("PAY_A", "PAY_C"), dated) == (
        "payment_holiday_key row 2 is 'PAY_C', expected names of the collection's calendars, "
        "'PAY_A', 'PAY_B' and 'PAY_D'; it holds no 'PAY_C'"
    )
    assert refused(rows_of(None), dated) == (
        "payment_holiday_key is missing, expected it when settlement_method = financial"
    )


def test_a_name_the_collection_lacks_is_refused_by_the_first_row_that_holds_it() -> None:
    lacking = (
        "expected names of the collection's calendars, 'PAY_A', 'PAY_B' and 'PAY_D'; it holds no"
    )
    assert refused(rows_of("PAY_A", "PAY_C", "PAY_C")) == (
        f"payment_holiday_key row 2 is 'PAY_C', {lacking} 'PAY_C'"
    )
    assert refused(rows_of("PAY_A", "PAY_B+PAY_C")) == (
        f"payment_holiday_key row 2 is 'PAY_B+PAY_C', {lacking} 'PAY_C'"
    )
    # Exactly, case and all: no folding, no trimming, no nearest name.
    assert refused(rows_of("pay_a")) == f"payment_holiday_key row 1 is 'pay_a', {lacking} 'pay_a'"
    # From the template the field alone is named.
    assert refused(rows_of(None), {**TEMPLATE, "payment_holiday_key": "PAY_C"}) == (
        f"payment_holiday_key is 'PAY_C', {lacking} 'PAY_C'"
    )
    # No fallback to the one calendar of a collection of one.
    alone = collect_holiday_calendars((PAY_A,), WorkCounter())
    assert refused(rows_of("PAY_B"), calendars=alone) == (
        "payment_holiday_key row 1 is 'PAY_B', expected names of the collection's calendars, "
        "'PAY_A'; it holds no 'PAY_B'"
    )
    # A collection of no calendars, which the library can make and the sheet cannot, says so.
    nothing = collect_holiday_calendars((), WorkCounter())
    assert refused(rows_of("PAY_A"), calendars=nothing) == (
        "payment_holiday_key row 1 is 'PAY_A', expected names of the collection's calendars, "
        "none; it holds no 'PAY_A'"
    )


@pytest.mark.parametrize(
    ("key", "reason"),
    [
        ("PAY_A+", "; a name is missing"),
        ("+PAY_B", "; a name is missing"),
        ("PAY_A++PAY_B", "; a name is missing"),
        ("PAY_A + PAY_B", ", each with no whitespace around it"),
        (" PAY_A", ", each with no whitespace around it"),
        ("PAY_A+PAY_A", ", each once; 'PAY_A' is given twice"),
        ("PAY_B+PAY_A+PAY_B", ", each once; 'PAY_B' is given twice"),
    ],
)
def test_a_key_that_is_no_name_or_names_joined_by_a_plus_sign_is_refused(
    key: str, reason: str
) -> None:
    form = "expected a calendar's name, or several joined by '+'"
    assert refused(rows_of("PAY_A", key)) == f"payment_holiday_key row 2 is {key!r}, {form}{reason}"
    with pytest.raises(ValueError) as refusal:
        calendar_key("payment_holiday_key", key)
    assert str(refusal.value) == f"payment_holiday_key is {key!r}, {form}{reason}"
    # A template reads the same form when it is made, before any collection is known.
    with pytest.raises(ValueError) as at_template:
        a_template({**TEMPLATE, "payment_holiday_key": key})
    assert str(at_template.value) == f"payment_holiday_key is {key!r}, {form}{reason}"


def test_the_names_of_a_key_are_a_set_read_once() -> None:
    assert calendar_key("k", "NYFED") == ("NYFED",)
    assert calendar_key("k", "NYFED+LON") == calendar_key("k", "LON+NYFED") == ("LON", "NYFED")
    assert calendar_key("k", "b+a+C") == ("C", "a", "b")  # exact text, sorted as text sorts


def test_a_financial_batch_needs_a_collection_and_a_physical_one_needs_neither() -> None:
    assert refused(rows_of("PAY_A"), calendars=None) == (
        "holiday_calendars is missing, expected a _CollectHolidayCalendars collection, which a "
        "financially settled batch selects a calendar from"
    )
    # No field from both, even to the same value.
    assert refused(rows_of("PAY_A"), {**TEMPLATE, "payment_holiday_key": "PAY_A"}) == (
        "payment_holiday_key is supplied by the template and by the ticket, expected by one of them"
    )
    physical = {
        **{k: v for k, v in TEMPLATE.items() if k != "payment_day"},
        "settlement_method": "physical",
    }
    for calendars in (None, CALENDARS):  # with a collection or without, nothing reads it
        assert booked(rows_of(None), physical, calendars).resolved.payment is None
        assert booked(rows_of(None), physical, calendars).resolved.payment_holiday_key is None
    assert refused(rows_of("PAY_A"), physical) == (
        "payment_holiday_key is 'PAY_A', expected none unless settlement_method = financial"
    )


def test_a_key_is_no_payment_group_and_a_strip_pays_each_month_on_its_rows_calendar() -> None:
    # PAY_A and PAY_D close different days and both reach 30 November: two rows on Z26, two
    # keys, one payment day and so one payment group; PAY_B's row pays 1 December, a second.
    batch = booked(rows_of("PAY_A", "PAY_D", "PAY_B"))
    assert paid(batch) == ["2026-11-30", "2026-11-30", "2026-12-01"]
    np.testing.assert_array_equal(batch.encoded.payment_date, dates("2026-11-30", "2026-12-01"))
    np.testing.assert_array_equal(batch.encoded.group_of_component, [0, 0, 1])
    # A strip repeats its row's key over its months: F27 expires Tuesday 29 December 2026, so
    # +2bd is Thursday 31 December on any of these calendars.
    strip = booked(rows_of("PAY_A+PAY_B", code="Z26-F27"))
    assert paid(strip) == ["2026-12-02", "2026-12-31"]
    assert keys_read_back(strip) == ["PAY_A+PAY_B"] * 2


# --- two legs ------------------------------------------------------------------------------------
# The pair and the spread of F27 pay +2bd from the later observation, Monday 4 January 2027:
# Wednesday the 6th on a calendar open all week, Thursday the 7th where Tuesday the 5th is closed.

WEEK = holiday_calendar("WEEK", dates("2030-01-01"))
JAN_5 = holiday_calendar("JAN_5", dates("2027-01-05"))
TWO_LEGS = collect_holiday_calendars((WEEK, JAN_5), WorkCounter())


@pytest.mark.parametrize(("key", "pays"), [("WEEK", "2027-01-06"), ("WEEK+JAN_5", "2027-01-07")])
def test_a_pair_and_a_spread_pay_on_the_calendar_their_key_selects(key: str, pays: str) -> None:
    pair = booked(
        PAIR_F27, {**PAIR_LIFECYCLE, "payment_holiday_key": key}, TWO_LEGS, indexes=(A, B)
    )
    assert paid(pair) == [pays]
    spread = booked(
        SPREAD_F27,
        {**SPREAD_LIFECYCLE, "payment_holiday_key": key},
        TWO_LEGS,
        indexes=(NTO, PAN),
        definition=FLOAT_FLOAT,
    )
    assert paid(spread) == [pays]
    assert keys_read_back(pair) == keys_read_back(spread) == [key]


# --- the quote template ---------------------------------------------------------------------------
# The request tests' strip on 31 December 2026, January at 1.00 and February at 1.20, paying +5bd
# after each month's last pricing day, Friday 29 January and Friday 26 February 2027. On a
# calendar open all week that is 5 February and 5 March, where the curve stands at 0.99 and 0.97;
# on FIFTHS, closed on those two days, Monday 8 February and Monday 8 March, at 0.98 and 0.96.

FIFTHS = holiday_calendar("FIFTHS", dates("2027-02-05", "2027-03-05"))
QUOTED = collect_holiday_calendars((WEEK, FIFTHS), WorkCounter())


def quote_terms(key: str | None, calendars: HolidayCalendars | None = QUOTED) -> QuoteTemplate:
    values: dict[str, object] = {
        "route": "bilateral",
        "settlement_method": "financial",
        "schedule_method": "asian",
        "quantity_per": "month",
        "settlement_frequency": "monthly",
        "nearby": 1.0,
        "payment_day": "+5bd",
        "discount_curve_key": "SOFR",
    }
    if key is not None:
        values["payment_holiday_key"] = key
    return quote_template(
        a_ticket({name: [value] for name, value in values.items()}), calendars, WorkCounter()
    )


def test_a_quote_template_binds_its_key_once_and_every_quote_under_it_uses_the_calendar() -> None:
    week, fifths, both = quote_terms("WEEK"), quote_terms("FIFTHS"), quote_terms("FIFTHS+WEEK")
    assert week.payment_calendar is WEEK and fifths.payment_calendar is FIFTHS
    assert both.payment_calendar is not None
    assert both.payment_calendar.name == "FIFTHS+WEEK"
    assert quote_terms(None).payment_calendar is None and quote_terms(None, None).values
    counter = WorkCounter()
    quote_template(a_ticket({"payment_holiday_key": ["FIFTHS+WEEK"]}), QUOTED, counter)
    assert counter.freeze().as_dict() == {
        "holiday_keys_bound": 1,
        "calendars_combined": 2,
        "holidays_read": 3,
        "holidays_kept": 3,
    }
    # A request: the ticket's hand prices, 448,200/390,000 paying the 5ths and 443,600/386,000
    # paying the 8ths, and its saved payment days.
    for template, pays, hand in (
        (week, ("2027-02-05", "2027-03-05"), DEFAULT_PRICE),
        (fifths, ("2027-02-08", "2027-03-08"), EXPLICIT_PRICE),
        (both, ("2027-02-08", "2027-03-08"), EXPLICIT_PRICE),
    ):
        saved = request(template=template)
        assert under(grid(saved), "payment_date") == [serial(each) for each in pays]
        assert price(MARKET, saved, RATES) == pytest.approx(hand, **CLOSE)
    # A direct quote of the two months, one a month under `month`, weighed by each payment's
    # factor: (0.99 x 1.00 + 0.97 x 1.20) / 1.96 and (0.98 x 1.00 + 0.96 x 1.20) / 1.94.
    for template, hand in ((week, 2.154 / 1.96), (fifths, 2.132 / 1.94), (both, 2.132 / 1.94)):
        direct = quote(MARKET, "F27-G27", template, "flat", RATES, WorkCounter())
        assert direct == pytest.approx(hand, **CLOSE)
        # The same two months by their dates, 1 January to 28 February 2027.
        by_dates = quote_by_dates(
            MARKET, day("2027-01-01"), day("2027-02-28"), template, "flat", RATES, WorkCounter()
        )
        assert by_dates == pytest.approx(hand, **CLOSE)


def test_a_quote_template_refuses_a_key_it_cannot_bind() -> None:
    with pytest.raises(ValueError) as lacking:
        quote_terms("WEEK+TOK")
    assert str(lacking.value) == (
        "payment_holiday_key is 'WEEK+TOK', expected names of the collection's calendars, "
        "'WEEK' and 'FIFTHS'; it holds no 'TOK'"
    )
    with pytest.raises(ValueError) as none:
        quote_terms("WEEK", None)
    assert str(none.value) == (
        "holiday_calendars is missing, expected a _CollectHolidayCalendars collection, which "
        "payment_holiday_key selects a calendar from"
    )


# --- the creators on the sheet --------------------------------------------------------------------


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    """The pair test's sheet for its futures index A, whose G27 expires Wednesday 27 January
    2027; two named calendars, OPEN closed on no day near it and JAN_28 closed the day after
    it, their collection, and a cleared financial template paying +2bd with no key of its own."""
    cells = the_sheet()
    create = bridge.entry("_CreateHolidayCalendar")
    cells["open"] = create("OPEN", serial("2030-01-01"))
    cells["jan_28"] = create("JAN_28", serial("2027-01-28"))
    cells["calendars"] = bridge.entry("_CollectHolidayCalendars")(
        down(cells["open"], cells["jan_28"])
    )
    fields: dict[str, object] = {
        "quantity_unit": "NYMEX NG",
        "quantity_per": "month",
        "settlement_frequency": "monthly",
        "nearby": 1.0,
        "schedule_method": "lastday",
        "route": "cleared",
        "settlement_method": "financial",
        "clearing_house": "TEST_CLEARER",
        "payment_day": "+2bd",
    }
    cells["keyless"] = bridge.entry("_CreateTradeTemplate")(
        "fixed_float", across(*fields), across(*fields.values())
    )
    cells["key_headers"] = across(
        "trade_id", "trade_date", "contract_code", "quantity", "fixed_price", "payment_holiday_key"
    )
    return cells


def spilled(handle: object) -> list[list[object]]:
    kinds, slots, text = cast(
        tuple[NDArray[np.uint8], NDArray[np.float64], str],
        bridge.entry("util_ReadHandle")(handle),
    )
    texts = iter(text.split("\0"))
    return [
        [
            next(texts) if kinds[r, c] == bridge.TEXT_CODE else slots[r, c]
            for c in range(kinds.shape[1])
        ]
        for r in range(kinds.shape[0])
    ]


def test_the_sheet_books_each_row_on_the_calendar_its_key_selects(sheet: dict[str, Any]) -> None:
    create = bridge.entry("_CreateTrades")
    rows = bridge.Cells.from_rows(
        [
            [1.0, serial("2026-12-15"), "G27", 1.0, 3.0, "OPEN"],
            [2.0, serial("2026-12-15"), "G27", 1.0, 3.0, "JAN_28"],
            [3.0, serial("2026-12-15"), "G27", 1.0, 3.0, "JAN_28+OPEN"],
        ]
    )
    batch = create(sheet["a"], sheet["key_headers"], rows, sheet["keyless"], sheet["calendars"])
    assert re.fullmatch(rf"{PID}:trades:A:\d+", str(batch))
    table = spilled(batch)
    # Friday 29 January on the open calendar; Monday 1 February where Thursday the 28th is closed.
    assert under(table, "payment_date") == [
        serial("2027-01-29"),
        serial("2027-02-01"),
        serial("2027-02-01"),
    ]
    assert table[0][-3:] == [
        "payment_holiday_key",
        "fixed_price_currency_unit",
        "fixed_price_quantity_unit",
    ]
    assert table[1][-3:] == ["str", "str", "str"]
    assert under(table, "payment_holiday_key") == ["OPEN", "JAN_28", "JAN_28+OPEN"]


def test_the_sheet_refuses_a_key_in_the_librarys_words_and_a_collection_in_the_seams(
    sheet: dict[str, Any],
) -> None:
    create = bridge.entry("_CreateTrades")
    library = "#ERROR _CreateTrades: ValueError: "

    def one(key: object) -> bridge.Cells:
        return across(1.0, serial("2026-12-15"), "G27", 1.0, 3.0, key)

    made = (sheet["a"], sheet["key_headers"])
    assert create(*made, one("TOK"), sheet["keyless"], sheet["calendars"]) == (
        library + "payment_holiday_key row 1 is 'TOK', expected names of the collection's "
        "calendars, 'OPEN' and 'JAN_28'; it holds no 'TOK'"
    )
    assert create(*made, one("OPEN+"), sheet["keyless"], sheet["calendars"]) == (
        library + "payment_holiday_key row 1 is 'OPEN+', expected a calendar's name, or several "
        "joined by '+'; a name is missing"
    )
    assert create(*made, one("OPEN"), sheet["keyless"], bridge.MISSING) == (
        library + "holiday_calendars is missing, expected a _CollectHolidayCalendars collection, "
        "which a financially settled batch selects a calendar from"
    )
    # A blank key and a number where the key goes are the seam's to refuse, by the cell.
    assert create(*made, one(None), sheet["keyless"], sheet["calendars"]) == (
        "#ERROR _CreateTrades: trade_rows cell (1, 6) is blank, expected text"
    )
    assert create(*made, one(46023.0), sheet["keyless"], sheet["calendars"]) == (
        "#ERROR _CreateTrades: trade_rows cell (1, 6) is number 46023.0, expected text"
    )
    # A calendar where the collection goes, and a collection that failed, by the argument.
    assert create(*made, one("OPEN"), sheet["keyless"], sheet["open"]) == (
        f"#ERROR _CreateTrades: holiday_calendars is holiday calendar handle {sheet['open']!r}, "
        "expected holiday calendars handle"
    )
    failed = bridge.entry("_CollectHolidayCalendars")(down(sheet["open"], sheet["open"]))
    assert create(*made, one("OPEN"), sheet["keyless"], failed) == (
        "#ERROR _CreateTrades: holiday_calendars is the creator's failure, expected holiday "
        f"calendars handle: {failed}"
    )
    # The same collection serves a quote template, which binds its key when it is made.
    quoted = bridge.entry("_CreateQuoteTemplate")(
        "fixed_float", across("payment_holiday_key"), across("JAN_28+OPEN"), sheet["calendars"]
    )
    assert re.fullmatch(rf"{PID}:quote_template:\d+", str(quoted))
    assert spilled(quoted)[2] == ["fixed_float", "JAN_28+OPEN"]
    assert bridge.entry("_CreateQuoteTemplate")(
        "fixed_float", across("payment_holiday_key"), across("TOK"), sheet["calendars"]
    ) == (
        "#ERROR _CreateQuoteTemplate: ValueError: payment_holiday_key is 'TOK', expected names "
        "of the collection's calendars, 'OPEN' and 'JAN_28'; it holds no 'TOK'"
    )
