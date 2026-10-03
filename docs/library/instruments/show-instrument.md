# _ShowInstrument

Draft for owner and engineering review. Not implemented; the proposed future fields and seam declaration have not passed the function-page review gate.

Shows one library-defined instrument schema as one row per field, with a name and description. This is
the read-only counterpart of [_ListInstruments](list-instruments.md).

## Worksheet contract

```python
def _ShowInstrument(
    instrument: Annotated[str, "One instrument name from _ListInstruments, such as future."],
) -> MixedArray: ...
```

Excel formula:

```excel
=_ShowInstrument("future")
```

`instrument` is the exact catalog identifier as text, or a reference to its cell in the list.
No instrument handle, index, template or market argument is required. The seam checks the
declared text input and mixed-table output: [inputs](../../seam/inputs.md) and
[outputs](../../seam/outputs.md).

Following the user's layout preference, fields run down rows. The seven columns are `field`,
`description`, `required`, `required_when`, `type`, `options`, `rule`, in
that order. The first row is that header; subsequent rows describe fields in the definition's
declared order. Required flags are Excel booleans; all other cells
are nonempty text. There are no spacer rows, blank placeholders,
object handles or additional implementation-type row.

Candidate contract-based future schema, for discussion. A template supplies defaults for
recognized trade fields; the selected traded product/agreement constrains the resolved values:

| field | description | required | required_when | type | options | rule |
|---|---|---|---|---|---|---|
| trade_id | External label identifying the deal | FALSE | none | text | no fixed list | Duplicate labels retain separate occurrences |
| trade_date | Date the deal was executed | TRUE | none | date | no fixed list | Explicit executed date; never inferred from as-of or today's date |
| index | The economic reference named by the deal | TRUE | none | index reference | compatible static reference | No market snapshot dependency |
| contract_specification | The selected reference lot/product specification | TRUE | none | text | selected index's specifications | Identify the intended reference specification explicitly |
| contract_code | The particular contract held or referenced | TRUE | none | text | selected schedule | One contract in the first supported profile |
| route | The actual trade's clearing arrangement | TRUE | none | code | cleared, bilateral | Must be supported for the selected traded product/agreement |
| settlement_method | The actual trade's final settlement form | TRUE | none | code | physical, financial | Actual trade terms; not automatically the reference contract's settlement form |
| clearing_house | The clearing organization for this trade | FALSE | route = cleared | reference | compatible clearing organization | Distinct from clearing firm/account; constrained by the actual route |
| broker | The broker recorded for the deal | FALSE | none | text | no fixed list in this sketch | Attribution; no fees or clearing role inferred from the label |
| quantity | Signed size of the position | TRUE | none | number | by supported profile | First NG profile: whole nonzero lots; no universal lot-integrality rule for bilateral extensions |
| quantity_unit | How the supplied quantity is measured | TRUE | none | code | by supported profile | First NG profile: LOT; later units require supported conversions |
| trade_price | The price agreed when the deal was executed | TRUE | none | number | no fixed list | Finite number in the defined quote units |

`future` here is a proposed desk family organized around a specified reference contract. A
bilateral lookalike can share this schema while retaining its own contractual treatment.
The table does not assert that every route/settlement pair is available or supported for every
reference. The first implementation remains a single NG case. See the
[field sketch](../../engineering-tickets/trade-valuation-pipeline/instrument-field-sketch.md)
for reference-versus-traded-product identity and the separate payment/margin rules still needed.

This is a schema proposal, not a change to the existing local `_CreateFuturesTrades` API.
`quantity` plus `quantity_unit` preserves the vocabulary in the user's example. For the first
NG future profile, the suggested unit is the instrument-level code `LOT`; the selected
specification supplies the quantity per lot. `LOT` is not a physical-unit category in the
existing unit-conversion tables. Choosing this surface instead of the local prototype's
`signed_lots` remains a field-review decision. Do not imply arbitrary physical quantities
are accepted until their conversion and lot-integrality rules are specified.

`contract_code` is proposed in place of `future_month` to match existing schedule terminology.
The first scope accepts one explicit monthly contract; a strip such as `cal27` is not
silently accepted. Strip syntax, constituent expansion and quantity allocation need their
own supported contract before such values appear as allowed inputs.

`contract_specification` identifies the lot/product specification because an existing `Index`
can contain several named specification rows. It is distinct from the monthly contract code.
Another explicit product-selection input could eventually supply this fact; do not guess the
first specification based on array order.

The field list is the logical instrument schema, not a declaration that all these fields must
be repeated in every ticket row. The future `CreateTrades` contract will establish which
facts arrive as shared arguments, template defaults and row columns.

## Excel help

| Item | Text |
|---|---|
| Function | Shows an instrument's fields, requirements, types and rules. |
| instrument | One instrument name from _ListInstruments, such as future. |

## The library checks

The identifier must be present in the same catalog `_ListInstruments` reads. Matching is
exact: no trimming, case folding, aliases or guessing. An unknown identifier fails with
the choices in catalog order. For the proposed one-instrument catalog:

```text
instrument is 'Future', expected one of: 'future'
```

An empty catalog gives:

```text
instrument is 'future', expected a listed instrument; none are defined
```

The seam's existing blank/missing/type errors apply before lookup. A failure publishes no
partial spill and creates no object. Optionality of trade fields is unrelated to the required
`instrument` argument of this reader.

## The schema columns

- `field`: canonical field identifiers, unique and in the definition's declared display order.
- `description`: the field's economic or recording meaning in plain language.
- `required`: whether the fact must always be present after defaults and static
  references have been resolved. TRUE does not require another cell on every ticket. FALSE
  does not by itself allow omission: `required_when` can still make the field mandatory.
- `required_when`: an additional condition making a field mandatory; `none` when absent.
  Conditions apply to the resolved values, including defaults. A supplied zero is
  present. Displayed conditions describe library-owned rules, not user-authored expressions.
- `type`: the semantic type of the eventual resolved input, not the storage dtype of the
  metadata cell. For example, `index reference` describes a trade input; this reader neither
  looks up nor publishes such a reference.
- `options`: the fixed allowed choices or the source of contextual choices. `no fixed list`
  and similar display phrases are explanatory text, not valid ticket values. A generic
  instrument reader cannot enumerate a selected index's contract codes without that index.
- `rule`: meaning and constraints beyond field type/options, including restrictions imposed
  by a selected traded product/agreement. Independently valid values can form an invalid pair.

A fact is mandatory when `required` is TRUE or its `required_when` condition holds. Validate
supplied values even when optional; do not replace missing facts with zero or empty text.
The default/override precedence belongs to trade construction. A template is a partial set
of defaults for recognized fields, with no separate field-permission policy. The resolved
trade satisfies the same rules regardless of which values came from a template or ticket.
Product constraints still apply; a template does not change what a selected product means.

The reader projects metadata from the shared instrument definition. Validation remains with
the appropriate owner: schema rules at construction, reference-data integrity in definition
constructors, relationship checks during static resolution, and market coverage at binding.
Descriptions must reference those rules; parsing prose from this spill is not a validation
mechanism. Editing or copying the spill does not alter the library definition.

When a future template/reference inspector is specified, it can show selected defaults,
resolved units and remaining ticket inputs. Keep those contextual operations separate from
this generic schema reader for now.

## Treatment of the earlier field list

| Earlier field | Proposal for review |
|---|---|
| trade_id | Keep optional attribution; occurrence identity always preserves every row |
| index | Keep the required static economic reference; no market snapshot dependency |
| future_month | Use contract_code with explicitly supported syntax |
| quantity, quantity_unit, trade_price | Keep their meanings explicit; first quantity profile proposed above |
| broker | Retain optional attribution as in the user's ticket; no pricing effect inferred |
| counterparty, marketer | Candidate attribution fields; add when their meaning and retention are agreed |
| clearing_house | Distinguish the clearing house from a clearing firm/account; agree whether selected specifications supply or constrain it |
| marketing_reserve | Defer until defined: currency/units, per-unit versus total, sign, and whether it changes value or is reporting-only |
| trade_date, contract_specification | Add the missing executed date and unambiguous specification selection |

Omitted candidates are not silently supported or discarded at ingestion. The eventual
constructor must reject fields absent from its approved schema. Final settlement belongs
to the actual traded product/agreement; price/quantity units come from the applicable static
definitions. This generic reader describes the domains without choosing or overriding facts.

The newer legacy template also supplies floating/curve sources, observation and payment
scheduling, spreads and conversion controls. Their proposed ownership and unresolved meaning
are recorded in the [field sketch](../../engineering-tickets/trade-valuation-pipeline/instrument-field-sketch.md).
They are not all new inputs to the future schema above.

## Tests

These are implementation acceptance cases, not new tests added by this documentation change.

| Case | Kind |
|---|---|
| Future produces the agreed seven headers and ordered field rows | Example |
| Required cells arrive as Excel booleans, not strings or numbers | Example through the seam |
| Conditional and option descriptions match library-owned rules; absent conditions display none | Example |
| Every listed identifier maps to exactly one inspectable schema | Property across the shipped catalog |
| Unknown/case-changed identifier, and empty catalog, produce the specified errors | Example |
| One-field definition produces a header plus one row; no special reader path | Example |
| Repeated calls neither create handles nor access trade/market state | Example and work budget |
| Real Excel displays descriptions and Boolean requirements in their columns | Excel smoke |

This shape has text columns and one Boolean column and fits the existing `MixedArray` result
contract. Verify the declaration and formatter through the normal seam review before
declaring it ready; formatting a schema does not require adding a new result-handle type.

## Not here

Template construction, ticket ingestion, static encoding, product-specific choice expansion,
market binding and valuation. The schema spill is descriptive metadata, not an executable
template table to pass back verbatim as trade rows. No caller-supplied schema changes which
instrument definitions the library accepts.
