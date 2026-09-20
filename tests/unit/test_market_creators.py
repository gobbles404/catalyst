"""The market's creators through the seam: the history, two handles in and one out, and the table
its handle spills, the calendar's four columns and a fixing price on each day, a number or a
word; then the market, the history and a price vector in, and the table its handle spills, a
price on every business day."""

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
HANDLE = re.compile(r"market_history:[0-9a-f]{6}:([0-9]{6})")
HEADERS = ["date", "prompt_contract", "is_business_day", "is_past", "fixing_price"]
TYPES = ["datetime64[D]", "str", "bool", "bool", "float64"]
FIXINGS_HEADERS = Cells.from_rows([["date", "settle"]])
SAMPLE = [[MAY_20, 70.85], [MAY_21, 71.10], [MAY_22, 71.25]]


def column(*cells: object) -> Cells:
    return Cells.from_rows([[cell] for cell in cells])


def a_valuation(serial: float = MAY_26, fraction: float = 0.5) -> str:
    text = bridge.call("_CreateValuationDate", [serial, fraction])
    assert isinstance(text, str) and text.startswith("valuation_date:"), text
    return text


def a_schedule(codes: tuple[str, ...], expiries: tuple[float, ...]) -> str:
    text = bridge.call(
        "_CreateExpirySchedule", [column(*codes), column(*expiries), MISSING, MISSING]
    )
    assert isinstance(text, str) and text.startswith("expiry_schedule:"), text
    return text


def a_holiday_calendar(*serials: float) -> str:
    text = bridge.call("_CreateHolidayCalendar", [column(*serials)])
    assert isinstance(text, str) and text.startswith("holiday_calendar:"), text
    return text


SCHEDULE = (("m26", "n26", "q26"), (MAY_19, JUN_22, JUL_21))


def a_calendar(
    valuation: str | None = None, holidays: str | None = None, mode: str = "daily"
) -> str:
    args = [
        valuation or a_valuation(),
        mode,
        a_schedule(*SCHEDULE),
        holidays or a_holiday_calendar(MAY_25),
    ]
    text = bridge.call("_CreateCalendar", args)
    assert isinstance(text, str) and text.startswith("calendar:"), text
    return text


def the_fixings(body: list[list[float]] = SAMPLE, holidays: str | None = None) -> str:
    args = [FIXINGS_HEADERS, Cells.from_rows(body), holidays or a_holiday_calendar(MAY_25)]
    text = bridge.call("_CreateDailyFixings", args)
    assert isinstance(text, str) and text.startswith("daily_fixings:"), text
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
            "#ERROR _CreateMarketHistory: ValueError: fixings date 2026-05-25 is a "
            "non-business day in calendar, expected no fixing",
        ),
        (
            [THE_CALENDAR, (SAMPLE[:2], MAY_25)],
            "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for "
            "2026-05-22, expected a fixing for every past business day in calendar",
        ),
        (
            [JAN_1, THE_FIXINGS],
            "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for "
            "2026-05-25, expected a fixing for every past business day in calendar",
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
            "#ERROR _CreateMarketHistory: fixings is missing, "
            "expected daily fixings or monthly fixings handle",
        ),
        (
            [THE_CALENDAR, None],
            "#ERROR _CreateMarketHistory: fixings is blank, "
            "expected daily fixings or monthly fixings handle",
        ),
        (
            [THE_CALENDAR, 70.85],
            "#ERROR _CreateMarketHistory: fixings is number 70.85, "
            "expected daily fixings or monthly fixings handle",
        ),
        (
            [THE_CALENDAR, "daily_fixings:000000:000001"],
            "#ERROR _CreateMarketHistory: fixings is text 'daily_fixings:000000:000001' "
            "naming no live object, expected daily fixings or monthly fixings handle",
        ),
        (
            [THE_CALENDAR, "#ERROR _CreateDailyFixings: table is blank, expected table"],
            "#ERROR _CreateMarketHistory: fixings is the creator's failure, expected daily "
            "fixings or monthly fixings handle: #ERROR _CreateDailyFixings: table is blank, "
            "expected table",
        ),
    ],
    ids=[
        "a fixing on the valuation date",
        "a fixing on the holiday the calendar closes",
        "the last past business day without a fixing",
        "a calendar open on the holiday the fixings skip",
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
        calendar = a_calendar(holidays=a_holiday_calendar(JAN_1))
    if fixings is THE_FIXINGS:
        fixings = the_fixings()
    elif isinstance(fixings, tuple):
        body, holiday = cast(tuple[list[list[float]], float], fixings)
        fixings = the_fixings(body, a_holiday_calendar(holiday))
    assert bridge.call("_CreateMarketHistory", [calendar, fixings]) == text


# The fixings must be of the calendar's kind: monthly fixings along a daily calendar, and daily
# fixings along a monthly one, are refused in the library's words before any fixing is read.
def test_the_fixings_must_be_of_the_calendars_kind() -> None:
    published = bridge.call(
        "_CreateExpirySchedule",
        [
            column("m26", "n26", "q26"),
            column(MAY_19, JUN_22, JUL_21),
            MISSING,
            column(MAY_20, JUN_22 + 1, JUL_21 + 1),
        ],
    )
    monthly = bridge.call(
        "_CreateCalendar", [a_valuation(), "monthly", published, a_holiday_calendar(MAY_25)]
    )
    assert isinstance(monthly, str) and monthly.startswith("calendar:"), monthly
    monthly_fixings = bridge.call("_CreateMonthlyFixings", [MAY_20, 2.5, published])
    assert bridge.call("_CreateMarketHistory", [monthly, the_fixings()]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings is daily fixings, "
        "expected monthly fixings for a monthly calendar"
    )
    assert bridge.call("_CreateMarketHistory", [a_calendar(), monthly_fixings]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings is monthly fixings, "
        "expected daily fixings for a daily calendar"
    )
    made = bridge.call("_CreateMarketHistory", [monthly, monthly_fixings])
    assert isinstance(made, str) and HANDLE.fullmatch(made), made


def test_a_handle_of_another_kind_in_either_slot_is_refused_by_name() -> None:
    calendar, fixings = a_calendar(), the_fixings()
    made = a_history(calendar, fixings)
    assert bridge.call("_CreateMarketHistory", [fixings, fixings]) == (
        f"#ERROR _CreateMarketHistory: calendar is daily fixings handle {fixings!r}, "
        "expected calendar handle"
    )
    assert bridge.call("_CreateMarketHistory", [calendar, calendar]) == (
        f"#ERROR _CreateMarketHistory: fixings is calendar handle {calendar!r}, "
        "expected daily fixings or monthly fixings handle"
    )
    assert bridge.call("_CreateMarketHistory", [made, fixings]) == (
        f"#ERROR _CreateMarketHistory: calendar is market history handle {made!r}, "
        "expected calendar handle"
    )


def test_a_failed_construction_publishes_no_object_and_no_handle() -> None:
    calendar, fixings = a_calendar(), the_fixings()
    short = the_fixings(SAMPLE[:2])
    before = number(a_history(calendar, fixings))
    assert bridge.call("_CreateMarketHistory", [calendar, short]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 2026-05-22, "
        "expected a fixing for every past business day in calendar"
    )
    assert number(a_history(calendar, fixings)) == before + 1


def test_two_histories_from_one_calendar_each_read_their_own_prices() -> None:
    calendar = a_calendar()
    first = a_history(calendar, the_fixings())
    second = a_history(calendar, the_fixings([[MAY_20, 1.0], [MAY_21, 2.0], [MAY_22, 3.0]]))
    assert [row[4] for row in rows(read(first))[2:5]] == [70.85, 71.10, 71.25]
    assert [row[4] for row in rows(read(second))[2:5]] == [1.0, 2.0, 3.0]
    assert [row[:4] for row in rows(read(first))] == [row[:4] for row in rows(read(second))]


def test_a_dead_history_handle_cannot_be_read() -> None:
    assert bridge.call("util_ReadHandle", ["market_history:000000:000001"]) == (
        "#ERROR util_ReadHandle: handle is text 'market_history:000000:000001' naming no live "
        "object, expected a handle"
    )


# --- _CreateMarket -----------------------------------------------------------------


MARKET = re.compile(r"market:[0-9a-f]{6}:([0-9]{6})")
MARKET_HEADERS = ["date", "prompt_contract", "is_business_day", "is_past", "price"]
JUN_18, JUN_19, JUN_23 = 46191.0, 46192.0, 46196.0


def a_vector(*prices: float) -> str:
    text = bridge.call("_CreatePriceVector", [column(*prices)])
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
    return the_fixings(body, a_holiday_calendar(*listed))


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
    calendar = a_calendar(valuation=a_valuation(JUN_22, 1.0), holidays=a_holiday_calendar(JUN_19))
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
            [MAY_19, THE_VECTOR],
            "#ERROR _CreateMarket: ValueError: market_history valuation date is 2026-05-19, "
            "expected a date from 2026-05-20 through 2026-07-21",
        ),
        (
            [JUL_21 + 1, (72.80,)],
            "#ERROR _CreateMarket: ValueError: market_history valuation date is 2026-07-22, "
            "expected a date from 2026-05-20 through 2026-07-21",
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
            [THE_HISTORY, "price_vector:000000:000001"],
            "#ERROR _CreateMarket: price_vector is text 'price_vector:000000:000001' naming no "
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
        "valued the day before the calendar",
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
    elif history == MAY_19:
        history = a_history(
            calendar=a_calendar(valuation=a_valuation(MAY_19)),
            fixings=the_fixings([[MAY_18, 70.0]]),
        )
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


def test_repeated_market_calls_publish_fresh_handles_and_the_earlier_ones_stand() -> None:
    history, vector = a_history(), a_vector(72.10, 72.80)
    first = a_market(history, vector)
    second = a_market(history, vector)
    assert market_number(second) == market_number(first) + 1
    assert rows(read(first)) == rows(read(second))


def test_a_dead_market_handle_cannot_be_read() -> None:
    assert bridge.call("util_ReadHandle", ["market:000000:000001"]) == (
        "#ERROR util_ReadHandle: handle is text 'market:000000:000001' naming no live object, "
        "expected a handle"
    )


# --- a monthly history and market -------------------------------------------------


# The market page's example as the sheet sends it: four contracts with the day each is
# published, valued on 25 June 2026 with the 24th a holiday, n26's fixing 2.95 dated the 23rd,
# and the quotes 3.10 and 3.20 of q26 and u26.
AUG_20, AUG_21, JUN_24, JUN_25 = 46254.0, 46255.0, 46197.0, 46198.0
TOY = (
    ("m26", "n26", "q26", "u26"),
    (MAY_19, JUN_22, JUL_21, AUG_20),
    (MAY_20, JUN_23, JUL_21 + 1, AUG_21),
)


def a_toy_schedule() -> str:
    codes, expiries, publications = TOY
    text = bridge.call(
        "_CreateExpirySchedule",
        [column(*codes), column(*expiries), MISSING, column(*publications)],
    )
    assert isinstance(text, str) and text.startswith("expiry_schedule:"), text
    return text


def a_monthly_history(
    as_of: float = JUN_25, fixings: list[list[float]] | None = None, schedule: str | None = None
) -> str:
    schedule = schedule or a_toy_schedule()
    calendar = bridge.call(
        "_CreateCalendar",
        [a_valuation(as_of), "monthly", schedule, a_holiday_calendar(JUN_24)],
    )
    body = fixings or [[JUN_23, 2.95]]
    monthly = bridge.call(
        "_CreateMonthlyFixings",
        [column(*(d for d, _ in body)), column(*(p for _, p in body)), schedule],
    )
    assert isinstance(monthly, str) and monthly.startswith("monthly_fixings:"), monthly
    text = bridge.call("_CreateMarketHistory", [calendar, monthly])
    assert isinstance(text, str) and HANDLE.fullmatch(text), text
    return text


def test_a_monthly_history_prices_every_day_of_the_expired_contract_and_is_unfixed_elsewhere() -> (
    None
):
    shown = rows(read(a_monthly_history()))
    assert len(shown) == 95 and shown[0] == HEADERS and shown[1] == TYPES
    by_day = {row[0]: row[1:] for row in shown[2:]}
    assert by_day[MAY_20] == ["n26", 1.0, 1.0, 2.95]
    assert by_day[JUN_22 - 2] == ["n26", 0.0, 1.0, 2.95]  # Saturday 20 June, priced and closed
    assert by_day[JUN_22] == ["n26", 1.0, 1.0, 2.95]
    assert by_day[JUN_23] == ["q26", 1.0, 1.0, "unfixed"]
    assert by_day[JUN_24] == ["q26", 0.0, 1.0, "unfixed"]
    assert by_day[JUN_25] == ["q26", 1.0, 0.0, "unfixed"]
    assert by_day[JUN_25 + 2] == ["q26", 0.0, 0.0, "unfixed"]
    assert by_day[JUL_21 + 1] == ["u26", 1.0, 0.0, "unfixed"]
    fifth = [row[4] for row in shown[2:]]
    assert "closed" not in fifth and fifth.count("unfixed") == 59 and fifth.count(2.95) == 34


def test_a_monthly_market_prices_every_day_from_history_or_the_vector() -> None:
    made = bridge.call("_CreateMarket", [a_monthly_history(), a_vector(3.10, 3.20)])
    assert isinstance(made, str) and MARKET.fullmatch(made), made
    shown = rows(read(made))
    by_day = {row[0]: row[1:] for row in shown[2:]}
    assert by_day[JUN_22 - 2] == ["n26", 0.0, 1.0, 2.95]
    assert by_day[JUN_22] == ["n26", 1.0, 1.0, 2.95]
    assert by_day[JUN_23] == ["q26", 1.0, 1.0, 3.10]
    assert by_day[JUN_24] == ["q26", 0.0, 1.0, 3.10]
    assert by_day[JUN_25] == ["q26", 1.0, 0.0, 3.10]
    assert by_day[JUN_25 + 2] == ["q26", 0.0, 0.0, 3.10]
    assert by_day[JUL_21 + 1] == ["u26", 1.0, 0.0, 3.20]
    assert by_day[AUG_20] == ["u26", 1.0, 0.0, 3.20]
    fifth = [row[4] for row in shown[2:]]
    assert all(not isinstance(cell, str) for cell in fifth)
    kinds, _, _ = read(made)
    assert (kinds[2:, 4] == NUMBER_CODE).all()


def test_a_monthly_history_that_cannot_be_made_says_why() -> None:
    schedule = a_toy_schedule()
    calendar = bridge.call(
        "_CreateCalendar", [a_valuation(JUN_25), "monthly", schedule, a_holiday_calendar(JUN_24)]
    )
    anchor_only = bridge.call("_CreateMonthlyFixings", [MAY_20, 1.0, schedule])
    assert bridge.call("_CreateMarketHistory", [calendar, anchor_only]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 'n26' published "
        "2026-06-23, expected a fixing for every expired contract in calendar"
    )
    too_far = bridge.call(
        "_CreateMonthlyFixings", [column(JUN_23, JUL_21 + 1), column(2.95, 3.05), schedule]
    )
    assert bridge.call("_CreateMarketHistory", [calendar, too_far]) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings date 2026-07-22 is 'q26', not expired "
        "on 2026-06-25, expected fixings of expired contracts only"
    )
    shared = bridge.call(
        "_CreateExpirySchedule",
        [
            column("m26", "n26", "q26", "u26"),
            column(MAY_19, JUN_22, JUL_21, AUG_20),
            MISSING,
            column(MAY_20, JUN_23, JUN_23, AUG_21),
        ],
    )
    ambiguous = bridge.call(
        "_CreateCalendar", [a_valuation(JUN_25), "monthly", shared, a_holiday_calendar(JUN_24)]
    )
    assert bridge.call(
        "_CreateMarketHistory",
        [ambiguous, bridge.call("_CreateMonthlyFixings", [JUN_23, 2.95, shared])],
    ) == (
        "#ERROR _CreateMarketHistory: ValueError: calendar publication date 2026-06-23 is 'n26' "
        "and 'q26', expected one contract per publication date"
    )


def test_a_failed_monthly_history_publishes_no_object_and_no_handle() -> None:
    schedule = a_toy_schedule()
    calendar = bridge.call(
        "_CreateCalendar", [a_valuation(JUN_25), "monthly", schedule, a_holiday_calendar(JUN_24)]
    )
    good = bridge.call("_CreateMonthlyFixings", [JUN_23, 2.95, schedule])
    anchor_only = bridge.call("_CreateMonthlyFixings", [MAY_20, 1.0, schedule])
    first = bridge.call("_CreateMarketHistory", [calendar, good])
    assert isinstance(first, str)
    before = number(first)
    refused = bridge.call("_CreateMarketHistory", [calendar, anchor_only])
    assert isinstance(refused, str) and refused.startswith("#ERROR")
    second = bridge.call("_CreateMarketHistory", [calendar, good])
    assert isinstance(second, str) and number(second) == before + 1


# The provisional roll through the seam: valued on n26's expiry day it is quoted; the day
# after, its provisional value keyed by its publication date, the 24th, replaces the quote in
# the vector, and the vector rolls to q26; the published price replaces the provisional one.
def test_the_provisional_roll_through_the_seam() -> None:
    schedule = bridge.call(
        "_CreateExpirySchedule",
        [
            column("m26", "n26", "q26", "u26"),
            column(MAY_19, JUN_22, JUL_21, AUG_20),
            MISSING,
            column(MAY_20, JUN_24, JUL_21 + 1, AUG_21),
        ],
    )
    holidays = a_holiday_calendar(JAN_1)
    on_expiry = bridge.call(
        "_CreateCalendar", [a_valuation(JUN_22, 1.0), "monthly", schedule, holidays]
    )
    anchor_only = bridge.call("_CreateMonthlyFixings", [MAY_20, 1.0, schedule])
    live = bridge.call(
        "_CreateMarket",
        [bridge.call("_CreateMarketHistory", [on_expiry, anchor_only]), a_vector(2.93, 3.10, 3.20)],
    )
    assert rows(read(live))[2 + 33][1:] == ["n26", 1.0, 0.0, 2.93]  # 22 June, expiry day, quoted
    day_after = bridge.call(
        "_CreateCalendar", [a_valuation(JUN_23, 0.0), "monthly", schedule, holidays]
    )
    provisional = bridge.call("_CreateMonthlyFixings", [JUN_24, 2.90, schedule])
    rolled = bridge.call(
        "_CreateMarket",
        [bridge.call("_CreateMarketHistory", [day_after, provisional]), a_vector(3.10, 3.20)],
    )
    shown = rows(read(rolled))
    assert shown[2 + 33][1:] == ["n26", 1.0, 1.0, 2.90] and shown[2 + 34][1:] == [
        "q26",
        1.0,
        0.0,
        3.10,
    ]
    published = bridge.call("_CreateMonthlyFixings", [JUN_24, 2.95, schedule])
    final = bridge.call(
        "_CreateMarket",
        [bridge.call("_CreateMarketHistory", [day_after, published]), a_vector(3.10, 3.20)],
    )
    assert rows(read(final))[2 + 33][4] == 2.95 and rows(read(rolled))[2 + 33][4] == 2.90
