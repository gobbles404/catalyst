# Exchange-traded commodity futures: cross-family contract matrix

Research synthesis, 14 September 2026. This is the map from the family surveys to the eventual futures trade representation. It is a requirements discussion, not an implemented schema or a claim that every exchange product has been onboarded.

The subsequent [semantic synthesis](futures-template-synthesis.md) develops the abstraction boundaries, power treatment and proposed initial scope. It refines the meaning of linearity and distinguishes shared observations from execution and position state.

**The surveys support one common futures trade record backed by precise, versioned exchange contract definitions.** Commodity families organize discovery and market data; the recurring contractual differences are quantity, price reference, schedules, settlement obligations and lifecycle events. Creating a subclass for every commodity would repeat those same differences many times.

## Coverage map

Each linked survey contains primary exchange sources, representative specifications and its own unresolved points. A listed specification establishes contract structure, not liquidity or availability of every maturity.

| Family and detailed survey | Coverage | Distinctions most useful to the common representation |
|---|---|---|
| [Petroleum](petroleum-futures-contracts.md) | Crude, refined products, distillates, regional assessments and differentials | Physical delivery, cash benchmarks and delivery elections; outright versus basis/spread; mass/volume conversions; shifted averaging windows. |
| [Natural gas and NGLs](natural-gas-and-ngl-futures-contracts.md) | Pipeline gas, LNG price benchmarks, regional gas basis and NGL products | Fixed total quantity versus daily quantity or constant flow; gas-day/time-zone conventions; assessment periods that differ from contract labels; EFP and cascade events. |
| [Power](power-futures-contracts.md) | Vanilla outright and location-basis futures, base/peak/off-peak, regional markets | Eligible delivery intervals; fixed MWh versus MW times hours; local calendars and clock changes; day-ahead versus real-time references; cascades. |
| [Metals](metals-futures-contracts.md) | Precious, base, ferrous, battery and other industrial metals | Fixed prompt dates; fine/gross/dry/theoretical mass; approved brands and warrants; delivery units different from trading lots; margin conventions. |
| [Agriculture, including softs](agricultural-futures-contracts.md) | Grains, oilseeds and oils, coffee, cocoa, sugar, cotton, juice, livestock, dairy and other agricultural products | Crop/grade/origin eligibility; shipping certificates and warehouse receipts; inspection and invoice adjustments; index release conventions; seasonal listings. |
| [Carbon and environmental](carbon-and-environmental-futures-contracts.md) | Allowances, offsets, performance credits, RECs/GOs, RINs and related cost/index exposure | Registry delivery; scheme, vintage and compliance eligibility; basket substitution; units distinct from underlying physical energy or emissions; conversion/assignment events. |
| [Freight and shipping](freight-futures-contracts.md) | Dry bulk, tanker, LNG/LPG freight, containers and freight indexes | Charter-days, freight tonnes, FEUs and currency/index-point multipliers; directional routes and benchmark vessels; Worldscale conversion; discrete publication sampling. |
| [Coal and coke](coal-and-coke-futures-contracts.md) | Seaborne/domestic thermal coal, coking coal and metallurgical coke | Heat-content and moisture basis; trading lots versus aggregate delivery units; quality-dependent invoice price and weight; maturity-specific standards. |
| [Fertilizers](fertilizer-futures-contracts.md) | Urea, UAN, DAP, MAP and ammonia | Short tons versus tonnes; product concentration; daily/weekly assessment combinations; trimming and missing-publication rules; physical versus cash urea. |
| [Chemicals and industrial materials](chemicals-and-industrial-materials-futures-contracts.md) | Methanol, polymers, polyester chain, rubber, pulp and paper | Grade, packaging and delivery mode; unusual assessment windows and quote scales; dry/conditioned weight; duty-paid/bonded and export delivery distinctions. |

Softs are already within agriculture. Forest products cross the agriculture and industrial-materials surveys; ammonia crosses fertilizers and chemicals. Gas price exposure and LNG freight are separate underlying references. These overlaps are reasons to allow classification tags, not duplicate the same exchange contract.

## Contract dimensions, independently of commodity

The following distinctions recur across the evidence. They need not all become direct fields on the trade record: many belong in the referenced contract definition or in resolved schedules.

| Dimension | Facts that must remain distinguishable | Examples / consequence |
|---|---|---|
| **Exchange contract identity** | Venue, product identifier, actual admitted maturity or prompt date, applicable definition version | A symbol or rulebook chapter can be reused. Historical and replacement contracts are not the same instrument. |
| **Quantity** | Number of lots; lot measure; fixed quantity versus rate integrated over a profile; monetary multiplier where appropriate | A one-day freight lot is already one day of exposure. A MW power lot needs eligible hours. An index future need not have a physical quantity. |
| **Quotation** | Currency, price unit, scale, execution tick, settlement precision and rounding | Cents/lb and dollars/t use different units and scales. Minimum execution increments need not constrain the final settlement price to the same grid. |
| **Price reference** | Named publisher/index, location, grade, delivery-cost basis, source unit and methodology version | Two prices at Richards Bay or the US Gulf can be different benchmarks. A reference location is not automatically a futures delivery location. |
| **Final-price expression** | Single fixing, arithmetic/weighted average, ordered differential, converted legs, trimmed observations, index basket | Operation order matters: transform daily inputs before averaging when the contract says so. Do not infer formulas from product names. |
| **Observation schedule** | Actual determination window, sampling frequency, weights, publication calendar, time zone, holiday/fallback rules | Calendar month, shifted month, remaining month, weekly observations and last-three-publication sampling are distinct. |
| **Contract and event dates** | Contract label/period, last trade, final observation, price publication, notice/tender, delivery, payment | Expiry is too ambiguous to stand for all of them. Some contracts stop trading before the reference period ends. |
| **Cash and margin obligations** | Daily settlement convention, final residual adjustment, payment currency/calendar and applicable clearing treatment | Avoid counting inception-to-final profit again after variation has been paid. Do not assume every futures market realizes daily variation identically. |
| **Physical eligibility** | Deliverable commodity or registry basket; permitted grades/brands/vintages; locations; documents; tolerances and invoice rules | Delivery might move gas, a warehouse warrant or an environmental certificate. The buyer does not necessarily receive a uniquely identified asset at execution. |
| **Lifecycle transformation** | Physical/cash election, compulsory EFP, cascade or assignment, generated positions and conversion ratios | A parent future can cease and create child positions. That is different from a package that opened several independent futures at execution. |
| **Effective terms and status** | Effective date and maturity applicability; current listing/suspension status; governing source | Two maturities traded today may use different delivery standards. A brochure is insufficient when a later notice changes the product. |

This table is a synthesis of the linked surveys. It deliberately separates independent economic facts without prescribing a class hierarchy or a free-form formula engine.

## Executions, terms and valuation context

### 1. The executed trade

For an ordinary outright futures execution, the natural core is the **resolved exchange contract instance, buy/sell, number of contracts and execution price**. Trade identity, execution timestamp and booking/account information can accompany it where the library's responsibilities require them. A trade executed relative to a later settlement price needs its actual execution convention and subsequent resolved price; it should not masquerade as a completed fixed-price execution.

The trade should not repeatedly ask the user for the same exchange-defined lot size, delivery grade or expiry rule. The product and maturity resolve those facts. Equally, product resolution must not guess a missing benchmark, maturity or unit from a loosely matching name.

A spread or strip execution needs constituent trade allocations when it creates separate positions. A **listed differential future** is a single contract whose own settlement definition specifies the difference. These are separate cases even when the execution screen displays one price.

### 2. The contract definition and resolved schedules

The contract definition supplies the quantity/quote conventions, named references, settlement obligations and applicable rules. Resolution for a particular maturity yields concrete observation and event dates where determinable, retaining rules for dates that depend on later publications or events. For example, a base-load month has eligible local intervals; a weekly-assessment future has publication and expiry conventions.

Specialized terms should appear only where applicable. A cash-settled freight future does not need warehouse-delivery fields. A physical metal future needs its eligible delivery rules but does not need a made-up monthly price average. Common facts can be reused without pretending that every combination of attributes is a valid listed product.

Store contractual calculation facts as data: component signs, fixed conversion factors where contractual, references to variable conversion observations, averaging rules and rounding. Pricing models, curve selection, interpolation and calibration remain separate machinery. This follows [principle 7](../../PRINCIPLES.md): contracts describe economic obligations, not how an engine computes their value.

Price admissibility must follow the product's rules. A universal positive-price constraint would reject legitimate negative gas/power prices and differentials. Initial margin is collateral, separate from commodity quantity and realized variation; current margin rates and position limits are operational reference data if the library supports them. [Gas survey and supporting rules](natural-gas-and-ngl-futures-contracts.md)

### 3. Shared observations and position state

Published fixings and corrections are shared **reference observations**, supplied through valuation context. Remaining exposure, settlement basis, paid/unpaid cash, assigned deliveries, elections and generated positions describe **position and settlement state**. Clearing allocations may combine executions; their cash histories need not map one-to-one to original trades. Neither observations nor position state should overwrite the original execution.

For a partially observed average, retain the contractual observation rules as fixings become known. For a cascade, the parent terminates under its rules and the resulting positions become explicit. For delivery, retain the applicable eligibility rules and record the allocated asset when known. Approved-deliverable lists, authoritative amendments and prescribed publication fallbacks can change the applicable schedule or eligible set; preserve those changes and their provenance. This separation supports valuation before and after events without letting market prices redefine the contract.

## What “linear future” should mean here

For a fixed-multiplier future with ordinary daily cash variation, an illustrative settlement change is:

`variation = signed_contracts × currency_per_quote_point × (new_settlement − previous_settlement)`

Here the multiplier must already incorporate the correct lot size and quotation scale. It can be derived from a resolved delivery profile when the contract uses a rate such as MW. The equation describes a settlement-price move; it is not a universal present-value formula or a physical delivery invoice.

Linearity in an instrument's own quote is bookkeeping, not sufficient justification for a linear instrument family: an option position also scales with its premium. A stronger initial meaning is unconditional fixed exposure affine in specified economic reference prices. Even that does not establish linearity in every underlying market input:

- Fertilizer trimming changes which raw assessments contribute.
- A price times a variable FX or freight conversion reference is not a fixed linear combination of both inputs.
- A deliverable basket or contractual election can contain economic optionality.
- The value of unpaid future cash depends on its timing and the applicable financing/margin treatment.

These qualifications should guide the pricing boundary, rather than force commodity-specific trade subclasses. The [semantic synthesis](futures-template-synthesis.md) recommends a documented exposure classification instead of an algebraic superclass promising more than every child can satisfy.

## Representative cases to review before fixing the template

These are proposed acceptance examples for the design discussion, not new tests or a promise to implement all markets at once. The detailed sources and qualifications are in each linked survey.

| Case | What a correct representation must make possible |
|---|---|
| 1. Physical crude and cash-settled crude assessment | Distinguish the benchmark's physical description from the holder's actual settlement obligations. |
| 2. Listed gas basis versus execution of two outright futures | Represent one contractual price difference separately from two positions with their own expiries and quantities. |
| 3. Fixed-total gas, daily gas quantity and constant-flow gas | Resolve total exposure according to the applicable quantity convention; never add an extra day/hour multiplier. |
| 4. Power month spanning a clock change | Use the actual eligible local intervals and contractual profile; a calendar-day count times 24 is not always valid. |
| 5. Fixed-MWh daily power versus MW-based monthly power | Keep the price-observation profile distinct from whether it also determines quantity. |
| 6. EEX quarter/year cascade | End the parent and create the specified shorter contracts without retaining duplicate exposure. |
| 7. LME rolling tenor selected at execution | Resolve the actual prompt date once; do not let the trade's maturity move each valuation day. |
| 8. Metal or agricultural delivery allocation | Keep trading exposure separate from actual weight, grade, receipt identity and invoice adjustment. |
| 9. Environmental future with a named vintage | Keep maturity, eligible vintage window, compliance scheme and actual registry allocation independent. |
| 10. Thirty one-day freight lots | A USD 100/day move produces USD 3,000 of variation before fees/rounding, without multiplying again by days in the month. |
| 11. Freight quoted through Worldscale | Respect the source scale, applicable daily flat rate and order of conversion/averaging. |
| 12. Container index sampled on three publication dates | Model the prescribed observations and fallback, rather than substitute a full-month average. |
| 13. SGX Indonesian coal future versus similarly named swap | Resolve the futures identity and its own lot size; a shared benchmark does not imply a shared multiplier. |
| 14. Domestic coal physical settlement | Preserve aggregate delivery unit, measured quality, price adjustment and billable-weight adjustment as different facts. |
| 15. CBOT fertilizer publisher set [300, 310, 320, 400] | Produce the contractual trimmed observation of 315, then apply the monthly aggregation; ordinary midpoint averaging would give 332.5. |
| 16. Physical polymer or polyester-chain delivery | Select the applicable delivery mode, tax basis, quality version and mode-specific deadline. |
| 17. Partially fixed average after last trade | Retain remaining observation exposure and unpaid cash instead of marking the trade economically finished at last trade. |
| 18. Rule amendment effective from a named maturity | Allow adjacent maturities booked on the same day to resolve different applicable standards. |

## Boundaries and remaining research

The ten surveys cover the main commodity families discussed, including softs. Possible **optional extensions** are weather-index futures, water-index futures and broad commodity basket/index futures. They have not received full family surveys here. Freight and environmental indexes already exercise monetary index multipliers, but do not establish the detailed methodology of those other products.

The research also leaves specific onboarding questions: conflicting product-page wording, inaccessible current delivery amendments, precise clearing cutoffs and status of some historical listings. Each survey labels its gaps. Those products should remain unconfigured until the relevant facts are resolved; an uncertain fact should not become a default in the common template.

The next design step is to review these recurring dimensions and choose a small representative set of supported futures. That is enough to define the first trade record and its reference-data boundary, while keeping the broader survey as evidence for later extensions.
