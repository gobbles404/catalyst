# WTI validation workbook

`wti-validation.xlsx` exercises the complete daily market path on main after PR88. The fixture is NYMEX Light Sweet Crude Oil (CL), valued **18 September 2026**, with the day fraction set to **1**. The library still treats the valuation day as live at that fraction.

## Open and use

Open the workbook with the goosedove add-in loaded. Press **Ctrl+Alt+Shift+F9** after opening: saved handle strings belong to the Excel session that created them and must be rebuilt in a new session.

- **WTI** contains the valuation controls, all eight creator formulas and a view around the valuation date.
- **Daily view** shows the full market beside its history, both from `util_ReadHandle` spills.
- **Definitions** contains the 96-contract F23–Z30 expiry schedule, standard American LO option expiries, 80 fixing holidays and source links.
- **Fixings** contains 938 explicitly synthetic daily prices, with complete business-day coverage from 21 December 2022 through 17 September 2026.
- **Prices** contains 51 sourced closing Last prices for V26–Z30. Only its numeric price column enters the price vector. The workbook contains no chart.
- **Checks** independently reconstructs every expected daily row from the worksheet inputs and compares dates, prompt codes, business/past flags and prices. The top checks pin the supplied baseline.

Blue cells are editable inputs. The workbook uses ordinary dependency-driven recalculation. Change a price in `Prices!C10:C60` to update the price vector and market. Calendar and history do not depend on those price cells. The price order is an explicit worksheet responsibility; the library only receives the numbers.

The dense market contains **2,892 dates** from **21 December 2022 through 20 November 2030**: 938 historical priced days, 1,050 live priced days, and 904 closed days. F23 expires on 20 December 2022 and only anchors the start; G23 is the first represented contract. V26 remains prompt through its expiry on 22 September 2026. X26 becomes prompt on 23 September. Z30 is the final represented contract, expiring on 20 November 2030.

This is a daily prompt-futures market fixture. It does not implement physical delivery, instrument averaging, trade valuation or risk. Contract units are documented for context; no unused index-definition wrapper is implied.

## Data provenance

Historical prices are **fabricated**, not WTI observations. For business-day observation index `i`, starting at zero, the fixture uses `round(74 + 7*sin(i/41) + 3*cos(i/17) + 0.009*i, 2)`. Values are stored as editable numbers, without volatile random formulas.

The price vector is the **18 September 2026 closing Last** displayed in the [Oilprice CL contract table](https://oilprice.com/futures/wti/). [Farmbucks](https://farmbucks.com/futures/energy/wti-crude) corroborates the first 20 contracts, V26–K28; M28–Z30 use Oilprice alone. The vector starts at V26 **100.30** and ends at Z30 **63.50**, USD/bbl. These are secondary-vendor last-traded prices, **not a verified CME official settlement strip**. Public settlement reporting differs from Last; the workbook does not mix those metrics. Deferred Last prices do not establish a common precise trade timestamp across contracts. Sources were retrieved 20 September 2026.

Expiry dates are derived from [CME Chapter 200](https://www.cmegroup.com/rulebook/NYMEX/2/200.pdf) for CL and [Chapter 310](https://www.cmegroup.com/rulebook/NYMEX/3/310.pdf) for standard LO, including the 2028–2030 extension. The workbook labels rule-derived versus corroborated futures dates. F23/G23 are corroborated by [CME notice 22-481](https://www.cmegroup.com/notices/clearing/2022/12/Chadv22-481.pdf). The July 2023–2030 option dates agree with the explicitly amended dates in [CME SER-8887](https://www.cmegroup.com/notices/ser/2021/12/SER-8887.pdf). V26 is also corroborated by Heritage West's [2026 futures calendar](https://www.heritagewestfutures.com/wp-content/uploads/2025/12/2026-Futures-Expiration-Calendar.pdf) and [options calendar](https://www.heritagewestfutures.com/wp-content/uploads/2025/12/2026-Options-Expiration-Calendar.pdf).

This is not an exhaustive export of historically listed exchange expirations. CME's rule preserves originally listed expiries following some later holiday changes, so an exchange notice takes precedence over rule-derived dates.

Fixing holidays exclude days without a newly derived CL settlement. They are not a generic US federal-holiday list: Columbus Day, Veterans Day, shortened settlement sessions and 9 January 2025 remain business days. Good Friday 2023/2026 are excluded even though the settlement files repeat the preceding day's price. Each holiday has a source link. The 2027 exclusions after New Year and the 2028–2030 exclusions project established practice and the [CME holiday calendar](https://www.cmegroup.com/trading-hours.html); separate final settlement notices were not verified. They are visibly labeled as projections. Friday 31 December 2027 remains a business day for energy, rather than being excluded because New Year's Day 2028 falls on Saturday. The 2024 Christmas exclusion follows the holiday notice and standard treatment.

## Repeat native Excel validation

From the repository root, with dependencies installed:

```powershell
uv sync --locked
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\validate_wti_workbook.ps1
```

The script builds this checkout's add-in, starts a separate hidden Excel process, and operates on a disposable workbook copy. It leaves other Excel sessions and the source workbook alone. Optional `-SaveCalculated` replaces the source with the restored, recalculated baseline after every check passes. Optional `-SnapshotPath <path>` exports baseline cell values for inspection.

Validation covers:

- Every market and history row against an independent PowerShell oracle, plus the worksheet's separate Excel formulas.
- A V26 price increase affecting only 18, 21 and 22 September 2026. Only price-vector and market handles may change.
- A historical fixing correction affecting only that historical date. Only fixings, history and market handles may change.
- Visible failures for a blank price, incorrect vector length, missing required fixing, and a fixing on the valuation date.
- A roll to 23 September: add the three newly historical business-day fixings, drop V26 from the vector, and verify X26 is first with 50 prices.
- All worksheets remain free of charts.
- Restoration of all changed inputs and formulas before saving any baseline caches.

The expected totals and date limits intentionally pin this fixture. When extending the horizon or changing the baseline valuation, update the creator ranges, worksheet checks and validation script together. Checks are terminal diagnostics; no market creator depends on them. Passing them establishes consistency with the supplied inputs, not independent exchange certification of every input date or price.

No Python pricing code, host transport or existing `handles.xlsx` content is changed by this workbook.

## Validation record

Created from main commit `6de63c8` (PR88 merged) and extended through Z30. On 20 September 2026, the full repository check passed: Ruff, Pyright, 1,049 Python tests, 141 host tests and 223 native Excel smoke formulas. The extended fixture passed workbook-specific native Excel validation: all 2,892 market/history rows, smart recalculation, error cases and the expiry roll. All 15 worksheet summary checks passed. Changed views and extended endpoints were visually inspected from native-calculated values; the original fixings, valuation inputs, frozen panes and validation rules were preserved.
