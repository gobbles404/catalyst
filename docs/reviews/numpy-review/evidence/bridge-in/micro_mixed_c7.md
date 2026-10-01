micro: micro_mixed.py; as-is scratch/verify/bridge-in/trees/c6/src vs proposed scratch/verify/bridge-in/trees/c7/src; 5 rounds, least of 7 repeats
| operation | as-is us (spread) | proposed us (spread) | change | peak B as-is -> proposed | numpy calls as-is -> proposed |
|---|---:|---:|---:|---:|---|
| CountMixed empty text mid 100 | 15.24 (15.24..26.38) | 12.52 (12.52..13.50) | -18% | 4,344 -> 4,344 | ndarray.ravel: 3->2 |
| CountMixed blank mid 100 (control) | 6.90 (6.90..7.71) | 7.17 (7.17..13.02) | +4% | 1,803 -> 1,803 | same |
| CountMixed empty text mid 10000 | 148.72 (148.72..163.79) | 143.04 (143.04..254.82) | -4% | 103,372 -> 103,372 | ndarray.ravel: 3->2 |
| CountMixed blank mid 10000 (control) | 8.77 (8.77..9.58) | 8.93 (8.93..14.93) | +2% | 10,456 -> 10,456 | same |
