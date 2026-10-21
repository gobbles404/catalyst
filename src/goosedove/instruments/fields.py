"""A template's row or a ticket's rows, bound to an instrument's fields and typed once at the seam:
the record a creator receives for an argument declared `FieldRow[S]` or `FieldRows[S]`, and the
one way the seam asks the library which instrument a selector names. The seam imports this; the
library never imports the seam. docs/seam/inputs.md decision 42 is the contract."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import singledispatch
from types import MappingProxyType
from typing import Final, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.kind import named
from goosedove.instruments.definitions import Field, Instrument, instrument


@dataclass(frozen=True, slots=True)
class DatesOrTexts:
    """A column whose cells hold a date or a text, each told apart by type once and never by
    reading, since payment-day-date-or-rule.md: is_date, over the rows in row order, True where
    the row holds a date; dates, the days of those rows in row order; texts, the texts of the
    other rows in row order. The seam's typed column for a field of that type on the way in,
    the record a batch keeps of what its rows entered, and a readback's column of the same
    shape on the way out, a date a date and a text a text."""

    is_date: NDArray[np.bool_]
    dates: NDArray[np.datetime64]
    texts: tuple[str, ...]

    @classmethod
    def of_texts(cls, texts: tuple[str, ...]) -> "DatesOrTexts":
        """Every row a text."""
        return cls(np.zeros(len(texts), dtype=bool), np.empty(0, dtype="datetime64[D]"), texts)

    @classmethod
    def of_dates(cls, dates: NDArray[np.datetime64]) -> "DatesOrTexts":
        """Every row a date."""
        return cls(np.ones(dates.size, dtype=bool), dates, ())


# No field with cells left unsupplied: the record of a body whose every cell holds a value, and
# the default a Python caller takes when it builds the record with full columns.
NO_MASKS: Final[Mapping[str, NDArray[np.bool_]]] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class FieldValues:
    """The fields a sheet supplied under one instrument, each column typed by the field's type as
    the seam checked it: instrument, the definition the headers were matched against; rows, one
    for a template and one or more for a ticket; names, the fields present, in the sheet's column
    order, each once, every one a field of the instrument; columns, by field name, each the
    seam's typed column, numbers as a float64 array, dates as a datetime64[D] array, text and
    codes as a tuple of text, a handle field as a tuple of the objects the handles stood for,
    one per row, and a field of a date or a text as the DatesOrTexts record above, since
    payment-day-date-or-rule.md; and supplied, since #172, by the name of each present field
    whose definition lets a cell go unsupplied, a read-only mask over the rows, True where the
    row holds a value,
    the field's column then holding the values of those rows alone, in row order, so that a
    row's absence is a fact beside the values and never a sentinel among them. A field absent
    from names was not supplied by any row; a blank cell of any other field never arrives, since
    the seam refused it. The accessors read a column by its name as the type the definition gave
    it; nothing here checks a value's meaning, which is the creator's to check."""

    instrument: Instrument
    rows: int
    names: tuple[str, ...]
    columns: Mapping[str, object]
    supplied: Mapping[str, NDArray[np.bool_]] = NO_MASKS

    def has(self, name: str) -> bool:
        return name in self.columns

    def supplied_rows(self, name: str) -> NDArray[np.bool_]:
        """Which rows supplied a present field: the seam's mask for a field whose cells may go
        unsupplied, and every row for any other, as for a record a Python caller built with full
        columns."""
        mask = self.supplied.get(name)
        return np.ones(self.rows, dtype=bool) if mask is None else mask

    def field(self, name: str) -> Field:
        """The definition of a field present, by its name."""
        return next(field for field in self.instrument.fields if field.name == name)

    def numbers(self, name: str) -> NDArray[np.float64]:
        return cast(NDArray[np.float64], self.columns[name])

    def dates(self, name: str) -> NDArray[np.datetime64]:
        return cast(NDArray[np.datetime64], self.columns[name])

    def texts(self, name: str) -> tuple[str, ...]:
        return cast(tuple[str, ...], self.columns[name])

    def objects(self, name: str) -> tuple[object, ...]:
        return cast(tuple[object, ...], self.columns[name])

    def dates_or_texts(self, name: str) -> DatesOrTexts:
        return cast(DatesOrTexts, self.columns[name])


@singledispatch
def selected(selector: object) -> Instrument:
    """The instrument a selector argument names, read off the value the seam validated: an
    instrument's name as text, matched exactly against the catalog, or the instrument a trade
    template holds. The kinds that select register themselves here, text in this module and
    the template in its own, as the market's binders do by fixings kind; registration asks
    only that a selector be text or a handle kind, so a kind with no rule here fails on the
    call, saying it selects no instrument."""
    raise ValueError(f"{named(selector)} selects no instrument")


@selected.register
def by_name(selector: str) -> Instrument:
    """An instrument named as text, the form _CreateTradeTemplate takes."""
    return instrument(selector)
