numpy 2.5.2

### c4 gas-daily-consecutive-by-span: day-after column + mask + any vs int64 mask + span

| operation | size | as-is us | proposed us | change | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|---:|
| consecutive check, success path | 100 | 4.75 | 3.04 | -36% | 1,600 | 483 |
| consecutive check, success path | 365 | 5.86 | 3.01 | -49% | 3,884 | 748 |
| consecutive check, success path | 3,652 | 21.19 | 5.25 | -75% | 33,467 | 4,035 |
| consecutive check, success path | 10,000 | 44.04 | 8.59 | -81% | 90,599 | 10,383 |
| consecutive check, success path | 36,500 | 153.86 | 18.26 | -88% | 329,099 | 36,883 |
