"""The prepared batch evaluated against one market: the quotes of its live references read off
the market once each, gathered onto the live slots and multiplied by their exposure, one
multiplication and one sum for the live amount, which the unsettled offsets and set amounts
complete into the mark; the cash as the preparation settled it; the risk by reference on the
batch's own axis, the price sensitivity in the settlement currency and the delta in lots of the
index's reporting lot with its total, shared with the preparation that settled them, since no
tick changes them; and DV01, zero by the undiscounted cleared model. One snapshot for the batch
as a whole,
immutable, retained with everything that explains it, the dated live contributions among it.
docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import KERNEL, WorkCounter
from goosedove.market.market import Market
from goosedove.trades.preparation import PreparedTrades
from goosedove.trades.terms import Route

LIVE_PRICES_READ = "live_prices_read"  # quotes read off the market, one per live reference


@dataclass(frozen=True, slots=True)
class TradeResults:
    """The preparation and the market, by reference, and the snapshot they make, read-only. The
    route and the currency name what the numbers are: for a cleared batch, mark is the
    undiscounted entry-to-current-price P&L of the groups not yet settled, live slots at their
    references' quotes and fixed slots at their settles, and cash the cumulative
    entry-to-final-price P&L of the groups settled by the valuation date, both in the settlement
    currency. dated_live_contribution[i] is live slot i's exposure times its reference's quote,
    paired with the preparation's live_slot; their sum is the live amount, and they allocate
    neither the offsets nor the mark among dates. contracts is the batch's axis, the schedule
    rows of its references in the schedule's order, the same whatever has fixed;
    price_sensitivity[r] is the change in mark for a move of one quote unit in contract r, the
    live exposure referencing it and zero where every slot of it has fixed, in
    price_sensitivity_unit, currency per quote currency per quote quantity unit; lot_delta[r] is
    the exposure still to price in contract r counted in lots of the index's reporting
    specification, the sensitivity over the lot's coefficient, in lot_unit, `lots of LOT (1000
    BBL)`, and lot_delta_total their sum, the number the risk report shows as the delta; the
    three arrays are the preparation's own, shared and never written. dv01 is zero: the cleared
    model is undiscounted, so a rate move changes nothing, a result of the model and not a
    placeholder. as_of is the history's valuation day."""

    prepared: PreparedTrades
    market: Market
    route: Route
    currency: str
    as_of: np.datetime64
    mark: float
    cash: float
    dated_live_contribution: NDArray[np.float64]
    contracts: NDArray[np.intp]
    price_sensitivity: NDArray[np.float64]
    price_sensitivity_unit: str
    lot_delta: NDArray[np.float64]
    lot_delta_total: float
    lot_unit: str
    dv01: float

    def codes(self) -> tuple[str, ...]:
        """The axis spelled as the schedule spells its codes, one per contract of the batch."""
        schedule = self.prepared.encoded.terms.schedule
        return tuple([schedule.codes[int(row)] for row in self.contracts])


def trade_results(prepared: PreparedTrades, market: Market, counter: WorkCounter) -> TradeResults:
    """The one way to make TradeResults: two rules, checked once, in this order, the first failure
    being the message; then the quotes read, one kernel call, and the snapshot.

    The market is over the history the batch was prepared against, the one object: a market over
    another history, a later valuation date or a corrected fixing, is refused, and the batch is
    prepared again outside, never silently here. The route is cleared: a bilateral batch is
    refused by name, since its value needs discount factors and a DV01 convention that are not
    built, and valuing it as if undiscounted would be a wrong number without a word.

    The market answers the quotes of the live references in the batch's order, one per distinct
    contract, and refuses a contract past its coverage by name, as it does for every reader; the
    quotes are gathered onto the live slots, each slot's exposure times its reference's quote is
    its contribution, and the live amount is their sum. The mark is the unsettled offsets and set
    amounts plus the live amount; the cash is the preparation's. The sensitivity, the lot delta
    and its total are the preparation's, shared, and the lot's words the index's.

    Work: one kernel call, one quote per live reference, reported to the counter; nothing of the
    encoding or the preparation is done again, and nothing per slot but the gather and the
    multiplication over the live ones.
    """
    terms = prepared.encoded.terms
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
    quotes = market.live_prices(prepared.live_references)
    dated_live_contribution = (
        prepared.dated_live_exposure[prepared.live_slot] * quotes[prepared.reference_of_live_slot]
    )
    live = float(dated_live_contribution.sum())
    counter.hit(KERNEL)
    counter.hit(LIVE_PRICES_READ, int(prepared.live_references.size))
    dated_live_contribution.setflags(write=False)
    conventions = terms.index.conventions
    return TradeResults(
        prepared,
        market,
        terms.route,
        conventions.currency_unit,
        prepared.history.calendar.valuation_date.as_of,
        prepared.offset_unsettled + prepared.set_unsettled + live,
        prepared.cash,
        dated_live_contribution,
        prepared.encoded.references,
        prepared.price_sensitivity,
        f"{conventions.currency_unit} per {conventions.quote_currency_unit}/"
        f"{conventions.quote_quantity_unit}",
        prepared.lot_delta,
        prepared.lot_delta_total,
        terms.reporting_lot.words,
        0.0,
    )
