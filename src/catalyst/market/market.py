"""The market: an index's history, its calendar with the price fixed on each period that has
fixed, and the quotes of the periods still to come, one per contract from the contract of the
first unfixed period on, in the schedule's order, through the schedule's last contract or
stopping before it; together the price on every priced period the quotes cover, the fixing
where the period has fixed and its contract's quote where it has not.
docs/library/market/market.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from catalyst.market.market_history import MarketHistory
from catalyst.market_data.price_vector import PriceVector


@dataclass(frozen=True, slots=True)
class Market:
    """The two objects the market was made from, kept by reference, and one number:
    first_contract is the row of the schedule whose contract the first unfixed period belongs
    to, counted from zero, so that the quote of the contract of any unfixed period the vector
    covers is price_vector.prices[calendar.contract[row] - first_contract], and the price on a
    fixed period is the history's fixing. The live-price coverage is the vector's own length,
    read and not held: it runs from first_contract through last_contract, which may come before
    the schedule's last. Nothing else is held: the periods, the contracts, the flags, the
    fixings and the quotes stay where they are."""

    market_history: MarketHistory
    price_vector: PriceVector
    first_contract: int

    @property
    def last_contract(self) -> int:
        """The row of the schedule of the last contract quoted, where the live-price coverage
        ends: the first contract and the vector's length, less one."""
        return self.first_contract + self.price_vector.prices.size - 1

    def live_prices(self, contracts: NDArray[np.intp]) -> NDArray[np.float64]:
        """The quotes of the contracts asked for, each a row of the schedule as the calendar's
        contract column holds it, in the order asked: the one place a live price is read, so
        the coverage rule is every reader's. A contract before the first one quoted or after
        the last is refused, the first such contract asked for being named, and never answered
        with another contract's quote: a row before the vector would otherwise count back from
        its end and return a wrong price with no failure at all, and a row past it would stop
        in NumPy's words.

        Live prices alone: the history's fixings are not looked at, and a contract before the
        coverage may have every period of its own fixed and priced there, so the words say the
        live-price coverage and not the market's. Which price a date takes, a fixing or a
        quote, is not answered here.
        """
        prices = self.price_vector.prices
        places = contracts - self.first_contract
        outside = (places < 0) | (places >= prices.size)
        if outside.any():
            codes = self.market_history.calendar.index.schedule.codes
            asked = int(contracts[int(outside.argmax())])  # the first asked for outside it
            if asked < self.first_contract:
                raise ValueError(
                    f"requested contract {codes[asked]!r} is before live-price coverage "
                    f"starting at {codes[self.first_contract]!r}"
                )
            raise ValueError(
                f"requested contract {codes[asked]!r} is beyond live-price coverage "
                f"ending at {codes[self.last_contract]!r}"
            )
        return prices[places]


def market(market_history: MarketHistory, price_vector: PriceVector) -> Market:
    """The one way to make a Market: three rules, checked once, in this order, the first
    failure being the message; then one number, and nothing built.

    The vector names the history's index: the text it was made with is the text the index
    was created with, compared exactly, so a vector labelled for another index is refused
    whatever its length, and another case or a space at the end is another name. The name
    is a label the sheet keeps, never a lookup: two indices of one name pass, and so does a
    column labelled wrongly, since the label is all the vector carries. Then the calendar
    has a period not yet fixed, since a market is the history with the quotes of
    the periods to come and a calendar fixed through its last period has nothing to quote. And
    the vector holds at least one price and at most one per contract from that period's
    contract through the schedule's last: the first price is that contract's, the prices after
    it follow the schedule's order with no contract skipped, and the vector may stop before the
    schedule does, so a schedule can run years past the quotes the desk has. The contracts
    whose periods have all fixed are not quoted, a contract is counted whether or not the
    calendar prices any of its remaining periods, and a vector with no price or with a price
    past the schedule's last contract is refused, never cut, repeated or filled in: no price
    would be a history alone, which is not a market. Which quote is which contract is the
    sheet's to keep right, and so is where a quote comes from; the count is all that can be
    checked here, and a count that fits says nothing of a vector left unchanged when the first
    contract rolled.

    The calendar's periods are in date order and the fixed side is before the valuation date
    or, for a Gas Daily flow day, on or before it, so the fixed periods come first and the row
    of the first unfixed one is the count of the fixed flags, which the calendar took once
    when it was made and holds: the market reads that row and the contract there, two reads,
    no count, no search, and no array made, whatever the calendar's length and the vector's.
    On a futures calendar that period is the valuation day and its contract the prompt; on a
    Gas Daily calendar the day after the valuation day, so the first quote is the balance of
    that month; on an IFERC calendar the first month whose index has not published. The two
    objects are kept as they are.
    """
    calendar = market_history.calendar
    if price_vector.index_name != calendar.index.name:
        raise ValueError(
            f"price_vector names index {price_vector.index_name!r}, "
            f"expected market_history's index {calendar.index.name!r}"
        )
    first = calendar.first_unfixed  # counted once when the calendar was made
    if first == calendar.dates.size:
        raise ValueError("market_history has no unfixed period, expected at least one to quote")
    first_contract = int(calendar.contract[first])
    codes = calendar.index.schedule.codes
    remaining = len(codes) - first_contract  # one or more: the first unfixed period's and on
    given = price_vector.prices.size
    if not 1 <= given <= remaining:
        bound = "at least 1" if given == 0 else f"at most {remaining}"
        raise ValueError(
            f"price_vector has {given} prices, expected {bound}, "
            f"one per contract from {codes[first_contract]!r} through {codes[-1]!r}"
        )
    return Market(market_history, price_vector, first_contract)
