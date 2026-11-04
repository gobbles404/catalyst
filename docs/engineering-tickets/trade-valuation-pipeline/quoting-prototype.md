# Four input quoting prototype

**Status:** Superseded on 18 October 2026 by [template-based quoting after named curves](template-based-quoting.md). Retained as the earlier whiteboard and source of worked examples. Do not implement its four-input surface alongside the replacement. The owner now wants a distinct quote template, sharing instrument field definitions, to carry repeated pricing terms and the named curve key.

## Purpose

Get one useful price from an existing market, a contract period, a schedule method and a quantity basis. The first use is an NGL Asian calendar swap, including strips and a month whose first observations have already fixed. The same function also supports the existing lastday, penultimate and last3day methods. Use this on a sheet before deciding whether quotes should use trade templates, their own templates or direct inputs in the longer term.

This prototype returns the **undiscounted whole-period breakeven fixed price**, in the index's quoted price units. It uses the prices supplied by the market. It does not establish a transactable bid or offer, apply payment-date discounting or claim to return the discounted fair price of an OTC strip.

[Pipeline packet](README.md) · [UAT notes](surface-uat-notes.md#25-template-based-quoting) · [Market](../../library/market/market.md) · [Trade schedule machinery](../../library/trades/kernel.md) · [Period grammar](../../library/utilities/start-date.md)

## Worksheet contract

```text
_Quote(market, contract_code, schedule_method, quantity_per) -> number
```

All four arguments are required. Keep the short name `_Quote` discussed with the owner. The first argument is an ordinary market handle; the other three are scalar text. The output is one numeric cell, suitable for comparison or entry into a ticket, without a result handle or a report function.

| Argument | Meaning | Examples |
|---|---|---|
| `market` | The index, valuation date, calendar, fixings and live price vector already bound together | Existing market handle |
| `contract_code` | One month or a strip, resolved through the existing period grammar and the index's schedule | `Z26`, `F27-G27`, `1H27`, `CAL27` |
| `schedule_method` | The existing rule selecting observation dates and their within-component weights | `asian`, `lastday`, `penultimate`, `last3day` |
| `quantity_per` | Relative quantity allocated to each component month | `month`, `calday` |

```excel
=_Quote(ngl_market, "CAL27", "asian", "calday")
=_Quote(ngl_market, "F27-G27", "asian", "month")
=_Quote(ng_market, "CAL27", "penultimate", "month")
```

These are proposed formulas, not functions already shipped. Contract labels keep the existing parser's case handling and strip forms. Method and quantity-basis texts use the existing exact spellings; do not add aliases such as `pen` or a second parser. BAL labels and explicit partial-month dates are outside this slice.

The scope is `fixed_float` pricing, so no instrument selector is needed. There is no template, route, quantity, fixed price, payment rule, discount curve or global valuation-date input. The market supplies its own valuation context. Function help and the kept workbook must call the result undiscounted so the four-input convenience cannot be mistaken for discounted OTC valuation.

## Economic rules

Resolve the requested period into its component months, in order. Every requested month must exist unambiguously in the index schedule. Use the existing index/method compatibility: futures indexes support the four existing methods; IFERC supports `lastday`, its publication-date observation; Gas Daily remains unsupported and fails explicitly.

For component month `i`, let `w_ij` be its schedule's observation weights, which sum to one. Each observation's price `p_ij` comes from history if the calendar marks it fixed, otherwise from the live price of the contract the calendar assigns to that observation.

```text
P_i = sum_j(w_ij * p_ij)

q_i = 1                         when quantity_per = month
q_i = calendar days in month i  when quantity_per = calday

quoted_price = sum_i(q_i * P_i) / sum_i(q_i)
```

`q_i` is relative quantity in one consistent underlying quantity unit, not a reporting-lot count. Its common scale cancels. No contract-specification selection, reporting-lot conversion, broker charge, clearing charge or marketing reserve enters the price.

**Keep the two sets of weights separate.** `calday` counts every calendar day, weekends and holidays included, when allocating quantity between months. It does not change an Asian schedule into calendar-day price averaging. The existing Asian rule still averages eligible pricing days. `month` allocates equal quantity to each month, even when their observation counts differ. In a single full month the two bases therefore return the same price.

Use the current schedule and calendar rules unchanged:

- Asian observations follow the calendar's pricing contract, which may roll during the averaging month. Do not require that reference to equal the quoted component's contract month.
- Lastday, penultimate and last3day keep their existing expiry-based dates, eligible-day rules and own-contract reference requirements. IFERC lastday keeps its publication-date meaning.
- Apply the existing fixed/live cutoff from the market's calendar, including the treatment of an observation on `as_of`. Never invent a second fixing cutoff inside quoting.
- A whole-month or strip request always covers the requested whole months. As `as_of` advances, fixings replace projections; the period and its quantity weights do not shrink. It never silently becomes a BAL request.
- A fully fixed period can return its realized whole-period average if the existing history covers it. This is a historical breakeven price, not a statement that the period is still tradable. Do not invent a payment or physical-delivery lifecycle without route/payment inputs. Creation of a market whose entire calendar has ended remains outside this ticket.

Return the price in exactly the index's existing quote currency and quote quantity units. For example, a market quoted in cents per gallon returns cents per gallon; do not return a monetary amount or silently convert to dollars. Finite zero and negative market prices remain valid where the existing market permits them.

## Reuse and ownership

Give quoting its own small home:

```text
src/catalyst/quoting/quote.py      Quote-specific resolution and fair-price calculation
src/catalyst/excel/quoting.py      Thin _Quote worksheet adapter
docs/library/quoting/quote.md       Maintained worksheet contract when implemented
```

Reuse period parsing and schedule-month resolution from `index_definitions`, the observation builder and schedule-method definitions, the calendar's reference mapping, and existing history/live-price access. Several checks presently live in trade encoding/preparation rather than the observation builder: closed observation days, unavailable boundary history, expiry-method reference mismatches and live-price coverage. Preserve the applicable observation/data checks in the quoting path; do not assume that calling the observation builder alone establishes them all.

Extract a narrowly shared helper only where needed to avoid duplicate rules or a dependency on booked-trade records. For example, month bounds belong with period arithmetic and last-observation lookup belongs with observations. Preserve existing trade behavior if a helper moves. Avoid a broad package reorganization, a generic pricing framework or a new instrument catalog in this PR.

The runtime path must not construct a dummy ticket/trade, build reserves or risk axes, or call the full trade creation/preparation/evaluation pipeline to obtain a scalar price. A private request or resolved-schedule record is fine if it makes responsibilities clearer; it creates no worksheet handle contract.

## Worked acceptance examples

Use synthetic fixtures with fully specified calendars and history. These are mathematical examples, not assertions about an exchange product. Pin the expected numbers independently of the production implementation.

### A two-month strip

Take January and February 2027, both still live, with component prices of 30 and 60 respectively. A month-matching Asian fixture can have every observation in each month projected from that month's one quote.

| Month | Component price | Calendar days | Quantity under month | Quantity under calday |
|---|---:|---:|---:|---:|
| January 2027 | 30 | 31 | 1 | 31 |
| February 2027 | 60 | 28 | 1 | 28 |

```text
_Quote(market, "F27-G27", "asian", "month")  = (30 + 60) / 2 = 45
_Quote(market, "F27-G27", "asian", "calday") = (31*30 + 28*60) / 59
                                                = 44.23728813559322
```

Quoting F27 alone returns 30 under either basis. Include a leap-February check so the calendar-day basis uses actual dates rather than a fixed month-length table.

### A whole month with fixings

For a synthetic January 2027 Asian, close 1 January and weekends and let the month have 20 pricing days. At `as_of = 9 January`, the first five pricing days have fixed at 25; the other fifteen project at 29.

```text
whole-month quote = (5*25 + 15*29) / 20 = 28
live price moves to 30, same history   = (5*25 + 15*30) / 20 = 28.75
one fixing moves from 25 to 27,
live price remains 29                 = (125 + 2 + 15*29) / 20 = 28.10
```

The quote is 28 initially under either quantity basis. A date roll with newly supplied fixings replaces the corresponding projections and retains all 20 observations. Also cover an observation on `as_of` and a fully fixed requested month within an otherwise valid market; neither case may request an expired live quote for a fixed observation.

### Asian pricing across a futures roll

Use a synthetic December 2026 calendar with weekends and 25 December closed, 22 pricing days. Let F27 expire on 21 December and G27 price the days after it. With all observations live, F27 quoted 70 and G27 quoted 76:

```text
15 observations use F27; 7 use G27
Z26 Asian quote = (15*70 + 7*76) / 22 = 71.9090909090909
```

Z26 is the requested averaging month; F27 and G27 are its pricing references. Repeat after the roll with the first fifteen observations fixed at 70 and only G27 live at 76: the answer stays the same and F27 is not requested from the live vector.

### The other schedule methods

Provide a synthetic expiry on Friday 29 January 2027 with Thursday 28 January closed. The eligible final three observation days are 26, 27 and 29 January. With those days fixed at 29, 31 and 33 respectively, a historical quote returns 33 for `lastday`, 31 for `penultimate` and 31 for `last3day`. Pin a live case and a strip for these methods as well, and IFERC lastday using its publication date rather than its last trading date.

## Validation and measured work

The existing seam resolves the handle and validates scalar types/shapes. The library validates the choices and economic/data coverage. Unknown method/basis, malformed code, unsupported index/method, missing or ambiguous schedule month, unavailable observation/fixing or required live price, empty observation set, and nonfinite arithmetic fail visibly. Name the relevant input, month or date. Never skip missing observations and renormalize the answer.

Supplement the hand answers with these checks:

- A strip equals the quantity-weighted combination of its monthly quotes. Single-month `month` and `calday` agree. Identical monthly prices give that same strip price under either basis.
- For a valid cleared financial fixture with all payments unpaid, booking the same period, method and quantity basis at the quoted price gives zero aggregate mark within justified numerical tolerance. This is a consistency check, not the sole source of expected answers.
- Quote-unit scale is retained, including a cents-quoted fixture; changing an irrelevant reporting-lot specification does not change the quote. Exercise finite zero and negative prices.
- Quote and fixing updates propagate through the existing market dependency; readers/handles supplied as inputs remain unchanged. A failing input and its correction are visible on the sheet.

Count actual work with the existing `WorkCounter`: component months resolved, observations built/consumed, fixed observations read, distinct live references gathered and price reductions. Read each distinct live reference once per call and gather onto its observations. State the counts and memory behavior for a month and a longer strip; do not gate on timing.

Full request resolution on each changed market is acceptable for this prototype. Do not promise preparation reuse, introduce a cache or add worksheet preparation functions to optimize it. Record the cost so UAT can inform whether a reusable quote definition is worthwhile. Keep the existing unchanged-call seam behavior and declare no new volatility.

Ship the library and seam tests, focused work-budget tests, help, host/smoke coverage and a small kept-workbook block in the same PR. The block should show the four input cells and the scalar output, name the index and its units, and visibly label the calculation **undiscounted**. Include the two-month basis comparison, a partially fixed Asian and one expiry-based method. Run the full repository gate; update the maintained quote page and its references once rather than duplicate its contract across tickets.

## UAT questions and boundaries

Use the prototype to find out whether direct inputs are convenient, which terms users repeat, and whether reuse should eventually come from an instrument template, a quote-specific template or a smaller convention record. Those are open design choices, not foundations to build speculatively now.

Ask what extra inspection is actually needed: the scalar price, its observation breakdown or its risk. Record examples where discounting materially changes the useful OTC answer and the payment terms those examples require. A discounted version needs payment dates and a curve; it must not infer them from these four inputs.

Deferred: discounting and payment conventions, routes and settlement lifecycle, custom quantity weights, BAL/explicit partial periods, quote templates or handles, quote risk/results/reporters, bid/ask/theo collections, executable prices/depth, spreads across indexes, reserves and marketing, ticket hygiene, and multiple discount curves. These do not block the four-input demo. The owner expects iteration, including changing the API after UAT if experience warrants it.
