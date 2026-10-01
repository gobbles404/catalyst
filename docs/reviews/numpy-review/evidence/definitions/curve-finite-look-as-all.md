as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.DiscountCurve.daily.3631 | 257.14 (257.14..417.85) | 254.01 (254.01..404.07) | -1% |  | 216,235 -> 216,235 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4 | same |
| create.DiscountCurve.anchors12.3630 | 148.81 (148.81..223.12) | 148.19 (148.19..199.00) | -0% |  | 89,570 -> 89,570 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4 | same |
| create.DiscountCurve.daily.365 | 104.02 (104.02..163.55) | 112.20 (112.20..132.88) | +8% |  | 23,541 -> 23,541 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4 | same |
| create.DiscountCurve.daily.36500 | 2680.46 (2680.46..3620.83) | 2619.44 (2619.44..2943.13) | -2% |  | 2,155,506 -> 2,155,506 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4 | same |
| reject.DiscountCurve.rises-last.3631 | 96.52 (96.52..145.69) | 91.06 (91.06..159.74) | -6% |  | 63,983 -> 63,983 (+0%) | ndarray.all: 0->1; ndarray.any: 4->3 | same |
| reject.DiscountCurve.unordered-last.3631 | 105.23 (105.23..161.27) | 97.67 (97.67..193.18) | -7% |  | 63,983 -> 63,983 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4 | same |
