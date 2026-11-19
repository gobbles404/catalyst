"""The trade template: shared field values under the fixed_float's definition, one row of any of its
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

from catalyst.excel import bridge
from catalyst.excel.bridge import Cells, Handle, register
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.sheet_days import SHEET_FIRST_DAY, SHEET_LAST_DAY
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.instruments.fields import FieldValues, selected
from catalyst.trades.template import DayOrRule, TradeTemplate, trade_template

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
    handle = ENTRY["_CreateTradeTemplate"]("fixed_float", row(*fields), row(*fields.values()))
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
    assert template.instrument is FIXED_FLOAT
    assert dict(template.defaults) == {"quantity_unit": "NYMEX NG", "schedule_method": "lastday"}
    assert list(template.defaults) == ["quantity_unit", "schedule_method"]  # the sheet's order
    assert isinstance(template.defaults, MappingProxyType)


def test_one_field_and_the_ng_templates_seven_take_one_path() -> None:
    one = a_template(route="cleared")
    assert dict(one.defaults) == {"route": "cleared"}
    ng = a_template(
        quantity_unit="NYMEX NG",
        quantity_per="month",
        settlement_frequency="monthly",
        schedule_method="lastday",
        route="cleared",
        settlement_method="physical",
        clearing_house="CME Clearing",
    )
    assert len(ng.defaults) == 7 and ng.defaults["clearing_house"] == "CME Clearing"
    # The unit is a name the index will be asked for; the template holds it as typed and asks
    # nothing of it, since it has no index.
    assert a_template(quantity_unit="ICE PHH").defaults["quantity_unit"] == "ICE PHH"


def test_each_value_is_the_scalar_its_type_names_and_a_calendar_the_object_itself() -> None:
    calendar = ENTRY["_CreateHolidayCalendar"](Cells.from_rows([[46352.0], [46381.0]]))
    template = a_template(
        quantity=10.0,
        trade_date=46289.0,
        contract_code="z26",
        payment_day="+2bd",
        payment_holiday_calendar=calendar,
    )
    defaults = template.defaults
    assert defaults["quantity"] == 10.0 and type(defaults["quantity"]) is float
    assert defaults["trade_date"] == np.datetime64("2026-09-24") and isinstance(
        defaults["trade_date"], np.datetime64
    )
    assert defaults["contract_code"] == "z26"  # as typed; resolution reads either case
    assert defaults["payment_day"] == DayOrRule(None, "+2bd")  # the rule, read for the grammar
    held = defaults["payment_holiday_calendar"]
    assert type(held) is HolidayCalendar
    assert held is behind("CatchCalendar", calendar)


def test_a_template_selects_its_instrument_for_a_ticket() -> None:
    assert selected(a_template(route="cleared")) is FIXED_FLOAT


def test_a_templates_numbers_pass_the_kernels_rules_as_a_tickets_do() -> None:
    template = a_template(quantity=-4.0, fixed_price=3.15, cva_reserve=-40.0)
    assert dict(template.defaults) == {"quantity": -4.0, "fixed_price": 3.15, "cva_reserve": -40.0}


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
            {"schedule_method": "Asian"},
            "schedule_method is 'Asian', expected lastday, penultimate, last3day or asian",
        ),
        (
            {"schedule_method": "Lastday"},
            "schedule_method is 'Lastday', expected lastday, penultimate, last3day or asian",
        ),
        ({"route": "Cleared"}, "route is 'Cleared', expected cleared or bilateral"),
        (
            {"settlement_method": "cash"},
            "settlement_method is 'cash', expected physical or financial",
        ),
        ({"quantity_per": "day"}, "quantity_per is 'day', expected month, calday or period"),
        (  # since #181 the utility's grammar, one or more instructions, read whole
            {"payment_day": "2bd"},
            "payment_day is '2bd', expected one or more of a sign, a whole count and bd, cd "
            "or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd",
        ),
        (
            {"payment_day": "+1bd+2xd"},
            "payment_day is '+1bd+2xd', expected one or more of a sign, a whole count and "
            "bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd; from character 5, "
            "'+2xd' begins "
            "with no instruction",
        ),
        (
            {"payment_day": "+1bd "},
            "payment_day is '+1bd ', expected one or more of a sign, a whole count and bd, "
            "cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd; from character 5, ' ' "
            "begins with no "
            "instruction",
        ),
        (
            {"quantity_unit": "NYMEX NG", "route": "cleared", "schedule_method": "pen"},
            "schedule_method is 'pen', expected lastday, penultimate, last3day or asian",
        ),
        ({"quantity": 1.5}, "quantity is 1.5, expected a whole number"),
        ({"quantity": -2.5}, "quantity is -2.5, expected a whole number"),
        ({"quantity": float("inf")}, "quantity is inf, expected a whole number"),
        (  # since #175: a marketing reserve is a finite amount of zero or more
            {"marketing_reserve": -5.0},
            "marketing_reserve is -5.0, expected a finite amount of zero or more",
        ),
        (
            {"marketing_reserve": float("inf")},
            "marketing_reserve is inf, expected a finite amount of zero or more",
        ),
        (
            {"marketing_reserve": float("nan")},
            "marketing_reserve is nan, expected a finite amount of zero or more",
        ),
        (  # since cva-reserve.md: a CVA reserve is a finite amount of either sign
            {"cva_reserve": float("inf")},
            "cva_reserve is inf, expected a finite amount",
        ),
        (
            {"cva_reserve": float("nan")},
            "cva_reserve is nan, expected a finite amount",
        ),
        ({"fixed_price": float("inf")}, "fixed_price is inf, expected a finite price"),
        (
            {"payment_day": LONG_LAG},
            "payment_day has a count of 4301 digits, expected at most 7; the sheet's "
            "calendar runs 1900-03-01 to 9999-12-31",
        ),
        (
            {"payment_day": "+99999999999999999999bd"},
            "payment_day has a count of 20 digits, expected at most 7; the sheet's calendar "
            "runs 1900-03-01 to 9999-12-31",
        ),
    ],
)
def test_a_value_against_its_fields_own_rule_is_refused_naming_the_field(
    fields: dict[str, object], message: str
) -> None:
    result = ENTRY["_CreateTradeTemplate"]("fixed_float", row(*fields), row(*fields.values()))
    assert result == f"#ERROR _CreateTradeTemplate: ValueError: {message}"


# The library imports nothing of the seam, so the two days the lag is held to are pinned to the
# seam's own serials, 61 and 2958465, and the count between them to the number the page quotes.
def test_the_sheets_calendar_the_lag_is_held_to_is_the_seams() -> None:
    assert bridge.EXCEL_EPOCH + np.timedelta64(bridge.FIRST_SERIAL, "D") == SHEET_FIRST_DAY
    assert bridge.EXCEL_EPOCH + np.timedelta64(bridge.LAST_SERIAL, "D") == SHEET_LAST_DAY


def test_the_builder_takes_one_row_of_field_values() -> None:
    two = FieldValues(FIXED_FLOAT, 2, ("quantity",), {"quantity": np.array([1.0, 2.0])})
    with pytest.raises(ValueError, match=r"^values has 2 rows, expected one row of field values$"):
        trade_template(two)


# --- the creator on the sheet -------------------------------------------------------------


def test_the_creator_publishes_a_template_handle_with_no_index_name() -> None:
    handle = ENTRY["_CreateTradeTemplate"]("fixed_float", row("quantity_unit"), row("NYMEX NG"))
    assert re.fullmatch(rf"{os.getpid()}:trade_template:\d+", str(handle))


def test_the_creators_refusals_come_in_the_seams_order_then_the_librarys() -> None:
    create = ENTRY["_CreateTradeTemplate"]
    assert create(None, row("quantity_unit"), row("lot")) == (
        "#ERROR _CreateTradeTemplate: instrument is blank, expected text"
    )
    assert create("Future", row("quantity_unit"), row("lot")) == (
        "#ERROR _CreateTradeTemplate: ValueError: instrument is 'Future', expected one of: "
        "'fixed_float', 'float_float', 'cashflow'"
    )
    assert str(create("fixed_float", row("Quantity_unit"), row("lot"))).startswith(
        "#ERROR _CreateTradeTemplate: fields cell (1, 1) is text 'Quantity_unit', "
        "expected a field of fixed_float: trade_id, "
    )
    assert create("fixed_float", row("quantity_unit"), Cells.from_rows([["lots"], ["lots"]])) == (
        "#ERROR _CreateTradeTemplate: values is 2x1 array, expected one row of field values"
    )
    # Shape before cells: a range one row too tall, its extra row blank, is named for its rows
    # and not for the blank, the seam's rule for every row type.
    assert create("fixed_float", row("quantity_unit"), Cells.from_rows([["lots"], [None]])) == (
        "#ERROR _CreateTradeTemplate: values is 2x1 array, expected one row of field values"
    )
    assert create("fixed_float", row("quantity_unit"), row(1.0)) == (
        "#ERROR _CreateTradeTemplate: values cell (1, 1) is number 1.0, expected text"
    )
    assert create("fixed_float", row("quantity"), row(1.5)) == (
        "#ERROR _CreateTradeTemplate: ValueError: quantity is 1.5, expected a whole number"
    )


def test_the_reader_spills_the_instrument_and_each_default_under_its_field() -> None:
    calendar = ENTRY["_CreateHolidayCalendar"](Cells.from_rows([[46352.0]]))
    handle = ENTRY["_CreateTradeTemplate"](
        "fixed_float",
        row("quantity_unit", "quantity", "trade_date", "payment_holiday_calendar"),
        row("LOT", 10.0, 46289.0, calendar),
    )
    assert spilled(handle) == [
        ["instrument", "quantity_unit", "quantity", "trade_date", "payment_holiday_calendar"],
        ["str", "str", "float64", "datetime64[D]", "str"],
        ["fixed_float", "LOT", 10.0, 46289.0, "a holiday calendar"],
    ]


def test_a_zero_quantity_is_held_as_a_row_kept_ready() -> None:
    # zero-quantities.md: nothing is a whole count, so a template may hold it and every row under
    # the template is then kept ready at nothing; negative zero is a number like any other.
    assert a_template(quantity=0.0).defaults["quantity"] == 0.0
    assert a_template(quantity=-0.0).defaults["quantity"] == 0.0
    handle = ENTRY["_CreateTradeTemplate"]("fixed_float", row("quantity"), row(0.0))
    assert re.fullmatch(rf"{os.getpid()}:trade_template:\d+", str(handle))


# --- the period fields, contract-codes-and-dates.md, since #172 ----------------------------------


def test_a_period_cell_left_empty_is_owned_by_the_template_and_supplied_to_no_row() -> None:
    # contract_code, start_date and end_date may stand with nothing in their cells, a blank or a
    # formula's "": the template owns the header for every batch made under it and supplies the
    # value to no row. Every other field's blank or empty cell is refused as its type refuses it.
    template = a_template(contract_code="", start_date=None, quantity_unit="GAL")
    assert template.names == ("contract_code", "start_date", "quantity_unit")
    assert dict(template.defaults) == {"quantity_unit": "GAL"}
    full = a_template(quantity_unit="NYMEX NG", schedule_method="lastday")
    assert full.names == tuple(full.defaults)
    create = ENTRY["_CreateTradeTemplate"]
    assert create("fixed_float", row("quantity_unit", "quantity"), row("GAL", None)) == (
        "#ERROR _CreateTradeTemplate: values cell (1, 2) is blank, expected number"
    )
    assert create("fixed_float", row("route"), row("")) == (
        "#ERROR _CreateTradeTemplate: values cell (1, 1) is empty text, expected text"
    )
    # The spill shows the words where the cell held nothing, text under the field's header.
    handle = create(
        "fixed_float", row("contract_code", "start_date", "quantity"), row("", None, 10.0)
    )
    assert spilled(handle) == [
        ["instrument", "contract_code", "start_date", "quantity"],
        ["str", "str", "str", "float64"],
        ["fixed_float", "(not supplied)", "(not supplied)", 10.0],
    ]


def test_a_contract_code_is_text_here_and_read_for_its_months_when_a_row_books_by_it() -> None:
    # The grammar's refusal moved to _CreateTrades, for the rows that book by the code: a template
    # holds a label the grammar refuses as typed, since a ticket of dated rows never reads it.
    template = a_template(contract_code="Z2026", end_date=46387.0)
    assert dict(template.defaults) == {
        "contract_code": "Z2026",
        "end_date": np.datetime64("2026-12-31"),
    }
    assert a_template(contract_code="Z27-F27").defaults["contract_code"] == "Z27-F27"


# Since #181 the template reads a payment rule as the date utility reads an offset: a zero, leading
# zeros, either case and a chain are rules, kept as written; the day each makes is the batch's to
# check, against the sheet's calendar and after the last observation.
def test_a_payment_rule_in_any_of_the_grammars_forms_is_a_template() -> None:
    for rule in ("+0bd", "+01bd", "+2BD", "+3em+25cd-1bd+1bd", "-1BD+1bd", "+0em+0cd+0bd"):
        made = ENTRY["_CreateTradeTemplate"]("fixed_float", row("payment_day"), row(rule))
        assert ":trade_template:" in str(made), (rule, made)
