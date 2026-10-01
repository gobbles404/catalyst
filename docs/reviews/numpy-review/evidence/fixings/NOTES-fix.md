# Fix: gas-daily-consecutive-by-span (worktree wf_0d4f8983-1f8-2, commit 686f217)

Flaw (both refuters): NaT in row 1 followed by the least int64 day numbers (INT64_MIN+1, ...)
passed the order mask and the span test, so a record with a NaT flow day was built; as-is refuses
it with "flow_date row 2 is -25252734927764585-06-08, expected NaT, the day after row 1's NaT".

Fix: one scalar test on the first day folded into the failure condition,
`days.size > 1 and (int(serial[0]) == NAT_DAY or <span test>)`, NAT_DAY = int(np.iinfo(np.int64).min)
at module level. The failure path is the old code, so the message is the old one word for word.
The guard moved from `days.size` to `days.size > 1`: for one row the span test was always 0 == 0,
and a one-row NaT must stay accepted as as-is accepts it (folding the NaT test in under `days.size`
would have sent it to argmax of an empty mask). Comment updated: a NaT after row 1 breaks the
order, a NaT first is told by its number. No per-element isnat pass.

Evidence
- Refuter scripts (gd.py, q3.py) on as-is vs fixed: all NaT cases identical messages.
- eq_cases.py: added 7 gd cases (nat_then_least{2,3,4,10}, nat_then_least_gap, nat_nat_then_least,
  one_least); backup in eq_cases.before_fix.py. eq_compare on fixed tree: 13,957 cases, 0 mismatches
  (eq_gas-daily-consecutive-by-span.after_fix.txt). On the pre-fix tree (trees/prefix): 4 mismatches,
  the nat_then_least cases, so the new cases catch the hole.
- ruff check/format clean, pyright 0 errors, unit 1271 passed, performance 103 passed; no budget pin moved.
- bench (bench_fix_gd.log): GasDailyFixings.365 peak 13,084 -> 10,012; .3652 121,555 -> 92,187;
  ledger ndarray.view 0->1 only. Saving survives.

Not done / left as found: 2-D inputs (Python-only). As-is accepts a (3,1) column and gives an odd
ValueError for (2,2); the candidate (before and after this fix) raises TypeError from int() of a
1-element row. Accept -> loud failure, not loud -> silent, so not touched here; flagged for the owner.
