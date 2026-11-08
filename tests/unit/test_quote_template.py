"""The quote template: the static terms of a quote under the fixed_float's definition, one row of
the fields a quote template may hold, each read for the rule intrinsic to its field and nothing
required; the booking facts and the period fields refused by name; the creator on the sheet, its
handle and its spill, and that it books nothing. docs/library/quoting/quote-template.md is the
page."""

import os
import re
from types import MappingProxyType
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from catalyst.excel import bridge
from catalyst.excel.bridge import Cells, Handle, register
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.instruments.fields import FieldValues
from catalyst.quoting.template import QuoteTemplate, quote_template
from catalyst.trades.template import DayOrRule

ENTRY = {
    name: bridge.entry(name)
    for name in (
        "_CreateQuoteTemplate",
        "_CreateTradeTemplate",
        "_CreateHolidayCalendar",
        "_CreateFuturesSchedule",
        "_CreateIndexConventions",
        "_CreateContractSpecifications",
        "_CreateIndex",
        "_CreateTrades",
        "_CreateCashflows",
        "util_ReadHandle",
    )
}
CAUGHT: list[object] = []


def CatchQuoteTemplate(template: Handle[QuoteTemplate]) -> float:
    """A hidden consumer: the object a quote-template handle stands for, caught on its way
    through."""
    CAUGHT.append(template)
    return 0.0


def CatchQuoteCalendar(calendar: Handle[HolidayCalendar]) -> float:
    CAUGHT.append(calendar)
    return 0.0


register(CatchQuoteTemplate, hidden=True)
register(CatchQuoteCalendar, hidden=True)


def row(*cells: object) -> Cells:
    return Cells.from_rows([list(cells)])


def cells(*rows: list[object]) -> Cells:
    return Cells.from_rows([list(each) for each in rows])


def behind(catcher: str, handle: object) -> object:
    assert bridge.call(catcher, [handle]) == 0.0, handle
    return CAUGHT.pop()


def create(*args: object) -> object:
    return ENTRY["_CreateQuoteTemplate"](*args)


def a_calendar() -> object:
    return ENTRY["_CreateHolidayCalendar"](cells([46352.0], [46381.0]))


def a_quote_template(**fields: object) -> QuoteTemplate:
    """A quote template of those fields, made through the seam so the values arrive typed."""
    handle = create("fixed_float", row(*fields), row(*fields.values()))
    template = behind("CatchQuoteTemplate", handle)
    assert type(template) is QuoteTemplate
    return template


def an_index() -> object:
    """The NG example's index through the seam, for the booking creators to refuse a quote
    template on."""
    schedule = ENTRY["_CreateFuturesSchedule"](
        cells(["X26"], ["Z26"], ["F27"]), cells([46323.0], [46351.0], [46385.0]), bridge.MISSING
    )
    conventions = ENTRY["_CreateIndexConventions"]("USD", "MMBTU", "USD", "ENERGY", "MMBTU")
    specs = ENTRY["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        row("NYMEX NG", 10000.0, "MMBTU", 0.0, 0.0),
    )
    return ENTRY["_CreateIndex"](
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        conventions,
        specs,
        a_calendar(),
        "NYMEX NG",
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


# The ticket's bilateral example: the seven fields a quote template may hold, the calendar a
# handle made per test.
BILATERAL: dict[str, object] = {
    "route": "bilateral",
    "settlement_method": "financial",
    "schedule_method": "asian",
    "quantity_per": "calday",
    "settlement_frequency": "monthly",
    "payment_day": "+5bd",
    "payment_holiday_calendar": None,
    "discount_curve_key": "SOFR",
}
ALLOWED = (
    "schedule_method, route, settlement_method, discount_curve_key, quantity_per, "
    "payment_day, payment_holiday_calendar, settlement_frequency"
)


def bilateral_values(calendar: object) -> list[object]:
    return [calendar if name == "payment_holiday_calendar" else v for name, v in BILATERAL.items()]


# --- the record ------------------------------------------------------------------------------


def test_the_tickets_bilateral_example_makes_a_template_of_its_seven_fields() -> None:
    calendar = a_calendar()
    handle = create("fixed_float", row(*BILATERAL), row(*bilateral_values(calendar)))
    template = behind("CatchQuoteTemplate", handle)
    assert type(template) is QuoteTemplate
    assert template.instrument is FIXED_FLOAT
    assert template.names == tuple(BILATERAL)  # the sheet's order
    assert list(template.values) == list(BILATERAL)
    assert isinstance(template.values, MappingProxyType)
    held = template.values["payment_holiday_calendar"]
    assert type(held) is HolidayCalendar and held is behind("CatchQuoteCalendar", calendar)
    texts = {k: v for k, v in template.values.items() if k != "payment_holiday_calendar"}
    expected = {k: v for k, v in BILATERAL.items() if k != "payment_holiday_calendar"}
    expected["payment_day"] = DayOrRule(None, "+5bd")  # the rule as a template holds it
    assert texts == expected


def test_a_cleared_financial_template_needs_no_key_and_one_field_takes_the_same_path() -> None:
    cleared = a_quote_template(
        route="cleared",
        settlement_method="financial",
        schedule_method="lastday",
        quantity_per="month",
        settlement_frequency="monthly",
        payment_day="+2bd",
        payment_holiday_calendar=a_calendar(),
    )
    assert len(cleared.values) == 7 and cleared.values["route"] == "cleared"
    one = a_quote_template(schedule_method="penultimate")
    assert dict(one.values) == {"schedule_method": "penultimate"}
    # A template is a partial record: what a completed quote requires, and whether its terms
    # agree, is the quote's rule, so a key beside a cleared route is held here as typed.
    held = a_quote_template(route="cleared", discount_curve_key="SOFR")
    assert dict(held.values) == {"route": "cleared", "discount_curve_key": "SOFR"}


def test_each_value_is_read_once_by_the_trade_templates_reader_and_kept_as_typed() -> None:
    template = a_quote_template(
        payment_day="+2BD", schedule_method="asian", discount_curve_key="ffois"
    )
    assert dict(template.values) == {
        "payment_day": DayOrRule(None, "+2BD"),
        "schedule_method": "asian",
        "discount_curve_key": "ffois",
    }
    assert all(
        type(value) is str for name, value in template.values.items() if name != "payment_day"
    )


def test_the_builder_takes_one_row_of_field_values() -> None:
    two = FieldValues(FIXED_FLOAT, 2, ("route",), {"route": ("cleared", "cleared")})
    with pytest.raises(ValueError, match=r"^values has 2 rows, expected one row of field values$"):
        quote_template(two)


# --- what a quote template may not hold --------------------------------------------------------

# Every field of the fixed_float a quote template refuses, each with a value its type takes, so
# that the header alone is what refuses it; the three period fields twice, a value and a blank,
# since their cells may be blank for a trade template and the header owns nothing here.
REFUSED: list[tuple[str, object]] = [
    ("trade_id", 1001.0),
    ("trade_date", 46289.0),
    ("contract_code", "Z26"),
    ("contract_code", ""),
    ("start_date", 46289.0),
    ("start_date", None),
    ("end_date", 46300.0),
    ("end_date", None),
    ("clearing_house", "CME Clearing"),
    ("counterparty", "ACME Trading"),
    ("broker", "none"),
    ("quantity", 10.0),
    ("quantity_unit", "NYMEX NG"),
    ("fixed_price", 3.0),
    ("marketing_reserve", 0.0),
    ("cva_reserve", -25.0),
]


@pytest.mark.parametrize(
    ("name", "value"), REFUSED, ids=[f"{name}={value!r}" for name, value in REFUSED]
)
def test_a_booking_field_or_a_period_field_is_refused_by_name_whatever_its_cell_holds(
    name: str, value: object
) -> None:
    assert create("fixed_float", row("route", name), row("cleared", value)) == (
        f"#ERROR _CreateQuoteTemplate: ValueError: {name} is a field of booking alone, expected "
        f"one a quote template holds: {ALLOWED}"
    )


def test_the_first_refused_header_in_the_sheets_order_is_named_before_any_value_is_read() -> None:
    refusal = (
        "#ERROR _CreateQuoteTemplate: ValueError: quantity is a field of booking alone, expected "
        f"one a quote template holds: {ALLOWED}"
    )
    assert (
        create("fixed_float", row("route", "quantity", "trade_id"), row("cleared", 10.0, 1001.0))
        == refusal
    )
    assert create("fixed_float", row("quantity", "route"), row(10.0, "Cleared")) == refusal
    assert {field.name for field in FIXED_FLOAT.fields if field.quote_allowed} == set(
        ALLOWED.split(", ")
    )


def test_an_instrument_no_quote_prices_is_refused_by_name() -> None:
    assert create("cashflow", row("currency"), row("USD")) == (
        "#ERROR _CreateQuoteTemplate: ValueError: instrument is 'cashflow', expected one a "
        "quote prices: 'fixed_float'"
    )


def test_the_creators_refusals_come_in_the_seams_order_then_the_librarys() -> None:
    assert create(None, row("route"), row("cleared")) == (
        "#ERROR _CreateQuoteTemplate: instrument is blank, expected text"
    )
    assert create("Future", row("route"), row("cleared")) == (
        "#ERROR _CreateQuoteTemplate: ValueError: instrument is 'Future', expected one of: "
        "'fixed_float', 'cashflow'"
    )
    assert str(create("fixed_float", row("Route"), row("cleared"))).startswith(
        "#ERROR _CreateQuoteTemplate: fields cell (1, 1) is text 'Route', "
        "expected a field of fixed_float: trade_id, "
    )
    assert create("fixed_float", row("route", "route"), row("cleared", "cleared")) == (
        "#ERROR _CreateQuoteTemplate: fields cell (1, 2) is text 'route', already given at "
        "cell (1, 1)"
    )
    assert create("fixed_float", row("route"), cells(["cleared"], ["cleared"])) == (
        "#ERROR _CreateQuoteTemplate: values is 2x1 array, expected one row of field values"
    )
    assert create("fixed_float", row("route"), row(1.0)) == (
        "#ERROR _CreateQuoteTemplate: values cell (1, 1) is number 1.0, expected text"
    )
    assert create("fixed_float", row("route"), row(None)) == (
        "#ERROR _CreateQuoteTemplate: values cell (1, 1) is blank, expected text"
    )
    assert create("fixed_float", row("payment_holiday_calendar"), row("x")) == (
        "#ERROR _CreateQuoteTemplate: values cell (1, 1) is text 'x' naming no live object, "
        "expected holiday calendar handle"
    )
    # Then the library's, each value for the rule intrinsic to its field, the trade template's.
    library = "#ERROR _CreateQuoteTemplate: ValueError: "
    assert create("fixed_float", row("route"), row("Cleared")) == (
        library + "route is 'Cleared', expected cleared or bilateral"
    )
    assert create("fixed_float", row("schedule_method"), row("Asian")) == (
        library + "schedule_method is 'Asian', expected lastday, penultimate, last3day or asian"
    )
    assert create("fixed_float", row("settlement_method"), row("cash")) == (
        library + "settlement_method is 'cash', expected physical or financial"
    )
    assert create("fixed_float", row("quantity_per"), row("day")) == (
        library + "quantity_per is 'day', expected month, calday or period"
    )
    assert create("fixed_float", row("payment_day"), row("2bd")) == (
        library + "payment_day is '2bd', expected one or more of a sign, a whole count and "
        "bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd"
    )
    assert create("fixed_float", row("discount_curve_key"), row(" SOFR")) == (
        library + "discount_curve_key is ' SOFR', expected a name with no whitespace around it"
    )
    assert create("fixed_float", row("discount_curve_key"), row(" ")) == (
        library + "discount_curve_key is ' ', expected a name, not whitespace alone"
    )


# --- the creator on the sheet -------------------------------------------------------------


def test_the_creator_publishes_a_quote_template_handle_with_no_index_name() -> None:
    handle = create("fixed_float", row("route"), row("cleared"))
    assert re.fullmatch(rf"{os.getpid()}:quote_template:\d+", str(handle))


def test_a_quote_template_books_nothing_and_a_trade_template_quotes_nothing() -> None:
    # The booking creators take a trade template and refuse a quote template by its kind, the
    # seam's rule for every handle argument, so no booking fact is ever read off a quote
    # template; and a consumer of a quote template refuses a trade template the same way.
    quote = create("fixed_float", row("route"), row("cleared"))
    assert ENTRY["_CreateCashflows"](row("amount"), row(100.0), quote) == (
        f"#ERROR _CreateCashflows: template is quote template handle {quote!r}, expected trade "
        "template handle"
    )
    assert ENTRY["_CreateTrades"](an_index(), row("quantity"), row(1.0), quote) == (
        f"#ERROR _CreateTrades: template is quote template handle {quote!r}, expected trade "
        "template handle"
    )
    trade = ENTRY["_CreateTradeTemplate"]("fixed_float", row("route"), row("cleared"))
    assert bridge.call("CatchQuoteTemplate", [trade]) == (
        f"#ERROR CatchQuoteTemplate: template is trade template handle {trade!r}, expected "
        "quote template handle"
    )


def test_the_reader_spills_the_instrument_and_each_value_under_its_field() -> None:
    handle = create("fixed_float", row(*BILATERAL), row(*bilateral_values(a_calendar())))
    assert spilled(handle) == [
        ["instrument", *BILATERAL],
        ["str"] * 9,
        [
            "fixed_float",
            "bilateral",
            "financial",
            "asian",
            "calday",
            "monthly",
            "+5bd",
            "a holiday calendar",
            "SOFR",
        ],
    ]


def test_creating_publishes_one_handle_and_reading_none() -> None:
    live, _ = bridge.live_handles()  # the store's count, and the bytes of prices held
    handle = create("fixed_float", row("route"), row("cleared"))
    assert bridge.live_handles()[0] == live + 1
    ENTRY["util_ReadHandle"](handle)
    assert bridge.live_handles()[0] == live + 1
