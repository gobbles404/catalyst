# Import cleared futures from an API by keyboard shortcut

[Issue #225](https://github.com/gobbles404/goosedove/issues/225) · [The host](../seam/host.md) ·
[Excel-DNA evidence](../seam/excel-dna-handles.md) · [Trade inputs](trade-valuation-pipeline/excel-trade-input-binding.md) ·
[_CreateTrades](../library/trades/create-trades.md)

**Status:** Agreed with the owner, 26 October 2026, from issue #225, which holds the workflow and its
rationale; this page holds the decisions and the design. Two pull requests: the first sends the
filter request, walks the IDs it returns and reports what it would fetch; the second fetches each
trade, turns it into ticket rows and inserts them. The first is built, on `feat/import-ids`, and
[import-trades.md](../library/importer/import-trades.md) says what it does today; the second waits
on the owner's redacted detail payload.

## Outcome

A person presses Ctrl+Shift+F in the workbook. The add-in asks an API on the desk's network for
today's cleared futures, which answers with a list of trade IDs. It walks those IDs newest first
and stops at the first one the workbook already holds, so a run fetches only what is new. It
fetches each new trade's details one at a time, turns each deal into one ticket row per month
with the source ID in `trade_id`, and inserts those rows into the trade tables the workbook names
for the deal's index and clearing house, moving the rows already there and overwriting nothing.
It then writes what it did, or why it stopped, into one cell. Nothing is priced, and nothing of
the pricing library changes: the rows are ordinary inputs to `_CreateTrades`, which keeps every
economic check it has today.

## The walk, in words

The filter's answer is a list of whole numbers in no particular order, each a trade ID once. The
walk sorts them descending and reads them newest first: an ID the workbook holds stops the walk
there, and every ID before it is fetched, in that order, one request at a time. An ID after the
stop is neither fetched nor looked at. This is the issue's deliberate early stop, accepted as the
first version's trade-off: it assumes the IDs grow with time, so that an imported ID means every
older one has been handled, and it accepts that an older trade that arrived late, or an earlier
import that stopped halfway, stays unseen until someone looks. The workbook is the record of what
was imported; there is no cursor and no second record.

| IDs returned, sorted descending | In the workbook? | What happens |
|---|---|---|
| 105 | no | fetched and staged |
| 104 | yes | the walk stops here |
| 103 | no | not fetched on this run |

A deal may become several rows, a calendar strip of twelve monthly quantities twelve rows, each
carrying the source ID. The ID found anywhere in any participating table counts as imported.

## Decisions, 26 October 2026

1. **The destinations are Excel Tables, named by the owner.** The production workbook keeps its
   tickets in Tables, which keep their formula columns and formatting when a row is inserted. A
   destination the configuration names that is not a Table is refused by name, and so is one whose
   headers are not the instrument's field names.
2. **The configuration lives in the workbook, in two Tables and one named cell the host looks for
   by name.** `import_settings`, two columns `setting` and `value`, holds `endpoint`, the address
   of the filter request, and `filter`, the request's text, today's cleared futures. `import_destinations`,
   three columns `index`, `clearing_house` and `table`, maps each pair to the Table that holds its
   trades; every Table it names is a participating table, scanned for imported IDs. The named cell
   `import_status` receives the run's words. The workbook is the product, and the host reads no
   ambient state: a missing name is a refusal that says which.
3. **The status is a cell, in the cell's words.** A command has no formula cell to fail into, so
   every run ends by writing one line into `import_status`: what was fetched and inserted, or
   `#ERROR GoosedoveImportTrades: ...` with the function, the exception and the message, as a cell
   shows a failure. No pop-up: the cell stays visible, other formulas may read it, and a hidden
   Excel can check it. A failure before insertion leaves every table untouched; a failure during
   insertion names the rows already written, since Excel offers no rollback.
4. **No credentials in the first version.** The API is reachable on the desk's network without
   a secret, so the endpoint stands in the settings and nothing else is needed. The principle
   stands for the day that changes: a secret never sits in a cell; it comes from outside Excel.
5. **HTTP through Python's standard library**, `urllib.request` and `json`, with a timeout. numpy
   stays the only dependency until the API's authentication or transport asks for more, and the
   switch is a few lines then.
6. **The importer is its own package, `src/goosedove/importer/`, and checks shape alone.** The
   pricing library never imports it and it never imports `goosedove.excel`. It reads the API's
   answers at that edge, a whole number per ID, each once, every required field present, and
   hands rows on under the instrument's field names; what a trade means economically stays
   `_CreateTrades`'s check, in one place.
7. **The shortcut is Ctrl+Shift+F, F for fetch, on the command `GoosedoveImportTrades`.**
   Excel-DNA's `ExcelCommand` attribute carries the shortcut in Excel's own key notation; the
   command is registered as the hidden-Excel quit command is, explicitly, and nothing on a
   worksheet fetches on recalculation.
8. **Network waits run off Excel's main thread; worksheet changes run on it.** The command starts
   the fetching on a background thread, which takes Python's lock in turn with any recalculation,
   and hands the reading of tables, the insertion and the status line to Excel's main thread
   through Excel-DNA's `QueueAsMacro`, the one way the add-in may use Excel's object model.
9. **Tests from recorded answers.** The suite runs against a stand-in for the API that serves
   recorded answers on the loopback interface, `tools/import_standin.py`, in the test process for
   the rules and in a process of its own for the pins; the owner supplies a redacted detail
   payload for the second slice. The command is exercised in a hidden Excel against the same
   stand-in, as the lifetime groups exercise the add-in, before any run against the real one.

Decided while building the first slice, 27 October 2026:

10. **The filter request is a POST carrying the filter's text as its body**, sent as it stands in
    the cell with `Content-Type: application/json; charset=utf-8`, the form a search request on an
    internal API usually takes; the issue left the form to the real API, and the first run against
    it settles the question. If the API takes the filter in the address instead, `fetch_ids` in
    `src/goosedove/importer/fetch.py` changes in one line and the settings keep their names. The
    request is sent once: a redirect is refused with its status and never followed, since following
    one would turn the POST into a GET without the filter's text, and only 200 is an answer, a 201,
    202 or 206 refused with IDs in it; the review's second and third findings.
11. **The seam keeps one entry for the host alone.** `_ImportTradeIds` is registered through
    `host_function`, so `entry` finds it and `function_specs` leaves it out: Excel is never told its
    name, no formula reaches it and nothing fetches on a recalculation, while its arguments are
    checked and its failure is cell text as for any function; a hidden worksheet function would
    have kept decision 7 only by convention.
12. **The host reads a Table's `trade_id` column cell by cell and judges kinds alone.** A number
    crosses; a blank holds no trade and is passed over, so a Table made of headers alone, with the
    one empty row Excel gives it, holds nothing; a text, a boolean or an Excel error is refused by
    the Table and the row, since the IDs of every Table cross as one column and the seam's words
    could name no Table. The settings' values cross as their cells hold them for the seam to judge.
    The ID the walk stopped at is held by the first Table, in the destinations' order, whose IDs
    hold it; the host passes one Table name per ID for that and for the whole-ID refusal.
13. **The line names twenty IDs and counts the rest**, so a first run against an empty workbook
    never writes a cell's worth of IDs; and with the name `import_status` missing the one line goes
    to Excel's status bar, the one place left that is no pop-up. A cell that will not take a write,
    a protected sheet say, sends the line there too with the cause, the review's fourth finding:
    before the request the run stops, `...; nothing was fetched`, and during it the line follows
    the cause, the cell keeping its progress text.
14. **The worker lets the host's buffers go.** Each run's request goes on a thread of its own, and
    the host keeps a set of pinned buffers per thread; the worker releases its set when its call is
    done, since a thread that ends keeps its pinned arrays alive otherwise, the review's first
    finding, 4.5 MB after five runs over a hundred thousand IDs. The count of sets is pinned.

## Pull request 1: the first request and the walk

Built, on `feat/import-ids`; [import-trades.md](../library/importer/import-trades.md) is the page.

- `goosedove.importer.walk`: `ids_from_json(text)`, the filter's answer read at the edge into
  IDs, a JSON list of whole numbers and nothing else; `walk(returned, imported, counter)`, the
  IDs to fetch newest first and the ID the walk stopped at, a repeated ID refused by name. Array
  code: one sort, one uniqueness check, one membership test over the IDs, no per-ID loop. Work
  reported as `ids_returned` and `ids_to_fetch`.
- `goosedove.importer.fetch`: the filter request, decision 10, through `urllib.request` with a
  timeout, its answer handed to `ids_from_json`; a connection refused, a timeout, a status other
  than 200, an answer that is no text or an endpoint that is no address is a refusal naming the
  address and the cause. Work reported as `requests_made` and `bytes_received`.
- `goosedove.importer.run`: `import_ids`, one run of this slice, the IDs made whole, the request,
  the walk and the line, `7 IDs returned, 3 to fetch: 107, 106, 105; stopped at 104, held by
  Trades_NYMEX_CME`, `7 IDs returned, none new; stopped at 107, held by Trades_NYMEX_CME`,
  `3 IDs returned, 3 to fetch: 105, 104, 103; none held`, `0 IDs returned, none new; none held`.
- The seam's entry `_ImportTradeIds(endpoint, filter, [trade_ids], [tables])`, decision 11.
- The host's command `GoosedoveImportTrades` on Ctrl+Shift+F, `host/Goosedove.Host/Importer.cs`:
  reads `import_settings`, `import_destinations` and the `trade_id` column of every participating
  Table, decision 12, calls the entry on a thread of its own and writes the line into
  `import_status` through `QueueAsMacro`, decision 8. It fetches no details and inserts nothing,
  so a first run against the real API proves the shortcut, the configuration, the Tables and the
  walk before any row moves.
- The page under `docs/library/importer/`, the host's tests without Excel, the lifetime group
  `import` in a hidden Excel against the stand-in, and a block in the kept workbook.

## Pull request 2: the details, the rows and the insertion

Waits on the redacted detail payload. What it builds: the detail request per ID, one at a time
in the walk's order; the mapping from a payload to ticket rows, a monthly strip expanded into one
row per month with the source ID in `trade_id`, each row's destination from its index and clearing
house, every row prepared and checked for shape before any insertion; the host inserting rows into
each Table and writing the prepared values, formula columns untouched; the status line with the
counts; a failed request, an unmapped destination or an invalid payload stopping the run before
insertion with no row written.

## Open, to settle against the payload

- The detail payload's fields and which carries the ID; its dates, units, quantities and prices,
  and how a strip is represented.
- What "today" means to the API and its date and time conventions.
- Whether the IDs are whole numbers that grow with time, which the early stop assumes.
- The insertion position within a Table, and whether any destination holds a formula column the
  rows must not touch.
- Pagination and error forms of the filter request, if any.

## Not in this ticket

Trade amendments or deletions, automatic refresh or polling, bilateral products, a general
synchronization engine, a persistent cursor or import database, a second record of what was
imported, changes to valuation or trade creation, credentials, and a pop-up of any kind.

## Tests

| Case | Where |
|---|---|
| the issue's table, the IDs unsorted: 105 fetched, 104 the stop, 103 unseen; none held, all fetched in order; the newest held, nothing fetched; an empty answer; a repeated ID and an ID that is no whole number refused in their words; the counts | `tests/unit/test_import_walk.py` |
| for any list of distinct IDs and any set held, the IDs to fetch are the descending prefix before the first held one, none of them held, and the stop is held or the walk reached the end | the same, a property |
| the walk's work at one ID and at ten thousand, the functions it runs once and what it allocates | `tests/performance/test_import_budgets.py` |
