as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.DiscountCurve.daily.3631 | 262.55 (262.55..728.29) | 246.68 (246.68..509.45) | -6% |  | 216,235 -> 216,347 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4; ndarray.view: 0->1 | same |
| create.DiscountCurve.anchors12.3630 | 165.79 (165.79..283.87) | 143.48 (143.48..289.40) | -13% |  | 89,570 -> 89,682 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4; ndarray.view: 0->1 | same |
| create.DiscountCurve.daily.365 | 106.69 (106.69..176.85) | 106.16 (106.16..241.72) | -0% |  | 23,541 -> 23,653 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4; ndarray.view: 0->1 | same |
| create.DiscountCurve.daily.36500 | 2800.60 (2800.60..9289.38) | 2868.43 (2868.43..8896.15) | +2% |  | 2,155,506 -> 2,155,618 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4; ndarray.view: 0->1 | same |
| reject.DiscountCurve.rises-last.3631 | 89.81 (89.81..206.74) | 103.92 (103.92..308.44) | +16% |  | 63,983 -> 63,983 (+0%) | ndarray.all: 0->1; ndarray.any: 4->3 | same |
| reject.DiscountCurve.unordered-last.3631 | 106.33 (106.33..229.58) | 105.50 (105.50..206.69) | -1% |  | 63,983 -> 63,983 (+0%) | ndarray.all: 0->1; ndarray.any: 5->4; ndarray.view: 0->1 | same |
