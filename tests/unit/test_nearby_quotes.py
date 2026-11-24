"""Quotes and requests for quote under the nearby field, nearby-selection.md's third slice: a
quote template's nearby is priced as a batch's is, through the reference rule the three share
and the history's reader. The ticket's two days across an expiry quote 80.5 at the first nearby
and 82.5 at the second off one history; a label's month and a request's row read the next
contract on every day, across the roll inside the month; a quote booked as a trade at its price
marks nothing while every payment is ahead, and once a month has paid its mark and its cash are
equal and opposite; and the refusals, a later nearby where it is not priced, a nearby the schedule
lists no contract for, and a history or a market that holds no price of it."""

import pytest
from test_create_trades import a_ticket, created, key_of
from test_nearby_fixings import JUNE_17, ROLL, history_on
from test_nearby_trades import JUNE_12, JUNE_16, WINDOW, rows_over, valued
from test_quote import a_template as a_quote_template
from test_trades import day, quoted

from catalyst.excel.utilities import shown
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.quoting.quote import quote, quote_by_dates
from catalyst.quoting.rfq import quote_rfq, rfq
from catalyst.quoting.template import QuoteTemplate
from catalyst.trades.template import DayOrRule

START, END = day("2026-06-15"), day("2026-06-16")
# July 2026 on the ticket's index: N26 is prompt through its expiry on Wednesday 15 July, eleven
# pricing days, and Q26 from the 16th, twelve. The second nearby reads Q26 and then U26.
JULY_FIRST = (11 * 81.0 + 12 * 83.0) / 23  # 82.0435, N26 at 81 and Q26 at 83
JULY_SECOND = (11 * 83.0 + 12 * 85.0) / 23  # 84.0435, Q26 at 83 and U26 at 85
NOT_ASIAN = (
    "expected 1 under schedule_method = lastday; the expiry-based methods take their own "
    "contract's days, and a later nearby is priced under asian"
)


def window_quote(nearby: int) -> QuoteTemplate:
    """The window's terms as a quote holds them: one average over the days given, cleared and
    paid on 18 June."""
    return a_quote_template(
        route="cleared",
        settlement_method="financial",
        schedule_method="asian",
        quantity_per="period",
        settlement_frequency="onetime",
        nearby=nearby,
        payment_day=DayOrRule(day("2026-06-18"), None),
        payment_calendar_key=key_of(ROLL.holiday_calendar),
    )


def monthly_quote(nearby: int, method: str = "asian") -> QuoteTemplate:
    """A month's terms: each month its own average, cleared, paid two business days after its
    last observation."""
    return a_quote_template(
        route="cleared",
        settlement_method="financial",
        schedule_method=method,
        quantity_per="month",
        settlement_frequency="monthly",
        nearby=nearby,
        payment_day=DayOrRule(None, "+2bd"),
        payment_calendar_key=key_of(ROLL.holiday_calendar),
    )


def dated(as_of: str, nearby: int, *quotes: float) -> float:
    market = quoted(history_on(as_of, 2), *quotes)
    return quote_by_dates(market, START, END, window_quote(nearby), "flat", None, WorkCounter())


def test_the_two_days_quote_80_5_at_the_first_nearby_and_82_5_at_the_second() -> None:
    # The ticket's table as a quote, both days fixed on 17 June: the first nearby reads M26 and
    # then N26, the second N26 and then Q26, off one history, a fixing read per day.
    assert dated(JUNE_17, 1, 81.5, 83.5) == 80.5
    assert dated(JUNE_17, 2, 81.5, 83.5) == 82.5
    counter = WorkCounter()
    market = quoted(history_on(JUNE_17, 2), 81.5, 83.5)
    assert quote_by_dates(market, START, END, window_quote(2), "flat", None, counter) == 82.5
    counts = counter.freeze().as_dict()
    assert (counts["fixings_read"], counts["live_prices_read"]) == (2, 0)
    # Nothing fixed on 12 June, M26 quoted 80, N26 81 and Q26 83: 80.5 and 82.
    assert dated(JUNE_12, 1, 80.0, 81.0, 83.0) == 80.5
    assert dated(JUNE_12, 2, 80.0, 81.0, 83.0) == 82.0
    # The expiry day fixed at 82 for the second nearby, Q26 quoted 83 for the 16th.
    assert dated(JUNE_16, 2, 81.0, 83.0) == 82.5


@pytest.mark.parametrize(
    ("as_of", "quotes"), [(JUNE_12, (80.0, 81.0, 83.0)), (JUNE_16, (81.0, 83.0))]
)
def test_a_second_nearby_quote_booked_as_a_trade_marks_nothing(
    as_of: str, quotes: tuple[float, ...]
) -> None:
    market = quoted(history_on(as_of, 2), *quotes)
    price = quote_by_dates(market, START, END, window_quote(2), "flat", None, WorkCounter())
    ticket: dict[str, list[object]] = {**rows_over((2.0,)), "fixed_price": [price]}
    batch, _ = created(ROLL, ticket, WINDOW)
    assert valued(batch, market).mark == pytest.approx(0.0, abs=1e-9)


def test_once_a_month_has_paid_the_mark_and_the_cash_are_equal_and_opposite() -> None:
    # The zero mark holds while every payment is ahead, quote.md's condition. A June and July
    # strip at the second nearby, valued Monday 6 July with N26 at 81, Q26 at 83 and U26 at 85.
    # June fixed whole, twenty days at 72 and the two across the expiry at 82 and 83, 1,605/22,
    # and paid on 2 July; July three days fixed at 72, eight at Q26's 83 and twelve at U26's 85,
    # 1,900/23. A cleared quote of two months weighs each one: their mean, 77.78162055. A barrel
    # a month booked at it has paid June's shortfall in cash and marks July's excess, the same
    # amount, 4.82707510, so the two sum to nothing and neither is nothing alone.
    market = quoted(history_on("2026-07-06", 2), 81.0, 83.0, 85.0)
    june, july = 1_605 / 22, 1_900 / 23
    price = quote(market, "M26-N26", monthly_quote(2), "flat", None, WorkCounter())
    assert price == pytest.approx((june + july) / 2) and price == pytest.approx(77.78162055)
    terms: dict[str, object] = {
        "quantity_unit": "BBL",
        "quantity_per": "month",
        "settlement_frequency": "monthly",
        "nearby": 2.0,
        "schedule_method": "asian",
        "route": "cleared",
        "settlement_method": "financial",
        "clearing_house": "CME Clearing",
        "payment_day": "+2bd",
        "payment_calendar_key": key_of(ROLL.holiday_calendar),
    }
    ticket: dict[str, list[object]] = {
        "trade_id": [1],
        "trade_date": ["2026-05-20"],
        "contract_code": ["M26-N26"],
        "quantity": [1.0],
        "fixed_price": [price],
    }
    batch, _ = created(ROLL, ticket, terms)
    results = valued(batch, market)
    assert results.mark == pytest.approx(july - price) and results.mark == pytest.approx(4.82707510)
    assert results.cash == pytest.approx(june - price) and results.cash == pytest.approx(
        -4.82707510
    )
    assert results.mark + results.cash == pytest.approx(0.0, abs=1e-9)
    # The same strip quoted and booked on 12 June, June part fixed and both payments ahead:
    # nothing of mark and nothing of cash.
    early = quoted(history_on(JUNE_12, 2), 80.0, 81.0, 83.0, 85.0)
    fair = quote(early, "M26-N26", monthly_quote(2), "flat", None, WorkCounter())
    ahead, _ = created(ROLL, {**ticket, "fixed_price": [fair]}, terms)
    before = valued(ahead, early)
    assert (before.mark, before.cash) == (pytest.approx(0.0, abs=1e-9), 0.0)


def test_a_requests_row_is_told_to_supply_nearby_on_the_quote_template() -> None:
    with pytest.raises(ValueError) as refusal:
        rfq(
            ROLL,
            a_ticket({"contract_code": ["N26"], "quantity": [1_000.0], "nearby": [2.0]}),
            monthly_quote(2),
            WorkCounter(),
        )
    assert str(refusal.value) == (
        "nearby is a field of the quote template, expected one a request's rows hold: "
        "contract_code, start_date, end_date, quantity, payment_day; supply nearby on the quote "
        "template"
    )


def test_a_label_and_a_request_read_the_next_contract_on_every_day_of_the_month() -> None:
    # July by its label, valued 12 June with M26 at 80, N26 at 81, Q26 at 83 and U26 at 85: the
    # roll falls inside the month, and each nearby moves on with the prompt.
    market = quoted(history_on(JUNE_12, 2), 80.0, 81.0, 83.0, 85.0)
    assert quote(market, "N26", monthly_quote(1), "flat", None, WorkCounter()) == pytest.approx(
        JULY_FIRST
    )
    assert quote(market, "N26", monthly_quote(2), "flat", None, WorkCounter()) == pytest.approx(
        JULY_SECOND
    )
    # The same month as a request's row, the request saved once and priced on the market, and its
    # readback showing the nearby last.
    saved = rfq(
        ROLL,
        a_ticket({"contract_code": ["N26"], "quantity": [1_000.0]}),
        monthly_quote(2),
        WorkCounter(),
    )
    assert quote_rfq(market, saved, "flat", None, WorkCounter()) == pytest.approx(JULY_SECOND)
    table = shown(saved)
    width = table.kinds.shape[1]
    assert list(table.texts)[width - 2 : width] == ["settlement_frequency", "nearby"]
    assert table.numeric_slots[2, -1] == 2.0


def test_a_later_nearby_is_refused_by_name_where_a_quote_does_not_price_it() -> None:
    market = quoted(history_on(JUNE_12, 2), 80.0, 81.0, 83.0, 85.0)
    with pytest.raises(ValueError) as refusal:
        quote(market, "N26", monthly_quote(2, "lastday"), "flat", None, WorkCounter())
    assert str(refusal.value) == f"nearby of the quote is 2, {NOT_ASIAN}"
    with pytest.raises(ValueError) as refusal:
        rfq(
            ROLL,
            a_ticket({"contract_code": ["N26"], "quantity": [1_000.0]}),
            monthly_quote(2, "lastday"),
            WorkCounter(),
        )
    assert str(refusal.value) == f"nearby of the request is 2, {NOT_ASIAN}"
    physical = a_quote_template(
        route="cleared",
        settlement_method="physical",
        schedule_method="lastday",
        quantity_per="month",
        settlement_frequency="monthly",
        nearby=2,
    )
    with pytest.raises(ValueError) as refusal:
        quote(market, "N26", physical, "flat", None, WorkCounter())
    assert str(refusal.value) == (
        "nearby of the quote is 2, expected 1 under settlement_method = physical; a physical "
        "position delivers its own contract, and a later nearby is cash settled on its average"
    )
    # The expiry-based methods and a physical quote stand at the first nearby, as they did.
    assert quote(market, "N26", monthly_quote(1, "lastday"), "flat", None, WorkCounter()) == 81.0


def test_a_quote_past_the_schedule_the_history_or_the_live_prices_is_refused() -> None:
    # U26 is the schedule's last contract and prompt from 17 August: no second nearby that day.
    market = quoted(history_on(JUNE_12, 2), 80.0, 81.0, 83.0, 85.0)
    rule = a_quote_template(
        **{**dict(window_quote(2).values), "payment_day": DayOrRule(None, "+2bd")}
    )
    with pytest.raises(ValueError) as refusal:
        quote_by_dates(
            market, day("2026-08-14"), day("2026-08-17"), rule, "flat", None, WorkCounter()
        )
    assert str(refusal.value) == (
        "2026-08-14 to 2026-08-17 observes 2026-08-17 at nearby 2, expected at most 1 that day, "
        "'U26' being prompt and 'U26' the schedule's last contract; the schedule lists no "
        "contract for a later nearby"
    )
    # A history of the prompt's settles alone holds no settle of the second nearby.
    alone = quoted(history_on(JUNE_17, 1), 81.5, 83.5)
    with pytest.raises(ValueError) as refusal:
        quote_by_dates(alone, START, END, window_quote(2), "flat", None, WorkCounter())
    assert str(refusal.value) == (
        "requested fixing of 'N26' on 2026-06-15 is the 2nd nearby's, 'M26' being prompt that "
        "day, beyond the 1 settle a day the history holds; expected fixings with a settle "
        "column for it"
    )
    # Live prices of M26 and N26 alone: the second nearby's 16 June reads Q26.
    short = quoted(history_on(JUNE_12, 2), 80.0, 81.0)
    with pytest.raises(ValueError, match="requested contract 'Q26' is beyond live-price coverage"):
        quote_by_dates(short, START, END, window_quote(2), "flat", None, WorkCounter())
    assert quote_by_dates(short, START, END, window_quote(1), "flat", None, WorkCounter()) == 80.5
