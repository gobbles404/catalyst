"""Whole-call benchmark of the prepared paths on whichever source tree PYTHONPATH names.

Written for the numpy review of 2026-10-01 (docs/reviews/numpy-review.md). Run with

    PYTHONPATH=<tree>/src .venv/bin/python tools/performance/numpy_review/bench_harness.py \\
        --scenarios NAME[,NAME...] [--all] [--list] [--batches 7] [--batch-ms 20] \\
        [--peak-repeats 3] [--json OUT.jsonl] [--no-ledger] [--no-time]

Each scenario builds its inputs before any clock starts, warms once and checks the answer, then
measures three things. Time: iterations calibrated to about --batch-ms per batch, --batches
batches, the per-call median and min of the batch means in microseconds; a creator's handle is
released after every call (bridge.release) so the store never grows and no object is retained
across iterations. Peak: the tracemalloc peak of one warm call, the least of --peak-repeats, as
tests/performance/test_seam_allocation.py pins it. Ledgers: which of the package's own functions
ran and which numpy C calls cProfile saw, exactly as tests/performance/conftest.py counts them.
One JSON object per scenario is printed, and appended to --json when given; its "tree" field says
which goosedove was imported, so an as-is run and a proposed run cannot be confused. Timings choose
experiments; nothing gates on them.
"""

import argparse
import cProfile
import ctypes
import json
import re
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

import goosedove
from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells, DateColumn, NumberColumn, TextColumn
from goosedove.excel.probes import probe

PACKAGE_DIR = str(Path(goosedove.__file__).parent)
ENTRY = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}
PUBLISHES = {name: publishes for name, _, _, _, publishes in bridge.function_specs()}


# The three looks with no probe of their own, as tests/performance/conftest.py registers them,
# and a column of dates out, so the serials conversion has a row.
@probe
def BenchFirstOfNumbers(values: NumberColumn) -> float:
    return float(values[0])


@probe
def BenchFirstOfDates(dates: DateColumn) -> str:
    return str(dates[0])


@probe
def BenchFirstOfNames(names: TextColumn) -> str:
    return names[0]


@probe
def BenchEchoDates(dates: DateColumn) -> DateColumn:
    return DateColumn(dates)


ENTRY.update(
    {
        name: bridge.entry(name)
        for name in (
            "BenchFirstOfNumbers",
            "BenchFirstOfDates",
            "BenchFirstOfNames",
            "BenchEchoDates",
        )
    }
)


# --- the ledgers, as tests/performance/conftest.py counts them ---------------------------------
_NUMPY_METHOD = re.compile(r"<method '(\w+)' of 'numpy\.(\w+)' objects>")
_NUMPY_FUNCTION = re.compile(r"<built-in method numpy\.(\w+)>")


def ledgers(fn: Callable[[], object]) -> tuple[dict[str, int], dict[str, int]]:
    """The package's own functions that ran, and the numpy C calls cProfile saw."""
    profiler = cProfile.Profile()
    profiler.enable()
    fn()
    profiler.disable()
    package: dict[str, int] = {}
    numpy_calls: dict[str, int] = {}
    for entry in profiler.getstats():
        code = entry.code
        if isinstance(code, str):
            method = _NUMPY_METHOD.fullmatch(code)
            function = _NUMPY_FUNCTION.fullmatch(code)
            if method:
                name = f"{method.group(2)}.{method.group(1)}"
            elif function:
                name = f"numpy.{function.group(1)}"
            else:
                continue
            numpy_calls[name] = numpy_calls.get(name, 0) + entry.callcount
        elif code.co_filename.startswith(PACKAGE_DIR):
            package[code.co_qualname] = package.get(code.co_qualname, 0) + entry.callcount
    return dict(sorted(package.items())), dict(sorted(numpy_calls.items()))


# --- inputs, mirroring tests/performance/test_seam_allocation.py -------------------------------
EPOCH = np.datetime64("1899-12-30")
Args = tuple[Any, ...]


def column(n: int) -> Cells:
    return Cells.from_rows([[float(i)] for i in range(n)])


def date_column(n: int) -> Cells:
    return Cells.from_rows([[float(46276 + i)] for i in range(n)])


def text_column(n: int) -> Cells:
    return Cells.from_rows([[f"name{i}"] for i in range(n)])


def mixed(n: int) -> Cells:
    return Cells.from_rows([[f"n{i}", 46164.0 + i, float(i), i % 2 == 0] for i in range(n // 4)])


HEADERS = Cells.from_rows([["date", "product", "quantity", "cleared"]])


def trades(n: int) -> Cells:
    return Cells.from_rows([[46276.0 + i, f"p{i}", float(i), i % 2 == 0] for i in range(n // 4)])


CURVE_HEADERS = Cells.from_rows([["date", "discount_factor"]])


def curve_body(rows: int) -> Cells:
    return Cells.from_rows([[46276.0 + i, 1.0 - i * 1e-5] for i in range(rows)])


def anchor_body(anchors: int, days: int) -> Cells:
    step = days // (anchors - 1)
    return Cells.from_rows([[46276.0 + i * step, 1.0 - i * step * 1e-5] for i in range(anchors)])


def schedule_columns(contracts: int, days_apart: int = 30) -> tuple[Cells, Cells, Cells, Cells]:
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    futures = Cells.from_rows([[46161.0 + days_apart * i] for i in range(contracts)])
    options = Cells.from_rows([[46156.0 + days_apart * i] for i in range(contracts)])
    publications = Cells.from_rows([[46162.0 + days_apart * i] for i in range(contracts)])
    return codes, futures, options, publications


def holiday_column(days: int) -> Cells:
    return Cells.from_rows([[46023.0 + 7 * i] for i in range(days)])


SPECIFICATION_HEADERS = Cells.from_rows(
    [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)


def specification_body(contracts: int) -> Cells:
    return Cells.from_rows(
        [[f"contract {i}", 1000.0 + i, "MMBTU", 3.0, 2.0] for i in range(contracts)]
    )


def conventions() -> object:
    return ENTRY["_CreateIndexConventions"]("USD", "MMBTU", "USD", "energy", "MMBTU")


def an_index(schedule: object, holidays: object = MISSING, name: str = "sample") -> object:
    return ENTRY["_CreateIndex"](
        name,
        schedule,
        conventions(),
        ENTRY["_CreateContractSpecifications"](SPECIFICATION_HEADERS, specification_body(1)),
        holidays,
    )


def thursdays(count: int) -> NDArray[np.datetime64]:
    """That many holidays a week apart from 1 January 2026, the days holiday_column lists."""
    return EPOCH + (46023 + 7 * np.arange(count)).astype("timedelta64[D]")


def fixings_columns(rows: int, holidays: int) -> tuple[Cells, Cells]:
    days = np.busday_offset(
        np.datetime64("2026-05-01"), np.arange(rows), holidays=thursdays(holidays)
    )
    serials = (days - EPOCH).astype(np.int64)
    return (
        Cells.from_rows([[float(serials[i])] for i in range(rows)]),
        Cells.from_rows([[100.0 + i % 7] for i in range(rows)]),
    )


def futures_index(contracts: int, days_apart: int = 30, holidays: int = 100) -> object:
    codes, futures, _, _ = schedule_columns(contracts, days_apart)
    schedule = ENTRY["_CreateFuturesSchedule"](codes, futures, MISSING)
    return an_index(schedule, ENTRY["_CreateHolidayCalendar"](holiday_column(holidays)))


def valuation() -> object:
    return ENTRY["_CreateValuationDate"](46276.0, 0.5)


def futures_calendar(contracts: int, days_apart: int = 30) -> tuple[object, object]:
    index = futures_index(contracts, days_apart)
    return ENTRY["_CreateCalendar"](valuation(), index), index


def futures_history(contracts: int, days_apart: int = 30) -> tuple[object, object, object]:
    """A calendar valued 2026-09-11 over that many contracts, and fixings on every business day
    from 2026-05-01 to the day before under a hundred Thursdays: (calendar, fixings, index)."""
    made, index = futures_calendar(contracts, days_apart)
    rows = int(np.busday_count("2026-05-01", "2026-09-11", holidays=thursdays(100)))
    fixings = ENTRY["_CreateFuturesFixings"](*fixings_columns(rows, 100), index)
    return made, fixings, index


def gas_daily_month_columns(months: int) -> tuple[Cells, Cells, Cells]:
    firsts = np.arange("2026-01", "2226-01", dtype="datetime64[M]")[: months + 1]
    starts = firsts[:-1].astype("datetime64[D]")
    ends = firsts[1:].astype("datetime64[D]") - np.timedelta64(1, "D")
    first = starts.astype(np.int64) + 25569  # 1 January 1970 is serial 25569
    last = ends.astype(np.int64) + 25569
    return (
        Cells.from_rows([[f"c{i}"] for i in range(months)]),
        Cells.from_rows([[float(first[i])] for i in range(months)]),
        Cells.from_rows([[float(last[i])] for i in range(months)]),
    )


def gas_daily_index(months: int) -> object:
    return an_index(ENTRY["_CreateGasDailySchedule"](*gas_daily_month_columns(months)))


def gas_daily_history(months: int) -> tuple[object, object, object]:
    """A calendar of that many months from January 2026 valued 2026-09-11, and prints from New
    Year's Day to the 11th: (calendar, fixings, index)."""
    index = gas_daily_index(months)
    made = ENTRY["_CreateCalendar"](valuation(), index)
    days = 46276 - 46023 + 1
    fixings = ENTRY["_CreateGasDailyFixings"](
        Cells.from_rows([[46023.0 + i] for i in range(days)]),
        Cells.from_rows([[2.8 + (i % 30) / 100] for i in range(days)]),
        index,
    )
    return made, fixings, index


def iferc_columns(contracts: int) -> tuple[Cells, Cells, Cells]:
    codes, last_trading, _, publications = schedule_columns(contracts)
    return codes, last_trading, publications


def iferc_fixing_columns(count: int) -> tuple[Cells, Cells]:
    codes, _, _, _ = schedule_columns(count)
    return codes, Cells.from_rows([[2.0 + i / 100] for i in range(count)])


def iferc_index(months: int) -> object:
    return an_index(ENTRY["_CreateIfercSchedule"](*iferc_columns(months)))


def iferc_history_all_fixed(months: int) -> tuple[object, object, object]:
    index = iferc_index(months)
    valued = ENTRY["_CreateValuationDate"](46162.0 + 30 * months, 0.5)
    made = ENTRY["_CreateCalendar"](valued, index)
    fixings = ENTRY["_CreateIfercFixings"](*iferc_fixing_columns(months), index)
    return made, fixings, index


def flow_day_columns(count: int) -> tuple[Cells, Cells]:
    return (
        Cells.from_rows([[46266.0 + i] for i in range(count)]),
        Cells.from_rows([[2.8 + (i % 30) / 100] for i in range(count)]),
    )


def price_column(prices: int) -> Cells:
    return Cells.from_rows([[74.25 + i % 7 - 3.0] for i in range(prices)])


def market_sources(contracts: int, days_apart: int) -> tuple[object, object]:
    made, fixings, _ = futures_history(contracts, days_apart)
    history = ENTRY["_CreateMarketHistory"](made, fixings)
    expiries = 46161.0 + days_apart * np.arange(contracts)
    first = int(np.searchsorted(expiries, 46276.0))
    quotes = Cells.from_rows([[70.0 + i % 5] for i in range(contracts - first)])
    return history, ENTRY["_CreatePriceVector"]("sample", quotes)


_keep: list[object] = []  # the ctypes buffers, kept alive for the life of the run


def host_buffers(n: int) -> tuple[int, int]:
    kinds = (ctypes.c_uint8 * n)(*([0] * n))
    numbers = (ctypes.c_double * n)(*[float(i) for i in range(n)])
    _keep.extend((kinds, numbers))
    return ctypes.addressof(kinds), ctypes.addressof(numbers)


# --- the scenarios -------------------------------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    name: str
    function: str
    args: Callable[[], Args]  # built once, before any clock
    check: Callable[[object], None]


def no_error(result: object) -> None:
    if isinstance(result, str) and result.startswith("#ERROR"):
        raise AssertionError(result)


def is_error(result: object) -> None:
    if not (isinstance(result, str) and result.startswith("#ERROR")):
        raise AssertionError(f"expected an #ERROR text, got {result!r}")


Catalogue = dict[str, Scenario]


def _add(
    into: Catalogue,
    name: str,
    function: str,
    args: Callable[[], Args],
    check: Callable[[object], None] = no_error,
) -> None:
    into[name] = Scenario(name, function, args, check)


def _probe_scenarios(into: Catalogue) -> None:
    _add(into, "probe.SumArray.10k", "SumArray", lambda: (column(10_000),))
    _add(into, "probe.CountMixed.10k", "CountMixed", lambda: (mixed(10_000),))
    _add(into, "probe.SumQuantity.10k", "SumQuantity", lambda: (HEADERS, trades(10_000)))
    _add(into, "probe.Dot.10k", "Dot", lambda: (column(10_000), column(10_000)))
    _add(into, "probe.EchoColumn.10k", "EchoColumn", lambda: (column(10_000),))
    _add(into, "probe.EchoMixed.numbers.10k", "EchoMixed", lambda: (column(10_000),))
    _add(into, "probe.EchoMixed.mixed.10k", "EchoMixed", lambda: (mixed(10_000),))
    grid = [[float(r * 100 + c) for c in range(100)] for r in range(100)]
    _add(into, "probe.RowSums.100x100", "RowSums", lambda: (Cells.from_rows(grid),))
    _add(into, "probe.Grid.5000x2", "Grid", lambda: (5000, 2))
    _add(into, "look.FirstOfNumbers.10k", "BenchFirstOfNumbers", lambda: (column(10_000),))
    _add(into, "look.FirstOfDates.100", "BenchFirstOfDates", lambda: (date_column(100),))
    _add(into, "look.FirstOfDates.10k", "BenchFirstOfDates", lambda: (date_column(10_000),))
    _add(into, "look.FirstOfNames.10k", "BenchFirstOfNames", lambda: (text_column(10_000),))
    _add(into, "look.EchoDates.10k", "BenchEchoDates", lambda: (date_column(10_000),))

    def bad_last() -> Args:
        rows: list[list[object]] = [[float(i)] for i in range(10_000)]
        rows[-1][0] = "x"
        return (Cells.from_rows(rows),)

    def empty_deep() -> Args:
        rows: list[list[object]] = [[f"n{i}"] for i in range(10_000)]
        rows[5_000][0] = ""
        return (Cells.from_rows(rows),)

    def bad_date_deep() -> Args:
        rows: list[list[object]] = [[float(46276 + i)] for i in range(10_000)]
        rows[5_000][0] = 46276.5
        return (Cells.from_rows(rows),)

    _add(into, "reject.SumArray.text-last.10k", "SumArray", bad_last, is_error)
    _add(into, "reject.CountMixed.empty-deep.10k", "CountMixed", empty_deep, is_error)
    _add(
        into, "reject.FirstOfDates.fraction-deep.10k", "BenchFirstOfDates", bad_date_deep, is_error
    )
    _add(
        into,
        "own.cells_from_buffers.10k",
        "cells_from_buffers",
        lambda: (*host_buffers(10_000), 10_000, 1, "", 1),
    )
    _add(
        into,
        "own.cells_from_buffers.100",
        "cells_from_buffers",
        lambda: (*host_buffers(100), 100, 1, "", 1),
    )


def index_args() -> Args:
    codes, futures, _, _ = schedule_columns(13)
    return (
        "Henry Hub NYMEX",
        ENTRY["_CreateFuturesSchedule"](codes, futures, MISSING),
        conventions(),
        ENTRY["_CreateContractSpecifications"](SPECIFICATION_HEADERS, specification_body(12)),
        ENTRY["_CreateHolidayCalendar"](holiday_column(100)),
    )


def _definition_scenarios(into: Catalogue) -> None:
    _add(into, "create.ValuationDate", "_CreateValuationDate", lambda: (46276.0, 0.5))
    _add(
        into,
        "create.DiscountCurve.daily.3631",
        "_CreateDiscountCurve",
        lambda: (CURVE_HEADERS, curve_body(3_631)),
    )
    _add(
        into,
        "create.DiscountCurve.anchors12.3630",
        "_CreateDiscountCurve",
        lambda: (CURVE_HEADERS, anchor_body(12, 3_630)),
    )
    _add(
        into,
        "create.FuturesSchedule.120",
        "_CreateFuturesSchedule",
        lambda: schedule_columns(120)[:3],
    )
    _add(
        into,
        "create.FuturesSchedule.1200",
        "_CreateFuturesSchedule",
        lambda: schedule_columns(1200)[:3],
    )
    _add(
        into, "create.HolidayCalendar.100", "_CreateHolidayCalendar", lambda: (holiday_column(100),)
    )
    _add(
        into,
        "create.HolidayCalendar.1000",
        "_CreateHolidayCalendar",
        lambda: (holiday_column(1000),),
    )
    _add(into, "create.IfercSchedule.120", "_CreateIfercSchedule", lambda: iferc_columns(120))
    _add(
        into,
        "create.GasDailySchedule.120",
        "_CreateGasDailySchedule",
        lambda: gas_daily_month_columns(120),
    )
    _add(
        into,
        "create.IndexConventions",
        "_CreateIndexConventions",
        lambda: ("USD", "MMBTU", "USD", "energy", "MMBTU"),
    )
    _add(
        into,
        "create.ContractSpecifications.120",
        "_CreateContractSpecifications",
        lambda: (SPECIFICATION_HEADERS, specification_body(120)),
    )
    _add(into, "create.Index.futures", "_CreateIndex", index_args)
    for rows in (260, 2_600, 26_000):
        apart = 30 if rows < 26_000 else 3_650
        _add(
            into,
            f"create.FuturesFixings.{rows}",
            "_CreateFuturesFixings",
            lambda rows=rows, apart=apart: (*fixings_columns(rows, 100), futures_index(2, apart)),
        )
    for days in (365, 3_652):
        _add(
            into,
            f"create.GasDailyFixings.{days}",
            "_CreateGasDailyFixings",
            lambda days=days: (*flow_day_columns(days), gas_daily_index(12)),
        )
    for months in (120, 1_200):
        _add(
            into,
            f"create.IfercFixings.{months}",
            "_CreateIfercFixings",
            lambda months=months: (*iferc_fixing_columns(months), iferc_index(months)),
        )
    for prices in (120, 10_000):
        _add(
            into,
            f"create.PriceVector.{prices}",
            "_CreatePriceVector",
            lambda prices=prices: ("sample", price_column(prices)),
        )


FUTURES_SIZES = (
    (13, 30),
    (122, 30),
    (13, 3_000),
)  # contracts and days apart: 360, 3,630 and 36,000 days


def _market_scenarios(into: Catalogue) -> None:
    for contracts, apart in FUTURES_SIZES:
        days = (contracts - 1) * apart
        _add(
            into,
            f"create.Calendar.futures.{days}",
            "_CreateCalendar",
            lambda c=contracts, d=apart: (valuation(), futures_index(c, d)),
        )
        _add(
            into,
            f"create.MarketHistory.futures.{days}",
            "_CreateMarketHistory",
            lambda c=contracts, d=apart: futures_history(c, d)[:2],
        )
    for months in (12, 120):
        _add(
            into,
            f"create.Calendar.gasdaily.{months}m",
            "_CreateCalendar",
            lambda m=months: (valuation(), gas_daily_index(m)),
        )
        _add(
            into,
            f"create.MarketHistory.gasdaily.{months}m",
            "_CreateMarketHistory",
            lambda m=months: gas_daily_history(m)[:2],
        )
    for months in (120, 1_200):
        _add(
            into,
            f"create.Calendar.iferc.{months}m",
            "_CreateCalendar",
            lambda m=months: (valuation(), iferc_index(m)),
        )
        _add(
            into,
            f"create.MarketHistory.iferc.{months}m",
            "_CreateMarketHistory",
            lambda m=months: iferc_history_all_fixed(m)[:2],
        )
    _add(into, "create.Market.futures.360", "_CreateMarket", lambda: market_sources(13, 30))
    _add(into, "create.Market.futures.3630", "_CreateMarket", lambda: market_sources(122, 30))


def _reader_scenarios(into: Catalogue) -> None:
    read = "util_ReadHandle"
    _add(into, "read.ValuationDate", read, lambda: (valuation(),))
    _add(
        into,
        "read.DiscountCurve.3631",
        read,
        lambda: (ENTRY["_CreateDiscountCurve"](CURVE_HEADERS, curve_body(3_631)),),
    )
    _add(
        into,
        "read.FuturesSchedule.120",
        read,
        lambda: (ENTRY["_CreateFuturesSchedule"](*schedule_columns(120)[:3]),),
    )
    _add(
        into,
        "read.HolidayCalendar.100",
        read,
        lambda: (ENTRY["_CreateHolidayCalendar"](holiday_column(100)),),
    )
    _add(
        into,
        "read.ContractSpecifications.120",
        read,
        lambda: (
            ENTRY["_CreateContractSpecifications"](SPECIFICATION_HEADERS, specification_body(120)),
        ),
    )
    _add(into, "read.Index", read, lambda: (ENTRY["_CreateIndex"](*index_args()),))
    _add(
        into,
        "read.FuturesFixings.2600",
        read,
        lambda: (ENTRY["_CreateFuturesFixings"](*fixings_columns(2_600, 100), futures_index(2)),),
    )
    _add(
        into,
        "read.PriceVector.10000",
        read,
        lambda: (ENTRY["_CreatePriceVector"]("sample", price_column(10_000)),),
    )
    for contracts, apart in FUTURES_SIZES[:2]:
        days = (contracts - 1) * apart
        _add(
            into,
            f"read.Calendar.futures.{days}",
            read,
            lambda c=contracts, d=apart: (futures_calendar(c, d)[0],),
        )
        _add(
            into,
            f"read.MarketHistory.futures.{days}",
            read,
            lambda c=contracts, d=apart: (
                ENTRY["_CreateMarketHistory"](*futures_history(c, d)[:2]),
            ),
        )
        _add(
            into,
            f"read.Market.futures.{days}",
            read,
            lambda c=contracts, d=apart: (ENTRY["_CreateMarket"](*market_sources(c, d)),),
        )
    _add(
        into,
        "read.MarketHistory.gasdaily.12m",
        read,
        lambda: (ENTRY["_CreateMarketHistory"](*gas_daily_history(12)[:2]),),
    )
    _add(
        into,
        "read.MarketHistory.iferc.120m",
        read,
        lambda: (ENTRY["_CreateMarketHistory"](*iferc_history_all_fixed(120)[:2]),),
    )
    _add(
        into,
        "read.Calendar.iferc.1200m",
        read,
        lambda: (ENTRY["_CreateCalendar"](valuation(), iferc_index(1_200)),),
    )


def scenarios() -> Catalogue:
    """Every scenario by name: the probes and looks, the creators, the readers."""
    into: Catalogue = {}
    _probe_scenarios(into)
    _definition_scenarios(into)
    _market_scenarios(into)
    _reader_scenarios(into)
    return into


# --- the clocks ----------------------------------------------------------------------------------
def runner(scenario: Scenario, args: Args) -> Callable[[], object]:
    """One warm call of the scenario, a creator's publication released inside it."""
    if scenario.function == "cells_from_buffers":
        own = bridge.cells_from_buffers
        pointers = cast(tuple[int, int, int, int, str, int], args)
        return lambda: own(*pointers)
    run = ENTRY[scenario.function]
    if not PUBLISHES.get(scenario.function):
        return lambda: run(*args)
    release = bridge.release

    def call() -> object:
        text = run(*args)
        if isinstance(text, str) and not text.startswith("#ERROR"):
            release(text)
        return text

    return call


def timed(fn: Callable[[], object], batches: int, batch_ms: float) -> tuple[float, float, int]:
    """The per-call median and min of the batch means, in microseconds, and the batch length."""
    iterations = 1
    while True:
        started = perf_counter_ns()
        for _ in range(iterations):
            fn()
        elapsed_ms = (perf_counter_ns() - started) / 1e6
        if elapsed_ms >= batch_ms or iterations >= 1_000_000:
            break
        iterations *= 2
    means: list[float] = []
    for _ in range(batches):
        started = perf_counter_ns()
        for _ in range(iterations):
            fn()
        means.append((perf_counter_ns() - started) / 1e3 / iterations)
    means.sort()
    return means[len(means) // 2], means[0], iterations


def peak_bytes(fn: Callable[[], object], repeats: int) -> int:
    """The least tracemalloc peak of that many warm calls."""
    peaks: list[int] = []
    for _ in range(repeats):
        fn()
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            fn()
            peaks.append(tracemalloc.get_traced_memory()[1])
        finally:
            tracemalloc.stop()
    return min(peaks)


def measure(scenario: Scenario, a: argparse.Namespace) -> dict[str, Any]:
    args = scenario.args()
    fn = runner(scenario, args)
    scenario.check(fn())  # warm, and check the answer
    row: dict[str, Any] = {
        "label": a.label,
        "tree": goosedove.__file__,
        "scenario": scenario.name,
        "function": scenario.function,
    }
    if not a.no_time:
        median, least, iterations = timed(fn, a.batches, a.batch_ms)
        row.update(us_median=round(median, 3), us_min=round(least, 3), iterations=iterations)
    row["peak_bytes"] = peak_bytes(fn, a.peak_repeats)
    if not a.no_ledger:
        package, numpy_calls = ledgers(fn)
        row["package_ledger"] = package
        row["numpy_ledger"] = numpy_calls
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--scenarios", default="", help="comma-separated substrings of names")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--batches", type=int, default=7)
    parser.add_argument("--batch-ms", type=float, default=20.0)
    parser.add_argument("--peak-repeats", type=int, default=3)
    parser.add_argument("--no-ledger", action="store_true")
    parser.add_argument("--no-time", action="store_true")
    parser.add_argument("--json", default="", help="append one JSON line per scenario here")
    parser.add_argument("--label", default="")
    a = parser.parse_args()
    catalogue = scenarios()
    if a.list:
        print("\n".join(catalogue))
        return
    wanted_words = [w for w in cast(str, a.scenarios).split(",") if w]
    wanted = (
        list(catalogue) if a.all else [n for n in catalogue if any(w in n for w in wanted_words)]
    )
    if not wanted:
        raise SystemExit("no scenario matches; --list shows them")
    lines: list[str] = []
    for name in wanted:
        line = json.dumps(measure(catalogue[name], a))
        print(line, flush=True)
        lines.append(line)
    if a.json:
        with open(cast(str, a.json), "a", encoding="utf-8") as out:
            out.write("".join(line + "\n" for line in lines))


if __name__ == "__main__":
    main()
