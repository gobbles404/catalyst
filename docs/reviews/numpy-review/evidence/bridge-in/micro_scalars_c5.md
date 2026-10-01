micro: micro_scalars.py; as-is scratch/verify/bridge-in/trees/c5base/src vs proposed scratch/verify/bridge-in/trees/c5/src; 5 rounds, least of 7 repeats
| operation | as-is us (spread) | proposed us (spread) | change | peak B as-is -> proposed | numpy calls as-is -> proposed |
|---|---:|---:|---:|---:|---|
| _date(46164.0) | 0.69 (0.69..1.23) | 0.69 (0.69..0.73) | +0% | 64 -> 64 | same |
| _dates(46164.0) scalar -> 1x1 | 1.60 (1.60..2.87) | 1.59 (1.59..1.90) | -0% | 408 -> 408 | same |
| call _CreateValuationDate(46276.0, 0.5) + release | 4.42 (4.42..7.10) | 4.33 (4.33..5.38) | -2% | 272 -> 272 | same |
| call FirstOfDates(46164.0) | 4.63 (4.63..7.52) | 4.76 (4.76..8.25) | +3% | 568 -> 568 | same |
| _numbers(5.0) scalar -> 1x1 | 1.04 (1.04..1.97) | 0.77 (0.77..1.57) | -25% | 216 -> 152 | numpy.array: 1->0; numpy.empty: 0->1 |
| _mixed(5.0) scalar -> 1x1 | 2.48 (2.48..4.15) | 1.99 (1.99..4.65) | -20% | 313 -> 257 | numpy.array: 2->0; numpy.empty: 0->2 |
| _mixed('x') scalar -> 1x1 | 2.56 (2.56..4.83) | 2.11 (2.11..4.26) | -17% | 313 -> 257 | numpy.array: 2->0; numpy.empty: 0->2 |
| call SumArray(5.0) | 3.62 (3.62..5.94) | 3.26 (3.26..5.99) | -10% | 376 -> 312 | numpy.array: 1->0; numpy.empty: 0->1 |
| call CountMixed(5.0) | 4.43 (4.43..4.77) | 3.72 (3.72..4.07) | -16% | 473 -> 449 | numpy.array: 2->0; numpy.empty: 0->2 |
| _cell flat 2 | 1.06 (1.06..1.11) | 1.08 (1.08..1.15) | +2% | 2,656 -> 2,656 | same |
| _cell flat 5001 | 1.08 (1.08..1.14) | 1.07 (1.07..1.14) | -1% | 2,656 -> 2,656 | same |
| _cell flat 9999 | 1.13 (1.13..1.27) | 1.15 (1.15..1.20) | +1% | 2,656 -> 2,656 | same |
| _cell flat 9996 | 4.27 (4.27..5.32) | 4.24 (4.24..4.69) | -1% | 10,285 -> 10,285 | same |
