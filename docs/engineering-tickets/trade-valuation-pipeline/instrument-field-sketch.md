# Instrument fields: requirements, templates and contractual authority

[Pipeline overview](README.md) · [Instrument definitions](00-instrument-definitions.md) ·
[_ShowInstrument draft](../../library/instruments/show-instrument.md)

Working sketch, 3 October 2026. This incorporates the user's second legacy template as input
to the new design. It does not adopt its instrument taxonomy, all option values or every
field as an implemented contract. Fields still run down rows in the proposed reader.

## Contract-based future family

Use `future` as the proposed desk family for a position tied to a specified reference contract,
with explicit terms for the actual trade. This may accommodate a supported bilateral
lookalike. The initial implementation remains one NG contract under one supported treatment;
the wider schema is not a promise to construct or evaluate every combination.

Keep three facts distinct:

| Fact | Meaning | Candidate representation |
|---|---|---|
| Contract identity | Which contract the position holds or references | index + selected specification + contract_code |
| Route | How the actual trade is arranged for clearing | cleared, bilateral |
| Settlement method | Whether the actual trade's final obligation is physical delivery or financial settlement | physical, financial |

This is the library's organizing vocabulary, not a claim that a bilateral agreement becomes
an exchange-listed future. Retain the actual product/agreement identity and treatment. A
shared family does not establish identical value, daily cash movements or payment dates.
Physical/financial describes final settlement here; interim cash settlement and collateral
rules are separate contractual facts. Neither route nor settlement method alone determines
discounting or the treatment of cash already paid.

Examples of different records the design must distinguish:

| Actual trade | Reference | Route | Settlement method |
|---|---|---|---|
| Position in a supported physical contract | That traded contract | cleared | physical |
| Position in a supported financial contract | That traded contract | cleared | financial |
| Supported bilateral financial lookalike | A named contract used to determine its payoff | bilateral | financial |

For the first two, the selected traded product establishes the permitted terms. For the last,
the bilateral agreement establishes its own settlement terms while the referenced contract's
definition remains unchanged. A reference to a physical product must not automatically force
the bilateral trade to have physical settlement. Conversely, a user cannot relabel an actual
position in a physical listed product as financial merely by changing a field.

The current specification object holds names, lot sizes and fees. It does not yet contain
the full agreement, clearing, margin or settlement definition. Capture the minimum missing
facts for the first supported case; a broad new product-catalog system is not a prerequisite.

## Metadata to adopt from the legacy template

The reader's proposed columns are:

```text
field | description | required | required_when | type | options | rule
```

| Metadata | Meaning |
|---|---|
| required | This fact must always exist in the resolved record |
| required_when | Additional condition that makes an otherwise optional fact mandatory |
| options | Fixed allowed choices, or a description of the reference supplying contextual choices |

`required` remains a Boolean column. For an optional field the
requirement is: required OR required_when holds. Conditions are evaluated after
defaults and reference facts are resolved. Omission of a condition uses the nonempty display
text `none`, not a blank cell. `options` uses nonempty descriptions such as `selected schedule`
or `no fixed list` when there is no static enum. These display phrases are not acceptable
ticket values or expressions to parse.

Represent supported conditions as library-owned rules. Rendering a rule as
`route = cleared` or `marketing_reserve is present` does not introduce an Excel-authored
expression language. Zero is a present numeric value; it is not omission. If the legacy
marketer rule is adopted later, a reserve of zero therefore still triggers that rule.
Reject incomplete or conflicting input explicitly; do not fill it with a guessed value.

The legacy `template_allowed` flag is dropped. A template is a partial set of defaults for
recognized trade fields, without a separate permission list. Template defaults and explicit
ticket values follow one documented precedence rule at construction. The final resolved
combination satisfies the same rules regardless of its source, including constraints from
the selected traded product/agreement. The generic reader lists the family domain; a selected
product/profile can narrow it.

## Where the old fields fit

| Legacy field(s) | Proposed treatment |
|---|---|
| trade_id | Optional external attribution; always retain separate occurrence identity |
| index | Static reference named by the economics; independent of market snapshots |
| counterparty, broker, marketer | Booking/attribution; define each entity's role and any conditional requirement |
| clearing_house | Actual clearing organization; distinguish it from broker, clearing firm and account; proposed requirement when route is cleared |
| marketing_reserve | Meaning remains open: monetary amount or rate, units, sign, allocation and effect on value; do not silently add it to price or fees |
| route | Keep cleared/bilateral as distinct from final settlement method; support valid combinations only |
| floating_source | Split its meaning before adopting it: contractual observation definition belongs to static terms; how unfixed observations are projected belongs to binding |
| curve_source | If it selects forecast/model inputs, place it in explicit binding/valuation context; if it changes the contractual reference paid, represent that as an economic reference instead |
| future_month | Prefer contract_code in the new vocabulary; syntax and strip expansion must be explicit |
| settle_rule | Last-day/penultimate appears to describe observation or final-price selection; name it accordingly, separately from payment timing |
| weekend_weighting | Contractual observation/quantity weighting; calendar_flow and publication_day require worked definitions rather than inference from names |
| start_date, end_date | Explicit contractually chosen period where supported; otherwise derived from the selected contract and not independently overrideable |
| settle_freq, settle_time_lag | Separate payment frequency/lag from observation frequency and margin timing; a lag needs an anchor, unit and applicable calendar/adjustment convention |
| quantity_per | period, busday and calday describe quantity allocation; define which dates and normalize once before encoding |
| schedule_method | Legacy values mix observation selection, averaging and expiry references; replace overlapping controls with one unambiguous resolved observation rule |
| quantity, quantity_unit | Explicit signed amount and measure; reference-compatible conversion and lot rules are static work |
| fixed_price | Agreed fixed price for a fixed/float trade; the contract-based future sketch currently uses trade_price; choose each schema's vocabulary without silently accepting aliases |
| index_spread | A possible contractual adjustment to the floating reference; define sign, price units, weighting and payment treatment before enabling it |
| strike_quantity_unit | Prefer a field describing the agreed price's denominator where conversion is allowed; derive it from reference conventions when fixed; do not introduce option terminology into a future merely to name a unit |
| currency_multiplier | Derive fixed scale conversions such as currency subunits from unit definitions; a market FX conversion is a separate explicit dependency; any contractual multiplier requires its own meaning |

Add `trade_date`, unambiguous specification selection and `settlement_method` to the new
sketch. Do not automatically accept all legacy fields as optional metadata: an unimplemented
economic field is an error, never silently discarded.

## Resolve overlapping controls once

A selected product can determine observation dates, weighting and final-price rules. A
supported bilateral agreement can instead provide permitted contractual choices. In either
case, static resolution establishes one effective rule. For example, two fields attempting
to choose different last-day/penultimate observations must fail or be removed from that
schema; their outcome cannot depend on whichever function reads one first.

An averaging contract may have its own quoted market identity. Its averaging definition does
not automatically require valuing it through a reconstructed daily Asian schedule. The trade
states what it references and pays; binding declares the supported market input/projection
relationship. Likewise, `gdd_curve` needs a precise definition before it is a supported choice.

## Next small review

Agree the future schema's required facts and default/override behavior, then show two resolved
examples: the first supported NG contract position and a later bilateral lookalike referencing
that contract. Name their final settlement and payment/cash treatment explicitly. Only the
first case needs to be implemented initially. Use these examples to decide which fields are
ticket inputs, template defaults or inherited static facts before adding broader scheduling
choices or another public function.
