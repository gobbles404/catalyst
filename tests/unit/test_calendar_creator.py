"""The calendar through the seam: three handles and the fixing mode in, one out, and the table its
handle spills, the same for daily and for monthly fixings."""

import re
from typing import cast

import pytest
from test_utilities import read, rows

from goosedove.excel import bridge
from goosedove.excel.bridge import BOOLEAN_CODE, MISSING, NUMBER_CODE, TEXT_CODE, Cells

# The page's sample as the sheet sends it: serials for 19 May, 20 May, 25 May, 22 June and
# 21 July 2026.
MAY_19, MAY_20, MAY_25, JUN_22, JUL_21 = 46161.0, 46162.0, 46167.0, 46195.0, 46224.0
HANDLE = re.compile(r"calendar:[0-9a-f]{6}:([0-9]{6})")
HEADERS = ["date", "prompt_contract", "is_business_day", "is_past"]
TYPES = ["datetime64[D]", "str", "bool", "bool"]


def column(*cells: object) -> Cells:
    return Cells.from_rows([[cell] for cell in cells])


def a_valuation(serial: float = MAY_25, fraction: float = 0.5) -> str:
    text = bridge.call("_CreateValuationDate", [serial, fraction])
    assert isinstance(text, str) and text.startswith("valuation_date:"), text
    return text


def a_schedule(
    codes: tuple[str, ...], expiries: tuple[float, ...], publications: tuple[float, ...] = ()
) -> str:
    published = column(*publications) if publications else MISSING
    text = bridge.call(
        "_CreateExpirySchedule", [column(*codes), column(*expiries), MISSING, published]
    )
    assert isinstance(text, str) and text.startswith("expiry_schedule:"), text
    return text


def a_holiday_calendar(*serials: float) -> str:
    text = bridge.call("_CreateHolidayCalendar", [column(*serials)])
    assert isinstance(text, str) and text.startswith("holiday_calendar:"), text
    return text


SAMPLE = (("m26", "n26", "q26"), (MAY_19, JUN_22, JUL_21))
# The same schedule with the day each contract's price is published, for a monthly calendar.
PUBLISHED = (("m26", "n26", "q26"), (MAY_19, JUN_22, JUL_21), (MAY_20, JUN_22 + 1, JUL_21 + 1))


def a_calendar(
    valuation: object = None,
    schedule: object = None,
    holidays: object = None,
    mode: object = "daily",
) -> str:
    args = [
        valuation or a_valuation(),
        mode,
        schedule or a_schedule(*SAMPLE),
        holidays or a_holiday_calendar(MAY_25),
    ]
    text = bridge.call("_CreateCalendar", args)
    assert isinstance(text, str) and HANDLE.fullmatch(text), text
    return text


def number(text: str) -> int:
    match = HANDLE.fullmatch(text)
    assert match, text
    return int(match.group(1))


def test_a_calendar_is_created_from_three_handles_and_read_back_day_by_day() -> None:
    shown = rows(read(a_calendar()))
    assert len(shown) == 65
    assert shown[0] == HEADERS
    assert shown[1] == TYPES
    assert shown[2] == [MAY_20, "n26", 1.0, 1.0]
    assert shown[4] == [MAY_20 + 2, "n26", 1.0, 1.0]
    assert shown[5] == [MAY_20 + 3, "n26", 0.0, 1.0]
    assert shown[6] == [MAY_20 + 4, "n26", 0.0, 1.0]
    assert shown[7] == [MAY_25, "n26", 0.0, 0.0]
    assert shown[8] == [MAY_25 + 1, "n26", 1.0, 0.0]
    assert shown[35] == [JUN_22, "n26", 1.0, 0.0]
    assert shown[36] == [JUN_22 + 1, "q26", 1.0, 0.0]
    assert shown[64] == [JUL_21, "q26", 1.0, 0.0]
    assert [row[0] for row in shown[2:]] == [MAY_20 + i for i in range(63)]


# The sheet is handed booleans for the two flags, dates for the days and text for the codes:
# the kinds say so, not the numbers behind them.
def test_the_flags_reach_the_sheet_as_booleans() -> None:
    kinds, _, _ = read(a_calendar())
    assert (kinds[:2] == TEXT_CODE).all()
    assert (kinds[2:, 0] == NUMBER_CODE).all()
    assert (kinds[2:, 1] == TEXT_CODE).all()
    assert (kinds[2:, 2:] == BOOLEAN_CODE).all()


def test_two_expiries_a_day_apart_spill_one_row() -> None:
    made = a_calendar(schedule=a_schedule(("m26", "n26"), (MAY_19, MAY_20)))
    assert rows(read(made)) == [HEADERS, TYPES, [MAY_20, "n26", 1.0, 1.0]]


def test_the_codes_come_back_exactly_as_typed() -> None:
    made = a_calendar(schedule=a_schedule(("M26", "n 26", "Q26 "), (MAY_19, JUN_22, JUL_21)))
    shown = rows(read(made))
    assert shown[2][1] == "n 26"
    assert shown[36][1] == "Q26 "


# A monthly calendar spills the same four columns as the daily one over the same schedule, and
# the mode is not a column: the handle is the difference, and the history refuses one.
def test_a_monthly_calendar_spills_the_same_rows_as_the_daily_one() -> None:
    schedule = a_schedule(*PUBLISHED)
    daily = a_calendar(schedule=schedule, mode="daily")
    monthly = a_calendar(schedule=schedule, mode="monthly")
    assert HANDLE.fullmatch(monthly) and monthly != daily
    assert rows(read(monthly)) == rows(read(daily)) == rows(read(a_calendar()))


def test_a_valuation_date_on_the_first_day_and_the_fraction_change_the_past_flag_alone() -> None:
    for fraction in (0.0, 1.0):
        shown = rows(read(a_calendar(valuation=a_valuation(MAY_20, fraction))))
        assert [row[3] for row in shown[2:]] == [0.0] * 63
        assert shown[2][:3] == [MAY_20, "n26", 1.0]


THE_VALUATION, THE_SCHEDULE, THE_HOLIDAYS = object(), object(), object()


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [THE_VALUATION, "daily", (("m26",), (MAY_19,)), THE_HOLIDAYS],
            "#ERROR _CreateCalendar: ValueError: expiry_schedule has 1 contract, "
            "expected at least 2",
        ),
        (
            [THE_VALUATION, "daily", (("m26", "m26"), (MAY_19, JUN_22)), THE_HOLIDAYS],
            "#ERROR _CreateCalendar: ValueError: "
            "future_code row 2 is 'm26', already given at row 1",
        ),
        (
            [
                THE_VALUATION,
                "daily",
                (("m26", "n26", "n26"), (MAY_19, JUN_22, JUL_21)),
                THE_HOLIDAYS,
            ],
            "#ERROR _CreateCalendar: ValueError: "
            "future_code row 3 is 'n26', already given at row 2",
        ),
        (
            [THE_VALUATION, "daily", (("m26", "n26"), (JUN_22, MAY_19)), THE_HOLIDAYS],
            "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 2026-05-19, "
            "expected a date after row 1's 2026-06-22",
        ),
        (
            [THE_VALUATION, "daily", (("m26", "n26"), (MAY_19, MAY_19)), THE_HOLIDAYS],
            "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 2026-05-19, "
            "expected a date after row 1's 2026-05-19",
        ),
        (
            [THE_VALUATION, "daily", (("m26", "n26"), (MAY_19, 1094736.0)), THE_HOLIDAYS],
            "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 4897-04-12, "
            "expected within 1048574 days of row 1's 2026-05-19",
        ),
        (
            [MISSING, "daily", THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: valuation_date is missing, expected valuation date handle",
        ),
        (
            [None, "daily", THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: valuation_date is blank, expected valuation date handle",
        ),
        (
            [MAY_25, "daily", THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: valuation_date is number 46167.0, "
            "expected valuation date handle",
        ),
        (
            ["x", "daily", THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: valuation_date is text 'x' naming no live object, "
            "expected valuation date handle",
        ),
        (
            [THE_VALUATION, "daily", MISSING, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: expiry_schedule is missing, expected expiry schedule handle",
        ),
        (
            [THE_VALUATION, "daily", THE_SCHEDULE, MISSING],
            "#ERROR _CreateCalendar: holiday_calendar is missing, expected holiday calendar handle",
        ),
        (
            [THE_VALUATION, "daily", THE_SCHEDULE, "calendar:000000:000001"],
            "#ERROR _CreateCalendar: holiday_calendar is text 'calendar:000000:000001' naming "
            "no live object, expected holiday calendar handle",
        ),
        (
            [THE_VALUATION, MISSING, THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: fixing_mode is missing, expected text",
        ),
        (
            [THE_VALUATION, None, THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: fixing_mode is blank, expected text",
        ),
        (
            [THE_VALUATION, "", THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: fixing_mode is empty text, expected text",
        ),
        (
            [THE_VALUATION, 1.0, THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: fixing_mode is number 1.0, expected text",
        ),
        (
            [THE_VALUATION, True, THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: fixing_mode is boolean TRUE, expected text",
        ),
        (
            [THE_VALUATION, "Daily", THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: ValueError: fixing_mode is 'Daily', "
            "expected 'daily' or 'monthly'",
        ),
        (
            [THE_VALUATION, " monthly", THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: ValueError: fixing_mode is ' monthly', "
            "expected 'daily' or 'monthly'",
        ),
        (
            [THE_VALUATION, "monthly", THE_SCHEDULE, THE_HOLIDAYS],
            "#ERROR _CreateCalendar: ValueError: fixing_mode 'monthly' requires "
            "publication_date in expiry_schedule",
        ),
        (
            [THE_VALUATION, "monthly", (("m26",), (MAY_19,)), THE_HOLIDAYS],
            "#ERROR _CreateCalendar: ValueError: fixing_mode 'monthly' requires "
            "publication_date in expiry_schedule",
        ),
    ],
    ids=[
        "a schedule of one contract",
        "the boundary code given again",
        "a code given twice after the boundary",
        "expiries backwards",
        "two expiries equal",
        "a span no sheet could show",
        "the valuation date left out",
        "a blank cell where the valuation date should be",
        "a number where the valuation date should be",
        "text naming no live valuation date",
        "the schedule left out",
        "the holiday calendar left out",
        "a dead handle where the holiday calendar should be",
        "the mode left out",
        "a blank cell where the mode should be",
        "empty text where the mode should be",
        "a number where the mode should be",
        "a boolean where the mode should be",
        "the mode capitalized",
        "the mode with a space before it",
        "monthly over a schedule without publication dates",
        "monthly over a schedule of one contract without them, the mode's rule first",
    ],
)
def test_a_calendar_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    given: list[object] = []
    for arg in args:
        if arg is THE_VALUATION:
            given.append(a_valuation())
        elif arg is THE_SCHEDULE:
            given.append(a_schedule(*SAMPLE))
        elif arg is THE_HOLIDAYS:
            given.append(a_holiday_calendar(MAY_25))
        elif isinstance(arg, tuple):
            codes, expiries = cast(tuple[tuple[str, ...], tuple[float, ...]], arg)
            given.append(a_schedule(codes, expiries))
        else:
            given.append(arg)
    assert bridge.call("_CreateCalendar", given) == text


def test_a_handle_of_another_kind_in_any_slot_is_refused_by_name() -> None:
    valuation, schedule, holidays = a_valuation(), a_schedule(*SAMPLE), a_holiday_calendar(MAY_25)
    made = a_calendar(valuation, schedule, holidays)
    assert bridge.call("_CreateCalendar", [schedule, "daily", schedule, holidays]) == (
        f"#ERROR _CreateCalendar: valuation_date is expiry schedule handle {schedule!r}, "
        "expected valuation date handle"
    )
    assert bridge.call("_CreateCalendar", [valuation, "daily", holidays, holidays]) == (
        f"#ERROR _CreateCalendar: expiry_schedule is holiday calendar handle {holidays!r}, "
        "expected expiry schedule handle"
    )
    assert bridge.call("_CreateCalendar", [valuation, "daily", schedule, made]) == (
        f"#ERROR _CreateCalendar: holiday_calendar is calendar handle {made!r}, "
        "expected holiday calendar handle"
    )


# The three-handle form of #82 to #86 is gone: its schedule lands in the mode's slot, which takes
# any text, and its holiday calendar in the schedule's, which names the wrong kind.
def test_the_old_three_argument_form_fails_and_makes_nothing() -> None:
    valuation, schedule, holidays = a_valuation(), a_schedule(*SAMPLE), a_holiday_calendar(MAY_25)
    before = number(a_calendar(valuation, schedule, holidays))
    assert bridge.call("_CreateCalendar", [valuation, schedule, holidays, MISSING]) == (
        f"#ERROR _CreateCalendar: expiry_schedule is holiday calendar handle {holidays!r}, "
        "expected expiry schedule handle"
    )
    assert bridge.call("_CreateCalendar", [valuation, schedule, MISSING, MISSING]) == (
        "#ERROR _CreateCalendar: expiry_schedule is missing, expected expiry schedule handle"
    )
    assert number(a_calendar(valuation, schedule, holidays)) == before + 1


def test_a_failed_construction_publishes_no_object_and_no_handle() -> None:
    valuation, schedule, holidays = a_valuation(), a_schedule(*SAMPLE), a_holiday_calendar(MAY_25)
    one = a_schedule(("m26",), (MAY_19,))
    before = number(a_calendar(valuation, schedule, holidays))
    assert bridge.call("_CreateCalendar", [valuation, "daily", one, holidays]) == (
        "#ERROR _CreateCalendar: ValueError: expiry_schedule has 1 contract, expected at least 2"
    )
    assert bridge.call("_CreateCalendar", [valuation, "monthly", schedule, holidays]) == (
        "#ERROR _CreateCalendar: ValueError: fixing_mode 'monthly' requires publication_date "
        "in expiry_schedule"
    )
    assert number(a_calendar(valuation, schedule, holidays)) == before + 1


def test_a_dead_calendar_handle_cannot_be_read() -> None:
    assert bridge.call("util_ReadHandle", ["calendar:000000:000001"]) == (
        "#ERROR util_ReadHandle: handle is text 'calendar:000000:000001' naming no live object, "
        "expected a handle"
    )
