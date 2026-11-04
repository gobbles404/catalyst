# Balance-of-period quotes

**Status:** Built in #208 on top of [template-based quoting](template-based-quoting.md) (#207); [quote.md](../../library/quoting/quote.md) owns the words, and the rest of this ticket is the plan as it was. One purpose: `_Quote` prices the balance of a period, `BALZ26`, `BALF27-G27`, `BALCAL27`, from the market's valuation day. Its signature does not change.

## What is going on

A period has two forms in the library today, and the balance is a third thing that turns into one of them.

- A **label** names whole months: `Z26`, `F27-G27`, `1H27`, `CAL27`. Its meaning is fixed; `period_months` in `index_definitions/periods.py` reads it, for a ticket's `contract_code` and for `_Quote`.
- A **pair of dates** names days: `start_date` and `end_date` on a ticket. The resolution splits them at month ends into components and clips each month to the days it covers; a part of a month prices under `asian` alone.
- A **balance** is a label whose meaning depends on a day: `BALZ26` runs from the valuation day to the period's end. Only `util_StartDate` and `util_EndDate` read it, because they are handed the valuation-date handle; a batch has none, so a ticket books a balance by pasting those two dates. `period_months` refuses the prefix on purpose: a function with no day cannot say what the label means.

`_Quote` wired up the first form only. The market it takes carries the valuation day, so the quote can read a balance the way the two utilities do; it did not. That is the whole gap. The period grammar is not at fault, and nothing in it changes: the one balance rule stays where it is and gains a third caller.

## Outcome

`_Quote(market, contract_code, template, [discount_curve_set])` accepts the balance of any label it accepts today, read from the market's valuation day: the balance of a period still ahead is the period, the balance of the current period runs from the valuation day to its end, and the balance of a period that has ended is refused as the utilities refuse it. A balance is asked for by name and never inferred: `CAL27` in June keeps every month, as #207 built it, and `BALCAL27` in June is the seven months left.

## The period reader

The quote reads its period through the balance-aware readers the utilities use, `start_date(period, as_of)` and `end_date(period, as_of)` with the market's valuation day, so the balance rule has one owner and one set of words. The days are then split at month ends into components with each month's days clipped to the span, exactly as the resolution does for a dated row; if that split is not yet a function both can call, extract it in a preparatory commit, as #207 extracted `observation_references` and `calendar_rows`, with the ticket's answers and words unchanged. Each component's schedule row comes from the same month lookup as today.

For a plain label nothing moves: the readers ignore the day, the span is whole months, and every answer in `tests/unit/test_quote.py` stands.

## Observations, weights and payments

Each component's observations come from the existing builder over its clipped days, so the rules are the ones a dated ticket row already meets, not new ones:

- `asian` prices the part of a month: its pricing days within the balance, an equal share each, each a fixing where the calendar has fixed and a live quote otherwise. The valuation day itself is live.
- `lastday`, `penultimate` and `last3day` take a whole month; a balance that cuts a month is refused by the observations in their own words, as a dated row is. On an IFERC index, lastday alone, the same.
- A balance whose remaining days hold no pricing day is refused by the observations as a component with no pricing day.
- `quantity_per = calday` weights a component by the calendar days it covers, the balance's own days; `month` weights it as one and does not prorate the partial month, as the booking model does not: in the January example the balance of January and the whole of February each weigh one per month, and 21 against 28 per calendar day.
- An empty first component refuses the entire strip: `BALF27-G27` on Saturday 30 January fails because January has no pricing day left, though February has, which follows the existing rule and never drops a component silently.
- Payments count from each component's last observation as today, so a balance pays on the day the whole month would.

## Worked acceptance

The strip index of `tests/unit/test_quote.py`: F27 and G27 month-matching, the market closed on weekends and 1 January, `+1bd` on a weekend-only payment calendar, SOFR 1 on the valuation day, 0.99 on 1 February and 0.98 on 1 March.

Valued Monday 11 January 2027 with the 4th to the 8th fixed at 25, F27 live at 29 and G27 at 60:

| Request | Observations | Cleared, per month | Bilateral, per month |
|---|---|---:|---:|
| `F27`, for contrast | 5 fixed at 25 and 15 live at 29 | 28 | 28 |
| `BALF27` | the 15 live days alone | 29 | 29 |
| `BALF27-G27` | January's 15 live days, February's 20 | `(29 + 60) / 2 = 44.5` | `(0.99 × 29 + 0.98 × 60) / 1.97 = 87.51 / 1.97` |

Per calendar day the January balance covers 21 days, the 11th to the 31st, and February 28: cleared `(21 × 29 + 28 × 60) / 49 = 2289 / 49`, bilateral `(21 × 0.99 × 29 + 28 × 0.98 × 60) / (21 × 0.99 + 28 × 0.98) = 2249.31 / 48.23`.

The calendar-year index of the same tests, valued 16 June 2027, June's first eleven days fixed at 38, M27 live at 42 and N27 to Z27 at 40: `BALCAL27` prices June from its eleven live days alone, 42, and the six months after at 40: `(42 + 6 × 40) / 7 = 282 / 7` per month and `(15 × 42 + 184 × 40) / 199 = 7990 / 199` per calendar day, June's balance covering fifteen days. On a curve at 0.98 for every payment ahead the bilateral quotes equal the cleared ones, every payment now carrying one factor; `CAL27` on the same market stays at `424.4 / 11.86`, its paid months at factor one beside them.

The booking check: book an equivalent `asian` trade on the balance's own dates, `util_StartDate` and `util_EndDate` with the valuation day, at the returned quote as its fixed price, a barrel of each month paying as the quote pays. Its mark is zero on the cleared and the bilateral route under both quantity bases; the hand calculations above stand on their own beside this comparison.

Refusals, each in words that exist today: `BALF27` valued 1 February, after the period ended; `BALF27` under `lastday`, `penultimate` or `last3day`, a part of a month; `BALF27` on a Saturday 30 January, a balance with no pricing day; `BALG27` in January is `G27`, the period whole. A `BAL` label on a ticket's `contract_code` stays refused; booking a balance remains the two date utilities' business.

## Implementation and work

`src/catalyst/quoting/quote.py` alone in the library, its `_the_months` step becoming the period step; a shared month-splitting helper beside the resolution's if one is extracted. No new counter: `months_resolved` counts the balance's components and the label is read as the utilities read it. The `contract_code` help line says the balance is from the market's valuation day, within its 253 characters. Pin the table above by hand, the refusals, the counters, a host fact, smoke rows and one row of the kept workbook beside the CAL27 block; `docs/library/quoting/quote.md` owns the words, and the packet and UAT notes move the balance from deferred to built.

## Not here

Dates as arguments of `_Quote`, a second form of the same request, until UAT asks for one; a balance on a ticket, which has no day; the balance of a period in any reader but the one the utilities use; everything on the quoting ticket's deferred list.
