"""What quoting costs, in the library and through the seam: the quote template's creation, one
read per value and one publication, as the trade template's; and the quote itself, a month and a
strip of twelve, the work it reports, the package's functions it runs and the peak it allocates.
The pins are the ticket's work rules, template-based-quoting.md: the template's values read once,
every month resolved once, each distinct live contract read once, the fixings one per fixed
observation, the payment rule read once and applied once over the months, the key bound once
and each distinct payment day after the valuation day read once off the curve, a paid month
reading nothing, and four reductions whatever the strip."""

from collections.abc import Callable
from types import MappingProxyType

import numpy as np
import pytest
from test_seam_allocation import SLACK, least_peak

from goosedove.calendar.calendar import calendar
from goosedove.excel import bridge
from goosedove.excel.bridge import Cells
from goosedove.globals.discount_curve import discount_curve
from goosedove.globals.discount_curve_set import DiscountCurveSet, collect_discount_curves
from goosedove.globals.unit_conversions import UNITS
from goosedove.globals.valuation_date import valuation_date
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.index import index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT
from goosedove.market.market import Market, market
from goosedove.market.market_history import market_history
from goosedove.market_data.futures_fixings import futures_fixings
from goosedove.market_data.price_vector import price_vector
from goosedove.quoting.quote import quote
from goosedove.quoting.template import QuoteTemplate
from goosedove.trades.template import DayOrRule

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}

# The ticket's bilateral template: the seven fields a quote template may hold.
TEMPLATE_FIELDS: dict[str, object] = {
    "route": "bilateral",
    "settlement_method": "financial",
    "schedule_method": "asian",
    "quantity_per": "calday",
    "settlement_frequency": "monthly",
    "payment_day": "+5bd",
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
        "_field_dates_or_texts": 1,  # the payment day, a date or a text, since
        # payment-day-date-or-rule.md: its two looks
        "_not_dates": 1,
        "_as_days": 1,
        "_field_handles": 1,
        "_resolve": 1,  # the one handle cell
        "_CreateQuoteTemplate": 1,
        "quote_template": 1,
        "quote_template.<locals>.<genexpr>": 7,  # the instrument's fields up to its first quoted
        "FieldValues.field": 16,  # each field once for its header's rule, once for its value's type
        "FieldValues.field.<locals>.<genexpr>": 32,
        "field_value": 8,  # one per field, no mask of supplied cells to read
        "FieldValues.texts": 6,
        "FieldValues.dates_or_texts": 1,
        "FieldValues.objects": 1,
        "route_of": 1,
        "settlement_of": 1,
        "schedule_method_of": 1,
        "quantity_per_of": 1,
        "settlement_frequency_of": 1,  # since onetime-averaging.md
        "choice": 5,
        "payment_rule_of": 1,
        "read_offset": 1,
        "curve_name": 1,
        "_publish": 1,
    }


# --- the quote: CAL27 in June27, the ticket's strip, and its June alone --------------------------

# Every month of 2027 expiring on its last calendar day, Z26 bounding the calendar, the market
# closed on weekends alone; valued on Wednesday 16 June 2027, January through May paid at 30, June
# half fixed at 38 and half live at 42, July through December live at 40, every payment still
# ahead discounted at 0.98 on a curve from the valuation day to 3 January 2028.
LETTERS = "FGHJKMNQUVXZ"
JUNE_16 = np.datetime64("2027-06-16", "D")
MONTH_ENDS = (
    np.arange("2027-02", "2028-02", dtype="datetime64[M]").astype("datetime64[D]")
    - np.timedelta64(1, "D")
).astype("datetime64[D]")
CAL = index(
    "CAL",
    "CAL index",
    futures_schedule(
        ("Z26", *(f"{LETTERS[i]}27" for i in range(12))),
        np.concatenate([np.array(["2026-12-31"], dtype="datetime64[D]"), MONTH_ENDS]),
        None,
    ),
    index_conventions("USD", "BBL", "USD", "VOLUME", "BBL", UNITS),
    contract_specifications(("BBL",), np.array([1.0]), ("BBL",), np.zeros(1), np.zeros(1), UNITS),
    holiday_calendar(np.array([], dtype="datetime64[D]")),
    "BBL",
    UNITS,
)
WEEKENDS_ONLY = holiday_calendar(np.array(["2030-01-01"], dtype="datetime64[D]"))
SOFR = discount_curve(
    "SOFR",
    np.array(["2027-06-16", "2027-07-01", "2028-01-03"], dtype="datetime64[D]"),
    np.array([1.0, 0.98, 0.98]),
)
RATES = collect_discount_curves((SOFR,), WorkCounter())


def a_template(route: str) -> QuoteTemplate:
    values: dict[str, object] = {
        "route": route,
        "settlement_method": "financial",
        "schedule_method": "asian",
        "quantity_per": "month",
        "settlement_frequency": "monthly",
        "payment_day": DayOrRule(None, "+1bd"),  # the rule as the template holds it
        "payment_holiday_calendar": WEEKENDS_ONLY,
    }
    if route == "bilateral":
        values["discount_curve_key"] = "SOFR"
    return QuoteTemplate(FIXED_FLOAT, tuple(values), MappingProxyType(values))


def in_june() -> Market:
    cal = calendar(valuation_date(JUNE_16, 0.5), CAL)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = np.where(priced >= np.datetime64("2027-06-01", "D"), 38.0, 30.0)
    history = market_history(cal, futures_fixings(priced[::-1].copy(), settles[::-1].copy(), CAL))
    return market(history, price_vector("CAL", np.array([42.0, *[40.0] * 6])))


MARKET = in_june()
BILATERAL = a_template("bilateral")
CLEARED = a_template("cleared")


def counted(code: str, template: QuoteTemplate, curves: DiscountCurveSet | None) -> dict[str, int]:
    counter = WorkCounter()
    quote(MARKET, code, template, curves, counter)
    return counter.freeze().as_dict()


def test_a_month_and_a_strip_report_their_work() -> None:
    # June alone: eleven fixings and eleven live days of M27, one payment ahead, one factor.
    assert counted("M27", BILATERAL, RATES) == {
        "curves_selected": 1,
        "fixings_read": 11,
        "live_prices_read": 1,
        "months_resolved": 1,
        "observations_made": 22,
        "payment_days_made": 1,
        "payment_factors_read": 1,
        "payment_rules_read": 1,
        "payment_shifts": 1,
        "price_reductions": 4,
        "schedule_codes_read": 13,
        "template_fields_read": 8,
    }
    # The year: 261 observations, 118 of them fixed, seven live contracts read once each, twelve
    # payment days of which seven are ahead and read off the curve; the cleared quote reads no
    # curve and binds no key, and the paid months alone read nothing live and no factor.
    assert counted("CAL27", BILATERAL, RATES) == {
        "curves_selected": 1,
        "fixings_read": 118,
        "live_prices_read": 7,
        "months_resolved": 12,
        "observations_made": 261,
        "payment_days_made": 12,
        "payment_factors_read": 7,
        "payment_rules_read": 1,
        "payment_shifts": 1,
        "price_reductions": 4,
        "schedule_codes_read": 13,
        "template_fields_read": 8,
    }
    cleared = counted("CAL27", CLEARED, None)
    assert "curves_selected" not in cleared and "payment_factors_read" not in cleared
    assert cleared["template_fields_read"] == 7
    # The balance of the year: June from its eleven live days and the six months after, no
    # fixing read, every payment ahead.
    assert counted("BALCAL27", BILATERAL, RATES) == {
        "curves_selected": 1,
        "fixings_read": 0,
        "live_prices_read": 7,
        "months_resolved": 7,
        "observations_made": 143,
        "payment_days_made": 7,
        "payment_factors_read": 7,
        "payment_rules_read": 1,
        "payment_shifts": 1,
        "price_reductions": 4,
        "schedule_codes_read": 13,
        "template_fields_read": 8,
    }
    paid = counted("F27-K27", BILATERAL, RATES)
    assert (paid["live_prices_read"], paid["payment_factors_read"]) == (0, 0)
    assert paid["curves_selected"] == 1


# The package's functions a quote runs, once each whatever the period, a month and a year alike:
# the terms read, the key bound to the collection's first curve, the period read as the two date
# utilities read it and resolved against the schedule's thirteen codes, the observations made by
# one method, their references
# and rows, the prices, quantities, payments and factors, the shares and their sum.
LEDGER = {
    "quote": 1,
    "the_terms": 1,
    "_the_conditions": 1,  # the conditional fields, since rfq-quoting.md
    "_text": 6,  # the six texts the bilateral template holds beside its payment day
    "route_of": 1,
    "settlement_of": 1,
    "schedule_method_of": 1,
    "quantity_per_of": 1,
    "settlement_frequency_of": 1,  # since onetime-averaging.md
    "choice": 5,
    "payment_rule_of": 1,
    "read_offset": 1,
    "the_curve": 1,
    "the_curve.<locals>.<genexpr>": 2,  # the collection searched to SOFR, its first curve
    "DiscountCurve.start_date": 2,
    "curve_starts_on": 1,
    "DiscountCurve.max_date": 1,
    "trade_schedule_of": 2,  # the quote's own read and the observations'
    "the_method": 1,
    "_the_period": 1,
    "_the_span": 1,
    "start_date": 1,  # the two readers the date utilities use, balance-of-period-quotes.md
    "end_date": 1,
    "balance_of": 2,  # each reader looks for the prefix
    "period_months": 2,  # and reads the label
    "_period_months": 2,
    "_label_months": 2,
    "schedule_months": 1,
    "month_and_year": 13,  # every code of the schedule read for its month
    "schedule_rows": 1,
    "month_bounds": 1,
    "observed": 1,
    "requires_whole_month": 1,
    "counts_back_from_expiry": 1,
    "with_holiday_calendar": 2,  # the observations' read and the references'
    "_the_days": 1,  # one method, one pass
    "_business_days_on": 1,
    "observations": 1,
    "observation_references": 1,
    "open_days": 1,
    "contract_on": 1,
    "requires_booked_reference": 1,
    "calendar_rows": 1,
    "_the_prices": 1,
    "Market.live_prices": 1,
    "_the_quantities": 1,
    "the_payments": 1,
    "last_days": 1,
    "shift_days": 1,
    "payments_after_observations": 1,  # the kernel's rule, one owner since
    # payment-day-date-or-rule.md
    "priced": 1,  # the request priced, since rfq-quoting.md, request.py
    "_the_factors": 1,
    "factors_on": 1,
    "WorkCounter.__init__": 1,
    "WorkCounter.hit": 12,
}


def test_a_month_and_a_strip_run_the_same_functions_once(call_profile: CallProfile) -> None:
    month = call_profile(lambda: quote(MARKET, "M27", BILATERAL, RATES, WorkCounter()))
    strip = call_profile(lambda: quote(MARKET, "CAL27", BILATERAL, RATES, WorkCounter()))
    assert month == LEDGER
    assert strip == LEDGER


# The peak of a quote, measured on 2026-10-18: 11,134 bytes for June's 22 observations and 26,579
# for the year's 261, about 65 bytes an observation, the arrays over the observations, their
# dates, weights, references, rows, prices and masks, over a floor of about 9,700 for the terms,
# the key bound and the arrays over the months: 70 an observation over 10,000 and the slack.
@pytest.mark.parametrize(
    ("code", "observations"),
    [("M27", 22), ("CAL27", 261), ("BALCAL27", 143)],
    ids=["a month", "a year", "the balance of the year"],
)
def test_a_quote_allocates_within_its_observations(code: str, observations: int) -> None:
    peak = least_peak(lambda: quote(MARKET, code, BILATERAL, RATES, WorkCounter()))
    assert peak <= 10_000 + 70 * observations + SLACK
