"""What a request for quote costs, rfq-quoting.md: creation resolves the months, the observations
and the payments once and reads no market, fixing or factor; quoting a saved request parses no
period, makes no observation and shifts no payment, and reads the history, the live prices and
the factors as a quote does on every call; the readback prices nothing; the retained bytes are
the request's own arrays; the peaks measured and pinned for a month and a year. The request is
the quote budgets' CAL index valued in June, its twelve months of 2027 at quantities one to
twelve under the ticket's bilateral template, paying +1bd or on the first day of each following
month."""

from collections.abc import Callable

import numpy as np
import pytest
from test_quote_budgets import BILATERAL, CAL, CLEARED, MARKET, RATES
from test_seam_allocation import SLACK, least_peak

from goosedove.excel import bridge
from goosedove.excel.utilities import shown
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.quoting.rfq import Rfq, quote_rfq, rfq
from goosedove.quoting.template import QuoteTemplate

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}
LETTERS = "FGHJKMNQUVXZ"
CODES = tuple(f"{LETTERS[i]}27" for i in range(12))
QUANTITIES = np.arange(1.0, 13.0)
# Each month's payment on the first day of the month after it, the five paid by June and the
# seven ahead within the curve, which runs to 3 January 2028.
DATES = np.array([f"2027-{m:02d}-01" for m in range(2, 13)] + ["2028-01-01"], dtype="datetime64[D]")


def made(
    n: int = 12,
    template: QuoteTemplate = BILATERAL,
    dates: np.ndarray | None = None,
    counter: WorkCounter | None = None,
) -> Rfq:
    return rfq(
        CAL,
        CODES[:n],
        QUANTITIES[:n],
        template,
        None if dates is None else dates[:n],
        counter or WorkCounter(),
    )


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
        "template_fields_read": 8,
    }
    by_request = counted(lambda c: made(n, BILATERAL, DATES, c))
    assert by_request == {**by_template, "payment_rules_read": 0, "payment_shifts": 0}


def test_quoting_a_saved_request_prices_and_resolves_nothing() -> None:
    # The year in June, as the quote reads it: 118 fixings, seven live contracts once each, the
    # curve selected and seven factors ahead, four reductions; no month resolved, no
    # observation made, no payment shifted. The cleared request reads no curve.
    saved = made()
    assert counted(lambda c: quote_rfq(MARKET, saved, RATES, c)) == {
        "curves_selected": 1,
        "fixings_read": 118,
        "live_prices_read": 7,
        "payment_factors_read": 7,
        "price_reductions": 4,
    }
    assert counted(lambda c: quote_rfq(MARKET, made(12, CLEARED), None, c)) == {
        "fixings_read": 118,
        "live_prices_read": 7,
        "price_reductions": 4,
    }


# The functions a quote of a saved request runs, once each whatever the request: the curve bound
# to the collection's first curve, the observations' calendar rows, the prices, the factors and
# the shares; nothing of the period, the observations or the payments.
QUOTE_LEDGER = {
    "quote_rfq": 1,
    "the_curve": 1,
    "the_curve.<locals>.<genexpr>": 2,
    "DiscountCurve.start_date": 2,
    "curve_starts_on": 1,
    "DiscountCurve.max_date": 1,
    "priced": 1,
    "calendar_rows": 1,
    "_the_prices": 1,
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
    assert call_profile(lambda: quote_rfq(MARKET, month, RATES, WorkCounter())) == QUOTE_LEDGER
    assert call_profile(lambda: quote_rfq(MARKET, year, RATES, WorkCounter())) == QUOTE_LEDGER


def test_creation_runs_the_resolution_once_and_nothing_of_the_pricing(
    call_profile: CallProfile,
) -> None:
    # The terms read, each code read once by the one reader and the schedule's thirteen read for
    # their months, the observations made by one method, their references, the payments shifted
    # once; with the request's dates no shift, the two columns' lengths checked; no price, row,
    # fixing or factor.
    by_template = call_profile(lambda: made(12, BILATERAL, None, WorkCounter()))
    assert by_template == {
        "rfq": 1,
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
        "trade_schedule_of": 2,  # the request's own read and the observations'
        "the_method": 1,
        "_aligned": 1,
        "_the_months": 1,
        "month_and_year": 25,  # the twelve codes and the schedule's thirteen
        "schedule_months": 1,
        "schedule_rows": 1,
        "month_bounds": 1,
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
        "WorkCounter.hit": 7,
    }
    by_request = call_profile(lambda: made(12, BILATERAL, DATES, WorkCounter()))
    shifted = ("the_payments", "shift_days", "_business_days_on")  # the rule's work, none
    expected = {k: v for k, v in by_template.items() if k not in shifted}
    assert by_request == {**expected, "_aligned": 2}


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
    holidays = PATH["_CreateHolidayCalendar"](column(serial("2027-01-01")))
    conventions = PATH["_CreateIndexConventions"]("USD", "BBL", "USD", "VOLUME", "BBL")
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
    weekends = PATH["_CreateHolidayCalendar"](column(serial("2030-01-01")))
    template = PATH["_CreateQuoteTemplate"](
        "fixed_float",
        row(
            "route",
            "settlement_method",
            "schedule_method",
            "quantity_per",
            "payment_day",
            "payment_holiday_calendar",
            "discount_curve_key",
            "settlement_frequency",
        ),
        row("bilateral", "financial", "asian", "month", "+5bd", weekends, "SOFR", "monthly"),
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
    codes, quantities = column("F27", "G27"), column(100_000.0, 300_000.0)
    saved = PATH["_CreateRFQ"](ix, codes, quantities, template, bridge.MISSING)
    return market, saved, rates, ix, template


def test_the_seam_creates_a_request_binding_its_columns_once_and_publishes_once(
    call_profile: CallProfile,
) -> None:
    _, _, _, ix, template = on_the_sheet()
    codes, quantities = column("F27", "G27"), column(100_000.0, 300_000.0)
    live = bridge.live_handles()

    def call() -> object:
        return PATH["_CreateRFQ"](ix, codes, quantities, template, bridge.MISSING)

    assert str(call()).split(":")[1:3] == ["rfq", "SEAM"]
    ran = call_profile(call)
    assert ran["_publish"] == 1 and ran["rfq"] == 1 and ran["_resolve"] == 2
    assert bridge.live_handles()[0] == live[0] + 2  # the two calls, each its own publication


def test_the_seam_quotes_a_saved_request_resolving_three_handles_and_publishing_nothing(
    call_profile: CallProfile,
) -> None:
    market, saved, rates, _, _ = on_the_sheet()
    live = bridge.live_handles()
    assert PATH["_QuoteRFQ"](market, saved, rates) == pytest.approx(448_200 / 390_000)
    assert call_profile(lambda: PATH["_QuoteRFQ"](market, saved, rates)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text": 3,
        "_resolve": 3,
        "_QuoteRFQ": 1,
        **QUOTE_LEDGER,
        "_number_out": 1,  # the price sent as a number
        "_scalar": 1,
    }
    assert bridge.live_handles() == live


def retained(saved: Rfq) -> int:
    """The bytes a request keeps in its arrays, each counted once: the entered quantities, the
    component quantities where they are not the entered ones, the contract rows, the payment
    days, the observations' three arrays and their references."""
    request = saved.request
    arrays = [
        saved.quantity,
        saved.component_quantity,
        request.quantity,
        request.contract,
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
    # Retained: eight bytes a month for the quantities, the contract rows and the payment days,
    # and 32 an observation for its component, day, weight and reference; the component
    # quantities are the entered ones per month, by reference, and the pricing form's are the
    # component quantities themselves.
    saved = made(n)
    assert saved.request.quantity is saved.component_quantity
    assert retained(saved) == 8 * 3 * n + 32 * observations
    # Creation's peak, measured on 2026-10-22: 6,568 bytes for a month's 21 observations and
    # 18,610 for the year's 261, about 50 an observation over a floor of 5,500 for the terms,
    # the columns and the arrays over the months; quoting the saved request 3,011 and 15,562,
    # about 52 an observation over 2,000, the rows, prices and masks over the observations.
    assert least_peak(lambda: made(n, BILATERAL, None, WorkCounter())) <= (
        5_500 + 55 * observations + SLACK
    )
    assert least_peak(lambda: quote_rfq(MARKET, saved, RATES, WorkCounter())) <= (
        2_000 + 55 * observations + SLACK
    )
