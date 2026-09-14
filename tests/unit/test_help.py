"""Function and argument help: the words beside each declaration, as Excel is told them."""

from typing import Annotated, cast

import pytest

from goosedove.excel import bridge
from goosedove.excel.bridge import Date, MixedArray, NumberColumn, excel_function, register
from goosedove.excel.probes import probe

SPECS = {
    name: (description, arguments, hidden)
    for name, description, arguments, hidden in bridge.function_specs()
}


# --- the three listed functions, exactly: this is the text the desk reads ----------------


def test_the_valuation_date_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["CreateValuationDate"]
    assert not hidden
    assert description == (
        "Creates a valuation-date handle from a date and the fraction of that day elapsed."
    )
    assert arguments == [
        ("as_of", "One date, from 1-Mar-1900 to 31-Dec-9999, with no time of day."),
        (
            "day_fraction_elapsed",
            "One number from 0 to 1: 0 is the start of as_of, 1 its end. "
            "The date is kept as given.",
        ),
    ]


def test_the_curve_creator_explains_itself() -> None:
    description, arguments, hidden = SPECS["CreateDiscountCurve"]
    assert not hidden
    assert description == (
        "Creates a daily discount-curve handle. Its last date is the latest the library prices."
    )
    assert arguments == [
        (
            "header_row",
            "One row holding the two headers, date and discount_factor, in either order; capitals "
            "do not matter.",
        ),
        (
            "table",
            "The body under the headers: one row per calendar day, the date and its discount "
            "factor, no day missing. The first factor is 1, and factors never rise and stay "
            "above 0.",
        ),
    ]


def test_the_reader_explains_itself() -> None:
    description, arguments, hidden = SPECS["util_ReadDiscountFactor"]
    assert not hidden
    assert description == "Reads the discount factor for one day from a discount-curve handle."
    assert arguments == [
        ("curve", "The cell holding a discount-curve handle, or a name for that cell."),
        ("date", "One date between the curve's first and last dates, inclusive."),
    ]


# --- what registration derives from the signature ---------------------------------------


def test_an_optional_argument_is_bracketed_and_says_what_omission_takes() -> None:
    _, arguments, hidden = SPECS["Times"]
    assert hidden
    assert arguments == [
        ("x", "One number to multiply."),
        ("[factor]", "One multiplier. 1 when omitted."),
    ]


def test_a_hidden_function_may_say_nothing() -> None:
    _, arguments, _ = SPECS["Add"]
    assert arguments == [("a", ""), ("b", "")]


# A date and a column default as the seam takes them: a serial, and one number for a one-cell range.
A_SERIAL = cast(Date, 46164.0)
ONE_WEIGHT = cast(NumberColumn, 2.0)
A_CELL = cast(MixedArray, 5.0)


@probe
def Defaults(
    number: Annotated[float, "A number."] = 1.0,
    fraction: Annotated[float, "A fraction."] = 0.05,
    whole: Annotated[int, "A whole number."] = 3,
    label: Annotated[str, "Text."] = "WTI",
    flag: Annotated[bool, "A flag."] = True,
    day: Annotated[Date, "A date."] = A_SERIAL,
    weights: Annotated[NumberColumn, "Weights."] = ONE_WEIGHT,
) -> float:
    return number


def test_a_default_is_shown_in_the_words_of_the_sheet() -> None:
    _, arguments, _ = {
        name: (description, arguments, hidden)
        for name, description, arguments, hidden in bridge.function_specs()
    }["Defaults"]
    assert arguments == [
        ("[number]", "A number. 1 when omitted."),
        ("[fraction]", "A fraction. 0.05 when omitted."),
        ("[whole]", "A whole number. 3 when omitted."),
        ("[label]", 'Text. "WTI" when omitted.'),
        ("[flag]", "A flag. TRUE when omitted."),
        ("[day]", "A date. 2026-05-22 when omitted."),
        ("[weights]", "Weights. 2 when omitted."),
    ]


# --- what registration refuses, on a function Excel lists ----------------------------------


def test_a_listed_function_without_a_docstring_refuses_to_register() -> None:
    def Mute(x: Annotated[float, "A number."]) -> float:
        return x

    with pytest.raises(TypeError, match="Mute has no docstring; a function Excel lists says what"):
        excel_function(Mute)
    assert register(Mute, hidden=True) is Mute


def test_a_listed_argument_without_help_refuses_to_register() -> None:
    def Quiet(x: float) -> float:
        """Says nothing of x."""
        return x

    with pytest.raises(TypeError, match="Quiet: x has no help; a function Excel lists says what"):
        excel_function(Quiet)
    assert register(Quiet, hidden=True) is Quiet


def test_anything_but_one_text_beside_the_type_refuses_to_register() -> None:
    def Loud(x: Annotated[float, "a", "b"]) -> float:
        """Two texts."""
        return x

    def Numbered(x: Annotated[float, 3]) -> float:
        """A number instead of a text."""
        return x

    with pytest.raises(TypeError, match=r"Loud: x declares .*, expected one text beside the type"):
        excel_function(Loud)
    with pytest.raises(TypeError, match=r"Numbered: x declares .*, expected one text beside the"):
        excel_function(Numbered)


def test_help_longer_than_excel_shows_refuses_to_register() -> None:
    def Long(x: Annotated[float, "a" * 254]) -> float:
        """Too much to say of x."""
        return x

    def Wordy(x: Annotated[float, "A number."]) -> float:
        return x

    Wordy.__doc__ = "w" * 254
    with pytest.raises(TypeError, match="Long: x's help is 254 characters, expected at most 253"):
        excel_function(Long)
    with pytest.raises(TypeError, match="Wordy's description is 254 characters, expected at most"):
        excel_function(Wordy)


def test_a_default_the_help_cannot_show_refuses_to_register() -> None:
    def Shown(values: Annotated[MixedArray, "Cells."] = A_CELL) -> float:
        return 1.0

    with pytest.raises(
        TypeError, match=r"Shown: values defaults to .*, which the help cannot show"
    ):
        register(Shown, hidden=True)
