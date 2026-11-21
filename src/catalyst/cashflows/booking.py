"""A batch of cashflows, cashflow-instrument.md: known signed amounts in one currency, each on
its own explicit payment day, booked from a template of the cashflow instrument and a ticket's
rows as a batch of trades is from its template and ticket, with no index, schedule, quantity or
market. The economic facts are the amount, the currency, the payment day and, since
cashflow-curve-keys.md, the key naming the curve the payment discounts on; beside them the
booking metadata, the trade date, the identifier, the counterparty and the description, labels
read for nothing. The rows are kept as booked, for reading back, and the amounts are summed once
per payment group, a payment day and a key, for valuing: two payments on one day under one key
are one amount to discount, and two on different days, or on one day under two keys, stay apart
whatever they net to, since their factors differ.
docs/library/cashflows/create-cashflows.md is the page."""

from dataclasses import dataclass
from functools import partial
from typing import cast

import numpy as np
from numpy.typing import NDArray

from catalyst.cashflows.rules import currency_of, finite_amounts
from catalyst.globals.discount_curve import curve_name
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import CASHFLOW
from catalyst.instruments.fields import FieldValues
from catalyst.trades.template import TradeTemplate
from catalyst.trades.terms import whole_trade_ids

CASHFLOWS_BOOKED = "cashflows_booked"  # ticket rows completed and typed, one per payment booked
PAYMENT_DAYS_MAPPED = "payment_days_mapped"  # distinct payment days, the batch's date axis
# Payment groups formed, a payment day and a key, the amounts summed in each, since
# cashflow-curve-keys.md.
PAYMENT_GROUPS_FORMED = "payment_groups_formed"


@dataclass(frozen=True, slots=True)
class Cashflows:
    """The batch as booked and as it is valued, every array read-only. Per row, in the ticket's
    order: trade_id, the source system's whole numbers, or None when neither the template nor
    the ticket supplied the field; trade_date; amount, signed, positive received and negative
    paid; payment_date; counterparty and description, labels as typed, or None when not
    supplied; and since cashflow-curve-keys.md discount_curve_key, the exact name of the curve
    the row's payment discounts on, the text alone and never a curve; currency, the one word
    every row shares. Then keys, the batch's distinct keys in the order the rows first name
    them. Then per payment group, a payment day and a key, in day order and within a day in key
    order, so that a batch on one key has one group a day: group_day, the group's place among
    payment_days; group_key, its key's place among keys; group_amounts, its rows' amounts
    summed; with group_of_row, each row's group. And the payment-time axes every curve's DV01
    is summed onto, static for the batch and shared by its keys: payment_days, the distinct
    payment days, increasing; months, the first day of each calendar month the days fall in,
    increasing, with month_of_day; and years likewise with year_of_month."""

    trade_id: NDArray[np.int64] | None
    trade_date: NDArray[np.datetime64]
    amount: NDArray[np.float64]
    currency: str
    payment_date: NDArray[np.datetime64]
    counterparty: tuple[str, ...] | None
    description: tuple[str, ...] | None
    discount_curve_key: tuple[str, ...]
    keys: tuple[str, ...]
    group_day: NDArray[np.intp]
    group_key: NDArray[np.intp]
    group_amounts: NDArray[np.float64]
    group_of_row: NDArray[np.intp]
    payment_days: NDArray[np.datetime64]
    months: NDArray[np.datetime64]
    month_of_day: NDArray[np.intp]
    years: NDArray[np.datetime64]
    year_of_month: NDArray[np.intp]

    @property
    def rows(self) -> int:
        return self.amount.size


def cashflows(ticket: FieldValues, template: TradeTemplate, counter: WorkCounter) -> Cashflows:
    """The one way to make Cashflows: the rules, checked in this order, the first failure being
    the message; then the amounts summed by payment group and the axes made.

    The template is of the cashflow instrument, a template of another refused by name, as the
    trades refuse a cashflow template; the ticket is bound against the template's instrument, which
    the seam did; no field is supplied by both, even to the same value; every required field,
    trade_date, amount, currency, payment_date and, since cashflow-curve-keys.md,
    discount_curve_key, is present in one of them. The currency is USD exactly, the template's
    one value, read when the template was made, or a column every row holds, each distinct text
    read once in the order its first row comes and named with that row; so one batch holds one
    currency. The trade IDs, where supplied, are whole numbers of at most 15 digits, the kernel's
    rule and the trades' words, the first bad row named; each amount is finite, zero and
    fractions included, the first bad row named; a date and a label are what they are. Each key
    is a curve's name by the curve's own rule, exact and with no whitespace around it, the
    template's one, read when the template was made, or the ticket's column, each distinct text
    read once and named with its first row; no curve is looked for here. A repeated row is a
    second payment; a zero amount is a row kept. Then the distinct payment days, one unique;
    the distinct keys in the order the rows first name them; the payment groups, the distinct
    pairs of day and key in day order, one unique more for a batch on several keys and the
    days themselves for a batch on one; and the amounts summed onto the groups, one
    bincount under numpy's flags down, a group's sum past the largest number refused by its
    day and its key, a group netting to zero kept as any other; and the months and the years
    the days fall in, two uniques, the places kept.

    Work: one cashflow per ticket row, one payment day per distinct day and one payment group
    per distinct day and key, reported to the counter; nothing per calendar day between, no
    curve or valuation date read.
    """
    fields = _booked(template, ticket)
    _the_required(fields)
    currency = _the_currency(fields)
    trade_id = (
        whole_trade_ids(fields.numbers("trade_id"), partial(fields.where, "trade_id"))
        if fields.has("trade_id")
        else None
    )
    amount = fields.numbers("amount")
    finite_amounts(amount, partial(fields.where, "amount"))
    trade_date = fields.dates("trade_date")
    payment_date = fields.dates("payment_date")
    counterparty = fields.texts("counterparty") if fields.has("counterparty") else None
    description = fields.texts("description") if fields.has("description") else None
    keyed, keys = _the_keys(fields)
    days, day_of_row = np.unique(payment_date, return_inverse=True)
    if len(keys) == 1:
        # One key: a group a day, the days' own places, nothing more sorted or placed.
        group_of_row = day_of_row
        group_day = np.arange(days.size, dtype=np.intp)
        group_key = np.zeros(days.size, dtype=np.intp)
    else:
        # A group is a day and a key: the pairs numbered day by day and key by key within a
        # day, so that their distinct numbers, sorted, are the groups in the record's order.
        place = {key: i for i, key in enumerate(keys)}
        key_of_row = np.array([place[key] for key in keyed], dtype=np.intp)
        pairs, group_of_row = np.unique(day_of_row * len(keys) + key_of_row, return_inverse=True)
        group_day, group_key = np.divmod(pairs, len(keys))
    with np.errstate(over="ignore", invalid="ignore"):  # the rule below is the judge
        sums = np.bincount(group_of_row, weights=amount, minlength=group_day.size)
    outrun = ~np.isfinite(sums)
    if outrun.any():
        g = int(outrun.argmax())
        raise ValueError(
            f"the payments on {days[group_day[g]]} on {keys[int(group_key[g])]} sum to "
            f"{float(sums[g])!r}, expected a finite amount of {currency}; the rows' amounts, each "
            "finite, sum past the largest number"
        )
    month_keys, month_of_day = np.unique(days.astype("datetime64[M]"), return_inverse=True)
    year_keys, year_of_month = np.unique(month_keys.astype("datetime64[Y]"), return_inverse=True)
    # The mappings as the record declares them, cast before they are frozen, so that the arrays
    # kept are the arrays frozen and no later cast hands back a writable copy.
    group_of_row = group_of_row.astype(np.intp, copy=False)
    group_day = group_day.astype(np.intp, copy=False)
    group_key = group_key.astype(np.intp, copy=False)
    month_of_day = month_of_day.astype(np.intp, copy=False)
    year_of_month = year_of_month.astype(np.intp, copy=False)
    months = month_keys.astype("datetime64[D]")
    years = year_keys.astype("datetime64[D]")
    arrays: tuple[NDArray[np.generic], ...] = (
        trade_date, amount, payment_date, group_day, group_key, sums, group_of_row, days, months,
        month_of_day, years, year_of_month,
    )  # fmt: skip
    for array in arrays:
        array.setflags(write=False)
    if trade_id is not None:
        trade_id.setflags(write=False)
    counter.hit(CASHFLOWS_BOOKED, fields.rows)
    counter.hit(PAYMENT_DAYS_MAPPED, int(days.size))
    counter.hit(PAYMENT_GROUPS_FORMED, int(group_day.size))
    return Cashflows(
        trade_id,
        trade_date,
        amount,
        currency,
        payment_date,
        counterparty,
        description,
        keyed,
        keys,
        group_day,
        group_key,
        sums,
        group_of_row,
        days,
        months,
        month_of_day,
        years,
        year_of_month,
    )


@dataclass(frozen=True, slots=True)
class _Booked:
    """Every field of the batch read from whichever of the two supplied it: the template's one
    value, the same on every row, or the ticket's column, one per row."""

    template: TradeTemplate
    ticket: FieldValues
    rows: int

    def has(self, name: str) -> bool:
        return name in self.template.names or self.ticket.has(name)

    def where(self, name: str, row: int) -> str:
        """A field named in a message: with the row when the ticket supplied it, since each row
        has its own value, and alone when the template did, since every row has the same."""
        if name in self.template.names:
            return name
        return f"{name} row {row + 1}"

    def numbers(self, name: str) -> NDArray[np.float64]:
        if name in self.template.names:
            return np.full(self.rows, float(cast(float, self.template.defaults[name])))
        return self.ticket.numbers(name)

    def dates(self, name: str) -> NDArray[np.datetime64]:
        if name in self.template.names:
            return np.full(self.rows, self.template.defaults[name], dtype="datetime64[D]")
        return self.ticket.dates(name)

    def texts(self, name: str) -> tuple[str, ...]:
        if name in self.template.names:
            return (cast(str, self.template.defaults[name]),) * self.rows
        return self.ticket.texts(name)


def _booked(template: TradeTemplate, ticket: FieldValues) -> _Booked:
    """The template's instrument the cashflow, the ticket bound against it, and the two
    disjoint."""
    if template.instrument is not CASHFLOW:
        raise ValueError(
            f"template is of instrument {template.instrument.name!r}, expected {CASHFLOW.name}, "
            "the one instrument whose cashflows are built"
        )
    if ticket.instrument is not template.instrument:
        raise ValueError(
            f"ticket is of instrument {ticket.instrument.name!r}, expected the template's, "
            f"{template.instrument.name!r}"
        )
    for name in ticket.names:
        if name in template.names:
            raise ValueError(
                f"{name} is supplied by the template and by the ticket, expected by one of them"
            )
    return _Booked(template, ticket, ticket.rows)


def _the_required(fields: _Booked) -> None:
    """Every field the definition requires, present in one of the two, in the definition's
    order."""
    for field in CASHFLOW.fields:
        if field.required and not fields.has(field.name):
            raise ValueError(
                f"{field.name} is missing, expected a value in the template or a column in the "
                "ticket"
            )


def _the_currency(fields: _Booked) -> str:
    """The batch's one currency: the template's value as read when the template was made, or
    the ticket's column, each distinct text read once in the order its first row comes."""
    texts = fields.texts("currency")
    if "currency" in fields.template.names:
        return texts[0]
    for text in dict.fromkeys(texts):
        currency_of(fields.where("currency", texts.index(text)), text)
    return texts[0]


def _the_keys(fields: _Booked) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The rows' keys, since cashflow-curve-keys.md: each row's key as typed, and the distinct
    keys in the order the rows first name them. The template's one key was read by the curve's
    name rule when the template was made and stands on every row, nothing looked at per row;
    the ticket's column is read here, each distinct text once by that rule and named with its
    first row."""
    name = "discount_curve_key"
    texts = fields.texts(name)
    if name in fields.template.names:
        return texts, texts[:1]
    keys = tuple(dict.fromkeys(texts))  # distinct, by first appearance
    for key in keys:
        curve_name(fields.where(name, texts.index(key)), key)
    return texts, keys
