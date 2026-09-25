"""The market: an index's history, its calendar with the settle fixed on each past business day,
and the current futures prices, one quote per contract from the valuation day's prompt through
the last; together the price on every business day of the calendar, the fixing where the day
has fixed and the prompt contract's quote where it has not. docs/library/market/market.md is
the page."""

from dataclasses import dataclass

import numpy as np

from goosedove.market.market_history import MarketHistory
from goosedove.market_data.price_vector import PriceVector


@dataclass(frozen=True, slots=True)
class Market:
    """The two objects the market was made from, kept by reference, and one number:
    first_contract is the row of the futures schedule whose contract is prompt on the valuation
    day, counted from zero, so that the quote of the contract prompt on any business day from
    the valuation day on is price_vector.prices[calendar.contract[row] - first_contract], and the
    price on a past business day is the history's fixing. Nothing else is held: the days, the
    prompts, the flags, the fixings and the quotes stay where they are."""

    market_history: MarketHistory
    price_vector: PriceVector
    first_contract: int


def market(market_history: MarketHistory, price_vector: PriceVector) -> Market:
    """The one way to make a Market: two rules, checked once, in this order, the first failure
    being the message; then one number, and nothing built.

    The valuation date lies within the calendar's days, the first and the last included: a
    calendar that starts after it or ends before it has no day whose prompt contract the first
    quote could be, and nothing here extends a calendar or guesses an earlier contract. And the
    vector holds exactly one price per contract from the valuation day's prompt through the
    schedule's last, in the schedule's order: the contracts expired before the valuation day are
    not quoted, the one expiring on it is, a contract is counted whether or not the market is
    open on any of its remaining days, and a price too many or too few is refused, never
    dropped, repeated or filled in. Which quote is which contract is the sheet's to keep right;
    the count is all that can be checked here.

    The valuation day's row is its day count from the calendar's first day, the calendar's days
    being consecutive, and its prompt row is read there: one subtraction and one read, no
    search, and no array made. The two objects are kept as they are.
    """
    calendar = market_history.calendar
    dates = calendar.dates
    as_of = calendar.valuation_date.as_of
    if as_of < dates[0] or as_of > dates[-1]:
        raise ValueError(
            f"market_history valuation date is {as_of}, "
            f"expected a date from {dates[0]} through {dates[-1]}"
        )
    valuation_row = int(
        (as_of - dates[0]) // np.timedelta64(1, "D")
    )  # the calendar's days are consecutive
    first_contract = int(calendar.contract[valuation_row])
    codes = calendar.schedule.codes
    expected = len(codes) - first_contract
    given = price_vector.prices.size
    if given != expected:
        raise ValueError(
            f"price_vector has {given} {'price' if given == 1 else 'prices'}, expected {expected}, "
            f"one per contract from {codes[first_contract]!r} through {codes[-1]!r}"
        )
    return Market(market_history, price_vector, first_contract)
