# _PrepareTrades

Built in #141 as ticket I5 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), with [_EvaluateTrades](evaluate-trades.md), [_ReportValues](report-values.md) and [_ReportRisk](report-risk.md); the design is [market binding](../../engineering-tickets/trade-valuation-pipeline/03-market-binding.md).

A batch of trades prepared against one market history: each observation whose day has passed fixed at that day's settle, each payment that has fallen due settled into cash, the live slots and the distinct contracts they quote off set out for the tick, and delta by contract settled once, since no tick changes it. One record per history: a fixing arrived or corrected, or the valuation date rolled, makes a new one, and a quote moving makes none. The kernel's `prepared_trades` does the work, [kernel.md](kernel.md); the code is `src/goosedove/excel/trades.py`.

## Worksheet contract

```python
def _PrepareTrades(
    trades: Handle[Trades],
    history: Handle[MarketHistory],
) -> Handle[PreparedTrades]: ...
```

| | A | B |
|---|---|---|
| 10 | `=_CreateTrades(I3, A4:E4, A5:E9, B3)` | shows `30512:trades:Henry Hub NYMEX:41`, the NG example's five rows |
| 11 | `=_PrepareTrades(A10, B12)` | shows `30512:prepared_trades:Henry Hub NYMEX:43`, B12 the index's history valued on 24 November 2026 |

Two handles, both required, neither with a default: the batch, the cell showing `_CreateTrades`'s result or a name for it, and the market history of the batch's index, the cell showing `_CreateMarketHistory`'s result or a name for it, valued on the day the batch is prepared for. The seam resolves the two handles and nothing else; a cell of another kind fails in the seam's words, `history is market handle '30512:market:Henry Hub NYMEX:44', expected market history handle`, before the function runs. The result is a handle, `30512:prepared_trades:Henry Hub NYMEX:43`, the index's name between the kind and the count, as [handles.md](../../seam/handles.md) says. A successful call publishes a prepared batch and changes neither input; a recalculation with the same arguments shares the live one; a new history, or a new batch, makes a new one, the old released when Excel disconnects its last creator.

## Excel help

| Item | Text |
|---|---|
| Function | Prepares a batch of trades against one market history, each observation whose day has passed fixed at that day's settle and each payment that has fallen due settled, and shows its handle, the text _EvaluateTrades takes as the prepared trades. |
| trades | The trades handle: the cell showing _CreateTrades's result, such as A10, or a name for it. |
| history | The market-history handle of the trades' index: the cell showing _CreateMarketHistory's result, such as B12, or a name for it, valued on the day the trades are prepared for. |

## The library checks

The kernel's three rules, in [kernel.md](kernel.md)'s words after `#ERROR _PrepareTrades: ValueError:`.

| Rule | Refused as |
|---|---|
| The history is over the batch's index, the one object: another index of the same facts and name is another index | `history is over another index, 'Henry Hub NYMEX', expected the trades', 'Henry Hub NYMEX'` |
| Every slot's day is a day of the calendar, which begins the day after the schedule's first expiry | `trade 'V3' at row 1 observes m26 on 2026-05-19, before the calendar begins; the schedule's first contract bounds the calendar and nothing prices it` |
| A physical future whose contract has expired is refused, delivery not being modeled; the contract's expiry decides, not an earlier observation's fixing | `trade 'NG-001' at row 1 on Z26 expired 2026-11-25, before valuation date 2026-11-26; a physical future after its expiry is not supported` |

A slot has fixed when the calendar marks its day fixed, the day after it at the earliest, so an observation stays live on its own day; a fixed slot's settle is the history's on that day, which the history holds for every fixed and priced day; a payment group is settled when every slot of it has fixed and its payment day is on or before the valuation date, the inclusive cutoff, fixed not being paid.

## What it retains

The batch and the history by reference; per slot whether it has fixed and its live exposure, zero where fixed; per payment group its set amount and whether it has settled; the live slots, the distinct contracts they reference and each slot's place among them; the unsettled offsets and set amounts summed, and the cash; delta by contract on the batch's axis and its total. Every array owned and read-only; nothing of a market or a quote.

## Reading it back

`util_ReadHandle` spills one row per slot: `contract_code`, the contract pricing the day; `observation_date`; `is_fixed`; `is_settled`, its payment group's; `live_exposure`, zero where fixed. The NG example on 24 November spills Z26 on 25 November and F27 on 29 December, both live, 160,000 and -50,000.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_trade_valuation.py` | the NG example prepared and read back; the toy's seven states, Z26 fixed and paid on 30 November read back; the seam's refusals in order, a blank, a dead text, a market where the history should be; the library's, another index's history, a physical contract past its expiry |
| `tests/performance/test_trade_valuation_budgets.py` | the call resolves two handles and runs `prepared_trades` and nothing of the encoding, the same at five trades and at two thousand; 8,912 bytes at 2,500 trades over 24 slots, by slot and never by trade |
| `tools/excel_smoke.ps1` | the smoke's chain, the handle's text, the reader, the three refusals |
| `tools/excel_lifetime.ps1 -Groups trades` | prepared against the chain's history, reused as it is through a price tick |
| `host/Goosedove.Host.Tests/CallTests.cs` | the host's chain and two refusals |
| `workbooks/handles.xlsx` | B1302 at the foot of the handles sheet, read back in F1302; the toy's seven states in I1342 to I1348, the tick's row taking the first's as it is, the paid state's read back in B1350 |

## Not here

No market, quote or value: [_EvaluateTrades](evaluate-trades.md). No history built, no fixing read beyond the history's own, no market whose whole calendar has ended, no incremental update when one fixing arrives: a new history is a new preparation, whole.
