"""The sheet's calendar, as the seam holds it: serial 61, 1 March 1900, the first day Excel's
serials and the real calendar agree on, to serial 2958465, 31 December 9999, the last day a cell
can show. A day outside it could never reach a cell, so a library rule that makes a day for the
sheet holds it to these two, each where it is made: a payment day where the lag is read and
where the day is counted, a shifted date where the shift is made. docs/seam/inputs.md states the
calendar for the seam; this is the library's one copy of its two ends."""

from typing import Final

import numpy as np

SHEET_FIRST_DAY: Final = np.datetime64("1900-03-01", "D")
SHEET_LAST_DAY: Final = np.datetime64("9999-12-31", "D")
