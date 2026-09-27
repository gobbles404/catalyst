"""The market data through the seam: what each creator shows for a right and a wrong call, and
that its handle resolves to the object the seam kept."""

import functools
import os
import re
from typing import cast

import pytest
from test_utilities import read, rows

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, Handle
from goosedove.excel.probes import probe
from goosedove.market_data.futures_fixings import FuturesFixings
from goosedove.market_data.gas_daily_fixings import GasDailyFixings
from goosedove.market_data.iferc_fixings import IfercFixings
from goosedove.market_data.price_vector import PriceVector

PID = os.getpid()  # leads every handle this Python publishes


def number(text: str, handle: re.Pattern[str]) -> int:
    """The publication count a handle carries; it moves only when an object is stored."""
    match = handle.fullmatch(text)
    assert match, text
    return int(match.group(1))


def a_valuation_date() -> str:
    """A handle of another kind, for the tests that hand a creator the wrong one."""
    return cast(str, bridge.call("_CreateValuationDate", [46161.0, 0.5]))


# --- _CreateFuturesFixings ---------------------------------------------------------


# The page's sample as the sheet sends it: a column of four serials, 1, 4, 5 and 6 May 2026, a
# Friday and the Monday to Wednesday after it, and a column of the settles beside them.
MAY_1, MAY_2, MAY_4, MAY_5, MAY_6 = 46143.0, 46144.0, 46146.0, 46147.0, 46148.0
DATES = Cells.from_rows([[MAY_1], [MAY_4], [MAY_5], [MAY_6]])
SETTLES = Cells.from_rows([[101.94], [106.42], [102.27], [95.08]])
FIXINGS = re.compile(r"[0-9]+:futures_fixings:.+:([0-9]+)")

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
CALENDAR = re.compile(r"[0-9]+:holiday_calendar:([0-9]+)")
THE_CALENDAR = object()  # in a case's arguments: the calendar's handle, made below


@functools.cache
def the_calendar() -> str:
    text = bridge.call("_CreateHolidayCalendar", [HOLIDAYS])
    assert isinstance(text, str) and CALENDAR.fullmatch(text), text
    return text


def an_index_of(name: str, schedule: object, holidays: object) -> str:
    """The index handle of that schedule handle and holiday calendar handle, with one set of
    conventions and specifications, since nothing here reads either."""
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
    assert isinstance(text, str) and text.startswith(f"{PID}:index:"), text
    return text


@functools.cache
def the_index() -> str:
    """A futures index of two contracts whose holiday calendar is the_calendar's, made once."""
    schedule = bridge.call(
        "_CreateFuturesSchedule",
        [Cells.from_rows([["m26"], ["n26"]]), Cells.from_rows([[46161.0], [46195.0]]), MISSING],
    )
    return an_index_of("sample", schedule, the_calendar())


# The market history reads futures fixings, but this hidden reader proves on its own that a
# handle resolves to the fixings the seam kept, with their columns as they arrived.
@probe
def ReadFuturesFixings(fixings: Handle[FuturesFixings]) -> str:
    days = " ".join(str(day) for day in fixings.dates)
    return f"{days} | {' '.join(repr(float(s)) for s in fixings.settles)}"


def the_fixings(days: object, settles: object) -> str:
    text = bridge.call("_CreateFuturesFixings", [days, settles, the_index()])
    assert isinstance(text, str) and FIXINGS.fullmatch(text), text
    return text


def test_fixings_are_created_from_two_columns_and_a_calendar_and_read_back() -> None:
    assert bridge.call("ReadFuturesFixings", [the_fixings(DATES, SETTLES)]) == (
        "2026-05-01 2026-05-04 2026-05-05 2026-05-06 | 101.94 106.42 102.27 95.08"
    )


# The fixings' handle carries their index's name, sample, between the tag and the count.
def test_a_fixings_handle_carries_its_indexs_name() -> None:
    made = the_fixings(DATES, SETTLES)
    assert made.startswith(f"{PID}:futures_fixings:sample:")
    assert made[len(f"{PID}:futures_fixings:sample:") :].isdigit()


# A single cell is a column of one, so the fixings of one day need no range.
def test_two_single_cells_make_the_fixings_of_one_day_under_a_calendar() -> None:
    assert bridge.call("ReadFuturesFixings", [the_fixings(MAY_1, 101.94)]) == "2026-05-01 | 101.94"


# Friday 22 May and Tuesday 26 May 2026: the weekend and the holiday between them are the days
# without a fixing, and the calendar's handle is what says so.
def test_a_listed_holiday_is_a_day_without_a_fixing() -> None:
    days = Cells.from_rows([[46164.0], [46168.0]])
    settles = Cells.from_rows([[101.94], [106.42]])
    assert bridge.call("ReadFuturesFixings", [the_fixings(days, settles)]) == (
        "2026-05-22 2026-05-26 | 101.94 106.42"
    )


@pytest.mark.parametrize(
    ("days", "settles", "calendar", "text"),
    [
        (
            DATES,
            Cells.from_rows([[101.94], [106.42], [102.27]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: ValueError: settle has 3 settles, expected 4, "
            "one per date",
        ),
        (
            Cells.from_rows([[MAY_4], [MAY_1]]),
            Cells.from_rows([[106.42], [101.94]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-01, "
            "expected a date after row 1's 2026-05-04",
        ),
        (
            Cells.from_rows([[MAY_1], [MAY_2]]),
            Cells.from_rows([[101.94], [100.0]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-02, a Saturday, "
            "expected a business day",
        ),
        (
            MAY_25,
            100.0,
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-05-25, a holiday, "
            "expected a business day",
        ),
        (
            Cells.from_rows([[MAY_1], [MAY_5]]),
            Cells.from_rows([[101.94], [102.27]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-05, "
            "expected 2026-05-04, the business day after row 1's 2026-05-01",
        ),
        (
            Cells.from_rows([[MAY_1], [None], [MAY_5]]),
            Cells.from_rows([[101.94], [106.42], [102.27]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: date cell (2, 1) is blank, expected date",
        ),
        (
            Cells.from_rows([[MAY_1], [MAY_4 + 0.5]]),
            Cells.from_rows([[101.94], [106.42]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: date cell (2, 1) is number 46146.5, expected date",
        ),
        (
            Cells.from_rows([["1-May-2026"], [MAY_4]]),
            Cells.from_rows([[101.94], [106.42]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: date cell (1, 1) is text '1-May-2026', expected date",
        ),
        (
            DATES,
            Cells.from_rows([[101.94], [None], [102.27], [95.08]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: settle cell (2, 1) is blank, expected number",
        ),
        (
            DATES,
            Cells.from_rows([[101.94], ["x"], [102.27], [95.08]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: settle cell (2, 1) is text 'x', expected number",
        ),
        (
            Cells.from_rows([[MAY_1, MAY_4]]),
            SETTLES,
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: date is 1x2 array, expected column of dates",
        ),
        (
            DATES,
            Cells.from_rows([[101.94, 106.42]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: settle is 1x2 array, expected column of numbers",
        ),
        (
            MISSING,
            SETTLES,
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: date is missing, expected column of dates",
        ),
        (
            DATES,
            MISSING,
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: settle is missing, expected column of numbers",
        ),
        (
            None,
            SETTLES,
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: date is blank, expected column of dates",
        ),
        (
            DATES,
            None,
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: settle is blank, expected column of numbers",
        ),
        (
            Cells.from_rows([[MAY_1], [None]]),
            Cells.from_rows([[101.94], [None]]),
            THE_CALENDAR,
            "#ERROR _CreateFuturesFixings: date cell (2, 1) is blank, expected date",
        ),
        (
            DATES,
            SETTLES,
            3.0,
            "#ERROR _CreateFuturesFixings: index is number 3.0, expected index handle",
        ),
        (
            DATES,
            SETTLES,
            None,
            "#ERROR _CreateFuturesFixings: index is blank, expected index handle",
        ),
        (
            DATES,
            SETTLES,
            MISSING,
            "#ERROR _CreateFuturesFixings: index is missing, expected index handle",
        ),
        (
            DATES,
            SETTLES,
            "holiday_calendar:9999999",
            "#ERROR _CreateFuturesFixings: index is text "
            "'holiday_calendar:9999999' naming no live object, expected index handle",
        ),
        (
            DATES,
            SETTLES,
            "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date",
            "#ERROR _CreateFuturesFixings: index is the creator's failure, expected index "
            "handle: #ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date",
        ),
    ],
    ids=[
        "a settle column one row short",
        "dates backwards",
        "a Saturday in the series",
        "a listed holiday in the series, one cell each",
        "a business day without a fixing",
        "a blank among the days",
        "a day with a time",
        "a day typed as text",
        "a blank among the settles",
        "text where a settle should be",
        "a row of days",
        "a row of settles",
        "the days left out",
        "the settles left out",
        "a blank cell where the days should be",
        "a blank cell where the settles should be",
        "both columns wrong, the days named first",
        "a number where the index should be",
        "a blank cell where the index should be",
        "the index left out",
        "text naming no live index",
        "a creator's failure where the index should be",
    ],
)
def test_fixings_that_cannot_be_made_say_why(
    days: object, settles: object, calendar: object, text: str
) -> None:
    calendar = the_index() if calendar is THE_CALENDAR else calendar
    assert bridge.call("_CreateFuturesFixings", [days, settles, calendar]) == text


def test_a_failed_fixings_construction_publishes_no_object_and_no_handle() -> None:
    before = number(the_fixings(DATES, SETTLES), FIXINGS)
    gap = Cells.from_rows([[MAY_1], [MAY_5]])
    assert bridge.call("_CreateFuturesFixings", [gap, SETTLES, the_index()]) == (
        "#ERROR _CreateFuturesFixings: ValueError: settle has 4 settles, expected 2, one per date"
    )
    two = Cells.from_rows([[101.94], [102.27]])
    assert bridge.call("_CreateFuturesFixings", [gap, two, the_index()]) == (
        "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-05, "
        "expected 2026-05-04, the business day after row 1's 2026-05-01"
    )
    saturday = Cells.from_rows([[MAY_1], [MAY_2]])
    assert bridge.call("_CreateFuturesFixings", [saturday, two, the_index()]) == (
        "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-02, a Saturday, "
        "expected a business day"
    )
    assert number(the_fixings(DATES, SETTLES), FIXINGS) == before + 1


def test_a_handle_of_another_kind_is_not_futures_fixings() -> None:
    other = a_valuation_date()
    assert bridge.call("ReadFuturesFixings", [other]) == (
        f"#ERROR ReadFuturesFixings: fixings is valuation date handle {other!r}, "
        "expected futures fixings handle"
    )


def test_a_handle_of_another_kind_is_not_an_index() -> None:
    other = a_valuation_date()
    assert bridge.call("_CreateFuturesFixings", [DATES, SETTLES, other]) == (
        f"#ERROR _CreateFuturesFixings: index is valuation date handle {other!r}, "
        "expected index handle"
    )


def test_an_index_of_another_kind_is_refused_in_the_librarys_words() -> None:
    schedule = bridge.call(
        "_CreateGasDailySchedule",
        [Cells.from_rows([["U26"]]), Cells.from_rows([[46266.0]]), Cells.from_rows([[46295.0]])],
    )
    conventions = bridge.call("_CreateIndexConventions", ["USD", "MMBTU", "USD", "energy", "MMBTU"])
    specifications = bridge.call(
        "_CreateContractSpecifications",
        [
            Cells.from_rows(
                [["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
            ),
            Cells.from_rows([["ICE", 2500.0, 0.0, 0.0]]),
        ],
    )
    gas_daily = bridge.call(
        "_CreateIndex", ["Henry Hub Gas Daily", schedule, conventions, specifications, MISSING]
    )
    assert bridge.call("_CreateFuturesFixings", [DATES, SETTLES, gas_daily]) == (
        "#ERROR _CreateFuturesFixings: ValueError: index is a Gas Daily index, "
        "expected a futures index"
    )


# --- _CreateIfercFixings ---------------------------------------------------------


# The page's sample as the sheet sends it, Waha IFERC gas: the first four months of 2026 as
# codes, and an illustrative index beside each.
IFERC_CODES = Cells.from_rows([["F26"], ["G26"], ["H26"], ["J26"]])
IFERC_PRICES = Cells.from_rows([[1.85], [2.10], [1.95], [1.60]])
IFERC_HANDLE = re.compile(r"[0-9]+:iferc_fixings:.+:([0-9]+)")
# ICE's last trading days and Platts' publication days for those four months, as serials.
IFERC_LAST_TRADING = Cells.from_rows([[46022.0], [46052.0], [46080.0], [46112.0]])
IFERC_PUBLICATION = Cells.from_rows([[46027.0], [46055.0], [46083.0], [46113.0]])


@functools.cache
def the_iferc_index() -> str:
    """The IFERC index of the four months the codes name, made once."""
    schedule = bridge.call(
        "_CreateIfercSchedule", [IFERC_CODES, IFERC_LAST_TRADING, IFERC_PUBLICATION]
    )
    return an_index_of("Waha IFERC", schedule, MISSING)


# The market history reads IFERC fixings, but this hidden reader proves on its own that a handle
# resolves to the fixings the seam kept, the codes as typed and the prices as numbers.
@probe
def ReadIfercFixings(fixings: Handle[IfercFixings]) -> str:
    return f"{' '.join(fixings.codes)} | {' '.join(repr(float(p)) for p in fixings.prices)}"


def iferc(codes: object, prices: object) -> str:
    text = bridge.call("_CreateIfercFixings", [codes, prices, the_iferc_index()])
    assert isinstance(text, str) and IFERC_HANDLE.fullmatch(text), text
    return text


def test_iferc_fixings_are_created_from_two_columns_and_read_back() -> None:
    made = iferc(IFERC_CODES, IFERC_PRICES)
    assert bridge.call("ReadIfercFixings", [made]) == "F26 G26 H26 J26 | 1.85 2.1 1.95 1.6"
    assert made.startswith(f"{PID}:iferc_fixings:Waha IFERC:")  # the index's name, as typed


# A single cell is a column of one, so the fixings of one month need no range.
def test_two_single_cells_make_the_fixings_of_one_month() -> None:
    assert bridge.call("ReadIfercFixings", [iferc("F26", 1.85)]) == "F26 | 1.85"


@pytest.mark.parametrize(
    ("codes", "prices", "text"),
    [
        (
            IFERC_CODES,
            Cells.from_rows([[1.85], [2.10], [1.95]]),
            "#ERROR _CreateIfercFixings: ValueError: price has 3 prices, expected 4, "
            "one per contract_code",
        ),
        (
            IFERC_CODES,
            Cells.from_rows([[1.85], [2.10], [1.95], [1.60], [1.50]]),
            "#ERROR _CreateIfercFixings: ValueError: price has 5 prices, expected 4, "
            "one per contract_code",
        ),
        (
            Cells.from_rows([["F26"], ["G26"], ["G26"], ["J26"]]),
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: ValueError: contract_code row 3 is 'G26', "
            "already given at row 2",
        ),
        (
            IFERC_CODES,
            Cells.from_rows([[1.85], [None], [1.95], [1.60]]),
            "#ERROR _CreateIfercFixings: price cell (2, 1) is blank, expected number",
        ),
        (
            IFERC_CODES,
            Cells.from_rows([[1.85], ["2.10"], [1.95], [1.60]]),
            "#ERROR _CreateIfercFixings: price cell (2, 1) is text '2.10', expected number",
        ),
        (
            Cells.from_rows([["F26"], [46027.0], ["H26"], ["J26"]]),
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code cell (2, 1) is number 46027.0, "
            "expected text",
        ),
        (
            Cells.from_rows([["F26"], [""], ["H26"], ["J26"]]),
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code cell (2, 1) is empty text, expected text",
        ),
        (
            Cells.from_rows([["F26", "G26"]]),
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code is 1x2 array, expected column of text",
        ),
        (
            IFERC_CODES,
            Cells.from_rows([[1.85, 2.10]]),
            "#ERROR _CreateIfercFixings: price is 1x2 array, expected column of numbers",
        ),
        (
            MISSING,
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code is missing, expected column of text",
        ),
        (
            IFERC_CODES,
            MISSING,
            "#ERROR _CreateIfercFixings: price is missing, expected column of numbers",
        ),
        (
            None,
            IFERC_PRICES,
            "#ERROR _CreateIfercFixings: contract_code is blank, expected column of text",
        ),
        (
            IFERC_CODES,
            None,
            "#ERROR _CreateIfercFixings: price is blank, expected column of numbers",
        ),
        (
            Cells.from_rows([["F26"], [46027.0]]),
            Cells.from_rows([[1.85], [None]]),
            "#ERROR _CreateIfercFixings: contract_code cell (2, 1) is number 46027.0, "
            "expected text",
        ),
    ],
    ids=[
        "a price column one row short",
        "a price column one row long",
        "a code given twice",
        "a blank among the prices",
        "text where a price should be",
        "a number among the codes",
        "empty text among the codes",
        "a row of codes",
        "a row of prices",
        "the codes left out",
        "the prices left out",
        "a blank cell where the codes should be",
        "a blank cell where the prices should be",
        "both columns wrong, the codes named first",
    ],
)
def test_iferc_fixings_that_cannot_be_made_say_why(
    codes: object, prices: object, text: str
) -> None:
    assert bridge.call("_CreateIfercFixings", [codes, prices, the_iferc_index()]) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap,
# whether the library or the seam refused the call.
def test_a_failed_iferc_construction_publishes_no_object_and_no_handle() -> None:
    before = number(iferc(IFERC_CODES, IFERC_PRICES), IFERC_HANDLE)
    index = the_iferc_index()
    assert bridge.call("_CreateIfercFixings", [IFERC_CODES, Cells.from_rows([[1.85]]), index]) == (
        "#ERROR _CreateIfercFixings: ValueError: price has 1 price, expected 4, "
        "one per contract_code"
    )
    twice = Cells.from_rows([["F26"], ["F26"]])
    assert bridge.call(
        "_CreateIfercFixings", [twice, Cells.from_rows([[1.85], [2.10]]), index]
    ) == (
        "#ERROR _CreateIfercFixings: ValueError: contract_code row 2 is 'F26', "
        "already given at row 1"
    )
    unknown = Cells.from_rows([["F26"], ["K26"]])
    assert bridge.call(
        "_CreateIfercFixings", [unknown, Cells.from_rows([[1.85], [2.10]]), index]
    ) == (
        "#ERROR _CreateIfercFixings: ValueError: contract_code row 2 is 'K26', "
        "expected one of the index's months"
    )
    assert (
        bridge.call(
            "_CreateIfercFixings",
            [IFERC_CODES, Cells.from_rows([[1.85], [None], [1.95], [1.60]]), index],
        )
        == "#ERROR _CreateIfercFixings: price cell (2, 1) is blank, expected number"
    )
    assert number(iferc(IFERC_CODES, IFERC_PRICES), IFERC_HANDLE) == before + 1


def test_a_handle_of_another_kind_is_not_iferc_fixings() -> None:
    other = the_fixings(DATES, SETTLES)
    assert bridge.call("ReadIfercFixings", [other]) == (
        f"#ERROR ReadIfercFixings: fixings is futures fixings handle {other!r}, "
        "expected iferc fixings handle"
    )
    schedule = cast(
        str,
        bridge.call(
            "_CreateIfercSchedule",
            [
                Cells.from_rows([["F26"], ["G26"]]),
                Cells.from_rows([[46022.0], [46052.0]]),
                Cells.from_rows([[46027.0], [46055.0]]),
            ],
        ),
    )
    assert bridge.call("ReadIfercFixings", [schedule]) == (
        f"#ERROR ReadIfercFixings: fixings is iferc schedule handle {schedule!r}, "
        "expected iferc fixings handle"
    )
    assert bridge.call("_CreateIfercFixings", [IFERC_CODES, IFERC_PRICES, schedule]) == (
        f"#ERROR _CreateIfercFixings: index is iferc schedule handle {schedule!r}, "
        "expected index handle"
    )


# The index by handle: left out, blank, a number, text naming no live object and a handle of
# another kind fail in the seam's words; an index of another kind and a code the index does not
# hold, in the library's.
def test_the_iferc_index_that_cannot_be_taken_says_why() -> None:
    for wrong, what in (
        (MISSING, "is missing"),
        (None, "is blank"),
        (1.85, "is number 1.85"),
        ("index:9999999", "is text 'index:9999999' naming no live object"),
    ):
        assert bridge.call("_CreateIfercFixings", [IFERC_CODES, IFERC_PRICES, wrong]) == (
            f"#ERROR _CreateIfercFixings: index {what}, expected index handle"
        )
    other = the_fixings(DATES, SETTLES)
    assert bridge.call("_CreateIfercFixings", [IFERC_CODES, IFERC_PRICES, other]) == (
        f"#ERROR _CreateIfercFixings: index is futures fixings handle {other!r}, "
        "expected index handle"
    )
    assert bridge.call("_CreateIfercFixings", [IFERC_CODES, IFERC_PRICES, the_index()]) == (
        "#ERROR _CreateIfercFixings: ValueError: index is a futures index, expected an IFERC index"
    )
    assert bridge.call(
        "_CreateIfercFixings", [IFERC_CODES, IFERC_PRICES, the_gas_daily_index()]
    ) == (
        "#ERROR _CreateIfercFixings: ValueError: index is a Gas Daily index, "
        "expected an IFERC index"
    )


# --- _CreateGasDailyFixings ------------------------------------------------------


# The page's sample as the sheet sends it, Henry Hub Gas Daily over Labor Day week 2026: serials
# for 4 to 9 September and an illustrative midpoint beside each, Friday's print carrying the
# weekend and the holiday.
SEP_4, SEP_5, SEP_6, SEP_7, SEP_8, SEP_9 = 46269.0, 46270.0, 46271.0, 46272.0, 46273.0, 46274.0
FLOW_DAYS = Cells.from_rows([[SEP_4], [SEP_5], [SEP_6], [SEP_7], [SEP_8], [SEP_9]])
MIDPOINTS = Cells.from_rows([[2.930], [2.875], [2.875], [2.875], [2.875], [2.900]])
GAS_DAILY_HANDLE = re.compile(r"[0-9]+:gas_daily_fixings:.+:([0-9]+)")


@functools.cache
def the_gas_daily_index() -> str:
    """The Gas Daily index of one month, September 2026, made once."""
    schedule = bridge.call(
        "_CreateGasDailySchedule",
        [Cells.from_rows([["U26"]]), Cells.from_rows([[46266.0]]), Cells.from_rows([[46295.0]])],
    )
    return an_index_of("Henry Hub Gas Daily", schedule, MISSING)


# The library has no consumer of Gas Daily fixings yet, so this hidden reader proves that a
# handle resolves to the fixings the seam kept, the flow days as days and the prices as numbers.
@probe
def ReadGasDailyFixings(fixings: Handle[GasDailyFixings]) -> str:
    kept = " ".join(str(day) for day in fixings.dates)
    return f"{kept} | {' '.join(repr(float(p)) for p in fixings.prices)}"


def gas_daily(flow_days: object, prices: object) -> str:
    text = bridge.call("_CreateGasDailyFixings", [flow_days, prices, the_gas_daily_index()])
    assert isinstance(text, str) and GAS_DAILY_HANDLE.fullmatch(text), text
    return text


def test_gas_daily_fixings_are_created_from_two_columns_and_read_back() -> None:
    made = gas_daily(FLOW_DAYS, MIDPOINTS)
    assert bridge.call("ReadGasDailyFixings", [made]) == (
        "2026-09-04 2026-09-05 2026-09-06 2026-09-07 2026-09-08 2026-09-09 | "
        "2.93 2.875 2.875 2.875 2.875 2.9"
    )
    assert made.startswith(f"{PID}:gas_daily_fixings:Henry Hub Gas Daily:")  # the index's name


# A single cell is a column of one, so the fixings of one day need no range.
def test_two_single_cells_make_the_fixings_of_one_day() -> None:
    assert bridge.call("ReadGasDailyFixings", [gas_daily(SEP_4, 2.930)]) == "2026-09-04 | 2.93"


@pytest.mark.parametrize(
    ("flow_days", "prices", "text"),
    [
        (
            FLOW_DAYS,
            Cells.from_rows([[2.930], [2.875], [2.875], [2.875], [2.875]]),
            "#ERROR _CreateGasDailyFixings: ValueError: price has 5 prices, expected 6, "
            "one per flow_date",
        ),
        (
            Cells.from_rows([[SEP_4], [SEP_6]]),
            Cells.from_rows([[2.930], [2.875]]),
            "#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-06, "
            "expected 2026-09-05, the day after row 1's 2026-09-04",
        ),
        (
            Cells.from_rows([[SEP_4], [SEP_4]]),
            Cells.from_rows([[2.930], [2.875]]),
            "#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-04, "
            "expected 2026-09-05, the day after row 1's 2026-09-04",
        ),
        (
            Cells.from_rows([[SEP_5], [SEP_4]]),
            Cells.from_rows([[2.875], [2.930]]),
            "#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-04, "
            "expected 2026-09-06, the day after row 1's 2026-09-05",
        ),
        (
            Cells.from_rows([[SEP_4], [None], [SEP_6]]),
            Cells.from_rows([[2.930], [2.875], [2.875]]),
            "#ERROR _CreateGasDailyFixings: flow_date cell (2, 1) is blank, expected date",
        ),
        (
            Cells.from_rows([[SEP_4], [SEP_5 + 0.5]]),
            Cells.from_rows([[2.930], [2.875]]),
            "#ERROR _CreateGasDailyFixings: flow_date cell (2, 1) is number 46270.5, expected date",
        ),
        (
            Cells.from_rows([["4-Sep-2026"], [SEP_5]]),
            Cells.from_rows([[2.930], [2.875]]),
            "#ERROR _CreateGasDailyFixings: flow_date cell (1, 1) is text '4-Sep-2026', "
            "expected date",
        ),
        (
            FLOW_DAYS,
            Cells.from_rows([[2.930], [None], [2.875], [2.875], [2.875], [2.900]]),
            "#ERROR _CreateGasDailyFixings: price cell (2, 1) is blank, expected number",
        ),
        (
            FLOW_DAYS,
            Cells.from_rows([[2.930], ["2.875"], [2.875], [2.875], [2.875], [2.900]]),
            "#ERROR _CreateGasDailyFixings: price cell (2, 1) is text '2.875', expected number",
        ),
        (
            Cells.from_rows([[SEP_4, SEP_5]]),
            MIDPOINTS,
            "#ERROR _CreateGasDailyFixings: flow_date is 1x2 array, expected column of dates",
        ),
        (
            FLOW_DAYS,
            Cells.from_rows([[2.930, 2.875]]),
            "#ERROR _CreateGasDailyFixings: price is 1x2 array, expected column of numbers",
        ),
        (
            MISSING,
            MIDPOINTS,
            "#ERROR _CreateGasDailyFixings: flow_date is missing, expected column of dates",
        ),
        (
            FLOW_DAYS,
            MISSING,
            "#ERROR _CreateGasDailyFixings: price is missing, expected column of numbers",
        ),
        (
            None,
            MIDPOINTS,
            "#ERROR _CreateGasDailyFixings: flow_date is blank, expected column of dates",
        ),
        (
            FLOW_DAYS,
            None,
            "#ERROR _CreateGasDailyFixings: price is blank, expected column of numbers",
        ),
        (
            Cells.from_rows([[SEP_4], [None]]),
            Cells.from_rows([[2.930], [None]]),
            "#ERROR _CreateGasDailyFixings: flow_date cell (2, 1) is blank, expected date",
        ),
    ],
    ids=[
        "a price column one row short",
        "a day skipped",
        "a day given twice",
        "a series pasted newest first",
        "a blank among the days",
        "a day with a time",
        "a day typed as text",
        "a blank among the prices",
        "text where a price should be",
        "a row of days",
        "a row of prices",
        "the days left out",
        "the prices left out",
        "a blank cell where the days should be",
        "a blank cell where the prices should be",
        "both columns wrong, the days named first",
    ],
)
def test_gas_daily_fixings_that_cannot_be_made_say_why(
    flow_days: object, prices: object, text: str
) -> None:
    assert bridge.call("_CreateGasDailyFixings", [flow_days, prices, the_gas_daily_index()]) == text


# The publication number moves only when an object is stored, so a failed creator leaves no gap,
# whether the library or the seam refused the call.
def test_a_failed_gas_daily_construction_publishes_no_object_and_no_handle() -> None:
    before = number(gas_daily(FLOW_DAYS, MIDPOINTS), GAS_DAILY_HANDLE)
    index = the_gas_daily_index()
    assert bridge.call(
        "_CreateGasDailyFixings", [FLOW_DAYS, Cells.from_rows([[2.930]]), index]
    ) == (
        "#ERROR _CreateGasDailyFixings: ValueError: price has 1 price, expected 6, "
        "one per flow_date"
    )
    skipped = Cells.from_rows([[SEP_4], [SEP_6]])
    assert bridge.call(
        "_CreateGasDailyFixings", [skipped, Cells.from_rows([[2.930], [2.875]]), index]
    ) == (
        "#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-06, "
        "expected 2026-09-05, the day after row 1's 2026-09-04"
    )
    assert (
        bridge.call(
            "_CreateGasDailyFixings",
            [
                FLOW_DAYS,
                Cells.from_rows([[2.930], [None], [2.875], [2.875], [2.875], [2.900]]),
                index,
            ],
        )
        == "#ERROR _CreateGasDailyFixings: price cell (2, 1) is blank, expected number"
    )
    assert number(gas_daily(FLOW_DAYS, MIDPOINTS), GAS_DAILY_HANDLE) == before + 1


def test_a_handle_of_another_kind_is_not_gas_daily_fixings() -> None:
    other = the_fixings(DATES, SETTLES)
    assert bridge.call("ReadGasDailyFixings", [other]) == (
        f"#ERROR ReadGasDailyFixings: fixings is futures fixings handle {other!r}, "
        "expected gas daily fixings handle"
    )
    schedule = cast(
        str,
        bridge.call(
            "_CreateGasDailySchedule",
            [
                Cells.from_rows([["U26"], ["V26"]]),
                Cells.from_rows([[46266.0], [46296.0]]),
                Cells.from_rows([[46295.0], [46326.0]]),
            ],
        ),
    )
    assert bridge.call("ReadGasDailyFixings", [schedule]) == (
        f"#ERROR ReadGasDailyFixings: fixings is gas daily schedule handle {schedule!r}, "
        "expected gas daily fixings handle"
    )
    assert bridge.call("_CreateGasDailyFixings", [FLOW_DAYS, MIDPOINTS, schedule]) == (
        f"#ERROR _CreateGasDailyFixings: index is gas daily schedule handle {schedule!r}, "
        "expected index handle"
    )


# The index by handle: left out, blank, a number, text naming no live object and a handle of
# another kind fail in the seam's words; an index of another kind in the library's.
def test_the_gas_daily_index_that_cannot_be_taken_says_why() -> None:
    for wrong, what in (
        (MISSING, "is missing"),
        (None, "is blank"),
        (2.93, "is number 2.93"),
        ("index:9999999", "is text 'index:9999999' naming no live object"),
    ):
        assert bridge.call("_CreateGasDailyFixings", [FLOW_DAYS, MIDPOINTS, wrong]) == (
            f"#ERROR _CreateGasDailyFixings: index {what}, expected index handle"
        )
    other = the_fixings(DATES, SETTLES)
    assert bridge.call("_CreateGasDailyFixings", [FLOW_DAYS, MIDPOINTS, other]) == (
        f"#ERROR _CreateGasDailyFixings: index is futures fixings handle {other!r}, "
        "expected index handle"
    )
    assert bridge.call("_CreateGasDailyFixings", [FLOW_DAYS, MIDPOINTS, the_index()]) == (
        "#ERROR _CreateGasDailyFixings: ValueError: index is a futures index, "
        "expected a Gas Daily index"
    )
    assert bridge.call("_CreateGasDailyFixings", [FLOW_DAYS, MIDPOINTS, the_iferc_index()]) == (
        "#ERROR _CreateGasDailyFixings: ValueError: index is an IFERC index, "
        "expected a Gas Daily index"
    )


# --- _CreatePriceVector -----------------------------------------------------------


# The page's sample as the sheet sends it: the index's name as typed and four prices, a zero and
# a negative among them and the first repeated, selected without a header.
NAME = "WTI NYMEX"
PRICES = Cells.from_rows([[74.25], [0.0], [-0.5], [74.25]])
VECTOR = re.compile(r"[0-9]+:price_vector:.+:([0-9]+)")


def a_vector(prices: object = PRICES, name: object = NAME) -> str:
    text = bridge.call("_CreatePriceVector", [name, prices])
    assert isinstance(text, str) and VECTOR.fullmatch(text), text
    return text


# The spill shows the prices and no name, so this hidden reader proves on its own that a handle
# resolves to the vector the seam kept, its name as typed.
@probe
def ReadPriceVectorName(price_vector: Handle[PriceVector]) -> str:
    return price_vector.index_name


def test_a_price_vector_is_created_from_a_name_and_a_column_and_read_back_in_order() -> None:
    made = a_vector()
    assert rows(read(made)) == [["price"], ["float64"], [74.25], [0.0], [-0.5], [74.25]]
    assert bridge.call("ReadPriceVectorName", [made]) == "WTI NYMEX"


def test_one_cell_is_a_vector_of_one_price() -> None:
    assert rows(read(a_vector(74.25))) == [["price"], ["float64"], [74.25]]


# The name is kept as typed and checked by nothing here: another case, a space at the end, a name
# no index bears and a name of one character make vectors alike, a literal in the formula and
# the cell holding it arriving as the same text; the handle carries the name between the tag and
# the count.
@pytest.mark.parametrize(
    "name",
    ["wti nymex", "WTI NYMEX ", "Brent", "x"],
    ids=["another case", "a space at the end", "a name no index bears", "one character"],
)
def test_any_text_names_a_vector_and_is_kept_as_typed(name: str) -> None:
    made = a_vector(name=name)
    assert bridge.call("ReadPriceVectorName", [made]) == name
    assert made.startswith(f"{PID}:price_vector:{name}:")


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
    ("args", "text"),
    [
        (
            [NAME, Cells.from_rows([[74.25, 0.0, -0.5]])],
            "#ERROR _CreatePriceVector: prices is 1x3 array, expected column of numbers",
        ),
        (
            [NAME, Cells.from_rows([[74.25, 1.0], [0.0, 2.0]])],
            "#ERROR _CreatePriceVector: prices is 2x2 array, expected column of numbers",
        ),
        (
            [NAME, Cells.from_rows([["price"], [74.25]])],
            "#ERROR _CreatePriceVector: prices cell (1, 1) is text 'price', expected number",
        ),
        (
            [NAME, Cells.from_rows([[74.25], ["74.25"]])],
            "#ERROR _CreatePriceVector: prices cell (2, 1) is text '74.25', expected number",
        ),
        (
            [NAME, Cells.from_rows([[74.25], [True]])],
            "#ERROR _CreatePriceVector: prices cell (2, 1) is boolean TRUE, expected number",
        ),
        (
            [NAME, Cells.from_rows([[74.25], [None]])],
            "#ERROR _CreatePriceVector: prices cell (2, 1) is blank, expected number",
        ),
        (
            [NAME, None],
            "#ERROR _CreatePriceVector: prices is blank, expected column of numbers",
        ),
        (
            [NAME, MISSING],
            "#ERROR _CreatePriceVector: prices is missing, expected column of numbers",
        ),
        (
            [NAME, "74.25"],
            "#ERROR _CreatePriceVector: prices is text '74.25', expected column of numbers",
        ),
        (
            [NAME, True],
            "#ERROR _CreatePriceVector: prices is boolean TRUE, expected column of numbers",
        ),
        ([None, PRICES], "#ERROR _CreatePriceVector: index_name is blank, expected text"),
        ([MISSING, PRICES], "#ERROR _CreatePriceVector: index_name is missing, expected text"),
        (["", PRICES], "#ERROR _CreatePriceVector: index_name is empty text, expected text"),
        ([74.25, PRICES], "#ERROR _CreatePriceVector: index_name is number 74.25, expected text"),
        ([True, PRICES], "#ERROR _CreatePriceVector: index_name is boolean TRUE, expected text"),
        (
            [Cells.from_rows([["WTI NYMEX"]]), PRICES],
            "#ERROR _CreatePriceVector: index_name is 1x1 array, expected text",
        ),
        (
            [Cells.from_rows([["WTI NYMEX"], ["Brent"]]), PRICES],
            "#ERROR _CreatePriceVector: index_name is 2x1 array, expected text",
        ),
        ([None, None], "#ERROR _CreatePriceVector: index_name is blank, expected text"),
        ([MISSING, MISSING], "#ERROR _CreatePriceVector: index_name is missing, expected text"),
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
        "a blank cell where the name should be",
        "the name left out",
        "empty text where the name should be",
        "a number where the name should be",
        "a boolean where the name should be",
        "a one-cell range where the name should be",
        "two names",
        "both blank, the name named first",
        "both left out, the name named first",
    ],
)
def test_a_vector_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    assert bridge.call("_CreatePriceVector", args) == text


# The store's diagnostic read counts the bytes of prices the live vectors hold, and a release
# takes them out; nothing per call reads it.
def test_the_live_count_carries_the_price_bytes_of_live_vectors() -> None:
    live, held = bridge.live_handles()
    made = a_vector()
    assert bridge.live_handles() == (live + 1, held + 4 * 8)
    assert bridge.release(made) is True
    assert bridge.live_handles() == (live, held)


def test_a_failed_vector_publishes_no_object_and_no_handle() -> None:
    before = number(a_vector(), VECTOR)
    assert bridge.call("_CreatePriceVector", [NAME, Cells.from_rows([[74.25], [None]])]) == (
        "#ERROR _CreatePriceVector: prices cell (2, 1) is blank, expected number"
    )
    assert bridge.call("_CreatePriceVector", [None, PRICES]) == (
        "#ERROR _CreatePriceVector: index_name is blank, expected text"
    )
    assert number(a_vector(), VECTOR) == before + 1
