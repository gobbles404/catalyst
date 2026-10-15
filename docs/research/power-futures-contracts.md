# Power futures: a vanilla contract survey

Reviewed 14 September 2026. Companion to the [petroleum](petroleum-futures-contracts.md) and [natural gas/NGL](natural-gas-and-ngl-futures-contracts.md) surveys. This pass covers exchange-listed energy futures, with representative contracts rather than an exhaustive location catalogue.

The central power-specific fact is the **load profile**: which delivery intervals count. Combined with the market location, price index and contract period, it defines the basic exposure. Baseload, peak and off-peak are useful labels, but their exact hours and calendars are contractual.

## The main groups

| Group | Economic meaning | Terms to preserve |
|---|---|---|
| Baseload / all-hours outright | Price exposure across every interval in the specified period | Location, period, time convention, quantity and settlement index. |
| Peak / off-peak outright | Price exposure across a specified subset of intervals | Hours, weekdays, holidays and treatment of clock changes. |
| Day-ahead / real-time outright | Exposure to a particular market's price for the same delivery location and intervals | Exact market/auction and index; these are different references. |
| Location basis | The difference between two defined regional or hub prices | Ordered legs, common or separate profiles and reference schedules. |
| Physical future | A listed future carrying a scheduled electricity delivery obligation | Delivery point, profile, nomination rules and invoice terms. |
| Longer-period future or strip | Exposure over months, quarters, seasons or years | Whether one contract remains open, cascades into shorter futures, or is an execution package of separate positions. |

These are overlapping attributes, not proposed subclasses. This review keeps caps/options, capacity, ancillary services, transmission rights, generation-linked shapes and OTC supply agreements outside the vanilla scope. A reference to spot-market prices does not make the future a spot contract.

## Representative contract terms

### United States

LMP means locational marginal price: the operator's electricity price for a specified node or hub. EPT means Eastern Prevailing Time. “HE” labels the hour **ending** at the stated time.

| Representative future | Quantity / profile | Price reference and settlement |
|---|---|---|
| NYMEX PJM Western Hub Real-Time Peak Monthly 1 MW | 1 MW × eligible hours; USD/MWh; tick 0.01. Monday–Friday excluding NERC holidays, **HE 08:00–23:00 EPT**, sixteen hours per eligible day. | Cash arithmetic average of eligible real-time hourly LMPs. Last trade last business day of month; payment two business days later, when reference prices become final for the contract. [Chapter 262](https://www.cmegroup.com/rulebook/NYMEX/2/262.pdf) |
| NYMEX PJM Western Hub Day-Ahead Off-Peak Monthly 1 MW | 1 MW × eligible hours; USD/MWh; tick 0.01. Ordinary weekdays HE 01:00–07:00 and 24:00; weekends/NERC holidays all hours, in EPT. | Cash arithmetic average of eligible **day-ahead** hourly LMPs. Last trade last business day of month; payment two business days later. Use actual intervals, including clock-change treatment. [Chapter 261](https://www.cmegroup.com/rulebook/NYMEX/2/261.pdf) |
| ICE PJM Western Hub Day-Ahead Peak PJC / Real-Time Peak PMI | 1 MW profile; USD/MWh. Both use the monthly 16-hour weekday/non-NERC-holiday peak profile above. | Separate day-ahead and real-time indexes; monthly average of daily peak averages. Last trade last business day of month; payment second clearing-organization business day afterward. [PJC](https://www.ice.com/products/6590366/PJM-Western-Hub-Day-Ahead-Peak-Fixed-Price-Future), [PMI](https://www.ice.com/products/6590369) |
| NYMEX / ICE PJM Western Hub Day-Ahead Peak Daily | **Fixed 16 MWh / 800 MWh**, respectively; USD/MWh. Each references the day's HE 08:00–23:00 EPT block. | Cash daily LMP average. Last trade preceding business day; payment three business days later, using the specified clearing calendar. Daily eligibility is defined independently of monthly weekday/holiday rules. [NYMEX chapter 808](https://www.cmegroup.com/rulebook/NYMEX/8/808.pdf), [ICE PDA](https://www.ice.com/products/6590471/PJM-Western-Hub-Day-Ahead-Peak-Daily-Fixed-Price-Future/specs) |

The two daily contracts illustrate different fixed multipliers for the same price window. ICE's USD0.01/MWh quotation convention is separate from its trade-type minimum-fluctuation rules. An off-peak average of all eligible hours and an average of daily off-peak averages also need not be equal when day lengths differ; preserve the specified aggregation hierarchy.

### Europe

| Representative future | Quantity / profile | Price reference and settlement |
|---|---|---|
| EEX German Base | 1 MW × all covered local hours; EUR/MWh; tick 0.01. Midnight–midnight, every day, with 23/25-hour clock-change days. | Cash German EPEX SPOT day-ahead reference. Day/weekend/week/month/quarter/year maturities; longer contracts cascade. [German market](https://www.eex.com/en/markets/power/german-power-markets), [size/tick](https://www.eex.com/en/markets/power/power-futures), [rules A.1.1](https://www.eex.com/fileadmin/EEX/Downloads/Rules/Contract_Specifications/20260723_EEX_Contract_Spezifications_0104a_E_FINAL.pdf) |
| EEX German Peak | 1 MW; EUR/MWh; tick 0.01. Standard week/month/quarter/year: **08:00–20:00 local time, Monday–Friday, including weekday holidays**. | Cash day-ahead reference for selected intervals. Peak day/weekend products have their own day selection. [Rules A.1.1.3](https://www.eex.com/fileadmin/EEX/Downloads/Rules/Contract_Specifications/20260723_EEX_Contract_Spezifications_0104a_E_FINAL.pdf) |
| ICE UK Gregorian Base / Peak, UBL / UPL | 1 MW; **GBP/MWh**, tick GBP0.01. Base: **23:00–23:00 London local time**, all days, actual hours. Peak: **07:00–19:00 Monday–Friday**. | Physical transfer through notified BSC Energy Accounts; half-hour settlement intervals. Monthly contracts and monthly strips. Last trade 17:00 London time two business days before delivery. [Base](https://www.ice.com/products/20788778/UK-Base-Electricity-Future-Gregorian), [peak](https://www.ice.com/products/20799523/UK-Peak-Electricity-Future-Gregorian), [governing rules W.3/W.4](https://www.ice.com/publicdocs/contractregs/33_SECTION_W.pdf) |
| Euronext Nordic System Price Base Month, NSBM | 1 MW × covered hours; EUR/MWh; tick 0.01; all hours/all days with clock-change adjustment. | Cash average of Nord Pool's Nordic System spot-price benchmark. [Specification](https://live.euronext.com/en/product/commodities-futures/NSBM-DAMS/contract-specification) |
| Euronext Nordic EPAD Base Month, e.g. Oslo OSBM | 1 MW × covered hours; EUR/MWh; tick 0.01; all-hours profile. | **Standalone cash basis future**: specified area price **minus Nordic System Price**. EPAD means Electricity Price Area Differential. [Specification](https://live.euronext.com/en/product/commodities-futures/OSBM-DAMS/contract-specification) |

EEX quarter futures cascade into three monthly futures; a year becomes January–March months plus Q2–Q4 quarters. The parent terminates and shorter positions are created. By contrast, EEX location-spread execution immediately produces two underlying positions. [ECC cascade explanation](https://www.eex.com/fileadmin/ECC/Downloads/Operations/Reports/Financial_Settlement_Reports/250919_Cascading_Explainer_ECC.pdf), [EEX spread trading](https://www.eex.com/en/markets/power/german-power-markets)

For EEX, longer maturities terminate on the third ECC business day before delivery. Ordinary cash fulfilment for EUR/GBP power is the ECC business day after final-price determination. Negative final settlement prices are expressly permitted. [Rules C.1.1/D.2.2](https://www.eex.com/fileadmin/EEX/Downloads/Rules/Contract_Specifications/20260723_EEX_Contract_Spezifications_0104a_E_FINAL.pdf)

Euronext's current System/EPAD settlement procedure uses **15-minute spot observations**. Clock-change days still require the contractual interval count. [June 2026 settlement procedure](https://live.euronext.com/sites/default/files/documentation/contract-specifications/Power%20Futures%20Daily%20Settlement%20Price%20Procedures.pdf)

### Australia and New Zealand

| Representative future | Quantity and price | Settlement / timing |
|---|---|---|
| ASX Australian baseload month / quarter | 1 MW across all hours, in NEM time; AUD/MWh; tick AUD0.01/MWh. NSW, Victoria, Queensland and South Australia are separate references. | Cash average of the region's five-minute spot prices. Monthly last trade is the last business day of the month; cash settlement follows on the fourth business day after month expiry. [Specifications, pp.21–22](https://www2.asx.com.au/content/dam/asx/participants/derivatives-market/ird/asx24-contract-specifications.pdf) |
| ASX conventional Australian peak quarter | 1 MW, 07:00–22:00 Monday–Friday, excluding specified public holidays; AUD/MWh. | Cash average of the selected peak spot prices. Profile hours determine the MWh quantity. This profile has a limited forward listing horizon; see note below. [Specifications, p.22](https://www2.asx.com.au/content/dam/asx/participants/derivatives-market/ird/asx24-contract-specifications.pdf) |
| ASX New Zealand baseload month / quarter | 0.1 MW across the base profile; NZD/MWh; separate Otahuhu and Benmore nodes. | Cash against the applicable node's electricity-price reference. The smaller MW lot is a contract parameter, not a new economic structure. [ASX product overview](https://www.asx.com.au/electricity) |

ASX now also lists straightforward morning and evening profiles: 06:00–09:00 and 16:00–21:00 NEM time, respectively, every day. Its conventional weekday peak contracts are not listed beyond 2028. This is a useful reason to version the profile and applicable series rather than hardcode one permanent Australian “peak.” [ASX profile fact sheet](https://www.asx.com.au/content/dam/asx/markets/trade-our-derivatives-market/asx-australian-morning-and-evening-peak-electricity-futures-fact-sheet.pdf)

## What the vanilla template needs

### 1. Quantity and profile are separate facts

For a rate-based contract:

```text
MWh per lot = MW per lot × total eligible delivery hours
position MWh = signed number of lots × MWh per lot
```

A fixed-MWh contract uses its stated quantity instead. Price averaging across a month does not by itself imply a rate-based quantity.

For illustration, a 1-MW base contract over exactly 30 ordinary 24-hour days represents 720 MWh. A 1-MW peak contract with twenty eligible 12-hour days represents 240 MWh. A price move of one currency unit/MWh therefore changes their values by 720 and 240 currency units per lot, respectively. These are arithmetic examples; actual exchange calendars determine actual quantities.

A profile definition should resolve its start/end dates, local time or fixed market time, eligible weekdays, holiday exclusions and intervals. Preserve whether labels denote hour beginning or hour ending. Observation granularity can be hourly, half-hourly, quarter-hourly or five-minute even when the quotation is per MWh.

### 2. The price reference is more than a location

The reference needs market operator/publisher, node/hub/zone, day-ahead or real-time market, exact index, selected intervals, aggregation and rounding. An outright may average daily averages; another may directly average settlement intervals. Retain the specified weights rather than infer them from the word “average.”

A plain basis future adds a signed second reference. A screen-traded spread that produces two outright positions should remain two positions. Neither “same country” nor “same delivery month” makes distinct location or market references interchangeable.

### 3. Keep the event dates distinct

Store or resolve the contract period, last trading date, observation window, final-price determination, payment date and any physical delivery dates. A cash future can remain exposed to spot observations during its contract period. A physical future can stop trading before that period begins. A quarter or year may instead terminate through a prescribed cascade.

Daily variation settlement is separate from the final settlement event. For a simple unchanged cash-futures position, `signed lots × MWh per lot × (final price − execution price)` describes cumulative trading P&L before fees and funding; it is not generally one payment made at expiry, and is not a valuation formula for a physical obligation.

### 4. Keep the trade record small

| Contract information | Minimal useful content |
|---|---|
| Identity | Exchange/product, applicable rule version, dated contract instance. |
| Market reference | Operator/index, location, day-ahead/real-time, currency and price denominator. |
| Period and profile | Start/end, base/peak/off-peak definition, time zone, holiday and interval conventions. |
| Quantity | Fixed MWh or MW rate, lot multiplier, resolved eligible energy. |
| Price definition | Outright or signed basis, averaging schedule/weights, rounding. |
| Settlement and lifecycle | Cash or physical, expiry/payment rules, any cascade or component positions. |

The trade occurrence then supplies the referenced contract, side, number of lots and execution-price terms. Fixings and settled/delivered amounts belong to state; pricing curves and forecasting models remain separate, consistent with [Principle 7](../../PRINCIPLES.md).

## Scope and verification limits

The common representation can remain **location + market reference + period + profile + quantity basis + settlement terms**. This survey establishes representative structures, not the availability or liquidity of every series. Individual onboarding still needs the applicable calendars, payment rules and exact index identifiers.

Two source/version details matter even in a vanilla pass. The Nordic System/EPAD suite is now on Euronext following the March 2026 migration; historic Nasdaq listings are not the current venue. ICE's UK product-page quotation wording is inconsistent, so the table follows governing rule W.4's **pounds/MWh**, not an additional pence conversion. [Nord Pool migration confirmation](https://www.nordpoolgroup.com/en/trading/euronext-nord-pool-power-futures-market/), [ICE W.4](https://www.ice.com/publicdocs/contractregs/33_SECTION_W.pdf)

For the physical UK example, final invoice payment rules require the clearing procedures; a variation-price-difference payment rule does not establish the physical invoice due date. The vanilla schema needs a place for those delivery obligations, without making physical nominations part of every cash future. [UK delivery procedures](https://www.ice.com/publicdocs/contractregs/34_SECTION_X.pdf)

This note proposes coverage requirements for discussion. It changes no constructor or pricing implementation.
