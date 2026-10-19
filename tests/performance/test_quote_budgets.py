"""What quoting costs, in the library and through the seam: the quote template's creation, one
read per value and one publication, as the trade template's; and the quote itself, a month and a
strip, pinned beside its hand numbers. The pins are the ticket's work rules,
template-based-quoting.md."""

from collections.abc import Callable

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}

# The ticket's bilateral template: the seven fields a quote template may hold.
TEMPLATE_FIELDS: dict[str, object] = {
    "route": "bilateral",
    "settlement_method": "financial",
    "schedule_method": "asian",
    "quantity_per": "calday",
    "payment_time_lag": "+5bd",
    "payment_holiday_calendar": None,
    "discount_curve_key": "SOFR",
}


def test_the_quote_template_creator_reads_each_value_once_and_publishes_once(
    call_profile: CallProfile,
) -> None:
    holidays = PATH["_CreateHolidayCalendar"](Cells.from_rows([[46352.0]]))
    headers = Cells.from_rows([list(TEMPLATE_FIELDS)])
    values = Cells.from_rows(
        [
            [
                holidays if name == "payment_holiday_calendar" else value
                for name, value in TEMPLATE_FIELDS.items()
            ]
        ]
    )

    def call() -> object:
        return PATH["_CreateQuoteTemplate"]("fixed_float", headers, values)

    assert str(call()).split(":")[1] == "quote_template"
    assert call_profile(call) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text": 2,  # the name, and the handle cell's text
        "_text_row": 1,
        "_texts": 1,
        "_shape": 2,  # the headers' row and, since the shape comes first, the values'
        "_one_row": 1,
        "_field_row": 1,  # one row, the template's shape before its cells, then the cells as they
        "_field_cells": 1,  # arrived, for the binding
        "by_name": 1,
        "instrument": 1,
        "_bind_fields": 1,
        "_field_body": 1,  # the cells placed among the texts once
        "_field_texts": 6,  # six text and code columns
        "_field_handles": 1,
        "_resolve": 1,  # the one handle cell
        "_CreateQuoteTemplate": 1,
        "quote_template": 1,
        "quote_template.<locals>.<genexpr>": 7,  # the instrument's fields up to its first quoted
        "FieldValues.field": 14,  # each field once for its header's rule, once for its value's type
        "FieldValues.field.<locals>.<genexpr>": 28,
        "field_value": 7,  # one per field, no mask of supplied cells to read
        "FieldValues.texts": 6,
        "FieldValues.objects": 1,
        "route_of": 1,
        "settlement_of": 1,
        "schedule_method_of": 1,
        "quantity_per_of": 1,
        "choice": 4,
        "payment_rule_of": 1,
        "read_offset": 1,
        "curve_name": 1,
        "_publish": 1,
    }
