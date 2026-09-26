"""The market's creators through the seam: the history, two handles in and one out, and the table
its handle spills, the calendar's four columns and a fixing price on each day, a number or a
word; then the market, the history and a price vector in, and the table its handle spills, a
price on every business day."""

import functools
import re
from typing import cast

import numpy as np
import pytest
from test_utilities import read, rows

from goosedove.excel import bridge
from goosedove.excel.bridge import BOOLEAN_CODE, MISSING, NUMBER_CODE, TEXT_CODE, Cells

# The page's sample as the sheet sends it: serials for 18 to 22 May, 25 and 26 May, 22 June and
# 21 July 2026, and 1 January.
MAY_18, MAY_19, MAY_20, MAY_21, MAY_22 = 46160.0, 46161.0, 46162.0, 46163.0, 46164.0
MAY_25, MAY_26, JUN_22, JUL_21, JAN_1 = 46167.0, 46168.0, 46195.0, 46224.0, 46023.0
HANDLE = re.compile(r"market_history:.+:([0-9]+)")
HEADERS = ["date", "contract", "is_priced", "is_fixed", "fixing_price"]
TYPES = ["datetime64[D]", "str", "bool", "bool", "float64"]
SAMPLE = [[MAY_20, 70.85], [MAY_21, 71.10], [MAY_22, 71.25]]


def column(*cells: object) -> Cells:
    return Cells.from_rows([[cell] for cell in cells])


def a_valuation(serial: float = MAY_26, fraction: float = 0.5) -> str:
    text = bridge.call("_CreateValuationDate", [serial, fraction])
    assert isinstance(text, str) and text.startswith("valuation_date:"), text
    return text


def a_schedule(codes: tuple[str, ...], expiries: tuple[float, ...]) -> str:
    text = bridge.call("_CreateFuturesSchedule", [column(*codes), column(*expiries), MISSING])
    assert isinstance(text, str) and text.startswith("futures_schedule:"), text
    return text


def a_holiday_calendar(*serials: float) -> str:
    text = bridge.call("_CreateHolidayCalendar", [column(*serials)])
    assert isinstance(text, str) and text.startswith("holiday_calendar:"), text
    return text


SCHEDULE = (("m26", "n26", "q26"), (MAY_19, JUN_22, JUL_21))


def an_index(schedule: object, holidays: object = MISSING, name: str = "WTI NYMEX") -> str:
    """The index handle of that schedule handle and holiday calendar handle, with one set of
    conventions and specifications, since nothing here reads either. Each call publishes a new
    index, as each _CreateIndex cell does; a calendar and the fixings it binds share one."""
    conventions = bridge.call("_CreateIndexConventions", ["USD", "BBL", "USD", "volume", "BBL"])
    specifications = bridge.call(
        "_CreateContractSpecifications",
        [
            Cells.from_rows(
                [["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
            ),
            Cells.from_rows([["NYMEX", 1000.0, 0.0, 0.0]]),
        ],
    )
    text = bridge.call("_CreateIndex", [name, schedule, conventions, specifications, holidays])
    assert isinstance(text, str) and text.startswith("index:"), text
    return text


@functools.cache
def index_closed_on(*serials: float) -> str:
    """The futures index of the sample's schedule with those holidays, made once per list, so
    that a calendar and fixings made over it share one object."""
    return an_index(a_schedule(*SCHEDULE), a_holiday_calendar(*serials))


def the_index() -> str:
    return index_closed_on(MAY_25)


def a_calendar(valuation: str | None = None, index: str | None = None) -> str:
    args = [valuation or a_valuation(), index or the_index()]
    text = bridge.call("_CreateCalendar", args)
    assert isinstance(text, str) and text.startswith("calendar:"), text
    return text


def the_fixings(body: list[list[float]] = SAMPLE, index: str | None = None) -> str:
    days = Cells.from_rows([[day] for day, _ in body])
    settles = Cells.from_rows([[settle] for _, settle in body])
    args = [days, settles, index or the_index()]
    text = bridge.call("_CreateFuturesFixings", args)
    assert isinstance(text, str) and text.startswith("futures_fixings:"), text
    return text


def a_history(calendar: str | None = None, fixings: str | None = None) -> str:
    text = bridge.call("_CreateMarketHistory", [calendar or a_calendar(), fixings or the_fixings()])
    assert isinstance(text, str) and HANDLE.fullmatch(text), text
    return text


def number(text: str) -> int:
    match = HANDLE.fullmatch(text)
    assert match, text
    return int(match.group(1))


def test_a_history_is_created_from_two_handles_and_read_back_day_by_day() -> None:
    shown = rows(read(a_history()))
    assert len(shown) == 65
    assert shown[0] == HEADERS
    assert shown[1] == TYPES
    assert shown[2] == [MAY_20, "n26", 1.0, 1.0, 70.85]
    assert shown[3] == [MAY_21, "n26", 1.0, 1.0, 71.10]
    assert shown[4] == [MAY_22, "n26", 1.0, 1.0, 71.25]
    assert shown[5] == [MAY_22 + 1, "n26", 0.0, 1.0, "closed"]
    assert shown[6] == [MAY_22 + 2, "n26", 0.0, 1.0, "closed"]
    assert shown[7] == [MAY_25, "n26", 0.0, 1.0, "closed"]
    assert shown[8] == [MAY_26, "n26", 1.0, 0.0, "unfixed"]
    assert shown[9] == [MAY_26 + 1, "n26", 1.0, 0.0, "unfixed"]
    assert shown[36] == [JUN_22 + 1, "q26", 1.0, 0.0, "unfixed"]
    assert shown[64] == [JUL_21, "q26", 1.0, 0.0, "unfixed"]
    assert [row[0] for row in shown[2:]] == [MAY_20 + i for i in range(63)]


# Every row of the calendar's own spill stands in the history's, and the fifth cell follows the
# two flags: closed where the market is shut, unfixed where it is open and the day not past, and
# the settle, a number, where it is open and past.
def test_every_calendar_row_stands_and_the_fifth_cell_follows_the_flags() -> None:
    calendar = a_calendar()
    days = rows(read(calendar))
    shown = rows(read(a_history(calendar=calendar)))
    assert [row[:4] for row in shown] == days
    fifth = [row[4] for row in shown[2:]]
    expected: list[object] = []
    for _, _, open_, past in days[2:]:
        expected.append("closed" if not open_ else "unfixed" if not past else "a number")
    assert [word if word in ("closed", "unfixed") else "a number" for word in fifth] == expected
    assert fifth.count("closed") == 19 and fifth.count("unfixed") == 41


# The sheet is handed a number on each fixed day and text on every other, the calendar's own
# kinds before it: the kinds say so, not the numbers behind them.
def test_the_fixing_price_reaches_the_sheet_as_a_number_where_fixed_and_text_elsewhere() -> None:
    kinds, _, _ = read(a_history())
    assert (kinds[:2] == TEXT_CODE).all()
    assert (kinds[2:, 0] == NUMBER_CODE).all()
    assert (kinds[2:, 1] == TEXT_CODE).all()
    assert (kinds[2:, 2:4] == BOOLEAN_CODE).all()
    assert kinds[2:5, 4].tolist() == [NUMBER_CODE] * 3
    assert (kinds[5:, 4] == TEXT_CODE).all()


def test_a_settle_of_zero_is_a_number_and_a_day_without_one_is_a_word() -> None:
    fixings = the_fixings([[MAY_20, 0.0], [MAY_21, -37.63], [MAY_22, 71.25]])
    spill = read(a_history(fixings=fixings))
    kinds, _, _ = spill
    shown = rows(spill)
    assert shown[2][4] == 0.0 and kinds[2, 4] == NUMBER_CODE
    assert shown[3][4] == -37.63 and kinds[3, 4] == NUMBER_CODE
    assert shown[5][4] == "closed" and kinds[5, 4] == TEXT_CODE
    assert shown[8][4] == "unfixed" and kinds[8, 4] == TEXT_CODE


# Valued on 20 May, the calendar's first day, no day is past: the fixings, on the Monday and
# Tuesday before, are before the valuation date and unused, and every row shows a word.
def test_a_calendar_with_no_past_business_day_is_a_history_without_a_price() -> None:
    fixings = the_fixings([[MAY_18, 70.0], [MAY_19, 70.5]])
    made = a_history(calendar=a_calendar(valuation=a_valuation(MAY_20)), fixings=fixings)
    shown = rows(read(made))
    assert len(shown) == 65
    assert shown[2] == [MAY_20, "n26", 1.0, 0.0, "unfixed"]
    assert {row[4] for row in shown[2:]} == {"closed", "unfixed"}


THE_CALENDAR, THE_FIXINGS = object(), object()


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [THE_CALENDAR, ([*SAMPLE, [MAY_26, 71.5]], MAY_25)],
            "#ERROR _CreateMarketHistory: ValueError: fixings date 2026-05-26 is on or "
            "after valuation date 2026-05-26, expected dates before the valuation date",
        ),
        (
            [THE_CALENDAR, ([*SAMPLE, [MAY_25, 71.4]], JAN_1)],
            "#ERROR _CreateMarketHistory: ValueError: fixings is over another index, "
            "'WTI NYMEX', expected the calendar's, 'WTI NYMEX'",
        ),
        (
            [THE_CALENDAR, (SAMPLE[:2], MAY_25)],
            "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for "
            "2026-05-22, expected a fixing for every fixed day in calendar",
        ),
        (
            [JAN_1, THE_FIXINGS],
            "#ERROR _CreateMarketHistory: ValueError: fixings is over another index, "
            "'WTI NYMEX', expected the calendar's, 'WTI NYMEX'",
        ),
        (
            [MISSING, THE_FIXINGS],
            "#ERROR _CreateMarketHistory: calendar is missing, expected calendar handle",
        ),
        (
            [None, THE_FIXINGS],
            "#ERROR _CreateMarketHistory: calendar is blank, expected calendar handle",
        ),
        (
            [MAY_26, THE_FIXINGS],
            "#ERROR _CreateMarketHistory: calendar is number 46168.0, expected calendar handle",
        ),
        (
            ["x", THE_FIXINGS],
            "#ERROR _CreateMarketHistory: calendar is text 'x' naming no live object, "
            "expected calendar handle",
        ),
        (
            [THE_CALENDAR, MISSING],
            "#ERROR _CreateMarketHistory: fixings is missing, expected a handle",
        ),
        (
            [THE_CALENDAR, None],
            "#ERROR _CreateMarketHistory: fixings is blank, expected a handle",
        ),
        (
            [THE_CALENDAR, 70.85],
            "#ERROR _CreateMarketHistory: fixings is number 70.85, expected a handle",
        ),
        (
            [THE_CALENDAR, "futures_fixings:9999999"],
            "#ERROR _CreateMarketHistory: fixings is text 'futures_fixings:9999999' "
            "naming no live object, expected a handle",
        ),
        (
            [THE_CALENDAR, "#ERROR _CreateFuturesFixings: date is blank, expected column of dates"],
            "#ERROR _CreateMarketHistory: fixings is the creator's failure, expected a handle: "
            "#ERROR _CreateFuturesFixings: date is blank, expected column of dates",
        ),
    ],
    ids=[
        "a fixing on the valuation date",
        "fixings over another index of the same name, closed elsewhere",
        "the last fixed day without a fixing",
        "a calendar over another index of the same name",
        "the calendar left out",
        "a blank cell where the calendar should be",
        "a number where the calendar should be",
        "text naming no live calendar",
        "the fixings left out",
        "a blank cell where the fixings should be",
        "a number where the fixings should be",
        "text naming no live fixings",
        "the fixings creator's failure relayed",
    ],
)
def test_a_history_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    calendar, fixings = args
    if calendar is THE_CALENDAR:
        calendar = a_calendar()
    elif calendar == JAN_1:
        calendar = a_calendar(index=index_closed_on(JAN_1))
    if fixings is THE_FIXINGS:
        fixings = the_fixings()
    elif isinstance(fixings, tuple):
        body, holiday = cast(tuple[list[list[float]], float], fixings)
        fixings = the_fixings(body, index_closed_on(holiday))
    assert bridge.call("_CreateMarketHistory", [calendar, fixings]) == text


def test_a_handle_of_another_kind_in_either_slot_is_refused_by_name() -> None:
    calendar, fixings = a_calendar(), the_fixings()
    made = a_history(calendar, fixings)
    assert bridge.call("_CreateMarketHistory", [fixings, fixings]) == (
        f"#ERROR _CreateMarketHistory: calendar is futures fixings handle {fixings!r}, "
        "expected calendar handle"
    )
    assert bridge.call("_CreateMarketHistory", [made, fixings]) == (
        f"#ERROR _CreateMarketHistory: calendar is market history handle {made!r}, "
        "expected calendar handle"
    )
    # The fixings slot takes any handle, so a calendar or a history there reaches the library,
    # which names what it is.
    assert bridge.call("_CreateMarketHistory", [calendar, calendar]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings is a calendar, "
        "expected futures, IFERC or Gas Daily fixings"
    )
    assert bridge.call("_CreateMarketHistory", [calendar, made]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings is a market history, "
        "expected futures, IFERC or Gas Daily fixings"
    )


def test_a_failed_construction_publishes_no_object_and_no_handle() -> None:
    calendar, fixings = a_calendar(), the_fixings()
    short = the_fixings(SAMPLE[:2])
    before = number(a_history(calendar, fixings))
    assert bridge.call("_CreateMarketHistory", [calendar, short]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 2026-05-22, "
        "expected a fixing for every fixed day in calendar"
    )
    assert number(a_history(calendar, fixings)) == before + 1


def test_two_histories_from_one_calendar_each_read_their_own_prices() -> None:
    calendar = a_calendar()
    first = a_history(calendar, the_fixings())
    second = a_history(calendar, the_fixings([[MAY_20, 1.0], [MAY_21, 2.0], [MAY_22, 3.0]]))
    assert [row[4] for row in rows(read(first))[2:5]] == [70.85, 71.10, 71.25]
    assert [row[4] for row in rows(read(second))[2:5]] == [1.0, 2.0, 3.0]
    assert [row[:4] for row in rows(read(first))] == [row[:4] for row in rows(read(second))]


# A _CreateIndex cell recalculated is a new index: the calendar over the old one with fixings
# over the new is refused, the name shown twice, and both remade over the new one read as before.
def test_an_index_remade_is_another_index_until_the_calendar_and_the_fixings_are_remade() -> None:
    before = rows(read(a_history()))
    remade = an_index(a_schedule(*SCHEDULE), a_holiday_calendar(MAY_25))
    fixings = the_fixings(index=remade)
    assert bridge.call("_CreateMarketHistory", [a_calendar(), fixings]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings is over another index, 'WTI NYMEX', "
        "expected the calendar's, 'WTI NYMEX'"
    )
    assert rows(read(a_history(a_calendar(index=remade), fixings))) == before


def test_a_dead_history_handle_cannot_be_read() -> None:
    assert bridge.call("util_ReadHandle", ["market_history:9999999"]) == (
        "#ERROR util_ReadHandle: handle is text 'market_history:9999999' naming no live "
        "object, expected a handle"
    )


# --- _CreateMarket -----------------------------------------------------------------


MARKET = re.compile(r"market:.+:([0-9]+)")
MARKET_HEADERS = ["date", "contract", "is_priced", "is_fixed", "price"]
JUN_18, JUN_19, JUN_23 = 46191.0, 46192.0, 46196.0


def a_vector(*prices: float, name: str = "WTI NYMEX") -> str:
    """The handle of a vector of those quotes, named for the futures index every history here
    is over unless named otherwise."""
    text = bridge.call("_CreatePriceVector", [name, column(*prices)])
    assert isinstance(text, str) and text.startswith("price_vector:"), text
    return text


def a_market(history: str | None = None, vector: str | None = None) -> str:
    text = bridge.call("_CreateMarket", [history or a_history(), vector or a_vector(72.10, 72.80)])
    assert isinstance(text, str) and MARKET.fullmatch(text), text
    return text


def market_number(text: str) -> int:
    match = MARKET.fullmatch(text)
    assert match, text
    return int(match.group(1))


def whole_fixings(first: float, last: float, *listed: float) -> str:
    """A fixing on every business day from the first serial to the last, the listed serials the
    holidays, checked against a calendar of those days; the last day's settle 71.60 and the
    rest below it."""
    epoch = np.datetime64("1899-12-30")
    serials = np.arange(int(first), int(last) + 1)
    days = epoch + serials.astype("timedelta64[D]")
    closed = epoch + np.array(listed, dtype=np.int64).astype("timedelta64[D]")
    kept = serials[np.is_busday(days, holidays=closed)].tolist()
    body = [[float(s), 70.0 + i * 0.05] for i, s in enumerate(kept)]
    body[-1][1] = 71.60
    return the_fixings(body, index_closed_on(*listed))


# The sample: the history of the tests above, valued on 26 May with the 25th a holiday, and two
# quotes, n26's and q26's. Every past business day keeps its fixing, every business day from
# the valuation day on takes its prompt contract's quote, and every other day is closed.
def test_a_market_is_created_from_two_handles_and_read_back_day_by_day() -> None:
    shown = rows(read(a_market()))
    assert len(shown) == 65
    assert shown[0] == MARKET_HEADERS
    assert shown[1] == TYPES
    assert shown[2] == [MAY_20, "n26", 1.0, 1.0, 70.85]
    assert shown[4] == [MAY_22, "n26", 1.0, 1.0, 71.25]
    assert shown[5] == [MAY_22 + 1, "n26", 0.0, 1.0, "closed"]
    assert shown[7] == [MAY_25, "n26", 0.0, 1.0, "closed"]
    assert shown[8] == [MAY_26, "n26", 1.0, 0.0, 72.10]
    assert shown[9] == [MAY_26 + 1, "n26", 1.0, 0.0, 72.10]
    assert shown[35] == [JUN_22, "n26", 1.0, 0.0, 72.10]
    assert shown[36] == [JUN_22 + 1, "q26", 1.0, 0.0, 72.80]
    assert shown[64] == [JUL_21, "q26", 1.0, 0.0, 72.80]
    fifth = [row[4] for row in shown[2:]]
    assert "unfixed" not in fifth
    assert fifth.count("closed") == 19
    assert [row[0] for row in shown[2:]] == [MAY_20 + i for i in range(63)]


# The page's example: valued on 22 June, n26's expiry day, with 19 June a holiday and the
# fixings whole through the 18th. The expiring contract is quoted on its expiry day, q26 from
# the day after, and the fixing on the 18th stands though n26 has a live quote too.
def test_the_expiring_contract_is_quoted_on_its_expiry_day_and_the_next_from_the_day_after() -> (
    None
):
    calendar = a_calendar(valuation=a_valuation(JUN_22, 1.0), index=index_closed_on(JUN_19))
    history = bridge.call("_CreateMarketHistory", [calendar, whole_fixings(MAY_20, JUN_18, JUN_19)])
    assert isinstance(history, str) and history.startswith("market_history:")
    shown = rows(read(a_market(history)))
    by_day = {row[0]: row[1:] for row in shown[2:]}
    assert by_day[JUN_18] == ["n26", 1.0, 1.0, 71.60]
    assert by_day[JUN_19] == ["n26", 0.0, 1.0, "closed"]
    assert by_day[JUN_19 + 1] == ["n26", 0.0, 1.0, "closed"]
    assert by_day[JUN_19 + 2] == ["n26", 0.0, 1.0, "closed"]
    assert by_day[JUN_22] == ["n26", 1.0, 0.0, 72.10]
    assert by_day[JUN_23] == ["q26", 1.0, 0.0, 72.80]
    assert by_day[JUL_21] == ["q26", 1.0, 0.0, 72.80]


# Valued on the calendar's last day, one quote is required, and on its first day two, with the
# fixings before the calendar unused; valued on a Saturday, the prompt contract of that day is
# the first quoted, and nothing moves to the Monday.
def test_valuation_on_the_first_or_last_day_or_a_weekend_needs_the_prompt_contracts_quotes() -> (
    None
):
    last = a_history(
        calendar=a_calendar(valuation=a_valuation(JUL_21)),
        fixings=whole_fixings(MAY_20, JUL_21 - 1, MAY_25),
    )
    shown = rows(read(a_market(last, a_vector(72.80))))
    assert shown[64] == [JUL_21, "q26", 1.0, 0.0, 72.80]
    assert shown[63][4] == 71.60
    first = a_history(
        calendar=a_calendar(valuation=a_valuation(MAY_20)),
        fixings=the_fixings([[MAY_18, 70.0], [MAY_19, 70.5]]),
    )
    shown = rows(read(a_market(first)))
    assert shown[2] == [MAY_20, "n26", 1.0, 0.0, 72.10]
    assert {row[4] for row in shown[2:]} == {72.10, 72.80, "closed"}
    saturday = a_history(
        calendar=a_calendar(valuation=a_valuation(MAY_22 + 1)), fixings=the_fixings(SAMPLE)
    )
    shown = rows(read(a_market(saturday)))
    assert shown[5] == [MAY_22 + 1, "n26", 0.0, 0.0, "closed"]
    assert shown[8] == [MAY_26, "n26", 1.0, 0.0, 72.10]


# The sheet is handed a number on every business day and text on every closed day.
def test_the_price_reaches_the_sheet_as_a_number_on_every_business_day() -> None:
    kinds, _, _ = read(a_market())
    calendar_kinds, _, _ = read(a_calendar())
    assert (kinds[:, :4] == calendar_kinds).all()
    assert (kinds[:2, 4] == TEXT_CODE).all()
    open_ = calendar_kinds[2:, 2] == BOOLEAN_CODE  # every flag cell; the flag's value is below
    assert open_.all()
    _, slots, _ = read(a_calendar())
    assert (kinds[2:, 4] == np.where(slots[2:, 2] == 1.0, NUMBER_CODE, TEXT_CODE)).all()


def test_a_zero_a_negative_and_a_repeated_quote_are_shown_as_given() -> None:
    shown = rows(read(a_market(vector=a_vector(0.0, -0.5))))
    assert shown[8][4] == 0.0 and shown[36][4] == -0.5
    shown = rows(read(a_market(vector=a_vector(72.10, 72.10))))
    assert shown[8][4] == 72.10 and shown[36][4] == 72.10


def test_two_markets_share_one_history_and_each_reads_its_own_quotes() -> None:
    history = a_history()
    first = a_market(history, a_vector(72.10, 72.80))
    second = a_market(history, a_vector(1.0, 2.0))
    assert [row[4] for row in rows(read(first))[8:10]] == [72.10, 72.10]
    assert [row[4] for row in rows(read(second))[8:10]] == [1.0, 1.0]
    assert [row[:4] for row in rows(read(first))] == [row[:4] for row in rows(read(second))]
    assert rows(read(first))[2][4] == rows(read(second))[2][4] == 70.85


THE_HISTORY, THE_VECTOR = object(), object()


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [THE_HISTORY, (72.10,)],
            "#ERROR _CreateMarket: ValueError: price_vector has 1 price, expected 2, "
            "one per contract from 'n26' through 'q26'",
        ),
        (
            [THE_HISTORY, (72.10, 72.80, 73.0)],
            "#ERROR _CreateMarket: ValueError: price_vector has 3 prices, expected 2, "
            "one per contract from 'n26' through 'q26'",
        ),
        (
            [JUL_21 + 1, (72.80,)],
            "#ERROR _CreateMarket: ValueError: market_history has no unfixed period, "
            "expected at least one to quote",
        ),
        (
            [MISSING, THE_VECTOR],
            "#ERROR _CreateMarket: market_history is missing, expected market history handle",
        ),
        (
            [None, THE_VECTOR],
            "#ERROR _CreateMarket: market_history is blank, expected market history handle",
        ),
        (
            [72.10, THE_VECTOR],
            "#ERROR _CreateMarket: market_history is number 72.1, expected market history handle",
        ),
        (
            ["x", THE_VECTOR],
            "#ERROR _CreateMarket: market_history is text 'x' naming no live object, "
            "expected market history handle",
        ),
        (
            [THE_HISTORY, MISSING],
            "#ERROR _CreateMarket: price_vector is missing, expected price vector handle",
        ),
        (
            [THE_HISTORY, None],
            "#ERROR _CreateMarket: price_vector is blank, expected price vector handle",
        ),
        (
            [THE_HISTORY, 72.10],
            "#ERROR _CreateMarket: price_vector is number 72.1, expected price vector handle",
        ),
        (
            [THE_HISTORY, "price_vector:9999999"],
            "#ERROR _CreateMarket: price_vector is text 'price_vector:9999999' naming no "
            "live object, expected price vector handle",
        ),
        (
            [THE_HISTORY, "#ERROR _CreatePriceVector: prices is blank, expected column of numbers"],
            "#ERROR _CreateMarket: price_vector is the creator's failure, expected price vector "
            "handle: #ERROR _CreatePriceVector: prices is blank, expected column of numbers",
        ),
    ],
    ids=[
        "one quote too few",
        "one quote too many",
        "valued the day after the calendar, the count unchecked",
        "the history left out",
        "a blank cell where the history should be",
        "a number where the history should be",
        "text naming no live history",
        "the vector left out",
        "a blank cell where the vector should be",
        "a number where the vector should be",
        "text naming no live vector",
        "the vector creator's failure relayed",
    ],
)
def test_a_market_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    history, vector = args
    if history is THE_HISTORY:
        history = a_history()
    elif history == JUL_21 + 1:
        history = a_history(
            calendar=a_calendar(valuation=a_valuation(JUL_21 + 1)),
            fixings=whole_fixings(MAY_20, JUL_21, MAY_25),
        )
    if vector is THE_VECTOR:
        vector = a_vector(72.10, 72.80)
    elif isinstance(vector, tuple):
        vector = a_vector(*cast(tuple[float, ...], vector))
    assert bridge.call("_CreateMarket", [history, vector]) == text


# Valued on 19 May 2026, m26's expiry day and the day before the calendar begins, with a fixing
# on the 18th, before it: nothing is fixed, and two quotes make a market from the 20th on, n26's
# quote on every business day through its expiry and q26's after.
def test_a_history_valued_before_its_calendar_is_a_market_from_the_calendars_first_day() -> None:
    history = a_history(
        calendar=a_calendar(valuation=a_valuation(MAY_19)), fixings=the_fixings([[MAY_18, 70.0]])
    )
    shown = rows(read(a_market(history)))
    assert shown[2] == [MAY_20, "n26", 1.0, 0.0, 72.10]
    assert shown[35] == [JUN_22, "n26", 1.0, 0.0, 72.10]
    assert shown[36] == [JUN_22 + 1, "q26", 1.0, 0.0, 72.80]
    assert {row[4] for row in shown[2:]} == {72.10, 72.80, "closed"}


def test_a_handle_of_another_kind_in_either_market_slot_is_refused_by_name() -> None:
    history, vector = a_history(), a_vector(72.10, 72.80)
    made = a_market(history, vector)
    assert bridge.call("_CreateMarket", [vector, vector]) == (
        f"#ERROR _CreateMarket: market_history is price vector handle {vector!r}, "
        "expected market history handle"
    )
    assert bridge.call("_CreateMarket", [history, history]) == (
        f"#ERROR _CreateMarket: price_vector is market history handle {history!r}, "
        "expected price vector handle"
    )
    assert bridge.call("_CreateMarket", [made, vector]) == (
        f"#ERROR _CreateMarket: market_history is market handle {made!r}, "
        "expected market history handle"
    )


def test_a_failed_market_publishes_no_object_and_no_handle() -> None:
    history, vector, short = a_history(), a_vector(72.10, 72.80), a_vector(72.10)
    before = market_number(a_market(history, vector))
    assert bridge.call("_CreateMarket", [history, short]) == (
        "#ERROR _CreateMarket: ValueError: price_vector has 1 price, expected 2, "
        "one per contract from 'n26' through 'q26'"
    )
    assert market_number(a_market(history, vector)) == before + 1


# The history's and the market's handles carry their index's name between the tag and the count.
def test_history_and_market_handles_carry_their_indexs_name() -> None:
    history = a_history()
    assert history.startswith("market_history:WTI NYMEX:")
    made = a_market(history)
    assert made.startswith("market:WTI NYMEX:")
    assert made[len("market:WTI NYMEX:") :].isdigit()


def test_repeated_market_calls_publish_fresh_handles_and_the_earlier_ones_stand() -> None:
    history, vector = a_history(), a_vector(72.10, 72.80)
    first = a_market(history, vector)
    second = a_market(history, vector)
    assert market_number(second) == market_number(first) + 1
    assert rows(read(first)) == rows(read(second))


# Releasing the vector's entry leaves the market whole: it holds the vector by its own reference,
# so its spill still reads the quotes while the vector's text names nothing.
def test_a_market_outlives_the_release_of_its_vectors_entry() -> None:
    history, vector = a_history(), a_vector(72.10, 72.80)
    made = a_market(history, vector)
    shown = rows(read(made))
    assert bridge.release(vector) is True
    assert rows(read(made)) == shown
    assert bridge.call("util_ReadHandle", [vector]) == (
        f"#ERROR util_ReadHandle: handle is text {vector!r} naming no live object, "
        "expected a handle"
    )
    assert bridge.release(made) is True


def test_a_dead_market_handle_cannot_be_read() -> None:
    assert bridge.call("util_ReadHandle", ["market:9999999"]) == (
        "#ERROR util_ReadHandle: handle is text 'market:9999999' naming no live object, "
        "expected a handle"
    )


# --- the two other histories through the seam ---------------------------------------------

# Serials for the schedule pages' samples: the Gas Daily months' first and last days, the IFERC
# months' last trading and publication days, and the valuation dates 25 September and 15
# November 2026.
SEP_1, SEP_25, SEP_30, OCT_1, OCT_31 = 46266.0, 46290.0, 46295.0, 46296.0, 46326.0
NOV_1, NOV_30, OCT_30, NOV_2, NOV_15, DEC_1 = 46327.0, 46356.0, 46325.0, 46328.0, 46341.0, 46357.0


@functools.cache
def the_gas_daily_index() -> str:
    """The Gas Daily index of the schedule page's three months, made once."""
    schedule = bridge.call(
        "_CreateGasDailySchedule",
        [column("U26", "V26", "X26"), column(SEP_1, OCT_1, NOV_1), column(SEP_30, OCT_31, NOV_30)],
    )
    return an_index(schedule, MISSING, "Henry Hub Gas Daily")


def a_gas_daily_calendar(as_of: float = SEP_25) -> str:
    text = bridge.call("_CreateCalendar", [a_valuation(as_of), the_gas_daily_index()])
    assert isinstance(text, str) and text.startswith("calendar:"), text
    return text


def prints_through(first: float, last: float) -> str:
    """A print on every flow day from the first serial to the last, 2.80 rising by a cent."""
    serials = [first + i for i in range(int(last - first) + 1)]
    prices = [2.80 + i / 100 for i in range(len(serials))]
    args = [column(*serials), column(*prices), the_gas_daily_index()]
    text = bridge.call("_CreateGasDailyFixings", args)
    assert isinstance(text, str) and text.startswith("gas_daily_fixings:"), text
    return text


@functools.cache
def the_iferc_index() -> str:
    """The IFERC index of the schedule page's three months, made once."""
    schedule = bridge.call(
        "_CreateIfercSchedule",
        [column("V26", "X26", "Z26"), column(SEP_30, OCT_30, NOV_30), column(OCT_1, NOV_2, DEC_1)],
    )
    return an_index(schedule, MISSING, "Henry Hub IFERC")


def an_iferc_calendar(as_of: float = NOV_15) -> str:
    text = bridge.call("_CreateCalendar", [a_valuation(as_of), the_iferc_index()])
    assert isinstance(text, str) and text.startswith("calendar:"), text
    return text


def indices_for(*pairs: tuple[str, float]) -> str:
    codes = column(*(code for code, _ in pairs))
    prices = column(*(price for _, price in pairs))
    text = bridge.call("_CreateIfercFixings", [codes, prices, the_iferc_index()])
    assert isinstance(text, str) and text.startswith("iferc_fixings:"), text
    return text


def test_a_gas_daily_history_is_created_from_two_handles_and_read_back_day_by_day() -> None:
    made = bridge.call(
        "_CreateMarketHistory", [a_gas_daily_calendar(), prints_through(SEP_1, SEP_25)]
    )
    assert isinstance(made, str) and HANDLE.fullmatch(made), made
    shown = rows(read(made))
    assert len(shown) == 93
    assert shown[0] == HEADERS and shown[1] == TYPES
    assert shown[2] == [SEP_1, "U26", 1.0, 1.0, 2.80]
    assert shown[26][:4] == [SEP_25, "U26", 1.0, 1.0]
    assert shown[26][4] == pytest.approx(3.04)
    assert shown[27] == [SEP_25 + 1, "U26", 1.0, 0.0, "unfixed"]
    assert shown[92] == [NOV_30, "X26", 1.0, 0.0, "unfixed"]
    assert "closed" not in {row[4] for row in shown[2:]}
    kinds, _, _ = read(made)
    assert (kinds[2:27, 4] == NUMBER_CODE).all() and (kinds[27:, 4] == TEXT_CODE).all()


def test_an_iferc_history_is_created_from_two_handles_and_read_back_month_by_month() -> None:
    made = bridge.call(
        "_CreateMarketHistory", [an_iferc_calendar(), indices_for(("X26", 2.10), ("V26", 1.85))]
    )
    assert isinstance(made, str) and HANDLE.fullmatch(made), made
    assert rows(read(made)) == [
        HEADERS,
        TYPES,
        [OCT_1, "V26", 1.0, 1.0, 1.85],
        [NOV_2, "X26", 1.0, 1.0, 2.10],
        [DEC_1, "Z26", 1.0, 0.0, "unfixed"],
    ]
    kinds, _, _ = read(made)
    assert kinds[2:, 4].tolist() == [NUMBER_CODE, NUMBER_CODE, TEXT_CODE]


def test_fixings_over_another_index_are_refused_through_the_seam() -> None:
    futures, gas_daily = the_fixings(), prints_through(SEP_1, SEP_25)
    iferc = indices_for(("V26", 1.85))
    assert bridge.call("_CreateMarketHistory", [a_calendar(), gas_daily]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings is over another index, "
        "'Henry Hub Gas Daily', expected the calendar's, 'WTI NYMEX'"
    )
    assert bridge.call("_CreateMarketHistory", [a_gas_daily_calendar(), iferc]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings is over another index, "
        "'Henry Hub IFERC', expected the calendar's, 'Henry Hub Gas Daily'"
    )
    assert bridge.call("_CreateMarketHistory", [an_iferc_calendar(), futures]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings is over another index, "
        "'WTI NYMEX', expected the calendar's, 'Henry Hub IFERC'"
    )
    assert bridge.call("_CreateMarketHistory", [a_calendar(), a_holiday_calendar(MAY_25)]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings is a holiday calendar, "
        "expected futures, IFERC or Gas Daily fixings"
    )


def test_the_other_kinds_rules_reach_the_sheet_in_the_librarys_words() -> None:
    assert bridge.call(
        "_CreateMarketHistory", [a_gas_daily_calendar(), prints_through(SEP_1, SEP_25 + 1)]
    ) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings flow_date 2026-09-26 is after "
        "valuation date 2026-09-25, expected flow days on or before the valuation date"
    )
    assert bridge.call(
        "_CreateMarketHistory", [a_gas_daily_calendar(), prints_through(SEP_1 + 1, SEP_25)]
    ) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 2026-09-01, "
        "expected a fixing for every fixed day in calendar"
    )
    assert bridge.call(
        "_CreateMarketHistory",
        [an_iferc_calendar(), indices_for(("V26", 1.85), ("X26", 2.10), ("Z26", 2.2))],
    ) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings contract_code 'Z26' is a month not "
        "yet fixed in calendar, expected an index for fixed months alone"
    )
    assert bridge.call(
        "_CreateMarketHistory", [an_iferc_calendar(), indices_for(("V26", 1.85))]
    ) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings has no index for X26, "
        "expected an index for every fixed month in calendar"
    )


def test_a_failed_construction_of_the_other_kinds_publishes_no_object_and_no_handle() -> None:
    made, prints = a_gas_daily_calendar(), prints_through(SEP_1, SEP_25)
    indices = indices_for(("V26", 1.85))
    before = number(cast(str, bridge.call("_CreateMarketHistory", [made, prints])))
    assert cast(str, bridge.call("_CreateMarketHistory", [made, indices])).startswith(
        "#ERROR _CreateMarketHistory: ValueError: fixings is over another index"
    )
    assert number(cast(str, bridge.call("_CreateMarketHistory", [made, prints]))) == before + 1


def test_a_gas_daily_market_is_created_from_two_handles_and_read_back_day_by_day() -> None:
    history = bridge.call(
        "_CreateMarketHistory", [a_gas_daily_calendar(), prints_through(SEP_1, SEP_25)]
    )
    made = a_market(cast(str, history), a_vector(2.95, 3.10, 3.40, name="Henry Hub Gas Daily"))
    assert cast(str, history).startswith("market_history:Henry Hub Gas Daily:")
    assert made.startswith("market:Henry Hub Gas Daily:")
    shown = rows(read(made))
    assert len(shown) == 93
    assert shown[0] == MARKET_HEADERS and shown[1] == TYPES
    assert shown[2] == [SEP_1, "U26", 1.0, 1.0, 2.80]
    assert shown[26][:4] == [SEP_25, "U26", 1.0, 1.0] and shown[26][4] == pytest.approx(3.04)
    assert shown[27] == [SEP_25 + 1, "U26", 1.0, 0.0, 2.95]
    assert shown[31] == [SEP_30, "U26", 1.0, 0.0, 2.95]
    assert shown[32] == [OCT_1, "V26", 1.0, 0.0, 3.10]
    assert shown[62] == [OCT_31, "V26", 1.0, 0.0, 3.10]
    assert shown[63] == [NOV_1, "X26", 1.0, 0.0, 3.40]
    assert shown[92] == [NOV_30, "X26", 1.0, 0.0, 3.40]
    kinds, _, _ = read(made)
    assert (kinds[2:, 4] == NUMBER_CODE).all()
    assert "closed" not in {row[4] for row in shown[2:]}
    assert "unfixed" not in {row[4] for row in shown[2:]}


def test_an_iferc_market_is_created_from_two_handles_and_read_back_month_by_month() -> None:
    history = bridge.call(
        "_CreateMarketHistory", [an_iferc_calendar(), indices_for(("X26", 2.10), ("V26", 1.85))]
    )
    made = a_market(cast(str, history), a_vector(2.20, name="Henry Hub IFERC"))
    assert cast(str, history).startswith("market_history:Henry Hub IFERC:")
    assert made.startswith("market:Henry Hub IFERC:")
    assert rows(read(made)) == [
        MARKET_HEADERS,
        TYPES,
        [OCT_1, "V26", 1.0, 1.0, 1.85],
        [NOV_2, "X26", 1.0, 1.0, 2.10],
        [DEC_1, "Z26", 1.0, 0.0, 2.20],
    ]
    kinds, _, _ = read(made)
    assert (kinds[2:, 4] == NUMBER_CODE).all()


def test_the_other_kinds_rules_reach_the_sheet_in_the_librarys_words_for_the_market() -> None:
    gas_daily = cast(
        str,
        bridge.call(
            "_CreateMarketHistory", [a_gas_daily_calendar(), prints_through(SEP_1, SEP_25)]
        ),
    )
    assert bridge.call(
        "_CreateMarket", [gas_daily, a_vector(2.95, name="Henry Hub Gas Daily")]
    ) == (
        "#ERROR _CreateMarket: ValueError: price_vector has 1 price, expected 3, "
        "one per contract from 'U26' through 'X26'"
    )
    ended = cast(
        str,
        bridge.call(
            "_CreateMarketHistory", [a_gas_daily_calendar(NOV_30), prints_through(SEP_1, NOV_30)]
        ),
    )
    assert bridge.call("_CreateMarket", [ended, a_vector(3.40, name="Henry Hub Gas Daily")]) == (
        "#ERROR _CreateMarket: ValueError: market_history has no unfixed period, "
        "expected at least one to quote"
    )
    iferc = cast(
        str,
        bridge.call(
            "_CreateMarketHistory", [an_iferc_calendar(), indices_for(("V26", 1.85), ("X26", 2.10))]
        ),
    )
    assert bridge.call("_CreateMarket", [iferc, a_vector(2.10, 2.20, name="Henry Hub IFERC")]) == (
        "#ERROR _CreateMarket: ValueError: price_vector has 2 prices, expected 1, "
        "one per contract from 'Z26' through 'Z26'"
    )
    published = cast(
        str,
        bridge.call(
            "_CreateMarketHistory",
            [
                an_iferc_calendar(DEC_1 + 14),
                indices_for(("V26", 1.85), ("X26", 2.10), ("Z26", 2.2)),
            ],
        ),
    )
    assert bridge.call("_CreateMarket", [published, a_vector(2.20, name="Henry Hub IFERC")]) == (
        "#ERROR _CreateMarket: ValueError: market_history has no unfixed period, "
        "expected at least one to quote"
    )


# The vector's name is the market's first rule and reaches the sheet in the library's words:
# a vector named for another index refused on each kind of history before the count is looked
# at, another case being another name; the vector of one kind's sample given to another's.
def test_a_vector_named_for_another_index_reaches_the_sheet_in_the_librarys_words() -> None:
    history = a_history()
    assert bridge.call("_CreateMarket", [history, a_vector(72.10, name="Brent")]) == (
        "#ERROR _CreateMarket: ValueError: price_vector names index 'Brent', "
        "expected market_history's index 'WTI NYMEX'"
    )
    assert bridge.call("_CreateMarket", [history, a_vector(72.10, 72.80, name="wti nymex")]) == (
        "#ERROR _CreateMarket: ValueError: price_vector names index 'wti nymex', "
        "expected market_history's index 'WTI NYMEX'"
    )
    gas_daily = bridge.call(
        "_CreateMarketHistory", [a_gas_daily_calendar(), prints_through(SEP_1, SEP_25)]
    )
    iferc = bridge.call(
        "_CreateMarketHistory", [an_iferc_calendar(), indices_for(("V26", 1.85), ("X26", 2.10))]
    )
    assert bridge.call("_CreateMarket", [gas_daily, a_vector(2.20, name="Henry Hub IFERC")]) == (
        "#ERROR _CreateMarket: ValueError: price_vector names index 'Henry Hub IFERC', "
        "expected market_history's index 'Henry Hub Gas Daily'"
    )
    assert bridge.call(
        "_CreateMarket", [iferc, a_vector(2.95, 3.10, 3.40, name="Henry Hub Gas Daily")]
    ) == (
        "#ERROR _CreateMarket: ValueError: price_vector names index 'Henry Hub Gas Daily', "
        "expected market_history's index 'Henry Hub IFERC'"
    )
