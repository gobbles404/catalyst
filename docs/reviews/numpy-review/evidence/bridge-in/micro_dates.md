micro: micro_dates.py; as-is <repo>/src vs proposed scratch/verify/bridge-in/trees/c1/src; 3 rounds, least of 7 repeats
| operation | as-is us (spread) | proposed us (spread) | change | peak B as-is -> proposed | numpy calls as-is -> proposed |
|---|---:|---:|---:|---:|---|
| _dates column 100 | 10.32 (10.32..15.34) | 9.92 (9.92..12.27) | -4% | 2,732 -> 1,248 | ndarray.all: 0->1; ndarray.any: 1->0; ndarray.astype: 2->0; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 0->2; ndarray.view: 0->2; ufunc.reduce: 1->3 |
| _dates column 10000 | 57.52 (57.52..93.16) | 44.88 (44.88..48.13) | -22% | 171,032 -> 90,289 | ndarray.all: 0->1; ndarray.any: 1->0; ndarray.astype: 2->0; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 0->2; ndarray.view: 0->2; ufunc.reduce: 1->3 |
| _dates_of strided table column 100 | 14.89 (14.89..21.91) | 12.78 (12.78..13.57) | -14% | 2,828 -> 1,344 | ndarray.all: 0->1; ndarray.any: 1->0; ndarray.astype: 2->0; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 0->2; ndarray.view: 0->2; ufunc.reduce: 1->3 |
| _dates_of strided table column 2500 | 40.31 (40.31..56.39) | 27.99 (27.99..37.85) | -31% | 43,628 -> 22,885 | ndarray.all: 0->1; ndarray.any: 1->0; ndarray.astype: 2->0; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 0->2; ndarray.view: 0->2; ufunc.reduce: 1->3 |
| _dates rejected fraction mid 100 | 11.17 (11.17..17.04) | 10.80 (10.80..20.57) | -3% | 2,852 -> 2,852 | ndarray.any: 1->0; ndarray.min: 0->1 |
| _dates rejected text last 100 | 16.26 (16.26..24.43) | 20.38 (20.38..23.44) | +25% | 2,852 -> 2,852 | ndarray.any: 1->0; ndarray.min: 0->1 |
| _dates rejected fraction mid 10000 | 21.68 (21.68..33.82) | 42.62 (42.62..54.39) | +97% | 90,192 -> 90,192 | ndarray.any: 1->0; ndarray.min: 0->1 |
| _dates rejected text last 10000 | 33.41 (33.41..51.59) | 34.49 (34.49..57.49) | +3% | 90,192 -> 90,192 | ndarray.any: 1->0; ndarray.min: 0->1 |
