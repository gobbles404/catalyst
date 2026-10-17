# How goosedove fits together

The short way in. goosedove prices commodity trades for a desk working in Excel. A sheet builds the pieces one formula at a time, each formula a worksheet function that makes an object and shows its handle, text such as `30512:market:Henry Hub NYMEX:36` that later formulas take as an argument. The library, `src/goosedove/`, holds the objects and the arithmetic and knows nothing of Excel. The seam carries values across: the host, a C# add-in under `host/`, reads cells and shows results; the bridge, `src/goosedove/excel/bridge.py`, checks every argument against the function's declaration once and converts every result once. What each page of this repository owns is the table in [docs/seam/working.md](seam/working.md#10-what-each-page-owns); the rules for contributing are in [AGENTS.md](../AGENTS.md) and the tenets behind them in [PRINCIPLES.md](../PRINCIPLES.md).

This page says how the pieces fit and where each responsibility lives. Every detail belongs to the page that owns it, linked where it comes up, and nothing here is a second copy of a rule.

## The pieces, in the order a sheet builds them

**1. Definitions: what an index is, and what a trade may be.** An index is one reference price, bound once by `_CreateIndex` from its name, a description, its contract schedule, its conventions, its contract specifications and, for a futures index, its holiday calendar, with the specification its trades' risk is reported in lots of. The schedule is one of three kinds, futures, IFERC or Gas Daily, and the kind decides how the calendar below prices each day. The instrument, `fixed_float`, is library data: its fields, their types, choices and rules, which `_ListInstruments` and `_ShowInstrument` spill and which the trade creators read. Pages: [docs/library/index-definitions/](library/index-definitions/index.md) and [docs/library/instruments/](library/instruments/show-instrument.md). Code: `src/goosedove/index_definitions/`, `src/goosedove/instruments/`.

**2. The market: what is known on a day.** `_CreateValuationDate` fixes the day. `_CreateCalendar(valuation_date, index)` lists the periods the index prices, a day each on a futures index, with the contract pricing each and whether it has fixed. The fixings creators hold what has printed, newest first as the desk keeps a series. `_CreateMarketHistory(calendar, fixings)` binds the two: the settle on every fixed day. `_CreatePriceVector(index_name, prices)` snaps today's quotes, one per contract still to come, and `_CreateMarket(history, price_vector)` is the history plus those quotes. `_CreateDiscountCurve` is the curve a bilateral trade is discounted on. Pages: [docs/library/calendar/](library/calendar/calendar.md), [market-data/](library/market-data/price-vector.md), [market/](library/market/market.md), [globals/](library/globals/discount-curve.md). Code: `src/goosedove/globals/`, `calendar/`, `market_data/`, `market/`.

**3. Trades: from a ticket to a risk report.** Four steps, each a function that makes one record and shows its handle, each record keeping the one before it by reference.

| Step | Function | What it makes | Page |
|---|---|---|---|
| Create | `_CreateTradeTemplate(instrument, fields, values)` then `_CreateTrades(index, fields, trade_rows, template)` | the batch: the resolved terms of every row, the days each component observes and with what weight, the static encoding of its exposure on dated slots and payment groups, and the reserves booked | [trade-template.md](library/trades/trade-template.md), [create-trades.md](library/trades/create-trades.md), [kernel.md](library/trades/kernel.md) |
| Prepare | `_PrepareTrades(trades, history)` | the batch against one history: which slots have fixed and at what settle, which payments have fallen due, the live exposure left, and the nominal risk, which no tick changes | [prepare-trades.md](library/trades/prepare-trades.md) |
| Evaluate | `_EvaluateTrades(prepared, market, [discount_curve])` | the results: mark and cash at today's quotes, and for a bilateral batch the discounted risk and DV01 on the curve | [evaluate-trades.md](library/trades/evaluate-trades.md) |
| Collect | `_AggregateResults(result_handles)` | one handle over many results, the saved risk summed by index and by curve, nothing valued again | [aggregate-results.md](library/trades/aggregate-results.md) |
| Read | `_ReportValues`, `_ReportRisk(results, risk, bucket)`, `_ReportReserves`, `util_ReadHandle` | spills of what a record holds; they make nothing | [report-values.md](library/trades/report-values.md), [report-risk.md](library/trades/report-risk.md), [report-reserves.md](library/trades/report-reserves.md), [read-handle.md](library/utilities/read-handle.md) |

Code: `src/goosedove/trades/`, one module per responsibility. `template.py` reads the shared field values; `resolution.py` completes each ticket row from the template and the index into resolved terms, which `terms.py` defines along with the rules of each schedule method; `observations.py` gives each component its observation days and weights; `encoding.py` turns terms and observations into exposures on dated slots, payment groups and the axes risk is reported on; `reserves.py` books the brokerage, clearing and marketing reserves; `preparation.py` applies a history; `evaluation.py` applies the quotes and the curve and holds the result record and its risk views; `aggregation.py` combines saved results; `display_axes.py` builds the periods a report runs over.

**4. The seam: how a formula reaches the library.** The host registers every function the bridge lists, scans a range in one pass into two buffers, and hands them over; the bridge checks each argument by the function's declared types, runs it, and converts the result by the declared return type; a failure is text in the cell naming the function and what went wrong. A creator's result is a handle; equal creator calls share one object, and the host releases it when Excel disconnects the last of them. Code that prices, caches, hashes or converts takes a `WorkCounter`, `src/goosedove/instrumentation/`, and the tests under `tests/performance` pin what it reports. Pages: [docs/seam/README.md](seam/README.md) is the way in; [inputs.md](seam/inputs.md) and [outputs.md](seam/outputs.md) are what may cross; [handles.md](seam/handles.md) is a handle's life. Code: `src/goosedove/excel/`, one module per group of functions, and `host/Goosedove.Host/`.

## What is made again when something changes

The record each step keeps, and what makes a new one. The guarantees are the owning pages'; this table only puts them side by side.

| You change | What is made again | What stands |
|---|---|---|
| a ticket row, the template, or a definition the batch uses | the batch, and then its preparation and results | the index and the market |
| a fixing arrives or is corrected, or the valuation date rolls | the history, then the preparation, then the results | the batch: [prepare-trades.md](library/trades/prepare-trades.md) makes a new preparation whole, and [evaluate-trades.md](library/trades/evaluate-trades.md) refuses a market over another history rather than preparing again |
| a quote moves, the tick | the results alone: the live slots gathered and multiplied, the whole batch, and for a bilateral batch the discount factors read again per payment day | the preparation and the encoding, which the tick does nothing of, [evaluate-trades.md](library/trades/evaluate-trades.md) |
| the discount curve | the results, over the same preparation | the same |
| a report's selector, `risk` or `bucket` | nothing: the readers select among saved vectors, [report-risk.md](library/trades/report-risk.md) | everything |
| the set of results collected | the collection: saved vectors summed by index and by curve, [aggregate-results.md](library/trades/aggregate-results.md) | every result in it |

A recalculation with the same arguments makes nothing: the seam shares the live object, [handles.md](seam/handles.md#publication-and-release). A tick is cheaper than a new history, and a new history cheaper than a new batch; the counts are the tests under `tests/performance/`, which say what each call runs and allocates.

## Three kinds of date

A trade carries three dates that must not be confused. The observation date is the day a price is taken: a `lastday` trade observes its contract's expiry day, an `asian` trade every pricing day of its month. The pricing contract is the contract whose price prices that day, by the calendar's rule; it is the booked contract under the expiry-based methods and, under `asian`, whichever contract the calendar gives, so a December booked as Z26 may price off F27. The payment date is the day a payment group pays, counted from the group's last observation by the trade's payment rule. The deltas are reported by observation day or by the pricing contract's month or year; the DV01 by payment day, month or year. The owners are [kernel.md](library/trades/kernel.md) for the slots and groups and [report-risk.md](library/trades/report-risk.md) for the axes.

## Where the code is

| What | Where |
|---|---|
| the library's objects, one package per group, in the order they import one another: globals and instrumentation first, then index_definitions, then instruments, calendar and market_data, then market, then trades | `src/goosedove/` |
| the worksheet functions, one module per group, and the bridge; the library never imports this package | `src/goosedove/excel/` |
| the host, Excel-DNA integration, the scan, the way out, handle lifetime, the work counter | `host/Goosedove.Host/`, with its tests, started without Excel, in `host/Goosedove.Host.Tests/` |
| the Python tests: the rules and the hand-worked numbers under `unit/`, the counts, ledgers and ceilings under `performance/` | `tests/` |
| the whole check, the smoke test in a hidden Excel, the lifetime script, the runners and the profiler | `check.ps1`, `tools/` |
| the kept workbook, one block per topic, for talking about a function on a real sheet | `workbooks/handles.xlsx` |
| the function pages, one per worksheet function: what each does today | `docs/library/` |
| the seam's pages: what may cross, handles, the host and the bridge, how it is measured | `docs/seam/` |
| the plans: tickets as proposed, kept as they were once built | `docs/engineering-tickets/` |
| the research the design drew on | `docs/research/`, `docs/futures-trade-field-review.md` |

## Reading on

For a function, its page under `docs/library/`. For a cell that looks wrong, [docs/seam/working.md](seam/working.md#1-when-a-cell-looks-wrong). For the design the trade pipeline was built from, [the pipeline packet](engineering-tickets/trade-valuation-pipeline/README.md), which is the plan as agreed and the tickets since; where a function page and a ticket differ, the page says what is built.
