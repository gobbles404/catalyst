numpy 2.5.2

### c3 futures-fixings-closed-by-all: ~is_busday + any vs is_busday + all

| operation | size | as-is us | proposed us | change | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|---:|
| closed-day check, success path | 100 | 4.26 | 3.74 | -12% | 1,140 | 1,140 |
| closed-day check, success path | 260 | 6.42 | 5.87 | -9% | 1,300 | 1,300 |
| closed-day check, success path | 2,600 | 38.89 | 38.30 | -2% | 5,392 | 3,640 |
| closed-day check, success path | 10,000 | 140.17 | 139.29 | -1% | 20,192 | 11,040 |
| closed-day check, success path | 26,000 | 334.33 | 336.26 | +1% | 52,192 | 27,040 |
