"""Contract codes as the desk types them, a month letter and a two-digit year, F26 for January
2026: the code of the month after, the month as CME's data feeds spell it, 202601, the code of
the month a day falls in and the first day of a code's month. Text or one date in, text or one
date out, no object and no handle; and the months of a schedule's codes, one read per code, for
the trades' resolution and the contract-price interpolation. docs/library/utilities/next-fut.md,
fut-to-cme.md, date-to-fut.md and fut-to-date.md are the pages."""

from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.iferc_schedule import IfercSchedule

# The exchanges' month letters, January to December, and the same in lowercase, the two
# spellings a code's letter is read in; the ten digits a year is written with.
MONTH_LETTERS = "FGHJKMNQUVXZ"
LOWER_LETTERS = MONTH_LETTERS.lower()
DIGITS = "0123456789"


def month_and_year(contract: str) -> tuple[int, int]:
    """The month, 1 to 12, and the year, 2000 to 2099, a code names: the letter's place among
    the twelve and the two digits after 2000, since the desk's codes are of this century. One
    month letter, in either case, F26 and f26 naming one month, and two digits, nothing before,
    between or after: the one form taken, three looks at three characters and no pattern. A
    strip, a season or a year, Cal27, W29, Q1 27, is no single contract, a four-digit year,
    F2026, is another spelling than the desk's codes use, and I is no month letter; each is
    refused naming what arrived and the form wanted."""
    if len(contract) == 3 and contract[1] in DIGITS and contract[2] in DIGITS:
        letter = contract[0]
        place = (
            MONTH_LETTERS.find(letter) if letter in MONTH_LETTERS else LOWER_LETTERS.find(letter)
        )
        if place >= 0:
            return place + 1, 2000 + int(contract[1:])
    raise ValueError(
        f"contract is {contract!r}, expected a month letter and a two-digit year, such as F26"
    )


def next_contract(contract: str) -> str:
    """The code of the month after the one given, the next in the exchanges' sequence: G26 after
    F26, F27 after Z26, the letter in the case the code was typed, a lowercase code giving a
    lowercase code. Z99 has no next that two digits can name, and is refused rather than wrapped
    to F00, which would read as January 2000."""
    month, year = month_and_year(contract)
    if month == 12 and year == 2099:
        raise ValueError(
            f"contract is {contract!r}, expected a month before December 2099, "
            "the last a two-digit year can name"
        )
    letter = MONTH_LETTERS[month % 12]  # the month after, January after December
    year = year + 1 if month == 12 else year
    return (letter if contract[0].isupper() else letter.lower()) + f"{year % 100:02d}"


def cme_code(contract: str) -> str:
    """The month as CME's data feeds spell it, the year then the month, two digits each for the
    month, 202601 for F26 and 202612 for Z26: text, since it names a month and is not a number
    to add to."""
    month, year = month_and_year(contract)
    return f"{year}{month:02d}"


def code_of_month(day: np.datetime64) -> str:
    """The code of the month a day falls in, F26 for any day of January 2026, the letter in
    capitals, since a day carries no case to keep. The day is read as the count of months since
    January 1970, one conversion as numpy counts them, and the year and the month fall out of
    that count; a day before 2000 or after 2099 names no year two digits can write, and is
    refused."""
    years, month = divmod(int(day.astype("datetime64[M]").astype(np.int64)), 12)
    year = 1970 + years
    if not 2000 <= year <= 2099:
        raise ValueError(
            f"date is {day}, expected a day from 2000 to 2099, the years a two-digit code can name"
        )
    return f"{MONTH_LETTERS[month]}{year % 100:02d}"


def first_day_of(contract: str) -> np.datetime64:
    """The first day of the month a code names, 1 January 2026 for F26, as a date: the one day
    a code names on its own, a contract's expiry being its schedule's to say."""
    month, year = month_and_year(contract)
    return np.datetime64(f"{year}-{month:02d}-01", "D")


def schedule_months(schedule: FuturesSchedule | IfercSchedule) -> NDArray[np.int64]:
    """The month of every code of the schedule, as numpy counts months, one read per code: a
    code that is no contract code is refused by row, and so are two rows for one month, since a
    month resolved to two rows would name no contract. The resolution reads them once,
    resolves the ticket's periods against them and hands them to the terms, which keep them for
    the encoding's contract-month axes since #186; since #198 the contract-price interpolation
    reads them once to place its anchors and the months between."""
    codes = schedule.codes
    months = np.empty(len(codes), dtype=np.int64)
    for i, code in enumerate(codes):
        try:
            month, year = month_and_year(code)
        except ValueError:
            raise ValueError(
                f"index schedule row {i + 1} is {code!r}, expected a contract code, "
                "a month letter and a two-digit year such as F26"
            ) from None
        months[i] = (year - 1970) * 12 + month - 1
    order = np.argsort(months, kind="stable")
    by_month = months[order]
    same = np.flatnonzero(by_month[1:] == by_month[:-1])
    if same.size:
        a, b = int(order[same[0]]), int(order[same[0] + 1])
        raise ValueError(
            f"index schedule rows {a + 1} and {b + 1} are {codes[a]!r} and {codes[b]!r}, "
            f"both {month_label(by_month[same[0]])}, expected one contract per month"
        )
    return months


def month_label(count: object) -> str:
    """A month as numpy counts them, written as the sheet reads one: 2027-04."""
    return str(np.datetime64(int(cast(Any, count)), "M"))
