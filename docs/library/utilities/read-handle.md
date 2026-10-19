# util_ReadHandle

Built in #66.

Reads the object a handle stands for onto the sheet as a table, a header row, a row of types, then one row per element: the table its creator took, or, for a curve, the daily table the creator built from the anchors it took, every day between them. It is how a person sees what is in memory, checks a block before stacking the next one on it, and hands an engineer the exact thing a formula holds. `util_ReadDiscountFactor` went with it: it existed only to prove that a handle resolves, and reading a whole curve proves that better than reading one day of it. The code is `src/goosedove/excel/utilities.py`, the function and the table each kind shows.

## Worksheet contract

```python
def util_ReadHandle(handle: Handle[object]) -> MixedArray: ...
```

`Handle[object]` is the seam's form for a handle of any kind, built in #64 ([inputs.md](../../seam/inputs.md) decision 40): the function receives the object whatever its kind, and every failure keeps the seam's words with no kind to name. `MixedArray` as a result is the mirror of the way in, built in #65 ([outputs.md](../../seam/outputs.md) decision 13): the rectangle spills one tagged value per cell, and `MixedArray.table` builds it from the headings and the object's columns, or, for the market history's and the market's columns of two kinds, one helper composes the record's three fields.

| | A | B |
|---|---|---|
| 1 | date | discount_factor |
| 2 | 11-Sep-2026 | 1 |
| 3 | 12-Sep-2026 | 0.9999 |
| 4 | 13-Sep-2026 | 0.9998 |
| 5 | `=_CreateDiscountCurve("SOFR", A1:B1, A2:B4)` | shows `30512:discount_curve:SOFR:2` |
| 7 | `=util_ReadHandle(B5)` | spills A7:C11, below |

| | A | B | C |
|---|---|---|---|
| 7 | date | discount_factor | name |
| 8 | datetime64[D] | float64 | str |
| 9 | 11-Sep-2026 | 1 | SOFR |
| 10 | 12-Sep-2026 | 0.9999 | SOFR |
| 11 | 13-Sep-2026 | 0.9998 | SOFR |

One argument, required: any live handle, the cell showing a creator's result or a name for it. The seam resolves it to the object, and every failure is the seam's, in the seam's words: a number or a blank where the handle should be, text naming no live object, or a creator's failure relayed by the reference. The result spills as returned: dates go out as Excel dates, serials the sheet formats, as every date the seam sends does, so a fresh column shows `46276` until it is formatted once; the row of types says which columns to format. Rows 7 and 9 to 11 are the daily table `_CreateDiscountCurve` built, which as anchors with no gaps is one it takes, with the curve's name on every row, last, so that every positional read of the two columns stands; `=_CreateDiscountCurve(C9, A7:B7, A9:B11)` makes an equal curve under the same name: a spill can be fed back to a creator. A curve built from sparse anchors spills its days, not its anchors, since #70.

## Excel help

Quoted from the declaration in `src/goosedove/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Reads the object behind a handle and spills it as a table: its headers, a row of types, then one row per element. |
| `handle` | The cell showing any creator's result, such as B5, or a name for it. |

## The library checks

None. Every kind the library publishes has a table, so there is no object the inspector cannot show, and a handle that resolves is shown; a handle that does not resolve fails in the seam's words before the function runs.

## The table

The first row is the headers, in the creator's own words: the headers its table took, or its parameter names. The rows are what the object holds, which for a curve is every day the creator filled between its anchors. The second row is the type of what the object holds in each column, in numpy's words where numpy holds it and Python's where Python does. Then one row per element, aligned across the columns as the object aligns them; a scalar field is a column of one row. A column holds one kind, the one its type names, except where a kind says otherwise: the market history's `fixing_price` is a number on a day that fixed and a word on a day that did not, since #84, and the market's `price` a number on every business day and a word on the rest, since #86, their type the number's, since the words are display, not values, and since #172 a trades spill's `entered_contract_code` and a template spill's period field whose cell held nothing show `(not supplied)`, words where no value stood. A column the creator was given none of is not shown, and what a kind keeps only to make a lookup fast, such as the curve's day count of its start, is not a fact of the object and is not shown. Nothing is sorted, rounded or reformatted.

What each kind shows:

| Kind | Headers | Types | Rows |
|---|---|---|---|
| `valuation_date` | `as_of`, `day_fraction_elapsed` | `datetime64[D]`, `float` | one |
| `discount_curve` | `date`, `discount_factor`, `name` | `datetime64[D]`, `float64`, `str` | one per calendar day, the anchors and every day filled between them, the curve's name on every row, last |
| `discount_curve_set` | `name`, `start_date`, `end_date`, `days` | `str`, `datetime64[D]`, `datetime64[D]`, `int64` | one per curve in the order given, its name, its first and its last day and the days between, inclusive; the daily factors are each curve's own handle's to spill; [collect-discount-curves.md](../globals/collect-discount-curves.md) |
| `futures_schedule` | `contract_code`, `future_expiry`, then `option_expiry` when the index has options | `str`, then `datetime64[D]` per date column | one per contract |
| `holiday_calendar` | `holiday` | `datetime64[D]` | one per holiday |
| `iferc_schedule` | `contract_code`, `publication_date`, two columns since #204 | `str`, `datetime64[D]` | one per contract month |
| `gas_daily_schedule` | `contract_code`, `first_date`, `last_date` | `str`, `datetime64[D]`, `datetime64[D]` | one per contract month |
| `index_conventions` | `quote_currency_unit`, `quote_quantity_unit`, `currency_unit`, `quantity_type`, `quantity_unit` | `str` five times | one |
| `contract_specifications` | `name`, `lot_size`, `lot_unit`, `brokerage_rate_per_lot`, `clearing_rate_per_lot` | `str`, `float64`, `str`, `float64`, `float64` | one per word for a quantity |
| `index` | `name`, `display_name`, `kind`, `contracts`, `specifications`, `has_holiday_calendar`, `reporting_lot`, and with a lot named `lot_size`, `lot_unit`, `lot_quote_quantity`, `lot_coefficient` | `str`, `str`, `str`, `int64`, `int64`, `bool`, `str`, then `float64`, `str`, `float64`, `float64` | one, a summary of what the index holds, since #169 the display name beside the name, the kind spelled `futures`, `IFERC` or `Gas Daily`, since #164 the reporting lot's name or `unset` and, named, its size, its unit, one lot in the quote quantity unit and the settlement currency a live lot makes per unit of quote price; the parts spill through their own handles |
| `futures_fixings` | `date`, `settle` | `datetime64[D]`, `float64` | one per fixing, newest first since #128, the order the creator takes and the sheet gave, each settle beside its own day; the fixings keep the columns oldest first, and the spill reads them from the last row back |
| `iferc_fixings` | `contract_code`, `price` | `str`, `float64` | one per month published, newest first since #147, the order the creator takes and the sheet gave, each price beside its own code; the fixings keep the columns oldest first, and the spill reads them from the last row back |
| `gas_daily_fixings` | `flow_date`, `price` | `datetime64[D]`, `float64` | one per calendar day, weekends and holidays included, newest first since #128, as the creator takes them |
| `price_vector` | `price` | `float64` | one per price, in the column's order |
| `market` | the calendar's four, then `price` | the calendar's four, then `float64` | one per calendar period through the last period of the last contract quoted, every row the calendar has when the quotes reach the schedule's end and no row past them when they stop before it, since #127; the fifth cell the fixing on a fixed and priced period, its contract's quote on an unfixed period, and the word `closed` where the calendar does not price the day, a futures weekend or holiday |
| `calendar` | `date`, `contract`, `is_priced`, `is_fixed` | `datetime64[D]`, `str`, `bool`, `bool` | one per calendar day from the day after the first contract's expiry to the last's on a futures calendar, one per flow day on a Gas Daily calendar, one per contract month on an IFERC calendar |
| `market_history` | the calendar's four, then `fixing_price` | the calendar's four, then `float64` | one per calendar period, every row the calendar has; the fifth cell the price fixed, a number, on a fixed and priced period, the word `closed` where the calendar does not price the day, a futures weekend or holiday, and `unfixed` where it prices but has not fixed, whatever market the calendar is of |
| `trade_template` | `instrument`, then each field the row named under its name in the sheet's order | `str`, then each by its field's type, a holiday calendar as the words of its kind, and since #172 `str` under a period field whose cell held nothing, the cell the words `(not supplied)` | one row, since #139; [trade-template.md](../trades/trade-template.md) |
| `quote_template` | `instrument`, then each field the row named under its name in the sheet's order | `str`, then each by its field's type, a holiday calendar as the words of its kind; every cell a value, no period field standing in a quote template | one row, since template-based-quoting.md; [quote-template.md](../quoting/quote-template.md) |
| `trades` | `row`, then the resolved terms under the definition's field names in its order, `trade_id` to `payment_date`, the ID as a number since #168, the labels, since #175 `counterparty` among them and since the named-curve arc's slice 3 `discount_curve_key` after it on a bilateral batch, and the payment fields where the batch has them, and since #175 `marketing_reserve` where it has that, the row's one amount on each of its components, then since #172 `entered_contract_code`, the code text the row entered or `(not supplied)`, apart from `contract_code`, the contract the resolution bound, then `start_date`, `end_date`, `covered_days` and `component_quantity`, the first and the last day each component covers, the days between them and the quantity the basis gives it, since #159 and #161, then `quote_quantity`, `coefficient`, `offset` | `int64` for the row, then each by its field, then `str`, `datetime64[D]` twice, `int64` and `float64` four times | one per component, each month of a strip its own row carrying the ticket's row number, since #139; [create-trades.md](../trades/create-trades.md) |
| `prepared_trades` | `pricing_contract`, `booked_contract`, `observation_date`, `payment_date` for a financial settlement, `is_fixed`, `is_settled`, `live_coefficient`, `live_lots` | `str`, `str`, `datetime64[D]`, `datetime64[D]`, `bool`, `bool`, `float64`, `float64` | one per slot of the dated axis, since #141, the contract pricing the day and the contract the slot's group was booked on, apart under `asian` since #165, the day its payment group pays beside the observation day since #162, a physical settlement showing none, the coefficient the settlement currency the slot's price moves the mark by and the lots the same in lots of the index's reporting lot since #164; [prepare-trades.md](../trades/prepare-trades.md) |
| `trade_results` | `pricing_contract`, `booked_contract`, `observation_date`, `payment_date` for a financial settlement, `is_fixed`, `live_coefficient`, `live_lots`, `live_contribution`, `contract_sensitivity`, `contract_nominal_delta`, `sensitivity_unit`, `lot_unit`, then since #170 `brokerage_reserve`, `clearing_reserve`, `marketing_reserve`, `currency`, then since #197 `contract_cross_gamma` and `cross_gamma_unit`, then since the named-curve arc's slice 3 `discount_curve_key` and `discount_curve`, the slot's group's key and the name of the curve the group was discounted on, a dash for a cleared batch | `str`, `str`, `datetime64[D]`, `datetime64[D]`, `bool`, then `float64` five times, then `str` twice, then `float64` three times and `str`, `float64`, `str`, `str`, `str` | one per slot, the two contracts apart since #165, the pricing contract's sensitivity and its delta in lots beside each of its slots, since #141 and in lots since #164, the payment day since #162, and the two units the risk numbers are in, the batch's on every row so that a row reads whole, and since #170 the batch's reserves once, on the first slot row, a dash on every later row, [report-reserves.md](../trades/report-reserves.md); [evaluate-trades.md](../trades/evaluate-trades.md) |
| `cashflows` | `trade_id` where the batch has it, `trade_date`, `amount`, `currency`, `payment_date`, and `counterparty` and `description` where it has them | `int64`, `datetime64[D]`, `float64`, `str`, `datetime64[D]`, `str`, `str` | one per payment booked, in the ticket's order, the template's value on every row, since #200; [create-cashflows.md](../cashflows/create-cashflows.md) |
| `cashflow_results` | `payment_date`, `amount`, `is_paid`, `payment_factor`, `npv`, `cash`, `dv01`, `currency`, `as_of`, then `cashflow_mark`, `cashflow_cash`, `cashflow_dv01` | `datetime64[D]`, `float64`, `bool`, `float64` four times, `str`, `datetime64[D]`, then `float64` three times | one per distinct payment day, increasing, paid or not, the rows' amounts summed on the day, the currency and the valuation day on every row, and the batch's three totals once, on the first row and a dash below, since #200; [evaluate-cashflows.md](../cashflows/evaluate-cashflows.md) |
| `aggregate_results` | `position`, `index`, `reporting_lot`, `route`, `curve`, `currency`, `nominal_delta`, `delta`, `dv01`, `as_of`, `cross_gamma`, `cross_gamma_unit` | `int64`, `str` five times, `float64` three times, `datetime64[D]`, `float64`, `str` | one per source in the order given, a repeat a row again, since #180, each source's saved totals and the day every source shares, the `curve` cell the heading's word for the source's curve, `SOFR` or `SOFR (curve_2)`, and a dash for a cleared source; since the named-curve arc's slice 2 a batch of cashflows a row too, `cashflow` under the route, its curve's word, its currency and its DV01, and a dash under the index, the lot, the deltas, the cross-gamma and its unit; [aggregate-results.md](../trades/aggregate-results.md) |

`=util_ReadHandle(B2)` on `=_CreateValuationDate(A2, 0.5)`:

| as_of | day_fraction_elapsed |
|---|---|
| datetime64[D] | float |
| 11-Sep-2026 | 0.5 |

`=util_ReadHandle(A8)` on the six-contract schedule of [futures-schedule.md](../index-definitions/futures-schedule.md) built with its options; the same schedule built without options shows the first two columns alone:

| contract_code | future_expiry | option_expiry |
|---|---|---|
| str | datetime64[D] | datetime64[D] |
| m26 | 19-May-2026 | 14-May-2026 |
| n26 | 22-Jun-2026 | 16-Jun-2026 |
| q26 | 21-Jul-2026 | 16-Jul-2026 |
| u26 | 20-Aug-2026 | 17-Aug-2026 |
| V26 | 22-Sep-2026 | 17-Sep-2026 |
| X26 | 20-Oct-2026 | 15-Oct-2026 |

`=util_ReadHandle(A12)` on the ten-day calendar of [holiday-calendar.md](../index-definitions/holiday-calendar.md) shows one column, `holiday` over `datetime64[D]`, then the ten days as given.

A new kind adds its row to this table on the pull request that builds its creator, and the same row in code: each kind registers how it shows in `src/goosedove/excel/utilities.py`, and a kind nobody registered fails in the cell, `#ERROR util_ReadHandle: TypeError: no table for a Widget`, rather than guessing its columns.

## Tests

The tests are `tests/unit/test_utilities.py`, through the seam; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1`, reading each spill with `INDEX`, and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| a valuation date: the two headers, the two types, one row, the date and the fraction exactly | example |
| the three-day curve: the three headers, the three types, three rows, dates as serials, factors exactly and the name on every row | example |
| a collection of curves: one row per curve in the order given, the name, the span as serials and the days; a collection of one | example |
| the six-contract schedule with options: three columns; without options: two | example |
| a three-day calendar: one column of dates under its two heading rows | example |
| the IFERC schedule: three headers, three types, then a code as text and two dates as serials per contract month | example |
| the Gas Daily schedule: three headers, three types, then a code as text and a month's first and last day as serials per contract month | example |
| index conventions: one row of five texts under its two heading rows | example |
| contract specifications: one row per contract, the name as text and the lot size and fees as numbers, under its two heading rows | example |
| the index: one row, the name, the display name and the kind as text, the two counts as numbers and the holiday flag a boolean, with a holiday calendar and without | example |
| futures fixings: two columns, dates as serials and settles exactly, one row per day in the order given, newest first, under its two heading rows | example |
| IFERC fixings: two columns, codes as text and prices exactly, a zero and a negative in their places, one row per month newest first, as the creator takes them, over a schedule running the other way, under its two heading rows | example |
| Gas Daily fixings: two columns, flow days as serials and prices exactly, newest first, a Friday under the three rows its print covers, under its two heading rows | example |
| each kind of fixings' spill, its two columns fed back to its creator, gives fixings with the same kept columns and the same spill, every price beside its own date or code, in `tests/unit/test_market_data.py` | example and property, through the seam |
| a price vector: one column of prices under its two heading rows, a zero and a negative price in their places | example |
| a market of one day: the quote a number on the open day, `closed` as text when the day is a holiday; a Gas Daily and an IFERC market of one month, the print or the index where fixed and the quote elsewhere; and for any history of any of the three kinds with any count of quotes from one to the contracts that remain, the calendar's rows through the last contract quoted and every period's fixing, quote or `closed` | example and property |
| the calendar: four columns, the day as a serial, the code as text and the two flags as booleans, their kinds the boolean code | example |
| the market history: five columns, the calendar's kinds then a number on the fixed day and text on a day without a price, over a futures calendar and over the other two | example |
| a curve's spill, its name from a body row, its first two headers and its rows' first two cells, fed back to `_CreateDiscountCurve` gives a curve with equal dates, factors and spill | example, through the seam |
| for any valid curve of N days, the spill is N + 2 rows by 3 columns, headers first, types second, and row i + 2 holds day i, its factor and the name | property |
| a number, a blank, text naming no live object, a creator's failure relayed: the seam's words, and nothing spilled | example, through the seam |
| a kind with no table fails in the cell rather than guessing; every kind a creator publishes has one | example |
| each kind inspected on a real sheet, with a schedule without options, a calendar of one day, a history and a market over 34 days and a vector of four prices | Excel smoke |

## Not here

The kind's name and the handle's text: the creator's cell shows both, and the count is the spill's height. Formatting the spilled cells: the sheet's. A filter, a range of rows, or a second argument: the whole object spills, every time. Editing an object through its spill; the internals a kind keeps to make a lookup fast; the text of a handle typed by hand.
