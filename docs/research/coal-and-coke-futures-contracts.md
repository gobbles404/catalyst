# Coal and coke futures: contract terms and template implications

Research date: 14 September 2026. Scope: exchange-listed futures, with historical contracts explicitly separated. The purpose is to identify contract facts needed by a general futures trade object; this is neither a liquidity ranking nor a proposal to implement another instrument class.

Coal adds three particularly useful cases: a cash future whose reference commodity has detailed physical specifications; small trading lots combined into much larger delivery units; and quality standards that change according to the contract month. Thermal coal, coking coal and coke belong in the same survey, but should have distinct commodity identities.

## 1. Divide the family by use and contractual reference

| Group | Economic reference | Principal distinctions to retain |
| --- | --- | --- |
| Seaborne thermal coal | Coal used principally as fuel; importing and exporting port benchmarks | Calorific value, gross/net measurement, moisture basis, origin/location, shipping basis and price publisher. |
| Domestic thermal coal | Domestic delivery locations and exchange quality specifications | Currency, receipt versus vehicle/vessel delivery, delivery aggregation, quality adjustments and taxes in the quoted basis. |
| Metallurgical/coking coal | Coal used to produce metallurgical coke | Premium versus second-tier grades, volatile matter, coking properties, ash and sulphur; a heat-content number alone is insufficient. |
| Metallurgical coke | The processed product used in ironmaking | Separate product identity and strength/reactivity specifications; do not treat it as another grade of thermal coal. |

This grouping is a modeling synthesis. The representative markets below establish the underlying distinctions. Petroleum coke belongs at the boundary with petroleum refining, and biomass pellets at the boundary with forest products; neither is silently included under metallurgical coke.

## 2. Representative contract specifications

Here, **t** means a metric tonne, **LTD** means last trading day, and ticks are quoted as price increment followed by the value for one monthly trading lot. Values calculated from lot size and tick are simple arithmetic, not separately quoted exchange fees.

### International thermal coal

| Exchange and future | Lot; quotation; tick | Settlement and benchmark | Expiry/period facts |
| --- | --- | --- | --- |
| **ICE API2 Rotterdam — ATW** | 1,000 t per month; USD/t; USD 0.05/t = USD 50 | Cash against the API2 monthly index published in the Argus/McCloskey Coal Price Index Report; reference location Amsterdam–Rotterdam–Antwerp. | Monthly LTD: last Friday of the contract month, preceding business day if a public holiday. Months and quarter/season/year strips are available. [ICE specification](https://www.ice.com/products/243/API2-Rotterdam-Coal-Futures) |
| **ICE API4 Richards Bay — AFR** | 1,000 t per month; USD/t; USD 0.05/t = USD 50 | Cash against the API4 monthly index; reference coal loaded at Richards Bay Coal Terminal, South Africa. | Same monthly last-Friday/preceding-business-day convention; months and longer strips. [ICE specification](https://www.ice.com/products/241/API4-Richards-Bay-Coal-Futures) |
| **ICE globalCOAL Newcastle — NCF** | 1,000 t per month; USD/t; USD 0.05/t = USD 50 | Cash against globalCOAL Monthly NEWC. Its monthly index averages the weekly indexes calculated on Fridays falling in the month. | The product page specifies cessation at noon London local time on the last Friday. Monthly contracts and quarter/year strips. [ICE specification](https://www.ice.com/products/1137/specs) |
| **ICE globalCOAL Richards Bay — GCF** | 1,000 t per month; USD/t; USD 0.05/t = USD 50 | Cash against globalCOAL Monthly RB, averaging the weekly Friday RB indexes. This is a different benchmark from API4 at the same port. | Product-page cessation is 17:00 London local time on the last Friday. Monthly contracts and quarter/year strips. [ICE specification](https://www.ice.com/products/63127241/globalCOAL-Richards-Bay-Coal-Futures) |
| **SGX IHS McCloskey Indonesian 4200kc GAR FOB Thermal Coal — M42F** | **10 t**; USD/t; USD 0.01/t = **USD 0.10** | Cash; arithmetic average of all published McCloskey Indonesian 4,200 kcal/kg GAR FOB marker observations in the expiring month, rounded to two decimals. | LTD is the marker's last publication day in the contract month. The current website lists through two calendar years including the current year. [SGX thermal-coal specification](https://www.sgx.com/derivatives/products/thermal-coal), [linked legal specification](https://api2.sgx.com/sites/default/files/2018-06/website%20Thermal%20Coal%20M42%20Futures%20contract%20specs.pdf) |

API2 references **CIF ARA**, whereas API4 references **FOB Richards Bay**; both use a 6,000 kcal/kg NAR basis. The globalCOAL RB alternative also has a 6,000 kcal/kg NAR reference. Shipping basis is part of benchmark identity even when the future settles entirely in cash. [globalCOAL financial contracts overview](https://www.globalcoal.com/coaltrading/financialcoaltrading.cfm)

There is a consequential SGX naming trap: **M42F is the 10-tonne listed future; M42 is the separate 1,000-tonne cleared swap**. Copying the swap multiplier into a futures definition produces a hundredfold error. SGX's current public product data explicitly separates both instruments. Only M42F is included here. [SGX thermal-coal product page](https://www.sgx.com/derivatives/products/thermal-coal)

### Coking coal and coke

| Exchange and future | Lot; quotation; tick | Settlement and underlying | Expiry and eligibility |
| --- | --- | --- | --- |
| **SGX TSI FOB Australia Premium Coking Coal — ACF** | 100 t; USD/t; USD 0.01/t = USD 1 | Cash; monthly arithmetic average of TSI premium coking coal, Australian exports FOB East Coast Australian port; two-decimal rounding. | Last index-publication day in the month. Final payments follow normal variation-margin procedures. [April 2026 legal specification](https://api2.sgx.com/sites/default/files/2026-04/SGX%20TSI%20FOB%20AUSTRALIA%20PREMIUM%20COKING%20COAL%20FUTURES%20CONTRACT%20SPECIFICATIONS.pdf) |
| **SGX McCloskey FOB Australia Hard Coking Coal — HCF** | 100 t; USD/t; USD 0.01/t = USD 1 | Cash; monthly arithmetic average of **MCC3 Australian FOB second-tier HCC** assessments, rounded to two decimals. | Last index-publication day; final settlement through variation margin. This is a separate second-tier benchmark, not an alias for ACF. [September 2026 legal specification](https://api2.sgx.com/sites/default/files/2026-09/SGX%20McCloskey%20FOB%20Australia%20Hard%20Coking%20Coal%20Futures%20Contract%20Specifications.pdf) |
| **DCE Coking Coal — JM** | 60 t; CNY/t; CNY 0.5/t = CNY 30 | Physical delivery at designated warehouses. | All months; LTD tenth trading day of delivery month; last delivery day third trading day after LTD. Quality standard JM003-2022 before JM2701; **JM004-2025 from JM2701**. [DCE January 2026 factsheet](https://www.dce.com.cn/dce/file/2026-01-15/17684624156122c9a882b9ae6dcbb289019bc092f6fc1681.pdf) |
| **DCE Coke — J** | 100 t; CNY/t; CNY 0.5/t = CNY 50 | Physical metallurgical coke at designated warehouses. | All months; LTD tenth trading day; final delivery third trading day after LTD. **J003-2024 applies from J2604**. [DCE January 2026 factsheet](https://www.dce.com.cn/dce/file/2026-01-15/17684624156122c9a882b9ae6dcbb289019bc092f6fc1681.pdf) |

HCF is included as a current September 2026 addition: SGX's updated product page contains its contract specification and describes both HCF and ACF. The associated 500-tonne swaps remain outside this survey's futures scope. [SGX coking-coal product page](https://www.sgx.com/derivatives/products/coking-coal)

### Domestic thermal coal: a different delivery structure

| Exchange and future | Lot; quotation; tick | Settlement and specification | Important lifecycle distinction |
| --- | --- | --- | --- |
| **Zhengzhou Commodity Exchange, Thermal Coal — ZC** | **100 t trading lot; 20,000 t delivery unit**; CNY/t; CNY 0.2/t = CNY 20 | Physical: factory warehouse receipts or vehicle/vessel-board delivery; EFP also permitted. Current benchmark is **5,000 kcal/kg net as received**, with specified sulphur, ash, volatile matter and moisture limits. | All months; LTD fifth trading day. Last delivery is eighth trading day for receipts, final calendar day for vehicle/vessel-board delivery. Rules apply from **ZC2511**. [CZCE 2025 thermal-coal business rules, Articles 3–23](https://www.czce.com.cn/cn/content_file/flfg/zcjywgz/pzxz/2025/10/cf887b5b1a904caeb0be8fe72e8bd1ac.pdf) |

ZC remains relevant as a contract-design example, but the exchange's February 2026 statistics show zero thermal-coal open interest. A current rulebook entry is not evidence that a particular market is practically executable. [CZCE February 2026 monthly report](https://english.czce.com.cn/en/content_file/MarketData/MonthlyReport/2026/3/a44277d37d634d07bb77e62c116ed16b.pdf)

## 3. What the futures record needs to preserve

### Quality basis has several independent dimensions

**Gross/net calorific value** and **sample moisture basis** answer different questions. GAR means gross as received; NAR means net as received. Dry, air-dried and as-received laboratory results cannot be substituted merely because each is expressed as a percentage or kcal/kg. Conversion between gross and net values also needs composition/moisture information; it is not a universal percentage discount. SGS's calculation guide separates these operations and the applicable testing standards. [SGS coal calculations](https://www.sgs.com/en/services/coal-calculations)

For a template, retain a quality-specification reference and its version, with structured facts where they are actually needed: heat-content measure and unit; moisture basis; sulphur and ash limits; size distribution; and coking/strength properties. An energy-unit conversion belongs to separate calculation machinery. It must not redefine which coal a future references.

The globalCOAL NEWC summary illustrates why a single calorific-value field is insufficient: 6,000 kcal/kg is the pricing basis, while 5,850 is the minimum; there are also moisture, ash, sulphur, grindability and size requirements. Its metallurgical summaries introduce coking properties rather than merely another heat-content band. These are reference-commodity specifications for the cash future, not a requirement for the holder to tender a cargo. [globalCOAL SCoTA specifications](https://www.globalcoal.com/scota/specifications.cfm)

### Location and shipping basis belong to the reference asset

Keep the benchmark's loading/delivery location and its shipping basis separately. API4 and globalCOAL RB share Richards Bay, yet their publisher and index methodology differ. Conversely, an exporting-port FOB price and an importing-region CIF price incorporate different transport obligations in their underlying physical markets.

A cash future can therefore need detailed reference-location facts while having **no physical-delivery obligation**. A physical future needs a further specification for eligible delivery locations, documents, quantity tolerances, inspection and transfer of title. Avoid making one ambiguous `delivery_location` field perform both jobs.

### Trading lot, invoice quantity and delivery unit are distinct

The number of lots times the trading multiplier describes futures exposure. Physical settlement may require an aggregate delivery unit, then adjust invoice quantities or prices for the accepted material. The ZC example above demonstrates why these should be separate facts.

ZC uses piecewise calorific-value price adjustments, sulphur discounts and moisture-related weight deductions. Price adjustment and billable-weight adjustment therefore need separate contractual facts. [CZCE rules, Article 23](https://www.czce.com.cn/cn/content_file/flfg/zcjywgz/pzxz/2025/10/cf887b5b1a904caeb0be8fe72e8bd1ac.pdf)

The physical inventory record can hold actual assay results, receipt identifiers and allocated locations when delivery occurs. A newly executed future should identify the applicable delivery basket/rules without pretending that those later allocations are already known.

### Averages require an observation convention

Specify the publisher, exact assessment/index, observation period, observation calendar, aggregation rule and rounding. “Monthly average coal price” is insufficient: a published monthly average of weekly indexes and an arithmetic average of daily assessments need not produce the same result.

ICE API2/API4 settlement uses the relevant published **monthly** index, compiled from weekly observations. Section U normally places publication of the exchange cash settlement price on the business day following the last Friday; payment is due no later than the trading day after publication, subject to clearing-house arrangements. Thus LTD, publication and payment are separate dates. [ICE contract rules, U.2 and U.6–U.7](https://www.ice.com/publicdocs/contractregs/29_SECTION_U.pdf)

The SGX HCF rules also allow exchange/clearing-house determination by alternative means if the prescribed final price is unavailable. Record the contractual fallback authority; do not quietly replace a missing index with an unrelated coal curve. [HCF specification, 3.3](https://api2.sgx.com/sites/default/files/2026-09/SGX%20McCloskey%20FOB%20Australia%20Hard%20Coking%20Coal%20Futures%20Contract%20Specifications.pdf)

### Longer periods can be strips of monthly obligations

ICE API2/API4 quarters, seasons and years are groups of month contracts. Their grouped trading ends at 17:00 on the last Friday of the **first** constituent month, adjusted for a holiday. This is not a single terminal settlement at the end of the quarter or year. [ICE procedures, V.1](https://www.ice.com/publicdocs/contractregs/32_SECTION_V.pdf)

Accordingly, keep the execution's strip identity and the constituent contract months/multipliers. A quarter with 1,000 tonnes in each month represents 3,000 tonnes, with three monthly settlement obligations. Do not calculate coal quantity from the number of calendar days as though it were a constant-MW power contract. The latter statement is a modeling inference from the strip specification.

### Effective terms can depend on maturity

DCE's quality transitions above show that two futures traded on the same day can have different applicable standards because their delivery months differ. A single current commodity specification attached to every expiry would erase this distinction. Contract-definition identity should therefore resolve the relevant maturity and rule version together.

## 4. Historical and unresolved listings: do not import old catalogues wholesale

| Exchange/product | Status established in primary material |
| --- | --- |
| **NYMEX API2, MTF** | Delisted **2 February 2026**. Its product history is useful, but it is not a current alternative to ICE API2. [SER 9671](https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2026/01/ser-9671.pdf) |
| **NYMEX API4, MFF** | The 2023 withdrawal left only expiries through December 2023 and stopped further listing. No current 2026 series is established. [NYMEX filing 23-336](https://www.cmegroup.com/content/dam/cmegroup/market-regulation/rule-filings/2023/8/23-336.pdf) |
| **NYMEX Australian coking coal ALW/ACT and API8 SSI** | Delisted in the **28 June 2021** filing. Still-accessible brochures do not establish availability. [NYMEX filing 21-246](https://www.cmegroup.com/market-regulation/rule-filings/2021/6/21-246.pdf) |
| **NYMEX Indonesian ICI4, ICI** | Delisted **21 November 2022**. Do not confuse its Argus/Coalindo assessment with SGX McCloskey M42. [NYMEX filing 22-485](https://www.cmegroup.com/market-regulation/rule-filings/2022/11/22-485.pdf) |
| **NYMEX US coal** | Central Appalachian QL/QLD delisted **9 January 2017**; Powder River Basin QP and CSX QXB delisted **11 January 2021**. These cannot support a claim of current US physical/short-ton futures coverage. [SER 7818](https://www.cmegroup.com/notices/ser/2017/01/SER-7818.pdf), [2021 delisting notice](https://www.cmegroup.com/notices/electronic-trading/2021/01/20210111.html) |
| **EEX coal** | EUR-denominated API2/API4 contracts were explicitly delisted in February 2016. That notice said USD contracts were unaffected **then**; this is not evidence of current availability. No current coal contract suite was established from the present EEX markets catalogue in this review. [EEX delisting notice](https://www.eex.com/fileadmin/Global/News/News_Import/EEX/Customer_Information/2016/20160126_Customer_Information_-_Delisting_of_EURO_Coal__prolongation_of_fee_waiver_for_delta_hedges.pdf), [current EEX markets](https://www.eex.com/en/markets) |

Older SGX API4/API5/API8, Indonesian sub-bituminous and CFR China JM25 entries also occur in historical rule revisions. The current public coal product pages retrieved for this review contain M42F, ACF and HCF. Historical tables were not promoted into current listings. This is a coverage limitation, not a claim that every omitted contract has a verified delisting date.

No current exchange-listed biomass-pellet or petroleum-coke future was verified for inclusion here. Physical cargo trading on globalCOAL is a separate market from the ICE cash futures; an electronic physical trading platform does not by itself satisfy the requested futures scope.

## 5. Minimal design conclusion

These contracts fit a common futures record if that record identifies a **versioned exchange contract and expiry**, side, lots and execution price, with contract reference data describing:

- Exact commodity/grade/index identity, currency and dimensional quotation.
- Trading multiplier, price increment and any distinct physical delivery unit.
- Cash fixing terms or physical eligibility/delivery terms, including relevant calendars.
- Independent observation, trading, publication, payment and delivery dates.
- Monthly constituents where an execution represents a strip.

Quality and reference-index terms describe the contract. Assay results and delivered receipts describe later allocations. Curves, calibration and price-conversion algorithms describe how the library computes a value. Keeping those responsibilities distinct follows the repository's principle that contracts are facts, not pricing machinery.

Source limitation: this is representative coverage, with stronger current detail for ICE, SGX, DCE and CZCE. Exact clearing cutoffs, every delivery warehouse and all current exchange risk controls require the applicable operational schedules when a contract definition is put into use. SGX's public specifications were also read through the website's public content API where the ordinary page renderer returned an unsupported-browser notice.
