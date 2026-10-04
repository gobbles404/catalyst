# The trade kernel

Built in #136 as ticket I1 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md). Since #139, ticket I4, [_CreateTrades](create-trades.md) resolves the terms from a template and a ticket on the sheet and publishes the batch, the terms and the encoding together; the record gained the instrument and the clearing house and broker labels, and a lot count or a price is refused naming the trade's own row, which a strip's component row is not. `_PrepareTrades`, `_EvaluateTrades` and the two reports stand on it in ticket I5.

The four steps of the pipeline as library code, `src/goosedove/trades/`: the resolved terms of a batch, their static encoding, the batch prepared against one market history, and its evaluation against one market. One occurrence takes the same path as a thousand and every occurrence counts, a duplicate twice. The [NG example](../../engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md) is the acceptance fixture: every hand answer on that page, the real NG rows before expiry and the toy lifecycle through its seven states, is pinned in `tests/unit/test_trades.py`, and the work of each step in `tests/performance/test_trade_budgets.py`.

## The four records

| Record | Builder | What it holds | What makes a new one |
|---|---|---|---|
| `ResolvedTrades` | `resolved_trades` | the instrument, the index and its futures schedule, the specification row, the route, the settlement, the schedule method, the quantity unit and basis; per occurrence its trade date and, where given, its label, clearing house and broker; per component its occurrence, its schedule row, its signed lots, its fixed price and, for a financial settlement, its payment day | a change to the ticket, the template or a definition used |
| `Encoded` | `encoded` | per component the signed quantity in the quote quantity unit, the coefficient, the settlement currency it makes per unit of quote price, and the entry-price offset in the settlement currency; the inputs, one per contract held, in the schedule's order; per input the summed quantity, the summed coefficient, which is the exposure every price multiplies, the summed offset and the one payment day | the same |
| `Prepared` | `prepared` | per input whether it is live and whether it is settled, and its set amount; the live contracts and their exposure; the unsettled offsets and set amounts summed, and the cash; delta by contract and its total, which no tick changes | a new history: a fixing arrived or corrected, or the valuation date rolled |
| `Results` | `results` | the route, the currency and the valuation day; mark and cash; the batch's contract axis, the preparation's delta and total shared, and DV01, with their unit | a new market: a tick, or anything that made a new preparation |

Each record keeps the one before it by reference, so a result explains itself back to the terms and the index, and every array is owned and read-only. Nothing in the kernel imports the Excel bridge; the unit tables and the work counter arrive as arguments and are never worksheet parameters.

## What each step does, and refuses

**The terms.** A futures index, since a future's contract is a row of a futures schedule and its final price the settlement on that row's expiry day; a row of its specifications, since the lot size is read there; `LOT` as the quantity unit, the one unit built. One or more occurrences, a date each and, for each label tuple given, a text each; one or more components, each of an occurrence, every occurrence holding at least one, each contract a row of the schedule, each lot count a whole nonzero number, each fixed price finite, the lots and the price named by the trade they belong to, as the sheet counts its rows. A financial settlement has one payment day per component; a physical one has none, since it pays on no day and a date given would invent a payment. The instrument is kept as the definition the terms stand under and read for nothing here.

| Rule broken | Message |
|---|---|
| the index is not a futures index | `index is a Gas Daily index, expected a futures index for a future` |
| the specification is no row of the index's | `specification is 1, expected a row of the index's specifications, 0 to 0` |
| the quantity unit is not lots | `quantity_unit is 'MMBTU', expected LOT, the one quantity unit built` |
| an occurrence holds no component | `trade 'NG-001' at row 5 has no component, expected at least one` |
| a contract is no row of the schedule | `contract row 4 is 3, expected a row of the schedule, 0 to 2` |
| a lot count is fractional, or zero | `lots of trade 'NG-003' at row 3 is 7.5, expected a whole number of lots`; `lots of trade 'NG-002' at row 2 is 0.0, expected a nonzero quantity` |
| a fixed price is not finite | `fixed_price of trade 'NG-004' at row 4 is inf, expected a finite price` |
| a financial settlement without its days, or a physical one with days | `payment_date is missing, expected one date per component with a financial settlement`; `payment_date has 5 dates, expected none with a physical settlement, which pays on no day` |

**The encoding.** Quantity is lots times the specification's lot size, restated in the conventions' quote quantity unit through the unit tables, both units of the quantity type as the index checked. The coefficient is the quantity restated from the quote currency to the settlement currency, so that a price in cents times it is an amount in dollars; every price the batch meets, a quote, a final settlement or the fixed price, multiplies the coefficient and never the quantity, which is kept apart as the physical fact. The offset is minus the coefficient times the fixed price. The inputs are the distinct contracts held, sorted, which is the schedule's order; the sums by input are one bincount each, so two occurrences on one contract are one input with their coefficients added, a duplicate twice. For a financial settlement every component on a contract pays on that contract's one day, and that day is after its expiry. The fees of the specification are read by nothing: reserves, never a contribution to value.

| Rule broken | Message |
|---|---|
| two payment days on one contract | `payment_date of trade 'NG-002' at row 2 is 2026-12-01, expected 2026-11-30, the one day Z26 pays` |
| a payment on or before the expiry | `F27 pays on 2026-12-29, expected a day after its expiry 2026-12-29, when its final price exists` |

For the NG rows, quantity `[100000, -40000, 70000, -120000, 100000]` MMBTU, the coefficient the same since dollars are quoted and paid, offset `[-310000, 126000, -238000, 402000, -310000]` USD, inputs Z26 and F27 at rows 1 and 2, exposure `[160000, -50000]`, offsets `[-494000, 164000]`, as the page says. One lot bought at 300 cents on an index quoted in cents and settled in dollars has a quantity of 10,000 MMBTU, a coefficient of 100 USD per cent per MMBTU and an offset of -30,000 USD: at 300 cents it marks zero, a cent moves it 100 dollars, and ten cents up it marks 1,000, live, fixed or paid.

**The preparation.** The history is over the trades' index, the one object. An input has fixed when the calendar marks its expiry day fixed, the day after the expiry at the earliest: a contract stays live on its expiry day, as the calendar's rule says. A physical future that has fixed is refused, naming the trade, the contract, its expiry and the valuation date, since delivery is not modeled and nothing is omitted, zeroed, kept in mark or moved to cash in its place. A financial future that has fixed takes its final price off the history, the settle on its expiry day, one read per fixed input; it is settled when it has fixed and its payment day is on or before the valuation date, the pipeline's inclusive cutoff, and fixed is not paid. The live inputs are the rest, with their exposure summed for the tick. Delta is settled here too, the exposure on the live inputs and zero on the fixed over the whole axis, with its total, since nothing a tick brings changes either.

| Rule broken | Message |
|---|---|
| the history is another index's | `history is over another index, 'Henry Hub NYMEX', expected the trades', 'Henry Hub NYMEX'` |
| a trade on the schedule's first contract, which bounds the calendar | `X26 expires 2026-10-28, before the calendar begins; the schedule's first contract bounds the calendar and nothing prices it` |
| a physical contract past its expiry | `trade 'NG-001' at row 1 on Z26 expired 2026-11-25, before valuation date 2026-11-26; a physical future after its expiry is not supported` |
| a financial contract expiring on a day its calendar closes | `Z26 expires 2026-11-26, a day its calendar does not price; no final price exists` |

**The evaluation.** The market is over the history the batch was prepared against, the one object; a market over another history is refused, and the batch is prepared again outside, never silently here. The route is cleared; a bilateral batch is refused by name until discount factors and a DV01 convention exist, rather than valued as if undiscounted. The market answers the quotes of the live contracts in the batch's order and refuses a contract past its coverage by name, as it does for every reader; the mark is the unsettled offsets and set amounts plus the exposure times the quotes, one dot product; the cash is the preparation's. Delta and its total are the preparation's, shared and never written, over the batch's whole axis, the contracts in the schedule's order whatever has fixed, the total the change for a common move of one in every contract; DV01 is zero, the undiscounted cleared model's answer and not a placeholder.

| Rule broken | Message |
|---|---|
| the market is over another history | `market is over another history of index 'Henry Hub NYMEX', expected the one the trades were prepared against` |
| the route is bilateral | `route is bilateral, expected cleared; bilateral valuation needs discount factors and a DV01 convention, not built yet` |
| a quote is missing for a traded contract | the market's own words, `requested contract 'F27' is beyond live-price coverage ending at 'Z26'` |

For the NG rows valued on 24 November 2026 at quotes `[3.20, 3.50]`: mark 7,000 USD, cash 0, delta `[160000, -50000]` USD per USD/MMBTU, total 110,000; at `[3.21, 3.50]` the mark is 8,600 and the delta unchanged. The five singletons mark `[10000, -2000, 7000, -18000, 10000]` and sum to the batch; the first four alone mark -3,000.

## The toy lifecycle

The toy product of the example page, financial, paying two business days after each contract's last trading day, with G27 after F27 so that every state has a market:

| As-of | Final prices | Quotes | Mark | Cash | Delta | Quotes read | Fixings read |
|---|---|---|---:|---:|---|---:|---:|
| 24 Nov | none | 3.20, 3.50, 3.60 | 7,000 | 0 | 160,000, -50,000 | 2 | 0 |
| 24 Nov, a tick | none | 3.21, 3.50, 3.60 | 8,600 | 0 | 160,000, -50,000 | 2 | 0 |
| 26 Nov | Z26 3.22 | 3.50, 3.60 | 10,200 | 0 | 0, -50,000 | 1 | 1 |
| 26 Nov, corrected | Z26 3.23 | 3.50, 3.60 | 11,800 | 0 | 0, -50,000 | 1 | 1 |
| 30 Nov, Z26 paid | Z26 3.23 | 3.50, 3.60 | -11,000 | 22,800 | 0, -50,000 | 1 | 1 |
| 30 Dec, both fixed | Z26 3.23, F27 3.45 | 3.60 | -8,500 | 22,800 | 0, 0 | 0 | 2 |
| 31 Dec, both paid | Z26 3.23, F27 3.45 | 3.60 | 0 | 14,300 | 0, 0 | 0 | 2 |

The last two states read no quote: the batch is fully fixed inside a market that still quotes G27, a contract no trade holds, and the axis stays Z26, F27. The settled amounts are the singletons summed, `[13000, -3200, 3500, -12000, 13000]` to 14,300.

## Work

Each builder reports to its counter what it did, in counts: the encoding one component encoded per component and one input per input; the preparation one input prepared per input and one fixing read per fixed input, nothing per component and nothing per day of the calendar; the evaluation one kernel call and one quote read per live input. A tick, a new market over the same preparation, runs the evaluation alone: `results` once, `Market.live_prices` once, and the counter, the same functions at five components and at two thousand, with nothing of the encoding or the preparation done again. The numpy call cProfile sees on a tick is the market's one look at the contracts asked for, with its reduction; the dot product is dispatched in C and unseen, as [measuring.md](../../seam/measuring.md) explains, and delta is not made again.

## Tests

| Case | Kind |
|---|---|
| the terms own frozen copies; every rule above refused with its message | example |
| the NG encoding to the number; a duplicate added twice; a lot in barrels under a gallon quote, a price in cents settling in dollars; one payment day per contract, the two refusals | example |
| one lot quoted in cents and settled in dollars, live, fixed and paid, at cost and ten cents up: zero and 1,000 dollars, a cent 100 dollars | example |
| both contracts live before expiry; live on the expiry day, expired the day after; another index refused whatever its name; the boundary contract refused; a closed expiry day refused | example |
| 7,000 then 8,600; the five singletons summed; the duplicate's 10,000 and 100,000; a tick folds nothing and leaves the preparation as it was; another history refused; a short vector refused in the market's words; a bilateral batch refused | example |
| the toy's seven states, mark, cash, delta, quotes and fixings read; the settled singletons summed; a fully fixed batch inside a live market reads no quote | example |
| any batch of up to eight rows over two contracts equals its singletons summed and the hand formula, doubles when doubled, and keeps its axis in the schedule's order | property |
| the counts each step reports, and the functions and numpy calls each step runs, at five components and at two thousand | budget |

## Not here

No preparation, evaluation or report on the sheet: ticket I5. The template, the ticket, the field names, the contract codes read for their month and the payment days counted from a lag and a calendar are [create-trades.md](create-trades.md)'s, which hands the kernel resolved terms; the toy's days still arrive resolved in these tests. No bilateral valuation, discount factor or DV01 convention, no `asian`, `penultimate` or `last3day`, no `day` quantity basis, no quantity unit but `LOT`, no cash instrument, and no market whose whole calendar has ended.
