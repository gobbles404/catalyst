# RFQ: a saved quantity and payment schedule for quoting

**Status:** Agreed 22 October 2026 and built in #218, stacked on #217; [rfq.md](../../library/quoting/rfq.md) is the page, and the shared calculation's home is `src/catalyst/quoting/request.py`.

## Outcome

A desk receives contract months, quantities and sometimes agreed payment dates. It should
enter those as aligned columns, save a request handle, inspect what it means and quote it
against changing market data. No headers/field table, manual SUMPRODUCT or booked trade is
needed. `_CreateRFQ` owns the static request; `_QuoteRFQ` prices it using the same calculation
as the existing `_Quote`. Keep `_Quote` as the convenient tenor-based entry point.

[Packet](README.md) · [UAT notes](surface-uat-notes.md#28-rfq-quantity-and-payment-schedules) ·
[Existing quote](../../library/quoting/quote.md) ·
[Quote template](../../library/quoting/quote-template.md) ·
[Payment day](payment-day-date-or-rule.md)

## Functions and scope

```text
_CreateRFQ(index, contract_codes, quantities, template, [payment_dates]) -> RFQ handle
_QuoteRFQ(market, rfq, [discount_curve_set]) -> price

_Quote(market, contract_code, template, [discount_curve_set]) -> price  # unchanged
```

`index` is one Index handle; `template` is an existing QuoteTemplate handle, not a trade
template. Use the seam's existing `TextColumn`, `NumberColumn` and optional `DateColumn`
forms for the three arrays. A single cell is a column of one. Horizontal and two-dimensional
ranges are outside this first slice; do not build a generic vector-binding extension.

The columns align by position and must have the same nonzero length. `contract_codes`
contains one month per row, such as `F27`, `g27`, `H27`, parsed through the existing contract
code machinery and mapped to the supplied index's schedule. Missing/ambiguous months fail.
Allow nonconsecutive months, any input order and repeated months; preserve occurrence order
in readback. Refuse strips and BAL codes here: each row already has one month's quantity
and payment, and the RFQ has no valuation-date input to resolve a moving balance.

One request has one index and one template's method, route, settlement and curve key. Reuse
the existing quote's index/method and financial/physical compatibility rules. This feature
does not depend on the two-index trade work. It adds no instrument or quote-template kind.

### Quantity meaning

Quantities are finite, nonnegative numbers, with at least one positive entry. Negative
quantities and an all-zero request fail by name; this is a weighted quote, not a spread or
a net position. A zero row receives normal contract, payment and coverage validation.

All quantities use one common underlying unit, chosen consistently by the caller. The
signature carries no unit labels and cannot detect mixed units. A common conversion cancels
from the quoted price; do not require a reporting lot or select a contract specification.
The existing template's `quantity_per` determines the component quantity:

| `quantity_per` | Supplied quantity means | Component quantity `q_i` |
|---|---|---|
| `month` | Total for that month | Supplied quantity |
| `calday` | Quantity per calendar day | Supplied quantity times calendar days in that month |

Calendar days include weekends and holidays. They do not replace the method's observation
weights. Monthly totals must not receive another day-count multiplier. Return the price in
the index's quote units, exactly as `_Quote` does; prices and fixings follow those units.

## Optional payment dates and explicit precedence

**For RFQs only, a supplied payment-date column takes precedence over the quote template's
`payment_day` default.** A template can retain `+5bd` and serve requests with or without
explicit dates. This is deliberate parameter precedence, not a change to booking's disjoint
template/ticket field rule. Do not mutate the template or generalize this into field overrides.

| Input | Effective payment dates |
|---|---|
| `payment_dates` omitted | Resolve the template's `payment_day` rule per component, or use its exact date on every component |
| Complete `payment_dates` column supplied | Use each supplied date exactly, without applying the template's default |
| Blank/partial column, wrong length or invalid date cell | Fail; no per-row fallback or single-date broadcast |
| Financial request with neither dates nor a template `payment_day` | Fail naming the missing payment source |
| Physical request with supplied dates | Fail; keep the existing no-payment treatment |

Omission means the argument is absent, not a referenced blank cell. A supplied column is
dates only, not date-rule text. The ordinary seam date validation applies. Explicit dates
are never shifted for weekends or holidays, and must be strictly after their component's
last observation, using the existing shared payment validation. The template's payment
calendar remains required for financial requests, including those with explicit dates,
consistent with the existing financial-template contract.

Choose the effective payment source before resolving payments. With explicit dates, do not
apply a default rule, test hypothetical default dates against this request, or read factors
at those default dates. Template creation still validates any supplied default's intrinsic
type/grammar; an override does not make an otherwise invalid template acceptable. A partial
template lacking `payment_day` is complete for this RFQ when the explicit column supplies
the dates; all other requirements still apply.

A rule anchors on the component's last observation, including IFERC publication, and uses
the existing offset/calendar code. Keep repeated months paying on different dates separate
until discounting and the final weighted sums. Dates are optional inputs, not a switch that
turns discounting on or off: route governs that.

## What is saved and what changes

The RFQ is an immutable record retaining the exact index and template objects, the entered
codes and quantities, the resolved monthly components and quantities, observation dates and
weights, their pricing-contract references, effective payment dates and payment source
(`template` or `request`). Resolve these once in creation. No live market, fixing values,
discount-curve objects, discount factors or quoted price belongs in this record.

Do not save history row positions or fixed/live flags in the RFQ. At quote time, the market
supplies its valuation day, history and prices; map the retained observations onto that
history and apply the existing fixing cutoff. An as-of change never shortens the RFQ.
An equal-valued but different index object is a mismatch; `_QuoteRFQ` requires the market's
index to be the RFQ's exact index before any data gathering.

Use the normal handle store, publication, reuse and release, under kind `rfq` with the index
name in the descriptor. `util_ReadHandle` shows one row per input occurrence, in supplied
order, with `row`, resolved `contract_code`, `quantity`, `quantity_per`,
`component_quantity`, `payment_source` and `payment_date`. Physical rows show the usual
dash for payment source/date. Include the index, method, route, quote units and curve key
as ordinary descriptive readback facts; expose no factor or price as though it were saved.
The original template readback still shows its default; RFQ readback shows the effective
dates and their source so the precedence is visible.

| Change | What happens |
|---|---|
| Quantity, contract, explicit date, template or index | Create a new RFQ; dependent quote recalculates |
| Live price tick | Reuse RFQ; read current history/prices and reprice |
| Fixing correction or valuation-day roll | Reuse RFQ; apply the new market's history and fixing state |
| Discount curve or collection | Reuse RFQ; select the current named curve and reprice |
| RFQ readback | Read saved facts only |

## Shared quote calculation

Extract the reusable static request resolution and pricing responsibilities from
`src/catalyst/quoting/quote.py` into the quoting package. Keep the common quote terms and
their requirements defined once. Reuse the existing observation, payment and market-data
helpers; do not copy the engine or book zero-strike trades to obtain a quote.

`_Quote` resolves its tenor to an internal request with today's month/calday quantities,
without publishing an extra handle. `_CreateRFQ` resolves the explicit columns to the
same internal pricing form and retains it. `_QuoteRFQ` consumes that retained form.
The shared calculation applies history, live prices and the selected curve:

```text
P_i = sum(observation_weight_ij * observation_price_ij)
D_i = 1 for cleared
      1 for bilateral payment_i <= as_of
      selected_curve(payment_i) for a future bilateral payment
K   = sum(q_i * D_i * P_i) / sum(q_i * D_i)
```

Reuse the existing numerical safeguards and extend them for arbitrary finite quantities:
no overflow, zero denominator through underflow, NaN or infinity may silently become a
quote. Pin scale invariance and one-month cancellation at representative small and large
scales; use stable normalization where needed and the existing loud-arithmetic refusal
conventions for quantities that cannot be represented after conversion to component size.

The existing bilateral curve-set/key/start/coverage rules apply, including a singleton set,
only checking the selected curve, and reading each distinct future payment factor once.
Cleared quotes refuse a supplied curve set. Paid financial months remain in the price at
factor 1, whole-month Asians retain past fixings and live projections, and expired physical
contracts still fail. No incremental fixing cache or quote-result handle is added.

## Worked acceptance

Synthetic month-matching Asian index, `as_of = 31-Dec-2026`, January/February 2027 prices
1.00 and 1.20. Observe pricing weekdays; last observations are 29 January and 26 February.
The payment calendar excludes weekends only. The template has `quantity_per = month`,
financial settlement, `payment_day = +5bd`, and, for bilateral, curve key `SOFR`.

| Code | Quantity | Default payment | Default DF | Explicit payment | Explicit DF |
|---|---:|---|---:|---|---:|
| F27 | 100,000 | 5-Feb-2027 | 0.99 | 8-Feb-2027 | 0.98 |
| G27 | 300,000 | 5-Mar-2027 | 0.97 | 8-Mar-2027 | 0.96 |

The synthetic curve starts at 1 on the valuation day and contains the four listed payment
points. Dates and factors are fixture data, not claims about an exchange or current rates.

```excel
=_CreateRFQ(propane_index, A2:A3, B2:B3, quote_template)
=_CreateRFQ(propane_index, A2:A3, B2:B3, quote_template, C2:C3)
=util_ReadHandle(rfq)
=_QuoteRFQ(propane_market, rfq, rates)
```

| Case | Expected price |
|---|---:|
| Cleared, either payment input | `(100000*1.00 + 300000*1.20)/400000 = 1.15` |
| Bilateral, default dates | `448200/390000 = 1.1492307692307693` |
| Bilateral, explicit dates overriding `+5bd` | `443600/386000 = 1.1492227979274612` |
| Both explicit payments deferred to 8-Mar at common DF 0.96 | `1.15` |
| Explicit-date request, G27 tick to 1.30, same RFQ | `472400/386000 = 1.2238341968911917` |

Also pin the following independently of the shared-engine equivalence checks:

- Single month: quoted monthly floating price regardless of quantity or its one DF.
- `calday`: the entered quantities become 3,100,000 and 8,400,000; cleared price
  `13180000/11500000`, approximately `1.1460869565`. The readback makes the day-count effect visible.
- An equal-quantity RFQ matches `_Quote` on the same full strip, under both quantity bases,
  routes and supported methods; existing BAL behavior in `_Quote` is unchanged.
- Reordering the aligned request rows preserves price; duplicates count; a zero row has no price weight but
  remains subject to normal validation. Same month with different dates is not collapsed
  before its different factors are applied.
- Full-month partial fixings, corrected fixing, date roll, all fixed/paid (within a valid
  market) and a fixed but unpaid month retain today's quote conventions; future factors are
  read by payment date, never observation date. Quote a valid RFQ at its common fixed price
  through the trade pipeline and obtain zero mark when every payment is still ahead.
- Explicit dates work when the template omits `payment_day`; valid explicit dates also work
  when the template's intrinsically valid default would produce an invalid payment for this
  period. A weekend explicit date remains exact. Dates on/before the last observation fail.
- Misaligned/empty columns, invalid months, blank date cells, negative/all-zero/nonfinite
  quantities, missing defaults, wrong template kind, index mismatch, physical payments and
  the existing market/fixing/curve refusals identify the relevant argument/row/contract.

## Delivery and evidence

One focused feature PR, with a behavior-preserving shared-quote extraction first, then the
RFQ record/creator/readback and `_QuoteRFQ` integration. Keep existing `_Quote` prices and
formula signatures pinned through the extraction; explain any legitimate count changes.

Use WorkCounter and meaningful budget tests: creation resolves months/observations/payments
once and reads no market, fixing or factor; quoting an existing RFQ performs zero period
parsing, observation generation and payment shifts. It still applies history and current
prices/factors on each call. Readback performs no pricing. Pin one and many months, repeated
references/dates, and retained memory without introducing timing gates.

Add seam tests, host facts, smoke and a compact kept-workbook example with omitted versus
explicit dates. Exercise ordinary lifetime reuse/release through a tick, a fixing/curve
change, failed input and recovery. Run the full repository gate. Current owner pages should
describe the two new functions and common calculation; link to that owner instead of
duplicating it across old tickets. Update the packet and UAT status when implementation lands.

Not in this slice: mixed quantity units, signed spread quantities, bid/ask or market depth,
several indexes, per-row methods/routes/curve keys, strips/BAL/partial dates in RFQ rows,
partial payment-date overrides, horizontal arrays, booking or accepting an RFQ, quote risk,
new result readers, disk persistence or a general override/caching framework.
