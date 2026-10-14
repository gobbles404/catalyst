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
    ["NG-001", serial("2026-09-24"), "Z26", 10.0, 3.1],
    ["NG-002", serial("2026-09-24"), "z26", -4.0, 3.15],
    ["NG-003", serial("2026-09-25"), "F27", 7.0, 3.4],
    ["NG-004", serial("2026-09-25"), "F27", -12.0, 3.35],
    ["NG-001", serial("2026-09-24"), "Z26", 10.0, 3.1],
]


def an_index(
    name: str,
    contracts: list[tuple[str, str]],
    holidays: list[str],
    lots: list[tuple[str, float]],
    measure: tuple[str, str] = ("ENERGY", "MMBTU"),
    quoted_in: str = "USD",
) -> tuple[str, str]:
    """An index of those contracts and holidays through the seam, quoted in that currency unit per
    the measure's unit and settled in USD, with one specification per name given, that many of the
    measure's unit a lot, in the order given, and its holiday calendar."""
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
    return str(ENTRY["_CreateIndex"](name, schedule, conventions, specifications, calendar)), str(
        calendar
    )


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
        [110_000.0, "USD per USD/MMBTU", 0.0, "USD per basis point", serial("2026-11-24")],
    ]


def test_the_readers_spill_the_dated_contents_one_row_per_slot(ng: dict[str, Any]) -> None:
    assert spilled(ENTRY["util_ReadHandle"](ng["prepared"])) == [
        ["contract_code", "observation_date", "is_fixed", "is_settled", "live_exposure"],
        ["str", "datetime64[D]", "bool", "bool", "float64"],
        ["Z26", serial("2026-11-25"), False, False, 160_000.0],
        ["F27", serial("2026-12-29"), False, False, -50_000.0],
    ]
    table = spilled(ENTRY["util_ReadHandle"](ng["results"]))
    assert table[:2] == [
        [
            "contract_code",
            "observation_date",
            "is_fixed",
            "live_exposure",
            "live_contribution",
            "contract_delta",
        ],
        ["str", "datetime64[D]", "bool", "float64", "float64", "float64"],
    ]
    assert table[2][:4] == ["Z26", serial("2026-11-25"), False, 160_000.0]
    assert table[2][4] == pytest.approx(512_000.0) and table[2][5] == 160_000.0
    assert table[3][4] == pytest.approx(-175_000.0) and table[3][5] == -50_000.0


def test_a_tick_makes_new_results_over_the_same_preparation_and_the_old_stand(
    ng: dict[str, Any],
) -> None:
    ticked = a_market(ng["history"], "Henry Hub NYMEX", 3.21, 3.50)
    later = ENTRY["_EvaluateTrades"](ng["prepared"], ticked)
    assert later != ng["results"]
    assert spilled(ENTRY["_ReportValues"](later))[2][0] == pytest.approx(8_600.0)
    assert spilled(ENTRY["_ReportValues"](ng["results"]))[2][0] == 7_000.0  # unmoved
    assert spilled(ENTRY["_ReportRisk"](later))[2][0] == 110_000.0  # delta, no tick changes it


def test_one_trade_takes_the_same_path_as_five(ng: dict[str, Any]) -> None:
    one = ENTRY["_CreateTrades"](ng["index"], row(*NG_HEADERS), rows(NG_ROWS[3]), ng["template"])
    prepared = ENTRY["_PrepareTrades"](one, ng["history"])
    results = ENTRY["_EvaluateTrades"](prepared, ng["market"])
    values = spilled(ENTRY["_ReportValues"](results))
    assert values[2][:2] == [pytest.approx(-18_000.0), 0.0]
    assert spilled(ENTRY["_ReportRisk"](results))[2][0] == -120_000.0


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


# The page's seven states, with its total P&L column typed from the page beside the mark and
# the cash, and an eighth day between two of them: Friday 27 November, Z26 fixed and not yet
# paid, since the payment calendar closes the 26th and two business days from the 25th land on
# Monday the 30th. A payment counted on an open calendar would fall on the 27th and turn the
# day's 11,800 of mark into cash.
@pytest.mark.parametrize(
    ("as_of", "settles", "quotes", "mark", "cash", "delta", "total"),
    [
        ("2026-11-24", {}, (3.20, 3.50, 3.60), 7_000, 0, 110_000, 7_000),
        ("2026-11-24", {}, (3.21, 3.50, 3.60), 8_600, 0, 110_000, 8_600),
        ("2026-11-26", Z26_FIRST, (3.50, 3.60), 10_200, 0, -50_000, 10_200),
        ("2026-11-26", Z26, (3.50, 3.60), 11_800, 0, -50_000, 11_800),
        ("2026-11-27", Z26, (3.50, 3.60), 11_800, 0, -50_000, 11_800),
        ("2026-11-30", Z26, (3.50, 3.60), -11_000, 22_800, -50_000, 11_800),
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
    assert slots[2] == ["Z26", serial("2026-11-25"), True, True, 0.0]
    assert slots[3] == ["F27", serial("2026-12-29"), False, False, -50_000.0]
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[2] == ["Z26", serial("2026-11-25"), True, 0.0, 0.0, 0.0]
    assert table[3][:4] == ["F27", serial("2026-12-29"), False, -50_000.0]
    assert table[3][4] == pytest.approx(-175_000.0) and table[3][5] == -50_000.0


def test_a_fully_fixed_batch_inside_a_live_market_reports_its_cash_and_no_live_exposure(
    toy: dict[str, Any],
) -> None:
    prepared, results = toy_state(toy, "2026-12-31", BOTH, (3.60,))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert [line[2:5] for line in slots[2:]] == [[True, True, 0.0], [True, True, 0.0]]
    assert spilled(ENTRY["util_ReadHandle"](results))[2:] == [
        ["Z26", serial("2026-11-25"), True, 0.0, 0.0, 0.0],
        ["F27", serial("2026-12-29"), True, 0.0, 0.0, 0.0],
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
    )
    clearing = ENTRY["_CreateHolidayCalendar"](column([serial("2027-05-31"), serial("2027-08-30")]))
    template = pen_template("ICE PHH", str(clearing))
    headers = row(*NG_HEADERS)
    long = ["PHH-1", serial("2027-06-01"), "N27", 2.0, 3.0]
    short = ["PHH-2", serial("2027-06-01"), "n27", -2.0, 3.0]
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
        ("2027-06-25", {}, (3.10, 3.15), 500, 0, 5_000),
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
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "USD per USD/MMBTU"


def test_the_pens_dates_read_back_from_the_batch_and_the_preparation(phh: dict[str, Any]) -> None:
    batch = spilled(ENTRY["util_ReadHandle"](phh["trades"]))
    assert batch[0][batch[0].index("payment_date")] == "payment_date"
    assert batch[2][batch[0].index("payment_time_lag")] == "+1bd"
    assert batch[2][batch[0].index("payment_date")] == serial("2027-06-28")
    assert batch[2][batch[0].index("contract_code")] == "N27"
    assert batch[2][batch[0].index("quote_quantity")] == 5_000.0
    _, prepared, _ = phh_state(phh, "2027-06-25", {}, (3.10, 3.15))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert slots[2] == ["N27", serial("2027-06-25"), False, False, 5_000.0]


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
        serial("2027-06-25"),
        True,
        False,
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
        "#ERROR _CreateTrades: ValueError: settlement is 'physical', expected 'financial' with "
        "the penultimate method; a penultimate future is cash settled on the business day before "
        "its contract's expiry"
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
        index, row(*NG_HEADERS), rows(["T-1", serial("2026-12-01"), "F27", 3.0, 60.0]), template
    )
    batch = spilled(ENTRY["util_ReadHandle"](trades))
    assert batch[2][batch[0].index("payment_date")] == serial("2026-12-21")
    assert batch[2][batch[0].index("quote_quantity")] == 3_000.0
    live = a_history(index, "2026-11-23", "2026-12-17", holidays, {})
    results = ENTRY["_EvaluateTrades"](
        ENTRY["_PrepareTrades"](trades, live), a_market(live, "WTI NYMEX", 61.0, 61.5)
    )
    assert valued(str(results)) == (pytest.approx(3_000), 0.0, pytest.approx(3_000))
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "USD per USD/BBL"
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
        ["E-1", serial("2026-09-24"), "Z26", 2.0, 3.1],
    )
    as_units, units_spill = valued_on_24_nov(
        index,
        "Henry Hub NYMEX",
        {**NG_TEMPLATE, "quantity_unit": "MMBTU"},
        ["E-2", serial("2026-09-24"), "Z26", 5_000.0, 3.1],
    )
    assert as_lots == as_units == (pytest.approx(500.0), 0.0, pytest.approx(5_000.0))
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
        index, row(*NG_HEADERS), rows(["C-1", serial("2026-09-24"), "Z26", 1.0, 300.0]), template
    )
    spill = spilled(ENTRY["util_ReadHandle"](trades))
    assert spill[2][spill[0].index("quote_quantity")] == 10_000.0
    assert spill[2][spill[0].index("coefficient")] == pytest.approx(100.0)
    assert spill[2][spill[0].index("offset")] == pytest.approx(-30_000.0)
    history = a_history(index, "2026-10-29", "2026-11-24", NG_HOLIDAYS, {})
    results = ENTRY["_EvaluateTrades"](
        ENTRY["_PrepareTrades"](trades, history), a_market(history, "cents", 310.0, 350.0)
    )
    assert valued(str(results)) == (pytest.approx(1_000.0), 0.0, pytest.approx(100.0))
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "USD per CENT/MMBTU"


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
    ["NG-001", serial("2026-10-06"), "Z26", 2.0, 3.0],
    ["ENTRY-002", serial("2026-10-06"), "F27", 0.0, 3.3],
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
    assert valued(results) == (pytest.approx(2_000), 0.0, pytest.approx(20_000))
    batch = spilled(ENTRY["util_ReadHandle"](trades))
    assert [line[1] for line in batch[2:]] == ["NG-001", "ENTRY-002"]  # the row kept, in its place
    assert batch[3][batch[0].index("quantity")] == 0.0
    assert batch[3][batch[0].index("offset")] == 0.0
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[2][:4] == ["Z26", serial("2026-11-25"), False, 20_000.0]
    assert table[2][5] == 20_000.0
    assert table[3] == [
        "F27",
        serial("2026-12-29"),
        False,
        0.0,
        0.0,
        0.0,
    ]  # on the axis, at nothing
    sold_trades, sold_prepared, sold = entry_state(ng, -1.0)
    assert sold_trades != trades and sold_prepared != prepared and sold != results
    assert valued(sold) == (pytest.approx(1_000), 0.0, pytest.approx(10_000))
    assert spilled(ENTRY["util_ReadHandle"](sold))[3][5] == -10_000.0
    assert valued(results) == (pytest.approx(2_000), 0.0, pytest.approx(20_000))  # the old stand


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
        "USD per USD/MMBTU",
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
        rows(["ENTRY-000", serial("2026-10-06"), "Z26", 0.0, 3.1]),
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
    assert slots[2] == ["Z26", serial("2026-11-25"), True, True, 0.0]  # fixed and paid, at nothing


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
        "#ERROR _PrepareTrades: ValueError: trade 'NG-001' at row 1 on Z26 expired 2026-11-25, "
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
        "#ERROR _PrepareTrades: ValueError: trade 'NG-001' at row 1 on Z26 expired 2026-11-25, "
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
