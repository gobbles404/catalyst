# A rolling nearby contract for futures averages

**Status:** The first slice built in #245 and the second in #246. Agreed with the owner on 13 November 2026 for
[issue #238](https://github.com/gobbles404/catalyst/issues/238), this page in the first slice's
first commit; three pull requests stacked from main after #242. The first, the fixings and the
history holding a settle for more than one nearby, is #245, the slice this page opens;
the second, the `nearby` field required of every template and priced on trades, is #246, and the third,
quotes and requests for quote, follow on it. It builds on
[calendar-driven-asian-references.md](calendar-driven-asian-references.md), #165, which gave an
asian observation the calendar's contract for its day, and on
[onetime-averaging.md](onetime-averaging.md) and [dated-quotes.md](dated-quotes.md).
[futures-fixings.md](../../library/market-data/futures-fixings.md) and
[market-history.md](../../library/market/market-history.md) are the owners the first slice updates.

## The issue

A customer swap can float on the average of the **second nearby** futures contract over a
period, not the first. A nearby is a contract counted from the prompt, the listed contract
nearest its expiry on a given day: the first nearby is the prompt itself, the second the next
contract the schedule lists, and so on. Which contract that is changes during the period: when
the prompt expires, every nearby moves on by one. The library prices the first nearby alone
today, the calendar giving each day its prompt contract, so the second-nearby swap cannot be
booked as what it is.

On any one day a trade still reads one contract. The change is which one: the prompt for a
first-nearby trade, the contract after it for a second. What changes shape is what trades share:
one history now holds more than one contract's settle for a day, and one batch can hold a
first-nearby row and a second-nearby row observing the same day.

## Decisions of 13 November 2026

| Decision | Agreed |
|---|---|
| The selection | A position counted from the prompt, never a contract code: `1` the prompt contract on each observation day, `2` the next the schedule lists, higher numbers the same way. The contract is found afresh for every observation day: its schedule row is the prompt's row that day plus the number less one. |
| The roll | The calendar's own rule and no other: the expiry day belongs to the expiring contract, and the day after to the next one listed. Listed contracts are counted, not calendar months. |
| The field | `nearby`, a whole number of 1 or more, on the `fixed_float`. **Required** on every trade template or ticket and on every quote template, as `settlement_frequency` is: a sheet says which contract it means and nothing is assumed. Every existing template gains it in the slice that adds it. |
| Where it is priced | First on one futures index, financially settled, under `asian`, for `monthly` and `onetime` alike. Everywhere else the field must be `1`, and another number is refused by name: the expiry-based methods, an IFERC index, two indexes and a physical settlement. |
| The fixings | One fixings object, one history and one market per index, as today. The settles grow sideways: the date column, then one settle column per nearby, the first nearby's first. Every cell holds a number. A sheet with one settle column changes nothing. |
| Identity | A settle in column `n` on a day is the settle of that day's `n`-th nearby, the contract the calendar's rule gives. The history holds the value by its day and its position and reads it back by day and contract; the readback shows the contract each settle was taken for. |
| No substitute | A fixing a trade needs and the history lacks is a refusal: never another nearby's settle, never a day carried forward, never a live quote for a past day. |

## The rule

```text
prompt(d)        = the first schedule row whose expiry is on or after day d      # the calendar's
contract(d, n)   = prompt(d) + n - 1                                             # n = nearby, 1 or more
price(d, n)      = the history's settle of contract(d, n) on d     where d has fixed
                 = the market's quote of contract(d, n)            where it has not
```

The period, the observation days, the weights, the quantity and the payment day are as they
are today; only the contract each observation reads changes. The delta of a second-nearby
trade is counted on the contracts it actually reads, so it nets against first-nearby trades and
plain futures positions on those same contracts.

## The example

A futures index whose contracts expire mid-month: K26 on 15 May 2026, which only bounds the
calendar, M26 on Monday 15 June, N26 on 15 July, Q26 on 14 August and U26 on 15 September. A
window of two observation days across the June expiry, 15 and 16 June, each weighted a half:

| Day | Prompt | First nearby's settle | Second nearby | Second nearby's settle |
|---|---|---:|---|---:|
| Monday 15 June, the expiry day | M26 | 80 | N26 | 82 |
| Tuesday 16 June | N26 | 81 | Q26 | 83 |
| **Average** | | **80.5** | | **82.5** |

Valued on 17 June with both days fixed, a first-nearby trade over the window averages 80.5 and
a second-nearby trade 82.5, both off one history made from one fixings object whose settle
range is two columns wide. The third nearby on 15 June would be Q26, and a history holding two
settles a day refuses it.

## The fixings and the history, the first slice

- `_CreateFuturesFixings(date, settle, index)` keeps its name and its three arguments. `settle`
  is a range of numbers one row per date and one column per nearby, `B2:B30` as today or
  `B2:C30` with the second nearby beside the first. The rule that was one settle per date is
  one row per date.
- `FuturesFixings.settles` holds the grid, days by nearbys, oldest day first as before.
- `MarketHistory.fixing_prices` holds the fixed and priced days by nearbys; an IFERC or a Gas
  Daily history is the same record one column wide. Each held settle must name a listed
  contract: a second nearby on a fixed day whose prompt is the schedule's last contract is
  refused when the history is made.
- One reader, the history's own, answers a fixing by calendar row and contract, as the market
  answers a live price by contract: the position is the contract's row less the prompt's on
  that day, and a contract outside the settles the history holds is refused by its day, its
  code and the prompt. The preparation of a batch and the pricing of a quote both read through
  it, in place of their two gathers by day alone.
- Readbacks: the fixings spill `date` then `nearby_1`, `nearby_2` and on, so the column a trade
  reads carries the trade's own word; the history spills the calendar's four columns and
  `fixing_price`, the prompt's as today, then for each further nearby its contract's code and
  its settle on every day.
- Results for every existing sheet are unchanged: a first-nearby observation reads position
  one, the prompt's.

## The field, the second slice

- Slot identity first, its own commit: a dated slot is a payment group, a day and a contract,
  where it was a group and a day, so a first-nearby row and a second-nearby row of one group
  and one day stay two exposures. The one-contract-per-day array no reader uses is deleted.
- `nearby` joins the definition, required, appended last as `settlement_frequency` was, a
  quote template allowed and required to hold it; every template in the tests, the host facts,
  the smoke, the lifetime script and the kept workbook gains `nearby = 1` in the same pull
  request, since a required field fails every entry without it.
- The reference rule gains the position in its one place, the function the batch, the quote and
  the request share. A contract past the schedule's end is refused by the trade, the day and
  the schedule's last contract; a fixing the history lacks by the history's reader; a quote
  past the live prices by the market's reader, as today.
- Quotes and requests accept `nearby = 1` and refuse another number by name until the third
  slice prices it.

As built in #246:

- The field is the trade's, one per row, `ResolvedTrades.nearby`, and not a leg's: a pair takes `1`, and
  nothing of a second leg's nearby is built.
- The number is read by `whole_nearbys`, whole, 1 or more and of at most 15 digits, the digits a cell
  carries exactly, as a trade ID's are; whether the schedule lists a contract that far on is the reference
  rule's, day by day, so the bound is the cell's and no count of contracts.
- `nearby_rules` in `terms.py` is the kernel's rule for a number above 1: an IFERC index, two indexes, a
  physical settlement and another method than `asian` refused in that order, the first row at fault named.
- The schedule's refusal names the trade, the day, the nearby, how far the schedule reaches that day, the
  day's prompt and the schedule's last contract: `trade 2 at row 2 observes 2026-08-17 at nearby 2,
  expected at most 1 that day, 'U26' being prompt and 'U26' the schedule's last contract; the schedule
  lists no contract for a later nearby`.
- Every existing template on a sheet takes `nearby = 1` through `HSTACK` in its creating formula, in the
  smoke, the lifetime script and the kept workbook alike, its typed cells as they were; a new block types
  a `nearby` column. The kept workbook's three date-and-settle tables that stood where a readback grew
  moved one column right, with the two notes that cite them.
- A quote template holding another number than `1` is refused when it is quoted, by `_Quote`,
  `_QuoteByDates` and `_CreateRFQ` alike: `nearby is 2, expected 1 in a quote template; a quote and a
  request for quote price the prompt contract's days, and a later nearby is booked as a trade`.

## Quotes and requests, the third slice

`_Quote`, `_QuoteByDates` and `_CreateRFQ` with `_QuoteRFQ` price a template's `nearby` as the
batch does, through the shared reference rule and the history's reader; a fair price booked as
a trade values to zero within rounding.

## Also pin

- The selection before, on and after an expiry, a window crossing several rolls, and a schedule
  whose listed months are not consecutive.
- Unfixed, partly fixed, fully fixed and unpaid, and paid windows; a corrected fixing; a roll of
  the valuation day; the original weights unchanged throughout.
- First-nearby and second-nearby rows in one batch, one history and one market, on the same
  days and in the same payment group, their exposures apart; the hedge against the actual
  contracts netting in a collection.
- The refusals: a missing nearby column, a schedule too short, live prices too short, and the
  field above 1 where it is not priced.
- Work by counts: what creation, history, preparation, quoting, evaluation and aggregation do,
  before and after, in each pull request; a tick of the prices re-reads no fixing.

## Outside this arc

A new index or market per nearby; a new instrument or pricing model; another roll rule;
averaging a fixed maturity; a second leg's nearby on a pair; IFERC, Gas Daily and LME nearbys;
fetching historical data; a full historical curve by contract and day. The market's own
readback keeps showing the prompt's fixing and the quote of each day's contract; a nearby
column there is not built.
