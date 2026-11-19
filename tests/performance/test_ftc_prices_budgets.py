"""What a request's fit-to-curve prices cost, ftc-monthly-prices.md: the saved request's own
prices read as its quote reads them and nothing of the period, the observations or the payments
made again; no curve bound and no factor read; one pass of rounding over the components and
five reductions whatever the request; the peak within the quote's own. The request is the
request budgets' year of 2027 on the quote budgets' CAL index valued in June."""

from collections.abc import Callable
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray
from test_quote_budgets import CLEARED, MARKET, RATES
from test_rfq_budgets import PATH, counted, made, on_the_sheet
from test_seam_allocation import SLACK, least_peak

from catalyst.excel import bridge
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.quoting.ftc_prices import ftc_prices
from catalyst.quoting.rfq import quote_rfq

CallProfile = Callable[[Callable[[], object]], dict[str, int]]
AGREED = 40.0


def test_the_prices_read_what_the_quote_reads_and_no_curve() -> None:
    # The year in June, as its quote reads it: 118 fixings and seven live contracts once each;
    # five reductions and twelve prices rounded; no curve selected and no factor read, on the
    # bilateral request as on the cleared one. A month the same but for its counts.
    saved = made()
    assert counted(lambda c: ftc_prices(MARKET, saved, AGREED, 2, c)) == {
        "fixings_read": 118,
        "live_prices_read": 7,
        "price_reductions": 5,
        "prices_rounded": 12,
    }
    assert counted(lambda c: ftc_prices(MARKET, made(12, CLEARED), AGREED, 2, c)) == counted(
        lambda c: ftc_prices(MARKET, saved, AGREED, 2, c)
    )
    quote = counted(lambda c: quote_rfq(MARKET, saved, "ftc", RATES, c))
    assert quote == {
        "curves_selected": 1,
        "fixings_read": 118,
        "live_prices_read": 7,
        "price_reductions": 4,
    }


# The functions the prices run, once each whatever the request: the market held to the request's
# index, the components' own prices by the quote's own step, the shares, the rounding and its
# reading of the digits a cell shows, the check's reading and the components' words; nothing of
# the curve, the factors or the request's making.
LEDGER = {
    "ftc_prices": 1,
    "on_its_index": 1,
    "component_prices": 1,
    "calendar_rows": 1,
    "_the_prices": 1,
    "MarketHistory.fixed_prices": 1,
    "Market.live_prices": 1,
    "shares": 1,
    "rounded": 1,
    "as_shown": 2,  # the prices in steps, and the average beside the agreed price
    "period_words": 1,
    "WorkCounter.__init__": 1,
    "WorkCounter.hit": 4,
}


def test_a_month_and_a_year_are_priced_through_the_same_functions_once(
    call_profile: CallProfile,
) -> None:
    month, year = made(1), made(12)
    assert call_profile(lambda: ftc_prices(MARKET, month, AGREED, 2, WorkCounter())) == LEDGER
    assert call_profile(lambda: ftc_prices(MARKET, year, AGREED, 2, WorkCounter())) == LEDGER
    assert not {"the_curve", "_the_factors", "factors_on", "priced", "rfq"} & set(LEDGER)


@pytest.mark.parametrize(("n", "observations"), [(1, 21), (12, 261)], ids=["a month", "a year"])
def test_the_prices_allocate_within_the_quotes_own_bound(n: int, observations: int) -> None:
    saved = made(n)
    assert least_peak(lambda: ftc_prices(MARKET, saved, AGREED, 2, WorkCounter())) <= (
        2_000 + 55 * observations + SLACK
    )


def test_the_seam_spills_the_prices_resolving_two_handles_and_publishing_nothing(
    call_profile: CallProfile,
) -> None:
    market, saved, _, _, _ = on_the_sheet()
    live = bridge.live_handles()
    kinds, slots, _ = cast(
        tuple[NDArray[np.uint8], NDArray[np.float64], str],
        PATH["_QuoteFTCPrices"](market, saved, 1.15, 2.0),
    )
    assert kinds.shape == (7, 4) and slots[5:, 3].tolist() == [1.0, 1.2]
    assert call_profile(lambda: PATH["_QuoteFTCPrices"](market, saved, 1.15, 2.0)) == {
        "Registered.run": 1,
        "_arguments": 1,
        "_validate": 4,  # the two handles, the price and the decimals
        "_text": 2,  # each handle cell's text
        "_resolve": 2,
        "_number": 2,  # the price, and the decimals read as a number before they are held whole
        "_whole": 1,
        "_QuoteFTCPrices": 1,
        **LEDGER,
        "ftc_prices_table": 1,
        "_mixed_out": 1,  # the table sent by its kinds, slots and texts
        "_bad_mixed": 1,  # and held to what a cell may hold, one look
    }
    assert bridge.live_handles() == live
