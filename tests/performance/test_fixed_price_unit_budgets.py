"""The work of a fixed price in a unit of its own, issue #273, measured against the same rows
with no unit typed, at 24 rows over two contracts and at 2,000 over twenty-four. A batch priced
in the unit its index quotes in, the unit typed on every row, is encoded by the functions and
the numpy calls of a batch that types none: the first leg's coefficient is handed back and
nothing is converted again. A batch that mixes units pairs its two unit fields in one pass,
whichever of the template and the ticket holds each, reads each distinct pair once and makes one
size per distinct unit and specification its rows select and one currency factor per unit, a
handful of numbers whatever the rows, then one product over the components. Preparing and
valuing either batch runs the same functions and the same numpy calls as the batch that types
none, and no conversion among them. Reading a batch back shows each row's unit in two columns
more, the two fields. The index is a premium quoted in dollars a pound, with a lot of 55,116
pounds, a pound and a tonne."""

from collections.abc import Callable

import numpy as np
import pytest
from holiday_fixtures import closed_on, index_on
from test_seam_allocation import SLACK, least_peak
from test_trade_creation_budgets import (
    CALENDARS,
    CODES,
    EXPIRIES,
    HOLIDAYS,
    TEMPLATE_FIELDS,
    contract_rows,
    one_row,
)

from catalyst.calendar.calendar import calendar
from catalyst.excel.utilities import shown
from catalyst.globals.unit_conversions import UNITS
from catalyst.globals.valuation_date import valuation_date
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT
from catalyst.instruments.fields import FieldValues
from catalyst.market.market import Market, market
from catalyst.market.market_history import MarketHistory, market_history
from catalyst.market_data.futures_fixings import futures_fixings
from catalyst.market_data.price_vector import price_vector
from catalyst.trades.encoding import encoded
from catalyst.trades.evaluation import trade_results
from catalyst.trades.observations import Observations
from catalyst.trades.preparation import prepared_trades
from catalyst.trades.resolution import resolved, trades
from catalyst.trades.template import TradeTemplate, trade_template
from catalyst.trades.terms import ResolvedTrades

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
SIZES = [(24, 2), (2_000, 24)]
IDS = ["24 rows", "two thousand rows"]

PREMIUM = index_on(
    "premium",
    "Sample premium index",
    futures_schedule(CODES, EXPIRIES, None),
    index_conventions("DOLLAR", "LB", "DOLLAR", "MASS", "LB", UNITS),
    contract_specifications(
        ("lot", "lb", "mt"),
        np.array([55_116.0, 1.0, 1.0]),
        ("LB", "LB", "MT"),
        np.zeros(3),
        np.zeros(3),
        UNITS,
    ),
    closed_on(HOLIDAYS),
    "lot",
    UNITS,
)
WORDS = ("lot", "lb", "mt")
# A unit as the two fields hold it: the currency unit and the quantity unit a price is per.
Unit = tuple[str, str]
MONEY, PER = "fixed_price_currency_unit", "fixed_price_quantity_unit"
# The index's own unit and three others: four distinct units, of the six their two currency
# units and three quantity units could make, and with three specifications twelve distinct
# pairs of a unit and a specification once the rows have gone round both.
MIXED: tuple[Unit, ...] = (("DOLLAR", "LB"), ("DOLLAR", "MT"), ("CENT", "LB"), ("CENT", "KG"))
OWN: tuple[Unit, ...] = (("DOLLAR", "LB"),)


def a_template(**more: str) -> TradeTemplate:
    """The creation budgets' template, cleared and financial, less the quantity unit, which
    each row supplies, and with whatever more is given."""
    fields = {k: v for k, v in TEMPLATE_FIELDS.items() if k != "quantity_unit"}
    return trade_template(one_row({**fields, **more}))


def a_ticket(
    rows: int,
    contracts: int,
    units: tuple[Unit, ...] | None,
    fields: tuple[str, ...] = (MONEY, PER),
) -> FieldValues:
    """That many single-month rows, each in its own quantity word, the three in turn, and each
    priced in the next of the units given, or in none where none is given; of a unit's two
    fields the ticket holds those named, both unless a template holds one."""
    on = contract_rows(rows, contracts)
    columns: dict[str, object] = {
        "trade_date": np.repeat(np.datetime64("2026-09-24", "D"), rows),
        "contract_code": tuple(CODES[int(i)] for i in on),
        "quantity": np.where(np.arange(rows) % 3 == 0, -3.0, 2.0),
        "quantity_unit": tuple(WORDS[i % 3] for i in range(rows)),
        "fixed_price": 0.90 + (np.arange(rows) % 7) / 100,
    }
    if units is not None:
        for at, name in enumerate((MONEY, PER)):
            if name in fields:
                columns[name] = tuple(units[i % len(units)][at] for i in range(rows))
    return FieldValues(FIXED_FLOAT, rows, tuple(columns), columns)


def terms_of(
    rows: int, contracts: int, units: tuple[Unit, ...] | None
) -> tuple[ResolvedTrades, tuple[Observations, ...]]:
    terms, observations, _ = resolved(
        (PREMIUM,), a_ticket(rows, contracts, units), a_template(), WorkCounter(), CALENDARS
    )
    return terms, observations


def more(mine: dict[str, int], theirs: dict[str, int]) -> dict[str, int]:
    """What one ledger holds over another, name by name, a name the other lacks from zero."""
    names = sorted(set(mine) | set(theirs))
    return {n: mine.get(n, 0) - theirs.get(n, 0) for n in names if mine.get(n) != theirs.get(n)}


# --- the encoding ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_a_batch_typed_in_the_indexes_unit_is_encoded_as_one_that_types_none(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    omitted, omitted_days = terms_of(rows, contracts, None)
    typed, typed_days = terms_of(rows, contracts, OWN)
    assert typed.price_units == omitted.price_units
    for profile in (call_profile, numpy_calls):
        assert profile(lambda: encoded(typed, typed_days, UNITS, WorkCounter())) == profile(
            lambda: encoded(omitted, omitted_days, UNITS, WorkCounter())
        )
    one = encoded(typed, typed_days, UNITS, WorkCounter())
    other = encoded(omitted, omitted_days, UNITS, WorkCounter())
    np.testing.assert_array_equal(one.offset, other.offset)


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_a_mixed_batch_converts_once_per_unit_and_specification_whatever_the_rows(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    omitted, omitted_days = terms_of(rows, contracts, None)
    mixed, mixed_days = terms_of(rows, contracts, MIXED)
    assert len(mixed.price_units) == 4
    mine, theirs = WorkCounter(), WorkCounter()
    encoded(mixed, mixed_days, UNITS, mine)
    encoded(omitted, omitted_days, UNITS, theirs)
    assert mine.freeze().as_dict() == theirs.freeze().as_dict()  # the same work reported
    # The functions a mixed batch runs over one that types no unit: each of the four units read
    # for its meaning once, no trade named where none is refused; one row of sizes per unit,
    # the three specifications its rows select, twelve factors, and one currency factor per
    # unit, sixteen conversions for four units over three specifications.
    assert more(
        call_profile(lambda: encoded(mixed, mixed_days, UNITS, WorkCounter())),
        call_profile(lambda: encoded(omitted, omitted_days, UNITS, WorkCounter())),
    ) == {
        "_the_fixed_unit": 4,
        "_the_sizes": 4,
        "UnitConversions.factor": 16,
        "UnitConversions.category": 16,
    }
    assert (
        more(
            numpy_calls(lambda: encoded(mixed, mixed_days, UNITS, WorkCounter())),
            numpy_calls(lambda: encoded(omitted, omitted_days, UNITS, WorkCounter())),
        )
        == MIXED_NUMPY
    )


# The numpy of a mixed batch's fixed coefficient, the same at both sizes: the units the rows are
# priced in found in one unique and put in the order of their first rows, the specifications
# each selects in one unique a unit, the two small tables and each unit's row of sizes, the
# flags down round the conversions and the product, and one look that every coefficient is
# finite.
MIXED_NUMPY = {
    "ndarray.any": 1,  # whether any coefficient outruns the largest number
    "ndarray.argsort": 2,  # the units' first rows within the unique, and their order
    "ndarray.flatten": 5,  # one per unique: the units, and the specifications of each of four
    "ndarray.sort": 4,  # the four units' specifications
    "numpy._make_extobj": 5,  # the flags down round each unit's sizes and round the product
    "numpy._unique_hash": 4,
    "numpy.asanyarray": 10,
    "numpy.empty": 1,
    "numpy.zeros": 6,  # the table of sizes, the currency factors and each unit's row of sizes
    "ufunc.reduce": 1,
}


# --- preparation and a tick -----------------------------------------------------------------------

AS_OF = "2026-10-01"


def a_history() -> MarketHistory:
    """The premium's history on 1 October 2026, before any contract of the ticket expires: 0.90
    on every fixed business day; its market quotes the 24 contracts from X26 on."""
    cal = calendar(valuation_date(np.datetime64(AS_OF, "D"), 0.5), PREMIUM)
    priced = cal.dates[cal.is_fixed & cal.is_priced]
    settles = np.full((priced.size, 1), 0.90)
    return market_history(cal, futures_fixings(priced[::-1].copy(), settles, PREMIUM))


def a_market(history: MarketHistory) -> Market:
    return market(history, price_vector(PREMIUM.name, 0.90 + np.arange(24) / 1000))


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_preparing_and_valuing_convert_nothing_whatever_unit_the_prices_are_in(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    history = a_history()
    quotes = a_market(history)
    batches = [
        trades(
            (PREMIUM,),
            a_ticket(rows, contracts, units),
            a_template(),
            UNITS,
            WorkCounter(),
            CALENDARS,
        )
        for units in (None, OWN, MIXED)
    ]
    for profile in (call_profile, numpy_calls):
        prepared = [
            profile(lambda b=batch: prepared_trades(b.encoded, (history,), WorkCounter()))
            for batch in batches
        ]
        assert prepared[0] == prepared[1] == prepared[2]
        assert "UnitConversions.factor" not in prepared[0]
    ready = [prepared_trades(batch.encoded, (history,), WorkCounter()) for batch in batches]
    for profile in (call_profile, numpy_calls):
        ticks = [
            profile(lambda p=each: trade_results(p, (quotes,), WorkCounter(), None))
            for each in ready
        ]
        assert ticks[0] == ticks[1] == ticks[2]
        assert "UnitConversions.factor" not in ticks[0]
    # And the three batches report the same work at each step.
    counted: list[tuple[dict[str, int], dict[str, int]]] = []
    for batch in batches:
        preparing, ticking = WorkCounter(), WorkCounter()
        each = prepared_trades(batch.encoded, (history,), preparing)
        trade_results(each, (quotes,), ticking, None)
        counted.append((preparing.freeze().as_dict(), ticking.freeze().as_dict()))
    assert counted[0] == counted[1] == counted[2]


# --- memory ---------------------------------------------------------------------------------------


def test_a_unit_on_every_row_costs_its_columns_read_and_nothing_per_row_beyond() -> None:
    # Creating 2,000 rows, the peak over a batch that types no unit: eight bytes a row, the
    # places of the rows among the distinct units as the two columns' read found them, held
    # while the kernel copies them, where the default makes its places once. Measured on
    # 2026-11-27: 665,118 with no unit typed, 681,491 with the index's unit on every row and
    # 681,850 with four units mixed, whose coefficient is made and dropped under that peak, as
    # the two columns' texts side by side are, read and dropped before it.
    rows, contracts = 2_000, 24

    def made(units: tuple[Unit, ...] | None) -> Callable[[], object]:
        ticket, template = a_ticket(rows, contracts, units), a_template()
        return lambda: trades((PREMIUM,), ticket, template, UNITS, WorkCounter(), CALENDARS)

    omitted, typed, mixed = (least_peak(made(units)) for units in (None, OWN, MIXED))
    assert typed <= omitted + 8 * rows + 2 * SLACK
    assert mixed <= omitted + 8 * rows + 2 * SLACK


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_the_resolution_pairs_the_two_fields_in_one_pass_and_nothing_per_row(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    template = a_template()
    plain = a_ticket(rows, contracts, None)

    def over(units: tuple[Unit, ...], profile: CallProfile, split: bool = False) -> dict[str, int]:
        """What resolving the units costs over the ticket that types none: both fields down
        the ticket, or split, the money on the template and the rest down the ticket."""
        ticket = a_ticket(rows, contracts, units, (PER,) if split else (MONEY, PER))
        shared = a_template(**{MONEY: units[0][0]}) if split else template
        return more(
            profile(lambda: resolved((PREMIUM,), ticket, shared, WorkCounter(), CALENDARS)),
            profile(lambda: resolved((PREMIUM,), plain, template, WorkCounter(), CALENDARS)),
        )

    # The two columns read once each and no text of either read for a form, there being none:
    # the pairs found and the rows' places checked in range and copied; one pair or four.
    for units in (OWN, MIXED):
        assert over(units, call_profile) == {
            "FieldValues.texts": 2,
            "_Fields.texts": 2,
            "_the_choices": 1,
            "_frozen_rows": 1,
        }
        # One unique over the two columns side by side, whose rows are the pairs, and one look
        # that every place is in range; no zeros, the places being the read's own.
        assert over(units, numpy_calls) == PAIRED_NUMPY
    # The money on the template: one column read from the ticket and the template's one value
    # repeated down the rows, which asks the ticket for its row count; one question fewer of
    # the ticket, whether it holds the field the template does. The same numpy.
    assert over(OWN, call_profile, split=True) == {
        "FieldValues.has": -1,
        "FieldValues.texts": 1,
        "_Fields.rows": 1,
        "_Fields.texts": 2,
        "_the_choices": 1,
        "_frozen_rows": 1,
    }
    assert over(OWN, numpy_calls, split=True) == PAIRED_NUMPY


# The numpy of pairing the two fields, the same at both sizes and for one pair or four, over a
# ticket that types no unit: the two columns laid side by side in one array, numpy's unique
# over its rows, which views each row as one record, sorts once and marks where the record
# changes, and the kernel's look that every place is in range.
PAIRED_NUMPY = {
    "ndarray.any": 1,
    "ndarray.argsort": 1,
    "ndarray.astype": 1,
    "ndarray.cumsum": 1,
    "ndarray.flatten": 1,
    "ndarray.reshape": 2,
    "ndarray.tolist": 1,  # the distinct pairs, a handful
    "ndarray.transpose": 2,
    "ndarray.view": 2,
    "numpy._is_view_safe_cast": 2,
    "numpy.array": 2,
    "numpy.asanyarray": 2,
    "numpy.ascontiguousarray": 1,
    "numpy.empty": 2,
    "numpy.normalize_axis_index": 4,
    "numpy.promote_types": 2,
    "numpy.zeros": -1,
    "ufunc.reduce": 2,
}


# --- the readback ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("rows", "contracts"), SIZES, ids=IDS)
def test_the_readback_shows_each_rows_unit_in_two_columns_more(
    call_profile: CallProfile, numpy_calls: CallProfile, rows: int, contracts: int
) -> None:
    # Measured against the readback before the unit was shown, the same batch at both sizes:
    # two text columns more, the helper that adds a column called 12 times where it was called
    # 10, and two arrays more, the distinct units' codes of each field, where there were 7. One
    # unit or four, the same functions and the same numpy. Nothing else moved.
    batches = [
        trades(
            (PREMIUM,),
            a_ticket(rows, contracts, units),
            a_template(),
            UNITS,
            WorkCounter(),
            CALENDARS,
        )
        for units in (None, OWN, MIXED)
    ]
    omitted, typed, mixed = (call_profile(lambda b=batch: shown(b)) for batch in batches)
    assert omitted == typed == mixed
    assert omitted["trades_table.<locals>.text"] == 12
    arrays = [numpy_calls(lambda b=batch: shown(b)) for batch in batches]
    assert arrays[0] == arrays[1] == arrays[2]
    assert arrays[0]["numpy.array"] == 9
    assert shown(batches[2]).kinds.shape[1] == 26  # 24 before: the unit is the last two columns


def test_the_readbacks_new_columns_cost_their_texts_and_nothing_more() -> None:
    # Reading 2,000 rows back: 1,433,685 bytes at the peak before the unit was shown, about 717
    # a row over 24 columns, and 1,614,809 with its two columns, about 807 a row over 26,
    # measured on 2026-11-27. A text cell is 33 bytes a row, its text kept for the way out and
    # its place among the cells, as each text column costs: 66 for the two. The other 24 are a
    # step of the tuple the texts are gathered into, which grows by a quarter at a time and
    # stands a step up at 13 text cells a row: 243,360 bytes at its peak where 12 a row peak at
    # 194,656. Four units mixed cost what one does, to the byte.
    rows, contracts = 2_000, 24
    peaks: list[int] = []
    for units in (None, OWN, MIXED):
        batch = trades(
            (PREMIUM,),
            a_ticket(rows, contracts, units),
            a_template(),
            UNITS,
            WorkCounter(),
            CALENDARS,
        )
        peaks.append(least_peak(lambda b=batch: shown(b)))
    for peak in peaks:
        assert peak <= 808 * rows + 2 * SLACK
    assert abs(peaks[2] - peaks[0]) <= SLACK
