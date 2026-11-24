"""The index: the schedule's kind read off the object, the holiday key as the kind requires,
bound to its calendar from the collection, and four objects held by reference, nothing copied and
nothing checked again."""

import dataclasses

import numpy as np
import pytest
from holiday_fixtures import index_on
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from catalyst.calendar.calendar import calendar
from catalyst.globals.unit_conversions import UNITS
from catalyst.globals.valuation_date import valuation_date
from catalyst.index_definitions.contract_specifications import (
    ContractSpecifications,
    contract_specifications,
)
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.gas_daily_schedule import gas_daily_schedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar, holiday_calendar
from catalyst.index_definitions.holiday_calendars import (
    HolidayCalendars,
    collect_holiday_calendars,
)
from catalyst.index_definitions.index import Index, index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.index_definitions.kind import Kind
from catalyst.index_definitions.published_schedule import published_schedule
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market_data.futures_fixings import futures_fixings


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


# The page's sample: three Henry Hub indices, one per market, sharing one conventions object,
# DOLLAR per MMBTU with quantities in MMBTU, and the specifications page's two lots.
FUTURES = futures_schedule(
    tuple(f"c{i}" for i in range(12)),
    dates(
        "2026-01-28",
        "2026-02-25",
        "2026-03-27",
        "2026-04-28",
        "2026-05-27",
        "2026-06-26",
        "2026-07-29",
        "2026-08-27",
        "2026-09-28",
        "2026-10-28",
        "2026-11-24",
        "2026-12-29",
    ),
    None,
)
# One print a month, the shape of a monthly index such as Inside FERC's.
MONTHLY = published_schedule(("V26", "X26", "Z26"), dates("2026-10-01", "2026-11-02", "2026-12-01"))
GAS_DAILY = gas_daily_schedule(
    ("U26", "V26", "X26"),
    dates("2026-09-01", "2026-10-01", "2026-11-01"),
    dates("2026-09-30", "2026-10-31", "2026-11-30"),
)
PUBLISHED = published_schedule(
    ("U26", "U26", "U26", "U26", "V26"),
    dates("2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"),
)
HOLIDAYS = holiday_calendar("NYMEX", dates("2026-01-01", "2026-01-19", "2026-02-16"))
ICE = holiday_calendar("ICE", dates("2026-01-01", "2026-04-03"))
CALENDARS = collect_holiday_calendars((HOLIDAYS, ICE), WorkCounter())
CONVENTIONS = index_conventions("DOLLAR", "MMBTU", "DOLLAR", "ENERGY", "MMBTU", UNITS)
SPECIFICATIONS = contract_specifications(
    ("NYMEX NG", "ICE NG"),
    np.array([10000.0, 2500.0]),
    ("MMBTU", "MMBTU"),
    np.array([3.0, 0.75]),
    np.array([2.0, 0.5]),
    UNITS,
)


def an_index(
    name: str = "Henry Hub NYMEX",
    schedule: object = FUTURES,
    specifications: ContractSpecifications = SPECIFICATIONS,
    holidays: HolidayCalendar | None = HOLIDAYS,
    reporting_lot: str | None = None,
) -> Index:
    return index_on(
        name, f"{name} index", schedule, CONVENTIONS, specifications, holidays, reporting_lot, UNITS
    )


# --- the sample ---------------------------------------------------------------


def test_the_futures_sample_binds_its_four_objects_and_reads_its_kind_off_the_schedule() -> None:
    made = an_index()
    assert made.name == "Henry Hub NYMEX"
    assert made.kind is Kind.FUTURES
    assert made.schedule is FUTURES
    assert made.holiday_calendar is HOLIDAYS
    assert made.conventions is CONVENTIONS
    assert made.specifications is SPECIFICATIONS


def test_the_monthly_and_gas_daily_samples_carry_no_holiday_calendar() -> None:
    monthly = index(
        "Henry Hub IFERC",
        "Henry Hub natural gas - Inside FERC monthly index",
        MONTHLY,
        CONVENTIONS,
        SPECIFICATIONS,
        None,
        None,
        UNITS,
        CALENDARS,
        WorkCounter(),
    )
    assert monthly.kind is Kind.PUBLISHED
    assert monthly.schedule is MONTHLY and monthly.holiday_calendar is None
    daily = index(
        "Henry Hub Gas Daily",
        "Henry Hub natural gas - Platts Gas Daily",
        GAS_DAILY,
        CONVENTIONS,
        SPECIFICATIONS,
        None,
        None,
        UNITS,
        CALENDARS,
        WorkCounter(),
    )
    assert daily.kind is Kind.GAS_DAILY
    assert daily.schedule is GAS_DAILY and daily.holiday_calendar is None
    assert monthly.conventions is daily.conventions is CONVENTIONS


# A published index, its prices a listed set of dated prints: the kind read off the schedule,
# no holiday calendar, and a key given refused before it is looked up, as on the other two.
def test_a_published_index_reads_its_kind_off_the_schedule_and_takes_no_holiday_key() -> None:
    weekly = index(
        "DOE Diesel",
        "U.S. national retail diesel - EIA weekly",
        PUBLISHED,
        CONVENTIONS,
        SPECIFICATIONS,
        None,
        None,
        UNITS,
        CALENDARS,
        WorkCounter(),
    )
    assert weekly.kind is Kind.PUBLISHED
    assert weekly.schedule is PUBLISHED and weekly.holiday_calendar is None
    counter = WorkCounter()
    with pytest.raises(ValueError) as failure:
        index(
            "DOE Diesel",
            "U.S. national retail diesel - EIA weekly",
            PUBLISHED,
            CONVENTIONS,
            SPECIFICATIONS,
            "NYMEX",
            None,
            UNITS,
            CALENDARS,
            counter,
        )
    assert str(failure.value) == "holiday_key is 'NYMEX', expected none with a published schedule"
    assert counter.freeze().as_dict() == {}


# --- what is rejected, in the order the rules run -----------------------------


def test_an_object_that_is_not_a_schedule_is_refused_naming_what_it_is() -> None:
    made = calendar(valuation_date(day("2026-06-01"), 0.5), an_index())
    fixings = futures_fixings(dates("2026-05-29"), np.array([[2.9]]), an_index())
    for wrong, what in (
        (HOLIDAYS, "a holiday calendar"),
        (made, "a calendar"),
        (fixings, "futures fixings"),
        (CONVENTIONS, "index conventions"),
        (an_index(), "an index"),
    ):
        with pytest.raises(ValueError) as failure:
            index(
                "Henry Hub NYMEX",
                "Henry Hub natural gas - NYMEX",
                wrong,
                CONVENTIONS,
                SPECIFICATIONS,
                None,
                None,
                UNITS,
                CALENDARS,
                WorkCounter(),
            )
        assert str(failure.value) == (
            f"schedule is {what}, expected a futures, Gas Daily or published schedule"
        )


def test_a_futures_index_needs_its_holiday_key_and_the_other_two_refuse_one() -> None:
    with pytest.raises(ValueError) as failure:
        index(
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            FUTURES,
            CONVENTIONS,
            SPECIFICATIONS,
            None,
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
    assert str(failure.value) == (
        "holiday_key is missing, expected a holiday calendar's key with a futures schedule"
    )
    with pytest.raises(ValueError) as failure:
        index(
            "Henry Hub IFERC",
            "Henry Hub natural gas - Inside FERC monthly index",
            MONTHLY,
            CONVENTIONS,
            SPECIFICATIONS,
            "NYMEX",
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
    assert str(failure.value) == "holiday_key is 'NYMEX', expected none with a published schedule"
    with pytest.raises(ValueError) as failure:
        index(
            "Henry Hub Gas Daily",
            "Henry Hub natural gas - Platts Gas Daily",
            GAS_DAILY,
            CONVENTIONS,
            SPECIFICATIONS,
            "NYMEX",
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
    assert str(failure.value) == "holiday_key is 'NYMEX', expected none with a Gas Daily schedule"


# --- the key, holiday-keys.md -------------------------------------------------


def keyed(
    key: str | None,
    calendars: HolidayCalendars | None = CALENDARS,
    schedule: object = FUTURES,
    counter: WorkCounter | None = None,
) -> Index:
    return index(
        "Henry Hub NYMEX",
        "Henry Hub natural gas - NYMEX",
        schedule,
        CONVENTIONS,
        SPECIFICATIONS,
        key,
        None,
        UNITS,
        calendars,
        counter or WorkCounter(),
    )


def test_the_key_selects_the_indexs_calendar_from_the_collection_by_reference() -> None:
    # One name is the collection's own calendar, nothing made; several are the calendar closed
    # on every day any of them is closed, named by the names in sorted order whatever the order
    # typed.
    assert keyed("NYMEX").holiday_calendar is HOLIDAYS
    assert keyed("ICE").holiday_calendar is ICE
    for key in ("NYMEX+ICE", "ICE+NYMEX"):
        union = keyed(key).holiday_calendar
        assert union is not None and union.name == "ICE+NYMEX"
        assert (
            union.holiday.tolist()
            == dates("2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03").tolist()
        )


def test_a_key_needs_a_collection_that_holds_its_names_exactly() -> None:
    with pytest.raises(ValueError) as failure:
        keyed("NYMEX", None)
    assert str(failure.value) == (
        "holiday_calendars is missing, expected a _CollectHolidayCalendars collection, which "
        "holiday_key selects a calendar from"
    )
    for key, missing in (("NYMX", "NYMX"), ("nymex", "nymex"), ("NYMEX+CME", "CME")):
        with pytest.raises(ValueError) as failure:
            keyed(key)
        assert str(failure.value) == (
            f"holiday_key is {key!r}, expected names of the collection's calendars, 'NYMEX' and "
            f"'ICE'; it holds no {missing!r}"
        )
    with pytest.raises(ValueError) as failure:
        keyed("NYMEX + ICE")
    assert str(failure.value) == (
        "holiday_key is 'NYMEX + ICE', expected a calendar's name, or several joined by '+', "
        "each with no whitespace around it"
    )


def test_the_kind_is_read_before_the_key_is_looked_up() -> None:
    # A published or a Gas Daily index refuses a key whatever it says and whether or not a
    # collection came with it: nothing is looked up for an index that reads no calendar.
    for schedule, words in ((MONTHLY, "a published"), (GAS_DAILY, "a Gas Daily")):
        for calendars in (CALENDARS, None):
            with pytest.raises(ValueError) as failure:
                keyed("NOWHERE", calendars, schedule)
            assert str(failure.value) == (
                f"holiday_key is 'NOWHERE', expected none with {words} schedule"
            )
    # And a futures index with no key is told the key is missing, collection or none.
    for calendars in (CALENDARS, None):
        with pytest.raises(ValueError, match=r"^holiday_key is missing, expected"):
            keyed(None, calendars)


def test_a_collection_nothing_selects_from_is_read_for_nothing() -> None:
    assert keyed(None, CALENDARS, MONTHLY).holiday_calendar is None
    assert keyed(None, None, GAS_DAILY).holiday_calendar is None


def test_the_work_of_an_index_is_its_one_key_and_a_unions_own_counts() -> None:
    def counted(key: str | None, schedule: object = FUTURES) -> dict[str, int]:
        counter = WorkCounter()
        keyed(key, CALENDARS, schedule, counter)
        return counter.freeze().as_dict()

    assert counted("NYMEX") == {"holiday_keys_bound": 1}
    assert counted("NYMEX+ICE") == {
        "calendars_combined": 2,
        "holidays_read": 5,
        "holidays_kept": 4,
        "holiday_keys_bound": 1,
    }
    assert counted(None, MONTHLY) == {}


def test_the_schedule_is_checked_before_the_holiday_key() -> None:
    with pytest.raises(ValueError) as failure:
        index(
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            HOLIDAYS,
            CONVENTIONS,
            SPECIFICATIONS,
            "NYMEX",
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
    assert str(failure.value).startswith("schedule is a holiday calendar")


# --- the name and the specifications are labels ----------------------------------------


def test_the_name_is_kept_as_typed_and_two_indices_may_share_it() -> None:
    for name in ("henry hub nymex", "HENRY HUB NYMEX", " Henry Hub NYMEX ", "Henry  Hub"):
        assert an_index(name).name == name
    first, second = an_index(), an_index()
    assert first.name == second.name and first is not second


# The specifications name the contracts the index trades as, not the schedule's months: one
# row against twelve contracts, or three against three, and neither name is a code.
def test_specifications_need_not_answer_to_the_schedules_codes_or_count() -> None:
    one = contract_specifications(
        ("ICE basis",), np.array([2500.0]), ("MMBTU",), np.array([0.5]), np.array([0.25]), UNITS
    )
    made = an_index(specifications=one)
    assert made.specifications is one
    assert len(made.specifications.names) == 1 and len(made.schedule.codes) == 12
    three = contract_specifications(
        ("V26", "X26", "Z26"),
        np.array([1.0, 1.0, 1.0]),
        ("MMBTU", "THERM", "GJ"),
        np.zeros(3),
        np.zeros(3),
        UNITS,
    )
    assert (
        index(
            "Henry Hub IFERC",
            "Henry Hub natural gas - Inside FERC monthly index",
            MONTHLY,
            CONVENTIONS,
            three,
            None,
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        ).specifications
        is three
    )


# The lot units are the one fact read across two definitions: each is a unit of the conventions'
# quantity type, so a barrel row and a gallon row stand under a volume index, and an MMBTU row
# is refused there naming the row, the unit and the units that would have done, after the kind
# and the holiday rules.
def test_lot_units_of_the_indexs_measure_pass_and_another_measures_are_refused() -> None:
    volume = index_conventions("DOLLAR", "BBL", "DOLLAR", "VOLUME", "BBL", UNITS)
    barrels_and_gallons = contract_specifications(
        ("lots", "gal"), np.array([1000.0, 1.0]), ("BBL", "GAL"), np.zeros(2), np.zeros(2), UNITS
    )
    made = index(
        "WTI NYMEX",
        "West Texas Intermediate crude oil - NYMEX",
        FUTURES,
        volume,
        barrels_and_gallons,
        "NYMEX",
        None,
        UNITS,
        CALENDARS,
        WorkCounter(),
    )
    assert made.specifications is barrels_and_gallons
    with pytest.raises(ValueError) as failure:
        index(
            "WTI NYMEX",
            "West Texas Intermediate crude oil - NYMEX",
            FUTURES,
            volume,
            SPECIFICATIONS,
            "NYMEX",
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
    assert str(failure.value) == (
        "specifications row 1 lot_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3"
    )
    mixed = contract_specifications(
        ("lots", "gal", "gas"),
        np.array([1000.0, 1.0, 1.0]),
        ("BBL", "GAL", "MMBTU"),
        np.zeros(3),
        np.zeros(3),
        UNITS,
    )
    with pytest.raises(ValueError) as failure:
        index(
            "WTI NYMEX",
            "West Texas Intermediate crude oil - NYMEX",
            FUTURES,
            volume,
            mixed,
            "NYMEX",
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
    assert str(failure.value) == (
        "specifications row 3 lot_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3"
    )
    with pytest.raises(ValueError) as failure:
        index(
            "Henry Hub NYMEX",
            "Henry Hub natural gas - NYMEX",
            FUTURES,
            CONVENTIONS,
            barrels_and_gallons,
            "NYMEX",
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
    assert str(failure.value) == (
        "specifications row 1 lot_unit is 'BBL', expected an ENERGY unit, MMBTU, BTU, THERM, GJ, "
        "MWH or KWH"
    )
    with pytest.raises(ValueError, match=r"^holiday_key is 'NYMEX', expected none"):
        index(
            "Henry Hub IFERC",
            "Henry Hub natural gas - Inside FERC monthly index",
            MONTHLY,
            volume,
            SPECIFICATIONS,
            "NYMEX",
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )


# --- ownership ----------------------------------------------------------------


def test_the_index_keeps_its_objects_themselves_and_refuses_writes() -> None:
    made = an_index()
    assert Index.__slots__ == (
        "name",
        "display_name",
        "kind",
        "schedule",
        "holiday_calendar",
        "conventions",
        "specifications",
        "reporting_lot",
    )
    field = "name"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(made, field, "other")


def test_making_an_index_changes_no_input_and_a_second_index_leaves_the_first() -> None:
    expiries_before = FUTURES.future_expiry.copy()
    holidays_before = HOLIDAYS.holiday.copy()
    lots_before = SPECIFICATIONS.lot_sizes.copy()
    codes_before = dataclasses.astuple(CONVENTIONS)
    first = an_index()
    second = an_index("Henry Hub NYMEX again")
    assert np.array_equal(FUTURES.future_expiry, expiries_before)
    assert np.array_equal(HOLIDAYS.holiday, holidays_before)
    assert np.array_equal(SPECIFICATIONS.lot_sizes, lots_before)
    assert dataclasses.astuple(CONVENTIONS) == codes_before
    assert first.name == "Henry Hub NYMEX" and second.name == "Henry Hub NYMEX again"
    assert first.schedule is second.schedule is FUTURES


# --- the general rule ---------------------------------------------------------


@given(
    name=st.text(min_size=1, max_size=30),
    kind=st.sampled_from(tuple(Kind)),
    count=st.integers(1, 6),
)
def test_any_kind_of_schedule_and_any_name_make_an_index_of_that_kind(
    name: str, kind: Kind, count: int
) -> None:
    schedule: object = {
        Kind.FUTURES: FUTURES,
        Kind.GAS_DAILY: GAS_DAILY,
        Kind.PUBLISHED: PUBLISHED,
    }[kind]
    specifications = contract_specifications(
        tuple(f"contract {i}" for i in range(count)),
        np.full(count, 1000.0),
        ("MMBTU",) * count,
        np.zeros(count),
        np.zeros(count),
        UNITS,
    )
    key = "NYMEX" if kind is Kind.FUTURES else None
    made = index(
        name,
        f"{name} index",
        schedule,
        CONVENTIONS,
        specifications,
        key,
        None,
        UNITS,
        CALENDARS,
        WorkCounter(),
    )
    assert made.name == name and made.kind is kind
    assert made.schedule is schedule
    assert made.holiday_calendar is (HOLIDAYS if kind is Kind.FUTURES else None)
    assert made.conventions is CONVENTIONS and made.specifications is specifications
    with pytest.raises(ValueError):
        index(
            name,
            f"{name} index",
            schedule,
            CONVENTIONS,
            specifications,
            None if key else "NYMEX",
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )


# --- the reporting lot, lot-delta-reporting.md ----------------------------------------------
# The ticket's ETE index: VOLUME in gallons, a LOT of a thousand barrels beside a barrel and a
# gallon of one each, quoted in cents a gallon and settled in dollars unless said.
ETE_SPECIFICATIONS = contract_specifications(
    ("LOT", "BBL", "GAL"),
    np.array([1000.0, 1.0, 1.0]),
    ("BBL", "BBL", "GAL"),
    np.zeros(3),
    np.zeros(3),
    UNITS,
)
ETE_FUTURES = futures_schedule(("X26", "Z26"), dates("2026-11-30", "2026-12-31"), None)


def ete(
    quote: tuple[str, str] = ("CENT", "GAL"),
    settled: str = "DOLLAR",
    reporting_lot: str | None = "LOT",
) -> Index:
    conventions = index_conventions(quote[0], quote[1], settled, "VOLUME", "GAL", UNITS)
    return index(
        "ETE",
        "Ethane - synthetic volume index",
        ETE_FUTURES,
        conventions,
        ETE_SPECIFICATIONS,
        "NYMEX",
        reporting_lot,
        UNITS,
        CALENDARS,
        WorkCounter(),
    )


def test_the_reporting_lot_is_resolved_once_into_its_quantity_and_its_coefficient() -> None:
    lot = ete().reporting_lot
    assert lot is not None
    assert (lot.specification, lot.name, lot.lot_size, lot.lot_unit) == (0, "LOT", 1000.0, "BBL")
    assert lot.quote_quantity == pytest.approx(42_000.0) and lot.coefficient == pytest.approx(420.0)
    assert lot.words == "lots of LOT (1000 BBL)"
    # The same lot in every quote and settlement unit: 42,000 gallons or a thousand barrels, and
    # the dollars or cents a live lot makes per unit of quote price.
    for quote, settled, quantity, coefficient in (
        (("DOLLAR", "GAL"), "DOLLAR", 42_000.0, 42_000.0),
        (("DOLLAR", "BBL"), "DOLLAR", 1_000.0, 1_000.0),
        (("CENT", "BBL"), "DOLLAR", 1_000.0, 10.0),
        (("CENT", "GAL"), "CENT", 42_000.0, 42_000.0),
    ):
        other = ete(quote, settled).reporting_lot
        assert other is not None
        assert other.quote_quantity == pytest.approx(quantity)
        assert other.coefficient == pytest.approx(coefficient)
    # A row that is not the first, a bare unit: the choice is the name's, nothing inferred.
    gallon = ete(reporting_lot="GAL").reporting_lot
    assert gallon is not None
    assert (gallon.specification, gallon.words) == (2, "lots of GAL (1 GAL)")
    assert gallon.coefficient == pytest.approx(0.01)


def test_an_index_made_without_a_reporting_lot_has_none() -> None:
    assert ete(reporting_lot=None).reporting_lot is None
    assert an_index().reporting_lot is None


@pytest.mark.parametrize("name", ["lot", " LOT", "LOTS", "", "MMBTU"])
def test_a_reporting_lot_names_one_of_the_specifications_exactly(name: str) -> None:
    with pytest.raises(ValueError) as failure:
        ete(reporting_lot=name)
    assert str(failure.value) == (
        f"reporting_lot is {name!r}, expected one of the specifications: 'LOT', 'BBL', 'GAL'"
    )


def test_a_reporting_lot_whose_quantity_outruns_the_largest_number_is_refused() -> None:
    huge = contract_specifications(
        ("LOT",), np.array([1e308]), ("BBL",), np.zeros(1), np.zeros(1), UNITS
    )
    conventions = index_conventions("CENT", "GAL", "DOLLAR", "VOLUME", "GAL", UNITS)
    with pytest.raises(ValueError) as failure:
        index(
            "ETE",
            "Ethane - synthetic volume index",
            ETE_FUTURES,
            conventions,
            huge,
            "NYMEX",
            "LOT",
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
    assert str(failure.value) == (
        "reporting_lot 'LOT' is inf GAL a lot, expected a finite quantity; the lot size outruns "
        "the largest number"
    )
    # The lot-unit rule comes first: an energy lot under volume conventions is named before any
    # lot is looked for.
    with pytest.raises(ValueError) as failure:
        index(
            "ETE",
            "Ethane - synthetic volume index",
            ETE_FUTURES,
            conventions,
            SPECIFICATIONS,
            "NYMEX",
            "LOT",
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
    assert str(failure.value).startswith("specifications row 1 lot_unit is 'MMBTU'")


# --- the display name, readable-index-names.md ---------------------------------------------------


def test_the_display_name_is_kept_as_typed_and_may_repeat_the_name() -> None:
    # A description beside the name, since #169: text as given, any case, spaces and all, the name
    # itself allowed, read by nothing here; the name and the kind stand as they were.
    assert an_index().display_name == "Henry Hub NYMEX index"
    for text in ("West Texas Intermediate crude oil - NYMEX", " spaced ", "Henry Hub NYMEX", "x"):
        made = index(
            "Henry Hub NYMEX",
            text,
            FUTURES,
            CONVENTIONS,
            SPECIFICATIONS,
            "NYMEX",
            None,
            UNITS,
            CALENDARS,
            WorkCounter(),
        )
        assert made.display_name == text and made.name == "Henry Hub NYMEX"
        assert made.kind is Kind.FUTURES
