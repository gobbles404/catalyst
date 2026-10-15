"""What the valuation path costs through the seam: _PrepareTrades, _EvaluateTrades and the two
reports, each as the host calls it. The pins are the pipeline's rules on the sheet: preparing
resolves two handles and runs the kernel's preparation and nothing of the encoding; a tick
resolves two handles and runs the evaluation alone, one quote per live reference, nothing of the
preparation; a report resolves one handle and lays out one row, no kernel call at all. The same
functions at five rows and at two thousand, and the peaks by slot and by reference, never by
trade."""

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from test_seam_allocation import SLACK, least_peak

from goosedove.excel import bridge
from goosedove.excel.bridge import Cells

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}
FIRST = np.datetime64("1899-12-30", "D")
SIZES = [(5, 2), (2_000, 24)]
IDS = ["five trades", "two thousand trades"]

# The budgets' index on the sheet: 25 monthly contracts from October 2026, each expiring on the
# last business day on or before the 25th, valued on 10 March 2027 with a settle of 3.00 on every
# fixed day and a quote per contract from the prompt on; the batch spread over the first 2 or 24
# contracts after the boundary, so that four or five contracts have fixed and the rest are live.
MONTHS = np.arange("2026-10", "2028-11", dtype="datetime64[M]")
LETTERS = "FGHJKMNQUVXZ"
CODES = [f"{LETTERS[int(m.astype(int)) % 12]}{str(m)[2:4]}" for m in MONTHS]
HOLIDAYS = np.array(["2026-12-25", "2027-01-01", "2027-12-24"], dtype="datetime64[D]")
EXPIRIES = np.busday_offset(
    MONTHS.astype("datetime64[D]") + np.timedelta64(24, "D"), 0, roll="backward", holidays=HOLIDAYS
)
AS_OF = np.datetime64("2027-03-10", "D")


def serial(day: np.datetime64) -> float:
    return float((day - FIRST).astype(np.int64))


def column(values: list[float]) -> Cells:
    return Cells.from_rows([[v] for v in values])


@pytest.fixture(scope="module")
def sheet() -> dict[str, Any]:
    schedule = PATH["_CreateFuturesSchedule"](
        Cells.from_rows([[code] for code in CODES]),
        column([serial(d) for d in EXPIRIES]),
        bridge.MISSING,
    )
    holidays = PATH["_CreateHolidayCalendar"](column([serial(d) for d in HOLIDAYS]))
    conventions = PATH["_CreateIndexConventions"]("USD", "MMBTU", "USD", "ENERGY", "MMBTU")
    specifications = PATH["_CreateContractSpecifications"](
        Cells.from_rows(
            [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
        ),
        Cells.from_rows([["lot", 10000.0, "MMBTU", 0.0, 0.0]]),
    )
    index = PATH["_CreateIndex"](
        "gas", "Sample gas index", schedule, conventions, specifications, holidays, "lot"
    )
    fields = [
        "quantity_unit",
        "quantity_per",
        "schedule_method",
        "route",
        "settlement_method",
        "clearing_house",
        "payment_time_lag",
        "payment_holiday_calendar",
    ]
    template = PATH["_CreateTradeTemplate"](
        "fixed_float",
        Cells.from_rows([fields]),
        Cells.from_rows(
            [["lot", "month", "lastday", "cleared", "financial", "TEST", "+2bd", holidays]]
        ),
    )
    days = np.arange(EXPIRIES[0] + np.timedelta64(1, "D"), AS_OF)
    days = days[np.is_busday(days, holidays=HOLIDAYS)]
    fixings = PATH["_CreateFuturesFixings"](
        column([serial(d) for d in days[::-1]]), column([3.0] * days.size), index
    )
    calendar = PATH["_CreateCalendar"](PATH["_CreateValuationDate"](serial(AS_OF), 0.5), index)
    history = PATH["_CreateMarketHistory"](calendar, fixings)
    live = int((EXPIRIES >= AS_OF).sum())
    market = PATH["_CreateMarket"](
        history, PATH["_CreatePriceVector"]("gas", column([3.5 + i / 100 for i in range(live)]))
    )
    headers = Cells.from_rows([["trade_date", "contract_code", "quantity", "fixed_price"]])
    return {
        "index": index,
        "template": template,
        "headers": headers,
        "history": history,
        "market": market,
    }


def a_batch(
    sheet: dict[str, Any], rows: int, contracts: int, template: object | None = None
) -> str:
    body = Cells.from_rows(
        [
            [46289.0, CODES[1 + i % contracts], 2.0 if i % 3 else -3.0, 3.0 + (i % 7) / 100]
            for i in range(rows)
        ]
    )
    chosen = sheet["template"] if template is None else template
    return str(PATH["_CreateTrades"](sheet["index"], sheet["headers"], body, chosen))


@pytest.fixture(scope="module")
def bilateral(sheet: dict[str, Any]) -> dict[str, Any]:
    """The sheet's batch made bilateral, since #177: the same fields with a counterparty for the
    clearing house and the route bilateral, and a curve anchored on the valuation day running to
    the end of 2028 at 0.9, past every payment."""
    holidays = PATH["_CreateHolidayCalendar"](column([serial(d) for d in HOLIDAYS]))
    fields = [
        "quantity_unit",
        "quantity_per",
        "schedule_method",
        "route",
        "settlement_method",
        "counterparty",
        "payment_time_lag",
        "payment_holiday_calendar",
    ]
    template = PATH["_CreateTradeTemplate"](
        "fixed_float",
        Cells.from_rows([fields]),
        Cells.from_rows(
            [
                [
                    "lot",
                    "month",
                    "lastday",
                    "bilateral",
                    "financial",
                    "ACME Trading",
                    "+2bd",
                    holidays,
                ]
            ]
        ),
    )
    curve = PATH["_CreateDiscountCurve"](
        Cells.from_rows([["date", "discount_factor"]]),
        Cells.from_rows([[serial(AS_OF), 1.0], [serial(np.datetime64("2028-12-31", "D")), 0.9]]),
    )
    return {"template": template, "curve": curve}


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_preparing_resolves_two_handles_and_runs_the_kernels_preparation_alone(
    call_profile: CallProfile, sheet: dict[str, Any], rows: int, contracts: int
) -> None:
    trades = a_batch(sheet, rows, contracts)

    def prepare() -> object:
        return PATH["_PrepareTrades"](trades, sheet["history"])

    assert str(prepare()).split(":")[1:3] == ["prepared_trades", "gas"]
    assert call_profile(prepare) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text": 2,
        "_resolve": 2,
        "_PrepareTrades": 1,
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
        "_publish": 1,
    }


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_a_tick_resolves_two_handles_and_runs_the_evaluation_alone(
    call_profile: CallProfile, sheet: dict[str, Any], rows: int, contracts: int
) -> None:
    prepared = PATH["_PrepareTrades"](a_batch(sheet, rows, contracts), sheet["history"])

    def tick() -> object:
        return PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING)

    assert str(tick()).split(":")[1:3] == ["trade_results", "gas"]
    assert call_profile(tick) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,  # the two handles and the curve left out, since #177
        "_text": 2,
        "_resolve": 2,
        "_EvaluateTrades": 1,
        "trade_results": 1,
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
        "_publish": 1,
    }


def test_a_report_resolves_one_handle_and_lays_out_one_row(
    call_profile: CallProfile, sheet: dict[str, Any]
) -> None:
    prepared = PATH["_PrepareTrades"](a_batch(sheet, 5, 2), sheet["history"])
    results = PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING)
    live = bridge.live_handles()
    for name, numeric, dated in (
        ("_ReportValues", 3, True),
        ("_ReportReserves", 3, False),  # three totals and a currency, no day, since #170
    ):
        profile = call_profile(lambda name=name: PATH[name](results))
        expected = {
            "Registered.run": 1,
            "_arguments": 1,
            "_validate": 1,
            "_text": 1,
            "_resolve": 1,
            name: 1,
            "MixedArray.table": 1,
            "_table_column": numeric,  # the numbers, and the day where the report has one
            "_mixed_out": 1,
            "_bad_mixed": 1,  # the way out's check of the rectangle, finding nothing wrong
        }
        if dated:
            expected["_serials"] = 1  # the day to its serial
            expected["_unit"] = 1
        assert profile == expected, name
    assert bridge.live_handles() == live  # a report publishes nothing


# Memory on the sheet, 2,500 single-month trades over 24 contracts, 24 slots: preparing peaks at
# the kernel's arrays by slot, some thirty of them at 24 elements each, where the hundred bytes
# an array costs beside its data outweighs the data, and the handle's small objects; a tick at
# the quotes and the contributions by live reference and slot; a report at one row laid out;
# none by trade, since the batch of five rows and two slots prepares at 3,527 bytes and the one
# of 2,500 rows at 8,912. Measured 2026-10-04: preparing 8,912 bytes, a tick 1,144, the values
# report 1,967 and the risk report 1,948; the risk report 2,079 since #177, its sixth column, and
# since #178 3,591 bytes for all three by day, 24 observation days under the Total in four
# columns, the rectangle and the DV01 column of zeros, within four slacks.
RISK_PEAK = 4 * SLACK


def test_the_valuation_path_allocates_by_slot_and_never_by_trade(sheet: dict[str, Any]) -> None:
    trades = a_batch(sheet, 2_500, 24)
    assert least_peak(lambda: PATH["_PrepareTrades"](trades, sheet["history"])) <= 10 * SLACK
    prepared = PATH["_PrepareTrades"](trades, sheet["history"])
    assert (
        least_peak(lambda: PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING))
        <= 2 * SLACK
    )
    results = PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING)
    assert least_peak(lambda: PATH["_ReportValues"](results)) <= 2 * SLACK
    assert least_peak(lambda: PATH["_ReportRisk"](results, "all", "day")) <= RISK_PEAK
    assert least_peak(lambda: PATH["_ReportReserves"](results)) <= 2 * SLACK


# --- the bilateral path through the seam, since #177 ----------------------------------------------


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_a_bilateral_tick_resolves_three_handles_and_runs_the_discounted_path_alone(
    call_profile: CallProfile,
    sheet: dict[str, Any],
    bilateral: dict[str, Any],
    rows: int,
    contracts: int,
) -> None:
    prepared = PATH["_PrepareTrades"](
        a_batch(sheet, rows, contracts, bilateral["template"]), sheet["history"]
    )

    def tick() -> object:
        return PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curve"])

    assert str(tick()).split(":")[1:3] == ["trade_results", "gas"]
    # The curve the third handle resolved; the kernel's bilateral path, the rules and the discounted
    # snapshot, beside the evaluator; nothing of the preparation, and no sort on a tick.
    assert call_profile(tick) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text": 3,
        "_resolve": 3,
        "_EvaluateTrades": 1,
        "trade_results": 1,
        "_the_curve": 1,
        "DiscountCurve.start_date": 2,
        "DiscountCurve.max_date": 1,
        "Market.live_prices": 1,
        "_discounted": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 6,
        "_publish": 1,
    }


def test_the_risk_report_resolves_one_handle_selects_a_view_and_lays_it_out(
    call_profile: CallProfile, sheet: dict[str, Any], bilateral: dict[str, Any]
) -> None:
    # Since #178: the three arguments validated, the two words chosen, the view selected by
    # reference, the observation axis for a delta, the payment axis for the DV01 and both with
    # the union for all three of a bilateral result, a cleared result's all on the observation
    # axis; the rectangle laid out by kind with the two date columns through the table builder;
    # nothing summed, nothing sorted, nothing published, the same over either route.
    prepared = PATH["_PrepareTrades"](a_batch(sheet, 5, 2), sheet["history"])
    cleared = PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING)
    prepared = PATH["_PrepareTrades"](a_batch(sheet, 5, 2, bilateral["template"]), sheet["history"])
    discounted = PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curve"])
    live = bridge.live_handles()
    views = {
        "nominal_delta": {"_delta_view": 1},
        "delta": {"_delta_view": 1},
        "dv01": {"_payment_view": 1},
    }
    for results, everything in (
        (cleared, {"_delta_view": 1}),
        (discounted, {"_delta_view": 1, "_payment_view": 1, "_union_view": 1}),
    ):
        for risk, selected in (*views.items(), ("all", everything)):
            for bucket in ("day", "month", "year"):
                profile = call_profile(
                    lambda handle=results, risk=risk, bucket=bucket: PATH["_ReportRisk"](
                        handle, risk, bucket
                    )
                )
                assert profile == {
                    "Registered.run": 1,
                    "_arguments": 1,
                    "_validate": 3,  # the results and the two words
                    "_text": 3,
                    "_resolve": 1,
                    "_ReportRisk": 1,
                    "choice": 2,  # the risk's word, one of four, and the bucket's, one of three
                    "TradeResults.report": 1,  # the result's own selection, since #180
                    "risk_view": 1,
                    **selected,
                    "_risk_table": 1,
                    "MixedArray.table": 2,  # the valuation day and the dates to serials
                    "_table_column": 2,
                    "_serials": 2,
                    "_unit": 2,
                    "_mixed_out": 1,
                    "_bad_mixed": 1,
                }, (risk, bucket)
    assert bridge.live_handles() == live  # a report publishes nothing


# Measured 2026-10-11 at 2,500 trades over 24 slots: a bilateral tick 5,901 bytes against the
# cleared tick's 1,490, the curve's handle, the groups' amounts, factors, NPVs and DV01s, the
# discounted lots by reference, day, month and year and, since #178, the DV01 by payment day,
# month and year, 5,093 before them; the risk report of all three by day 6,263 bytes, 48 rows
# under the Total, the 24 observation days and the 24 payment days in four columns, the three
# vectors placed on the union, against the cleared batch's 3,591, within seven slacks.
def test_the_bilateral_path_allocates_by_group_and_slot_and_never_by_trade(
    sheet: dict[str, Any], bilateral: dict[str, Any]
) -> None:
    prepared = PATH["_PrepareTrades"](
        a_batch(sheet, 2_500, 24, bilateral["template"]), sheet["history"]
    )
    assert (
        least_peak(lambda: PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curve"]))
        <= 8 * SLACK
    )
    results = PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curve"])
    assert least_peak(lambda: PATH["_ReportRisk"](results, "all", "day")) <= 7 * SLACK


# --- a collection of results through the seam, since #180 -----------------------------------------


def n_results(
    sheet: dict[str, Any], bilateral: dict[str, Any], rows: int, contracts: int, n: int = 2
) -> list[str]:
    """n results of one bilateral batch over one market and curve, n handles of one content."""
    prepared = PATH["_PrepareTrades"](
        a_batch(sheet, rows, contracts, bilateral["template"]), sheet["history"]
    )
    return [
        str(PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curve"]))
        for _ in range(n)
    ]


HANDLES = [2, 24]
HANDLE_IDS = ["two results", "twenty-four results"]


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
@pytest.mark.parametrize("n", HANDLES, ids=HANDLE_IDS)
def test_a_collection_resolves_each_handle_once_and_runs_the_collector_alone(
    call_profile: CallProfile,
    numpy_calls: CallProfile,
    sheet: dict[str, Any],
    bilateral: dict[str, Any],
    rows: int,
    contracts: int,
    n: int,
) -> None:
    handles = n_results(sheet, bilateral, rows, contracts, n)
    cells = Cells.from_rows([[handle] for handle in handles])
    live = bridge.live_handles()
    # The vector's shape checked once, the cells decoded in one pass and each read and resolved
    # once, so the seam's entries grow with the handles and nothing else does; the collector's own
    # functions and nothing of the kernel, the market or the curve; one publication.
    assert call_profile(lambda: PATH["_AggregateResults"](cells)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve_each": 1,
        "_values": 1,
        "_decoded": n,
        "_text": n,
        "_resolve": n,
        "_AggregateResults": 1,
        "aggregate_results": 1,
        "_grouped_by_index": 1,
        "_grouped_by_curve": 1,
        "_index_group": 1,
        "_rate_group": 1,
        "_summed": 7,
        "_compensated": 11,
        "_outrun": 3,
        "_report_axes": 3,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 20,
        "_publish": 1,
    }
    # The seam makes no numpy call of its own: every one below is the collector's, the same at two
    # handles and at twenty-four, as test_aggregate_budgets.py pins them; before #180's review a
    # look per text cell counted the texts before it, n squared over the range.
    assert numpy_calls(lambda: PATH["_AggregateResults"](cells)) == {
        "ndarray.any": 11,
        "ndarray.flatten": 16,
        "ndarray.searchsorted": 19,
        "ndarray.setflags": 41,
        "ndarray.sort": 16,
        "numpy._make_extobj": 11,
        "numpy._unique_hash": 16,
        "numpy.array": 2,
        "numpy.asanyarray": 32,
        "numpy.zeros": 22,
        "ufunc.reduce": 11,
    }
    assert bridge.live_handles()[0] == live[0] + 2


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_a_collection_report_resolves_one_handle_and_copies_through_saved_places(
    call_profile: CallProfile,
    sheet: dict[str, Any],
    bilateral: dict[str, Any],
    rows: int,
    contracts: int,
) -> None:
    handles = n_results(sheet, bilateral, rows, contracts)
    collection = str(PATH["_AggregateResults"](Cells.from_rows([handles])))
    live = bridge.live_handles()
    # The collection's handle resolved by the two-kind rule, the two words chosen, the collection's
    # own selection with a copy per column, and #178's rectangle; nothing summed, nothing published.
    for risk, selected in (
        ("nominal_delta", {"_lots": 1, "_placed": 1}),
        ("delta", {"_discounted_lots": 1, "_placed": 1}),
        ("dv01", {"_dv01": 1, "_placed": 1}),
        ("all", {"_lots": 1, "_discounted_lots": 1, "_dv01": 1, "_placed": 3}),
    ):
        for bucket in ("day", "month", "year"):
            profile = call_profile(
                lambda risk=risk, bucket=bucket: PATH["_ReportRisk"](collection, risk, bucket)
            )
            assert profile == {
                "Registered.run": 1,
                "_arguments": 1,
                "_validate": 3,
                "_text": 3,
                "_resolve": 1,
                "_ReportRisk": 1,
                "choice": 2,
                "AggregateResults.report": 1,
                "aggregate_view": 1,
                "_axes_of": 1,
                **selected,
                "_risk_table": 1,
                "MixedArray.table": 2,
                "_table_column": 2,
                "_serials": 2,
                "_unit": 2,
                "_mixed_out": 1,
                "_bad_mixed": 1,
            }, (risk, bucket)
    assert bridge.live_handles() == live


# Measured 2026-10-11 at two results of 2,500 trades over 24 slots: the collection 16,640 bytes,
# the stacked day axes of the two sources with their places and the compensated pass over them, the
# unions and the record; its report of all three by day 6,263 bytes, the same rectangle
# a result's report lays out, 48 dated rows in four columns.
def test_a_collection_allocates_by_the_saved_entries_and_its_report_by_the_rectangle(
    sheet: dict[str, Any], bilateral: dict[str, Any]
) -> None:
    handles = n_results(sheet, bilateral, 2_500, 24)
    cells = Cells.from_rows([[handle] for handle in handles])
    assert least_peak(lambda: PATH["_AggregateResults"](cells)) <= 17 * SLACK
    collection = str(PATH["_AggregateResults"](cells))
    assert least_peak(lambda: PATH["_ReportRisk"](collection, "all", "day")) <= 7 * SLACK


# --- a combined payment calendar, combine-holiday-calendars.md ------------------------------------


# A template paying on a combination of the sheet's calendar with itself does the plain template's
# work, call for call, at creation, preparation, evaluation and reporting: the union ran once, when
# the combination was made, and no step after it reads a calendar again.
def test_a_combined_payment_calendar_adds_no_work_after_creation(
    call_profile: CallProfile, sheet: dict[str, Any]
) -> None:
    holidays = PATH["_CreateHolidayCalendar"](column([serial(d) for d in HOLIDAYS]))
    combined = str(PATH["_CombineHolidayCalendars"](Cells.from_rows([[holidays], [holidays]])))
    fields = Cells.from_rows(
        [
            [
                "quantity_unit",
                "quantity_per",
                "schedule_method",
                "route",
                "settlement_method",
                "clearing_house",
                "payment_time_lag",
                "payment_holiday_calendar",
            ]
        ]
    )
    on_combined = PATH["_CreateTradeTemplate"](
        "fixed_float",
        fields,
        Cells.from_rows(
            [["lot", "month", "lastday", "cleared", "financial", "TEST", "+2bd", combined]]
        ),
    )
    rows, contracts = 50, 6

    def steps(template: object) -> list[dict[str, int]]:
        batch = a_batch(sheet, rows, contracts, template)
        prepared = str(PATH["_PrepareTrades"](batch, sheet["history"]))
        results = str(PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING))
        return [
            call_profile(lambda: a_batch(sheet, rows, contracts, template)),
            call_profile(lambda: PATH["_PrepareTrades"](batch, sheet["history"])),
            call_profile(
                lambda: PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING)
            ),
            call_profile(lambda: PATH["_ReportRisk"](results, "all", "day")),
        ]

    plain, on_combination = steps(sheet["template"]), steps(on_combined)
    assert on_combination == plain
    assert all("combine_holiday_calendars" not in step for step in on_combination)
    # The union itself, once, when the combination was made.
    assert (
        call_profile(
            lambda: PATH["_CombineHolidayCalendars"](Cells.from_rows([[holidays], [holidays]]))
        )["combine_holiday_calendars"]
        == 1
    )
