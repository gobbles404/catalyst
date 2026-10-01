numpy 2.5.2

### c5 builders-copy-of-fresh-seam-columns: np.array copy of the seam's column vs keeping it

| operation | size | as-is us | proposed us | change | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|---:|
| date column: np.array(col, 'datetime64[D]') vs keep | 100 | 0.67 | 0.04 | -94% | 1,056 | 0 |
| number column: np.array(col, float64) vs keep | 100 | 0.48 | 0.04 | -92% | 896 | 0 |
| date column: np.array(col, 'datetime64[D]') vs keep | 260 | 0.72 | 0.04 | -95% | 2,336 | 0 |
| number column: np.array(col, float64) vs keep | 260 | 0.56 | 0.04 | -93% | 2,176 | 0 |
| date column: np.array(col, 'datetime64[D]') vs keep | 2,600 | 1.38 | 0.04 | -97% | 21,056 | 0 |
| number column: np.array(col, float64) vs keep | 2,600 | 1.31 | 0.04 | -97% | 20,896 | 0 |
| date column: np.array(col, 'datetime64[D]') vs keep | 10,000 | 3.40 | 0.04 | -99% | 80,256 | 0 |
| number column: np.array(col, float64) vs keep | 10,000 | 3.88 | 0.04 | -99% | 80,096 | 0 |
| date column: np.array(col, 'datetime64[D]') vs keep | 26,000 | 7.83 | 0.04 | -100% | 208,256 | 0 |
| number column: np.array(col, float64) vs keep | 26,000 | 7.94 | 0.04 | -99% | 208,096 | 0 |
