# Instrument fields: requirements, templates and contractual authority

[Pipeline overview](README.md) · [Instrument definitions](00-instrument-definitions.md) ·
[_ShowInstrument draft](../../library/instruments/show-instrument.md)

Working sketch, 3 October 2026. This incorporates the user's second legacy template as input
to the new design. It does not adopt its instrument taxonomy, all option values or every
field as an implemented contract. Fields run across columns in the proposed reader, with
metadata row labels down its first column.

## Current refinement: schedule_method and quantity_per

The trade selects `schedule_method`; a template can default it. The library owns the
standardized definitions. This is the field name for v1, replacing the conversational
proposal `pricing_convention`. `exact` and `cfd` are excluded from v1; no decision about
whether those desk terms are synonyms is needed for this scope.

The candidate methods are `asian`, `lastday`, `penultimate` and `last3day`. Use
`penultimate` as the proposed canonical spelling rather than introducing a second `pen`
alias. `lastday` and `penultimate` are built; `asian` and `last3day` fail by name until they are,
never accepted and ignored. Their precise definitions remain proposals for review:

| schedule_method | Static observations selected | Proposed weights |
|---|---|---|
| asian | Eligible published observations in the resolved pricing period | Equal, summing to one |
| lastday | The reference contract's final eligible pricing observation | One |
| penultimate | The eligible observation immediately before that final observation | One |
| last3day | The reference contract's final three eligible pricing observations | One third each |

The reference supplies the applicable calendar, price source and expiry anchor. An Asian
using a rolling futures reference also needs the supported reference-contract mapping;
the method name does not invent one. The penultimate anchor is the referenced contract's
last pricing day, not an already shifted penultimate product expiry. Those are distinct
static inputs. Payment dates are separate from both observation dates and trading expiry.

`quantity_per` is a trade field with just `month` and `day` for v1. Proposed meaning:
`month` is the entered quantity for each contract month; `day` is the entered quantity
per calendar day in the resolved quantity period. This calendar-day meaning is a proposal
to make the simple choice explicit, not a new business-day option. In a full 30-day month,
100 units/month becomes 100 units and 100 units/day becomes 3,000 units. Counting 21
publication days must not turn the latter into 2,100. Both methods of stating quantity
are independent of which observations set the price. Partial-month allocation is deferred.

The existing contract specification remains the lot/quantity/fee definition. It does not
become a container for all observation and payment rules. The resolved trade retains its
selected schedule method, quantity basis and explicit payment dates. Physical-delivery
handling is outside scope; payment-date resolution is built, #139 and #144.

Proposed library homes, not files implemented by this refinement:

```text
src/goosedove/instruments/future.py
    future field schema; schedule_method and quantity_per fields
src/goosedove/instruments/schedule_methods.py
    closed method identifiers and immutable descriptive definitions
src/goosedove/trades/observation_schedule.py
    private expansion of a selected rule with static reference dates/calendars
```

The schema reader describes the same library definitions used by construction. Templates
store selections, not copies or replacements of the rule definitions. CreateTrades resolves
the selection and compatible static references, then its encoding child produces identified
observations and normalized weights. Quantity conversion produces a total signed quantity
per component; multiplying by the normalized weights produces the encoded coefficients.
History/as-of and live price values are not inputs to this static work. Preparation later
folds known observations and compresses compatible remaining coefficients by market input
and payment group. No public schedule-builder handle is needed in the first design.

For a hypothetical 30-day month, 100 MMBTU/day and trade price 3.00 give total quantity
3,000 and fixed contribution -9,000. With 20 equal eligible Asian observations, each
coefficient is 150; penultimate places all 3,000 on its one selected observation. This is
an illustrative numerical example, not an exchange calendar or contract specification.
Both retain a separate payment date. A direct whole-contract average price must still be
distinguished from prices for remaining observations at binding; this refinement does not
change that existing boundary.

## Current refinement: monthly strips, index-owned specifications and fixed_price

Propose extending contract_code to one month or a strip using the existing library period
grammar. The same `period_months` implementation behind util_StartDate/util_EndDate already
accepts case-insensitive cal27 and z27-x28, and that is the rule for ticket values: `Z26`
or `z26`, `CAL27` or `cal27`, while field names stay exact. Verified boundaries are
January-December 2027 and December 2027-November 2028 respectively, both twelve months. The
helpers establish bounds, not actual trade components, schedule coverage, averaging rules or
payments. Creation reads every code of the index's schedule for its month, refusing a label
that is not a code and two rows for one month, and keeps the mapping once.

Creation must resolve every constituent month against the supplied static index schedule,
then encode monthly components while retaining one original trade occurrence. Reuse the
period parser rather than asking the workbook to call date helpers first. Missing or
ambiguous schedule months fail. These are the requirements the general creator meets, built
in #139 as [create-trades.md](../../library/trades/create-trades.md).

| Ticket term | Proposed strip interpretation |
|---|---|
| quantity_per=month | Entered signed quantity in every constituent month |
| quantity_per=day | Entered signed quantity times calendar days in each month, under the proposed day convention |
| fixed_price | Same agreed price for each monthly component |
| schedule_method | Applied separately to each monthly component and its reference anchor |
| payment terms | Resolved payment_date per component from payment_time_lag, payment_holiday_calendar and the product-defined anchor; see the accepted starting point below |

For example, CAL27 with quantity 100 MMBTU/month creates twelve components of 100 MMBTU;
100 MMBTU/day creates 3,100 in January, 2,800 in February and so on. A monthly Asian strip
contains twelve monthly averages, not one annual average. A bullet is the same expansion
with one constituent. Explicit start_date/end_date and exact can remain deferred for these
whole-month cases. Neither one price applied to a strip nor its period boundary determines
the payment schedule; do not assign all payments to the strip end implicitly.

CreateTrades obtains specification data through the supplied Index's specifications. A
template or ticket still chooses the named row when the index offers several named specifications.
There is no additional specification object to pass, and no implicit choice of the first
row. Index is static reference data; using it does not make creation depend on Market,
history, current prices or valuation as-of. Unit conversions remain explicit static inputs.

Use fixed_price for the agreed fixed price in the proposed future definition. No alias is
proposed.

## Current refinement: payment_time_lag

Accepted as a reasonable starting point, with broader bilateral payment conventions left
for later refinement. Use payment_time_lag, a string such as "+1bd", in the trade row or
template, with payment_holiday_calendar; both are required when `settlement_method` is
`financial`, and a physical contract supplies neither. No schedule field is added for the
anchor; [fixing and payment state](fixing-and-payment-state.md) sets out how the dates are
to be derived from the contract month, business-day rules and the two calendars. The supported product definition supplies the
anchor and counting convention; creation generates a payment_date per monthly component.
Keep the lag and resulting dates distinctly named. The
[cleared contract review](fixing-and-payment-state.md#cleared-payment-convention-selected-rule-and-resolved-date)
records PHH at "+1bd" and ETE at "+2bd" after each traded contract's own Last Trading Day,
counting Clearing Organization business days strictly after the anchor. CreateTrades parses
the lag once. The actual payment calendar is an existing HolidayCalendar reference and a
static creation dependency, independent of the pricing calendar. Reuse NumPy business-day
arithmetic for the array of monthly dates. Start with positive whole business-day lags;
zero-day adjustment semantics, direct payment-date overrides and broader bilateral
conventions remain unspecified. Exact pricing-date windows remain deferred. Built in #139 as
the resolution's payment days, [create-trades.md](../../library/trades/create-trades.md).

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

The physical/financial distinctions above preserve economic context; physical delivery is
not an implementation prerequisite or an active v1 schedule control. The current
specification object holds names, lot sizes, lot units and fees. Keep that responsibility;
the trade's selected library conventions provide its pricing schedule and payment terms.
A broad new product-catalog system is not a prerequisite.

## Metadata to adopt from the legacy template

The reader's agreed row labels, down the first column, are:

```text
field
description
required
required_when
type
options
rule
```

| Metadata | Meaning |
|---|---|
| required | This fact must always exist in the resolved record |
| required_when | Additional condition that makes an otherwise optional fact mandatory |
| options | Fixed allowed choices, or a description of the reference supplying contextual choices |

Each instrument field occupies a column to the right, matching trade-header orientation.
The field identifiers form the complete accepted set for that instrument. Template and
ticket headers match them exactly, with no case folding, trimming, aliases or ignored extras;
column order may vary. This field-name rule does not change the separate parsing rules for
values such as contract codes, whose accepted month/strip syntax is described above.
The `required` row contains Boolean values after its text label. For an optional field the
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
recognized trade fields, without a separate permission list. Template fields and ticket
columns must be disjoint; any overlap fails, even when values match. The final resolved
combination satisfies the same rules regardless of its source, including constraints from
the selected traded product/agreement. The generic reader lists the family domain; a selected
product/profile can narrow it.

## Where the old fields fit

| Legacy field(s) | Proposed treatment |
|---|---|
| trade_id | Optional external attribution; always retain separate occurrence identity |
| index | The `_CreateTrades` argument, once for the batch; not a field; independent of market snapshots |
| counterparty, broker, marketer | Booking/attribution; define each entity's role and any conditional requirement |
| clearing_house | Actual clearing organization; distinguish it from broker, clearing firm and account; proposed requirement when route is cleared |
| marketing_reserve | Meaning remains open: monetary amount or rate, units, sign, allocation and effect on value; do not silently add it to price or fees |
| route | Keep cleared/bilateral as distinct from final settlement method; support valid combinations only |
| floating_source | Split its meaning before adopting it: contractual observation definition belongs to static terms; how unfixed observations are projected belongs to binding |
| curve_source | If it selects forecast/model inputs, place it in explicit binding/valuation context; if it changes the contractual reference paid, represent that as an economic reference instead |
| future_month | Prefer contract_code in the new vocabulary; syntax and strip expansion must be explicit |
| settle_rule | Use schedule_method for observation selection; payment dates stay separate |
| weekend_weighting | Contractual observation/quantity weighting; calendar_flow and publication_day require worked definitions rather than inference from names |
| start_date, end_date | Explicit contractually chosen period where supported; otherwise derived from the selected contract and not independently overrideable |
| settle_freq, settle_time_lag | Use payment_time_lag for the agreed lag string, such as "+1bd", with payment_holiday_calendar and a product-defined anchor; payment frequency stays separate |
| quantity_per | V1 month or day only; proposed day meaning is calendar day, independently of pricing-day weights |
| schedule_method | Trade-selected library definition: asian, lastday, penultimate or last3day; lastday supported first; exact and cfd excluded from v1 |
| quantity, quantity_unit | Explicit signed amount and measure; reference-compatible conversion and lot rules are static work |
| fixed_price | Chosen name for the agreed fixed price in the future schema as well; replaces the proposed trade_price name without adding an alias |
| index_spread | A possible contractual adjustment to the floating reference; define sign, price units, weighting and payment treatment before enabling it |
| strike_quantity_unit | Prefer a field describing the agreed price's denominator where conversion is allowed; derive it from reference conventions when fixed; do not introduce option terminology into a future merely to name a unit |
| currency_multiplier | Derive fixed scale conversions such as currency subunits from unit definitions; a market FX conversion is a separate explicit dependency; any contractual multiplier requires its own meaning |

Retain `trade_date` and unambiguous specification selection; add `schedule_method`,
`quantity_per` and explicit resolved payment dates. Physical-delivery handling is outside
the active scope. Do not automatically accept all legacy fields as optional metadata: an unimplemented
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

Review the proposed method definitions and the month/day quantity meanings against a
monthly ethane Asian and an NG penultimate example. Then specify how each resolves explicit
payment dates, keeping those independent of the pricing schedule. No exact/CFD or physical
delivery work is required for this review. These are design refinements, not implementation
of the methods or new constructor arguments.
