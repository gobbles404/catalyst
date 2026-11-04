"""A collection of named discount curves, multiple-discount-curves.md: the curves as they are,
by reference, in the order given, each name once; no date read, nothing of the factors made or
combined. The seam's words and handles are test_globals.py."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_bilateral_kernel import A_YEAR, AS_OF, TWO_YEARS, curve_of

from catalyst.globals.discount_curve import DiscountCurve
from catalyst.globals.discount_curve_set import DiscountCurveSet, collect_discount_curves
from catalyst.instrumentation.work_counts import WorkCounter

SOFR = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90))
FFOIS = curve_of((AS_OF, 1.0), (A_YEAR, 0.96), (TWO_YEARS, 0.92), name="FFOIS")


def collected(*curves: DiscountCurve, counter: WorkCounter | None = None) -> DiscountCurveSet:
    return collect_discount_curves(curves, counter or WorkCounter())


def refused(*curves: DiscountCurve) -> str:
    counter = WorkCounter()
    with pytest.raises(ValueError) as caught:
        collect_discount_curves(curves, counter)
    assert counter.freeze().as_dict() == {}  # a refusal counts nothing
    return str(caught.value)


# --- what a collection is -------------------------------------------------------------------------


def test_a_collection_keeps_the_curves_as_given_in_order_by_reference() -> None:
    counter = WorkCounter()
    both = collected(FFOIS, SOFR, counter=counter)
    assert isinstance(both, DiscountCurveSet)
    assert both.curves == (FFOIS, SOFR)
    assert both.curves[0] is FFOIS and both.curves[1] is SOFR  # the objects, not copies
    assert both.names == ("FFOIS", "SOFR")
    assert counter.freeze().as_dict() == {"curves_collected": 2}
    assert collected(SOFR, FFOIS).names == ("SOFR", "FFOIS")  # the order given, never sorted


def test_a_collection_of_one_curve_is_a_collection() -> None:
    counter = WorkCounter()
    one = collected(SOFR, counter=counter)
    assert one.curves == (SOFR,) and one.names == ("SOFR",)
    assert counter.freeze().as_dict() == {"curves_collected": 1}


# No date is read: which curves must start on the valuation day and cover which payments is the
# evaluation's to decide for the curves a batch selects, so curves of any spans sit together.
def test_no_date_is_read_so_curves_of_any_spans_sit_in_one_collection() -> None:
    one_day = curve_of((AS_OF, 1.0), name="ONE_DAY")
    later = curve_of(("2029-01-04", 1.0), ("2030-01-04", 0.9), name="LATER")
    assert collected(SOFR, one_day, later).names == ("SOFR", "ONE_DAY", "LATER")


# Equal factors under different names are two curves, and a name is matched exactly, case and all.
def test_names_are_matched_exactly_so_equal_factors_or_a_different_case_are_other_curves() -> None:
    twin = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90), name="TWIN")
    lower = curve_of((AS_OF, 1.0), (A_YEAR, 0.95), (TWO_YEARS, 0.90), name="sofr")
    assert collected(SOFR, twin, lower).names == ("SOFR", "TWIN", "sofr")


def test_the_collection_is_frozen_and_the_curves_stand_as_they_were() -> None:
    both = collected(SOFR, FFOIS)
    field = "curves"  # named apart, so the assignment below stays a runtime fact to check
    with pytest.raises(AttributeError):
        setattr(both, field, ())  # a frozen record refuses the assignment
    assert both.curves[0].factors is SOFR.factors  # nothing copied
    assert not SOFR.factors.flags.writeable and not FFOIS.factors.flags.writeable


# --- each name once -------------------------------------------------------------------------------


# The first repeat is refused with the cell it repeats, the cells counted from one in the order
# the sheet gave them; the same curve given twice is a repeat too, as is a later snapshot of a name.
@pytest.mark.parametrize(
    ("curves", "message"),
    [
        (
            (SOFR, SOFR),
            "curve_handles cell 1 and cell 2 are both named 'SOFR', expected each name once",
        ),
        (
            (SOFR, FFOIS, curve_of((AS_OF, 1.0), (A_YEAR, 0.94))),
            "curve_handles cell 1 and cell 3 are both named 'SOFR', expected each name once",
        ),
        (
            (FFOIS, SOFR, FFOIS, SOFR),
            "curve_handles cell 1 and cell 3 are both named 'FFOIS', expected each name once",
        ),
        (
            (FFOIS, curve_of((AS_OF, 1.0), name="SOFR"), SOFR),
            "curve_handles cell 2 and cell 3 are both named 'SOFR', expected each name once",
        ),
    ],
    ids=["the same curve twice", "a later snapshot", "two names each twice", "a repeat not first"],
)
def test_a_repeated_name_is_refused_naming_the_first_repeat(
    curves: tuple[DiscountCurve, ...], message: str
) -> None:
    assert refused(*curves) == message


# --- the general rules ----------------------------------------------------------------------------


@given(count=st.integers(1, 30))
def test_any_distinct_names_collect_in_order_counting_each(count: int) -> None:
    names = [f"CURVE_{i}" for i in range(count)]
    curves = tuple(curve_of((AS_OF, 1.0), name=name) for name in names)
    counter = WorkCounter()
    both = collect_discount_curves(curves, counter)
    assert both.names == tuple(names)
    assert all(kept is given for kept, given in zip(both.curves, curves, strict=True))
    assert counter.freeze().as_dict() == {"curves_collected": count}


@given(names=st.lists(st.sampled_from(["A", "B", "C"]), min_size=2, max_size=8))
def test_any_repeat_is_refused_naming_the_first_repeat_and_the_cell_it_repeats(
    names: list[str],
) -> None:
    curves = tuple(curve_of((AS_OF, 1.0), name=name) for name in names)
    first_cell: dict[str, int] = {}
    repeat = None
    for i, name in enumerate(names):
        if name in first_cell:
            repeat = (first_cell[name] + 1, i + 1, name)
            break
        first_cell[name] = i
    if repeat is None:
        assert collected(*curves).names == tuple(names)
    else:
        earlier, later, name = repeat
        assert refused(*curves) == (
            f"curve_handles cell {earlier} and cell {later} are both named {name!r}, "
            "expected each name once"
        )
