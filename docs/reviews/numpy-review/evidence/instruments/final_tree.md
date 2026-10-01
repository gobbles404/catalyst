as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-3/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| look.FirstOfDates.100 | 18.30 (18.30..20.74) | 16.41 (16.41..21.46) | -10% |  | 2,892 -> 2,892 (+0%) | same | same |
| look.FirstOfDates.10k | 71.41 (71.41..103.61) | 68.22 (68.22..77.96) | -4% |  | 171,192 -> 171,192 (+0%) | same | same |
| create.DiscountCurve.daily.3631 | 274.29 (274.29..440.83) | 248.03 (248.03..277.48) | -10% |  | 216,235 -> 216,235 (+0%) | same | same |
| create.DiscountCurve.anchors12.3630 | 146.01 (146.01..246.23) | 153.59 (153.59..250.10) | +5% |  | 89,570 -> 89,570 (+0%) | same | same |
| create.HolidayCalendar.100 | 20.38 (20.38..30.61) | 19.19 (19.19..30.60) | -6% |  | 2,892 -> 2,892 (+0%) | same | same |
| create.HolidayCalendar.1000 | 27.30 (27.30..37.15) | 26.59 (26.59..37.75) | -3% |  | 18,192 -> 18,192 (+0%) | same | same |
| create.FuturesFixings.260 | 78.74 (78.74..101.16) | 75.93 (75.93..124.88) | -4% |  | 11,194 -> 11,194 (+0%) | same | same |
| create.FuturesFixings.2600 | 240.47 (240.47..382.49) | 243.78 (243.78..286.35) | +1% |  | 93,094 -> 93,094 (+0%) | same | same |
| create.FuturesFixings.26000 | 1857.82 (1857.82..2938.97) | 1870.22 (1870.22..2956.50) | +1% |  | 912,094 -> 912,094 (+0%) | same | same |
| create.Calendar.futures.360 | 40.26 (40.26..57.03) | 42.35 (42.35..43.92) | +5% |  | 8,572 -> 8,572 (+0%) | same | same |
| create.Calendar.futures.36000 | 985.10 (985.10..1394.49) | 974.36 (974.36..1060.86) | -1% |  | 649,228 -> 649,228 (+0%) | same | same |
| read.DiscountCurve.3631 | 97.46 (97.46..178.35) | 99.34 (99.34..112.85) | +2% |  | 128,381 -> 128,381 (+0%) | same | same |
| own.cells_from_buffers.10k | 7.80 (7.80..11.73) | 7.56 (7.56..11.23) | -3% |  | 90,768 -> 90,768 (+0%) | same | same |
| own.cells_from_buffers.100 | 3.97 (3.97..4.69) | 3.86 (3.86..7.29) | -3% |  | 1,636 -> 1,636 (+0%) | same | same |
