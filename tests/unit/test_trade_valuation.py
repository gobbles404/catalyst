"""The valuation path on the sheet: _PrepareTrades, _EvaluateTrades, _ReportValues and
_ReportRisk over the kernel, through the seam. The NG example and its toy lifecycle valued cell to
cell, the two reports' spills pinned, the handles' texts, the readers' spills of the dated
contents, a tick making new results over the same preparation while the old results stand, and
each refusal in the seam's order and then the library's. docs/library/trades/prepare-trades.md,
evaluate-trades.md, report-values.md and report-risk.md are the pages."""

import os
import re
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

ENTRY = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}
FIRST = np.datetime64("1899-12-30", "D")


def serial(text: str) -> float:
    return float((np.datetime64(text, "D") - FIRST).astype(np.int64))


def row(*cells: object) -> Cells:
    return Cells.from_rows([list(cells)])


def rows(*lines: list[Any]) -> Cells:
    return Cells.from_rows(list(lines))


def column(values: NDArray[Any] | list[float]) -> Cells:
    return Cells.from_rows([[float(v)] for v in values])


def spilled(result: object) -> list[list[object]]:
    kinds, slots, text = cast(tuple[NDArray[np.uint8], NDArray[np.float64], str], result)
    texts = iter(text.split("\0"))
    return [
        [
            next(texts) if kinds[r, c] == bridge.TEXT_CODE else slots[r, c]
            for c in range(kinds.shape[1])
        ]
        for r in range(kinds.shape[0])
    ]


NG_TEMPLATE = {
    "quantity_unit": "NYMEX NG",
    "quantity_per": "month",
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "physical",
    "clearing_house": "CME Clearing",
}
NG_HEADERS = ("trade_id", "trade_date", "contract_code", "quantity", "fixed_price")
NG_ROWS: list[list[object]] = [
    [1001.0, serial("2026-09-24"), "Z26", 10.0, 3.1],
    [1002.0, serial("2026-09-24"), "z26", -4.0, 3.15],
    [1003.0, serial("2026-09-25"), "F27", 7.0, 3.4],
    [1004.0, serial("2026-09-25"), "F27", -12.0, 3.35],
    [1001.0, serial("2026-09-24"), "Z26", 10.0, 3.1],
]


def an_index(
    name: str,
    contracts: list[tuple[str, str]],
    holidays: list[str],
    lots: list[tuple[str, float]],
    measure: tuple[str, str] = ("ENERGY", "MMBTU"),
    quoted_in: str = "USD",
    reporting_lot: str | None = "",
) -> tuple[str, str]:
    """An index of those contracts and holidays through the seam, quoted in that currency unit per
    the measure's unit and settled in USD, with one specification per name given, that many of the
    measure's unit a lot, in the order given, the first of them the reporting lot unless another
    name is given and None leaving the index without one, and its holiday calendar."""
    schedule = ENTRY["_CreateFuturesSchedule"](
        rows(*[[code] for code, _ in contracts]),
        column([serial(expiry) for _, expiry in contracts]),
        bridge.MISSING,
    )
    calendar = ENTRY["_CreateHolidayCalendar"](column([serial(day) for day in holidays]))
    conventions = ENTRY["_CreateIndexConventions"](
        quoted_in, measure[1], "USD", measure[0], measure[1]
    )
    specifications = ENTRY["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        rows(*[[name, size, measure[1], 0.0, 0.0] for name, size in lots]),
    )
    lot = lots[0][0] if reporting_lot == "" else reporting_lot
    made = ENTRY["_CreateIndex"](
        name,
        f"{name} index",
        schedule,
        conventions,
        specifications,
        calendar,
        bridge.MISSING if lot is None else lot,
    )
    return str(made), str(calendar)


def a_history(
    index: str, first: str, as_of: str, holidays: list[str], settles: dict[str, float]
) -> str:
    """The index's history valued on that day: 3.00 on every business day from the calendar's first
    day to the day before, the settles given standing on their days, newest first as the fixings
    creator takes them."""
    days = np.arange(np.datetime64(first, "D"), np.datetime64(as_of, "D"))
    days = days[np.is_busday(days, holidays=np.array(holidays, dtype="datetime64[D]"))]
    prices = np.full(days.size, 3.0)
    for text, price in settles.items():
        prices[days == np.datetime64(text, "D")] = price
    fixings = ENTRY["_CreateFuturesFixings"](
        column([serial(str(d)) for d in days[::-1]]), column(prices[::-1]), index
    )
    calendar = ENTRY["_CreateCalendar"](ENTRY["_CreateValuationDate"](serial(as_of), 0.5), index)
    return str(ENTRY["_CreateMarketHistory"](calendar, fixings))


def a_market(history: str, name: str, *quotes: float) -> str:
    return str(
        ENTRY["_CreateMarket"](history, ENTRY["_CreatePriceVector"](name, column(list(quotes))))
    )


@pytest.fixture(scope="module")
def ng() -> dict[str, Any]:
    """The NG example on the sheet: the index, the template, the five rows as a batch, the
    history valued on 24 November 2026 with a settle of 3.00 on every fixed day, and the market
    quoting Z26 at 3.20 and F27 at 3.50."""
    holidays = ["2026-11-26", "2026-12-25"]
    index, _ = an_index(
        "Henry Hub NYMEX",
        [("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29")],
        holidays,
        [("NYMEX NG", 10_000.0)],
    )
    template = ENTRY["_CreateTradeTemplate"](
        "future", row(*NG_TEMPLATE), row(*NG_TEMPLATE.values())
    )
    trades = ENTRY["_CreateTrades"](index, row(*NG_HEADERS), rows(*NG_ROWS), template)
    history = a_history(index, "2026-10-29", "2026-11-24", holidays, {})
    market = a_market(history, "Henry Hub NYMEX", 3.20, 3.50)
    prepared = ENTRY["_PrepareTrades"](trades, history)
    results = ENTRY["_EvaluateTrades"](prepared, market)
    return {
        "index": index,
        "template": template,
        "trades": trades,
        "history": history,
        "market": market,
        "prepared": prepared,
        "results": results,
    }


# --- the NG example valued cell to cell -----------------------------------------------------


def test_the_handles_are_named_for_the_index(ng: dict[str, Any]) -> None:
    pid = os.getpid()
    assert re.fullmatch(rf"{pid}:prepared_trades:Henry Hub NYMEX:\d+", str(ng["prepared"]))
    assert re.fullmatch(rf"{pid}:trade_results:Henry Hub NYMEX:\d+", str(ng["results"]))


def test_the_values_report_spills_the_mark_and_the_cash_under_the_routes_labels(
    ng: dict[str, Any],
) -> None:
    assert spilled(ENTRY["_ReportValues"](ng["results"])) == [
        ["cleared_mark", "cleared_cash", "currency", "as_of"],
        ["float64", "float64", "str", "datetime64[D]"],
        [7_000.0, 0.0, "USD", serial("2026-11-24")],
    ]


def test_the_risk_report_spills_the_total_delta_and_the_dv01_with_their_units(
    ng: dict[str, Any],
) -> None:
    assert spilled(ENTRY["_ReportRisk"](ng["results"])) == [
        ["delta_total", "delta_unit", "dv01", "dv01_unit", "as_of"],
        ["float64", "str", "float64", "str", "datetime64[D]"],
        [11.0, "lots of NYMEX NG (10000 MMBTU)", 0.0, "USD per basis point", serial("2026-11-24")],
    ]


def test_the_readers_spill_the_dated_contents_one_row_per_slot(ng: dict[str, Any]) -> None:
    assert spilled(ENTRY["util_ReadHandle"](ng["prepared"])) == [
        [
            "pricing_contract",
            "booked_contract",
            "observation_date",
            "is_fixed",
            "is_settled",
            "live_coefficient",
            "live_lots",
        ],
        ["str", "str", "datetime64[D]", "bool", "bool", "float64", "float64"],
        ["Z26", "Z26", serial("2026-11-25"), False, False, 160_000.0, 16.0],
        ["F27", "F27", serial("2026-12-29"), False, False, -50_000.0, -5.0],
    ]
    table = spilled(ENTRY["util_ReadHandle"](ng["results"]))
    assert table[:2] == [
        [
            "pricing_contract",
            "booked_contract",
            "observation_date",
            "is_fixed",
            "live_coefficient",
            "live_lots",
            "live_contribution",
            "contract_sensitivity",
            "contract_lot_delta",
            "sensitivity_unit",
            "lot_unit",
            "brokerage_reserve",
            "clearing_reserve",
            "marketing_reserve",
            "currency",
        ],
        ["str", "str", "datetime64[D]", "bool"]
        + ["float64"] * 5
        + ["str", "str"]
        + ["float64"] * 3
        + ["str"],
    ]
    assert table[2][:6] == ["Z26", "Z26", serial("2026-11-25"), False, 160_000.0, 16.0]
    assert table[2][6:9] == [pytest.approx(512_000.0), 160_000.0, 16.0]
    assert table[2][9:] == [
        "USD per USD/MMBTU",
        "lots of NYMEX NG (10000 MMBTU)",
        0.0,
        0.0,
        0.0,
        "USD",
    ]  # the units, on every row, and the batch's reserves once, none at these rates
    assert table[3][9:] == ["USD per USD/MMBTU", "lots of NYMEX NG (10000 MMBTU)"] + ["-"] * 4
    assert table[3][4:6] == [160_000.0 * -5 / 16, -5.0]
    assert table[3][6:9] == [pytest.approx(-175_000.0), -50_000.0, -5.0]


def test_a_tick_makes_new_results_over_the_same_preparation_and_the_old_stand(
    ng: dict[str, Any],
) -> None:
    ticked = a_market(ng["history"], "Henry Hub NYMEX", 3.21, 3.50)
    later = ENTRY["_EvaluateTrades"](ng["prepared"], ticked)
    assert later != ng["results"]
    assert spilled(ENTRY["_ReportValues"](later))[2][0] == pytest.approx(8_600.0)
    assert spilled(ENTRY["_ReportValues"](ng["results"]))[2][0] == 7_000.0  # unmoved
    assert spilled(ENTRY["_ReportRisk"](later))[2][0] == 11.0  # lots; no tick changes it


def test_one_trade_takes_the_same_path_as_five(ng: dict[str, Any]) -> None:
    one = ENTRY["_CreateTrades"](ng["index"], row(*NG_HEADERS), rows(NG_ROWS[3]), ng["template"])
    prepared = ENTRY["_PrepareTrades"](one, ng["history"])
    results = ENTRY["_EvaluateTrades"](prepared, ng["market"])
    values = spilled(ENTRY["_ReportValues"](results))
    assert values[2][:2] == [pytest.approx(-18_000.0), 0.0]
    assert spilled(ENTRY["_ReportRisk"](results))[2][0] == -12.0  # twelve lots sold


# --- the toy lifecycle on the sheet: the seven states of the example page ---------------------

TOY_HOLIDAYS = ["2026-11-26", "2026-12-25", "2027-01-01"]


@pytest.fixture(scope="module")
def toy() -> dict[str, Any]:
    """The toy of the example page on the sheet: TOY_GAS with G27 after F27, the payment calendar
    closed on 26 November, 25 December and New Year's Day, the financial template paying two
    business days after each expiry, and the five NG rows as a batch."""
    index, calendar = an_index(
        "TOY_GAS",
        [
            ("X26", "2026-10-28"),
            ("Z26", "2026-11-25"),
            ("F27", "2026-12-29"),
            ("G27", "2027-01-27"),
        ],
        TOY_HOLIDAYS,
        [("TOY", 10_000.0)],
    )
    fields = {
        **NG_TEMPLATE,
        "quantity_unit": "TOY",
        "settlement_method": "financial",
        "clearing_house": "TEST_CLEARER",
        "payment_time_lag": "+2bd",
        "payment_holiday_calendar": calendar,
    }
    template = ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*fields.values()))
    trades = ENTRY["_CreateTrades"](index, row(*NG_HEADERS), rows(*NG_ROWS), template)
    return {"index": index, "template": template, "trades": trades}


def toy_state(
    toy: dict[str, Any], as_of: str, settles: dict[str, float], quotes: tuple[float, ...]
) -> tuple[str, str]:
    """One state of the lifecycle: the history valued on that day with those settles standing on
    their days, the market quoting from the prompt on, the batch prepared and evaluated; the
    prepared and the results handles."""
    history = a_history(toy["index"], "2026-10-29", as_of, TOY_HOLIDAYS, settles)
    market = a_market(history, "TOY_GAS", *quotes)
    prepared = ENTRY["_PrepareTrades"](toy["trades"], history)
    return str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


def valued(results: str) -> tuple[float, float, float]:
    """The mark, the cash and the total delta a results handle reports."""
    values = spilled(ENTRY["_ReportValues"](results))[2]
    risk = spilled(ENTRY["_ReportRisk"](results))[2]
    return cast(float, values[0]), cast(float, values[1]), cast(float, risk[0])


Z26_FIRST = {"2026-11-25": 3.22}
Z26 = {"2026-11-25": 3.23}
BOTH = {"2026-11-25": 3.23, "2026-12-29": 3.45}
TOY_UNITS = ["USD per USD/MMBTU", "lots of TOY (10000 MMBTU)"]  # on every results row


# The page's seven states, with its total P&L column typed from the page beside the mark and
# the cash, and an eighth day between two of them: Friday 27 November, Z26 fixed and not yet
# paid, since the payment calendar closes the 26th and two business days from the 25th land on
# Monday the 30th. A payment counted on an open calendar would fall on the 27th and turn the
# day's 11,800 of mark into cash.
@pytest.mark.parametrize(
    ("as_of", "settles", "quotes", "mark", "cash", "delta", "total"),
    [
        ("2026-11-24", {}, (3.20, 3.50, 3.60), 7_000, 0, 11, 7_000),
        ("2026-11-24", {}, (3.21, 3.50, 3.60), 8_600, 0, 11, 8_600),
        ("2026-11-26", Z26_FIRST, (3.50, 3.60), 10_200, 0, -5, 10_200),
        ("2026-11-26", Z26, (3.50, 3.60), 11_800, 0, -5, 11_800),
        ("2026-11-27", Z26, (3.50, 3.60), 11_800, 0, -5, 11_800),
        ("2026-11-30", Z26, (3.50, 3.60), -11_000, 22_800, -5, 11_800),
        ("2026-12-30", BOTH, (3.60,), -8_500, 22_800, 0, 14_300),
        ("2026-12-31", BOTH, (3.60,), 0, 14_300, 0, 14_300),
    ],
    ids=[
        "24 Nov, initial",
        "24 Nov, a tick",
        "26 Nov, Z26 fixed at 3.22",
        "26 Nov, corrected to 3.23",
        "27 Nov, Z26 fixed and unpaid, the 26th closed",
        "30 Nov, Z26 paid",
        "30 Dec, both fixed, F27 unpaid",
        "31 Dec, both paid",
    ],
)
def test_the_toys_states_value_on_the_sheet_as_the_page_says(
    toy: dict[str, Any],
    as_of: str,
    settles: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
    total: float,
) -> None:
    _, results = toy_state(toy, as_of, settles, quotes)
    got = valued(results)
    assert got[0] == pytest.approx(mark) and got[1] == pytest.approx(cash)
    assert got[2] == pytest.approx(delta)
    assert got[0] + got[1] == pytest.approx(total)  # the page's total P&L column, as typed
    assert spilled(ENTRY["_ReportValues"](results))[2][3] == serial(as_of)


def test_the_tick_reuses_the_initial_states_preparation(toy: dict[str, Any]) -> None:
    history = a_history(toy["index"], "2026-10-29", "2026-11-24", TOY_HOLIDAYS, {})
    prepared = ENTRY["_PrepareTrades"](toy["trades"], history)
    initial = ENTRY["_EvaluateTrades"](prepared, a_market(history, "TOY_GAS", 3.20, 3.50, 3.60))
    ticked = ENTRY["_EvaluateTrades"](prepared, a_market(history, "TOY_GAS", 3.21, 3.50, 3.60))
    assert valued(str(initial))[0] == pytest.approx(7_000)
    assert valued(str(ticked))[0] == pytest.approx(8_600)
    assert valued(str(initial))[0] == pytest.approx(7_000)  # the old results stand


def test_a_market_over_a_corrected_history_of_the_same_day_is_refused_until_prepared_again(
    toy: dict[str, Any],
) -> None:
    # The same index and the same valuation day, Z26's final corrected from 3.22 to 3.23: the
    # market over the corrected history is another history's, refused by object and never by
    # name or day, and preparing again against it gives the page's 11,800.
    first = a_history(toy["index"], "2026-10-29", "2026-11-26", TOY_HOLIDAYS, Z26_FIRST)
    corrected = a_history(toy["index"], "2026-10-29", "2026-11-26", TOY_HOLIDAYS, Z26)
    prepared = ENTRY["_PrepareTrades"](toy["trades"], first)
    on_first = ENTRY["_EvaluateTrades"](prepared, a_market(first, "TOY_GAS", 3.50, 3.60))
    assert valued(str(on_first))[0] == pytest.approx(10_200)
    assert ENTRY["_EvaluateTrades"](prepared, a_market(corrected, "TOY_GAS", 3.50, 3.60)) == (
        "#ERROR _EvaluateTrades: ValueError: market is over another history of index 'TOY_GAS', "
        "expected the one the trades were prepared against"
    )
    again = ENTRY["_PrepareTrades"](toy["trades"], corrected)
    on_corrected = ENTRY["_EvaluateTrades"](again, a_market(corrected, "TOY_GAS", 3.50, 3.60))
    assert valued(str(on_corrected))[0] == pytest.approx(11_800)


def test_the_paid_contract_reads_back_fixed_and_settled_with_no_live_exposure(
    toy: dict[str, Any],
) -> None:
    prepared, results = toy_state(toy, "2026-11-30", Z26, (3.50, 3.60))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    z26 = ["Z26", "Z26", serial("2026-11-25"), serial("2026-11-30")]  # priced and booked alike
    assert slots[2] == [*z26, True, True, 0.0, 0.0]
    assert slots[3] == [
        "F27",
        "F27",
        serial("2026-12-29"),
        serial("2026-12-31"),
        False,
        False,
        -50_000.0,
        -5.0,
    ]
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[2] == [*z26, True, *([0.0] * 5), *TOY_UNITS, 0.0, 0.0, 0.0, "USD"]
    assert table[3][-4:] == ["-"] * 4
    assert table[3][:7] == [
        "F27",
        "F27",
        serial("2026-12-29"),
        serial("2026-12-31"),
        False,
        -50_000.0,
        -5.0,
    ]
    assert table[3][7:10] == [pytest.approx(-175_000.0), -50_000.0, -5.0]


def test_a_fully_fixed_batch_inside_a_live_market_reports_its_cash_and_no_live_exposure(
    toy: dict[str, Any],
) -> None:
    prepared, results = toy_state(toy, "2026-12-31", BOTH, (3.60,))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert [line[4:8] for line in slots[2:]] == [[True, True, 0.0, 0.0], [True, True, 0.0, 0.0]]
    assert spilled(ENTRY["util_ReadHandle"](results))[2:] == [
        ["Z26", "Z26", serial("2026-11-25"), serial("2026-11-30"), True]
        + [0.0] * 5
        + TOY_UNITS
        + [0.0, 0.0, 0.0, "USD"],
        ["F27", "F27", serial("2026-12-29"), serial("2026-12-31"), True]
        + [0.0] * 5
        + TOY_UNITS
        + ["-"] * 4,
    ]
    assert valued(results) == (pytest.approx(0.0), pytest.approx(14_300), 0.0)


def test_a_lag_past_the_sheets_calendar_fails_the_template_or_the_batch_in_the_librarys_words(
    toy: dict[str, Any],
) -> None:
    # The grammar's bound is the template's to refuse, the day the batch's: a lag of three million
    # business days reads as a lag, and the batch it would make pays Z26 in the year 10076, which
    # no cell could show, so nothing is published and nothing unnamed reaches the sheet.
    fields = {
        **NG_TEMPLATE,
        "quantity_unit": "TOY",
        "settlement_method": "financial",
        "clearing_house": "TEST_CLEARER",
        "payment_holiday_calendar": ENTRY["_CreateHolidayCalendar"](column([serial("2026-01-01")])),
    }
    beyond = {**fields, "payment_time_lag": "+99999999999999999999bd"}
    assert ENTRY["_CreateTradeTemplate"]("future", row(*beyond), row(*beyond.values())) == (
        "#ERROR _CreateTradeTemplate: ValueError: payment_time_lag is "
        "'+99999999999999999999bd', expected at most 2,113,146 business days, the sheet's "
        "calendar from 1900-03-01 to 9999-12-31 end to end"
    )
    far = {**fields, "payment_time_lag": "+2100000bd"}
    template = ENTRY["_CreateTradeTemplate"]("future", row(*far), row(*far.values()))
    assert ":trade_template:" in str(template)  # a lag the template cannot yet see past
    assert ENTRY["_CreateTrades"](toy["index"], row(*NG_HEADERS), rows(*NG_ROWS), template) == (
        "#ERROR _CreateTrades: ValueError: payment_time_lag is '+2100000bd', counted from "
        "2026-11-25 to 10076-05-06, expected a payment day on or before 9999-12-31, the last a "
        "sheet can show"
    )
    long_lag = {**fields, "payment_time_lag": "+" + "9" * 4301 + "bd"}
    shown = str(ENTRY["_CreateTradeTemplate"]("future", row(*long_lag), row(*long_lag.values())))
    assert shown.startswith("#ERROR _CreateTradeTemplate: ValueError: payment_time_lag is '+9999")
    assert shown.endswith("the sheet's calendar from 1900-03-01 to 9999-12-31 end to end")


def test_a_missing_final_price_fails_the_history_before_any_trade_is_prepared(
    toy: dict[str, Any],
) -> None:
    # The settle on Z26's expiry day is a fixing like any other: a series that skips it is a
    # series like any other to the fixings creator, and the history valued after that day refuses
    # it, so no forecast ever stands in for a final price.
    days = np.arange(np.datetime64("2026-10-29", "D"), np.datetime64("2026-11-26", "D"))
    days = days[np.is_busday(days, holidays=np.array(TOY_HOLIDAYS, dtype="datetime64[D]"))]
    without = days[days != np.datetime64("2026-11-25", "D")]
    fixings = ENTRY["_CreateFuturesFixings"](
        column([serial(str(d)) for d in without[::-1]]), column([3.0] * without.size), toy["index"]
    )
    calendar = ENTRY["_CreateCalendar"](
        ENTRY["_CreateValuationDate"](serial("2026-11-26"), 0.5), toy["index"]
    )
    assert ENTRY["_CreateMarketHistory"](calendar, fixings) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 2026-11-25, "
        "expected a fixing for every fixed day in calendar"
    )


# --- the penultimate futures on the sheet: ICE PHH and ICE WTI T ------------------------------
# penultimate-trades.md's example: the NG index of 2027, M27 before and Q27 after N27, the pricing
# calendar closing Memorial Day and the observed Independence Day, the ICE lot of 2,500 MMBTU one
# of its specifications; the pen template, cleared through ICE Clear Europe, paying one business
# day after the pen day on a clearing calendar; two long lots of N27 at 3.00.

PHH_HOLIDAYS = ["2027-05-31", "2027-07-05"]
PEN_FIELDS = (
    "quantity_unit",
    "quantity_per",
    "schedule_method",
    "route",
    "settlement_method",
    "clearing_house",
    "payment_time_lag",
    "payment_holiday_calendar",
)


def pen_template(specification: str, clearing: str) -> str:
    return str(
        ENTRY["_CreateTradeTemplate"](
            "future",
            row(*PEN_FIELDS),
            row(
                specification,
                "month",
                "penultimate",
                "cleared",
                "financial",
                "ICE Clear Europe",
                "+1bd",
                clearing,
            ),
        )
    )


@pytest.fixture(scope="module")
def phh() -> dict[str, Any]:
    index, _ = an_index(
        "Henry Hub NYMEX",
        [("M27", "2027-05-26"), ("N27", "2027-06-28"), ("Q27", "2027-07-28")],
        PHH_HOLIDAYS,
        [("NYMEX NG", 10_000.0), ("ICE PHH", 2_500.0)],
        reporting_lot="ICE PHH",
    )
    clearing = ENTRY["_CreateHolidayCalendar"](column([serial("2027-05-31"), serial("2027-08-30")]))
    template = pen_template("ICE PHH", str(clearing))
    headers = row(*NG_HEADERS)
    long = [1.0, serial("2027-06-01"), "N27", 2.0, 3.0]
    short = [2.0, serial("2027-06-01"), "n27", -2.0, 3.0]
    return {
        "index": index,
        "template": template,
        "headers": headers,
        "long": long,
        "short": short,
        "trades": ENTRY["_CreateTrades"](index, headers, rows(long), template),
    }


def phh_state(
    phh: dict[str, Any], as_of: str, settles: dict[str, float], quotes: tuple[float, ...]
) -> tuple[str, str, str]:
    """One state of the pen's life: the history valued that day with those settles on their
    days, the market quoting from the prompt on, the batch prepared and evaluated; the history,
    the prepared and the results handles."""
    history = a_history(phh["index"], "2027-05-27", as_of, PHH_HOLIDAYS, settles)
    market = a_market(history, "Henry Hub NYMEX", *quotes)
    prepared = ENTRY["_PrepareTrades"](phh["trades"], history)
    return history, str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


PEN_FIXED = {"2027-06-25": 3.20}
PEN_CORRECTED = {"2027-06-25": 3.21}


@pytest.mark.parametrize(
    ("as_of", "settles", "quotes", "mark", "cash", "delta"),
    [
        ("2027-06-25", {}, (3.10, 3.15), 500, 0, 2),
        ("2027-06-26", PEN_FIXED, (3.10, 3.15), 1_000, 0, 0),
        ("2027-06-28", PEN_FIXED, (3.10, 3.15), 0, 1_000, 0),
    ],
    ids=["25 Jun, live on the pen day", "26 Jun, fixed, unpaid", "28 Jun, paid"],
)
def test_the_phh_pen_values_on_the_sheet_as_the_page_says(
    phh: dict[str, Any],
    as_of: str,
    settles: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
) -> None:
    _, _, results = phh_state(phh, as_of, settles, quotes)
    assert valued(results) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(delta))
    values = spilled(ENTRY["_ReportValues"](results))[2]
    assert values[2:] == ["USD", serial(as_of)]
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "lots of ICE PHH (2500 MMBTU)"


def test_the_pens_dates_read_back_from_the_batch_and_the_preparation(phh: dict[str, Any]) -> None:
    batch = spilled(ENTRY["util_ReadHandle"](phh["trades"]))
    assert batch[0][batch[0].index("payment_date")] == "payment_date"
    assert batch[2][batch[0].index("payment_time_lag")] == "+1bd"
    assert batch[2][batch[0].index("payment_date")] == serial("2027-06-28")
    assert batch[2][batch[0].index("contract_code")] == "N27"
    assert batch[2][batch[0].index("quote_quantity")] == 5_000.0
    _, prepared, _ = phh_state(phh, "2027-06-25", {}, (3.10, 3.15))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert slots[2] == [
        "N27",
        "N27",
        serial("2027-06-25"),
        serial("2027-06-28"),
        False,
        False,
        5_000.0,
        2.0,
    ]


def test_a_tick_moves_the_live_pen_on_the_same_preparation(phh: dict[str, Any]) -> None:
    history, prepared, results = phh_state(phh, "2027-06-25", {}, (3.10, 3.15))
    ticked = ENTRY["_EvaluateTrades"](prepared, a_market(history, "Henry Hub NYMEX", 3.11, 3.15))
    assert valued(str(ticked))[0] == pytest.approx(550)
    assert valued(results)[0] == pytest.approx(500)


def test_a_corrected_pen_fixing_takes_a_new_history_and_the_underlyings_final_changes_nothing(
    phh: dict[str, Any],
) -> None:
    _, _, corrected = phh_state(phh, "2027-06-26", PEN_CORRECTED, (3.10, 3.15))
    assert valued(corrected) == (pytest.approx(1_050), 0.0, 0.0)
    # On 29 June the pen has paid and N27 has expired; its settle of the 28th stands in the
    # history, at 3.25 or at 3.35, and the pen's amount is the 25th's either way.
    for final in (3.25, 3.35):
        _, _, paid = phh_state(phh, "2027-06-29", {**PEN_CORRECTED, "2027-06-28": final}, (3.15,))
        assert valued(paid) == (0.0, pytest.approx(1_050), 0.0)


def test_a_fixed_pen_inside_a_live_market_is_unmoved_by_the_underlyings_quote(
    phh: dict[str, Any],
) -> None:
    _, prepared, quiet = phh_state(phh, "2027-06-26", PEN_FIXED, (3.10, 3.15))
    _, _, loud = phh_state(phh, "2027-06-26", PEN_FIXED, (3.50, 3.55))
    assert valued(quiet) == valued(loud) == (pytest.approx(1_000), 0.0, 0.0)
    assert spilled(ENTRY["util_ReadHandle"](prepared))[2] == [
        "N27",
        "N27",
        serial("2027-06-25"),
        serial("2027-06-28"),
        True,
        False,
        0.0,
        0.0,
    ]


def test_the_short_pen_and_the_long_sum_to_nothing_and_each_equals_itself_alone(
    phh: dict[str, Any],
) -> None:
    both = ENTRY["_CreateTrades"](
        phh["index"], phh["headers"], rows(phh["long"], phh["short"]), phh["template"]
    )
    reversed_rows = ENTRY["_CreateTrades"](
        phh["index"], phh["headers"], rows(phh["short"], phh["long"]), phh["template"]
    )
    short = ENTRY["_CreateTrades"](
        phh["index"], phh["headers"], rows(phh["short"]), phh["template"]
    )
    history = a_history(phh["index"], "2027-05-27", "2027-06-28", PHH_HOLIDAYS, PEN_FIXED)
    market = a_market(history, "Henry Hub NYMEX", 3.10, 3.15)

    def cash_of(batch: object) -> float:
        results = ENTRY["_EvaluateTrades"](ENTRY["_PrepareTrades"](batch, history), market)
        return valued(str(results))[1]

    assert cash_of(short) == pytest.approx(-1_000)
    assert cash_of(both) == pytest.approx(0.0) == cash_of(reversed_rows)
    assert cash_of(phh["trades"]) + cash_of(short) == pytest.approx(cash_of(both))


# R1's strip batch on the sheet, the kernel's hand answers reached through the entries: A, two lots
# of the N27-Q27 strip at 3.00, A again, and C, one lot of q27 sold at 3.05, on the PHH index with
# U27 after Q27 so that every state has a market.
STRIP_ROWS: list[list[object]] = [
    [1.0, serial("2027-06-01"), "N27-Q27", 2.0, 3.0],
    [1.0, serial("2027-06-01"), "N27-Q27", 2.0, 3.0],
    [3.0, serial("2027-06-01"), "q27", -1.0, 3.05],
]
STRIP_LIFECYCLE: list[
    tuple[str, dict[str, float], tuple[float, ...], int, int, tuple[int, int]]
] = [
    ("2027-06-24", {}, (3.10, 3.40), 4_125, 0, (4, 3)),
    ("2027-06-25", {}, (3.10, 3.40), 4_125, 0, (4, 3)),
    ("2027-06-26", PEN_FIXED, (3.10, 3.40), 5_125, 0, (0, 3)),
    ("2027-06-28", PEN_FIXED, (3.10, 3.40), 3_125, 2_000, (0, 3)),
    ("2027-07-27", PEN_FIXED, (3.40,), 3_125, 2_000, (0, 3)),
    ("2027-07-28", {**PEN_FIXED, "2027-07-27": 3.45}, (3.50,), 0, 5_500, (0, 0)),
]
STRIP_IDS = [
    "24 Jun, both live",
    "25 Jun, N27 live on its pen day",
    "26 Jun, N27 fixed, unpaid",
    "28 Jun, N27 paid",
    "27 Jul, Q27 live on its pen day",
    "28 Jul, both paid",
]


@pytest.fixture(scope="module")
def strip() -> dict[str, Any]:
    index, _ = an_index(
        "Henry Hub NYMEX",
        [
            ("M27", "2027-05-26"),
            ("N27", "2027-06-28"),
            ("Q27", "2027-07-28"),
            ("U27", "2027-08-27"),
        ],
        PHH_HOLIDAYS,
        [("NYMEX NG", 10_000.0), ("ICE PHH", 2_500.0)],
        reporting_lot="ICE PHH",
    )
    clearing = ENTRY["_CreateHolidayCalendar"](column([serial("2027-05-31"), serial("2027-08-30")]))
    template = pen_template("ICE PHH", str(clearing))
    return {
        "index": index,
        "template": template,
        "trades": strip_batch(index, template, STRIP_ROWS),
    }


def strip_batch(index: str, template: str, lines: list[list[object]]) -> str:
    return str(ENTRY["_CreateTrades"](index, row(*NG_HEADERS), rows(*lines), template))


def strip_state(
    strip: dict[str, Any],
    trades: str,
    as_of: str,
    settles: dict[str, float],
    quotes: tuple[float, ...],
) -> str:
    history = a_history(strip["index"], "2027-05-27", as_of, PHH_HOLIDAYS, settles)
    market = a_market(history, "Henry Hub NYMEX", *quotes)
    return str(ENTRY["_EvaluateTrades"](ENTRY["_PrepareTrades"](trades, history), market))


@pytest.mark.parametrize(
    ("as_of", "settles", "quotes", "mark", "cash", "delta"), STRIP_LIFECYCLE, ids=STRIP_IDS
)
def test_the_pen_strip_batch_values_on_the_sheet_as_the_hand_says(
    strip: dict[str, Any],
    as_of: str,
    settles: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: tuple[float, float],
) -> None:
    results = strip_state(strip, strip["trades"], as_of, settles, quotes)
    assert valued(results) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(sum(delta)))
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert [(line[0], line[9]) for line in table[2:]] == [("N27", delta[0]), ("Q27", delta[1])]
    turned = strip_batch(strip["index"], strip["template"], STRIP_ROWS[::-1])
    assert valued(strip_state(strip, turned, as_of, settles, quotes)) == (
        pytest.approx(mark),
        pytest.approx(cash),
        pytest.approx(sum(delta)),
    )
    singles = [
        valued(
            strip_state(
                strip,
                strip_batch(strip["index"], strip["template"], [line]),
                as_of,
                settles,
                quotes,
            )
        )
        for line in STRIP_ROWS
    ]
    assert sum(single[0] for single in singles) == pytest.approx(mark)
    assert sum(single[1] for single in singles) == pytest.approx(cash)


def test_the_pen_strips_days_and_amounts_read_back_from_the_batch(strip: dict[str, Any]) -> None:
    batch = spilled(ENTRY["util_ReadHandle"](strip["trades"]))
    head = batch[0]
    assert [line[head.index("row")] for line in batch[2:]] == [1.0, 1.0, 2.0, 2.0, 3.0]
    assert [line[head.index("quote_quantity")] for line in batch[2:]] == [
        5_000.0, 5_000.0, 5_000.0, 5_000.0, -2_500.0
    ]  # fmt: skip
    assert [line[head.index("payment_date")] for line in batch[2:]] == [
        serial("2027-06-28"), serial("2027-07-28"), serial("2027-06-28"), serial("2027-07-28"),
        serial("2027-07-28"),
    ]  # fmt: skip


def test_a_series_without_the_pen_days_settle_is_refused_before_any_trade_is_prepared(
    phh: dict[str, Any],
) -> None:
    # The settle of the 25th is a fixing like any other. A series that skips it but holds the
    # underlying's final settle of the 28th is refused by the fixings creator for the gap; a
    # series that stops the day before is refused by the history valued after the 25th. Either
    # way no trade is prepared, and the final settle never stands in for the pen fixing.
    days = np.arange(np.datetime64("2027-05-27", "D"), np.datetime64("2027-06-29", "D"))
    days = days[np.is_busday(days, holidays=np.array(PHH_HOLIDAYS, dtype="datetime64[D]"))]
    gap = days[days != np.datetime64("2027-06-25", "D")]
    assert ENTRY["_CreateFuturesFixings"](
        column([serial(str(d)) for d in gap[::-1]]), column([3.0] * gap.size), phh["index"]
    ) == (
        "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2027-06-24, expected "
        "2027-06-25, the business day before row 1's 2027-06-28"
    )
    short = days[days < np.datetime64("2027-06-25", "D")]
    fixings = ENTRY["_CreateFuturesFixings"](
        column([serial(str(d)) for d in short[::-1]]), column([3.0] * short.size), phh["index"]
    )
    calendar = ENTRY["_CreateCalendar"](
        ENTRY["_CreateValuationDate"](serial("2027-06-29"), 0.5), phh["index"]
    )
    assert ENTRY["_CreateMarketHistory"](calendar, fixings) == (
        "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 2027-06-25, "
        "expected a fixing for every fixed day in calendar"
    )


def test_a_physical_pen_is_refused_when_the_batch_is_made(phh: dict[str, Any]) -> None:
    fields = tuple(name for name in PEN_FIELDS if not name.startswith("payment_"))
    physical = ENTRY["_CreateTradeTemplate"](
        "future",
        row(*fields),
        row("ICE PHH", "month", "penultimate", "cleared", "physical", "ICE Clear Europe"),
    )
    assert ENTRY["_CreateTrades"](phh["index"], phh["headers"], rows(phh["long"]), physical) == (
        "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' "
        "with the penultimate method of trade 1 at row 1; a penultimate future is cash "
        "settled on the business day before its contract's expiry"
    )


def test_the_wti_pen_values_its_thousand_barrel_lots_in_dollars_a_barrel() -> None:
    # ICE WTI T F27 on a CL index in barrels: the pen day Friday 18 December 2026, the payment
    # Monday the 21st, the underlying's expiry. Three lots at 60.00: live on 17 December at 61.00,
    # 3,000 of mark and a delta of 3,000 USD per USD/BBL; paid on the 21st at a pen fixing of
    # 61.50, 4,500 of cash.
    holidays = ["2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18"]
    index, _ = an_index(
        "WTI NYMEX",
        [("Z26", "2026-11-20"), ("F27", "2026-12-21"), ("G27", "2027-01-20")],
        holidays,
        [("NYMEX CL", 1_000.0), ("ICE WTI T", 1_000.0)],
        ("VOLUME", "BBL"),
    )
    clearing = ENTRY["_CreateHolidayCalendar"](column([serial("2026-12-25"), serial("2026-12-28")]))
    template = pen_template("ICE WTI T", str(clearing))
    trades = ENTRY["_CreateTrades"](
        index, row(*NG_HEADERS), rows([1.0, serial("2026-12-01"), "F27", 3.0, 60.0]), template
    )
    batch = spilled(ENTRY["util_ReadHandle"](trades))
    assert batch[2][batch[0].index("payment_date")] == serial("2026-12-21")
    assert batch[2][batch[0].index("quote_quantity")] == 3_000.0
    live = a_history(index, "2026-11-23", "2026-12-17", holidays, {})
    results = ENTRY["_EvaluateTrades"](
        ENTRY["_PrepareTrades"](trades, live), a_market(live, "WTI NYMEX", 61.0, 61.5)
    )
    assert valued(str(results)) == (pytest.approx(3_000), 0.0, pytest.approx(3))
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "lots of NYMEX CL (1000 BBL)"
    paid = a_history(index, "2026-11-23", "2026-12-21", holidays, {"2026-12-18": 61.5})
    results = ENTRY["_EvaluateTrades"](
        ENTRY["_PrepareTrades"](trades, paid), a_market(paid, "WTI NYMEX", 61.0, 61.5)
    )
    assert valued(str(results)) == (0.0, pytest.approx(4_500), 0.0)


# --- the quantity unit on the sheet ---------------------------------------------------------------
# quantity-unit-selection.md through the entries: the PHH fixture above already selects the second
# of the NG index's two specifications; here two selections of one quantity value alike, the name
# reads back under quantity_unit, and a cents index shows quote quantity and coefficient apart.

NG_CONTRACTS = [("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29")]
NG_HOLIDAYS = ["2026-11-26", "2026-12-25"]


def valued_on_24_nov(
    index: str, name: str, template_fields: dict[str, object], row_: list[object]
) -> tuple[tuple[float, float, float], list[list[object]]]:
    template = ENTRY["_CreateTradeTemplate"](
        "future", row(*template_fields), row(*template_fields.values())
    )
    trades = ENTRY["_CreateTrades"](index, row(*NG_HEADERS), rows(row_), template)
    history = a_history(index, "2026-10-29", "2026-11-24", NG_HOLIDAYS, {})
    results = ENTRY["_EvaluateTrades"](
        ENTRY["_PrepareTrades"](trades, history), a_market(history, name, 3.20, 3.50)
    )
    return valued(str(results)), spilled(ENTRY["util_ReadHandle"](trades))


def test_two_selections_of_one_quantity_value_and_risk_alike() -> None:
    index, _ = an_index(
        "Henry Hub NYMEX",
        NG_CONTRACTS,
        NG_HOLIDAYS,
        [("NYMEX NG", 10_000.0), ("ICE PHH", 2_500.0), ("MMBTU", 1.0)],
    )
    as_lots, lots_spill = valued_on_24_nov(
        index,
        "Henry Hub NYMEX",
        {**NG_TEMPLATE, "quantity_unit": "ICE PHH"},
        [1.0, serial("2026-09-24"), "Z26", 2.0, 3.1],
    )
    as_units, units_spill = valued_on_24_nov(
        index,
        "Henry Hub NYMEX",
        {**NG_TEMPLATE, "quantity_unit": "MMBTU"},
        [2.0, serial("2026-09-24"), "Z26", 5_000.0, 3.1],
    )
    assert as_lots == as_units == (pytest.approx(500.0), 0.0, pytest.approx(0.5))  # NYMEX lots
    unit = lots_spill[0].index("quantity_unit")
    assert lots_spill[2][unit] == "ICE PHH" and units_spill[2][unit] == "MMBTU"
    assert "contract_specification" not in lots_spill[0]
    quote = lots_spill[0].index("quote_quantity")
    assert lots_spill[2][quote] == units_spill[2][quote] == 5_000.0
    assert lots_spill[2][lots_spill[0].index("quantity")] == 2.0
    assert units_spill[2][units_spill[0].index("quantity")] == 5_000.0


def test_a_cents_index_reads_back_the_quote_quantity_apart_from_the_coefficient() -> None:
    # One lot of 10,000 MMBTU quoted in cents and settled in dollars, as the kernel page has it:
    # a quote quantity of 10,000 MMBTU, a coefficient of 100 dollars a cent, and the risk in
    # dollars per cent per MMBTU.
    index, _ = an_index(
        "cents", NG_CONTRACTS, NG_HOLIDAYS, [("NYMEX NG", 10_000.0)], quoted_in="CENT"
    )
    template = ENTRY["_CreateTradeTemplate"](
        "future", row(*NG_TEMPLATE), row(*NG_TEMPLATE.values())
    )
    trades = ENTRY["_CreateTrades"](
        index, row(*NG_HEADERS), rows([1.0, serial("2026-09-24"), "Z26", 1.0, 300.0]), template
    )
    spill = spilled(ENTRY["util_ReadHandle"](trades))
    assert spill[2][spill[0].index("quote_quantity")] == 10_000.0
    assert spill[2][spill[0].index("coefficient")] == pytest.approx(100.0)
    assert spill[2][spill[0].index("offset")] == pytest.approx(-30_000.0)
    history = a_history(index, "2026-10-29", "2026-11-24", NG_HOLIDAYS, {})
    results = ENTRY["_EvaluateTrades"](
        ENTRY["_PrepareTrades"](trades, history), a_market(history, "cents", 310.0, 350.0)
    )
    assert valued(str(results)) == (pytest.approx(1_000.0), 0.0, pytest.approx(1.0))
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "lots of NYMEX NG (10000 MMBTU)"


def test_the_old_field_is_refused_at_the_seam_as_unknown(ng: dict[str, Any]) -> None:
    message = str(
        ENTRY["_CreateTradeTemplate"](
            "future", row("contract_specification", "quantity_unit"), row("NYMEX NG", "NYMEX NG")
        )
    )
    assert message.startswith(
        "#ERROR _CreateTradeTemplate: fields cell (1, 1) is text 'contract_specification', "
        "expected a field of future: trade_id, trade_date, contract_code, "
    )
    assert str(
        ENTRY["_CreateTrades"](
            ng["index"],
            row(*NG_HEADERS, "contract_specification"),
            rows([*NG_ROWS[0], "NYMEX NG"]),
            ng["template"],
        )
    ).startswith("#ERROR _CreateTrades: fields cell (1, 6) is text 'contract_specification', ")


# --- a quantity of zero on the sheet: the row kept ready ------------------------------------------
# zero-quantities.md's example through the entries: NG-001, two lots of Z26 at 3.00, and ENTRY-002,
# a row of F27 at 3.30 kept ready at nothing, valued with both live, Z26 at 3.10 and F27 at 3.40;
# then the row sold, one lot, through a new batch over the same history and market.

ENTRY_ROWS: list[list[object]] = [
    [1001.0, serial("2026-10-06"), "Z26", 2.0, 3.0],
    [1002.0, serial("2026-10-06"), "F27", 0.0, 3.3],
]


def entry_state(ng: dict[str, Any], second: float) -> tuple[str, str, str]:
    """The two rows with that many of F27, created on the NG index under its template, prepared
    against the fixture's history of 24 November and evaluated at 3.10 and 3.40: the trades, the
    prepared and the results handles."""
    trades = str(
        ENTRY["_CreateTrades"](
            ng["index"],
            row(*NG_HEADERS),
            rows(ENTRY_ROWS[0], [*ENTRY_ROWS[1][:3], second, 3.3]),
            ng["template"],
        )
    )
    prepared = str(ENTRY["_PrepareTrades"](trades, ng["history"]))
    market = a_market(ng["history"], "Henry Hub NYMEX", 3.10, 3.40)
    return trades, prepared, str(ENTRY["_EvaluateTrades"](prepared, market))


def test_the_pages_example_marks_2000_with_the_row_kept_ready_and_1000_once_it_is_sold(
    ng: dict[str, Any],
) -> None:
    trades, prepared, results = entry_state(ng, 0.0)
    assert valued(results) == (pytest.approx(2_000), 0.0, pytest.approx(2))
    batch = spilled(ENTRY["util_ReadHandle"](trades))
    assert [line[1] for line in batch[2:]] == [1001.0, 1002.0]  # the row kept, in its place
    assert batch[3][batch[0].index("quantity")] == 0.0
    assert batch[3][batch[0].index("offset")] == 0.0
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[2][:5] == ["Z26", "Z26", serial("2026-11-25"), False, 20_000.0]
    assert table[2][7] == 20_000.0 and table[2][8] == 2.0  # the contract's, and in lots
    units = ["USD per USD/MMBTU", "lots of NYMEX NG (10000 MMBTU)"]
    assert table[3] == ["F27", "F27", serial("2026-12-29"), False] + [0.0] * 5 + units + ["-"] * 4
    sold_trades, sold_prepared, sold = entry_state(ng, -1.0)
    assert sold_trades != trades and sold_prepared != prepared and sold != results
    assert valued(sold) == (pytest.approx(1_000), 0.0, pytest.approx(1))  # a lot sold
    assert spilled(ENTRY["util_ReadHandle"](sold))[3][7:9] == [-10_000.0, -1.0]
    assert valued(results) == (pytest.approx(2_000), 0.0, pytest.approx(2))  # the old stand


def test_an_all_zero_batch_is_a_batch_like_any_other_reporting_nothing(ng: dict[str, Any]) -> None:
    trades = ENTRY["_CreateTrades"](
        ng["index"],
        row(*NG_HEADERS),
        rows([*ENTRY_ROWS[0][:3], 0.0, 3.0], ENTRY_ROWS[1]),
        ng["template"],
    )
    assert re.fullmatch(rf"{os.getpid()}:trades:Henry Hub NYMEX:\d+", str(trades))
    prepared = ENTRY["_PrepareTrades"](trades, ng["history"])
    results = ENTRY["_EvaluateTrades"](prepared, ng["market"])
    assert spilled(ENTRY["_ReportValues"](results))[2] == [0.0, 0.0, "USD", serial("2026-11-24")]
    assert spilled(ENTRY["_ReportRisk"](results))[2] == [
        0.0,
        "lots of NYMEX NG (10000 MMBTU)",
        0.0,
        "USD per basis point",
        serial("2026-11-24"),
    ]
    assert len(spilled(ENTRY["util_ReadHandle"](trades))) == 4  # both rows kept
    assert [line[0] for line in spilled(ENTRY["util_ReadHandle"](prepared))[2:]] == ["Z26", "F27"]


def test_a_zero_financial_trade_stays_at_nothing_live_fixed_and_paid(toy: dict[str, Any]) -> None:
    trades = ENTRY["_CreateTrades"](
        toy["index"],
        row(*NG_HEADERS),
        rows([1000.0, serial("2026-10-06"), "Z26", 0.0, 3.1]),
        toy["template"],
    )
    history = ""
    for as_of, settles, quotes in (
        ("2026-11-24", {}, (3.20, 3.50, 3.60)),
        ("2026-11-26", Z26, (3.50, 3.60)),
        ("2026-11-30", Z26, (3.50, 3.60)),
    ):
        history = a_history(toy["index"], "2026-10-29", as_of, TOY_HOLIDAYS, settles)
        prepared = ENTRY["_PrepareTrades"](trades, history)
        results = ENTRY["_EvaluateTrades"](prepared, a_market(history, "TOY_GAS", *quotes))
        assert valued(str(results)) == (0.0, 0.0, 0.0), as_of
    slots = spilled(ENTRY["util_ReadHandle"](ENTRY["_PrepareTrades"](trades, history)))
    assert slots[2] == [
        "Z26",
        "Z26",
        serial("2026-11-25"),
        serial("2026-11-30"),
        True,
        True,
        0.0,
        0.0,
    ]  # fixed and paid, at nothing


def test_zero_bypasses_neither_coverage_expiry_nor_identity_on_the_sheet(
    ng: dict[str, Any],
) -> None:
    trades, prepared, _ = entry_state(ng, 0.0)
    assert ENTRY["_EvaluateTrades"](prepared, a_market(ng["history"], "Henry Hub NYMEX", 3.10)) == (
        "#ERROR _EvaluateTrades: ValueError: requested contract 'F27' is beyond live-price "
        "coverage ending at 'Z26'"
    )
    expired = a_history(ng["index"], "2026-10-29", "2026-11-26", ["2026-11-26", "2026-12-25"], {})
    assert ENTRY["_PrepareTrades"](trades, expired) == (
        "#ERROR _PrepareTrades: ValueError: trade 1001 at row 1 on Z26 expired 2026-11-25, "
        "before valuation date 2026-11-26; a physical future after its expiry is not supported"
    )
    # An all-zero batch is held to the identity rules as any batch is: a history over another
    # index of the same facts and name, and a market over another history of the same index.
    nothing = ENTRY["_CreateTrades"](
        ng["index"],
        row(*NG_HEADERS),
        rows([*ENTRY_ROWS[0][:3], 0.0, 3.0], ENTRY_ROWS[1]),
        ng["template"],
    )
    twin, _ = an_index("Henry Hub NYMEX", NG_CONTRACTS, NG_HOLIDAYS, [("NYMEX NG", 10_000.0)])
    other = a_history(twin, "2026-10-29", "2026-11-24", NG_HOLIDAYS, {})
    assert ENTRY["_PrepareTrades"](nothing, other) == (
        "#ERROR _PrepareTrades: ValueError: history is over another index, 'Henry Hub NYMEX', "
        "expected the trades', 'Henry Hub NYMEX'"
    )
    prepared_nothing = ENTRY["_PrepareTrades"](nothing, ng["history"])
    yesterday = a_history(ng["index"], "2026-10-29", "2026-11-23", NG_HOLIDAYS, {})
    assert ENTRY["_EvaluateTrades"](
        prepared_nothing, a_market(yesterday, "Henry Hub NYMEX", 3.10, 3.40)
    ) == (
        "#ERROR _EvaluateTrades: ValueError: market is over another history of index "
        "'Henry Hub NYMEX', expected the one the trades were prepared against"
    )
    assert valued(str(ENTRY["_EvaluateTrades"](prepared_nothing, ng["market"]))) == (0.0, 0.0, 0.0)


# --- what is refused, in the seam's order and then the library's ------------------------------


def test_the_refusals_come_in_the_seams_order_then_the_librarys(ng: dict[str, Any]) -> None:
    prepare, evaluate = ENTRY["_PrepareTrades"], ENTRY["_EvaluateTrades"]
    assert (
        prepare(None, ng["history"])
        == "#ERROR _PrepareTrades: trades is blank, expected trades handle"
    )
    assert prepare("x:trades:9", ng["history"]) == (
        "#ERROR _PrepareTrades: trades is text 'x:trades:9' naming no live object, "
        "expected trades handle"
    )
    assert prepare(ng["trades"], ng["market"]) == (
        f"#ERROR _PrepareTrades: history is market handle {ng['market']!r}, "
        "expected market history handle"
    )
    assert evaluate(ng["prepared"], bridge.MISSING) == (
        "#ERROR _EvaluateTrades: market is missing, expected market handle"
    )
    assert evaluate(ng["trades"], ng["market"]) == (
        f"#ERROR _EvaluateTrades: prepared is trades handle {ng['trades']!r}, "
        "expected prepared trades handle"
    )
    assert ENTRY["_ReportValues"](ng["prepared"]) == (
        f"#ERROR _ReportValues: results is prepared trades handle {ng['prepared']!r}, "
        "expected trade results handle"
    )
    assert ENTRY["_ReportRisk"](None) == (
        "#ERROR _ReportRisk: results is blank, expected trade results handle"
    )
    # Then the library: another index's history, the same facts and name; a market over another
    # history; a physical contract past its expiry; a bilateral route.
    twin, _ = an_index(
        "Henry Hub NYMEX",
        [("X26", "2026-10-28"), ("Z26", "2026-11-25"), ("F27", "2026-12-29")],
        ["2026-11-26", "2026-12-25"],
        [("NYMEX NG", 10_000.0)],
    )
    other = a_history(twin, "2026-10-29", "2026-11-24", ["2026-11-26", "2026-12-25"], {})
    assert prepare(ng["trades"], other) == (
        "#ERROR _PrepareTrades: ValueError: history is over another index, 'Henry Hub NYMEX', "
        "expected the trades', 'Henry Hub NYMEX'"
    )
    assert evaluate(ng["prepared"], a_market(other, "Henry Hub NYMEX", 3.2, 3.5)) == (
        "#ERROR _EvaluateTrades: ValueError: market is over another history of index "
        "'Henry Hub NYMEX', expected the one the trades were prepared against"
    )
    expired = a_history(ng["index"], "2026-10-29", "2026-11-26", ["2026-11-26", "2026-12-25"], {})
    assert prepare(ng["trades"], expired) == (
        "#ERROR _PrepareTrades: ValueError: trade 1001 at row 1 on Z26 expired 2026-11-25, "
        "before valuation date 2026-11-26; a physical future after its expiry is not supported"
    )
    bilateral = ENTRY["_CreateTradeTemplate"](
        "future",
        row("quantity_unit", "quantity_per", "schedule_method", "route", "settlement_method"),
        row("NYMEX NG", "month", "lastday", "bilateral", "physical"),
    )
    trades = ENTRY["_CreateTrades"](ng["index"], row(*NG_HEADERS), rows(*NG_ROWS), bilateral)
    assert evaluate(prepare(trades, ng["history"]), ng["market"]) == (
        "#ERROR _EvaluateTrades: ValueError: route is bilateral, expected cleared; bilateral "
        "valuation needs discount factors and a DV01 convention, not built yet"
    )


# --- the last3day method on the sheet ---------------------------------------------------------
# last3day-trades.md's synthetic example through the entries: the index SYN, quoted in USD per
# MMBTU with one specification UNIT of one MMBTU, X26 expiring 30 November 2026, Z26 7 December
# and F27 7 January 2027, the market closed on 4 December; the template last3day, cleared,
# financial, paying two weekdays after the last observation; A 60 of Z26 at 70 and B -30 at 72.

L3D_HOLIDAYS = ["2026-12-04"]
L3D_SETTLES = {
    "2026-12-01": 70.0,
    "2026-12-02": 71.0,
    "2026-12-03": 75.0,
    "2026-12-07": 73.0,
    "2026-12-08": 80.0,
}
L3D_A: list[object] = [1.0, serial("2026-11-20"), "Z26", 60.0, 70.0]
L3D_B: list[object] = [2.0, serial("2026-11-20"), "Z26", -30.0, 72.0]
L3D_STRIP: list[object] = [19.0, serial("2026-11-20"), "Z26-F27", 3.0, 70.0]


def l3d_template(payment_holidays: list[str], settlement: str = "financial") -> str:
    fields = PEN_FIELDS if settlement == "financial" else PEN_FIELDS[:6]
    calendar = ENTRY["_CreateHolidayCalendar"](column([serial(d) for d in payment_holidays]))
    values: list[object] = [
        "UNIT",
        "month",
        "last3day",
        "cleared",
        settlement,
        "Prototype Clearing",
        "+2bd",
        calendar,
    ]
    return str(ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*values[: len(fields)])))


@pytest.fixture(scope="module")
def l3d() -> dict[str, Any]:
    index, _ = an_index(
        "SYN",
        [("X26", "2026-11-30"), ("Z26", "2026-12-07"), ("F27", "2027-01-07")],
        L3D_HOLIDAYS,
        [("UNIT", 1.0)],
    )
    template = l3d_template(["2026-01-01"])
    headers = row(*NG_HEADERS)
    return {
        "index": index,
        "template": template,
        "headers": headers,
        "trades": ENTRY["_CreateTrades"](index, headers, rows(L3D_A, L3D_B), template),
    }


def l3d_state(
    l3d: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    trades: object | None = None,
    settles: dict[str, float] = L3D_SETTLES,
) -> tuple[str, str, str]:
    """One state: the history valued that day over the page's series, the market quoting from
    the prompt contract on, the batch prepared and evaluated; the three handles."""
    history = a_history(l3d["index"], "2026-12-01", as_of, L3D_HOLIDAYS, settles)
    market = a_market(history, "SYN", *quotes)
    prepared = ENTRY["_PrepareTrades"](l3d["trades"] if trades is None else trades, history)
    return history, str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta"),
    [
        ("2026-12-02", (74.0, 80.0), 180, 0, 30),
        ("2026-12-03", (74.0, 80.0), 150, 0, 20),
        ("2026-12-04", (74.0, 80.0), 160, 0, 10),
        ("2026-12-07", (74.0, 80.0), 160, 0, 10),
        ("2026-12-08", (80.0,), 150, 0, 0),
        ("2026-12-09", (80.0,), 0, 150, 0),
    ],
    ids=[
        "2 Dec, all three live",
        "3 Dec, the 2nd fixed",
        "4 Dec, the 2nd and 3rd fixed",
        "7 Dec, the last live on its own day",
        "8 Dec, all three fixed, unpaid",
        "9 Dec, paid",
    ],
)
def test_the_last3day_batch_values_on_the_sheet_as_the_page_says(
    l3d: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
) -> None:
    _, _, results = l3d_state(l3d, as_of, quotes)
    assert valued(results) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(delta))
    assert spilled(ENTRY["_ReportValues"](results))[2][2:] == ["USD", serial(as_of)]
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "lots of UNIT (1 MMBTU)"
    slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert [line[0] for line in slots] == ["Z26"] * 3
    assert [line[9] for line in slots] == [pytest.approx(delta)] * 3  # the contract's lots
    live = [line[5] for line in slots]
    assert sum(1 for exposure in live if exposure != 0) * 10 == delta


def test_the_last3day_days_and_payment_read_back_from_the_batch_and_the_preparation(
    l3d: dict[str, Any],
) -> None:
    batch = spilled(ENTRY["util_ReadHandle"](l3d["trades"]))
    columns = batch[0]
    assert [line[columns.index("payment_date")] for line in batch[2:]] == [serial("2026-12-09")] * 2
    assert [line[columns.index("quote_quantity")] for line in batch[2:]] == [60.0, -30.0]
    assert [line[columns.index("offset")] for line in batch[2:]] == [-4_200.0, 2_160.0]
    _, prepared, _ = l3d_state(l3d, "2026-12-04", (74.0, 80.0))
    pays = serial("2026-12-09")
    assert spilled(ENTRY["util_ReadHandle"](prepared))[2:] == [
        ["Z26", "Z26", serial("2026-12-02"), pays, True, False, 0.0, 0.0],
        ["Z26", "Z26", serial("2026-12-03"), pays, True, False, 0.0, 0.0],
        ["Z26", "Z26", serial("2026-12-07"), pays, False, False, 10.0, 10.0],
    ]
    _, paid, _ = l3d_state(l3d, "2026-12-09", (80.0,))
    assert [line[4:6] for line in spilled(ENTRY["util_ReadHandle"](paid))[2:]] == [[True, True]] * 3


def test_a_tick_moves_the_live_last3day_slots_and_the_old_results_stand(
    l3d: dict[str, Any],
) -> None:
    history, prepared, results = l3d_state(l3d, "2026-12-03", (74.0, 80.0))
    ticked = ENTRY["_EvaluateTrades"](prepared, a_market(history, "SYN", 75.0, 80.0))
    assert valued(str(ticked)) == (pytest.approx(170), 0.0, pytest.approx(20))
    assert valued(results) == (pytest.approx(150), 0.0, pytest.approx(20))


def test_a_corrected_last3day_fixing_takes_a_new_history_and_a_new_preparation(
    l3d: dict[str, Any],
) -> None:
    _, prepared, _ = l3d_state(l3d, "2026-12-03", (74.0, 80.0))
    corrected = a_history(
        l3d["index"], "2026-12-01", "2026-12-03", L3D_HOLIDAYS, {**L3D_SETTLES, "2026-12-02": 72.0}
    )
    market = a_market(corrected, "SYN", 74.0, 80.0)
    assert ENTRY["_EvaluateTrades"](prepared, market) == (
        "#ERROR _EvaluateTrades: ValueError: market is over another history of index 'SYN', "
        "expected the one the trades were prepared against"
    )
    again = ENTRY["_PrepareTrades"](l3d["trades"], corrected)
    assert valued(str(ENTRY["_EvaluateTrades"](again, market))) == (
        pytest.approx(160),
        0.0,
        pytest.approx(20),
    )


def test_a_last3day_strip_marks_42_with_a_delta_of_3_on_each_month_and_its_duplicate_twice(
    l3d: dict[str, Any],
) -> None:
    for lines, mark, delta in ((rows(L3D_STRIP), 42, 3.0), (rows(L3D_STRIP, L3D_STRIP), 84, 6.0)):
        strip = ENTRY["_CreateTrades"](l3d["index"], l3d["headers"], lines, l3d["template"])
        batch = spilled(ENTRY["util_ReadHandle"](strip))
        columns = batch[0]
        months = [line[columns.index("contract_code")] for line in batch[2:]]
        pays = [line[columns.index("payment_date")] for line in batch[2:]]
        assert months == ["Z26", "F27"] * (len(months) // 2)
        assert pays == [serial("2026-12-09"), serial("2027-01-11")] * (len(months) // 2)
        _, _, results = l3d_state(l3d, "2026-12-02", (74.0, 80.0), strip)
        assert valued(results) == (pytest.approx(mark), 0.0, pytest.approx(2 * delta))
        slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
        assert [(line[0], line[2]) for line in slots] == [
            ("Z26", serial("2026-12-02")),
            ("Z26", serial("2026-12-03")),
            ("Z26", serial("2026-12-07")),
            ("F27", serial("2027-01-05")),
            ("F27", serial("2027-01-06")),
            ("F27", serial("2027-01-07")),
        ]
        assert [line[9] for line in slots] == [pytest.approx(delta)] * 6  # the month's lots
        assert [line[5] for line in slots] == [pytest.approx(delta / 3)] * 6  # a third a day


def test_the_last3day_batch_equals_its_singletons_summed_in_either_order(
    l3d: dict[str, Any],
) -> None:
    def marked(lines: Cells) -> tuple[float, float, float]:
        batch = ENTRY["_CreateTrades"](l3d["index"], l3d["headers"], lines, l3d["template"])
        return valued(l3d_state(l3d, "2026-12-03", (74.0, 80.0), batch)[2])

    a, b = marked(rows(L3D_A)), marked(rows(L3D_B))
    both, reversed_rows = marked(rows(L3D_A, L3D_B)), marked(rows(L3D_B, L3D_A))
    assert both == reversed_rows == (pytest.approx(150), 0.0, pytest.approx(20))
    assert both[0] == pytest.approx(a[0] + b[0]) and both[2] == pytest.approx(a[2] + b[2])
    zero: list[object] = [26.0, serial("2026-11-20"), "F27", 0.0, 71.0]
    kept = ENTRY["_CreateTrades"](
        l3d["index"], l3d["headers"], rows(L3D_A, L3D_B, zero), l3d["template"]
    )
    _, _, results = l3d_state(l3d, "2026-12-03", (74.0, 80.0), kept)
    assert valued(results) == (pytest.approx(150), 0.0, pytest.approx(20))
    slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert [line[0] for line in slots] == ["Z26"] * 3 + ["F27"] * 3
    assert [line[9] for line in slots] == [pytest.approx(20)] * 3 + [0.0] * 3


def test_a_physical_last3day_future_is_refused_when_the_batch_is_made_on_the_sheet(
    l3d: dict[str, Any],
) -> None:
    physical = l3d_template(["2026-01-01"], "physical")
    assert ENTRY["_CreateTrades"](l3d["index"], l3d["headers"], rows(L3D_A), physical) == (
        "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' "
        "with the last3day method of trade 1 at row 1; a last3day future is cash settled on the "
        "average of its last three pricing days"
    )


# --- the asian method on the sheet -----------------------------------------------------------
# asian-trades.md's synthetic ethane example through the entries: the index ETHANE, quoted in USD
# per gallon with one specification GAL of one gallon, X26 expiring 30 November 2026, Z26 31
# December, F27 29 January 2027 and G27 26 February, the market closed on 25 December and 1
# January; the template asian, cleared, financial, paying two weekdays after the month's last
# pricing day on a calendar closed on 1 January; A 4,400 gallons of Z26 at 0.25 and B -2,200 at
# 0.26. The live input is the projection of the month's remaining days, not a quote of the whole
# month's average, and the delta is to that input.

ETHANE_HOLIDAYS = ["2026-12-25", "2027-01-01"]


def ethane_settles() -> dict[str, float]:
    """The page's daily series: 0.28 from 30 November, 0.24 on 1 December, 0.30 on the 2nd, 0.26
    on the 31st and 0.30 on every January pricing day."""
    days = np.arange(np.datetime64("2026-11-30"), np.datetime64("2027-02-01"))
    days = days[np.is_busday(days, holidays=np.array(ETHANE_HOLIDAYS, dtype="datetime64[D]"))]
    series = {str(d): (0.30 if str(d) >= "2027-01-01" else 0.28) for d in days}
    series.update({"2026-12-01": 0.24, "2026-12-02": 0.30, "2026-12-31": 0.26})
    return series


ETHANE_SETTLES = ethane_settles()
ETHANE_A: list[object] = [1.0, serial("2026-11-20"), "Z26", 4_400.0, 0.25]
ETHANE_B: list[object] = [2.0, serial("2026-11-20"), "Z26", -2_200.0, 0.26]
ETHANE_STRIP: list[object] = [19.0, serial("2026-11-20"), "Z26-F27", 2_200.0, 0.25]
LIVE_QUOTES = (0.28, 0.30, 0.32)
LATER_QUOTES = (0.30, 0.32)


def asian_template(
    payment_holidays: list[str], settlement: str = "financial", basis: str = "month"
) -> str:
    fields = PEN_FIELDS if settlement == "financial" else PEN_FIELDS[:6]
    calendar = ENTRY["_CreateHolidayCalendar"](column([serial(d) for d in payment_holidays]))
    values: list[object] = [
        "GAL",
        basis,
        "asian",
        "cleared",
        settlement,
        "Prototype Clearing",
        "+2bd",
        calendar,
    ]
    return str(ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*values[: len(fields)])))


@pytest.fixture(scope="module")
def ethane() -> dict[str, Any]:
    index, _ = an_index(
        "ETHANE",
        [
            ("X26", "2026-11-30"),
            ("Z26", "2026-12-31"),
            ("F27", "2027-01-29"),
            ("G27", "2027-02-26"),
        ],
        ETHANE_HOLIDAYS,
        [("GAL", 1.0)],
        ("VOLUME", "GAL"),
    )
    template = asian_template(["2027-01-01"])
    headers = row(*NG_HEADERS)
    return {
        "index": index,
        "template": template,
        "headers": headers,
        "trades": ENTRY["_CreateTrades"](index, headers, rows(ETHANE_A, ETHANE_B), template),
    }


def ethane_state(
    ethane: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    trades: object | None = None,
    settles: dict[str, float] = ETHANE_SETTLES,
) -> tuple[str, str, str]:
    """One state: the history valued that day over the page's series from 30 November, the
    market quoting from the prompt contract on, the batch prepared and evaluated."""
    history = a_history(ethane["index"], "2026-11-30", as_of, ETHANE_HOLIDAYS, settles)
    market = a_market(history, "ETHANE", *quotes)
    prepared = ENTRY["_PrepareTrades"](ethane["trades"] if trades is None else trades, history)
    return history, str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta"),
    [
        ("2026-12-01", LIVE_QUOTES, 88, 0, 2_200),
        ("2026-12-02", LIVE_QUOTES, 84, 0, 2_100),
        ("2026-12-03", LIVE_QUOTES, 86, 0, 2_000),
        ("2026-12-25", LIVE_QUOTES, 86, 0, 400),
        ("2026-12-31", LIVE_QUOTES, 86, 0, 100),
        ("2027-01-01", LATER_QUOTES, 84, 0, 0),
        ("2027-01-04", LATER_QUOTES, 84, 0, 0),
        ("2027-01-05", LATER_QUOTES, 0, 84, 0),
    ],
    ids=[
        "1 Dec, all live",
        "2 Dec, one fixed",
        "3 Dec, two fixed",
        "25 Dec, eighteen fixed",
        "31 Dec, the last live on its own day",
        "1 Jan, all fixed, unpaid",
        "4 Jan, still unpaid",
        "5 Jan, paid",
    ],
)
def test_the_asian_batch_values_on_the_sheet_as_the_page_says(
    ethane: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
) -> None:
    _, _, results = ethane_state(ethane, as_of, quotes)
    assert valued(results) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(delta))
    assert spilled(ENTRY["_ReportValues"](results))[2][2:] == ["USD", serial(as_of)]
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "lots of GAL (1 GAL)"
    slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert len(slots) == 22 and [line[0] for line in slots] == ["Z26"] * 22
    assert [line[9] for line in slots] == [pytest.approx(delta)] * 22  # the contract's lots
    assert sum(1 for line in slots if line[5] != 0) * 100 == delta


def test_the_asian_days_and_payment_read_back_from_the_batch_and_the_preparation(
    ethane: dict[str, Any],
) -> None:
    batch = spilled(ENTRY["util_ReadHandle"](ethane["trades"]))
    columns = batch[0]
    assert [line[columns.index("payment_date")] for line in batch[2:]] == [serial("2027-01-05")] * 2
    assert [line[columns.index("quote_quantity")] for line in batch[2:]] == [4_400.0, -2_200.0]
    assert [line[columns.index("offset")] for line in batch[2:]] == [
        pytest.approx(-1_100.0),
        pytest.approx(572.0),
    ]
    _, prepared, _ = ethane_state(ethane, "2026-12-02", LIVE_QUOTES)
    slots = spilled(ENTRY["util_ReadHandle"](prepared))[2:]
    assert len(slots) == 22
    pays = serial("2027-01-05")
    assert slots[0] == ["Z26", "Z26", serial("2026-12-01"), pays, True, False, 0.0, 0.0]
    hundred = pytest.approx(100.0)  # a gallon is the lot, so the lots are the gallons
    assert slots[1] == ["Z26", "Z26", serial("2026-12-02"), pays, False, False, hundred, hundred]
    assert slots[-1] == ["Z26", "Z26", serial("2026-12-31"), pays, False, False, hundred, hundred]
    _, paid, _ = ethane_state(ethane, "2027-01-05", LATER_QUOTES)
    assert [line[4:6] for line in spilled(ENTRY["util_ReadHandle"](paid))[2:]] == [
        [True, True]
    ] * 22


def test_a_tick_moves_the_live_asian_slots_and_the_old_results_stand(
    ethane: dict[str, Any],
) -> None:
    history, prepared, results = ethane_state(ethane, "2026-12-02", LIVE_QUOTES)
    ticked = ENTRY["_EvaluateTrades"](prepared, a_market(history, "ETHANE", 0.29, 0.30, 0.32))
    assert valued(str(ticked)) == (pytest.approx(105), 0.0, pytest.approx(2_100))
    assert valued(results) == (pytest.approx(84), 0.0, pytest.approx(2_100))


def test_a_corrected_asian_fixing_takes_a_new_history_and_a_new_preparation(
    ethane: dict[str, Any],
) -> None:
    _, prepared, _ = ethane_state(ethane, "2026-12-02", LIVE_QUOTES)
    corrected = a_history(
        ethane["index"],
        "2026-11-30",
        "2026-12-02",
        ETHANE_HOLIDAYS,
        {**ETHANE_SETTLES, "2026-12-01": 0.25},
    )
    market = a_market(corrected, "ETHANE", *LIVE_QUOTES)
    assert ENTRY["_EvaluateTrades"](prepared, market) == (
        "#ERROR _EvaluateTrades: ValueError: market is over another history of index 'ETHANE', "
        "expected the one the trades were prepared against"
    )
    again = ENTRY["_PrepareTrades"](ethane["trades"], corrected)
    assert valued(str(ENTRY["_EvaluateTrades"](again, market))) == (
        pytest.approx(85),
        0.0,
        pytest.approx(2_100),
    )


def test_a_payment_calendar_closed_on_the_fourth_pays_on_the_sixth_on_the_sheet(
    ethane: dict[str, Any],
) -> None:
    closed_fourth = asian_template(["2027-01-01", "2027-01-04"])
    batch = ENTRY["_CreateTrades"](
        ethane["index"], ethane["headers"], rows(ETHANE_A, ETHANE_B), closed_fourth
    )
    spill = spilled(ENTRY["util_ReadHandle"](batch))
    pay = spill[0].index("payment_date")
    assert [line[pay] for line in spill[2:]] == [serial("2027-01-06")] * 2
    _, _, fifth = ethane_state(ethane, "2027-01-05", LATER_QUOTES, batch)
    _, _, sixth = ethane_state(ethane, "2027-01-06", LATER_QUOTES, batch)
    assert valued(fifth) == (pytest.approx(84), 0.0, 0.0)
    assert valued(sixth) == (0.0, pytest.approx(84), 0.0)


def test_an_asian_strip_marks_176_with_2200_on_each_month_and_its_duplicate_twice(
    ethane: dict[str, Any],
) -> None:
    for lines, mark, delta, exposures in (
        (rows(ETHANE_STRIP), 176, 2_200.0, (100.0, 110.0)),
        (rows(ETHANE_STRIP, ETHANE_STRIP), 352, 4_400.0, (200.0, 220.0)),
    ):
        strip = ENTRY["_CreateTrades"](
            ethane["index"], ethane["headers"], lines, ethane["template"]
        )
        batch = spilled(ENTRY["util_ReadHandle"](strip))
        columns = batch[0]
        months = [line[columns.index("contract_code")] for line in batch[2:]]
        pays = [line[columns.index("payment_date")] for line in batch[2:]]
        assert months == ["Z26", "F27"] * (len(months) // 2)
        assert pays == [serial("2027-01-05"), serial("2027-02-02")] * (len(months) // 2)
        _, _, results = ethane_state(ethane, "2026-12-01", LIVE_QUOTES, strip)
        assert valued(results) == (pytest.approx(mark), 0.0, pytest.approx(2 * delta))
        slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
        assert [line[0] for line in slots] == ["Z26"] * 22 + ["F27"] * 20
        assert slots[22][2] == serial("2027-01-04") and slots[-1][2] == serial("2027-01-29")
        assert [line[9] for line in slots] == [pytest.approx(delta)] * 42  # each month's lots
        assert [line[5] for line in slots] == [pytest.approx(exposures[0])] * 22 + [
            pytest.approx(exposures[1])
        ] * 20


def test_the_asian_batch_equals_its_singletons_summed_in_either_order(
    ethane: dict[str, Any],
) -> None:
    def marked(lines: Cells) -> tuple[float, float, float]:
        batch = ENTRY["_CreateTrades"](
            ethane["index"], ethane["headers"], lines, ethane["template"]
        )
        return valued(ethane_state(ethane, "2026-12-02", LIVE_QUOTES, batch)[2])

    a, b = marked(rows(ETHANE_A)), marked(rows(ETHANE_B))
    both, reversed_rows = marked(rows(ETHANE_A, ETHANE_B)), marked(rows(ETHANE_B, ETHANE_A))
    assert (a[0], b[0]) == (pytest.approx(124), pytest.approx(-40))
    assert both == reversed_rows == (pytest.approx(84), 0.0, pytest.approx(2_100))
    assert both[0] == pytest.approx(a[0] + b[0]) and both[2] == pytest.approx(a[2] + b[2])
    zero: list[object] = [26.0, serial("2026-11-20"), "F27", 0.0, 0.27]
    kept = ENTRY["_CreateTrades"](
        ethane["index"], ethane["headers"], rows(ETHANE_A, ETHANE_B, zero), ethane["template"]
    )
    _, _, results = ethane_state(ethane, "2026-12-02", LIVE_QUOTES, kept)
    assert valued(results) == (pytest.approx(84), 0.0, pytest.approx(2_100))
    slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert [line[0] for line in slots] == ["Z26"] * 22 + ["F27"] * 20
    assert [line[9] for line in slots] == [pytest.approx(2_100)] * 22 + [0.0] * 20


def test_a_physical_asian_future_is_refused_when_the_batch_is_made_on_the_sheet(
    ethane: dict[str, Any],
) -> None:
    physical = asian_template(["2027-01-01"], "physical")
    assert ENTRY["_CreateTrades"](ethane["index"], ethane["headers"], rows(ETHANE_A), physical) == (
        "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' "
        "with the asian method of trade 1 at row 1; an asian future is cash settled on the "
        "average of its month's pricing days"
    )


def test_a_calday_batch_values_as_the_month_batch_of_its_component_quantity(
    ethane: dict[str, Any],
) -> None:
    # Z26 at 110 gallons a calendar day against Z26 at 3,410 gallons a month, both at 0.25: one
    # deal stated two ways, so every state agrees to the bit. On 2 December, the 1st fixed at
    # 0.24 and 21 days live at 0.28, each is 155 gallons a day, the mark 155 * (6.12 - 5.50) =
    # 96.1 and the delta 155 * 21 = 3,255; paid on 5 January, the fixings summing to 6.12 as
    # well, the cash is 96.1. The spill keeps 110 beside 31 days and 3,410.
    by_day = ENTRY["_CreateTrades"](
        ethane["index"],
        ethane["headers"],
        rows([3.0, serial("2026-11-20"), "Z26", 110.0, 0.25]),
        asian_template(["2027-01-01"], basis="calday"),
    )
    by_month = ENTRY["_CreateTrades"](
        ethane["index"],
        ethane["headers"],
        rows([13.0, serial("2026-11-20"), "Z26", 3_410.0, 0.25]),
        ethane["template"],
    )
    for as_of, quotes, expected in (
        ("2026-12-02", LIVE_QUOTES, (96.1, 0.0, 3_255.0)),
        ("2027-01-05", LATER_QUOTES, (0.0, 96.1, 0.0)),
    ):
        _, _, daily = ethane_state(ethane, as_of, quotes, trades=by_day)
        _, _, monthly = ethane_state(ethane, as_of, quotes, trades=by_month)
        assert valued(daily) == valued(monthly)
        assert valued(daily) == tuple(pytest.approx(x) for x in expected)
    batch = spilled(ENTRY["util_ReadHandle"](by_day))
    columns = batch[0]
    names = ("quantity", "quantity_per", "covered_days", "component_quantity", "quote_quantity")
    assert [batch[2][columns.index(name)] for name in names] == [
        110.0,
        "calday",
        31.0,
        3_410.0,
        3_410.0,
    ]


# --- explicit dates on the sheet ---------------------------------------------------------------
# trade-periods-and-bal.md, slice C: the booked period of the page, 15 to 31 December 2026 on the
# ethane index, 2,000 gallons a month at 0.25, asian, financial and cleared, paying two weekdays
# after the last pricing day: 17 covered days, 12 observations a twelfth each, the fixed leg -500
# and the payment 5 January; the fixings 0.24 on the 15th, 0.26 on the 31st and 0.28 on every
# other December pricing day, the live projection 0.28. The dates come from the helpers,
# util_StartDate and util_EndDate on BALZ26 with the reference date, or are typed, alike.

DATE_HEADERS = ("trade_id", "trade_date", "start_date", "end_date", "quantity", "fixed_price")
DECEMBER_PRICING = [
    str(d)
    for d in np.arange(np.datetime64("2026-11-30"), np.datetime64("2027-01-01"))
    if np.is_busday(d, holidays=np.array(ETHANE_HOLIDAYS, dtype="datetime64[D]"))
]
PERIOD_SETTLES = {**{d: 0.28 for d in DECEMBER_PRICING}, "2026-12-15": 0.24, "2026-12-31": 0.26}
PERIOD_STATES = [
    ("2026-12-15", LIVE_QUOTES, 60, 0, 2_000),
    ("2026-12-16", LIVE_QUOTES, 160 / 3, 0, 5_500 / 3),
    ("2027-01-01", LATER_QUOTES, 50, 0, 0),
    ("2027-01-05", LATER_QUOTES, 0, 50, 0),
]


def dated_rows(*trades: tuple[int, float, float, float]) -> Cells:
    """Rows of the dated ticket: a label, the first and last day as serials and the quantity, each
    at 0.25 and struck on 20 November."""
    return rows(
        *[
            [label, serial("2026-11-20"), start, end, quantity, 0.25]
            for label, start, end, quantity in trades
        ]
    )


def period_state(
    ethane: dict[str, Any],
    trades: object,
    as_of: str,
    quotes: tuple[float, ...],
    settles: dict[str, float] = PERIOD_SETTLES,
) -> tuple[str, str, str]:
    """One state of a dated batch: the history valued that day over the page's series from
    30 November, the market quoting from the prompt contract on, the batch prepared and
    evaluated."""
    history = a_history(ethane["index"], "2026-11-30", as_of, ETHANE_HOLIDAYS, settles)
    market = a_market(history, "ETHANE", *quotes)
    prepared = ENTRY["_PrepareTrades"](trades, history)
    return history, str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


@pytest.fixture(scope="module")
def booked(ethane: dict[str, Any]) -> dict[str, Any]:
    """The page's booking two ways: the dates from the helpers on BALZ26 with 15 December as the
    reference, and the same dates typed; and the calday twin, 2,000 a day over the 17 days."""
    start = cast(float, ENTRY["util_StartDate"]("BALZ26", serial("2026-12-15")))
    end = cast(float, ENTRY["util_EndDate"]("BALZ26", serial("2026-12-15")))
    assert (start, end) == (serial("2026-12-15"), serial("2026-12-31"))
    headers = row(*DATE_HEADERS)
    helped = ENTRY["_CreateTrades"](
        ethane["index"], headers, dated_rows((16, start, end, 2_000.0)), ethane["template"]
    )
    typed = ENTRY["_CreateTrades"](
        ethane["index"],
        headers,
        dated_rows((16, serial("2026-12-15"), serial("2026-12-31"), 2_000.0)),
        ethane["template"],
    )
    by_day = ENTRY["_CreateTrades"](
        ethane["index"],
        headers,
        dated_rows((16, serial("2026-12-15"), serial("2026-12-31"), 2_000.0)),
        asian_template(["2027-01-01"], basis="calday"),
    )
    return {"headers": headers, "helped": helped, "typed": typed, "by_day": by_day}


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta"),
    PERIOD_STATES,
    ids=["15 Dec, all live", "16 Dec, one fixed", "1 Jan, all fixed, unpaid", "5 Jan, paid"],
)
def test_the_booked_period_values_on_the_sheet_as_the_page_says(
    ethane: dict[str, Any],
    booked: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
) -> None:
    _, _, helped = period_state(ethane, booked["helped"], as_of, quotes)
    _, _, typed = period_state(ethane, booked["typed"], as_of, quotes)
    assert valued(helped) == valued(typed)
    assert valued(helped) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(delta))
    _, _, by_day = period_state(ethane, booked["by_day"], as_of, quotes)
    assert valued(by_day) == (
        pytest.approx(17 * mark),
        pytest.approx(17 * cash),
        pytest.approx(17 * delta),
    )


def test_the_booked_period_reads_back_its_days_and_a_roll_moves_only_the_states(
    ethane: dict[str, Any], booked: dict[str, Any]
) -> None:
    batch = spilled(ENTRY["util_ReadHandle"](booked["helped"]))
    columns = batch[0]
    line = batch[2]
    names = (
        "contract_code",
        "quantity",
        "quantity_per",
        "start_date",
        "end_date",
        "covered_days",
        "component_quantity",
    )
    assert [line[columns.index(name)] for name in names] == [
        "Z26",
        2_000.0,
        "month",
        serial("2026-12-15"),
        serial("2026-12-31"),
        17.0,
        2_000.0,
    ]
    assert spilled(ENTRY["util_ReadHandle"](booked["typed"]))[2] == line
    assert (
        spilled(ENTRY["util_ReadHandle"](booked["by_day"]))[2][columns.index("component_quantity")]
        == 34_000.0
    )
    history, prepared, results = period_state(ethane, booked["helped"], "2026-12-16", LIVE_QUOTES)
    slots = spilled(ENTRY["util_ReadHandle"](prepared))[2:]
    assert [line[2] for line in slots] == [
        serial(d)
        for d in (
            "2026-12-15",
            "2026-12-16",
            "2026-12-17",
            "2026-12-18",
            "2026-12-21",
            "2026-12-22",
            "2026-12-23",
            "2026-12-24",
            "2026-12-28",
            "2026-12-29",
            "2026-12-30",
            "2026-12-31",
        )
    ]
    assert [line[3] for line in slots] == [serial("2027-01-05")] * 12  # the payment day
    assert [line[4] for line in slots] == [True] + [False] * 11
    assert slots[1][6] == pytest.approx(2_000 / 12)
    # A tick reuses the preparation over the same history; the old results stand.
    ticked = ENTRY["_EvaluateTrades"](prepared, a_market(history, "ETHANE", 0.30, 0.30, 0.32))
    assert valued(str(ticked)) == (
        pytest.approx(2_000 / 12 * (0.24 + 11 * 0.30) - 500),
        0.0,
        pytest.approx(5_500 / 3),
    )
    assert valued(results) == (pytest.approx(160 / 3), 0.0, pytest.approx(5_500 / 3))
    # The day rolled on: a new preparation, the same booked days, quantities and weights.
    _, rolled, _ = period_state(ethane, booked["helped"], "2026-12-17", LIVE_QUOTES)
    assert rolled != prepared
    later = spilled(ENTRY["util_ReadHandle"](rolled))[2:]
    assert [line[2] for line in later] == [line[2] for line in slots]
    assert [line[4] for line in later] == [True, True] + [False] * 10
    assert spilled(ENTRY["util_ReadHandle"](booked["helped"]))[2] == line
    # A fixing before the period, changed: the value stands once prepared against the new history.
    _, _, changed = period_state(
        ethane, booked["helped"], "2026-12-16", LIVE_QUOTES, {**PERIOD_SETTLES, "2026-12-14": 0.50}
    )
    assert valued(changed) == valued(results)


def test_two_starts_on_one_contract_share_a_batch_and_two_ends_pay_apart(
    ethane: dict[str, Any], booked: dict[str, Any]
) -> None:
    # P from the 15th and Q from the 1st, both to the 31st: on 2 December the batch is the two
    # singletons summed, 60 and 66 of mark, 2,000 and 2,100 of delta; reversed rows and a duplicate
    # of P alike; a zero row adds nothing. Ending on the 30th Q pays on 4 January, a group of its
    # own: on the 4th its 1,298/21 is cash, twenty days at 0.28 and the 15th at 0.24 over its 21
    # days, beside P's 50 still in mark, and the preparation reads back the two days.
    headers = booked["headers"]
    first, last = serial("2026-12-01"), serial("2026-12-31")
    p = (16, serial("2026-12-15"), last, 2_000.0)
    q = (17, first, last, 2_200.0)
    together = ENTRY["_CreateTrades"](
        ethane["index"], headers, dated_rows(p, q), ethane["template"]
    )
    reversed_rows = ENTRY["_CreateTrades"](
        ethane["index"], headers, dated_rows(q, p), ethane["template"]
    )
    doubled = ENTRY["_CreateTrades"](
        ethane["index"], headers, dated_rows(p, q, p), ethane["template"]
    )
    with_zero = ENTRY["_CreateTrades"](
        ethane["index"], headers, dated_rows(p, q, (26, first, last, 0.0)), ethane["template"]
    )
    _, _, both = period_state(ethane, together, "2026-12-02", LIVE_QUOTES)
    _, _, only_p = period_state(ethane, booked["typed"], "2026-12-02", LIVE_QUOTES)
    _, _, only_q = period_state(
        ethane,
        ENTRY["_CreateTrades"](ethane["index"], headers, dated_rows(q), ethane["template"]),
        "2026-12-02",
        LIVE_QUOTES,
    )
    assert valued(both) == (pytest.approx(126), 0.0, pytest.approx(4_100))
    assert valued(only_p) == (pytest.approx(60), 0.0, pytest.approx(2_000))
    assert valued(only_q) == (pytest.approx(66), 0.0, pytest.approx(2_100))
    _, _, swapped = period_state(ethane, reversed_rows, "2026-12-02", LIVE_QUOTES)
    assert valued(swapped) == valued(both)
    _, _, twice = period_state(ethane, doubled, "2026-12-02", LIVE_QUOTES)
    assert valued(twice) == (pytest.approx(186), 0.0, pytest.approx(6_100))
    _, _, zeroed = period_state(ethane, with_zero, "2026-12-02", LIVE_QUOTES)
    assert valued(zeroed) == valued(both)
    apart = ENTRY["_CreateTrades"](
        ethane["index"],
        headers,
        dated_rows(p, (17, first, serial("2026-12-30"), 2_200.0)),
        ethane["template"],
    )
    batch = spilled(ENTRY["util_ReadHandle"](apart))
    assert [line[batch[0].index("payment_date")] for line in batch[2:]] == [
        serial("2027-01-05"),
        serial("2027-01-04"),
    ]
    _, prepared, on_fourth = period_state(ethane, apart, "2027-01-04", LATER_QUOTES)
    assert valued(on_fourth) == (pytest.approx(50), pytest.approx(1_298 / 21), 0.0)
    slots = spilled(ENTRY["util_ReadHandle"](prepared))[2:]
    assert [line[3] for line in slots] == [serial("2027-01-04")] * 21 + [serial("2027-01-05")] * 12
    assert [line[5] for line in slots] == [True] * 21 + [False] * 12  # Q settled, P not yet
    _, _, on_fifth = period_state(ethane, apart, "2027-01-05", LATER_QUOTES)
    assert valued(on_fifth) == (pytest.approx(0), pytest.approx(50 + 1_298 / 21), 0.0)


# --- payment groups: two payment days on one contract through the seam ----------------------
# multiple-payment-groups.md's example on the sheet: the PAYS index of X26, Z26 and F27 expiring
# 30 November 2026, 4 December and 8 January 2027, no holiday that matters, one UNIT of one MMBTU;
# a last3day template over seven fields, the lag left to the ticket; A, 60 of Z26 at 70 at +1bd,
# paying Monday 7 December, and B, -30 at 72 at +3bd, paying Wednesday the 9th; the settles of
# the 2nd, 3rd and 4th 71, 75 and 73.
PAYS_FIELDS = (*PEN_FIELDS[:6], "payment_holiday_calendar")
PAYS_HEADERS = (*NG_HEADERS, "payment_time_lag")
PAYS_HOLIDAYS = ["2026-01-01"]
PAYS_A: list[object] = [1.0, serial("2026-11-30"), "Z26", 60.0, 70.0, "+1bd"]
PAYS_B: list[object] = [2.0, serial("2026-11-30"), "Z26", -30.0, 72.0, "+3bd"]
PAYS_SETTLES = {"2026-12-02": 71.0, "2026-12-03": 75.0, "2026-12-04": 73.0}
PAYS_STATES = [
    ("2026-12-02", (74.0, 80.0), 180, 0, 30, [False, False]),
    ("2026-12-03", (74.0, 80.0), 150, 0, 20, [False, False]),
    ("2026-12-04", (74.0, 80.0), 160, 0, 10, [False, False]),
    ("2026-12-05", (80.0,), 150, 0, 0, [False, False]),
    ("2026-12-07", (80.0,), -30, 180, 0, [True, False]),
    ("2026-12-09", (80.0,), 0, 150, 0, [True, True]),
]
PAYS_IDS = [
    "2 Dec, all three live",
    "3 Dec, the 2nd fixed",
    "4 Dec, the 3rd fixed too",
    "5 Dec, both final, neither paid",
    "7 Dec, A paid, B unpaid",
    "9 Dec, B paid",
]


@pytest.fixture(scope="module")
def pays() -> dict[str, Any]:
    index, _ = an_index(
        "PAYS",
        [("X26", "2026-11-30"), ("Z26", "2026-12-04"), ("F27", "2027-01-08")],
        PAYS_HOLIDAYS,
        [("UNIT", 1.0)],
    )
    calendar = ENTRY["_CreateHolidayCalendar"](column([serial("2026-01-01")]))
    template = ENTRY["_CreateTradeTemplate"](
        "future",
        row(*PAYS_FIELDS),
        row("UNIT", "month", "last3day", "cleared", "financial", "Prototype Clearing", calendar),
    )
    headers = row(*PAYS_HEADERS)
    return {
        "index": index,
        "template": template,
        "headers": headers,
        "trades": ENTRY["_CreateTrades"](index, headers, rows(PAYS_A, PAYS_B), template),
    }


def pays_state(
    pays: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    trades: object | None = None,
    settles: dict[str, float] = PAYS_SETTLES,
) -> tuple[str, str, str]:
    history = a_history(pays["index"], "2026-12-01", as_of, PAYS_HOLIDAYS, settles)
    market = a_market(history, "PAYS", *quotes)
    prepared = ENTRY["_PrepareTrades"](pays["trades"] if trades is None else trades, history)
    return history, str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "delta", "settled"), PAYS_STATES, ids=PAYS_IDS
)
def test_two_payment_days_on_one_contract_value_on_the_sheet_as_the_ticket_says(
    pays: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
    settled: list[bool],
) -> None:
    _, prepared, results = pays_state(pays, as_of, quotes)
    assert valued(results) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(delta))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert slots[0] == [
        "pricing_contract",
        "booked_contract",
        "observation_date",
        "payment_date",
        "is_fixed",
        "is_settled",
        "live_coefficient",
        "live_lots",
    ]
    assert slots[1] == [
        "str",
        "str",
        "datetime64[D]",
        "datetime64[D]",
        "bool",
        "bool",
        "float64",
        "float64",
    ]
    days = [serial(d) for d in ("2026-12-02", "2026-12-03", "2026-12-04")]
    assert [line[2] for line in slots[2:]] == days * 2
    assert [line[3] for line in slots[2:]] == [serial("2026-12-07")] * 3 + [
        serial("2026-12-09")
    ] * 3
    assert [line[5] for line in slots[2:]] == [settled[0]] * 3 + [settled[1]] * 3
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[0] == [
        "pricing_contract",
        "booked_contract",
        "observation_date",
        "payment_date",
        "is_fixed",
        "live_coefficient",
        "live_lots",
        "live_contribution",
        "contract_sensitivity",
        "contract_lot_delta",
        "sensitivity_unit",
        "lot_unit",
        "brokerage_reserve",
        "clearing_reserve",
        "marketing_reserve",
        "currency",
    ]
    assert [line[3] for line in table[2:]] == [line[3] for line in slots[2:]]
    assert table[2][-4:] == [0.0, 0.0, 0.0, "USD"]
    assert [line[-4:] for line in table[3:]] == [["-"] * 4] * 5  # once, not per slot
    assert [line[9] for line in table[2:]] == [pytest.approx(delta)] * 6  # the contract's, once


def test_the_two_lags_read_back_from_the_batch_and_the_preparation_outlives_a_tick(
    pays: dict[str, Any],
) -> None:
    batch = spilled(ENTRY["util_ReadHandle"](pays["trades"]))
    columns = batch[0]
    assert [line[columns.index("payment_time_lag")] for line in batch[2:]] == ["+1bd", "+3bd"]
    assert [line[columns.index("payment_date")] for line in batch[2:]] == [
        serial("2026-12-07"),
        serial("2026-12-09"),
    ]
    assert [line[columns.index("offset")] for line in batch[2:]] == [-4_200.0, 2_160.0]
    history, prepared, results = pays_state(pays, "2026-12-03", (74.0, 80.0))
    ticked = ENTRY["_EvaluateTrades"](prepared, a_market(history, "PAYS", 75.0, 80.0))
    assert valued(str(ticked)) == (pytest.approx(170), 0.0, pytest.approx(20))
    assert valued(results) == (pytest.approx(150), 0.0, pytest.approx(20))
    _, again, corrected = pays_state(
        pays, "2026-12-03", (74.0, 80.0), settles={**PAYS_SETTLES, "2026-12-02": 72.0}
    )
    assert again != prepared
    assert valued(corrected) == (pytest.approx(160), 0.0, pytest.approx(20))


def test_two_payment_days_equal_their_singletons_and_matching_days_compress_on_the_sheet(
    pays: dict[str, Any],
) -> None:
    def marked(lines: Cells, as_of: str, quotes: tuple[float, ...]) -> tuple[float, float, float]:
        batch = ENTRY["_CreateTrades"](pays["index"], pays["headers"], lines, pays["template"])
        return valued(pays_state(pays, as_of, quotes, batch)[2])

    for as_of, quotes, mark, cash, delta, _ in PAYS_STATES:
        a, b = marked(rows(PAYS_A), as_of, quotes), marked(rows(PAYS_B), as_of, quotes)
        both = marked(rows(PAYS_A, PAYS_B), as_of, quotes)
        swapped = marked(rows(PAYS_B, PAYS_A), as_of, quotes)
        assert both == swapped == (pytest.approx(mark), pytest.approx(cash), pytest.approx(delta))
        assert both[0] == pytest.approx(a[0] + b[0]) and both[1] == pytest.approx(a[1] + b[1])
    # A at +3bd too: one group paying the 9th, three slots, and nothing paid on the 7th.
    same: list[object] = [*PAYS_A[:5], "+3bd"]
    one_group = ENTRY["_CreateTrades"](
        pays["index"], pays["headers"], rows(same, PAYS_B), pays["template"]
    )
    _, prepared, results = pays_state(pays, "2026-12-07", (80.0,), one_group)
    assert len(spilled(ENTRY["util_ReadHandle"](prepared))) == 5
    assert valued(results) == (pytest.approx(150), 0.0, 0.0)


# --- mixed fields in one batch through the seam, mixed-trade-fields.md ----------------------------
# The ticket's example on the sheet: the MIXED index, USD per GAL, GAL and BBL specifications of one
# unit each, X26, Z26, F27 and G27 expiring 30 November 2026, 31 December, 29 January 2027 and
# 26 February, the market closed on 25 December; a template of six fields, the route, the
# settlement, the trade date, the price of 10, +1bd and a payment calendar closed on 1 January; the
# ticket's seven columns with each row's unit, basis, method and clearing house. Every settle 11,
# the projection 12: 256 and 128 on 1 December, 194 and 66 on the 30th, 275 of mark with -62 of cash
# and 85 on the 31st, 190 unpaid on 1 January, 128 of cash on the 4th.
MIXED_FIELDS = (
    "route",
    "settlement_method",
    "trade_date",
    "fixed_price",
    "payment_time_lag",
    "payment_holiday_calendar",
)
MIXED_HEADERS = (
    "trade_id",
    "contract_code",
    "quantity",
    "quantity_unit",
    "quantity_per",
    "schedule_method",
    "clearing_house",
)
MIXED_A: list[object] = [1.0, "Z26", 1.0, "BBL", "month", "lastday", "Clearer A"]
MIXED_B: list[object] = [2.0, "Z26", -2.0, "GAL", "calday", "penultimate", "Clearer B"]
MIXED_C: list[object] = [3.0, "Z26", 3.0, "BBL", "month", "last3day", "Clearer A"]
MIXED_D: list[object] = [4.0, "Z26", 22.0, "GAL", "month", "asian", "Clearer B"]
MIXED_HOLIDAYS = ["2026-12-25"]
MIXED_DECEMBER = [
    str(d)
    for d in np.arange(np.datetime64("2026-12-01"), np.datetime64("2027-01-01"))
    if np.is_busday(d, holidays=np.array(MIXED_HOLIDAYS, dtype="datetime64[D]"))
]
MIXED_SETTLES = {d: 11.0 for d in MIXED_DECEMBER}
MIXED_QUOTES = (12.0, 13.0, 14.0)
MIXED_LATER = (13.0, 14.0)
MIXED_STATES = [
    ("2026-12-01", MIXED_QUOTES, 256, 0, 128),
    ("2026-12-30", MIXED_QUOTES, 194, 0, 66),
    ("2026-12-31", MIXED_QUOTES, 275, -62, 85),
    ("2027-01-01", MIXED_LATER, 190, -62, 0),
    ("2027-01-04", MIXED_LATER, 0, 128, 0),
]
MIXED_IDS = [
    "1 Dec, everything live",
    "30 Dec, the 29th and before fixed",
    "31 Dec, B paid",
    "1 Jan, everything fixed, the rest unpaid",
    "4 Jan, both paid",
]


@pytest.fixture(scope="module")
def mixed() -> dict[str, Any]:
    schedule = ENTRY["_CreateFuturesSchedule"](
        rows(["X26"], ["Z26"], ["F27"], ["G27"]),
        column([serial(d) for d in ("2026-11-30", "2026-12-31", "2027-01-29", "2027-02-26")]),
        bridge.MISSING,
    )
    holidays = ENTRY["_CreateHolidayCalendar"](column([serial(d) for d in MIXED_HOLIDAYS]))
    conventions = ENTRY["_CreateIndexConventions"]("USD", "GAL", "USD", "VOLUME", "GAL")
    specifications = ENTRY["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        rows(["GAL", 1.0, "GAL", 0.0, 0.0], ["BBL", 1.0, "BBL", 0.0, 0.0]),
    )
    index = str(
        ENTRY["_CreateIndex"](
            "MIXED",
            "Synthetic volume index for the mixed-fields example",
            schedule,
            conventions,
            specifications,
            holidays,
            "GAL",
        )
    )
    payments = ENTRY["_CreateHolidayCalendar"](column([serial("2027-01-01")]))
    template = ENTRY["_CreateTradeTemplate"](
        "future",
        row(*MIXED_FIELDS),
        row("cleared", "financial", serial("2026-11-30"), 10.0, "+1bd", payments),
    )
    headers = row(*MIXED_HEADERS)
    return {
        "index": index,
        "template": template,
        "headers": headers,
        "trades": ENTRY["_CreateTrades"](
            index, headers, rows(MIXED_A, MIXED_B, MIXED_C, MIXED_D), template
        ),
    }


def mixed_state(
    mixed: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    trades: object | None = None,
    settles: dict[str, float] = MIXED_SETTLES,
) -> tuple[str, str, str]:
    history = a_history(mixed["index"], "2026-11-30", as_of, MIXED_HOLIDAYS, settles)
    market = a_market(history, "MIXED", *quotes)
    prepared = ENTRY["_PrepareTrades"](mixed["trades"] if trades is None else trades, history)
    return history, str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


@pytest.mark.parametrize(("as_of", "quotes", "mark", "cash", "delta"), MIXED_STATES, ids=MIXED_IDS)
def test_the_mixed_batch_values_on_the_sheet_as_the_ticket_says(
    mixed: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    delta: float,
) -> None:
    _, prepared, results = mixed_state(mixed, as_of, quotes)
    assert valued(results) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(delta))
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "lots of GAL (1 GAL)"
    slots = spilled(ENTRY["util_ReadHandle"](prepared))[2:]
    assert len(slots) == 23 and [line[0] for line in slots] == ["Z26"] * 23
    assert [line[3] for line in slots] == [serial("2026-12-31")] + [serial("2027-01-04")] * 22
    assert [line[5] for line in slots] == [as_of >= "2026-12-31"] + [as_of >= "2027-01-04"] * 22
    table = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert [line[9] for line in table] == [pytest.approx(delta)] * 23


def test_the_mixed_batch_reads_back_each_rows_own_choices(mixed: dict[str, Any]) -> None:
    # A strip beside the four rows, S the whole of December and January under asian in gallons a
    # month: its two components show S's choices, not row 1's.
    strip: list[object] = [19.0, "Z26-F27", 5.0, "GAL", "month", "asian", "Clearer B"]
    handle = ENTRY["_CreateTrades"](
        mixed["index"],
        mixed["headers"],
        rows(MIXED_A, MIXED_B, MIXED_C, MIXED_D, strip),
        mixed["template"],
    )
    batch = spilled(ENTRY["util_ReadHandle"](handle))
    columns = batch[0]

    def column_of(name: str) -> list[object]:
        return [line[columns.index(name)] for line in batch[2:]]

    assert column_of("row") == [1.0, 2.0, 3.0, 4.0, 5.0, 5.0]
    assert column_of("contract_code") == ["Z26", "Z26", "Z26", "Z26", "Z26", "F27"]
    assert column_of("schedule_method") == [
        "lastday",
        "penultimate",
        "last3day",
        "asian",
        "asian",
        "asian",
    ]
    assert column_of("quantity_unit") == ["BBL", "GAL", "BBL", "GAL", "GAL", "GAL"]
    assert column_of("quantity_per") == ["month", "calday", "month", "month", "month", "month"]
    assert column_of("clearing_house") == [
        "Clearer A",
        "Clearer B",
        "Clearer A",
        "Clearer B",
        "Clearer B",
        "Clearer B",
    ]
    assert column_of("quantity") == [1.0, -2.0, 3.0, 22.0, 5.0, 5.0]
    assert column_of("component_quantity") == [1.0, -62.0, 3.0, 22.0, 5.0, 5.0]
    assert column_of("quote_quantity") == [42.0, -62.0, 126.0, 22.0, 5.0, 5.0]
    assert column_of("payment_time_lag") == ["+1bd"] * 6
    assert column_of("payment_date") == [
        serial("2027-01-04"),
        serial("2026-12-31"),
        serial("2027-01-04"),
        serial("2027-01-04"),
        serial("2027-01-04"),
        serial("2027-02-01"),
    ]
    assert column_of("offset") == [-420.0, 620.0, -1_260.0, -220.0, -50.0, -50.0]


def test_a_tick_moves_the_mixed_batch_and_the_old_results_stand(mixed: dict[str, Any]) -> None:
    history, prepared, results = mixed_state(mixed, "2026-12-30", MIXED_QUOTES)
    ticked = ENTRY["_EvaluateTrades"](prepared, a_market(history, "MIXED", 13.0, 13.0, 14.0))
    assert valued(str(ticked)) == (pytest.approx(260), 0.0, pytest.approx(66))
    assert valued(results) == (pytest.approx(194), 0.0, pytest.approx(66))
    _, again, corrected = mixed_state(
        mixed, "2026-12-30", MIXED_QUOTES, settles={**MIXED_SETTLES, "2026-12-29": 12.0}
    )
    assert again != prepared and valued(corrected) == (pytest.approx(237), 0.0, pytest.approx(66))


def test_the_mixed_batch_equals_its_singletons_on_the_sheet_and_a_uniform_field_either_way(
    mixed: dict[str, Any],
) -> None:
    def marked(lines: Cells, as_of: str, quotes: tuple[float, ...]) -> tuple[float, float, float]:
        batch = ENTRY["_CreateTrades"](mixed["index"], mixed["headers"], lines, mixed["template"])
        return valued(mixed_state(mixed, as_of, quotes, batch)[2])

    for as_of, quotes, mark, cash, delta in MIXED_STATES:
        alone = [marked(rows(line), as_of, quotes) for line in (MIXED_A, MIXED_B, MIXED_C, MIXED_D)]
        both = marked(rows(MIXED_A, MIXED_B, MIXED_C, MIXED_D), as_of, quotes)
        swapped = marked(rows(MIXED_D, MIXED_C, MIXED_B, MIXED_A), as_of, quotes)
        assert both == swapped == (pytest.approx(mark), pytest.approx(cash), pytest.approx(delta))
        assert both[0] == pytest.approx(sum(one[0] for one in alone))
        assert both[1] == pytest.approx(sum(one[1] for one in alone))
    # The method from the template, the ticket without its column, or the ticket's column of one
    # word: the same batch; and both at once refused as any field is.
    without = row(*(name for name in MIXED_HEADERS if name != "schedule_method"))
    lastday_template = ENTRY["_CreateTradeTemplate"](
        "future",
        row(*MIXED_FIELDS, "schedule_method"),
        row(
            "cleared",
            "financial",
            serial("2026-11-30"),
            10.0,
            "+1bd",
            ENTRY["_CreateHolidayCalendar"](column([serial("2027-01-01")])),
            "lastday",
        ),
    )
    shorter = [[*line[:5], *line[6:]] for line in (MIXED_A, MIXED_B, MIXED_C, MIXED_D)]
    by_template = ENTRY["_CreateTrades"](mixed["index"], without, rows(*shorter), lastday_template)
    uniform = [[*line[:5], "lastday", line[6]] for line in (MIXED_A, MIXED_B, MIXED_C, MIXED_D)]
    by_ticket = ENTRY["_CreateTrades"](
        mixed["index"], mixed["headers"], rows(*uniform), mixed["template"]
    )
    for as_of, quotes, *_ in MIXED_STATES[:3]:
        assert valued(mixed_state(mixed, as_of, quotes, by_template)[2]) == valued(
            mixed_state(mixed, as_of, quotes, by_ticket)[2]
        )
    assert str(
        ENTRY["_CreateTrades"](mixed["index"], mixed["headers"], rows(*uniform), lastday_template)
    ) == (
        "#ERROR _CreateTrades: ValueError: schedule_method is supplied by the template and by the "
        "ticket, expected by one of them"
    )
    assert str(
        ENTRY["_CreateTrades"](
            mixed["index"],
            mixed["headers"],
            rows(MIXED_A, [2.0, "Z26", -2.0, "ICE", "calday", "penultimate", "Clearer B"]),
            mixed["template"],
        )
    ) == (
        "#ERROR _CreateTrades: ValueError: quantity_unit row 2 is 'ICE', expected one of the "
        "index's specifications: 'GAL', 'BBL'"
    )


# --- delta in lots of the index's reporting specification, lot-delta-reporting.md ---------------
# The ticket's ETE index: VOLUME in gallons, settled in dollars and quoted in cents a gallon unless
# said; three specifications, LOT of a thousand barrels, BBL of one barrel and GAL of one gallon,
# and LOT the reporting lot, so a live lot is 42,000 gallons, 420 dollars a cent a gallon of
# sensitivity and one lot of delta whatever word the row entered its quantity in. X26 expires
# 30 November 2026, Z26 31 December and F27 29 January; the market closes on Christmas Day and the
# payment calendar on New Year's Day. The rows at 25 cents a gallon valued at 28: 1,260 dollars of
# mark each, 420 of sensitivity and one lot.
ETE_CONTRACTS = [("X26", "2026-11-30"), ("Z26", "2026-12-31"), ("F27", "2027-01-29")]
ETE_HOLIDAYS = ["2026-12-25"]
ETE_LOTS: list[list[object]] = [["LOT", 1000.0, "BBL"], ["BBL", 1.0, "BBL"], ["GAL", 1.0, "GAL"]]
ETE_FIELDS = ("route", "settlement_method", "clearing_house", "payment_time_lag")
ETE_HEADERS = (
    "trade_id",
    "trade_date",
    "contract_code",
    "quantity",
    "quantity_unit",
    "fixed_price",
    "schedule_method",
)
ETE_DATED = (
    "trade_id",
    "trade_date",
    "start_date",
    "end_date",
    "quantity",
    "quantity_unit",
    "fixed_price",
    "schedule_method",
)
ETE_ROWS: list[list[object]] = [
    [1.0, serial("2026-11-20"), "Z26", 1.0, "LOT", 25.0, "lastday"],
    [2.0, serial("2026-11-20"), "Z26", 1000.0, "BBL", 25.0, "lastday"],
    [3.0, serial("2026-11-20"), "Z26", 42000.0, "GAL", 25.0, "lastday"],
]


def ete_index(
    quote: tuple[str, str] = ("CENT", "GAL"),
    settled: str = "USD",
    reporting_lot: object = "LOT",
    fees: dict[str, tuple[float, float]] | None = None,
) -> str:
    """The ETE index through the seam, quoted in that currency unit per that quantity unit and
    settled in that currency, the reporting lot as given, MISSING for none, and since #170 the
    brokerage and clearing rates per lot of the specifications named, the rest free."""
    rates = fees or {}
    schedule = ENTRY["_CreateFuturesSchedule"](
        rows(*[[code] for code, _ in ETE_CONTRACTS]),
        column([serial(expiry) for _, expiry in ETE_CONTRACTS]),
        bridge.MISSING,
    )
    calendar = ENTRY["_CreateHolidayCalendar"](column([serial(day) for day in ETE_HOLIDAYS]))
    conventions = ENTRY["_CreateIndexConventions"](quote[0], quote[1], settled, "VOLUME", "GAL")
    specifications = ENTRY["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        rows(
            *[
                [name, size, unit, *rates.get(str(name), (0.0, 0.0))]
                for name, size, unit in ETE_LOTS
            ]
        ),
    )
    made = ENTRY["_CreateIndex"](
        "ETE",
        "Ethane - synthetic volume index",
        schedule,
        conventions,
        specifications,
        calendar,
        reporting_lot,
    )
    return str(made)


def ete_template(basis: str | None = "month") -> str:
    """A financial template paying one business day after the last observation on a calendar
    closed on New Year's Day, the basis in it unless None leaves it to the ticket."""
    payments = str(ENTRY["_CreateHolidayCalendar"](column([serial("2027-01-01")])))
    fields = ["quantity_per", *ETE_FIELDS, "payment_holiday_calendar"]
    values: list[object] = [basis, "cleared", "financial", "ETE Clearing", "+1bd", payments]
    if basis is None:
        fields, values = fields[1:], values[1:]
    return str(ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*values)))


@pytest.fixture(scope="module")
def ete() -> dict[str, Any]:
    return {"index": ete_index(), "template": ete_template(), "by_row": ete_template(None)}


def ete_state(
    index: str,
    template: str,
    lines: list[list[object]],
    as_of: str,
    settles: dict[str, float],
    quotes: tuple[float, ...],
    headers: tuple[str, ...] = ETE_HEADERS,
) -> tuple[str, str, str]:
    """That ticket on the index under the template, prepared against the history valued that
    day, 3.00 on every fixed day but the settles given, and evaluated at the quotes: the trades,
    the prepared and the results handles."""
    trades = str(ENTRY["_CreateTrades"](index, row(*headers), rows(*lines), template))
    history = a_history(index, "2026-11-30", as_of, ETE_HOLIDAYS, settles)
    prepared = str(ENTRY["_PrepareTrades"](trades, history))
    results = str(ENTRY["_EvaluateTrades"](prepared, a_market(history, "ETE", *quotes)))
    return trades, prepared, results


@pytest.mark.parametrize(
    "line", ETE_ROWS, ids=["a lot", "a thousand barrels", "forty-two thousand gallons"]
)
def test_an_ete_row_reports_one_lot_whatever_word_entered_it(
    ete: dict[str, Any], line: list[object]
) -> None:
    trades, prepared, results = ete_state(
        ete["index"], ete["template"], [line], "2026-12-02", {}, (28.0, 29.0)
    )
    assert valued(results) == (pytest.approx(1_260), 0.0, pytest.approx(1))
    risk = spilled(ENTRY["_ReportRisk"](results))[2]
    assert risk[1] == "lots of LOT (1000 BBL)" and risk[3] == "USD per basis point"
    batch = spilled(ENTRY["util_ReadHandle"](trades))
    assert batch[2][batch[0].index("quote_quantity")] == pytest.approx(42_000.0)
    assert batch[2][batch[0].index("coefficient")] == pytest.approx(420.0)
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert slots[0][6:] == ["live_coefficient", "live_lots"]
    assert slots[2][6:] == [pytest.approx(420.0), pytest.approx(1.0)]
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[0][5:] == [
        "live_coefficient",
        "live_lots",
        "live_contribution",
        "contract_sensitivity",
        "contract_lot_delta",
        "sensitivity_unit",
        "lot_unit",
        "brokerage_reserve",
        "clearing_reserve",
        "marketing_reserve",
        "currency",
    ]
    assert table[2][5:] == [
        pytest.approx(420.0),
        pytest.approx(1.0),
        pytest.approx(11_760.0),
        pytest.approx(420.0),
        pytest.approx(1.0),
        "USD per CENT/GAL",
        "lots of LOT (1000 BBL)",
        0.0,
        0.0,
        0.0,
        "USD",
    ]


def test_the_three_ete_rows_together_report_three_lots(ete: dict[str, Any]) -> None:
    _, _, results = ete_state(
        ete["index"], ete["template"], ETE_ROWS, "2026-12-02", {}, (28.0, 29.0)
    )
    assert valued(results) == (pytest.approx(3_780), 0.0, pytest.approx(3))
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert len(table) == 3  # one slot, the three rows' observations summed into it
    assert table[2][5:] == [
        pytest.approx(1_260.0),
        pytest.approx(3.0),
        pytest.approx(35_280.0),
        pytest.approx(1_260.0),
        pytest.approx(3.0),
        "USD per CENT/GAL",
        "lots of LOT (1000 BBL)",
        0.0,
        0.0,
        0.0,
        "USD",
    ]


def test_a_partial_asian_period_reports_the_live_half_of_its_lots(ete: dict[str, Any]) -> None:
    # 14 to 17 December 2026, four weekday observations a quarter each, valued on the 16th with
    # the 14th settled at 26 and the 15th at 27, the 16th and the 17th live at 28. By hand over the
    # three rows: 1,260 of coefficient, set amounts 315 * 26 + 315 * 27 = 16,695, live 630 * 28 =
    # 17,640, the fixed leg -31,500, so 2,835 of mark, 630 of sensitivity and 1.5 lots, half the
    # weight of three lots still to price; a 1,500-barrel equivalent, not a count of days.
    lines: list[list[object]] = [
        [
            label,
            serial("2026-11-20"),
            serial("2026-12-14"),
            serial("2026-12-17"),
            q,
            unit,
            25.0,
            "asian",
        ]
        for label, q, unit in ((1, 1.0, "LOT"), (2, 1000.0, "BBL"), (3, 42000.0, "GAL"))
    ]
    _, prepared, results = ete_state(
        ete["index"],
        ete["template"],
        lines,
        "2026-12-16",
        {"2026-12-14": 26.0, "2026-12-15": 27.0},
        (28.0, 29.0),
        ETE_DATED,
    )
    assert valued(results) == (pytest.approx(2_835), 0.0, pytest.approx(1.5))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))[2:]
    assert [line[2] for line in slots] == [
        serial(d) for d in ("2026-12-14", "2026-12-15", "2026-12-16", "2026-12-17")
    ]
    assert [line[7] for line in slots] == [0.0, 0.0, pytest.approx(0.75), pytest.approx(0.75)]
    assert spilled(ENTRY["util_ReadHandle"](results))[2][8:10] == [
        pytest.approx(630.0),
        pytest.approx(1.5),
    ]


@pytest.mark.parametrize(
    ("quote", "settled", "fixed", "live", "quantity", "coefficient", "mark"),
    [
        (("CENT", "GAL"), "USD", 25.0, 28.0, 42_000.0, 420.0, 1_260.0),
        (("USD", "GAL"), "USD", 0.25, 0.28, 42_000.0, 42_000.0, 1_260.0),
        (("USD", "BBL"), "USD", 10.5, 11.76, 1_000.0, 1_000.0, 1_260.0),
        (("CENT", "BBL"), "USD", 1_050.0, 1_176.0, 1_000.0, 10.0, 1_260.0),
        (("CENT", "GAL"), "CENT", 25.0, 28.0, 42_000.0, 42_000.0, 126_000.0),
    ],
    ids=[
        "CENT/GAL in USD",
        "USD/GAL in USD",
        "USD/BBL in USD",
        "CENT/BBL in USD",
        "CENT/GAL in CENT",
    ],
)
def test_a_lot_is_one_lot_in_every_quote_and_settlement_unit(
    quote: tuple[str, str],
    settled: str,
    fixed: float,
    live: float,
    quantity: float,
    coefficient: float,
    mark: float,
) -> None:
    # The same physical lot and the same three cents a gallon of move: the coefficient and the
    # mark restate in each unit, the lot delta is one throughout, and the index reads back the
    # lot's quantity in the quote unit and its coefficient in the settlement currency.
    index = ete_index(quote, settled)
    line: list[object] = [1.0, serial("2026-11-20"), "Z26", 1.0, "LOT", fixed, "lastday"]
    _, _, results = ete_state(index, ete_template(), [line], "2026-12-02", {}, (live, live))
    assert valued(results) == (pytest.approx(mark), 0.0, pytest.approx(1))
    assert spilled(ENTRY["_ReportValues"](results))[2][2] == settled
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "lots of LOT (1000 BBL)"
    shown = spilled(ENTRY["util_ReadHandle"](index))
    assert shown[0][6:] == [
        "reporting_lot",
        "lot_size",
        "lot_unit",
        "lot_quote_quantity",
        "lot_coefficient",
    ]
    assert shown[2][6:] == [
        "LOT",
        1000.0,
        "BBL",
        pytest.approx(quantity),
        pytest.approx(coefficient),
    ]
    # The results read back the two units the risk numbers are in, on every row: the same
    # lot delta under the same heading is 420 or 42,000 of sensitivity, and the units say which.
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[2][10:] == [
        f"{settled} per {quote[0]}/{quote[1]}",
        "lots of LOT (1000 BBL)",
        0.0,
        0.0,
        0.0,
        settled,  # the reserves' currency, the settlement currency
    ]


def test_the_reporting_lot_is_the_indexs_choice_and_scales_the_lots_alone() -> None:
    # Ten thousand and 2,500 MMBTU, entered in MMBTU on an index whose first specification is the
    # unit itself: against the 10,000 lot, one lot and a quarter; against the 2,500 lot, four and
    # one; the mark and the sensitivity the same under either, the choice the index's and never a
    # row's or the first row's.
    lots = [("MMBTU", 1.0), ("NYMEX NG", 10_000.0), ("ICE PHH", 2_500.0)]
    fields = {**NG_TEMPLATE, "quantity_unit": "MMBTU"}
    for reporting_lot, size, expected in (
        ("NYMEX NG", 10000, (1.0, 0.25)),
        ("ICE PHH", 2500, (4.0, 1.0)),
    ):
        index, _ = an_index(
            "Henry Hub NYMEX", NG_CONTRACTS, NG_HOLIDAYS, lots, reporting_lot=reporting_lot
        )
        template = ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*fields.values()))
        history = a_history(index, "2026-10-29", "2026-11-24", NG_HOLIDAYS, {})
        market = a_market(history, "Henry Hub NYMEX", 3.20, 3.50)
        for quantity, lots_reported in zip((10_000.0, 2_500.0), expected, strict=True):
            line: list[object] = [5.0, serial("2026-09-24"), "Z26", quantity, 3.1]
            trades = ENTRY["_CreateTrades"](index, row(*NG_HEADERS), rows(line), template)
            results = str(
                ENTRY["_EvaluateTrades"](ENTRY["_PrepareTrades"](trades, history), market)
            )
            assert valued(results) == (
                pytest.approx(quantity / 10),
                0.0,
                pytest.approx(lots_reported),
            )
            table = spilled(ENTRY["util_ReadHandle"](results))
            assert table[2][7] == pytest.approx(quantity)  # the sensitivity, whatever the lot
            unit = spilled(ENTRY["_ReportRisk"](results))[2][1]
            assert unit == f"lots of {reporting_lot} ({size} MMBTU)"


def test_every_method_fully_live_reports_one_lot_and_a_strip_a_lot_a_month(
    ete: dict[str, Any],
) -> None:
    lines: list[list[object]] = [
        [label, serial("2026-11-20"), "Z26", 1.0, "LOT", 25.0, method]
        for label, method in (
            (12, "lastday"),
            (16, "penultimate"),
            (20, "last3day"),
            (19, "asian"),
        )
    ]
    _, _, results = ete_state(ete["index"], ete["template"], lines, "2026-12-01", {}, (28.0, 29.0))
    assert valued(results) == (pytest.approx(4 * 1_260), 0.0, pytest.approx(4))
    for line in lines:
        _, _, alone = ete_state(
            ete["index"], ete["template"], [line], "2026-12-01", {}, (28.0, 29.0)
        )
        assert valued(alone) == (pytest.approx(1_260), 0.0, pytest.approx(1)), line[0]
    # A lot a month over Z26-F27, F27 at 29: a lot of delta on each contract, two in all.
    strip: list[object] = [26.0, serial("2026-11-20"), "Z26-F27", 1.0, "LOT", 25.0, "lastday"]
    _, _, over_two = ete_state(
        ete["index"], ete["template"], [strip], "2026-12-02", {}, (28.0, 29.0)
    )
    assert valued(over_two) == (pytest.approx(1_260 + 1_680), 0.0, pytest.approx(2))
    table = spilled(ENTRY["util_ReadHandle"](over_two))[2:]
    assert [(line[0], line[9]) for line in table] == [
        ("Z26", pytest.approx(1.0)),
        ("F27", pytest.approx(1.0)),
    ]
    # Twenty barrels a calendar day over 16 to 20 December, five covered days for three weekday
    # observations: a hundred barrels, a tenth of a lot, whatever the days observed.
    dated: list[object] = [
        4.0,
        serial("2026-11-20"),
        serial("2026-12-16"),
        serial("2026-12-20"),
        20.0,
        "BBL",
        25.0,
        "asian",
        "calday",
    ]
    _, prepared, by_day = ete_state(
        ete["index"],
        ete["by_row"],
        [dated],
        "2026-12-02",
        {},
        (28.0, 29.0),
        (*ETE_DATED, "quantity_per"),
    )
    assert valued(by_day) == (pytest.approx(126), 0.0, pytest.approx(0.1))
    assert len(spilled(ENTRY["util_ReadHandle"](prepared))) == 2 + 3


def test_lots_leave_with_the_weights_and_none_stays_after_payment(ete: dict[str, Any]) -> None:
    # New Year's Day, Z26 fixed at 30 on the 31st and its payment on Monday the 4th still ahead:
    # 2,100 of mark and no lots; the 4th, the 2,100 cash, nothing live and no lots.
    line = ETE_ROWS[0]
    _, _, unpaid = ete_state(
        ete["index"], ete["template"], [line], "2027-01-01", {"2026-12-31": 30.0}, (29.0,)
    )
    assert valued(unpaid) == (pytest.approx(2_100), 0.0, 0.0)
    _, _, paid = ete_state(
        ete["index"], ete["template"], [line], "2027-01-04", {"2026-12-31": 30.0}, (29.0,)
    )
    assert valued(paid) == (0.0, pytest.approx(2_100), 0.0)


def test_lot_deltas_are_signed_fractional_and_add_up_in_any_order(ete: dict[str, Any]) -> None:
    def state(lines: list[list[object]]) -> tuple[float, float, float]:
        return valued(
            ete_state(ete["index"], ete["template"], lines, "2026-12-02", {}, (28.0, 29.0))[2]
        )

    sold: list[object] = [1.0, serial("2026-11-20"), "Z26", -1.0, "LOT", 25.0, "lastday"]
    assert state([sold]) == (pytest.approx(-1_260), 0.0, pytest.approx(-1))
    one_barrel: list[object] = [2.0, serial("2026-11-20"), "Z26", 1.0, "BBL", 25.0, "lastday"]
    assert state([one_barrel]) == (pytest.approx(1.26), 0.0, pytest.approx(0.001))
    kept: list[object] = [11.0, serial("2026-11-20"), "Z26", 0.0, "LOT", 25.0, "lastday"]
    three = (pytest.approx(3_780), 0.0, pytest.approx(3))
    assert state([*ETE_ROWS, kept]) == three and state(ETE_ROWS[::-1]) == three
    assert state([ETE_ROWS[0], ETE_ROWS[0]]) == (pytest.approx(2_520), 0.0, pytest.approx(2))
    offset: list[object] = [2.0, serial("2026-11-20"), "Z26", -1000.0, "BBL", 25.0, "lastday"]
    assert state([ETE_ROWS[0], offset]) == (0.0, 0.0, 0.0)


# --- calendar-driven asian references, calendar-driven-asian-references.md ---------------------
# The ticket's WTI-like index through the seam: Z26, F27, G27 and H27 expiring on 20 November,
# 21 December, 20 January and 22 February, the market and the payment calendar closed on
# 25 December and New Year's Day, dollars a barrel settled in dollars, a barrel the specification
# entered and a thousand-barrel LOT the reporting lot; the asian template paying +2bd; and the
# booking of 18 to 28 December, 1,200 barrels at 70, by its dates.
WTI_HOLIDAYS = ["2026-12-25", "2027-01-01"]
WTI_WINDOW = ("2026-12-18", "2026-12-21", "2026-12-22", "2026-12-23", "2026-12-24", "2026-12-28")
WTI_SETTLES = {
    **dict(zip(WTI_WINDOW, (71.0, 73.0, 74.0, 76.0, 75.0, 77.0), strict=True)),
    "2026-12-29": 78.0,
}
WTI_ROW: list[object] = [
    23.0,
    serial("2026-11-20"),
    serial("2026-12-18"),
    serial("2026-12-28"),
    1_200.0,
    70.0,
]


def wti_template(lag: str = "+2bd", method: str | None = "asian", unit: str = "BBL") -> str:
    """The asian template in barrels, or the unit given, cleared and financial, paying that lag
    on the WTI-like calendar; with no method, a template that leaves the method to the rows."""
    calendar = ENTRY["_CreateHolidayCalendar"](column([serial(d) for d in WTI_HOLIDAYS]))
    fields = [f for f in PEN_FIELDS if method is not None or f != "schedule_method"]
    values: list[object] = [unit, "month", method, "cleared", "financial", "Prototype Clearing"]
    values = [v for v in values if v is not None] + [lag, calendar]
    return str(ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*values)))


@pytest.fixture(scope="module")
def wti() -> dict[str, Any]:
    index, _ = an_index(
        "WTI",
        [
            ("Z26", "2026-11-20"),
            ("F27", "2026-12-21"),
            ("G27", "2027-01-20"),
            ("H27", "2027-02-22"),
        ],
        WTI_HOLIDAYS,
        [("BBL", 1.0), ("LOT", 1_000.0)],
        ("VOLUME", "BBL"),
        reporting_lot="LOT",
    )
    template = wti_template()
    return {
        "index": index,
        "template": template,
        "trades": ENTRY["_CreateTrades"](index, row(*DATE_HEADERS), rows(WTI_ROW), template),
    }


def wti_state(
    wti: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    trades: object | None = None,
    settles: dict[str, float] = WTI_SETTLES,
) -> tuple[str, str, str]:
    """One state: the history valued that day from Monday 23 November, the first priced day after
    Z26 expires, every unnamed settle 3.00, the market quoting from the first unfixed day's contract
    on, the batch prepared and evaluated."""
    history = a_history(wti["index"], "2026-11-23", as_of, WTI_HOLIDAYS, settles)
    market = a_market(history, "WTI", *quotes)
    prepared = ENTRY["_PrepareTrades"](wti["trades"] if trades is None else trades, history)
    return history, str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


@pytest.mark.parametrize(
    ("as_of", "quotes", "mark", "cash", "lots", "by_contract"),
    [
        ("2026-12-18", (72.0, 75.0), 4_800, 0, 1.2, (0.4, 0.8)),
        ("2026-12-19", (72.0, 75.0), 4_600, 0, 1.0, (0.2, 0.8)),
        ("2026-12-22", (75.0,), 4_800, 0, 0.8, (0.0, 0.8)),
        ("2026-12-22", (76.0,), 5_600, 0, 0.8, (0.0, 0.8)),
        ("2026-12-29", (75.0,), 5_200, 0, 0.0, (0.0, 0.0)),
        ("2026-12-30", (75.0,), 0, 5_200, 0.0, (0.0, 0.0)),
    ],
    ids=[
        "18 Dec, all live",
        "19 Dec, the first fixed",
        "22 Dec, both F27 days fixed",
        "22 Dec, G27 at 76",
        "29 Dec, all fixed, unpaid",
        "30 Dec, paid",
    ],
)
def test_the_wti_asian_values_on_the_sheet_as_the_ticket_says(
    wti: dict[str, Any],
    as_of: str,
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    lots: float,
    by_contract: tuple[float, float],
) -> None:
    # The six states of the ticket's table through the registered functions, the vector starting
    # at the first unfixed day's contract, F27 through the 21st and G27 alone from the 22nd; the
    # results read back with F27 then G27 as the pricing contract and Z26 as the booked one on
    # every row, the payment day the 30th, and each contract's lots beside its slots.
    _, _, results = wti_state(wti, as_of, quotes)
    assert valued(results) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(lots))
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "lots of LOT (1000 BBL)"
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[0][:4] == [
        "pricing_contract",
        "booked_contract",
        "observation_date",
        "payment_date",
    ]
    slots = table[2:]
    assert [line[0] for line in slots] == ["F27", "F27", "G27", "G27", "G27", "G27"]
    assert [line[1] for line in slots] == ["Z26"] * 6  # booked as Z26 throughout
    assert [line[2] for line in slots] == [serial(d) for d in WTI_WINDOW]
    assert [line[3] for line in slots] == [serial("2026-12-30")] * 6
    assert [line[9] for line in slots] == [pytest.approx(by_contract[0])] * 2 + [
        pytest.approx(by_contract[1])
    ] * 4


def test_two_groups_on_one_pricing_day_read_back_apart_by_their_booked_contracts(
    wti: dict[str, Any],
) -> None:
    # A December asian booked as Z26 over the 1st to the 21st and a lastday F27 over its own month
    # both observe Monday 21 December, F27's expiry, off F27, and both pay the 22nd at +1bd: the
    # results spill's two rows of that day read F27 as the pricing contract and Z26 then F27 as the
    # booked one, and the pair values as its singletons summed, 5,000 of mark and 2.5 lots on
    # 1 December at 72 and 75.
    template = wti_template("+1bd", None)
    headers = row(*DATE_HEADERS, "schedule_method")
    asian: list[object] = [
        1.0,
        *WTI_ROW[1:2],
        serial("2026-12-01"),
        serial("2026-12-21"),
        1_500.0,
        70.0,
        "asian",
    ]
    future: list[object] = [
        6.0,
        *WTI_ROW[1:2],
        serial("2027-01-01"),
        serial("2027-01-31"),
        1_000.0,
        70.0,
        "lastday",
    ]
    pair = ENTRY["_CreateTrades"](wti["index"], headers, rows(asian, future), template)
    _, _, both = wti_state(wti, "2026-12-01", (72.0, 75.0), pair)
    slots = spilled(ENTRY["util_ReadHandle"](both))[2:]
    assert len(slots) == 16  # the asian's fifteen days and the future's one
    assert slots[14][:4] == ["F27", "Z26", serial("2026-12-21"), serial("2026-12-22")]
    assert slots[15][:4] == ["F27", "F27", serial("2026-12-21"), serial("2026-12-22")]
    assert valued(both) == (pytest.approx(5_000), 0.0, pytest.approx(2.5))
    alone = [
        wti_state(wti, "2026-12-01", (72.0, 75.0), one)[2]
        for one in (
            ENTRY["_CreateTrades"](wti["index"], headers, rows(asian), template),
            ENTRY["_CreateTrades"](wti["index"], headers, rows(future), template),
        )
    ]
    assert [valued(one) for one in alone] == [
        (pytest.approx(3_000), 0.0, pytest.approx(1.5)),
        (pytest.approx(2_000), 0.0, pytest.approx(1.0)),
    ]


def test_a_code_entry_and_the_dates_of_the_whole_month_agree_on_the_wti_asian(
    wti: dict[str, Any],
) -> None:
    # Z26 typed as a code and 1 to 31 December typed as dates book the same December: 22 days,
    # 15 priced by F27 and 7 by G27, 100 barrels a day of 2,200, the same slots read back, the
    # same payment on 5 January and the same 6,500 of mark at 72 and 75 on 1 December, 2.2 lots,
    # 1.5 on F27 and 0.7 on G27.
    by_code = ENTRY["_CreateTrades"](
        wti["index"],
        row(*NG_HEADERS),
        rows([26.0, serial("2026-11-20"), "Z26", 2_200.0, 70.0]),
        wti["template"],
    )
    by_dates = ENTRY["_CreateTrades"](
        wti["index"],
        row(*DATE_HEADERS),
        rows(
            [26.0, serial("2026-11-20"), serial("2026-12-01"), serial("2026-12-31"), 2_200.0, 70.0]
        ),
        wti["template"],
    )
    _, prepared_by_code, code = wti_state(wti, "2026-12-01", (72.0, 75.0), by_code)
    _, prepared_by_dates, dated = wti_state(wti, "2026-12-01", (72.0, 75.0), by_dates)
    slots = spilled(ENTRY["util_ReadHandle"](prepared_by_code))
    assert slots == spilled(ENTRY["util_ReadHandle"](prepared_by_dates))
    assert [line[0] for line in slots[2:]] == ["F27"] * 15 + ["G27"] * 7
    assert [line[1] for line in slots[2:]] == ["Z26"] * 22
    assert [line[3] for line in slots[2:]] == [serial("2027-01-05")] * 22
    assert valued(code) == valued(dated) == (pytest.approx(6_500), 0.0, pytest.approx(2.2))
    assert [line[9] for line in spilled(ENTRY["util_ReadHandle"](code))[2:]] == [
        pytest.approx(1.5)
    ] * 15 + [pytest.approx(0.7)] * 7


# --- delta by day, month and year, daily-risk-vector.md ------------------------------------------
# The ticket's month-aligned index through the seam, X26 bounding the calendar, Z26 expiring
# 31 December and F27 29 January, closed on 25 December and New Year's Day, a barrel and a
# thousand-barrel LOT; a template leaving the method to the rows at +1bd; 22 LOT of a December
# asian and 3 LOT of a Z26 penultimate at 70; every settle 75 and the quote 75.
DECEMBER_PRICING_DAYS = [
    str(d)
    for d in np.arange(np.datetime64("2026-12-01"), np.datetime64("2027-01-01"))
    if np.is_busday(d, holidays=np.array(WTI_HOLIDAYS, dtype="datetime64[D]"))
]
SEVENTY_FIVE = {d: 75.0 for d in DECEMBER_PRICING_DAYS}
DELTA_HEADERS = ["bucket_start", "delta", "delta_unit", "as_of"]
DELTA_TYPES = ["datetime64[D]", "float64", "str", "datetime64[D]"]
LOT_UNIT = "lots of LOT (1000 BBL)"


@pytest.fixture(scope="module")
def monthly() -> dict[str, Any]:
    index, _ = an_index(
        "MONTHLY",
        [("X26", "2026-11-30"), ("Z26", "2026-12-31"), ("F27", "2027-01-29")],
        WTI_HOLIDAYS,
        [("BBL", 1.0), ("LOT", 1_000.0)],
        ("VOLUME", "BBL"),
        reporting_lot="LOT",
    )
    template = wti_template("+1bd", None, "LOT")
    headers = row(*NG_HEADERS, "schedule_method")
    asian: list[object] = [1.0, serial("2026-11-20"), "Z26", 22.0, 70.0, "asian"]
    pen: list[object] = [16.0, serial("2026-11-20"), "Z26", 3.0, 70.0, "penultimate"]
    return {
        "index": index,
        "template": template,
        "headers": headers,
        "trades": ENTRY["_CreateTrades"](index, headers, rows(asian, pen), template),
        "reversed": ENTRY["_CreateTrades"](index, headers, rows(pen, asian), template),
    }


def monthly_state(
    monthly: dict[str, Any], as_of: str, trades: object | None = None
) -> tuple[str, str, str]:
    history = a_history(monthly["index"], "2026-11-30", as_of, WTI_HOLIDAYS, SEVENTY_FIVE)
    market = a_market(history, "MONTHLY", 75.0)
    prepared = ENTRY["_PrepareTrades"](monthly["trades"] if trades is None else trades, history)
    return history, str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


@pytest.mark.parametrize(
    ("as_of", "live", "mark", "cash"),
    [
        ("2026-12-01", 25, 125_000, 0),
        ("2026-12-30", 5, 125_000, 0),
        ("2026-12-31", 1, 110_000, 15_000),
        ("2027-01-01", 0, 110_000, 15_000),
        ("2027-01-04", 0, 0, 125_000),
    ],
    ids=["1 Dec", "30 Dec", "31 Dec", "1 Jan", "4 Jan"],
)
def test_the_delta_reports_by_day_month_and_year_on_the_sheet_as_the_ticket_says(
    monthly: dict[str, Any], as_of: str, live: float, mark: float, cash: float
) -> None:
    # The ticket's table through the registered functions: the day view 22 rows, December's
    # pricing days with a lot each and 4 on the 30th while live and zero once fixed, the month
    # view one row from 1 December and the year view one row from 1 January 2026, both the live
    # lots; the unit and the valuation day on every row; the selector left out the day view; the
    # rows reversed the same.
    for trades in (None, monthly["reversed"]):
        _, _, results = monthly_state(monthly, as_of, trades)
        assert valued(results) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(live))
        by_day = spilled(ENTRY["_ReportDelta"](results, "day"))
        assert spilled(ENTRY["_ReportDelta"](results, bridge.MISSING)) == by_day
        assert by_day[:2] == [DELTA_HEADERS, DELTA_TYPES]
        assert [line[0] for line in by_day[2:]] == [serial(d) for d in DECEMBER_PRICING_DAYS]
        expected = [
            0.0 if d < as_of else (4.0 if d == "2026-12-30" else 1.0) for d in DECEMBER_PRICING_DAYS
        ]
        assert [line[1] for line in by_day[2:]] == [pytest.approx(x) for x in expected]
        assert [line[2:] for line in by_day[2:]] == [[LOT_UNIT, serial(as_of)]] * 22
        by_month = spilled(ENTRY["_ReportDelta"](results, "month"))
        assert by_month == [
            DELTA_HEADERS,
            DELTA_TYPES,
            [serial("2026-12-01"), pytest.approx(live), LOT_UNIT, serial(as_of)],
        ]
        by_year = spilled(ENTRY["_ReportDelta"](results, "year"))
        assert by_year[2] == [serial("2026-01-01"), pytest.approx(live), LOT_UNIT, serial(as_of)]
        assert sum(cast(float, line[1]) for line in by_day[2:]) == pytest.approx(
            spilled(ENTRY["_ReportRisk"](results))[2][0]
        )


def test_the_delta_report_refuses_a_bucket_that_is_none_of_the_three(
    monthly: dict[str, Any],
) -> None:
    _, prepared, results = monthly_state(monthly, "2026-12-01")
    expected = "expected day, month or year"
    assert ENTRY["_ReportDelta"](results, "quarter") == (
        f"#ERROR _ReportDelta: ValueError: bucket is 'quarter', {expected}"
    )
    assert ENTRY["_ReportDelta"](results, "Day") == (
        f"#ERROR _ReportDelta: ValueError: bucket is 'Day', {expected}"
    )
    assert (
        ENTRY["_ReportDelta"](results, None)
        == "#ERROR _ReportDelta: bucket is blank, expected text"
    )
    assert ENTRY["_ReportDelta"](results, "") == (
        "#ERROR _ReportDelta: bucket is empty text, expected text"
    )
    assert ENTRY["_ReportDelta"](results, 1.0) == (
        "#ERROR _ReportDelta: bucket is number 1.0, expected text"
    )
    assert ENTRY["_ReportDelta"](None, bridge.MISSING) == (
        "#ERROR _ReportDelta: results is blank, expected trade results handle"
    )
    assert ENTRY["_ReportDelta"](prepared, bridge.MISSING) == (
        f"#ERROR _ReportDelta: results is prepared trades handle {prepared!r}, "
        "expected trade results handle"
    )


def test_the_six_day_asian_reports_its_days_month_and_year_and_a_tick_changes_none(
    wti: dict[str, Any],
) -> None:
    # The rolling asian's six days at 0.2 a day on 18 December, one December bucket and one 2026
    # bucket of 1.2; a tick over the same preparation spills the same three views; after the roll
    # on the 22nd the first two days read zero and the axes stand.
    history, prepared, results = wti_state(wti, "2026-12-18", (72.0, 75.0))
    by_day = spilled(ENTRY["_ReportDelta"](results, bridge.MISSING))
    assert [line[0] for line in by_day[2:]] == [serial(d) for d in WTI_WINDOW]
    assert [line[1] for line in by_day[2:]] == [pytest.approx(0.2)] * 6
    assert spilled(ENTRY["_ReportDelta"](results, "month"))[2] == [
        serial("2026-12-01"),
        pytest.approx(1.2),
        LOT_UNIT,
        serial("2026-12-18"),
    ]
    assert spilled(ENTRY["_ReportDelta"](results, "year"))[2][:2] == [
        serial("2026-01-01"),
        pytest.approx(1.2),
    ]
    ticked = ENTRY["_EvaluateTrades"](prepared, a_market(history, "WTI", 73.0, 76.0))
    for bucket in ("day", "month", "year"):
        assert spilled(ENTRY["_ReportDelta"](str(ticked), bucket)) == spilled(
            ENTRY["_ReportDelta"](results, bucket)
        )
    _, _, rolled = wti_state(wti, "2026-12-22", (75.0,))
    rolled_days = spilled(ENTRY["_ReportDelta"](rolled, bridge.MISSING))[2:]
    assert [line[0] for line in rolled_days] == [serial(d) for d in WTI_WINDOW]
    assert [line[1] for line in rolled_days] == [
        pytest.approx(x) for x in (0, 0, 0.2, 0.2, 0.2, 0.2)
    ]


# --- an IFERC basis future on the sheet, iferc-basis-futures.md -----------------------------
# The ticket's Waha-like index through the seam: X26, Z26 and F27 with their last trading and
# publication days, dollars an MMBtu, a 2,500 MMBtu LOT and a bare MMBTU, the LOT reported and no
# pricing calendar; a payment calendar closing New Year's Day; the template cleared, financial,
# lastday, LOT a month at +3bd; WAH001, 1 LOT of Z26 at -0.50 booked 30 November, paying
# 3 December.
WAHA_MONTHS = [
    ("X26", "2026-10-30", "2026-11-02"),
    ("Z26", "2026-11-30", "2026-12-01"),
    ("F27", "2026-12-31", "2027-01-04"),
]
WAHA_LOT = "lots of LOT (2500 MMBTU)"
WAHA_X26 = {"X26": -0.40}  # the earlier month's index, which every December history must hold
WAHA_Z26 = {"X26": -0.40, "Z26": -0.20}
WAHA_CORRECTED = {"X26": -0.40, "Z26": -0.10}
WAHA_ROW: list[object] = [1001.0, serial("2026-11-30"), "Z26", 1.0, -0.5]


def an_iferc_index(
    name: str, months: list[tuple[str, str, str]], lots: list[tuple[str, float]]
) -> str:
    """An IFERC index through the seam: its months with their last trading and publication days,
    dollars an MMBtu settled in dollars, the specifications given in MMBtu, the first the
    reporting lot, and no pricing calendar."""
    schedule = ENTRY["_CreateIfercSchedule"](
        rows(*[[code] for code, _, _ in months]),
        column([serial(last) for _, last, _ in months]),
        column([serial(published) for _, _, published in months]),
    )
    conventions = ENTRY["_CreateIndexConventions"]("USD", "MMBTU", "USD", "ENERGY", "MMBTU")
    specifications = ENTRY["_CreateContractSpecifications"](
        row("name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"),
        rows(*[[lot, size, "MMBTU", 0.0, 0.0] for lot, size in lots]),
    )
    return str(
        ENTRY["_CreateIndex"](
            name, f"{name} index", schedule, conventions, specifications, bridge.MISSING, lots[0][0]
        )
    )


def an_iferc_history(index: str, as_of: str, indices: dict[str, float]) -> str:
    """The index's history valued on that day with the months' indices given, newest first as the
    fixings creator takes them."""
    codes = list(reversed(indices))
    fixings = ENTRY["_CreateIfercFixings"](
        rows(*[[code] for code in codes]), column([indices[code] for code in codes]), index
    )
    calendar = ENTRY["_CreateCalendar"](ENTRY["_CreateValuationDate"](serial(as_of), 0.5), index)
    return str(ENTRY["_CreateMarketHistory"](calendar, fixings))


@pytest.fixture(scope="module")
def waha() -> dict[str, Any]:
    index = an_iferc_index("WAHA", WAHA_MONTHS, [("LOT", 2_500.0), ("MMBTU", 1.0)])
    pays = ENTRY["_CreateHolidayCalendar"](column([serial("2027-01-01")]))
    fields = {
        "quantity_unit": "LOT",
        "quantity_per": "month",
        "schedule_method": "lastday",
        "route": "cleared",
        "settlement_method": "financial",
        "clearing_house": "ICE Clear Europe",
        "payment_time_lag": "+3bd",
        "payment_holiday_calendar": pays,
    }
    template = ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*fields.values()))
    trades = ENTRY["_CreateTrades"](index, row(*NG_HEADERS), rows(WAHA_ROW), template)
    return {"index": index, "pays": pays, "fields": fields, "template": template, "trades": trades}


def waha_state(
    waha: dict[str, Any], as_of: str, indices: dict[str, float], quotes: tuple[float, ...]
) -> tuple[str, str, str]:
    """One state: the history valued on that day with those months' indices, the market quoting
    from the first unfixed month on, the batch prepared and evaluated; the history, the prepared
    and the results handles."""
    history = an_iferc_history(waha["index"], as_of, indices)
    market = a_market(history, "WAHA", *quotes)
    prepared = ENTRY["_PrepareTrades"](waha["trades"], history)
    return history, str(prepared), str(ENTRY["_EvaluateTrades"](prepared, market))


@pytest.mark.parametrize(
    ("as_of", "indices", "quotes", "mark", "cash", "live"),
    [
        ("2026-11-30", WAHA_X26, (-0.30, -0.10), 500, 0, 1),
        ("2026-12-01", WAHA_X26, (-0.30, -0.10), 500, 0, 1),
        ("2026-12-01", WAHA_X26, (-0.25, -0.10), 625, 0, 1),
        ("2026-12-02", WAHA_Z26, (-0.10,), 750, 0, 0),
        ("2026-12-03", WAHA_Z26, (-0.10,), 0, 750, 0),
        ("2026-12-02", WAHA_CORRECTED, (-0.10,), 1_000, 0, 0),
    ],
    ids=[
        "30 Nov, booked, live at -0.30",
        "1 Dec, publication day, live at -0.30",
        "1 Dec, a tick to -0.25",
        "2 Dec, fixed at -0.20 and unpaid",
        "3 Dec, paid",
        "2 Dec, the index corrected to -0.10",
    ],
)
def test_the_waha_basis_future_values_on_the_sheet_as_the_ticket_says(
    waha: dict[str, Any],
    as_of: str,
    indices: dict[str, float],
    quotes: tuple[float, ...],
    mark: float,
    cash: float,
    live: int,
) -> None:
    # The ticket's table cell to cell: the mark, the cash and the lots; the one slot read back as
    # Z26 pricing and booked, observed 1 December and paying 3 December, fixed the day after
    # publication and settled on the payment day; the delta by day one row, 1 December, the lots
    # while live and zero after, the lot unit and the valuation day beside it, the month and the
    # year one row each.
    _, prepared, results = waha_state(waha, as_of, indices, quotes)
    assert valued(results) == (pytest.approx(mark), pytest.approx(cash), pytest.approx(live))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert slots[0] == [
        "pricing_contract",
        "booked_contract",
        "observation_date",
        "payment_date",
        "is_fixed",
        "is_settled",
        "live_coefficient",
        "live_lots",
    ]
    assert slots[2] == [
        "Z26",
        "Z26",
        serial("2026-12-01"),
        serial("2026-12-03"),
        live == 0,
        as_of >= "2026-12-03",
        2_500.0 * live,
        float(live),
    ]
    by_day = spilled(ENTRY["_ReportDelta"](results, bridge.MISSING))
    assert by_day[2:] == [[serial("2026-12-01"), pytest.approx(live), WAHA_LOT, serial(as_of)]]
    assert spilled(ENTRY["_ReportDelta"](results, "month"))[2][:2] == [
        serial("2026-12-01"),
        pytest.approx(live),
    ]
    assert spilled(ENTRY["_ReportDelta"](results, "year"))[2][:2] == [
        serial("2026-01-01"),
        pytest.approx(live),
    ]


def test_the_waha_batch_reads_back_its_days_and_a_tick_reuses_its_preparation(
    waha: dict[str, Any],
) -> None:
    # The batch's spill carries the resolved payment day, 3 December, beside the lastday method;
    # a tick on 1 December makes new results over the same preparation, 625 against 500, the first
    # standing; the risk report counts in lots of the 2,500 MMBtu LOT with 2,500 dollars per
    # dollar an MMBtu of sensitivity.
    table = spilled(ENTRY["util_ReadHandle"](waha["trades"]))
    headers = [str(name) for name in table[0]]
    at = dict(zip(headers, table[2], strict=True))
    assert headers[13] == "payment_date"
    assert (at["contract_code"], at["schedule_method"]) == ("Z26", "lastday")
    assert (at["payment_time_lag"], at["payment_date"]) == ("+3bd", serial("2026-12-03"))
    history, prepared, results = waha_state(waha, "2026-12-01", WAHA_X26, (-0.30, -0.10))
    ticked = str(ENTRY["_EvaluateTrades"](prepared, a_market(history, "WAHA", -0.25, -0.10)))
    assert ticked != results
    assert valued(ticked) == (pytest.approx(625), 0, pytest.approx(1))
    assert valued(results) == (pytest.approx(500), 0, pytest.approx(1))
    risk = spilled(ENTRY["_ReportRisk"](results))
    assert risk[0][:2] == ["delta_total", "delta_unit"] and risk[2][:2] == [1, WAHA_LOT]


def test_an_iferc_batch_that_is_not_a_financial_lastday_one_is_refused_when_made(
    waha: dict[str, Any],
) -> None:
    physical = {
        **{
            key: value
            for key, value in waha["fields"].items()
            if key not in ("payment_time_lag", "payment_holiday_calendar")
        },
        "settlement_method": "physical",
    }
    template = ENTRY["_CreateTradeTemplate"]("future", row(*physical), row(*physical.values()))
    assert ENTRY["_CreateTrades"](waha["index"], row(*NG_HEADERS), rows(WAHA_ROW), template) == (
        "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' "
        "on an IFERC index; an IFERC basis future is cash settled on its month's published index"
    )
    by_row = {key: value for key, value in waha["fields"].items() if key != "schedule_method"}
    template = ENTRY["_CreateTradeTemplate"]("future", row(*by_row), row(*by_row.values()))
    assert ENTRY["_CreateTrades"](
        waha["index"],
        row(*NG_HEADERS, "schedule_method"),
        rows([*WAHA_ROW, "asian"]),
        template,
    ) == (
        "#ERROR _CreateTrades: ValueError: schedule_method of trade 1001 at row 1 is 'asian', "
        "expected 'lastday' on an IFERC index; an IFERC month has one index, published once"
    )


# --- numeric trade IDs on the sheet, numeric-trade-ids.md -----------------------------------
# The ticket's rows through the registered functions: numbers in, numbers back, the 15 digits
# exact, the instrument saying number, a template's ID on every row, and the seam's own words for
# text, a boolean, a blank and empty text before the library's for a fraction or a sixteenth digit.
ID_ROWS: list[list[object]] = [
    [123456.0, serial("2026-10-09"), "Z26", 1.0, 3.0],
    [123457.0, serial("2026-10-09"), "F27", -2.0, 3.1],
    [123456.0, serial("2026-10-09"), "Z26", 1.0, 3.0],
]


def test_numeric_ids_cross_the_seam_and_read_back_as_numbers(ng: dict[str, Any]) -> None:
    trades = ENTRY["_CreateTrades"](ng["index"], row(*NG_HEADERS), rows(*ID_ROWS), ng["template"])
    table = spilled(ENTRY["util_ReadHandle"](trades))
    assert table[0][1] == "trade_id" and table[1][1] == "int64"
    assert [line[1] for line in table[2:]] == [123456.0, 123457.0, 123456.0]
    assert [line[0] for line in table[2:]] == [1.0, 2.0, 3.0]
    big = ENTRY["_CreateTrades"](
        ng["index"],
        row(*NG_HEADERS),
        rows(
            [999_999_999_999_999.0, serial("2026-10-09"), "Z26", 1.0, 3.0],
            [-999_999_999_999_999.0, serial("2026-10-09"), "F27", 1.0, 3.0],
            [0.0, serial("2026-10-09"), "Z26", 1.0, 3.0],
        ),
        ng["template"],
    )
    assert [line[1] for line in spilled(ENTRY["util_ReadHandle"](big))[2:]] == [
        999_999_999_999_999.0,
        -999_999_999_999_999.0,
        0.0,
    ]
    shown = spilled(ENTRY["_ShowInstrument"]("future"))
    assert shown[4][1] == "number" and shown[5][1] == "a whole number of at most 15 digits"


def test_a_templates_numeric_id_reads_back_as_a_number_and_reaches_every_row(
    ng: dict[str, Any],
) -> None:
    fields = {**NG_TEMPLATE, "trade_id": 77.0}
    template = ENTRY["_CreateTradeTemplate"]("future", row(*fields), row(*fields.values()))
    shown = spilled(ENTRY["util_ReadHandle"](template))
    at = shown[0].index("trade_id")
    assert (shown[1][at], shown[2][at]) == ("float64", 77.0)
    trades = ENTRY["_CreateTrades"](
        ng["index"], row(*NG_HEADERS[1:]), rows(*[line[1:] for line in ID_ROWS]), template
    )
    assert [line[1] for line in spilled(ENTRY["util_ReadHandle"](trades))[2:]] == [77.0] * 3
    assert ENTRY["_CreateTradeTemplate"](
        "future", row(*fields), row(*{**fields, "trade_id": 12.5}.values())
    ) == (
        "#ERROR _CreateTradeTemplate: ValueError: trade_id is 12.5, expected a whole number of at "
        "most 15 digits"
    )
    assert ENTRY["_CreateTrades"](ng["index"], row(*NG_HEADERS), rows(*ID_ROWS), template) == (
        "#ERROR _CreateTrades: ValueError: trade_id is supplied by the template and by the ticket, "
        "expected by one of them"
    )


@pytest.mark.parametrize(
    ("cell", "message"),
    [
        (
            "NG-001",
            "#ERROR _CreateTrades: trade_rows cell (1, 1) is text 'NG-001', expected number",
        ),
        (True, "#ERROR _CreateTrades: trade_rows cell (1, 1) is boolean TRUE, expected number"),
        (
            "",
            "#ERROR _CreateTrades: trade_rows cell (1, 1) is empty text, expected number",
        ),
        (
            None,
            "#ERROR _CreateTrades: trade_rows cell (1, 1) is blank, expected number",
        ),
        (
            123456.5,
            "#ERROR _CreateTrades: ValueError: trade_id row 1 is 123456.5, expected a whole "
            "number of at most 15 digits",
        ),
        (
            1e15,
            "#ERROR _CreateTrades: ValueError: trade_id row 1 is 1000000000000000, expected a "
            "whole number of at most 15 digits",
        ),
    ],
    ids=["text", "a boolean", "empty text", "a blank", "a fraction", "a sixteenth digit"],
)
def test_an_id_cell_that_is_not_a_whole_number_fails_in_the_seams_or_the_librarys_words(
    ng: dict[str, Any], cell: object, message: str
) -> None:
    assert (
        ENTRY["_CreateTrades"](
            ng["index"],
            row(*NG_HEADERS),
            rows([cell, serial("2026-10-09"), "Z26", 1.0, 3.0]),
            ng["template"],
        )
        == message
    )


# --- the reserves, reserve-totals.md --------------------------------------------------------------
# The ticket's worked example on the ETE index, cents a gallon settled in dollars: LOT at 10.00 and
# 4.00 a lot, BBL at 0.01 and 0.004 a barrel, GAL free; four December rows, 2 LOT, -2 LOT, 1,000
# BBL and 0 LOT at 25 cents: 50 of brokerage and 20 of clearing, marketing nought, in USD, booked
# when the batch is made and the same through every tick, fixing, correction and payment,
# since #170.
RESERVE_FEES = {"LOT": (10.0, 4.0), "BBL": (0.01, 0.004)}
RESERVE_ROWS: list[list[object]] = [
    [101.0, serial("2026-11-20"), "Z26", 2.0, "LOT", 25.0, "lastday"],
    [102.0, serial("2026-11-20"), "Z26", -2.0, "LOT", 25.0, "lastday"],
    [103.0, serial("2026-11-20"), "Z26", 1000.0, "BBL", 25.0, "lastday"],
    [104.0, serial("2026-11-20"), "Z26", 0.0, "LOT", 25.0, "lastday"],
]
RESERVE_SPILL: list[list[object]] = [
    ["brokerage_reserve", "clearing_reserve", "marketing_reserve", "currency"],
    ["float64", "float64", "float64", "str"],
    [50.0, 20.0, 0.0, "USD"],
]
RESERVE_HEADERS = ["brokerage_reserve", "clearing_reserve", "marketing_reserve", "currency"]


@pytest.fixture(scope="module")
def fees() -> dict[str, Any]:
    return {"index": ete_index(fees=RESERVE_FEES), "template": ete_template()}


def reserved(results: str) -> list[list[object]]:
    return spilled(ENTRY["_ReportReserves"](results))


def test_the_tickets_four_rows_report_fifty_and_twenty_dollars_of_reserves(
    fees: dict[str, Any],
) -> None:
    trades, _, results = ete_state(
        fees["index"], fees["template"], RESERVE_ROWS, "2026-12-02", {}, (28.0, 29.0)
    )
    assert reserved(results) == RESERVE_SPILL
    # The results readback shows the four once, on its one slot row here; the batch's readback
    # carries no reserve, the owner's choice of the evaluated results as the place to read them.
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[0][-4:] == RESERVE_HEADERS
    assert table[1][-4:] == ["float64", "float64", "float64", "str"]
    assert len(table) == 3 and table[2][-4:] == [50.0, 20.0, 0.0, "USD"]
    batch = spilled(ENTRY["util_ReadHandle"](trades))
    assert not any("reserve" in str(header) for header in batch[0])
    # Value and risk are the free rows': the two LOT rows net, the barrels mark three cents on
    # 42,000 gallons, 1,260 dollars, and one lot stands.
    assert valued(results) == (pytest.approx(1_260.0), 0.0, pytest.approx(1.0))


@pytest.mark.parametrize(
    ("method", "slots"), [("lastday", 1), ("penultimate", 1), ("last3day", 3), ("asian", 22)]
)
def test_the_pricing_days_change_no_reserve_and_the_readback_shows_it_once(
    fees: dict[str, Any], method: str, slots: int
) -> None:
    # The same four rows under each method: one, three or December's 22 pricing days a row, the
    # same 50 and 20; the readback's first slot row holds them and every later row a dash.
    lines = [[*line[:-1], method] for line in RESERVE_ROWS]
    _, _, results = ete_state(
        fees["index"], fees["template"], lines, "2026-12-02", {}, (28.0, 29.0)
    )
    assert reserved(results) == RESERVE_SPILL
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert len(table) == 2 + slots
    assert table[2][-4:] == [50.0, 20.0, 0.0, "USD"]
    assert [line[-4:] for line in table[3:]] == [["-", "-", "-", "-"]] * (slots - 1)


def test_one_batch_keeps_its_reserves_through_ticks_fixings_corrections_and_payment(
    fees: dict[str, Any],
) -> None:
    # One batch made once, then 2 December live at 28 and a tick to 31 over the same preparation,
    # 1 January with Z26 fixed at 27 and unpaid, the same day with the fixing corrected to 26.5,
    # and 4 January, paid: the mark and the cash move, the reserves never.
    index = fees["index"]
    trades = str(
        ENTRY["_CreateTrades"](index, row(*ETE_HEADERS), rows(*RESERVE_ROWS), fees["template"])
    )
    live = a_history(index, "2026-11-30", "2026-12-02", ETE_HOLIDAYS, {})
    prepared = str(ENTRY["_PrepareTrades"](trades, live))
    states = [
        str(ENTRY["_EvaluateTrades"](prepared, a_market(live, "ETE", 28.0, 29.0))),
        str(ENTRY["_EvaluateTrades"](prepared, a_market(live, "ETE", 31.0, 29.0))),
    ]
    for as_of, settle in (("2027-01-01", 27.0), ("2027-01-01", 26.5), ("2027-01-04", 27.0)):
        history = a_history(index, "2026-11-30", as_of, ETE_HOLIDAYS, {"2026-12-31": settle})
        again = str(ENTRY["_PrepareTrades"](trades, history))
        states.append(str(ENTRY["_EvaluateTrades"](again, a_market(history, "ETE", 30.0))))
    assert [valued(state)[:2] for state in states] == [
        (pytest.approx(1_260.0), 0.0),
        (pytest.approx(2_520.0), 0.0),  # the tick: six cents on 42,000 gallons
        (pytest.approx(840.0), 0.0),  # fixed at two cents, not yet paid
        (pytest.approx(630.0), 0.0),  # the corrected fixing, a cent and a half
        (0.0, pytest.approx(840.0)),  # paid on 4 January
    ]
    for state in states:
        assert reserved(state) == RESERVE_SPILL


def test_recreating_the_batch_with_other_quantities_or_rates_books_other_reserves(
    fees: dict[str, Any],
) -> None:
    doubled = [[*line[:3], 2 * cast(float, line[3]), *line[4:]] for line in RESERVE_ROWS]
    _, _, results = ete_state(
        fees["index"], fees["template"], doubled, "2026-12-02", {}, (28.0, 29.0)
    )
    assert reserved(results)[2] == [100.0, 40.0, 0.0, "USD"]
    dearer = ete_index(fees={"LOT": (12.0, 5.0), "BBL": (0.02, 0.005)})
    _, _, results = ete_state(dearer, ete_template(), RESERVE_ROWS, "2026-12-02", {}, (28.0, 29.0))
    assert reserved(results)[2] == [68.0, 25.0, 0.0, "USD"]  # 24 + 24 + 20 and 10 + 10 + 5
    by_barrel = ete_index(reporting_lot="BBL", fees=RESERVE_FEES)
    _, _, results = ete_state(
        by_barrel, ete_template(), RESERVE_ROWS, "2026-12-02", {}, (28.0, 29.0)
    )
    assert reserved(results) == RESERVE_SPILL
    assert valued(results)[2] == pytest.approx(1_000.0)  # the lot changed, the reserves did not


def test_a_calday_strip_and_a_partial_asian_month_reserve_on_their_counts(
    fees: dict[str, Any],
) -> None:
    # 2 BBL a calendar day over Z26 and F27, December's 31 days and January's 31, 124 BBL: 1.24
    # and 0.496. A partial December asian of 1,000 BBL on the month basis, the 10th to the 20th,
    # reserves the whole month's 10 and 4, its quantity standing for the month.
    strip: list[list[object]] = [
        [201.0, serial("2026-10-20"), "Z26-F27", 2.0, "BBL", 25.0, "lastday"]
    ]
    _, _, results = ete_state(
        fees["index"], ete_template("calday"), strip, "2026-12-02", {}, (28.0, 29.0)
    )
    assert reserved(results)[2] == [pytest.approx(1.24), pytest.approx(0.496), 0.0, "USD"]
    partial: list[list[object]] = [
        [
            301.0,
            serial("2026-11-20"),
            serial("2026-12-10"),
            serial("2026-12-20"),
            1000.0,
            "BBL",
            25.0,
            "asian",
        ]
    ]
    _, _, results = ete_state(
        fees["index"], fees["template"], partial, "2026-12-02", {}, (28.0, 29.0), ETE_DATED
    )
    assert reserved(results)[2] == [10.0, 4.0, 0.0, "USD"]


def test_reserves_past_the_largest_number_publish_no_batch() -> None:
    # A rate of 1e308 a lot is a number a cell holds; two lots of it are not, and two rows of one
    # lot each sum past it: the batch is refused at creation, naming the category and the row,
    # and nothing is published.
    huge = ete_index(fees={"LOT": (1e308, 0.0)})
    template = ete_template()
    two = [[101.0, serial("2026-11-20"), "Z26", 2.0, "LOT", 25.0, "lastday"]]
    ones = [
        [101.0, serial("2026-11-20"), "Z26", 1.0, "LOT", 25.0, "lastday"],
        [102.0, serial("2026-11-20"), "Z26", 1.0, "LOT", 25.0, "lastday"],
    ]
    live = bridge.live_handles()
    assert ENTRY["_CreateTrades"](huge, row(*ETE_HEADERS), rows(*two), template) == (
        "#ERROR _CreateTrades: ValueError: brokerage reserve of trade 101 at row 1 is inf, "
        "expected a finite amount of USD; 2.0 of 'LOT' at 1e+308 a lot"
    )
    assert ENTRY["_CreateTrades"](huge, row(*ETE_HEADERS), rows(*ones), template) == (
        "#ERROR _CreateTrades: ValueError: the batch has inf of brokerage reserve in all, expected "
        "a finite amount of USD; the components' reserves, each finite, sum past the largest number"
    )
    assert bridge.live_handles() == live


def test_the_reserves_report_refuses_a_blank_and_another_handle_in_the_seams_words(
    fees: dict[str, Any],
) -> None:
    _, prepared, _ = ete_state(
        fees["index"], fees["template"], RESERVE_ROWS, "2026-12-02", {}, (28.0, 29.0)
    )
    assert ENTRY["_ReportReserves"](None) == (
        "#ERROR _ReportReserves: results is blank, expected trade results handle"
    )
    assert ENTRY["_ReportReserves"](prepared) == (
        f"#ERROR _ReportReserves: results is prepared trades handle {prepared!r}, "
        "expected trade results handle"
    )
    assert ENTRY["_ReportReserves"]("x:trade_results:9") == (
        "#ERROR _ReportReserves: results is text 'x:trade_results:9' naming no live object, "
        "expected trade results handle"
    )


# --- contract codes and dates on one ticket, contract-codes-and-dates.md, since #172 ------------
# The ticket's acceptance example: a synthetic financial asian index quoted in USD per BBL, a BBL
# specification of one and a LOT of 1,000 BBL, the reporting lot; weekday pricing, no holiday that
# matters; V26 expiring on Friday 30 October 2026, so that it prices every October pricing day,
# with U26 before it to open the calendar on 30 September; every observation live at 72 on
# 1 October and every fixed price 70; +1bd on the same weekday calendar. Row 1, V26 and no dates,
# 100 BBL a month: 100 BBL over October's 22 pricing days, 200 of mark, 0.10 lots. Row 2, V26
# beside 12 to 31 October, 100 BBL a month: the same 100 BBL over the window's 15 days, 200 and
# 0.10. Row 3, no code, 12 to 20 October at 10 BBL a calendar day: 90 BBL over 7 pricing days, 180
# and 0.09. Together 290 BBL, 580 of mark and 0.29 lots; rows 1 and 2 pay Monday 2 November, row
# 3 Wednesday the 21st, each row's quantity spread over its own days.

CODE_DATE_HEADERS = (
    "trade_id",
    "trade_date",
    "contract_code",
    "start_date",
    "end_date",
    "quantity",
    "quantity_per",
    "fixed_price",
)
BBL_HOLIDAYS = ["2030-01-01"]  # the weekday calendars need one holiday to be made; none in 2026


def code_date_row(
    label: int, code: object, start: object, end: object, quantity: float, basis: str
) -> list[object]:
    """A row of the acceptance ticket, struck on 15 September at 70; a code or dates left as
    formula-empty text, or a blank, supply nothing."""
    return [float(label), serial("2026-09-15"), code, start, end, quantity, basis, 70.0]


BBL_ROWS = (
    code_date_row(1, "V26", "", "", 100.0, "month"),
    code_date_row(2, "V26", serial("2026-10-12"), serial("2026-10-31"), 100.0, "month"),
    code_date_row(3, "", serial("2026-10-12"), serial("2026-10-20"), 10.0, "calday"),
)


@pytest.fixture(scope="module")
def bbl() -> dict[str, Any]:
    index, calendar = an_index(
        "BBL_ASIAN",
        [
            ("U26", "2026-09-29"),
            ("V26", "2026-10-30"),
            ("X26", "2026-11-30"),
            ("Z26", "2026-12-31"),
        ],
        BBL_HOLIDAYS,
        [("BBL", 1.0), ("LOT", 1_000.0)],
        measure=("VOLUME", "BBL"),
        reporting_lot="LOT",
    )
    template = ENTRY["_CreateTradeTemplate"](
        "future",
        row(*[name for name in PEN_FIELDS if name != "quantity_per"]),
        row("BBL", "asian", "cleared", "financial", "Prototype Clearing", "+1bd", calendar),
    )
    history = a_history(index, "2026-09-30", "2026-10-01", BBL_HOLIDAYS, {})
    market = a_market(history, "BBL_ASIAN", 72.0, 72.0, 72.0)
    return {"index": index, "template": template, "history": history, "market": market}


def bbl_valued(bbl: dict[str, Any], *lines: list[object]) -> tuple[str, tuple[float, float, float]]:
    """A batch of those rows on the acceptance index, and its mark, cash and delta on 1 October."""
    batch = ENTRY["_CreateTrades"](
        bbl["index"], row(*CODE_DATE_HEADERS), rows(*lines), bbl["template"]
    )
    prepared = ENTRY["_PrepareTrades"](batch, bbl["history"])
    return str(batch), valued(str(ENTRY["_EvaluateTrades"](prepared, bbl["market"])))


def test_the_three_rows_of_the_ticket_value_as_the_page_says_and_sum_their_singletons(
    bbl: dict[str, Any],
) -> None:
    batch, value = bbl_valued(bbl, *BBL_ROWS)
    assert value == (pytest.approx(580), 0.0, pytest.approx(0.29))
    table = spilled(ENTRY["util_ReadHandle"](batch))
    columns = table[0]

    def column_of(name: str) -> list[object]:
        return [line[columns.index(name)] for line in table[2:]]

    assert column_of("row") == [1.0, 2.0, 3.0]
    assert column_of("contract_code") == ["V26"] * 3  # the resolved contract on every row
    assert column_of("entered_contract_code") == ["V26", "V26", "(not supplied)"]
    assert column_of("start_date") == [
        serial(d) for d in ("2026-10-01", "2026-10-12", "2026-10-12")
    ]
    assert column_of("end_date") == [serial(d) for d in ("2026-10-31", "2026-10-31", "2026-10-20")]
    assert column_of("covered_days") == [31.0, 20.0, 9.0]
    assert column_of("quantity") == [100.0, 100.0, 10.0]
    assert column_of("quantity_per") == ["month", "month", "calday"]
    assert column_of("component_quantity") == [100.0, 100.0, 90.0]
    assert column_of("quote_quantity") == [100.0, 100.0, 90.0]
    assert column_of("payment_date") == [serial("2026-11-02")] * 2 + [serial("2026-10-21")]
    # Two payment groups of V26: 22 slots paying 2 November and 7 paying the 21st.
    prepared = ENTRY["_PrepareTrades"](batch, bbl["history"])
    slots = spilled(ENTRY["util_ReadHandle"](prepared))[2:]
    assert len(slots) == 29
    assert [line[3] for line in slots].count(serial("2026-11-02")) == 22
    assert [line[3] for line in slots].count(serial("2026-10-21")) == 7
    assert [line[4] for line in slots] == [False] * 29  # every observation live
    results = ENTRY["_EvaluateTrades"](prepared, bbl["market"])
    by_month = spilled(ENTRY["_ReportDelta"](results, "month"))
    assert by_month[2] == [
        serial("2026-10-01"),
        pytest.approx(0.29),
        "lots of LOT (1000 BBL)",
        serial("2026-10-01"),
    ]
    # Each row alone values as the page says, and the batch is their sum.
    for line, mark, lots in (
        (BBL_ROWS[0], 200, 0.10),
        (BBL_ROWS[1], 200, 0.10),
        (BBL_ROWS[2], 180, 0.09),
    ):
        _, alone = bbl_valued(bbl, line)
        assert alone == (pytest.approx(mark), 0.0, pytest.approx(lots))
    # Rows 2 and 3 as a ticket of dates alone, the codes left out, value the same.
    headers = (
        "trade_id",
        "trade_date",
        "start_date",
        "end_date",
        "quantity",
        "quantity_per",
        "fixed_price",
    )
    dated_only = ENTRY["_CreateTrades"](
        bbl["index"],
        row(*headers),
        rows(*[[*line[:2], *line[3:]] for line in BBL_ROWS[1:]]),
        bbl["template"],
    )
    _, two = bbl_valued(bbl, *BBL_ROWS[1:])
    assert (
        valued(
            str(
                ENTRY["_EvaluateTrades"](
                    ENTRY["_PrepareTrades"](dated_only, bbl["history"]), bbl["market"]
                )
            )
        )
        == two
        == (pytest.approx(380), 0.0, pytest.approx(0.19))
    )


def test_a_whole_month_by_dates_is_the_codes_own_and_a_label_beside_dates_moves_nothing(
    bbl: dict[str, Any],
) -> None:
    by_code = bbl_valued(bbl, BBL_ROWS[0])
    by_dates = bbl_valued(
        bbl, code_date_row(4, None, serial("2026-10-01"), serial("2026-10-31"), 100.0, "month")
    )
    superseded = bbl_valued(
        bbl, code_date_row(5, "X26", serial("2026-10-01"), serial("2026-10-31"), 100.0, "month")
    )
    balmo = bbl_valued(
        bbl, code_date_row(6, "BALV26", serial("2026-10-01"), serial("2026-10-31"), 100.0, "month")
    )
    assert by_code[1] == by_dates[1] == superseded[1] == balmo[1]
    assert by_code[1] == (pytest.approx(200), 0.0, pytest.approx(0.10))
    for batch, entered in ((by_dates, "(not supplied)"), (superseded, "X26"), (balmo, "BALV26")):
        table = spilled(ENTRY["util_ReadHandle"](batch[0]))
        line = table[2]
        assert line[table[0].index("contract_code")] == "V26"
        assert line[table[0].index("entered_contract_code")] == entered
    for batch in (by_code, by_dates, superseded, balmo):
        slots = spilled(ENTRY["util_ReadHandle"](ENTRY["_PrepareTrades"](batch[0], bbl["history"])))
        assert len(slots) == 24 and [line[3] for line in slots[2:]] == [serial("2026-11-02")] * 22


def test_a_row_booking_half_a_period_or_none_fails_on_the_sheet_in_the_librarys_words(
    bbl: dict[str, Any],
) -> None:
    create = ENTRY["_CreateTrades"]
    headers = row(*CODE_DATE_HEADERS)
    assert create(
        bbl["index"],
        headers,
        rows(code_date_row(5, "V26", serial("2026-10-12"), "", 100.0, "month")),
        bbl["template"],
    ) == (
        "#ERROR _CreateTrades: ValueError: start_date row 1 is 2026-10-12 without end_date row 1, "
        "expected both dates, the period's first and last day, or neither and a contract_code"
    )
    assert create(
        bbl["index"],
        headers,
        rows(BBL_ROWS[0], code_date_row(6, None, "", None, 100.0, "month")),
        bbl["template"],
    ) == (
        "#ERROR _CreateTrades: ValueError: row 2 has no period, expected a contract_code or "
        "start_date with end_date on each row; contract_code, start_date and end_date are not "
        "supplied"
    )
    # A number where a code or a date should be is the field's type refusing it, as ever.
    assert (
        create(
            bbl["index"],
            headers,
            rows(code_date_row(7, 26.0, "", "", 100.0, "month")),
            bbl["template"],
        )
        == "#ERROR _CreateTrades: trade_rows cell (1, 3) is number 26.0, expected text"
    )
    assert (
        create(
            bbl["index"],
            headers,
            rows(code_date_row(8, "", "October", serial("2026-10-20"), 100.0, "month")),
            bbl["template"],
        )
        == "#ERROR _CreateTrades: trade_rows cell (1, 4) is text 'October', expected date"
    )
