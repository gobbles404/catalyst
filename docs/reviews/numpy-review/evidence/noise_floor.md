as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: <repo>/src/goosedove/__init__.py
rounds: 3, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| probe.EchoMixed.numbers.10k | 26.45 (26.45..27.44) | 29.30 (29.30..37.34) | +11% | up | 50,536 -> 50,536 (+0%) | same | same |
| look.FirstOfDates.10k | 37.99 (37.99..42.83) | 42.81 (42.81..44.11) | +13% |  | 171,192 -> 171,192 (+0%) | same | same |
| create.DiscountCurve.daily.3631 | 153.78 (153.78..180.81) | 161.93 (161.93..193.42) | +5% |  | 216,235 -> 216,235 (+0%) | same | same |
| create.FuturesFixings.2600 | 128.35 (128.35..134.55) | 130.99 (130.99..139.40) | +2% |  | 93,094 -> 93,094 (+0%) | same | same |
| create.FuturesFixings.26000 | 932.71 (932.71..1001.76) | 937.82 (937.82..1076.03) | +1% |  | 912,094 -> 912,094 (+0%) | same | same |
| create.Calendar.futures.3630 | 90.78 (90.78..98.50) | 94.92 (94.92..98.00) | +5% |  | 66,677 -> 66,677 (+0%) | same | same |
| create.MarketHistory.futures.3630 | 20.00 (20.00..21.31) | 20.27 (20.27..21.42) | +1% |  | 16,584 -> 16,584 (+0%) | same | same |
| read.DiscountCurve.3631 | 74.65 (74.65..77.56) | 73.52 (73.52..82.39) | -2% |  | 128,381 -> 128,381 (+0%) | same | same |
| own.cells_from_buffers.10k | 6.03 (6.03..6.30) | 6.10 (6.10..6.27) | +1% |  | 90,768 -> 90,768 (+0%) | same | same |
