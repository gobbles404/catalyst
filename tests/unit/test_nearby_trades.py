"""The nearby field on trades, nearby-selection.md's second slice: a fixed_float row says which
listed contract prices each of its observation days, counted from the day's prompt, 1 the prompt
and 2 the next the schedule lists, found afresh for every day by the calendar's own roll. The
ticket's two days across an expiry, 80.5 for a first-nearby row and 82.5 for a second-nearby row
off one history and one market; the two in one batch and one payment group, their exposures
apart; the selection before, on and after each roll; the states from live to paid with the
original weights standing; the hedge on the contracts actually read netting in a collection; and
the refusals, a field left out, a number that is no position, a nearby the schedule lists no
contract for, a history or a market that holds no price of it, and a later nearby where it is
not priced."""

from typing import Any

import numpy as np
import pytest
from test_create_trades import a_template, an_index, created, key_of, refused
from test_nearby_fixings import CODES, JUNE_17, ROLL, history_on
from test_quote import a_template as a_quote_template
from test_trades import day, quoted

from catalyst.calendar.calendar import contract_on
from catalyst.excel.utilities import shown
from catalyst.index_definitions.futures_schedule import FuturesSchedule
from catalyst.index_definitions.kind import Kind
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market import Market
from catalyst.quoting.quote import quote_by_dates
from catalyst.trades.aggregation import aggregate_results
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import Trades
from catalyst.trades.results import TradeResults
from catalyst.trades.schedule_methods import METHODS, ScheduleMethod
from catalyst.trades.template import DayOrRule
from catalyst.trades.terms import Settlement, nearby_rules, one_choice

# A window's terms on the ticket's index: one average over the row's days, a barrel the unit,
# cleared and paid on Thursday 18 June 2026, two days after the window's last observation.
WINDOW: dict[str, object] = {
    "quantity_unit": "BBL",
    "quantity_per": "period",
    "settlement_frequency": "onetime",
    "schedule_method": "asian",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "CME Clearing",
    "payment_day": day("2026-06-18"),
    "payment_holiday_key": key_of(ROLL.holiday_calendar),
}
JUNE_12, JUNE_16, JUNE_19 = "2026-06-12", "2026-06-16", "2026-06-19"


def rows_over(
    nearbys: tuple[float, ...] | None,
    start: str = "2026-06-15",
    end: str = "2026-06-16",
) -> dict[str, list[object]]:
    """A ticket of one row per nearby given, each 2,000 barrels against 80 over the same days,
    the ticket's two across M26's expiry unless said; no nearby column where none is given, the
    template then holding the field."""
    n = 1 if nearbys is None else len(nearbys)
    ticket: dict[str, list[object]] = {
        "trade_id": list(range(1, n + 1)),
        "trade_date": ["2026-06-01"] * n,
        "start_date": [start] * n,
        "end_date": [end] * n,
        "quantity": [2_000.0] * n,
        "fixed_price": [80.0] * n,
    }
    if nearbys is not None:
        ticket["nearby"] = list(nearbys)
    return ticket


def booked(*nearbys: float, **window: Any) -> Trades:
    """The rows booked under the window's terms, each row's nearby its own."""
    return created(ROLL, rows_over(nearbys, **window), WINDOW)[0]


def codes_of(batch: Trades) -> list[str]:
    """The contract each slot reads, in slot order: by group, by day and by contract."""
    return [CODES[int(r)] for r in batch.encoded.legs[0].slot_reference]


def valued(batch: Trades, market: Market) -> TradeResults:
    prepared = prepared_trades(batch.encoded, (market.market_history,), WorkCounter())
    return trade_results(prepared, (market,), WorkCounter())


def deltas(results: TradeResults) -> dict[str, float]:
    """The nominal delta by contract code, in barrels, the reporting lot."""
    leg = results.legs[0]
    return dict(zip(leg.codes(), leg.nominal_delta.tolist(), strict=True))


# --- the ticket's numbers -----------------------------------------------------------------------


def test_a_second_nearby_window_averages_82_5_off_the_history_a_first_reads_at_80_5() -> None:
    # The ticket's table, valued 17 June with both days fixed. The first nearby is M26 on its
    # expiry day and N26 the day after, 80 and 81; the second is N26 and then Q26, 82 and 83.
    # 2,000 barrels against 80: 1,000 at the 80.5 average and 5,000 at 82.5, off one history.
    history = history_on(JUNE_17, 2)
    market = quoted(history, 81.5, 83.5)
    first, second = booked(1.0), booked(2.0)
    assert codes_of(first) == ["M26", "N26"]
    assert codes_of(second) == ["N26", "Q26"]
    assert first.resolved.nearby.tolist() == [1] and second.resolved.nearby.tolist() == [2]
    assert not second.resolved.nearby.flags.writeable
    counter = WorkCounter()
    prepared = prepared_trades(second.encoded, (history,), counter)
    assert counter.freeze()["fixings_read"] == 2  # one per fixed day, each its own contract's
    assert prepared.legs[0].settle.tolist() == [82.0, 83.0]
    results = trade_results(prepared, (market,), WorkCounter())
    assert (results.mark, results.cash) == (pytest.approx(5_000.0), 0.0)
    assert valued(first, market).mark == pytest.approx(1_000.0)
    # The template may hold the field for every row, as it holds the frequency.
    under_template, _ = created(ROLL, rows_over(None), {**WINDOW, "nearby": 2.0})
    assert codes_of(under_template) == ["N26", "Q26"]
    assert valued(under_template, market).mark == pytest.approx(5_000.0)


def test_a_first_and_a_second_nearby_row_share_a_group_and_a_day_and_keep_their_exposures() -> None:
    # One batch, one history and one market: the two rows cover the same days and pay on the
    # same day, so they are one payment group, and on each day they read two contracts, so each
    # day is two slots. N26 is read twice, by the first nearby on the 16th and by the second on
    # the 15th: two slots, one reference on the delta axis.
    batch = booked(1.0, 2.0)
    leg = batch.encoded.legs[0]
    assert leg.slot_group.tolist() == [0, 0, 0, 0]
    assert [str(d) for d in leg.slot_date] == ["2026-06-15"] * 2 + ["2026-06-16"] * 2
    assert codes_of(batch) == ["M26", "N26", "N26", "Q26"]
    assert leg.slot_exposure.tolist() == [1_000.0] * 4  # half of each row's 2,000 on each day
    assert [CODES[int(r)] for r in leg.references] == ["M26", "N26", "Q26"]
    assert [str(d) for d in leg.days] == ["2026-06-15", "2026-06-16"]
    assert leg.day_of_slot.tolist() == [0, 0, 1, 1]


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta", "fixings"),
    [
        # Friday 12 June, nothing fixed, M26 quoted 80, N26 81 and Q26 83: the first nearby
        # projects 80.5 and the second 82, 1,000 and 4,000; N26 carries both rows' barrels.
        (JUNE_12, (80.0, 81.0, 83.0), 5_000.0, 0.0, {"M26": 1_000, "N26": 2_000, "Q26": 1_000}, 0),
        # Tuesday 16 June, the expiry day fixed at 80 and 82, N26 quoted 81 and Q26 83: 80.5
        # and 82.5, the fixed day's barrels off the delta.
        (JUNE_16, (81.0, 83.0), 6_000.0, 0.0, {"M26": 0, "N26": 1_000, "Q26": 1_000}, 2),
        # Wednesday 17 June, both days fixed and unpaid: the ticket's two averages.
        (JUNE_17, (81.5, 83.5), 6_000.0, 0.0, {"M26": 0, "N26": 0, "Q26": 0}, 4),
        # Friday 19 June, paid on the 18th: cash, nothing live.
        (JUNE_19, (81.5, 83.5), 0.0, 6_000.0, {"M26": 0, "N26": 0, "Q26": 0}, 4),
    ],
    ids=["live", "partly fixed", "fixed and unpaid", "paid"],
)
def test_the_two_rows_through_their_states_on_the_original_weights(
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: dict[str, float],
    fixings: int,
) -> None:
    batch = booked(1.0, 2.0)
    history = history_on(as_of, 2)
    counter = WorkCounter()
    prepared = prepared_trades(batch.encoded, (history,), counter)
    assert counter.freeze()["fixings_read"] == fixings
    tick = WorkCounter()
    results = trade_results(prepared, (quoted(history, *quotes),), tick)
    assert "fixings_read" not in tick.freeze().as_dict()  # a tick re-reads no fixing
    assert (results.mark, results.cash) == (pytest.approx(mark), pytest.approx(cash))
    assert deltas(results) == pytest.approx(delta)
    # The valuation day rolled and nothing of the encoding moved: the weights are the booking's.
    assert prepared.encoded is batch.encoded
    assert batch.encoded.legs[0].slot_exposure.tolist() == [1_000.0] * 4


def test_a_tick_and_a_corrected_fixing_move_the_nearby_that_reads_them() -> None:
    batch = booked(1.0, 2.0)
    # A tick of N26 on 16 June, 81 to 82: the first nearby's live day reads it, 1,000 more, and
    # the second's live day reads Q26 and stands.
    history = history_on(JUNE_16, 2)
    prepared = prepared_trades(batch.encoded, (history,), WorkCounter())
    ticked = trade_results(prepared, (quoted(history, 82.0, 83.0),), WorkCounter())
    assert ticked.mark == pytest.approx(7_000.0)
    # The second nearby's settle of 15 June corrected from 82 to 84 and the batch prepared
    # again: the second-nearby row averages 83.5, 2,000 more, and the first-nearby row, which
    # read M26 that day, is where it was.
    corrected = history_on(
        JUNE_17, 2, {"2026-06-15": (80.0, 84.0, 84.0), "2026-06-16": (81.0, 83.0, 85.0)}
    )
    market = quoted(corrected, 81.5, 83.5)
    assert valued(batch, market).mark == pytest.approx(8_000.0)
    assert valued(booked(1.0), market).mark == pytest.approx(1_000.0)
    assert valued(booked(2.0), market).mark == pytest.approx(7_000.0)


# --- the selection -----------------------------------------------------------------------------


@pytest.mark.parametrize("nearby", [1, 2])
def test_the_contract_is_the_days_prompt_and_the_nearby_counted_on_across_every_roll(
    nearby: int,
) -> None:
    # A window from Friday 12 June to Friday 14 August, across M26's expiry on 15 June, N26's on
    # 15 July and up to Q26's own on 14 August: on every day the contract is the calendar's
    # prompt for the day and the nearby counted on from it, the expiry day the expiring
    # contract's, the day after the next one's.
    terms = {**WINDOW, "payment_day": "+2bd", "nearby": float(nearby)}
    batch, _ = created(ROLL, rows_over(None, "2026-06-12", "2026-08-14"), terms)
    leg = batch.encoded.legs[0]
    schedule = ROLL.schedule
    assert isinstance(schedule, FuturesSchedule)
    prompt = contract_on(schedule, leg.slot_date)
    np.testing.assert_array_equal(leg.slot_reference, prompt + nearby - 1)
    by_day = dict(zip([str(d) for d in leg.slot_date], codes_of(batch), strict=True))
    first = {1: "M26", 2: "N26"}[nearby]
    then = {1: "N26", 2: "Q26"}[nearby]
    last = {1: "Q26", 2: "U26"}[nearby]
    assert (by_day["2026-06-12"], by_day["2026-06-15"]) == (first, first)  # before and on
    assert (by_day["2026-06-16"], by_day["2026-07-15"]) == (then, then)  # after, to the next
    assert (by_day["2026-07-16"], by_day["2026-08-14"]) == (last, last)
    assert len(by_day) == 46  # every business day of the window once, no holiday among them


def test_listed_contracts_are_counted_and_not_calendar_months() -> None:
    # A schedule listing June, September and December: the second nearby of a June day is
    # September, the next contract listed, and never July.
    gaps = an_index(
        "GAPS",
        (
            ("K26", "2026-05-15"),
            ("M26", "2026-06-15"),
            ("U26", "2026-09-15"),
            ("Z26", "2026-12-15"),
        ),
        ("2027-01-01",),
        (("BBL", 1.0, "BBL"),),
        ("VOLUME", "BBL"),
    )
    terms = {**WINDOW, "payment_holiday_key": key_of(gaps.holiday_calendar), "nearby": 2.0}
    batch, _ = created(gaps, rows_over(None), terms)
    codes = gaps.schedule.codes
    assert [codes[int(r)] for r in batch.encoded.legs[0].slot_reference] == ["U26", "Z26"]


# --- the hedge ---------------------------------------------------------------------------------


def test_a_second_nearby_window_nets_against_futures_on_the_contracts_it_reads() -> None:
    # Valued 12 June, the second-nearby window carries 1,000 barrels of N26 and 1,000 of Q26,
    # the contracts it reads, not M26 and N26, the first nearby's. A thousand barrels sold of
    # each, plain positions on their own contracts, net the collection to nothing on both.
    history = history_on(JUNE_12, 2)
    market = quoted(history, 80.0, 81.0, 83.0)
    window = valued(booked(2.0), market)
    assert deltas(window) == pytest.approx({"N26": 1_000.0, "Q26": 1_000.0})
    futures: dict[str, object] = {
        "quantity_unit": "BBL",
        "quantity_per": "month",
        "settlement_frequency": "monthly",
        "nearby": 1.0,
        "schedule_method": "lastday",
        "route": "cleared",
        "settlement_method": "financial",
        "clearing_house": "CME Clearing",
        "payment_day": "+2bd",
        "payment_holiday_key": key_of(ROLL.holiday_calendar),
    }
    sold: dict[str, list[object]] = {
        "trade_id": [10, 11],
        "trade_date": ["2026-06-01"] * 2,
        "contract_code": ["N26", "Q26"],
        "quantity": [-1_000.0, -1_000.0],
        "fixed_price": [81.0, 83.0],
    }
    hedge = valued(created(ROLL, sold, futures)[0], market)
    assert deltas(hedge) == pytest.approx({"N26": -1_000.0, "Q26": -1_000.0})
    collection = aggregate_results([window, hedge], WorkCounter())
    (group,) = collection.index_groups
    assert [CODES[int(r)] for r in group.references] == ["N26", "Q26"]
    assert group.nominal_delta.tolist() == [0.0, 0.0]
    assert group.nominal_delta_total == 0.0


# --- the readback ------------------------------------------------------------------------------


def test_the_trades_readback_ends_with_each_rows_nearby_and_then_its_calendar_key() -> None:
    table = shown(booked(1.0, 2.0))
    width = table.kinds.shape[1]
    texts = list(table.texts)
    # The heading row's end: nearby, and after it, since payment-calendar-keys.md, the key.
    assert texts[width - 3 : width] == [
        "settlement_frequency",
        "nearby",
        "payment_holiday_key",
    ]
    assert texts[2 * width - 2 : 2 * width] == ["int64", "str"]  # their types beneath
    assert table.numeric_slots[2:, -2].tolist() == [1.0, 2.0]


# --- the refusals ------------------------------------------------------------------------------


def test_the_field_is_required_of_every_batch_and_read_as_a_position() -> None:
    assert refused(ROLL, rows_over(None), WINDOW) == (
        "nearby is missing, expected a value in the template or a column in the ticket"
    )
    assert refused(ROLL, rows_over((1.0,)), {**WINDOW, "nearby": 1.0}) == (
        "nearby is supplied by the template and by the ticket, expected by one of them"
    )
    rule = (
        "expected a whole number of 1 or more, of at most 15 digits: 1 the prompt contract, 2 "
        "the next the schedule lists"
    )
    for entered, words in ((0.0, "0"), (-1.0, "-1"), (1.5, "1.5"), (1e300, "1e+300")):
        assert (
            refused(ROLL, rows_over((1.0, entered)), WINDOW) == f"nearby row 2 is {words}, {rule}"
        )
        with pytest.raises(ValueError) as refusal:
            a_template({"nearby": entered})
        assert str(refusal.value) == f"nearby is {words}, {rule}"
    with pytest.raises(ValueError) as refusal:
        a_template({"nearby": float("nan")})
    assert str(refusal.value) == f"nearby is nan, {rule}"
    assert a_template({"nearby": 3.0}).defaults["nearby"] == 3


def test_a_nearby_the_schedule_lists_no_contract_for_is_refused_by_trade_and_day() -> None:
    # U26 is the schedule's last contract and prompt from 17 August: a second nearby has no
    # contract that day. And the third nearby runs out a month sooner, when Q26 turns prompt.
    terms = {**WINDOW, "payment_day": "+2bd"}
    assert refused(ROLL, rows_over((1.0, 2.0), "2026-08-14", "2026-08-17"), terms) == (
        "trade 2 at row 2 observes 2026-08-17 at nearby 2, expected at most 1 that day, 'U26' "
        "being prompt and 'U26' the schedule's last contract; the schedule lists no contract "
        "for a later nearby"
    )
    assert refused(ROLL, rows_over((3.0,), "2026-06-12", "2026-08-14"), terms) == (
        "trade 1 at row 1 observes 2026-07-16 at nearby 3, expected at most 2 that day, 'Q26' "
        "being prompt and 'U26' the schedule's last contract; the schedule lists no contract "
        "for a later nearby"
    )


def test_a_history_or_a_market_without_the_nearbys_price_refuses_and_substitutes_nothing() -> None:
    second = booked(2.0)
    # A history of the prompt's settles alone: the second nearby's fixing is not there.
    with pytest.raises(ValueError) as refusal:
        prepared_trades(second.encoded, (history_on(JUNE_17, 1),), WorkCounter())
    assert str(refusal.value) == (
        "requested fixing of 'N26' on 2026-06-15 is the 2nd nearby's, 'M26' being prompt that "
        "day, beyond the 1 settle a day the history holds; expected fixings with a settle "
        "column for it"
    )
    # Live prices of M26 and N26 alone on 12 June: the second nearby's 16 June reads Q26.
    history = history_on(JUNE_12, 2)
    prepared = prepared_trades(second.encoded, (history,), WorkCounter())
    with pytest.raises(ValueError, match="requested contract 'Q26' is beyond live-price coverage"):
        trade_results(prepared, (quoted(history, 80.0, 81.0),), WorkCounter())
    # The first-nearby row reads M26 and N26 and values on the same two prices.
    first = prepared_trades(booked(1.0).encoded, (history,), WorkCounter())
    assert trade_results(first, (quoted(history, 80.0, 81.0),), WorkCounter()).mark == (
        pytest.approx(1_000.0)
    )


def test_a_later_nearby_is_refused_by_name_where_it_is_not_priced() -> None:
    monthly: dict[str, object] = {
        "quantity_unit": "BBL",
        "quantity_per": "month",
        "settlement_frequency": "monthly",
        "route": "cleared",
        "clearing_house": "CME Clearing",
    }
    by_code: dict[str, list[object]] = {
        "trade_id": [1, 2],
        "trade_date": ["2026-06-01"] * 2,
        "contract_code": ["N26", "N26"],
        "quantity": [1_000.0, 1_000.0],
        "fixed_price": [80.0, 80.0],
    }
    financial = {
        **monthly,
        "settlement_method": "financial",
        "payment_day": "+2bd",
        "payment_holiday_key": key_of(ROLL.holiday_calendar),
    }
    # An expiry-based method takes its own contract's days: the first such row is named, an
    # asian row beside it standing.
    mixed: dict[str, list[object]] = {
        **by_code,
        "schedule_method": ["asian", "lastday"],
        "nearby": [2.0, 2.0],
    }
    assert refused(ROLL, mixed, financial) == (
        "nearby of trade 2 at row 2 is 2, expected 1 under schedule_method = lastday; the "
        "expiry-based methods take their own contract's days, and a later nearby is priced "
        "under asian"
    )
    # A physical position delivers its own contract.
    physical = {**monthly, "settlement_method": "physical", "schedule_method": "lastday"}
    assert refused(ROLL, {**by_code, "nearby": [1.0, 2.0]}, physical) == (
        "nearby of trade 2 at row 2 is 2, expected 1 under settlement_method = physical; a "
        "physical position delivers its own contract, and a later nearby is cash settled on its "
        "average"
    )
    # A published index and a pair, the kernel's rule over the occurrences: the first later nearby
    # named, and every row at 1 standing under any terms.
    later = np.array([1, 2], dtype=np.intp)
    asian = one_choice(METHODS, ScheduleMethod.ASIAN, 2)

    def named(k: int) -> str:
        return f"trade at row {k + 1}"

    with pytest.raises(ValueError) as refusal:
        nearby_rules(later, asian, Settlement.FINANCIAL, Kind.PUBLISHED, False, named)
    assert str(refusal.value) == (
        "nearby of trade at row 2 is 2, expected 1 on a published index; a print counts toward "
        "its own month, and there is no contract to roll"
    )
    with pytest.raises(ValueError) as refusal:
        nearby_rules(later, asian, Settlement.FINANCIAL, Kind.FUTURES, True, named)
    assert str(refusal.value) == (
        "nearby of trade at row 2 is 2, expected 1 with two indexes; a later nearby on a pair is "
        "not built"
    )
    lastday = one_choice(METHODS, ScheduleMethod.LASTDAY, 2)
    nearby_rules(
        np.ones(2, dtype=np.intp), lastday, Settlement.PHYSICAL, Kind.PUBLISHED, True, named
    )


def test_a_quote_template_is_required_to_hold_the_field() -> None:
    # What a quote prices under the field is tests/unit/test_nearby_quotes.py's.
    market = quoted(history_on(JUNE_17, 2), 81.5, 83.5)
    terms: dict[str, object] = {
        "route": "cleared",
        "settlement_method": "financial",
        "schedule_method": "asian",
        "quantity_per": "period",
        "settlement_frequency": "onetime",
        "payment_day": DayOrRule(day("2026-06-18"), None),
        "payment_holiday_key": key_of(ROLL.holiday_calendar),
    }
    start, end = day("2026-06-15"), day("2026-06-16")
    with pytest.raises(ValueError) as refusal:
        quote_by_dates(market, start, end, a_quote_template(**terms), "flat", None, WorkCounter())
    assert str(refusal.value) == "nearby is missing, expected it in the quote template"
    first = a_quote_template(**terms, nearby=1)
    assert quote_by_dates(market, start, end, first, "flat", None, WorkCounter()) == 80.5
