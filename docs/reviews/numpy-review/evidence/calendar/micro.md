| operation | as-is us | proposed us | change | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|
| futures contract, 90 days / 4 contracts |     1.86 |     4.61 | +147% | 1,040 | 1,504 |
| futures contract, 360 days / 13 contracts |     5.75 |     4.58 |  -20% | 3,200 | 3,808 |
| futures contract, 9990 days / 334 contracts |   195.23 |    10.71 |  -95% | 80,240 | 85,984 |
| futures contract, 10000 days / 10001 contracts |   223.21 |    55.24 |  -75% | 80,320 | 240,736 |
| futures contract, 36000 days / 1201 contracts |   636.66 |    18.17 |  -97% | 288,320 | 307,936 |
| gas daily contract, 90 days / 3 months |     1.97 |     4.23 | +114% | 1,040 | 1,504 |
| gas daily contract, 360 days / 12 months |     4.45 |     4.61 |   +4% | 3,200 | 3,808 |
| gas daily contract, 9990 days / 333 months |   148.87 |    10.91 |  -93% | 80,240 | 85,984 |
| gas daily contract, 36000 days / 1200 months |   621.12 |    22.39 |  -96% | 288,320 | 307,936 |
| is_fixed + first_unfixed, 100 days |     1.92 |     2.24 |  +17% | 620 | 389 |
| is_fixed + first_unfixed, 360 days |     2.49 |     2.45 |   -2% | 880 | 649 |
| is_fixed + first_unfixed, 10000 days |    13.41 |     2.77 |  -79% | 10,520 | 10,321 |
| is_fixed + first_unfixed, 36000 days |    41.49 |     3.99 |  -90% | 36,520 | 36,321 |
| is_fixed by datetime64 vs int64 view, 100 days |     1.23 |     2.85 | +132% | 620 | 855 |
| is_fixed by datetime64 vs int64 view, 360 days |     1.43 |     3.05 | +114% | 880 | 855 |
| is_fixed by datetime64 vs int64 view, 10000 days |    12.95 |     6.46 |  -50% | 10,520 | 10,375 |
| is_fixed by datetime64 vs int64 view, 36000 days |    41.61 |    14.16 |  -66% | 36,520 | 36,375 |
| order check by datetime64 vs int64 view, 13 expiries |     1.08 |     1.20 |  +11% | 460 | 556 |
| order check by datetime64 vs int64 view, 121 expiries |     1.25 |     1.24 |   -0% | 568 | 664 |
| order check by datetime64 vs int64 view, 1201 expiries |     2.91 |     1.83 |  -37% | 1,648 | 1,744 |
| order check by datetime64 vs int64 view, 10000 expiries |    14.35 |     4.92 |  -66% | 10,447 | 10,543 |
| iferc dates copy vs reference, 100 months |     0.63 |     0.05 |  -92% | 1,056 | 0 |
| iferc dates copy vs reference, 120 months |     0.61 |     0.05 |  -92% | 1,216 | 0 |
| iferc dates copy vs reference, 1200 months |     0.93 |     0.05 |  -95% | 9,856 | 0 |
| iferc dates copy vs reference, 10000 months |     3.41 |     0.06 |  -98% | 80,256 | 0 |
| history row offsets, 100 fixings |     6.46 |     7.53 |  +17% | 2,224 | 1,471 |
| history row offsets, 260 fixings |     8.90 |     9.17 |   +3% | 4,784 | 3,443 |
| history row offsets, 10000 fixings |    55.27 |    29.64 |  -46% | 168,976 | 169,023 |
| history row offsets, 26000 fixings |   134.06 |    69.79 |  -48% | 440,976 | 441,023 |
