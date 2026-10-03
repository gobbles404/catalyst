"""What one call through the seam allocates on the Python heap, at its peak, and what a
creator's publication still holds once the call has returned.

tracemalloc sees Python objects and numpy's data buffers, which numpy registers with it, on
every thread of this process and not only in the call measured; it does not see the host's
pinned buffers or anything in the CLR. Each ceiling is the peak measured plus slack, and
since #NN every pin is the least of three warm measurements, each with its own untraced
warmup and its own trace, so that an allocation the call did not make, another thread's or a
resize of the store's dictionary, which lands on one call in many, never lands on the pin.
The least is what a warm call does every time, not a cold call and not a worst case: a change
that allocates a new full-size temporary on every call stands in all three samples and fails
here, and a change that removes one lowers the ceiling in its own PR.
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


def least_peak(fn: Callable[[], object]) -> int:
    """The least of three peaks of one call, each with its own untraced warmup and its own trace.

    One sample can be raised by what the call did not do: a resize of the store's dictionary,
    which lands on one call in many, or an allocation on another thread of the process, an xdist
    worker's receiver among them. What the call does every time stands in all three samples and
    so in the least; so does a disturbance that lands on all three. A call that fails is not
    retried: its error comes out of the first sample, with tracing stopped.
    """
    return min(peak_bytes(fn) for _ in range(3))


# The measure itself: three samples, each a warmup untraced and then one traced call, six calls
# in all, and the pin is the least of the three. A 4-kilobyte temporary made on the traced call
# of one sample, whichever one, leaves the least where the other two put it, under the slack;
# with one sample, or the greatest or the mean of three, it would stand over it.
@pytest.mark.parametrize("noisy_sample", [0, 1, 2], ids=["first", "second", "third"])
def test_a_spike_in_one_sample_does_not_set_the_least(noisy_sample: int) -> None:
    traced: list[bool] = []

    def work() -> object:
        traced.append(tracemalloc.is_tracing())
        noisy = len(traced) == 2 * noisy_sample + 2  # the traced call of the noisy sample
        return bytearray(4 * SLACK) if noisy else None

    assert least_peak(work) < SLACK
    assert traced == [False, True] * 3


# A full-size temporary made on every call, 8 bytes per cell, stands in every sample and so in
# the least, freed before the call returns or not: the scalar call's pin above, which the slack
# holds, would fail with it.
def test_a_full_size_temporary_on_every_call_stands_in_the_least() -> None:
    def call_with_scratch() -> object:
        scratch = np.empty(N)
        result = ENTRY["Add"](1.0, 2.0)
        del scratch
        return result

    peak = least_peak(call_with_scratch)
    assert peak >= 8 * N
    assert peak > SLACK
    assert not tracemalloc.is_tracing()


# A call that fails, in the warmup or under the trace, fails the measurement at once: the error
# as it was raised, no second sample taken, and tracing stopped behind it.
@pytest.mark.parametrize("failing_call", [1, 2], ids=["the warmup", "the traced call"])
def test_a_failing_call_is_not_retried_and_tracing_stops(failing_call: int) -> None:
    traced: list[bool] = []

    def work() -> None:
        traced.append(tracemalloc.is_tracing())
        if len(traced) == failing_call:
            raise ValueError("measured failure")

    with pytest.raises(ValueError, match=r"^measured failure$"):
        least_peak(work)
    assert traced == [False, True][:failing_call]
    assert not tracemalloc.is_tracing()


def test_a_scalar_call_allocates_only_small_objects() -> None:
    assert least_peak(lambda: ENTRY["Add"](1.0, 2.0)) <= SLACK
    assert least_peak(lambda: ENTRY["Zero"]()) <= SLACK
    assert least_peak(lambda: ENTRY["Fail"]()) <= SLACK


# A range of numbers is accepted on the host's summary alone: no look at the kinds, so no
# temporary per cell. Measured 192 bytes at ten thousand cells on 2026-09-11, down from 77,008
# when every range paid a look and its 8-byte-per-cell scratch.
def test_a_range_of_numbers_in_makes_no_temporary() -> None:
    column = Cells.from_rows([[float(i)] for i in range(N)])
    assert least_peak(lambda: ENTRY["SumArray"](column)) <= SLACK


# A column of text is accepted on the summary too, and the host's tuple of text cells is
# handed over as it is. Measured 192 bytes at ten thousand cells on 2026-09-11, down from
# 160,635 when the tuple went into an object array and came back out as a second tuple.
def test_a_column_of_text_in_makes_no_temporary() -> None:
    names = Cells.from_rows([[f"name{i}"] for i in range(N)])
    assert least_peak(lambda: ENTRY["FirstOfNames"](names)) <= SLACK


# A rejected range still takes the look that names the bad cell: one 1-byte mask over the
# kinds, and a second one while the bad cell's text is found by counting the text cells before
# it. Measured 20,640 at ten thousand cells with the bad cell last, down from 87,239 when the
# compare against an IntEnum cast the kinds through numpy's 8-byte scratch buffer.
# A mixed range is accepted on the host's summary too, and the record holds the storage the
# range already had, so nothing is made per cell. Measured 248 bytes at ten thousand cells on
# 2026-09-12: the record, its shape, and the small objects any call makes.
def test_a_mixed_range_in_makes_no_temporary() -> None:
    cells = Cells.from_rows([[f"n{i}", 46164.0 + i, float(i), i % 2 == 0] for i in range(N // 4)])
    assert least_peak(lambda: ENTRY["CountMixed"](cells)) <= SLACK


# A scalar becomes a one-cell range, which is the only mixed input that allocates storage of
# its own: two one-element arrays. Measured 473 bytes on 2026-09-12.
def test_a_scalar_promoted_to_a_mixed_range_stays_small() -> None:
    assert least_peak(lambda: ENTRY["CountMixed"](5.0)) <= SLACK


# A table pays for what it converts, and nothing per row beyond that. Measured 43,940 bytes at
# ten thousand cells, 2,500 rows of four columns, on 2026-10-01: the date column's masks and its
# three arrays on the way to days, the boolean column, and a 1-byte mask per column, about 17.6
# bytes per row and 4.4 per cell. The column of text adds nothing per row: it is a slice of the
# host's tuple. It was 135,186 bytes, 13.5 per cell, while the texts were placed by a mask, a
# count and a cumulative sum and gathered from an array of them: what the ceiling of 14 per cell
# covered, and the ceiling of 5 refuses.
def test_a_table_in_pays_for_its_conversions_and_nothing_per_row_beyond() -> None:
    headers = Cells.from_rows([["date", "product", "quantity", "cleared"]])
    body = Cells.from_rows([[46276.0 + i, f"p{i}", float(i), i % 2 == 0] for i in range(N // 4)])
    assert least_peak(lambda: ENTRY["SumQuantity"](headers, body)) <= 5 * N + SLACK


# Naming the bad cell is the rejection path's work. A blank is one mask over the kinds, measured
# 13,008 at ten thousand cells. An empty text costs more, because its place among the texts has
# to be turned into its place among the cells: measured 103,372, about 10 bytes per cell.
def test_a_rejected_mixed_range_pays_to_locate_the_cell_it_names() -> None:
    rows: list[list[object]] = [[float(i)] for i in range(N)]
    rows[N // 2][0] = None
    blank = Cells.from_rows(rows)
    assert least_peak(lambda: ENTRY["CountMixed"](blank)) <= 2 * N + SLACK
    texts: list[list[object]] = [[f"n{i}"] for i in range(N)]
    texts[N // 2][0] = ""
    empty = Cells.from_rows(texts)
    assert least_peak(lambda: ENTRY["CountMixed"](empty)) <= 11 * N + SLACK


def test_a_rejected_range_pays_one_look_and_its_two_masks() -> None:
    rows: list[list[object]] = [[float(i)] for i in range(N)]
    rows[-1][0] = "x"
    column = Cells.from_rows(rows)
    assert least_peak(lambda: ENTRY["SumArray"](column)) <= 2 * N + SLACK


# The way out still looks once, for finite numbers: one byte per cell. Measured 10,385.
def test_a_column_out_adds_only_its_finite_mask() -> None:
    column = Cells.from_rows([[float(i)] for i in range(N)])
    assert least_peak(lambda: ENTRY["EchoColumn"](column)) <= N + SLACK


def test_an_array_out_peaks_at_the_array_and_its_finite_mask() -> None:
    assert least_peak(lambda: ENTRY["Grid"](N // 2, 2)) <= 9 * N + SLACK


# The mixed road out pays its three looks, a 1-byte mask each and the compares behind them, and
# over text the joined string and its encoding in Excel's units. Measured 50,536 bytes over ten
# thousand numbers and 72,213 over the mixed column, a text in every fourth cell, on 2026-09-15.
def test_a_mixed_array_out_peaks_at_its_masks_and_its_joined_text() -> None:
    numbers = Cells.from_rows([[float(i)] for i in range(N)])
    assert least_peak(lambda: ENTRY["EchoMixed"](numbers)) <= 6 * N + SLACK
    mixed = Cells.from_rows([[f"n{i}", 46164.0 + i, float(i), i % 2 == 0] for i in range(N // 4)])
    assert least_peak(lambda: ENTRY["EchoMixed"](mixed)) <= 8 * N + SLACK


# --- handles ------------------------------------------------------------------
# A creator keeps what it makes: the record, its entry in the store and its text; a reader
# keeps nothing, and its numpy scalars are the small objects.

CURVE_HEADERS = Cells.from_rows([["date", "discount_factor"]])


def curve_body(rows: int) -> Cells:
    return Cells.from_rows([[46276.0 + i, 1.0 - i * 1e-5] for i in range(rows)])


# Measured 272 bytes for the valuation date on 2026-10-01, the record and its entry. It took
# 1,144 while the scalar date was a span of days built and then added to the epoch, a kilobyte
# of numpy's scalar arithmetic, which a ceiling of twice the slack covered and the slack alone
# refuses. Reading it back as a three-row table is 1,671, measured on 2026-09-15 and unmoved:
# the kinds, the slots and the masks of six cells.
def test_a_creator_of_a_small_object_and_its_reader_stay_small() -> None:
    assert least_peak(lambda: ENTRY["_CreateValuationDate"](46276.0, 0.5)) <= SLACK
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
    the futures, the options and a third column a month apart, dates for the schedules of the
    other markets."""
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    futures = Cells.from_rows([[46161.0 + 30 * i] for i in range(contracts)])
    options = Cells.from_rows([[46156.0 + 30 * i] for i in range(contracts)])
    publications = Cells.from_rows([[46162.0 + 30 * i] for i in range(contracts)])
    return codes, futures, options, publications


# A schedule keeps a copy of each date column, 8 bytes per contract each, and on the way pays
# each column's conversion to days and its look: measured 4,928 bytes with options and 3,280
# without at 120 contracts on 2026-09-14, about 32 and 17 bytes per contract on top of a
# creator's small objects, which twice the slack covers; 39,516 and 21,640 at 1,200 contracts.
def test_a_futures_schedule_keeps_a_copy_of_each_date_column() -> None:
    contracts = 120
    codes, futures, options, _ = schedule_columns(contracts)
    with_options = least_peak(lambda: ENTRY["_CreateFuturesSchedule"](codes, futures, options))
    assert with_options <= 32 * contracts + 2 * SLACK
    without = least_peak(lambda: ENTRY["_CreateFuturesSchedule"](codes, futures, MISSING))
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


def iferc_columns(contracts: int) -> tuple[Cells, Cells, Cells]:
    """Codes, the day each month's future stops trading and the day its index is published, for
    that many contract months, as the sheet sends them: the codes, the futures and the
    third date column of schedule_columns."""
    codes, last_trading, _, publications = schedule_columns(contracts)
    return codes, last_trading, publications


# An IFERC schedule keeps a copy of each of its two date columns, 8 bytes per contract month
# each, and on the way pays each column's conversion to days and its look, as an expiry
# schedule with options does: measured 4,928 bytes at 120 contract months on 2026-09-24, about
# 32 bytes per month on top of a creator's small objects, which twice the slack covers; 39,516
# at 1,200, the futures schedule with options' figures to the byte.
def test_an_iferc_schedule_keeps_a_copy_of_each_date_column() -> None:
    contracts = 120
    codes, last_trading, publications = iferc_columns(contracts)
    assert (
        least_peak(lambda: ENTRY["_CreateIfercSchedule"](codes, last_trading, publications))
        <= 32 * contracts + 2 * SLACK
    )


def gas_daily_columns(contracts: int) -> tuple[Cells, Cells, Cells]:
    """Codes and the first and last day of gas of that many contract months, as the sheet sends
    them: the codes, the options and the third date column of schedule_columns, any dates
    serving a peak."""
    codes, _, first, last = schedule_columns(contracts)
    return codes, first, last


# A Gas Daily schedule keeps a copy of each of its two date columns, as the IFERC schedule does:
# measured 4,928 bytes at 120 contract months on 2026-09-24 and 39,516 at 1,200, the IFERC
# schedule's figures to the byte, under the same ceiling.
def test_a_gas_daily_schedule_keeps_a_copy_of_each_date_column() -> None:
    contracts = 120
    codes, first, last = gas_daily_columns(contracts)
    assert (
        least_peak(lambda: ENTRY["_CreateGasDailySchedule"](codes, first, last))
        <= 32 * contracts + 2 * SLACK
    )


# Five texts kept as they arrived, the record and its entry: measured 281 bytes on 2026-09-16,
# and 1,162 for reading them back as a three-row table of fifteen text cells.
def test_a_creator_of_index_conventions_and_its_reader_stay_small() -> None:
    codes = ("USD", "BBL", "USD", "volume", "BBL")
    assert least_peak(lambda: ENTRY["_CreateIndexConventions"](*codes)) <= 2 * SLACK
    handle = ENTRY["_CreateIndexConventions"](*codes)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](handle)) <= 2 * SLACK


SPECIFICATION_HEADERS = Cells.from_rows(
    [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)


def specification_body(contracts: int) -> Cells:
    """That many contracts as the sheet sends them: a name, a whole lot size and two fees."""
    return Cells.from_rows(
        [[f"contract {i}", 1000.0 + i, "MMBTU", 3.0, 2.0] for i in range(contracts)]
    )


def an_index(schedule: object, holidays: object = MISSING) -> object:
    """The index handle of that schedule handle and holiday calendar handle, with the conventions
    of gas and one lot, since nothing measured here reads either."""
    return ENTRY["_CreateIndex"](
        "sample",
        schedule,
        ENTRY["_CreateIndexConventions"]("USD", "MMBTU", "USD", "energy", "MMBTU"),
        ENTRY["_CreateContractSpecifications"](SPECIFICATION_HEADERS, specification_body(1)),
        holidays,
    )


# Contract specifications keep a copy of each numeric column, 24 bytes per contract, and on the
# way pay the table path, the names gathered and the builder's four looks, one mask each: measured
# 12,163 bytes at 120 contracts on 2026-09-17, about 76 bytes per contract beyond a creator's
# small objects; 3,037 at two contracts and 3,327 at a dozen.
def test_contract_specifications_keep_a_copy_of_each_numeric_column() -> None:
    contracts = 120
    body = specification_body(contracts)
    assert (
        least_peak(lambda: ENTRY["_CreateContractSpecifications"](SPECIFICATION_HEADERS, body))
        <= 100 * contracts + 2 * SLACK
    )


# An index is its record, a name and five references, and its reader a three-row table of five
# cells: measured 241 and 1,131 bytes on 2026-09-25, which twice the slack covers.
def test_an_index_keeps_one_small_record_and_its_reader_stays_small() -> None:
    codes, futures, _, _ = schedule_columns(13)
    schedule = ENTRY["_CreateFuturesSchedule"](codes, futures, MISSING)
    conventions = ENTRY["_CreateIndexConventions"]("USD", "MMBTU", "USD", "energy", "MMBTU")
    specifications = ENTRY["_CreateContractSpecifications"](
        SPECIFICATION_HEADERS, specification_body(12)
    )
    holidays = ENTRY["_CreateHolidayCalendar"](holiday_column(100))
    assert (
        least_peak(
            lambda: ENTRY["_CreateIndex"](
                "Henry Hub NYMEX", schedule, conventions, specifications, holidays
            )
        )
        <= 2 * SLACK
    )
    made = ENTRY["_CreateIndex"]("Henry Hub NYMEX", schedule, conventions, specifications, holidays)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](made)) <= 2 * SLACK


def test_owning_a_range_peaks_at_the_two_copies() -> None:
    kinds = (ctypes.c_uint8 * N)(*([0] * N))
    numbers = (ctypes.c_double * N)(*[float(i) for i in range(N)])
    pointers = ctypes.addressof(kinds), ctypes.addressof(numbers)
    assert least_peak(lambda: bridge.cells_from_buffers(*pointers, N, 1, "", 1)) <= 9 * N + SLACK


def fixings_columns(rows: int, holidays: int) -> tuple[Cells, Cells]:
    """That many futures fixings as the sheet sends them, the newest day in the first row: a
    column of serials and a column of settles, one per business day from Friday 1 May 2026 under
    a calendar of that many Thursdays a week apart, the calendar holiday_column makes."""
    epoch = np.datetime64("1899-12-30")
    closed = epoch + (46023 + 7 * np.arange(holidays)).astype("timedelta64[D]")
    days = np.busday_offset(np.datetime64("2026-05-01"), np.arange(rows), holidays=closed)
    serials = (days - epoch).astype(np.int64)
    newest_first = range(rows - 1, -1, -1)
    return (
        Cells.from_rows([[float(serials[i])] for i in newest_first]),
        Cells.from_rows([[100.0 + i % 7] for i in newest_first]),
    )


# Futures fixings keep a copy of each column, 16 bytes per row, and on the way pay the date
# column's masks and its arrays on the way to days, and the builder's two looks, the order and
# the days closed, and its count of the business days between the last row's date and the
# first's, two dates and no temporary: measured 8,624 bytes at 260 rows on 2026-10-01, about 29
# bytes per row on top of the slack, 11,210 when the gaps were a look over the business day
# after each date; 69,464 at 2,600 and 677,864 at 26,000, 26 bytes per row, where they were
# 93,110 and 912,110, 35 per row. Taking the rows newest first and copying each column from its
# last row back added 40 bytes at any count, the two views the copies read through: 8,664 at
# 260 rows and 69,504 at 2,600 on 2026-10-02. A ceiling of 35 per row holds the new form and
# refuses the old.
def test_futures_fixings_keep_a_copy_of_each_column() -> None:
    rows = 260
    codes, futures, _, _ = schedule_columns(2)
    index = an_index(
        ENTRY["_CreateFuturesSchedule"](codes, futures, MISSING),
        ENTRY["_CreateHolidayCalendar"](holiday_column(100)),
    )
    days, settles = fixings_columns(rows, 100)
    assert (
        least_peak(lambda: ENTRY["_CreateFuturesFixings"](days, settles, index))
        <= 35 * rows + SLACK
    )


def calendar_sources(contracts: int) -> tuple[object, object]:
    """The two handles a calendar takes: the valuation date, and the index of a schedule of that
    many monthly contracts a month apart with a calendar of a hundred holidays a week apart."""
    codes, futures, _, _ = schedule_columns(contracts)
    schedule = ENTRY["_CreateFuturesSchedule"](codes, futures, MISSING)
    holidays = ENTRY["_CreateHolidayCalendar"](holiday_column(100))
    return ENTRY["_CreateValuationDate"](46276.0, 0.5), an_index(schedule, holidays)


# A calendar keeps four columns, 18 bytes per day, the days and the prompt rows 8 each and the
# two flags a byte each, and on the way pays the arange, the searchsorted and the flags'
# temporaries: measured 8,620 bytes at 360 days on 2026-09-18, about 24 bytes per day on top of
# a creator's small objects, which twice the slack covers; 66,741 at 3,630 days and 661,841 at
# 36,630, 18 bytes per day. Reading it back pays the reader's rectangle, four cells per day,
# the codes placed as text and the days to serials: measured 26,308 at 360 days, about 18
# bytes per cell; 251,938 at 3,630 days, 17.4 per cell. The ceiling is 18 per cell at both
# sizes: a second copy of the codes alive at the peak, 8 bytes per day, read 276,540 at 3,630
# days and passed a ceiling of 20 at 360, so the larger size is pinned too. Measured again on
# 2026-10-02, when the reader began to cut its columns at a row a market may give it: 26,708
# and 252,338, 400 bytes more at either size, the cuts' own small objects and none per day.
def test_a_calendar_keeps_four_columns_and_its_reader_pays_per_cell() -> None:
    days = 360
    valuation, index = calendar_sources(13)
    assert least_peak(lambda: ENTRY["_CreateCalendar"](valuation, index)) <= 25 * days + 2 * SLACK
    made = ENTRY["_CreateCalendar"](valuation, index)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](made)) <= 18 * 4 * days + 2 * SLACK
    ten_years = ENTRY["_CreateCalendar"](*calendar_sources(122))
    assert least_peak(lambda: ENTRY["util_ReadHandle"](ten_years)) <= 18 * 4 * 3_630 + 2 * SLACK


def gas_daily_month_columns(months: int) -> tuple[Cells, Cells, Cells]:
    """Codes and the first and last day of that many calendar months from January 2026, laid
    end to end, as the sheet sends them."""
    firsts = np.arange("2026-01", "2126-01", dtype="datetime64[M]")[: months + 1]
    starts = firsts[:-1].astype("datetime64[D]")
    ends = firsts[1:].astype("datetime64[D]") - np.timedelta64(1, "D")
    # Days since 1970 to the sheet's serials: 1 January 1970 is serial 25569.
    first = starts.astype(np.int64) + 25569
    last = ends.astype(np.int64) + 25569
    return (
        Cells.from_rows([[f"c{i}"] for i in range(months)]),
        Cells.from_rows([[float(first[i])] for i in range(months)]),
        Cells.from_rows([[float(last[i])] for i in range(months)]),
    )


# A Gas Daily calendar keeps the futures calendar's four columns, 18 bytes per day, and pays the
# arange, the searchsorted and the flags' temporaries the same way, less a business-day look:
# measured 7,969 bytes at 365 days on 2026-09-25, about 22 bytes per day, and 67,351 at 3,653,
# 18 bytes per day, which the futures calendar's 25 per day covers. An IFERC calendar keeps one
# row per month, its copy of the publication days and its rows, and pays one look, the flags
# and the set its codes are checked through, most of the peak at a small count: measured
# 10,504 bytes at 120 months and 41,224 at 1,200, 34 bytes per month, which 80 per month covers
# with twice the slack, as the IFERC fixings' set does.
def test_the_other_two_calendars_keep_four_columns_per_period() -> None:
    valuation = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    gas_daily = ENTRY["_CreateGasDailySchedule"](*gas_daily_month_columns(12))
    gas_daily_index = an_index(gas_daily)
    assert (
        least_peak(lambda: ENTRY["_CreateCalendar"](valuation, gas_daily_index))
        <= 25 * 365 + 2 * SLACK
    )
    iferc = ENTRY["_CreateIfercSchedule"](*iferc_columns(120))
    iferc_index = an_index(iferc)
    assert (
        least_peak(lambda: ENTRY["_CreateCalendar"](valuation, iferc_index)) <= 80 * 120 + 2 * SLACK
    )


def history_sources(contracts: int) -> tuple[object, object]:
    """The two handles a history takes: the calendar calendar_sources makes, valued on 11
    September 2026, and fixings on every business day from Friday 1 May 2026 to the day
    before, under the same hundred Thursdays, so every fixed business day has one."""
    valuation, index = calendar_sources(contracts)
    made = ENTRY["_CreateCalendar"](valuation, index)
    closed = np.datetime64("1899-12-30") + (46023 + 7 * np.arange(100)).astype("timedelta64[D]")
    rows = int(np.busday_count("2026-05-01", "2026-09-11", holidays=closed))
    fixings = ENTRY["_CreateFuturesFixings"](*fixings_columns(rows, 100), index)
    return made, fixings


# A history keeps two columns, 16 bytes per fixed business day, the row and the price, and
# nothing per day of the calendar, which it keeps as it is; on the way it pays the builder's
# looks, a byte or so per fixing and per day for the days covered and the flags combined:
# measured 3,681 bytes at 360 days with 76 fixings on 2026-09-19, 16,641 at 3,600 days and
# 148,641 at 36,600, 4 bytes per day. Reading it back pays the calendar's table and then the
# fifth column, the words made once, the wider kinds and slots, the codes paired with the
# words, and the mixed road's masks over five columns: measured 53,627 at 360 days on
# 2026-09-19 through the helper the market's reader shares, from 51,267 before it, about 30
# bytes per cell; 629,741 at 3,600 days and 6,528,344 at 36,600, 35 bytes per cell, where the
# road splits the joined text per text.
def test_a_market_history_keeps_two_short_columns_and_its_reader_pays_per_cell() -> None:
    days = 360
    made, fixings = history_sources(13)
    assert least_peak(lambda: ENTRY["_CreateMarketHistory"](made, fixings)) <= 6 * days + 2 * SLACK
    history = ENTRY["_CreateMarketHistory"](made, fixings)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](history)) <= 30 * 5 * days + 2 * SLACK


def gas_daily_history_sources() -> tuple[object, object]:
    """The two handles a Gas Daily history takes: the calendar of the twelve months of 2026
    valued on 11 September, and a print on every flow day from New Year's Day to the 11th, so
    that every fixed day has one."""
    valuation = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    schedule = ENTRY["_CreateGasDailySchedule"](*gas_daily_month_columns(12))
    index = an_index(schedule)
    made = ENTRY["_CreateCalendar"](valuation, index)
    days = 46276 - 46023 + 1  # New Year's Day 2026 is serial 46023
    newest_first = range(days - 1, -1, -1)  # the sheet's order, the 11th in the first row
    fixings = ENTRY["_CreateGasDailyFixings"](
        Cells.from_rows([[46023.0 + i] for i in newest_first]),
        Cells.from_rows([[2.8 + (i % 30) / 100] for i in newest_first]),
        index,
    )
    return made, fixings


def iferc_history_sources() -> tuple[object, object]:
    """The two handles an IFERC history takes: the calendar of the ten years of months
    iferc_columns lays out, valued after the last month's publication day so that every month
    has fixed, and an index for each of them."""
    valuation = ENTRY["_CreateValuationDate"](49740.0, 0.5)
    schedule = ENTRY["_CreateIfercSchedule"](*iferc_columns(120))
    index = an_index(schedule)
    made = ENTRY["_CreateCalendar"](valuation, index)
    fixings = ENTRY["_CreateIfercFixings"](*iferc_fixing_columns(120), index)
    return made, fixings


# A Gas Daily history keeps the same two columns, 16 bytes per fixed day, and every day of the
# calendar through the valuation day is fixed, so it pays per day what the futures history pays
# per fixing, the print's row and its inside mask, the days covered, the flags combined and the
# copied prices: measured 7,404 bytes at 365 days with 254 prints on 2026-09-25, and 95,752 at
# 3,652 days all fixed, 26 bytes per day, which 30 per day covers with twice the slack. An IFERC
# history keeps two columns per month and pays the dict its codes are found through, the rows,
# the two looks and the argsort, most of the peak at a small count: measured 12,544 bytes at 120
# months and 105,204 at 1,200, 88 bytes per month, which 100 per month covers. Reading either
# back pays the reader's rectangle as the futures history's does: measured 51,332 at 365 days
# and 480,153 at 3,652, 26 bytes per cell; 19,091 at 120 months, 32 bytes per cell at that
# count, and 158,941 at 1,200, 26 per cell.
def test_the_other_two_histories_keep_two_short_columns_and_their_readers_pay_per_cell() -> None:
    days, months = 365, 120
    made, prints = gas_daily_history_sources()
    assert least_peak(lambda: ENTRY["_CreateMarketHistory"](made, prints)) <= 30 * days + 2 * SLACK
    daily = ENTRY["_CreateMarketHistory"](made, prints)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](daily)) <= 30 * 5 * days + 2 * SLACK
    calendar, indices = iferc_history_sources()
    assert (
        least_peak(lambda: ENTRY["_CreateMarketHistory"](calendar, indices))
        <= 100 * months + 2 * SLACK
    )
    monthly = ENTRY["_CreateMarketHistory"](calendar, indices)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](monthly)) <= 35 * 5 * months + 2 * SLACK


def iferc_fixing_columns(count: int) -> tuple[Cells, Cells]:
    """That many contract months' indices as the sheet sends them: the codes of schedule_columns
    and a price beside each."""
    codes, _, _, _ = schedule_columns(count)
    return codes, Cells.from_rows([[2.0 + i / 100] for i in range(count)])


# IFERC fixings keep the seam's tuple of codes as it is and a copy of the price column, 8 bytes
# per month, and on the way pay the set of the index's months the codes are struck off, one set
# checking membership and repeats alike, which is most of the peak at a small count: measured
# 10,600 bytes at 120 months on 2026-09-24 with the set of the codes, and the same shape with the
# set of the months since #109, about 80 bytes per month at that size on top of a creator's small
# objects, which twice the slack covers, and 41,348 at 1,200, 34 bytes per month, the set growing
# slower than the count.
def test_iferc_fixings_keep_a_copy_of_their_prices() -> None:
    count = 120
    codes, prices = iferc_fixing_columns(count)
    index = an_index(ENTRY["_CreateIfercSchedule"](*iferc_columns(count)))
    assert (
        least_peak(lambda: ENTRY["_CreateIfercFixings"](codes, prices, index))
        <= 80 * count + 2 * SLACK
    )


def flow_day_columns(count: int) -> tuple[Cells, Cells]:
    """That many consecutive flow days from 1 September 2026 as the sheet sends them, the newest
    in the first row, a serial per row, and a price beside each."""
    newest_first = range(count - 1, -1, -1)
    return (
        Cells.from_rows([[46266.0 + i] for i in newest_first]),
        Cells.from_rows([[2.8 + (i % 30) / 100] for i in newest_first]),
    )


# Gas Daily fixings keep a copy of each column, 16 bytes per flow day, and on the way pay the
# date column's masks and its arrays on the way to days, then the day before each day and the
# mask of the days that are not it: measured 13,108 bytes at a year of flow days on 2026-09-24,
# 36 bytes per day, and 121,513 at ten years, 33 bytes per day, which 40 per day covers with
# twice the slack for a creator's small objects. Taking the rows newest first and copying each
# column from its last row back added 40 bytes at any count, the two views the copies read
# through: 13,156 at a year and 121,561 at ten years on 2026-10-02, against 13,116 and 121,521
# for the old form measured the same day.
def test_gas_daily_fixings_keep_a_copy_of_each_column() -> None:
    count = 365
    flow_days, prices = flow_day_columns(count)
    index = an_index(ENTRY["_CreateGasDailySchedule"](*gas_daily_month_columns(12)))
    assert (
        least_peak(lambda: ENTRY["_CreateGasDailyFixings"](flow_days, prices, index))
        <= 40 * count + 2 * SLACK
    )


def price_column(prices: int) -> Cells:
    """That many prices as the sheet sends them, one per row, around 74."""
    return Cells.from_rows([[74.25 + i % 7 - 3.0] for i in range(prices)])


def price_vector_peaks(prices: int) -> tuple[int, int]:
    """The least peak of creating a vector of that many prices, and of reading it back."""
    column = price_column(prices)
    made = ENTRY["_CreatePriceVector"]("sample", column)
    return (
        least_peak(lambda: ENTRY["_CreatePriceVector"]("sample", column)),
        least_peak(lambda: ENTRY["util_ReadHandle"](made)),
    )


# A price vector keeps one copy of its column, 8 bytes per price, and nothing else per price:
# the column is accepted on the host's summary, so no look and no temporary, and the name is
# the text the seam already holds. Measured 1,273 bytes at 120 prices on 2026-09-19, the copy
# plus a creator's small objects, which twice the slack covers, and 80,314 at 10,000, 8 bytes
# per price; 392 for a single cell; with the name, on 2026-09-26, 1,281, 80,322 and 408, the
# record's one more slot. Reading it back pays the table's kinds and slots and the mixed road's
# masks: measured 2,492 at 120 prices, about 20 bytes per cell, and 140,812 at 10,000, 14.
def test_a_price_vector_keeps_one_copy_of_its_column_and_nothing_per_price_beyond() -> None:
    for prices in (120, 10_000):
        created, read = price_vector_peaks(prices)
        assert created <= 8 * prices + 2 * SLACK
        assert read <= 21 * (prices + 2) + SLACK
    assert least_peak(lambda: ENTRY["_CreatePriceVector"]("sample", 74.25)) <= SLACK


def market_sources(contracts: int, days_apart: int) -> tuple[object, object]:
    """The two handles a market takes: the history of a calendar of that many contracts that
    many days apart from 19 May 2026, valued on 11 September 2026 with a fixing on every
    business day before it under a hundred Thursdays, and a vector with one quote per contract
    from the valuation day's prompt through the last."""
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    futures = Cells.from_rows([[46161.0 + days_apart * i] for i in range(contracts)])
    valuation = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    schedule = ENTRY["_CreateFuturesSchedule"](codes, futures, MISSING)
    index = an_index(schedule, ENTRY["_CreateHolidayCalendar"](holiday_column(100)))
    made = ENTRY["_CreateCalendar"](valuation, index)
    closed = np.datetime64("1899-12-30") + (46023 + 7 * np.arange(100)).astype("timedelta64[D]")
    rows = int(np.busday_count("2026-05-01", "2026-09-11", holidays=closed))
    fixings = ENTRY["_CreateFuturesFixings"](*fixings_columns(rows, 100), index)
    history = ENTRY["_CreateMarketHistory"](made, fixings)
    first = int(np.searchsorted(46161.0 + days_apart * np.arange(contracts), 46276.0))
    quotes = Cells.from_rows([[70.0 + i % 5] for i in range(contracts - first)])
    return history, ENTRY["_CreatePriceVector"]("sample", quotes)


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


def gas_daily_market_sources() -> tuple[object, object]:
    """The two handles a Gas Daily market takes: the history gas_daily_history_sources makes,
    the twelve months of 2026 valued on 11 September, and a vector of four quotes, the balance
    of September and the three months after it."""
    history = ENTRY["_CreateMarketHistory"](*gas_daily_history_sources())
    return history, ENTRY["_CreatePriceVector"](
        "sample", Cells.from_rows([[3.0 + i] for i in range(4)])
    )


def iferc_market_sources(months: int = 120) -> tuple[object, object]:
    """The two handles an IFERC market takes: the calendar of that many months as iferc_columns
    lays them out, ten years unless more are asked for, valued on 11 September 2026 with four
    months published and an index for each, and a vector of one quote per month still to
    publish, 116 over the ten years."""
    valuation = ENTRY["_CreateValuationDate"](46276.0, 0.5)
    schedule = ENTRY["_CreateIfercSchedule"](*iferc_columns(months))
    index = an_index(schedule)
    made = ENTRY["_CreateCalendar"](valuation, index)
    fixings = ENTRY["_CreateIfercFixings"](*iferc_fixing_columns(4), index)
    history = ENTRY["_CreateMarketHistory"](made, fixings)
    return history, ENTRY["_CreatePriceVector"](
        "sample", Cells.from_rows([[2.0 + i] for i in range(months - 4)])
    )


# The same record over the other two histories, a year of flow days with four quotes and ten
# years of months with 116, the row of the first unfixed period read off the calendar.
@pytest.mark.parametrize(
    "sources",
    [gas_daily_market_sources, iferc_market_sources],
    ids=["a Gas Daily market", "an IFERC market"],
)
def test_a_market_over_the_other_two_calendars_keeps_the_same_record(
    sources: Callable[[], tuple[object, object]],
) -> None:
    history, quotes = sources()
    assert least_peak(lambda: ENTRY["_CreateMarket"](history, quotes)) <= 2 * SLACK


# Reading a market back pays the calendar's table and then the fifth column through the
# history's helper, with the live rows, their prompts and their quotes on top: measured 50,931
# bytes at 360 days on 2026-09-19, about 28 bytes per cell, and 501,307 at 3,600. A Gas Daily
# market reads back the same way, 48,612 bytes at 365 days on 2026-09-25, 27 per cell, and an
# IFERC market 20,163 at 120 months, 34 bytes per cell at that small count. Measured again on
# 2026-10-02, when the reader began to stop at the last row the quotes cover: 50,789, 501,165,
# 48,468 and 20,107, each 80 bytes above the build before it, 48 for IFERC, none of it per row.
def test_reading_a_market_back_pays_per_cell() -> None:
    days, months = 360, 120
    made = ENTRY["_CreateMarket"](*market_sources(13, 30))
    assert least_peak(lambda: ENTRY["util_ReadHandle"](made)) <= 30 * 5 * days + 2 * SLACK
    daily = ENTRY["_CreateMarket"](*gas_daily_market_sources())
    assert least_peak(lambda: ENTRY["util_ReadHandle"](daily)) <= 30 * 5 * 365 + 2 * SLACK
    monthly = ENTRY["_CreateMarket"](*iferc_market_sources())
    assert least_peak(lambda: ENTRY["util_ReadHandle"](monthly)) <= 35 * 5 * months + 2 * SLACK


def a_short_vector(quotes: int) -> object:
    """A vector of that many quotes, fewer than the schedule it meets has left."""
    return ENTRY["_CreatePriceVector"](
        "sample", Cells.from_rows([[70.0 + i] for i in range(quotes)])
    )


# A market whose quotes stop before the schedule does keeps the same small record, and reading
# it back pays for the rows the quotes cover and no others, however long the calendar and the
# schedule run on: the columns are cut at the last row covered before anything is made of them,
# and the codes are taken no further than the last contract covered. The calendars here are a
# hundred years long, so that a temporary the length of the calendar, a byte a day, or of the
# schedule, eight bytes a month, would stand above the ceiling. Measured on 2026-10-02: one
# quote over a hundred years of days, 120 rows covered of 36,000, reads back in 17,907
# bytes, the same to the byte as over one year of days; a Gas Daily market with the balance of
# September alone, 273 rows of 365, in 36,094; an IFERC market with one quote over a
# hundred years of months, 5 rows of 1,200, in 4,922, most of it the reader's fixed
# cost; and one with 56 quotes of 116, 60 rows of 120, in 12,247, 41 bytes per
# cell at that small count, where the whole takes 20,107.
def test_a_market_stopping_early_is_read_back_for_the_rows_it_covers() -> None:
    covered = 120  # the days from 20 May 2026 through the first quoted contract's expiry
    quote = a_short_vector(1)
    year, _ = market_sources(13, 30)
    century, _ = market_sources(1201, 30)
    assert least_peak(lambda: ENTRY["_CreateMarket"](century, quote)) <= 2 * SLACK
    over_a_year = ENTRY["_CreateMarket"](year, quote)
    over_a_century = ENTRY["_CreateMarket"](century, quote)
    ceiling = 30 * 5 * covered + 2 * SLACK
    assert least_peak(lambda: ENTRY["util_ReadHandle"](over_a_year)) <= ceiling
    assert least_peak(lambda: ENTRY["util_ReadHandle"](over_a_century)) <= ceiling
    gas_daily, _ = gas_daily_market_sources()
    balance = ENTRY["_CreateMarket"](gas_daily, quote)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](balance)) <= 30 * 5 * 273 + 2 * SLACK
    months, _ = iferc_market_sources(1200)
    one_month = ENTRY["_CreateMarket"](months, quote)
    assert least_peak(lambda: ENTRY["util_ReadHandle"](one_month)) <= 6 * SLACK
    iferc, _ = iferc_market_sources()
    half = ENTRY["_CreateMarket"](iferc, a_short_vector(56))
    assert least_peak(lambda: ENTRY["util_ReadHandle"](half)) <= 40 * 5 * 60 + 2 * SLACK


# --- what a publication keeps -------------------------------------------------
# The peaks above bound what a call allocates on its way; these pin what is still held when it
# has returned, and that a release lets all of it go. numpy registers every data buffer it
# allocates with tracemalloc under a domain of its own, np.lib.tracemalloc_domain, so that
# domain alone is the arrays' bytes: the buffers allocated since tracing started and still
# alive. Nothing else is in the measure: not a buffer made before tracing started, a
# dependency's columns among them, not a Python object, the record, its entry in the store,
# its handle or a tuple of texts, and nothing the host or Excel holds.

DAY_BYTES = np.dtype("datetime64[D]").itemsize
NUMBER_BYTES = np.dtype(np.float64).itemsize
ROW_BYTES = np.dtype(np.intp).itemsize
FLAG_BYTES = np.dtype(np.bool_).itemsize


def numpy_bytes() -> int:
    """The bytes of the numpy data buffers allocated since tracing started and still alive."""
    snapshot = tracemalloc.take_snapshot()
    buffers = snapshot.filter_traces([tracemalloc.DomainFilter(True, np.lib.tracemalloc_domain)])
    return sum(trace.size for trace in buffers.traces)


def retained_numpy_bytes(create: Callable[[], object]) -> tuple[int, int]:
    """The numpy bytes a creator's publication holds once the call has returned, and once it has
    been released. The inputs and the handles the creator depends on are made before this is
    called, so nothing of theirs is counted. The publication is released whatever happens in
    between, and both the creation and the release must have succeeded."""
    tracemalloc.start()
    try:
        made = create()
        text = made if isinstance(made, str) else ""
        try:
            assert text and not text.startswith("#ERROR"), f"the creator returned {made!r}"
            held = numpy_bytes()
        finally:
            released = bridge.release(text)
        assert released, f"{text} named no publication to release"
        return held, numpy_bytes()
    finally:
        tracemalloc.stop()


# The measure itself: a buffer made before tracing started is never counted, a buffer made
# since is counted to the byte, a Python object beside it adds nothing, and the count returns to
# zero when the buffer is freed. A numpy release that moved its buffers out of the domain would
# fail here, loudly, before any pin below read zero for the wrong reason.
def test_the_retained_measure_counts_new_numpy_buffers_and_nothing_else() -> None:
    before = np.empty(4_096)
    tracemalloc.start()
    try:
        assert numpy_bytes() == 0
        made = np.empty(4_096)
        words = ["text"] * 4_096
        assert numpy_bytes() == made.nbytes == 4_096 * NUMBER_BYTES
        del made
        assert numpy_bytes() == 0
    finally:
        tracemalloc.stop()
    assert before.size == len(words) == 4_096


# A discount curve keeps its two columns, a day and a factor for every day from the first anchor
# to the last, the same from a daily table and from a dozen anchors, and nothing once released.
@pytest.mark.parametrize("given", ["a daily table", "a dozen anchors"])
def test_a_discount_curve_keeps_its_two_columns_and_release_frees_them(given: str) -> None:
    days = 3_631
    body = curve_body(days) if given == "a daily table" else anchor_body(12, days - 1)
    kept = retained_numpy_bytes(lambda: ENTRY["_CreateDiscountCurve"](CURVE_HEADERS, body))
    assert kept == (days * (DAY_BYTES + NUMBER_BYTES), 0)


# Futures fixings keep their two columns, a date and a settle per row; the index and its
# holiday calendar were made before and are not theirs.
def test_futures_fixings_keep_their_two_columns_and_release_frees_them() -> None:
    rows = 260
    codes, futures, _, _ = schedule_columns(2)
    index = an_index(
        ENTRY["_CreateFuturesSchedule"](codes, futures, MISSING),
        ENTRY["_CreateHolidayCalendar"](holiday_column(100)),
    )
    days, settles = fixings_columns(rows, 100)
    kept = retained_numpy_bytes(lambda: ENTRY["_CreateFuturesFixings"](days, settles, index))
    assert kept == (rows * (DAY_BYTES + NUMBER_BYTES), 0)


# A holiday calendar keeps its one column of dates.
def test_a_holiday_calendar_keeps_its_one_column_and_release_frees_it() -> None:
    dates = 100
    holidays = holiday_column(dates)
    kept = retained_numpy_bytes(lambda: ENTRY["_CreateHolidayCalendar"](holidays))
    assert kept == (dates * DAY_BYTES, 0)


# A futures calendar keeps its four columns: the days, the row of each day's contract, and the
# two flags, priced and fixed.
def test_a_futures_calendar_keeps_its_four_columns_and_release_frees_them() -> None:
    days = 360
    valuation, index = calendar_sources(13)
    kept = retained_numpy_bytes(lambda: ENTRY["_CreateCalendar"](valuation, index))
    assert kept == (days * (DAY_BYTES + ROW_BYTES + 2 * FLAG_BYTES), 0)
