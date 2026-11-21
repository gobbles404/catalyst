"""What a request for quote costs, rfq-quoting.md: creation resolves the months, the observations
and the payments once and reads no market, fixing or factor; quoting a saved request parses no
period, makes no observation and shifts no payment, and reads the history, the live prices and
the factors as a quote does on every call; the readback prices nothing; the retained bytes are
the request's own arrays; the peaks measured and pinned for a month and a year. The request is
the quote budgets' CAL index valued in June, its twelve months of 2027 at quantities one to
twelve under the ticket's bilateral template, paying +1bd or on the first day of each following
month."""

from collections.abc import Callable
from types import MappingProxyType

import numpy as np
import pytest
from test_quote_budgets import BILATERAL, CAL, CLEARED, MARKET, RATES
from test_seam_allocation import SLACK, least_peak

from catalyst.excel import bridge
from catalyst.excel.utilities import shown
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.instruments.fields import DatesOrTexts, FieldValues
from catalyst.quoting.rfq import Rfq, quote_rfq, rfq
from catalyst.quoting.template import QuoteTemplate

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}
LETTERS = "FGHJKMNQUVXZ"
CODES = tuple(f"{LETTERS[i]}27" for i in range(12))
QUANTITIES = np.arange(1.0, 13.0)
# Each month's payment on the first day of the month after it, the five paid by June and the
# seven ahead within the curve, which runs to 3 January 2028.
DATES = np.array([f"2027-{m:02d}-01" for m in range(2, 13)] + ["2028-01-01"], dtype="datetime64[D]")


def a_ticket(rows: int, columns: dict[str, object]) -> FieldValues:
    """A request's ticket of that many rows as the seam hands it over, every cell supplied: the
    columns typed as the fixed_float's fields are, codes as text, quantities as numbers and
    payment days as dates."""
    return FieldValues(FIXED_FLOAT, rows, tuple(columns), columns)


def _the_ticket(n: int, dated: bool) -> FieldValues:
    columns: dict[str, object] = {"contract_code": CODES[:n], "quantity": QUANTITIES[:n]}
    if dated:
        columns["payment_day"] = DatesOrTexts.of_dates(DATES[:n])
    return a_ticket(n, columns)


# The request's tickets, a month's and a year's, each with and without the request's own payment
# days: made here, as the module loads, so that no measured call builds its own input whichever
# test runs first. Made on first use they were built inside the first call that asked, and a
# ledger read alone, with no earlier test to have asked, counted the building as the request's.
_TICKETS = MappingProxyType(
    {(n, dated): _the_ticket(n, dated) for n in (1, 12) for dated in (False, True)}
)


def ticket_of(n: int, dated: bool) -> FieldValues:
    """The request's ticket of n months at quantities one to n, with the request's own payment
    days when dated."""
    return _TICKETS[(n, dated)]


def made(
    n: int = 12,
    template: QuoteTemplate = BILATERAL,
    dates: np.ndarray | None = None,
    counter: WorkCounter | None = None,
) -> Rfq:
    return rfq(CAL, ticket_of(n, dates is not None), template, counter or WorkCounter())


def counted(fn: Callable[[WorkCounter], object]) -> dict[str, int]:
    counter = WorkCounter()
    fn(counter)
    return counter.freeze().as_dict()


@pytest.mark.parametrize(("n", "observations"), [(1, 21), (12, 261)], ids=["a month", "a year"])
def test_creation_resolves_once_and_reads_no_market(n: int, observations: int) -> None:
    # The template's values once, the schedule's thirteen codes once, each month once, the
    # observations, the rule read and applied once over the months and a payment day a month;
    # with the request's own dates no rule and no shift, the days taken as given. Nothing of a
    # history, a price, a curve or a factor.
    by_template = counted(lambda c: made(n, BILATERAL, None, c))
    assert by_template == {
        "months_resolved": n,
        "observations_made": observations,
        "payment_days_made": n,
        "payment_rules_read": 1,
        "payment_shifts": 1,
        "schedule_codes_read": 13,
        "template_fields_read": 9,
        "ticket_codes_read": n,  # each distinct code of the rows, read once, since dated-quotes.md
    }
    by_request = counted(lambda c: made(n, BILATERAL, DATES, c))
    assert by_request == {**by_template, "payment_rules_read": 0, "payment_shifts": 0}


def test_quoting_a_saved_request_prices_and_resolves_nothing() -> None:
    # The year in June, as the quote reads it: 118 fixings, seven live contracts once each, the
    # curve selected and seven factors ahead, four reductions; no month resolved, no
    # observation made, no payment shifted. The cleared request reads no curve.
    saved = made()
    assert counted(lambda c: quote_rfq(MARKET, saved, "flat", RATES, c)) == {
        "curves_selected": 1,
        "fixings_read": 118,
        "live_prices_read": 7,
        "payment_factors_read": 7,
        "price_reductions": 4,
    }
    assert counted(lambda c: quote_rfq(MARKET, made(12, CLEARED), "flat", None, c)) == {
        "fixings_read": 118,
        "live_prices_read": 7,
        "price_reductions": 4,
    }


# The functions a quote of a saved request runs, once each whatever the request: the curve bound
# to the collection's first curve, the observations' calendar rows, the prices, the factors and
# the shares; nothing of the period, the observations or the payments.
QUOTE_LEDGER = {
    "quote_rfq": 1,
    "pricing_of": 1,  # the pricing read once, flat or ftc, since fit-to-curve-price.md
    "choice": 1,
    "on_its_index": 1,  # the market over the request's index, the check its prices share
    "the_curve": 1,
    "curve_named": 1,  # the shared step, shared-curve-binding.md
    "DiscountCurve.start_date": 2,
    "curve_starts_on": 1,
    "DiscountCurve.max_date": 1,
    "priced": 1,
    "component_prices": 1,  # each component's own price and its share, the two steps the
    "shares": 1,  # fit-to-curve prices share with the quote since ftc-monthly-prices.md
    "calendar_rows": 1,
    "_the_prices": 1,
    "MarketHistory.fixed_prices": 1,  # each fixed day's settle, by its day and its contract
    "Market.live_prices": 1,
    "_the_factors": 1,
    "factors_on": 1,
    "WorkCounter.__init__": 1,
    "WorkCounter.hit": 5,
}


def test_a_month_and_a_year_quote_through_the_same_functions_once(
    call_profile: CallProfile,
) -> None:
    month, year = made(1), made(12)
    assert (
        call_profile(lambda: quote_rfq(MARKET, month, "flat", RATES, WorkCounter())) == QUOTE_LEDGER
    )
    assert (
        call_profile(lambda: quote_rfq(MARKET, year, "flat", RATES, WorkCounter())) == QUOTE_LEDGER
    )


def test_a_fit_to_curve_price_of_a_saved_request_reads_no_factor(
    call_profile: CallProfile,
) -> None:
    # fit-to-curve-price.md: the same saved request under ftc, the curve selected as under flat
    # and no factor read; the functions the flat price runs but the factors'; a cleared request
    # the same work under either; within the flat price's bound.
    saved = made()
    assert counted(lambda c: quote_rfq(MARKET, saved, "ftc", RATES, c)) == {
        "curves_selected": 1,
        "fixings_read": 118,
        "live_prices_read": 7,
        "price_reductions": 4,
    }
    factors = ("_the_factors", "factors_on", "DiscountCurve.max_date")
    assert call_profile(lambda: quote_rfq(MARKET, saved, "ftc", RATES, WorkCounter())) == {
        **{name: count for name, count in QUOTE_LEDGER.items() if name not in factors},
        "DiscountCurve.start_date": 1,  # read for the start alone, not again for a factor
        "WorkCounter.hit": 4,  # one fewer, the factors uncounted
    }
    cleared = made(12, CLEARED)
    assert counted(lambda c: quote_rfq(MARKET, cleared, "ftc", None, c)) == counted(
        lambda c: quote_rfq(MARKET, cleared, "flat", None, c)
    )
    assert least_peak(lambda: quote_rfq(MARKET, saved, "ftc", RATES, WorkCounter())) <= (
        2_000 + 55 * 261 + SLACK
    )


def test_creation_runs_the_resolution_once_and_nothing_of_the_pricing(
    call_profile: CallProfile,
) -> None:
    # The terms read, the ticket's headers checked, each code read once through the period
    # grammar and the schedule's thirteen for their months, each row's period by the booking's
    # rule, the observations made by one method, their references, the payments shifted once;
    # with the request's dates the column read and no shift; no price, row, fixing or factor.
    by_template = call_profile(lambda: made(12, BILATERAL, None, WorkCounter()))
    assert by_template == {
        "rfq": 1,
        "_the_fields": 1,  # the ticket's headers among the five a request's rows hold, since
        # dated-quotes.md
        "FieldValues.has": 5,  # the quantity and the payment column looked for, the three period
        # fields by their readers
        "the_terms": 1,
        "_the_conditions": 1,
        "_text": 6,
        "route_of": 1,
        "settlement_of": 1,
        "schedule_method_of": 1,
        "quantity_per_of": 1,
        "settlement_frequency_of": 1,  # since onetime-averaging.md
        "choice": 5,
        "payment_rule_of": 1,
        "read_offset": 1,
        "the_frequency": 1,  # the kernel's rule over the template's one set of terms
        "the_nearby": 1,  # the nearby.s, nearby-selection.md, over the same terms
        "nearby_rules": 1,
        "frequency_rules": 1,
        "trade_schedule_of": 2,  # the request's own read and the observations'
        "the_method": 1,
        "_texts_of": 1,  # the codes with which rows supplied one
        "FieldValues.supplied_rows": 1,
        "FieldValues.texts": 1,
        "_dates_of": 2,  # the two date columns, none in this ticket
        "schedule_months": 1,
        "month_and_year": 13,  # the schedule's thirteen codes; the rows' twelve go through the
        # period grammar below
        "contract_days": 1,  # the days the schedule's contracts price on, a window's search key
        "resolve_periods": 1,  # each row's period by the booking's rule, since dated-quotes.md
        "resolve_periods.<locals>.<lambda>": 12,  # each distinct code named for its first row
        "_where": 12,
        "_distinct_texts": 1,
        "months_of": 12,  # the twelve codes read once each through the period grammar
        "period_months": 12,
        "_period_months": 12,
        "_label_months": 12,
        "month_bounds": 1,
        "_the_contracts": 1,  # each component's schedule row, the months' by their month
        "schedule_rows": 1,
        "FieldValues.numbers": 1,
        "_the_quantities": 1,
        "_the_component_quantities": 1,
        "observed": 1,
        "requires_whole_month": 1,
        "counts_back_from_expiry": 1,
        "with_holiday_calendar": 2,
        "_the_days": 1,
        "_business_days_on": 1,
        "observations": 1,
        "observation_references": 1,
        "open_days": 1,
        "contract_on": 1,
        "requires_booked_reference": 1,
        "the_payments": 1,
        "last_days": 1,
        "shift_days": 1,
        "payments_after_observations": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 8,  # since dated-quotes.md the ticket's codes read beside the seven
    }
    by_request = call_profile(lambda: made(12, BILATERAL, DATES, WorkCounter()))
    shifted = ("the_payments", "shift_days", "_business_days_on")  # the rule's work, none
    expected = {k: v for k, v in by_template.items() if k not in shifted}
    assert by_request == {**expected, "_the_dates": 1, "FieldValues.dates_or_texts": 1}


def test_the_readback_prices_nothing(call_profile: CallProfile) -> None:
    saved = made()
    ran = call_profile(lambda: shown(saved))
    assert "rfq_table" in ran
    assert not {"priced", "_the_prices", "Market.live_prices", "factors_on", "quote_rfq"} & set(ran)
    assert counted(lambda c: shown(saved)) == {}


def serial(text: str) -> float:
    return float((np.datetime64(text, "D") - np.datetime64("1899-12-30", "D")).astype(np.int64))


def column(*cells: object) -> bridge.Cells:
    return bridge.Cells.from_rows([[cell] for cell in cells])


def row(*cells: object) -> bridge.Cells:
    return bridge.Cells.from_rows([list(cells)])


def on_the_sheet() -> tuple[object, object, object, object, object]:
    """The ticket's strip through the seam: the market on 31 December 2026 at 1.00 and 1.20, the
    bilateral +5bd template, the collection holding SOFR, the two columns and the saved request."""
    schedule = PATH["_CreateFuturesSchedule"](
        column("Z26", "F27", "G27"),
        column(serial("2026-12-15"), serial("2027-01-29"), serial("2027-02-26")),
        bridge.MISSING,
    )
    holidays = PATH["_CreateHolidayCalendar"](column(serial("2027-01-01")), bridge.MISSING)
    conventions = PATH["_CreateIndexConventions"]("DOLLAR", "BBL", "DOLLAR", "VOLUME", "BBL")
    specifications = PATH["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        row("BBL", 1.0, "BBL", 0.0, 0.0),
    )
    ix = PATH["_CreateIndex"](
        "SEAM", "SEAM index", schedule, conventions, specifications, holidays, "BBL"
    )
    date = PATH["_CreateValuationDate"](serial("2026-12-31"), 0.5)
    days = np.arange(np.datetime64("2026-12-16", "D"), np.datetime64("2026-12-31", "D"))
    fixed = [str(d) for d in days[np.is_busday(days)]][::-1]
    fixings = PATH["_CreateFuturesFixings"](
        column(*[serial(d) for d in fixed]), column(*[3.0] * len(fixed)), ix
    )
    history = PATH["_CreateMarketHistory"](PATH["_CreateCalendar"](date, ix), fixings)
    market = PATH["_CreateMarket"](history, PATH["_CreatePriceVector"]("SEAM", column(1.0, 1.2)))
    weekends = PATH["_CreateHolidayCalendar"](column(serial("2030-01-01")), "PAYS")
    template = PATH["_CreateQuoteTemplate"](
        "fixed_float",
        row(
            "route",
            "settlement_method",
            "schedule_method",
            "quantity_per",
            "payment_day",
            "payment_calendar_key",
            "discount_curve_key",
            "settlement_frequency",
            "nearby",
        ),
        row("bilateral", "financial", "asian", "month", "+5bd", "PAYS", "SOFR", "monthly", 1.0),
        PATH["_CollectPaymentCalendars"](weekends),
    )
    curve = PATH["_CreateDiscountCurve"](
        "SOFR",
        row("date", "discount_factor"),
        bridge.Cells.from_rows(
            [
                [serial("2026-12-31"), 1.0],
                [serial("2027-02-05"), 0.99],
                [serial("2027-03-05"), 0.97],
            ]
        ),
    )
    rates = PATH["_CollectDiscountCurves"](curve)
    saved = PATH["_CreateRFQ"](ix, HEADERS, TICKET, template)
    return market, saved, rates, ix, template


HEADERS = row("contract_code", "quantity")
TICKET = bridge.Cells.from_rows([["F27", 100_000.0], ["G27", 300_000.0]])


def test_the_seam_creates_a_request_binding_its_columns_once_and_publishes_once(
    call_profile: CallProfile,
) -> None:
    _, _, _, ix, template = on_the_sheet()
    live = bridge.live_handles()

    def call() -> object:
        return PATH["_CreateRFQ"](ix, HEADERS, TICKET, template)

    assert str(call()).split(":")[1:3] == ["rfq", "SEAM"]
    ran = call_profile(call)
    assert ran["_publish"] == 1 and ran["rfq"] == 1 and ran["_resolve"] == 2
    assert bridge.live_handles()[0] == live[0] + 2  # the two calls, each its own publication


def test_the_seam_quotes_a_saved_request_resolving_three_handles_and_publishing_nothing(
    call_profile: CallProfile,
) -> None:
    market, saved, rates, _, _ = on_the_sheet()
    live = bridge.live_handles()
    assert PATH["_QuoteRFQ"](market, saved, "flat", rates) == pytest.approx(448_200 / 390_000)
    assert call_profile(lambda: PATH["_QuoteRFQ"](market, saved, "flat", rates)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,  # the three handles and the pricing, one argument more
        "_text": 4,  # each handle cell's text, and the pricing's
        "_resolve": 3,
        "_QuoteRFQ": 1,
        **QUOTE_LEDGER,
        "_number_out": 1,  # the price sent as a number
        "_scalar": 1,
    }
    assert bridge.live_handles() == live


def retained(saved: Rfq) -> int:
    """The bytes a request keeps in its arrays, each counted once: the entered quantities, the
    component quantities where they are not the entered ones, the period's contract rows, first
    and last days and window marks, the payment days, the observations' three arrays and their
    references."""
    request = saved.request
    arrays = [
        saved.occurrence,
        saved.quantity,
        saved.component_quantity,
        request.quantity,
        request.period.contract,
        request.period.first,
        request.period.last,
        request.period.window,
        request.references,
        request.observations.component,
        request.observations.date,
        request.observations.weight,
        request.payment_date,
    ]
    seen: set[int] = set()
    total = 0
    for a in arrays:
        if a is None or id(a) in seen:
            continue
        seen.add(id(a))
        total += a.nbytes
    return total


@pytest.mark.parametrize(("n", "observations"), [(1, 21), (12, 261)], ids=["a month", "a year"])
def test_a_request_retains_its_arrays_and_allocates_within_its_observations(
    n: int, observations: int
) -> None:
    # Retained: eight bytes a month for the quantities, the contract rows, the payment days and
    # since dated-quotes.md the period's first and last days and the row each component came
    # from, one for its window mark, and 32 an observation for its component, day, weight and
    # reference; the component quantities are the entered ones per month, by reference, and the
    # pricing form's are the component quantities themselves.
    saved = made(n)
    assert saved.request.quantity is saved.component_quantity
    assert retained(saved) == 8 * 6 * n + n + 32 * observations
    # Creation's peak, measured on 2026-11-01 under the ticket form: 8,540 bytes for a month's 21
    # observations and 20,122 for the year's 261, about 48 an observation over a floor of 7,500
    # for the terms, the rows' periods and the arrays over the components; quoting the saved
    # request 3,011 and 15,562, about 52 an observation over 2,000, the rows, prices and masks
    # over the observations.
    assert least_peak(lambda: made(n, BILATERAL, None, WorkCounter())) <= (
        7_500 + 55 * observations + SLACK
    )
    assert least_peak(lambda: quote_rfq(MARKET, saved, "flat", RATES, WorkCounter())) <= (
        2_000 + 55 * observations + SLACK
    )


# --- a request of windows, dated-quotes.md ------------------------------------------------------
# Twelve windows of 2027, the 11th to the 25th of each month at quantities one to twelve, under the
# ticket's bilateral template holding onetime and period: a window per row, no code read, each
# paying +1bd from its own last observation, 128 observations, 57 of them fixed by June.

ONETIME = QuoteTemplate(
    FIXED_FLOAT,
    BILATERAL.names,
    MappingProxyType(
        {**BILATERAL.values, "quantity_per": "period", "settlement_frequency": "onetime"}
    ),
    BILATERAL.payment_calendar,
)
WINDOWS = a_ticket(
    12,
    {
        "start_date": np.array([f"2027-{m:02d}-11" for m in range(1, 13)], dtype="datetime64[D]"),
        "end_date": np.array([f"2027-{m:02d}-25" for m in range(1, 13)], dtype="datetime64[D]"),
        "quantity": QUANTITIES,
    },
)
# What the rows by dates run that the rows by code do not, and the other way round: the two date
# columns read with the rows that supplied them in place of the code column, the windows' last
# months' ends and their contracts' one search in place of the twelve codes' grammar.
BY_CODE = (
    "FieldValues.texts",
    "_where",
    "resolve_periods.<locals>.<lambda>",
    "months_of",
    "period_months",
    "_period_months",
    "_label_months",
)


def test_a_request_of_windows_resolves_each_row_once_and_reprices_resolving_nothing(
    call_profile: CallProfile,
) -> None:
    assert counted(lambda c: rfq(CAL, WINDOWS, ONETIME, c)) == {
        "observations_made": 128,
        "payment_days_made": 12,
        "payment_rules_read": 1,
        "payment_shifts": 1,
        "schedule_codes_read": 13,
        "template_fields_read": 9,
        "ticket_codes_read": 0,
        "windows_resolved": 12,
    }
    by_code = call_profile(lambda: made(12, BILATERAL, None, WorkCounter()))
    by_dates = call_profile(lambda: rfq(CAL, WINDOWS, ONETIME, WorkCounter()))
    assert by_dates == {
        **{name: count for name, count in by_code.items() if name not in BY_CODE},
        "FieldValues.dates": 2,
        "FieldValues.supplied_rows": 2,
        "month_bounds": 2,  # and the windows' last months' ends
        "window_rows": 1,  # the windows' contracts, the first pricing each one's first day
    }
    saved = rfq(CAL, WINDOWS, ONETIME, WorkCounter())
    assert counted(lambda c: quote_rfq(MARKET, saved, "flat", RATES, c)) == {
        "curves_selected": 1,
        "fixings_read": 57,
        "live_prices_read": 7,
        "payment_factors_read": 7,
        "price_reductions": 4,
    }
    assert (
        call_profile(lambda: quote_rfq(MARKET, saved, "flat", RATES, WorkCounter())) == QUOTE_LEDGER
    )
    assert retained(saved) == 8 * 6 * 12 + 12 + 32 * 128
    # Measured on 2026-11-01: creation 12,560 bytes, within the request's own bound; the quote
    # 10,952, about 70 an observation where the year's is 52, since 70 of the 128 observations are
    # live and each live one carries its reference and its place among the distinct contracts
    # beside the fixed one's search, where the year in June has 143 live of 261.
    assert least_peak(lambda: rfq(CAL, WINDOWS, ONETIME, WorkCounter())) <= 7_500 + 55 * 128 + SLACK
    assert (
        least_peak(lambda: quote_rfq(MARKET, saved, "flat", RATES, WorkCounter()))
        <= 3_000 + 55 * 128 + SLACK
    )
