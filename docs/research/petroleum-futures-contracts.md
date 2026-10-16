# Petroleum futures: contract terms for a general trade representation

Research reviewed 14 September 2026. This is an evidence note for discussion, not an approved constructor specification or an implementation decision.

The main finding is that the commodity taxonomy and the contract taxonomy are different. Crude, gasoline, diesel, jet, fuel oil and LPG all recur as outright prices, averages, differentials and physically delivered contracts. A useful futures representation needs to describe the price definition and settlement obligations independently of the commodity name.

## Scope and how to read the evidence

The survey covers CME Group's NYMEX contracts, ICE Futures Europe and U.S., ICE Futures Abu Dhabi, Gulf Mercantile Exchange, SGX, INE, SHFE and TOCOM. DCE LPG is retained as an unresolved coverage item. NYMEX is part of CME Group; the execution platform, listing exchange and clearing house are separate identities. The examples are selected for differences in economic terms. Presence in a current product guide or rulebook is evidence of documented terms, not proof of current liquidity or availability of every maturity.

Petroleum scope includes crude grades and locations; gasoline and blendstocks; gasoil, diesel, heating oil and jet; residual and marine fuels; naphtha; LPG and other natural gas liquids; and bitumen. Biofuel blending substitutes are included at the boundary. Freight, emissions certificates, agricultural feedstocks and polymer futures deserve separate reviews even where they appear in the same exchange energy catalogue. This scope does not turn them into petroleum delivery obligations.

Sources are official exchange product specifications, rulebooks and settlement documents. Specific discrepancies are recorded below instead of being silently resolved. Dates, quality schedules and publisher methodologies must be tied to the applicable rule version before production use. A historical footer is not by itself evidence that the chapter is obsolete, and a recent crawl date is not a rule effective date.

## The contract groups

| Group | What distinguishes it | Examples to represent |
|---|---|---|
| Physical benchmark | Delivery against a quality, location and procedural specification | WTI, RBOB, NY Harbor ULSD, ICE gasoil, Oman, Murban |
| Delivery with an election | More than one prescribed settlement route | ICE Brent's EFP delivery and cash election |
| Cash to one observation | A final futures settlement, index, marker or monthly posted price | Micro WTI, Brent last-day/penultimate, Saudi propane contract price |
| Average of an outright price | Several observations contribute to one final price | WTI/Brent first-line, Singapore product assessments |
| Basis or other differential | An ordered subtraction of defined references | Crude location/quality basis, jet versus ULSD, regional product spreads |
| Crack or converted spread | Price references use different commodity units or fixed conversion factors | Gasoil/Brent, fuel oil/Brent, naphtha/Brent |
| Short or irregular pricing window | Daily, weekly, selected-start BALMO, or industry trade month | Dated Brent weekly CFD, naphtha BALMO, Canadian crude trade month |
| Local currency or tax treatment | Settlement references include FX or special tax conventions | TOCOM Dubai, bonded Chinese oil contracts, EIA flat-tax fuels |

These groups overlap: a cash-settled crack can use a balance-of-month window, separate publication calendars and a fixed tonne-to-barrel factor. They are review groups, not proposed subclasses. Product evidence follows.

## Contract evidence

### U.S. and European physical benchmarks

In the tables, `M` means the named delivery/contract month, `bbl` a U.S. petroleum barrel, `gal` a U.S. liquid gallon and `t` a metric tonne. Price increments are trading ticks unless otherwise stated.

| Contract | Lot; quote; increment | Settlement, dates and delivery terms |
|---|---|---|
| NYMEX WTI, CL | 1,000 bbl; USD/bbl; $0.01 | Physical FOB Cushing. Normal expiry is three business days before the preceding month's 25th, or three business days before the business day preceding a non-business 25th. Later calendar changes preserve listed expiry unless that date becomes a holiday, when it moves to the preceding business day. Delivery is during M. Qualifying domestic streams have specified quality tests, including sulphur ≤0.42% and API gravity 37–42. Volume is at 60°F. The ±2% tolerance applies only to eligible transfer modes. Normal payment date is the following month's 20th, with banking-day adjustments. [Chapter 200](https://www.cmegroup.com/content/dam/cmegroup/rulebook/NYMEX/2/200.pdf) |
| NYMEX RBOB gasoline, RB | 42,000 gal; USD/gal; $0.0001 | Physical NY Harbor blendstock for subsequent ethanol blending. Expiry last business day before M; delivery starts after M's fifth business day and completes by its last business day. Quality is seasonal; September itself has two volatility regimes tied to nominations. Eligible marine, pipeline and transfer methods have their own conditions/tolerances. [Chapter 191](https://www.cmegroup.com/rulebook/NYMEX/1a/191.pdf) |
| NYMEX NY Harbor ULSD, HO | 42,000 gal; USD/gal; $0.0001 | Physical on-road ULSD, explicitly excluding biodiesel/renewable diesel in the chapter. Expiry and delivery window follow the RB pattern. Mode-dependent quantity tolerances and 60°F measurement apply. Payment is normally noon on the business day after receipt or noon on M's last business day, whichever is earlier; multiple deliveries can create multiple payments. [Chapter 150](https://www.cmegroup.com/rulebook/NYMEX/1a/150.pdf) |
| ICE Brent, B | 1,000 bbl; USD/bbl; $0.01 | EFP-deliverable, with an option to cash settle against the ICE Brent Index for the last trading day, published the next trading day. EFP means exchange of futures for a related physical position. Expiry is the last business day of M−2 with year-end exceptions. Preserve the election route; a simple mandatory-physical flag is insufficient. [Specification](https://www.ice.com/products/219/Brent-Crude-Futures) |
| ICE Low Sulphur Gasoil, G | 100 t; USD/t; $0.25 | Physical ARA region, including eligible Flushing/Ghent facilities. Delivery quantity is **118.35 m³ per lot** under the specified density convention. Delivery is 16th–month-end. Seller nominates installation; buyer nominates day within an agreed five-day range. Expiry is noon London, two business days before the 14th. Summer/winter quality regimes differ. [Specification](https://www.ice.com/products/34361119/Low-Sulphur-Gasoil-FuturesIGAC) |

For physical gasoil, quality, eligible origins, charges and alternative delivery arrangements live in the detailed delivery rules, not merely the product title. An agreed alternative delivery procedure can release the cleared contract into an agreed delivery arrangement. [ICE Section J1](https://www.ice.com/publicdocs/contractregs/15_SECTION_J1.pdf)

### Cash outright, basis and crack futures

| Contract | Lot and quote | Final price and timing that distinguish it |
|---|---|---|
| NYMEX Micro WTI, MCL | 100 bbl; USD/bbl | Cash to the corresponding CL **daily settlement on MCL's expiry**, one business day before CL expires. It does not wait for CL's later final expiry price. [Chapter 309](https://www.cmegroup.com/rulebook/NYMEX/3/309.pdf), [CME expiry explanation](https://www.cmegroup.com/education/courses/understanding-micro-futures-contracts-at-cme-group/micro-crude-futures/managing-expiration-of-the-micro-wti-crude-oil-futures-contract) |
| NYMEX E-mini crude | 500 bbl; USD/bbl | Cash against CL on its own expiry, one business day before CL. Trade increment $0.025; settlement increment $0.001. [Chapter 401](https://www.cmegroup.com/rulebook/NYMEX/4/401.pdf) |
| NYMEX E-mini RBOB; Micro RBOB/ULSD | E-mini RB 21,000 gal; micros 4,200 gal; USD/gal | Cash against corresponding standard contract on the smaller future's expiry. E-mini RB expires second-last business day before M, with $0.001 trade/$0.0001 settlement increments. Micros expire one business day before their standards. [E-mini RB](https://www.cmegroup.com/rulebook/NYMEX/4/403.pdf), [Micro RB](https://www.cmegroup.com/rulebook/NYMEX/4/435.pdf), [Micro ULSD](https://www.cmegroup.com/rulebook/NYMEX/4/434.pdf) |
| ICE WTI, T | 1,000 bbl; USD/bbl | Cash against the NYMEX WTI penultimate settlement. Expiry four U.S. business days before M−1's 25th, adjusted if the 25th is not a business day. This differs from physically delivered NYMEX CL. [Specification](https://www.ice.com/products/213/WTI-Crude-Futures) |
| NYMEX Crude Oil Bullet; Crude Oil Last Day Financial | 1,000 bbl; USD/bbl | Bullet observes CL one business day before CL expiry; last-day observes its final settlement. Identical barrel exposure does not make their expiry observations identical. [Bullet](https://www.cmegroup.com/rulebook/NYMEX/6/691.pdf), [last-day](https://www.cmegroup.com/rulebook/NYMEX/8/828.pdf) |
| NYMEX Brent Penultimate / Brent Last Day Financial | Chapters specify 1,000 bbl; USD/bbl; multiplier text needs reconciliation | Penultimate references the ICE Brent futures settlement before expiry; last-day references the ICE Brent Index published after final trading. Index versus futures settlement is a material distinction. [Chapter 692](https://www.cmegroup.com/rulebook/NYMEX/6/692.pdf), [Chapter 698](https://www.cmegroup.com/rulebook/NYMEX/6/698.pdf) |
| ICE Brent 1st Line, I | 1,000 bbl; USD/bbl | Cash monthly average of front-month Brent daily settlements, switching to the next contract **on the underlying's expiry date**. Trades through month-end trading day; final payment +2 clearing-house business days. [Specification](https://www.ice.com/products/6753532/Brent-1st-Line-Future), [TTT Part II A, item 1](https://www.ice.com/publicdocs/contractregs/82_SECTION_TTT_Part_II_A.pdf) |
| NYMEX WTI Financial | 1,000 bbl; USD/bbl | Chapter 510 allows monthly, quarterly, semiannual and annual averaging periods ending in the contract month. The stated contract quantity remains 1,000 barrels for each period type. The longer period does not by itself multiply lot quantity by its month count. [Chapter 510](https://www.cmegroup.com/rulebook/NYMEX/5/510.pdf) |
| NYMEX Group Three Sub-octane Gasoline | 42,000 gal; USD/gal | Cash month-average of the specified Platts regional gasoline assessment. Its versus-RBOB counterpart uses common publication days and rounds daily assessment means before averaging. Both expire on the last business day of the contract month. [Outright](https://www.cmegroup.com/rulebook/NYMEX/3/322.pdf), [basis](https://www.cmegroup.com/rulebook/NYMEX/3/323.pdf) |
| NYMEX NY Jet Fuel versus NY Harbor ULSD | 42,000 gal; USD/gal | Monthly average of Platts NY jet barge midpoint minus nearby HO, using joint pricing days. Daily midpoint is rounded to a thousandth of a cent before averaging. Last-business-day expiry. [Chapter 413](https://www.cmegroup.com/rulebook/NYMEX/4/413.pdf) |
| NYMEX Gulf Coast Jet Up-Down; Gulf Coast ULSD Up-Down BALMO | 42,000 gal; USD/gal | Jet is a monthly USGC pipeline jet-minus-HO basis. ULSD BALMO averages the corresponding pipeline basis from selected start through month-end. Both use joint pricing days. Here “Up-Down” is a price differential, not a binary payoff. [Jet](https://www.cmegroup.com/rulebook/NYMEX/6/608.pdf), [ULSD BALMO](https://www.cmegroup.com/rulebook/NYMEX/3/338.pdf) |
| NYMEX WTI Houston versus WTI Trade Month | 1,000 bbl; USD/bbl | Uses Argus's published first-month Houston differential weighted-average price. Window: first business day after M−2's 25th to last business day on/before M−1's 25th; trading ends then. The published differential is itself an observable, not necessarily a subtraction to reconstruct. [Chapter 319](https://www.cmegroup.com/rulebook/NYMEX/3/319.pdf) |
| NYMEX WCS Hardisty EMDA Monthly | 1,000 bbl; USD/bbl | CAMI volume-weighted differential versus CL calendar-month average. Window starts first Canadian business day of M−1 and ends the Canadian business day before Enbridge's Notice of Shipments date; trading ends then. [Chapter 638](https://www.cmegroup.com/rulebook/NYMEX/6/638.pdf) |
| NYMEX Houston versus Brent Cross-Month | 1,000 bbl; USD/bbl | Houston first-month Argus index average minus ICE Brent average for **M+2**, using its specified industry trade-month window. [Chapter 1232](https://www.cmegroup.com/rulebook/NYMEX/12/1232.pdf) |
| NYMEX Houston versus Dubai Trade Month | 1,000 bbl; USD/bbl | Argus Houston minus Platts Dubai using non-common pricing: each leg has its own publication days and average. [Chapter 1309](https://www.cmegroup.com/rulebook/NYMEX/13/1309.pdf) |
| ICE Dated Brent versus Brent 1st Line, DBF | 1,000 bbl; USD/bbl | Platts Dated Brent midpoint average minus Brent first-line average; common pricing. Month-end expiry; payment +2 clearing-house business days. [Specification](https://www.ice.com/products/6753361/Crude-Diff-Dated-Brent-vs-Brent-1st-Line-Future) |
| ICE Singapore 380 CST fuel oil, SYS | 1,000 t; USD/t | Cash month-average of specified Platts Singapore HSFO midpoints, on publication days. Month-end expiry; payment +2 clearing-house business days. [Specification](https://www.ice.com/products/6753551/Fuel-Oil-380-CST-Singapore-Future) |
| ICE Singapore Mogas 92, SMT | 1,000 bbl; USD/bbl | Cash month-average of Platts FOB Singapore gasoline midpoints, using Singapore business days. Month-end expiry; specified payment lag **one business day**. [Specification](https://www.ice.com/products/5029394/Gasoline-Singapore-Mogas-92-Unleaded-Platts-Future) |
| ICE Argus Eurobob Oxy FOB Rotterdam barges, AEO | 1,000 t; USD/t | Monthly cash Argus midpoint average on publisher days. Month-end expiry; payment +2 clearing-house business days. [Specification](https://www.ice.com/products/6753470/Argus-Eurobob-Oxy-FOB-Rotterdam-Barges-Future) |
| ICE Jet CIF NWE cargoes, JCN; jet versus gasoil, ULJ | 1,000 t; USD/t | Outright is a Platts monthly jet midpoint average, with +2 clearing-house-business-day payment. Differential subtracts rolling gasoil using **non-common pricing** and a stated **one-business-day** payment lag. [Outright](https://www.ice.com/products/6753534/Jet-CIF-NWE-Cargoes-Future), [differential](https://www.ice.com/products/6753447/Jet-Fuel-Diff-Jet-CIF-NWE-Cargoes-vs-Low-Sulphur-Gasoil-1st-Line-Future) |

The following formulas are dimensional translations of the contract specifications. `avg` must retain the contract's own dates, roll rule and rounding; it does not mean a generic average over all weekdays.

| Crack or converted spread | Lot / quote / settlement expression | Required distinction |
|---|---|---|
| ICE gasoil/Brent crack in barrels, ULD | 1,000 bbl; USD/bbl; `avg(gasoil USD/t)/7.45 − avg(Brent USD/bbl)` | Fixed 7.45 bbl/t; each reference rolls on its own expiry. [Specification](https://www.ice.com/products/6753331/Gasoil-Crack-Low-Sulphur-Gasoil-1st-Line-vs-Brent-1st-Line-Future-in-Bbls) |
| ICE Singapore 380/Brent crack, SPS | **1,000 t = 6,350 bbl**; USD/bbl; `avg(fuel oil USD/t)/6.35 − avg(Brent USD/bbl)` | Nominal lot unit differs from quote unit. A $1/bbl change corresponds to $6,350 per lot before cash-rounding rules, not $1,000. [Specification](https://www.ice.com/products/6753328/Fuel-Oil-Crack-Fuel-Oil-380-CST-Singapore-vs-Brent-1st-Line-Future) |
| ICE Japan naphtha/Brent crack, NBG | 1,000 bbl; USD/bbl; `avg(naphtha USD/t)/8.90 − avg(Brent USD/bbl)` | Fixed 8.90 bbl/t and non-common publication calendars. [Specification](https://www.ice.com/products/65898862/Naphtha-Crack-Naphtha-C-F-Japan-Platts-vs-Brent-1st-Line-Future-in-Bbls) |
| ICE Heating Oil/Gasoil arb, ULM | 1,000 bbl = 42,000 gal; **USD/gal**; `avg(HO USD/gal) − avg(gasoil USD/t)/312.9` | Fixed 312.9 gal/t. “In Bbls” in the name does not identify the quote denominator. [Specification](https://www.ice.com/products/6753449/Heating-Oil-Arb-Heating-Oil-1st-Line-vs-Low-Sulphur-Gasoil-1st-Line-Future-in-Bbls) |
| NYMEX Gasoil Crack Spread (1000mt) | 7,450 bbl / 1,000 t; USD/bbl; 7.45 conversion | Non-common pricing, daily rounding of converted gasoil and explicit Brent expiry-day roll. This is a different lot size from ICE ULD. [Chapter 143](https://www.cmegroup.com/rulebook/NYMEX/1a/143.pdf) |

A cash differential future is one listed contract. An exchange spread strategy can instead generate several underlying positions: ICE explicitly says its Brent/WTI futures spread produces two positions with separate expiries. Likewise, trade-at-settlement/marker describes execution-price formation, which can initially be a reference plus an offset; it does not define a new terminal payoff. [ICE spread](https://www.ice.com/products/1242/Brent-WTI-Futures-Spread), [CME trade-at-marker](https://www.cmegroup.com/articles/2024/energy-trading-at-marker-frequently-asked-questions.html)

Short-period instruments need special attention. ICE's weekly Dated/BFOE CFD is documented as a 1,000-barrel execution package comprising five 200-barrel daily contracts, whereas NYMEX chapter 1145 specifies its own 1,000-barrel weekly contract. ICE retains the basis month from the first pricing day, includes special holiday handling, and excludes cross-month weeks. Its payment timeline needs clarification before implementation, as recorded below. [ICE weekly CFD](https://www.ice.com/products/6753348/Weekly-CFD-Dated-Brent-Platts-vs-First-Month-BFOE-Platts-Future)

### Other venues and currencies

| Venue / contract | Lot; quote; increment | Settlement and additional contractual dimensions |
|---|---|---|
| Gulf Mercantile Exchange Oman, OQD / clearing OQ | 1,000 bbl; USD/bbl; $0.01 | Physical FOB Oman; expiry last trading day of M−2. Permitted loading includes Mina Al Fahal and floating storage in Omani waters. Tolerance is ±0.2% at terminal or ±0.5% for floating storage. Volume is temperature-corrected to 60°F; quality follows normal export quality at loading place/time. [Summary](https://www.gulfmerc.com/gme-product-services/gme-contracts-contract-summary-oqd), [Chapter 10, March 2025](https://d2744r28dxz36a.cloudfront.net/Rulebook/GME%20Rulebook%20-%20Chapter%2010%20%2807%20March%202025%29.pdf) |
| ICE Futures Abu Dhabi Murban, ADM | 1,000 bbl; USD/bbl; $0.01 | Physical FOB ADNOC Fujairah into buyer's vessel. Expires 16:30 Singapore on last trading day of M−2, with year-end exception. Delivery price is the expiry Singapore marker, distinct from ordinary daily settlement. ±0.2% loading tolerance. The contract has no minimum delivery quantity, but terminal loading minimum is **200,000 bbl**, with co-loading permitted. [Specification](https://www.ice.com/products/75443578/Murban-Crude-Oil-Futures/) |
| INE crude, SC | 1,000 bbl; RMB/bbl excluding tax/duty; RMB0.1 | Physical designated-storage delivery. Expiry last trading day of M−1, subject to announced holiday adjustments; five trading days for delivery. Medium-sour benchmark quality; actual eligible grades and premiums/discounts are separately prescribed. [Contract](https://www.ine.cn/eng/market/futures/energy/sc/contract/index.html), [appendices](https://www.ine.cn/eng/market/futures/energy/sc/appendixes/) |
| INE low-sulphur fuel oil, LU | 10 t; RMB/t excluding tax/duty; RMB1 | Physical bonded warehouse/factory delivery. Expiry last trading day of M−1; next five trading days for delivery. Restated 2026 quality specifies ≤0.50% sulphur and detailed viscosity/density/test limits. [Amendment](https://www.ine.com.cn/eng/circularnews/circular/202506/t20250627_828185.html), [restated contract](https://www.ine.com.cn/eng/circularnews/circular/202506/W020250627601943483859.docx) |
| SHFE fuel oil, FU | 10 t; tax-exclusive RMB/t; RMB1 | Bonded physical RMG380 fuel oil. Current product identity and lot verified. The retrieved 2024 rules give M−1 last-trading-day expiry, two-business-day delivery and last-five-traded-day average settlement benchmark; a 2026 rules revision still needs checking for these timing details. [Product](https://www.shfe.com.cn/eng/Market/Futures/Energy/fu_f/), [retrieved 2024 rules](https://tsite.shfe.com.cn/eng/services/rules/shfe/911404890.html) |
| SHFE bitumen, BU | 10 t; RMB/t; RMB1 | Physical duty-paid registered #70 Class-A road bitumen. Expiry M's 15th with holiday/announced adjustments; two following business days for delivery. Invoice benchmark averages last five traded days' settlement prices. ±3% quantity tolerance; factory loading at 130–160°C. [January 2026 rules](https://www.shfe.com.cn/eng/services/Rules/SHFERules/202512/t20251231_829981.html) |
| SGX Platts Gasoil FOB Singapore Index, GOF; Naphtha CFR Japan Index, NJF | GOF 1,000 bbl, USD/bbl; NJF 100 t, USD/t; $0.01 | Cash monthly arithmetic averages of specified Platts spot assessments, rounded to three decimals. Expiry is the relevant month's last index-publication day, described as last Singapore business day. The similarly named naphtha swap has a different 1,000-t lot. [SGX specifications](https://www.sgx.com/derivatives/products/oil?cc=GOF) |
| TOCOM Platts Dubai crude | 50 kL; JPY/kL; JPY10 | Cash: monthly average of S&P Dubai nearest-shipment-month prices converted using a separate monthly MUFG FX average, then converted to kL and rounded to JPY10. FX uses bank business days. Expiry final business day of M; payment next business day. [Specification](https://www.jpx.co.jp/english/derivatives/products/energy/platts-dubai-futures/01.html), [April 2026 outline, pp.18–19](https://www.jpx.co.jp/english/derivatives/rules/outline/dreu250000001ove-att/EN_Outline_20260413.pdf) |
| TOCOM kerosene | 50-kL trading lot; **100-kL delivery unit**; JPY/kL; JPY10 | Physical JIS Grade 1, domestic/customs-cleared kerosene delivered into barges at eligible Tokyo/Kanagawa/Chiba marine facilities. Expiry day session on M−1's 25th under the exchange calendar. Delivery through M; seller chooses point and buyer generally chooses day. Delivery price is expiry day-session VWAP. [Specification](https://www.jpx.co.jp/english/derivatives/products/energy/kerosene-futures/01.html) |

GME's expiry marker is unusually instructive: the expiring month's marker uses the second-nearby marker plus a signed adjustment derived from the first/second-month spread over marker windows on the preceding three trading days. The procedure includes no-trade fallback rules. Consequently, even the delivery invoice benchmark can be a derived marker rather than the expiring contract's own closing trade. [GME settlement procedure](https://www.gulfmerc.com/gme-product-services/gme-trading-settlements), [2025 member notice](https://d2744r28dxz36a.cloudfront.net/MemberNotices/2025/25-021.pdf)

INE LU further distinguishes a 10-t futures lot from operational minimums: current delivery rules describe 5,000-t warehouse load-in and generally 1,000-t load-out/factory take-delivery. They also specify warrant validity and expiry. Their English final-price wording needs reconciliation, as recorded below. [2026 delivery rules, Articles 161–175](https://www.shfe.cn/eng/services/Rules/INERules/202606/t20260626_832299.html)

### Additional petroleum and blending cases

| Contract | Contract terms that add coverage | Implication |
|---|---|---|
| NYMEX Mont Belvieu Physical Non-TET Propane (OPIS), chapter 364 | 42,000 U.S. gallons; USD/gallon; physical in-well or agreed book transfer at the Enterprise facility, with permitted mutually agreed alternatives. Volume is measured at 60°F and no volume tolerance is permitted. Trading ends on the second-last business day of the expiring month; delivery is the last business day. The OPIS price on the last trade date determines the delivery basis. Payment is due by noon on the fifth business day after delivery. [Rules](https://www.cmegroup.com/rulebook/NYMEX/3/364.pdf) | Physical need not mean loading a ship or moving inventory. Title-transfer method, measurement conditions and invoice timing matter. |
| NYMEX Mini Argus Propane (Saudi Aramco), chapter 851 | 100 metric tonnes; USD/tonne; cash to Argus's final Saudi Aramco propane contract-price assessment for the contract month. Trading ends on the last business day of the preceding month, using the UK holiday calendar. [Rules](https://www.cmegroup.com/rulebook/NYMEX/8/851.pdf) | A monthly reference price can be one posted assessment, rather than an average of daily observations. |
| NYMEX Japan C&F Naphtha (Platts) BALMO, chapter 308 | 1,000 metric tonnes; USD/tonne; cash to the arithmetic average of the Platts high/low quotations from the selected start date to month-end. Trading ends on the last business day of the contract month. [Rules](https://www.cmegroup.com/rulebook/NYMEX/3/308.pdf) | The selected start is an economic term. A BALMO is not a full-month contract whose elapsed observations are simply deleted at valuation. |
| NYMEX FAME 0 Biodiesel FOB Rotterdam (Argus), RED compliant, chapter 1147 | 100 metric tonnes; USD/tonne; monthly cash average of Argus bid/ask midpoints on publication days; last business day expiry. [Rules](https://www.cmegroup.com/rulebook/NYMEX/11/1147.pdf) | Sustainability classification and delivered-price basis distinguish the reference assessment. |
| NYMEX HVO FOB ARA Range Class II (Argus), chapter 750 | 100 metric tonnes; USD/tonne; monthly cash average of the specified Argus HVO Class II assessment; last business day expiry. [Rules](https://www.cmegroup.com/rulebook/NYMEX/7/750.pdf) | Renewable diesel is a further reference definition within the same averaging structure. |
| NYMEX EIA Flat Tax On-Highway Diesel, chapter 301 | 42,000 gallons; USD/gallon; cash to a monthly arithmetic average of weekly U.S. retail diesel observations. Tax adjustment refers to rates at 1 March 2009; the chapter also defines tax-event resets and an alternative-source mechanism for missing weekly publication. [Rules](https://www.cmegroup.com/rulebook/NYMEX/3/301.pdf) | Observation frequency need not be daily, and disruption/fallback and tax adjustments are contract terms. Current tradability was not separately established. |
| NYMEX EIA Flat Tax U.S. Retail Gasoline, chapter 313 | Also 42,000 gallons and USD/gallon, averaging weekly observations; its tax baseline is 1 January 2010. [Rules](https://www.cmegroup.com/rulebook/NYMEX/3/313.pdf) | Closely named products can carry different adjustment baselines. Current tradability was not separately established. |

The current NYMEX catalogue also documents ethane, normal and isobutane, natural gasoline, MTBE, Eurobob gasoline, gasoline octane spreads, multiple fuel-oil sulphur/viscosity grades, UCO, UCOME, RME and biofuel-versus-gasoil contracts. These extend the product inventory; each still needs its own reference and terms verification. [NYMEX rulebook catalogue](https://www.cmegroup.com/rulebook/NYMEX/)

## Details that change the economic representation

### 1. Final settlement method and price definition are independent

A physical future can use an external assessed price for the delivery invoice, as the Mont Belvieu example shows. A cash future can reference another physically delivered future. Cash settlement therefore does not imply spot-price settlement, and physical settlement does not identify a unique final-price algorithm.

Daily mark-to-market is a separate matter again. CME describes futures settlement variation as cash banked each day, calculated from new trades and existing positions; there are also intraday clearing cycles. The final expiry price must not be confused with the daily settlement series or the schedule on which variation is paid. [CME money calculations](https://www.cmegroup.com/clearing/files/CME-Money-Calculations-Futures-and-Options.pdf), [clearing cycles](https://www.cmegroup.com/notices/clearing/2023/12/Chadv23-374.pdf)

Design inference: keep final price, final settlement route, variation schedule and physical invoice obligations distinguishable. A price-to-entry P&L is not automatically the current unpaid value after variation has been settled. Model and funding choices belong in pricing machinery, consistent with the repository's contracts-as-data principle.

### 2. A reference needs more identity than a curve name

At minimum, the evidence points to publisher/exchange, precise assessment or product, price type, location, grade, delivery basis, currency/unit and applicable reference period. A named futures reference also needs a contract-month selection rule.

The ICE Brent Singapore Marker first-line future uses observations at 16:30 Singapore prevailing time. A separately documented penultimate-day variant explicitly selects the following underlying month on the expiring front month's expiry day. Both use 1,000-barrel lots and USD/barrel quotes. A generic label such as `Brent front month` loses this distinction. [Singapore Marker](https://www.ice.com/products/81987202/Crude-Outright-Brent-Singapore-Marker-1st-Line-Future), [penultimate-day variant](https://www.ice.com/products/82908539/Brent-Singapore-Marker-Penultimate-Day-1st-Line-Future)

Design inference: contract-defined reference selection belongs with the instrument facts. Mapping those facts onto a market-data curve or forecasting model belongs elsewhere. Publication timestamps and time zones matter when deciding whether an observation is already known.

### 3. Averages require observation and calendar rules

For a fixed weighted linear price definition, a useful mathematical description is:

`settlement_price = constant + sum(component_coefficient * component_average)`

Each component average has explicit observation dates, weights, raw-price transformation and reference selection. This is a description of economic terms, not a proposal to store executable pricing code in a trade. Multiplicative FX and physical delivery choices require additional treatment.

The following must be distinguished:

| Detail | Why it matters |
|---|---|
| Calendar month versus industry trade month | Pricing can straddle calendar months or finish before the named delivery month. |
| One observation, daily observations or weekly releases | The number and weight of contributing observations differ. |
| Common pricing | ICE defines the calendar using dates on which all relevant reference prices are scheduled to be published or announced. An unexpected missing observation is handled separately. |
| Non-common pricing | Each leg uses its own publication days and denominator. |
| Selected-start BALMO | The contractual window differs from a full month, and its start must be retained. |
| Fixed reference maturity versus rolling nearby | One window can refer to one contract or switch between contracts. |
| Assessment midpoint versus published average or VWAP | These are distinct raw observations; volume weighting is not arithmetic averaging. |
| Intermediate and final rounding | Rounding each day's midpoint and then averaging can differ from rounding only the result. |

ICE's scheduled-publication definition is explicit in Rule 19.01. The governing wording must be retained for each product; observed missing data must not silently redefine its calendar. [ICE Chapter 19](https://www.theice.com/publicdocs/rulebooks/futures_us/19_Oil_Futures_and_Related_Options_Contracts.pdf)

A particularly useful weekly example is NYMEX Dated Brent versus Brent First Month BFOE, chapter 1145: 1,000 barrels, USD/barrel, Monday-Friday common pricing, and the BFOE month is held constant for the entire week using the month first listed on the week's last publication day. Its expiry boilerplate contains a discrepancy discussed below. [Rules](https://www.cmegroup.com/content/dam/cmegroup/rulebook/NYMEX/11/1145.pdf)

For an average already in progress, the economic schedule does not change as valuation advances. The observed contribution becomes known and only the remaining observations need projection. Missing expected publication and a scheduled non-publication day are different facts. The former requires the specified fallback or an explicit failure.

### 4. Dates must be named by their job

The following are different: the listed contract period; each underlying reference period; first and last observation; trading termination date and time; settlement-price determination/publication; final cash payment; notice/election deadlines; delivery window; delivery completion; and invoice payment.

For example, ICE WTI first-line averages NYMEX front-month settlements over the production month, trades through the contract month's last trading day, and pays two clearing-house business days afterward. It is a 1,000-barrel cash future even though its reference is a physical WTI future. [ICE WTI first-line](https://www.ice.com/products/6753542/WTI-1st-Line-Future)

Design inference: one `expiry` field cannot substitute for this schedule. Date-generating conventions and their calendars may be maintained outside the trade and resolved into explicit dated facts. The representation needs to retain the result and its governing convention/version without assuming today's calendar was always applicable.

### 5. Quantity and price dimensions must be explicit

Separate number of contracts, nominal quantity per contract, nominal quantity unit, quote currency, currency scale (dollars versus cents), quote denominator and the resulting monetary multiplier. Physical delivery units, minimum parcels and tolerances are additional terms.

The distinction between a U.S. gallon and a barrel is a fixed volume conversion. A tonne-to-barrel ratio is generally a product/density convention; a fixed exchange crack ratio is a contractual coefficient. It must not silently become a universal physical-density conversion.

The library's existing [unit-conversions scope](../library/globals/unit-conversions.md) explicitly excludes compound prices, FX, contract units and mass-volume conversion without density. This evidence identifies the next consumers of those concepts; it does not change that scope or decide their implementation.

### 6. Physical terms are a structured obligation

The contract evidence supports a delivery specification containing eligible commodity grades or quality limits; location/facility choices; loading, pipeline, in-tank, in-well, book-transfer or warrant method; measurement basis; permitted quantities and tolerances; who nominates each choice and by when; quality/location premiums or discounts where applicable; delivery window; invoice-price basis; taxes and charges; payment; and any prescribed alternative route or election.

The permitted choices and the choices actually exercised are different records. A trade can reference the standard delivery terms while later lifecycle events record nominations, assignments, quantities and completed delivery. The price risk of a physically delivered future is often handled through its quoted futures price, but that does not erase delivery obligations or make every embedded delivery choice economically linear.

### 7. Signed prices, ticks and rounding are not interchangeable

CME's trading infrastructure explicitly supports zero and negative futures trade and settlement prices where enabled for the product. Positive-only price validation would reject valid petroleum outcomes. Product-specific tick grids and price limits remain separate facts. [CME negative-price support](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457223927/Positive%2BZero%2Band%2BNegative%2BFutures%2BTrade%2Band%2BSettlement%2BPrices)

Trading increment, settlement precision, source-assessment precision and cash rounding can all differ. Store or reference each where it governs an observable result. Do not round historical observations to the trading tick merely because the futures quote uses that increment.

## Candidate information blocks for the eventual template

These are deductions for review, not a proposed giant constructor or an approved class hierarchy.

| Block | Facts to accommodate | Likely owner |
|---|---|---|
| Trade occurrence | Identity, side, number of lots, trade timestamp, referenced listed contract, execution-price terms (fixed price or settlement/marker plus offset) with units | Trade record |
| Product definition | Listing exchange, product identifiers, clearing venue, lot size, quote conventions, governing rule version/source | Reusable contract definition |
| Listed contract instance | Named month/week/day/window and resolved economic dates, selected BALMO start where applicable | Contract instance referenced by trade |
| Price definition | One or more exact references, component signs/coefficients, transformations, conversion factors, observation schedules, averaging and roll rules, rounding, fallback terms | Contract definition plus resolved instance |
| Settlement obligations | Final cash/physical/election terms, payment schedule, daily variation treatment, separate delivery invoice basis if needed | Contract definition plus resolved instance |
| Physical specification | Eligible quality/location/method, quantity rules, choices/deadlines, delivery terms and invoice adjustments | Referenced delivery specification |
| Contract state | Resolved execution price where initially reference-based, fixings known as of valuation, last variation settled, unpaid cash, actual elections/nominations and delivery events | Lifecycle/valuation state, outside immutable trade economics |
| Pricing inputs | Futures curves, assessed-price curves, FX, discount/funding inputs, model selection and work counter | Pricing context/machinery |

The direction consistent with [Principle 7](../../PRINCIPLES.md) is a small trade occurrence referring to complete contract facts. This avoids copying the same exchange rules onto every row while preserving the exact meaning of each trade. It also leaves room for a simple outright to be the one-reference case of a common price representation.

Do not assume every globally traded oil future is jointly linear in every underlying risk factor. In particular, multiplying an oil average by a stochastic FX average is bilinear in those factors; fixed currency conversion and stochastic FX conversion are different cases. The payoff remains linear in the quoted listed futures price. What `linear` means in this library therefore needs to be stated before accepting every case into a single pricer.

## Evidence limitations and decisions still to make

| Item | What remains unresolved and how it affects use |
|---|---|
| NYMEX RBOB crack, chapter 559 | Its formula converts gasoline to USD/bbl before subtracting crude, but its quote/value paragraphs specify USD/gal and 42,000 gallons. Resolve against operational product reference data or exchange clarification; do not guess a factor of 42. [Chapter](https://www.cmegroup.com/rulebook/NYMEX/5/559.pdf) |
| NYMEX Brent chapters 692/698 | Both state 1,000 barrels but parenthetical value-multiplier text reads 100.0. Contract size alone does not resolve the contradictory value text. The evidence table therefore flags the multiplier. |
| NYMEX weekly Dated/BFOE, chapter 1145 | Weekly price-definition provisions coexist with daily-contract wording in expiry/final-settlement provisions. The weekly average and month-selection rule are supported; precise expiry needs another source. |
| ICE weekly Dated/BFOE CFD | Page gives payment relative to last trade even though last trade precedes the pricing week. Reconcile the package's daily settlement schedule with its governing rules before implementation. |
| ICE Brent/WTI spread strategy | Page supports the two-position structure but contradicts itself about bought-spread leg direction. Resolve strategy legs from exchange definitions; do not infer them from the name. |
| GME ordinary daily settlement | Current summary and settlement pages disagree on the ordinary settlement time. The independently corroborated expiry marker is reported; the disputed daily time is not encoded. |
| INE LU final-price wording | English 2026 Article 174 describes a mean of executed prices during the last five trading days. Do not replace that with a mean of daily settlement prices without checking authoritative text. |
| SHFE FU effective version | Retrieved 2024 timing provisions need verification against the indexed January 2026 revision. Older official manuals also contain a legacy 50-t lot and must not override current 10-t product terms. |
| DCE LPG, PG | Included in scope, but the actual primary specification could not be retrieved reliably. Its lot, expiry, mixture quality and delivery rules remain a research gap. [Official rules-publication reference](https://www.dce.com.cn/dceg/file/2025-05-29/1748480861759ff80808197162e7117301971994a63f12f6.pdf) |
| Contract-level gaps | Some chapters do not fully identify nearby-month mapping, publication delay, cash-payment timing, price correction treatment or fallback. Detailed Brent election deadlines/default, complete nomination schedules and all publisher methodologies require further extraction before an executable contract master is populated. |
| Inventory limits | This is a broad structural survey, not a certified inventory of all current petroleum listings. It has not independently surveyed every other venue, every biofuel/SAF assessment, or every jurisdiction's petroleum contracts. |

The findings establish concrete examples for a later reviewed coverage set: physical WTI; Brent election; gasoil volume delivery; Micro WTI penultimate cash; first-line rolling average; common-day jet basis; non-common jet/gasoil basis; trade-month published differential; cross-month reference; event-driven Canadian window; naphtha BALMO; both weekly CFD structures; converted fuel-oil crack; monthly posted propane; yen/FX-average Dubai; bonded fuel-oil warrants; and duty-paid bitumen. Each should be represented without guessing an unresolved term. These are candidate acceptance cases, not tests added in this research task.

The next design discussion can be concrete: define what a futures trade occurrence owns, what it references, and what the first pricing function is meant to return (quoted fair price, P&L since execution, unsettled variation, or another explicitly named quantity). Those are separate questions from cataloguing every oil ticker.

No constructor, pricing implementation, repository principle or existing library decision was changed by this research.
