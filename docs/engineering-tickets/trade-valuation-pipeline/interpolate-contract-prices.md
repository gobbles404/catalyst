# Linear interpolation of contract prices

[Pipeline overview](README.md) · [UAT item 21](surface-uat-notes.md#21-linear-interpolation-of-contract-prices)

**Status:** Built in #198, 17 October 2026, as one feature PR from main; [interpolate-contracts.md](../../library/utilities/interpolate-contracts.md) owns the function. It came before multiple discount curves within a trade array and after the single-curve cross-gamma work, #197, independently of it.

## Outcome

Given an index and a few outright contract prices, infer every monthly contract from the first anchor month through the last, inclusive. Resolve their futures expiry dates from the index's schedule, interpolate prices on those dates, and spill each contract beside its expiry and price. December-to-December anchors produce thirteen monthly rows without the user supplying a target list.

The caller chooses when straight-line interpolation is appropriate. This function does not infer a commodity's seasonality, select a market or choose which prices are reliable anchors. Prices must be supplied in the index's quote convention; their numeric values do not identify their source or unit, so the function performs no price-unit conversion. The first example below uses a CL-style series.

## Worksheet contract

```text
util_InterpolateContracts(index, anchor_contracts, anchor_prices)
    -> contract_code / future_expiry / price table
```

All three arguments are required. Use the existing `Handle[Index]`, `TextColumn`, `NumberColumn` declarations and `MixedArray` return type. Anchor inputs have no headers and use the existing vertical-column rules, with no new seam form or implicit coercion.

| Argument | Meaning |
|---|---|
| `index` | The index handle supplying the contract schedule; this slice supports futures indexes only |
| `anchor_contracts` | At least two distinct outright contract months, in strictly increasing month order |
| `anchor_prices` | One finite price per anchor, in the same row order; prices may rise, fall, repeat, be zero or be negative |

There is no `target_contracts` parameter. Output contains every monthly contract between the anchor endpoints, including the endpoints, once each in chronological contract-month order. An intermediate supplied anchor remains in its proper month and retains its price. No handle is created.

### Contract labels

Accept either of these text forms in `anchor_contracts`, including a mixture within the column:

| Input text | Resolved month | Output code |
|---|---|---|
| `Z27`, `z27` | December 2027 | `Z27` |
| `202712` | December 2027 | `Z27` |
| `K28`, `k28`, `202805` | May 2028 | `K28` |

The six-character form is the text returned by [util_FutToCme](../../library/utilities/fut-to-cme.md). It is a month label, not a number used in the interpolation. Excel numeric cells such as numeric `202712` remain invalid for a text column; use text cells or the existing utility's text output. Do not add number-to-text coercion.

Accept the existing 2000–2099 year range, valid month letters and valid `YYYYMM` months only. Match the complete string without trimming or aliases. No exchange/product root, date serial, strip, range, CAL, BAL, quarter or half-year label belongs in these point inputs. Format is inferred from the label; there is no format parameter.

Normalize before checking anchors: `Z27` and `202712` are duplicate months and fail even when their prices agree. Fail on unsorted anchors rather than silently reordering prices. Preserve the existing contract-code parser's accepted forms for its existing consumers; this utility's new `YYYYMM` reading must not change trade-entry behavior.

## Contract and expiry resolution

The [index](../../library/index-definitions/index.md) supplies a [futures schedule](../../library/index-definitions/futures-schedule.md), with a contract code and `future_expiry` per row. Resolve contract identity by month, using the existing monthly schedule interpretation where practical. A lowercase schedule code and its uppercase form name the same month. IFERC and Gas Daily indexes fail for this slice rather than substituting publication, trading or flow dates for futures expiry.

Generate the inclusive monthly range between the first and last anchor months, then resolve every generated month to exactly one schedule row. Every anchor and every intervening month must be present: a missing month or duplicate monthly identity fails, even when that month has no supplied price. Do not silently skip a month, choose one of two rows, or manufacture an expiry. Preserve the existing monthly schedule-reading rules rather than adding a competing interpretation.

That existing monthly reader checks all schedule labels for valid monthly codes and uniqueness, including rows outside the interpolation range. Retain its error ordering and existing consumers' behavior. The new expiry checks below apply only to the selected output months.

For the resolved output months, futures expiries must be valid dates and strictly increasing in contract-month order. Equal or reversed expiries fail naming the offending contracts and dates. Use `future_expiry` exactly as supplied by the index: no option expiry, payment date, month-start substitution or additional holiday adjustment. Dates outside the selected month range are not interpolation points.

This uses the static index definition only. It requires no market, history, fixings, valuation date or current prompt. It does not filter out expired months; the requested anchor endpoints determine the range.

## Calculation

Between adjacent anchors, interpolate the **price itself**, using elapsed calendar days between the contracts' scheduled futures expiries:

```text
w = (target_future_expiry - left_future_expiry)
    / (right_future_expiry - left_future_expiry)

target_price = (1 - w) * left_price + w * right_price
```

This follows the calendar-day weighting in the existing [library convention](../../library/conventions.md#what-holds-everywhere), with the index's futures expiries as the coordinates. Weekends and leap days count in the elapsed time. Monthly describes which contracts are output; it does not imply equal time steps or the use of month-start dates. `YYYYMM` text identifies a month and is never used as a numeric coordinate.

Use the existing NumPy dependency's [numpy.interp](https://numpy.org/doc/stable/reference/generated/numpy.interp.html) for the numerical work, on day offsets from the first anchor's expiry. Validated expiry order and the generated inclusive range keep every interpolation point within coverage: NumPy's default endpoint repetition must never mask a bad schedule. Each interval uses its own adjacent anchors. A target at an anchor retains that anchor's price exactly. No extrapolation occurs before or after the supplied anchor range.

Return finite `float64` prices without display rounding or tick-size rounding. Check newly calculated values before returning the spill. If arithmetic cannot produce a finite result, fail naming the target; do not substitute zero, an endpoint or a clipped answer. No partial table is returned on any failure.

### Worked example

Use a synthetic CL-style index with the following schedule entries. These are fixed test inputs, not a claim about an exchange's published dates. Prices are illustrative USD per barrel.

| Scheduled contract | future_expiry |
|---|---|
| J27 | 2027-03-22 |
| K27 | 2027-04-20 |
| M27 | 2027-05-20 |

Supply only the April and June prices:

| Anchor contract | Anchor price |
|---|---:|
| `202704` | 70.00 |
| `202706` | 76.00 |

The helper infers April, May and June. Its spill has the repository's ordinary two heading rows, then three data rows:

| contract_code | future_expiry | price |
|---|---|---:|
| str | datetime64[D] | float64 |
| J27 | 2027-03-22 | 70.00000000000000 |
| K27 | 2027-04-20 | 72.94915254237289 |
| M27 | 2027-05-20 | 76.00000000000000 |

March 22 to May 20 is 59 calendar days; April 20 is 29 days after March 22:

```text
K27 = 70 + (29 / 59) * (76 - 70)
    = 72.94915254237289
```

The displayed decimals illustrate the answer; they do not specify production rounding. Expiries spill as Excel date values, not date strings. The equivalent `J27` / `M27` anchor labels give the same result. Supplying `K27` as an additional anchor at 74 makes its output exactly 74; any other intervening months in a longer example interpolate against their nearest supplied anchors.

## Using the spill as market input

The helper generates the monthly list; the worksheet selects the applicable portion for a market. To build a price vector, select a contiguous price range starting at that market's current prompt, following its existing schedule order. A one-off price can be looked up by contract code in the spill.

```text
index handle + anchor contract cells + anchor price cells
    -> util_InterpolateContracts
    -> labeled contract_code / future_expiry / price spill
    -> select the applicable numeric price cells, excluding both heading rows
    -> _CreatePriceVector(index_name, prices)
    -> _CreateMarket(history, price_vector)
```

For the worked example, anchors in `A2:A3`, prices in `B2:B3`, and the index handle in `D2`:

```excel
E2: =util_InterpolateContracts(D2,A2:A3,B2:B3)
I2: =_CreatePriceVector(index_name,G4:G6)
```

`E2:G3` holds the two heading rows; `E4:E6` names the three months, `F4:F6` holds their expiries and `G4:G6` their prices. The price-vector formula assumes J27 is the market's prompt and J27/K27/M27 are its next three contracts. The kept-workbook example must make that alignment explicit, with a preceding boundary contract as required by the existing market calendar. `index_name` denotes the cell or named range already used for that index's name.

**Current limitation:** [PriceVector](../../library/market-data/price-vector.md) stores prices and an index name, not contract labels or expiries. Selecting the prices drops those labels; the market still applies its positional rules. This utility verifies contracts against the index schedule but does not determine which is currently prompt. Using the whole spill when its first contract is not the market's prompt is still wrong. No automatic rollover, quote padding or label-aware market binding is part of this change.

Anchor price or index-definition changes recalculate the spill and its dependent vector/market/evaluation chain through Excel dependency. The utility is not volatile and has no global `as_of` dependency. A valuation-date roll does not independently change its range; the sheet remains responsible for selecting the live portion. It does not cache an interpolation plan or selectively update months in this PR. Existing risk remains sensitivity to the resulting contract prices; hedge sensitivities to the sparse anchor quotes are separate work.

## Implementation boundaries

Keep three responsibilities clear: resolve the anchors and inclusive monthly range against the index into contract codes and expiry dates; validate and interpolate the numeric arrays; format the three output columns at the seam. The numerical implementation knows nothing of Excel or handles. Reuse existing contract-code and monthly schedule operations where practical; if sharing requires moving a small definition-level helper out of trades, make that move without changing its current consumers' rules. Do not make market-data arithmetic depend on trade valuation. Choose a small, semantic home for contract-price interpolation alongside market-data code, with only the worksheet wrapper in `excel/utilities.py`.

The existing discount-factor interpolation also calls `numpy.interp`, but its surrounding rules are different: it builds every calendar day and protects the discount curve's decreasing factors. Do not pass commodity prices through that wrapper or import its monotonicity constraints. This PR does not require a general interpolation framework, new dependency, rate-curve refactor or new handle type.

Use current seam refusals for handle/type/shape/blank inputs. Library failures cover a non-futures index, the anchor/price length mismatch, too few anchors, invalid labels, duplicate or non-increasing anchor months, missing or ambiguous schedule months, invalid/non-increasing selected expiries and nonfinite arithmetic. Name the relevant argument and one-based supplied row, or the inferred contract and schedule row where applicable; duplicate anchors should identify both source rows. Anchor errors use supplied row order where a rule has several offenders; schedule-label errors retain the existing monthly reader's order. Document the meaningful rules once on the function's owning page; exact messages and work counts belong in tests.

## Verification and work

1. **Hand answers and range:** pin the worked example, exact endpoints, two adjacent anchor months with no gap, and December-to-December producing exactly thirteen rows. Test three or more irregularly spaced anchors to prove each missing month uses its enclosing pair. Include a leap-day expiry interval with independently calculated day counts.
2. **Dates and prices:** change an intermediate contract's expiry while retaining its month/code and anchor prices; its price must follow the changed day weight, proving month starts are not used. Equivalent code/CME anchor labels give identical results. Include rising, falling, flat, zero and negative prices. Constant prices remain constant; inserting an anchor whose price lies on the existing line preserves that line within float tolerance.
3. **Refusals:** mismatched column lengths, one anchor, duplicate normalized anchors, unsorted anchors, invalid labels, text-versus-numeric `YYYYMM`, wrong handle kinds and blank cells fail. Refuse IFERC/Gas Daily indexes, absent anchor or intervening months, duplicate schedule months and invalid/equal/reversed selected expiries. Pin an unrepresentable numerical result without relying on floating-point warnings being enabled. Never substitute month starts or omit an unresolvable month.
4. **Surface and connection:** check all three column names, types, date values and chronological monthly rows through the seam, host replay and Excel smoke. Add a small kept-workbook example feeding the applicable price column to an ordinary vector and market, with both an anchor-price update and an index-expiry update. The same explicit prices must produce the same existing valuation results. Confirm the index itself is unchanged by interpolation.
5. **Measured work:** use the repository's `WorkCounter` convention for parsing/conversion and numerical work. Count supplied anchors, schedule rows inspected, generated months, one vector interpolation and output size honestly. Pin small and larger ranges and the absence of publication, market/history reads, rate-curve construction and dense daily expansion. Storage follows the schedule-resolution work, anchors and generated months, not all intervening days. Report actual before/after work and allocation evidence; no timing gate or caching framework.

Run the full repository gate. Existing rate interpolation and market behavior must remain unchanged. A successful feature PR includes the worksheet function and help, the library implementation, focused numerical/seam/performance tests, its integration example, and one maintained utility page linked from the utility index. Link that page from this ticket and the UAT note when built, following the [documentation ownership map](../../seam/working.md#10-what-each-page-owns).

## Scope and sequence

This is one feature PR with one public function. It comes before multiple discount curves inside a trade array and does not depend on that work or the cross-gamma implementation. Keep ticket/reference-data hygiene for its separate discussion around quoting.

Seasonal interpolation, curve fitting, strip-average constraints, bid/ask/theo quote sets, market depth, sparse-anchor hedge risk, automatic market construction and changes to trade valuation are outside this ticket. An inferred monthly range, the index's expiry dates and a visibly paired contract/expiry/price spill are the complete first step.
