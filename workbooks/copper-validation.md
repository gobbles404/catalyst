# LME copper validation workbook

`copper-validation.xlsx` is a worked example for standard LME Copper (CA), with a valuation date of **18 September 2026**, synthetic prices in **USD per tonne**, and selected dated prices through **December 2030**. One CA lot is 25 tonnes. It keeps the existing WTI and NG workbooks unchanged.

The workbook deliberately separates a rolling cash-reference series from the output the current library produces. The latter is a diagnostic, not a complete LME market. All prices are synthetic; none is represented as an observed 18 September close. The library's day fraction is 1, but its calendar and market do not enforce the exchange's intraday trading deadline or incorporate a same-day cash assessment after publication.

## Start here

On **Copper**, compare the observation date, cash delivery date, and delivery date of the contract selected by the library. The first example is the essential difference:

| Observation date | Cash delivery date | Native contract delivery date |
| --- | --- | --- |
| 18 Sep 2026 | 22 Sep 2026 | 21 Sep 2026 |
| 21 Sep 2026 | 23 Sep 2026 | 22 Sep 2026 |
| 8 Oct 2026 | 13 Oct 2026 | 9 Oct 2026 |
| 9 Oct 2026 | 13 Oct 2026 | 13 Oct 2026 |
| 12 Oct 2026 | 14 Oct 2026 | 13 Oct 2026 |

The library chooses the first contract whose supplied last trading date is on or after the calendar row. A cash-reference projection instead needs the contract for that observation's cash delivery date. An occasional matching row does not establish that the two mappings are equivalent.

Change **Prompt prices!F11**, the synthetic price for 22 September delivery. The reference cash row for 18 September changes, while the native live row for 21 September changes. The original historical fixings remain unchanged. This is a visible example of the mapping difference, using the same underlying dated price.

The worked block on Copper also shows a cash assessment observed on 17 September for 21 September delivery, alongside the live dated future for that same delivery. A published historical assessment does not freeze the price of an outstanding future. The future can continue trading until its own last trading deadline.

## Dates and reference prices

These fields have distinct meanings:

- **Observation date:** when the daily cash assessment is published. Historical fixings use this key.
- **Cash delivery date:** the prompt date represented by that day's cash assessment.
- **Contract prompt date:** the delivery maturity identifying an individual dated future.
- **Last trading date/time:** the contract's trading deadline. Standard CA trades until 12:30 London time on the trading day before its prompt date.

The cash-date rule is the **first settlement business day after the next LME business day**. The workbook exposes both steps:

```excel
=WORKDAY(WORKDAY(observation_date,1,lme_holidays),1,settlement_holidays)
```

Using two days on a single combined holiday calendar is incorrect around US-only settlement holidays. For example, the next LME business day after Friday 9 October 2026 is Monday 12 October, even though USD settlement is closed that Monday. Cash is Tuesday 13 October. Thursday 8 October has the same cash date. Those two daily assessments can have different prices and must remain separate observations.

The **Official Cash Settlement Price** is a specific LME reference, the cash offer established during the second Ring. It is distinct from an end-of-day Closing Price. Future rows in this workbook show a current dated future as a price projection for the matching cash maturity; they do not claim to know a future published cash assessment.

Copper Monthly Average Futures and TAPOs reference an average of daily cash assessments. That average is over observation dates in the relevant month. The final MASP is one monthly number, but before month-end the averaging period contains known daily assessments and projected remaining assessments. A single third-Wednesday CA future does not represent that payoff. This workbook explains the distinction but does not price the averaging instrument.

## Workbook structure

| Sheet | Purpose |
| --- | --- |
| Copper | Main worked examples, controls, native creator handles, and remaining behavior to implement |
| Cash dates | Dense observation-date series with the two-step cash-date mapping, exact dated-price lookup, native comparison, and visible gaps |
| Library view | Actual `util_ReadHandle` output for the native market and market history |
| Prompt prices | 119 editable synthetic prices keyed by dated contract, including the native diagnostic's TOM point |
| Fixings | 938 synthetic daily cash observations, keyed by observation date, with the associated cash delivery date shown separately |
| Definitions | 1,031 selected schedule rows, separate LME and settlement holiday lists, 251 official Cash/3M checker rows, and primary sources |
| Checks | Baseline assertions and independent comparisons against all 251 published cash dates |

The dense native calendar runs from **31 December 2022 through 17 December 2030**, containing **2,909 rows**: 938 historical business days, 1,076 live business days and 895 closed days. Its first schedule row is an anchor only. The last selected delivery prompt is **18 December 2030**, whose last trading date is 17 December.

The schedule uses unique workbook identifiers such as `CA-2026-09-22`. They are not vendor symbols. The existing library already accepts arbitrary unique codes; monthly futures-letter parsing is not the obstacle. In historical rows, the native price comes from the cash observation; it does not inherit its delivery identity from the calendar's assigned contract. Cash dates shows that observation's actual cash delivery date separately.

The forward selection contains daily/TOM dates through 18 December 2026, selected Wednesdays through 17 March 2027, and selected third Wednesdays thereafter through December 2030. It is not an exhaustive list of all eligible LME prompts. Additional second-business-day monthly prompts are omitted. Dates are rule-derived from published calendars; this is not an export of every contract that traded.

The exceptional 19 June 2024 and 19 June 2030 listed prompts are omitted from the selected schedule. The 2024 prompt had exceptional delivery arrangements; the 2030 date remains listed by explicit exchange exception pending updates. The settlement calendar still excludes those USD banking holidays. Their treatment cannot be reduced to an ordinary prompt-equals-settlement assumption.

## Reading the comparisons

- **HISTORY:** the historical cash assessment is supplied by observation date.
- **CLOSED:** no assessment is assigned to a non-business day.
- **MATCH:** an exact dated price exists and the native contract happens to have the same delivery date.
- **DATE GAP:** an exact dated price exists, but the native contract has a different delivery date.
- **NEEDS CURVE:** the selected dated strip has no exact price for the required cash date. The reference price is `unavailable`.

Of the 1,076 live business dates, 122 have exact points in the supplied selection. Of those, 61 match the native contract and 61 expose a date gap. The other 954 require additional points or an explicitly chosen curve construction method. No interpolation is silently invented. The native output remains populated because its existing behavior assigns the next unexpired contract; that does not establish a valid interpolated LME curve.

Historical prices are generated as `8750 + 220*sin(i/31) + 95*cos(i/13) + 1.1*i`, with `i` starting at zero on the first observation. Forward prices are `10000 + 1.75*(prompt - 21-Sep-2026) + 32*sin((prompt - 18-Sep-2026)/43)`, where date differences are calendar days. Both are rounded to the nearest USD 0.50 and stored as editable numeric inputs.

## Sources and limits

Sources are recorded together on Definitions. The holiday fixture was checked against LME calendars and notices for 2023–2030. Future published schedules remain subject to later notices.

- [LME Copper specifications](https://www.lme.com/Metals/Non-ferrous/LME-Copper/Contract-specifications): standard CA, lot size, prompt structure, and monthly-average product distinctions.
- [LME prompt-date structure](https://www.lme.com/Sustainability-and-Physical-Markets/Physical-market-benefits/Prompt-date-structure): final trading deadline and prompt conventions.
- [LME Rulebook, 31 July 2026](https://www.lme.com/-/media/files/company/market-regulation/rulebook/evergreen-for-non-rulebook-pages/rulebook-as-of-31-july-2026.pdf): Business Day, Settlement Business Day, and Cash definitions.
- [Official Cash/3M checker, April 2026–March 2027](https://www.lme.com/-/media/files/data/reports-and-data/cash-and-3-month-promt-date-checker/cash--3m-prompts--apr-26-to-mar-27.xlsx): all 251 published rows are reproduced as source inputs. The cash-date calculation agrees with every row. The 3M dates are source context, not a claimed implementation of rolling 3M pricing.
- [LME trading calendar, 2025–2035](https://www.lme.com/-/media/files/trading/lme-trading-calendar-2025-2035.pdf), [2023–2024 notice 22/102](https://www.lme.com/api/sitecore/MemberNoticesSearchApi/Download?id=405caf05-068d-412b-b42e-bccc7dd5cd09), [Coronation notice 23/063](https://www.lme.com/-/media/Files/News/Notices/2023/04/Calendar-and-Market-Holiday-23-063-Banking-Holidays-NonValid-Prompt-Dates-and-LME-Business-Days-2023.pdf), and [2026–2030 notice 26/131](https://www.lme.com/api/sitecore/MemberNoticesSearchApi/Download?id=5653e7e0-8bb6-4bea-80ae-fab0d46334de): separate LME business and non-settlement dates.
- [2024 exceptional delivery notice 24/128](https://www.lme.com/-/media/Files/News/Notices/2024/03/CALENDAR-AND-MARKET-HOLIDAY-FEES-24-128-CLARIFICATION-IN-RESPECT-OF-DELIVERY-ARRANGEMENTS-FOR-PROMPT.pdf) and the published calendar's 2030 footnote: exceptional prompt treatment.
- [Official Prices explained](https://www.lme.com/Market-data/LME-reference-prices/LME-Official-Price): identity of the cash settlement reference.

Sources were retrieved on 20 September 2026. The workbook is a validation and learning fixture; it does not implement interpolation, basis adjustments between reference-price types, intraday publication/trading state, outstanding-position valuation, delivery instructions, or monthly-average instrument pricing.

## Repeat native Excel validation

From the repository root:

```powershell
uv sync --locked
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validate_copper_workbook.ps1
```

The validator builds this checkout's add-in and starts its own hidden Excel process. It works on a disposable copy and leaves the source and other Excel sessions alone. `-SaveCalculated` saves restored baseline caches only after checks pass; `-SnapshotPath <path>` exports the baseline for inspection.

The validator compares every native market/history row and every cash-reference row against independent date and price calculations, verifies the 251 official date examples, exercises price/fixing changes and handle propagation, and tests invalid inputs. It also checks that changing the valuation-day fraction does not apply an intraday cutoff in the present implementation. All temporary changes are restored before saving.

The worksheet's baseline checks are deliberately pinned. When changing the valuation date, schedule selection, or fixture horizon, update expected counts and validate the input ranges together. Checks are terminal diagnostics; creator functions do not depend on their results.

No library or host behavior is changed by this workbook. Passing its tests verifies the current behavior and the separately stated reference calculation; the marked market gaps remain open.

## Validation record

Validated on 20 September 2026 against main `6de63c8`, on the workbook branch. Native Excel passed the full-row oracle, all 20 baseline checks, all 251 official cash-date comparisons, selective price/fixing updates, input failures, schedule failures, and the valuation-fraction comparison. Temporary inputs were restored before saving the calculated workbook.

All seven sheets were visually reviewed from native-calculated values. Excel's displayed conditional-format colors were verified for date gaps, closed days, the valuation date, and a temporary failed check restored afterward. The repository checks passed: Ruff, Pyright, 1,049 Python tests, 141 host tests, and 223 Excel smoke formulas. WTI and NG remain byte-for-byte unchanged.
