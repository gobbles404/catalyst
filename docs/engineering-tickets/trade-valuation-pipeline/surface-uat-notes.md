# Trade surface UAT notes

[Pipeline overview](README.md) · [Bilateral discounting and DV01](bilateral-discounting-and-dv01.md)

Running list started 8 October 2026 while testing the trade prototype in Excel.
Record observations and decisions here before turning them into implementation tickets.

| Item | Owner direction | Status |
|---|---|---|
| 1. Delta reporting | Report delta in **lots**, using one explicitly designated specification per index, independently of trade entry units. | Agreed; [engineering ticket](lot-delta-reporting.md) drafted |
| 2. `trade_id` | Treat it as an **alphanumeric identifier**, rather than a quantity. | Proposed; entry details to confirm |
| 3. Start/end date helper inputs | Keep the worksheet arguments unchanged; allow dates as well as period labels to feed the trade's date fields. Preserve case-insensitive BAL entry. | Requested; date passthrough interpretation below; BAL labels already supported |

## 1. Delta reporting

For the fully live ETE example, `1 LOT`, `1000 BBL` and `42000 GAL` each represent
one lot of exposure. Three positive trades entered together represent three lots.

With a CENT/GAL quote and USD settlement, the current encoding produces a coefficient
of 420 USD per one-cent/gallon move per equivalent trade. That coefficient is useful
for valuation, but it is not the lot delta the owner expects to read. Preserve the
pricing arithmetic and distinguish its monetary sensitivity from the requested lot view.

The agreed reporting basis is one designated existing specification on the index.
Each entry specification already has its own size and unit; the reporting selection is
independent of which row a trade uses. Remaining Asian lot delta follows the live
observation weights. See [Report trade delta in index-defined lots](lot-delta-reporting.md)
for the recommended selection mechanism, calculation and acceptance cases.

The relationship to discounted monetary sensitivity remains a bilateral design choice.
The pending bilateral ticket's report contract must incorporate that distinction before
it is finalized.

## 2. Trade identifiers

In the reviewed prototype through #163, `trade_id` already accepts alphanumeric text,
text containing only digits, and punctuation. A numeric Excel cell is rejected as
the wrong type; accepting that cell would be a separate surface decision.

The proposed meaning of `trade_id` is an identifier that can contain letters and digits,
for example `ETE001`. Do not infer a letters-and-digits-only restriction, uniqueness rule
or automatic numeric-cell conversion from this note. Numeric Excel cells versus text
identifiers, preservation of leading zeros, and any character restrictions remain to
be clarified if relevant to UAT.

## 3. Dates and period labels through the same helpers

Keep the existing worksheet call shapes:

```text
util_StartDate(period, [reference_date]) -> date
util_EndDate(period, [reference_date])   -> date
```

Interpret the requested date support as accepting an actual Excel date in the first
argument and returning that date unchanged from either helper. Period labels keep their
existing meanings. This widens accepted input types without adding or reordering arguments;
engineering must provide the seam support rather than assume date-or-text is supported today.
Do not introduce parsing of date strings such as `10/08/26`.

| First input | Reference date | Start helper | End helper |
|---|---|---|---|
| Excel date 8-Oct-2026 | omitted | 8-Oct-2026 | 8-Oct-2026 |
| `v26` | omitted | 1-Oct-2026 | 31-Oct-2026 |
| `balv26` | 8-Oct-2026 | 8-Oct-2026 | 31-Oct-2026 |
| `BALV26` or `BalV26` | 8-Oct-2026 | 8-Oct-2026 | 31-Oct-2026 |

BAL already works case-insensitively in the prototype. Preserve that behavior and its
explicit reference requirement. A valid reference supplied with an ordinary label or an
explicit date does not change the result; supplied arguments still undergo normal validation.
Keep the helpers deterministic and nonvolatile, with existing missing/blank distinctions.

The helper outputs populate the ticket's `start_date` and `end_date` columns, with no
`contract_code` column. A BAL label can feed both helpers; independently entered start and
end dates feed their respective helpers. The booking reference stays fixed as market
`as_of` advances. These formulas do not snapshot a changing reference cell.

Acceptance should cover the table, existing BAL refusals, date validation through the seam,
and one worksheet example containing ordinary labels, BAL labels and explicit dates. This
is a helper-input extension; `_CreateTrades` and the trade-period rules stay as specified in
[Calendar day quantities and fixed BAL trade periods](trade-periods-and-bal.md).
