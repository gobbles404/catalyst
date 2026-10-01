numpy 2.5.2

### c2 futures-fixings-wholeness-by-count: busday_offset column + mask + any vs one busday_count

| operation | size | as-is us | proposed us | change | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|---:|
| wholeness check, success path | 100 | 15.58 | 2.77 | -82% | 2,304 | 1,912 |
| wholeness check, success path | 260 | 26.72 | 3.21 | -88% | 3,584 | 1,912 |
| wholeness check, success path | 2,600 | 145.82 | 2.77 | -98% | 23,999 | 1,912 |
| wholeness check, success path | 10,000 | 447.76 | 3.14 | -99% | 90,599 | 1,912 |
| wholeness check, success path | 26,000 | 993.95 | 2.95 | -100% | 234,599 | 1,912 |
