# A concrete dense-matrix trade experiment

This is a small experiment for reviewing the representation, not a production valuation
engine. It leaves discounting out. Quantities below are already in barrels and prices in
USD per barrel. Futures rows calculate a price difference from the agreed trade price;
swap rows calculate projected payment amounts. They are not interchangeable cash balances
or a portfolio PV.

## What belongs to the trade

The trade remains a static record of the accepted deal. Its template supplies the shared
product, index, units and conventions. Its details supply the trade identity, trade date,
contract or averaging period, signed quantity, agreed price and payment terms.

Preparing that record resolves an observation schedule: precisely which prices enter the
payoff, and with which contractual weights. Two trades may share that schedule without
becoming one trade. No current market price or received fixing is written into the trade.

For this specimen, each trade has one component and refers to a shared schedule:

| Trade | Product | Schedule | Signed barrels | Agreed price |
|---|---|---|---:|---:|
| O001 | Future | Current CL F27 mark | 10,000 | 70.00 |
| O002 | Future | Current CL G27 mark | -4,000 | 71.00 |
| O003 | Asian swap | Four-observation average | 6,000 | 70.50 |
| O004 | Asian swap | The same four-observation average | -2,000 | 71.00 |
| O005 | Penultimate-style swap | The second F27 observation | -3,000 | 70.75 |

The four-observation average is deliberately a toy schedule: two F27 observations and
two G27 observations, each with weight 1/4. It is not a real monthly exchange calendar.
Likewise, the single-observation swap illustrates the shape of a penswap; these fixture
dates do not establish an exchange's penultimate settlement date.

## The full daily view

An observation key identifies an index/source, contract, observation kind and, for a
dated settlement, its date. Current marks and dated settlements are distinct observations.
Product names do not enter that identity: an Asian and a penswap can consume the same
dated settlement.

Columns are a flat list of the observations actually needed. We do not need a rectangle
of every contract against every date.

| Trade | F27 mark | G27 mark | F27 day 1 | F27 day 2 | G27 day 3 | G27 day 4 | Constant |
|---|---:|---:|---:|---:|---:|---:|---:|
| O001 | 10,000 | 0 | 0 | 0 | 0 | 0 | -700,000 |
| O002 | 0 | -4,000 | 0 | 0 | 0 | 0 | 284,000 |
| O003 | 0 | 0 | 1,500 | 1,500 | 1,500 | 1,500 | -423,000 |
| O004 | 0 | 0 | -500 | -500 | -500 | -500 | 142,000 |
| O005 | 0 | 0 | 0 | -3,000 | 0 | 0 | 212,250 |

The first six numeric columns form **A**, the dense exposure matrix. The last column is
**c**, the static constant vector. In this example, each constant is minus signed quantity
times agreed price.

The market supplies **x**, one price per observation in exactly that column order:

```text
x = [72, 73, 70, 72, 73, 73]
amounts = A @ x + c
        = [20,000, -8,000, 9,000, -2,000, -3,750]
```

For T components and O distinct observations:

```text
A: (T, O)     x: (O,)     c: (T,)     amounts: (T,)
```

One trade is simply T = 1. The numerical operation is unchanged. Each row retains its
trade/component identity, including duplicate occurrences. A multi-month strip can
contribute multiple component rows with a mapping back to the original deal.

## What the market contains

The full observation vector is the clearest interface for checking the arithmetic. It
can be built from a smaller set of current market points plus known fixings.

Here the two current points are CL F27 at 72 and CL G27 at 73. The first dated observation
has already fixed at 70. The remaining dated observations are projected using their
referenced contract's current price. That projection is an explicit modeling choice,
not an assertion that all those prices are the same economic observable.

| Observation | F27 coefficient | G27 coefficient | Known fixing offset |
|---|---:|---:|---:|
| F27 current mark | 1 | 0 | 0 |
| G27 current mark | 0 | 1 | 0 |
| F27 day 1, fixed | 0 | 0 | 70 |
| F27 day 2, projected | 1 | 0 | 0 |
| G27 day 3, projected | 0 | 1 | 0 |
| G27 day 4, projected | 0 | 1 | 0 |

The two coefficient columns form **B**; the last column is **k**. The compact current
market vector is **p**:

```text
p = [72, 73]
x = B @ p + k

B: (O, M)     p: (M,)     k: (O,)
```

The numeric arrays travel with their ordered observation/market-point identities. An
array of the right length with the wrong order is invalid. Fixing status is explicit;
a genuine zero fixing is valid, and missing data must fail.

The existing `Market` already uses a contract vector and a calendar mapping to provide
daily prices. This specimen keeps an explicit mapping because the current calendar and
history cover prompt-contract observations, not every possible historical contract/date
settlement needed by arbitrary trades.

## Compression is substitution

Substituting the market expression into the trade expression gives:

```text
amounts = A @ (B @ p + k) + c
        = (A @ B) @ p + (c + A @ k)

W = A @ B
b = c + A @ k
amounts = W @ p + b
```

The compressed representation is:

| Trade | F27 coefficient | G27 coefficient | Constant including known fixings |
|---|---:|---:|---:|
| O001 | 10,000 | 0 | -700,000 |
| O002 | 0 | -4,000 | 284,000 |
| O003 | 1,500 | 3,000 | -318,000 |
| O004 | -500 | -1,000 | 107,000 |
| O005 | -3,000 | 0 | 212,250 |

`W` has shape `(5, 2)`, instead of `A`'s `(5, 6)`. Both produce the same five results,
within floating-point tolerance. For O003, for example:

```text
full:       1,500 * (70 + 72 + 73 + 73) - 423,000 = 9,000
compressed: 1,500 * 72 + 3,000 * 73 - 318,000     = 9,000
```

This compression follows dependencies. Two distinct points that happen to have equal
prices are never merged. If two daily observations have separate projected prices, they
keep separate points in `p`; the representation still works, but may compress less.
If a product has its own traded monthly-average price, that is its own market point;
the representation must not automatically add historical fixings to it a second time.

Keep trade rows for individual results. If an aggregate of compatible amounts is wanted,
sum their coefficient rows and constants. The two Asian rows alone become
`1,000 * F27 + 2,000 * G27 - 211,000`, giving 7,000 here. Netting coefficients must not
discard constants, even when net quantity is zero. Payment dates and settlement treatment
remain attached to the original components for subsequent valuation.

## What changes and when

| Event | Trade and A/c | Market p | B/k and derived W/b |
|---|---|---|---|
| Current price changes | Unchanged | Update | Unchanged if projection unchanged |
| A dated observation fixes | Unchanged | Current prices may also move | Replace that projected observation with its fixing; rebuild derived compression |
| Projection model changes | Unchanged | Depends on model | Rebuild |
| Trade terms or contractual schedule change | Prepare again | Independent | Rebind and rebuild |

A fixing removes that dated observation's sensitivity to future prices. It does not
freeze the current futures mark. Its weight stays 1/4 in this example; the three
remaining observations are not renormalized to sum to one.

## Running the specimen

```powershell
uv run python -m tools.examples.linear_trade_matrices
```

The runnable experiment lives in `tools/examples/linear_trade_matrices.py`. It is kept
outside the production library so the object shapes can be changed after reviewing the
example. The existing NG Excel ingestion remains the first production trade surface.

The dense view is a correctness reference and an inspection surface. It does not establish
that materializing every dense intermediate is efficient for a large portfolio. The
experiment counts preparation, matrix work and array sizes; timing and memory profiling
on representative portfolios should guide a later choice of dense, indexed or sparse
storage. Exact compression here means algebraically equivalent, subject to ordinary
floating-point rounding, not bit-for-bit identical under every regrouping.
