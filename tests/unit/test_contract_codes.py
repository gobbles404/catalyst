"""Contract codes read for their month and year: the code of the month after, and the month as
CME's feeds spell it; one form taken, a month letter and two digits, and everything else refused
naming what arrived."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from goosedove.index_definitions.contract_codes import (
    MONTH_LETTERS,
    cme_code,
    code_of_month,
    first_day_of,
    month_and_year,
    next_contract,
)

# --- what a code names --------------------------------------------------------


def test_the_twelve_letters_are_the_months_in_order_and_the_digits_the_year_after_2000() -> None:
    assert MONTH_LETTERS == "FGHJKMNQUVXZ"
    assert [month_and_year(f"{letter}26") for letter in MONTH_LETTERS] == [
        (month, 2026) for month in range(1, 13)
    ]
    assert month_and_year("F00") == (1, 2000)
    assert month_and_year("Z99") == (12, 2099)
    assert month_and_year("f26") == month_and_year("F26") == (1, 2026)


# --- the next contract --------------------------------------------------------


@pytest.mark.parametrize(
    ("contract", "following"),
    [
        ("F26", "G26"),
        ("G26", "H26"),
        ("H26", "J26"),
        ("J26", "K26"),
        ("K26", "M26"),
        ("M26", "N26"),
        ("N26", "Q26"),
        ("Q26", "U26"),
        ("U26", "V26"),
        ("V26", "X26"),
        ("X26", "Z26"),
        ("Z26", "F27"),
        ("Z29", "F30"),
        ("Z98", "F99"),
        ("m26", "n26"),
        ("z26", "f27"),
        ("F00", "G00"),
    ],
    ids=[
        "January to February",
        "February to March",
        "March to April",
        "April to May",
        "May to June",
        "June to July",
        "July to August",
        "August to September",
        "September to October",
        "October to November",
        "November to December",
        "December to the next January",
        "across a decade",
        "the last year two digits name",
        "a lowercase code gives a lowercase code",
        "a lowercase December gives a lowercase January",
        "the year 2000",
    ],
)
def test_the_next_contract_is_the_month_after_in_the_code_given(
    contract: str, following: str
) -> None:
    assert next_contract(contract) == following


# --- the CME month ------------------------------------------------------------


@pytest.mark.parametrize(
    ("contract", "month"),
    [
        ("F26", "202601"),
        ("G26", "202602"),
        ("J26", "202604"),
        ("U26", "202609"),
        ("V26", "202610"),
        ("X26", "202611"),
        ("Z26", "202612"),
        ("f27", "202701"),
        ("F00", "200001"),
        ("Z99", "209912"),
    ],
    ids=[
        "January",
        "February, two digits",
        "April, J and not I",
        "September, U",
        "October, V",
        "November, X",
        "December",
        "a lowercase code, the same month",
        "the year 2000",
        "the last month two digits name",
    ],
)
def test_the_cme_month_is_the_year_then_the_month_as_text(contract: str, month: str) -> None:
    assert cme_code(contract) == month
    assert isinstance(cme_code(contract), str)


# --- what is refused ----------------------------------------------------------


@pytest.mark.parametrize(
    "contract",
    [
        "Cal27",
        "cal27",
        "W29",
        "Q1 27",
        "F2026",
        "F2",
        "F",
        "26",
        "26F",
        " F26",
        "F26 ",
        "F-26",
        "I26",
        "A26",
        "FF26",
        "F2a",
        "F²6",
    ],
    ids=[
        "a calendar strip",
        "a calendar strip in lowercase",
        "a winter strip",
        "a quarter",
        "a four-digit year",
        "a one-digit year",
        "a letter alone",
        "a year alone",
        "the year before the letter",
        "a leading space",
        "a trailing space",
        "a hyphen",
        "I, which the exchanges skip",
        "a letter that is no month",
        "two letters",
        "a letter among the digits",
        "a digit from another script",
    ],
)
def test_anything_but_a_month_letter_and_two_digits_is_refused_naming_it(contract: str) -> None:
    message = f"contract is {contract!r}, expected a month letter and a two-digit year, such as F26"
    with pytest.raises(ValueError) as failure:
        next_contract(contract)
    assert str(failure.value) == message
    with pytest.raises(ValueError) as failure:
        cme_code(contract)
    assert str(failure.value) == message


def test_december_2099_has_no_next_that_two_digits_can_name() -> None:
    for contract in ("Z99", "z99"):
        with pytest.raises(ValueError) as failure:
            next_contract(contract)
        assert str(failure.value) == (
            f"contract is {contract!r}, expected a month before December 2099, "
            "the last a two-digit year can name"
        )
    assert cme_code("Z99") == "209912"  # the month itself is named


# --- the general rule ---------------------------------------------------------


# Twelve steps from any contract reach the same letter a year on, each step one month later as
# the CME month counts it, and the month read back from the next code is the one after.
@given(month=st.integers(0, 11), year=st.integers(0, 97), lower=st.booleans())
def test_twelve_next_contracts_are_a_year_and_each_is_one_month_on(
    month: int, year: int, lower: bool
) -> None:
    letter = MONTH_LETTERS[month]
    code = (letter.lower() if lower else letter) + f"{year:02d}"
    walked = code
    for _ in range(12):
        following = next_contract(walked)
        before, after = month_and_year(walked), month_and_year(following)
        assert (after[0], after[1]) == ((before[0] % 12) + 1, before[1] + (before[0] == 12))
        assert int(cme_code(following)) - int(cme_code(walked)) in (
            1,
            89,
        )  # a month, or December to January
        assert following[0].islower() == lower
        walked = following
    assert walked == (letter.lower() if lower else letter) + f"{year + 1:02d}"


# --- the month a day falls in, and the first day of a code's month ------------------------


def day(text: str) -> np.datetime64:
    return np.datetime64(text, "D")


@pytest.mark.parametrize(
    ("date", "code"),
    [
        ("2026-01-01", "F26"),
        ("2026-01-15", "F26"),
        ("2026-01-31", "F26"),
        ("2026-02-28", "G26"),
        ("2028-02-29", "G28"),
        ("2026-05-19", "K26"),
        ("2026-06-22", "M26"),
        ("2026-07-21", "N26"),
        ("2026-12-31", "Z26"),
        ("2000-01-01", "F00"),
        ("2099-12-31", "Z99"),
        ("2030-04-10", "J30"),
    ],
    ids=[
        "the first of January",
        "the middle of January",
        "the last of January",
        "the last of February",
        "a leap day",
        "19 May, a WTI June expiry, is May's code and not June's",
        "22 June",
        "21 July",
        "the last day of a year",
        "the first day two digits name",
        "the last day two digits name",
        "April, J",
    ],
)
def test_the_code_of_a_day_is_its_months_in_capitals(date: str, code: str) -> None:
    assert code_of_month(day(date)) == code


@pytest.mark.parametrize(
    "date", ["1999-12-31", "1970-01-01", "1900-01-01", "2100-01-01", "2150-06-15"]
)
def test_a_day_outside_the_years_two_digits_name_is_refused(date: str) -> None:
    with pytest.raises(ValueError) as failure:
        code_of_month(day(date))
    assert str(failure.value) == (
        f"date is {date}, expected a day from 2000 to 2099, the years a two-digit code can name"
    )


@pytest.mark.parametrize(
    ("contract", "first"),
    [
        ("F26", "2026-01-01"),
        ("G28", "2028-02-01"),
        ("m26", "2026-06-01"),
        ("n26", "2026-07-01"),
        ("Z26", "2026-12-01"),
        ("F00", "2000-01-01"),
        ("Z99", "2099-12-01"),
    ],
    ids=[
        "January",
        "a leap February, the first all the same",
        "a lowercase June",
        "a lowercase July",
        "December",
        "the first month two digits name",
        "the last month two digits name",
    ],
)
def test_the_first_day_of_a_codes_month_is_a_date(contract: str, first: str) -> None:
    made = first_day_of(contract)
    assert made == day(first)
    assert made.dtype == np.dtype("datetime64[D]")


def test_a_code_that_is_no_single_contract_has_no_first_day() -> None:
    for contract in ("Cal27", "W29", "F2026", " F26"):
        with pytest.raises(ValueError) as failure:
            first_day_of(contract)
        assert str(failure.value) == (
            f"contract is {contract!r}, expected a month letter and a two-digit year, such as F26"
        )


# Any day of this century: its code's first day is the first of its own month, and the code of
# that first day is the code again, in capitals; the CME month of the code is the day's year and
# month.
@given(offset=st.integers(0, 36_524))
def test_any_day_of_the_century_round_trips_through_its_code(offset: int) -> None:
    date = day("2000-01-01") + np.timedelta64(offset, "D")
    code = code_of_month(date)
    first = first_day_of(code)
    assert first.astype("datetime64[M]") == date.astype("datetime64[M]")
    assert first == date.astype("datetime64[M]").astype("datetime64[D]")
    assert code_of_month(first) == code
    assert cme_code(code) == str(date.astype("datetime64[M]")).replace("-", "")
    assert code_of_month(first_day_of(code.lower())) == code
