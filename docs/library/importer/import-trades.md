# GoosedoveImportTrades and _ImportTradeIds

Built from [import-cleared-futures.md](../../engineering-tickets/import-cleared-futures.md), issue #225, as its first slice. A person presses Ctrl+Shift+F in a workbook. The add-in's command `GoosedoveImportTrades` reads the configuration the workbook holds, asks the API named there for today's cleared futures' trade IDs, walks them newest first against the IDs the workbook's trade Tables already hold, and writes one line into the named cell `import_status` saying what a run would fetch and where the walk stopped. Nothing is fetched beyond the IDs and nothing is inserted: a first run against the real API proves the shortcut, the configuration, the Tables and the walk before any row moves. The second slice fetches each new trade and inserts its rows. The code is `src/goosedove/importer/`, the request, the walk and the run; `src/goosedove/excel/importer.py`, the seam's entry; and `host/Goosedove.Host/Importer.cs`, the command.

## What the workbook holds

The command looks for three things by name, in the active workbook, on any sheet:

| Name | What it is | What it holds |
|---|---|---|
| `import_settings` | a Table with the columns `setting` and `value`, exactly | a row `endpoint`, the address of the filter request, and a row `filter`, the request's text, the API's own filter document, each once and nothing else |
| `import_destinations` | a Table with the columns `index`, `clearing_house` and `table`, exactly | one row per index and clearing house, `table` naming the Table that holds its trades; every Table named is a participating Table, read for the IDs it holds; this slice reads the `table` column alone, and the second reads the other two |
| `import_status` | a workbook-level name on one cell | the run's line, written by every run |

A participating Table has a column `trade_id`, the instrument's field, holding the source system's deal number on every row that came from the API, as [_CreateTrades](../trades/create-trades.md) takes it. The configuration as the lifetime group lays it out, the two Tables, one destination Table with two trades and one with none yet, and the status cell under them:

| | A | B | C | D | E | F | G | H | I |
|---|---|---|---|---|---|---|---|---|---|
| 1 | setting | value | | index | clearing_house | table | | trade_id | quantity |
| 2 | endpoint | `http://api.desk/trades/search` | | WTI NYMEX | NYMEX | Trades_NYMEX | | 104 | 10 |
| 3 | filter | `{"product": "cleared futures", "traded": "today"}` | | NG NYMEX | NYMEX | Trades_NG | | 90 | 5 |
| 6 | `3 IDs returned, 1 to fetch: 105; stopped at 104, held by Trades_NYMEX` | | | | | | | | |

A1:B3 is the Table `import_settings`, D1:F3 `import_destinations`, H1:I3 `Trades_NYMEX`, and `Trades_NG` stands on another range with its headers and no trade yet; A6 carries the name `import_status`. The API answered 103, 105 and 104: 105 is to fetch, 104 stops the walk, and 103 is not looked at, the ticket's table.

## What the cell shows

While the request is out, `fetching trade IDs from http://api.desk/trades/search ...`; a second press meanwhile is refused in the cell, `#ERROR GoosedoveImportTrades: a run is in progress; its line replaces this one when it ends`, and the running one's line replaces it. Then one of:

| The cell shows | When |
|---|---|
| `7 IDs returned, 3 to fetch: 107, 106, 105; stopped at 104, held by Trades_NYMEX` | the walk stopped at an ID a Table holds; the IDs before it are to fetch, newest first |
| `7 IDs returned, none new; stopped at 107, held by Trades_NYMEX` | the newest ID is already held |
| `3 IDs returned, 3 to fetch: 105, 104, 103; none held` | no Table holds any of them |
| `0 IDs returned, none new; none held` | the filter matched nothing |
| `30 IDs returned, 30 to fetch: 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11 and 10 more; none held` | more than twenty to fetch: twenty named, the rest counted |
| `#ERROR GoosedoveImportTrades: the workbook has no Table import_settings` | the host's own refusal, in the form a cell shows a failure |
| `#ERROR _ImportTradeIds: ValueError: the filter returned 104 more than once, expected each trade ID once` | the seam's or the library's refusal, exactly as a cell would show it |

One ID is `1 ID returned`. The ID the walk stopped at is held by the first Table, in the destinations' order, whose IDs hold it. With the name `import_status` missing there is no cell to write, and the one line, `#ERROR GoosedoveImportTrades: the workbook has no name import_status`, goes to Excel's status bar instead; no run shows a pop-up. When the cell will not take a write, a protected sheet say, the status bar carries the cause with what the cell would have shown: before the run, `#ERROR GoosedoveImportTrades: import_status could not be written: <Excel's words>; nothing was fetched`, and the run is not started; during the run, `...; the run's line: 3 IDs returned, 1 to fetch: 105; stopped at 104, held by Trades_NYMEX`, the cell keeping its progress text, the most a protected sheet allows.

## The request

One POST to the endpoint, the filter's text as its body, sent as it stands in the cell with `Content-Type: application/json; charset=utf-8` and `Accept: application/json`, through Python's standard library with a timeout of thirty seconds to connect and for each read; no credentials, the ticket's decision 4. The system's proxy settings apply as urllib reads them, the environment's and then Windows' own, so the request takes the road the desk's browser takes. The answer is read whole as UTF-8 text and must be a JSON list of whole numbers, each a trade ID once, in any order. The request is sent once and answered by the address it was sent to: a redirect is refused with its status and never followed, since following one would turn the POST into a GET without the filter's text, and only 200 is an answer, so a 201, 202 or 206 with IDs in it is refused too, a 206 being a partial answer. Whether the real API takes the filter as a POST body or as part of the address is settled against it on the first run; the ticket's decision 10 records the form built and the one line that changes it.

The request's refusals name the address and the cause: `the filter request to http://api.desk/trades/search answered 500 Internal Server Error, expected 200`; `... answered 302 Found, expected 200`; `... answered 206 Partial Content, expected 200`; `... failed: timed out`; `... failed: [WinError 10061] No connection could be made because the target machine actively refused it`; `... answered 2 bytes that are not UTF-8 text`; `the filter request to nowhere failed: expected an http or https address`, before any request leaves. The reader's: `the filter's answer is an object, expected a list of trade IDs`; `the filter's item 2 is text '104', expected a whole number, a trade ID`; `the filter's answer is not JSON: Expecting value: line 1 column 1 (char 0)`.

## The walk

The IDs returned are sorted descending and read newest first; an ID the workbook holds stops the walk there, every ID before it is to fetch in that order, and every ID after it is neither fetched nor looked at, the ticket's deliberate early stop and the assumption it rests on. A repeated ID is refused by name. [walk.py](../../../src/goosedove/importer/walk.py) is array code over the IDs, one sort, one look for a repeat, one membership test and one search, and reports `ids_returned` and `ids_to_fetch`.

## The host's reading

The command runs on Excel's main thread in its own macro context and reads the workbook through the object model, the one place the add-in does. It finds each Table by name on any sheet, reads the headers exactly spelled, and reads the `trade_id` column of every participating Table cell by cell: a number crosses, a blank holds no trade and is passed over, so a Table made of headers alone, with the one empty row Excel gives it, holds nothing; a text, a boolean or an Excel error is refused by the Table and the row, `Trades_NYMEX row 2 trade_id is text 'abc', expected number`, since the IDs of every Table cross as one column and the seam's own words could name no Table. The host checks no meaning: it tells one kind of cell from another, as its scan does. The settings' values cross as their cells hold them, for the seam to judge in its words, `#ERROR _ImportTradeIds: endpoint is blank, expected text`; an Excel error in a value is the host's refusal, since the object model hands an error over as a number.

The IDs of every participating Table stand together, each Table's IDs in a run, in the order the destinations first name the Tables, a Table named twice read once; beside each ID the host passes its Table's name. The library makes the IDs whole once, `whole_trade_ids`, and refuses the first that is not by its Table and its place among that Table's IDs: `Trades_NYMEX trade_id 2 is 90.5, expected a whole number of at most 15 digits`.

The request leaves on a thread of its own, so Excel stays free while it waits: the seam's entry takes Python's lock in turn with any recalculation and lets it go while the network waits. The line comes back onto Excel's thread through Excel-DNA's `QueueAsMacro`, the one way a cell may be written from elsewhere, and is written into the status cell; [host.md](../../seam/host.md#the-import-command) says how.

The host's own refusals, each in the status cell as `#ERROR GoosedoveImportTrades: ...`: `no workbook is open`; `the workbook has no Table import_settings`; `import_settings has headers setting, valeur, expected setting and value`; `import_settings has no rows, expected endpoint and filter`; `import_settings row 2 has setting text 'filtre', expected endpoint or filter`; `import_settings names endpoint twice, expected once`; `import_settings has no row filter, expected endpoint and filter`; `import_settings value of endpoint is an Excel error, expected text`; `import_destinations has headers index, table, expected index, clearing_house and table`; `import_destinations row 2 has table blank, expected a Table's name`; `import_destinations row 2 names Trades_X, which is not a Table in this workbook`; `Trades_NYMEX has no column trade_id`; `import_status refers to 4 cells, expected one`.

## The seam's entry

```python
def _ImportTradeIds(
    endpoint: str,
    filter: str,
    trade_ids: NumberColumn | None = None,
    tables: TextColumn | None = None,
) -> str: ...
```

Registered through `host_function`, the one entry the host alone calls: prepared and checked as every function is, its arguments by [inputs.md](../../seam/inputs.md)'s rules and its text result by [outputs.md](../../seam/outputs.md)'s, and left out of what Excel is told, so no formula reaches it and nothing fetches on a recalculation, the ticket's decision 7. The host calls it with the two settings and, when any Table holds an ID, the two columns, the IDs and one Table name per ID; with no ID held it leaves both out, and the entry takes `None` for each, the seam's rule for an argument left out. The two come together or not at all: `trade_ids is given without tables, expected both, one table per ID`; `tables has 1 names, expected one per trade ID, 2`.

## Tests

| Case | Where |
|---|---|
| the request is a POST carrying the filter as its body; the answer as IDs; a status other than 200, a 201, 202 or 206 with IDs in it among them, a redirect refused and never followed, an answer that is no list, no JSON or no text, nobody listening, an answer that never comes, an endpoint that is no http address refused before any request, each in its words; the counts | `tests/unit/test_import_fetch.py` |
| the line's words; the issue's table through the run; the holder the first Table in order; the twenty named and the rest counted; the two columns together; the whole-ID refusal by Table and place, before any request; the entry prepared and never told to Excel; its refusals in a cell's form | `tests/unit/test_import_run.py` |
| the walk: the issue's table, the edges, the repeat, the reader's refusals, the property every walk keeps | `tests/unit/test_import_walk.py` |
| the counts; the walk, the reader and the run itemized, through the entry as the host calls it, against the stand-in in a process of its own; the peaks | `tests/performance/test_import_budgets.py` |
| the host's readers of the two Tables and of a `trade_id` column, each refusal; the line through the host's path against a stand-in and against a port nobody listens on; five runs on fresh threads over a hundred thousand held IDs leaving no set of buffers behind; the entry absent from the registration | `host/Goosedove.Host.Tests/ImporterTests.cs` |
| the command in a hidden Excel, run by name, over the Tables and the status cell against the stand-in in a process of its own: the issue's table, the request as the stand-in saw it, the walk's three ends, each refusal, the status cell protected before a run and during one, the status bar with the name gone | `tools/excel_lifetime.ps1`, the `import` group |
| the stand-in for the API, its paths and what it records | `tools/import_standin.py` |

## Not here

The detail requests, the rows a trade becomes and their insertion into the Tables are the second slice's, waiting on a redacted payload; so are the `index` and `clearing_house` columns' meaning and the check of a destination Table's headers against the instrument's fields. The shortcut key itself is not pressed by any test: the hidden Excel runs the command by name, as `Application.Run` runs any macro, and the binding is Excel-DNA's from the attribute, Excel's own notation `^F` for Ctrl+Shift+F, as its template binds Ctrl+Shift+D with `^D`. Credentials, a pop-up of any kind, a cursor or a second record of what was imported, and the GET form of the filter request are not built, the ticket's list.
