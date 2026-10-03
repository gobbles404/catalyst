"""Periods as the desk labels them: a contract month, F26; a quarter, 1Q27; a calendar year,
CAL28; a winter, W29, November to the March after; a summer, S28, April to October; and a range
of two labels joined by a hyphen, F26-Z28, from the first day of the left to the last day of the
right. Each is read for two months, numpy's month unit, its first month and the month after its
last, from which its first and its last calendar day follow by one conversion each. Text in and
one date out, no object and no handle; the letters are read in either case, by the owner's
decision for these utilities. docs/library/utilities/start-date.md holds the grammar."""

import numpy as np

from goosedove.index_definitions.contract_codes import DIGITS, LOWER_LETTERS, MONTH_LETTERS

# The forms a message offers, in the words the pages use.
FORMS = "a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28"

# The months a strip covers: the quarter from its number, the winter from November of its year
# for five months, the summer from April for seven, the calendar year from January for twelve.
MONTHS_IN_WINTER = 5
MONTHS_IN_SUMMER = 7


def period_months(period: str) -> tuple[np.datetime64, np.datetime64]:
    """The first month of a period and the month after its last, read from its label.

    One label, or two joined by one hyphen: the whole expression is read whichever end is
    wanted, so asking for a start cannot hide an end that is no label. A range runs from the
    left label's first month to the right label's last, every month between them included, so
    W28-W29 covers the summer of 2029 as well as the two winters; the right label may start and
    end no earlier than the left, since a range that cut off part of either end would say so to
    nobody. Nothing is sorted or swapped.
    """
    left, hyphen, right = period.partition("-")
    first, after = _label_months(left, period)
    if hyphen:
        start, end = _label_months(right, period)
        if start < first or end < after:
            raise ValueError(
                f"period is {period!r}, expected range endpoints in chronological order"
            )
        after = end
    return first, after


def start_date(period: str) -> np.datetime64:
    """The first calendar day of the period, the first month's first day."""
    first, _ = period_months(period)
    return first.astype("datetime64[D]")


def end_date(period: str) -> np.datetime64:
    """The last calendar day of the period, the day before the month after its last begins, so
    a February's own length and a winter's March of the next year, or the next century, fall out
    of numpy's month unit with nothing counted by hand."""
    _, after = period_months(period)
    return after.astype("datetime64[D]") - np.timedelta64(1, "D")


def _label_months(label: str, period: str) -> tuple[np.datetime64, np.datetime64]:
    """One label's first month and the month after its last: a month letter and two digits, a
    quarter number, Q and two digits, CAL and two digits, W or S and two digits, the letters in
    either case and the two digits the year after 2000. Anything else, a space, a one-digit
    year, a fifth quarter, an empty end of a range or a second hyphen among them, is refused,
    naming the whole expression as it arrived."""
    if len(label) < 3 or label[-2] not in DIGITS or label[-1] not in DIGITS:
        raise _malformed(period)
    year = 2000 + int(label[-2:])
    head = label[:-2]
    if len(head) == 1:
        place = MONTH_LETTERS.find(head) if head in MONTH_LETTERS else LOWER_LETTERS.find(head)
        if place >= 0:
            first = np.datetime64(f"{year}-{place + 1:02d}", "M")
            return first, first + np.timedelta64(1, "M")
        if head in "Ww":
            first = np.datetime64(f"{year}-11", "M")
            return first, first + np.timedelta64(MONTHS_IN_WINTER, "M")
        if head in "Ss":
            first = np.datetime64(f"{year}-04", "M")
            return first, first + np.timedelta64(MONTHS_IN_SUMMER, "M")
    elif len(head) == 2 and head[0] in "1234" and head[1] in "Qq":
        first = np.datetime64(f"{year}-{3 * (int(head[0]) - 1) + 1:02d}", "M")
        return first, first + np.timedelta64(3, "M")
    elif len(head) == 3 and head[0] in "Cc" and head[1] in "Aa" and head[2] in "Ll":
        first = np.datetime64(f"{year}-01", "M")
        return first, first + np.timedelta64(12, "M")
    raise _malformed(period)


def _malformed(period: str) -> ValueError:
    return ValueError(f"period is {period!r}, expected {FORMS}")
