# Anchor IFERC payments on publication dates

**Status:** Drafted 18 October 2026 by the owner, reviewed the same day and built in #204 on
`feat/iferc-publication-anchor` from `feat/keyed-curves`, stacked on #203. The
review's five edits are in: the same-day refusal pins move to a zero lag, the one-rule help
sentence, Excel's own refusal of a stale three-argument cell, the references beyond the owning
pages, and the two budget moves. The ICE comparison below was gathered during the review.

## Outcome

An IFERC schedule supplies each contract month's publication date. Trade creation applies
`payment_time_lag` to that date, using `payment_holiday_calendar`, on both the cleared and
bilateral routes. Remove `last_trading_date` from the schedule entirely.

This follows the desk's bilateral terms: payment is five business days after publication.
It also avoids deriving publication from an exchange trading date through a second holiday
calendar. Publication is an explicit input already needed for fixings.

This changes the payment anchor; it is not merely a signature cleanup. Existing lags must
be reviewed and migrated deliberately.

## Public and saved contracts

| Boundary | Current | Proposed |
|---|---|---|
| Excel creator | `_CreateIfercSchedule(contract_code, last_trading_date, publication_date)` | `_CreateIfercSchedule(contract_code, publication_date)` |
| Saved schedule | Codes and two aligned date arrays | Codes and one aligned publication-date array |
| Schedule readback | `contract_code`, `last_trading_date`, `publication_date` | `contract_code`, `publication_date` |
| IFERC payment anchor | Last trading date | Publication date |

Keep the existing schedule ownership and validation boundaries: one publication date per
code, copied and read-only; the calendar retains its rules for codes and publication order.
The old three-argument call fails through the normal signature checks: a cell still holding
three arguments fails in Excel's own words before the add-in runs, `#VALUE!`, never the seam's,
so the kept workbook's creator cells are rewritten before its rebuild. No compatibility
overload, ignored argument or retained unused date array.

No new instrument field, payment-anchor selector or final-settlement-date field. Keep
`payment_time_lag` and `payment_holiday_calendar` in the template or ticket as today.

## Payment resolution

For each IFERC component:

```text
observation_date = schedule.publication_date[component_contract]
payment_date = shift_days(observation_date, payment_time_lag, payment_holiday_calendar)
```

Reuse the existing date-offset engine, including ordered compound offsets. IFERC's one
observation is its publication date, so its payment anchor is the existing last-observation
calculation, `_last_days`, and one anchor rule serves every index: the component's last
observation day. Remove the separate last-trading-date payment branch; avoid adding another
parallel implementation of payment arithmetic.

The `payment_time_lag` help says that one rule and no other: `Applied in order from the
component's last observation day, business days on the payment calendar: the expiry under
lastday on a futures index, the publication day on an IFERC one; the payment must be after it;
+1bd for PHH, +2bd for Waha`. It is pinned by the help, instrument and show-instrument tests
and shown in the kept workbook's shown instrument.

- Resolve and retain payment dates at trade creation, as today. Prices, fixings and discount
  factors do not enter this step.
- The supplied publication date is authoritative. Do not infer or roll it using the payment
  calendar, silently combine holiday calendars, or infer terms from an index or venue name.
- Keep the requirement that payment is strictly after the component's last observation.
  Same-day or earlier payments fail with the existing trade/component attribution.
- Keep observation generation, publication-day fixing cutoff and history lookup unchanged.
  Futures schedules and their payment anchors are unchanged.
- Evaluation consumes the resolved payment dates as today. Corrected dates may change the
  cash transition, bilateral discount factors and rate-dependent results. They do not change
  commodity observation dates, quantities or nominal delta.

## Date examples and exchange check

These are hand-checkable payment-rule examples. Calendars exclude weekends and only the
additional holidays named in the table; they are not declarations of ICE terms.

| Publication | Lag | Additional payment holidays | Expected payment |
|---|---|---|---|
| 1 December 2026 | `+2bd` | None | 3 December 2026 |
| 1 December 2026 | `+5bd` | None | 8 December 2026 |
| 1 December 2026 | `+2bd` | 2 December 2026 | 4 December 2026 |
| 4 December 2026 | `+1bd` | 4 December 2026 | 7 December 2026 |
| 1 December 2025 | `+5bd` | None | 8 December 2025 |
| 1 December 2026 | `+0bd` | None | Refuse: payment is on publication |
| 1 December 2026 | `-1bd` | None | Refuse: payment precedes publication |

The desk's bilateral `+5bd` rule is confirmed; the applicable payment holidays come from
the agreement. A publisher's holidays explain the supplied publication date and do not
automatically become payment holidays.

For cleared examples, the publication-relative lag is checked against the actual ICE payment
rule before it is presented as a production convention. ICE's
[Waha Basis Future](https://www.ice.com/products/6590171/Waha-Basis-Future) and
[HSC Basis Future](https://www.ice.com/products/6590137/HSC-Basis-Future) describe final
payment as the third clearing-organization business day after the last trading day. Their
published final settlement date is not itself a payment-date instruction.

The [Waha expiry table](https://www.ice.com/products/6590171/Waha-Basis-Future/expiry), read
on 18 October 2026, gives the last trading date and the final settlement date of every listed
month; the final settlement date is two clearing business days after last trading in each,
and payment is the business day after it. With the index printing on the month's first
business day, the supplied input, publication `+2bd` reproduces every one:

| Month | ICE last trading | ICE final settlement | Payment, last trading `+3bd` | Publication, supplied | Publication `+2bd` |
|---|---|---|---|---|---|
| Nov26 | Fri 30 Oct 2026 | Tue 3 Nov 2026 | Wed 4 Nov 2026 | Mon 2 Nov 2026 | Wed 4 Nov 2026 |
| Dec26 | Mon 30 Nov 2026 | Wed 2 Dec 2026 | Thu 3 Dec 2026 | Tue 1 Dec 2026 | Thu 3 Dec 2026 |
| Jan27 | Thu 31 Dec 2026 | Tue 5 Jan 2027 | Wed 6 Jan 2027, 1 January closed | Mon 4 Jan 2027 | Wed 6 Jan 2027 |
| Mar27 | Fri 26 Feb 2027 | Tue 2 Mar 2027 | Wed 3 Mar 2027 | Mon 1 Mar 2027 | Wed 3 Mar 2027 |
| Apr27 | Wed 31 Mar 2027 | Fri 2 Apr 2027 | Mon 5 Apr 2027 | Thu 1 Apr 2027 | Mon 5 Apr 2027 |
| Nov27 | Fri 29 Oct 2027 | Tue 2 Nov 2027 | Wed 3 Nov 2027 | Mon 1 Nov 2027 | Wed 3 Nov 2027 |
| Dec27 | Tue 30 Nov 2027 | Thu 2 Dec 2027 | Fri 3 Dec 2027 | Wed 1 Dec 2027 | Fri 3 Dec 2027 |

No listed month's window from last trading to payment crosses Thanksgiving, 26 November 2026
and 25 November 2027, or Good Friday, 26 March 2027; New Year's Day is the one holiday crossed,
in Jan27, and both counts honour it. The two counts agree whenever publication is the first
clearing business day after last trading. A month whose index prints later than that would
pay a day late under a uniform `+2bd`: surface its dates for a convention decision before
claiming support. Do not silently adjust a calendar, invent another field or hide the
difference by changing expected answers. This check does not add last trading back to the
library record.

## Complete the cutover

Update the schedule model and creator, Excel signature/help/readback, and trade payment
resolution. Migrate direct constructors and every kept caller: unit/property/performance
tests, host replay, smoke/lifetime scripts where applicable, and the kept workbook.

For example, when A contains codes, B last trading dates and C publication dates:

```excel
Before: =_CreateIfercSchedule(A2:A4,B2:B4,C2:C4)
After:  =_CreateIfercSchedule(A2:A4,C2:C4)
```

Remove the middle argument, preserving the publication input. Schedule readback's publication
column moves from 3 to 2: migrate `INDEX`, spill references, expected headers and any workbook
cells using that position. Recalculate the kept workbook and inspect its dependent results.

Inventory IFERC payment lags separately from schedule formulas. Do not automatically keep
every old lag or subtract one business day from all of them. Preserve intended payment dates
where terms are unchanged; record and independently check intentional corrections. Existing
synthetic tests with publication 1 December, old anchor 30 November and `+3bd` can use `+2bd`
to retain a 3 December payment. Their purpose and expected payment remain the same. Three
pins change meaning and are listed in the PR: `+1bd` now pays the day after publication and is
accepted, so the same-day refusal, pinned twice in `tests/unit/test_create_trades.py` and once
in `tests/unit/test_trades.py`, moves to a zero lag, `+0bd` and `+0cd`; and the compound
`+0em+2bd` counts from December's end, paying 5 January 2027, the pair `+3bd` and `+3cd` paying
together on 4 December.

Update current owning documentation and its references: the IFERC schedule, trade creation,
instrument field description, read-handle/help pages, and architecture date explanation; and
the references that still state the old anchor, schedule-method-ownership.md's IFERC row,
compound-date-offsets.md's IFERC line, template-based-quoting.md's payment line, the sample
table on iferc-fixings.md, read-handle.md's row, create-trades.md's anchor words and tests rows
and architecture.md's payment-date paragraph. Record this ticket in the pipeline index and UAT
log. Mark the earlier IFERC ticket's anchor decision as superseded with a link; do not rewrite
historical decisions into new ones or duplicate this specification across pages.

## Acceptance and verification

1. The two-argument creator and two-column readback work end to end. Publication data retains
   its immutability and existing calendar/fixing validation. No executable IFERC consumer
   retains or derives a last trading date.
2. Pin the date examples above, including both routes, a holiday crossing, a publication day
   closed on the payment calendar, a compound offset and the same-day refusal. A calendar
   change can change payment without changing publication.
3. A strip and duplicate rows use the same path as a singleton. Mixed lags/calendars retain
   distinct payment groups where necessary; compression and curve ownership remain correct.
4. Walk a known amount through fixed-but-unpaid, payment day and paid states. Verify mark/cash,
   bilateral discounting, DV01 and cross-gamma against independently calculated expectations
   for the resolved dates. Nominal commodity risk and fixing behavior retain their meanings.
5. Existing non-IFERC futures examples retain their dates and results. Neither preparation
   nor a price tick gains date generation or payment-calendar work.
6. Update meaningful work/allocation budgets for removal of one schedule date array and
   the changed anchor path: the IFERC creation ledger gains one `_last_days` call and one
   searchsorted, and the schedule's creation loses one copy and freeze. Check fixtures
   deriving payments from last trading dates as well as constructor calls. State
   before/after counts; no timing threshold.
7. Run the repository gate, documentation checks and actual workbook recalculation. List
   intentional payment/result changes in the PR so a green test is not the only evidence.

## Scope

One PR for the publication-anchor cutover and its callers. No new schedule methods, payment
rule language, automatic publisher calendar, exchange-date downloader, quoting behavior,
discounting methodology or changes to cashflow instruments. Coordinate the branch with the
named-curve work already in flight; this ticket does not reopen its design.
