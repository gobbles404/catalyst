# NG validation workbook

`ng-validation.xlsx` compares three Henry Hub references on main after PR88, valued **18 September 2026**, with the day fraction set to **1**. The existing NYMEX NG case retains its sourced forward prices. The IFERC and Gas Daily cases add independent synthetic prices and expose where the current prompt-date calendar differs from physical gas delivery.

| Reference | Historical input | Coverage |
| --- | --- | --- |
| NYMEX NG | Daily futures-settlement fixture | Complete existing daily prompt-futures path |
| Henry Hub IFERC | Monthly publication-price fixture | Monthly history and live prices on the library's prompt-tenure dates |
| Henry Hub Gas Daily | Daily assessment-price fixture | Existing daily path plus explicit delivery-package gaps |

**The workbook does not implement a complete physical Gas Daily market.** Weekend and holiday flow dates, assessment-to-delivery mapping, and the current delivery month's remaining prices are not covered by the library's daily prompt-date path. The workbook keeps these differences visible instead of marking them as successful physical-market coverage. IFERC readback dates likewise represent prompt tenure, not the delivery month to which the published price applies.

## Open and use

Open the workbook with the goosedove add-in loaded. Press **Ctrl+Alt+Shift+F9** after opening: saved handle strings belong to the Excel session that created them and must be rebuilt in a new session.

- **NG** contains the valuation controls, all eight creator formulas and a view around the valuation date.
- **Daily view** shows the full market beside its history, both from `util_ReadHandle` spills.
- **Definitions** contains the 96-contract F23–Z30 expiry schedule, standard American ON option expiries, 80 fixing holidays and source links.
- **Fixings** contains 933 explicitly synthetic daily prices, with complete business-day coverage from 29 December 2022 through 17 September 2026.
- **Prices** contains 51 vendor closing prices for V26–Z30, dated 18 September 2026. Only its numeric price column enters the price vector. The workbook contains no chart.
- **Checks** independently reconstructs every expected daily row from the worksheet inputs and compares dates, prompt codes, business/past flags and prices. The top checks pin the supplied baseline.
- **IFERC** and **Gas Daily** each contain their own valuation controls and eight creator formulas in `C12:C19`. Their valuation date is in `C6`, day fraction in `C7`, and fixing mode in `C8`.
- **IFERC dates** and **Gas Daily dates** show the full market and history beside an independent worksheet oracle. Each has 2,891 rows, from 31 December 2022 through 29 November 2030.
- **IFERC inputs** and **Gas Daily inputs** contain separate expiry schedules, publication-calendar fixtures, fixings, synthetic forward prices, and source links.

Blue cells are editable inputs. Prices display three decimal places, in USD/MMBtu. The workbook uses ordinary dependency-driven recalculation. Change a price in `Prices!C10:C60` to update the price vector and market. Calendar and history do not depend on those price cells. The price order is an explicit worksheet responsibility; the library only receives the numbers.

The dense market contains **2,890 dates** from **29 December 2022 through 26 November 2030**: 933 historical priced days, 1,054 live priced days, and 903 closed days. F23 expires on 28 December 2022 and only anchors the start; G23 is the first represented contract. V26 remains prompt through its expiry on 28 September 2026. X26 becomes prompt on 29 September. Z30 is the final represented contract, expiring on 26 November 2030.

These counts describe the original six-sheet NYMEX NG case. The added reference cases have their own inputs and counts below. No case implements physical delivery, instrument averaging, trade valuation or risk. Contract units are documented for context; no unused index-definition wrapper is implied.

## NYMEX NG data provenance

Historical prices are **fabricated**, not Henry Hub observations. For business-day observation index `i`, starting at zero, the fixture uses `round(3.20 + 0.55*sin(i/41) + 0.25*cos(i/17) + 0.0003*i, 3)`. Values are stored as editable numbers, without volatile random formulas.

The price vector uses **18 September 2026 closing prices (vendor settlement-marked Last)** from dated historical rows on [Barchart contract pages](https://barchart.websol.barchart.com/?1_selected_selected=futureQuote&1_show=futureDetail&lang=en&module=demo&region=US&symbol=NGV26). The vector starts at V26 **2.912** and ends at Z30 **4.226**, USD/MMBtu. [Investing.com's contract table](https://www.investing.com/commodities/natural-gas-contracts) corroborates 36 contracts, X27–Z30 excluding F28 and M28. These are vendor closing values, **not a directly verified CME official settlement strip**, and are not described as last-traded prices. The dated historical observations avoid substituting prices from the Sunday reopening. Sources were retrieved 20 September 2026.

Expiry dates use [CME Chapter 220](https://www.cmegroup.com/rulebook/NYMEX/2/220.pdf) for NG and [Chapter 370](https://www.cmegroup.com/rulebook/NYMEX/3/370.pdf) for standard American ON options. NG expires three business days before the first calendar day of the delivery month; ON expires one business day before the future. The first day of the month is not first adjusted backward. NG's contract size is 10,000 MMBtu, with an outright price increment of USD 0.001/MMBtu.

Eight futures dates are explicitly corroborated by CME delivery notices: F23/G23 in [notice 22-481](https://www.cmegroup.com/notices/clearing/2022/12/Chadv22-481.pdf), N23/Q23 in [notice 23-181](https://www.cmegroup.com/notices/clearing/2023/06/Chadv23-181.pdf), M24/N24 in [notice 24-140](https://www.cmegroup.com/notices/clearing/2024/05/Chadv24-140.pdf), and N25/Q25 in [notice 25-216](https://www.cmegroup.com/content/dam/cmegroup/notices/clearing/2025/06/chadv25-216.pdf). All 2026 futures and ON option dates agree with Heritage West's [futures calendar](https://www.heritagewestfutures.com/wp-content/uploads/2025/12/2026-Futures-Expiration-Calendar.pdf) and [options calendar](https://www.heritagewestfutures.com/wp-content/uploads/2025/12/2026-Options-Expiration-Calendar.pdf). Other dates are rule-derived, not individually verified listed expirations. CME's rule preserves originally listed expiries following some later holiday changes, so an exchange notice takes precedence over rule-derived dates.

Fixing holidays exclude days without newly derived NG settlements. The researched CME energy notices cover NG and CL. The list is not a generic US federal-holiday calendar: Columbus Day, Veterans Day, shortened settlement sessions and 9 January 2025 remain business days. Good Friday 2023/2026 are excluded even when settlement files repeat the preceding day's price. Each holiday has a source link. The 2027 exclusions after New Year and all 2028–2030 exclusions project established practice and the [CME holiday calendar](https://www.cmegroup.com/trading-hours.html); separate final settlement notices were not verified. They are visibly labeled as projections. Friday 31 December 2027 remains a business day for energy when New Year's Day 2028 falls on Saturday. No contract-level publication-date column is supplied for this daily NG fixture.

## Henry Hub IFERC case

The `IFERC` sheet calls `_CreateCalendar` in `monthly` mode, supplies a publication date to `_CreateExpirySchedule`, and creates history with `_CreateMonthlyFixings`. It uses **44 monthly fixings**, G23–U26, and a **51-price V26–Z30 vector**. Expired contracts obtain their price from the fixing keyed by their publication date; unexpired contracts obtain it from the vector. Expiry day remains live. Every row assigned to a monthly contract receives its price, including weekends and holidays, while retaining `is_business_day` as information.

The dense readback contains **2,891 dates**: **1,340 fixed rows** and **1,551 live rows**, with no unpriced closed rows. Live monthly prices also populate past dates assigned to an unexpired contract. This differs deliberately from daily mode, where only dates before valuation can use history.

These are prompt-tenure dates. For example, V26 is prompt from **1–30 September 2026**, expires on **30 September**, and has a **1 October** publication date for the October delivery month. A September delivery date instead refers to U26 and its September published price. `IFERC!B49:G52` places those two date axes side by side; the comparison is an explanation of different meanings, not a failure of the prompt-calendar oracle.

The provisional workflow is tested with the January 2026 publication delay. F26 remains live on 31 December 2025. On 1 January 2026 it has expired and history requires a value keyed by **5 January 2026**, its publication date. A supplied provisional value can occupy that fixing key until the published value replaces it. The library does not separately tag the value as provisional, and an already-created history remains immutable. This is a temporary validation scenario, not an extra fixing in the baseline workbook.

## Henry Hub Gas Daily case

The `Gas Daily` sheet calls `_CreateCalendar` in `daily` mode and `_CreateDailyFixings` with the separate Platts assessment-calendar fixture. It contains **926 synthetic historical assessments**, from **3 January 2023 through 17 September 2026**, and **51 synthetic V26–Z30 forward prices**. Its dense readback has **926 fixed rows**, **1,051 live business-day rows**, and **914 closed rows**. The valuation day remains live even with day fraction 1.

This exercises the existing assessment-date path; it does not turn that path into a physical flow-date market. A Friday assessment can supply several delivery days, including weekends, and a known assessment can apply to delivery dates after valuation. The current daily function accepts only historical fixing dates and leaves weekends and holidays closed. Its next-expiring monthly contract also differs from the current delivery month's remaining exposure.

`Gas Daily!B49:G56` compares expected delivery-package prices with native readback for ordinary weekdays, the September weekend, Labor Day, and a month boundary. [Platts' 2026 Labor Day notice](https://www.spglobal.com/energy/en/pricing-benchmarks/our-methodology/subscriber-notes/090126-north-american-natural-gas-labor-day-holiday-schedule) confirms that the 4 September assessment covers 5–8 September flows. The ordinary 18 September Friday package is inferred from the [Platts methodology](https://www.spglobal.com/content/dam/spglobal/ci/en/documents/platts/en/our-methodology/methodology-specifications/natural-gas/us-canada-natural-gas-methodology.pdf) to cover 19–21 September. The worksheet's `GAP` results are expected evidence of unsupported delivery behavior, not passed delivery checks.

Two separate illustrative assessment prices, **2.765 on 18 September** and **2.845 on 30 September**, live in `Gas Daily inputs!U16:W17`. They support the delivery comparisons without loading current or future observations into the historical fixing series. They are fabricated, not observed assessments. A coincidentally equal comparison price would not establish correct delivery mapping.

## Added reference inputs and provenance

Both new input sheets use the same layout:

| Range | Contents |
| --- | --- |
| `B10:F105` | 96 F23–Z30 contracts: code, expiry, IFERC publication date where applicable, delivery month, and date provenance |
| `H10:J99` | 90 publication/assessment holiday inputs and their verification status |
| `L10:N53` on IFERC | 44 publication-date fixings and their contract codes |
| `L10:N935` on Gas Daily | 926 assessment-date fixings and their synthetic provenance |
| `Q10:S60` | 51 V26–Z30 contract codes, synthetic outright prices, and the snapshot valuation date |
| `R10:R60` | Editable numeric prices passed to `_CreatePriceVector` |

The expiry rule is the last business day before the delivery month. **51 HEN listed expiries, V26–Z30**, were corroborated against the [ICE Henry Basis expiry table](https://www.ice.com/products/6590136/Henry-Basis-Future/expiry); earlier dates are rule-derived. F23 expires 30 December 2022 and anchors the start; Z30 expires 29 November 2030. The [HEN specification](https://www.ice.com/products/6590136) supplies the IFERC-linked convention. The [HIS specification](https://www.ice.com/products/6590185) and [Henry Physical Gas Daily Monthly specification](https://www.ice.com/products/1164/Henry-Physical-Gas-Daily-Monthly) support the Gas Daily-linked monthly expiry convention. A HEN-listed date on the Gas Daily input sheet is a corroborating monthly convention, not evidence of a listed outright Gas Daily price contract.

HEN is IFERC minus NYMEX; HIS is the Gas Daily monthly average minus IFERC; the physical Gas Daily monthly contract is priced at a premium or discount to its reference. **Their spread prices must not be pasted as outright benchmark prices.** No current outright monthly Gas Daily-average contract with this full strip was verified. The workbook does not present this convention as a balance-of-delivery-month curve. No corresponding option expiry convention was verified, so option dates are omitted for both cases.

The new publication-calendar fixture is separate from the NYMEX settlement holiday calendar. **Six exclusions are confirmed by dated Platts notices; all remaining entries are visibly assumed or projected.** The official annual 2025–2027 calendar links were located, but their workbook contents could not be retrieved for full verification. The day after Thanksgiving uses a [published Platts precedent](https://commodityinsights.spglobal.com/rs/325-KYL-599/images/Platts%202019%20Gas%20Daily%20Calendar.pdf). Christmas Eve is not automatically excluded: Platts collected data on 24 December 2025. The confirmed extra closures on 26 December 2025 and 2 January 2026 are included. These inputs are a transparent validation fixture, not a production Platts holiday master.

Publication dates generally use the first assumed Platts publication business day of the delivery month, with a confirmed override for **5 January 2026** from [Platts' January publication announcement](https://www.spglobal.com/energy/en/pricing-benchmarks/our-methodology/subscriber-notes/120425-platts-confirms-daily-monthly-north-american-natural-gas-trading-calendar-for-christmas-new-years-day). Other individually unverified dates remain rule-derived and are labeled as such. In particular, later-year publication dates and holidays are projections that require review against publisher announcements. Expiry business days and publication business days are separate calendars. Intraday publication timing is outside the current fields.

All new historical and forward prices are **independent deterministic synthetic fixtures**, stored as editable numbers and rounded to three decimals in USD/MMBtu. No verified public 18 September 2026 IFERC or Gas Daily outright strip was found. The snapshot date is a valuation label, not a claim that these numbers were observed closing prices. The NYMEX NG prices are not substituted into either benchmark.

- IFERC fixing index `i` starts at zero for G23: `round(3.05 + 0.48*cos(i*pi/6) + 0.006*i, 3)`.
- Gas Daily observation index `i` starts at zero on 3 January 2023: `round(2.85 + 0.45*sin(i/37) + 0.20*cos(i/13) + 0.00025*i, 3)`.
- Forward index `i` starts at zero for V26; `m` is the delivery month numbered January = 0 through December = 11. IFERC uses `round(3.15 + 0.48*cos(m*pi/6) + 0.007*i, 3)`; Gas Daily uses `round(3.08 + 0.57*cos(m*pi/6) + 0.007*i, 3)`.

Changing `R10:R60` rebuilds only that case's price vector and market. Changing its historical fixing values rebuilds its fixings, history and market. The original NYMEX NG formulas do not depend on the two added cases. None of these functions checks benchmark identity, so keeping the three references' inputs separate remains a worksheet responsibility.

## Repeat native Excel validation

From the repository root, with dependencies installed:

```powershell
uv sync --locked
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validate_ng_workbook.ps1
```

The script builds this checkout's add-in, starts a separate hidden Excel process, and operates on a disposable workbook copy. It leaves other Excel sessions and the source workbook alone. Optional `-SaveCalculated` replaces the source with the restored, recalculated baseline after every check passes. Optional `-SnapshotPath <path>` exports baseline cell values for inspection.

Validation covers:

- Every market and history row against an independent PowerShell oracle, plus the worksheet's separate Excel formulas.
- A V26 price increase affecting only 18, 21, 22, 23, 24, 25 and 28 September 2026. Only price-vector and market handles may change.
- V26 remains prompt on its 28 September expiry, and X26 becomes prompt the following day.
- A historical fixing correction affecting only that historical date. Only fixings, history and market handles may change.
- Visible failures for a blank price, incorrect vector length, missing required fixing, and a fixing on the valuation date.
- A roll to 29 September: add the seven newly historical business-day fixings, drop V26 from the vector, and verify X26 is first with 50 prices, 940 historical priced days and 1,047 live priced days.
- Three-decimal formats on the editable price and fixing columns.
- All worksheets remain free of charts.
- Restoration of all changed inputs and formulas before saving any baseline caches.

The same runner invokes `tools/ng_benchmark_checks.ps1` for the added IFERC and Gas Daily cases. Its checks cover every market/history row and worksheet oracle, expected baseline counts, selective price/fixing recalculation, blank prices, incorrect vector lengths, missing required fixings, and the relevant daily or monthly fixing failures. A separate temporary IFERC January scenario checks expiry-day live pricing, refusal when the expired contract's fixing is absent, a provisional value on 1 January keyed by 5 January, replacement with the published value, and immutability of the earlier history. The helper uses the runner's owned hidden Excel session and restores every baseline input before saving.

Native consistency checks and delivery-gap comparisons answer different questions. Passing the native checks confirms the current prompt-date implementation against its supplied inputs. It does not close the physical delivery gaps documented on the two main case sheets.

Dense readback and the worksheet oracles deliberately add validation work. This workbook is not a hot-path latency benchmark.

The expected totals and date limits intentionally pin this fixture. When extending the horizon or changing the baseline valuation, update the creator ranges, worksheet checks and validation script together. Checks are terminal diagnostics; no market creator depends on them. Passing them establishes consistency with the supplied inputs, not independent exchange certification of every input date or price.

No Python pricing code, host transport or existing WTI and `handles.xlsx` content is changed by this workbook.

## Validation record

Created alongside the WTI fixture on the branch based on main commit `6de63c8` (PR88 merged). On 20 September 2026, the full repository check passed: Ruff, Pyright, 1,049 Python tests, 141 host tests and 223 native Excel smoke formulas. The NG workbook passed native Excel validation for all 2,890 market/history rows, selective recalculation, error cases, three-decimal formats and the September 29 expiry roll. All 15 worksheet summary checks passed. All six sheets and their extended endpoints were visually inspected from native-calculated values. The existing WTI workbook is unchanged.

The IFERC and Gas Daily extension was validated on 20 September 2026. Both 2,891-row market/history views and their independent worksheet oracles passed. Selective price/fixing updates, input-error cases, the January provisional-to-published transition, and immutable earlier history passed in native Excel. The original NG case passed again. The eight Gas Daily delivery comparisons intentionally retain `GAP`; they document unsupported behavior rather than failed prompt-date calculations.

All six added sheets and their endpoints were visually inspected using native-calculated values. Native Excel rendering confirmed the input notes and layouts. Valuation-date shading, closed-day shading, failed-check highlighting and the delivery-gap highlighting were checked in Excel, including temporary failures restored before saving. An independent preservation audit found no changes to the original six sheets' values, formulas, base cell styles or dimensions; all 51 sourced NG prices, 96 expiry/option rows, 80 holidays and 933 fixings are unchanged. Conditional-format rules were restored or expressed as explicit comparisons so their intended highlights render in Excel. The full repository check also passed with the same Python, host and Excel smoke counts listed above. The WTI workbook remains byte-for-byte unchanged.
