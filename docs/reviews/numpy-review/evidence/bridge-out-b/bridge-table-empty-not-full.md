as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-out-b/snap/table/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| read.DiscountCurve.3631 | 100.09 (100.09..251.31) | 94.41 (94.41..193.45) | -6% |  | 128,381 -> 128,381 (+0%) | numpy.asarray: 1->0 | same |
| read.HolidayCalendar.100 | 48.93 (48.93..96.50) | 47.90 (47.90..95.96) | -2% |  | 3,850 -> 3,850 (+0%) | numpy.asarray: 1->0 | same |
| read.Index | 65.59 (65.59..121.78) | 60.17 (60.17..104.73) | -8% |  | 1,137 -> 1,137 (+0%) | same | same |
| read.FuturesFixings.2600 | 97.55 (97.55..168.36) | 82.17 (82.17..172.95) | -16% |  | 92,296 -> 92,296 (+0%) | numpy.asarray: 1->0 | same |
| read.PriceVector.10000 | 58.39 (58.39..98.37) | 51.60 (51.60..110.49) | -12% |  | 140,812 -> 140,812 (+0%) | numpy.asarray: 1->0 | same |
| read.Calendar.futures.3630 | 486.74 (486.74..864.25) | 525.40 (525.40..866.43) | +8% |  | 251,938 -> 251,970 (+0%) | same | same |
| out.Table.num2.100 | 55.99 (55.99..88.74) | 51.53 (51.53..83.89) | -8% |  | 4,798 -> 4,798 (+0%) | numpy.asarray: 1->0 | same |
| out.Table.num4.100 | 62.55 (62.55..113.43) | 64.66 (64.66..104.35) | +3% |  | 6,664 -> 6,664 (+0%) | numpy.asarray: 1->0 | same |
| out.Table.text.100 | 71.77 (71.77..93.31) | 68.01 (68.01..130.54) | -5% |  | 6,453 -> 6,453 (+0%) | same | same |
| out.Table.num2.10k | 173.54 (173.54..200.18) | 173.49 (173.49..276.71) | -0% |  | 351,326 -> 351,326 (+0%) | numpy.asarray: 1->0 | same |
| out.Table.num4.10k | 298.35 (298.35..498.56) | 248.09 (248.09..396.94) | -17% |  | 560,856 -> 560,856 (+0%) | numpy.asarray: 1->0 | same |
| out.Table.text.10k | 1058.84 (1058.84..1971.18) | 1049.52 (1049.52..2038.40) | -1% |  | 938,401 -> 938,401 (+0%) | same | same |
| out.Table.num2.100k | 3395.02 (3395.02..5194.56) | 3229.89 (3229.89..5457.22) | -5% |  | 3,501,326 -> 3,501,326 (+0%) | numpy.asarray: 1->0 | same |
| out.Table.num4.100k | 3043.04 (3043.04..4934.49) | 2896.38 (2896.38..4602.97) | -5% |  | 5,600,856 -> 5,600,856 (+0%) | numpy.asarray: 1->0 | same |
| out.Table.text.100k | 17442.87 (17442.87..26382.39) | 16432.24 (16432.24..28233.93) | -6% |  | 9,668,401 -> 9,668,401 (+0%) | same | same |
