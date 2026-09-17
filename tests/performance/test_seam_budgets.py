"""What one call through the seam costs, itemized: exact and deterministic."""

import ctypes
from collections.abc import Callable
from datetime import date

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import MISSING, Cells

CallProfile = Callable[[Callable[[], object]], dict[str, int]]

# Each registered function's prepared path, fetched once as the host does at registration; the
# three looks in conftest.py (FirstOfNumbers, FirstOfDates, FirstOfNames) are registered
# when pytest loads it, so they are in it too.
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}


def test_accepted_scalar_call_itemized(call_profile: CallProfile) -> None:
    PATH["Add"](1.0, 2.0)
    assert call_profile(lambda: PATH["Add"](1.0, 2.0)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_number": 2,
        "Add": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_rejected_scalar_call_stops_at_the_first_failure(call_profile: CallProfile) -> None:
    assert call_profile(lambda: PATH["Add"]("x", 2.0)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_number": 1,
        "_Rejected.__init__": 1,
        "describe": 1,
    }


# A range of numbers needs no look: the host's summary settles it. Whatever a range holds, the
# seam's own functions run the same number of times.
def test_accepted_array_call_itemized(call_profile: CallProfile) -> None:
    column = Cells.from_rows([[float(i)] for i in range(10_000)])
    PATH["SumArray"](column)
    assert call_profile(lambda: PATH["SumArray"](column)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_numbers": 1,
        "SumArray": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_accepted_column_call_itemized(call_profile: CallProfile) -> None:
    column = Cells.from_rows([[float(i)] for i in range(10_000)])
    PATH["FirstOfNumbers"](column)
    assert call_profile(lambda: PATH["FirstOfNumbers"](column)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_numbers": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_accepted_date_column_call_itemized(call_profile: CallProfile) -> None:
    column = Cells.from_rows([[float(61 + i)] for i in range(10_000)])
    PATH["FirstOfDates"](column)
    assert call_profile(lambda: PATH["FirstOfDates"](column)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_date_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_dates": 1,
        "_not_dates": 1,  # the two helpers the date rule shares with a table's column of dates
        "_as_days": 1,
        "_text_out": 1,
        "_scalar": 1,
    }


def test_accepted_text_column_call_itemized(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    names = Cells.from_rows([[f"name{i}"] for i in range(10_000)])
    PATH["FirstOfNames"](names)
    assert call_profile(lambda: PATH["FirstOfNames"](names)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_texts": 1,
        "_text_out": 1,
        "_scalar": 1,
    }
    # The host's tuple of text cells is the column itself, handed over as it is: nothing is
    # asked of numpy. Before, the tuple went into an object array and back out of one.
    assert numpy_calls(lambda: PATH["FirstOfNames"](names)) == {}


# A bad cell deep inside a range is found and named without a walk, whatever it holds.
REJECTED_DEEP = {
    "Registered.run": 1,
    "_arguments": 1,
    "_validate": 1,
    "_numbers": 1,
    "_first_bad": 1,
    "_cell": 1,
    "_Rejected.__init__": 1,
    "describe": 1,
}


def test_blank_deep_in_a_column_is_named_without_a_walk(call_profile: CallProfile) -> None:
    rows: list[list[object]] = [[float(i)] for i in range(10_000)]
    rows[5_000][0] = None
    column = Cells.from_rows(rows)
    assert call_profile(lambda: PATH["SumArray"](column)) == REJECTED_DEEP


def test_text_deep_in_a_column_is_named_without_a_walk(call_profile: CallProfile) -> None:
    rows: list[list[object]] = [[float(i)] for i in range(10_000)]
    rows[5_000][0] = "n/a"
    column = Cells.from_rows(rows)
    assert call_profile(lambda: PATH["SumArray"](column)) == REJECTED_DEEP


# --- every probe, itemized on both ledgers ------------------------------------
# The package ledger is the seam's own functions; the numpy ledger is the copies and
# reductions numpy ran for them. Inputs are built inside the test: a large parameter would
# put its repr into the test id, which pytest keeps in an environment variable that Windows
# caps at 32,767 characters.

N = 10_000


def column() -> Cells:
    return Cells.from_rows([[float(i)] for i in range(N)])


def row() -> Cells:
    return Cells.from_rows([[float(i) for i in range(N)]])


def grid() -> Cells:
    return Cells.from_rows([[float(r * 100 + c) for c in range(100)] for r in range(100)])


def test_zero_is_the_floor_of_one_call(call_profile: CallProfile) -> None:
    PATH["Zero"]()
    assert call_profile(lambda: PATH["Zero"]()) == {
        "Registered.run": 1,
        "_arguments": 1,
        "Zero": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_a_missing_argument_takes_its_default_without_a_look(call_profile: CallProfile) -> None:
    PATH["Times"](5.0, MISSING)
    assert call_profile(lambda: PATH["Times"](5.0, MISSING)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_number": 1,
        "Times": 1,
        "_number_out": 1,
        "_scalar": 1,
    }


def test_text_in_and_out_itemized(call_profile: CallProfile) -> None:
    PATH["EchoText"]("WTI")
    assert call_profile(lambda: PATH["EchoText"]("WTI")) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_text": 1,
        "EchoText": 1,
        "_text_out": 1,
        "_scalar": 1,
    }


def test_a_boolean_in_and_out_itemized(call_profile: CallProfile) -> None:
    PATH["EchoBoolean"](True)
    assert call_profile(lambda: PATH["EchoBoolean"](True)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_boolean": 1,
        "EchoBoolean": 1,
        "_boolean_out": 1,
        "_scalar": 1,
    }


def test_a_failing_body_costs_no_look(call_profile: CallProfile) -> None:
    PATH["Fail"]()
    assert call_profile(lambda: PATH["Fail"]()) == {
        "Registered.run": 1,
        "_arguments": 1,
        "Fail": 1,
    }


def test_two_ranges_are_two_checks_and_no_look(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    a, b = column(), column()
    PATH["Dot"](a, b)
    assert call_profile(lambda: PATH["Dot"](a, b)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_column": 2,
        "_one_column": 2,
        "_shape": 2,
        "_numbers": 2,
        "Dot": 1,
        "_number_out": 1,
        "_scalar": 1,
    }
    # Two ranges of numbers: the host's summary settles both, so numpy takes no look at all.
    assert numpy_calls(lambda: PATH["Dot"](a, b)) == {}


def test_a_sum_is_one_reduction_and_no_look(numpy_calls: CallProfile) -> None:
    values = column()
    PATH["SumArray"](values)
    assert numpy_calls(lambda: PATH["SumArray"](values)) == {
        "ndarray.sum": 1,
        "ufunc.reduce": 1,
    }


# The mixed road out runs the same functions and takes the same three looks whatever the
# rectangle holds: one for a cell holding no value, one for a number that is not finite, one
# for a boolean slot that is not 0 or 1. The texts are joined and encoded once, off the ledger,
# and split per text only when the total runs past what a cell holds.
@pytest.mark.parametrize("rectangle", ["numbers", "mixed"])
def test_a_mixed_array_out_takes_three_looks_whatever_it_holds(
    rectangle: str, call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    cells = column() if rectangle == "numbers" else mixed()
    PATH["EchoMixed"](cells)
    assert call_profile(lambda: PATH["EchoMixed"](cells)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_mixed": 1,
        "EchoMixed": 1,
        "_mixed_out": 1,
        "_bad_mixed": 1,  # the cells holding no value, flagged in one array
    }
    assert numpy_calls(lambda: PATH["EchoMixed"](cells)) == {
        "ndarray.any": 3,
        "numpy.ascontiguousarray": 2,  # the kinds and the numbers, already contiguous: no copy
        "ufunc.reduce": 3,
    }


def mixed() -> Cells:
    """A trade's shape: a name, a serial, a quantity and a flag, over and over."""
    return Cells.from_rows([[f"n{i}", 46164.0 + i, float(i), i % 2 == 0] for i in range(N // 4)])


# A mixed range is the numeric call with one rule changed, and that is the whole difference:
# the summary settles the kinds, so numpy is asked for nothing on either.
def test_a_mixed_range_costs_the_numeric_call_with_one_rule_changed(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    numbers, cells = column(), mixed()
    PATH["CountArray"](numbers)
    PATH["CountMixed"](cells)
    assert call_profile(lambda: PATH["CountArray"](numbers)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_numbers": 1,
        "CountArray": 1,
        "_whole_out": 1,
        "_scalar": 1,
    }
    assert call_profile(lambda: PATH["CountMixed"](cells)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_mixed": 1,  # where the numeric call runs _numbers
        "MixedArray.shape": 1,  # and the record reads its own rows and columns
        "CountMixed": 1,
        "_whole_out": 1,
        "_scalar": 1,
    }
    assert numpy_calls(lambda: PATH["CountArray"](numbers)) == {}
    assert numpy_calls(lambda: PATH["CountMixed"](cells)) == {}


# Whatever the offending cell holds, and however it fails, the same functions run once each.
def test_a_mixed_range_names_its_first_bad_cell_the_same_way_whichever_way_it_is_bad(
    call_profile: CallProfile,
) -> None:
    rejected = {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_mixed": 1,
        "_bad_mixed": 1,
        "_first_bad": 1,
        "_cell": 1,
        "_Rejected.__init__": 1,
        "describe": 1,
    }
    blank: list[list[object]] = [[float(i)] for i in range(N)]
    blank[N // 2][0] = None
    empty: list[list[object]] = [[f"n{i}"] for i in range(N)]
    empty[N // 2][0] = ""
    for rows in (blank, empty):
        values = Cells.from_rows(rows)
        PATH["CountMixed"](values)
        assert call_profile(lambda v=values: PATH["CountMixed"](v)) == rejected


HEADERS = Cells.from_rows([["date", "product", "quantity", "cleared"]])


def trades() -> Cells:
    """A table's body at N cells: a date, a text, a number and a flag per row."""
    return Cells.from_rows([[46276.0 + i, f"p{i}", float(i), i % 2 == 0] for i in range(N // 4)])


# A table is the mixed call with the binding and one rule per column on top: every bridge
# function runs once, and numpy takes one look per column, one conversion per date or boolean
# column, and one gather for the column of text, whatever the number of rows.
def test_a_table_in_itemized(call_profile: CallProfile, numpy_calls: CallProfile) -> None:
    body = trades()
    PATH["SumQuantity"](HEADERS, body)
    assert call_profile(lambda: PATH["SumQuantity"](HEADERS, body)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text_row": 1,  # the header row, as any row of text
        "_one_row": 1,
        "_shape": 1,
        "_texts": 1,
        "_mixed": 1,  # the body, admitted as any mixed range
        "MixedArray.shape": 1,
        "_refine": 1,  # then bound and refined
        "_bind": 1,
        "_refine.<locals>.<lambda>": 1,  # the text places, made once on first use
        "_text_places": 1,
        "_dates_of": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_texts_of": 1,
        "_numbers_of": 1,
        "_booleans_of": 1,
        "SumQuantity": 1,
        "_number_out": 1,
        "_scalar": 1,
    }
    assert numpy_calls(lambda: PATH["SumQuantity"](HEADERS, body)) == {
        "ndarray.any": 4,  # one look per column
        "ndarray.astype": 3,  # the date column twice on its way to days, the boolean column once
        "numpy.array": 1,  # the texts as an array, for the gather
        "ndarray.cumsum": 1,  # the text cells above each row
        "ndarray.sum": 3,  # text cells per row, text cells to the left, and the probe's own sum
        "ufunc.reduce": 7,
    }


# A bad cell deep in a column is found by that column's look and named without a walk, and
# the columns after it are never looked at.
def test_a_table_rejected_on_a_cell_names_it_after_one_look_at_its_column(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    rows: list[list[object]] = [[46276.0 + i, f"p{i}", float(i), i % 2 == 0] for i in range(N // 4)]
    rows[N // 8][2] = "x"
    body = Cells.from_rows(rows)
    PATH["SumQuantity"](HEADERS, body)
    assert call_profile(lambda: PATH["SumQuantity"](HEADERS, body)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text_row": 1,
        "_one_row": 1,
        "_shape": 1,
        "_texts": 1,
        "_mixed": 1,
        "MixedArray.shape": 1,
        "_refine": 1,
        "_bind": 1,
        "_refine.<locals>.<lambda>": 1,
        "_text_places": 1,
        "_dates_of": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_texts_of": 1,
        "_numbers_of": 1,  # the third column fails here, and the fourth is never reached
        "_bad_cell": 1,
        "_cell": 1,
        "describe": 1,
    }
    assert numpy_calls(lambda: PATH["SumQuantity"](HEADERS, body)) == {
        "ndarray.any": 3,
        "ndarray.argmax": 1,  # the first bad cell of the column
        "ndarray.ravel": 1,  # and its text, by counting the text codes before it
        "ndarray.astype": 2,
        "numpy.array": 1,
        "ndarray.cumsum": 1,
        "ndarray.sum": 2,
        "ufunc.reduce": 5,
    }


def test_a_column_out_copies_nothing(call_profile: CallProfile, numpy_calls: CallProfile) -> None:
    values = column()
    PATH["EchoColumn"](values)
    assert call_profile(lambda: PATH["EchoColumn"](values)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_numbers": 1,
        "EchoColumn": 1,
        "_column_out": 1,
        "_dimensions": 1,
        "_finite": 1,
    }
    # No look in, the summary settles it; one look out (all); ascontiguousarray hands back the
    # same array.
    assert numpy_calls(lambda: PATH["EchoColumn"](values)) == {
        "ndarray.all": 1,
        "ndarray.reshape": 1,
        "numpy.ascontiguousarray": 1,
        "ufunc.reduce": 1,
    }


def test_a_row_out_costs_what_a_column_out_costs(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    values = row()
    PATH["EchoRow"](values)
    assert call_profile(lambda: PATH["EchoRow"](values)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_row": 1,
        "_one_row": 1,
        "_shape": 1,
        "_numbers": 1,
        "EchoRow": 1,
        "_row_out": 1,
        "_dimensions": 1,
        "_finite": 1,
    }
    assert numpy_calls(lambda: PATH["EchoRow"](values)) == {
        "ndarray.all": 1,
        "ndarray.reshape": 1,
        "numpy.ascontiguousarray": 1,
        "ufunc.reduce": 1,
    }


def test_one_answer_per_row_itemized(call_profile: CallProfile, numpy_calls: CallProfile) -> None:
    values = grid()
    PATH["RowSums"](values)
    assert call_profile(lambda: PATH["RowSums"](values)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_numbers": 1,
        "RowSums": 1,
        "_column_out": 1,
        "_dimensions": 1,
        "_finite": 1,
    }
    assert numpy_calls(lambda: PATH["RowSums"](values)) == {
        "ndarray.sum": 1,
        "ndarray.all": 1,
        "ndarray.reshape": 1,
        "numpy.ascontiguousarray": 1,
        "ufunc.reduce": 2,
    }


def test_an_array_out_from_nothing_in_itemized(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    PATH["Grid"](5000, 2)
    assert call_profile(lambda: PATH["Grid"](5000, 2)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_whole": 2,
        "_number": 2,
        "Grid": 1,
        "_array_out": 1,
        "_dimensions": 1,
        "_finite": 1,
    }
    assert numpy_calls(lambda: PATH["Grid"](5000, 2)) == {
        "numpy.arange": 1,
        "ndarray.reshape": 1,
        "numpy.ascontiguousarray": 1,
        "ndarray.all": 1,
        "ufunc.reduce": 1,
    }


# --- handles: a creator publishes, a reader resolves, itemized --------------
# A creator is the call for its inputs with the library's builder and one publication on top;
# a reader is a text call with one lookup on top. The store is asked one question per call.

CURVE_HEADERS = Cells.from_rows([["date", "discount_factor"]])


def curve_body(rows: int) -> Cells:
    """A curve's table: one calendar day and its factor per row, from 11 September 2026."""
    return Cells.from_rows([[46276.0 + i, 1.0 - i * 1e-5] for i in range(rows)])


def test_a_valuation_date_is_two_scalars_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    PATH["_CreateValuationDate"](46276.0, 0.5)
    assert call_profile(lambda: PATH["_CreateValuationDate"](46276.0, 0.5)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_date": 1,  # the date, through the number rule it builds on, then its own two tests
        "_number": 2,
        "_CreateValuationDate": 1,
        "valuation_date": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateValuationDate"](46276.0, 0.5)) == {}


def anchor_body(anchors: int, days: int) -> Cells:
    """Anchors spread evenly over that many days from 11 September 2026, as the sheet sends them."""
    step = days // (anchors - 1)
    return Cells.from_rows([[46276.0 + i * step, 1.0 - i * step * 1e-5] for i in range(anchors)])


# A curve: the table path, the builder's own looks on the anchors, the days between them filled,
# and one publication. The same functions run and the same looks are taken whether the anchors
# are every day of ten years or a dozen over them: the work of filling is per day, inside one
# numpy call, and no ledger counts it.
CURVE_LEDGER = {
    "Registered.run": 1,
    "_arguments": 1,
    "_validate": 2,
    "_text_row": 1,
    "_one_row": 1,
    "_shape": 1,
    "_texts": 1,
    "_mixed": 1,
    "MixedArray.shape": 1,
    "_refine": 1,
    "_bind": 1,
    "_dates_of": 1,  # no column of text, so no text places are made
    "_not_dates": 1,
    "_as_days": 1,
    "_numbers_of": 1,
    "_CreateDiscountCurve": 1,
    "discount_curve": 1,
    "interpolate_discount_factors": 1,
    "_publish": 1,
}
CURVE_NUMPY = {
    "ndarray.any": 5,  # one look per column, then finite, rising and unordered, one look each
    "ndarray.astype": 3,  # the date column on its way to days, and the gaps between anchors
    "numpy.asarray": 2,  # the anchors' days read as they are, and the interpolation's own
    "numpy.arange": 2,  # the days from the first anchor to the last, and their offsets
    "ndarray.repeat": 1,  # the anchor each day runs to, which the line is held above
    "ndarray.setflags": 2,  # frozen
    "ufunc.reduce": 5,
}


def test_a_discount_curve_is_a_table_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    body = curve_body(3_631)
    PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)
    assert call_profile(lambda: PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)) == CURVE_LEDGER
    assert numpy_calls(lambda: PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)) == CURVE_NUMPY


def test_a_curve_from_a_dozen_anchors_runs_what_a_daily_table_runs(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    body = anchor_body(12, 3_630)
    PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)
    assert call_profile(lambda: PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)) == CURVE_LEDGER
    assert numpy_calls(lambda: PATH["_CreateDiscountCurve"](CURVE_HEADERS, body)) == CURVE_NUMPY


# The reader of any handle: the text rule and one lookup, the kind's table built a column at a
# time, dates to serials, and the mixed road out with its three looks.
def test_a_reader_is_a_text_call_one_lookup_and_a_table_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    handle = PATH["_CreateDiscountCurve"](CURVE_HEADERS, curve_body(3_631))
    PATH["util_ReadHandle"](handle)
    assert call_profile(lambda: PATH["util_ReadHandle"](handle)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve": 1,  # the handle: the text rule, then one dictionary lookup
        "_text": 1,
        "util_ReadHandle": 1,
        "discount_curve_table": 1,  # the kind's own table, reached by dispatch, not by a check
        "MixedArray.table": 1,
        "_table_column": 2,  # each array column checked before its copy: the dates, the factors
        "_unit": 1,
        "_serials": 1,
        "_mixed_out": 1,
        "_bad_mixed": 1,
    }
    assert numpy_calls(lambda: PATH["util_ReadHandle"](handle)) == {
        "numpy.empty": 2,  # the kinds, and the slots underneath numpy's full
        "numpy.asarray": 1,
        "numpy.datetime_data": 1,  # the unit of the date column
        "ndarray.any": 5,  # the serials' two checks, then the mixed road's three looks
        "numpy.ascontiguousarray": 2,
        "ufunc.reduce": 5,
    }


def test_a_dead_handle_is_refused_after_one_lookup(call_profile: CallProfile) -> None:
    dead = "discount_curve:000000:000001"
    assert call_profile(lambda: PATH["util_ReadHandle"](dead)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve": 1,
        "_text": 1,
    }


# --- the first index definition: three columns in, one publication out -----------------


def schedule_columns(contracts: int) -> tuple[Cells, Cells, Cells]:
    """Codes and two date columns for that many monthly contracts, as the sheet sends them."""
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    futures = Cells.from_rows([[46161.0 + 30 * i] for i in range(contracts)])
    options = Cells.from_rows([[46156.0 + 30 * i] for i in range(contracts)])
    return codes, futures, options


# Ten years of monthly contracts: the text column handed over as it is, one look and two
# conversions per date column, the builder's two copies, and one publication.
def test_an_expiry_schedule_is_three_columns_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, futures, options = schedule_columns(120)
    PATH["_CreateExpirySchedule"](codes, futures, options)
    assert call_profile(lambda: PATH["_CreateExpirySchedule"](codes, futures, options)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text_column": 1,
        "_date_column": 2,
        "_one_column": 3,
        "_shape": 3,
        "_texts": 1,
        "_dates": 2,
        "_not_dates": 2,
        "_as_days": 2,
        "_CreateExpirySchedule": 1,
        "expiry_schedule": 1,
        "_one_per_code": 2,  # the one rule, once per date column
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateExpirySchedule"](codes, futures, options)) == {
        "ndarray.any": 2,  # one look per date column, for the calendar
        "ndarray.astype": 4,  # each date column on its way to days
        "numpy.array": 2,  # the two copies the schedule keeps
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 2,
    }


# The third column left out: the stored default is handed over, and nothing runs for it.
def test_an_expiry_schedule_without_options_pays_for_two_columns(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, futures, _ = schedule_columns(120)
    PATH["_CreateExpirySchedule"](codes, futures, MISSING)
    assert call_profile(lambda: PATH["_CreateExpirySchedule"](codes, futures, MISSING)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text_column": 1,
        "_date_column": 1,
        "_one_column": 2,
        "_shape": 2,
        "_texts": 1,
        "_dates": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_CreateExpirySchedule": 1,
        "expiry_schedule": 1,
        "_one_per_code": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateExpirySchedule"](codes, futures, MISSING)) == {
        "ndarray.any": 1,
        "ndarray.astype": 2,
        "numpy.array": 1,
        "ndarray.setflags": 1,
        "ufunc.reduce": 1,
    }


# --- the second index definition: one column in, one publication out ------------------


def holiday_column(days: int) -> Cells:
    """That many holidays as the sheet sends them, one serial per row, a week apart."""
    return Cells.from_rows([[46023.0 + 7 * i] for i in range(days)])


# Ten years of one market's holidays: one look and two conversions for the column, the builder's
# one copy and one publication. The builder has no rule of its own, so nothing else runs.
def test_a_holiday_calendar_is_one_column_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    holidays = holiday_column(100)
    PATH["_CreateHolidayCalendar"](holidays)
    assert call_profile(lambda: PATH["_CreateHolidayCalendar"](holidays)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_date_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_dates": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_CreateHolidayCalendar": 1,
        "holiday_calendar": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateHolidayCalendar"](holidays)) == {
        "ndarray.any": 1,  # one look, for the calendar
        "ndarray.astype": 2,  # the column on its way to days
        "numpy.array": 1,  # the one copy the calendar keeps
        "ndarray.setflags": 1,  # frozen
        "ufunc.reduce": 1,
    }


# --- the third index definition: five texts in, one publication out ------------------


# Five scalars, each through the text rule, the builder and one publication: nothing is asked of
# numpy, and the builder has no rule of its own to run.
def test_index_conventions_are_five_texts_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes = ("USD", "BBL", "USD", "volume", "BBL")
    PATH["_CreateIndexConventions"](*codes)
    assert call_profile(lambda: PATH["_CreateIndexConventions"](*codes)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 5,
        "_text": 5,
        "_CreateIndexConventions": 1,
        "index_conventions": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateIndexConventions"](*codes)) == {}


# --- the fourth index definition: a table of contracts in, one publication out ----------


SPEC_HEADERS = Cells.from_rows(
    [["name", "lot_size", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
)


def spec_body(contracts: int) -> Cells:
    """That many contracts as the sheet sends them: a name, a whole lot size and two fees."""
    return Cells.from_rows([[f"contract {i}", 1000.0 + i, 3.0, 2.0] for i in range(contracts)])


# A dozen contracts at the table path: the header row as any row of text, the body admitted as
# a mixed range and bound, then each column through its rule, the names gathered and the three
# number columns as views, the builder's look at the lot sizes for a fraction, its three copies
# and one publication. Twenty-one calls across eighteen functions.
def test_contract_specs_are_a_table_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    body = spec_body(12)
    PATH["_CreateContractSpecs"](SPEC_HEADERS, body)
    assert call_profile(lambda: PATH["_CreateContractSpecs"](SPEC_HEADERS, body)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text_row": 1,
        "_one_row": 1,
        "_shape": 1,
        "_texts": 1,
        "_mixed": 1,
        "MixedArray.shape": 1,
        "_refine": 1,
        "_bind": 1,
        "_refine.<locals>.<lambda>": 1,  # the text places, made once on first use
        "_text_places": 1,
        "_texts_of": 1,
        "_numbers_of": 3,
        "_CreateContractSpecs": 1,
        "contract_specs": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateContractSpecs"](SPEC_HEADERS, body)) == {
        "ndarray.any": 5,  # one look per column, then the builder's, for a lot size with a fraction
        "numpy.array": 4,  # the names as an array for the gather, and the builder's three copies
        "ndarray.cumsum": 1,  # the text cells above each row
        "ndarray.sum": 2,  # text cells per row, and to the left
        "ndarray.setflags": 3,  # frozen
        "ufunc.reduce": 7,
    }


# cells_from_buffers is the real entry for a range: what the host's pinned buffers cost to own.
def host_buffers(text_cell: bool) -> tuple[int, int, str, int]:
    kinds = (ctypes.c_uint8 * N)(*([0] * (N - 1) + [1 if text_cell else 0]))
    numbers = (ctypes.c_double * N)(*[float(i) for i in range(N)])
    _keep.extend((kinds, numbers))
    seen = bridge.ONLY_NUMBERS | (bridge.ONLY_TEXT if text_cell else 0)
    return ctypes.addressof(kinds), ctypes.addressof(numbers), "x" if text_cell else "", seen


_keep: list[object] = []


@pytest.mark.parametrize("text_cell", [False, True], ids=["numbers", "one text cell"])
def test_cells_from_buffers_copies_each_buffer_once(
    text_cell: bool, call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    kinds, numbers, text, seen = host_buffers(text_cell)
    bridge.cells_from_buffers(kinds, numbers, N, 1, text, seen)
    assert call_profile(lambda: bridge.cells_from_buffers(kinds, numbers, N, 1, text, seen)) == {
        "cells_from_buffers": 1,
    }
    # Two views, two copies, and no look: the host's summary says whether there is text.
    assert numpy_calls(lambda: bridge.cells_from_buffers(kinds, numbers, N, 1, text, seen)) == {
        "numpy.frombuffer": 2,
        "ndarray.reshape": 2,
        "ndarray.copy": 2,
    }


# --- the first market data: two columns in, one publication out ----------------------------


def curve_columns(contracts: int) -> tuple[Cells, Cells]:
    """Codes and prices for that many contracts, as the sheet sends them."""
    codes = Cells.from_rows([[f"c{i}"] for i in range(contracts)])
    prices = Cells.from_rows([[70.0 + i / 100] for i in range(contracts)])
    return codes, prices


# Ten years of monthly contracts: the text column handed over as it is, after one pass over the
# tuple for an empty text, and the number column accepted on the host's summary alone, no look at
# the kinds of either, the builder's one copy and one publication: fifteen calls across twelve
# functions, the shape and kind rules once per column. What a welded table of the same two
# columns would add is in test_a_table_in_itemized: the header row, one look per column and the
# gathers.
def test_a_futures_curve_is_two_columns_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    codes, prices = curve_columns(120)
    PATH["_CreateFuturesCurve"](codes, prices)
    assert call_profile(lambda: PATH["_CreateFuturesCurve"](codes, prices)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text_column": 1,
        "_column": 1,
        "_one_column": 2,
        "_shape": 2,
        "_texts": 1,
        "_numbers": 1,
        "_CreateFuturesCurve": 1,
        "futures_curve": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateFuturesCurve"](codes, prices)) == {
        "numpy.array": 1,  # the one copy the curve keeps
        "ndarray.setflags": 1,  # frozen
    }


# --- the second market data: a table in, one publication out --------------------------------


FIXINGS_HEADERS = Cells.from_rows([["date", "settle"]])


def fixings_body(rows: int) -> Cells:
    """That many daily fixings as the sheet sends them, a serial and a settle per row."""
    return Cells.from_rows([[46143.0 + i, 100.0 + i % 7] for i in range(rows)])


# A year of fixings at the table path: the header row as any row of text, the body admitted as a
# mixed range and bound, one look per column, the date column converted to days, the builder's
# one look for the order of the dates and its two copies, and one publication. Nineteen calls
# across eighteen functions, the accept rule once per argument.
def test_daily_fixings_are_a_table_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    body = fixings_body(260)
    PATH["_CreateDailyFixings"](FIXINGS_HEADERS, body)
    assert call_profile(lambda: PATH["_CreateDailyFixings"](FIXINGS_HEADERS, body)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_text_row": 1,
        "_one_row": 1,
        "_shape": 1,
        "_texts": 1,
        "_mixed": 1,
        "MixedArray.shape": 1,
        "_refine": 1,
        "_bind": 1,
        "_dates_of": 1,  # no column of text, so no text places are made
        "_not_dates": 1,
        "_as_days": 1,
        "_numbers_of": 1,
        "_CreateDailyFixings": 1,
        "daily_fixings": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateDailyFixings"](FIXINGS_HEADERS, body)) == {
        "ndarray.any": 3,  # one look per column, then the builder's, for a date out of order
        "ndarray.astype": 2,  # the date column on its way to days
        "numpy.array": 2,  # the two copies the fixings keep
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 3,
    }


# --- the third market data: two columns in, the months kept as months -----------------------


def month_columns(count: int) -> tuple[Cells, Cells]:
    """That many months from January 2016 as the sheet sends them, the first day of each as a
    serial, and a price beside each."""
    firsts = [date(2016 + i // 12, 1 + i % 12, 1) for i in range(count)]
    months = Cells.from_rows([[float((first - date(1899, 12, 30)).days)] for first in firsts])
    return months, Cells.from_rows([[2.0 + i / 100] for i in range(count)])


# Ten years of months: the date column through its look and its conversion to days, the number
# column accepted on the host's summary alone, then the builder's two looks, the first day of
# each month and the order of the months, its months made from the days and its one copy of the
# prices, and one publication. Seventeen calls across fourteen functions.
def test_monthly_fixings_are_two_columns_in_and_months_kept(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    months, prices = month_columns(120)
    PATH["_CreateMonthlyFixings"](months, prices)
    assert call_profile(lambda: PATH["_CreateMonthlyFixings"](months, prices)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_date_column": 1,
        "_column": 1,
        "_one_column": 2,
        "_shape": 2,
        "_dates": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "_numbers": 1,
        "_CreateMonthlyFixings": 1,
        "monthly_fixings": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["_CreateMonthlyFixings"](months, prices)) == {
        "ndarray.any": 3,  # the column's look for the calendar, the first day, the order
        "ndarray.astype": 4,  # the column to days, to months, and back to days for the look
        "numpy.asarray": 1,  # the days read as they are
        "numpy.array": 1,  # the one copy, the prices; the months are the builder's own
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 3,
    }
