"""Periods as the desk labels them: a contract month, F26; a quarter, 1Q27; since #NN a half-year,
1H27, January to June, and 2H27, July to December; a calendar year, CAL28; a winter, W29,
November to the March after; a summer, S28, April to October; and a range of two labels joined
by a hyphen, F26-Z28, from the first day of the left to the last day of the right. Each is read
for two months, numpy's month unit, its first month and the month after its last, from which its
first and its last calendar day follow by one conversion each. The balance
of any of them, BALZ26, runs from the valuation day the desk supplies, or from the label's first
day when that is later, to the label's last day, since #173; a period that ended before the
valuation day is refused. Text and a day in and one date out, no object and no handle here: the
worksheet functions read the day off a valuation-date handle and pass it in. The letters are read
in either case, by the owner's decision for these utilities.
docs/library/utilities/start-date.md holds the grammar."""

import numpy as np

from goosedove.index_definitions.contract_codes import DIGITS, LOWER_LETTERS, MONTH_LETTERS

# The forms a message offers, in the words the pages use.
FORMS = (
    "a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
)

# The months a strip covers: the quarter from its number, the half-year from January or July for
# six, the winter from November of its year for five months, the summer from April for seven,
# the calendar year from January for twelve.
MONTHS_IN_HALF = 6
MONTHS_IN_WINTER = 5
MONTHS_IN_SUMMER = 7
# The balance-of-period prefix, read once in either case: BALZ26, balcal26, BalX26-Z26.
BALANCE = "BAL"


def period_months(period: str) -> tuple[np.datetime64, np.datetime64]:
    """The first month of a period and the month after its last, read from its label.

    One label, or two joined by one hyphen: the whole expression is read whichever end is
    wanted, so asking for a start cannot hide an end that is no label. A range runs from the
    left label's first month to the right label's last, every month between them included, so
    W28-W29 covers the summer of 2029 as well as the two winters; the right label may start and
    end no earlier than the left, since a range that cut off part of either end would say so to
    nobody. Nothing is sorted or swapped. A BAL prefix is no label here: the contract codes of a
    ticket read through this and take no balance, which is the two date utilities' alone.
    """
    return _period_months(period, period)


def _period_months(expression: str, period: str) -> tuple[np.datetime64, np.datetime64]:
    """The reading, over the expression given, refusing in the name of the whole label as it
    arrived, which is the expression itself but for the balance of a period."""
    left, hyphen, right = expression.partition("-")
    first, after = _label_months(left, period)
    if hyphen:
        start, end = _label_months(right, period)
        if start < first or end < after:
            raise ValueError(
                f"period is {period!r}, expected range endpoints in chronological order"
            )
        after = end
    return first, after


def balance_of(period: str) -> str | None:
    """The label under a BAL prefix, or None when the period has none. One prefix, in either
    case, and the rest read as any label is: BALBALZ26 is refused as the label BALZ26 would be,
    BAL alone as the empty label, both naming the whole expression as it arrived."""
    return period[len(BALANCE) :] if period[: len(BALANCE)].upper() == BALANCE else None


def start_date(period: str, as_of: np.datetime64 | None = None) -> np.datetime64:
    """The first calendar day of the period: the first month's first day, or for the balance of
    a period the later of the valuation day and that first day, since #173, the day the deal
    covers from, a period that has ended refused; for an ordinary label a day given is read for
    nothing, so one formula serves a column of both."""
    label = balance_of(period)
    if label is None:
        first, _ = period_months(period)
        return first.astype("datetime64[D]")
    first, after = _period_months(label, period)
    return _balance_from(
        as_of,
        first.astype("datetime64[D]"),
        after.astype("datetime64[D]") - np.timedelta64(1, "D"),
        period,
    )


def end_date(period: str, as_of: np.datetime64 | None = None) -> np.datetime64:
    """The last calendar day of the period, the day before the month after its last begins, so
    a February's own length and a winter's March of the next year, or the next century, fall out
    of numpy's month unit with nothing counted by hand; the balance of a period ends on the same
    day, its valuation day checked here too, so that asking for an end cannot hide a period that
    has ended or a balance asked for without its day."""
    label = balance_of(period)
    first, after = period_months(period) if label is None else _period_months(label, period)
    last = after.astype("datetime64[D]") - np.timedelta64(1, "D")
    if label is not None:
        _balance_from(as_of, first.astype("datetime64[D]"), last, period)
    return last


def _balance_from(
    as_of: np.datetime64 | None, first: np.datetime64, last: np.datetime64, period: str
) -> np.datetime64:
    """The first day the balance of a period covers, since #173: the valuation day given, since
    the balance of a period starts on no day the label names, and the later of it and the
    label's first day, so a future period is the whole period and a current one runs from the
    day itself; a period that ended before the valuation day is refused naming the label, the
    day and the end, never a one-day deal at the month's end. A Saturday is a day like any other:
    no business-day rule applies here, the schedule method choosing the pricing days later."""
    if as_of is None:
        raise ValueError(
            f"valuation_date is missing, expected a valuation-date handle with {period!r}, "
            "whose day starts the balance of a period"
        )
    if as_of > last:
        raise ValueError(
            f"valuation_date is {as_of}, after {period!r} ended on {last}, expected a valuation "
            "day on or before the period's last day"
        )
    return max(as_of, first)


def _label_months(label: str, period: str) -> tuple[np.datetime64, np.datetime64]:
    """One label's first month and the month after its last: a month letter and two digits, a
    quarter number, Q and two digits, since #NN a half number, 1 or 2, H and two digits, CAL and
    two digits, W or S and two digits, the letters in either case and the two digits the year
    after 2000. H and two digits alone is March, the contract month, as it always was: a half
    leads with its number as a quarter does. Anything else, a space, a one-digit year, a fifth
    quarter, a third half, an empty end of a range or a second hyphen among them, is refused,
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
    elif len(head) == 2 and head[0] in "12" and head[1] in "Hh":
        first = np.datetime64(f"{year}-{MONTHS_IN_HALF * (int(head[0]) - 1) + 1:02d}", "M")
        return first, first + np.timedelta64(MONTHS_IN_HALF, "M")
    elif len(head) == 3 and head[0] in "Cc" and head[1] in "Aa" and head[2] in "Ll":
        first = np.datetime64(f"{year}-01", "M")
        return first, first + np.timedelta64(12, "M")
    raise _malformed(period)


def _malformed(period: str) -> ValueError:
    return ValueError(f"period is {period!r}, expected {FORMS}")
