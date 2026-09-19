"""The market data through the seam: what each creator shows for a right and a wrong call, and
that its handle resolves to the object the seam kept."""

import functools
import re
from typing import cast

import pytest
from test_utilities import read, rows

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle
from goosedove.excel.probes import probe
from goosedove.market_data.daily_fixings import DailyFixings
from goosedove.market_data.monthly_fixings import MonthlyFixings


def number(text: str, handle: re.Pattern[str]) -> int:
    """The running publication number a handle carries; it moves only when an object is stored."""
    match = handle.fullmatch(text)
    assert match, text
    return int(match.group(1))


def a_valuation_date() -> str:
    """A handle of another kind, for the tests that hand a creator the wrong one."""
    return cast(str, bridge.call("_CreateValuationDate", [46161.0, 0.5]))


# --- _CreateDailyFixings ---------------------------------------------------------


# The page's sample as the sheet sends it: the header row, then four rows of a serial and a
# settle, 1, 4, 5 and 6 May 2026, a Friday and the Monday to Wednesday after it.
MAY_1, MAY_2, MAY_4, MAY_5, MAY_6 = 46143.0, 46144.0, 46146.0, 46147.0, 46148.0
HEADERS = Cells.from_rows([["date", "settle"]])
BODY = Cells.from_rows([[MAY_1, 101.94], [MAY_4, 106.42], [MAY_5, 102.27], [MAY_6, 95.08]])
FIXINGS = re.compile(r"daily_fixings:[0-9a-f]{6}:([0-9]{6})")

# The calendar page's sample as the sheet sends it, the ten days one market is closed in 2026,
# one serial per row; the one in May is the 25th, a Monday. Made once into the handle every
# fixings call takes, so a test that counts publications sees the fixings' alone.
MAY_25 = 46167.0
HOLIDAYS = Cells.from_rows(
    [
        [s]
        for s in (
            46023.0,
            46041.0,
            46069.0,
            46115.0,
            MAY_25,
            46192.0,
            46206.0,
            46272.0,
            46352.0,
            46381.0,
        )
    ]
)
CALENDAR = re.compile(r"holiday_calendar:[0-9a-f]{6}:([0-9]{6})")
THE_CALENDAR = object()  # in a case's arguments: the calendar's handle, made below


@functools.cache
def the_calendar() -> str:
    text = bridge.call("_CreateHolidayCalendar", [HOLIDAYS])
    assert isinstance(text, str) and CALENDAR.fullmatch(text), text
    return text


# The library has no consumer of daily fixings yet, so this hidden reader proves that a handle
# resolves to the fixings the seam kept, with their columns as they arrived.
@probe
def ReadDailyFixings(fixings: Handle[DailyFixings]) -> str:
    days = " ".join(str(day) for day in fixings.dates)
    return f"{days} | {' '.join(repr(float(s)) for s in fixings.settles)}"


def the_fixings(headers: object, body: object) -> str:
    text = bridge.call("_CreateDailyFixings", [headers, body, the_calendar()])
    assert isinstance(text, str) and FIXINGS.fullmatch(text), text
    return text


def test_fixings_are_created_from_a_table_and_a_calendar_and_read_back() -> None:
    assert bridge.call("ReadDailyFixings", [the_fixings(HEADERS, BODY)]) == (
        "2026-05-01 2026-05-04 2026-05-05 2026-05-06 | 101.94 106.42 102.27 95.08"
    )


def test_the_fixings_headers_bind_in_either_order_and_any_case() -> None:
    headers = Cells.from_rows([["SETTLE", "Date"]])
    body = Cells.from_rows([[101.94, MAY_1], [106.42, MAY_4]])
    assert bridge.call("ReadDailyFixings", [the_fixings(headers, body)]) == (
        "2026-05-01 2026-05-04 | 101.94 106.42"
    )


# Friday 22 May and Tuesday 26 May 2026: the weekend and the holiday between them are the days
# without a fixing, and the calendar's handle is what says so.
def test_a_listed_holiday_is_a_day_without_a_fixing() -> None:
    body = Cells.from_rows([[46164.0, 101.94], [46168.0, 106.42]])
    assert bridge.call("ReadDailyFixings", [the_fixings(HEADERS, body)]) == (
        "2026-05-22 2026-05-26 | 101.94 106.42"
    )


@pytest.mark.parametrize(
    ("headers", "body", "calendar", "text"),
    [
        (
            Cells.from_rows([["date", "price"]]),
            BODY,
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: header_row cell (1, 2) is text 'price', "
            "expected one of date or settle",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, "x"], [MAY_4, 106.42]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: table cell (1, 2) is text 'x', expected number",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_4, 106.42], [MAY_1, 101.94]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-01, "
            "expected a date after row 1's 2026-05-04",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, 101.94], [MAY_2, 100.0]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-02, a Saturday, "
            "expected a business day",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_25, 100.0]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: ValueError: date row 1 is 2026-05-25, a holiday, "
            "expected a business day",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, 101.94], [MAY_5, 102.27]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-05, "
            "expected 2026-05-04, the business day after row 1's 2026-05-01",
        ),
        (
            HEADERS,
            Cells.from_rows([[MAY_1, 101.94, 1.0]]),
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: header_row has 2 headers, expected 3, "
            "one per column of table",
        ),
        (HEADERS, None, THE_CALENDAR, "#ERROR _CreateDailyFixings: table is blank, expected table"),
        (
            HEADERS,
            MISSING,
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: table is missing, expected table",
        ),
        (
            Cells.from_rows([["date"], ["settle"]]),
            BODY,
            THE_CALENDAR,
            "#ERROR _CreateDailyFixings: header_row is 2x1 array, expected row of text",
        ),
        (
            HEADERS,
            BODY,
            3.0,
            "#ERROR _CreateDailyFixings: holiday_calendar is number 3.0, "
            "expected holiday calendar handle",
        ),
        (
            HEADERS,
            BODY,
            None,
            "#ERROR _CreateDailyFixings: holiday_calendar is blank, "
            "expected holiday calendar handle",
        ),
        (
            HEADERS,
            BODY,
            MISSING,
            "#ERROR _CreateDailyFixings: holiday_calendar is missing, "
            "expected holiday calendar handle",
        ),
        (
            HEADERS,
            BODY,
            "holiday_calendar:000000:000001",
            "#ERROR _CreateDailyFixings: holiday_calendar is text "
            "'holiday_calendar:000000:000001' naming no live object, "
            "expected holiday calendar handle",
        ),
        (
            HEADERS,
            BODY,
            "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date",
            "#ERROR _CreateDailyFixings: holiday_calendar is the creator's failure, "
            "expected holiday calendar handle: #ERROR _CreateHolidayCalendar: holiday cell "
            "(2, 1) is blank, expected date",
        ),
    ],
    ids=[
        "an unknown header",
        "text in the settle column",
        "dates backwards",
        "a Saturday in the series",
        "a listed holiday in the series",
        "a business day without a fixing",
        "a body one column wider than its headers",
        "a blank cell where the body should be",
        "the body left out",
        "headers down a column",
        "a number where the calendar should be",
        "a blank cell where the calendar should be",
        "the calendar left out",
        "text naming no live calendar",
        "the calendar creator's failure relayed",
    ],
)
def test_fixings_that_cannot_be_made_say_why(
    headers: object, body: object, calendar: object, text: str
) -> None:
    calendar = the_calendar() if calendar is THE_CALENDAR else calendar
    assert bridge.call("_CreateDailyFixings", [headers, body, calendar]) == text


def test_a_failed_fixings_construction_publishes_no_object_and_no_handle() -> None:
    before = number(the_fixings(HEADERS, BODY), FIXINGS)
    gap = Cells.from_rows([[MAY_1, 101.94], [MAY_5, 102.27]])
    assert bridge.call("_CreateDailyFixings", [HEADERS, gap, the_calendar()]) == (
        "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-05, "
        "expected 2026-05-04, the business day after row 1's 2026-05-01"
    )
    assert number(the_fixings(HEADERS, BODY), FIXINGS) == before + 1


def test_a_handle_of_another_kind_is_not_daily_fixings() -> None:
    other = a_valuation_date()
    assert bridge.call("ReadDailyFixings", [other]) == (
        f"#ERROR ReadDailyFixings: fixings is valuation date handle {other!r}, "
        "expected daily fixings handle"
    )


def test_a_handle_of_another_kind_is_not_a_holiday_calendar() -> None:
    other = a_valuation_date()
    assert bridge.call("_CreateDailyFixings", [HEADERS, BODY, other]) == (
        f"#ERROR _CreateDailyFixings: holiday_calendar is valuation date handle {other!r}, "
        "expected holiday calendar handle"
    )


# --- _CreateMonthlyFixings -------------------------------------------------------


# The page's sample as the sheet sends it, Waha IFERC gas: the day Platts published each month's
# final index, January to April 2026, January's on 5 January as announced, and an illustrative
# price beside each.
JAN_5, FEB_2, MAR_2, APR_1 = 46027.0, 46055.0, 46083.0, 46113.0
PUBLICATION_DATES = Cells.from_rows([[JAN_5], [FEB_2], [MAR_2], [APR_1]])
MONTHLY = Cells.from_rows([[1.85], [2.10], [1.95], [1.60]])
MONTHLY_HANDLE = re.compile(r"monthly_fixings:[0-9a-f]{6}:([0-9]{6})")
THE_SCHEDULE = object()  # in a case's arguments: the Waha schedule's handle, made below
NO_PUBLICATIONS = object()  # the same schedule built without its publication dates

# The Waha schedule as the sheet sends it: six contract months, December 2025 to May 2026, the
# last day of bidweek as each future's expiry, no options, and the day each month's final index
# is published, so the fixings above sit inside it with a publication before and one after.
WAHA_CODES = Cells.from_rows([["Z25"], ["F26"], ["G26"], ["H26"], ["J26"], ["K26"]])
WAHA_FUTURES = Cells.from_rows([[45989.0], [46022.0], [46052.0], [46080.0], [46112.0], [46142.0]])
WAHA_PUBLICATIONS = Cells.from_rows([[45992.0], [JAN_5], [FEB_2], [MAR_2], [APR_1], [46143.0]])
SCHEDULE_HANDLE = re.compile(r"expiry_schedule:[0-9a-f]{6}:([0-9]{6})")


@functools.cache
def the_waha_schedule(published: bool = True) -> str:
    publications = WAHA_PUBLICATIONS if published else MISSING
    text = bridge.call("_CreateExpirySchedule", [WAHA_CODES, WAHA_FUTURES, MISSING, publications])
    assert isinstance(text, str) and SCHEDULE_HANDLE.fullmatch(text), text
    return text


# The library has no consumer of monthly fixings yet, so this hidden reader proves that a handle
# resolves to the fixings the seam kept, the publication dates as days.
@probe
def ReadMonthlyFixings(fixings: Handle[MonthlyFixings]) -> str:
    kept = " ".join(str(day) for day in fixings.publication_dates)
    return f"{kept} | {' '.join(repr(float(p)) for p in fixings.prices)}"


def monthly(publication_dates: object, prices: object) -> str:
    text = bridge.call("_CreateMonthlyFixings", [publication_dates, prices, the_waha_schedule()])
    assert isinstance(text, str) and MONTHLY_HANDLE.fullmatch(text), text
    return text


def test_monthly_fixings_are_created_from_two_columns_and_a_schedule_and_read_back() -> None:
    assert bridge.call("ReadMonthlyFixings", [monthly(PUBLICATION_DATES, MONTHLY)]) == (
        "2026-01-05 2026-02-02 2026-03-02 2026-04-01 | 1.85 2.1 1.95 1.6"
    )


# A single cell is a column of one, so a fixing of one publication needs no range.
def test_two_single_cells_make_a_fixing_of_one_publication() -> None:
    assert bridge.call("ReadMonthlyFixings", [monthly(JAN_5, 1.85)]) == "2026-01-05 | 1.85"


# The same schedule with its publication dates shuffled and one repeated, codes and futures
# alongside, says the same about the series.
def test_a_schedule_with_its_publication_dates_shuffled_and_repeated_says_the_same() -> None:
    codes = Cells.from_rows([["J26"], ["F26"], ["G26"], ["H26"], ["G26"]])
    futures = Cells.from_rows([[46112.0], [46022.0], [46052.0], [46080.0], [46052.0]])
    publications = Cells.from_rows([[APR_1], [JAN_5], [FEB_2], [MAR_2], [FEB_2]])
    schedule = bridge.call("_CreateExpirySchedule", [codes, futures, MISSING, publications])
    text = bridge.call("_CreateMonthlyFixings", [PUBLICATION_DATES, MONTHLY, schedule])
    assert bridge.call("ReadMonthlyFixings", [text]) == (
        "2026-01-05 2026-02-02 2026-03-02 2026-04-01 | 1.85 2.1 1.95 1.6"
    )


@pytest.mark.parametrize(
    ("publication_dates", "prices", "schedule", "text"),
    [
        (
            PUBLICATION_DATES,
            Cells.from_rows([[1.85], [2.10], [1.95]]),
            THE_SCHEDULE,
            "#ERROR _CreateMonthlyFixings: ValueError: price has 3 prices, expected 4, "
            "one per publication_date",
        ),
        (
            Cells.from_rows([[46023.0], [FEB_2]]),
            Cells.from_rows([[1.85], [2.10]]),
            THE_SCHEDULE,
            "#ERROR _CreateMonthlyFixings: ValueError: publication_date row 1 is 2026-01-01, "
            "expected one of the schedule's publication dates",
        ),
        (
            Cells.from_rows([[FEB_2], [JAN_5]]),
            Cells.from_rows([[2.10], [1.85]]),
            THE_SCHEDULE,
            "#ERROR _CreateMonthlyFixings: ValueError: publication_date row 2 is 2026-01-05, "
            "expected a date after row 1's 2026-02-02",
        ),
        (
            Cells.from_rows([[JAN_5], [MAR_2]]),
            Cells.from_rows([[1.85], [1.95]]),
            THE_SCHEDULE,
            "#ERROR _CreateMonthlyFixings: ValueError: publication_date row 2 is 2026-03-02, "
            "expected 2026-02-02, the schedule's publication after row 1's 2026-01-05",
        ),
        (
            PUBLICATION_DATES,
            MONTHLY,
            NO_PUBLICATIONS,
            "#ERROR _CreateMonthlyFixings: ValueError: expiry_schedule has no publication dates, "
            "expected a schedule with one per contract",
        ),
        (
            PUBLICATION_DATES,
            Cells.from_rows([[1.85], [None], [1.95], [1.60]]),
            THE_SCHEDULE,
            "#ERROR _CreateMonthlyFixings: price cell (2, 1) is blank, expected number",
        ),
        (
            Cells.from_rows([["Jan-26"], [FEB_2]]),
            Cells.from_rows([[1.85], [2.10]]),
            THE_SCHEDULE,
            "#ERROR _CreateMonthlyFixings: publication_date cell (1, 1) is text 'Jan-26', "
            "expected date",
        ),
        (
            PUBLICATION_DATES,
            MISSING,
            THE_SCHEDULE,
            "#ERROR _CreateMonthlyFixings: price is missing, expected column of numbers",
        ),
        (
            PUBLICATION_DATES,
            MONTHLY,
            MISSING,
            "#ERROR _CreateMonthlyFixings: expiry_schedule is missing, "
            "expected expiry schedule handle",
        ),
        (
            PUBLICATION_DATES,
            MONTHLY,
            None,
            "#ERROR _CreateMonthlyFixings: expiry_schedule is blank, "
            "expected expiry schedule handle",
        ),
        (
            PUBLICATION_DATES,
            MONTHLY,
            2.86,
            "#ERROR _CreateMonthlyFixings: expiry_schedule is number 2.86, "
            "expected expiry schedule handle",
        ),
    ],
    ids=[
        "a price column one row short",
        "the first of the month in place of the publication day",
        "dates backwards",
        "a publication skipped",
        "a schedule without publication dates",
        "a blank among the prices",
        "a date typed as text",
        "the price column left out",
        "the schedule left out",
        "a blank cell where the schedule should be",
        "a number where the schedule should be",
    ],
)
def test_monthly_fixings_that_cannot_be_made_say_why(
    publication_dates: object, prices: object, schedule: object, text: str
) -> None:
    if schedule is THE_SCHEDULE:
        schedule = the_waha_schedule()
    elif schedule is NO_PUBLICATIONS:
        schedule = the_waha_schedule(published=False)
    assert bridge.call("_CreateMonthlyFixings", [publication_dates, prices, schedule]) == text


def test_a_failed_monthly_construction_publishes_no_object_and_no_handle() -> None:
    before = number(monthly(PUBLICATION_DATES, MONTHLY), MONTHLY_HANDLE)
    skipped = Cells.from_rows([[JAN_5], [MAR_2]])
    prices = Cells.from_rows([[1.85], [1.95]])
    assert bridge.call("_CreateMonthlyFixings", [skipped, prices, the_waha_schedule()]) == (
        "#ERROR _CreateMonthlyFixings: ValueError: publication_date row 2 is 2026-03-02, "
        "expected 2026-02-02, the schedule's publication after row 1's 2026-01-05"
    )
    assert number(monthly(PUBLICATION_DATES, MONTHLY), MONTHLY_HANDLE) == before + 1


def test_a_handle_of_another_kind_is_not_monthly_fixings() -> None:
    other = the_fixings(HEADERS, BODY)
    assert bridge.call("ReadMonthlyFixings", [other]) == (
        f"#ERROR ReadMonthlyFixings: fixings is daily fixings handle {other!r}, "
        "expected monthly fixings handle"
    )


def test_a_handle_of_another_kind_is_not_an_expiry_schedule() -> None:
    other = the_fixings(HEADERS, BODY)
    assert bridge.call("_CreateMonthlyFixings", [PUBLICATION_DATES, MONTHLY, other]) == (
        f"#ERROR _CreateMonthlyFixings: expiry_schedule is daily fixings handle {other!r}, "
        "expected expiry schedule handle"
    )


# --- _CreatePriceVector -----------------------------------------------------------


# The page's sample as the sheet sends it: four prices, a zero and a negative among them and the
# first repeated, selected without a header.
PRICES = Cells.from_rows([[74.25], [0.0], [-0.5], [74.25]])
VECTOR = re.compile(r"price_vector:[0-9a-f]{6}:([0-9]{6})")


def a_vector(prices: object = PRICES) -> str:
    text = bridge.call("_CreatePriceVector", [prices])
    assert isinstance(text, str) and VECTOR.fullmatch(text), text
    return text


def test_a_price_vector_is_created_from_a_column_and_read_back_in_order() -> None:
    assert rows(read(a_vector())) == [["price"], ["float64"], [74.25], [0.0], [-0.5], [74.25]]


def test_one_cell_is_a_vector_of_one_price() -> None:
    assert rows(read(a_vector(74.25))) == [["price"], ["float64"], [74.25]]


# Each call publishes anew, over the same prices or a different number of them, and an earlier
# handle still reads its own snapshot.
def test_every_vector_call_publishes_a_fresh_handle_and_the_earlier_ones_stand() -> None:
    first = a_vector()
    same = a_vector()
    longer = a_vector(Cells.from_rows([[74.25], [0.0], [-0.5], [74.25], [75.0]]))
    assert number(same, VECTOR) == number(first, VECTOR) + 1
    assert number(longer, VECTOR) == number(same, VECTOR) + 1
    assert rows(read(first))[2:] == [[74.25], [0.0], [-0.5], [74.25]]
    assert rows(read(same))[2:] == [[74.25], [0.0], [-0.5], [74.25]]
    assert rows(read(longer))[2:] == [[74.25], [0.0], [-0.5], [74.25], [75.0]]


@pytest.mark.parametrize(
    ("prices", "text"),
    [
        (
            Cells.from_rows([[74.25, 0.0, -0.5]]),
            "#ERROR _CreatePriceVector: prices is 1x3 array, expected column of numbers",
        ),
        (
            Cells.from_rows([[74.25, 1.0], [0.0, 2.0]]),
            "#ERROR _CreatePriceVector: prices is 2x2 array, expected column of numbers",
        ),
        (
            Cells.from_rows([["price"], [74.25]]),
            "#ERROR _CreatePriceVector: prices cell (1, 1) is text 'price', expected number",
        ),
        (
            Cells.from_rows([[74.25], ["74.25"]]),
            "#ERROR _CreatePriceVector: prices cell (2, 1) is text '74.25', expected number",
        ),
        (
            Cells.from_rows([[74.25], [True]]),
            "#ERROR _CreatePriceVector: prices cell (2, 1) is boolean TRUE, expected number",
        ),
        (
            Cells.from_rows([[74.25], [None]]),
            "#ERROR _CreatePriceVector: prices cell (2, 1) is blank, expected number",
        ),
        (None, "#ERROR _CreatePriceVector: prices is blank, expected column of numbers"),
        (MISSING, "#ERROR _CreatePriceVector: prices is missing, expected column of numbers"),
        ("74.25", "#ERROR _CreatePriceVector: prices is text '74.25', expected column of numbers"),
        (True, "#ERROR _CreatePriceVector: prices is boolean TRUE, expected column of numbers"),
    ],
    ids=[
        "a row where a column is expected",
        "two columns",
        "the header taken with the prices",
        "numeric text among the prices",
        "a boolean among the prices",
        "a blank among the prices",
        "a blank cell where the column should be",
        "the column left out",
        "numeric text where the column should be",
        "a boolean where the column should be",
    ],
)
def test_a_vector_that_cannot_be_made_says_why(prices: object, text: str) -> None:
    assert bridge.call("_CreatePriceVector", [prices]) == text


def test_a_failed_vector_publishes_no_object_and_no_handle() -> None:
    before = number(a_vector(), VECTOR)
    assert bridge.call("_CreatePriceVector", [Cells.from_rows([[74.25], [None]])]) == (
        "#ERROR _CreatePriceVector: prices cell (2, 1) is blank, expected number"
    )
    assert number(a_vector(), VECTOR) == before + 1
