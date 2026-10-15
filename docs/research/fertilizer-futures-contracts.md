# Fertilizer futures: contract terms for a general trade representation

Reviewed 14 September 2026. Scope is exchange-listed futures. This survey adds nitrogen fertilizers, phosphates and ammonia to the agricultural and industrial-materials research. It establishes representative contract structures, not a complete security master or an approved trade schema.

**The main additions are assessment-combination rules, nutrient and delivery-basis identity, and physical urea delivery.** CBOT fertilizer futures and ICE ammonia futures settle financially; ZCE urea provides the physical contrast. A fertilizer contract is not necessarily an agricultural future in an exchange's own catalogue.

## Coverage and units

| Group | Verified exchange coverage | Distinctions to preserve |
|---|---|---|
| Urea | CBOT US Gulf, Egypt, Brazil and Middle East; smaller US Gulf contract; ZCE physical urea | Granular specification, shipping basis, region, short ton versus metric tonne, cash versus physical settlement. |
| Urea ammonium nitrate solution, UAN | CBOT NOLA | Concentration and regional assessment identity; solution mass is not contained-nitrogen mass. |
| Diammonium phosphate, DAP | CBOT NOLA | Compound/grade and barge-delivery price basis. |
| Monoammonium phosphate, MAP | CBOT Brazil | Assessment includes the 11-52 grade designation and CFR basis. |
| Ammonia | ICE Argus Northwest Europe and US Gulf; ICE Platts Northwest Europe | Publisher, daily versus weekly observations, FOB versus CFR and duty treatment. |

NOLA means New Orleans. `t` below means metric tonne; `st` means US short ton. FOB and CFR identify different shipping-cost bases. In a financially settled contract, these describe the **referenced assessment**, not an obligation for the futures holder to arrange that shipment. The mass in a fertilizer lot is product mass unless the contract expressly says otherwise.

The current [CBOT rulebook](https://www.cmegroup.com/rulebook/CBOT/) lists the relevant contracts in chapters 41–45 and 47–49. This survey did not establish a current exchange-listed potash contract. A publication called “Potash Futures” is insufficient evidence: S&P uses that name for a forecasting report. Other fertilizer compounds remain a coverage question, not an assertion that no exchange anywhere lists them. [S&P product description](https://www.spglobal.com/energy/en/products-solutions/fertilizers/potash-futures)

## CBOT cash-settled fertilizers

All eight contracts below quote USD per stated ton unit. The 100-ton contracts have a USD 0.25 price tick, worth USD 25 per lot. The ten-short-ton contract instead has a USD 1 tick, worth USD 10. Their floating settlement prices have USD 0.01 precision; an execution tick and a settlement-price increment are separate facts. Each row links its governing chapter.

| Future / code | Lot | Assessment identity and frequency | Source |
|---|---:|---|---|
| Urea US Gulf — **UFV** | 100 st | ICIS granular barges, FOB USG, 0–30 days; Profercy US Gulf FOB, 30 days. **Daily** inputs. | [Chapter 41](https://www.cmegroup.com/rulebook/CBOT/III/41.pdf) |
| Urea FOB Egypt — **UFE** | 100 t | ICIS and Profercy granular spot Egypt FOB. Weekly. | [Chapter 42](https://www.cmegroup.com/rulebook/CBOT/III/42.pdf) |
| Urea CFR Brazil — **UFB** | 100 t | ICIS and Profercy granular spot Brazil CFR. Weekly. | [Chapter 43](https://www.cmegroup.com/rulebook/CBOT/III/43.pdf) |
| Urea FOB Middle East — **UME** | 100 t | ICIS and Profercy granular Arab Gulf FOB. Weekly. | [Chapter 44](https://www.cmegroup.com/rulebook/CBOT/III/44.pdf) |
| UAN FOB NOLA — **UNO** | 100 st | ICIS 32% UAN FOB NOLA; Profercy NOLA/Cincinnati netback assessment. Weekly. | [Chapter 45](https://www.cmegroup.com/rulebook/CBOT/III/45.pdf) |
| DAP FOB NOLA — **DFN** | 100 st | ICIS and Profercy DAP bulk, NOLA FOB barge, short-ton basis. Weekly. | [Chapter 47](https://www.cmegroup.com/rulebook/CBOT/III/47.pdf) |
| Ten-Ton Urea US Gulf — **MFV** | 10 st | Same named daily US Gulf assessment inputs as UFV; its own contract size and price increment. | [Chapter 48](https://www.cmegroup.com/rulebook/CBOT/III/48.pdf) |
| MAP CFR Brazil — **MFC** | 100 t | ICIS MAP bulk Brazil CFR sight; Profercy Brazil CFR 11-52. Weekly. | [Chapter 49](https://www.cmegroup.com/rulebook/CBOT/III/49.pdf) |

The current [CME fact card](https://www.cmegroup.com/markets/agriculture/files/cbot-fertilizer-products-fact-card.pdf) identifies **UNO** for the UAN future. Some educational material retains UFU, an older swap identifier. Use the current listed future's identity, and keep exchange/venue with the symbol: symbols are not globally unique.

### Assessment arithmetic matters

The rules do **not** simply average the two publishers' midpoints. For a publication set containing each publisher's low and high, remove one highest observation and one lowest observation, then average the remaining pair. Average those daily or weekly results over the contractual period. A tie removes one occurrence of the extreme, not every matching value. [US Gulf rule 41101](https://www.cmegroup.com/rulebook/CBOT/III/41.pdf)

Missing-data rules are contractual too. A publisher's single price is included twice. When one publisher supplies no price, average the available publisher's prices; when neither publishes, omit that observation period. These are not instructions to insert zeroes, duplicate the previous fixing, or reweight by calendar days. [Middle East rule 44101](https://www.cmegroup.com/rulebook/CBOT/III/44.pdf)

For an illustrative publication set of **[300, 310, 320, 400]**, the contractual trimmed result is **315**. Averaging the two publisher midpoints instead gives **332.5**. These are invented numbers, showing why a generic “average index” label is insufficient. Trimming also means the result is not one fixed linear combination of all raw inputs: which observations survive depends on their values.

UFV and MFV currently use **daily** observations. The daily change applied to April 2024 maturities onward; old weekly descriptions should not be propagated into today's US Gulf definitions. [Exchange amendment](https://www.cmegroup.com/notices/ser/2023/10/SER-9262.pdf)

### Expiry, averaging and cash timing

| Convention | Contracts | Meaning |
|---|---|---|
| Publication-linked month-end | UFV and MFV | Last trade is the month's last business day that is an ICIS and/or Profercy publication date. December observations run only through last trade. [MFV rule 48102.E](https://www.cmegroup.com/rulebook/CBOT/III/48.pdf) |
| Last Thursday with calendar adjustments | UFE, UFB, UME, UNO, DFN and MFC | Normally last Thursday, with the specified business-day adjustments. December uses the Thursday **immediately preceding December 26**, adjusted as prescribed; December 26 itself is excluded. [Egypt rule 42102.E](https://www.cmegroup.com/rulebook/CBOT/III/42.pdf) |
| December cutoff | Weekly contracts | December's averaging is expressly truncated at last trade. Do not apply that cutoff indiscriminately to every month's publications. [Brazil rule 43101](https://www.cmegroup.com/rulebook/CBOT/III/43.pdf) |

The weekly rules include Exchange and London business-day conditions; the exact schedule should be resolved for the relevant maturity. Daily variation margin, final price determination and final cash movement are distinct events. These chapters establish cash settlement following termination; this review does not establish a universal fixed payment lag for the CBOT suite.

## ICE ammonia

Each representative contract below is **100 metric tonnes**, quoted in USD/t, financially settled. Its page lists up to 36 consecutive months and final payment two clearing-house business days after last trade. Those common terms do not make the benchmarks interchangeable.

| Future / venue | Final price reference | Last trade and source |
|---|---|---|
| Argus NWE CFR — **AOA**, ICE Futures Europe | Monthly average of daily Argus Northwest Europe CFR, duty-paid/free assessments. | Last trading day of the month. [Specification](https://www.ice.com/products/82800207/Ammonia-Outright-Argus-Ammonia-NWE-CFR-Future) |
| Argus US Gulf CFR — **AOH**, ICE Futures U.S. | Monthly average of daily Argus US Gulf CFR assessments. | Last trading day of the month. [Specification](https://www.ice.com/products/83048632/Ammonia-Outright-Argus-Ammonia-US-Gulf-CFR-Future) |
| Argus US Gulf FOB — **AOX**, ICE Futures U.S. | Monthly average of daily Argus US Gulf FOB assessments. | Last trading day of the month. [Specification](https://www.ice.com/products/83049093/Ammonia-Outright-Argus-Ammonia-US-Gulf-FOB-Future) |
| Platts NWE CFR weekly — **AOC**, ICE Futures Europe | Average of the high/low midpoints from the weekly Platts Fertecon ammonia report, Northwest Europe CFR duty-paid/free. | Last Thursday; preceding business/publication day when required. [Specification](https://www.ice.com/products/83046799/Ammonia-Outright-Ammonia-CFR-NWE-Weekly-Platts-Future) |

The ICE pages distinguish a **USD 0.01/t trading quotation** from **USD 0.001/t minimum fluctuation and settlement quotation**. Preserve the published fields and reconcile the executable increment against governing rules or exchange reference data before configuration. Do not resolve that discrepancy by rounding all prices to whichever value is convenient.

The AOC page retrieved for this review gives the last-Thursday rule above; it does not establish the CBOT December exception. Its weekly midpoint formula also differs from CBOT's two-publisher trimming. Publication calendars and the named assessments belong to each contract independently.

Ammonia appears in ICE's energy catalogue, but these references should not acquire an invented “green,” “blue,” emissions-certified or fuel-grade eligibility requirement. A use-case classification does not alter the named benchmark.

## Physical contrast: ZCE urea

Zhengzhou Commodity Exchange's **UR** establishes a materially different structure: physical urea delivery, designated facilities and deliverable-product rules. The January 2026 rules specify **20 t per trading lot and delivery unit**, quotation in **CNY/t**, a **CNY 1/t tick** worth **CNY 20**, last trading on the **tenth trading day** of the delivery month and last delivery on its **thirteenth trading day**. The benchmark delivery price includes tax and packaging. [Exchange-authored 2026 rules, mirrored attachment](https://np-newsimg.dfcfw.com/download/A2_cms_f_20260116162839944245?abc8712.pdf%3F=&direct=1)

Benchmark quality uses GB/T 2440-2017 agricultural premium small/medium-granule urea. Amended substitute-grade and discount provisions apply from **UR2703 onward**; the other changes apply from 16 January 2026. Permitted substitutes include specified large-granule grades. Regional adjustments are announced separately and remain an onboarding input. Do not apply one undated quality schedule to all maturities. [2026 rules and applicability](https://np-newsimg.dfcfw.com/download/A2_cms_f_20260116162839944245?abc8712.pdf%3F=&direct=1)

**Source qualification:** the original exchange announcement returned an access error, so the exchange-authored attachment was read from a third-party mirror. The China Futures Association independently records the announcement's date, title and original URL. This is stronger evidence than a broker's paraphrase, but retain the provenance and replace the mirror with an accessible exchange copy when available. [Announcement record](https://www.cfachina.org/dzss/202602121342064685/files/basic-html/page51.html), [original exchange announcement](https://www.czce.com.cn/cn/gyjys/jysdt/ggytz/webinfo/2026/1/5b00453421d74365824060ede0e4cb07.htm)

ZCE has also documented group delivery with nearby pickup: eligible nonbenchmark locations can carry announced adjustments, with settlement of the difference between factory warehouse and receiver. This illustrates why delivery location and invoice adjustment must be separate from the exchange quote. Current participating facilities and adjustment schedules still require current reference data. [ZCE March 2024 monthly report](https://english.czce.com.cn/en/rootfiles/2024/04/16/1714279746355913-1714279746368811.pdf)

## Consequences for the eventual trade template

These are design inferences, not new user-entered fields for every fertilizer trade.

1. **Keep the product's unit exact.** Short tons, metric tonnes, solution mass and contained-nutrient mass are different quantities. Concentration belongs to benchmark or eligibility identity; it does not silently rescale lot size.
2. **Represent the complete final-price recipe.** Publisher, assessment, daily/weekly schedule, trimming or midpoint operation, observation omissions and final rounding determine the price.
3. **Separate commodity identity from settlement.** Physical UR and cash-settled US Gulf urea can belong to the same family while creating different obligations.
4. **Separate contract dates.** Last trade need not mean month-end, last observation or payment day. December rules are product-specific.
5. **Keep quote conventions explicit.** Trading tick, floating-price precision, mass unit and monetary multiplier are independent contract facts.
6. **Version deliverability and reference definitions.** A grade amendment or publisher-frequency change can apply by contract maturity. Date-sensitive reference data should resolve those facts before pricing.

The most revealing acceptance examples are the four-price trimming calculation, the 100-st versus 10-st tick calculation, weekly December expiry, and a physically delivered UR maturity with its applicable quality schedule. Together they cover the new structures without requiring a fertilizer-specific pricing engine.
