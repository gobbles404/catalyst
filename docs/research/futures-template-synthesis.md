# A semantic starting point for commodity futures

Design proposal, 14 September 2026. Synthesizes the ten family surveys indexed in the [contract matrix](futures-contract-matrix.md). This is a proposal for discussion, not an approved constructor, implementation plan or amendment to existing library decisions.

## Recommendation

**Use a common futures trade, composed with independently meaningful contract terms. Give time-shaped exposure, price determination, fulfilment and clearing their own concepts. Let commodity domains own their asset definitions and conventions.**

Power deserves a substantial domain vocabulary, but its vanilla futures do not require a different executed-trade core. Conversely, calling everything a future does not justify giving it one valuation formula or reducing its terms to an unrestricted dictionary.

The aim is permissiveness about which economic references and conventions can be represented, coupled with precision about what each fact means. This does not require supporting every surveyed product or allowing arbitrary combinations of otherwise valid fields.

Two corrections sharpen the earlier matrix. Linearity in an instrument's own quoted price is not a useful definition of a linear instrument: an option position also scales with its quoted premium. Published fixings also belong to shared reference observations; they are not mutable copies owned by every trade that uses them.

## 1. What the common trade actually means

An ordinary futures trade records an execution in a particular exchange contract:

```text
FuturesTrade
    contract       a particular listed contract, with resolved maturity/prompt
    signed_lots    the number and direction of contracts executed
    entry_price    the agreed price, in that contract's quotation
```

These are conceptual names, not a proposed function signature. Occurrence identity is preserved; execution time and booking information can accompany the trade where needed. Two identical executions remain two occurrences. A current position is a different record from either execution.

Initially, an entry price can simply be known. Trade-at-settlement and other unresolved-price executions can be added as explicit execution terms when supported; they do not justify optional price fields and implicit defaults now.

The referenced contract has the following separate responsibilities:

| Concept | Question it answers | What does not answer it |
|---|---|---|
| **Contract identity** | Which exchange obligation and particular maturity/prompt is this? | A commodity name, rolling tenor or curve node alone. |
| **Quotation** | What does one quoted price unit mean? | Currency alone: USD/t and US cents/lb have different units and scales. |
| **Lot definition** | What exposure does one contract represent? | The benchmark ship's size, a delivery batch or a guessed monthly quantity. |
| **Price determination** | Which reference and observations establish a contractual price? | The market model used to estimate that price. |
| **Fulfilment terms** | What obligations close or replace this contract? | A price formula alone. |
| **Clearing terms** | How are price changes realized, collateralized and paid? | The eventual cash/physical label. |

Each concept may reference dated exchange rules without placing their entire text on the trade. That reference preserves identity and provenance; it does not make unimplemented rules executable.

Product definitions may share facts. They must still resolve valid contractual combinations. A user should not independently override an exchange contract's lot, grade and averaging window while retaining its exchange identity.

## 2. Quantity: generalize the measure, preserve how it arises

The surveys support three quantity meanings, plus monetary index sizing:

| Meaning | Example | How one lot's exposure is resolved |
|---|---|---|
| **Fixed amount** | A fixed number of barrels, tonnes, MWh, certificates or charter-days | Use the stated amount once. |
| **Amount per contractual period** | A specified GJ amount for each gas day | Sum the amounts for the defined periods. Day length need not alter each day's amount. |
| **Rate over intervals** | MW over eligible electricity hours | Integrate the rate over the eligible elapsed intervals. |
| **Monetary index multiplier** | Currency per index point | Use the monetary multiplier; there may be no physical quantity. |

These are different meanings even if they eventually yield the same number. The [gas](natural-gas-and-ngl-futures-contracts.md), [power](power-futures-contracts.md) and [freight](freight-futures-contracts.md) surveys establish the distinctions.

For ordinary fixed-exposure futures calculations they resolve to a **monetary value per quoted price point per lot**. That is a useful common computational result. It is not a replacement for the contractual lot definition.

Avoid independently authoring both the lot definition and its derived monetary multiplier when one determines the other. Derive the multiplier using the quotation scale, and retain its dimensional meaning. An exchange index contract can instead state that multiplier directly.

Trading exposure, minimum delivery batch and actual invoiced quantity remain separate. Moisture, purity and weight tolerances do not silently change the original number of contracts. Their consequences belong to the applicable delivery calculation.

## 3. Power: separate three meanings of time

Power's distinctive requirement is an explicit relationship with delivery intervals. That requirement is shared with gas and potentially other scheduled commodities. It belongs in reusable time and quantity concepts, with power-specific reference definitions and conventions.

There are three independent questions:

1. **Quantity:** which periods or intervals determine the amount represented by a lot?
2. **Price:** which observations contribute, what periods do they describe, and with which weights?
3. **Obligations:** when do trading, fixing, cash payment, delivery or conversion events occur?

They can share an interval definition when the contract says so. A common month label does not establish that relationship. In particular, a cash power future can reference electricity delivery intervals without obliging its holder to deliver electricity.

The daily PJM peak examples make this concrete. NYMEX's contract has a fixed **16 MWh** lot; ICE's has **800 MWh**. Both use the sixteen peak hours ending 08:00–23:00 EPT. The price window therefore cannot determine the lot quantity. [NYMEX chapter 808](https://www.cmegroup.com/rulebook/NYMEX/8/808.pdf), [ICE specification](https://www.ice.com/products/6590471/PJM-Western-Hub-Day-Ahead-Peak-Daily-Fixed-Price-Future/specs)

A predetermined 1 MW profile over 720 eligible hours instead gives 720 MWh. A clock change may change eligible elapsed hours. Quarter-hour observations do not multiply exposure by four: four quarter-hours still cover one hour.

Even equal quantity intervals do not imply equal price aggregation. Consider two selected days containing eight and twenty-four hours, priced uniformly at 100 and zero respectively. An equally weighted average of the two daily averages is **50**; an equally weighted average of the thirty-two hourly prices is **25**. Both cover thirty-two hours of quantity for a 1 MW contract. This is an invented arithmetic example, demonstrating why price weights must be explicit.

The useful power specialization is therefore an **electricity reference** with market location, day-ahead/real-time identity, market clock and observation conventions, plus **interval definitions** for quantity or delivery when applicable. Base/peak/off-peak are named conventions built from these concepts. They should not be universal enum values that mean the same hours everywhere.

Scheduled exposure is within this vanilla boundary. Discretionary consumption, swing rights, generation-dependent volume, dispatch and storage optimization introduce choices or contingent quantities. They deserve separate treatment. A predetermined peak profile does not introduce those rights.

## 4. References, averaging and basis

Price determination has a small useful vocabulary:

- **Named reference observation:** a published assessment, index fixing or specified exchange price.
- **Temporal aggregation:** a specified observation set, weighting and aggregation order.
- **Difference or fixed combination:** identified components with signs, coefficients and compatible quotation meanings.

Averages and differences can both be expressed as weighted sums mathematically. Keeping their semantic roles visible remains useful: averaging prices through time and comparing two delivery locations answer different contractual questions. Components can have separate observation schedules; a common schedule must not be assumed.

A directly published basis assessment can remain one named reference. It need not be reconstructed as two outright prices. Conversely, a contract prescribing a difference must preserve that definition. A listed basis future remains **one exchange instrument**, even when a model uses two curves to estimate its fair price. A spread execution producing two futures creates two positions. Model decomposition must not replace contractual identity.

Do not begin with a universal language for every formula in the surveys. A specialized publisher methodology can be referenced explicitly and supported by its own evaluator later. Trimming, floating FX conversion and conditional fallbacks should not be mislabeled ordinary weighted averages merely to fit an initial type.

## 5. A useful meaning of linear

The most defensible initial meaning is **unconditional, fixed exposure that is affine in specified economic reference prices**. “Affine” permits a fixed offset, such as the agreed entry level:

```text
economic price difference = a1 × reference1 + a2 × reference2 + ... − K
```

This describes the exposure, not its payment schedule or present value. Predetermined observation weights and quantities can be included in the coefficients after resolution. Exercise gates, caps, floors and discretionary quantity are outside this initial promise.

The reference level matters. A future on a published index can have simple exposure to that index, while the index itself has a nonlinear methodology. Reconstructing a trimmed fertilizer index from individual quotes is a different operation from using its published fixing. A floating FX conversion also need not be linear in both the commodity and FX inputs. Physical delivery choices can introduce additional optionality when estimating the future's price from underlying markets.

Consequently, **do not make `Linear` promise universal linearity in every underlying risk factor**. For this library, it can be a documented exposure classification used by supported pricing operations. A hard inheritance relationship is useful only if the base class has an invariant and operations every child actually satisfies. Merely having a price and quantity would also admit options and supplies no such invariant.

Futures and swaps can share references, units and observation concepts while retaining different settlement mechanics. A future is not obtained by taking a forward-style discounted terminal cashflow and changing its type label.

## 6. Fulfilment, price and clearing are independent

Three broad completion outcomes are meaningful:

| Outcome | Economic consequence |
|---|---|
| **Financial close** | Final residual cash obligations are determined under the contract's clearing convention. |
| **Delivery** | An eligible asset, entitlement or scheduled commodity obligation is transferred, with applicable invoicing. |
| **Position replacement** | The original position ends and specified new positions arise, potentially with associated cash obligations. |

These are named meanings, not a complete lifecycle language. A contract can have intermediate replacement events or conditional routes. Its ordinary outcome, holder elections and exceptional remedies should be distinguished when supported.

Price determination remains separate because physical delivery also needs prices: an exchange settlement, an average or a quality-adjusted invoice basis. Clearing remains separate because financial finalization does not imply realized daily variation.

LME Monthly Average Futures are a concrete counterexample: the June 2026 clearing rules assign them discounted contingent variation margin, with contingent credits unavailable for cash withdrawal, despite financial final settlement. That convention changes outstanding claims and their timing. [LME Clear rules, C4.2–C4.6 and Annex 1 §2.6](https://www.lme.com/-/media/files/clearing/rules-and-regulations/22-06-2026-lme-clear-rulebook.pdf)

Physical delivery also has several meaningful domains:

- **Scheduled commodity delivery:** gas or electricity delivery intervals, points and operational rules.
- **Inventory or custody entitlement:** goods, warehouse receipts, warrants and rights to call for shipment.
- **Registry asset transfer:** scheme-defined allowances, credits or certificates and their eligibility.

Some shared transfer concepts are possible, but their asset definitions must preserve what ownership grants. A registry transfer does not automatically retire a credit. Warrant transfer does not necessarily load metal onto a truck. Payment, ownership transfer and physical movement need not occur simultaneously. See the [environmental](carbon-and-environmental-futures-contracts.md), [metals](metals-futures-contracts.md) and [agricultural](agricultural-futures-contracts.md) surveys.

Permitted grades, brands, locations, vintage baskets and packaging are generally data within these domains. A material change in obligation, entitlement, allowed choice or required state deserves a separate semantic concept. A different grade threshold usually does not deserve a different futures class.

## 7. Terms, observations and position state

The earlier trade/terms/state split needs one further distinction:

| Information | Ownership and meaning |
|---|---|
| **Contract terms** | Shared contractual facts, with applicable amendments and rule provenance. |
| **Execution** | Original trade occurrence, signed lots and agreed terms. |
| **Reference observations** | Shared published fixings, corrections and their as-of availability. |
| **Position and settlement state** | Remaining exposure, last relevant settlement basis, unpaid cash, elections, allocations and replacement positions. |
| **Valuation inputs and assumptions** | Curves, discounting and models supplied to a calculation. |

Clearing may net or allocate multiple executions, so every cash movement need not belong directly to one original trade. That does not require building a full clearing ledger now. It requires not baking a false one-execution/one-payment-history assumption into the first object.

For an averaging contract, the terms specify observations; the valuation context supplies those already known and projections where appropriate. Each trade need not own a mutable copy of the same index history. Authoritative amendments and publication fallbacks must retain provenance rather than silently mutate the original execution.

## 8. Representation and supported calculations

Separate three tasks before implementing a pricing function:

1. **Use the listed contract's observed quote:** identify the instrument and interpret price movements in the correct monetary units.
2. **Estimate a fair futures quote from underlying markets:** apply reference definitions, observations and any required delivery or market model.
3. **Value outstanding claims:** account for the settlement basis, already paid cash, remaining obligations and the applicable financing/clearing treatment.

None is automatically equivalent to the others. A quote is not a present value. For a constant position with fixed multiplier, the difference from its execution price can describe cumulative trading P&L before fees and funding. If variation has already been paid, that whole amount is not still an unpaid claim.

A physical future may be representable and usable with its own market quote before the library supports warehouse allocation or fundamental delivery-option valuation. Those unsupported operations should fail explicitly. An opaque rule reference alone is not evidence that an engine can perform them.

Limited operations must not mean incomplete objects. A precise listed-contract reference can be complete as a reference without expanding every warehouse rule into fields. It is a different claim from having a fully parsed, executable delivery definition. Each representation must be valid and complete for its stated meaning.

Prepare the requested calculation once: resolve its required facts and supported conventions at the library entry boundary, then dispatch to machinery that trusts that resolution. Do not make internal engines repeatedly inspect missing fields to discover what they can do. Missing support must not trigger guessed prices, cash substitution or default calendars. This applies [principle 1](../../PRINCIPLES.md) without requiring full delivery automation.

## 9. A narrow first implementation boundary

My recommended first specification would support known execution prices, fixed contract counts, exact dated identities, explicit quotation units and one understood clearing convention. Begin with cash futures referencing a single fixing or a specified average; include a listed basis example to exercise independent references.

If power belongs in the first release, add **predetermined interval quantity** and an explicit observation schedule now. A fixed-MWh power future also exercises power pricing without requiring rate-derived sizing. Start with supplied, resolved schedules if necessary; automatic generation from exchange calendars is a separate capability. Do not make the existing date-only slice silently acquire holiday or intraday behavior.

Use a small set of examples to test the concepts:

| Example | Boundary it exercises |
|---|---|
| Fixed-quantity cash future with one fixing | Common trade, quotation and financial close. |
| Fixed-quantity assessment-average future | Price schedule independent of quantity. |
| Listed location-basis future | One instrument, separate references, explicit signs. |
| Fixed-MWh versus MW-profile power | Shared trade with genuinely different lot definitions. |
| Physically delivered metal or registry future | Faithful identity/terms, with delivery operations explicitly outside the first supported calculation set. |

Defer automated delivery allocation and invoicing, cascades, contingent-margin valuation, unresolved-price execution, floating FX formulas and endogenous/optional volumes until their required operations are chosen. The representation should leave room for named extensions; it should not add `other`, optional dictionaries or a generic expression interpreter merely to claim universal coverage.

The existing [unit-conversion scope](../library/globals/unit-conversions.md) deliberately excludes compound price units and contract quantities. Those are new semantic concepts to specify, not extra conversion-table rows. Existing date decisions similarly leave business calendars for a separate step. This proposal changes neither decision.

## Design test for future extensions

Before adding a field or subtype, ask:

- Does it change the meaning of the price, quantity, obligation or admissible choice?
- Or is it another value within an already meaningful definition?
- Which operation needs it, and what information does that operation consume?
- Can the requirement be stated without mentioning a particular commodity?

Power's interval quantity passes this test as a reusable concept. Its particular peak hours are convention data. Registry eligibility deserves its own asset vocabulary. A particular vintage is a value within that vocabulary. Cascading changes positions and deserves an explicit lifecycle operation. A different futures month does not.

That is the proposed boundary: common execution semantics, reusable economic concepts, and specialized asset or settlement domains where the meaning actually changes.
