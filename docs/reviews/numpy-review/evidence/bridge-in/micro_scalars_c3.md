micro: micro_scalars.py; as-is <repo>/src vs proposed scratch/verify/bridge-in/trees/c3/src; 3 rounds, least of 7 repeats
| operation | as-is us (spread) | proposed us (spread) | change | peak B as-is -> proposed | numpy calls as-is -> proposed |
|---|---:|---:|---:|---:|---|
| _date(46164.0) | 2.49 (2.49..4.56) | 0.71 (0.71..1.16) | -72% | 984 -> 64 | same |
| _dates(46164.0) scalar -> 1x1 | 3.44 (3.44..4.39) | 1.68 (1.68..2.07) | -51% | 984 -> 408 | same |
| call _CreateValuationDate(46276.0, 0.5) + release | 6.73 (6.73..7.57) | 4.48 (4.48..4.84) | -33% | 1,144 -> 272 | same |
| call FirstOfDates(46164.0) | 7.00 (7.00..9.23) | 4.66 (4.66..5.42) | -33% | 1,144 -> 568 | same |
| _numbers(5.0) scalar -> 1x1 | 1.04 (1.04..1.21) | 1.05 (1.05..2.08) | +1% | 216 -> 216 | same |
| _mixed(5.0) scalar -> 1x1 | 2.52 (2.52..2.77) | 2.60 (2.60..5.05) | +3% | 313 -> 313 | same |
| _mixed('x') scalar -> 1x1 | 2.64 (2.64..2.82) | 2.66 (2.66..5.23) | +1% | 313 -> 313 | same |
| call SumArray(5.0) | 3.70 (3.70..6.06) | 3.84 (3.84..6.70) | +4% | 376 -> 376 | same |
| call CountMixed(5.0) | 4.43 (4.43..7.43) | 4.45 (4.45..7.89) | +1% | 473 -> 473 | same |
| _cell flat 2 | 1.08 (1.08..1.08) | 1.10 (1.10..1.11) | +2% | 2,656 -> 2,656 | same |
| _cell flat 5001 | 1.07 (1.07..1.08) | 1.09 (1.09..1.10) | +2% | 2,656 -> 2,656 | same |
| _cell flat 9999 | 1.15 (1.15..1.16) | 1.15 (1.15..1.28) | +0% | 2,656 -> 2,656 | same |
| _cell flat 9996 | 4.32 (4.32..7.64) | 4.35 (4.35..4.49) | +0% | 10,285 -> 10,285 | same |
