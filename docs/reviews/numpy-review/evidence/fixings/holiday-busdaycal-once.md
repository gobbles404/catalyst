as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.HolidayCalendar.100 | 20.55 (20.55..39.34) | 29.38 (29.38..43.04) | +43% |  | 2,892 -> 3,056 (+6%) | same | same |
| create.HolidayCalendar.1000 | 30.77 (30.77..54.58) | 70.10 (70.10..115.84) | +128% | up | 18,192 -> 24,656 (+36%) | same | same |
| create.FuturesFixings.260 | 83.10 (83.10..128.92) | 75.26 (75.26..208.86) | -9% |  | 11,194 -> 10,346 (-8%) | same | same |
| create.FuturesFixings.2600 | 268.02 (268.02..439.28) | 239.38 (239.38..448.09) | -11% |  | 93,094 -> 92,246 (-1%) | same | same |
| create.FuturesFixings.26000 | 2015.26 (2015.26..3036.73) | 1866.30 (1866.30..2978.68) | -7% |  | 912,094 -> 911,246 (-0%) | same | same |
| create.FuturesFixings.260.h1000 | 113.63 (113.63..173.41) | 88.28 (88.28..153.43) | -22% |  | 18,394 -> 10,346 (-44%) | same | same |
| create.FuturesFixings.2600.h1000 | 506.94 (506.94..1062.40) | 482.01 (482.01..615.11) | -5% |  | 100,294 -> 92,246 (-8%) | same | same |
| create.FuturesFixings.260.h10000 | 469.64 (469.64..794.53) | 86.84 (86.84..134.04) | -82% | down | 90,394 -> 10,346 (-89%) | same | same |
| create.Calendar.futures.360 | 41.71 (41.71..71.00) | 42.23 (42.23..62.52) | +1% |  | 8,572 -> 7,772 (-9%) | same | same |
| create.Calendar.futures.3630 | 163.46 (163.46..397.66) | 145.71 (145.71..251.75) | -11% |  | 66,677 -> 66,677 (+0%) | same | same |
| create.Calendar.futures.36000 | 982.43 (982.43..1520.94) | 977.76 (977.76..1521.78) | -0% |  | 649,228 -> 649,228 (+0%) | same | same |
| create.Calendar.futures.360.h1000 | 72.15 (72.15..126.07) | 42.88 (42.88..63.16) | -41% | down | 15,772 -> 7,772 (-51%) | same | same |
| create.Calendar.futures.3630.h1000 | 285.71 (285.71..416.10) | 228.80 (228.80..297.72) | -20% |  | 71,471 -> 66,677 (-7%) | same | same |
| create.Calendar.futures.360.h10000 | 369.26 (369.26..627.35) | 42.57 (42.57..55.70) | -88% | down | 87,772 -> 7,772 (-91%) | same | same |
| create.HolidayCalendar.10000 | 79.03 (79.03..157.22) | 454.50 (454.50..573.88) | +475% | up | 171,192 -> 240,656 (+41%) | same | same |
