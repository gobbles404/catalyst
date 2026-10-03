# 0. Library-owned instrument definitions

[Pipeline overview](README.md) · [Next: trade representation](01-trade-representation.md)

The first worksheet contracts are now drafted separately:
[_ListInstruments](../../library/instruments/list-instruments.md) and
[_ShowInstrument](../../library/instruments/show-instrument.md). The latter follows the
user's preference for one field per row, with its name and description. Both are read-only;
the pages remain proposals, not implemented functions.

The [field sketch](instrument-field-sketch.md) incorporates the second legacy template:
conditional requirements, template defaults, option domains and the distinction between
a reference contract and the actual trade's settlement terms.

## Responsibility and authority

Provide the defined, common starting point for constructing supported instruments. Users
select an approved definition, inspect its fields and permitted choices, and populate
templates/tickets under that definition. They do not define new payoff formulas, arbitrary
legs or different interpretations of the same instrument name in their workbooks.

Call this the instrument catalog or instrument definitions. The repository already uses
`instrumentation` for work-count/performance measurement. “Prototype” is useful here as a
domain term for an approved starting definition; it does not require a class inheritance tree.

The catalog is a prerequisite to the per-trade pipeline, not an operation repeated on every
trade or price tick. A library change is required to support new instrument economics.

## Four levels of information

| Level | Owns | Example |
|---|---|---|
| Instrument definition | Library-owned meaning, schema, supported choices/combinations and supported measures | `future`, single-index fixed/float `swap` |
| Product/reference definitions | Concrete product identity, index, units, schedules, lot size and settlement conventions | The selected NG product/specification and its reference index |
| Template | Instrument/reference selections and a partial set of default trade values | A book/account and default contract under the chosen product |
| Trade or cash record | The actual executed terms, payment obligation or explicitly defined balance | Signed lots and agreed price, or a known USD payment |

These are responsibilities, not a requirement to invent four frameworks. Product definitions
can allow contractually variable fields for a supported bilateral product; they fix listed
product facts that the user is not permitted to override. A template cannot relax either rule.

The current index/schedule/specification objects are reusable ingredients, not a complete
approved instrument catalog. In particular, index kind describes a reference-price/calendar
family; it does not distinguish a future from a swap using that reference. Current user-built
specification/index tables also do not establish every product's economic identity or prove
that all supplied definitions belong together.

The first trade path can use the existing validated Index, conventions, schedule and selected
specification objects as its static inputs. A new broad product catalog is not a prerequisite.
Trade resolution owns the compatibility checks between the ticket and those definitions;
market binding owns compatibility and coverage against the supplied market snapshot.
Generic instrument schemas are index-neutral; an executed trade still identifies its reference.

Reference-data authority is a separate decision. Existing unit checks establish internal
consistency, while the Index name is a label. They do not prove that an internally consistent
definition named NG represents the intended product. Do not claim schema readers alone
prevent inconsistent reference data across workbooks.

## Initial vocabulary and bounded scope

These are proposed families, not a claim that all are implemented or that every product
commonly described by each name is supported:

| Definition | Initial economic meaning | Terms it needs |
|---|---|---|
| `future` | A contract-referenced linear position with explicit actual-trade treatment | Contract identity, quantity/unit, agreed price, trade date, route and settlement terms |
| `swap` | Initially one supported fixed-versus-floating structure on one reference index | Product/index, observation period or contract, signed quantity/unit, agreed fixed price, payment terms, trade date |
| `cash_flow` | A known contractual payment | Signed money amount, currency, payment date, settlement state and attribution |
| `static_cash` | Proposed meaning: an existing cash balance at a specified snapshot | Signed money amount, currency, effective snapshot and explicitly named balance meaning |
| `basis_swap` | Reserved for a supported two-floating-reference instrument | Out of scope; reject construction until its contract is implemented |
| `option` | Reserved for a supported optional payoff | Out of scope; reject construction until its contract is implemented |

A standalone quoted basis future remains a `future`. Its settlement formula does not make
it a two-leg basis swap. The proposed future family is organized around contract identity
and can include a supported bilateral lookalike; it is not a legal classification shortcut.
Keep the actual product/agreement, clearing and payment/cash treatment. Physical/financial
final settlement is separate from cleared/bilateral route, and neither determines a universal
discounting rule. A physical reference contract can supply the price for a financial bilateral
trade while both records retain their respective contractual meanings.

Settle `static_cash` precisely before implementing it. An existing balance, historical settled
P&L, and an unpaid amount are different facts. Passing a payment date does not establish that
a cash flow settled. Neither cash type should require a fictitious commodity index, contract,
quantity or agreed commodity price merely to fit a universal row schema. A balance snapshot
is not a consummated trade; the intake must document which kind of economic record it represents.

## What a readable definition should expose

Each definition has an immutable identity/revision and a support status. Its field description
identifies meaning, type, units or unit source, required/optional/conditional status, permitted
values, defaults and which source may provide or override the field. Include conditional and
cross-field rules, not just independently valid enum values.

For example, a future schema could expose:

| Field | Domain | Source/constraint |
|---|---|---|
| Instrument kind | Selected approved definition | Not a user-written payoff instruction |
| Product | Compatible authoritative product reference | Selection or permitted template default |
| Trade ID | Optional nonempty label | Attribution only; duplicate labels do not merge occurrences |
| Trade date | Date | Ticket or explicitly permitted default |
| Contract | Contract accepted by the selected product schedule | Template default or ticket |
| Signed lots | Whole nonzero quantity for the initially supported listed product | Ticket; product owns the quantity convention |
| Agreed price | Finite number in product price units | Ticket; any price restrictions must be product rules, not a universal positivity assumption |
| Route | cleared, bilateral | Actual trade arrangement, compatible with its product/agreement |
| Settlement method | physical, financial | Actual trade's final obligation, determined by its product/agreement |

The fact that `physical` and `financial` are both recognized values does not make both valid
for the same selected traded product. The catalog must describe and enforce combinations.
Where a bilateral agreement only references that product's price, its own agreed settlement
form is a different fact. Do not automatically inherit the reference's delivery obligation.
Unknown fields, unsupported choices, missing requirements and attempts to override locked
facts fail with the field, selected definition and expected choice identified.

## Storage and surface proposal

Start with small typed, immutable definition records in a source-controlled library package
such as `src/goosedove/instruments/`. Field contracts and supported instrument identities
belong there. Keep encoding/evaluation functions separate and dispatch explicitly on approved
instrument identity; do not expose kernel names or cache/matrix choices as user fields.

Existing index/specification/convention modules remain the home of reference-data behavior
where they fit. Curated built-in product definitions and named templates can be packaged as
reviewed library data. Changing definitions follows normal code/data review and acceptance
examples; it is not accomplished by editing a schema in a workbook.

A user-created template is an immutable object containing an approved definition reference
and defaults for recognized trade fields. Its worksheet inputs participate in ordinary dependencies. It cannot
add a field, replace a rule or create a new instrument type. The library may also ship named
templates. No universal YAML interpreter, plugin system or template inheritance is required.

A template may be incomplete. Required and conditional requirements apply to the completed
trade after defaults and ticket values are resolved; template creation does not require a
fully specified trade.

The proposed read-only surface is:

```excel
=_ListInstruments()
=_ShowInstrument("future")
```

These functions return spills, not definition handles. List identifies inspectable schemas;
Show describes one generic schema. Neither selects an index, creates a template or resolves
ticket values. `required` and `required_when` describe when a fact must exist in the resolved
record; a template default or static reference may supply it. `options` gives the domain or
its source. Templates have no separate field-permission policy: the resolved trade follows
the same rules regardless of whether a value came from a template or ticket.
A later template/reference inspector can show
selected defaults and remaining ticket inputs once that stage is specified.

Only expose defaults once their fields are supported. A no-template path still
needs an explicit approved instrument definition and all required terms. The earlier
`_CreateTrades(index, labels, rows, [template])` is therefore an incomplete universal signature:
the same index can underlie different instruments, and cash may have no index. Decide how the
definition is supplied, directly or through a selected template, before freezing the API.
Selection of a template must not silently become permission to invent economic rules.

## Dependencies and acceptance

- Two users selecting the same definition and supplying the same resolved terms obtain the
  same economic interpretation. Retain definition/product identity rather than only display text.
- Existing records retain immutable definition references. A catalog update does not mutate
  their meaning; reconstruction under a changed definition is explicit and attributable.
- Catalog readers expose schema descriptions, fields, types, requirements and rules. Concrete
  choices that depend on an index are identified as contextual rather than guessed. Catalog
  visibility establishes inspection support, not construction or pricing support; unsupported
  operations fail explicitly. The first reader has no capability/status column.
- A template supplies defaults for recognized fields. The resolved trade is validated under
  the same rules regardless of value source; conflicts with locked facts and arbitrary payoff
  formulas fail. Missing and blank follow the existing seam contract.
- Test one accepted and several rejected constructions for each implemented prototype,
  including a same-index future/swap distinction and cash records without commodity fields.
- Keep instrument definitions independent of history, prices, array layout and ownership
  machinery. Their supported field/combination rules feed representation and encoding.

Begin with a reviewable future schema and the static definitions used by the NG example.
Catalog inspection can be built before the complete valuation path. Add other definitions
as their fields are agreed; constructor and evaluation support remain separate milestones.
The wider vocabulary guides boundaries without requiring all types to ship in the first PR.

