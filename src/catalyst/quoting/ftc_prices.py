"""The fit-to-curve prices of a saved request, ftc-monthly-prices.md: the bridge from the one
price a desk agrees with a customer back to the fixed price of each component, a month or a
window, that the deal is booked at. The request is the one a quote prices, rfq.py, so each
component's own price and its share are formed as `_QuoteRFQ` forms them, request.py, and
nothing is worked out a second way:

    curve_i  = each component's own price          as the quote has it
    ftc      = sum(share_i * curve_i)              the request's fit-to-curve quote
    fixed_i  = round(curve_i + (price - ftc))      the same amount on every component
    average  = sum(share_i * fixed_i)              what the fixed prices come back to
    difference = average - price

the rounding the sheet's own ROUND, and the average and the difference read to the fifteen
significant digits a cell shows, so that prices that tie say zero and not the sixteenth digit's
dust. No factor of any curve is read, a fit-to-curve price discounting nothing. The fixed prices are
not fitted to the agreed price: each is rounded alone, the average and its difference from the
agreed price are shown beside them, and what is done about a difference is the desk's.
docs/library/quoting/quote-ftc-prices.md is the page."""

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market import Market
from catalyst.quoting.request import PRICE_REDUCTIONS, component_prices, shares
from catalyst.quoting.rfq import Rfq, on_its_index
from catalyst.trades.terms import period_words

PRICES_ROUNDED: Final = "prices_rounded"  # the fixed prices rounded, one per component
MOST_DECIMALS: Final = 15  # the digits a cell shows of a number, so the most a price can be held to
# A price in steps of the allowed decimals holds a digit at that place while it is below this,
# fifteen digits, the digits a cell shows.
_FIFTEEN_DIGITS: Final = 1e15
# The powers of ten a reading to fifteen digits scales by, each read from its own decimal text
# and so exact, where a power computed at run time need not be.
_TENS: Final = np.array([float(f"1e{k}") for k in range(23)])


@dataclass(frozen=True, slots=True)
class FtcPrices:
    """A request's fit-to-curve prices at an agreed price, read-only: the agreed price as given;
    the average of the fixed prices, each at its component's share, and its difference from the
    agreed price, the average less the agreed, both as a cell shows them, to fifteen
    significant digits; and per component in the request's order its
    period in words, a contract code or a window's two dates, the quantity the average weighs
    it by, its own price on the curve and its fixed price at the allowed decimals."""

    agreed: float
    average: float
    difference: float
    period: tuple[str, ...]
    quantity: NDArray[np.float64]
    curve_price: NDArray[np.float64]
    fixed_price: NDArray[np.float64]


def ftc_prices(
    market: Market, request: Rfq, price: float, decimals: int, counter: WorkCounter
) -> FtcPrices:
    """A saved request's fit-to-curve prices on a market at an agreed price, the rules in this
    order, the first failure being the message: the decimals from 0 to 15; the market's index
    the request's, the one object, before any data is gathered; each component's own price as
    the quote forms it, a physical request's contracts not yet expired; the request's
    fit-to-curve quote, the shares of the quantities alone, to the last digit the number
    `_QuoteRFQ` gives under ftc; the same amount on every component, the agreed price less that
    quote, a shifted price past the largest number refused; each shifted price rounded alone to
    the allowed decimals, rounded; then the average of the fixed prices by the same shares and
    its difference from the agreed price, each read to the fifteen significant digits a cell
    shows before the one is taken from the other: a component's own price is a sum of weighted
    observations and carries the sixteenth digit's dust, so that prices which tie to the cent
    would otherwise differ by 4e-16, and a check that says so is no check. No curve is taken
    and no factor read. Work: the fixings and the live prices read, as a quote's; five
    reductions, the components' prices, the largest weight's exponent, the weights, the quote
    and the average; and the prices rounded, one per component."""
    if not 0 <= decimals <= MOST_DECIMALS:
        raise ValueError(
            f"decimals is {decimals}, expected a whole number from 0 to {MOST_DECIMALS}, the "
            "decimals a fixed price may hold"
        )
    on_its_index(market, request)
    saved = request.request
    curve = component_prices(saved, market, counter)
    share = shares(saved.quantity, np.ones(curve.size))
    quote = float((share * curve).sum())
    with np.errstate(over="ignore", invalid="ignore"):  # the rule below is the judge
        shifted = curve + (price - quote)
    outrun = ~np.isfinite(shifted)
    if outrun.any():
        k = int(outrun.argmax())
        raise ValueError(
            f"price is {price!r}, expected a price the request's own can be moved to; "
            f"{saved.component(k)} at {float(curve[k])!r}, moved by the price less the "
            f"fit-to-curve quote of {quote!r}, outruns the largest number"
        )
    fixed = rounded(shifted, decimals)
    counter.hit(PRICES_ROUNDED, fixed.size)
    average, agreed = as_shown(np.array([float((share * fixed).sum()), price])).tolist()
    counter.hit(PRICE_REDUCTIONS, 5)
    period = saved.period
    words = period_words(
        saved.schedule.codes, period.contract, period.window, period.first, period.last
    )
    for column in (curve, fixed):
        column.setflags(write=False)
    return FtcPrices(
        price, average, average - agreed, tuple(words.tolist()), saved.quantity, curve, fixed
    )


def rounded(price: NDArray[np.float64], decimals: int) -> NDArray[np.float64]:
    """Each price at the allowed decimals as the sheet's own ROUND gives it, so that a cell of
    `=ROUND(curve + shift, decimals)` beside the result agrees with it: the price in steps of
    the allowed decimals, read to the fifteen significant digits a cell shows, as_shown, and a
    half step then taken away from zero. The reading is what makes 4.515 at two decimals 4.52:
    the number a cell holds for 4.515 is a hair under it, and its nearest hundredth by the bits
    alone is 4.51, which no one reading the sheet would call rounded. A price already too large
    to hold a digit at the allowed decimals, fifteen digits or more of steps, is left as it is,
    and a result of zero is zero and never minus zero. One pass over the array, no step per
    price."""
    step = _TENS[decimals]
    with np.errstate(over="ignore"):  # a product past the largest number holds no such digit
        steps = price * step
    held = np.abs(steps) < _FIFTEEN_DIGITS  # false for a product past the largest number too
    whole = np.floor(np.abs(as_shown(np.where(held, steps, 0.0))) + 0.5)
    return np.where(held, np.copysign(whole, steps) / step + 0.0, price)


def as_shown(number: NDArray[np.float64]) -> NDArray[np.float64]:
    """Each number read to the fifteen significant digits a cell shows of it, the nearest number
    of that many digits: its size scaled by the power of ten that brings fifteen digits before
    the point, rounded to a whole number and scaled back, both by an exact power, so that the
    result is the number a cell would hold for those digits typed. The power is 14 less the
    size's own power of ten, from none to the last exact power, which only a size below 1e-8
    would pass and such a size is read to twenty-two decimals instead; a magnitude one off
    beside an exact power of ten reads fourteen or sixteen digits, the same number. A number of
    fifteen digits or more before the point is left as it is, and zero is zero."""
    size = np.abs(number)
    held = size < _FIFTEEN_DIGITS
    inside = np.where(held, size, 0.0)
    magnitude = np.floor(np.log10(np.where(inside > 0, inside, 1.0)))
    scale = _TENS[np.clip(14 - magnitude, 0, _TENS.size - 1).astype(np.intp)]
    return np.where(held, np.copysign(np.rint(inside * scale) / scale, number), number)
