"""A batch of cashflows, cashflow-instrument.md: known signed amounts in one currency, each on
its own explicit payment day, booked from a template of the cashflow instrument and a ticket's
rows as a batch of trades is from its template and ticket, with no index, schedule, quantity or
market. The economic facts are the amount, the currency and the payment day; beside them the
booking metadata, the trade date, the identifier, the counterparty and the description, labels
read for nothing. The rows are kept as booked, for reading back, and the amounts are summed once
per distinct payment day, for valuing: two payments on one day are one amount to discount, and
two on different days stay apart whatever they net to, since their factors differ.
docs/library/cashflows/create-cashflows.md is the page."""

from dataclasses import dataclass
from functools import partial
from typing import cast

import numpy as np
from numpy.typing import NDArray

from goosedove.cashflows.rules import currency_of, finite_amounts
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import CASHFLOW
from goosedove.instruments.fields import FieldValues
from goosedove.trades.template import TradeTemplate
from goosedove.trades.terms import whole_trade_ids

CASHFLOWS_BOOKED = "cashflows_booked"  # ticket rows completed and typed, one per payment booked
PAYMENT_DAYS_MAPPED = "payment_days_mapped"  # distinct payment days, the amounts summed on each


@dataclass(frozen=True, slots=True)
class Cashflows:
    """The batch as booked and as it is valued, every array read-only. Per row, in the ticket's
    order: trade_id, the source system's whole numbers, or None when neither the template nor
    the ticket supplied the field; trade_date; amount, signed, positive received and negative
    paid; payment_date; and counterparty and description, labels as typed, or None when not
    supplied; currency, the one word every row shares. Then per distinct payment day,
    increasing: payment_days and payment_amounts, the rows' amounts summed on each day, with
    day_of_row, each row's place among the days; and the payment-time axes a DV01 report is
    summed onto, static for the batch: months, the first day of each calendar month the days fall
    in, increasing, with month_of_day, and years likewise with year_of_month."""

    trade_id: NDArray[np.int64] | None
    trade_date: NDArray[np.datetime64]
    amount: NDArray[np.float64]
    currency: str
    payment_date: NDArray[np.datetime64]
    counterparty: tuple[str, ...] | None
    description: tuple[str, ...] | None
    payment_days: NDArray[np.datetime64]
    payment_amounts: NDArray[np.float64]
    day_of_row: NDArray[np.intp]
    months: NDArray[np.datetime64]
    month_of_day: NDArray[np.intp]
    years: NDArray[np.datetime64]
    year_of_month: NDArray[np.intp]

    @property
    def rows(self) -> int:
        return self.amount.size


def cashflows(ticket: FieldValues, template: TradeTemplate, counter: WorkCounter) -> Cashflows:
    """The one way to make Cashflows: the rules, checked in this order, the first failure being
    the message; then the amounts summed by payment day and the axes made.

    The template is of the cashflow instrument, a template of another refused by name, as the
    trades refuse a cashflow template; the ticket is bound against the template's instrument, which
    the seam did; no field is supplied by both, even to the same value; every required field,
    trade_date, amount, currency and payment_date, is present in one of them. The currency is
    USD exactly, the template's one value, read when the template was made, or a column every
    row holds, each distinct text read once in the order its first row comes and named with that
    row; so one batch holds one currency. The trade IDs, where supplied, are whole numbers of at
    most 15 digits, the kernel's rule and the trades' words, the first bad row named; each amount
    is finite, zero and fractions included, the first bad row named; a date and a label are what
    they are. A repeated row is a second payment; a zero amount is a row kept. Then the distinct
    payment days, one unique, and the amounts summed onto them, one bincount under numpy's flags
    down, a day's sum past the largest number refused by its day; and the months and the years
    those days fall in, two uniques, the places kept.

    Work: one cashflow per ticket row and one payment day per distinct day, reported to the
    counter; nothing per calendar day between, no curve or valuation date read.
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
    days, day_of_row = np.unique(payment_date, return_inverse=True)
    with np.errstate(over="ignore", invalid="ignore"):  # the rule below is the judge
        sums = np.bincount(day_of_row, weights=amount, minlength=days.size)
    outrun = ~np.isfinite(sums)
    if outrun.any():
        k = int(outrun.argmax())
        raise ValueError(
            f"the payments on {days[k]} sum to {float(sums[k])!r}, expected a finite amount of "
            f"{currency}; the rows' amounts, each finite, sum past the largest number"
        )
    month_keys, month_of_day = np.unique(days.astype("datetime64[M]"), return_inverse=True)
    year_keys, year_of_month = np.unique(month_keys.astype("datetime64[Y]"), return_inverse=True)
    months = month_keys.astype("datetime64[D]")
    years = year_keys.astype("datetime64[D]")
    arrays: tuple[NDArray[np.generic], ...] = (
        trade_date, amount, payment_date, days, sums, day_of_row, months, month_of_day, years,
        year_of_month,
    )  # fmt: skip
    for array in arrays:
        array.setflags(write=False)
    if trade_id is not None:
        trade_id.setflags(write=False)
    counter.hit(CASHFLOWS_BOOKED, fields.rows)
    counter.hit(PAYMENT_DAYS_MAPPED, int(days.size))
    return Cashflows(
        trade_id,
        trade_date,
        amount,
        currency,
        payment_date,
        counterparty,
        description,
        days,
        sums,
        day_of_row.astype(np.intp),
        months,
        month_of_day.astype(np.intp),
        years,
        year_of_month.astype(np.intp),
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
