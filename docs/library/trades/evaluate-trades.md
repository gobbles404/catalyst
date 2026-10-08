# _EvaluateTrades

Built in #141 as ticket I5 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), with [_PrepareTrades](prepare-trades.md), [_ReportValues](report-values.md) and [_ReportRisk](report-risk.md); the design is [evaluation](../../engineering-tickets/trade-valuation-pipeline/04-evaluation.md) and [results](../../engineering-tickets/trade-valuation-pipeline/05-results.md).

Prepared trades evaluated against one market: one quote per live contract read off the market, a contract's payment groups sharing it, gathered onto the live slots and multiplied by their exposure for the live amount, which the unsettled offsets and set amounts complete into the mark; the cash as the preparation settled it; delta by contract and its total, the preparation's, shared; DV01, zero by the undiscounted cleared model. One immutable snapshot for the batch as a whole, retained with the dated contributions that explain it. Creating one is the tick: a new market over the same preparation makes new results and does nothing of the preparation or the encoding again, and the old results stand. The kernel's `trade_results` does the work, [kernel.md](kernel.md); the code is `src/goosedove/excel/trades.py`.

## Worksheet contract

```python
def _EvaluateTrades(
    prepared: Handle[PreparedTrades],
    market: Handle[Market],
) -> Handle[TradeResults]: ...
```

| | A | B |
|---|---|---|
| 11 | `=_PrepareTrades(A10, I11)` | shows `30512:prepared_trades:Henry Hub NYMEX:43` |
| 12 | `=_EvaluateTrades(A11, I12)` | shows `30512:trade_results:Henry Hub NYMEX:45`, I12 the market over the history in I11 quoting Z26 at 3.20 and F27 at 3.50, the two handles beside the index in I3 and outside the reports' spills, A13:D15 and A17:E19 |

Two handles, both required, neither with a default: the prepared trades, the cell showing `_PrepareTrades`'s result or a name for it, and the market over the history they were prepared against, the cell showing `_CreateMarket`'s result or a name for it, with the day's quotes. The seam resolves the two handles and nothing else; a cell of another kind fails in the seam's words, `prepared is trades handle '30512:trades:Henry Hub NYMEX:41', expected prepared trades handle`. The result is a handle, `30512:trade_results:Henry Hub NYMEX:45`, named for the index. A successful call publishes results and changes neither input; a recalculation with the same arguments shares the live results; a new market makes new results and the old are released when Excel disconnects their last creator, a report referring to the old cell holding them meanwhile.

## Excel help

| Item | Text |
|---|---|
| Function | Evaluates prepared trades against one market, the live observations at their contracts' quotes and the fixed at their settles, into the batch's mark, cash and delta, and shows its handle, the text the two reports take as the results. |
| prepared | The prepared-trades handle: the cell showing _PrepareTrades's result, such as A11, or a name for it. |
| market | The market handle over the history the trades were prepared against: the cell showing _CreateMarket's result, such as I12, or a name for it, with the day's quotes. |

## The library checks

The kernel's rules, in [kernel.md](kernel.md)'s words after `#ERROR _EvaluateTrades: ValueError:`.

| Rule | Refused as |
|---|---|
| The market is over the history the batch was prepared against, the one object; a later history is a new preparation, never a silent one here | `market is over another history of index 'Henry Hub NYMEX', expected the one the trades were prepared against` |
| The route is cleared; bilateral valuation needs discount factors and a DV01 convention | `route is bilateral, expected cleared; bilateral valuation needs discount factors and a DV01 convention, not built yet` |
| Every live contract is quoted, the market's own rule | `requested contract 'F27' is beyond live-price coverage ending at 'Z26'` |

The quotes carry no labels, as [market.md](../market/market.md#when-the-first-contract-rolls) records: the first price is the first unfixed contract's and the rest follow the schedule. A batch prepared again after the valuation date rolls past a contract's expiry takes the first quote for the next contract, so a vector left in place across the roll values the batch's live contracts at the quotes of the contracts before them, and nothing refuses it unless the vector reached the schedule's end, where it is now a price too many. Move the vector with the date, as the lifetime's `valuation` group does on a sheet after walking into the refusal, since #155; labels for the vector are deferred work, recorded under [Accepted constraints](../../engineering-tickets/trade-valuation-pipeline/README.md#accepted-constraints).

Under an averaging method, `last3day` and `asian`, a live price is the projection of the contract's remaining unfixed days at one common price, and the history supplies the daily prices being averaged: the market performs no conversion from a quote of the whole month's average, which is not that projection once a day has fixed, and the delta is to the projection input, not to such a quote, since #158, [asian-trades.md](../../engineering-tickets/trade-valuation-pipeline/asian-trades.md).

For the NG example on 24 November 2026 at 3.20 and 3.50: a mark of 7,000 USD, no cash, delta 160,000 and -50,000 USD per USD/MMBTU, total 110,000; at 3.21 the mark is 8,600 and the delta unchanged. For the toy on 30 November, Z26 fixed at 3.23 and paid, F27 at 3.50: a mark of -11,000 and cash of 22,800; its seven states are the example page's table, and [kernel.md](kernel.md) has them with the quotes and fixings read.

## What it retains

The preparation and the market by reference; the route, the currency and the valuation day; the mark and the cash; per live slot its dated contribution, exposure times its contract's quote, allocating neither the offsets nor the mark among dates; the batch's contract axis with the preparation's delta and total, shared and never written; DV01 and the units. Fees are reserves and appear in no number.

## Reading it back

The two reports spill the scalars, [report-values.md](report-values.md) and [report-risk.md](report-risk.md). `util_ReadHandle` spills the dated contents, one row per slot: `contract_code`, `observation_date`, for a financial settlement `payment_date`, the day the slot's payment group pays, since #162, `is_fixed`, `live_exposure` and `live_contribution`, the slot's own, zero where fixed, and `contract_delta`, the contract's delta read by each slot's reference and so the same number on every slot of one contract, whatever group holds it, named for whose it is: in the daily toy after 1 December fixes the slots show 0, 10 and 10 of exposure beside 20 of contract delta on each. The NG example spills Z26 with 160,000, 512,000 and 160,000 and F27 with -50,000, -175,000 and -50,000.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_trade_valuation.py` | the NG example's results, their handle, the reports and the reader; a tick making new results over the same preparation while the old stand at 7,000; one trade through the same path; the toy's seven states with the page's total column as typed and, since #148, the 27th between the fixing and the payment, the 26th closed, its fixed and paid contract read back and its fully fixed batch reporting its cash with no live exposure, and a corrected history of the same day refused until prepared again; the PHH pen's three states, its tick, its corrected fixing, the underlying's final settle moved and the pen unmoved, the long and the short and their sum, and the WTI pen's thousand-barrel lots; since #152 the pen strip batch of R1's acceptance list on the sheet, a strip, its duplicate and a signed lot through six states with the delta read contract by contract, the rows reversed and the singletons summed alike, and the batch's rows, amounts and payment days read back; the seam's refusals in order and the library's, another history's market, a bilateral route; since #162 two payment days on one contract through the ticket's six states, the old results standing on a tick, the singletons summed in every state and order and matching days compressing into one group |
| `tests/performance/test_trade_valuation_budgets.py` | a tick resolves two handles and runs `trade_results` and `Market.live_prices` once each, nothing of the preparation or the encoding, the same at five trades and at two thousand; 1,144 bytes at 2,500 trades |
| `tools/excel_smoke.ps1`, the host's `CallTests.cs`, `tools/excel_lifetime.ps1 -Groups trades,valuation`, `workbooks/handles.xlsx` | the chain on a sheet, from the host, through a price tick with the preparation reused; since #155, a second evaluation over equal prices sharing the results and, through a tick, keeping the old results alive and readable at their old mark while the live mark moves, the copy cleared releasing them; the valuation day moved onto n26's expiry and past it, the results remade; the two-price vector left in place across the roll refused, the results failing with the market and the reports showing the failure and no number, until the vector is trimmed to the contract that remains; and at the foot of the handles sheet, B1303 and the toy's seven states in J1342 to J1348; since #162 the payment-groups block, A paid and B not on 7 December, -30 of mark beside 180 of cash, the results read back with each slot's payment day and the contract's delta of nothing |

## Not here

No bilateral value, discount factor or DV01 beyond the cleared model's zero; no per-trade value, the batch being the unit; no scenario or bump, which is a new market and a new evaluation; no selective recalculation on a tick, the whole batch's live slots being gathered and multiplied, which is the work.
