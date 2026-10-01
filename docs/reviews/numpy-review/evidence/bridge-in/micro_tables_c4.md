micro: micro_tables.py; as-is scratch/verify/bridge-in/trees/c4base/src vs proposed scratch/verify/bridge-in/trees/c4/src; 3 rounds, least of 7 repeats
| operation | as-is us (spread) | proposed us (spread) | change | peak B as-is -> proposed | numpy calls as-is -> proposed |
|---|---:|---:|---:|---:|---|
| _refine Trades 25 rows | 24.29 (24.29..44.40) | 24.13 (24.13..42.49) | -1% | 1,162 -> 1,137 | ndarray.any: 3->0; ndarray.max: 1->4; ndarray.min: 1->3; ufunc.reduce: 6->8 |
| _refine two text columns 25 rows | 16.63 (16.63..33.00) | 13.05 (13.05..24.73) | -21% | 1,162 -> 1,112 | ndarray.any: 5->0; ndarray.max: 0->5; ndarray.min: 0->2; ufunc.reduce: 5->7 |
| _refine Trades 250 rows | 26.59 (26.59..29.04) | 24.52 (24.52..28.96) | -8% | 3,412 -> 3,162 | ndarray.any: 3->0; ndarray.max: 1->4; ndarray.min: 1->3; ufunc.reduce: 6->8 |
| _refine two text columns 250 rows | 24.20 (24.20..42.75) | 15.33 (15.33..18.27) | -37% | 4,987 -> 4,712 | ndarray.any: 5->0; ndarray.max: 0->5; ndarray.min: 0->2; ufunc.reduce: 5->7 |
| _refine Trades 2500 rows | 54.79 (54.79..88.22) | 49.49 (49.49..66.12) | -10% | 25,912 -> 23,412 | ndarray.any: 3->0; ndarray.max: 1->4; ndarray.min: 1->3; ufunc.reduce: 6->8 |
| _refine two text columns 2500 rows | 51.41 (51.41..88.44) | 33.73 (33.73..76.68) | -34% | 43,237 -> 40,712 | ndarray.any: 5->0; ndarray.max: 0->5; ndarray.min: 0->2; ufunc.reduce: 5->7 |
| _numbers_of 25 | 2.51 (2.51..4.57) | 1.31 (1.31..2.55) | -48% | 314 -> 217 | ndarray.any: 1->0; ndarray.max: 0->1 |
| _booleans_of 25 | 2.79 (2.79..5.05) | 2.63 (2.63..4.89) | -6% | 338 -> 313 | ndarray.any: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 |
| text look (kinds col) 25 | 1.88 (1.88..2.16) | 1.89 (1.89..3.52) | +1% | 218 -> 218 | same |
| _numbers_of 2500 | 5.53 (5.53..6.34) | 2.28 (2.28..4.11) | -59% | 2,789 -> 217 | ndarray.any: 1->0; ndarray.max: 0->1 |
| _booleans_of 2500 | 9.22 (9.22..9.35) | 7.26 (7.26..8.23) | -21% | 5,288 -> 2,788 | ndarray.any: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 |
| text look (kinds col) 2500 | 4.94 (4.94..5.37) | 4.83 (4.83..6.11) | -2% | 2,693 -> 2,693 | same |
