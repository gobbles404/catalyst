# When a price fixes and when a payment settles

[Pipeline overview](README.md) · [Preparation](03-market-binding.md) · [Results](05-results.md)

**Status:** Research and lifecycle whiteboard, updated 4 October 2026. The first model now
explicitly excludes margining and actual-payment reconciliation. It proposes assumed payment
on the encoded date; the earlier actual-payment discussion below is background, not a build
prerequisite. See [proposed result fields by route](result-fields-by-route.md).
The exchange example uses ICE's Henry Penultimate Fixed Price Future (PHH). Numerical cash
examples are fictional bilateral payments, not historical prices or a claim that a cleared
future makes one entry-to-final-price cash transfer at expiry.

## What the ICE contract establishes

PHH is a monthly cash-settled future. Its final reference is the corresponding NYMEX Henry
Hub contract's settlement on the business day preceding NYMEX's scheduled last trading day.
ICE trading ends four business days before the contract month starts; final payment falls
on the next clearing business day after that trading cutoff.
[ICE product specification](https://www.ice.com/products/6590264).

## Cleared payment convention: selected rule and resolved date

**Decision:** Use payment_time_lag, a string such as "+1bd", and
payment_holiday_calendar as static trade-row or template inputs. The supported product
definition establishes the anchor and counting convention. CreateTrades parses the lag
once and resolves and stores payment_date per monthly component. This is the accepted
starting design, built for `lastday` in #139 as
[create-trades.md](../../library/trades/create-trades.md) describes under payment days.
[R1](penultimate-trades.md) specifies the penultimate extension. Broader bilateral conventions
remain deferred, with their limited coverage explicitly accepted for this first step.

The anchor need not be user-entered when supported product terms establish it, but it
cannot be assumed universally from a reference index. For example, a hypothetical bilateral
January gas swap could use the January futures fixing in late December and agree payment
five business days after January month-end. Payment occurs after expiry but is calculated
from month-end. FpML likewise represents a commodity payment's relative date separately
from its day offset, including calculation-period-end and last-pricing-date choices.
[FpML commodity relative payment dates](https://cdn.fpml.org/spec/fpml-5-12-4-rec-1/html/confirmation/schemaDocumentation/schemas/fpml-com-5-12_xsd/complexTypes/CommodityRelativePaymentDates.html).
This example explains the boundary; broader bilateral conventions remain deferred.

Rechecked against ICE product pages on 3 October 2026. Explicit date-window/exact support
remains deferred. For cleared monthly futures, distinguish the supplied `payment_time_lag`
from the actual `payment_date` resolved for each component.

| Contract | Anchor supplied by product definition | payment_time_lag | Calendar named by the contract |
|---|---|---|---|
| Henry Penultimate Fixed Price Future, PHH | That ICE contract's Last Trading Day | "+1bd" | Clearing Organization business days |
| Ethane, OPIS Mt. Belvieu Non-TET Future, ETE | That ICE contract's Last Trading Day | "+2bd" | Clearing Organization business days |

Sources: [PHH](https://www.ice.com/products/6590264) and
[ETE](https://www.ice.com/products/6590286). Both pages identify ICEU as clearing venue.
These are different final-payment conventions despite both being cleared futures. Neither
rule is a general zero-day cleared-futures default. The PHH payment anchor is its own
trading cutoff; its final price instead references NYMEX NG's penultimate settlement.

Accepted starting fields for the template/ticket:

```text
payment_time_lag = "+1bd" or "+2bd"            # required when settlement_method = financial
payment_holiday_calendar = existing HolidayCalendar reference

CreateTrades -> payment_dates[monthly_component]
```

For the reviewed products, the library uses the actual traded contract's last trading day
as the anchor and counts eligible days strictly after it. The lag string expresses a
positive whole number of business days; creation converts it once to the internal numeric
offset. The trade row can supply the field, or a template can provide the shared default.
The same choice applies to the payment calendar, which uses the existing immutable
HolidayCalendar object transported by its Excel handle. No separate public anchor selector,
numeric lag field or payment-rule constructor is needed for this starting scope.
Listed-product terms must still validate together; a supplied lag/calendar cannot redefine
the traded product.
The [R1 implementation](penultimate-trades.md), built in #NN, derives the pen expiry from the
underlying NYMEX expiry and pricing calendar, then applies `payment_time_lag` from the pen
expiry on the payment calendar. For its supported pen products, the pen expiry is both the
observation date and payment anchor. `lastday` keeps its existing expiry anchor. Both resolved
dates are retained at creation; the underlying schedule is unchanged. This supersedes the
earlier adjusted-lag proposal. Exchange date examples and separate-calendar tests validate the
rule; changing the entered lag to compensate for the wrong anchor is not the implementation.
This limited method-to-anchor relationship does not establish a general rule for future
Asian or bilateral products. R1 includes PHH and ICE WTI and distinguishes the WTI payment
deadline from an observed cash transfer.
Existing ContractSpecifications keeps its lot/unit/fee responsibility. The instrument's
schedule_method still selects pricing observations, independently of payment_time_lag.

For positive lags, select the first or second eligible calendar day strictly after the
anchor; do not first roll the anchor forward and then add the lag, which can overcount if
the anchor is closed on the payment calendar. A hypothetical Friday anchor with Monday
closed on that calendar gives Tuesday for +1bd and Wednesday for +2bd. This is an
illustration, not a dated ICE holiday calculation. Supporting 0bd later requires an explicit
closed-anchor adjustment rule. No further roll menu is needed to express these two ICE rules.

Reuse the existing HolidayCalendar data and NumPy business-day arithmetic. The repository
already uses these primitives in futures_fixings.py; it does not yet have a shared payment
date function. A small private date consumer can construct a busdaycalendar with Monday-Friday
as eligible weekdays and the supplied holidays, then apply busday_offset to an array of
anchors. For strictly positive lags, roll="backward" followed by the offset implements the
strict-after rule even when the anchor is closed. Do not extend that expression to zero
without specifying its adjustment behavior. NumPy supplies arithmetic, not authoritative
exchange holiday data. Resolve the resulting date array once during CreateTrades, including
all monthly strip components; price ticks do not rebuild it.
[NumPy busdaycalendar](https://numpy.org/doc/stable/reference/generated/numpy.busdaycalendar.html),
[NumPy busday_offset](https://numpy.org/doc/stable/reference/generated/numpy.busday_offset.html).

The initial supported products establish a last-trading-day anchor. A future bilateral
example may require a month-end anchor or a different payment rule; that extension and
direct date overrides remain deferred.

Keep the payment calendar separate from the pricing calendar. ICE publishes an
[operating calendar](https://www.ice.com/publicdocs/clear_europe/circulars/C25074.pdf) and a
[currency holiday schedule](https://www.ice.com/publicdocs/ICEU_Currency_BankHolidays_2026.pdf)
as distinct schedules. The reviewed product convention counts Clearing Organization
business days; do not substitute OPIS/NYMEX holidays or silently combine all holidays.
Currency-specific operational cash handling is outside this finalization model. A concrete
date fixture must use the applicable contractual calendar data for its year.

For CAL27, apply the selected rule independently to each constituent's trading cutoff and
retain twelve payment dates. No pricing/fixing values are required to generate these dates.
Preparation uses the dates with history/as-of under the existing modeled cash cutoff.
Cleared cash remains modeled finalized economic P&L; it does not assert that the full
entry-to-final-price P&L is transferred on that final payment date. Margining remains excluded.

## Monthly constituents and fixing state

For this discussion Cal26 means the January-December strip of monthly contracts, not one
annual-average instrument. Each constituent retains its monthly price determination and
settlement rules. ICE's general calendar-strip explanation describes a year as its monthly
constituents; that guide is for ICE Futures Europe, not a substitute for a PHH execution's
actual package definition or allocations.
[ICE strip guide, section 3.6](https://www.ice.com/publicdocs/IFEU_Common_Strategies_and_Strips.pdf).

Under PHH's rule, the March price becomes final before March starts. The contract month is
not the payment month. No exact historical 2026 day is asserted here; date generation must
use the applicable exchange and clearing calendars. In particular, an expiry field labelled
final settlement is not automatically the cash payment date.

For background, ICE Clear Europe also marks open positions daily and settles variation P&L
in cash overnight. Those flows are outside our initial model; monthly final settlement does
not describe the actual frequency of cash movements.
[ICE Clear Europe risk management](https://www.ice.com/clear-europe/risk-management).

A bilateral Cal26 swap may adopt the same monthly price references, but its own agreement
establishes payment timing and any collateral/cash mechanics. Do not inherit every clearing
cash rule merely because the swap references PHH or the same NYMEX prices.

## Two independent questions

| Question | Example states | Evidence |
|---|---|---|
| How much of the floating price is known? | Unfixed, partially fixed, fully fixed | Observation schedule, publication cutoff, fixing history |
| Which components remain in modeled value? | Before payment date, on/after payment date | Encoded payment dates, valuation as-of and explicit assumed-settlement convention |

Use `floating_leg_set` for the amount contributed by known observations. It is not synonymous
with cash paid. A fixing says which price applies; a payment event says which obligation
has been discharged. There is no need to invent two different kinds of set floating price
to distinguish a paid month from an unpaid month. For this first model, the payment event
is assumed from the scheduled date; it is not supplied by a bank ledger.

For the monthly PHH strip, imagine a snapshot after March's final price is established but
before its final payment, assuming earlier months' payment dates have passed:

| Constituent | Final price known? | Modeled final settlement reached? |
|---|---|---|
| January, February | Yes | Yes, by the example's dates and convention |
| March | Yes | No, final payment outstanding |
| April-December | No | No, still live monthly positions |

This table concerns modeled finalization. A whole-trade flag such as Cal26_is_settled cannot
represent these constituent states adequately. Actual daily margin cash remains out of scope.

An Asian observation window can also be partially fixed while its one monthly payment is
unpaid. That intermediate price state does not apply to PHH's single final fixing in the
same way; preserve the actual product's observation rule.

## A bilateral March payment, with simple numbers

Assume a fictional bilateral monthly payment receives floating and pays 3.00 USD/MMBtu on
2,500 MMBtu. The applicable monthly reference eventually fixes at 3.20. Assume no earlier
payment or collateral transfer and no fees. These choices explain the states; they are not
PHH's daily variation-margin cash mechanics.

```text
fixed_leg = -2500 * 3.00 = -7500
floating_leg_set = 2500 * 3.20 = 8000
floating_leg_live = 0
known net payment = 500
```

| March state | Bilateral NPV | Modeled bilateral cash |
|---|---:|---:|
| Fixed, before payment date; discount factor 0.99 | 495 | 0 |
| Fixed, on/after payment date | 0 | 500 |

The original fixing stays 3.20 in every row. Floating commodity delta is zero once this
particular price has fixed. Before payment the claim may still have rate sensitivity.
The full net amount of 500 becomes cash, not the prior discounted NPV of 495. Remove both
fixed and floating contributions from remaining value together. The proposed cumulative
cash field is a signed historical payment total, not a reinvested cash-account balance.

Keeping the Cal26 trade's terms does not keep all twelve monthly obligations outstanding.
Past components remain available as source facts, while evaluation
values the remaining obligations and reports cash under its separately defined scope.

## Background: actual cleared cash would need different inputs

For a cleared PHH position, entry-to-final-price P&L can have been paid in multiple variation
margin transfers. Do not compute quantity times final-minus-entry price and book that whole
amount again as the final payment. A current daily settlement quote is also not necessarily
the contract's final fixing. Current price, final observation and paid cash are different inputs.

Cash for the March contract and cash paid during March are different selections. The latter
uses actual cash dates and may include variation margin on several later-dated contracts.
We are not building that feature here. The proposed cleared result instead returns
`cleared_mark` and `cleared_cash`, with shared `delta` and `dv01` names.
Its cash field means modeled finalized P&L. Bilateral `bilateral_cash` is proposed as all
modeled settled payments in the supplied collection through as-of.

## Consequences for the pipeline

| Boundary | Responsibility |
|---|---|
| CreateTrades | Retain contractual observation and payment rules/dates for monthly constituents; executed terms remain static |
| PrepareTrades(trades, history) | Fold fixings, derive modeled settlement from dates/as-of, and retain contributions by relevant payment group |
| Evaluation with explicit valuation context | Discount remaining bilateral payments, report settled amounts without discounting, and complete route-specific values and shared risks |
| Readers | Display the completed result's selected cash scope and remaining value; no settlement inference or lazy pricing |

The proposed cutoff is `payment_date <= as_of`. Encoded dates plus history's as-of supply
everything needed for this assumed-settlement mask, so the initial preparation needs no
extra settlement store. An as-of change already rebuilds preparation. The model requires
final fixings for settled components and fails if they are missing.

Reaching a date does not prove an actual transfer; that distinction is captured by the
explicit modeling convention. If actual-payment reporting is added later, settlement records
could change independently and must become an explicit dependency. Partial payment of 200
against a 500 obligation would then leave 300 outstanding. That future reconciliation mode,
along with margining, is outside the first implementation.

Acceptance: fixing changes set/live exposure without itself declaring a payment; a date roll
moves the full net payment from remaining value into the settled bucket without changing its
fixing; monthly components can occupy different states; no component is counted twice. Test
before/on/after-date cutoffs and required missing fixings under one explicit as-of convention.
