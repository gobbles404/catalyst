# Select trade quantity units from index specifications

[Pipeline overview](README.md) · [Trade creation](create-trade.md) ·
[Instrument definitions](00-instrument-definitions.md) · [Show instrument](../../library/instruments/show-instrument.md)

**Status:** Agreed 5 October 2026; ready for implementation. This ticket changes the
trade implementation in PRs #136–#144, reviewed through `7650bfe`. Implement as one focused
PR on the completed trade stack while it remains open, or on main once it contains that
stack. This ticket supersedes the two-field quantity selection in the earlier pipeline
pages; update those pages with the implementation.

## Outcome

Use `quantity_unit` to select a named row from the supplied index's contract specifications.
Remove `contract_specification` as a separate future field. The index remains the owner of
the available quantity definitions, and trade creation resolves the selection once.

Today, booking two ICE PHH lots requires `contract_specification = ICE PHH`,
`quantity_unit = LOT` and `quantity = 2`. After this change, it requires
`quantity_unit = ICE PHH` and `quantity = 2`.

The index's `ContractSpecifications` object and its constructor stay as they are. Its names,
sizes, units and fee metadata remain reference data. Selecting a row does not choose the
schedule method, settlement method, clearing house or payment terms, and fees remain reserves
outside trade valuation.

## Example

Suppose the index contains these specification rows:

| name | lot_size | lot_unit |
|---|---:|---|
| NYMEX NG | 10000 | MMBTU |
| ICE PHH | 2500 | MMBTU |
| MMBTU | 1 | MMBTU |

These quantity entries resolve as follows; other required trade fields are omitted here:

| quantity | quantity_unit | Resolved quantity |
|---:|---|---:|
| 2 | NYMEX NG | 20000 MMBTU |
| 2 | ICE PHH | 5000 MMBTU |
| -2 | ICE PHH | -5000 MMBTU |
| 5000 | MMBTU | 5000 MMBTU |

Each line illustrates a possible selection. The existing restriction to one selected
specification per batch remains. A bare unit such as `MMBTU` is accepted only if the index
actually has a specification with that name; the global unit-conversion table does not
create an implicit choice.

## Surface and validation

The pipeline signatures remain:

```text
_CreateTradeTemplate(instrument, fields, values)
_CreateTrades(index, fields, trade_rows, template)
_PrepareTrades(trades, history)
_EvaluateTrades(prepared, market)
_ReportValues(results)
_ReportRisk(results)
```

1. **Instrument definition.** Remove `contract_specification`. Keep `quantity_unit` required
   and define it as text selecting a specification by name. `_ShowInstrument("future")`
   keeps its existing transposed layout. Its options/rule describe "names in the supplied
   index's contract specifications"; it cannot enumerate an index's names because it takes
   no index. Remove the fixed `LOT` choice and describe quantity as a count of the selected
   quantity definition.
2. **Template creation.** A template can retain `quantity_unit`, but has no index against
   which to check membership. The seam checks nonempty text; defer membership validation to
   `_CreateTrades`. Remove the intrinsic `LOT` check. Reusing a template with another index
   succeeds only when that index contains the selected name; the supplied index owns the
   meaning and size of that selection.
3. **Trade creation.** After completing the template and ticket, require one `quantity_unit`
   for the batch. Look it up exactly in `index.specifications.names`, using the existing
   specification-selection mechanism. No trimming, case folding, aliases, first-row fallback
   or inference from `lot_unit`. Unknown names fail with the field, supplied value and valid
   index names; identify the ticket row when applicable. Retain the resolved selection.
4. **Entry rules.** `quantity_unit` may come from the template or the ticket, never both,
   even if the values agree. Unknown headers and duplicates still fail. A ticket column
   must contain the same selection on every row; supporting mixed selections in one batch
   is separate work.
5. **Cutover.** `contract_specification` becomes an unknown field in templates and tickets.
   `LOT` has no special meaning or compatibility fallback; it is accepted only if an index
   explicitly defines a specification named `LOT`.

## Resolution and encoding

Resolve the specification during `_CreateTrades`, then keep the existing numerical path:

```text
selected = index.specifications[selected_row]
quote_quantity = quantity * selected.lot_size
                 * conversion(selected.lot_unit, index.quote_quantity_unit)
coefficient = quote_quantity * quote_currency_unit_to_settlement_currency_unit
offset = -coefficient * fixed_price
```

The currency factor is the existing unit conversion, such as CENT to USD. Observation
weights and compression consume these coefficients as before. Under `quantity_per = month`,
a strip applies the entered quantity to every constituent month as it does today.

Keep one authoritative resolved specification selection, the index by reference, and the
information needed to explain the chosen name in readback. An internal specification-row
reference is still useful; removing the worksheet field does not remove that relationship.
Do not retain two independently editable selectors. Rename private quantity fields or
helpers where calling every entered quantity an exchange lot would now misstate its meaning.
Retain the existing owned, read-only arrays; readers project this state without rebuilding it.

Preparation, evaluation and reports must not look up specification names or repeat unit
conversion. Price ticks continue to consume the prepared arrays. Market/history identity,
dated slots, payment handling, risk vectors and result meanings are unchanged.

The existing finite, signed, nonzero, whole-number quantity rule remains for this slice.
Adding fractional quantities requires a separate decision; accepting a specification named
`MMBTU` does not silently introduce different numeric rules.

Update both the template's field readers and the resolved-terms validation: neither may
retain a literal `quantity_unit == LOT` gate. The principal implementation areas are the
instrument definition, template readers, resolution and terms, followed by trade readbacks;
the encoding already has the selected-row size and unit conversion this change needs.

## Documentation and workbook cutover

Update the instrument catalog, template/trade help and function pages, current pipeline
decisions, examples, fixtures, host/smoke cases and kept workbook together. Old NG and PHH
examples move the former specification name into `quantity_unit` and remove the old field.

`util_ReadHandle` for templates and trades must show the selected name under `quantity_unit`.
The trade spill removes the separate `contract_specification` column while retaining
quantity, resolved quote quantity, coefficient and offset. Update shifted column references
and spill assertions deliberately. Prepared/results readbacks and the two report layouts
keep their current meanings.

Update present-tense documentation and examples; do not rewrite archived design history or
add compatibility aliases. State the new meaning of `quantity_unit` consistently wherever
the old literal `LOT` rule is described.

## Acceptance

| Case | Required result |
|---|---|
| Instrument discovery | Future has one required `quantity_unit` selector, no `contract_specification`; Show explains index-supplied choices without changing its layout or signature. |
| Index-neutral template | A template accepts a nonempty name without an index. Creation succeeds with an index containing it and fails with an index lacking it. |
| Selection errors | Unknown names, missing fields, conflicting row selections and template/ticket overlap fail visibly. Case or whitespace changes fail when the resulting exact text is not itself a defined name. Old field names fail as unknown. |
| No implicit units | A globally known unit absent from the index's specification names fails. An explicitly defined size-one unit succeeds. Test `LOT` absent and explicitly defined. |
| Non-first specification | Use an NG index with NYMEX NG first and ICE PHH second. Two PHH units encode 5000 MMBTU, not 20000. At fixed price 3.00 and live price 3.10, mark is 500 and delta is 5000. A 3.20 pen fixing gives 1000 fixed-unpaid mark, then 1000 cash on payment, with zero delta after fixing. |
| Selected size and unit | Include a second specification whose lot unit differs from the first. Pin both row selections independently; choosing row zero's size or unit must fail the tests. Include a CENT/USD case where quote quantity and coefficient differ, including their readbacks and risk labels. |
| Equivalent quantities | Different selections representing the same underlying quantity, with all other economic terms equal, produce equal values and risk. |
| Quantity and strips | Signed whole quantities and explicit size-one units follow the same encoding path. Zero, fractional and nonfinite quantities remain refused. Monthly strips retain per-month quantity semantics. |
| Cardinality and compression | One trade follows the same path as many; duplicates count, ticket order does not change economics, and a compatible batch equals its summed singletons. |
| Cutover equivalence | Migrated NG, PHH and WTI examples preserve mark, cash, dates and risk. Preserve independent financial expectations; do not regenerate answers to make the field change pass. |
| Excel dependency path | Changing a template or ticket selection creates the corresponding new trade/preparation/result chain. A price-only update still reuses preparation. Unknown selection publishes no trade handle. |

Keep existing work budgets and add meaningful coverage for the new lookup boundary. Record
any changed creation/seam counts; preparation and tick work must not gain specification
lookup or quantity conversion. Run `check.ps1`, including the host, Excel smoke and trades
lifetime checks, and verify the migrated kept workbook's formulas and spills in Excel.

Follow the repository's separate-review rule for changes to existing goldens. This is one
field-selection change, not a new product catalog, fractional-quantity feature, mixed-spec
batch feature, or change to settlement, valuation or risk.
