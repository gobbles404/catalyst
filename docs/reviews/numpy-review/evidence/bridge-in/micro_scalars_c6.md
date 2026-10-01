micro: micro_scalars.py; as-is scratch/verify/bridge-in/trees/c5/src vs proposed scratch/verify/bridge-in/trees/c6/src; 5 rounds, least of 7 repeats
| operation | as-is us (spread) | proposed us (spread) | change | peak B as-is -> proposed | numpy calls as-is -> proposed |
|---|---:|---:|---:|---:|---|
| _date(46164.0) | 0.69 (0.69..1.37) | 0.69 (0.69..0.81) | +0% | 64 -> 64 | same |
| _dates(46164.0) scalar -> 1x1 | 1.63 (1.63..3.46) | 1.58 (1.58..1.86) | -3% | 408 -> 408 | same |
| call _CreateValuationDate(46276.0, 0.5) + release | 4.36 (4.36..7.47) | 4.41 (4.41..4.97) | +1% | 272 -> 272 | same |
| call FirstOfDates(46164.0) | 4.54 (4.54..8.15) | 4.59 (4.59..9.10) | +1% | 568 -> 568 | same |
| _numbers(5.0) scalar -> 1x1 | 0.80 (0.80..1.45) | 0.80 (0.80..1.48) | +0% | 152 -> 152 | same |
| _mixed(5.0) scalar -> 1x1 | 1.99 (1.99..3.55) | 1.95 (1.95..3.56) | -2% | 257 -> 257 | same |
| _mixed('x') scalar -> 1x1 | 2.15 (2.15..3.97) | 2.11 (2.11..2.34) | -2% | 257 -> 257 | same |
| call SumArray(5.0) | 3.37 (3.37..5.01) | 3.29 (3.29..3.59) | -3% | 312 -> 312 | same |
| call CountMixed(5.0) | 3.82 (3.82..6.80) | 3.92 (3.92..4.07) | +3% | 449 -> 449 | same |
| _cell flat 2 | 1.10 (1.10..2.89) | 0.79 (0.79..1.23) | -28% | 2,656 -> 0 | ndarray.item: 0->2 |
| _cell flat 5001 | 1.08 (1.08..1.18) | 0.81 (0.81..1.15) | -25% | 2,656 -> 0 | ndarray.item: 0->2 |
| _cell flat 9999 | 1.16 (1.16..1.21) | 0.89 (0.89..1.53) | -24% | 2,656 -> 0 | ndarray.item: 0->2 |
| _cell flat 9996 | 4.39 (4.39..5.99) | 4.12 (4.12..5.06) | -6% | 10,285 -> 10,285 | ndarray.item: 0->1 |
