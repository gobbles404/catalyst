"""The trade template: shared field values under the future's definition, one row of any of its
fields, each read for the rule intrinsic to its field and nothing required; the template selects
the instrument for a ticket; the creator on the sheet, its handle and its spill.
docs/library/trades/trade-template.md is the page."""

import os
import re
from types import MappingProxyType
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells, Handle, register
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.instruments.definitions import FUTURE
from goosedove.instruments.fields import FieldValues, selected
from goosedove.trades.template import (
    MOST_BUSINESS_DAYS,
    SHEET_FIRST_DAY,
    SHEET_LAST_DAY,
    TradeTemplate,
    trade_template,
)

ENTRY = {
    name: bridge.entry(name)
    for name in ("_CreateTradeTemplate", "_CreateHolidayCalendar", "util_ReadHandle")
}
CAUGHT: list[object] = []


def CatchTemplate(template: Handle[TradeTemplate]) -> float:
    """A hidden consumer: the object a template handle stands for, caught on its way through."""
    CAUGHT.append(template)
    return 0.0


def CatchCalendar(calendar: Handle[HolidayCalendar]) -> float:
    CAUGHT.append(calendar)
    return 0.0


register(CatchTemplate, hidden=True)
register(CatchCalendar, hidden=True)


def row(*cells: object) -> Cells:
    return Cells.from_rows([list(cells)])


def behind(catcher: str, handle: object) -> object:
    assert bridge.call(catcher, [handle]) == 0.0, handle
    return CAUGHT.pop()


def a_template(**fields: object) -> TradeTemplate:
    """A template of those fields, made through the seam so the values arrive typed."""
    handle = ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*fields.values()))
    template = behind("CatchTemplate", handle)
    assert type(template) is TradeTemplate
    return template


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


# --- the record ------------------------------------------------------------------------------


def test_the_page_example_makes_a_template_of_its_two_fields() -> None:
    template = a_template(quantity_unit="NYMEX NG", schedule_method="lastday")
    assert template.instrument is FUTURE
    assert dict(template.defaults) == {"quantity_unit": "NYMEX NG", "schedule_method": "lastday"}
    assert list(template.defaults) == ["quantity_unit", "schedule_method"]  # the sheet's order
    assert isinstance(template.defaults, MappingProxyType)


def test_one_field_and_the_ng_templates_six_take_one_path() -> None:
    one = a_template(route="cleared")
    assert dict(one.defaults) == {"route": "cleared"}
    ng = a_template(
        quantity_unit="NYMEX NG",
        quantity_per="month",
        schedule_method="lastday",
        route="cleared",
        settlement_method="physical",
        clearing_house="CME Clearing",
    )
    assert len(ng.defaults) == 6 and ng.defaults["clearing_house"] == "CME Clearing"
    # The unit is a name the index will be asked for; the template holds it as typed and asks
    # nothing of it, since it has no index.
    assert a_template(quantity_unit="ICE PHH").defaults["quantity_unit"] == "ICE PHH"


def test_each_value_is_the_scalar_its_type_names_and_a_calendar_the_object_itself() -> None:
    calendar = ENTRY["_CreateHolidayCalendar"](Cells.from_rows([[46352.0], [46381.0]]))
    template = a_template(
        quantity=10.0,
        trade_date=46289.0,
        contract_code="z26",
        payment_time_lag="+2bd",
        payment_holiday_calendar=calendar,
    )
    defaults = template.defaults
    assert defaults["quantity"] == 10.0 and type(defaults["quantity"]) is float
    assert defaults["trade_date"] == np.datetime64("2026-09-24") and isinstance(
        defaults["trade_date"], np.datetime64
    )
    assert defaults["contract_code"] == "z26"  # as typed; resolution reads either case
    assert defaults["payment_time_lag"] == "+2bd"
    held = defaults["payment_holiday_calendar"]
    assert type(held) is HolidayCalendar
    assert held is behind("CatchCalendar", calendar)


def test_a_template_selects_its_instrument_for_a_ticket() -> None:
    assert selected(a_template(route="cleared")) is FUTURE


def test_a_templates_numbers_pass_the_kernels_rules_as_a_tickets_do() -> None:
    template = a_template(quantity=-4.0, fixed_price=3.15)
    assert dict(template.defaults) == {"quantity": -4.0, "fixed_price": 3.15}


def test_a_field_the_ticket_must_supply_is_not_required_of_a_template() -> None:
    # Nothing of trade_date, contract_code, quantity or fixed_price, and no payment fields with a
    # financial settlement: the ticket completes it, and resolution checks the whole.
    template = a_template(settlement_method="financial", route="bilateral")
    assert dict(template.defaults) == {"settlement_method": "financial", "route": "bilateral"}


# A lag of 4,301 digits fits a cell and would fail Python's own conversion, which refuses more
# than 4,300 digits with words of its own; the bound names it before any digit is converted.
LONG_LAG = "+" + "9" * 4301 + "bd"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"schedule_method": "asian"},
            "schedule_method is 'asian', expected lastday or penultimate, the two methods built",
        ),
        (
            {"schedule_method": "Lastday"},
            "schedule_method is 'Lastday', expected lastday or penultimate, the two methods built",
        ),
        ({"route": "Cleared"}, "route is 'Cleared', expected cleared or bilateral"),
        (
            {"settlement_method": "cash"},
            "settlement_method is 'cash', expected physical or financial",
        ),
        ({"quantity_per": "day"}, "quantity_per is 'day', expected month, the one basis built"),
        (
            {"payment_time_lag": "+0bd"},
            "payment_time_lag is '+0bd', expected a positive whole number of business days, "
            "such as +1bd",
        ),
        (
            {"payment_time_lag": "2bd"},
            "payment_time_lag is '2bd', expected a positive whole number of business days, "
            "such as +1bd",
        ),
        (
            {"payment_time_lag": "+01bd"},
            "payment_time_lag is '+01bd', expected a positive whole number of business days, "
            "such as +1bd",
        ),
        (
            {"contract_code": "Z2026"},
            "contract_code is 'Z2026', expected a contract or strip with two-digit years, "
            "such as F26, 1Q27, CAL28, W29, S28 or F26-Z28",
        ),
        (
            {"contract_code": "Z27-F27"},
            "contract_code is 'Z27-F27', expected range endpoints in chronological order",
        ),
        (
            {"quantity_unit": "NYMEX NG", "route": "cleared", "schedule_method": "pen"},
            "schedule_method is 'pen', expected lastday or penultimate, the two methods built",
        ),
        ({"quantity": 1.5}, "quantity is 1.5, expected a whole number"),
        ({"quantity": -2.5}, "quantity is -2.5, expected a whole number"),
        ({"quantity": float("inf")}, "quantity is inf, expected a whole number"),
        ({"fixed_price": float("inf")}, "fixed_price is inf, expected a finite price"),
        (
            {"payment_time_lag": LONG_LAG},
            f"payment_time_lag is {LONG_LAG!r}, expected at most 2,113,146 business days, "
            "the sheet's calendar from 1900-03-01 to 9999-12-31 end to end",
        ),
        (
            {"payment_time_lag": "+99999999999999999999bd"},
            "payment_time_lag is '+99999999999999999999bd', expected at most 2,113,1"
            "46 business days, the sheet's calendar from 1900-03-01 to 9999-12-31 end to end",
        ),
    ],
)
def test_a_value_against_its_fields_own_rule_is_refused_naming_the_field(
    fields: dict[str, object], message: str
) -> None:
    result = ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*fields.values()))
    assert result == f"#ERROR _CreateTradeTemplate: ValueError: {message}"


# The library imports nothing of the seam, so the two days the lag is held to are pinned to the
# seam's own serials, 61 and 2958465, and the count between them to the number the page quotes.
def test_the_sheets_calendar_the_lag_is_held_to_is_the_seams() -> None:
    assert bridge.EXCEL_EPOCH + np.timedelta64(bridge.FIRST_SERIAL, "D") == SHEET_FIRST_DAY
    assert bridge.EXCEL_EPOCH + np.timedelta64(bridge.LAST_SERIAL, "D") == SHEET_LAST_DAY
    assert MOST_BUSINESS_DAYS == 2_113_146


def test_the_builder_takes_one_row_of_field_values() -> None:
    two = FieldValues(FUTURE, 2, ("quantity",), {"quantity": np.array([1.0, 2.0])})
    with pytest.raises(ValueError, match=r"^values has 2 rows, expected one row of field values$"):
        trade_template(two)


# --- the creator on the sheet -------------------------------------------------------------


def test_the_creator_publishes_a_template_handle_with_no_index_name() -> None:
    handle = ENTRY["_CreateTradeTemplate"]("future", row("quantity_unit"), row("NYMEX NG"))
    assert re.fullmatch(rf"{os.getpid()}:trade_template:\d+", str(handle))


def test_the_creators_refusals_come_in_the_seams_order_then_the_librarys() -> None:
    create = ENTRY["_CreateTradeTemplate"]
    assert create(None, row("quantity_unit"), row("lot")) == (
        "#ERROR _CreateTradeTemplate: instrument is blank, expected text"
    )
    assert create("Future", row("quantity_unit"), row("lot")) == (
        "#ERROR _CreateTradeTemplate: ValueError: instrument is 'Future', expected one of: 'future'"
    )
    assert str(create("future", row("Quantity_unit"), row("lot"))).startswith(
        "#ERROR _CreateTradeTemplate: fields cell (1, 1) is text 'Quantity_unit', "
        "expected a field of future: trade_id, "
    )
    assert create("future", row("quantity_unit"), Cells.from_rows([["lots"], ["lots"]])) == (
        "#ERROR _CreateTradeTemplate: values is 2x1 array, expected one row of field values"
    )
    # Shape before cells: a range one row too tall, its extra row blank, is named for its rows
    # and not for the blank, the seam's rule for every row type.
    assert create("future", row("quantity_unit"), Cells.from_rows([["lots"], [None]])) == (
        "#ERROR _CreateTradeTemplate: values is 2x1 array, expected one row of field values"
    )
    assert create("future", row("quantity_unit"), row(1.0)) == (
        "#ERROR _CreateTradeTemplate: values cell (1, 1) is number 1.0, expected text"
    )
    assert create("future", row("quantity"), row(1.5)) == (
        "#ERROR _CreateTradeTemplate: ValueError: quantity is 1.5, expected a whole number"
    )


def test_the_reader_spills_the_instrument_and_each_default_under_its_field() -> None:
    calendar = ENTRY["_CreateHolidayCalendar"](Cells.from_rows([[46352.0]]))
    handle = ENTRY["_CreateTradeTemplate"](
        "future",
        row("quantity_unit", "quantity", "trade_date", "payment_holiday_calendar"),
        row("LOT", 10.0, 46289.0, calendar),
    )
    assert spilled(handle) == [
        ["instrument", "quantity_unit", "quantity", "trade_date", "payment_holiday_calendar"],
        ["str", "str", "float64", "datetime64[D]", "str"],
        ["future", "LOT", 10.0, 46289.0, "a holiday calendar"],
    ]


def test_a_zero_quantity_is_held_as_a_row_kept_ready() -> None:
    # zero-quantities.md: nothing is a whole count, so a template may hold it and every row under
    # the template is then kept ready at nothing; negative zero is a number like any other.
    assert a_template(quantity=0.0).defaults["quantity"] == 0.0
    assert a_template(quantity=-0.0).defaults["quantity"] == 0.0
    handle = ENTRY["_CreateTradeTemplate"]("future", row("quantity"), row(0.0))
    assert re.fullmatch(rf"{os.getpid()}:trade_template:\d+", str(handle))
