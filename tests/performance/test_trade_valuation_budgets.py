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
from holiday_fixtures import key_in
from test_seam_allocation import KEYWORD_CALL, SLACK, least_peak

from catalyst.excel import bridge
from catalyst.excel.bridge import Cells

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
    # Under a name since payment-calendar-keys.md: the index prices on it and a template's key
    # selects it from the collection below.
    holidays = PATH["_CreateHolidayCalendar"]("PAYS", column([serial(d) for d in HOLIDAYS]))
    conventions = PATH["_CreateIndexConventions"]("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU")
    specifications = PATH["_CreateContractSpecifications"](
        Cells.from_rows(
            [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
        ),
        Cells.from_rows([["lot", 10000.0, "MMBTU", 0.0, 0.0]]),
    )
    index = PATH["_CreateIndex"](
        "gas",
        "Sample gas index",
        schedule,
        conventions,
        specifications,
        key_in(holidays),
        "lot",
        PATH["_CollectHolidayCalendars"](holidays),
    )
    fields = [
        "quantity_unit",
        "quantity_per",
        "schedule_method",
        "route",
        "settlement_method",
        "clearing_house",
        "payment_day",
        "payment_holiday_key",
        "settlement_frequency",
        "nearby",
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
                    "cleared",
                    "financial",
                    "TEST",
                    "+2bd",
                    "PAYS",
                    "monthly",
                    1.0,
                ]
            ]
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
        "holidays": holidays,
        "calendars": PATH["_CollectHolidayCalendars"](holidays),
    }


def a_batch(
    sheet: dict[str, Any],
    rows: int,
    contracts: int,
    template: object | None = None,
    calendars: object | None = None,
) -> str:
    body = Cells.from_rows(
        [
            [46289.0, CODES[1 + i % contracts], 2.0 if i % 3 else -3.0, 3.0 + (i % 7) / 100]
            for i in range(rows)
        ]
    )
    chosen = sheet["template"] if template is None else template
    held = sheet["calendars"] if calendars is None else calendars
    return str(PATH["_CreateTrades"](sheet["index"], sheet["headers"], body, chosen, held))


@pytest.fixture(scope="module")
def bilateral(sheet: dict[str, Any]) -> dict[str, Any]:
    """The sheet's batch made bilateral, since #177: the same fields with a counterparty for the
    clearing house and the route bilateral, and a curve anchored on the valuation day running to
    the end of 2028 at 0.9, past every payment."""
    fields = [
        "quantity_unit",
        "quantity_per",
        "schedule_method",
        "route",
        "settlement_method",
        "counterparty",
        "discount_curve_key",
        "payment_day",
        "payment_holiday_key",
        "settlement_frequency",
        "nearby",
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
                    "SOFR",
                    "+2bd",
                    "PAYS",
                    "monthly",
                    1.0,
                ]
            ]
        ),
    )
    curve = PATH["_CreateDiscountCurve"](
        "SOFR",
        Cells.from_rows([["date", "discount_factor"]]),
        Cells.from_rows([[serial(AS_OF), 1.0], [serial(np.datetime64("2028-12-31", "D")), 0.9]]),
    )
    curves = PATH["_CollectDiscountCurves"](curve)  # the collection of one, since slice 3
    return {"template": template, "curve": curve, "curves": curves}


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
        "_resolve_each": 1,
        "_text": 2,
        "_resolve": 2,
        "_PrepareTrades": 1,
        "prepared_trades": 1,
        "_the_slot_rows": 1,
        "calendar_rows": 1,
        "_the_set_amounts": 1,  # since #190 the set amounts by slot and by group, finite
        "MarketHistory.fixed_prices": 1,  # each fixed slot's settle, by its day and its contract
        "_the_histories": 1,  # two-index-fixed-float.md: the histories matched to the legs by index
        "_the_prepared_leg": 1,  # the leg prepared against its history
        "_the_sensitivity": 1,  # the sensitivity by contract, finite
        "_the_totals": 1,  # the two unsettled totals, finite
        "compensated": 1,  # two-index-one-price.md: the signed terms under one compensation
        "period_axis": 2,  # the month and the year displays, since #186
        "period_start": 2,
        "places_from": 2,
        "rows_through": 2,
        "display_periods": 2,
        "early_risk": 1,
        "early_fact": 2,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 3,
        "ResolvedTrades.descriptor": 1,  # the handle's name, the legs' index names joined,
        # since two-index-fixed-float.md
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
        "_resolve_each": 1,
        "_text": 2,
        "_resolve": 2,
        "_EvaluateTrades": 1,
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "compensated": 1,  # two-index-one-price.md: the signed terms under one compensation
        "_cleared_leg": 1,  # the leg's results, the nominal risk by reference
        "Market.live_prices": 1,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 2,
        "ResolvedTrades.descriptor": 1,  # the handle's name, the legs' index names joined,
        # since two-index-fixed-float.md
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
        ("_ReportReserves", 4, False),  # four totals, a currency and its unit, no day, since
        # #170, cva-reserve.md and currency-and-currency-unit.md, whose text column is no
        # numeric one and adds no call to either report
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
            expected["trade_values_label"] = 1  # the route's word for the labels, since #200
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
# columns, the rectangle and the DV01 column of zeros, and since #197 4,233 for all four, the
# cross-gamma's column of zeros beside the DV01's, within five slacks. Since
# currency-and-currency-unit.md each report's row holds the currency unit too, a word more: the
# values report 1,994 bytes where it was 1,967 and the reserves report 1,259 where it was 1,151.
RISK_PEAK = 5 * SLACK


def test_the_valuation_path_allocates_by_slot_and_never_by_trade(sheet: dict[str, Any]) -> None:
    trades = a_batch(sheet, 2_500, 24)
    # Since two-index-one-price.md the preparation sums the cash's signed terms under one
    # compensation, a handful of small arrays over the groups: a slack more.
    assert least_peak(lambda: PATH["_PrepareTrades"](trades, sheet["history"])) <= 11 * SLACK
    prepared = PATH["_PrepareTrades"](trades, sheet["history"])
    assert (
        least_peak(lambda: PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING))
        <= KEYWORD_CALL + 2 * SLACK
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
        return PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curves"])

    assert str(tick()).split(":")[1:3] == ["trade_results", "gas"]
    # The curve the third handle resolved; the kernel's bilateral path, the rules and the discounted
    # snapshot, beside the evaluator; nothing of the preparation, and no sort on a tick.
    assert call_profile(tick) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_resolve_each": 1,
        "_text": 3,
        "_resolve": 3,
        "_EvaluateTrades": 1,
        "trade_results": 1,
        "_the_markets": 1,  # two-index-fixed-float.md: the markets matched to the legs by history
        "_the_contributions": 1,  # the leg's live contributions off its market
        "compensated": 1,  # two-index-one-price.md: the signed terms under one compensation
        "_the_lots_arrays": 1,  # the leg's discounted lots and their sums
        "_the_lots_checked": 1,
        "_discounted_leg": 1,  # the leg's results over them
        "_the_curves": 1,  # the rules and the key bound, since named-curves-slice-3.md
        "curve_named": 1,  # the shared step, shared-curve-binding.md
        "_each_period_finite": 2,  # each curve's DV01 views and cross-gamma views finite
        "curve_starts_on": 1,  # the start rule, shared with the cashflows since #200
        "DiscountCurve.start_date": 2,
        "DiscountCurve.max_date": 1,
        "Market.live_prices": 1,
        "_discounted": 1,
        "factors_on": 1,  # the factors by position, shared since #200
        "discounted": 1,  # the values and the DV01s, shared since #200
        "_cross_gamma": 1,  # since #197, after every rule of the discounted path
        "early_risk": 3,  # since #186, and the cross-gamma's since #197
        "early_fact": 6,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 8,
        "ResolvedTrades.descriptor": 1,  # the handle's name, the legs' index names joined,
        # since two-index-fixed-float.md
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
    discounted = PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curves"])
    live = bridge.live_handles()

    def selected(on_curve: bool, risk: str, bucket: str) -> dict[str, int]:
        # By day, by reference, all three of a bilateral result copied through the day union;
        # by month and by year, since #186, the display axis, the saved refusals read for every
        # risk shown and a copy per column, a cleared result's DV01 nothing to copy or refuse.
        if bucket == "day":
            copies = {"placed": 4} if risk == "all" and on_curve else {}
            return {"_day_view": 1, **copies}
        if risk in ("dv01", "cross_gamma"):
            # Since #197 the cross-gamma like the DV01: a cleared result's the known zero, a
            # column of zeros made and nothing refused; since slice 2 the contribution's
            # vector picked for the bucket.
            of = "_dv01_of" if risk == "dv01" else "_cross_of"
            shown = {"EarlyRisk.refuse": 1, "placed": 1, of: 1} if on_curve else {}
            return {"_period_view": 1, "_saved": 1, **shown}
        if risk == "all":
            n = 4 if on_curve else 2
            of = {"_dv01_of": 1, "_cross_of": 1} if on_curve else {}
            return {
                "_period_view": 1,
                "_period_all": 1,
                "_saved": 1,
                "EarlyRisk.refuse": n,
                "placed": n,
                **of,
            }
        return {"_period_view": 1, "_saved": 1, "EarlyRisk.refuse": 1, "placed": 1}

    for results, on_curve in ((cleared, False), (discounted, True)):
        for risk in ("nominal_delta", "delta", "dv01", "cross_gamma", "all"):
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
                    "choice": 2,  # the risk's word, one of five, and the bucket's, one of three
                    "TradeResults.report": 1,  # the result's own selection, since #180
                    "risk_view": 1,
                    "delta_labels": 1,  # the headings, spelled once in risk_report.py
                    "dv01_label": 1,
                    "cross_gamma_label": 1,
                    **({"curve_words": 1} if on_curve else {}),  # the curve's word, since slice 2
                    **selected(on_curve, risk, bucket),
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
# month and year, 5,093 before them, and 8,257 on 2026-10-17 since #197, the cross-gamma's
# weight by group, its vector by slot and its four saved views, and 9,249 on 2026-10-18 since
# named-curves-slice-3.md, the DV01 totals by curve and the keyed payments' records, within
# ten slacks; the risk
# report of all three by day 6,263 bytes, 48 rows under the Total, the 24 observation days and
# the 24 payment days in four columns, the three vectors placed on the union, against the
# cleared batch's 3,591, within seven slacks, and 7,313 for all four since #197, the
# cross-gamma's column placed beside them, within eight.
def test_the_bilateral_path_allocates_by_group_and_slot_and_never_by_trade(
    sheet: dict[str, Any], bilateral: dict[str, Any]
) -> None:
    prepared = PATH["_PrepareTrades"](
        a_batch(sheet, 2_500, 24, bilateral["template"]), sheet["history"]
    )
    assert (
        least_peak(lambda: PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curves"]))
        <= 10 * SLACK
    )
    results = PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curves"])
    assert least_peak(lambda: PATH["_ReportRisk"](results, "all", "day")) <= 8 * SLACK


# --- a collection of results through the seam, since #180 -----------------------------------------


def n_results(
    sheet: dict[str, Any], bilateral: dict[str, Any], rows: int, contracts: int, n: int = 2
) -> list[str]:
    """n results of one bilateral batch over one market and curve, n handles of one content."""
    prepared = PATH["_PrepareTrades"](
        a_batch(sheet, rows, contracts, bilateral["template"]), sheet["history"]
    )
    return [
        str(PATH["_EvaluateTrades"](prepared, sheet["market"], bilateral["curves"]))
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
        "_contributions_of": 1,  # since slice 2: the contributions counted and the words made
        "_cross_contributions": 2 * n,
        "_curve_words": 1,  # one wording for the rate and the cross groups
        "curve_words": 1,
        "_grouped_by_curve": 1,
        "_grouped_by_index_and_curve": 1,
        "_index_group": 1,
        "_rate_group": 1,
        "_cross_group": 1,
        "_summed": 11,
        "_compensated": 15,
        "_outrun": 4,
        "_report_axes": 1,
        "_period_report_axes": 2,
        "period_start": 2,
        "places_from": 6,
        "rows_through": 4,
        "display_periods": 2,
        "_early_lots": 2,
        "early_risk": 4,
        "early_fact": 8,
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 30,
        "_publish": 1,
    }
    # The seam makes no numpy call of its own: every one below is the collector's, the same at two
    # handles and at twenty-four, as test_aggregate_budgets.py pins them; before #180's review a
    # look per text cell counted the texts before it, n squared over the range.
    assert numpy_calls(lambda: PATH["_AggregateResults"](cells)) == {
        "generic.astype": 2,  # the valuation day to its month and its year, since #186
        "ndarray.any": 15,  # since #197 the cross group's four looks for a sum past the largest
        "ndarray.astype": 14,  # the display axes' keys, periods and first days
        "ndarray.flatten": 14,  # since #197 the cross group's four unions among the uniques
        "ndarray.nonzero": 8,  # the looks for risk before the start, four measures, two buckets
        "ndarray.ravel": 8,
        "ndarray.searchsorted": 23,  # since #197 eight more, the cross group's places
        "ndarray.setflags": 46,  # since #197 thirteen more, the cross group's arrays and places
        "ndarray.sort": 14,
        "numpy._make_extobj": 15,
        "numpy._unique_hash": 14,
        "numpy.arange": 2,  # the two display axes
        "numpy.array": 3,  # the three groups' positions
        "numpy.asanyarray": 36,
        "numpy.zeros": 30,  # fifteen compensated passes, two each
        "ufunc.reduce": 15,
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
    # By month and by year, since #186, the saved facts read: the one index group's for a delta,
    # the one rate group's for the DV01, all three under all.
    for risk, selected, refused in (
        ("nominal_delta", {"_lots": 1, "placed": 1}, 1),
        ("delta", {"_discounted_lots": 1, "placed": 1}, 1),
        ("dv01", {"_dv01": 1, "placed": 1}, 1),
        ("cross_gamma", {"_cross_gamma": 1, "placed": 1}, 1),
        (
            "all",
            {
                "_aggregate_all": 1,
                "_lots": 1,
                "_discounted_lots": 1,
                "_dv01": 1,
                "_cross_gamma": 1,
                "placed": 4,
            },
            4,
        ),
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
                "delta_labels": 1,  # one index group; the headings spelled once in risk_report.py
                "dv01_label": 2,  # one rate group, and the cleared column of its one currency
                "cross_gamma_label": 1,  # one cross group, since #197
                "_axes_of": 1,
                "_refuse_early": 1,  # since #186; the saved refusals read by month and by year
                **({} if bucket == "day" else {"_early_of": 1, "EarlyRisk.refuse": refused}),
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
# unions and the record, and 19,092 on 2026-10-17 since #197 with the cross group, its four
# unions and places beside the index group's, within nineteen slacks; its report of all three by
# day 6,263 bytes, the same rectangle a result's report lays out, 48 dated rows in four columns,
# and all four since #197 within eight slacks.
def test_a_collection_allocates_by_the_saved_entries_and_its_report_by_the_rectangle(
    sheet: dict[str, Any], bilateral: dict[str, Any]
) -> None:
    handles = n_results(sheet, bilateral, 2_500, 24)
    cells = Cells.from_rows([[handle] for handle in handles])
    assert least_peak(lambda: PATH["_AggregateResults"](cells)) <= 19 * SLACK
    collection = str(PATH["_AggregateResults"](cells))
    assert least_peak(lambda: PATH["_ReportRisk"](collection, "all", "day")) <= 8 * SLACK


# --- a combined payment calendar, combine-holiday-calendars.md ------------------------------------

# What a key of two names adds to the making of a batch beside a key of one.
COMBINED_AT_CREATION = {
    "calendar_named": 1,  # the second name found in the collection
    "combine_holiday_calendars": 1,
    "_owning": 1,  # the union's days, copied once and frozen
    "WorkCounter.hit": 3,  # the calendars taken, the days read and the days kept
}


# A template whose key joins the sheet's calendar with a twin of it, PAYS+TWIN, does the plain
# template's work, call for call, at preparation, evaluation and reporting: since
# payment-calendar-keys.md the union runs once, when the batch is made, where it ran when the
# combination's own cell was made, and no step after it reads a calendar again.
def test_a_combined_payment_calendar_adds_no_work_after_creation(
    call_profile: CallProfile, sheet: dict[str, Any]
) -> None:
    twin = PATH["_CreateHolidayCalendar"]("TWIN", column([serial(d) for d in HOLIDAYS]))
    both = PATH["_CollectHolidayCalendars"](Cells.from_rows([[sheet["holidays"]], [twin]]))
    fields = Cells.from_rows(
        [
            [
                "quantity_unit",
                "quantity_per",
                "schedule_method",
                "route",
                "settlement_method",
                "clearing_house",
                "payment_day",
                "payment_holiday_key",
                "settlement_frequency",
                "nearby",
            ]
        ]
    )
    on_combined = PATH["_CreateTradeTemplate"](
        "fixed_float",
        fields,
        Cells.from_rows(
            [
                [
                    "lot",
                    "month",
                    "lastday",
                    "cleared",
                    "financial",
                    "TEST",
                    "+2bd",
                    "PAYS+TWIN",
                    "monthly",
                    1.0,
                ]
            ]
        ),
    )
    rows, contracts = 50, 6

    def steps(template: object) -> list[dict[str, int]]:
        batch = a_batch(sheet, rows, contracts, template, both)
        prepared = str(PATH["_PrepareTrades"](batch, sheet["history"]))
        results = str(PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING))
        return [
            call_profile(lambda: a_batch(sheet, rows, contracts, template, both)),
            call_profile(lambda: PATH["_PrepareTrades"](batch, sheet["history"])),
            call_profile(
                lambda: PATH["_EvaluateTrades"](prepared, sheet["market"], bridge.MISSING)
            ),
            call_profile(lambda: PATH["_ReportRisk"](results, "all", "day")),
        ]

    plain, on_combination = steps(sheet["template"]), steps(on_combined)
    assert on_combination[1:] == plain[1:]
    assert all("combine_holiday_calendars" not in step for step in on_combination[1:])
    # The union itself, once, when the batch is made: the second name found, the two calendars
    # combined into one, its three counts reported; nothing else of the creation differs.
    created, created_plain = on_combination[0], plain[0]
    assert {
        name: created.get(name, 0) - created_plain.get(name, 0)
        for name in sorted(set(created) | set(created_plain))
        if created.get(name, 0) != created_plain.get(name, 0)
    } == COMBINED_AT_CREATION
