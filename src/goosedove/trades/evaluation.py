"""The prepared batch evaluated against one market: the quotes of its live inputs read off the
market, aligned by schedule row, one multiplication and one addition for the mark; the cash as
the preparation settled it; delta by contract on the batch's own axis and its total, shared with
the preparation that settled them, since no tick changes them; and DV01, zero by the
undiscounted cleared model. One snapshot for the
batch as a whole, immutable, retained with everything that explains it.
docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import KERNEL, WorkCounter
from goosedove.market.market import Market
from goosedove.trades.preparation import Prepared
from goosedove.trades.terms import Route

LIVE_PRICES_READ = "live_prices_read"  # quotes read off the market, one per live input


@dataclass(frozen=True, slots=True)
class Results:
    """The preparation and the market, by reference, and the snapshot they make, read-only. The
    route and the currency name what the numbers are: for a cleared batch, mark is the
    undiscounted entry-to-current-price P&L of the inputs not yet settled, live at their quotes
    and fixed at their final prices, and cash the cumulative entry-to-final-price P&L of the
    inputs settled by the valuation date, both in the settlement currency. contracts is the
    batch's axis, the schedule rows of its inputs in the schedule's order, the same whatever has
    fixed; delta[m] is the change in mark for a move of one quote unit in contract m, the
    exposure where it is live and zero where it has fixed, in delta_unit, currency per quote
    currency per quote quantity unit, the preparation's own array shared and never written;
    delta_total is the change for a common move of one in every contract, the sum. dv01 is zero:
    the cleared model is undiscounted, so a rate move changes nothing, a result of the model and
    not a placeholder. as_of is the history's valuation day."""

    prepared: Prepared
    market: Market
    route: Route
    currency: str
    as_of: np.datetime64
    mark: float
    cash: float
    contracts: NDArray[np.intp]
    delta: NDArray[np.float64]
    delta_total: float
    dv01: float
    delta_unit: str

    def codes(self) -> tuple[str, ...]:
        """The axis spelled as the schedule spells its codes, one per contract of the batch."""
        schedule = self.prepared.encoded.terms.schedule
        return tuple([schedule.codes[int(row)] for row in self.contracts])


def results(prepared: Prepared, market: Market, counter: WorkCounter) -> Results:
    """The one way to make Results: two rules, checked once, in this order, the first failure
    being the message; then the quotes read, one kernel call, and the snapshot.

    The market is over the history the batch was prepared against, the one object: a market over
    another history, a new fixing or another valuation date, is refused, and the batch prepared
    again outside, never silently here. The route is cleared: a bilateral batch needs discount
    factors and a DV01 convention that are not built, so it is refused by name rather than valued
    as if undiscounted. Then the market answers the quotes of the live contracts, in the batch's
    order, and refuses by name a contract before or past its coverage, as it does for every
    reader; the live amount is the exposure times the quotes, one dot product; the mark adds the
    unsettled offsets and set amounts; the cash is the preparation's, and so are delta and its
    total, shared and not made again, since nothing a tick brings changes them.

    Work: one kernel call and one quote read per live input, reported to the counter; no fixing
    read, nothing per component, nothing of the encoding or the preparation done again.
    """
    encoded = prepared.encoded
    terms = encoded.terms
    if market.market_history is not prepared.history:
        name = market.market_history.calendar.index.name
        raise ValueError(
            f"market is over another history of index {name!r}, "
            "expected the one the trades were prepared against"
        )
    if terms.route is not Route.CLEARED:
        raise ValueError(
            f"route is {terms.route.value}, expected cleared; bilateral valuation needs discount "
            "factors and a DV01 convention, not built yet"
        )
    quotes = market.live_prices(prepared.live_contracts)
    counter.hit(LIVE_PRICES_READ, int(quotes.size))
    live = float(prepared.live_exposure @ quotes)
    counter.hit(KERNEL)
    conventions = terms.index.conventions
    return Results(
        prepared,
        market,
        terms.route,
        conventions.currency_unit,
        prepared.history.calendar.valuation_date.as_of,
        prepared.offset_unsettled + prepared.set_unsettled + live,
        prepared.cash,
        encoded.inputs,
        prepared.delta,
        prepared.delta_total,
        0.0,
        f"{conventions.currency_unit} per {conventions.quote_currency_unit}/"
        f"{conventions.quote_quantity_unit}",
    )
