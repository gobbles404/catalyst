# _ShowInstrument

Agreed starting reader contract. Not implemented; the future schema and seam declaration remain subject to engineering verification.

Shows one library-defined instrument schema with fields across columns and metadata down
rows, including descriptions, requirements and defined options. This is the read-only counterpart of
[_ListInstruments](list-instruments.md). Both use the same private library definitions that
template and trade construction will consume.

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

Fields run across columns to align with trade-table headers. The first column contains the
seven row labels `field`, `description`, `required`, `required_when`, `type`, `options`,
`rule`, in that order. Each subsequent column describes one field in the definition's
declared order. For N fields, the spill has seven rows and N + 1 columns. In the first row,
field identifiers begin in column two; those cells match the names used as trade headers.
The `required` row contains Excel booleans after its text label; all other cells are
nonempty text. There are no spacer rows, blank placeholders, object handles or additional
implementation-type row. This is the default layout; no transpose argument is introduced.

Candidate contract-based future schema, for discussion. A template supplies defaults for
recognized trade fields; the selected traded product/agreement constrains the resolved values:

| field | trade_id | trade_date | index | contract_specification | contract_code | schedule_method | route | settlement_method | clearing_house | broker | quantity | quantity_unit | quantity_per | fixed_price | payment_time_lag | payment_holiday_calendar |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| description | External label identifying the deal | Date the deal was executed | The economic reference named by the deal | Name selecting the lot and quantity specification from the index | One monthly contract or a strip of monthly contracts | How observations determine the floating price | The actual trade's clearing arrangement | Descriptive final-settlement form of the actual trade | The clearing organization for this trade | The broker recorded for the deal | Signed size of the position | How the supplied quantity is measured | Whether quantity applies per month or per day | The fixed price agreed when the deal was executed | Business-day offset from the payment anchor defined by the supported product | Calendar supplying holidays for payment-day counting |
| required | FALSE | TRUE | TRUE | TRUE | TRUE | TRUE | TRUE | TRUE | FALSE | FALSE | TRUE | TRUE | TRUE | TRUE | TRUE | TRUE |
| required_when | none | none | none | none | none | none | none | none | route = cleared | none | none | none | none | none | none | none |
| type | text | date | index reference | text | text | code | code | code | reference | text | number | code | code | number | text | holiday calendar reference |
| options | no fixed list | no fixed list | compatible static reference | selected index's specifications | existing contract-period grammar, subject to index schedule coverage | asian, lastday, penultimate, last3day | cleared, bilateral | physical, financial | compatible clearing organization | no fixed list in this sketch | by supported profile | by supported profile | month, day | no fixed list | +1bd, +2bd and other positive whole-business-day offsets consistent with supported trade terms | compatible static payment calendar |
| rule | Duplicate labels retain separate occurrences | Explicit executed date; never inferred from as-of or today's date | No market snapshot dependency | Data is obtained through index; template can supply the selection; no separate specification handle | Proposed strip expansion: CAL27 is F27 through Z27; Z27-X28 is December 2027 through November 2028, inclusive | Library-defined rule selected by the trade; template may default it; exact and cfd excluded from v1 | Must be supported for the selected traded product/agreement | Retained product/trade fact; physical-delivery handling is outside v1; does not choose pricing observations or payment dates | Distinct from clearing firm/account; constrained by the actual route | Attribution; no fees or clearing role inferred from the label | First NG profile: whole nonzero lots; no universal lot-integrality rule for bilateral extensions | First NG profile: LOT; later units require supported conversions | Proposed: each contract month or each calendar day in the quantity period; independent of observation weights | Finite number in the defined quote units; applies to every monthly constituent of a flat-priced strip | Trade row or template supplies it; PHH uses +1bd and ETE uses +2bd; initially count eligible days strictly after the actual traded contract's last trading day | Reuse HolidayCalendar; Monday-Friday excluding listed holidays; independent of pricing calendar |

`future` here is a proposed desk family organized around a specified reference contract. A
bilateral lookalike can share this schema while retaining its own contractual treatment.
The table does not assert that every route/settlement pair is available or supported for every
reference. The existing ingestion prototype remains limited to individual contract codes. See the
[field sketch](../../engineering-tickets/trade-valuation-pipeline/instrument-field-sketch.md)
for the current schedule-method and quantity-basis proposals and separate payment rules.
Physical-delivery handling is outside scope. The
[accepted payment starting point](../../engineering-tickets/trade-valuation-pipeline/fixing-and-payment-state.md#cleared-payment-convention-selected-rule-and-resolved-date)
distinguishes the payment_time_lag input from derived payment_dates: PHH uses +1bd and ETE
uses +2bd. The supported product defines the actual traded contract's Last Trading Day as
the initial anchor and counts eligible days strictly after it. That cutoff is not necessarily
the reference contract's expiry. A trade row or template supplies payment_time_lag and the
existing HolidayCalendar handle as payment_holiday_calendar. CreateTrades parses the lag
once, then resolves and stores each monthly component's payment_date from these static
dependencies. There is no additional public payment-rule field, constructor or handle.
Positive whole business days are the initial scope; zero-day adjustment semantics and
broader bilateral payment terms remain deferred. This accepted starting design is not yet
implemented.

This is a schema proposal, not a change to the existing local `_CreateFuturesTrades` API.
`quantity` plus `quantity_unit` preserves the vocabulary in the user's example. For the first
NG future profile, the suggested unit is the instrument-level code `LOT`; the selected
specification supplies the quantity per lot. `LOT` is not a physical-unit category in the
existing unit-conversion tables. Choosing this surface instead of the local prototype's
`signed_lots` remains a field-review decision. Do not imply arbitrary physical quantities
are accepted until their conversion and lot-integrality rules are specified.

`contract_code` now proposes one month or a monthly strip using the existing period grammar.
Reuse `period_months` from `index_definitions/periods.py`, the library function behind
util_StartDate/util_EndDate, during creation. It already understands cal27 and z27-x28;
it does not yet create trade components or payment dates. Creation must enumerate the
constituent months and resolve every month unambiguously against the index's schedule.
Case-insensitive period parsing does not authorize ambiguous schedule identities or missing
months. No market prices are needed. Explicit start_date/end_date and exact remain deferred
while full-month strips cover the intended cases.

One strip ticket remains one trade occurrence with monthly components. quantity_per=month
applies the entered quantity to each month; quantity_per=day applies it to each calendar day
of each month under the proposed calendar-day convention. The same fixed_price and
schedule_method apply to each constituent. An Asian strip therefore has monthly averages;
it does not become one average over the entire strip. Resolve an explicit payment date per
component using payment_time_lag, payment_holiday_calendar and the supported product's
payment anchor. Monthly dates can differ; the period parser does
not provide them. Resolved payment_date is a stored component date, not a rule-valued date
field on the ticket. Direct payment-date override inputs are not specified by this
cleared-rule draft; exact pricing-date windows remain deferred.

`contract_specification` identifies the lot/quantity specification because an existing `Index`
can contain several named specification rows. It is distinct from the monthly contract code.
Another explicit product-selection input could eventually supply this fact; do not guess the
first specification based on array order.

The specification records already belong to Index. CreateTrades selects the named row from
index.specifications rather than taking another specifications object. A template can choose
that name once for its tickets. Index can contain several specifications, so index alone
does not select a lot size; do not infer the first row, or use quantity_unit=LOT to choose.
Static index references preserve market-independent creation: prices, fixings, history and
valuation as-of remain later dependencies.

`fixed_price` replaces `trade_price` in this proposed instrument schema. It is not an alias.
The existing _CreateFuturesTrades prototype still uses trade_price; renaming that implemented
API, its workbook and tests is separate implementation work, not performed by this draft.

The current method proposal and proposed library homes are in the
[field sketch](../../engineering-tickets/trade-valuation-pipeline/instrument-field-sketch.md#current-refinement-schedule_method-and-quantity_per).
The resolved trade owns its selection; library code defines the rule and static reference
data supplies its calendar and contract anchors. No independent pricing_convention field
or pen alias is proposed. The month/day meanings and method weights remain reviewable design
choices; no schedule implementation or prototype API change is included here.

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

## The metadata rows

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
Trade construction combines disjoint template fields and ticket columns. Any overlap fails,
including equal values; there is no override or per-field permission policy. The resolved
trade satisfies the same rules regardless of which values came from a template or ticket.
Product constraints still apply; a template does not change what a selected product means.

The field row is the complete set of permitted identifiers for that instrument. Template
and trade headers must match it exactly: case-sensitive, with no trimming, aliases or fuzzy
matching. Column order may vary. Unknown columns fail instead of being ignored or carried
as arbitrary metadata; optional fields remain subject to the same names, types and rules.

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
| quantity, quantity_unit, fixed_price | Use fixed_price for the agreed price; quantity basis is explicit and applies per monthly component |
| broker | Retain optional attribution as in the user's ticket; no pricing effect inferred |
| counterparty, marketer | Candidate attribution fields; add when their meaning and retention are agreed |
| clearing_house | Distinguish the clearing house from a clearing firm/account; agree whether selected specifications supply or constrain it |
| marketing_reserve | Defer until defined: currency/units, per-unit versus total, sign, and whether it changes value or is reporting-only |
| trade_date, contract_specification | Add the missing executed date and unambiguous specification selection |
| schedule_method, quantity_per | Retain these field names; library-defined methods and month/day quantity basis; exact and cfd outside v1 |
| settlement_method | Retain physical/financial identification; physical-delivery handling is outside v1 and does not set payment dates |

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
| Future produces seven metadata rows, with row labels in column one and fields in declared order across the remaining columns | Example |
| Required cells arrive as Excel booleans, not strings or numbers | Example through the seam |
| Conditional and option descriptions match library-owned rules; absent conditions display none | Example |
| Every listed identifier maps to exactly one inspectable schema | Property across the shipped catalog |
| Unknown/case-changed identifier, and empty catalog, produce the specified errors | Example |
| One-field definition produces seven rows and two columns; no special reader path | Example |
| Repeated calls neither create handles nor access trade/market state | Example and work budget |
| Real Excel preserves field headers across columns, metadata labels down column one and Boolean requirements in the required row | Excel smoke |

This shape has a text label column and field columns containing text plus a Boolean
required cell. It fits the existing `MixedArray` result contract. Verify the declaration
and formatter through the normal seam review before
declaring it ready; formatting a schema does not require adding a new result-handle type.

## Not here

Template construction, ticket ingestion, static encoding, product-specific choice expansion,
market binding and valuation. The schema spill is descriptive metadata, not an executable
template table to pass back verbatim as trade rows. No caller-supplied schema changes which
instrument definitions the library accepts.
