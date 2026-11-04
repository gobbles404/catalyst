# Futures trade representation: contract research

Research collected 27 September 2026; design reconciliation 3 October 2026 · Catalyst

This report preserves research on Henry Hub, Waha, crude oil, refined products, ethane, carbon allowances and COMEX copper. Exchange facts are linked to primary sources; they have not been reverified during this documentation reconciliation. Sample trades and firm/account names are fictional.

The ten commodity-family surveys, the cross-family matrix and the synthesis behind this report are in [docs/research](research/futures-contract-matrix.md), reviewed 14 September 2026 and frozen.

**The [trade-valuation pipeline](engineering-tickets/trade-valuation-pipeline/README.md) is the current engineering contract.** Its [instrument field sketch](engineering-tickets/trade-valuation-pipeline/instrument-field-sketch.md), [ShowInstrument specification](library/instruments/show-instrument.md) and [CreateTrades specification](engineering-tickets/trade-valuation-pipeline/create-trade.md) supersede this report's earlier schema and build sequence. This survey is supporting research, not a second backlog or permission to add arbitrary trade fields. Physical delivery processing and margining are outside v1.

## 1. Research in the agreed pipeline

The library owns the instrument definition. A template selects that instrument and supplies shared permitted fields; ticket rows complete the executed deal. `CreateTrades` resolves those terms against static Index definitions and encodes them. `PrepareTrades` applies history and retains aggregate compatible live exposures; `EvaluateTrades` consumes the current market and produces aggregate results for pure readers.

The field universe is larger than the trade-entry form:

| Component | What it contains |
|---|---|
| Trade template | Shared fields from the selected library instrument definition |
| Individual trade details | Executed facts: trade identifier, trade date, quantity, agreed price, and selections left open by the template |
| Shared definitions | Product identity, conventions, lot size, settlement terms, fixing methodology, delivery eligibility and date rules |
| Resolved contract schedule | Applicable observation, trading and payment dates; notice/delivery research below is outside v1 |
| Valuation inputs | Current prices, published fixings and as-of state, supplied separately from static trade terms |

**Template and ticket fields are disjoint.** Repeating a template field in the ticket fails even when its value is identical. Headers must exactly match the selected instrument definition; unknown fields, aliases, case/whitespace variants and duplicate headers fail. The completed terms must also satisfy the selected product's static facts. Neither a ticket nor a template can quietly turn a physical listed future into a financial one.

Terminology is deliberate: a **quote** is an offered price/terms; a **trade** is a consummated deal; **agreed trade price** is its execution price; **market price** is a valuation input; a **fixing** is an established observation. A contract period identifies the listed maturity; it is separate from trade date.

Each independently traded future has its own market identity. Waha Basis, penultimate gas and monthly-average futures remain single-index trades. Their final-price methodologies may reference other prices without creating additional trade legs.

### Contract codes and strips

**`contract_code` should be explicit in the trade entry.** It identifies the contract binding within the selected index/product specification. `Z26` conventionally means December 2026; it does not by itself identify gas, copper or any other product. The full resolved identity includes the selected product/specification and listed contract. Codes are resolved against supplied definitions; exact accepted spellings and year conventions must be explicit. [CME month codes](https://www.cmegroup.com/month-codes.html), [contract trading codes](https://www.cmegroup.com/education/courses/introduction-to-futures/understanding-contract-trading-codes).

The user-facing field can also accept a defined strip alias such as `Cal27`. Its definition must say whether that code selects one listed instrument or a package of listed contracts:

| Selected product | Example entry | Resolved binding | Price-observation implication |
|---|---|---|---|
| NG | `Z26` | One December 2026 contract | One listed maturity with its own terms |
| ETE | `Z26` | One December 2026 contract | Its final fixing averages observations; this does not turn it into a strip |
| NG | `Cal27`, when defined as a calendar strip | January through December 2027 contracts, `F27` through `Z27` | Twelve constituent contracts retain their own market prices and schedules |

ICE defines a calendar strip as buying all monthly contracts for the selected year. Its strip convention is distinct from an average-priced monthly future. [ICE common strategies and strips, sections 3.6 and 4.1](https://www.ice.com/publicdocs/IFEU_Common_Strategies_and_Strips.pdf).

Contract selection and fixing method are separate: one contract can average daily prices, and a strip can contain averaging contracts. A product may also define a single longer-period averaging instrument; a year label alone is not authority to expand it into twelve contracts. WTI Financial's rules describe longer-period averaging contracts, but the applicable listing/contract definition must establish the actual binding. [CME Chapter 510](https://www.cmegroup.com/rulebook/NYMEX/5/510.pdf).

“Bullet” can remain a desk term, but it should not silently mean both “one listed maturity” and “one observation or payment.” Those are separate facts.

The current [creation contract](engineering-tickets/trade-valuation-pipeline/create-trade.md) defines the initial strip form: `contract_code` resolves monthly constituents, `quantity_per` establishes the quantity basis, and one `fixed_price` applies to each constituent. For example, `CAL27` with `quantity = +10`, a `quantity_unit` naming the index's lot specification and `quantity_per = month` contributes +10 of that lot in each month. This is an explicitly booked flat-price strip, not an inference that a package-average execution price applies to every month. Package allocation and arbitrary component ratios from the earlier survey are not additional v1 input fields.

## 2. Contract survey

Sizes below are nominal total quantity per lot. They are not daily quantities. Financial means cash final settlement; physical futures also have ordinary variation cash settlement during their lives.

| Product and identifier | Listing exchange | Quantity per lot | Native price units | Final settlement and defining feature |
|---|---|---:|---|---|
| [Henry Hub Natural Gas — NG](https://www.cmegroup.com/rulebook/NYMEX/2/220.pdf) | NYMEX | 10,000 MMBtu | USD/MMBtu | **PHYSICAL**; natural gas at Henry Hub, Louisiana |
| [Henry Penultimate Fixed Price — PHH](https://www.ice.com/products/6590264) | ICE Futures U.S. | 2,500 MMBtu | USD/MMBtu | **FINANCIAL**; corresponding NG settlement one business day before NG's last scheduled trading day |
| [Waha Basis — WAH](https://www.ice.com/products/6590171/Waha-Basis-Future) | ICE Futures U.S. | 2,500 MMBtu | USD/MMBtu | **FINANCIAL**; own basis fixing, defined from Waha Inside FERC less corresponding NG final settlement |
| [Waha Fixed Price — FQW](https://www.ice.com/products/69723181/Waha-Fixed-Price-Future) | ICE Futures U.S. | 2,500 MMBtu | USD/MMBtu | **FINANCIAL**; specified Waha Inside FERC monthly index |
| [Light Sweet Crude Oil — CL](https://www.cmegroup.com/rulebook/NYMEX/2/200.pdf) | NYMEX | 1,000 US barrels | USD/barrel | **PHYSICAL**; eligible crude at Cushing, Oklahoma |
| [RBOB Gasoline — RB](https://www.cmegroup.com/rulebook/NYMEX/1a/191.pdf) | NYMEX | 42,000 US gallons | USD/gallon | **PHYSICAL**; specified gasoline blendstock in New York Harbor; quality requirements can depend on delivery season |
| [NY Harbor ULSD — HO](https://www.cmegroup.com/rulebook/NYMEX/1a/150.pdf) | NYMEX | 42,000 US gallons | USD/gallon | **PHYSICAL**; specified ultra-low-sulfur diesel in New York Harbor |
| [Ethane, OPIS Mt. Belvieu Non-TET — ETE](https://www.ice.com/products/6590286) | ICE Futures U.S. | 1,000 barrels = 42,000 gallons | USD/gallon | **FINANCIAL**; average of applicable OPIS daily Purity Ethane assessments during the contract period |
| [WTI Financial — CSX / CS](https://www.cmegroup.com/rulebook/NYMEX/5/510.pdf) | NYMEX | 1,000 barrels | USD/barrel | **FINANCIAL**; calendar-period arithmetic average of first-nearby CL daily settlements |
| [WTI 1st Line — R](https://www.ice.com/products/6753542/WTI-1st-Line-Future) | ICE Futures U.S. | 1,000 barrels | USD/barrel | **FINANCIAL**; monthly average of NYMEX front-month WTI settlements |
| [EUA Futures — C / ECF](https://www.ice.com/products/197/EUA-Futures) | ICE Endex | 1,000 EU allowances | EUR/tonne CO2 equivalent | **PHYSICAL**; registry transfer of EU allowances, each representing one tonne CO2 equivalent |
| [CCA Specific Vintage 2026 — CCU](https://www.ice.com/products/82612871/California-Carbon-Allowance-Specific-Vintage-2026-Future) | ICE Futures U.S. | 1,000 allowances | USD/allowance | **PHYSICAL**; California MTS transfer, specified vintage only |
| [CCA Vintage 2026 — CB6](https://www.ice.com/products/82612870/California-Carbon-Allowance-Vintage-2026-Future) | ICE Futures U.S. | 1,000 allowances | USD/allowance | **PHYSICAL**; broader vintage eligibility, including prior vintages under the product rules |
| [Copper — HG](https://www.cmegroup.com/rulebook/COMEX/1a/111.pdf) | COMEX | 25,000 pounds | USD/pound | **PHYSICAL**; approved Grade 1 copper cathodes at designated warehouses |

Identifiers need namespaces: CSX is the Globex code and CS the ClearPort code; C and ECF are different ICE identifier fields. The identifier alone should not be treated as a globally unique product key. [CME CSX/CS filing](https://www.cmegroup.com/content/dam/cmegroup/market-regulation/rule-filings/2024/3/24-061_1.pdf), [ICE EUA identifiers](https://www.ice.com/products/197/EUA-Futures).

### What the examples require us to distinguish

**Averaging.** ETE uses OPIS publication dates and the daily assessment field named “Average”; averaging those observations is a second operation. The source assessment is in cents/gallon, requiring normalization to the contract's dollars/gallon. An execution during the month still references the product's full observation period. [ETE specification](https://www.ice.com/products/6590286).

WTI Financial requires a first-nearby selection rule across dates; the selected CL maturity can change within the month. The exact roll boundary needs confirmation before implementation. Its rules also permit quarterly, semiannual and annual periods while retaining the 1,000-barrel lot. Period length therefore cannot determine quantity. “Calendar swap” here means a calendar-period average, not a two-maturity calendar spread. [WTI Financial rules](https://www.cmegroup.com/rulebook/NYMEX/5/510.pdf).

**Own market versus final-price methodology.** WAH trades as one basis index. Similarly, a traded average-price future can be valued from its own market price. Reconstructing a price from underlying observations/curves is an explicit valuation choice, with its own dependency mapping. It is not implied merely by a product's final fixing formula.

**Delivery assets.** Allowance program, registry and eligible vintage identify what can be delivered. Vintage is separate from futures delivery month. A tonne CO2 equivalent is an emissions measure, not permission to interchange EUA and CCA assets or to convert allowances as ordinary commodity mass. [EUA](https://www.ice.com/products/197/EUA-Futures), [specific-vintage CCA](https://www.ice.com/products/82612871/California-Carbon-Allowance-Specific-Vintage-2026-Future), [standard-vintage CCA](https://www.ice.com/products/82612870/California-Carbon-Allowance-Vintage-2026-Future).

**Copper.** HG has a $0.0005/pound ordinary tick, worth $12.50 per nominal lot. Actual delivery weight can vary by ±2%. The lot used for futures exposure and the weight on a delivery invoice are different facts. [Copper rules](https://www.cmegroup.com/rulebook/COMEX/1a/111.pdf).

## 3. Exchange, clearing house and clearing firm

"ICE versus CME" is useful shorthand for exchange groups, but insufficient for identifying how a trade is listed, executed and cleared.

The labels below distinguish venue and account concepts; they are not additional accepted ticket headers. The current instrument definition alone establishes allowed fields.

| Research term | Meaning | Sample values | Possible source |
|---|---|---|---|
| `exchange_group` | Corporate grouping; useful for display | CME Group; ICE | Shared exchange reference |
| `listing_exchange` | Exchange listing the contract | NYMEX; COMEX; ICE Futures U.S.; ICE Endex | Product specification |
| `execution_venue` | Where this particular execution occurred, when recorded | CME Globex; configured ICE execution venue | Execution record |
| `execution_method` | How it was executed | Screen; block; other supported exchange method | Execution record and applicable method definition |
| `clearing_house` | Central counterparty/clearing organization | CME Clearing; ICE Clear Europe | Product-compatible clearing route |
| `clearing_firm` | Firm clearing/carrying the customer's trade | Configured firm reference, e.g. fictional `Firm A` | Account/template or trade allocation |
| `clearing_account` | Account at that firm | Fictional `Metals-01` | Account/template or trade allocation |
| `executing_broker` | Broker handling execution, if applicable | Configured broker reference | Execution record |

These are references to configured entities, not exhaustive hardcoded enums. An FCM is a futures commission merchant; that is a firm role, not a synonym for an exchange or clearing house. The executing broker and clearing firm can differ. [CME clearing membership](https://www.cmegroup.com/clearing/membership.html).

| Contracts in this review | Listing exchange | Clearing house |
|---|---|---|
| NG, CL, RB, HO, CSX | NYMEX | CME Clearing |
| HG | COMEX | CME Clearing |
| PHH, WAH, FQW, ETE, R, CCU, CB6 | ICE Futures U.S. | ICE Clear Europe |
| EUA | ICE Endex | ICE Clear Europe |

The ICE Futures U.S. products selected here clear through ICE Clear Europe; an IFUS listing does not by itself imply ICE Clear U.S. [CME clearing membership](https://www.cmegroup.com/clearing/membership.html), [ICE Clear Europe scope](https://www.ice.com/clear-europe/regulation), [ICE energy/environmental fee schedule](https://www.ice.com/publicdocs/futures_us/IFUS_Energy_Fees.pdf).

## 4. What the research contributes to the field definition

The earlier wide field proposal is superseded. Use the [instrument field sketch](engineering-tickets/trade-valuation-pipeline/instrument-field-sketch.md) and [ShowInstrument spill](library/instruments/show-instrument.md) for exact names, requiredness, types and choices. In particular, `trade_id` is optional attribution; executed size uses `quantity`, `quantity_unit` and `quantity_per`; the agreed price field is `fixed_price`. Retained occurrence identity does not depend on a user-supplied trade identifier. The former `signed_lots` and `agreed_trade_price` names are not accepted aliases.

This research identifies facts the design must obtain from an appropriate source. It does not establish a trade column for every fact:

| Research distinction | Current design boundary |
|---|---|
| Quote currency/unit, amount currency and quantity category | Static Index conventions; creation validates compatible quantity and price terms |
| Lot size/unit and per-lot fee rates | Named row in `index.specifications`, selected by `quantity_unit`, the desk's word for a quantity of the index |
| Listed contract and observation dates | Static schedule and supported `schedule_method`, resolved once during creation |
| Published observations versus current prices | History enters PrepareTrades; live prices enter EvaluateTrades |
| Observation, expiry and payment dates | Distinct facts; supported payment terms resolve explicit payment dates during creation |
| Delivery eligibility, allowances/vintage, actual weight, warehouse and registry events | Contract research for later scope; physical delivery processing is outside v1 |
| Execution venue, firm/account and operational allocations | Research context, not arbitrary metadata permitted by the current definition |
| Daily variation cash and collateral treatment | Separate economic concepts; margining is outside v1 |

The present `ContractSpecifications` object supplies lot/unit/fee arrays, not the entire exchange rulebook. Static product facts needed for a supported schedule or payment anchor must be provided explicitly; a clearing-house string or specification display name is insufficient. The [creation specification](engineering-tickets/trade-valuation-pipeline/create-trade.md) records the Index source and the remaining input-placement decision.

### Dates and calendars: retained exchange evidence

These are different events, not aliases for one settlement date:

| Example | Scheduling lesson |
|---|---|
| PHH | Own expiry is four business days before the contract month; its fixing selects NG's penultimate settlement; final payment is the next clearing business day. [ICE](https://www.ice.com/products/6590264) |
| WAH / FQW | Trading ends before the contract month; the relevant Waha publication can arrive afterward; payment is third clearing business day after last trade. [WAH](https://www.ice.com/products/6590171/Waha-Basis-Future), [FQW](https://www.ice.com/products/69723181/Waha-Fixed-Price-Future) |
| ETE / R | Observation period, expiry and final payment are separate; final payment is second clearing business day after last trade. Resolve exact expiry from the exchange schedule. [ETE](https://www.ice.com/products/6590286), [R](https://www.ice.com/products/6753542/WTI-1st-Line-Future) |
| CL | Expiry is in the preceding month under the 25th-day rule; delivery is in the contract month; invoice payment has a following-month rule. [CME](https://www.cmegroup.com/rulebook/NYMEX/2/200.pdf) |
| HG | Last trade is third-last business day of delivery month, while delivery can run from its first through last business day. Delivery can precede expiry. [COMEX](https://www.cmegroup.com/rulebook/COMEX/1a/111.pdf) |

The accepted initial payment fields are `payment_time_lag` and `payment_holiday_calendar`; their supported anchor/counting rules are described in the [fixing and payment specification](engineering-tickets/trade-valuation-pipeline/fixing-and-payment-state.md). This limited rule does not claim to express all bilateral or delivery-invoice conventions.

Metals notice and invoice rules also use actual delivery events: first notice is the prior month's last business day, and the invoice carries actual warrant, weight, brand and warehouse details. Those are later lifecycle facts, not required v1 ticket fields. [NYMEX/COMEX Chapter 7, Rule 706](https://www.cmegroup.com/rulebook/NYMEX/1/7.pdf).

Missing observations cannot be silently treated as zero or skipped. Preparation needs an explicit distinction between a non-publication date and a required fixing that is absent. Publication/cutoff details remain a binding decision in the current packet; this survey does not invent a fallback.

## 5. A small trade entry still refers to richer definitions

A hypothetical HG trade with `contract_code = Z26`, `quantity = +10`, a `quantity_unit` naming the index's 25,000-LB contract specification, `quantity_per = month` and `fixed_price = 4.25` has nominal exposure of +250,000 LB under that specification. The user does not type copper grade, tick or eligible warehouse lists into every trade. [Copper specification](https://www.cmegroup.com/rulebook/COMEX/1a/111.pdf), [COMEX clearing membership](https://www.cmegroup.com/clearing/membership/comex.html).

This is an economic illustration, not a complete constructible v1 ticket or a claim that the copper product path is implemented. The current [NG worked example](engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md) demonstrates shared template terms, disjoint ticket fields, static encoding and preparation. Immutable resolved values/references preserve executed terms when a user later constructs a different template.

## 6. Individual records and array aggregation

Retain trade occurrences even when preparation and market reads are shared. These hypothetical HG trades share product, period and account:

| Trade | Signed lots | Agreed USD/LB | Signed nominal LB | Signed price constant, USD |
|---|---:|---:|---:|---:|
| T-001 | +10 | 4.25 | +250,000 | +1,062,500 |
| T-002 | -4 | 4.30 | -100,000 | -430,000 |
| Aggregate | +6 | No single price required | +150,000 | +632,500 |

The price constant is signed nominal quantity multiplied by agreed price. It is an arithmetic term, not an upfront futures purchase payment. At an illustrative current market price of 4.40 USD/LB, combined gross P&L since execution is:

`150,000 × 4.40 − 632,500 = USD 27,500`

This is an arithmetic illustration before fees and delivery effects, not a statement that USD 27,500 is currently unpaid or is a discounted present value. Reconciling actual paid/unpaid cash would require variation cash history, which is outside v1. The pipeline's modeled cleared mark/cash instead uses the explicit fixing and payment-date rules in the [result contract](engineering-tickets/trade-valuation-pipeline/05-results.md). If buys and sells net to zero quantity, their price constants can still leave nonzero P&L; net lots and an average entry price are not a sufficient general representation.

The agreed preparation retains aggregate compatible live exposures and fixed/set contributions. The source batch preserves occurrences and component/payment mappings; this does not require one output per trade at every tick. Simple listed futures can share market reads and arithmetic. Averaging dependencies are prepared only when required by the chosen valuation/fixing calculation. A matrix or sparse representation is justified by actual dimensions and measured work, rather than by the trade object's shape.

| Aggregation purpose | Preserve |
|---|---|
| Share market reads | Exact index/market-point identity and snapshot |
| Combine linear exposure | Converted units, compatible market point, signed exposure and constants; retain trade mapping |
| Combine cash/operational positions | Currency, cash dates, legal entity, clearing house/firm/account and applicable netting rules |
| Combine delivery obligations | Deliverable eligibility, vintage, location, delivery window and actual allocations |

The last two rows are research boundaries, not v1 operational netting or delivery requirements.

Different accounts can share numerical work without becoming one legally netted position. Different payment dates can share price gathering without becoming one discounted payment. Distinct product prices or allowance assets remain distinct even when the commodity label or emissions measure looks similar.

## 7. Cleared swaps and the futures template

**Preserve the contractual distinction; share numerical work where the actual terms permit it.** The products surveyed so far do not demonstrate a need for a separate cleared-swap pricing family. Several products that traders discuss as swaps are formally futures.

| Example | Verified contract form | Implication for this design |
|---|---|---|
| WTI Financial, CS/CSX | NYMEX future with averaging | Fits the futures template with its own fixing and schedule definition. [CME rules](https://www.cmegroup.com/rulebook/NYMEX/5/510.pdf) |
| WTI 1st Line, R | ICE financial future | Monthly average-price economics do not establish swap legal form. [ICE specification](https://www.ice.com/products/6753542/WTI-1st-Line-Future) |
| Henry Penultimate, PHH | ICE financial future | Penultimate reference selection belongs in the product's terms. [ICE specification](https://www.ice.com/products/6590264) |
| Waha Basis, WAH | ICE financial future | Its basis economics remain a single listed product. [ICE specification](https://www.ice.com/products/6590171/Waha-Basis-Future) |

There is a historical reason for overlapping terminology: ICE transitioned its cleared OTC energy swaps to economically equivalent futures in October 2012. That historical change should not be confused with the current classification of every instrument someone calls a swap. [ICE transition announcement](https://ir.theice.com/press/news-details/2012/ICE-Completes-Transition-of-Energy-Swaps-to-Futures/default.aspx).

CME ClearPort is a clearing service covering multiple contract forms. Submission through it does not, by itself, establish that a trade is a swap. Similarly, a privately negotiated futures block remains a futures transaction. Identify the actual cleared product and rulebook. [CME ClearPort](https://www.cmegroup.com/clearport.html), [CME block trades](https://www.cmegroup.com/clearing/trading-practices/block-trades.html).

If the project adds a true cleared swap, these are research dimensions to review, not new accepted field names or enumerations:

| Dimension | Proposed values / source | Why retain it |
|---|---|---|
| Contract form | `FUTURE` / `SWAP`, supplied by product definition | Preserves the contractual identity; it is not inferred from the payoff or execution channel |
| Clearing arrangement | `CENTRALLY_CLEARED` / `BILATERAL`, supplied by executed terms and clearing records | Independent of contract form; a swap can be centrally cleared |
| Final settlement form | Existing `PHYSICAL` / `FINANCIAL` | Independent of whether the instrument is a future or swap |
| Cash and margin rules | Shared rule reference | Establish what cash settles exposure, what constitutes collateral, and any interest treatment |
| Contract/payment schedule | Shared rules plus resolved dates | A listed contract code or explicit periods must retain actual fixing and payment timing |
| Clearing house, firm, account | Existing references | Retain the applicable clearing and account relationship |

This table is historical terminology for a possible extension. The current template identifies its instrument through the first argument to CreateTradeTemplate; the field names and choices come from the approved instrument definition. The table neither adds an `instrument_type` ticket field nor defines a swap schema. Margining and actual bank-cash reconciliation are outside v1; route-specific modeled mark/cash remain part of the [result contract](engineering-tickets/trade-valuation-pipeline/05-results.md).

Daily cash movement alone is insufficient to prove equivalence. Cleared derivatives can use cash as settlement of exposure or as collateral against it; the applicable contractual treatment determines the cash/value split. Do not infer a universal futures-versus-swaps rule from the label. [Federal Reserve explanation of cleared-derivative settlement models](https://www.federalreserve.gov/frrs/guidance/regulatory-capital-treatment-of-certain-centrally-cleared-derivative-contracts-under-regulatory-capital-rules.htm).

For an actual swap, check fixing dates, payment dates, quantity profiles, cash treatment and applicable discounting against the proposed equivalent future. Identical final-price formulas alone do not establish identical value or settlement obligations. Compatible observations, exposures and payment calculations can still share arrays and one batch evaluation path.

No currently offered true cleared CL/Henry Hub swap was verified for this report. The concrete examples above are futures. The recommendation is to keep the classification explicit and defer additional swap-specific machinery until a real product or confirmation supplies terms that require it.

## 8. Current authority and remaining product research

The current project already has an `Index` holding schedule, conventions and specification references; price and position quantity units can differ. `FuturesSchedule.codes` already stores contract codes alongside expiry dates; explicit trade binding and strip expansion are proposed uses/extensions, not functionality established by the presence of those codes. Existing specifications contain lot sizes and brokerage/clearing fee arrays. Their names, and index display names, are not a canonical product registry. [Index implementation](../src/catalyst/index_definitions/index.py), [specifications](../src/catalyst/index_definitions/contract_specifications.py).

This report proposes richer settlement, venue, delivery and fixing definitions. It does not imply they already exist. EUR requires changes to the current USD/CENT conventions, and allowances need a suitable asset/quantity representation. The current futures schedule stores expiry information, not the full generic observation/notice/delivery/payment model above. [Conventions](../src/catalyst/index_definitions/index_conventions.py), [futures schedule](../src/catalyst/index_definitions/futures_schedule.py), [unit definitions](../src/catalyst/globals/unit_conversions.py).

The [pipeline overview](engineering-tickets/trade-valuation-pipeline/README.md) supplies the current implementation sequence and open decisions. The [NG creation/preparation example](engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md) already supplies the initial hand calculations and array sketch. Begin with that bounded path; implementing or resolving every product in this survey is not a prerequisite.

Later product slices need their own authoritative facts, such as the WTI first-nearby roll boundary and applicable expiry/payment calendars. Preserve the distinctions researched here while adding only reviewed fields to the instrument definition. Template and ticket sources remain disjoint; static facts resolve during CreateTrades; history changes prepare afresh; compatible price ticks evaluate the retained preparation.

Physical delivery processing, margining, order execution and a universal legal trade-capture schema remain outside v1. Research on their identities and dates does not authorize those workflows or make them prerequisites for the first valuation path.

## 9. Assessment of the two Priceratops engineers' recommendations

This historical assessment compares two engineers' advice supplied in the design conversation. The second engineer's pasted summary was a local attachment, not a repository artifact; its linked full source was inaccessible. Priceratops code, historical counts and measurements were not independently audited for this assessment; they are reported experience. Both engineers examined the same earlier project, so agreement between them is not independent validation of every proposed choice.

**Assessment: substantial architectural agreement, with different emphasis. Our independent contract research supports the common direction and supplies constraints on its application.** The first engineer is more cautious about representation size and futures settlement. The second is more explicit about one linear kernel, legs as data, unit/sign normalization, direct risk and independent expected results.

### Comparing their advice

| Topic | First engineer | Second engineer | Assessment |
|---|---|---|---|
| Separation of work | Describe, prepare, gather inputs, calculate/report | Build rows, then price rows | Compatible descriptions at different levels. Preserve input gathering as an identifiable shared step |
| Common arithmetic | Constant plus weighted prices; payment amounts before valuation | One discounted linear formula and row builders | Same mathematical foundation; the second states its universality more strongly |
| Product identity | Recognizable products sharing mechanics | A fixed instrument vocabulary familiar to the desk | Keep product meaning; do not create a pricing class for every index or convention |
| Stable preparation | Reuse calendars, referenced contracts and weights | Trades do not rebuild on market-price refresh | Direct agreement |
| Actual legs | Each leg has its own index, dates and conventions | Legs are explicit data, not hidden inside pricing or nine secondary columns | Compatible; only actual contractual legs warrant that representation |
| Performance | Avoid repeated traversal and expanded intermediate rows | Convert once, resolve once, keep arrays | Complementary; arithmetic speed does not establish representation efficiency |
| Tests | Worked examples plus initial/repeat/update measurements | Hand-derived expectations, deliberate failures and chosen tolerance | The second adds useful specificity |
| Build order | Cash and swaps before futures | Cash, futures, then averaging and basis | A sequencing difference. Our futures-first progression remains the project choice |

### Qualifications we should retain

1. **Static trades, separate market inputs.** The user confirmed that “trades hold no prices” means no changing market-price snapshot. Agreed execution price remains part of the static trade. Published fixings and settlement history are separate dated inputs/state, rather than mutations of the executed terms.

2. **A common linear calculation is not a complete futures settlement model.** For a prepared component, `amount = constant + sum(coefficient × market_price)` is a useful common form. Coefficients can include each exposure's sign, quantity and unit scales. The first engineer's form is more general than factoring one quantity outside several differently sized legs. Payment dates, currencies, already-settled cash, variation treatment and delivery obligations still need their own rules. A price constant is not proof of a cash payment.

3. **Legs, strip constituents and fixing observations are different structures.** A listed Waha basis future remains one index. An ethane averaging future remains one listed contract. A defined `Cal27` strip contains actual monthly contract positions. A negotiated two-index swap can have actual contractual legs, each with its own terms. An array may combine their arithmetic without making their trade records interchangeable.

4. **Direct delta needs a named market input.** With fixed coefficients, sensitivity to the selected independent price inputs follows directly from those coefficients; discounting adds its factor where applicable. That does not automatically supply rate risk, FX risk or risk through a curve-building model. A future marked to its own ETE price has quantity-based sensitivity to that price. A reconstruction from daily observations has a different dependency mapping. Fixed observations lose forward-price sensitivity within that reconstruction; their arrival does not automatically shrink delta to an independently traded futures price.

5. **Templates supply shared terms once.** The template and ticket provide disjoint subsets of the approved fields. An overlap fails even for equal values; absent required economics and explicit blanks also fail. An arbitrary blank must not silently become zero, a side or a date. Creating a changed template must not mutate previously created trades.

6. **Do not import the old discounting menu.** The second summary reports policies such as fees/fixed legs always discounted, swaps only when bilateral and futures never. Those are another implementation's policies, not sufficient rules for our library. We need the actual cash treatment, payment dates and requested output. Discount compatible payments by their own dates; distinguish cumulative P&L, already-settled cash and outstanding value.

7. **A closed menu of economic forms need not close the index universe.** `FUTURE` and, eventually, genuine swap structures can have recognizable entry forms. `lastday` or `penultimate` can be defined convention selections. Neither requires hardcoding every exchange symbol as a separate instrument implementation.

### What our research has independently established

| Finding from our survey | Relationship to the advice |
|---|---|
| Small trade record referencing specifications, conventions and schedules | Supports stable structure separate from values and resolving meaning once |
| Explicit `contract_code` with resolved single-contract/strip binding | Makes the dependency mapping and original deal identity concrete |
| Different exchange, clearing house, firm and account | Demonstrates why shared arithmetic cannot imply operational or legal netting |
| Separate expiry, observation/publication, notice, delivery and payment dates | Supports payment-specific treatment and qualifies a universal discounted row |
| Different price/position units, EUR and distinct allowance assets | Reinforces conversion once, explicit currencies and compatibility validation |
| Standalone basis and averaging futures | Prevents creating artificial trade legs or silently reconstructing their markets |
| Preserved trade occurrences and signed price constants | Supports aggregation without losing attribution or zero-net-position P&L |

The field survey contributes product meaning. The current pipeline packet now establishes the preparation and aggregate-result responsibility boundaries, with remaining function and rates decisions recorded there. This survey does not freeze those representations or require every product and delivery workflow before pricing one future.

### What their measurements do and do not establish

| Reported experiment | Boundary | What it supports |
|---|---|---|
| First engineer: 5,000 swaps, 5.16 seconds to 0.38 seconds | Python evaluation, publication and aggregate readers; excludes Excel | Batching and removing repeated work can materially improve a meaningful refresh boundary |
| Second engineer: 5,000 swaps, 2.2 milliseconds build and 0.4 milliseconds price | NumPy demonstration excluding calendar/date construction | Prepared arithmetic can be cheap; this is not a comparable end-to-end result |

These are different workloads/boundaries and cannot establish a relative speedup between the proposed designs. The first account's rejected representation with roughly 30 times as many intermediate rows remains a relevant warning. For Catalyst, use work counts and representation sizes: preparation builds, calendar work, market points gathered, components evaluated and temporary allocation size. Timings can supplement those observations, not replace correctness or work-budget checks.

### How to use the advice now

Keep the useful safeguards: explicit data, one normalization/sign contract, independent expected answers, tolerances and named linear price sensitivities. The current [NG worked example](engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md) has replaced the former request to create an NG example. It covers opposite signs, duplicate occurrences and aggregate exposure over two contracts; its real NG scope is open-contract economic mark. A separate toy lifecycle example covers fixing/payment transitions without inventing a financial final payment for physical NG.

The [pipeline packet](engineering-tickets/trade-valuation-pipeline/README.md) controls implementation order. Preparation is explicit and retained, evaluation returns the supplied collection's aggregate results, and readers do no pricing. Complete the bounded first path and its acceptance checks before broadening products. Exact-date/CFD inputs and two-index basis swaps are deferred. The bilateral rates and payment work remains a separately specified slice; no private history cache or generic product hierarchy is a prerequisite.

## 10. Where rates enter the calculation

The trade is static. Current commodity prices, discount curves, fixings and settlement state are inputs to valuation. Separating amount calculation from valuation means two connected operations over shared prepared data, not two independent traversals of the trade:

```text
projected_amounts = constants + commodity_exposures @ commodity_prices
payment_values    = projected_amounts * payment_date_discount_factors
collection_value  = sum(payment_values)
```

This illustrates valuation of future-dated cash payments under an explicit model; it is not a settled bilateral API. A floating payment's projected amount is not an already-known cash amount; uncertainty and any projection assumptions remain identifiable. The arithmetic does not authorize treating every future as one discounted terminal payment.

| Layer | Rates-related information |
|---|---|
| Static trade/shared terms | Payment currency and date rules; contractual settlement/collateral agreement where applicable |
| Prepared data | Payment dates, payment treatment, curve-selection keys and mappings back to trades |
| Valuation inputs | As-of date, supplied discount curves, commodity market inputs and current settlement state |
| Valuation operation | Select the applicable curve, gather the payment-date factors and apply them to eligible outstanding payments |

A curve-selection policy maps currency and the applicable agreement/treatment to a supplied curve. Currency alone need not determine the correct curve. Neither today's interest rate nor today's discount factor belongs in the static trade.

### Why payment dates survive aggregation

For two known, unpaid USD cash amounts under one chosen curve:

| Payment | Amount | Discount factor | Present value |
|---|---:|---:|---:|
| Earlier receipt | +2,000 | 0.99 | +1,980 |
| Later payment | -2,000 | 0.97 | -1,940 |
| Total | 0 | — | +40 |

Netting the nominal amounts before discounting would lose the USD 40. Amounts sharing currency, date and valuation treatment can share the numerical operation, while retaining attribution and operational-account boundaries.

For an illustrative bilateral gas payment, 10,000 MMBtu times a projected price difference of 0.20 USD/MMBtu gives a projected USD 2,000 payment. At a factor of 0.99 its modeled PV is USD 1,980. Holding that commodity projection fixed, changing the factor to 0.98 changes PV to USD 1,960. Once the fixing establishes the nominal amount, commodity-price sensitivity ends for that fixed payment, but discount sensitivity remains until payment. Once paid, it belongs to settled cash, not the future-receivable calculation.

For an exchange future, the same USD 2,000 difference relative to original execution instead measures cumulative price P&L. Settlement variation moves cash during the contract's life; do not discount that entire cumulative P&L to expiry. Outstanding settlement, collateral/funding, delivery invoices and a futures-to-forward adjustment are distinct calculations if required. [CME futures money calculations](https://www.cmegroup.com/clearing/files/CME-Money-Calculations-Futures-and-Options.pdf).

### Existing support and remaining work

Catalyst already has an immutable daily `DiscountCurve` of dates and factors, built from supplied anchors with linear interpolation in factors. It starts at factor 1, rejects extrapolation in its construction, and enforces positive, non-increasing factors. The latter is an already accepted limitation on negative-rate curves. It is a useful array building block, not a complete curve-selection or trade-valuation system. [Current curve implementation](../src/catalyst/globals/discount_curve.py), [curve contract and deferred pricing work](library/globals/discount-curve.md).

The later rates slice must establish curve selection, valuation-date alignment and payment-date coverage; no silent extension or reuse of yesterday's anchored factors. For an initial implementation, requiring curve start to equal valuation date is a proposed explicit policy, not existing consumer behavior. Building curves from rate instruments can remain outside the first instrument implementation: supplied discount factors are sufficient to establish the interface.

Rate risk also needs a definition. With commodity projections held fixed, direct discount risk is `sum(amount × change_in_discount_factor)`. Sensitivity to supplied DF anchors is not automatically sensitivity to market rate instruments. A DV01 requires a declared rate-bump/curve mapping. If commodity projections themselves depend on rates, total rate sensitivity also includes that dependency.

### Reuse across updates

| Changed input | Work to share/reuse | Work potentially affected |
|---|---|---|
| Commodity market price | Contract structure, dates, unit factors, unchanged discount factors | Dependent projected amounts and values |
| Rates/discount factors on the same grid | Contract structure and commodity amount calculation | Discount gathers, present values and relevant risk |
| New fixing | Unchanged contract terms and payment schedule | Known/projected split and affected sensitivities |
| Valuation date or settlement event | Static trade and still-valid definitions | Curve alignment, outstanding/paid classification and affected preparation |

Gather shared curve/date combinations once where useful. Cache positions into a curve only with its grid identity: a changed curve start changes the array offsets. These are proposed work boundaries; the choice between selective recalculation and a compact full batch should be measured.

Historical performance evidence and the updated independent review scope are in the [review brief](independent-review-brief.md).
