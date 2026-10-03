# Futures trade representation: contract survey and proposed fields

Review draft · 27 September 2026 · Goosedove

This report consolidates Henry Hub, Waha, crude oil, refined products, ethane, carbon allowances and COMEX copper. Exchange facts are linked to primary sources. Field names and enumerations below are design proposals, not an implemented API. Sample trades and firm/account names are fictional.

## 1. Recommended shape

Use one broad **futures trade template**, optionally narrowed by product, contract period, book and clearing account. Individual details complete the executed deal. Together they resolve once into a complete trade with references to shared definitions.

The field universe is larger than the trade-entry form:

| Component | What it contains |
|---|---|
| Trade template | Reusable defaults or selections, such as an index, specification, book or account |
| Individual trade details | Executed facts: trade identifier, trade date, quantity, agreed price, and selections left open by the template |
| Shared definitions | Product identity, conventions, lot size, settlement terms, fixing methodology, delivery eligibility and date rules |
| Resolved contract schedule | Applicable observation, trading, notice, delivery and payment dates |
| Valuation inputs and lifecycle records | Current prices, published fixings, cash already settled, allocations and actual delivery events |

**A template default and an exchange-defined fact have different authority.** Details can replace a default month or book. Selecting a listed product determines its lot size and final settlement form. A conflicting override must fail or select a different product/specification; it cannot quietly turn a physical future into a financial one.

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

Use the resolved choice **`SINGLE_CONTRACT` / `STRIP`** rather than infer structure from the code's spelling. This is separate from the fixing method: one contract can average daily prices, and a strip can contain averaging contracts. A product may also define a single longer-period averaging instrument; a year label alone is not authority to expand it into twelve contracts. WTI Financial's rules describe longer-period averaging contracts, but the applicable listing/contract definition must establish the actual binding. [CME Chapter 510](https://www.cmegroup.com/rulebook/NYMEX/5/510.pdf).

“Bullet” can remain a desk term, but it should not silently mean both “one listed maturity” and “one observation or payment.” Those are separate facts.

For a strip, preserve one deal/package identity and resolve its constituents once. Define quantity explicitly: for an equal monthly strip with one lot of each month per strip unit, **+10 strip units means +10 lots in each month, or 120 monthly lots total**. The component-lot ratios belong in the shared strip definition. Keep the agreed package price and the actual component execution prices or an explicit allocation rule; an average package price does not prove that every month executed at that price.

| Conditional strip information | Domain / sample | Purpose |
|---|---|---|
| `strip_definition_ref` | Reference: NG calendar-year strip definition | Defines accepted alias, constituent selection and lot ratios |
| `signed_strip_units` | Signed whole count: `+10` | Multiplies component lots per strip unit; single contracts continue to use `signed_lots` |
| `component_contracts`, `component_lot_ratios` | Resolved arrays: twelve monthly codes, twelve ratios of `1` | Preserve each listed contract, market point and schedule |
| `agreed_package_price`, `component_execution_prices` | Price plus reported/explicitly allocated component prices | Preserve executed terms and support monthly cash/P&L attribution |

This extends the user's compact trade entry, not the meaning of an individual listed future. The prepared path receives per-contract arrays for both one-contract trades and strips.

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

“ICE versus CME” is useful shorthand for exchange groups, but insufficient for identifying how a trade is listed, executed and cleared.

| Field | Meaning | Sample values | Usually supplied by |
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

## 4. Proposed field universe

**Domain notation:** `Choice` means a deliberately limited set for this scope. `Reference` means a supplied definition or configured record: extensible, but validated, rather than arbitrary prose. `Value` means a typed number, date or identifier. A sample is not an exhaustive list unless explicitly called a choice.

The names describe information requirements. They do not prescribe one wide object or a new class for every group. References can expose facts without copying them into every trade. In the existing project, an index's display name is not a unique lookup key.

### A. Trade terms and booking information

| Proposed field | Domain / sample | Requirement and source |
|---|---|---|
| `trade_id` | Value: `T-000123` | Required booking identity; can be generated. Equal economics do not mean the same trade |
| `trade_date` | Value: `2026-09-25` | Required executed deal date; preserve the exchange business date where applicable |
| `execution_timestamp` | Value: `2026-09-25T14:30:00-04:00` | Optional precision; does not replace trade date |
| `index_ref` | Reference: any supplied compatible futures index | Required selection, from template or details |
| `contract_spec_ref` | Reference: chosen contract specification for that index | Required selection; may be determined by a product template |
| `contract_code` | Defined code: `Z26`; defined strip alias: `Cal27` | Required binding selection, from template or details; resolve within the selected product/specification |
| `resolved_contract_binding` | Derived choice: `SINGLE_CONTRACT`, `STRIP` | Determined by the supplied contract/strip definition, not separately overridden |
| `contract_period` | Resolved period: December 2026 or calendar 2027 | Describes the selected binding; period dates alone are not its identity |
| `signed_lots` | Value: `+10`, `-4` | Required for a single contract; nonzero signed whole lots. Positive buy, negative sell. Strips use defined units and component ratios as above |
| `agreed_trade_price` | Value: `4.25`, in selected product units | Required for a single contract; preserve package/component prices for strips. Product rules govern validity; no universal positive-price requirement |
| `legal_entity_ref` | Reference: fictional `TradingCo` | Required for operational positions; template/account may supply it |
| `book_ref` | Reference: fictional `Metals` | Booking allocation; template/details |
| `clearing_route_ref` | Reference: allowed product/house route | Usually determined by the product; validate any selectable route |
| `clearing_firm_ref`, `clearing_account_ref` | References: `Firm A`, `Metals-01` | Required for a booked cleared position; an analytical example can omit them explicitly |
| `execution_venue_ref`, `execution_method_ref` | References: venue and supported method | Optional for pricing; useful execution provenance |
| `executing_broker_ref` | Reference | Conditional on broker involvement |
| `external_execution_id`, `external_clearing_id` | Namespaced identifiers | Optional reconciliation references; keep their namespaces |
| `fee_schedule_ref` | Reference to product/account fee terms | Optional pricing cost input; actual charges belong in fee events |
| `template_ref`, `template_revision` | Reference/value | Optional provenance; resolved terms must remain reproducible if defaults later change |

An entry form may expose `side = BUY / SELL` plus a positive lot count. Resolve that once to signed lots; avoid independently editable side and signed quantity in the economic representation. A contract month, book or index need not be re-entered if the template supplies it.

### B. Shared product specifications and conventions

| Proposed field | Domain / sample | Meaning |
|---|---|---|
| `instrument_type` | Choice for this template: `FUTURE` | Identifies the trade family; bilateral lookalikes will need their own contractual treatment |
| `product_ref`, `product_name` | Reference plus display text | Official product identity; display names are not sufficient keys |
| `external_product_codes` | Namespaced code collection | Example: Globex `CSX`, ClearPort `CS` |
| `definition_revision`, `effective_applicability` | Version reference/date or contract range | Proposed provenance for rules applicable to a contract; exchange amendments may apply by maturity |
| `listing_exchange_ref` | Reference | See venue table |
| `allowed_clearing_routes` | References | Permitted house/product combinations |
| `final_settlement_type` | **Choice: `PHYSICAL`, `FINANCIAL`** | Final obligation if carried into settlement; financial means cash here |
| `futures_cash_rule_ref` | Reference | Variation cash and final cash treatment, independently of physical/financial final settlement |
| `lot_size`, `lot_quantity_unit` | Positive value plus unit reference | Examples: 10,000 MMBtu; 25,000 LB |
| `quantity_measure` | Reference; examples `energy`, `volume`, `mass`, proposed allowance count | Restricts meaningful conversions |
| `position_quantity_unit` | Unit reference | Unit used for position/exposure reporting; may differ from price denominator |
| `price_currency`, `price_currency_unit` | Currency/unit references: USD and USD or US cents; EUR and EUR | Currency identity and fixed scale are separate |
| `price_denominator_unit` | Unit reference: MMBtu, BBL, GAL, LB, allowance, emissions tonne | Quantity to which one unit of price applies |
| `cash_currency` | Currency reference | Native settlement currency, distinct from chosen reporting currency |
| `price_increment_rule_ref` | Reference, possibly constant | HG ordinary tick 0.0005 USD/LB; ICE gas increments can depend on execution method |
| `settlement_precision_rule_ref` | Reference | Official settlement rounding/precision may differ from trading tick |
| `listing_schedule_ref` | Reference | Permitted contract periods and their identifiers |

Currency and unit choices are extensible reference values, not a permanent enum containing only today's examples. USD/cents conversion is fixed scaling. EUR/USD conversion requires market FX input. Price currency and cash currency coincide in the surveyed products; a future product with different currencies would require explicit contractual conversion terms. Choosing a reporting currency does not change those terms. The mapping from allowance count to an emissions-price denominator is asset-specific and does not establish fungibility across programs.

### C. Shared fixing and averaging definitions

| Proposed field | Domain / sample | Applicability |
|---|---|---|
| `daily_settlement_rule_ref` | Reference to own exchange settlement procedure | All futures; separate from a final fixing formula |
| `final_price_rule_ref` | Reference to structured final-price definition | All products; can select an exchange price, assessment or formula |
| `reference_price_refs` | One or more benchmark references | PHH: NG settlement; WAH: named Waha and NG inputs; ETE: specified OPIS assessment |
| `publisher_ref`, `assessment_field` | Reference/defined field | OPIS and its daily `Average` field, for example |
| `source_price_units` | Unit references | Normalize source inputs to product units once |
| `reference_contract_selection_ref` | Rule reference | Specified maturity; first nearby with an explicit roll convention |
| `observation_period_rule_ref` | Rule reference | Full contract month, defined multi-month period, selected settlement date |
| `observation_calendar_ref` | Calendar reference | Publisher observations can follow a different calendar from exchange trading |
| `observation_aggregation` | Initial choices: `SINGLE_OBSERVATION`, `ARITHMETIC_MEAN`, `WEIGHTED_MEAN` | Within a reference series; conditional, not a universal classification of the whole payoff |
| `observation_weight_rule_ref` | Rule reference | Equal eligible-date weights or explicitly specified weights; total quantity stays independent |
| `publication_and_revision_rule_ref` | Rule reference | Which publication/revision establishes the fixing, including official fallback provisions |

Missing data is not silently treated as a zero or skipped observation. The implementation must distinguish a non-publication date from an expected observation that is missing. No generic fallback should be invented in the trade template.

### D. Dates, calendars and physical delivery

| Proposed field | Domain / sample | Location |
|---|---|---|
| `trading_calendar_ref`, `trading_timezone` | Calendar/timezone references | Shared product definition |
| `expiry_rule_ref` | Rule reference | Shared; resolves to last trading date/time |
| `last_trade_datetime` | Date/time | Resolved listed contract schedule |
| `observation_dates`, `final_fixing_datetime` | Dates/times, when known | Resolved fixing schedule; publication may follow last trade |
| `first_notice_date`, `last_notice_date` | Conditional dates | Resolved physical contract schedule |
| `delivery_window_start`, `delivery_window_end` | Conditional dates/times | Resolved permitted delivery window |
| `final_cash_payment_rule_ref` | Rule/calendar reference | Financial final settlement; resolves to payment date(s) |
| `delivery_invoice_rule_ref` | Rule reference | Physical invoice price, quantity, charges and payment convention |
| `payment_calendar_ref` | Calendar reference | Clearing/banking calendar governing the relevant payment |
| `deliverable_asset_ref` | Reference | Copper cathodes, eligible crude, gas, EUA or CCA |
| `quality_eligibility_ref` | Structured rule/reference | Grade, approved brand, seasonal quality, permitted substitutes |
| `delivery_location_eligibility_ref` | Structured rule/reference | Hub, port, eligible warehouses or other approved locations |
| `delivery_method_ref` | Rule reference | Permitted commodity/title transfer, warehouse warrant, registry transfer |
| `delivery_quantity_tolerance` | Conditional numeric/rule reference | HG ±2% of nominal quantity, for example |
| `allowance_program_ref`, `registry_ref` | Conditional references | Carbon program and transfer registry |
| `vintage_eligibility_ref` | Conditional rule reference | Specified vintage only; broader permitted vintages and exceptions |

These are different events, not aliases for one `settlement_date`:

| Example | Scheduling lesson |
|---|---|
| PHH | Own expiry is four business days before the contract month; its fixing selects NG's penultimate settlement; final payment is the next clearing business day. [ICE](https://www.ice.com/products/6590264) |
| WAH / FQW | Trading ends before the contract month; the relevant Waha publication can arrive afterward; payment is third clearing business day after last trade. [WAH](https://www.ice.com/products/6590171/Waha-Basis-Future), [FQW](https://www.ice.com/products/69723181/Waha-Fixed-Price-Future) |
| ETE / R | Observation period, expiry and final payment are separate; final payment is second clearing business day after last trade. Resolve exact expiry from the exchange schedule. [ETE](https://www.ice.com/products/6590286), [R](https://www.ice.com/products/6753542/WTI-1st-Line-Future) |
| CL | Expiry is in the preceding month under the 25th-day rule; delivery is in the contract month; invoice payment has a following-month rule. [CME](https://www.cmegroup.com/rulebook/NYMEX/2/200.pdf) |
| HG | Last trade is third-last business day of delivery month, while delivery can run from its first through last business day. Delivery can precede expiry. [COMEX](https://www.cmegroup.com/rulebook/COMEX/1a/111.pdf) |

Metals notice and invoice rules also use actual delivery events: first notice is the prior month's last business day, and the invoice carries actual warrant, weight, brand and warehouse details. Store these events when known rather than require a specific warrant at trade inception. [NYMEX/COMEX Chapter 7, Rule 706](https://www.cmegroup.com/rulebook/NYMEX/1/7.pdf).

### E. Current state and calculation inputs

Keep these alongside the immutable trade terms, supplied as dated inputs or events:

| Field/input group | Examples | Why separate |
|---|---|---|
| Valuation context | As-of date/time, market snapshot, reporting currency, FX inputs | The same trade can be valued repeatedly |
| Market observations | Own current market price, published benchmark fixings | Changing values do not change executed terms |
| Variation settlement state | Prior settlement basis, settlement dates, cash paid/received | Agreed price alone cannot identify unpaid versus already settled P&L |
| Position/lifecycle events | Corrections, cancellations, transfers, allocations, delivery obligations | Preserve history and distinguish transaction identity from current position |
| Delivery events | Actual weight, warrant, warehouse, registry transfer, invoice date and amount | Some facts are unknown until delivery |
| Actual fee events | Brokerage and clearing charges, currency and charge date | Can differ from template fee estimates |

A lifecycle-status dropdown would require a separately reviewed event model. Avoid one boolean `settled` for a future that has daily cash settlement, possible open exposure and a later delivery obligation.

## 5. A small trade entry form can still cover this universe

Illustrative copper template and trade, using hypothetical prices:

| Field | Template supplies | Individual details supply | Resolved result |
|---|---|---|---|
| Trade type | FUTURE | — | FUTURE |
| Index / specification | HG index and COMEX copper specification | — | Selected HG contract definition |
| Contract code | Left open | Z26 | Single listed December 2026 contract |
| Trade ID | — | T-001 | T-001 |
| Trade date | — | 2026-09-25 | 2026-09-25 |
| Signed lots | — | +10 | +10 |
| Agreed price | — | 4.25 | 4.25 USD/LB |
| Legal entity / book | TradingCo / Metals | — | TradingCo / Metals |
| Clearing firm / account | Firm A / Metals-01 | — | Firm A / Metals-01 |

Product selection supplies COMEX, CME Clearing, physical final settlement, 25,000 LB per lot and the price convention. Nominal exposure is therefore +250,000 LB. The user does not type grade, tick, first-notice rules or eligible warehouse lists into every trade. [Copper specification](https://www.cmegroup.com/rulebook/COMEX/1a/111.pdf), [COMEX clearing membership](https://www.cmegroup.com/clearing/membership/comex.html).

A broader template could leave index/specification open. A narrower template could also supply the month. Shared definitions can be reused without requiring any template at all. Preserve the resolved immutable references/values so editing a reusable default does not silently rewrite old executions.

## 6. Individual records and array aggregation

Retain trade occurrences even when preparation and market reads are shared. These hypothetical HG trades share product, period and account:

| Trade | Signed lots | Agreed USD/LB | Signed nominal LB | Signed price constant, USD |
|---|---:|---:|---:|---:|
| T-001 | +10 | 4.25 | +250,000 | +1,062,500 |
| T-002 | -4 | 4.30 | -100,000 | -430,000 |
| Aggregate | +6 | No single price required | +150,000 | +632,500 |

The price constant is signed nominal quantity multiplied by agreed price. It is an arithmetic term, not an upfront futures purchase payment. At an illustrative current market price of 4.40 USD/LB, combined gross P&L since execution is:

`150,000 × 4.40 − 632,500 = USD 27,500`

This is an arithmetic illustration before fees and delivery effects, not a statement that USD 27,500 is currently unpaid or is a discounted present value. Variation cash history determines that split. If buys and sells net to zero quantity, their price constants can still leave nonzero P&L; net lots and an average entry price are not a sufficient general representation.

The prepared numerical representation can hold arrays of market-point positions, signed converted quantities, entry constants and trade mappings. Simple listed futures can share market reads and arithmetic. Averaging dependencies are prepared only when required by the chosen valuation/fixing calculation. A matrix or sparse representation is justified by actual dimensions and measured work, rather than by the trade object's shape.

| Aggregation purpose | Preserve |
|---|---|
| Share market reads | Exact index/market-point identity and snapshot |
| Combine linear exposure | Converted units, compatible market point, signed exposure and constants; retain trade mapping |
| Combine cash/operational positions | Currency, cash dates, legal entity, clearing house/firm/account and applicable netting rules |
| Combine delivery obligations | Deliverable eligibility, vintage, location, delivery window and actual allocations |

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

If the project adds a true cleared swap, the candidate common fields are:

| Dimension | Proposed values / source | Why retain it |
|---|---|---|
| Contract form | `FUTURE` / `SWAP`, supplied by product definition | Preserves the contractual identity; it is not inferred from the payoff or execution channel |
| Clearing arrangement | `CENTRALLY_CLEARED` / `BILATERAL`, supplied by executed terms and clearing records | Independent of contract form; a swap can be centrally cleared |
| Final settlement form | Existing `PHYSICAL` / `FINANCIAL` | Independent of whether the instrument is a future or swap |
| Cash and margin rules | Shared rule reference | Establish what cash settles exposure, what constitutes collateral, and any interest treatment |
| Contract/payment schedule | Shared rules plus resolved dates | A listed contract code or explicit periods must retain actual fixing and payment timing |
| Clearing house, firm, account | Existing references | Retain the applicable clearing and account relationship |

The first two rows describe a possible extension to the model. They do not change the current futures template's `instrument_type = FUTURE`, or imply that a swap record has already been designed.

Daily cash movement alone is insufficient to prove equivalence. Cleared derivatives can use cash as settlement of exposure or as collateral against it; the applicable contractual treatment determines the cash/value split. Do not infer a universal futures-versus-swaps rule from the label. [Federal Reserve explanation of cleared-derivative settlement models](https://www.federalreserve.gov/frrs/guidance/regulatory-capital-treatment-of-certain-centrally-cleared-derivative-contracts-under-regulatory-capital-rules.htm).

For an actual swap, check fixing dates, payment dates, quantity profiles, cash treatment and applicable discounting against the proposed equivalent future. Identical final-price formulas alone do not establish identical value or settlement obligations. Compatible observations, exposures and payment calculations can still share arrays and one batch evaluation path.

No currently offered true cleared CL/Henry Hub swap was verified for this report. The concrete examples above are futures. The recommendation is to keep the classification explicit and defer additional swap-specific machinery until a real product or confirmation supplies terms that require it.

## 8. What to establish now, and what remains a proposal

The current project already has an `Index` holding schedule, conventions and specification references; price and position quantity units can differ. `FuturesSchedule.codes` already stores contract codes alongside expiry dates; explicit trade binding and strip expansion are proposed uses/extensions, not functionality established by the presence of those codes. Existing specifications contain lot sizes and brokerage/clearing fee arrays. Their names, and index display names, are not a canonical product registry. [Index implementation](C:/Users/jgile/.codex/worktrees/5b83/goosedove/src/goosedove/index_definitions/index.py), [specifications](C:/Users/jgile/.codex/worktrees/5b83/goosedove/src/goosedove/index_definitions/contract_specifications.py).

This report proposes richer settlement, venue, delivery and fixing definitions. It does not imply they already exist. EUR requires changes to the current USD/CENT conventions, and allowances need a suitable asset/quantity representation. The current futures schedule stores expiry information, not the full generic observation/notice/delivery/payment model above. [Conventions](C:/Users/jgile/.codex/worktrees/5b83/goosedove/src/goosedove/index_definitions/index_conventions.py), [futures schedule](C:/Users/jgile/.codex/worktrees/5b83/goosedove/src/goosedove/index_definitions/futures_schedule.py), [unit definitions](C:/Users/jgile/.codex/worktrees/5b83/goosedove/src/goosedove/globals/unit_conversions.py).

The recommended initial decision set is:

1. **Keep the trade small:** identity, trade date, selected definitions, explicit contract code, signed quantity with its defined basis, agreed price, and booking/clearing references. Resolve any strip into its constituent contracts once.
2. **Use explicit domains:** physical/financial is a two-value choice; index, currency, exchange, house and firm are validated references with extensible choices.
3. **Resolve defaults once:** trade details complete or replace template defaults; exchange-defined facts follow the selected specification.
4. **Keep distinct schedules and events:** last trade, observation, publication, notice, delivery and payment have their own meanings.
5. **Separate stable terms from current state:** market ticks update inputs; fixing arrivals and lifecycle/date changes can require different preparation.

Before numerical implementation, work through a small set of resolved records using these fields: NG, PHH, WAH, ETE, WTI Financial, EUA, specific-vintage CCA and HG. Confirm the WTI first-nearby roll boundary, select authoritative expiry calendars and define the required futures P&L/cash outputs. Then implement the simplest future through the same batch path intended for many trades.

Full delivery processing, margin simulation, order execution and a universal legal trade-capture schema are outside this field review. Their relevant identity, schedule and event boundaries are retained so they need not be forced into the agreed-price trade record later.

## 9. Assessment of the two Priceratops engineers' recommendations

This assessment compares the first engineer's advice supplied in the conversation with the [second engineer's pasted summary](<C:/Users/jgile/.codex/attachments/e135d8da-4f8a-4f29-9ca0-62c36180dcdd/Pasted text.txt>). The linked full artifact was inaccessible. Priceratops code, historical counts and measurements were not independently audited for this assessment; they are reported experience. Both engineers examined the same earlier project, so agreement between them is not independent validation of every proposed choice.

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

5. **Deliberate defaults remain valid.** Our template exists to supply known shared values. This is compatible with rejecting absent required economics and rejecting an explicitly blank input. An omitted override may inherit a declared template value; an arbitrary blank must not silently become zero, a side or a date. Template resolution must not rewrite old executions when defaults later change.

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

The field survey answers what the contract means. It has **not yet established the complete prepared representation, lifecycle inputs or output definitions**. The engineers' warning about building many instruments before settling the evaluation boundary is relevant to our next step. The field universe is a review checklist, not a requirement to build every field and delivery workflow before pricing one future.

### What their measurements do and do not establish

| Reported experiment | Boundary | What it supports |
|---|---|---|
| First engineer: 5,000 swaps, 5.16 seconds to 0.38 seconds | Python evaluation, publication and aggregate readers; excludes Excel | Batching and removing repeated work can materially improve a meaningful refresh boundary |
| Second engineer: 5,000 swaps, 2.2 milliseconds build and 0.4 milliseconds price | NumPy demonstration excluding calendar/date construction | Prepared arithmetic can be cheap; this is not a comparable end-to-end result |

These are different workloads/boundaries and cannot establish a relative speedup between the proposed designs. The first account's rejected representation with roughly 30 times as many intermediate rows remains a relevant warning. For Goosedove, use work counts and representation sizes: preparation builds, calendar work, market points gathered, components evaluated and temporary allocation size. Timings can supplement those observations, not replace correctness or work-budget checks.

### Recommended synthesis and next step

Retain the first engineer's careful economic boundaries and add the second engineer's concrete safeguards: explicit data for actual legs, one normalization/sign contract, independently calculated expected results, explicit tolerances and analytic linear price sensitivity. Keep the user's progression: futures, bilateral future lookalikes, penultimate variants, then CFD/last-three-day/Asian structures as their terms are established. Cash arithmetic can be a tiny validation example without becoming a prerequisite product project.

The next design artifact should be a worked **NG `Z26` evaluation example**, before a broad implementation:

1. Show template plus executed details and the complete resolved record, including the agreed price.
2. Name the as-of inputs: current market price, previous settlement basis and relevant settled cash/history.
3. Define separately the requested cumulative P&L, settled cash, outstanding mark/settlement amount and price delta, including fees only under an explicit treatment.
4. Show the minimal prepared arrays and mappings back to each trade occurrence and market point; one trade uses the same path as many.
5. Establish buy/sell signs, unit factors and independent expected numbers with chosen tolerances. Include equal-and-opposite quantities that leave nonzero P&L.
6. Specify expected work for first calculation, unchanged repeat, one-price update and then a fixing/date/lifecycle change. A tick must not regenerate stable schedules; a changed fixing or settlement event must update the affected state correctly.

Once that example is coherent, a defined `Cal27` strip tests constituent mapping and shared market reads. The subsequent bilateral lookalike tests payment-date valuation. Those cases should determine the useful shared representation before choosing a dense matrix, sparse matrix or a more elaborate product hierarchy.

## 10. Where rates enter the calculation

The trade is static. Current commodity prices, discount curves, fixings and settlement state are inputs to valuation. Separating amount calculation from valuation means two connected operations over shared prepared data, not two independent traversals of the trade:

```text
projected_amounts = constants + commodity_exposures @ commodity_prices
payment_values    = projected_amounts * payment_date_discount_factors
trade_values      = aggregate(payment_values, payment_to_trade)
```

This describes ordinary future cash payments under an explicit valuation model. A floating payment's projected amount is not an already-known cash amount; uncertainty and any projection assumptions remain identifiable. The arithmetic does not authorize treating every future as one discounted terminal payment.

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

Goosedove already has an immutable daily `DiscountCurve` of dates and factors, built from supplied anchors with linear interpolation in factors. It starts at factor 1, rejects extrapolation in its construction, and enforces positive, non-increasing factors. The latter is an already accepted limitation on negative-rate curves. It is a useful array building block, not a complete curve-selection or trade-valuation system. [Current curve implementation](C:/Users/jgile/.codex/worktrees/5b83/goosedove/src/goosedove/globals/discount_curve.py:21), [curve contract and deferred pricing work](C:/Users/jgile/.codex/worktrees/5b83/goosedove/docs/library/globals/discount-curve.md:124).

The first consumer must establish curve selection, valuation-date alignment and payment-date coverage; no silent extension or reuse of yesterday's anchored factors. For an initial implementation, requiring curve start to equal valuation date is a proposed explicit policy, not existing consumer behavior. Building curves from rate instruments can remain outside the first instrument implementation: supplied discount factors are sufficient to establish the interface.

Rate risk also needs a definition. With commodity projections held fixed, direct discount risk is `sum(amount × change_in_discount_factor)`. Sensitivity to supplied DF anchors is not automatically sensitivity to market rate instruments. A DV01 requires a declared rate-bump/curve mapping. If commodity projections themselves depend on rates, total rate sensitivity also includes that dependency.

### Reuse across updates

| Changed input | Work to share/reuse | Work potentially affected |
|---|---|---|
| Commodity market price | Contract structure, dates, unit factors, unchanged discount factors | Dependent projected amounts and values |
| Rates/discount factors on the same grid | Contract structure and commodity amount calculation | Discount gathers, present values and relevant risk |
| New fixing | Unchanged contract terms and payment schedule | Known/projected split and affected sensitivities |
| Valuation date or settlement event | Static trade and still-valid definitions | Curve alignment, outstanding/paid classification and affected preparation |

Gather shared curve/date combinations once where useful. Cache positions into a curve only with its grid identity: a changed curve start changes the array offsets. These are proposed work boundaries; the choice between selective recalculation and a compact full batch should be measured.

The current performance evidence and a ready-to-share independent review scope are in the [review brief](C:/Users/jgile/.codex/worktrees/5b83/goosedove/docs/independent-review-brief.md).
