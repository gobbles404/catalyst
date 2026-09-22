"""What one call through the seam allocates on the Python heap, at its peak.

tracemalloc sees Python objects and numpy's data buffers, which numpy registers with it.
It does not see the host's pinned buffers or anything in the CLR. Each ceiling is the
peak measured on 2026-09-11 plus slack, so a change that allocates a new full-size
temporary fails here and a change that removes one lowers the ceiling in its own PR.
"""

import ctypes
import tracemalloc
from collections.abc import Callable

import numpy as np
import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells

# Each function's prepared path, fetched once as the host does at registration.
ENTRY = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}

N = 10_000
SLACK = 1024  # bytes of small objects a call may make on top of its per-cell temporaries


def peak_bytes(fn: Callable[[], object]) -> int:
    """The peak of the Python heap during one warm call, above where it stood before."""
    fn()
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        fn()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_a_scalar_call_allocates_only_small_objects() -> None:
    assert peak_bytes(lambda: ENTRY["Add"](1.0, 2.0)) <= SLACK
    assert peak_bytes(lambda: ENTRY["Zero"]()) <= SLACK
    assert peak_bytes(lambda: ENTRY["Fail"]()) <= SLACK


# A range of numbers is accepted on the host's summary alone: no look at the kinds, so no
# temporary per cell. Measured 192 bytes at ten thousand cells on 2026-09-11, down from 77,008
# when every range paid a look and its 8-byte-per-cell scratch.
def test_a_range_of_numbers_in_makes_no_temporary() -> None:
    column = Cells.from_rows([[float(i)] for i in range(N)])
    assert peak_bytes(lambda: ENTRY["SumArray"](column)) <= SLACK


# A column of text is accepted on the summary too, and the host's tuple of text cells is
# handed over as it is. Measured 192 bytes at ten thousand cells on 2026-09-11, down from
# 160,635 when the tuple went into an object array and came back out as a second tuple.
def test_a_column_of_text_in_makes_no_temporary() -> None:
    names = Cells.from_rows([[f"name{i}"] for i in range(N)])
    assert peak_bytes(lambda: ENTRY["FirstOfNames"](names)) <= SLACK


# A rejected range still takes the look that names the bad cell: one 1-byte mask over the
# kinds, and a second one while the bad cell's text is found by counting the text cells before
# it. Measured 20,640 at ten thousand cells with the bad cell last, down from 87,239 when the
# compare against an IntEnum cast the kinds through numpy's 8-byte scratch buffer.
# A mixed range is accepted on the host's summary too, and the record holds the storage the
# range already had, so nothing is made per cell. Measured 248 bytes at ten thousand cells on
# 2026-09-12: the record, its shape, and the small objects any call makes.
def test_a_mixed_range_in_makes_no_temporary() -> None:
    cells = Cells.from_rows([[f"n{i}", 46164.0 + i, float(i), i % 2 == 0] for i in range(N // 4)])
    assert peak_bytes(lambda: ENTRY["CountMixed"](cells)) <= SLACK


# A scalar becomes a one-cell range, which is the only mixed input that allocates storage of
# its own: two one-element arrays. Measured 473 bytes on 2026-09-12.
def test_a_scalar_promoted_to_a_mixed_range_stays_small() -> None:
    assert peak_bytes(lambda: ENTRY["CountMixed"](5.0)) <= SLACK


# A table pays for what it converts and gathers, and nothing per row beyond that. Measured
# 135,266 bytes at ten thousand cells, 2,500 rows of four columns, on 2026-09-13: the date
# column's masks and its three arrays on the way to days, the text mask and the counts that place
# each text, the texts as an array and the gathered tuple, the boolean column, and a 1-byte mask
# per column. About 54 bytes per row, and one mask per column beyond that.
def test_a_table_in_pays_for_its_conversions_and_nothing_per_row_beyond() -> None:
    headers = Cells.from_rows([["date", "product", "quantity", "cleared"]])
    body = Cells.from_rows([[46276.0 + i, f"p{i}", float(i), i % 2 == 0] for i in range(N // 4)])
    assert peak_bytes(lambda: ENTRY["SumQuantity"](headers, body)) <= 14 * N + SLACK


# Naming the bad cell is the rejection path's work. A blank is one mask over the kinds, measured
# 13,008 at ten thousand cells. An empty text costs more, because its place among the texts has
# to be turned into its place among the cells: measured 103,372, about 10 bytes per cell.
def test_a_rejected_mixed_range_pays_to_locate_the_cell_it_names() -> None:
    rows: list[list[object]] = [[float(i)] for i in range(N)]
    rows[N // 2][0] = None
    blank = Cells.from_rows(rows)
    assert peak_bytes(lambda: ENTRY["CountMixed"](blank)) <= 2 * N + SLACK
    texts: list[list[object]] = [[f"n{i}"] for i in range(N)]
    texts[N // 2][0] = ""
    empty = Cells.from_rows(texts)
    assert peak_bytes(lambda: ENTRY["CountMixed"](empty)) <= 11 * N + SLACK


def test_a_rejected_range_pays_one_look_and_its_two_masks() -> None:
    rows: list[list[object]] = [[float(i)] for i in range(N)]
    rows[-1][0] = "x"
    column = Cells.from_rows(rows)
    assert peak_bytes(lambda: ENTRY["SumArray"](column)) <= 2 * N + SLACK


# The way out still looks once, for finite numbers: one byte per cell. Measured 10,385.
def test_a_column_out_adds_only_its_finite_mask() -> None:
    column = Cells.from_rows([[float(i)] for i in range(N)])
    assert peak_bytes(lambda: ENTRY["EchoColumn"](column)) <= N + SLACK


def test_an_array_out_peaks_at_the_array_and_its_finite_mask() -> None:
    assert peak_bytes(lambda: ENTRY["Grid"](N // 2, 2)) <= 9 * N + SLACK


# The mixed road out pays its three looks, a 1-byte mask each and the compares behind them, and
# over text the joined string and its encoding in Excel's units. Measured 50,536 bytes over ten
# thousand numbers and 72,213 over the mixed column, a text in every fourth cell, on 2026-09-15.
def test_a_mixed_array_out_peaks_at_its_masks_and_its_joined_text() -> None:
    numbers = Cells.from_rows([[float(i)] for i in range(N)])
    assert peak_bytes(lambda: ENTRY["EchoMixed"](numbers)) <= 6 * N + SLACK
    mixed = Cells.from_rows([[f"n{i}", 46164.0 + i, float(i), i % 2 == 0] for i in range(N // 4)])
    assert peak_bytes(lambda: ENTRY["EchoMixed"](mixed)) <= 8 * N + SLACK


# --- handles ------------------------------------------------------------------
# A creator keeps what it makes: the record, its entry in the store and its text; a reader
# keeps nothing, and its numpy scalars are the small objects. Each is the least of three warm
# calls, so that a resize of the store's dictionary, which lands on one call in many, never
# lands on the pin.

CURVE_HEADERS = Cells.from_rows([["date", "discount_factor"]])


def curve_body(rows: int) -> Cells:
    return Cells.from_rows([[46276.0 + i, 1.0 - i * 1e-5] for i in range(rows)])


def least_peak(fn: Callable[[], object]) -> int:
    return min(peak_bytes(fn) for _ in range(3))


# Measured 1,176 bytes for the valuation date on 2026-09-14, and 1,671 for reading it back as a
# three-row table on 2026-09-15: the record and its entry, then the kinds, the slots and the
# masks of six cells.
def test_a_creator_of_a_small_object_and_its_reader_stay_small() -> None:
    assert least_peak(lambda: ENTRY["_CreateValuationDate"](46276.0, 0.5)) <= 2 * SLACK
    handle = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](handle)) <= 2 * SLACK


# Reading a ten-year curve back builds its table, the kinds and the slots of 3,633 rows by two,
# the serials on the way, and the mixed road's masks: measured 128,381 bytes on 2026-09-15,
# about 18 bytes per cell out.
def test_reading_a_curve_back_peaks_at_its_table_and_the_roads_masks() -> None:
    handle = ENTRY["_CreateDiscountCurve"](CURVE_HEADERS, curve_body(3_631))
    cells = 3_633 * 2
    assert least_peak(lambda: ENTRY["util_ReadHandle"](handle)) <= 18 * cells + SLACK


def anchor_body(anchors: int, days: int) -> Cells:
    """Anchors spread evenly over that many days from 11 September 2026, as the sheet sends them."""
    step = days // (anchors - 1)
    return Cells.from_rows([[46276.0 + i * step, 1.0 - i * step * 1e-5] for i in range(anchors)])


# A ten-year curve from a daily table keeps its two arrays, 16 bytes per day, and on the way pays
# the table path's conversion of the date column, the builder's looks, and the filling of every
# day it was given, the anchors' offsets, the day grid, the anchors each day runs to and the two
# results: measured 216,443 bytes at 3,631 days on 2026-09-17, about 60 bytes per day, up from
# 129,027 when a daily table was copied rather than filled.
def test_a_discount_curve_from_a_daily_table_pays_its_looks_and_its_filling_once() -> None:
    days = 3_631
    body = curve_body(days)
    assert (
        least_peak(lambda: ENTRY["_CreateDiscountCurve"](CURVE_HEADERS, body)) <= 60 * days + SLACK
    )


# A dozen anchors over ten years pay for the days they fill, not for the anchors: the day grid,
# the offsets numpy interpolates over, the anchor each day runs to and the two arrays the curve
# keeps, measured 89,602 bytes at 3,631 days on 2026-09-17, about 25 bytes per day.
def test_a_discount_curve_from_a_dozen_anchors_pays_for_the_days_it_fills() -> None:
    days = 3_631
    body = anchor_body(12, days - 1)
    assert (
        least_peak(lambda: ENTRY["_CreateDiscountCurve"](CURVE_HEADERS, body)) <= 25 * days + SLACK
    )


def schedule_columns(contracts: int) -> tuple[Cells, Cells, Cells, Cells]:
    """Codes and three date columns for that many monthly contracts, as the sheet sends them:
    the futures, the options and the publication dates."""
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    futures = Cells.from_rows([[46161.0 + 30 * i] for i in range(contracts)])
    options = Cells.from_rows([[46156.0 + 30 * i] for i in range(contracts)])
    publications = Cells.from_rows([[46162.0 + 30 * i] for i in range(contracts)])
    return codes, futures, options, publications


# A schedule keeps a copy of each date column, 8 bytes per contract each, and on the way pays
# each column's conversion to days and its look: measured 4,928 bytes with options and 3,280
# without at 120 contracts on 2026-09-14, about 32 and 17 bytes per contract on top of a
# creator's small objects, which twice the slack covers; 39,516 and 21,640 at 1,200 contracts.
# With the publication dates as well, 7,312 at 120 contracts on 2026-09-17 and 59,180 at 1,200,
# a third column's copy and conversions; with the publication dates and the options left out,
# 4,928 and 39,516, the three-column cost.
def test_an_expiry_schedule_keeps_a_copy_of_each_date_column() -> None:
    contracts = 120
    codes, futures, options, publications = schedule_columns(contracts)
    every = least_peak(
        lambda: ENTRY["_CreateExpirySchedule"](codes, futures, options, publications)
    )
    assert every <= 48 * contracts + 2 * SLACK
    with_options = least_peak(
        lambda: ENTRY["_CreateExpirySchedule"](codes, futures, options, MISSING)
    )
    assert with_options <= 32 * contracts + 2 * SLACK
    published = least_peak(
        lambda: ENTRY["_CreateExpirySchedule"](codes, futures, MISSING, publications)
    )
    assert published <= 32 * contracts + 2 * SLACK
    without = least_peak(lambda: ENTRY["_CreateExpirySchedule"](codes, futures, MISSING, MISSING))
    assert without <= 17 * contracts + 2 * SLACK


def holiday_column(days: int) -> Cells:
    """That many holidays as the sheet sends them, one serial per row, a week apart."""
    return Cells.from_rows([[46023.0 + 7 * i] for i in range(days)])


# A calendar keeps a copy of its column, 8 bytes per holiday, and on the way pays the column's
# conversion to days and its look, as a schedule without options does: measured 2,908 bytes at
# 100 holidays on 2026-09-16, about 17 bytes per holiday on top of a creator's small objects,
# which twice the slack covers; 18,208 at 1,000 holidays and 171,208 at 10,000.
def test_a_holiday_calendar_keeps_a_copy_of_its_column() -> None:
    days = 100
    holidays = holiday_column(days)
    assert least_peak(lambda: ENTRY["_CreateHolidayCalendar"](holidays)) <= 17 * days + 2 * SLACK


def publication_columns(contracts: int) -> tuple[Cells, Cells]:
    """Codes and the day each contract's reference price is published, for that many monthly
    contracts, as the sheet sends them: the codes and the publication dates of schedule_columns."""
    codes, _, _, publications = schedule_columns(contracts)
    return codes, publications


# A publication schedule keeps a copy of its date column, 8 bytes per contract, and the seam's
# tuple of codes as it is, and on the way pays the column's conversion to days and its look, as a
# schedule without options does: measured 3,280 bytes at 120 contracts on 2026-09-22,
# about 17 bytes per contract on top of a creator's small objects, which twice the slack covers;
# 21,640 at 1,200 contracts, the two-column expiry schedule's figures to the byte.
def test_a_publication_schedule_keeps_a_copy_of_its_date_column() -> None:
    contracts = 120
    codes, publications = publication_columns(contracts)
    assert (
        least_peak(lambda: ENTRY["_CreatePublicationSchedule"](codes, publications))
        <= 17 * contracts + 2 * SLACK
    )


# Five texts kept as they arrived, the record and its entry: measured 281 bytes on 2026-09-16,
# and 1,162 for reading them back as a three-row table of fifteen text cells.
def test_a_creator_of_index_conventions_and_its_reader_stay_small() -> None:
    codes = ("USD", "BBL", "USD", "volume", "BBL")
    assert least_peak(lambda: ENTRY["_CreateIndexConventions"](*codes)) <= 2 * SLACK
    handle = ENTRY["_CreateIndexConventions"](*codes)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](handle)) <= 2 * SLACK


SPECIFICATION_HEADERS = Cells.from_rows(
    [["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)


def specification_body(contracts: int) -> Cells:
    """That many contracts as the sheet sends them: a name, a whole lot size and two fees."""
    return Cells.from_rows([[f"contract {i}", 1000.0 + i, 3.0, 2.0] for i in range(contracts)])


# Contract specifications keep a copy of each numeric column, 24 bytes per contract, and on the
# way pay the table path, the names gathered and the builder's look at the lot sizes: measured
# 12,163 bytes at 120 contracts on 2026-09-17, about 76 bytes per contract beyond a creator's
# small objects; 3,037 at two contracts and 3,327 at a dozen.
def test_contract_specifications_keep_a_copy_of_each_numeric_column() -> None:
    contracts = 120
    body = specification_body(contracts)
    assert (
        least_peak(lambda: ENTRY["_CreateContractSpecifications"](SPECIFICATION_HEADERS, body))
        <= 100 * contracts + 2 * SLACK
    )


def test_owning_a_range_peaks_at_the_two_copies() -> None:
    kinds = (ctypes.c_uint8 * N)(*([0] * N))
    numbers = (ctypes.c_double * N)(*[float(i) for i in range(N)])
    pointers = ctypes.addressof(kinds), ctypes.addressof(numbers)
    assert peak_bytes(lambda: bridge.cells_from_buffers(*pointers, N, 1, "", 1)) <= 9 * N + SLACK


FIXINGS_HEADERS = Cells.from_rows([["date", "settle"]])


def fixings_body(rows: int, holidays: int) -> Cells:
    """That many daily fixings as the sheet sends them, a serial and a settle per row, one per
    business day from Friday 1 May 2026 under a calendar of that many Thursdays a week apart,
    the calendar holiday_column makes."""
    epoch = np.datetime64("1899-12-30")
    closed = epoch + (46023 + 7 * np.arange(holidays)).astype("timedelta64[D]")
    days = np.busday_offset(np.datetime64("2026-05-01"), np.arange(rows), holidays=closed)
    serials = (days - epoch).astype(np.int64)
    return Cells.from_rows([[float(serials[i]), 100.0 + i % 7] for i in range(rows)])


# Daily fixings keep a copy of each column, 16 bytes per row, and on the way pay the table path,
# the date column's masks and its arrays on the way to days, and the builder's three looks, the
# order, the days closed and the gaps, the last over the business day after each date, a
# full-size temporary: measured 11,482 bytes at 260 rows on 2026-09-17, about 44 bytes per row,
# up from 7,563 before the calendar was checked; 93,326 at 2,600 and 912,278 at 26,000, 35
# bytes per row.
def test_daily_fixings_keep_a_copy_of_each_column() -> None:
    rows = 260
    calendar = ENTRY["_CreateHolidayCalendar"](holiday_column(100))
    body = fixings_body(rows, 100)
    assert (
        least_peak(lambda: ENTRY["_CreateDailyFixings"](FIXINGS_HEADERS, body, calendar))
        <= 45 * rows + SLACK
    )


def calendar_sources(contracts: int) -> tuple[object, str, object, object]:
    """What a calendar takes: the valuation date's handle, the mode, daily, a schedule of that
    many monthly contracts a month apart, and a calendar of a hundred holidays a week apart."""
    codes, futures, _, _ = schedule_columns(contracts)
    return (
        ENTRY["_CreateValuationDate"](46276.0, 0.5),
        "daily",
        ENTRY["_CreateExpirySchedule"](codes, futures, MISSING, MISSING),
        ENTRY["_CreateHolidayCalendar"](holiday_column(100)),
    )


# A calendar keeps four columns, 18 bytes per day, the days and the prompt rows 8 each and the
# two flags a byte each, and on the way pays the arange, the searchsorted and the flags'
# temporaries: measured 8,620 bytes at 360 days on 2026-09-18, about 24 bytes per day on top of
# a creator's small objects, which twice the slack covers; 66,741 at 3,630 days and 661,841 at
# 36,630, 18 bytes per day. The mode, since #87, adds one reference to the record and nothing
# per day, daily or monthly alike. Reading it back pays the reader's rectangle, four cells per day,
# the codes gathered as text and the days to serials: measured 26,308 at 360 days, about 18
# bytes per cell; 251,938 at 3,630 days.
def test_a_calendar_keeps_four_columns_and_its_reader_pays_per_cell() -> None:
    days = 360
    valuation, mode, schedule, holidays = calendar_sources(13)
    assert (
        least_peak(lambda: ENTRY["_CreateCalendar"](valuation, mode, schedule, holidays))
        <= 25 * days + 2 * SLACK
    )
    made = ENTRY["_CreateCalendar"](valuation, mode, schedule, holidays)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](made)) <= 20 * 4 * days + 2 * SLACK
    codes, futures, _, publications = schedule_columns(13)
    published = ENTRY["_CreateExpirySchedule"](codes, futures, MISSING, publications)
    assert (
        least_peak(lambda: ENTRY["_CreateCalendar"](valuation, "monthly", published, holidays))
        <= 25 * days + 2 * SLACK
    )


def history_sources(contracts: int) -> tuple[object, object]:
    """The two handles a history takes: the calendar calendar_sources makes, valued on 11
    September 2026, and fixings on every business day from Friday 1 May 2026 to the day
    before, under the same hundred Thursdays, so every past business day has one."""
    valuation, mode, schedule, holidays = calendar_sources(contracts)
    made = ENTRY["_CreateCalendar"](valuation, mode, schedule, holidays)
    closed = np.datetime64("1899-12-30") + (46023 + 7 * np.arange(100)).astype("timedelta64[D]")
    rows = int(np.busday_count("2026-05-01", "2026-09-11", holidays=closed))
    fixings = ENTRY["_CreateDailyFixings"](FIXINGS_HEADERS, fixings_body(rows, 100), holidays)
    return made, fixings


# A daily history keeps two columns, 16 bytes per past business day, the row and the price, and
# nothing per day of the calendar, which it keeps as it is; on the way it pays the builder's
# looks, a byte or so per fixing and per day for the days covered and the flags combined:
# measured 3,681 bytes at 360 days with 76 fixings on 2026-09-19 and again on 2026-09-20 with
# the daily rules in a function of their own, 16,641 at 3,600 days and 148,641 at 36,600, 4
# bytes per day. Reading it back pays the calendar's table and then the fifth column, the words
# made once, the wider kinds and slots, the codes paired with the words, and the mixed road's
# masks over five columns: measured 53,627 at 360 days on 2026-09-19 through the helper the
# market's reader shares, from 51,267 before it, about 30 bytes per cell; 629,741 at 3,600 days
# and 6,528,344 at 36,600, 35 bytes per cell, where the road splits the joined text per text.
def test_a_market_history_keeps_two_short_columns_and_its_reader_pays_per_cell() -> None:
    days = 360
    made, fixings = history_sources(13)
    assert least_peak(lambda: ENTRY["_CreateMarketHistory"](made, fixings)) <= 6 * days + 2 * SLACK
    history = ENTRY["_CreateMarketHistory"](made, fixings)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](history)) <= 30 * 5 * days + 2 * SLACK


def monthly_sources(contracts: int) -> tuple[object, object]:
    """The two handles a monthly history takes: a monthly calendar over the schedule of
    schedule_columns with its publication dates, the day after each expiry, under the same
    hundred Thursdays, valued on 11 September 2026, and fixings for the contracts expired by
    then, the anchor's left out, so every expired contract has one and no other does."""
    codes, futures, _, publications = schedule_columns(contracts)
    schedule = ENTRY["_CreateExpirySchedule"](codes, futures, MISSING, publications)
    valuation = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    holidays = ENTRY["_CreateHolidayCalendar"](holiday_column(100))
    made = ENTRY["_CreateCalendar"](valuation, "monthly", schedule, holidays)
    expired = int(np.searchsorted(46161.0 + 30 * np.arange(contracts), 46276.0))
    dates = Cells.from_rows([[46162.0 + 30 * i] for i in range(1, expired)])
    prices = Cells.from_rows([[2.0 + i / 100] for i in range(1, expired)])
    return made, ENTRY["_CreateMonthlyFixings"](dates, prices, schedule)


# A monthly history keeps the same two columns, 16 bytes per day of an expired contract, every
# day of it, weekends and holidays included, and nothing per day of the rest of the calendar;
# on the way it pays the rows listed, the prompts of those rows and the prices gathered through
# them, 8 bytes each per such day, and the searches over the schedule's publication dates, a
# few bytes per contract: measured 3,599 bytes at 360 days with 90 such days on
# 2026-09-20, and 3,707 at 3,600 days over 121 contracts with the same 90, the
# difference the contracts' own. Reading it back pays what the daily history's reading pays
# less the words array, one word serving every day without a fixing: measured 50,227 at 360
# days, about 28 bytes per cell, and 631,465 at 3,600.
def test_a_monthly_history_keeps_two_columns_of_its_expired_days_and_reads_back_per_cell() -> None:
    days, priced = 360, 90
    made, fixings = monthly_sources(13)
    assert (
        least_peak(lambda: ENTRY["_CreateMarketHistory"](made, fixings)) <= 32 * priced + 2 * SLACK
    )
    history = ENTRY["_CreateMarketHistory"](made, fixings)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](history)) <= 30 * 5 * days + 2 * SLACK


def published_columns(count: int) -> tuple[Cells, Cells]:
    """That many monthly publications as the sheet sends them, the publication dates of the
    schedule schedule_columns makes, a serial per row, and a price beside each."""
    _, _, _, publications = schedule_columns(count)
    return publications, Cells.from_rows([[2.0 + i / 100] for i in range(count)])


# Monthly fixings keep a copy of each column, 16 bytes per fixing, and on the way pay the date
# column's masks and arrays to days, a sorted copy of the schedule's publication dates, 8 bytes
# per contract of the schedule, and the places, the next publications and the looks over the
# column: measured 7,631 bytes at 120 fixings against a schedule of 120 contracts on 2026-09-17,
# about 64 bytes per fixing, up from 4,472 when the months were kept as months and nothing was
# checked; 62,622 at 1,200 and 613,422 at 12,000, 51 bytes per fixing.
def test_monthly_fixings_keep_a_copy_of_each_column() -> None:
    count = 120
    codes, futures, _, publications = schedule_columns(count)
    schedule = ENTRY["_CreateExpirySchedule"](codes, futures, MISSING, publications)
    dates, prices = published_columns(count)
    assert (
        least_peak(lambda: ENTRY["_CreateMonthlyFixings"](dates, prices, schedule))
        <= 60 * count + 2 * SLACK
    )


def price_column(prices: int) -> Cells:
    """That many prices as the sheet sends them, one per row, around 74."""
    return Cells.from_rows([[74.25 + i % 7 - 3.0] for i in range(prices)])


def price_vector_peaks(prices: int) -> tuple[int, int]:
    """The least peak of creating a vector of that many prices, and of reading it back."""
    column = price_column(prices)
    made = ENTRY["_CreatePriceVector"](column)
    return (
        least_peak(lambda: ENTRY["_CreatePriceVector"](column)),
        least_peak(lambda: ENTRY["util_ReadHandle"](made)),
    )


# A price vector keeps one copy of its column, 8 bytes per price, and nothing else per price:
# the column is accepted on the host's summary, so no look and no temporary. Measured 1,273
# bytes at 120 prices on 2026-09-19, the copy plus a creator's small objects, which twice the
# slack covers, and 80,314 at 10,000, 8 bytes per price; 392 for a single cell. Reading it back
# pays the table's kinds and slots and the mixed road's masks: measured 2,492 at 120 prices,
# about 20 bytes per cell, and 140,812 at 10,000, 14.
def test_a_price_vector_keeps_one_copy_of_its_column_and_nothing_per_price_beyond() -> None:
    for prices in (120, 10_000):
        created, read = price_vector_peaks(prices)
        assert created <= 8 * prices + 2 * SLACK
        assert read <= 21 * (prices + 2) + SLACK
    assert least_peak(lambda: ENTRY["_CreatePriceVector"](74.25)) <= SLACK


def market_sources(contracts: int, days_apart: int) -> tuple[object, object]:
    """The two handles a market takes: the history of a calendar of that many contracts that
    many days apart from 19 May 2026, valued on 11 September 2026 with a fixing on every
    business day before it under a hundred Thursdays, and a vector with one quote per contract
    from the valuation day's prompt through the last."""
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    futures = Cells.from_rows([[46161.0 + days_apart * i] for i in range(contracts)])
    valuation = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    schedule = ENTRY["_CreateExpirySchedule"](codes, futures, MISSING, MISSING)
    holidays = ENTRY["_CreateHolidayCalendar"](holiday_column(100))
    made = ENTRY["_CreateCalendar"](valuation, "daily", schedule, holidays)
    closed = np.datetime64("1899-12-30") + (46023 + 7 * np.arange(100)).astype("timedelta64[D]")
    rows = int(np.busday_count("2026-05-01", "2026-09-11", holidays=closed))
    fixings = ENTRY["_CreateDailyFixings"](FIXINGS_HEADERS, fixings_body(rows, 100), holidays)
    history = ENTRY["_CreateMarketHistory"](made, fixings)
    first = int(np.searchsorted(46161.0 + days_apart * np.arange(contracts), 46276.0))
    quotes = Cells.from_rows([[70.0 + i % 5] for i in range(contracts - first)])
    return history, ENTRY["_CreatePriceVector"](quotes)


# A market keeps its record, two references and one number, and makes no array: measured 984
# bytes on 2026-09-19 at a year of days with nine quotes, ten years with one and a year with
# 246, the same to the byte, which twice the slack covers.
@pytest.mark.parametrize(
    ("contracts", "days_apart"),
    [(13, 30), (2, 3600), (361, 1)],
    ids=["a year of days, nine quotes", "ten years of days, one quote", "a year, 246 quotes"],
)
def test_a_market_keeps_one_small_record_whatever_the_sizes(
    contracts: int, days_apart: int
) -> None:
    history, quotes = market_sources(contracts, days_apart)
    assert least_peak(lambda: ENTRY["_CreateMarket"](history, quotes)) <= 2 * SLACK


# Reading a market back pays the calendar's table and then the fifth column through the
# history's helper, with the live rows, their prompts and their quotes on top: measured 50,931
# bytes at 360 days on 2026-09-19, about 28 bytes per cell, and 501,307 at 3,600.
def test_reading_a_market_back_pays_per_cell() -> None:
    days = 360
    made = ENTRY["_CreateMarket"](*market_sources(13, 30))
    assert least_peak(lambda: ENTRY["util_ReadHandle"](made)) <= 30 * 5 * days + 2 * SLACK


# A monthly market keeps the same record and makes no array, measured 984 bytes on 2026-09-20
# at a year of days over thirteen contracts, the daily market's figure to the byte. Reading it
# back pays the calendar's table and the fifth column with the live rows, every day of a
# contract not yet expired, their prompts and their quotes: measured 50,547 bytes at 360 days,
# about 28 bytes per cell, and 500,907 at 3,600.
def test_a_monthly_market_keeps_one_small_record_and_reads_back_per_cell() -> None:
    days = 360
    history = ENTRY["_CreateMarketHistory"](*monthly_sources(13))
    quotes = ENTRY["_CreatePriceVector"](Cells.from_rows([[3.0 + i % 5 / 10] for i in range(9)]))
    assert least_peak(lambda: ENTRY["_CreateMarket"](history, quotes)) <= 2 * SLACK
    made = ENTRY["_CreateMarket"](history, quotes)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](made)) <= 30 * 5 * days + 2 * SLACK
