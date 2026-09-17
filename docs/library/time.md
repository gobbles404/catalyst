# Time

Decided in #72, ahead of the functions that need it.

Not a function page. This page records what the owner and the engineer settled about contract months, their codes, calendar days and business days, from a braindump the owner brought on 2026-09-17, before any function reads a code or counts a business day. It binds nothing on its own: each rule below moves to the page of the function that first needs it, in that function's pull request, and this page then points there. What it settles now is the vocabulary and the mechanism, so those pages are short when they come, and what it declines, so the braindump is not reviewed twice.

## Contract months

A contract month is a unit of its own, as a day is: `datetime64[M]` in the library, beside `datetime64[D]` for a date, never a first-of-month date standing in for a month. numpy does the arithmetic: `months + np.timedelta64(3, "M")` moves by contract months, `months.astype("datetime64[D]")` is each month's first day, the next month's first day less one day is its last, and `np.arange` over two months is every month between them. No month arithmetic is written by hand, and nothing runs per month. The seam refuses a date coarser than a day on the way out ([outputs.md](../seam/outputs.md)), so a month crosses to the sheet as its first day, its last day, or its code. Coming in, the seam's wanted-next table ([inputs.md](../seam/inputs.md)) already holds `ContractMonth`, a whole serial on the first of a month, with the trap it must handle, that typing Dec-27 into a cell stores the 27th of December; it would hand the library this unit. A code in text is the other way in, and which a function takes is its page's call.

## Codes

One spelling: a month letter and two digits, `M26`, matched exactly, never trimmed or re-cased, as unit codes are ([conventions.md](conventions.md)). The letters are the exchanges', F G H J K M N Q U V X Z for January to December, and the two digits are the year in 2000 to 2099, a fixed horizon, not a window sliding with the valuation date, so a code means the same month on every day. `CreateExpirySchedule`'s sample, `m26` beside `V26`, moves to `M26` in the pull request whose builder first reads codes.

| Letter | F | G | H | J | K | M | N | Q | U | V | X | Z |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Month | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |

Reading a code is `[FGHJKMNQUVXZ][0-9][0-9]` over the seam's tuple of texts, once, at the creator; writing one is the month's letter and the year's last two digits. The horizon bounds the writer too: a month outside 2000 to 2099 has no code and fails rather than wrapping.

## The schedule's rules, when it reads codes

The owner asked for the check that a schedule's contracts are in order and none is skipped. That is the rule the expiry page defers to its first reader, and the builder takes it the day it reads codes:

| Rule | Message |
|---|---|
| every code is a month letter and two digits | `future_code row 3 is 'm26', expected a month letter and two digits, such as M26` |
| the months increase, each the month after the one before | `future_code row 4 is Q26, expected N26, the month after row 3's M26` |
| the future expiries increase with them | `future_expiry row 4 is 2026-07-21, expected a date after row 3's 2026-07-21` |
| an option expires on or before its future | `option_expiry row 4 is 2026-08-21, expected a date on or before row 4's future_expiry 2026-08-20` |

Rows count as the sheet counts them. The consecutive rule refuses a market that lists only some months, as grains and rough rice do; when such a market arrives, that rule becomes a fact of the market rather than of the library, decided then, together with what a gap means to the nearby lookup below. The last rule is the engineer's proposal, not yet the owner's decision.

## Nearby contracts

The first nearby contract on a date is the first in the schedule whose future expires on or after that date; whether a contract is still prompt on its own expiry day is a fork below. In numpy it is `np.searchsorted` over the expiry column, one call for a column of dates, and a date after the last expiry has no contract and fails. The n-th nearby is n positions later in the schedule, never n months later: a schedule with gaps would otherwise land on a month with no contract. A roll lag, where a market rolls before expiry, shifts the date by business days first, through the holiday calendar as below, and only where a contract states one.

## Calendar days, weekends and business days

Every range of dates in the library is calendar days, weekends and holidays included, spelled out day by day: a period is `np.arange` over days, as the curve's days are, and nothing is skipped to save rows. Business days are a separate fact, needed only where a contract's terms state one: a roll lag, a settlement lag, or the day a fixing prices. They come from numpy, `np.is_busday`, `np.busday_offset` and `np.busday_count`, taking the holiday calendar's array as `holidays` and a week mask, Monday to Friday unless the market says otherwise, over whole columns at once; no day-by-day loop and no weekday arithmetic written here. The sentence in [conventions.md](conventions.md#what-holds-everywhere), that no business-day adjustment happens anywhere, changes in the pull request that first needs one, to: none happens unless a contract's terms state it, and then only through the calendar, never by default.

The shape to leave room for is Gas Daily daily: a swap settling every calendar day of its period against a daily assessment, weekends and holidays included, where a weekend day's price is the one assessed on the last business day before it. So a period is calendar days, each calendar day has a pricing day, and the holiday calendar decides which days price. A library that dropped weekends from a period could not price it.

## Readers the owner wants

Worksheet functions with the `util_` prefix, which [conventions.md](conventions.md) reserves for the owner to state, and the owner has: the first and last calendar day of a code's month, `util_ContractStart("M26")` showing 1-Jun-2026 and `util_ContractEnd("M26")` 30-Jun-2026. Not next; each gets its page when it is, and each is one line over the month unit above.

## Declined

From the braindump, each with the rule it met and what stands instead:

| Mechanism | Why not | Instead |
|---|---|---|
| serial-to-date and back in the library, an epoch of 1899-12-31 with a shift at serial 60 | the seam does it once, epoch 1899-12-30, serials below 61 refused rather than shifted ([inputs.md](../seam/inputs.md)) | dates arrive as `datetime64[D]` |
| a date parser over five text formats, `Any`, an `isinstance` chain and `.title()` | no coercion at the seam, text is never a date, and no `isinstance` inside the library | the seam's `Date` |
| `datetime.date` and hand-written month arithmetic | the library's units are `datetime64[D]` and `datetime64[M]` | numpy |
| `KeyError` for a missing contract | every rule is a `ValueError` in the grammar, `{argument} is {what arrived}, expected {what was wanted}` | the messages above |
| header aliases, `month`, `contract_month`, `fut_month` | one name per thing, aliases stay on the workbook side; the schedule takes columns without headers | the declared columns |
| a sorted-months cache set on the record through `getattr` | records are frozen; a sorted column is a builder rule, checked once | `searchsorted` |
| a memo keyed by a namespace string and a name | identity is content, never a label; caching is parked for the measurement session and will key on digests | nothing yet |
| a settlement lag as text, `+2bd`, parsed by regex on each call, falling back to the pricing calendar when the payment calendar is missing | a lag is a fact of a contract, typed once at its creator; a missing calendar fails, it is never substituted | two typed fields, when a contract has a lag |
| day-by-day loops for business days, and a weekday counter | no per-item loops | `busday_offset`, `busday_count` |
| the n-th nearby by adding months | skips over a gap to a month with no contract | by position |
| row-numbered messages naming the table from inside the library | the seam counts rows and the builder checks meaning | the builder's messages |

## Forks

| Fork | Where it stands |
|---|---|
| code case | decided: uppercase only, `M26` |
| weekends in a period | decided: every calendar day, weekends included |
| contracts in order and none skipped | decided as the rule; relaxed for a market listing only some months when one arrives |
| an option's expiry on or before its future's | proposed above; the owner decides with the schedule's rules |
| prompt on the expiry day | open: the owner decides when the nearby reader is written; one flag on the lookup |
| the week mask | open: Monday to Friday until a market trading weekends arrives |
| the horizon | decided: 2000 to 2099, fixed |

## When it is time

Three pull requests, in this order, each with its page: the schedule's builder reads codes, the rules above and the sample's spelling; the nearby reader, first and n-th, with the roll lag only if a market states one; the two `util_` readers, any time after the first. Business days enter with the first contract whose terms need them, and Gas Daily daily is the first daily-settled shape to build for. Nothing from the declined table returns.
