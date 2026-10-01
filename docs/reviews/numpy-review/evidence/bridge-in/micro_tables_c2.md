micro: micro_tables.py; as-is <repo>/src vs proposed scratch/verify/bridge-in/trees/c2/src; 3 rounds, least of 7 repeats
| operation | as-is us (spread) | proposed us (spread) | change | peak B as-is -> proposed | numpy calls as-is -> proposed |
|---|---:|---:|---:|---:|---|
| _refine Trades 25 rows | 48.25 (48.25..54.75) | 22.52 (22.52..23.30) | -53% | 4,224 -> 1,729 | ndarray.cumsum: 1->0; ndarray.sum: 2->0; numpy.array: 1->0; ufunc.reduce: 6->4 |
| _refine two text columns 25 rows | 45.51 (45.51..46.34) | 16.73 (16.73..17.24) | -63% | 4,529 -> 1,162 | ndarray.cumsum: 1->0; ndarray.sum: 3->0; numpy.array: 1->0; ufunc.reduce: 8->5 |
| _refine Trades 250 rows | 81.28 (81.28..82.45) | 30.94 (30.94..33.71) | -62% | 15,798 -> 5,554 | ndarray.cumsum: 1->0; ndarray.sum: 2->0; numpy.array: 1->0; ufunc.reduce: 6->4 |
| _refine two text columns 250 rows | 90.70 (90.70..92.18) | 23.85 (23.85..25.78) | -74% | 18,479 -> 4,987 | ndarray.cumsum: 1->0; ndarray.sum: 3->0; numpy.array: 1->0; ufunc.reduce: 8->5 |
| _refine Trades 2500 rows | 281.04 (281.04..291.66) | 61.70 (61.70..140.69) | -78% | 135,048 -> 43,804 | ndarray.cumsum: 1->0; ndarray.sum: 2->0; numpy.array: 1->0; ufunc.reduce: 6->4 |
| _refine two text columns 2500 rows | 425.82 (425.82..462.79) | 49.50 (49.50..58.74) | -88% | 157,979 -> 43,237 | ndarray.cumsum: 1->0; ndarray.sum: 3->0; numpy.array: 1->0; ufunc.reduce: 8->5 |
| _numbers_of 25 | 2.41 (2.41..2.46) | 2.35 (2.35..3.14) | -3% | 314 -> 314 | same |
| _booleans_of 25 | 2.83 (2.83..2.98) | 2.97 (2.97..3.93) | +5% | 338 -> 338 | same |
| text look (kinds col) 25 | 1.85 (1.85..1.92) | 1.84 (1.84..2.53) | -1% | 218 -> 218 | same |
| _numbers_of 2500 | 5.37 (5.37..5.78) | 5.44 (5.44..5.60) | +1% | 2,789 -> 2,789 | same |
| _booleans_of 2500 | 8.86 (8.86..9.34) | 8.95 (8.95..9.25) | +1% | 5,288 -> 5,288 | same |
| text look (kinds col) 2500 | 4.67 (4.67..5.03) | 4.79 (4.79..4.90) | +2% | 2,693 -> 2,693 | same |
