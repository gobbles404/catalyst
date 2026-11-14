"""The fixings and the history of more than one nearby, nearby-selection.md's first slice: one
fixings object whose settles are a grid, a row per day and a column per nearby, the prompt's
first; one history holding each fixed day's settles by position and answering a fixing by its
day and its contract; the ticket's two days across an expiry, 80.5 for the first nearby and 82.5
for the second off one history; a contract the history holds no settle of refused by its day
and never substituted; a settle for a nearby the schedule lists no contract for refused when
the history is made; and a batch and a quote of today reading the prompt's column whatever the
width."""

import numpy as np
import pytest
from test_create_trades import an_index, created
from test_quote import a_template as a_quote_template
from test_trades import day, quoted
from test_utilities import rows

from catalyst.calendar.calendar import calendar
from catalyst.excel.utilities import shown
from catalyst.globals.valuation_date import valuation_date
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market_history import MarketHistory, market_history, nth
from catalyst.market_data.futures_fixings import futures_fixings
from catalyst.quoting.quote import quote_by_dates
from catalyst.trades.evaluation import trade_results
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.template import DayOrRule

# The ticket's index: contracts expiring mid-month, K26 on Friday 15 May 2026, which only bounds
# the calendar, M26 on Monday 15 June, N26 on 15 July, Q26 on 14 August and U26 on 15 September,
# the market closed on New Year's Day alone, a barrel the one specification and the lot reported.
CONTRACTS = (
    ("K26", "2026-05-15"),
    ("M26", "2026-06-15"),
    ("N26", "2026-07-15"),
    ("Q26", "2026-08-14"),
    ("U26", "2026-09-15"),
)
CODES = tuple(code for code, _ in CONTRACTS)
ROLL = an_index("ROLL", CONTRACTS, ("2027-01-01",), (("BBL", 1.0, "BBL"),), ("VOLUME", "BBL"))
K26, M26, N26, Q26, U26 = range(5)
# The two days across M26's expiry, the ticket's table: on the expiry day M26 is prompt and N26
# the second nearby, the day after N26 is prompt and Q26 the second; a third nearby beside them
# for the widths that carry one. Every other day settles 70, 72 and 74.
ACROSS = {"2026-06-15": (80.0, 82.0, 84.0), "2026-06-16": (81.0, 83.0, 85.0)}
JUNE_17 = "2026-06-17"


def history_on(
    as_of: str, nearbys: int, across: dict[str, tuple[float, float, float]] = ACROSS
) -> MarketHistory:
    """The index's history valued that day, its fixings a grid that many nearbys wide: every
    business day from Monday 18 May, the calendar's first priced day, to the day before, the
    ticket's settles on the two days across the expiry or the ones given in their place."""
    days = np.busday_offset(
        "2026-05-18", np.arange(np.busday_count("2026-05-18", as_of)), roll="forward"
    )
    grid = np.tile(np.array([70.0, 72.0, 74.0]), (days.size, 1))
    for on, settles in across.items():
        grid[days == np.datetime64(on)] = settles
    fixings = futures_fixings(days[::-1].copy(), grid[::-1, :nearbys].copy(), ROLL)
    return market_history(calendar(valuation_date(np.datetime64(as_of), 0.5), ROLL), fixings)


def rows_of(history: MarketHistory, *days: str) -> np.ndarray:
    return (np.array(days, dtype="datetime64[D]") - history.calendar.dates[0]).astype(np.intp)


def test_one_history_reads_the_first_nearby_at_80_5_and_the_second_at_82_5() -> None:
    # The ticket's table. One fixings object two columns wide, one history: each fixed day's
    # settles held by position, the prompt's first, and read by the day and the contract. The
    # first nearby is M26 on its expiry day and N26 the day after, 80 and 81; the second is N26
    # and then Q26, 82 and 83.
    history = history_on(JUNE_17, 2)
    assert history.fixing_prices.shape == (22, 2)
    assert history.fixing_prices.flags.owndata and not history.fixing_prices.flags.writeable
    rows = rows_of(history, "2026-06-15", "2026-06-16")
    assert [CODES[int(c)] for c in history.calendar.contract[rows]] == ["M26", "N26"]
    first = history.fixed_prices(rows, np.array([M26, N26]))
    second = history.fixed_prices(rows, np.array([N26, Q26]))
    assert first.tolist() == [80.0, 81.0] and first.mean() == 80.5
    assert second.tolist() == [82.0, 83.0] and second.mean() == 82.5
    # In any order asked, a row twice, each fixing its own day's and its own contract's.
    again = history.fixed_prices(rows[[1, 0, 1]], np.array([Q26, M26, N26]))
    assert again.tolist() == [83.0, 80.0, 81.0]
    # A history of the prompt alone holds the first column and answers the prompt as it did.
    alone = history_on(JUNE_17, 1)
    assert alone.fixing_prices.shape == (22, 1)
    assert alone.fixed_prices(rows, np.array([M26, N26])).tolist() == [80.0, 81.0]
    np.testing.assert_array_equal(alone.fixing_prices[:, 0], history.fixing_prices[:, 0])


def test_a_contract_the_history_holds_no_settle_of_is_refused_and_never_substituted() -> None:
    # The third nearby of the expiry day is Q26, and a history of two settles a day refuses it;
    # a history of the prompt alone refuses the second; a contract before the prompt is refused
    # at the other end, where a position below nothing would count back from the last column.
    two = history_on(JUNE_17, 2)
    rows = rows_of(two, "2026-06-15", "2026-06-16")
    with pytest.raises(ValueError) as refused:
        two.fixed_prices(rows, np.array([Q26, Q26]))
    assert str(refused.value) == (
        "requested fixing of 'Q26' on 2026-06-15 is the 3rd nearby's, 'M26' being prompt that "
        "day, beyond the 2 settles a day the history holds; expected fixings with a settle "
        "column for it"
    )
    with pytest.raises(ValueError) as refused:
        history_on(JUNE_17, 1).fixed_prices(rows, np.array([M26, Q26]))
    assert str(refused.value) == (
        "requested fixing of 'Q26' on 2026-06-16 is the 2nd nearby's, 'N26' being prompt that "
        "day, beyond the 1 settle a day the history holds; expected fixings with a settle "
        "column for it"
    )
    with pytest.raises(ValueError) as refused:
        two.fixed_prices(rows, np.array([M26, M26]))
    assert str(refused.value) == (
        "requested fixing of 'M26' on 2026-06-16 is of a contract before 'N26', the contract "
        "the calendar gives that day; a history holds the settle of that contract and of those "
        "after it"
    )
    # Three columns hold the third nearby, Q26 on the expiry day and U26 the day after.
    three = history_on(JUNE_17, 3)
    assert three.fixed_prices(rows, np.array([Q26, U26])).tolist() == [84.0, 85.0]


def test_a_settle_for_a_nearby_the_schedule_lists_no_contract_for_is_refused() -> None:
    # Each held settle is of a listed contract. Valued 18 August the fixed days run through
    # 17 August, the first day U26, the schedule's last contract, is prompt: two columns then
    # hold a second nearby with no contract to be the settle of, and three columns fail sooner,
    # on 16 July, the first day Q26 is prompt. A history that stops while two contracts remain
    # holds two columns whole.
    with pytest.raises(ValueError) as refused:
        history_on("2026-08-18", 2)
    assert str(refused.value) == (
        "fixings has 2 settles on 2026-08-17, expected at most 1, the contracts the schedule "
        "lists from 'U26', prompt that day, through 'U26', its last; a later nearby names no "
        "listed contract"
    )
    with pytest.raises(ValueError) as refused:
        history_on("2026-08-18", 3)
    assert str(refused.value) == (
        "fixings has 3 settles on 2026-07-16, expected at most 2, the contracts the schedule "
        "lists from 'Q26', prompt that day, through 'U26', its last; a later nearby names no "
        "listed contract"
    )
    assert history_on("2026-08-17", 2).fixing_prices.shape[1] == 2
    assert history_on("2026-08-18", 1).fixing_prices.shape[1] == 1


@pytest.mark.parametrize("nearbys", [1, 2, 3], ids=["one column", "two", "three"])
def test_a_first_nearby_average_reads_the_prompts_column_whatever_the_width(nearbys: int) -> None:
    # A batch and a quote of today, the first nearby's: 2,000 barrels receiving the average of
    # 15 and 16 June against 80, paid 18 June, valued 17 June with both days fixed. The average
    # is 80.5 and the mark 1,000 whatever further nearbys the history holds beside the
    # prompt's; two fixings are read, one per fixed day; and the quote of the same window is
    # the average.
    history = history_on(JUNE_17, nearbys)
    template: dict[str, object] = {
        "quantity_unit": "BBL",
        "quantity_per": "period",
        "settlement_frequency": "onetime",
        "nearby": 1.0,
        "schedule_method": "asian",
        "route": "cleared",
        "settlement_method": "financial",
        "clearing_house": "CME Clearing",
        "payment_day": day("2026-06-18"),
        "payment_holiday_calendar": ROLL.holiday_calendar,
    }
    ticket: dict[str, list[object]] = {
        "trade_id": [1],
        "trade_date": ["2026-06-01"],
        "start_date": ["2026-06-15"],
        "end_date": ["2026-06-16"],
        "quantity": [2_000.0],
        "fixed_price": [80.0],
    }
    batch, _ = created(ROLL, ticket, template)
    codes = [CODES[int(r)] for r in batch.encoded.legs[0].slot_reference]
    assert codes == ["M26", "N26"]  # the prompt on the expiry day, the next contract after it
    counter = WorkCounter()
    prepared = prepared_trades(batch.encoded, (history,), counter)
    assert counter.freeze()["fixings_read"] == 2
    assert prepared.legs[0].settle.tolist() == [80.0, 81.0]
    market = quoted(history, 81.5, 83.5)
    results = trade_results(prepared, (market,), WorkCounter())
    assert (results.mark, results.cash) == (pytest.approx(1_000.0), 0.0)
    quote = a_quote_template(
        route="cleared",
        settlement_method="financial",
        schedule_method="asian",
        quantity_per="period",
        settlement_frequency="onetime",
        nearby=1.0,
        payment_day=DayOrRule(day("2026-06-18"), None),
        payment_holiday_calendar=ROLL.holiday_calendar,
    )
    price = quote_by_dates(market, day("2026-06-15"), day("2026-06-16"), quote, None, WorkCounter())
    assert price == 80.5


def test_a_position_reads_as_the_sheet_counts_it() -> None:
    assert [nth(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 101, 111)] == [
        "1st",
        "2nd",
        "3rd",
        "4th",
        "11th",
        "12th",
        "13th",
        "21st",
        "22nd",
        "23rd",
        "101st",
        "111th",
    ]


def serial(text: str) -> float:
    """A day as the sheet holds it, the serial a spill shows."""
    return float((np.datetime64(text) - np.datetime64("1899-12-30")).astype(int))


def test_the_history_spills_each_further_nearbys_contract_and_settle_beside_the_prompts() -> None:
    # The readback: the calendar's four columns and fixing_price, the prompt's, as a history
    # always spilled; then for the second nearby the contract its settle is of, on every day,
    # and the settle where the day has fixed. On the expiry day the second nearby is N26 and
    # the day after Q26; a Saturday is closed and a day to come unfixed in both price columns;
    # and on a day U26, the schedule's last contract, is prompt no second nearby is listed, a
    # dash. A history of the prompt alone spills the five columns it always did, cell for cell.
    table = shown(history_on(JUNE_17, 2))
    spilled = rows((table.kinds, table.numeric_slots, "\0".join(table.texts)))
    assert spilled[0] == [
        "date",
        "contract",
        "is_priced",
        "is_fixed",
        "fixing_price",
        "nearby_2_contract",
        "nearby_2_fixing_price",
    ]
    assert spilled[1] == ["datetime64[D]", "str", "bool", "bool", "float64", "str", "float64"]
    by_day = {line[0]: line[1:] for line in spilled[2:]}
    assert by_day[serial("2026-06-12")] == ["M26", 1.0, 1.0, 70.0, "N26", 72.0]
    assert by_day[serial("2026-06-13")] == ["M26", 0.0, 1.0, "closed", "N26", "closed"]
    assert by_day[serial("2026-06-15")] == ["M26", 1.0, 1.0, 80.0, "N26", 82.0]
    assert by_day[serial("2026-06-16")] == ["N26", 1.0, 1.0, 81.0, "Q26", 83.0]
    assert by_day[serial("2026-06-17")] == ["N26", 1.0, 0.0, "unfixed", "Q26", "unfixed"]
    assert by_day[serial("2026-08-17")] == ["U26", 1.0, 0.0, "unfixed", "-", "unfixed"]
    alone = shown(history_on(JUNE_17, 1))
    assert rows((alone.kinds, alone.numeric_slots, "\0".join(alone.texts))) == [
        line[:5] for line in spilled
    ]
    three = shown(history_on(JUNE_17, 3))
    wide = rows((three.kinds, three.numeric_slots, "\0".join(three.texts)))
    assert wide[0][5:] == [
        "nearby_2_contract",
        "nearby_2_fixing_price",
        "nearby_3_contract",
        "nearby_3_fixing_price",
    ]
    assert {line[0]: line[5:] for line in wide[2:]}[serial("2026-06-15")] == [
        "N26",
        82.0,
        "Q26",
        84.0,
    ]
