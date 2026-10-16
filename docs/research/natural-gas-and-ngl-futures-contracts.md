# Natural gas and NGL futures: contract terms for a general trade representation

Research reviewed 14 September 2026. Evidence for discussion, not an approved constructor specification or an implementation decision. Companion to the [petroleum survey](petroleum-futures-contracts.md).

The largest addition to the petroleum findings is a quantity profile. A gas contract can represent a fixed total energy quantity, a fixed quantity for each gas day, or a constant energy flow during each delivery hour. These produce different contract quantities, especially across months of different lengths and daylight-saving changes. The price observation schedule remains a separate contract fact.

## Scope and evidence

The verified examples cover CME Group/NYMEX, ICE Futures U.S., ICE Futures Europe/Endex, EEX/ECC, ASX, MCX and NSE, with NGL extensions identified below. The survey selects structurally distinct terms rather than every location ticker. A chapter or product page establishes documented terms, not current liquidity or every presently tradable maturity. Effective dates, applicable contract months, retirement notices and live series definitions matter.

Three commodity groups should stay distinct:

| Commodity group | Scope |
|---|---|
| Pipeline natural gas | Hub/market-area gas, traded primarily by energy content; physical network obligations and financial price references. |
| LNG | Liquefied natural gas, predominantly methane. LNG-linked futures can reference delivered-cargo assessments while being entirely cash settled. |
| NGLs/LPG | Ethane, propane, normal butane, isobutane and natural gasoline/pentanes-plus; relevant mixtures and baskets. LPG covers propane/butane products and mixtures. These are chemically and commercially distinct from LNG. |

EIA distinguishes the NGL components and excludes LNG from its hydrocarbon-gas-liquids grouping. [NGL glossary](https://www.eia.gov/tools/glossary/?id=natural), [HGL definitions](https://www.eia.gov/analysis/hgl/)

Bespoke gas supply with volume optionality, storage, transport capacity, liquefaction services and LNG cargo-sale agreements are boundary cases, not automatically exchange futures. Likewise, an exchange's spot, forward, swap, option and futures catalogues must not be merged merely because they share a hub. Renewable-gas certificates and petrochemical olefins need their own instrument review.

`M` below means the named contract/delivery month. MMBtu is one million Btu, GJ a gigajoule, MW an energy rate and MWh an energy quantity. `t` means metric tonne; `gal` means U.S. liquid gallon; `bbl` means petroleum barrel. A quoted price, a trading tick, settlement precision and final cash rounding are separate facts.

## Review groups

| Group | Examples / defining terms |
|---|---|
| Physical pipeline benchmarks | Henry Hub, European virtual hubs; quality/network rules, nominations and delivery profiles. |
| Cash benchmark expiry | Last-day, penultimate, micro and e-mini contracts tied to a particular futures settlement. |
| Monthly physical-market index | A bidweek/month-ahead index for delivery during M, rather than a month-long daily average. |
| Geographic basis | Local monthly index minus a benchmark futures expiry price, or another specified index. |
| Daily-price versus monthly-index differential | Realized daily-price average minus the month-ahead index. |
| Daily and balance-of-month | Individual gas-day price, weekend/holiday packages, selected windows and scheduled publications. |
| European spot-index financial | EGSI and other cash benchmarks distinct from physical monthly futures settlement. |
| LNG assessment and derived LNG price | JKM, NWE and U.S. Gulf references; shipping periods, offset assessment windows, gas-plus-basis formulas. |
| Currency-converted gas | Fixed-energy USD products tied to European flow products; INR contracts tied to Henry Hub. |
| Physical and financial NGL components | Same named liquid/facility can appear in both title-transfer and cash-price products. |
| NGL spreads and baskets | Location/product spreads, fixed component baskets, LPG/crude/naphtha/gas conversion coefficients. |
| Cascading maturities | A quarter/season/year can become several shorter futures rather than one terminal cash settlement. |

These are overlapping review groups, not proposed subclasses.

## North American gas

### Benchmark-linked and physical futures

| Contract | Quantity / quote | Settlement reference and expiry |
|---|---|---|
| NYMEX Henry Hub, NG | Fixed 10,000 MMBtu; USD/MMBtu; tick 0.001; physical delivery tolerance ±2% | Physical at Henry Hub, Louisiana, during M. Last trade third business day before M, with protection for originally listed expiry after certain subsequent holiday changes. [Chapter 220](https://www.cmegroup.com/rulebook/NYMEX/2/220.pdf) |
| NYMEX Micro Henry Hub, MNG | Fixed 1,000 MMBtu; USD/MMBtu; tick 0.001 | Cash NG-linked; expires one business day before NG. The chapter and educational description need reconciliation over the precise final observation; see evidence gaps. [Chapter 440](https://www.cmegroup.com/rulebook/NYMEX/4/440.pdf) |
| NYMEX E-mini, QG | Fixed 2,500 MMBtu; USD/MMBtu; tick 0.005 | Cash at corresponding NG settlement on **QG's own last trading day**, immediately before NG expiry. [Chapter 402](https://www.cmegroup.com/rulebook/NYMEX/4/402.pdf) |
| NYMEX Henry Hub Last Day / Look-Alike Last Day financial | Fixed 2,500 / 10,000 MMBtu; USD/MMBtu; tick 0.001 | Cash corresponding NG final expiry settlement; last trade third business day before M. Same reference does not imply same multiplier. [Chapter 508](https://www.cmegroup.com/rulebook/NYMEX/5/508.pdf), [823](https://www.cmegroup.com/rulebook/NYMEX/8/823.pdf) |
| NYMEX Henry Hub Penultimate / Look-Alike Penultimate financial | Fixed 2,500 / 10,000 MMBtu; USD/MMBtu; tick 0.001 | Cash NG settlement on the business day **before NG expiry**; trading ends that earlier day. [Chapter 529](https://www.cmegroup.com/rulebook/NYMEX/5/529.pdf), [824](https://www.cmegroup.com/rulebook/NYMEX/8/824.pdf) |
| NYMEX Henry Hub Weekly | Fixed 10,000 MMBtu; USD/MMBtu; tick 0.001 | Arithmetic average of first-nearby NG settlements for each business day of the contract week. If NG expires that week, use the **second nearby for the entire week**. Expires Friday/preceding business day. This averages futures prices, not physical spot prices. [Chapter 509](https://www.cmegroup.com/rulebook/NYMEX/5/509.pdf) |
| ICE Henry LD1 Fixed Price, H / 25K | Fixed 2,500 / 25,000 MMBtu; USD/MMBtu; standard quote increment 0.001 | Cash corresponding NG final settlement; last trade third business day before M. H pays first clearing-organization business day after expiry. [H](https://www.ice.com/products/6590258), [25K](https://www.ice.com/products/49883945) |
| ICE Henry LD1 Same Day Fixed Price, SDH | Fixed 2,500 MMBtu per daily contract; USD/MMBtu | Cash first-nearby monthly NG settlement **on that daily contract date**. Last trade that business day; payment next clearing-organization business day. A daily maturity need not reference daily physical gas. [Specification](https://www.ice.com/products/6590266/Henry-LD1-Same-Day-Fixed-Price-Future) |

NG's delivery rules incorporate the Sabine FERC tariff effective at delivery. Delivery is FOB the buyer's interconnection, by flow/displacement or permitted intra-hub transfer, as uniformly as pipeline practice allows. Physical payment normally falls on the following month's 20th with a bespoke holiday adjustment. Invoices use actual delivered energy, with provisional payment and later correction when quantities are unavailable. Thus the fixed futures multiplier, permitted delivery tolerance and final physical invoice quantity are distinct. [NG delivery and payment rules](https://www.cmegroup.com/rulebook/NYMEX/2/220.pdf)

### Regional indexes, basis and daily gas

| Contract | Quantity / quote | Settlement formula and calendar |
|---|---|---|
| ICE Waha Fixed Price, FQW | Fixed 2,500 MMBtu; USD/MMBtu | Single monthly Inside FERC Waha Index, first publication in M. Last trade last business day before M; payment third clearing business day after expiry. This is a bidweek index, not an average across M's daily spot prices. [Specification](https://www.ice.com/products/69723181/Waha-Fixed-Price-Future) |
| ICE Waha Basis, WAH | Fixed 2,500 MMBtu; USD/MMBtu | Inside FERC Waha monthly index **minus** corresponding NG final settlement. Same premonth expiry and +3 clearing-business-day payment convention. The components have different fixing events. [Specification](https://www.ice.com/products/6590171/Waha-Basis-Future) |
| ICE SoCal Border Basis, SCL | Fixed 2,500 MMBtu; USD/MMBtu | NGI SoCal Border monthly average minus corresponding NG final settlement. Last trade last business day before M; payment third clearing business day after last trade. Regional basis does not universally use Inside FERC. [Specification](https://www.ice.com/products/6590152/Socal-Border-Basis-Future) |
| ICE Waha Index, WAI | Fixed 2,500 MMBtu **for the monthly contract**; USD/MMBtu | Average Gas Daily Waha Midpoints for each calendar delivery day minus monthly Inside FERC Waha Index. Last trade **before M**, daily observations **during M**, payment +3 clearing business days after M's last business day. [Specification](https://www.ice.com/products/6590216) |
| ICE Chicago Index, CIS | Fixed 2,500 MMBtu; USD/MMBtu | Average Platts Gas Daily Chicago city-gates Midpoints minus NGI Bidweek Survey Chicago Citygate monthly average. Same premonth expiry/postmonth settlement structure. One future combines different publishers and assessment definitions. [Specification](https://www.ice.com/products/6590179/Chicago-Index-Future) |
| ICE Henry Swing, HHD / Waha Swing, WAS | Fixed 2,500 MMBtu **per daily contract**; USD/MMBtu | Cash specified Gas Daily location Midpoint for the delivery date. Last trade preceding business day; payment +3 clearing business days after expiry. These listed “Swing” contracts do not provide a buyer's volume-exercise right. [Henry](https://www.ice.com/products/6590229/specs), [Waha](https://www.ice.com/products/6590256/Waha-Swing-Future) |

These ICE pages commonly quote prices to USD0.0001/MMBtu but refer separately to Chapter 18 Resolution 1 for minimum fluctuations by trade type. Quote precision is not necessarily the executable tick.

Platts Gas Daily's field named “Midpoint” is a **volume-weighted transaction average**, not `(high + low) / 2`. Trade date, publication date and flow date differ: a normal Friday transaction period covers Saturday–Monday, with holiday/month-end exceptions. For a future averaging calendar delivery days, the implementation inference is to assign the assessment to its covered flow dates before averaging, rather than average unique publication records. [Platts U.S./Canada gas methodology, July 2026](https://www.spglobal.com/content/dam/spglobal/ci/en/documents/platts/en/our-methodology/methodology-specifications/natural-gas/us-canada-natural-gas-methodology.pdf)

### Canadian references

| Contract | Quantity and quote | Price definition and dates |
|---|---|---|
| ICE AB NIT Basis, AEC | Fixed 2,500 MMBtu; USD/MMBtu | Cash: CGPR's NGX AB-NIT month-ahead 7A index in USD/MMBtu minus NYMEX NG final settlement for the corresponding period. Trading ends last business day before M; publication is the period's first publication date. Payment uses a Canadian-business-day step followed by a clearing-organization-business-day step. [Specification](https://www.ice.com/products/6590123/AB-NIT-Basis-Future) |
| ICE AB NIT (7a/5a) Index, NG7 | Fixed 2,500 MMBtu; USD/MMBtu | Cash: average daily 5A prices **minus** monthly 7A index, despite the order suggested by the title. Trading ends before M, but daily observations continue during M and payment follows M's end. Both are specifically the publisher's USD/MMBtu series. [Specification](https://www.ice.com/products/64286867/AB-NIT-7a-5a-Index-Future) |

Design consequence: Canada does not imply CAD/GJ. Nor should the library derive USD from a CAD series if the contract directly specifies a published USD index. Price identity must include series, currency, denominator, statistic and delivery period.

## European pipeline gas and LNG

### Physical hub gas and short periods

| Contract | Quantity / quote | Delivery and expiry terms |
|---|---|---|
| ICE Endex Dutch TTF monthly, TFM | **1 MW × actual delivery hours**; 23/24/25 MWh per gas day; EUR/MWh; tick 0.005; screen minimum five lots | Equal hourly transfer of TTF rights, 06:00–06:00 local gas day. Last trade 18:00 CET two **UK business days** before delivery; final end-of-day settlement sets invoice price. ICE nominates to GTS via Edig@s before 13:00 preceding business day. [Specification](https://www.ice.com/products/27996665/Dutch-TTF-Natural-Gas-Futures) |
| ICE TTF daily, TFE | Same 1 MW flow basis and EUR/MWh quote | Daily futures underpin day-ahead, weekend, balance-of-week, next-working-week and BOM strips. Last trade 18:00 preceding business day; nomination deadline 20:00. Weekend groups can include UK bank holidays. BOM begins two business days ahead, with at least two gas days. [Specification](https://www.ice.com/products/45436633/Dutch-TTF-Natural-Gas-Daily-Futures) |
| ICE NBP monthly / daily, M / NBD | **1,000 therm/day**; pence/therm; tick 0.01p; monthly screen minimum five lots | Physical transfer of NBP rights. Monthly last trade 17:00 London time two business days before delivery; daily expiry preceding business day. Matching Gemini nominations by 18:30 preceding business day. [Monthly](https://www.ice.com/products/910/UK-NBP-Natural-Gas-Futures), [daily](https://www.ice.com/products/20774967/UK-NBP-Natural-Gas-Daily-Future) |
| ICE THE / Austrian CEGH VTP, GNM / AVM | **1 MW × actual 23/24/25 hours**; EUR/MWh; tick 0.005; minimum five lots | Equal hourly physical hub-right delivery, 06:00–06:00. Monthly expiry 18:00 CET two UK business days before delivery. ICE Edig@s nominations before 13:00 preceding business day, in kWh/hour. THE's current page retains a legacy NCG URL. [THE](https://www.ice.com/products/27996810/NCG-Gas-Futures), [VTP](https://www.ice.com/products/71523204) |
| ICE French PEG, PEG | **1 MWh/day**; EUR/MWh; tick 0.005; screen minimum **120 lots** | Fixed daily energy, spread equally over delivery hours; physical PEG-right transfer. Expiry two UK business days before delivery. ICE nominates before 13:00 preceding business day in kWh/hour. [Specification](https://www.ice.com/products/82426582/French-PEG-Natural-Gas-Futures) |
| ICE Italian PSV, IGA | Described as 1 MW, but explicitly **24 MWh/day**; EUR/MWh; tick 0.005; minimum five lots | Physical PSV transfer; fixed 24-hour multiplier is a contractual exception. Expiry two UK business days before delivery; ICE PSV nominations before 11:30 preceding business day, in **MWh/day**. [Specification](https://www.ice.com/products/49321531/Italian-PSV-Natural-Gas-Futures.) |
| ICE PEG Daily Financial ICIS, DFV | **1 MWh/day**; EUR/MWh; tick 0.005; screen minimum 120 lots | Cash midpoint of applicable ICIS Day-ahead/Weekend bid and offer assessments. Daily contracts/strips; expiry 18:00 preceding business day. Unlike Platts Gas Daily “Midpoint,” this benchmark does specify bid/offer midpoint. [Specification](https://www.ice.com/products/83045090) |

ICE Endex defines “CET” as CET **or summer time as applicable**, unless specified otherwise. Use a local-time-zone rule, not an unconditional UTC+1 offset. Its NextHour/WithinDay gas instruments are classified as **spot**, despite sharing the venue. [Current Endex rules, general time provision and Appendix A.3.1](https://www.ice.com/publicdocs/endex/ICE_Endex_Markets_B.V._Rules.pdf)

NBP's gas-day rule states 05:00–05:00 without an explicit time-zone label in that section; this needs further procedure-level confirmation. Individual daily contracts remain distinct within a group. Longer positions are regrouped after cessation under the delivery procedures. Price-difference settlement and the physical invoice are separate cash obligations; a payment provision for the former does not establish the latter's due date. [NBP contract rules, S.1/S.3](https://www.ice.com/publicdocs/contractregs/27_SECTION_S.pdf), [procedures, T.2/T.9](https://www.ice.com/publicdocs/contractregs/30_SECTION_T.pdf)

### Currency-converted European gas

| Contract | Quantity / quote | Price reference and dates |
|---|---|---|
| ICE TTF 1st Line Financial USD, TFU | Fixed **10,000 MMBtu**; USD/MMBtu; tick 0.001 | Average daily TFM settlements **while the named delivery month is front month**, converting each day at its 16:00 UK EUR/USD fixing. Previous published FX if missing. Expiry two business days before delivery; payment +2 clearing-house business days. [Specification](https://www.ice.com/products/68361290/Dutch-TTF-Natural-Gas-1st-Line-Financial-Futures-USD-MMBTU) |
| ICE NBP 1st Line Financial USD, UKD | Fixed **10,000 MMBtu**; USD/MMBtu; governing-rule tick 0.001 | Same structure, using daily NBP settlements and GBP/USD. Expiry two business days before delivery; payment +2 clearing-house business days. Web-page numeric tick conflicts with the governing rule; see gaps. [Specification](https://www.ice.com/products/67961645/UK-NBP-Natural-Gas-1st-Line-Financial-Futures-USD-MMBTU), [Section ZZZZZZ.4](https://www.ice.com/publicdocs/contractregs/177_Section_ZZZZZZ.pdf) |
| ICE Futures U.S. TTF Last Day Financial USD, TLD | Fixed **2,500 MMBtu**; USD/MMBtu | One TFM last-trading-day observation, converted at that day's 16:00 UK EUR/USD, with prior-publication fallback. Last trade two business days before delivery. Longer displayed periods are monthly strips. Detailed IFUS conversion/payment rule remains to verify. [Specification](https://www.ice.com/products/68361285/Dutch-TTF-Natural-Gas-Last-Day-Financial-Futures-USD-MMBTU) |

The first-line window is **before physical delivery**, while that named month is the front contract. Do not import a petroleum convention that instead rolls nearby contracts during the named month.

The following dimensional expressions are inferred from the contractual unit definitions and daily conversion order; they are not pricing-model prescriptions:

```text
TTF_USD = average_d(TTF_EUR_per_MWh[d] × EURUSD_USD_per_EUR[d] × 0.293071)
NBP_USD = average_d(NBP_pence_per_therm[d] × 0.1 × GBPUSD_USD_per_GBP[d])
```

The rules define 1 MMBtu as 293.071 kWh and 1 therm as 29.3071 kWh. FX fallback is applied per observation before averaging. [USD gas contract rules](https://www.ice.com/publicdocs/contractregs/177_Section_ZZZZZZ.pdf), [NBP unit definition](https://www.ice.com/publicdocs/contractregs/27_SECTION_S.pdf)

### LNG-linked futures

All examples in this table are cash settled; DES/FOB describes the referenced assessment's delivery basis.

| Contract | Quantity / quote | Observation window and settlement |
|---|---|---|
| ICE JKM monthly | Fixed 10,000 MMBtu; USD/MMBtu; tick 0.001 | Average Platts DES Japan/Korea Marker for delivery M, on publication days **16th M−2 to 15th M−1**. Nonbusiness start follows/end precedes. Expiry adjusted 15th M−1; payment +2 clearing-house business days. [Specification](https://www.ice.com/products/6753280/JKM-LNG-PLATTS-Future) |
| ICE JKM BALMO, JKD | Fixed 10,000 MMBtu; USD/MMBtu; tick 0.001 | Same assessment, from **first nearby business day after transaction conclusion** to adjusted 15th M−1. Expiry at window end; payment +2 clearing-house business days. The observation start depends on the trade occurrence. [Specification](https://www.ice.com/products/71090498/JKM-LNG-Platts-Balmo-Future) |
| CME JKM front/back half-month, JKF / JKB | Fixed 10,000 MMBtu; USD/MMBtu; **trade tick 0.005, settlement increment 0.001** | Front averages 16th–last day M−2; back 1st–15th M−1. Expiry last weekday of window, adjusted earlier for exchange closure; final determination can wait for publication/next exchange business day. [Chapters 875](https://www.cmegroup.com/rulebook/NYMEX/8/875.pdf), [876](https://www.cmegroup.com/rulebook/NYMEX/8/876.pdf) |
| ICE West India Marker, WIM | Fixed 10,000 MMBtu; USD/MMBtu; tick 0.001 | Platts DES West India Marker AARXS00, same 16th M−2–15th M−1 window; payment +2 clearing-house business days. This future has distinct terms from ICE's similarly named OTC product. [Specification](https://www.ice.com/products/79234890) |
| ICE NWE LNG Spark, NWL | Fixed 10,000 MMBtu; USD/MMBtu; tick 0.001 | Average **daily USD-converted TTF + SparkNWE Basis**, on **Spark assessment days** while M is front month. Expiry two business days before delivery; payment +2 clearing-house business days. The rules also describe SparkSWE. [Specification](https://www.ice.com/products/82725198/NWE-LNG-Spark-Futures), [Section 7N1](https://www.ice.com/publicdocs/contractregs/Rule_Section_7N1.pdf) |
| ICE Gulf Coast LNG 1st Line, GPF | Fixed 10,000 MMBtu; USD/MMBtu; tick 0.001 | Average Platts FOB Gulf Coast GCM for M while M is front month. IFEU venue; expiry last day M−1/preceding business day; payment +2 clearing-house business days. [Specification](https://www.ice.com/products/72270573/Gulf-Coast-LNG-Platts-1st-Line-Financial-Future) |
| ICE Gulf Coast LNG Last Day, GCL | Fixed 10,000 MMBtu; USD/MMBtu; tick 0.001 | Operative reference term uses the assessment **three business days before M**; short description instead says average. IFUS venue; expiry that day; payment +1 clearing-organization business day. Preserve discrepancy pending rule reconciliation. [Specification](https://www.ice.com/products/63127250/Gulf-Coast-LNG-Platts-Last-Day-Future) |

Spark's formula is a useful composed-price example: `average_on_Spark_days(TTF_EUR/MWh × 0.293071 × same_day_EURUSD + SparkNWE_USD/MMBtu)`. The publication calendar, daily FX conversion and addition occur inside the averaging operation. [Spark contract rules](https://www.ice.com/publicdocs/contractregs/Rule_Section_7N1.pdf)

### EEX contrasts and lifecycle

| Contract group | Verified terms |
|---|---|
| EEX physical gas | TTF/THE/PSV and several other hubs use 1 MW; PEG/PVB/FIN/LTU/LVA-EST use 1 MWh/day; NBP uses 1,000 therm/day. Gas is delivered at the applicable virtual point under network rules. Physical monthly delivery uses the last-trading-day settlement price. [July 2026 specifications, A.1.2 and D.2.3](https://www.eex.com/fileadmin/EEX/Downloads/Rules/Contract_Specifications/20260723_EEX_Contract_Spezifications_0104a_E_FINAL.pdf) |
| EEX EGSI financial gas | CEGH VTP, NBP, THE and TTF products cash-settle against the corresponding European Gas Spot Index; day/weekend/week/month and longer cascading maturities are documented. These are distinct from physical futures. [Specifications, A.1.2.4 and D.2.3.2](https://www.eex.com/fileadmin/EEX/Downloads/Rules/Contract_Specifications/20260723_EEX_Contract_Spezifications_0104a_E_FINAL.pdf) |

The EGSI daily index is itself a volume-weighted spot-trade benchmark. That weighting is part of constructing the daily observable; it does not license using one pooled volume-weighted average for every longer-period future. [EEX index description](https://webshop.eex-group.com/data-type/eex-natural-gas-index-european-gas-spot-index-egsi-file-cloud-eod)

EEX/ECC cascading replaces a longer position with shorter positions. A quarter becomes three months; a calendar year becomes January–March months plus Q2–Q4 quarters; a season becomes its first three months plus the remaining quarter. Preserve the generated contract identities and the position/cash adjustments required by clearing; do not retain both parent and children as live exposure. [ECC cascading explanation](https://www.eex.com/fileadmin/ECC/Downloads/Operations/Reports/Financial_Settlement_Reports/250919_Cascading_Explainer_ECC.pdf)

ECC's physical-gas expiry timeline distinguishes the monthly last-trading date, subsequent nominations, daily delivery payments and reduction of the remaining contract quantity as delivery progresses. Its monthly last trading day is two ECC business days before delivery starts; longer maturities terminate/cascade one ECC business day earlier. [March 2026 timeline](https://www.ecc.de/fileadmin/ECC/Downloads/Operations/Processes/20260323_GAS_Expiry_Timeline.pdf)

## Other gas markets and currencies

| Contract | Quantity / quote | Settlement and calendar terms |
|---|---|---|
| ASX Wallumbilla, GZ | 100 GJ **per day** over M; AUD/GJ; AUD0.01 tick | Physical via mandatory Delivery EFP for open expiry positions, resulting in an AEMO monthly Wallumbilla netted contract at the High Pressure Trade Point. Last trade five business days before M. The future leads to another delivery contract, not merely a cash index payment. [ASX fact sheet](https://www.asx.com.au/content/dam/asx/markets/trade-our-derivatives-market/derivatives-market-overview/energy-derivatives/australian-gas-fact-sheet.pdf) |
| ASX Victorian wholesale gas, GX | 100 GJ **per day** over a calendar quarter; AUD/GJ; AUD0.01 tick | Cash against the quarter's average beginning-of-day (06:00) wholesale gas price. Last trade last business day of quarter; settlement fourth business day afterward. [ASX fact sheet](https://www.asx.com.au/content/dam/asx/markets/trade-our-derivatives-market/derivatives-market-overview/energy-derivatives/australian-gas-fact-sheet.pdf), [December 2025 specifications, p.35](https://www2.asx.com.au/content/dam/asx/participants/derivatives-market/ird/asx24-contract-specifications.pdf) |
| MCX natural gas / mini | Fixed 1,250 / 250 MMBtu; INR/MMBtu; INR0.10 tick | Cash to NYMEX front-month NG settlement on the MCX contract's last trading day, converted using the **last available** RBI USDINR reference rate and rounded to tick. Expiry comes from the launch calendar. These references are not necessarily simultaneous. [2026 standard terms](https://www.mcxindia.com/docs/default-source/products/contract-specification/natural-gas/natural-gas-january-2026-contract-onwards2ff2141b-f6e4-4b6a-9f0e-59f260cecf9b.pdf), [mini](https://www.mcxindia.com/docs/default-source/products/contract-specification/natural-gas-mini-option/natural-gas-mini-january-2026-contract-onwards.pdf) |
| NSE Henry Hub natural gas / mini | Fixed 1,250 / 250 MMBtu; INR/MMBtu; INR0.10 tick | Cash against NG on own expiry, with last-available RBI USDINR conversion. Expiry follows the exchange launch calendar. [NSE specifications](https://www.nseindia.com/static/products-services/commodity-derivatives-contract-specification-energy) |
| NSE Indian Natural Gas, NATGASIND | Fixed 250 MMBtu; INR/MMBtu on gross-calorific-value basis; INR1 tick | Cash monthly weighted average of actual IGX deliveries, excluding specified ceiling-price, small-scale LNG and long-duration trades. Price basis identifies Gujarat/Dahej and excludes specified taxes, fees and transport charges. Last trade last business day of M. This is a domestic reference, distinct from NSE's Henry Hub contracts. [NSE specifications](https://www.nseindia.com/static/products-services/commodity-derivatives-contract-specification-energy) |

## NGL and LPG contracts

### Components, grades and delivery

| Contract | Quantity / quote | Settlement and physical-market distinctions |
|---|---|---|
| NYMEX physical Mont Belvieu Non-TET ethane / propane | **42,000 gal = 1,000 bbl**, at **60°F**, no volume tolerance; USD/gal; tick 0.00001 | Physical Enterprise Mont Belvieu delivery. Last trade second-last business day of M; delivery last business day. Invoice uses respective OPIS average **on last trading day**, rather than full-month average. [Ethane chapter 369](https://www.cmegroup.com/rulebook/NYMEX/3/369.pdf), [propane 364](https://www.cmegroup.com/rulebook/NYMEX/3/364.pdf) |
| NYMEX Conway Physical Propane In-Well | **42,000 gal**, 60°F, no tolerance; USD/gal; tick 0.00001 | Title transfer, last-business-day delivery and penultimate-business-day expiry/OPIS invoice reference. Rulebook names Williams Midstream NGL facility; current operator identity requires verification. [Chapter 241](https://www.cmegroup.com/rulebook/NYMEX/2/241.pdf) |
| NYMEX cash Non-TET purity ethane / normal butane / isobutane / natural gasoline | Each **42,000 gal**; USD/gal; tick 0.00001 | Four separate cash futures, averaging the exact applicable OPIS “Any Current Month” series on business days of M. Last trade last business day of M. Component, purity and assessment identity matter. [C2 chapter 410](https://www.cmegroup.com/rulebook/NYMEX/4/410.pdf), [nC4 411](https://www.cmegroup.com/rulebook/NYMEX/4/411.pdf), [iC4 406](https://www.cmegroup.com/rulebook/NYMEX/4/406.pdf), [C5+ 405](https://www.cmegroup.com/rulebook/NYMEX/4/405.pdf) |
| NYMEX cash Mont Belvieu TET / Non-TET propane | Each **42,000 gal**; USD/gal; tick 0.00001 | Cash monthly average of distinct OPIS TET or Non-TET propane series. Last trade last business day of M. Same chemical and town do not identify the same deliverable market. [TET chapter 409](https://www.cmegroup.com/rulebook/NYMEX/4/409.pdf), [Non-TET 414](https://www.cmegroup.com/rulebook/NYMEX/4/414.pdf) |
| ICE Ethane in E/P Mix, OPIS Conway In-Well, ECC | **1,000 bbl**, explicit 42 gal/bbl conversion; USD/gal | **Cash** monthly average of OPIS Conway “Ethane (in E-P)” series; last trade period's last business day; payment +2 clearing-house business days. Neither purity ethane nor evidence of a fixed physical blend ratio. [Specification](https://www.ice.com/products/6590284/Ethane-in-E-P-Mix) |
| ICE Normal Butane, OPIS LST ISOM Grade, BUE | **1,000 bbl = 42,000 gal**; USD/gal | Cash monthly OPIS “TET Isom N. Butane” series; last trade last trading day of M; payment +2 clearing-house business days. LST in title, ETR ISOM on screen and TET in assessment require explicit mapping. [Specification](https://www.ice.com/products/79234889) |
| NYMEX Non-TET Ethane BALMO | **42,000 gal**; USD/gal; tick 0.00001 | Cash OPIS Purity Ethane average from selected start through month end, inclusive. Last trade last business day of M. **Do not prorate the lot by remaining days.** [Chapter 298](https://www.cmegroup.com/rulebook/NYMEX/2/298.pdf) |

NYMEX in-well delivery uses a Product Transfer Order or equivalent title transfer, with agreed book-transfer alternatives. Contractual “FOB” here concerns freedom from liens, taxes and charges; it does not establish marine loading. Payment is due by noon New York on the fifth business day after completed delivery. Purity ethane still permits specified impurities: ethane plus ethylene must be at least 95 liquid-volume percent. Propane has a separate quality envelope, including at least 90% propane and limits on propylene/heavier components. Quality and facility references therefore need versions. [Ethane delivery rules](https://www.cmegroup.com/rulebook/NYMEX/3/369.pdf), [propane quality rules](https://www.cmegroup.com/rulebook/NYMEX/3/364.pdf)

### Global LPG prices, spreads and baskets

| Contract | Quantity / quote | Price formula and dates |
|---|---|---|
| ICE NGL Basket, OPIS Mont Belvieu Non-TET, NGB | **1,000 bbl**; USD/bbl; trading quotation 0.01, settlement/minimum fluctuation 0.001 | Monthly basket: **42% ethane, 28% propane, 11% normal butane, 6% isobutane, 13% natural gasoline**. Convert component cents/gal to USD/bbl. Last trade last trading day of M; payment +2 clearing-house business days. Short-reference field conflicts with detailed basket definition; see gaps. [ICE](https://www.ice.com/products/62666435/NGL-Basket-OPIS-Mt-Belvieu-Non-TET-Futures), [OPIS confirmation](https://www.opis.com/about/news-item/launched-today-ngl-basket-opis-mont-belvieu-non-tet/) |
| ICE Propane Argus Saudi CP Mini, AFK | **100 t**; USD/t; trading quotation 0.01, minimum fluctuation 0.001 | Cash **single** Argus Saudi Aramco Propane CP observation on first business day of M. Last trade before M; payment +2 clearing-house business days after expiry. Monthly CP is not a daily-price average. [Specification](https://www.ice.com/products/57250502/Propane-Argus-Saudi-CP-Mini-Future) |
| ICE Butane Argus Sonatrach CP, ABO | **1,000 t**; USD/t; trading quotation 0.01, settlement quotation 0.001 | Cash single Argus Sonatrach FOB Bethioua Butane observation on first business day of M. Last trade before M; payment +2 clearing-house business days. FOB identifies the assessment, without creating physical delivery. [Specification](https://www.ice.com/products/61989097/Butane-Argus-Sonatrach-CP-Future) |
| ICE Propane Argus Far East Index, AFE | **1,000 t**; USD/t; stated minimum fluctuation 0.001, subject to trade-type rules | Cash mean of Argus AFEI propane publication-day prices during the period. Last trade period's last business day; payment +2 clearing-house business days. [Specification](https://www.ice.com/products/6590281/Propane-Argus-Far-East-Index-AFEI-Future) |
| ICE Daily Argus Far East Propane Mini, AFD | **100 t**; USD/t; trading quotation 0.01, settlement/minimum fluctuation 0.001 | Daily cash high/low AFEI quotation average. Last trade **second Argus publication business day after the nominal contract date**; payment +2 clearing-house business days. Daily label, observation and expiry dates are separate. [Specification](https://www.ice.com/products/69732302/Propane-Daily-Argus-Far-East-Mini-Future) |
| ICE Propane Argus Ningbo Index BALMO, PRT | **1,000 t**; USD/t; stated quotation/tick 0.001 | Cash Argus Ningbo propane BALMO; last trade last trading day of M. Public page does not fully define start-date generation or final payment; detailed rules remain necessary. [Specification](https://www.ice.com/products/82280438/Propane-Argus-Ningbo-Index-ANI-Balmo-Future) |
| ICE Non-TET Mont Belvieu Propane vs AFEI, CEZ | **1,000 t**; USD/t; tick 0.001 | Average converted OPIS propane **minus** average Argus AFEI, with **non-common pricing**. Convert each U.S. observation using **521 gal/t**, rounding to nearest USD cent/t **before averaging**. Last trade last trading day of M; payment +2 clearing-house business days. [Specification](https://www.ice.com/products/53168964/Propane-OPIS-Mt-Belvieu-Non-TET-vs-Propane-Argus-Far-East-Index-Future) |
| ICE AFEI Propane vs Japan Naphtha, ARR | **1,000 t**; USD/t; tick 0.001 | Average Argus AFEI minus average Platts C+F Japan naphtha. **Non-common pricing** requires separate publication schedules. Last trade last trading day of M; payment +2 clearing-house business days. [Specification](https://www.ice.com/products/53168960/Propane-Argus-Far-East-Index-AFEI-vs-Naphtha-C-F-Japan-Cargoes-Platts-Future) |
| ICE CIF ARA Propane vs Brent 1st Line, PRQ / PRR | PRQ **1,000 bbl**; PRR **1,000 t = 12,404.762 bbl**; both quote **USD/bbl**, tick 0.0001 | Convert each propane USD/t assessment at **12.404762 bbl/t**, round to USD cent/bbl, then average and subtract Brent first-line average. Brent rolls on its expiry date. Last trade last trading day of M; payment not specified on inspected pages. [PRQ](https://www.ice.com/products/82270943/Propane-Argus-CIF-ARA-vs-Brent-1st-Line-Future-in-bbls), [PRR](https://www.ice.com/api/productguide/spec/82280436/pdf) |

The PRR example separates three notions that often get conflated: **lot unit = tonne; quotation denominator = barrel; cash multiplier = contractual barrels per lot**. The conversion is a prescribed coefficient, not a request to infer the cargo's density. Similarly, non-common pricing means `average(A on A's dates) − average(B on B's dates)`; a common-date average of daily differences can produce a different result.

Further catalogue variants include butane AFEI/CIF ARA, other component BALMOs and normal-butane versus gasoline/WTI. They extend combinations of the structures above; this survey does not certify every maturity or symbol. [ICE butane catalogue](https://www.ice.com/products?filter=butane)

## Additions to the eventual trade representation

These are deductions from the examples, not an approved storage layout.

### Quantity basis and delivery profile

The total exposure for `n` lots follows different rules:

| Quantity basis | Total contract quantity |
|---|---|
| Fixed total | `n × quantity_per_lot` |
| Fixed daily quantity | `n × quantity_per_gas_day × number_of_contract_gas_days` |
| Constant flow | `n × flow_rate × sum(actual_contract_delivery_hours)` |

The formulas are dimensional descriptions. They must use the product's documented convention, including fixed-day exceptions. A month with 31 days does not make a fixed 10,000-MMBtu contract into 310,000 MMBtu. Equally, a daily-quantity contract cannot be treated as one day's quantity for the entire month.

A gas-day label and its physical interval are distinct. Store or reference its local start time, time-zone/DST convention, and start/end timestamps. In a flow contract, a clock change can alter the monetary multiplier; in a fixed-daily-quantity contract it need not. Keep minimum executable lots separate from the size of one contractual lot.

Delivery quantity and cash-index weighting are independent. An equal energy allocation to every gas day does not establish that the price publisher weights every publication equally. A publication can apply to several delivery days; the reference schedule needs a mapping between publication date, covered delivery dates, applicable price and weight. Missing expected data must invoke the contract's fallback or an explicit failure, rather than silently shorten the average.

### Price-reference identity and observation state

The reference definition needs publisher/exchange, location or market area, index/assessment identifier, statistic, currency and denominator, price type, observation date/time, delivery period, and underlying-contract selection. A monthly index fixed near the start of M and an average of daily prices for M remain different even though both are described as M's gas price.

Preserve at least four period concepts: listed contract period, physical delivery period, assessment publication window and the delivery/shipping period described by those assessments. The last trading date can precede most of the fixings. An expired contract may therefore still contain unknown observations and unpaid settlement obligations.

The component list must accommodate a directly published basis, calculated signed differences, fixed weighted baskets, and products of gas and FX observations. A component's observed/future split belongs to valuation state; it must not rewrite the original observation schedule.

### Operation order, units and currency

`average(gas × FX)` and `average(gas) × average(FX)` are different contracts. Converting each observation, converting a final average, applying a last-available FX fixing, and using an already published converted index are separate rules. Conversion factors and intermediate rounding must be retained in the order prescribed.

Energy-unit conversion can use fixed definitions once the unit convention is identified. Converting standard gas volume to energy additionally requires heating value and the relevant standard conditions; converting NGL mass to liquid volume requires density or an explicit contractual coefficient. Gross/net calorific value, pressure, temperature and dry/wet measurement basis are not interchangeable. The existing [unit-conversions scope](../library/globals/unit-conversions.md) does not supply these product-specific assumptions.

A universal positive-price constraint would fail: EEX EGSI rules expressly permit negative final settlements, and its physical gas rules specify seller payment when the purchase price is negative. [EEX specifications, D.2.3](https://www.eex.com/fileadmin/EEX/Downloads/Rules/Contract_Specifications/20260723_EEX_Contract_Spezifications_0104a_E_FINAL.pdf)

### Physical delivery and lifecycle

Pipeline-gas terms need the virtual point or pipeline location, applicable network quality/tariff version, delivery rate/profile, nominations, balancing/shipper requirements, quantity tolerances, transfer method, invoice price and payment schedule. NGL terms need the product/facility specification, title-transfer or loading method, standard-temperature measurement and physical payment obligations. An LNG assessment's delivery basis describes the referenced market; it does not by itself create a cargo obligation for a cash future.

A delivery EFP, cascading, an execution strip and an optional alternative delivery arrangement are different lifecycle mechanisms. Their resulting contracts, positions and payments should be explicit. They cannot all be represented by switching a cash/physical flag at expiry.

Daily variation settlement remains separate from final cash settlement and physical invoicing, as in the petroleum survey. Initial margin is a collateral requirement rather than a traded commodity quantity. Current margin rates and position limits belong in effective-dated operational reference data if supported, not in the fundamental payoff definition.

### The meaning of linear

Fixed-quantity daily gas futures and fixed-coefficient basis/basket formulas can belong to a linear family. A name containing “swing” is not sufficient evidence of a volume option. Conversely, a supply contract that actually lets a party choose quantities subject to minimum/maximum or cumulative constraints cannot be priced as an unconditional fixed profile. Storage and transport optimization are also separate economic rights.

A currency-translated gas payoff is linear in the quoted futures price but can be bilinear in gas and FX risk factors. The representation can describe those terms without prescribing a pricing model. Optional physical choices, unknown volume weights and fixed weights must not be conflated.

### Candidate information blocks

| Block | Additions exposed by this survey |
|---|---|
| Trade occurrence | Referenced contract instance, side, lots and execution-price terms; preserve occurrence identity. |
| Contract quantity | Fixed-total/daily/flow basis, quantity unit, profile, lot and executable-size conventions, resolved total quantity and quote multiplier. |
| Economic schedules | Gas-day definition, delivery interval, observation-to-delivery mapping, reference periods, independent calendars, payment and nomination dates. |
| Price definition | Bidweek/month-ahead versus daily versus futures-expiry reference, component coefficients, weights, FX/conversion order, rounding and fallbacks. |
| Settlement obligations | Physical network/title-transfer terms, cash schedules, prescribed EFP or cascade rules and destination contract definitions. |
| State | Fixings, resolved execution price, settled variation, unpaid cash, delivered quantities, remaining delivery obligation and generated child positions. |
| Provenance | Applicable product identifiers, rule version/effective dates, relevant index methodology and any unresolved source discrepancy. |

As in the petroleum review, [Principle 7](../../PRINCIPLES.md) points to a small trade record referencing complete economic facts, with pricing inputs, forecasting models and computation kept separate. Explicit schedules can be prepared before pricing without requiring the existing date-only library slice to start guessing market calendars.

## Coverage cases and unresolved evidence

The following are useful **future acceptance cases**, once a trade representation is proposed. They are research examples, not tests added to the library:

| Case | What it should demonstrate |
|---|---|
| Fixed monthly Henry Hub versus TTF versus PEG/PSV | Fixed energy, actual-hour flow and fixed-daily energy resolve different quantities. |
| TTF across a clock change | Gas-day boundaries resolve correctly; changing hour count changes flow-contract quantity. |
| Waha Index after last trade but before month end | The position is no longer tradable, yet still has unfixed daily prices and unpaid settlement. |
| AB NIT 7a/5a | Formula sign follows operative terms, not the order of names. |
| HH weekly straddling monthly expiry | Maturity selector uses second nearby for the whole week. |
| JKM monthly versus BALMO | Delivery-month identity survives an offset or transaction-dependent publication window. |
| TTF USD and NWE Spark | Per-day gas/FX conversion precedes averaging; Spark basis is added on its specified schedule. |
| Ethane BALMO | Shorter price window does not reduce the fixed contract lot. |
| NGL basket and propane/Brent PRR | Weighted components, intermediate rounding and mismatched lot/quote units remain explicit. |
| EEX year/season cascade | Parent exposure terminates and shorter contract positions are created without double counting. |
| ASX Wallumbilla expiry | An obligatory delivery EFP creates the specified downstream physical contract. |
| Physical NG and NGL invoices | Variation settlement, delivered quantities, tolerances and physical payment are distinct. |

Material evidence gaps and source conflicts:

- **CME Micro NG:** chapter 440's wording refers to corresponding NG “final settlement price,” while CME's educational explanation describes daily settlement and an expiry one day before NG. Confirm the precise observation in clearing procedures before mapping MNG to either the last-day or penultimate family. [Rule](https://www.cmegroup.com/rulebook/NYMEX/4/440.pdf), [CME explanation](https://www.cmegroup.com/education/courses/understanding-micro-futures-contracts-at-cme-group/micro-crude-futures/micro-henry-hub-natural-gas-futures-product-overview)
- **ICE UKD:** the webpage prints a numeric 0.0001 tick, but its prose and governing Section ZZZZZZ.4 indicate 0.001. The report uses the rulebook value with this discrepancy retained. [Governing rule](https://www.ice.com/publicdocs/contractregs/177_Section_ZZZZZZ.pdf)
- **ICE GCL:** the short description says average while the operative reference specifies a single premonth date. **ICE NGB:** the short reference field names TET natural gasoline while the detailed formula defines the five-component Non-TET basket, corroborated by OPIS. Do not onboard either by selecting whichever label is easiest to parse. Sources are attached to their table rows.
- **Physical European gas:** final physical-invoice payment lags were not established for every ICE product. NBP's gas-day time-zone normalization also remains unresolved. Nomination deadlines and variation-settlement payment language are insufficient substitutes. IFUS TLD's detailed conversion and payment rules also require confirmation.
- **DCE LPG PG:** accessible official contract terms were not recovered after searches and direct retrieval attempts. This is a significant unverified extension for an inclusive global NGL universe; secondary reproductions have not been promoted to verified specifications.
- **SGX LPG/NGL futures, standalone North American gas BALMO and dedicated fractionation/ethane–gas spread futures:** a current specification was not established. This is an inventory gap, not a claim these products do not exist. A tradable strip, broker package or margin offset does not establish a standalone future.
- **ICE NGX/OTC boundary:** cleared physical gas needs its own agreement-level review. ICE's Henry Physical Basis LD1 page is explicitly an **OTC** product, with 100 MMBtu per lot **per day**; it is not evidence that ICE Henry cash futures have daily-sized monthly lots. [OTC specification](https://www.ice.com/products/1188)
- **Historical listings:** ICE JKM Half-Month JKH was explicitly deleted effective 19 September 2022; CME JKF/JKB supply the documented half-month examples here. Historic NYMEX regional-gas chapter numbers have also been reused: chapter 509 now covers HH Weekly. Current applicable rules outrank old launch notices. [ICE deletion](https://www.ice.com/publicdocs/contractregs/86_SECTION_TTT_Part_II_E.pdf), [NYMEX catalogue](https://www.cmegroup.com/rulebook/NYMEX/)
- **Operational completion:** incorporated tariffs, publisher correction/fallback provisions, exact trade-type ticks, date-specific listing calendars and physical facility identities still need product-by-product onboarding. Rulebook presence alone does not establish active liquidity. MCX already publishes separate 2026 and 2027 contract terms, reinforcing the need to select rules by applicable series. [MCX natural gas catalogue](https://www.mcxindia.com/products/energy/natural-gas)

No constructor, pricing implementation, repository principle or existing library decision was changed by this research.
