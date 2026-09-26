"""The calendar through the seam: a valuation date and an index in, one handle out, and the table
it spills."""

import re
from typing import cast

import pytest
from test_utilities import read, rows

from goosedove.excel import bridge
from goosedove.excel.bridge import BOOLEAN_CODE, MISSING, NUMBER_CODE, TEXT_CODE, Cells

# The page's sample as the sheet sends it: serials for 19 May, 20 May, 25 May, 22 June and
# 21 July 2026.
MAY_19, MAY_20, MAY_25, JUN_22, JUL_21 = 46161.0, 46162.0, 46167.0, 46195.0, 46224.0
HANDLE = re.compile(r"calendar:.+:([0-9]+)")
HEADERS = ["date", "contract", "is_priced", "is_fixed"]
TYPES = ["datetime64[D]", "str", "bool", "bool"]


def column(*cells: object) -> Cells:
    return Cells.from_rows([[cell] for cell in cells])


def a_valuation(serial: float = MAY_25, fraction: float = 0.5) -> str:
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


def an_index(schedule: object, holidays: object = MISSING) -> str:
    """The index handle of that schedule handle and holiday calendar handle, with one set of
    conventions and specifications, since the calendar reads neither."""
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
    text = bridge.call("_CreateIndex", ["sample", schedule, conventions, specifications, holidays])
    assert isinstance(text, str) and text.startswith("index:"), text
    return text


SAMPLE = (("m26", "n26", "q26"), (MAY_19, JUN_22, JUL_21))


def a_futures_index(schedule: object = None, holidays: object = None) -> str:
    return an_index(schedule or a_schedule(*SAMPLE), holidays or a_holiday_calendar(MAY_25))


def a_calendar(valuation: object = None, index: object = None) -> str:
    text = bridge.call("_CreateCalendar", [valuation or a_valuation(), index or a_futures_index()])
    assert isinstance(text, str) and HANDLE.fullmatch(text), text
    return text


def number(text: str) -> int:
    match = HANDLE.fullmatch(text)
    assert match, text
    return int(match.group(1))


# The calendar's handle carries its index's name, sample, between the tag and the count.
def test_a_calendar_handle_carries_its_indexs_name() -> None:
    made = a_calendar()
    assert made.startswith("calendar:sample:")
    assert made[len("calendar:sample:") :].isdigit()


def test_a_calendar_is_created_from_two_handles_and_read_back_day_by_day() -> None:
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
    made = a_calendar(index=a_futures_index(a_schedule(("m26", "n26"), (MAY_19, MAY_20))))
    assert rows(read(made)) == [HEADERS, TYPES, [MAY_20, "n26", 1.0, 1.0]]


def test_the_codes_come_back_exactly_as_typed() -> None:
    made = a_calendar(
        index=a_futures_index(a_schedule(("M26", "n 26", "Q26 "), (MAY_19, JUN_22, JUL_21)))
    )
    shown = rows(read(made))
    assert shown[2][1] == "n 26"
    assert shown[36][1] == "Q26 "


def test_a_valuation_date_on_the_first_day_and_the_fraction_change_the_past_flag_alone() -> None:
    for fraction in (0.0, 1.0):
        shown = rows(read(a_calendar(valuation=a_valuation(MAY_20, fraction))))
        assert [row[3] for row in shown[2:]] == [0.0] * 63
        assert shown[2][:3] == [MAY_20, "n26", 1.0]


THE_VALUATION, THE_INDEX = object(), object()


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (
            [THE_VALUATION, (("m26",), (MAY_19,))],
            "#ERROR _CreateCalendar: ValueError: index has 1 contract, expected at least 2",
        ),
        (
            [THE_VALUATION, (("m26", "m26"), (MAY_19, JUN_22))],
            "#ERROR _CreateCalendar: ValueError: "
            "contract_code row 2 is 'm26', already given at row 1",
        ),
        (
            [THE_VALUATION, (("m26", "n26", "n26"), (MAY_19, JUN_22, JUL_21))],
            "#ERROR _CreateCalendar: ValueError: "
            "contract_code row 3 is 'n26', already given at row 2",
        ),
        (
            [THE_VALUATION, (("m26", "n26"), (JUN_22, MAY_19))],
            "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 2026-05-19, "
            "expected a date after row 1's 2026-06-22",
        ),
        (
            [THE_VALUATION, (("m26", "n26"), (MAY_19, MAY_19))],
            "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 2026-05-19, "
            "expected a date after row 1's 2026-05-19",
        ),
        (
            [THE_VALUATION, (("m26", "n26"), (MAY_19, 1094736.0))],
            "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 4897-04-12, "
            "expected within 1048574 days of row 1's 2026-05-19",
        ),
        (
            [MISSING, THE_INDEX],
            "#ERROR _CreateCalendar: valuation_date is missing, expected valuation date handle",
        ),
        (
            [None, THE_INDEX],
            "#ERROR _CreateCalendar: valuation_date is blank, expected valuation date handle",
        ),
        (
            [MAY_25, THE_INDEX],
            "#ERROR _CreateCalendar: valuation_date is number 46167.0, "
            "expected valuation date handle",
        ),
        (
            ["x", THE_INDEX],
            "#ERROR _CreateCalendar: valuation_date is text 'x' naming no live object, "
            "expected valuation date handle",
        ),
        (
            [THE_VALUATION, MISSING],
            "#ERROR _CreateCalendar: index is missing, expected index handle",
        ),
        (
            [THE_VALUATION, None],
            "#ERROR _CreateCalendar: index is blank, expected index handle",
        ),
        (
            [THE_VALUATION, 3.0],
            "#ERROR _CreateCalendar: index is number 3.0, expected index handle",
        ),
        (
            [THE_VALUATION, "index:9999999"],
            "#ERROR _CreateCalendar: index is text 'index:9999999' naming no live object, "
            "expected index handle",
        ),
        (
            [THE_VALUATION, "#ERROR _CreateIndex: name is blank, expected text"],
            "#ERROR _CreateCalendar: index is the creator's failure, expected index handle: "
            "#ERROR _CreateIndex: name is blank, expected text",
        ),
    ],
    ids=[
        "an index of one contract",
        "the boundary code given again",
        "a code given twice after the boundary",
        "expiries backwards",
        "two expiries equal",
        "a span no sheet could show",
        "the valuation date left out",
        "a blank cell where the valuation date should be",
        "a number where the valuation date should be",
        "text naming no live valuation date",
        "the index left out",
        "a blank cell where the index should be",
        "a number where the index should be",
        "a dead handle where the index should be",
        "the index creator's failure relayed",
    ],
)
def test_a_calendar_that_cannot_be_made_says_why(args: list[object], text: str) -> None:
    given: list[object] = []
    for arg in args:
        if arg is THE_VALUATION:
            given.append(a_valuation())
        elif arg is THE_INDEX:
            given.append(a_futures_index())
        elif isinstance(arg, tuple):
            codes, expiries = cast(tuple[tuple[str, ...], tuple[float, ...]], arg)
            given.append(a_futures_index(a_schedule(codes, expiries)))
        else:
            given.append(arg)
    assert bridge.call("_CreateCalendar", given) == text


def test_a_handle_of_another_kind_in_either_slot_is_refused_by_name() -> None:
    valuation, schedule, holidays = a_valuation(), a_schedule(*SAMPLE), a_holiday_calendar(MAY_25)
    index = an_index(schedule, holidays)
    made = a_calendar(valuation, index)
    assert bridge.call("_CreateCalendar", [index, index]) == (
        f"#ERROR _CreateCalendar: valuation_date is index handle {index!r}, "
        "expected valuation date handle"
    )
    for wrong, word in (
        (schedule, "futures schedule"),
        (holidays, "holiday calendar"),
        (valuation, "valuation date"),
        (made, "calendar"),
    ):
        assert bridge.call("_CreateCalendar", [valuation, wrong]) == (
            f"#ERROR _CreateCalendar: index is {word} handle {wrong!r}, expected index handle"
        )


def test_a_failed_construction_publishes_no_object_and_no_handle() -> None:
    valuation, index = a_valuation(), a_futures_index()
    one = a_futures_index(a_schedule(("m26",), (MAY_19,)))
    before = number(a_calendar(valuation, index))
    assert bridge.call("_CreateCalendar", [valuation, one]) == (
        "#ERROR _CreateCalendar: ValueError: index has 1 contract, expected at least 2"
    )
    assert number(a_calendar(valuation, index)) == before + 1


def test_a_dead_calendar_handle_cannot_be_read() -> None:
    assert bridge.call("util_ReadHandle", ["calendar:9999999"]) == (
        "#ERROR util_ReadHandle: handle is text 'calendar:9999999' naming no live object, "
        "expected a handle"
    )


# --- the two other kinds of index through the seam -----------------------------------------

# Serials for the two schedule pages' samples: 1 September, 30 September, 1 October, 31 October,
# 1 November and 30 November 2026 for the Gas Daily months; the last trading and publication
# days of the IFERC months, 30 September and 1 October, 30 October and 2 November, 30 November
# and 1 December 2026; and the valuation dates 25 September and 15 November 2026.
SEP_1, SEP_30, OCT_1, OCT_31, NOV_1, NOV_30 = 46266.0, 46295.0, 46296.0, 46326.0, 46327.0, 46356.0
OCT_30, NOV_2, DEC_1 = 46325.0, 46328.0, 46357.0
SEP_25, NOV_15 = 46290.0, 46341.0


def a_gas_daily_schedule() -> str:
    text = bridge.call(
        "_CreateGasDailySchedule",
        [column("U26", "V26", "X26"), column(SEP_1, OCT_1, NOV_1), column(SEP_30, OCT_31, NOV_30)],
    )
    assert isinstance(text, str) and text.startswith("gas_daily_schedule:"), text
    return text


def an_iferc_schedule() -> str:
    text = bridge.call(
        "_CreateIfercSchedule",
        [column("V26", "X26", "Z26"), column(SEP_30, OCT_30, NOV_30), column(OCT_1, NOV_2, DEC_1)],
    )
    assert isinstance(text, str) and text.startswith("iferc_schedule:"), text
    return text


def a_gas_daily_calendar() -> str:
    return a_calendar(a_valuation(SEP_25), an_index(a_gas_daily_schedule()))


def an_iferc_calendar() -> str:
    return a_calendar(a_valuation(NOV_15), an_index(an_iferc_schedule()))


def test_a_gas_daily_calendar_is_created_from_two_handles_and_read_back_day_by_day() -> None:
    shown = rows(read(a_gas_daily_calendar()))
    assert len(shown) == 93
    assert shown[0] == HEADERS and shown[1] == TYPES
    assert shown[2] == [SEP_1, "U26", 1.0, 1.0]
    assert shown[26] == [SEP_25, "U26", 1.0, 1.0]  # the valuation day, printed before it began
    assert shown[27] == [SEP_25 + 1, "U26", 1.0, 0.0]
    assert shown[31] == [SEP_30, "U26", 1.0, 0.0]
    assert shown[32] == [OCT_1, "V26", 1.0, 0.0]
    assert shown[92] == [NOV_30, "X26", 1.0, 0.0]
    assert [row[0] for row in shown[2:]] == [SEP_1 + i for i in range(91)]


def test_an_iferc_calendar_is_created_from_two_handles_and_read_back_month_by_month() -> None:
    assert rows(read(an_iferc_calendar())) == [
        HEADERS,
        TYPES,
        [OCT_1, "V26", 1.0, 1.0],
        [NOV_2, "X26", 1.0, 1.0],
        [DEC_1, "Z26", 1.0, 0.0],
    ]


def test_the_flags_of_the_two_other_kinds_reach_the_sheet_as_booleans() -> None:
    for made in (a_gas_daily_calendar(), an_iferc_calendar()):
        kinds, _, _ = read(made)
        assert (kinds[:2] == TEXT_CODE).all()
        assert (kinds[2:, 0] == NUMBER_CODE).all()
        assert (kinds[2:, 1] == TEXT_CODE).all()
        assert (kinds[2:, 2:] == BOOLEAN_CODE).all()


def test_a_gas_daily_gap_and_iferc_months_out_of_order_are_refused_in_the_librarys_words() -> None:
    gapped = bridge.call(
        "_CreateGasDailySchedule",
        [column("U26", "V26"), column(SEP_1, OCT_1 + 1), column(SEP_30, OCT_31)],
    )
    assert bridge.call("_CreateCalendar", [a_valuation(SEP_25), an_index(gapped)]) == (
        "#ERROR _CreateCalendar: ValueError: first_date row 2 is 2026-10-02, "
        "expected 2026-10-01, the day after row 1's last_date 2026-09-30"
    )
    backwards = bridge.call(
        "_CreateIfercSchedule",
        [column("X26", "V26"), column(OCT_30, SEP_30), column(NOV_2, OCT_1)],
    )
    assert bridge.call("_CreateCalendar", [a_valuation(NOV_15), an_index(backwards)]) == (
        "#ERROR _CreateCalendar: ValueError: publication_date row 2 is 2026-10-01, "
        "expected a date after row 1's 2026-11-02"
    )


def test_a_failed_construction_of_the_other_kinds_publishes_no_object_and_no_handle() -> None:
    valuation, index = a_valuation(SEP_25), an_index(a_gas_daily_schedule())
    gapped = an_index(
        bridge.call(
            "_CreateGasDailySchedule",
            [column("U26", "V26"), column(SEP_1, OCT_1 + 1), column(SEP_30, OCT_31)],
        )
    )
    before = number(a_calendar(valuation, index))
    assert cast(str, bridge.call("_CreateCalendar", [valuation, gapped])).startswith(
        "#ERROR _CreateCalendar: ValueError: first_date row 2 is 2026-10-02"
    )
    assert number(a_calendar(valuation, index)) == before + 1
