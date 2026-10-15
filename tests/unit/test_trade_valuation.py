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
    assert slots[2] == ["Z26", serial("2026-11-25"), serial("2026-11-30"), True, True, 0.0]
    assert slots[3] == ["F27", serial("2026-12-29"), serial("2026-12-31"), False, False, -50_000.0]
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[2] == ["Z26", serial("2026-11-25"), serial("2026-11-30"), True, 0.0, 0.0, 0.0]
    assert table[3][:5] == ["F27", serial("2026-12-29"), serial("2026-12-31"), False, -50_000.0]
    assert table[3][5] == pytest.approx(-175_000.0) and table[3][6] == -50_000.0


def test_a_fully_fixed_batch_inside_a_live_market_reports_its_cash_and_no_live_exposure(
    toy: dict[str, Any],
) -> None:
    prepared, results = toy_state(toy, "2026-12-31", BOTH, (3.60,))
    slots = spilled(ENTRY["util_ReadHandle"](prepared))
    assert [line[3:6] for line in slots[2:]] == [[True, True, 0.0], [True, True, 0.0]]
    assert spilled(ENTRY["util_ReadHandle"](results))[2:] == [
        ["Z26", serial("2026-11-25"), serial("2026-11-30"), True, 0.0, 0.0, 0.0],
        ["F27", serial("2026-12-29"), serial("2026-12-31"), True, 0.0, 0.0, 0.0],
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
    assert slots[2] == ["N27", serial("2027-06-25"), serial("2027-06-28"), False, False, 5_000.0]


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
        serial("2027-06-28"),
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


# R1's strip batch on the sheet, the kernel's hand answers reached through the entries: A, two lots
# of the N27-Q27 strip at 3.00, A again, and C, one lot of q27 sold at 3.05, on the PHH index with
# U27 after Q27 so that every state has a market.
STRIP_ROWS: list[list[object]] = [
    ["A", serial("2027-06-01"), "N27-Q27", 2.0, 3.0],
    ["A", serial("2027-06-01"), "N27-Q27", 2.0, 3.0],
    ["C", serial("2027-06-01"), "q27", -1.0, 3.05],
]
STRIP_LIFECYCLE: list[
    tuple[str, dict[str, float], tuple[float, ...], int, int, tuple[int, int]]
] = [
    ("2027-06-24", {}, (3.10, 3.40), 4_125, 0, (10_000, 7_500)),
    ("2027-06-25", {}, (3.10, 3.40), 4_125, 0, (10_000, 7_500)),
    ("2027-06-26", PEN_FIXED, (3.10, 3.40), 5_125, 0, (0, 7_500)),
    ("2027-06-28", PEN_FIXED, (3.10, 3.40), 3_125, 2_000, (0, 7_500)),
    ("2027-07-27", PEN_FIXED, (3.40,), 3_125, 2_000, (0, 7_500)),
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
    assert [(line[0], line[-1]) for line in table[2:]] == [("N27", delta[0]), ("Q27", delta[1])]
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
        "with the penultimate method of trade 'PHH-1' at row 1; a penultimate future is cash "
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
    assert slots[2] == [
        "Z26",
        serial("2026-11-25"),
        serial("2026-11-30"),
        True,
        True,
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
L3D_A: list[object] = ["A", serial("2026-11-20"), "Z26", 60.0, 70.0]
L3D_B: list[object] = ["B", serial("2026-11-20"), "Z26", -30.0, 72.0]
L3D_STRIP: list[object] = ["S", serial("2026-11-20"), "Z26-F27", 3.0, 70.0]


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
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "USD per USD/MMBTU"
    slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert [line[0] for line in slots] == ["Z26"] * 3
    assert [line[6] for line in slots] == [pytest.approx(delta)] * 3  # the contract's delta
    live = [line[4] for line in slots]
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
        ["Z26", serial("2026-12-02"), pays, True, False, 0.0],
        ["Z26", serial("2026-12-03"), pays, True, False, 0.0],
        ["Z26", serial("2026-12-07"), pays, False, False, 10.0],
    ]
    _, paid, _ = l3d_state(l3d, "2026-12-09", (80.0,))
    assert [line[3:5] for line in spilled(ENTRY["util_ReadHandle"](paid))[2:]] == [[True, True]] * 3


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
        assert [(line[0], line[1]) for line in slots] == [
            ("Z26", serial("2026-12-02")),
            ("Z26", serial("2026-12-03")),
            ("Z26", serial("2026-12-07")),
            ("F27", serial("2027-01-05")),
            ("F27", serial("2027-01-06")),
            ("F27", serial("2027-01-07")),
        ]
        assert [line[6] for line in slots] == [pytest.approx(delta)] * 6  # the month's delta
        assert [line[4] for line in slots] == [pytest.approx(delta / 3)] * 6  # a third a day


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
    zero: list[object] = ["Z", serial("2026-11-20"), "F27", 0.0, 71.0]
    kept = ENTRY["_CreateTrades"](
        l3d["index"], l3d["headers"], rows(L3D_A, L3D_B, zero), l3d["template"]
    )
    _, _, results = l3d_state(l3d, "2026-12-03", (74.0, 80.0), kept)
    assert valued(results) == (pytest.approx(150), 0.0, pytest.approx(20))
    slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert [line[0] for line in slots] == ["Z26"] * 3 + ["F27"] * 3
    assert [line[6] for line in slots] == [pytest.approx(20)] * 3 + [0.0] * 3


def test_a_physical_last3day_future_is_refused_when_the_batch_is_made_on_the_sheet(
    l3d: dict[str, Any],
) -> None:
    physical = l3d_template(["2026-01-01"], "physical")
    assert ENTRY["_CreateTrades"](l3d["index"], l3d["headers"], rows(L3D_A), physical) == (
        "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' "
        "with the last3day method of trade 'A' at row 1; a last3day future is cash settled on the "
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
ETHANE_A: list[object] = ["A", serial("2026-11-20"), "Z26", 4_400.0, 0.25]
ETHANE_B: list[object] = ["B", serial("2026-11-20"), "Z26", -2_200.0, 0.26]
ETHANE_STRIP: list[object] = ["S", serial("2026-11-20"), "Z26-F27", 2_200.0, 0.25]
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
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "USD per USD/GAL"
    slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert len(slots) == 22 and [line[0] for line in slots] == ["Z26"] * 22
    assert [line[6] for line in slots] == [pytest.approx(delta)] * 22  # the contract's delta
    assert sum(1 for line in slots if line[4] != 0) * 100 == delta


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
    assert slots[0] == ["Z26", serial("2026-12-01"), pays, True, False, 0.0]
    assert slots[1] == ["Z26", serial("2026-12-02"), pays, False, False, pytest.approx(100.0)]
    assert slots[-1] == ["Z26", serial("2026-12-31"), pays, False, False, pytest.approx(100.0)]
    _, paid, _ = ethane_state(ethane, "2027-01-05", LATER_QUOTES)
    assert [line[3:5] for line in spilled(ENTRY["util_ReadHandle"](paid))[2:]] == [
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
        assert slots[22][1] == serial("2027-01-04") and slots[-1][1] == serial("2027-01-29")
        assert [line[6] for line in slots] == [pytest.approx(delta)] * 42  # each month's delta
        assert [line[4] for line in slots] == [pytest.approx(exposures[0])] * 22 + [
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
    zero: list[object] = ["Z", serial("2026-11-20"), "F27", 0.0, 0.27]
    kept = ENTRY["_CreateTrades"](
        ethane["index"], ethane["headers"], rows(ETHANE_A, ETHANE_B, zero), ethane["template"]
    )
    _, _, results = ethane_state(ethane, "2026-12-02", LIVE_QUOTES, kept)
    assert valued(results) == (pytest.approx(84), 0.0, pytest.approx(2_100))
    slots = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert [line[0] for line in slots] == ["Z26"] * 22 + ["F27"] * 20
    assert [line[6] for line in slots] == [pytest.approx(2_100)] * 22 + [0.0] * 20


def test_a_physical_asian_future_is_refused_when_the_batch_is_made_on_the_sheet(
    ethane: dict[str, Any],
) -> None:
    physical = asian_template(["2027-01-01"], "physical")
    assert ENTRY["_CreateTrades"](ethane["index"], ethane["headers"], rows(ETHANE_A), physical) == (
        "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' "
        "with the asian method of trade 'A' at row 1; an asian future is cash settled on the "
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
        rows(["C", serial("2026-11-20"), "Z26", 110.0, 0.25]),
        asian_template(["2027-01-01"], basis="calday"),
    )
    by_month = ENTRY["_CreateTrades"](
        ethane["index"],
        ethane["headers"],
        rows(["M", serial("2026-11-20"), "Z26", 3_410.0, 0.25]),
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


def dated_rows(*trades: tuple[str, float, float, float]) -> Cells:
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
        ethane["index"], headers, dated_rows(("P", start, end, 2_000.0)), ethane["template"]
    )
    typed = ENTRY["_CreateTrades"](
        ethane["index"],
        headers,
        dated_rows(("P", serial("2026-12-15"), serial("2026-12-31"), 2_000.0)),
        ethane["template"],
    )
    by_day = ENTRY["_CreateTrades"](
        ethane["index"],
        headers,
        dated_rows(("P", serial("2026-12-15"), serial("2026-12-31"), 2_000.0)),
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
    assert [line[1] for line in slots] == [
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
    assert [line[2] for line in slots] == [serial("2027-01-05")] * 12  # the payment day
    assert [line[3] for line in slots] == [True] + [False] * 11
    assert slots[1][5] == pytest.approx(2_000 / 12)
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
    assert [line[1] for line in later] == [line[1] for line in slots]
    assert [line[3] for line in later] == [True, True] + [False] * 10
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
    p = ("P", serial("2026-12-15"), last, 2_000.0)
    q = ("Q", first, last, 2_200.0)
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
        ethane["index"], headers, dated_rows(p, q, ("Z", first, last, 0.0)), ethane["template"]
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
        dated_rows(p, ("Q", first, serial("2026-12-30"), 2_200.0)),
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
    assert [line[2] for line in slots] == [serial("2027-01-04")] * 21 + [serial("2027-01-05")] * 12
    assert [line[4] for line in slots] == [True] * 21 + [False] * 12  # Q settled, P not yet
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
PAYS_A: list[object] = ["A", serial("2026-11-30"), "Z26", 60.0, 70.0, "+1bd"]
PAYS_B: list[object] = ["B", serial("2026-11-30"), "Z26", -30.0, 72.0, "+3bd"]
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
        "contract_code",
        "observation_date",
        "payment_date",
        "is_fixed",
        "is_settled",
        "live_exposure",
    ]
    assert slots[1] == ["str", "datetime64[D]", "datetime64[D]", "bool", "bool", "float64"]
    days = [serial(d) for d in ("2026-12-02", "2026-12-03", "2026-12-04")]
    assert [line[1] for line in slots[2:]] == days * 2
    assert [line[2] for line in slots[2:]] == [serial("2026-12-07")] * 3 + [
        serial("2026-12-09")
    ] * 3
    assert [line[4] for line in slots[2:]] == [settled[0]] * 3 + [settled[1]] * 3
    table = spilled(ENTRY["util_ReadHandle"](results))
    assert table[0] == [
        "contract_code",
        "observation_date",
        "payment_date",
        "is_fixed",
        "live_exposure",
        "live_contribution",
        "contract_delta",
    ]
    assert [line[2] for line in table[2:]] == [line[2] for line in slots[2:]]
    assert [line[6] for line in table[2:]] == [pytest.approx(delta)] * 6  # the contract's, once


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
MIXED_A: list[object] = ["A", "Z26", 1.0, "BBL", "month", "lastday", "Clearer A"]
MIXED_B: list[object] = ["B", "Z26", -2.0, "GAL", "calday", "penultimate", "Clearer B"]
MIXED_C: list[object] = ["C", "Z26", 3.0, "BBL", "month", "last3day", "Clearer A"]
MIXED_D: list[object] = ["D", "Z26", 22.0, "GAL", "month", "asian", "Clearer B"]
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
    index = str(ENTRY["_CreateIndex"]("MIXED", schedule, conventions, specifications, holidays))
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
    assert spilled(ENTRY["_ReportRisk"](results))[2][1] == "USD per USD/GAL"
    slots = spilled(ENTRY["util_ReadHandle"](prepared))[2:]
    assert len(slots) == 23 and [line[0] for line in slots] == ["Z26"] * 23
    assert [line[2] for line in slots] == [serial("2026-12-31")] + [serial("2027-01-04")] * 22
    assert [line[4] for line in slots] == [as_of >= "2026-12-31"] + [as_of >= "2027-01-04"] * 22
    table = spilled(ENTRY["util_ReadHandle"](results))[2:]
    assert [line[6] for line in table] == [pytest.approx(delta)] * 23


def test_the_mixed_batch_reads_back_each_rows_own_choices(mixed: dict[str, Any]) -> None:
    # A strip beside the four rows, S the whole of December and January under asian in gallons a
    # month: its two components show S's choices, not row 1's.
    strip: list[object] = ["S", "Z26-F27", 5.0, "GAL", "month", "asian", "Clearer B"]
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
            rows(MIXED_A, ["B", "Z26", -2.0, "ICE", "calday", "penultimate", "Clearer B"]),
            mixed["template"],
        )
    ) == (
        "#ERROR _CreateTrades: ValueError: quantity_unit row 2 is 'ICE', expected one of the "
        "index's specifications: 'GAL', 'BBL'"
    )
