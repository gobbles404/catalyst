as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-3/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| out.Date.const | 12.92 (12.92..14.85) | 4.25 (4.25..4.76) | -67% | down | 1,185 -> 952 (-20%) | generic.view: 0->1; ndarray.any: 2->0; numpy.array: 1->0; ufunc.reduce: 2->0 | _serials: 1->0 |
| out.Date.echo | 16.83 (16.83..19.49) | 6.67 (6.67..7.36) | -60% | down | 1,217 -> 1,144 (-6%) | generic.view: 0->1; ndarray.any: 2->0; numpy.array: 1->0; ufunc.reduce: 2->0 | _serials: 1->0 |
