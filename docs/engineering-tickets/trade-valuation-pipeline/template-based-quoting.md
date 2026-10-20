# Quote templates and whole period pricing with named discount curves

**Status:** Ready for quoting implementation; quoting itself is not built. The [named discount curves arc](multiple-discount-curves.md) is implemented through #203, and #204 supplies the publication-based IFERC payment anchor. Base the quoting feature branch on that completed stack, or on main once it contains those changes; this is a separate feature PR, not another named-curve slice. Retain the agreed separate quote templates and entire requested period, with factor 1 for payment dates on or before `as_of`. This replaces the public API proposed in the [four-input prototype](quoting-prototype.md); retain its useful examples, not a second worksheet call form.

## Outcome

Keep the quoting formula short by placing repeated static terms in a quote template selected from the `fixed_float` instrument. Quote a month or strip from one market, using Asian, lastday, penultimate or last3day observations. A cleared quote is undiscounted. A bilateral quote uses factor 1 for elapsed payment dates and the selected named curve for future payment dates. CAL27 requested in June27 still includes January through December, using past fixings and live prices for the remaining observations.

```text
_CreateQuoteTemplate(instrument, fields, values) -> quote_template_handle
_Quote(market, contract_code, template, [discount_curve_set]) -> number
```

The quote output is one whole-period indicative fixed price in the index's quoted units, not a trade value or a handle. With all payments still ahead, it is the fair fixed price making the equivalent trade's mark zero. With elapsed payments, it includes those periods under the explicit convention below; it is not the remaining trade's zero-mark price or a reconstruction of a historical executable quote. This remains a first usable quoting slice for UAT, rather than a general quoting framework.

[Pipeline packet](README.md) · [UAT notes](surface-uat-notes.md#25-template-based-quoting) · [Existing template](../../library/trades/trade-template.md) · [Schedule machinery](../../library/trades/kernel.md) · [Market](../../library/market/market.md) · [Named curves](../../library/globals/discount-curve.md) · [Curve collection](../../library/globals/collect-discount-curves.md) · [Evaluation's curve rules](../../library/trades/evaluate-trades.md)

## Surface and dependency

Add `_CreateQuoteTemplate("fixed_float", fields, values)`, returning a distinct `QuoteTemplate` handle. Reuse the instrument's field definitions and shared value readers; do not reuse a `TradeTemplate` handle and silently discard booking fields. The creator supplies the instrument once, so `_Quote` needs no instrument argument. There is no new quote instrument or public quote-preparation handle.

Example bilateral template values:

| Field | Value |
|---|---|
| `route` | `bilateral` |
| `settlement_method` | `financial` |
| `schedule_method` | `asian` |
| `quantity_per` | `calday` |
| `payment_time_lag` | `+5bd` |
| `payment_holiday_calendar` | Payment-calendar handle |
| `discount_curve_key` | `SOFR` |

```excel
=_CreateQuoteTemplate("fixed_float", fields, values)
=_Quote(ngl_market, "CAL27", ngl_otc_template, rates)
=_Quote(ngl_market, "CAL27", ngl_cleared_template)
```

The rate inputs already exist:

```text
_CreateDiscountCurve(name, header_row, table) -> discount_curve_handle
_CollectDiscountCurves(curve_handles) -> discount_curve_set_handle
```

Here `rates` is the collection made from a cell, row or column of named curve handles, such as SOFR and FFOIS. A one-curve quote still uses `_CollectDiscountCurves` over that one handle. The collection retains the curve objects; it does not blend their factors or put rates into the market. Only the two quoting functions above are new. A cleared financial template has `route = cleared` and no discount key; its other pricing and payment terms can be the same.

The quote's first three arguments are required. Its template argument accepts a quote template only; a trade template fails by kind. Trade and cashflow booking likewise refuse quote templates. The fourth argument is an optional curve-set handle, with its meaning controlled by the template:

| Template route | Curve-set input | Treatment |
|---|---|---|
| `cleared` | Omitted | All pricing weights use a factor of 1 |
| `bilateral` | Required, including for a one-curve quote | Resolve the template's key in the supplied set |
| `cleared` with a set supplied | Refused | No silently ignored rates input |

Use the existing exact, case-sensitive name/key rule, with no surrounding whitespace, and the collection's unique-name rule. No first-curve default, name alias or raw-curve alternative. Bind the template's key once, including for a singleton set; then check only the selected curve's valuation-date start and future-payment coverage. Unused members may have other starts or shorter spans: do not validate their dates or read their factors. One template selects one curve for this quote; the fact that a set can contain several curves does not introduce per-month curve selection here. Keep the existing seam's omitted-versus-blank distinction.

The market remains unchanged. Rates are supplied directly to `_Quote`, as they are to `_EvaluateTrades(prepared, market, [discount_curve_set])`. A rates update makes a new curve and collection, leaving the quote template and market unchanged. For a bump scenario, replace the selected SOFR member with the result of `util_BumpDiscountCurve`; do not collect base and bumped SOFR together, because both retain the same name and the collection correctly refuses that duplicate. No single-curve adapter or named-curve migration is part of this PR.

## Instrument field requirements by purpose

Define each field's type, choices and intrinsic value rule once in the library-owned instrument definition. Add applicability and required/conditional requirements for booking and quoting there. These are metadata, not a `template_type` field in tickets, and not a second handwritten instrument or a quoting-local list of field names. The creator determines the purpose. Existing booking requirements retain their meaning.

Templates may remain partial. A creator checks supplied headers and values; `_CreateTrades` checks a completed booking, while `_Quote` checks the quote template plus its explicit contract and market inputs. A quote missing a required term fails naming it. Do not require trade identifiers, attribution, quantity or a fixed price merely to quote.

| Field or input | Booking | Quoting |
|---|---|---|
| Instrument carried by the template | Existing catalog rules | `fixed_float` only; unsupported instruments fail by name |
| `route`, `settlement_method`, `schedule_method`, `quantity_per` | Existing required fields | Required; same value choices and compatible combinations |
| `payment_time_lag`, `payment_holiday_calendar` | Existing financial/physical rules | Required for financial settlement, including cleared financial; absent for physical |
| `discount_curve_key` | Existing named-curve rules | Required for bilateral; refused for cleared; resolved against the set at quote time |
| `contract_code`, `start_date`, `end_date` | Existing period rules | The quote's contract argument owns the period; these headers are not allowed in a quote template |
| `fixed_price`, `quantity`, `quantity_unit` | Existing required fields | Not allowed as template inputs; price is the output and the relative quantity basis is sufficient |
| Trade identifiers/dates, counterparty, broker, clearing-house attribution, reserves and other booking-only fields | Existing required/optional/conditional rules | Not allowed in a quote template |

Reject an inapplicable header at quote-template creation, including an otherwise blank period header. No supplied field is silently ignored. Keep strict header spelling, duplicate/shape rules and typed reference cells through the existing field-row machinery. Extend `_ShowInstrument` to expose quote applicability and requirements from the same metadata alongside its existing booking rows; preserve those rows' meanings. Add `quote_allowed`, `quote_required` and `quote_required_when` rows, where required means required in the completed quote request, not necessarily present at template creation. A library definition cannot require a field that its purpose refuses.

The quote template retains the instrument, supplied names and typed values by reference or value as appropriate, without an index or market state. `util_ReadHandle` shows those supplied terms using the existing template readback pattern. Its ordinary handle kind is `quote_template`; publication, reuse and release follow the existing store. No quantity input, new weighting enum or reporting-lot dependency is introduced. Template-held curve **keys** are static text; live curve handles and factors stay outside the template.

## Periods and observations

Accept one full contract month or a strip through the existing contract-period parser and index schedule: for example `Z26`, `F27-G27`, `1H27` and `CAL27`, with its existing case handling. Resolve every component month once. Missing or ambiguous months fail. BAL codes, explicit partial dates and arbitrary quantity profiles are deferred.

Use all four existing methods on futures indexes and `lastday` on IFERC. Unsupported index/method combinations, including Gas Daily, fail explicitly. The shared schedule rules determine observation dates and normalized weights. An Asian follows the pricing contract assigned to each day by the index calendar, including rolls; expiry-based methods retain their own-reference and eligible-day requirements. IFERC lastday observes the publication date.

Use history for observations the calendar marks fixed and the appropriate live contract price for the rest, retaining the current `as_of` cutoff. A whole-month quote includes observations already fixed; moving `as_of` does not shorten the period or turn it into BAL. Gather each distinct required live reference once; fixed observations do not request expired live prices. Preserve the applicable observation, boundary-history, fixing and quote-coverage refusals, including those currently applied outside the observation builder.

## Monthly quantities, payment dates and fair price

For month `i`, form its floating price from its observations:

```text
P_i = sum_j(observation_weight_ij * observation_price_ij)

q_i = 1                         for quantity_per = month
q_i = calendar days in month i  for quantity_per = calday

D_i = 1                         for cleared
D_i = 1                         for bilateral when payment_i <= as_of
D_i = selected_curve(payment_i) for bilateral when payment_i > as_of

K = sum_i(q_i * D_i * P_i) / sum_i(q_i * D_i)
```

Return `K` in the index's price units. Relative quantities use one consistent underlying unit; a common quantity or unit-conversion scale cancels. `calday` includes weekends and holidays when weighting months, but it does not alter the schedule's within-month observation weights. Never use pricing-day counts as calendar-day quantities.

Resolve each financial component's payment date with the same rules as trade creation: every component anchors on its last observation. On an IFERC index that is the publication date, for both cleared and bilateral quotes; there is no last-trading-date input or reconstructed final-settlement-date step. Apply the existing compound date-offset reader and the supplied payment calendar. Preserve the rule that payment follows the final observation when its price is known. Keep each component's price, quantity and payment associated until the weighted sums are formed; do not blend prices first and then apply one factor to the strip. The anchor decision is [iferc-publication-payment-anchor.md](iferc-publication-payment-anchor.md).

For bilateral quoting, the selected curve starts on the market's valuation date and covers every requested future payment date. Set factors to 1 for dates on or before `as_of` without requesting them from the curve: this is the quote convention, not extrapolation. A missing key, wrong start or uncovered future payment fails before a number is returned. Keep the bilateral set/key/start checks even for an entirely historical request, but perform zero factor reads when no payments are ahead. Discount factors weight **both** the floating-price numerator and the fixed-leg denominator. Consequently, one month with one payment has the same quoted price cleared or bilateral, and a common factor across all payments cancels too.

### Whole period quotes across the valuation date

Keep every requested financial component in both sums, whether its payment is past, today or future. Historical observations use fixings; remaining observations use live projections. Do not drop paid months, convert CAL27 to the balance of 2027 or renormalize weights over only live observations. Missing required history remains an error.

Fixing state and payment timing are independent. A fully fixed month paying after `as_of` still uses its future payment factor. A partly fixed month's known and live observations share the factor for that month's payment. The rule is `payment_date <= as_of`, never `observation_date <= as_of`.

For CAL27 requested in June27, January through May remain in the price at their realized observations, June uses its fixed and live observations, and the rest use live prices. Each month's resolved payment date selects factor 1 or the curve. An entirely fixed and paid financial period returns its quantity-weighted realized price, with no live-price or factor reads; the market may still carry unused live contracts under its existing construction rules.

Including elapsed payments at factor 1 is the agreed full-period indicative-price convention. It does not undo settled cash, claim that past cashflows have remaining PV, or specify catch-up settlement terms for a newly booked backdated trade. Trade evaluation's mark/cash split and expiry rules are unchanged. The zero-mark comparison to trade evaluation applies only when all payments are still ahead.

For cleared physical settlement, this first slice still supports `lastday` under the existing compatibility and expired-physical rules, with no invented payment dates. Its expiry day's live status follows the calendar. The financial past-payment convention does not silently widen physical-delivery handling.

There is no already-paid-period refusal for financial quotes. This replaces the earlier ticket draft's proposed lifecycle limit.

## Worked acceptance

Use synthetic fixtures, not exchange assertions. Hand answers are independent expectations; comparisons with trade evaluation supplement them.

### Cleared and bilateral strip

Let `as_of = 31 December 2026`. A month-matching Asian calendar closes weekends and 1 January. January/February 2027 have last observations on 29 January and 26 February. A `+1bd` payment rule on a weekend-only payment calendar gives 1 February and 1 March. Supply an ordinary named curve starting at 1 on `as_of`, with factors 0.99 and 0.98 on those dates. Both component prices are still entirely live.

| Component | Floating price | Calendar days | Payment date | Selected DF |
|---|---:|---:|---|---:|
| January 2027 | 30 | 31 | 1 February 2027 | 0.99 |
| February 2027 | 60 | 28 | 1 March 2027 | 0.98 |

| Quantity basis | Cleared quote | Bilateral quote |
|---|---:|---:|
| `month` | `90 / 2 = 45` | `88.5 / 1.97 = 44.923857868020306` |
| `calday` | `2610 / 59 = 44.23728813559322` | `2567.1 / 58.13 = 44.16136246344401` |

January alone quotes 30 under both routes and both quantity bases. With the two floating prices reversed, the equal-month cleared quote remains 45 but the bilateral quote becomes `88.8 / 1.97 = 45.076142131979694`. This proves a scalar cleared price cannot be passed into a second function to recover the bilateral price.

Include a second named curve with visibly different payment factors. Changing the template's key selects it; reordering the set does not change the answer. Updating only the selected curve reprices the quote over the same template and market. With both selected payment factors equal to 0.98, the bilateral quotes equal the corresponding cleared quotes. An unused curve with a different start or insufficient coverage does not fail or change the quote and causes no factor reads; selecting that curve fails by the relevant date rule. A singleton containing FFOIS cannot satisfy a template selecting SOFR. Exercise a new collection containing bumped SOFR in place of base SOFR, and the existing duplicate-name refusal if both are supplied.

### Fixings and methods

Retain independently checked examples from the superseded prototype:

- A 20-observation Asian with five fixings at 25 and fifteen live projections at 29 has a single-month quote of 28. A live move to 30 gives 28.75; one fixing corrected up by 2 gives 28.10 with live prices still 29. Keep payment in the future; clearing versus bilateral discounting does not change that month's price.
- December 2026 has 22 pricing days when weekends and 25 December are closed. With 15 days priced by F27 at 70 and seven by G27 at 76, the Asian price is `1582 / 22 = 71.9090909090909`. After the roll, history supplies F27's fixed observations and the live vector supplies only G27.
- Pin lastday, penultimate and last3day dates and prices by hand, including a holiday immediately before expiry. For IFERC, pin the publication observation and the payment offset from that same publication date under each route and its payment calendar; no last trading date is needed. Test one month and a strip through the same calculation path.

On a multi-payment strip with unequal component prices, pin a payment-calendar change that shifts one component's payment and changes its factor relative to the others. The bilateral price then changes while the cleared price stands, provided both requests remain valid. A single month's factor would cancel, so do not use that case to expect a price change. Cover a leap February, a fully fixed but unpaid component, factor 1 on the payment day and the separate physical-expiry refusal.

### CAL27 in June27

Use `as_of = 16 June 2027`, a synthetic month-matching Asian calendar closed only on weekends, and `+1bd` on a weekend-only payment calendar. January through May have paid, most recently May on 1 June. June pays 1 July; December pays 3 January 2028. January through May's observations are all 30. June has 22 observation days: 11 fixed days through 15 June at 38 and 11 live days from 16 June at 42, giving a monthly price of 40. July through December project at 40. Supply a selected curve starting at 1 on `as_of` and giving 0.98 on every future payment date.

| Components | Monthly price | Month weight | Calendar-day weight | Payment factor |
|---|---:|---:|---:|---:|
| January through May, fixed | 30 | 5 | 151 | 1 |
| June, partly fixed | 40 | 1 | 30 | 0.98 |
| July through December, live | 40 | 6 | 184 | 0.98 |

The cleared equal-month quote is `430 / 12 = 35.833333333333336`; the bilateral equal-month quote is `424.4 / 11.86 = 35.78414839797639`. For `calday`, the cleared answer is `13090 / 365`, and bilateral is `12918.8 / 360.72`. Use the independent fractions as expectations with numerical tolerance. The period contains 12 months in every case; it never becomes a seven-month quote at 40.

Pin a historical fixing correction, a change to a live quote and a change to the selected future factors, each affecting its intended contributions. A past-month-only request returns 30 with no live or factor reads. A curve starting in June need not cover January through May. Add a payment exactly on `as_of` using factor 1; a fully fixed month with payment after `as_of` still uses the curve. Missing historical fixings or missing future factor coverage fail instead of removing a month.

## Implementation and work

Use `src/goosedove/quoting/template.py` for the quote template, `src/goosedove/quoting/quote.py` for pricing and `src/goosedove/excel/quoting.py` for the thin worksheet adapters. Shared field definitions remain under `instruments/`. Add `docs/library/quoting/quote-template.md` and `quote.md` as the respective maintained owners when built. A small private request or resolved-component record is appropriate if it clarifies responsibilities; no public quote-result handle is required.

Reuse instrument/template validation, schedule methods, period parsing, observations, calendar references, date offsets and market access. For rates, reuse the name/key reader in `globals/discount_curve.py` and the curve-start check and factor gather in `globals/payments.py`; factor gathering requires coverage to have been checked by the caller. The current key-binding helper in trade evaluation takes a prepared trade batch, so it is not a general quote resolver. If sharing key selection or schedule/payment resolution requires an extraction, move only the common facts/arrays calculation in a separate preparatory commit, keeping trade-specific error context and existing answers unchanged. Quote failures must name the requested key or component/payment, not a fictitious booked row. Do not build dummy trades or run the full booking, preparation, reserves and risk pipeline to solve a scalar quote. Do not create duplicate discounting or schedule implementations.

Measure actual work through the existing counters: template fields read, resolved months, observations, fixed inputs, distinct live references, payment rules/dates, curve-key resolutions, distinct future payment factors read and price reductions. Selected-key lookup occurs once per bilateral quote; deduplicate factor reads on identical future payment dates. Past/today factors require no curve reads. A fully fixed quote reads no live prices, and a fully paid financial quote reads no factors. Report work and memory for a month and a strip; no timing gate.

Full request resolution on a changed input is acceptable initially. A price tick may rebuild the internal quote schedule; the existing unchanged-call behavior remains. Promise no hidden preparation cache or selective recomputation. Reconsider reuse only after observing the costs. The template, market, calendars, set and curves are read-only inputs; new rates produce a new set and a new quoted scalar, not mutations of those inputs.

## Verification and delivery

Build the feature as one reviewable PR using the implemented named-curve worksheet surface and publication-based IFERC schedule. First establish purpose-aware field metadata and the quote-template path, with any small shared-helper extraction; then the quote calculation and worksheet coverage. Keep the commits independently understandable and existing booking behavior unchanged. The named-curve creators, trade/cashflow evaluation, saved risk contributions and risk reports retain their contracts; this PR consumes rates and returns a price. Add no four-argument method/basis overload, trade-template acceptance or alternate `_QuoteDiscounted` function.

Acceptance includes the hand examples, ordinary zero/negative finite prices, unchanged quote units including cents per gallon, a flat-factor/single-payment cancellation, and zero mark when an equivalent valid financial trade is booked at `K` with all payments unpaid. For the trade comparison, use the same index, quantity basis, observations, payment rules and selected curve. Include both routes; do not derive expected prices solely from that comparison.

Test partial quote-template creation followed by a named missing-term refusal at `_Quote`; wrong instrument or handle kind; rejected booking-only and period headers, including blank cells; strict, duplicate and unknown headers; incompatible terms; missing/extra curve-set arguments; unresolved key; curve start/future coverage; unavailable observations/prices; and nonfinite arithmetic. Pin the quote requirements exposed by `_ShowInstrument` to the same metadata the creators consume, and preserve all booking requirements and answers. An unsupported request fails visibly rather than guessing missing terms or returning a partial price.

Ship help, unit/seam tests, work-budget tests, host/smoke checks and a small kept-workbook block in the same PR. The block should expose the quote-template creator and readback, market, tenor and optional rates set beside the scalar, identify route and quote units, and demonstrate the CAL27-in-June case, a price move, a selected-curve move, a fixing correction, an invalid key and recovery. Cover quote-template publication/reuse/release and dependent quote recovery without inventing a quote-result store. Run the full repository gate and update the maintained owners and changed references once.

## Out of scope and UAT questions

Deferred: bid/ask/theo sets, executable prices and depth, quote risk or decomposition reporters, new instruments, multiple indexes or several curve keys within one quote, custom quantity profiles, BAL/partial-date requests, actual cash accounting or backdated catch-up settlement, fees/reserves in the price, credit/funding adjustments, automatic curve construction, caches and ticket hygiene.

Use UAT to check whether the dedicated quote template and short formula feel natural; whether the whole-period price matches the desk's CAL27-in-June request; which component/payment readback is actually needed; and which real requests hit the remaining period boundaries. Those observations may justify another slice. They do not require engineering to prebuild a general quote framework now.
