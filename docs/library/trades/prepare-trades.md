# _PrepareTrades

Built in #141 as ticket I5 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), with [_EvaluateTrades](evaluate-trades.md), [_ReportValues](report-values.md) and [_ReportRisk](report-risk.md); the design is [market binding](../../engineering-tickets/trade-valuation-pipeline/03-market-binding.md).

A batch of trades prepared against one market history, a futures index's daily history or since #167 an IFERC index's monthly one: each observation whose day has passed fixed at that day's settle, a month's published index on an IFERC index, each payment that has fallen due settled into cash, the live slots and the distinct contracts they quote off set out for the tick, and the risk settled once, the price sensitivity by contract and, since #164, the delta in lots of the index's reporting lot by contract and by slot, since no tick changes it. One record per history: a fixing arrived or corrected, or the valuation date rolled, makes a new one, and a quote moving makes none. The kernel's `prepared_trades` does the work, [kernel.md](kernel.md); the code is `src/goosedove/excel/trades.py`.

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
| 11 | `=_PrepareTrades(A10, I11)` | shows `30512:prepared_trades:Henry Hub NYMEX:43`, I11 the index's history valued on 24 November 2026, beside the index in I3 and outside the reports' spills below |

Two handles, both required, neither with a default: the batch, the cell showing `_CreateTrades`'s result or a name for it, and the market history of the batch's index, the cell showing `_CreateMarketHistory`'s result or a name for it, valued on the day the batch is prepared for. The seam resolves the two handles and nothing else; a cell of another kind fails in the seam's words, `history is market handle '30512:market:Henry Hub NYMEX:44', expected market history handle`, before the function runs. The result is a handle, `30512:prepared_trades:Henry Hub NYMEX:43`, the index's name between the kind and the count, as [handles.md](../../seam/handles.md) says. A successful call publishes a prepared batch and changes neither input; a recalculation with the same arguments shares the live one; a new history, or a new batch, makes a new one, the old released when Excel disconnects its last creator.

## Excel help

| Item | Text |
|---|---|
| Function | Prepares a batch of trades against one market history, each observation whose day has passed fixed at that day's settle and each payment that has fallen due settled, and shows its handle, the text _EvaluateTrades takes as the prepared trades. |
| trades | The trades handle: the cell showing _CreateTrades's result, such as A10, or a name for it. |
| history | The market-history handle of the trades' index: the cell showing _CreateMarketHistory's result, such as I11, or a name for it, valued on the day the trades are prepared for. |

## The library checks

The kernel's four rules, in [kernel.md](kernel.md)'s words after `#ERROR _PrepareTrades: ValueError:`.

| Rule | Refused as |
|---|---|
| The history is over the batch's index, the one object: another index of the same facts and name is another index | `history is over another index, 'Henry Hub NYMEX', expected the trades', 'Henry Hub NYMEX'` |
| On a futures index every slot's day is a day of the calendar, which begins the day after the schedule's first expiry; on an IFERC index, since #167, every slot's day is a month's publication day and its row that month's, the first month a month like any other, [iferc-basis-futures.md](../../engineering-tickets/trade-valuation-pipeline/iferc-basis-futures.md) | `trade 'V3' at row 1 observes 2026-05-19, before the calendar begins on 2026-05-20; the schedule's first contract, m26, bounds the calendar and nothing prices its days` |
| A physical future whose contract has expired is refused, delivery not being modeled; the contract's expiry decides, not an earlier observation's fixing | `trade 'NG-001' at row 1 on Z26 expired 2026-11-25, before valuation date 2026-11-26; a physical future after its expiry is not supported` |
| Every live lot, every lot delta and their total are finite numbers, since #164: a lot small enough against a quantity large enough, a BTU against 10^303 MMBTU, keeps a finite sensitivity and divides it past the largest number once it is counted in lots, or two contracts' finite deltas sum past it, and nothing is published that a reader would then fail on; the first slot past it is named, then the first contract, then the batch | `trade 'H' at row 1 on 2026-11-25, a day Z26 prices, has inf live lots, expected a finite number of lots of BTU (1 BTU); the exposure in lots outruns the largest number`; `Z26 has inf of lot delta, expected a finite number of lots of NYMEX NG (10000 MMBTU); the exposure in lots outruns the largest number`; `the batch has inf of lot delta in all, expected a finite number of lots of BTU (1 BTU); the contracts' deltas, each finite, sum past the largest number` |
| Every day's, month's and year's lots are finite numbers too, since #166: a bucket's sum can outrun what the contract's sum, taken in slot order, did not, and nothing is published that a reader would then fail on; the first bucket past it is named | `the day 2026-11-23 has inf of lot delta in all, expected a finite number of lots of BTU (1 BTU); its exposures in lots sum past the largest number`; `the month from 2026-11-01 has inf of lot delta in all, expected a finite number of lots of BTU (1 BTU); its exposures in lots sum past the largest number` |

A slot has fixed when the calendar marks its day fixed, the day after it at the earliest, so an observation stays live on its own day; a fixed slot's settle is the history's on that day, which the history holds for every fixed and priced day; a payment group is settled when every slot of it has fixed and its payment day is on or before the valuation date, the inclusive cutoff, fixed not being paid; since #162 a payment group is a contract and the day it pays, so a contract whose components pay on two days is two groups, one of which may be cash while the other is live or unpaid, [multiple-payment-groups.md](../../engineering-tickets/trade-valuation-pipeline/multiple-payment-groups.md).

## What it retains

The batch and the history by reference; per slot whether it has fixed and its live exposure, zero where fixed; per payment group, a contract and the day it pays, its set amount and whether it has settled; the live slots, the distinct contracts they reference and each slot's place among them; the unsettled offsets and set amounts summed, and the cash; the price sensitivity by contract on the batch's axis, the delta in lots of the index's reporting lot by contract with its total, and the live lots by slot, the sensitivity and the exposure over the lot's coefficient the index resolved once, since #164, so that nothing is looked up or converted here or on a tick, [lot-delta-reporting.md](../../engineering-tickets/trade-valuation-pipeline/lot-delta-reporting.md). Since #166 the live lots summed once more onto the encoding's time axes, by observation day, calendar month and calendar year, the three vectors `_ReportDelta` selects among, each checked finite, [daily-risk-vector.md](../../engineering-tickets/trade-valuation-pipeline/daily-risk-vector.md). Every array owned and read-only; nothing of a market or a quote.

## Reading it back

`util_ReadHandle` spills one row per slot: `pricing_contract`, the contract pricing the day, whose settle fixes the slot and whose quote projects it; `booked_contract`, the contract the slot's payment group was booked on, which owns the fixed leg and the payment, the same contract under the expiry-based methods and under `asian` whichever the calendar gave the day, since #165, F27 and then G27 against Z26 for a December on a WTI-like schedule, [calendar-driven-asian-references.md](../../engineering-tickets/trade-valuation-pipeline/calendar-driven-asian-references.md); `observation_date`; for a financial settlement `payment_date`, the day the slot's payment group pays, since #162, so that two groups of one contract observing one day read apart, a physical settlement paying on no day and showing none; `is_fixed`; `is_settled`, its payment group's; `live_coefficient`, the settlement currency the slot's price moves the mark by, zero where fixed, named for what it is since #164; `live_lots`, the same exposure in lots of the index's reporting lot. The NG example on 24 November spills Z26 on 25 November and F27 on 29 December, both live, each priced and booked alike, 160,000 and -50,000 of coefficient, 16 and -5 lots; the toy on 30 November spills Z26 paying that day, fixed and settled, and F27 paying 31 December, live.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_trade_valuation.py` | since #167 the Waha basis future's six states on the sheet, its slot read back fixed the day after publication and settled on the payment day; the NG example prepared and read back; the toy's seven states, Z26 fixed and paid on 30 November read back; the PHH pen's slot on its pen day, live, then fixed; the seam's refusals in order, a blank, a dead text, a market where the history should be; the library's, another index's history, a physical contract past its expiry; since #162 two payment days on one contract, A at +1bd and B at +3bd, read back with each slot's payment day, A's three settled on 7 December and B's three not, and two ends on one contract paying apart; since #164 the lots beside every coefficient, the ETE rows one lot each and the partial Asian period's live slots three quarters of a lot; since #165 the WTI-like booking read back with F27 then G27 as the pricing contract and Z26 as the booked one on every row, two groups on one pricing day apart by their booked contracts |
| `tests/performance/test_trade_valuation_budgets.py` | the call resolves two handles and runs `prepared_trades` and nothing of the encoding, the same at five trades and at two thousand; 8,912 bytes at 2,500 trades over 24 slots, by slot and never by trade |
| `tools/excel_smoke.ps1` | the smoke's chain, the handle's text, the reader, the three refusals; since #162 the payment day beside each financial slot and the payment-groups block's six slots, A's settled and B's not; since #165 the WTI-like booking's eight-row spill with its pricing and booked contracts, every earlier read a column to the right |
| `tools/excel_lifetime.ps1 -Groups trades,valuation` | prepared against the chain's history, reused as it is through a price tick; since #155, remade when the valuation day moves onto n26's expiry, the slot still live on its own day, and past it, the slot fixed and its group settled, read back through `util_ReadHandle`, the settled column the fifth since #162 and the sixth since #165, `booked_contract` before it |
| `host/Goosedove.Host.Tests/CallTests.cs` | the host's chain and two refusals; since #162 the two-payment-days fact, the slots with their payment days; since #165 the WTI-like booking's spill, F27 then G27 priced and Z26 booked |
| `workbooks/handles.xlsx` | B1302 at the foot of the handles sheet, read back in F1302; the toy's seven states in I1342 to I1348, the tick's row taking the first's as it is, the paid state's read back in B1350; since #162 the payment-groups block in rows 1563 to 1605, the 7 December preparation read back in B1589 with each slot's payment day, and every financial readback above a column wider; since #164 every prepared readback a column wider again, `live_lots` after the coefficient; since #165 a column wider once more, `booked_contract` after `pricing_contract`, and the WTI-like block in rows 1695 to 1737, the 18 December preparation read back in B1719 |

## Not here

No market, quote or value: [_EvaluateTrades](evaluate-trades.md). No history built, no fixing read beyond the history's own, no market whose whole calendar has ended, no incremental update when one fixing arrives: a new history is a new preparation, whole.
