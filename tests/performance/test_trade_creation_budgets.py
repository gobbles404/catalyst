"""What creating a batch costs, in the library and through the seam: the work resolution and
encoding report, which of the package's functions run and how many times, and which numpy C
calls cProfile sees, at five rows over two contracts and at two thousand over twenty-four. The
pins are the creator's work rules: the schedule's codes are read once each, however many rows;
each distinct contract code of the ticket is read once, through the period grammar, and the rows
holding it cost nothing more; the lag is read once per distinct text; and nothing else runs per
row, the components made in one pass of array arithmetic. The two ledgers differ in the counts
that follow the distinct codes alone, which the test says."""

from collections.abc import Callable

import numpy as np
import pytest
from numpy.typing import NDArray

from catalyst.excel import bridge
from catalyst.excel.bridge import Cells
from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.holiday_calendar import holiday_calendar
from catalyst.index_definitions.iferc_schedule import iferc_schedule
from catalyst.index_definitions.index import index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.instruments.fields import DatesOrTexts, FieldValues
from catalyst.trades.encoding import encoded
from catalyst.trades.resolution import resolved, trades
from catalyst.trades.schedule_methods import METHODS, ScheduleMethod
from catalyst.trades.template import TradeTemplate, trade_template
from catalyst.trades.terms import BASES, QuantityPer

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
SIZES = [(5, 2), (2_000, 24)]
IDS = ["five rows", "two thousand rows"]
PATH = {name: bridge.entry(name) for name, *_ in bridge.function_specs()}

# A financial index of 25 monthly contracts from October 2026, coded as the desk codes them, each
# expiring on the last business day on or before the 25th of its month, as the kernel budgets
# have it; a payment calendar of the same holidays.
MONTHS = np.arange("2026-10", "2028-11", dtype="datetime64[M]")
LETTERS = "FGHJKMNQUVXZ"
CODES = tuple(f"{LETTERS[int(m.astype(int)) % 12]}{str(m)[2:4]}" for m in MONTHS)
# The calendar days of each of the 25 months, October 2026 to October 2028, by hand, February
# 2028 the leap month among them: what a quantity per calendar day multiplies.
MONTH_DAYS_BY_HAND = np.array(
    [
        31,
        30,
        31,
        31,
        28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
        31,
        29,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
    ],
    dtype=np.int64,
)
HOLIDAYS = np.array(["2026-12-25", "2027-01-01", "2027-12-24"], dtype="datetime64[D]")
EXPIRIES = np.busday_offset(
    MONTHS.astype("datetime64[D]") + np.timedelta64(24, "D"), 0, roll="backward", holidays=HOLIDAYS
)
GAS = index(
    "gas",
    "Sample gas index",
    futures_schedule(CODES, EXPIRIES, None),
    index_conventions("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot",), np.array([10_000.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    holiday_calendar(HOLIDAYS),
    "lot",
    UNITS,
)
PAYMENT_CALENDAR = holiday_calendar(HOLIDAYS)
# The asian method's index: the same months, each contract expiring on its month's last business
# day, so that every pricing day of a month prices its own contract.
MONTH_ENDS = np.busday_offset(
    (MONTHS + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D"),
    0,
    roll="backward",
    holidays=HOLIDAYS,
)
ASIAN_GAS = index(
    "gas",
    "Sample gas index",
    futures_schedule(CODES, MONTH_ENDS, None),
    index_conventions("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot",), np.array([10_000.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    holiday_calendar(HOLIDAYS),
    "lot",
    UNITS,
)
TEMPLATE_FIELDS: dict[str, object] = {
    "quantity_unit": "lot",
    "quantity_per": "month",
    "settlement_frequency": "monthly",
    "nearby": 1.0,
    "schedule_method": "lastday",
    "route": "cleared",
    "settlement_method": "financial",
    "clearing_house": "TEST_CLEARER",
    "payment_day": "+2bd",
    "payment_holiday_calendar": PAYMENT_CALENDAR,
}


def one_row(fields: dict[str, object]) -> FieldValues:
    """A template's row as the seam hands it over, the payment day as its typed column."""
    columns: dict[str, object] = {
        name: _payment_day(value) if name == "payment_day" else (value,)
        for name, value in fields.items()
    }
    return FieldValues(FIXED_FLOAT, 1, tuple(fields), columns)


def _payment_day(value: object) -> DatesOrTexts:
    """A template's payment day as the seam types it: a text a rule, anything else a date."""
    if isinstance(value, str):
        return DatesOrTexts.of_texts((value,))
    return DatesOrTexts.of_dates(np.array([value], dtype="datetime64[D]"))


def a_template(method: str = "lastday", basis: str = "month") -> TradeTemplate:
    fields: dict[str, object] = {
        **TEMPLATE_FIELDS,
        "schedule_method": method,
        "quantity_per": basis,
        "settlement_frequency": "monthly",
        "nearby": 1.0,
    }
    return trade_template(one_row(fields))


def contract_rows(rows: int, contracts: int) -> NDArray[np.intp]:
    """The schedule row of each ticket row, spread over the first contracts after the boundary."""
    return 1 + np.arange(rows, dtype=np.intp) % contracts


def a_ticket(rows: int, contracts: int) -> FieldValues:
    """That many single-month rows, as the seam hands them over: dates, codes, lots and prices."""
    on = contract_rows(rows, contracts)
    return FieldValues(
        FIXED_FLOAT,
        rows,
        ("trade_date", "contract_code", "quantity", "fixed_price"),
        {
            "trade_date": np.repeat(np.datetime64("2026-09-24", "D"), rows),
            "contract_code": tuple(CODES[int(i)] for i in on),
            "quantity": np.where(np.arange(rows) % 3 == 0, -3.0, 2.0),
            "fixed_price": 3.0 + (np.arange(rows) % 7) / 100,
        },
    )


def test_a_dated_row_reads_no_rule_and_a_mixed_ticket_counts_its_rules_alone(
    call_profile: CallProfile,
) -> None:
    # Since payment-day-date-or-rule.md: a template dated after every row's last observation
    # reads no rule and shifts nothing, the ruled path never entered and the dated rows checked
    # once through the kernel's rule; a ticket mixing one rule with dates reads that rule once
    # and shifts once, over the ruled components alone.
    dated = trade_template(
        one_row({**TEMPLATE_FIELDS, "payment_day": np.datetime64("2028-12-15", "D")})
    )
    ticket = a_ticket(5, 2)
    counter = WorkCounter()
    resolved((GAS,), ticket, dated, counter)
    counts = counter.freeze().as_dict()
    assert (counts["payment_rules_read"], counts["payment_shifts"]) == (0, 0)
    profile = call_profile(lambda: resolved((GAS,), ticket, dated, WorkCounter()))
    assert "_the_ruled_days" not in profile and "shift_days" not in profile
    assert profile["payments_after_observations"] == 1
    ruled = trade_template(
        one_row({k: v for k, v in TEMPLATE_FIELDS.items() if k != "payment_day"})
    )
    mixed = FieldValues(
        FIXED_FLOAT,
        ticket.rows,
        (*ticket.names, "payment_day"),
        {
            **ticket.columns,
            "payment_day": DatesOrTexts(
                np.array([False, True, False, True, False]),
                np.array(["2028-12-15", "2028-12-15"], dtype="datetime64[D]"),
                ("+2bd",) * 3,
            ),
        },
    )
    counter = WorkCounter()
    resolved((GAS,), mixed, ruled, counter)
    counts = counter.freeze().as_dict()
    assert (counts["payment_rules_read"], counts["payment_shifts"]) == (1, 1)
    profile = call_profile(lambda: resolved((GAS,), mixed, ruled, WorkCounter()))
    assert (profile["_the_ruled_days"], profile["shift_days"]) == (1, 1)
    assert profile["payments_after_observations"] == 1


# --- the work the two children report -----------------------------------------------------------


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_creation_reports_its_rows_its_components_and_every_schedule_code(
    rows: int, contracts: int
) -> None:
    counter = WorkCounter()
    batch = trades((GAS,), a_ticket(rows, contracts), a_template(), UNITS, counter)
    assert batch.encoded.legs[0].group_contract.size == contracts
    assert counter.freeze().as_dict() == {
        "encoded_components": rows,
        "encoded_groups": contracts,  # one payment day per contract: one group each
        "encoded_observations": rows,
        "encoded_slots": contracts,
        "payment_rules_read": 1,  # since #181: one rule, applied once over one calendar
        "payment_shifts": 1,
        "reserved_fee_components": rows,  # clearing alone: cleared and unbrokered, since #188
        "resolved_components": rows,
        "resolved_occurrences": rows,
        "schedule_codes_read": 25,
        "ticket_codes_read": contracts,  # each distinct code of the rows, read once, since #172
    }


# --- the resolution's ledger ----------------------------------------------------------------------
# The same functions at both sizes, each once or a few times, but for four counts that follow the
# distinct contract codes of the ticket: each is read once through the period grammar, months_of,
# period_months and _label_months, and named once for its first row, _Fields.where, which the lag,
# the quantity unit and the four other batch fields are named for as well, the ticket's row or the
# template's name. The schedule's 25 codes are read once each, month_and_year, whatever the
# ticket holds. Nothing runs per row.


def resolution_ledger(distinct: int) -> dict[str, int]:
    return {
        "resolved": 1,
        "_fields": 1,
        "_the_required": 1,
        "_the_required.<locals>.<genexpr>": 2,  # a period field looked for, the code found first
        "_the_specification": 1,  # once per distinct unit, one here
        "_the_conditions": 1,
        "observed": 1,  # the methods' observations, made here so that payment counts from them
        "requires_whole_month": 1,  # the methods' two facts the observations read, once each
        "counts_back_from_expiry": 1,
        "_the_days": 1,  # one method present, its observations once
        "with_holiday_calendar": 1,  # the index's calendar typed once for the methods that read it
        "observations": 1,
        "last_days": 1,  # each component's last observation, the day its payment counts from
        "trade_schedule_of": 3,  # the resolution's, the observations' and then the kernel's
        "reporting_lot_of": 2,  # the resolution's and the kernel's: the nominal delta counts in
        "schedule_months": 1,
        "month_and_year": 25,
        "_the_periods": 1,  # each row's period chosen, since #172, and resolved to its components
        "resolve_periods": 1,  # the rows' periods by the one rule a request shares since
        # dated-quotes.md
        "resolve_periods.<locals>.<lambda>": distinct,  # each distinct code named for its first row
        "schedule_rows": 1,
        "_the_contracts": 1,  # each component's row, a month's by its month, a window's by its
        # first day, since the review of onetime-averaging.md's third slice
        "contract_days": 1,  # the days the schedule's contracts price on, a window's search key
        "month_bounds": 2,  # the first and last day of each component's month, and since
        # onetime-averaging.md the terms' calculation period of each component, that month
        "_each_distinct": 4,  # the units, the methods, the bases and the frequencies; the rules
        # below
        "_each_distinct.<locals>.<lambda>": 4,  # each distinct text named for its first row
        "_distinct_texts": 6,  # those four, since onetime-averaging.md the frequencies, and the
        # codes of the rows that book by code
        "months_of": distinct,
        "period_months": distinct,
        "_period_months": distinct,  # the reading under it, shared with the balance of a period
        "_label_months": distinct,
        "_Fields.where": distinct + 7,  # and once each for the lag and the six batch fields
        "payment_rule_of": 1,  # one distinct rule, read whole into its instructions, since #181
        "read_offset": 1,
        "shift_days": 1,  # the rule applied to its components on their one calendar at once
        "_business_days_on": 1,  # the one business-day instruction, one numpy offset
        "_the_payment_terms": 1,
        "_Fields.days_or_rules": 1,  # the payment days read once, dates or rules, since
        # payment-day-date-or-rule.md
        "DatesOrTexts.of_texts": 1,  # the template's one rule on every row
        "_the_ruled_days": 1,  # every row by a rule: the path as it was, over every component
        "_the_ruled_days.<locals>.<lambda>": 1,  # the distinct rule named for its first row
        "_the_ruled_days.<locals>.row_of": 2,  # the rule's first row, and its calendar's
        "schedule_method_of": 1,
        "route_of": 1,
        "settlement_of": 1,
        "quantity_per_of": 1,
        "settlement_frequency_of": 1,  # since onetime-averaging.md
        "frequency_rules": 2,  # the frequency's rules, since onetime-averaging.md, once by the
        # resolution ahead of the periods and once by the kernel, which owns them
        "_the_monthly_components": 1,  # each monthly component in one calendar month
        "choice": 5,
        "_Fields.one_text": 2,  # the route and the settlement, one each for the batch
        "_Fields.has": 24,  # the required fields, the nearby among them since
        # nearby-selection.md, the code the first period field found, and
        # since #175 the counterparty's condition and the marketing reserve looked for, since
        # slice 3 the key's condition and the key itself, since two-index-one-price.md the
        # second leg's one field and no second price, since cva-reserve.md the CVA reserve
        "_Fields.rows": 11,  # the template's nearby repeated over the rows, nearby-selection.md;
        # the rows asked once less: the periods count their own since
        # dated-quotes.md, a request's rows resolving through the same rule
        "_Fields.texts": 5,  # the four row fields' columns read once each, the codes apart
        # and the payment day, read through days_or_rules
        "_Fields.period_texts": 1,  # the codes, with which rows supplied one, since #172
        "_Fields.period_dates": 2,  # the two dates, none supplied by this ticket
        "_Fields.labels": 3,  # clearing_house, counterparty and broker; the IDs are read by ids
        "_Fields.keys": 1,  # the curve keys, since named-curves-slice-3.md, none on a cleared route
        "_Fields.amounts": 2,  # the marketing reserve since #175 and the CVA reserve since
        # cva-reserve.md, each None when neither supplies it
        "_Fields.ids": 1,  # the trade IDs, whole numbers since #168, none in this ticket
        "_Fields.nearbys": 1,  # each row's nearby, the template's one, nearby-selection.md
        "_the_nearbys": 1,  # one per occurrence and 1 or more
        "nearby_rules": 1,  # a later nearby under asian on one futures index alone
        "_Fields.numbers": 2,
        "_Fields.dates": 1,
        "_Fields.objects": 1,
        "FieldValues.has": 16,
        "FieldValues.supplied_rows": 1,  # which rows hold a code: every one, the column full
        "FieldValues.texts": 1,
        "FieldValues.numbers": 2,
        "FieldValues.dates": 1,
        "resolved_trades": 1,
        "_the_leg_fields": 1,  # two-index-fixed-float.md: the second leg's field, its method
        "_owner": 1,  # the words naming an index's specifications and schedule in a refusal
        "_schedule_of": 1,
        "_the_payments": 1,  # the payment anchors, the later of the legs' last observations
        "_the_leg": 1,  # the leg's columns copied and frozen
        "_the_leg_selections": 1,  # the leg's specification rows and methods, then the basis
        "_the_choices": 2,
        "_the_contract_column": 1,  # the leg's contract rows, each a row of its schedule
        "_the_component_column": 2,  # the contract column and the price column, one per component
        "_the_prices": 1,  # two-index-one-price.md: the trade's one price column, finite
        # float-float-spread.md: the price's field by its instrument, read once by the
        # resolution, to read the column, and once by the kernel, to name it
        "price_words": 2,
        # float-float-units.md: a price's unit present exactly on a float_float, none here
        "spread_unit": 1,
        "_the_keys": 1,  # the keys present exactly on the bilateral route, since slice 3
        "_the_selections": 1,  # each occurrence's unit, method, basis and frequency in range
        "_the_method": 1,
        # expired-physical-cash.md: the one house a physical batch names; a financial batch's
        # settlement looked at and nothing more
        "_the_clearing_house": 1,
        "_the_occurrences": 1,
        "_the_brokered": 1,  # which rows name a broker, since #188
        "_the_components": 1,
        "whole_quantities": 1,
        "finite_prices": 1,
        "_the_payment": 1,
        "_frozen_days": 4,  # the trade dates, the payment days, the starts and the ends
        "_frozen_rows": 7,  # the occurrence, the contract, the four selections and the nearby
        "_frozen_numbers": 2,
        "_the_component_quantity": 1,  # each component's quantity by the basis
        "_the_calculation_periods": 1,  # each component's period, since onetime-averaging.md
        "WorkCounter.__init__": 1,
        "WorkCounter.hit": 6,  # the rows, the components, the schedule's codes and the ticket's,
        # and since #181 the rules read and the shifts applied
    }


# The resolution's numpy, the same at both sizes but for the two months of each distinct code: the
# periods' arithmetic, each component's month to its first and its last day, the observations'
# builder, which checks the order and the weights, counts twice and copies and freezes three
# columns, the payment offset and the kernel's frozen copies, the days each component covers
# counted off its two dates, the end held on or after the start and both in one month;
# the quantity rule is one look, whole or not, since zero is a count, zero-quantities.md; and the
# payment days are one look against the sheet's last day, 31 December 9999, since a later day
# could reach no cell; and the distinct codes and the distinct lags are each sorted once by their
# first rows, so that a refusal names the first bad row and not the first bad spelling. Since #172
# each row chooses its period: three looks over the rows, half a pair or no period, an end before
# its start among the dated rows and whether any component is a dated row's; four counts, each
# row's place among the rows that supplied a start, an end, a code and both dates; the dated and
# the coded rows found once each; the two months of the dated rows' dates, four conversions of
# an empty array here; and the mask of the rows that entered a code copied and frozen. The
# expiry-based methods' whole-month look is each method's own, not here, so that the asian
# method, which takes a part of a month, spreads this dict without it.
def resolution_numpy(contracts: int) -> dict[str, int]:
    return {
        "generic.astype": 2 * contracts,  # each distinct code's two months as counts
        "ndarray.all": 1,
        "ndarray.any": 34,  # three the selections in range, two the methods present, since
        # onetime-averaging.md six the frequency rules', two by the resolution ahead of the
        # periods and two by the kernel that owns them, one whether any component is a window
        # and one again for its period, one
        # whether any row entered a date for its payment day, since payment-day-date-or-rule.md,
        # one the
        # payment instruction's look at the sheet's calendar, since #181, one the
        # basis, two each component's end on or after its start and in one month, three the
        # periods' since #172, and since nearby-selection.md two the nearbys', each 1 or more and
        # whether any is a later one
        "ndarray.argsort": 15,  # two per distinct read, the texts and their first rows, five reads,
        # and the rule-and-calendar groups' unique, since #181
        "ndarray.astype": 24,  # the month bounds four, the one-month look two, the days one, the
        # calculation periods' six since onetime-averaging.md, the
        # three row fields' positions among their distinct texts, the dated rows' months four
        "ndarray.clip": 1,
        "ndarray.cumsum": 13,  # one per distinct read within numpy's unique, five, two more, the
        # rule-and-calendar groups' since #181, and
        # the four ranks of the rows since #172
        "ndarray.flatten": 9,  # one per unique, the five reads and the methods present, one more,
        # and the rule-and-calendar groups' since #181
        "ndarray.max": 1,
        "ndarray.min": 1,
        "ndarray.nonzero": 4,  # the first look at the missing months, the components of each
        # method, the dated rows and the coded rows
        "ndarray.ravel": 4,
        "ndarray.repeat": 1,
        "ndarray.reshape": 9,  # one more within the groups' unique, since #181
        "ndarray.round": 1,
        "ndarray.searchsorted": 1,  # each component's last observation, its payment's anchor
        "ndarray.setflags": 22,  # the kernel's thirteen copies, the nearbys' among them since
        # nearby-selection.md, the two period bounds since
        # onetime-averaging.md, the three selections among them, the
        # schedule's months since #186,
        # rule kept as text since #181 and frozen by no one,
        # the observations' three, the rows that entered a code
        "ndarray.sort": 1,  # the methods present, numpy's unique over the components' codes
        "numpy._unique_hash": 1,  # numpy's own look within that unique
        "numpy.array": 29,  # the four distinct reads' texts and three of their values, the rules
        # and the terms' copy of the schedule's months since #186,
        # kept as text since #181, the coded rows' texts
        # and their spans, the three selections copied into the kernel's record, two of them the
        # dates copied, the mask of the rows that entered a code, and the nearbys copied into the
        # kernel's record, nearby-selection.md
        "numpy.asanyarray": 23,  # two more within the groups' unique, since #181
        "numpy.asarray": 1,  # the stray days' NaT fill, read for its type, since #181
        "numpy.arange": 4,  # one of them the components counted off for the anchor search; the
        # lastday days take their components from the methods' positions, not a count
        "numpy.empty": 31,  # among them each row's first month and the month after its last, the
        # two dates' empty values, and since #181 the payment days, the stray instruction and the
        # stray day of the shift and of the resolution, the groups' unique, and the template's
        # nearby repeated over the rows, nearby-selection.md
        "numpy.fromiter": 1,
        "numpy.normalize_axis_index": 1,
        "numpy.zeros": 4,  # the two dates supplied by no row; since #188 the rows of no broker;
        # the template's rule on every row, no row dated, since payment-day-date-or-rule.md
        "ufunc.reduce": 37,  # one per look
    }


# The expiry-based methods take a component that covers its whole month and look once that each
# does, two conversions of its month and one look; the asian method, which takes a part of a
# month, has no such look.
WHOLE_MONTHS = {"_whole_months": 1}
WHOLE_MONTHS_NUMPY = {"ndarray.any": 35, "ndarray.astype": 27, "ufunc.reduce": 38}


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_resolution_reads_each_distinct_code_once_and_nothing_per_row(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    ticket, template = a_ticket(rows, contracts), a_template()
    assert call_profile(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **resolution_ledger(contracts),
        **WHOLE_MONTHS,
    }
    assert numpy_calls(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **resolution_numpy(contracts),
        **WHOLE_MONTHS_NUMPY,
    }


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_the_penultimate_method_adds_one_look_at_the_expiries_and_nothing_per_row(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    # The pen's observations read the index's holiday calendar once and ask once whether every
    # expiry is open; the step back and the payment offset are numpy's business-day functions,
    # dispatched in C and unseen. The counts the batch reports are lastday's.
    ticket, template = a_ticket(rows, contracts), a_template("penultimate")
    counter = WorkCounter()
    terms, (observations,), _ = resolved((GAS,), ticket, template, counter)
    assert terms.payment is not None
    np.testing.assert_array_equal(
        observations.date, np.busday_offset(EXPIRIES[terms.legs[0].contract], -1, holidays=HOLIDAYS)
    )
    np.testing.assert_array_equal(
        terms.payment.date, np.busday_offset(observations.date, 2, holidays=HOLIDAYS)
    )
    assert counter.freeze().as_dict() == {
        "payment_rules_read": 1,  # since #181: one rule, applied once over one calendar
        "payment_shifts": 1,
        "resolved_components": rows,
        "resolved_occurrences": rows,
        "schedule_codes_read": 25,
        "ticket_codes_read": contracts,  # each distinct code of the rows, read once, since #172
    }
    assert call_profile(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **resolution_ledger(contracts),
        **WHOLE_MONTHS,
        "_with_expiries_priced": 1,
        "with_holiday_calendar": 1,
        "open_days": 1,
    }
    assert numpy_calls(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **resolution_numpy(contracts),
        **WHOLE_MONTHS_NUMPY,
        "ndarray.any": 36,  # and whether any expiry is closed
        "ufunc.reduce": 39,
    }


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_the_last3day_method_gives_three_days_per_component_and_one_payment_after_the_last(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    # Three observations per component, the expiry and the two business days before it, a third
    # each: the same one look at the expiries as the pen's, one business-day offset over the
    # components and the three offsets at once, and the payment counted from the last of each
    # component's days, the expiry, so the payment days are lastday's. Nothing runs per row, and
    # the counts the batch reports are the components', not the observations'.
    ticket, template = a_ticket(rows, contracts), a_template("last3day")
    counter = WorkCounter()
    terms, (observations,), _ = resolved((GAS,), ticket, template, counter)
    assert terms.payment is not None
    expiries = EXPIRIES[terms.legs[0].contract]
    np.testing.assert_array_equal(
        observations.date,
        np.busday_offset(expiries[:, None], [[-2, -1, 0]], holidays=HOLIDAYS).ravel(),
    )
    np.testing.assert_array_equal(observations.component, np.repeat(np.arange(rows), 3))
    np.testing.assert_allclose(observations.weight, np.full(3 * rows, 1 / 3))
    np.testing.assert_array_equal(
        terms.payment.date, np.busday_offset(expiries, 2, holidays=HOLIDAYS)
    )
    assert counter.freeze().as_dict() == {
        "payment_rules_read": 1,  # since #181: one rule, applied once over one calendar
        "payment_shifts": 1,
        "resolved_components": rows,
        "resolved_occurrences": rows,
        "schedule_codes_read": 25,
        "ticket_codes_read": contracts,  # each distinct code of the rows, read once, since #172
    }
    assert call_profile(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **resolution_ledger(contracts),
        **WHOLE_MONTHS,
        "_with_expiries_priced": 1,
        "with_holiday_calendar": 1,
        "open_days": 1,
    }
    assert numpy_calls(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **resolution_numpy(contracts),
        **WHOLE_MONTHS_NUMPY,
        "ndarray.any": 36,  # and whether any expiry is closed
        "ndarray.repeat": 2,  # each component three times, for its three observations
        "ndarray.ravel": 5,  # the three days of each component laid out in one column
        "numpy.asarray": 2,  # the three offsets as an array for the offset, and the NaT fill
        "ufunc.reduce": 39,
    }


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_the_asian_method_gives_a_month_of_days_per_component_and_one_payment_after_the_last(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    # Every pricing day of each component's calendar month, an equal share each, on an index
    # whose contracts expire at their month's end: the holiday calendar read once, one count of
    # the days over the components from the days each covers, which the periods gave as dates
    # already, and one offset over the observations, in C and unseen but for the arrays they take
    # and give; the payment counted from the month's last pricing day. Nothing runs per row, and
    # the counts the batch reports are the components'.
    ticket, template = a_ticket(rows, contracts), a_template("asian")
    counter = WorkCounter()
    terms, (observations,), _ = resolved((ASIAN_GAS,), ticket, template, counter)
    assert terms.payment is not None
    months: NDArray[np.datetime64] = MONTHS[terms.legs[0].contract]
    firsts: NDArray[np.datetime64] = months.astype("datetime64[D]")
    afters: NDArray[np.datetime64] = (months + np.timedelta64(1, "M")).astype("datetime64[D]")
    days: NDArray[np.int64] = np.busday_count(firsts, afters, holidays=HOLIDAYS)
    np.testing.assert_array_equal(observations.component, np.repeat(np.arange(rows), days))
    np.testing.assert_allclose(observations.weight, np.repeat(1.0 / days, days))
    # Each component's days counted off its month's first day, one component at a time: the
    # fixture's own arithmetic, not the builder's one offset over every observation.
    by_component: list[NDArray[np.datetime64]] = [
        np.busday_offset(firsts[k], np.arange(int(days[k])), roll="forward", holidays=HOLIDAYS)
        for k in range(rows)
    ]
    np.testing.assert_array_equal(observations.date, np.concatenate(by_component))
    np.testing.assert_array_equal(
        terms.payment.date,
        np.busday_offset(MONTH_ENDS[terms.legs[0].contract], 2, holidays=HOLIDAYS),
    )
    assert counter.freeze().as_dict() == {
        "payment_rules_read": 1,  # since #181: one rule, applied once over one calendar
        "payment_shifts": 1,
        "resolved_components": rows,
        "resolved_occurrences": rows,
        "schedule_codes_read": 25,
        "ticket_codes_read": contracts,  # each distinct code of the rows, read once, since #172
    }
    assert call_profile(lambda: resolved((ASIAN_GAS,), ticket, template, WorkCounter())) == {
        **resolution_ledger(contracts),
        "with_holiday_calendar": 1,
    }
    assert numpy_calls(lambda: resolved((ASIAN_GAS,), ticket, template, WorkCounter())) == {
        **resolution_numpy(contracts),
        "ndarray.any": 35,  # whether any component has no pricing day
        "ndarray.cumsum": 14,  # where each component's observations start
        "ndarray.repeat": 5,  # the components, their starts, their first days and their weights
        "ndarray.sum": 1,  # how many observations in all
        "numpy.arange": 5,  # the place of each observation within its component
        "numpy.empty": 30,  # one fewer: no array of ones for the weights
        "ufunc.reduce": 39,
    }


# --- through the seam ---------------------------------------------------------------------------
# _CreateTrades: the four arguments alone, the two handles resolved, the ticket bound against the
# template's instrument with one look per column, then the library's two children and one
# publication; the same at five rows and at 2,500 but for the distinct-code counts above.

SERIAL = np.datetime64("1899-12-30", "D")


def serial(day: np.datetime64) -> float:
    return float((day - SERIAL).astype(np.int64))


@pytest.fixture(scope="module")
def sheet() -> dict[str, object]:
    schedule = PATH["_CreateFuturesSchedule"](
        Cells.from_rows([[code] for code in CODES]),
        Cells.from_rows([[serial(day)] for day in EXPIRIES]),
        bridge.MISSING,
    )
    holidays = PATH["_CreateHolidayCalendar"](Cells.from_rows([[serial(day)] for day in HOLIDAYS]))
    conventions = PATH["_CreateIndexConventions"]("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU")
    specifications = PATH["_CreateContractSpecifications"](
        Cells.from_rows(
            [["name", "lot_size", "lot_unit", "brokerage_rate_per_lot", "clearing_rate_per_lot"]]
        ),
        Cells.from_rows([["lot", 10000.0, "MMBTU", 0.0, 0.0]]),
    )
    values = [
        holidays if name == "payment_holiday_calendar" else value
        for name, value in TEMPLATE_FIELDS.items()
    ]
    return {
        "index": PATH["_CreateIndex"](
            "gas", "Sample gas index", schedule, conventions, specifications, holidays, "lot"
        ),
        "template": PATH["_CreateTradeTemplate"](
            "fixed_float", Cells.from_rows([list(TEMPLATE_FIELDS)]), Cells.from_rows([values])
        ),
        "headers": Cells.from_rows([["trade_date", "contract_code", "quantity", "fixed_price"]]),
    }


def a_body(rows: int, contracts: int) -> Cells:
    on = contract_rows(rows, contracts)
    return Cells.from_rows(
        [
            [46289.0, CODES[int(on[i])], -3.0 if i % 3 == 0 else 2.0, 3.0 + (i % 7) / 100]
            for i in range(rows)
        ]
    )


@pytest.mark.parametrize(
    ("rows", "contracts"), [(5, 2), (2_500, 24)], ids=["five rows", "2,500 rows"]
)
def test_the_creator_binds_once_per_column_resolves_once_and_publishes_once(
    call_profile: CallProfile, sheet: dict[str, object], rows: int, contracts: int
) -> None:
    body = a_body(rows, contracts)

    def call() -> object:
        return PATH["_CreateTrades"](sheet["index"], sheet["headers"], body, sheet["template"])

    assert str(call()).split(":")[1:3] == ["trades", "gas"]
    seam = {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,
        "_resolve_each": 1,  # the index cell, one object
        "_text": 2,  # the two handles' texts
        "_resolve": 2,  # the index and the template, one lookup each
        "_text_row": 1,
        "_texts": 1,
        "_shape": 1,
        "_field_rows": 1,  # the body as it arrived, since #172, for the binding to read
        "_field_cells": 1,
        "by_template": 1,  # the template selects the instrument
        "_bind_fields": 1,
        "_field_body": 1,  # the cells placed among the texts once
        "_unsupplied": 1,  # the code column's cells that supplied nothing, none here
        "_field_dates": 1,
        "_as_days": 1,
        "_not_dates": 1,
        "_field_texts": 1,
        "_field_numbers": 2,
        "_one_row": 1,
        "_CreateTrades": 1,
        "trades": 1,
        "encoded": 1,
        "_the_groups": 1,
        "_the_amounts": 1,  # two-index-fixed-float.md: the leg's two amounts per component
        # float-float-units.md: the selected specifications' sizes in the quote unit, the
        # conversions the amounts made inline before, one factor per distinct selection still
        "_the_sizes": 1,
        "_the_price_leg": 1,  # the trade's own side, once: a fixed leg, or a spread leg
        "_the_group_offsets": 1,  # the trade's own sides by group
        "_the_exposures": 1,  # the leg's slots' exposures
        "_distinct": 2,  # the groups by period and day, the slots by group, day and contract
        "_the_references": 1,
        "observation_references": 1,  # the reader shared with a quote, template-based-quoting.md
        "requires_booked_reference": 1,  # the methods' fact the references read, once
        "with_holiday_calendar": 2,  # the observations' and the encoding's
        "open_days": 1,
        "contract_on": 1,
        "_the_slots": 1,
        "_the_day_axis": 1,  # the day axis, since #166
        "_the_contract_periods": 1,  # the contract month and year axes, since #186
        "UnitConversions.factor": 2,
        "UnitConversions.category": 2,
        "_payments_after_observations": 1,
        "onetime_components": 1,  # the groups keyed by the frequency beside the period
        "payments_after_observations": 1,  # the kernel's rule, one owner since
        # payment-day-date-or-rule.md
        "reserves": 1,  # the booked brokerage and clearing, once over the components, since #170
        "_charged": 1,  # clearing, the one fee a cleared, unbrokered template charges, since #188
        "_summed_once": 2,  # the marketing and the CVA reserve, none here, since cva-reserve.md
        "ResolvedTrades.descriptor": 1,  # the handle's name, the legs' index names joined,
        # since two-index-fixed-float.md
        "_publish": 1,
    }
    expected = {**resolution_ledger(contracts), **WHOLE_MONTHS, **seam, "WorkCounter.hit": 11}
    assert call_profile(call) == expected


def test_the_template_creator_reads_each_value_once_and_publishes_once(
    call_profile: CallProfile, sheet: dict[str, object]
) -> None:
    holidays = PATH["_CreateHolidayCalendar"](Cells.from_rows([[46352.0]]))
    headers = Cells.from_rows([list(TEMPLATE_FIELDS)])
    values = Cells.from_rows(
        [
            [
                holidays if name == "payment_holiday_calendar" else value
                for name, value in TEMPLATE_FIELDS.items()
            ]
        ]
    )

    def call() -> object:
        return PATH["_CreateTradeTemplate"]("fixed_float", headers, values)

    assert str(call()).split(":")[1] == "trade_template"
    assert call_profile(call) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 3,
        "_text": 2,  # the name, and the handle cell's text
        "_text_row": 1,
        "_texts": 1,
        "_shape": 2,  # the headers' row and, since the shape comes first, the values'
        "_one_row": 1,
        "_field_row": 1,  # one row, the template's shape before its cells, then the cells as they
        "_field_cells": 1,  # arrived, since #172, for the binding
        "by_name": 1,
        "instrument": 1,
        "_bind_fields": 1,
        "_field_body": 1,  # the cells placed among the texts once
        "_field_texts": 7,  # seven text and code columns
        "_field_dates_or_texts": 1,  # the payment day, a date or a text, since
        # payment-day-date-or-rule.md: its two looks
        "_not_dates": 1,
        "_as_days": 1,
        "_field_numbers": 1,  # the nearby, the template's one number, nearby-selection.md
        "_field_handles": 1,
        "_resolve": 1,  # the one handle cell
        "_CreateTradeTemplate": 1,
        "trade_template": 1,
        "_holds": 10,  # whether the row supplied each field's value, since #172
        "field_value": 10,  # one per field, the nearby the tenth
        "FieldValues.field": 10,
        "FieldValues.field.<locals>.<genexpr>": 20,
        "FieldValues.texts": 7,
        "FieldValues.numbers": 1,
        "nearby_of": 1,  # the nearby read for its rule when the template is made
        "whole_nearbys": 1,
        "FieldValues.dates_or_texts": 1,
        "FieldValues.objects": 1,
        "route_of": 1,
        "settlement_of": 1,
        "schedule_method_of": 1,
        "quantity_per_of": 1,
        "settlement_frequency_of": 1,  # since onetime-averaging.md
        "choice": 5,
        "payment_rule_of": 1,  # the rule read whole, since #181
        "read_offset": 1,
        "_publish": 1,
    }


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_the_calday_basis_counts_the_days_once_over_the_schedule_and_multiplies_once(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    # The entered quantity times the calendar days of each component's month: the days counted
    # once over the schedule's 25 months and gathered per component, under either basis, and
    # under calday one look that no product would outrun the largest number, one multiplication
    # over the components and the product frozen; the same functions as under month, nothing per
    # row.
    ticket, template = a_ticket(rows, contracts), a_template(basis="calday")
    terms, _, _ = resolved((GAS,), ticket, template, WorkCounter())
    days = MONTH_DAYS_BY_HAND[terms.legs[0].contract]
    np.testing.assert_array_equal(terms.covered_days, days)
    np.testing.assert_array_equal(terms.component_quantity, terms.quantity * days)
    assert (terms.quantity_per == BASES.index(QuantityPer.CALDAY)).all()
    assert call_profile(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **resolution_ledger(contracts),
        **WHOLE_MONTHS,
    }
    assert numpy_calls(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **resolution_numpy(contracts),
        **WHOLE_MONTHS_NUMPY,
        "ndarray.any": 36,  # and whether any product would outrun the largest number
        "ndarray.setflags": 23,  # the product frozen, the brokered rows since #188, the periods
        "numpy._make_extobj": 1,  # the error state set once, the overflow this rule's to catch
        "ufunc.reduce": 39,
    }


# --- a ticket of dates --------------------------------------------------------------------------
# trade-periods-and-bal.md, slice C: start_date and end_date in place of a contract code. The same
# functions as the codes take but the grammar's, nothing read per distinct text, the two date
# columns read once each and the end held on or after the start in one look, the months of the
# dates four conversions; the components, their days and their payment days the codes' own when
# the dates are whole months, and under asian a part of each month observed on its own days.


def a_dated_ticket(rows: int, contracts: int, from_day: int = 0) -> FieldValues:
    """The same rows booked by dates: each component's month from its first day, or the day that
    many days after it, to its last."""
    on = contract_rows(rows, contracts)
    first = MONTHS[on].astype("datetime64[D]") + np.timedelta64(from_day, "D")
    last = (MONTHS[on] + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D")
    return FieldValues(
        FIXED_FLOAT,
        rows,
        ("trade_date", "start_date", "end_date", "quantity", "fixed_price"),
        {
            "trade_date": np.repeat(np.datetime64("2026-09-24", "D"), rows),
            "start_date": first,
            "end_date": last,
            "quantity": np.where(np.arange(rows) % 3 == 0, -3.0, 2.0),
            "fixed_price": 3.0 + (np.arange(rows) % 7) / 100,
        },
    )


def dated_ledger(contracts: int) -> dict[str, int]:
    """The code path's functions but the grammar's: no reading per distinct text, the lags' one
    distinct read, the three date columns read once each."""
    ledger = resolution_ledger(contracts)
    for name in (
        "months_of",
        "period_months",
        "_period_months",
        "_label_months",
        "FieldValues.texts",
    ):
        del ledger[name]
    del ledger["resolve_periods.<locals>.<lambda>"]  # no code of any row named: none is read
    return {
        **ledger,
        "_Fields.where": 7,  # the lag and the six batch fields, no code named
        "_Fields.has": 25,  # the three period fields looked for, the two dates found; the
        # second leg's one field since two-index-one-price.md, the CVA reserve since
        # cva-reserve.md
        "_the_required.<locals>.<genexpr>": 3,
        "_Fields.rows": 10,  # one less since dated-quotes.md, the periods counting their own rows
        "_Fields.dates": 1,  # the trade dates; the two dates come through the periods' own read
        "FieldValues.has": 17,
        "FieldValues.dates": 3,
        "FieldValues.supplied_rows": 2,  # which rows hold a start and an end: every one
    }


def dated_numpy(contracts: int) -> dict[str, int]:
    """The code path's numpy but the distinct codes' conversions: the dates' months four
    conversions of full arrays in place of empty ones, the coded rows' texts an empty read, and
    one mask of zeros for the code no row entered in place of the dates' two."""
    numpy = resolution_numpy(contracts)
    del numpy["generic.astype"]
    return {
        **numpy,
        "numpy.empty": 30,  # the codes' empty values, no dates' empty values
        "numpy.zeros": 3,  # the rows of no broker since #188
    }


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_a_ticket_of_dates_resolves_as_its_codes_would_through_the_same_functions_but_the_grammars(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    ticket, template = a_dated_ticket(rows, contracts), a_template()
    terms, (observations,), _ = resolved((GAS,), ticket, template, WorkCounter())
    by_code, (by_code_observations,), _ = resolved(
        (GAS,), a_ticket(rows, contracts), template, WorkCounter()
    )
    for mine, theirs in (
        (terms.legs[0].contract, by_code.legs[0].contract),
        (terms.start_date, by_code.start_date),
        (terms.end_date, by_code.end_date),
        (terms.covered_days, by_code.covered_days),
        (observations.date, by_code_observations.date),
    ):
        np.testing.assert_array_equal(mine, theirs)
    assert terms.payment is not None and by_code.payment is not None
    np.testing.assert_array_equal(terms.payment.date, by_code.payment.date)
    assert call_profile(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **dated_ledger(contracts),
        **WHOLE_MONTHS,
    }
    assert numpy_calls(lambda: resolved((GAS,), ticket, template, WorkCounter())) == {
        **dated_numpy(contracts),
        **WHOLE_MONTHS_NUMPY,
    }


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_a_part_of_each_month_under_asian_observes_its_own_days_and_nothing_per_row(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    # Each component from the eleventh of its month to the last: ten days fewer covered than the
    # month, its pricing days counted from its own start, the same functions as the whole months'
    # with the holiday calendar read once and no whole-month look.
    ticket, template = a_dated_ticket(rows, contracts, 10), a_template("asian")
    terms, (observations,), _ = resolved((ASIAN_GAS,), ticket, template, WorkCounter())
    np.testing.assert_array_equal(
        terms.covered_days, MONTH_DAYS_BY_HAND[terms.legs[0].contract] - 10
    )
    days: NDArray[np.int64] = np.busday_count(
        terms.start_date, terms.end_date + np.timedelta64(1, "D"), holidays=HOLIDAYS
    )
    np.testing.assert_array_equal(observations.component, np.repeat(np.arange(rows), days))
    assert bool((observations.date >= terms.start_date[observations.component]).all())
    assert call_profile(lambda: resolved((ASIAN_GAS,), ticket, template, WorkCounter())) == {
        **dated_ledger(contracts),
        "with_holiday_calendar": 1,
    }
    assert numpy_calls(lambda: resolved((ASIAN_GAS,), ticket, template, WorkCounter())) == {
        **dated_numpy(contracts),
        "ndarray.any": 35,  # and whether any component has no pricing day
        "ndarray.cumsum": 14,  # where each component's observations start
        "ndarray.repeat": 5,  # the components, their starts, their first days and their weights
        "ndarray.sum": 1,  # how many observations in all
        "numpy.arange": 5,  # the place of each observation within its component
        "numpy.empty": 29,  # no array of ones for the weights
        "ufunc.reduce": 39,
    }


# --- a onetime window across a month end, onetime-averaging.md ------------------------------------
# Each row from the eleventh of its month to the tenth of the next, one onetime period each: 2,000
# rows over twenty-three contracts, not twenty-four, since the window of the schedule's last month
# would run past its last expiry, where nothing prices it.
WINDOW_SIZES = [(5, 2), (2_000, 23)]


def a_window_ticket(rows: int, contracts: int) -> FieldValues:
    """The rows booked by dates across a month end: the eleventh of each row's month to the tenth
    of the month after."""
    on = contract_rows(rows, contracts)
    first = MONTHS[on].astype("datetime64[D]") + np.timedelta64(10, "D")
    last = (MONTHS[on] + np.timedelta64(1, "M")).astype("datetime64[D]") + np.timedelta64(9, "D")
    return FieldValues(
        FIXED_FLOAT,
        rows,
        ("trade_date", "start_date", "end_date", "quantity", "fixed_price"),
        {
            "trade_date": np.repeat(np.datetime64("2026-09-24", "D"), rows),
            "start_date": first,
            "end_date": last,
            "quantity": np.where(np.arange(rows) % 3 == 0, -3.0, 2.0),
            "fixed_price": 3.0 + (np.arange(rows) % 7) / 100,
        },
    )


def window_template() -> TradeTemplate:
    """The asian template under onetime, the quantity the period's total."""
    fields: dict[str, object] = {
        **TEMPLATE_FIELDS,
        "schedule_method": "asian",
        "quantity_per": "period",
        "settlement_frequency": "onetime",
        "nearby": 1.0,
    }
    return trade_template(one_row(fields))


@pytest.mark.parametrize(("rows", "contracts"), WINDOW_SIZES, ids=IDS)
def test_a_onetime_window_is_one_component_across_its_month_end_and_nothing_runs_per_row(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    # One component per row, its period the window, one group per distinct window and payment
    # day and one fee component per row, where the same rows under monthly are two of each; the
    # same observations and slots either way, since the days are the same days. The resolution
    # runs the dated asian ticket's functions, the month bounds once more for the windows' last
    # month, the frequency's rules looking twice more under onetime, twice in each of their two
    # runs, the periods' two conversions of the windows' ends and their look at the windows, and
    # one search for the windows' contracts, the first pricing each one's first day, with its
    # look at the windows opening too late; the encoding runs the same functions and numpy over
    # a window as over months.
    ticket, template = a_window_ticket(rows, contracts), window_template()
    counter = WorkCounter()
    batch = trades((ASIAN_GAS,), ticket, template, UNITS, counter)
    terms = batch.resolved
    assert terms.occurrence.size == rows
    np.testing.assert_array_equal(terms.period_start, terms.start_date)
    np.testing.assert_array_equal(terms.period_end, terms.end_date)
    assert batch.encoded.group_head.size == contracts
    twin = WorkCounter()
    monthly = trades((ASIAN_GAS,), ticket, a_template("asian"), UNITS, twin)
    assert monthly.resolved.occurrence.size == 2 * rows
    counts, twice = counter.freeze().as_dict(), twin.freeze().as_dict()
    assert (counts["resolved_components"], twice["resolved_components"]) == (rows, 2 * rows)
    assert (counts["encoded_groups"], twice["encoded_groups"]) == (contracts, 2 * contracts)
    assert (counts["reserved_fee_components"], twice["reserved_fee_components"]) == (rows, 2 * rows)
    for name in ("encoded_observations", "encoded_slots", "resolved_occurrences"):
        assert counts[name] == twice[name]
    assert call_profile(lambda: resolved((ASIAN_GAS,), ticket, template, WorkCounter())) == {
        **dated_ledger(contracts),
        "with_holiday_calendar": 1,
        "month_bounds": 3,  # and the windows' last months' ends
        "window_rows": 1,  # the windows' contracts, the first pricing each one's first day, one
        # search shared with the dated quote since dated-quotes.md
    }
    assert numpy_calls(lambda: resolved((ASIAN_GAS,), ticket, template, WorkCounter())) == {
        **dated_numpy(contracts),
        "ndarray.any": 40,  # the part-month asian ticket's 33, the frequency's two looks under
        # onetime, the method and the basis, in each of its two runs, and whether any window
        # opens after the last day the schedule's contracts price
        "ndarray.astype": 28,  # and the windows' ends, two conversions, and the periods' two
        "ndarray.cumsum": 14,
        "ndarray.repeat": 5,
        "ndarray.searchsorted": 2,  # and the windows' contracts, the first pricing each one's
        # first day, one search over the windows
        "ndarray.sum": 1,
        "numpy.arange": 5,
        "numpy.empty": 30,  # and the components' rows, the months' and the windows' placed
        "ufunc.reduce": 44,
    }
    terms, (observations,), _ = resolved((ASIAN_GAS,), ticket, template, WorkCounter())
    months, (by_month,), _ = resolved((ASIAN_GAS,), ticket, a_template("asian"), WorkCounter())
    assert call_profile(
        lambda: encoded(terms, (observations,), UNITS, WorkCounter())
    ) == call_profile(lambda: encoded(months, (by_month,), UNITS, WorkCounter()))
    assert numpy_calls(
        lambda: encoded(terms, (observations,), UNITS, WorkCounter())
    ) == numpy_calls(lambda: encoded(months, (by_month,), UNITS, WorkCounter()))


# --- a mixed ticket: units, bases and methods row by row ------------------------------------------
# mixed-trade-fields.md: the asian index with a second specification, MMBTU of one, and a ticket
# whose every lap over the contracts takes the next method, the unit and the basis turning row by
# row, under a template that leaves the three fields to the ticket. Eight rows over two contracts
# hold every method once per contract; two thousand over twenty-four hold each many times.
MIXED_SIZES = [(8, 2), (2_000, 24)]
MIXED_IDS = ["eight rows", "two thousand rows"]
MIXED_GAS = index(
    "gas",
    "Sample gas index",
    futures_schedule(CODES, MONTH_ENDS, None),
    index_conventions("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot", "MMBTU"),
        np.array([10_000.0, 1.0]),
        ("MMBTU", "MMBTU"),
        np.array([0.0, 0.0]),
        np.array([0.0, 0.0]),
        UNITS,
    ),
    holiday_calendar(HOLIDAYS),
    "lot",
    UNITS,
)
METHOD_NAMES_BY_LAP = ("lastday", "penultimate", "last3day", "asian")
# The pricing days of each month, the asian rows' observations, the fixture's own arithmetic.
PRICING_DAYS = np.busday_count(
    MONTHS.astype("datetime64[D]"),
    (MONTHS + np.timedelta64(1, "M")).astype("datetime64[D]"),
    holidays=HOLIDAYS,
)


def mixed_template() -> TradeTemplate:
    """The template with the three row fields left to the ticket."""
    fields: dict[str, object] = {
        name: value
        for name, value in TEMPLATE_FIELDS.items()
        if name not in ("quantity_unit", "quantity_per", "schedule_method")
    }
    return trade_template(one_row(fields))


def a_mixed_ticket(rows: int, contracts: int) -> FieldValues:
    """The ticket's rows with each row's unit, basis and method: the unit turning every row, the
    basis every two, the method every lap over the contracts."""
    on = contract_rows(rows, contracts)
    lap = np.arange(rows) // contracts
    return FieldValues(
        FIXED_FLOAT,
        rows,
        (
            "trade_date",
            "contract_code",
            "quantity",
            "fixed_price",
            "quantity_unit",
            "quantity_per",
            "schedule_method",
        ),
        {
            "trade_date": np.repeat(np.datetime64("2026-09-24", "D"), rows),
            "contract_code": tuple(CODES[int(i)] for i in on),
            "quantity": np.where(np.arange(rows) % 3 == 0, -3.0, 2.0),
            "fixed_price": 3.0 + (np.arange(rows) % 7) / 100,
            "quantity_unit": tuple(("lot", "MMBTU")[i % 2] for i in range(rows)),
            "quantity_per": tuple(("month", "calday")[(i // 2) % 2] for i in range(rows)),
            "schedule_method": tuple(METHOD_NAMES_BY_LAP[int(i)] for i in lap % 4),
        },
    )


@pytest.mark.parametrize(("rows", "contracts"), MIXED_SIZES, ids=MIXED_IDS)
def test_a_mixed_ticket_reads_each_distinct_choice_once_and_nothing_per_row(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    # Each distinct unit, method and basis read once, two, four and two, and named once for its
    # first row; the three columns from the ticket, so three looks and three reads more and three
    # repeats of a template value fewer; the four methods made once each with the open-expiry look
    # the penultimate and last3day rows need; nothing per row, the same at eight rows and at two
    # thousand.
    ticket, template = a_mixed_ticket(rows, contracts), mixed_template()
    counter = WorkCounter()
    terms, (observations,), _ = resolved((MIXED_GAS,), ticket, template, counter)
    assert counter.freeze().as_dict() == {
        "payment_rules_read": 1,  # since #181: one rule, applied once over one calendar
        "payment_shifts": 1,
        "resolved_components": rows,
        "resolved_occurrences": rows,
        "schedule_codes_read": 25,
        "ticket_codes_read": contracts,  # each distinct code of the rows, read once, since #172
    }
    np.testing.assert_array_equal(np.bincount(terms.legs[0].specification), [rows // 2, rows // 2])
    np.testing.assert_array_equal(np.bincount(terms.quantity_per), [rows // 2, rows // 2])
    lap = (np.arange(rows) // contracts) % 4
    np.testing.assert_array_equal(
        terms.legs[0].schedule_method,
        [METHODS.index(ScheduleMethod(METHOD_NAMES_BY_LAP[int(i)])) for i in lap],
    )
    assert observations.component.size == int(
        (
            np.array([1, 1, 3, 0])[lap]
            + np.where(lap == 3, PRICING_DAYS[terms.legs[0].contract], 0)
        ).sum()
    )
    assert call_profile(lambda: resolved((MIXED_GAS,), ticket, template, WorkCounter())) == {
        **resolution_ledger(contracts),
        **WHOLE_MONTHS,
        "_the_specification": 2,  # two distinct units
        "schedule_method_of": 4,  # four distinct methods
        "quantity_per_of": 2,  # two distinct bases
        "choice": 9,  # the methods, the bases, the frequency, the route and the settlement
        "_Fields.where": contracts + 12,  # five more distinct texts named
        "_each_distinct.<locals>.<lambda>": 9,  # likewise
        "_Fields.rows": 8,  # three fewer than the resolution's: the ticket's three columns, no
        # template value repeated
        "FieldValues.has": 19,  # three columns more looked for, the second price no field
        "FieldValues.texts": 4,  # and read
        "_the_days": 4,  # the four methods present, once each
        "_with_expiries_priced": 1,  # the penultimate and last3day rows' expiries open
        "open_days": 1,
    }
    assert numpy_calls(lambda: resolved((MIXED_GAS,), ticket, template, WorkCounter())) == {
        **resolution_numpy(contracts),
        **WHOLE_MONTHS_NUMPY,
        "ndarray.any": 38,  # the open expiries, the asian pricing days and the calday products
        "ndarray.astype": 28,  # the observations' days as counts, to put them back in order,
        # and the periods' six since onetime-averaging.md
        "ndarray.cumsum": 14,  # where each asian component's observations start
        "ndarray.nonzero": 7,  # the components of each of the four methods
        "ndarray.ravel": 8,  # the same, and the last3day days laid out in one column
        "ndarray.repeat": 6,  # last3day's components, asian's four repeats
        "ndarray.setflags": 23,  # the calday products frozen, the brokered rows, the periods
        "ndarray.sum": 1,  # how many asian observations in all
        "numpy._make_extobj": 1,  # the error state set once for the calday products
        "numpy.arange": 5,  # the place of each asian observation within its component
        "numpy.asanyarray": 26,
        "numpy.asarray": 2,  # the three last3day offsets taken as an array, the NaT fill
        "numpy.empty": 33,
        "ufunc.reduce": 42,
    }


# --- an IFERC ticket, iferc-basis-futures.md ------------------------------------------------
# The same 25 months on an IFERC index, each published on the first business day of its month;
# the ticket's rows resolve against it as against the futures index, the lastday method the one
# an IFERC index takes, and each payment counts from the publication day since
# iferc-publication-payment-anchor.md.
IFERC_PUBLICATION = np.busday_offset(
    MONTHS.astype("datetime64[D]"), 0, roll="forward", holidays=HOLIDAYS
)
BASIS = index(
    "basis",
    "Sample basis index",
    iferc_schedule(CODES, IFERC_PUBLICATION),
    index_conventions("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU", UNITS),
    contract_specifications(
        ("lot",), np.array([2_500.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
    ),
    None,
    "lot",
    UNITS,
)
# The IFERC resolution's functions are the futures lastday resolution's but the two that read
# the days: no pricing calendar typed and no days made, the payment anchored on each component's
# last observation, its publication day, by the same search. Its numpy loses the unique over
# the components' methods with its sort, hash, nonzero, ravel and flatten, a look and three
# conversions, and gains one look, the publication days against the components' own.
# On an IFERC index the observations read no calendar and make no days, and the one fact read is
# the methods' IFERC support, by the terms and then by the observations.
IFERC_RESOLUTION = {
    name: count
    for name, count in {**resolution_ledger(1), **WHOLE_MONTHS, "supported_on_iferc": 2}.items()
    if name
    not in ("_the_days", "with_holiday_calendar", "requires_whole_month", "counts_back_from_expiry")
}
IFERC_RESOLUTION_NUMPY = {
    name: count
    for name, count in {
        **resolution_numpy(1),
        **WHOLE_MONTHS_NUMPY,
        "ndarray.any": 33,  # one fewer: the IFERC rule is read as every row supported, one all
        "numpy.arange": 5,  # the components counted off for the anchor search, the futures' own
        # since iferc-publication-payment-anchor.md, beside the observations' places
        "ndarray.all": 3,  # in place of any row other than lastday, since the rule has one owner
        "ndarray.nonzero": 3,
        "ndarray.ravel": 3,
        "ndarray.flatten": 8,
        "numpy.asanyarray": 20,
    }.items()
    if name not in ("ndarray.sort", "numpy._unique_hash")
}


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_an_iferc_ticket_resolves_like_a_futures_one_without_the_days(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    ticket, template = a_ticket(rows, contracts), a_template()
    counter = WorkCounter()
    terms, (observations,), _ = resolved((BASIS,), ticket, template, counter)
    np.testing.assert_array_equal(observations.date, IFERC_PUBLICATION[terms.legs[0].contract])
    np.testing.assert_array_equal(observations.weight, np.ones(rows))
    assert terms.payment is not None
    np.testing.assert_array_equal(
        terms.payment.date,
        np.busday_offset(IFERC_PUBLICATION[terms.legs[0].contract], 2, holidays=HOLIDAYS),
    )
    assert counter.freeze().as_dict() == {
        "payment_rules_read": 1,  # since #181: one rule, applied once over one calendar
        "payment_shifts": 1,
        "resolved_components": rows,
        "resolved_occurrences": rows,
        "schedule_codes_read": 25,
        "ticket_codes_read": contracts,  # each distinct code of the rows, read once, since #172
    }
    by_distinct = {
        name: (count if name not in resolution_ledger(1) else resolution_ledger(contracts)[name])
        for name, count in IFERC_RESOLUTION.items()
    }
    assert call_profile(lambda: resolved((BASIS,), ticket, template, WorkCounter())) == by_distinct
    numpy = {
        **IFERC_RESOLUTION_NUMPY,
        "generic.astype": 2 * contracts,
    }
    assert numpy_calls(lambda: resolved((BASIS,), ticket, template, WorkCounter())) == numpy


# --- the marketing reserve, booking-fields-and-marketing-reserve.md ------------------------------
# A ticket with a marketing column sums its amounts once per row, reported as reserved_occurrences
# beside the components' brokerage and clearing, since #175, and a CVA column the same, the rows
# counted once per reserve field, since cva-reserve.md; nothing else in the counter moves.


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_a_marketing_and_a_cva_column_each_sum_once_per_row_and_the_counter_says_so(
    rows: int, contracts: int
) -> None:
    base = a_ticket(rows, contracts)
    ticket = FieldValues(
        FIXED_FLOAT,
        rows,
        (*base.names, "marketing_reserve", "cva_reserve"),
        {
            **base.columns,
            "marketing_reserve": np.full(rows, 7.5),
            "cva_reserve": np.full(rows, -2.5),  # signed, since cva-reserve.md
        },
    )
    counter = WorkCounter()
    batch = trades((GAS,), ticket, a_template(), UNITS, counter)
    assert batch.encoded.reserves.marketing == pytest.approx(7.5 * rows)
    assert batch.encoded.reserves.cva == pytest.approx(-2.5 * rows)
    alone = FieldValues(
        FIXED_FLOAT,
        rows,
        (*base.names, "cva_reserve"),
        {**base.columns, "cva_reserve": np.full(rows, -2.5)},
    )
    once = WorkCounter()
    assert trades((GAS,), alone, a_template(), UNITS, once).encoded.reserves.cva == pytest.approx(
        -2.5 * rows
    )
    assert once.freeze()["reserved_occurrences"] == rows  # the one field's rows
    assert counter.freeze().as_dict() == {
        "encoded_components": rows,
        "encoded_groups": contracts,
        "encoded_observations": rows,
        "encoded_slots": contracts,
        "payment_rules_read": 1,  # since #181: one rule, applied once over one calendar
        "payment_shifts": 1,
        "reserved_fee_components": rows,  # clearing alone: cleared and unbrokered, since #188
        "reserved_occurrences": 2 * rows,  # the rows once per reserve field booked, marketing
        # since #175 and CVA since cva-reserve.md
        "resolved_components": rows,
        "resolved_occurrences": rows,
        "schedule_codes_read": 25,
        "ticket_codes_read": contracts,
    }


# --- a half-year strip, half-year-strips.md -------------------------------------------------------


def one_code(code: str) -> FieldValues:
    """One row booking that code, as the seam hands it over."""
    return FieldValues(
        FIXED_FLOAT,
        1,
        ("trade_date", "contract_code", "quantity", "fixed_price"),
        {
            "trade_date": np.array(["2026-09-24"], dtype="datetime64[D]"),
            "contract_code": (code,),
            "quantity": np.array([2.0]),
            "fixed_price": np.array([3.0]),
        },
    )


def test_a_half_year_does_the_work_of_its_six_month_strip(
    call_profile: CallProfile, numpy_calls: CallProfile
) -> None:
    # The half reads its one label where the range reads two; from the months on, the resolution,
    # the observations and the payment days are the same calls and the same numpy, since #182:
    # nothing is parsed or expanded again after creation.
    half, strip, template = one_code("1H27"), one_code("F27-M27"), a_template()
    for ticket in (half, strip):
        resolved((GAS,), ticket, template, WorkCounter())
    through_half = call_profile(lambda: resolved((GAS,), half, template, WorkCounter()))
    through_strip = call_profile(lambda: resolved((GAS,), strip, template, WorkCounter()))
    assert through_half.pop("_label_months") == 1
    assert through_strip.pop("_label_months") == 2
    assert through_half == through_strip
    assert numpy_calls(lambda: resolved((GAS,), half, template, WorkCounter())) == numpy_calls(
        lambda: resolved((GAS,), strip, template, WorkCounter())
    )
    terms, _, _ = resolved((GAS,), half, template, WorkCounter())
    assert terms.legs[0].contract.size == 6
