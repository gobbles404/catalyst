"""What one call through the seam costs, itemized: exact and deterministic."""

import ctypes
from collections.abc import Callable

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
    PATH["CreateValuationDate"](46276.0, 0.5)
    assert call_profile(lambda: PATH["CreateValuationDate"](46276.0, 0.5)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 2,
        "_date": 1,  # the date, through the whole-number and number rules it builds on
        "_whole": 1,
        "_number": 2,
        "CreateValuationDate": 1,
        "valuation_date": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["CreateValuationDate"](46276.0, 0.5)) == {}


# A ten-year curve: the table path, then the builder's own looks and the two copies it keeps.
def test_a_discount_curve_is_a_table_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    body = curve_body(3_631)
    PATH["CreateDiscountCurve"](CURVE_HEADERS, body)
    assert call_profile(lambda: PATH["CreateDiscountCurve"](CURVE_HEADERS, body)) == {
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
        "CreateDiscountCurve": 1,
        "discount_curve": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["CreateDiscountCurve"](CURVE_HEADERS, body)) == {
        "ndarray.any": 5,  # one look per column, then finite, rising and gapped, one look each
        "ndarray.astype": 2,  # the date column on its way to days
        "numpy.array": 2,  # the two copies the curve keeps
        "ndarray.setflags": 2,  # frozen
        "ufunc.reduce": 5,
    }


# The reader of any handle: the text rule and one lookup, the kind's table built a column at a
# time, dates to serials, and the mixed road out with its three looks.
def test_a_reader_is_a_text_call_one_lookup_and_a_table_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    handle = PATH["CreateDiscountCurve"](CURVE_HEADERS, curve_body(3_631))
    PATH["ReadHandle"](handle)
    assert call_profile(lambda: PATH["ReadHandle"](handle)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve": 1,  # the handle: the text rule, then one dictionary lookup
        "_text": 1,
        "ReadHandle": 1,
        "discount_curve_table": 1,  # the kind's own table, reached by dispatch, not by a check
        "MixedArray.table": 1,
        "_table_column": 2,  # each array column checked before its copy: the dates, the factors
        "_unit": 1,
        "_serials": 1,
        "_mixed_out": 1,
        "_bad_mixed": 1,
    }
    assert numpy_calls(lambda: PATH["ReadHandle"](handle)) == {
        "numpy.empty": 2,  # the kinds, and the slots underneath numpy's full
        "numpy.asarray": 1,
        "numpy.datetime_data": 1,  # the unit of the date column
        "ndarray.any": 5,  # the serials' two checks, then the mixed road's three looks
        "numpy.ascontiguousarray": 2,
        "ufunc.reduce": 5,
    }


def test_a_dead_handle_is_refused_after_one_lookup(call_profile: CallProfile) -> None:
    dead = "discount_curve:000000:000001"
    assert call_profile(lambda: PATH["ReadHandle"](dead)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_resolve": 1,
        "_text": 1,
    }


# --- the first market definition: three columns in, one publication out -----------------


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
    PATH["CreateExpirySchedule"](codes, futures, options)
    assert call_profile(lambda: PATH["CreateExpirySchedule"](codes, futures, options)) == {
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
        "CreateExpirySchedule": 1,
        "expiry_schedule": 1,
        "_one_per_code": 2,  # the one rule, once per date column
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["CreateExpirySchedule"](codes, futures, options)) == {
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
    PATH["CreateExpirySchedule"](codes, futures, MISSING)
    assert call_profile(lambda: PATH["CreateExpirySchedule"](codes, futures, MISSING)) == {
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
        "CreateExpirySchedule": 1,
        "expiry_schedule": 1,
        "_one_per_code": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["CreateExpirySchedule"](codes, futures, MISSING)) == {
        "ndarray.any": 1,
        "ndarray.astype": 2,
        "numpy.array": 1,
        "ndarray.setflags": 1,
        "ufunc.reduce": 1,
    }


# --- the second market definition: one column in, one publication out ------------------


def holiday_column(days: int) -> Cells:
    """That many holidays as the sheet sends them, one serial per row, a week apart."""
    return Cells.from_rows([[46023.0 + 7 * i] for i in range(days)])


# Ten years of one market's holidays: one look and two conversions for the column, the builder's
# one copy and one publication. The builder has no rule of its own, so nothing else runs.
def test_a_holiday_calendar_is_one_column_in_and_one_publication_out(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    holidays = holiday_column(100)
    PATH["CreateHolidayCalendar"](holidays)
    assert call_profile(lambda: PATH["CreateHolidayCalendar"](holidays)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 1,
        "_date_column": 1,
        "_one_column": 1,
        "_shape": 1,
        "_dates": 1,
        "_not_dates": 1,
        "_as_days": 1,
        "CreateHolidayCalendar": 1,
        "holiday_calendar": 1,
        "_publish": 1,
    }
    assert numpy_calls(lambda: PATH["CreateHolidayCalendar"](holidays)) == {
        "ndarray.any": 1,  # one look, for the calendar
        "ndarray.astype": 2,  # the column on its way to days
        "numpy.array": 1,  # the one copy the calendar keeps
        "ndarray.setflags": 1,  # frozen
        "ufunc.reduce": 1,
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
