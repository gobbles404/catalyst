# Fix for bridge-serials-out / bridge-table-column-writes-into-slots (group bridge-out-a)

Worktree: worktrees/wf_1c4545af-6ae-2
Fix commit: 228f94c fix(bridge-serials-out): read the days' int64 view over native single days (diff: fix.diff)

## Flaw
The gate `_unit(x) == "D"` admits datetime64[2D], [7D] and big-endian '>M8[D]'. The candidates read
`days.view(np.int64)`, which for those dtypes is not a count of days: [2D] gave silently wrong serials
(as-is 46163, proposed 35866); big-endian was refused as outside the calendar.

## Fix
`DAY: Final = np.dtype("datetime64[D]")`; in `_serials` and `_table_column`'s day branch,
`counted = days.astype(DAY, copy=False).view(np.int64)`. Gate unchanged. The comment above EPOCH_DAYS
and both docstrings now say the view is taken over DAY. `_date_out` goes through `_serials`, so the
scalar [2D] case is fixed too. No test added (minimal fix; the probes below are the evidence).

## Evidence
- Refuter scripts (multi_day.py, byteorder.py, probe_dates.py): fixed == as-is on every line;
  probe_dates.py output byte-identical (probe_dates.asis.out / probe_dates.fixed.out).
- fix_probe.py: [2D]/[7D]/[D] x little/big endian x {ok, NaT, outside, early, late, huge int64, strided}
  x {column, row, table, scalar}: 168 same, 0 diff vs as-is, run with -W error.
- No copy: fix_nocopy_record.out: a holiday_calendar record's frozen datetime64[D] column,
  `astype(DAY, copy=False) is col` True, view shares memory; table peak 129,348 B (= slots + kinds),
  as-is 372,714 B. Also True for a native, read-only and strided array.
- Equivalence scripts re-run on fixed tree (eq_*.fix.out): eq_serials 652 equal / 5 diff,
  eq_table 307,887 / 1, eq_mixed_out 10,098 / 4, eq_text_units 1,298 / 0 -- identical totals and
  identical DIFF lines to the verifier's *.final.out (all pre-existing, loud->loud or type-violating).
- ruff check/format, pyright: clean. tests/unit: all pass. tests/performance: the same 10 failing
  tests as the pre-fix tree (pins moved by the candidates). Fix's own ledger effect (ledgers/ledger_diff.txt):
  numpy ledger 'ndarray.astype' +1 per date column (not 'numpy.asarray' as anticipated) in
  test_a_reader_is_a_text_call_one_lookup_and_a_table_out, test_reading_a_calendar_back_rebuilds_nothing,
  test_reading_a_market_history_back_rebuilds_nothing, test_reading_a_market_back_rebuilds_nothing[x3].
  Package ledgers unchanged; allocation pin test_a_creator_of_a_small_object_and_its_reader_stay_small
  still 2102 > 2048 (moved by the candidates, unchanged by the fix).
- bench_compare (3 rounds): pre-fix -> fixed: every peak byte identical, only ndarray.astype +1 per
  date column (bench.prefix_vs_fix.md). as-is -> fixed: savings survive (bench.fix.md), e.g.
  EchoDates.10k 251,256 -> 171,192; FuturesFixings.2600 92,296 -> 57,885; HolidayCalendar.100 3,850 -> 1,763.
