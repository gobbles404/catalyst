"""The market: an index's history, its calendar with the price fixed on each period that has
fixed, and the quotes of the periods still to come, one per contract from the contract of the
first unfixed period through the last; together the price on every priced period of the
calendar, the fixing where the period has fixed and its contract's quote where it has not.
docs/library/market/market.md is the page."""

from dataclasses import dataclass

import numpy as np

from goosedove.market.market_history import MarketHistory
from goosedove.market_data.price_vector import PriceVector


@dataclass(frozen=True, slots=True)
class Market:
    """The two objects the market was made from, kept by reference, and one number:
    first_contract is the row of the schedule whose contract the first unfixed period belongs
    to, counted from zero, so that the quote of the contract of any unfixed period is
    price_vector.prices[calendar.contract[row] - first_contract], and the price on a fixed
    period is the history's fixing. Nothing else is held: the periods, the contracts, the
    flags, the fixings and the quotes stay where they are."""

    market_history: MarketHistory
    price_vector: PriceVector
    first_contract: int


def market(market_history: MarketHistory, price_vector: PriceVector) -> Market:
    """The one way to make a Market: two rules, checked once, in this order, the first failure
    being the message; then one number, and nothing built.

    The calendar has a period not yet fixed, since a market is the history with the quotes of
    the periods to come and a calendar fixed through its last period has nothing to quote. And
    the vector holds exactly one price per contract from that period's contract through the
    schedule's last, in the schedule's order: the contracts whose periods have all fixed are
    not quoted, a contract is counted whether or not the calendar prices any of its remaining
    periods, and a price too many or too few is refused, never dropped, repeated or filled in.
    Which quote is which contract is the sheet's to keep right, and so is where a quote comes
    from; the count is all that can be checked here.

    The calendar's periods are in date order and the fixed side is before the valuation date
    or, for a Gas Daily flow day, on or before it, so the fixed periods come first and the row
    of the first unfixed one is the count of the fixed flags: one count and one read, no
    search, and no array made. On a futures calendar that period is the valuation day and its
    contract the prompt; on a Gas Daily calendar the day after the valuation day, so the first
    quote is the balance of that month; on an IFERC calendar the first month whose index has
    not published. The two objects are kept as they are.
    """
    calendar = market_history.calendar
    fixed = int(np.count_nonzero(calendar.is_fixed))  # the fixed periods come first
    if fixed == calendar.dates.size:
        raise ValueError("market_history has no unfixed period, expected at least one to quote")
    first_contract = int(calendar.contract[fixed])
    codes = calendar.schedule.codes
    expected = len(codes) - first_contract
    given = price_vector.prices.size
    if given != expected:
        raise ValueError(
            f"price_vector has {given} {'price' if given == 1 else 'prices'}, expected {expected}, "
            f"one per contract from {codes[first_contract]!r} through {codes[-1]!r}"
        )
    return Market(market_history, price_vector, first_contract)
