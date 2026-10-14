"""A template's row or a ticket's rows, bound to an instrument's fields and typed once at the seam:
the record a creator receives for an argument declared `FieldRow[S]` or `FieldRows[S]`, and the
one way the seam asks the library which instrument a selector names. The seam imports this; the
library never imports the seam. docs/seam/inputs.md decision 42 is the contract."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import singledispatch
from typing import cast

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.kind import named
from goosedove.instruments.definitions import Field, Instrument, instrument


@dataclass(frozen=True, slots=True)
class FieldValues:
    """The fields a sheet supplied under one instrument, each column typed by the field's type as
    the seam checked it: instrument, the definition the headers were matched against; rows, one
    for a template and one or more for a ticket; names, the fields present, in the sheet's column
    order, each once, every one a field of the instrument; and columns, by field name, each the
    seam's typed column, numbers as a float64 array, dates as a datetime64[D] array, text and
    codes as a tuple of text, and a handle field as a tuple of the objects the handles stood for,
    one per row. A field absent from names was not supplied; a blank cell never arrives, since
    the seam refused it. The accessors read a column by its name as the type the definition gave
    it; nothing here checks a value's meaning, which is the creator's to check."""

    instrument: Instrument
    rows: int
    names: tuple[str, ...]
    columns: Mapping[str, object]

    def has(self, name: str) -> bool:
        return name in self.columns

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
