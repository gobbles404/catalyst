# Onetime averaging across calendar months

**Status:** Agreed 1 November 2026 as issue #231, three stacked pull requests from main: the first, the calculation period beside every component and the payment groups keyed by it, is built in #232; the second, the `settlement_frequency` field required of every template and refused by every consumer until priced, is built in #233 on it; the third, the whole-period average, is built in #234 on it. [kernel.md](../../library/trades/kernel.md) owns the groups, [create-trades.md](../../library/trades/create-trades.md) the entry and [show-instrument.md](../../library/instruments/show-instrument.md) the fields.

## The issue

Support a financially settled `fixed_float` whose Asian average covers one explicit start/end window, even when that window crosses calendar months. The WTI trade-month example is the first acceptance case. Preserve the existing monthly-strip economics and distinguish a whole-period average from a monthly NG strip whose payments are deferred to one date.

This is a researched proposal, not an implemented feature. Code inspected and current behavior reproduced at commit `4161152f3dd9f37a3207818706db4ac95ab49a15`.

**Recommendation and size**

Start with `monthly` and `onetime` as the two calculation-period choices. Those cover the requested monthly strip and single bounded average. A three-month, seasonal, or annual single average is still `onetime` with different boundaries. Recurring quarterly settlements, irregular schedules, and stub conventions should wait for concrete requirements; these two values are an initial scope, not a claim that markets have only two frequencies.

This is a medium-sized structural change, not a new pricing model and not just an enum addition. A planning estimate is **5–10 focused developer days across about three reviewable changes**, including tests and Excel acceptance, after the field semantics are settled. Generalizing expiry-based methods, IFERC, two-index trades, and every RFQ form simultaneously would enlarge that estimate.

**Current behavior and the missing behavior**

A dated `asian` row is expanded at calendar month ends. Each piece receives its own entered monthly quantity, normalized daily weights, and payment anchor. Nearby-contract selection already works independently of that split.

For May 26–June 25, 2026, with the NYMEX settlement calendar:

| Current component | Observations | Quantity with 1,000 BBL/month | Weight per observation |
| --- | ---: | ---: | ---: |
| May 26–31 | 4 | 1,000 | 1/4 |
| June 1–25 | 18 | 1,000 | 1/18 |

Thus current entry produces `1000*(A_May-K) + 1000*(A_June-K)`. The requested TMA is `1000*((4*A_May + 18*A_June)/22 - K)`. Both use the same nearby fixing series; their quantity and averaging semantics differ.

Crossing a futures expiry within one calendar month already works: June 1–25 gives one 18-observation average, with 15 July WTI settlements and three August settlements.

An explicit common `payment_day` already makes monthly pieces pay together, but preserves their independent quantities and weights. This was intentional in [#213](https://github.com/gobbles404/goosedove/issues/213), implemented by #214. Explicit date entry was also intentional; the [period design](trade-periods-and-bal.md#exact-periods-and-schedule-methods) added no separate `exact` pricing method.

**Proposed entry semantics**

The existing `fixed_float` instrument schema should declare the selection, with the value supplied through the trade or template. Proposed public spelling: `settlement_frequency = monthly | onetime`. Its documentation must say that it selects **independently calculated payoff periods**, not merely the cash payment date. Keep `schedule_method` and `payment_day` separate.

| Selection | Calculation periods | Asian normalization | Payment rule anchor |
| --- | --- | --- | --- |
| `monthly` | One per covered calendar-month portion | Separately within each portion | Each portion's last observation |
| `onetime` | One inclusive start/end period | Across all eligible observations in that period | The entire period's final observation |

An entered payment date remains an explicit date after the relevant final observation; the existing payment-calendar and date/rule behavior stays authoritative. A futures expiry changes an observation's pricing reference, not the calculation-period boundary.

Add an explicit total-period quantity basis, proposed `quantity_per = period`, rather than silently changing `month`. Initial bounded support: `onetime` + `asian` on a futures index + `period` quantity, financially settled. Preserve current `monthly` combinations and their `month`/`calday` meanings. Initially reject unimplemented combinations by name, including `onetime` with a monthly quantity, physical settlement, or expiry-based/IFERC methods. Calendar-day quantity for a whole-period average can follow a separately agreed rule; it must not be guessed from pricing-day counts.

Existing callers and kept workbooks should migrate explicitly to `monthly` when this field becomes required. No retired-name aliases or implicit compatibility behavior. The final field name and the allowed-combination table should be agreed before implementation; the semantics above are the recommendation.

**WTI acceptance: one average, one quantity, one payment**

[CME Rule 804101](https://www.cmegroup.com/rulebook/NYMEX/8/804.pdf) defines the NYMEX-based TMA as an arithmetic average of first-nearby WTI settlements. Its window starts on the first business day after the 25th two months before the named month and ends on the last business day on/before the 25th of the preceding month.

For July 2026, use May 26–June 25. Applying the [CL expiry rule](https://www.cmegroup.com/rulebook/NYMEX/2/200.pdf), July CL expires June 22. There are 19 July-contract observations and three August-contract observations; [June 19 has no CME/NYMEX settlements](https://www.cmegroup.com/tools-information/holiday-calendar/files/2026/juneteenth-day-settlement-times-2026.pdf). All 22 weights are 1/22.

Book a synthetic 2,200-barrel receive-floating/pay-fixed trade at 71, paying June 29. Before observations begin, with July futures at 70 and August at 72, the projected average is `(19*70 + 3*72)/22 = 70.272727...`, the undiscounted value is **-1,600**, and the nominal sensitivities are **1,900 barrels to July and 300 to August**. Bilateral valuation discounts the single payoff to June 29. These are invented prices for acceptance, not historical market observations.

A 1,000-barrel total-period trade must also work directly without fractional ticket quantities. Do not implement the feature as the user's manual 4/22 and 18/22 quantity workaround.

This case is specifically the NYMEX-based TMA. Argus Formula Basis is a different fixing source; this issue does not substitute NYMEX settlements for it. Automatic generation of a named WTI trade month's boundaries is not required: explicit start/end dates are sufficient.

**NG strip: distinguish two legitimate meanings of 'settles once'**

A monthly NG strip paid on one date can retain each month's benchmark and volume:

`payoff(T) = sum_m Q_m * (S_m - K)`

For a last-day Henry Hub strip, `S_m` is the corresponding month's final futures settlement, as specified by [CME Chapter 823](https://www.cmegroup.com/rulebook/NYMEX/8/823.pdf). It must not silently become a daily nearby average.

Synthetic example, all amounts paid on April 7, 2027:

| Month | Quantity, MMBtu | Final reference price | Fixed price | Amount |
| --- | ---: | ---: | ---: | ---: |
| January | 10,000 | 3 | 3.5 | -5,000 |
| February | 20,000 | 5 | 3.5 | 30,000 |
| March | 10,000 | 4 | 3.5 | 5,000 |

The common-date amount is **30,000**. The quantity-weighted reference is **4.25**, not the equally weighted monthly mean of 4. The current system can represent this through monthly rows and one explicit `payment_day`, preserving the selected monthly observation method. Internal groups need not collapse into one group merely because their amounts pay on the same date.

An NG Asian averaging every eligible daily nearby fixing across the whole strip is a different contract. It can use the proposed futures-Asian `onetime` path if those are the agreed economics. Do not infer that fixing rule from the word NG or from payment frequency.

Keep both examples in acceptance. The remaining product question is whether the NG request needs only the already-supported common payment date, or also a rule automatically anchored to the strip's final observation. The latter is payment-schedule work; it must not redefine monthly averaging or quantity weights.

Primary product documentation supports the distinction: ICE SDX describes a [single swap](https://idd.ice.com/CM/CMHelp/Content/FM/Swap.htm) over three months with one settlement, versus a [swap strip](https://idd.ice.com/CM/CMHelp/Content/FM/Swap_Strip.htm) with fixing sets for successive settlements. Its [conventions table](https://idd.ice.com/CM/CMHelp/Content/FM/Market_Conventions_for_T.htm) distinguishes daily NG Asian observations from exchange-based NG swap fixings. These are supporting examples, not a universal OTC confirmation convention.

**Implementation assessment**

| Area | Work and risk |
| --- | --- |
| Definitions/templates | Add the field and quantity basis, document compatible combinations, and migrate trade/quote templates and workbook examples. |
| Period resolution and terms | `resolution.py` splits by month; `terms.py` explicitly rejects cross-month components. Represent a calculation period independently of a single booked futures month. Do not assign an arbitrary future to make the old shape fit. |
| Observations and quantities | `observations.py` already averages eligible days over supplied bounds. Reuse that arithmetic over the whole period and apply its quantity once. |
| Payment grouping and encoding | `encoding.py` assumes booked-contract/payment/curve group keys. Remove the mandatory monthly identity while preserving legitimate compression and distinct pricing references. |
| Preparation/evaluation/risk | Reuse the fixed/live exposure engine. Commodity delta still follows July/August pricing references; DV01 follows the payment date. Update group labels and validation rather than building a second evaluator. |
| Fees and readback | Charge the total period quantity once; retain marketing reserve per entered occurrence. Expose actual period bounds, frequency, quantity meaning, fixing weights/references and payment date without a misleading single contract label. Include the observation contribution readback added in #229. |
| Quote/RFQ | Quote and RFQ paths independently build monthly requests in `quoting/quote.py`, `request.py` and `rfq.py`. Reuse the resolved-period rules where supported. The existing RFQ input is monthly contract rows, not arbitrary date windows: explicitly refuse an unsupported `onetime` request rather than silently quote monthly economics. Arbitrary-date RFQ entry needs an explicit follow-up scope if not included. |
| Two-index trades | Either support a shared period/quantity/payment with each leg's own fixing calendar and normalized weights, or explicitly reject `onetime` for two-index entry initially. Do not accidentally enable mixed-method whole-period trades. |

Suggested slices: (1) separate calculation-period identity from booked-contract identity while preserving monthly behavior; (2) add the bounded whole-period Asian path, quantity basis, payment anchor and risk/reserve/readback behavior; (3) complete the template/Excel/quote cutover and acceptance. Any unsupported quote or two-index combination must fail before the feature is exposed. Share the period resolution; do not duplicate TMA-specific pricing.

**Validation and work budgets**

- Preserve existing monthly results and the supported date/nearby-roll behavior. Within one calendar month, equivalent `monthly` and `onetime` trades must agree.
- Pin the WTI numbers above, holiday endpoints, expiry-day inclusion, a range containing no pricing day, and missing index/history coverage.
- Test before fixing, partially fixed, fully fixed but unpaid, and paid states; corrected fixings; live-price bumps; and as-of rolls. Original whole-period weights never renormalize as observations fix.
- Compare the 2,200-barrel TMA with 400-barrel and 1,800-barrel monthly pieces at a common payment date, with marketing reserves zero. Test the 1,000-barrel case directly.
- Preserve the NG common-payment example and its unequal monthly quantities. A common payment date must not replace those weights with an equal-month or equal-day average.
- Verify fair quote followed by equivalent booking gives zero NPV for supported entry forms; unimplemented quote/RFQ combinations fail clearly.
- Verify one period quantity in fees, sign/zero quantities, duplicates/reordering, reporting by actual pricing contract, and payment-based DV01. Run host/smoke/lifetime and kept-workbook acceptance.

Measured current creation probe: May 26–June 25, four supplied futures schedule rows, 1,000 BBL/month, cleared, no broker, explicit June 29 payment. Proposed counts below are design targets for the new whole-period representation, not measured future results or a claim of equivalent old/new quantity semantics.

| Work fact | Current monthly split | Whole-period target |
| --- | ---: | ---: |
| Resolved occurrences | 1 | 1 |
| Resolved / encoded components | 2 / 2 | 1 / 1 |
| Encoded payment groups | 2 | 1 |
| Encoded observations / slots | 22 / 22 | 22 / 22 |
| Distinct pricing references | 2 | 2 |
| Fee components, clearing only | 2 | 1 |
| Schedule codes read | 4 | 4 |

Keep/update `tests/performance` budgets for resolution, encoding, preparation, evaluation, reserves, quote and RFQ as affected. Creation resolves periods once; a live tick rebuilds no dates, weights or payment schedules and reads each distinct live pricing contract once. Measure counts and allocations; do not gate on elapsed time. Implementation PRs must report measured counts before/after. Never change source and golden files in the same PR.

**Boundaries and related work**

Initial new scope is financial, single-index futures-Asian whole-period averaging, alongside unchanged monthly behavior and the NG deferred-payment regression. No new `exact` method, options/volatility engine, automatic WTI date generator, Argus data integration, physical settlement changes, general recurrence/custom schedule framework, or automatic fractional allocation workaround. Gas Daily trade support remains [#211](https://github.com/gobbles404/goosedove/issues/211), LME remains [#230](https://github.com/gobbles404/goosedove/issues/230), and fixed-price curve-shape allocation remains [#219](https://github.com/gobbles404/goosedove/issues/219).

Documentation owners to update with implementation: `docs/library/instruments/show-instrument.md`, `docs/library/trades/create-trades.md`, `kernel.md`, affected reserves/risk/readback pages, and the relevant quote/template/RFQ owners. Resolve the period once and consume it downstream, keep trade economics as data, and reuse the common engine in line with PRINCIPLES.md.

## The review and the decisions

The review of 31 October 2026 ran the issue's two examples through main at `4161152`. The WTI window of 26 May to 25 June 2026 as one dated asian row at 1,000 bbl a month, valued 20 May with July at 70 and August at 72, resolves to two components, May 26 to 31 at four observations of 250 bbl and June 1 to 25 at eighteen of 55.6, marks -1,666.67 and carries 1,833 and 167 of nominal delta to July and August; the same window as the 400 and 1,800 workaround marks -1,600.00 with 1,900 and 300, the TMA's numbers. The NG strip of 10,000, 20,000 and 10,000 at 3, 5 and 4 against 3.5, every month paying 7 April 2027, marks 30,000 with every group reading that payment day, and its quantity-weighted reference is 4.25. So "settles one time" names two contracts: a strip paid once, each month its own fixing and quantity netted into one payment, which a strip code or a dated row with a date `payment_day` books today; and one average over the whole window with one quantity, the new path, the two differing even at equal monthly quantities since months hold different numbers of observations.

The owner's decisions, 1 November 2026:

1. **Field name and default.** `settlement_frequency = monthly | onetime`, required, supplied through the trade or the template, defined explicitly: `monthly` creates separate calculation periods at calendar-month boundaries; `onetime` creates one calculation period across the supplied start and end dates. `payment_day` separately determines when payment occurs.
2. **Quantity basis.** `monthly` with `quantity_per = month | calday`, and `onetime` with `quantity_per = period | calday`. `month` applies the entered quantity to each monthly portion; `period` makes it the total for the entire window; `calday` multiplies the entered daily quantity by the calendar days in each calculation period, weekends and holidays included. It changes quantity, not the asian fixing weights.
3. **Payment rule.** Both explicit dates and rules such as `+2bd` stay. For `onetime` the rule counts from the entire window's final observation; for `monthly` from each monthly portion's final observation. The separate feature that keeps monthly calculations but anchors every payment to the strip's final fixing is deferred; a common explicit payment date already handles that case.
4. **Labels.** `booked_contract` is renamed `booked_period` and shows the date range for an `onetime` period, in the form every date in a refusal takes, `2026-05-26 to 2026-06-25 paying on 2026-06-29`. `pricing_contract` stays for the actual underlying futures references. Typed dates internally.
5. **The monthly grouping identity is the calendar month.** `K26` stays in `booked_period`, and today's grouping by month, payment date and discount-curve key is preserved. The clipped start and end dates still determine each component's observations, averaging weights and `calday` quantity: grouping two May rows together must not recompute them as one average. For `onetime`, the period identity uses the exact start and end dates.
6. **The shared template carries `settlement_frequency`.** The same field is required for quoting and booking, beside `quantity_per`. A template may contain `onetime`; the unsupported consumer rejects it explicitly. `_Quote`, `_QuoteRFQ`, two-index entry and physical settlement name `settlement_frequency = onetime` in the refusal, with no fallback to monthly behavior.

## The slices

Three pull requests, each stacked on the one before, each with the whole gate green:

1. **The calculation period.** A typed period, its first and its last day, beside every component of the resolved terms, derived there; the payment groups keyed by period, payment day and curve key, in period order; the group's contract kept for the monthly label and the physical batch's expiry check; `booked_contract` renamed `booked_period` on the prepared and the results readbacks. No number moves.
2. **The field.** `settlement_frequency`, required on the trade template and the quote template, `quantity_per` gaining `period`; every consumer refusing `onetime` and `period` by name until built; every template, host fact, smoke block, lifetime group and kept-workbook block migrated to `monthly`. Since a required field fails every entry that lacks it, the field and the migration land together.
3. **The whole-period average.** `_CreateTrades` accepting `onetime` with `asian` on a futures index, a financial settlement and `period` or `calday`; the period the row's two dates, one component, one group, its label the dates; the WTI and the NG numbers above pinned on every surface; fees charging the period quantity once; the readback, the risk and the reserves; the pages.

## As built, slice 1

`ResolvedTrades.period_start[k]` and `period_end[k]`, the first and the last day of the k-th component's calculation period, derived in `resolved_trades` by `_the_calculation_periods` from the component's start date, the calendar month it lies in, through `month_bounds`, now the terms' and imported by the resolution and the quoting from there; frozen, eight bytes each a component. The encoding's `_the_groups` keys the groups by the two bounds, the payment day and the curve key, one lexsort as before, and under a physical settlement by the two bounds alone; `group_contract` stays each group's head component's contract, the contract of its month, read for the label, the refusals and the physical expiry check and for no key. `_slot_names` in `excel/utilities.py` names the second column `booked_period`.

The work: the resolution freezes two arrays more, `ndarray.setflags` 20 where it was 18 and 21 where it was 19, and converts six more, `ndarray.astype` 23, 26 and 27 where they were 17, 20 and 21; its call profile reads `month_bounds` twice where it read it once and `_the_calculation_periods` once; the creation's peak grows by the two bounds, 296 bytes a row where it was 280. No other count, peak or byte pin moved, and no number on any surface.

Tests: `tests/unit/test_trades.py`, each component's period its calendar month and two rows of one month paying on one day one group with their own days and weights; the readback column renamed where it was read, in `tests/unit/test_trade_valuation.py`, `test_trades.py` and `test_two_index.py`, the host's `CallTests.cs`, the smoke's MY7 pin and the kept workbook's nineteen header cells.

## As built, slice 2

The field. `settlement_frequency` is the `fixed_float`'s twenty-second field, last in the catalog, required of a trade and of a quote, a code of `monthly` or `onetime`, read in a template and in a ticket by `settlement_frequency_of` as the basis is read; `quantity_per` gains `period`, its options `month, calday, period`. The resolution reads each distinct text once, as it reads the basis, and hands the terms a selection per occurrence; `ResolvedTrades.settlement_frequency[i]` keeps it, the position among `FREQUENCIES`, frozen, and the trades readback shows it last, after the encoding's columns, so that no column before it moves.

The rules, in the kernel's terms, where every booking passes: `_the_frequency` refuses the first `onetime` row by its trade, `settlement_frequency of trade 1 at row 1 is 'onetime', expected 'monthly', the one selection this version books; a onetime period across the row's dates is not built, and nothing prices it as monthly`, and under `monthly` the first `period` row, `quantity_per of trade 1 at row 1 is 'period', expected 'month' or 'calday' under settlement_frequency = monthly; period is the total of a onetime period and says nothing of a month`. A quote and a request for quote read the field from the template as they read the basis and refuse both words in their own: `settlement_frequency is 'onetime', expected 'monthly'; a quote prices by the month and does not price a onetime period across a window's dates as monthly` and `quantity_per is 'period', expected 'month' or 'calday'; period is the total of a onetime period, which a quote does not price`; the two quantity matches carry the `period` arm as a refusal, so that no path prices it as a month. Two-index entry and a physical settlement meet the general refusal in this slice; the third narrows it to the combinations it does not price and names each. One gap, found in review: the resolution still splits a `onetime` row at month ends and observes the pieces before the terms refuse it, so a window whose month fragment holds no pricing day, 30 January to 10 February 2027 say, meets the asian method's refusal first and not the named one. The third slice reads the frequency before the periods are built, so that a `onetime` row is one period and the unsupported combinations are named ahead of any observation rule, with that window as a regression test.

The migration, the field and it in one pull request since a required field fails every entry without it: every template literal and keyword template in the tests, `tests/unit/test_trade_valuation.py` through a `templated` helper that appends the field where a test's field tuple leaves it out, so that the tuples and the slices over them stand; the host's template rows, the field last in a quote template's row and after the basis in a trade template's; the smoke's and the lifetime's blocks, the field appended after each block's last cell and the formulas' ranges extended, a block whose next column is taken stacking the shared row's new cell onto its range with `HSTACK`; and the kept workbook's forty-two template formulas and seventy-three typed cells, three date-and-settle tables shifted one column right by inserting cells in their rows, which moves every reference, so that the readbacks beside them have a column to grow into, and the two notes citing those tables' addresses retyped. Twenty-one trades and template readbacks and the two shown instruments grow by one column; no number moves.

The work: the resolution reads one distinct text more, `_each_distinct` 4 where it was 3 with its lambda, `_distinct_texts` 6, `choice` 5, `_Fields.texts` 5, `_Fields.rows` 11, `_Fields.has` 23, `_Fields.where` one more, `_frozen_rows` 6, `settlement_frequency_of` and `_the_frequency` once each; its numpy `numpy.array` three more, `ndarray.argsort` two, `ndarray.any` three, `ufunc.reduce` three, `numpy.empty` and `numpy.asanyarray` two each, `ndarray.setflags`, `ndarray.cumsum`, `ndarray.flatten`, `ndarray.reshape` and `ndarray.astype` one each; the template creators read one field more, `field_value` 9 for a trade template and 8 for a quote template, `template_fields_read` 8 where it was 7; the shown instrument lays out 230 cells where it laid out 220; the creation's least peak 321 bytes a row where it was 296, the frequency's selection, its inverse and its frozen copy. No other count, peak or byte pin moved.

Tests: `tests/unit/test_trades.py`, the frequency kept per occurrence and the two refusals in the kernel's words, the first `onetime` row named; `tests/unit/test_create_trades.py`, the field missing from both sources, a word off the list, `onetime` and `period` through the resolution, and the field as a ticket column; `tests/unit/test_quote.py` and `tests/unit/test_rfq.py`, the two refusals of a quote and of a request; `tests/unit/test_instruments.py` and `tests/unit/test_quote_template.py`, the catalog's lists with the field last; every budget pin above.

## As built, slice 3

The whole-period average. A `onetime` row is one component whatever months its dates span: the resolution reads the frequency before any period is built, `frequency_rules` in `terms.py`, the kernel's rule and the resolution's first, so that the combinations the kernel does not average are refused in their own words and never in an observation's, the review's gap closed and the 30 January to 10 February 2027 window a regression test; then `_the_periods` makes one component for the row, its schedule row the month the window opens in, which prices nothing, and its days the whole window, and `_the_calculation_periods` makes its period the two dates where a `monthly` component's is its calendar month. The asian method averages every pricing day the window covers, 1/N each, each day priced by the contract the calendar gives it, so the WTI trade month of 26 May to 25 June 2026 is 22 observations, N26's nineteen through its expiry on the 22nd and Q26's three; the quantity is the entered total under `period` and the daily quantity times the window's calendar days under `calday`, 31 here; the payment counts from the window's final observation by the row's date or rule; the fees charge the one component once. The rules, in order, each naming the first row at fault by its trade: an IFERC index, two indexes, a physical settlement, a method other than `asian`, a quantity per `month`, and `period` under `monthly`.

The label. `booked_words` in `terms.py` is the one source of a component's period in words, the contract's code of a month and the two dates of a window, `2026-05-26 to 2026-06-25`, made when a readback or a refusal asks, vectorized over the components asked for, and kept by nothing; the encoding keeps `Encoded.group_head`, each group's head component, from which `group_label` and `group_words` name a group, and the `EncodedLeg` keeps no label. The trades readback shows the words under `booked_period` where it showed `contract_code`, the slot readbacks the group's words on every slot, and `settlement_frequency` reads the row's own word. The catalog's two field rules say what is priced; `_Quote`, `_QuoteRFQ`, two indexes and a physical settlement refuse `onetime` by name as the second slice left them.

The work, measured: a onetime window costs one component, one group and one fee component a row where `monthly` costs two of each, the same observations and slots; the resolution's call profile reads `frequency_rules` twice, once ahead of the periods and once in the terms, where it read `_the_frequency` once, and `_the_monthly_components` once, the one-month rule moved out of `_the_components`; its numpy ledger four looks more on every ticket, `ndarray.any` 32 where it was 28 and `ufunc.reduce` 35 where it was 31, the frequency's two looks in each run, the periods' look at the windows and the calculation periods' once more; a window ticket adds the month bounds once, two conversions of the windows' ends and the frequency's two looks under onetime more, `ndarray.any` 37, `ndarray.astype` 28 and `ufunc.reduce` 41 against the part-month asian ticket's 33, 24 and 37. The encoding's functions and numpy are the same over a window as over months, and its ledger is as it was. The creation's least peak is 324 bytes a row where it was 321, three one-byte masks, which rows are a window and which components. No other count, peak or byte pin moved, and no number on any monthly surface.

Tests: `tests/unit/test_onetime_average.py`, the WTI numbers above on every surface, -1,600 with 1,900 and 300 barrels of delta before any day fixes, -2,700 with 800 and 300 part fixed, -4,400 fixed and then cash, 1,000 barrels directly, the window equal to the 400 and 1,800 workaround to the slot, `calday` 3,100, one month alike under either frequency, the weekend fragment and its two refused twins, the NG strip paid once at 30,000 beside the strip's average as another contract, the readbacks through the seam; `tests/unit/test_trades.py`, the rules in the kernel's words and the group's label in a refusal; `tests/unit/test_create_trades.py`, the rules through the resolution; `tests/performance/test_trade_creation_budgets.py`, the window ticket's budget beside the moved pins; `tests/performance/test_seam_allocation.py`, the creator's peak. The host's fact books the window on 23 April and reads the readbacks, the mark and the refusal; the smoke's MS6 block books 18 December to 15 January on the WTI-like index, 1,900 barrels for the period, 8,900 of mark and 1.9 lots over nineteen slots; the kept workbook rebuilt, its eighteen trades readbacks' headers renamed, the two shown instruments' rule rows restated and the note of 8 October at D1538 retyped, no number moving.
