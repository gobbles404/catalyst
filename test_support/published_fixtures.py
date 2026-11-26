"""Published indexes of one print a month for tests: the shape of a monthly index such as
Inside FERC's, whose month is one price. Fixings are entered by publication date, and a test that
thinks in months names them by code through here.
"""

from collections.abc import Sequence
from typing import cast

import numpy as np
from numpy.typing import NDArray

from catalyst.excel.bridge import Cells
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.published_schedule import PublishedSchedule
from catalyst.market_data.published_fixings import PublishedFixings, published_fixings

EXCEL_EPOCH = np.datetime64("1899-12-30", "D")


def publication_dates(codes: Sequence[str], index: Index) -> NDArray[np.datetime64]:
    """The publication date of each of those months of an index of one print a month, in the
    order given."""
    schedule = cast(PublishedSchedule, index.schedule)
    rows = np.array([schedule.codes.index(code) for code in codes], dtype=np.intp)
    return schedule.publication_date[np.searchsorted(schedule.contract, rows)]


def fixings_by_code(
    codes: Sequence[str], prices: NDArray[np.float64], index: Index
) -> PublishedFixings:
    """The fixings of an index of one print a month, each named by its month's code: made by the
    library's one way, on the dates the index's schedule gives those months."""
    return published_fixings(publication_dates(codes, index), prices, index)


def serial_column(days: NDArray[np.datetime64]) -> Cells:
    """Those days as the sheet enters them, one column of Excel date serials."""
    serials = (days - EXCEL_EPOCH).astype(np.float64)
    return Cells.from_rows([[float(serial)] for serial in serials])
